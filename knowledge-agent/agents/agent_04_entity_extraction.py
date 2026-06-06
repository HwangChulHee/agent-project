import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from agents.prompts.entity_extraction import SYSTEM

load_dotenv()

MODEL = "gpt-4o-mini"
SUMMARIES_PATH = "data/parsed/2210.03629/2210.03629_03.summaries.json"
OUT_PATH = "data/parsed/2210.03629/2210.03629_04.concepts.json"
SMOKE_INDICES = [1, 9]  # ABSTRACT / RELATED WORK

client = OpenAI()


def extract_one(summary_text: str) -> list:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": summary_text}],
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


def run(full: bool):
    with open(SUMMARIES_PATH, encoding="utf-8") as f:
        summaries = json.load(f)

    indices = range(len(summaries)) if full else SMOKE_INDICES
    all_concepts = []
    for i in indices:
        concepts = extract_one(summaries[i]["summary"])
        all_concepts.extend(concepts)
        print(f"  [{i:2}] {summaries[i]['heading'][:40]:42} 개념 {len(concepts)}개")

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

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="전체 실행 (없으면 스모크)")
    run(ap.parse_args().run)
