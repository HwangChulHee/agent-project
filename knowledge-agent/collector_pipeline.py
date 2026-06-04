"""
Collector 파이프라인 — KARMA 흐름을 잇는 orchestrator.
fetch(Ingestion) → judge(Evaluator) → [통과] → extract(Entity) → align(Schema) → 맵 통합.
새 로직 최소, 기존 부품 조율.
"""
from kb.store import load_map, save_map, find_gaps
from agents.collectors.arxiv import fetch
from agents.evaluator_agent import judge_paper
from agents.entity_extraction_agent import extract
from agents.schema_alignment_agent import align

# 통합 대상 카테고리 (known/irrelevant는 버림)
INTEGRATE = {"extend", "new", "contradict"}
VALUE_MIN = 0.5  # 이 미만은 노이즈로 보고 버림 (임시 컷, 나중에 임베딩으로 정밀화)


def run_collector(max_results=4):
    m = load_map()
    papers = fetch(max_results=max_results)
    print(f"{len(papers)}개 논문 수집\n")

    integrated, skipped = [], []
    for p in papers:
        verdict = judge_paper(m, p)
        cat, val = verdict["category"], verdict["value"]

        # 통과 필터
        if cat not in INTEGRATE or val < VALUE_MIN:
            skipped.append((p["title"][:45], cat, val))
            continue

        # 통과 → 개념 추출 + 맵 병합
        extracted = extract(p["text"])
        added, merged = align(m, extracted, source=p["source_id"])

        integrated.append({
            "title": p["title"][:45], "category": cat, "value": val,
            "related": verdict.get("related_concepts", []),
            "added": added, "merged": [c for _, c in merged],
        })

    save_map(m)

    # 리포트
    print("=" * 55)
    print(f"통합 {len(integrated)}개 / 버림 {len(skipped)}개\n")
    for it in integrated:
        print(f"[{it['value']}] {it['category']:10} {it['title']}")
        print(f"     기존 연결: {it['related']}")          # 위상 해석 (가벼운 버전)
        print(f"     신규 개념: {it['added']}")
        print(f"     병합됨:    {it['merged']}")
        print()
    if skipped:
        print("버린 것:")
        for t, c, v in skipped:
            print(f"  [{v}] {c:10} {t}")


if __name__ == "__main__":
    run_collector(max_results=4)
