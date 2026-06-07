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
    """이름이 특정 모델 인스턴스인가(개념 아님). 정확/버전 매칭 — 부분문자열 아님."""
    return bool(_MODEL_RE.match(name.strip().lower()))


# 일반 원시어 차단(결정적). 메서드를 분해한 구성 동작/원시 개념(act/reasoning/thought 등)은
# 명명된 메서드가 아니라 노드로 부적합. 프롬프트가 'reasoning processes' 류 제외를
# 지시하지만 가끔 단독으로 샌다(실측: 'Act' 11섹션 중 1). 정확매칭이라 'ReAct'·
# 'thought generator'·'Tree of Thoughts' 같은 진짜 개념은 안 건드림.
_GENERIC_PRIMITIVES = frozenset({
    "act", "action", "acting", "observation", "observe",
    "reasoning", "reason", "thought", "thoughts",
})


def is_noise_concept(name: str) -> bool:
    """노드로 부적합한 추출 노이즈(모델 인스턴스 + 일반 원시어)."""
    return is_model_instance(name) or name.strip().lower() in _GENERIC_PRIMITIVES


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
        kept = [c for c in concepts if not is_noise_concept(c["name"])]
        dropped += [c["name"] for c in concepts if is_noise_concept(c["name"])]
        all_concepts.extend(kept)
        print(f"  [{i:2}] {summaries[i]['heading'][:40]:42} 개념 {len(kept)}개"
              + (f"  (노이즈 {len(concepts)-len(kept)} 제거)" if len(kept) != len(concepts) else ""))
    if dropped:
        print(f"\n  노이즈 필터 제거(모델/원시어): {dropped}")

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
