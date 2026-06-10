"""수집 에이전트 (전환 4/4) — 의도 파싱 → 현황(개념+논문 두 각도) → 현황 보고 + 충분성 추천.

v2 이중 노드 임베딩(node_embeddings_v2.json) 위에서 동작.
- 개념 매칭(definition): "이 주제 관련 기법이 뭐 있나".
- 논문 매칭(problem): "같은 문제를 다룬 논문이 뭐 있나" (세렌디피티 씨앗).
arXiv 실제 수집/승인/분기는 다음 조각. 이번은 현황 보고까지만.

실행: uv run python agent_collect.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = "gpt-5.4-mini"
EMBED_MODEL = "text-embedding-3-small"

INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_intent",
        "description": "수집 명령의 의도를 구조화해 보고한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "수집 주제, 영어 연구용어로 (예: RAG robustness to retrieval noise)"},
                "topic_kr": {"type": "string", "description": "주제를 해석한 한국어 한 줄. 입력 문장을 복사하지 말고, 어떤 연구 주제로 이해했는지 풀어쓴다 (예: '검색된 문서에 노이즈가 섞여도 답변 품질을 유지하는 RAG 기법')"},
                "interpretation": {"type": "string", "description": "이 주제의 가능한 갈래들과 그중 어느 갈래로 좁혔는지 2~3문장. 모호한 부분이 있으면 명시 (예: '강건성은 검색 노이즈/적대적 공격/분포 변화로 갈리는데, RAG 맥락에선 보통 검색 노이즈를 뜻하므로 그쪽으로 해석')"},
                "period_from": {"type": "string", "description": "YYYY-MM. 명시 없으면 빈 문자열"},
                "period_to": {"type": "string", "description": "YYYY-MM. 명시 없으면 빈 문자열"},
            },
            "required": ["topic", "topic_kr", "interpretation"],
        },
    },
}


# --- 임베딩 로더 (v2, 타입 분리) ---
def load_embeddings():
    """node_embeddings_v2.json -> 타입별(개념/논문) 정규화 행렬로 분리.

    반환: model, norm(v2 nodes dict), (concept_keys, concept_mat), (paper_keys, paper_mat)
    """
    store = json.loads(Path("data/outputs/node_embeddings_v2.json").read_text())
    norm = json.loads(Path("data/outputs/normalized_v2.json").read_text())["nodes"]
    model = store["model"]

    def build(prefix):
        keys = [k for k in store["vectors"] if k.startswith(prefix)]
        if not keys:
            return [], None
        mat = np.array([store["vectors"][k] for k in keys], dtype=np.float32)
        mat /= np.linalg.norm(mat, axis=1, keepdims=True)
        return keys, mat

    return model, norm, build("concept:"), build("paper:")


# --- 두 각도 매칭 ---
def embed_query(topic, model):
    qv = client.embeddings.create(model=model, input=[topic]).data[0].embedding
    q = np.array(qv, dtype=np.float32)
    return q / np.linalg.norm(q)


def match(q, keys, mat, top=8, floor=0.30):
    """topic 벡터와 코사인 유사. floor 미만은 컷, 상위 top개만."""
    if mat is None:
        return []
    sims = mat @ q  # 코사인 (둘 다 정규화됨)
    order = np.argsort(-sims)[:top]
    return [(keys[i], float(sims[i])) for i in order if sims[i] >= floor]


def parse_intent(text):
    system = (
        "너는 논문 수집 에이전트의 의도 파싱기다. 사용자의 수집 명령을 report_intent로 보고한다. "
        "topic은 arXiv 검색에 쓸 영어 연구용어로, interpretation은 주제의 가능한 갈래와 좁힌 방향을 적는다."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
        tools=[INTENT_TOOL],
        tool_choice={"type": "function", "function": {"name": "report_intent"}},
    )
    return json.loads(resp.choices[0].message.tool_calls[0].function.arguments)


# --- 현황 보고 + 충분성 추천 (LLM 1회) ---
REPORT_SYSTEM = (
    "너는 논문 수집 에이전트의 현황 분석가다. 주어진 수집 주제에 대해, 이미 보유한 "
    "관련 기법(개념)과 같은 문제를 다룬 논문을 사람이 읽기 좋게 풀어 설명하고, "
    "이 주제가 현재 그래프에 얼마나 덮여 있는지 종합 판정과 충분성 추천을 낸다.\n"
    "아래 구조 그대로(한국어)로만 출력한다:\n"
    "  관련 기법(개념):\n"
    "  • <이름> — <이 주제 관점에서 한 줄 풀이> (<점수>)\n"
    "  같은 문제를 다룬 논문:\n"
    "  • <제목> — <problem 한 줄 요약> (<점수>)\n"
    "  종합: <어느 측면이 덮였고 어디가 비었나 1~2문장>\n"
    "  추천: <충분 | 부분적(수집 권장) | 비어있음(수집 강력 권장)> — <한 줄 근거>\n"
    "규칙: 단순 나열이 아니라 주제 관점의 풀이를 쓴다. 정의 미보유 개념은 '정의 미보유'로 짧게 적는다. "
    "점수는 괄호로 작게 병기하되 사람 문장이 주가 되게 한다. 추천은 세 등급 중 하나만 고른다. "
    "후보가 비었으면 솔직히 비었다고 적고 추천에 반영한다."
)


def _concept_line(key, score, norm):
    n = norm.get(key, {})
    name = n.get("canonical", key.split(":", 1)[-1])
    definition = (n.get("definition") or "").strip()
    if n.get("def_status") == "placeholder" or not definition:
        return f"- {name} (정의 미보유) [{score:.2f}]"
    return f"- {name}: {definition} [{score:.2f}]"


def _paper_line(key, score, norm):
    n = norm.get(key, {})
    title = n.get("title", key.split(":", 1)[-1])
    problem = (n.get("problem") or "").strip() or "(문제 설명 없음)"
    return f"- {title} — {problem} [{score:.2f}]"


def build_status_report(intent, cm_hits, pm_hits, norm):
    concepts = "\n".join(_concept_line(k, s, norm) for k, s in cm_hits) or "(매칭된 개념 없음)"
    papers = "\n".join(_paper_line(k, s, norm) for k, s in pm_hits) or "(매칭된 논문 없음)"
    user = (
        f"수집 주제: {intent['topic']} — {intent.get('topic_kr', '')}\n"
        f"해석: {intent.get('interpretation', '')}\n\n"
        f"[보유 개념 후보 — definition 매칭]\n{concepts}\n\n"
        f"[같은 문제 논문 후보 — problem 매칭]\n{papers}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


SMOKE = [
    "2024년 RAG 강건성 논문 가져와줘",
    "knowledge graph 만드는 논문들 찾아와",
    "멀티에이전트 협업 관련 최신 논문 수집해줘",
]


if __name__ == "__main__":
    model, norm, (ck, cm), (pk, pm) = load_embeddings()

    # --- 하드 게이트: 데이터 정합성 (깨지면 비정상 종료) ---
    try:
        assert model == EMBED_MODEL, f"model 불일치: {model}"
        assert len(ck) == 73, f"개념 임베딩 73 기대, 실제 {len(ck)}"
        assert len(pk) == 68, f"논문 임베딩 68 기대, 실제 {len(pk)}"
    except AssertionError as e:
        print(f"게이트 실패: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"게이트 통과: 개념 {len(ck)} + 논문 {len(pk)} (model={model})\n")

    for query in SMOKE:
        intent = parse_intent(query)
        q = embed_query(intent["topic"], model)
        cm_hits = match(q, ck, cm)   # [(concept:key, score)]
        pm_hits = match(q, pk, pm)   # [(paper:key, score)]
        report = build_status_report(intent, cm_hits, pm_hits, norm)  # LLM 1회
        print(f'"{query}"\n  topic: {intent["topic"]}')
        print(report)
        print()
