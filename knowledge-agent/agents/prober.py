"""
프로빙 에이전트 — 개념 하나에 대해 질문 생성 → 답 받기 → 채점 → mastery 갱신.
LLM: 질문+루브릭 생성, CoT 채점(5등분). 갱신: 부드러운 수렴.
"""
import json
import os
from datetime import date
from dotenv import load_dotenv
from openai import OpenAI
from kb.store import load_map, save_map, get_node

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

ALPHA = 0.7                              # 옛값 유지 비율 (부드러운 수렴)
LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]     # 5등분

Q_PROMPT = """너는 LLM/에이전트 연구 분야의 출제자다.
개념 "{concept}"에 대한 이해도를 측정할 서술형 질문 1개와 채점 루브릭을 만든다.

원칙:
- 재려는 것은 '에세이 완성도'가 아니라 '핵심 메커니즘을 이해하는가'다.
- 질문은 그 개념의 작동 방식을 묻는다 (정의 암송이 아니라).
- 핵심 요소(elements)는 '이해의 증거'가 되는 기술적 포인트로 한다.
  형식적 요소(예시 제시, 중요성 서술)는 넣지 마라.
- 핵심 메커니즘을 정확히 짚으면 예시나 미사여구가 없어도 만점이다.

JSON으로만:
{{"question": "...",
  "elements": ["핵심 메커니즘 포인트1", "포인트2"],
  "full_mark": "핵심 메커니즘을 정확히 짚은 답",
  "zero_mark": "메커니즘을 전혀 모르는 답"}}"""

G_PROMPT = """너는 채점자다. 아래 답을 루브릭으로 채점한다.

질문: {question}
핵심 요소: {elements}
만점 답: {full_mark}
빵점 답: {zero_mark}

사용자 답: {answer}

채점 원칙:
- 먼저 답이 '맞힌' 요소를 인정하라. 빠진 것부터 세지 마라.
- 핵심 메커니즘을 정확히 짚었으면, 표현이 거칠거나 예시가 없어도 높은 점수를 줘라.
- 핵심 요소 중 대부분을 맞히면 0.75 이상, 절반이면 0.5, 핵심을 짚었으나 부정확하면 0.25.
- 형식(에세이다움, 예시 유무)으로 깎지 마라. 이해도만 본다.

먼저 맞힌 요소와 놓친 요소를 분석하고, 그다음 0.0~1.0 점수를 매겨라.
JSON으로만:
{{"reasoning": "분석...", "score": 0.0}}"""


def make_question(concept):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": Q_PROMPT.format(concept=concept)}],
        response_format={"type": "json_object"}, temperature=0.3,
    )
    return json.loads(resp.choices[0].message.content)


def get_user_answer(question):
    """답 받는 부분 — 한 곳으로 모음 (나중에 합성 사용자로 교체 가능)."""
    print(f"\n[질문] {question}")
    return input("[답] ")


def grade(q, answer):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": G_PROMPT.format(
            question=q["question"], elements=q["elements"],
            full_mark=q["full_mark"], zero_mark=q["zero_mark"], answer=answer)}],
        response_format={"type": "json_object"}, temperature=0,
    )
    r = json.loads(resp.choices[0].message.content)
    raw = float(r.get("score", 0))
    r["score"] = min(LEVELS, key=lambda x: abs(x - raw))  # 5등분 snap
    return r


def update_mastery(old, score):
    return ALPHA * old + (1 - ALPHA) * score


def probe_concept(m, concept_id):
    node = get_node(m, concept_id)
    if node is None:
        print(f"'{concept_id}' 노드가 맵에 없음")
        return
    old = node["mastery"]

    q = make_question(concept_id)
    answer = get_user_answer(q["question"])
    result = grade(q, answer)

    new = update_mastery(old, result["score"])
    node["mastery"] = new
    node["last_touched"] = date.today().isoformat()

    print(f"\n[채점 근거] {result['reasoning']}")
    print(f"[점수] {result['score']}  (요소: {q['elements']})")
    print(f"[mastery] {old:.3f} → {new:.3f}")


if __name__ == "__main__":
    m = load_map()
    probe_concept(m, "리랭킹")   # 프론티어 1순위를 프로빙
    save_map(m)
