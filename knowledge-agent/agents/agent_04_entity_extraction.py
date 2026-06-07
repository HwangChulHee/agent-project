import re
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from agents.prompts.entity_extraction import SYSTEM
from agents.paths import paper_paths

load_dotenv()

MODEL = "gpt-4o-mini"
SMOKE_INDICES = [1, 9]  # ABSTRACT / RELATED WORK

client = OpenAI()

# 모델 인스턴스 차단(결정적). 프롬프트가 제외를 지시하지만, 실험 섹션처럼 모델이
# "주어"로 등장하면 LLM이 규칙을 무시하고 뽑는다(실측: §4 Experiments에서 'GPT-4'
# 2/2 누출). → 추출 후 규칙으로 거른다. 프롬프트가 이미 열거한 모델군을 결정적으로 강제.
_MODEL_FAMILIES = ("gpt", "chatgpt", "instructgpt", "palm", "llama", "lamda",
                   "gopher", "chinchilla", "opt", "bloom", "codex", "t5",
                   "bert", "roberta", "claude", "gemini", "mistral", "falcon",
                   "qwen", "vicuna", "alpaca", "flan")
# 단독 모델군 이름, 또는 'gpt-4'/'gpt-3.5'/'palm-540b'/'llama-2-70b' 같은 버전·파라미터 변형.
_MODEL_RE = re.compile(
    r"^(?:" + "|".join(_MODEL_FAMILIES) + r")(?:[-\s]?\d[\w.\-]*)?$")


def is_model_instance(name: str) -> bool:
    """이름이 특정 모델 인스턴스인가(개념 아님). 정확/버전 매칭 — 부분문자열 아님.
    모델군은 유한·알려짐 + 프롬프트가 이미 열거 → 결정적 강제(하드코딩 허용 케이스).
    cf) 일반 원시어/개념성 판단은 단어 리스트로 박지 않고 '코퍼스 재등장'으로 풀 예정
    (WORKLOG 열린 설계). 'Act'류 드문 노이즈는 그때까지 감수."""
    return bool(_MODEL_RE.match(name.strip().lower()))


def extract_one(summary_text: str, heading: str = "") -> list:
    # heading을 함께 넘긴다 — 프롬프트가 "이 섹션의 주개념 vs 스쳐가는 개념"을
    # 구분해 성질을 엉뚱한 개념에 귀속하지 않도록(주어 귀속 가드).
    user = f"Section heading: {heading}\n\nSummary:\n{summary_text}" if heading else summary_text
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("concepts", [])


def group(concepts: list) -> list:
    """같은 이름(소문자) 묶기. 정의는 버리지 않고 리스트로 모음.
    선택(어느 정의가 최선)은 align이 시드맵과의 거리로 판단."""
    grouped = {}
    for c in concepts:
        key = c["name"].strip().lower()
        definition = (c.get("definition") or "").strip()
        if key not in grouped:
            grouped[key] = {"name": c["name"].strip(), "definitions": []}
        if definition and definition not in grouped[key]["definitions"]:
            grouped[key]["definitions"].append(definition)
    return list(grouped.values())


def run(paper: str, full: bool):
    P = paper_paths(paper)
    with open(P["03"], encoding="utf-8") as f:
        summaries = json.load(f)

    indices = range(len(summaries)) if full else SMOKE_INDICES
    all_concepts, dropped = [], []
    for i in indices:
        concepts = extract_one(summaries[i]["summary"], summaries[i].get("heading", ""))
        kept = [c for c in concepts if not is_model_instance(c["name"])]
        dropped += [c["name"] for c in concepts if is_model_instance(c["name"])]
        all_concepts.extend(kept)
        print(f"  [{i:2}] {summaries[i]['heading'][:40]:42} 개념 {len(kept)}개"
              + (f"  (모델인스턴스 {len(concepts)-len(kept)} 제거)" if len(kept) != len(concepts) else ""))
    if dropped:
        print(f"\n  모델 인스턴스 필터 제거: {dropped}")

    grouped = group(all_concepts)
    multi = sum(1 for c in grouped if len(c["definitions"]) > 1)
    print(f"\n원시 {len(all_concepts)}개 → 그룹화 {len(grouped)}개 "
          f"(정의 여러 개인 개념 {multi}개)")

    if not full:
        print("\n=== 그룹화된 개념 (스모크) ===")
        for c in grouped:
            print(f"  - {c['name'][:28]:30} 정의 {len(c['definitions'])}개")
        print("\n=== SMOKE 끝 — 형식 OK면 `--run`으로 전체 ===")
        return

    with open(P["04"], "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {P['04']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--run", action="store_true", help="전체 실행 (없으면 스모크)")
    args = ap.parse_args()
    run(args.paper, args.run)
