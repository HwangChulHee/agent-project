"""data/queries/ep{1,2}_queries.md → data/queries/queries.json

마크다운 파싱해서 35개 쿼리 JSON 생성. 로더에서 이 JSON 읽음.

사용: uv run python scripts/build_queries_json.py
"""
import json
import re
from pathlib import Path

QUERIES_DIR = Path("data/queries")
OUT_PATH = QUERIES_DIR / "queries.json"


def parse_md(path: Path, episode: str) -> list[dict]:
    """ep1_queries.md / ep2_queries.md 파싱.

    포맷:
        ## Factoid (사실 ...)

        ### Q1.1 — 차라투스트라는 몇 살에...
        - **요약(KO)**: ...
        - **Ground truth (EN)**: ...
    """
    text = path.read_text(encoding="utf-8")
    queries = []

    # ## 섹션 단위 분할 (카테고리)
    sections = re.split(r"^## ", text, flags=re.M)

    current_category = None
    for section in sections:
        if not section.strip():
            continue
        first_line = section.split("\n", 1)[0]
        # "Factoid (사실 ...)" 같은 헤더에서 카테고리 추출
        m = re.match(r"^(Factoid|Concept|Metaphor|Background)", first_line, re.I)
        if not m:
            continue
        current_category = m.group(1).lower()

        # ### Q1.1 ... 단위 분할
        items = re.split(r"^### Q\d+\.\d+ — ", section, flags=re.M)
        for item in items[1:]:  # 첫 부분은 섹션 헤더
            lines = item.strip().split("\n")
            if not lines:
                continue
            query_text = lines[0].strip()

            # Ground truth (EN) 추출
            gt_match = re.search(r"\*\*Ground truth \(EN\)\*\*:\s*(.+?)(?:\n|$)",
                                  item, re.M)
            if not gt_match:
                print(f"  ⚠ Ground truth 없음: {query_text[:40]}")
                continue
            ground_truth = gt_match.group(1).strip()

            # 한국어 요약 추출 (검수·표시용)
            ko_match = re.search(r"\*\*요약\(KO\)\*\*:\s*(.+?)(?:\n|$)",
                                  item, re.M)
            ko_summary = ko_match.group(1).strip() if ko_match else ""

            queries.append({
                "text": query_text,
                "category": current_category,
                "episode": episode,
                "ground_truth_en": ground_truth,
                "summary_ko": ko_summary,
            })

    return queries


def main():
    all_queries = []
    for ep, fname in [("ep1", "ep1_queries.md"), ("ep2", "ep2_queries.md")]:
        path = QUERIES_DIR / fname
        if not path.exists():
            print(f"  SKIP {fname}")
            continue
        qs = parse_md(path, ep)
        print(f"  {fname}: {len(qs)} 쿼리")
        all_queries.extend(qs)

    # 카테고리별 분포
    from collections import Counter
    by_cat = Counter(q["category"] for q in all_queries)
    by_ep = Counter(q["episode"] for q in all_queries)

    print(f"\n총 {len(all_queries)} 쿼리")
    print(f"  카테고리: {dict(by_cat)}")
    print(f"  에피소드: {dict(by_ep)}")

    # JSON 저장
    OUT_PATH.write_text(
        json.dumps(all_queries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ {OUT_PATH} ({OUT_PATH.stat().st_size:,} 바이트)")


if __name__ == "__main__":
    main()
