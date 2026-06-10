"""수집 에이전트 1/5 — [1] 의도 파싱 + [2] 현황 확인 스모크.

문장 -> {topic, period, related_nodes} -> [2.5] 해석 확인 문장 출력.
실행: uv run python agent_collect.py
"""
import json
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()
MODEL = "gpt-5.4-mini"

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


def load_node_embeddings():
    store = json.loads(Path("data/outputs/node_embeddings.json").read_text())
    norm = json.loads(Path("data/outputs/normalized.json").read_text())["nodes"]
    keys = list(store["vectors"].keys())
    mat = np.array([store["vectors"][k] for k in keys], dtype=np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True)  # 정규화
    canon = {k: norm[k]["canonical"] for k in keys if k in norm}
    return store["model"], keys, mat, canon


def match_nodes(topic, model, keys, mat, canon, top=10):
    qv = client.embeddings.create(model=model, input=[topic]).data[0].embedding
    q = np.array(qv, dtype=np.float32)
    q /= np.linalg.norm(q)
    sims = mat @ q  # 코사인 (둘 다 정규화됨)
    order = np.argsort(-sims)[:top]
    return [(canon.get(keys[i], keys[i]), float(sims[i])) for i in order]


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


def confirm_message(intent):
    period = ""
    if intent.get("period_from") or intent.get("period_to"):
        period = f" / 기간: {intent.get('period_from') or '처음'} ~ {intent.get('period_to') or '현재'}"
    held = ", ".join(intent["related_nodes"]) if intent["related_nodes"] else "(이 주제 보유 노드 없음)"
    reasons = f" — {intent['node_reasons']}" if intent.get("node_reasons") and intent["related_nodes"] else ""
    return (
        f"이렇게 이해했어 — {intent['topic_kr']} ({intent['topic']}){period}\n"
        f"  해석: {intent.get('interpretation', '')}\n"
        f"  현재 보유: {held}{reasons}\n"
        f"  이 방향으로 찾을까?"
    )


SMOKE = [
    "2024년 RAG 강건성 논문 가져와줘",
    "멀티에이전트 협업 관련 최신 논문 수집해줘",
    "2023년부터 작년까지 LLM 평가 벤치마크 논문",
    "knowledge graph 만드는 논문들 찾아와",
]

if __name__ == "__main__":
    model, keys, mat, canon = load_node_embeddings()
    print(f"노드 임베딩 {len(keys)}개 로드 (model={model})\n")
    for q in SMOKE:
        intent = parse_intent(q)
        matches = match_nodes(intent["topic"], model, keys, mat, canon)
        print(f'"{q}"')
        print(f"  topic: {intent['topic']}")
        print(f"  해석: {intent.get('interpretation','')[:100]}...")
        print(f"  유사 노드(상위 10, 점수순):")
        for name, score in matches:
            print(f"    {score:.3f}  {name}")
        print()
