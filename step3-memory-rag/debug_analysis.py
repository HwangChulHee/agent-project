"""Phase 2 분석 — 정형 vs 비정형 비율 측정 (H 그룹)."""
from __future__ import annotations

import random
import statistics
from collections import defaultdict
from pathlib import Path

from parser import Parser

ZIPS = [
    ("삼성전자",   "data/00126380_20250311001085.zip"),
    ("SK하이닉스", "data/00164779_20250319000665.zip"),
    ("한미반도체", "data/00161383_20250313001171.zip"),
]
OUT = Path("data/debug/H_analysis")

PREFIX_DELIM = "\n---\n"  # chunker._make_table_prefix 의 마지막 구분자

TABLE_HINT_KEYWORDS = [
    "다음과 같", "아래", "상기", "위 표", "위 표는",
    "하기", "다음의", "와 같습니다", "과 같습니다",
    "다음 표", "아래 표", "위와 같",
]


def _split_table_chunk(text: str) -> tuple[str, str]:
    """표 chunk 의 prefix 와 표 본문 분리.

    chunker.py 의 _make_table_prefix 출력 형식:
      "[섹션경로]\\n직전문장\\n---\\n표markdown"
    구분자 '\\n---\\n' 첫 등장 기준 split.
    prefix 가 없으면 prefix="", body=text.
    """
    if PREFIX_DELIM in text:
        head, body = text.split(PREFIX_DELIM, 1)
        return head, body
    return "", text


# ─────────────────────────────────────────────────────────────
# A. 글자수 기준 정형/비정형 비율
# ─────────────────────────────────────────────────────────────
def dump_A(all_chunks_by_company):
    print("[A] 비율 측정 ...")
    lines = []
    totals = {"table_body": 0, "table_prefix": 0, "text_only": 0}

    for name, chunks in all_chunks_by_company.items():
        tb = tp = tx = 0
        for c in chunks:
            if c.metadata["has_table"]:
                pref, body = _split_table_chunk(c.text)
                tp += len(pref)
                tb += len(body)
            else:
                tx += len(c.text)
        total = tb + tp + tx
        totals["table_body"] += tb
        totals["table_prefix"] += tp
        totals["text_only"] += tx

        pure_table = tb
        narrative = tp + tx
        ratio_total = pure_table + narrative

        lines.append(f"[{name}]")
        lines.append(f"  표 본문 글자수        : {tb:>10,}  ({tb/total*100:5.1f}%)  ← 순수 markdown 표")
        lines.append(f"  표 prefix(설명) 글자수: {tp:>10,}  ({tp/total*100:5.1f}%)  ← 표에 붙은 서술")
        lines.append(f"  독립 텍스트 글자수    : {tx:>10,}  ({tx/total*100:5.1f}%)  ← has_table=False")
        lines.append(f"  총 글자수             : {total:>10,}")
        lines.append(
            f"  → 순수 표 vs 서술(prefix+독립): "
            f"{pure_table/ratio_total*100:5.1f}% : {narrative/ratio_total*100:5.1f}%"
        )
        lines.append("")

    tb, tp, tx = totals["table_body"], totals["table_prefix"], totals["text_only"]
    total = tb + tp + tx
    pure_table = tb
    narrative = tp + tx
    lines.append("[3사 합계]")
    lines.append(f"  표 본문 글자수        : {tb:>10,}  ({tb/total*100:5.1f}%)")
    lines.append(f"  표 prefix(설명) 글자수: {tp:>10,}  ({tp/total*100:5.1f}%)")
    lines.append(f"  독립 텍스트 글자수    : {tx:>10,}  ({tx/total*100:5.1f}%)")
    lines.append(f"  총 글자수             : {total:>10,}")
    lines.append(
        f"  → 순수 표 vs 서술(prefix+독립): "
        f"{pure_table/(pure_table+narrative)*100:5.1f}% : "
        f"{narrative/(pure_table+narrative)*100:5.1f}%"
    )

    out = "\n".join(lines) + "\n"
    (OUT / "00_ratio.txt").write_text(out, encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────
# B. 섹션별 정형/비정형 분포 (삼성)
# ─────────────────────────────────────────────────────────────
def dump_B(samsung_chunks):
    print("[B] 섹션별 분포 (삼성) ...")
    # main XML 만 — SECTION-1 단위 집계
    main = [c for c in samsung_chunks if c.metadata["source_xml"] == "main"]

    sec_data = defaultdict(lambda: {
        "n_table": 0, "n_text": 0,
        "table_body_chars": 0, "table_prefix_chars": 0, "text_chars": 0,
    })
    for c in main:
        s1 = c.metadata["section_path"].split(" > ")[0]
        d = sec_data[s1]
        if c.metadata["has_table"]:
            d["n_table"] += 1
            pref, body = _split_table_chunk(c.text)
            d["table_body_chars"] += len(body)
            d["table_prefix_chars"] += len(pref)
        else:
            d["n_text"] += 1
            d["text_chars"] += len(c.text)

    # 14개 SECTION-1 알파벳 → 로마숫자 순으로 정렬은 어려우니
    # ATOCID 순서 못 보장. 일단 main XML 순서대로 — chunks 순서로.
    order_seen = []
    for c in main:
        s1 = c.metadata["section_path"].split(" > ")[0]
        if s1 not in order_seen:
            order_seen.append(s1)

    lines = ["[삼성전자] 섹션별 분포 (main XML)", ""]
    lines.append(
        f"{'SECTION-1':<42}{'표chunk':>8}{'텍스트':>8}"
        f"{'표본문':>9}{'표설명':>8}{'독립텍스트':>10}"
    )
    lines.append("-" * 86)
    for s1 in order_seen:
        d = sec_data[s1]
        total = d["table_body_chars"] + d["table_prefix_chars"] + d["text_chars"]
        if total == 0:
            continue
        tb_pct = d["table_body_chars"] / total * 100
        tp_pct = d["table_prefix_chars"] / total * 100
        tx_pct = d["text_chars"] / total * 100
        # 제목 길면 자름
        title = s1 if len(s1) <= 40 else s1[:39] + "…"
        lines.append(
            f"{title:<42}{d['n_table']:>8}{d['n_text']:>8}"
            f"{tb_pct:>8.1f}%{tp_pct:>7.1f}%{tx_pct:>9.1f}%"
        )
    lines.append("")
    lines.append("주: 표본문=순수 markdown, 표설명=표 chunk 의 prefix, "
                 "독립텍스트=has_table=False chunk")

    out = "\n".join(lines) + "\n"
    (OUT / "01_by_section.txt").write_text(out, encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────
# C. 텍스트 chunk 휴리스틱 분류
# ─────────────────────────────────────────────────────────────
def dump_C(all_chunks_by_company):
    print("[C] 텍스트 chunk 휴리스틱 분류 ...")
    all_text = []
    for chunks in all_chunks_by_company.values():
        for c in chunks:
            if not c.metadata["has_table"]:
                all_text.append(c)

    n_short = 0
    n_pointer = 0
    n_suspect = 0
    independent = []
    for c in all_text:
        is_short = len(c.text) < 200
        has_pointer = any(kw in c.text for kw in TABLE_HINT_KEYWORDS)
        if is_short:
            n_short += 1
        if has_pointer:
            n_pointer += 1
        if is_short or has_pointer:
            n_suspect += 1
        else:
            independent.append(c)

    sizes = [len(c.text) for c in independent]

    lines = [f"[C] 텍스트 chunk 휴리스틱 분류 (3사 합계)", ""]
    lines.append(f"독립 텍스트 chunk 총: {len(all_text)}개")
    lines.append(f"  표 설명 의심 (짧음 or 표 지시어): "
                 f"{n_suspect}개 ({n_suspect/len(all_text)*100:.1f}%)")
    lines.append(f"    - 짧음(<200자)         : {n_short}개")
    lines.append(f"    - 표 지시어 포함       : {n_pointer}개")
    lines.append(f"  독립 서술 추정          : {len(independent)}개 "
                 f"({len(independent)/len(all_text)*100:.1f}%)")
    lines.append("")
    if sizes:
        lines.append(
            f"독립 서술 추정 chunk 글자수 분포: "
            f"mean={statistics.mean(sizes):.0f}, "
            f"median={statistics.median(sizes):.0f}, "
            f"max={max(sizes)}, total={sum(sizes):,}자"
        )
    lines.append("")
    lines.append(f"사용한 표 지시어 키워드: {TABLE_HINT_KEYWORDS}")

    out = "\n".join(lines) + "\n"
    (OUT / "02_textchunk_classify.txt").write_text(out, encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────
# D. 텍스트 chunk 샘플 30개 (섹션 골고루)
# ─────────────────────────────────────────────────────────────
def dump_D(all_chunks_by_company):
    print("[D] 텍스트 chunk 샘플 30개 ...")
    all_text = []
    for chunks in all_chunks_by_company.values():
        for c in chunks:
            if not c.metadata["has_table"]:
                all_text.append(c)

    # 섹션별 그룹핑 (section_path 의 SECTION-1)
    by_section = defaultdict(list)
    for c in all_text:
        s1 = c.metadata["section_path"].split(" > ")[0]
        by_section[s1].append(c)

    rng = random.Random(42)
    # 섹션별로 골고루 — round-robin
    sections = sorted(by_section.keys())
    pool = []
    pos = {s: 0 for s in sections}
    shuffled_per_section = {s: rng.sample(by_section[s], len(by_section[s]))
                            for s in sections}

    while len(pool) < 30 and any(pos[s] < len(shuffled_per_section[s]) for s in sections):
        for s in sections:
            if pos[s] < len(shuffled_per_section[s]):
                pool.append(shuffled_per_section[s][pos[s]])
                pos[s] += 1
                if len(pool) >= 30:
                    break

    lines = ["# 텍스트 chunk 샘플 30개 — 사람 판정용 (섹션 round-robin)", ""]
    for i, c in enumerate(pool, 1):
        is_short = len(c.text) < 200
        has_pointer = any(kw in c.text for kw in TABLE_HINT_KEYWORDS)
        suspect = "표설명 의심" if (is_short or has_pointer) else "독립 서술 추정"
        lines.append(f"═══ 샘플 #{i:02d} ═══")
        lines.append(f"company : {c.metadata.get('company')}")
        lines.append(f"source  : {c.metadata.get('source_xml')}")
        lines.append(f"section : {c.metadata['section_path']}")
        lines.append(f"length  : {len(c.text)}자  "
                     f"(short={is_short}, pointer={has_pointer})")
        lines.append(f"휴리스틱 판정: {suspect}")
        lines.append("─" * 50)
        lines.append(c.text)
        lines.append("")

    (OUT / "03_textchunk_samples.txt").write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_chunks_by_company = {}
    for name, zp in ZIPS:
        print(f"parsing {name} ...")
        all_chunks_by_company[name] = Parser().parse(zp)

    ratio_txt = dump_A(all_chunks_by_company)
    section_txt = dump_B(all_chunks_by_company["삼성전자"])
    classify_txt = dump_C(all_chunks_by_company)
    dump_D(all_chunks_by_company)

    print("\n" + "=" * 70)
    print("00_ratio.txt")
    print("=" * 70)
    print(ratio_txt)
    print("=" * 70)
    print("01_by_section.txt")
    print("=" * 70)
    print(section_txt)
    print("=" * 70)
    print("02_textchunk_classify.txt")
    print("=" * 70)
    print(classify_txt)


if __name__ == "__main__":
    main()
