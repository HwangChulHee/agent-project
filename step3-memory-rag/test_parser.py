"""Parser 통합 테스트 + 검수 출력."""
import statistics
from pathlib import Path
from parser import Parser

ZIPS = [
    ("삼성전자",   "data/00126380_20250311001085.zip"),
    ("SK하이닉스", "data/00164779_20250319000665.zip"),
    ("한미반도체", "data/00161383_20250313001171.zip"),
]


def main():
    p = Parser()
    for name, zp in ZIPS:
        print(f"\n{'='*60}\n[{name}] {zp}\n{'='*60}")
        chunks = p.parse(zp)

        main_chunks = [c for c in chunks if c.metadata["source_xml"] == "main"]
        sections_l1 = set(
            c.metadata["section_path"].split(" > ")[0]
            for c in main_chunks
        )
        print(f"\n메인 XML chunks: {len(main_chunks)}")
        print(f"SECTION-1 distinct: {len(sections_l1)}")
        assert len(sections_l1) == 14, \
            f"expected 14 sections, got {len(sections_l1)}: {sections_l1}"
        print("✓ 14개 SECTION-1 확인")

        sizes = [len(c.text) for c in chunks]
        print(f"\nchunk 크기 — count: {len(chunks)}, "
              f"mean: {statistics.mean(sizes):.0f}, "
              f"median: {statistics.median(sizes):.0f}, "
              f"p95: {sorted(sizes)[int(len(sizes)*0.95)]}, "
              f"max: {max(sizes)}")

        table_chunks = [c for c in chunks if c.metadata["has_table"]]
        print(f"\n표 chunks: {len(table_chunks)}")
        if table_chunks:
            sample = table_chunks[len(table_chunks)//2]
            print(f"\n--- 표 chunk 샘플 ---")
            print(f"path: {sample.metadata['section_path']}")
            print(f"aclass: {sample.metadata['aclass']}")
            print(sample.text[:800])
            print("---")


if __name__ == "__main__":
    main()
