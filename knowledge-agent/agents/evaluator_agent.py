"""
가치 판정 — arXiv 논문을 현재 맵에 비춰 분류.
확장/새영역/모순/무관/중복 + 가치점수(0~1) + 근거.
인용수 무관, 오직 '내 맵과의 관계'로 판정. 맵에 쓰지 않음(판정만).
"""
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from kb.store import load_map
from agents.collectors.arxiv import fetch

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"
LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]

JUDGE_PROMPT = """너는 개인 지식 시스템의 가치 판정기다.
사용자의 지식 맵에 비춰, 새 논문이 '읽을 가치'가 있는지 판정한다.

[사용자가 아는 개념 (mastery 0~1)]
{known}

[사용자 분야]
LLM 에이전트 (RAG/검색, 메모리, 플래닝, 도구사용, 멀티에이전트, 평가 등)

[새 논문]
제목: {title}
초록: {abstract}

판정 카테고리(category) 하나를 고른다:
- extend: 사용자가 아는 개념을 넓히거나 깊게 함
- new: 맵에 없지만 사용자 분야 안의 새 개념 (묻힌 보석 후보)
- contradict: 사용자가 믿을 만한 것과 충돌하는 주장
- known: 사용자가 이미 잘 아는 것의 반복
- irrelevant: 사용자 분야 밖이거나 무관 (예: 비전·로보틱스·하드웨어)

가치점수(value) 0~1: irrelevant/known은 낮게, new/extend는 높게, contradict는 최상.

먼저 맵과의 관계를 분석하고, 그다음 판정하라. JSON으로만:
{{"reasoning": "...", "category": "...", "value": 0.0,
  "related_concepts": ["맵에서 관련된 개념들"]}}"""


def map_summary(m):
    """맵을 판정용 요약으로 — 개념: mastery 목록."""
    return ", ".join(f"{cid}({n['mastery']})" for cid, n in m["nodes"].items())


def judge_paper(m, paper):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(
            known=map_summary(m), title=paper["title"], abstract=paper["text"])}],
        response_format={"type": "json_object"}, temperature=0,
    )
    r = json.loads(resp.choices[0].message.content)
    raw = float(r.get("value", 0))
    r["value"] = min(LEVELS, key=lambda x: abs(x - raw))
    return r


if __name__ == "__main__":
    m = load_map()
    papers = fetch(max_results=8)
    print(f"{len(papers)}개 논문 판정\n")

    results = []
    for p in papers:
        r = judge_paper(m, p)
        results.append((p, r))

    # 가치 높은 순 정렬
    results.sort(key=lambda x: x[1]["value"], reverse=True)
    for p, r in results:
        print(f"[{r['value']}] {r['category']:11} {p['title'][:55]}")
        print(f"          관련: {r.get('related_concepts', [])}")
        print(f"          근거: {r['reasoning'][:90]}...")
        print()
