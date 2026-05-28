"""Parser 통합 테스트 + 검수 출력 (2차)."""
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
    print(f"Parser 파라미터: target={p.target_chunk_chars}, "
          f"max={p.max_chunk_chars}, overlap={p.overlap_chars}")

    for name, zp in ZIPS:
        print(f"\n{'='*60}\n[{name}] {zp}\n{'='*60}")
        chunks = p.parse(zp)

        main_chunks = [c for c in chunks if c.metadata["source_xml"] == "main"]
        sections_l1 = set(
            c.metadata["section_path"].split(" > ")[0]
            for c in main_chunks
        )

        # 검수 1 — 14대 챕터
        names = sorted(sections_l1)
        print(f"\n[검수 1] SECTION-1 ({len(names)}개):")
        for n in names:
            print(f"  - {n}")
        assert len(sections_l1) == 14, \
            f"expected 14 sections, got {len(sections_l1)}: {sections_l1}"
        print("✓ 14개 SECTION-1 확인")

        sizes = [len(c.text) for c in chunks]
        truncated = [c for c in chunks if c.metadata.get("truncated")]

        # 검수 2 — chunk 크기
        print(f"\n[검수 2] chunk 크기 — count: {len(chunks)}, "
              f"mean: {statistics.mean(sizes):.0f}, "
              f"median: {statistics.median(sizes):.0f}, "
              f"p95: {sorted(sizes)[int(len(sizes)*0.95)]}, "
              f"max: {max(sizes)}")
        print(f"  truncated chunks: {len(truncated)}")
        oversized_untruncated = [
            c for c in chunks
            if len(c.text) > 6000 and not c.metadata.get("truncated")
        ]
        print(f"  6000자 초과 (truncate 안 된 것): {len(oversized_untruncated)}")
        if oversized_untruncated:
            for c in oversized_untruncated[:3]:
                print(f"    ⚠ {len(c.text)}자  "
                      f"path={c.metadata['section_path']}  "
                      f"has_table={c.metadata['has_table']}")

        buckets = [(0,500),(500,1000),(1000,1500),(1500,3000),(3000,6000),(6000,float('inf'))]
        for lo, hi in buckets:
            cnt = sum(1 for c in chunks if lo < len(c.text) <= hi)
            label = f"{lo}~{hi}" if hi != float('inf') else f"{lo}+"
            print(f"  {label:>12}: {cnt}")

        # 검수 3 — has_table 비율
        table_chunks = [c for c in chunks if c.metadata["has_table"]]
        ratio = len(table_chunks) / len(chunks) * 100
        print(f"\n[검수 3] has_table: {len(table_chunks)}/{len(chunks)} ({ratio:.1f}%)")
        if name == "한미반도체":
            status = "✓" if ratio <= 60 else "⚠"
            print(f"  {status} 한미 목표: 60% 이하 (현재 {ratio:.1f}%)")

        # 검수 4 — 표 prefix
        print(f"\n[검수 4] 표 chunk prefix 검증 (앞 5개):")
        ok = 0
        for c in table_chunks[:5]:
            starts_with_path = c.text.startswith("[") and "]\n" in c.text[:200]
            ok += 1 if starts_with_path else 0
            head = c.text[:120].replace("\n", " | ")
            print(f"  {'✓' if starts_with_path else '✗'} {head}...")
        print(f"  prefix 적용: {ok}/5 (앞 5개 기준)")

        # 검수 5 — 구두점 분할 (한미 최대 텍스트 chunk)
        text_only = [c for c in chunks if not c.metadata["has_table"]]
        if text_only:
            longest_text = max(text_only, key=lambda c: len(c.text))
            print(f"\n[검수 5] 텍스트 chunk max: {len(longest_text.text)}자  "
                  f"path={longest_text.metadata['section_path']}")

        # 표 chunk 샘플 1개 (전체 보기)
        if table_chunks:
            sample = table_chunks[len(table_chunks)//2]
            print(f"\n--- 표 chunk 샘플 (mid) ---")
            print(f"path: {sample.metadata['section_path']}")
            print(f"aclass: {sample.metadata['aclass']}  "
                  f"truncated: {sample.metadata.get('truncated', False)}")
            print(sample.text[:800])
            print("---")


if __name__ == "__main__":
    main()
