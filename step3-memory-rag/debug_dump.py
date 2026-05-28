"""Phase 2 디버그 덤프 — 파서/청커 산출물을 사람이 읽을 수 있게 덤프.

파서 코드는 수정하지 않고 호출만. 결과는 data/debug/ 하위 4그룹에 저장.
"""
from __future__ import annotations

import statistics
import zipfile
from pathlib import Path

from lxml import etree as ET

from parser import Parser, COMPANY_MAP
from parser.xml_loader import load_xmls_from_zip
from parser.section_tree import parse_section_tree
from parser.text_extract import extract_text
from parser.table_to_md import extract_table_as_text, table_to_markdown
from parser.models import SectionNode

TABLE_TAGS = {"TABLE", "TABLE-GROUP"}

ZIPS = [
    ("삼성전자",   "data/00126380_20250311001085.zip"),
    ("SK하이닉스", "data/00164779_20250319000665.zip"),
    ("한미반도체", "data/00161383_20250313001171.zip"),
]
DEBUG = Path("data/debug")


# ─────────────────────────────────────────────────────────────
# 헬퍼: 메인 XML 원문 / 메인 root 가져오기
# ─────────────────────────────────────────────────────────────
def _main_xml_raw(zip_path: str) -> str:
    """메인 XML 원문을 문자열로."""
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".xml"):
                continue
            stem = Path(info.filename).stem
            if "_00760" in stem or "_00761" in stem:
                continue
            return zf.read(info.filename).decode("utf-8", errors="replace")
    return ""


def _main_root(zip_path: str):
    for fn, st, root in load_xmls_from_zip(zip_path):
        if st == "main":
            return root
    return None


def _section_iter_text_tables(node: SectionNode, depth: int = 0):
    """SectionNode 트리를 순회하며 (depth, title, body_text, tables) yield.

    하위 섹션이 있어도 자기 body_elements 가 있으면 함께 내보낸다.
    chunker 의 _iter_leaves 와 같은 의미(섹션 사이 body 도 포함).
    """
    text_elems, table_elems = [], []
    for elem in node.body_elements:
        tag = elem.tag
        if isinstance(tag, str) and tag in TABLE_TAGS:
            table_elems.append(elem)
        else:
            text_elems.append(elem)
    body_text = extract_text(text_elems)

    tables_md = []
    for tbl in table_elems:
        actuals = []
        if tbl.tag == "TABLE-GROUP":
            actuals.extend(tbl.findall("TABLE"))
        elif tbl.tag == "TABLE":
            actuals.append(tbl)
        for table in actuals:
            txt = extract_table_as_text(table)
            if txt:
                tables_md.append(("TEXT-CONTAINER", table.get("ACLASS"), txt))
            else:
                md = table_to_markdown(table)
                if md.strip():
                    tables_md.append(("MARKDOWN", table.get("ACLASS"), md))

    if body_text.strip() or tables_md:
        yield depth, node.title, body_text, tables_md

    for child in node.children:
        yield from _section_iter_text_tables(child, depth + 1)


def _collect_section1_dump(node: SectionNode) -> str:
    """SECTION-1 하나의 모든 자식 텍스트/표를 하나의 통짜 문자열로."""
    buf = []
    title1 = node.title
    buf.append(f"████████ {title1} ████████\n")

    table_idx = 0
    for depth, title, body_text, tables in _section_iter_text_tables(node):
        if depth > 0 and title:
            indent = "  " * (depth - 1)
            buf.append(f"\n{indent}── [{depth}] {title} ──\n")
        if body_text.strip():
            buf.append(body_text)
            buf.append("")
        for kind, aclass, md in tables:
            table_idx += 1
            buf.append(f"--- 표 {table_idx} ({kind}, aclass: {aclass}) ---")
            buf.append(md)
            buf.append("")
    return "\n".join(buf) + "\n"


# ─────────────────────────────────────────────────────────────
# A. 문제 chunk 덤프
# ─────────────────────────────────────────────────────────────
def dump_A():
    print("\n[A] 문제 chunk 덤프 ...")

    # A-1. 삼성 max chunk
    samsung = Parser().parse("data/00126380_20250311001085.zip")
    biggest = max(samsung, key=lambda c: len(c.text))
    out = (
        f"길이: {len(biggest.text)}자\n"
        f"section: {biggest.metadata['section_path']}\n"
        f"source_xml: {biggest.metadata['source_xml']}\n"
        f"has_table: {biggest.metadata['has_table']}\n"
        f"aclass: {biggest.metadata.get('aclass')}\n"
        f"section_level: {biggest.metadata.get('section_level')}\n"
        f"{'='*70}\n{biggest.text}\n"
    )
    (DEBUG / "A_problems" / "01_samsung_max.txt").write_text(out, encoding="utf-8")

    # A-2. 한미 가장 긴 텍스트(=표 아님) chunk
    hanmi = Parser().parse("data/00161383_20250313001171.zip")
    text_chunks = [c for c in hanmi if not c.metadata["has_table"]]
    longest = max(text_chunks, key=lambda c: len(c.text))
    out2 = (
        f"길이: {len(longest.text)}자\n"
        f"section: {longest.metadata['section_path']}\n"
        f"source_xml: {longest.metadata['source_xml']}\n"
        f"has_table: {longest.metadata['has_table']}\n"
        f"aclass: {longest.metadata.get('aclass')}\n"
        f"{'='*70}\n{longest.text}\n"
    )
    (DEBUG / "A_problems" / "02_hanmi_text.txt").write_text(out2, encoding="utf-8")

    # A-3. TABLE / TABLE-GROUP 통계 + 삼성 max chunk 추적
    lines = []
    lines.append("=" * 70)
    lines.append("TABLE / TABLE-GROUP 통계 (메인 XML 원문 기준)")
    lines.append("=" * 70)
    for name, zp in ZIPS:
        raw = _main_xml_raw(zp)
        root = _main_root(zp)
        n_table = raw.count("<TABLE ") + raw.count("<TABLE>")
        n_group = raw.count("<TABLE-GROUP ") + raw.count("<TABLE-GROUP>")
        # 실제 element 카운트 (재확인용)
        n_table_el = len(root.findall(".//TABLE")) if root is not None else 0
        n_group_el = len(root.findall(".//TABLE-GROUP")) if root is not None else 0
        lines.append(f"\n[{name}]")
        lines.append(f"  문자열 카운트   <TABLE: {n_table}   <TABLE-GROUP: {n_group}")
        lines.append(f"  element 카운트  TABLE: {n_table_el}   TABLE-GROUP: {n_group_el}")

    # 삼성 max chunk 가 어디서 왔는지 — 같은 section_path 리프의 TABLE 개수
    lines.append("\n" + "=" * 70)
    lines.append("삼성 max chunk 추적")
    lines.append("=" * 70)
    target_path = biggest.metadata["section_path"]
    lines.append(f"target section_path : {target_path}")
    lines.append(f"chunk 길이         : {len(biggest.text):,}자")
    lines.append(f"has_table          : {biggest.metadata['has_table']}")

    # 같은 section_path 를 가진 chunk 전부 — 표 1개가 잘려 여러 chunk가 됐는지 확인
    same_path = [c for c in samsung if c.metadata["section_path"] == target_path]
    table_chunks_same = [c for c in same_path if c.metadata["has_table"]]
    lines.append(
        f"\n같은 section_path 의 chunk: {len(same_path)}개 "
        f"(그 중 표: {len(table_chunks_same)})"
    )
    sizes = sorted([len(c.text) for c in same_path], reverse=True)
    lines.append(f"크기 top10: {sizes[:10]}")

    # 같은 section_path 의 SectionNode 를 트리에서 찾기
    root_main = _main_root("data/00126380_20250311001085.zip")
    sections = parse_section_tree(root_main)

    def _find_leaf(node: SectionNode, path: list[str], target: list[str]):
        cur = path + [node.title] if node.title else path
        if cur == target:
            yield node
        for ch in node.children:
            yield from _find_leaf(ch, cur, target)

    target_parts = target_path.split(" > ")
    leaves = []
    for s in sections:
        leaves.extend(_find_leaf(s, [], target_parts))
    lines.append(f"\n트리에서 매칭된 SectionNode: {len(leaves)}개")
    for i, leaf in enumerate(leaves):
        n_table_leaf = sum(
            1 for e in leaf.body_elements
            if isinstance(e.tag, str) and e.tag == "TABLE"
        )
        n_group_leaf = sum(
            1 for e in leaf.body_elements
            if isinstance(e.tag, str) and e.tag == "TABLE-GROUP"
        )
        # TABLE-GROUP 내부 실제 TABLE
        inner_tables = 0
        for e in leaf.body_elements:
            if isinstance(e.tag, str) and e.tag == "TABLE-GROUP":
                inner_tables += len(e.findall("TABLE"))
        lines.append(
            f"  leaf #{i} body_elements: {len(leaf.body_elements)}개  "
            f"TABLE: {n_table_leaf}  TABLE-GROUP: {n_group_leaf} (내부 TABLE {inner_tables}개)"
        )

    # 모든 leaf 합쳐서 — 표 markdown 별 길이 분포 (>1500인 것 추적)
    big_tables = []
    for i, leaf in enumerate(leaves):
        for e in leaf.body_elements:
            if not isinstance(e.tag, str):
                continue
            actuals = []
            if e.tag == "TABLE":
                actuals = [e]
            elif e.tag == "TABLE-GROUP":
                actuals = e.findall("TABLE")
            for t in actuals:
                txt = extract_table_as_text(t)
                if txt:
                    big_tables.append(("text-container", len(txt), t.get("ACLASS")))
                else:
                    md = table_to_markdown(t)
                    if md.strip():
                        big_tables.append(("markdown", len(md), t.get("ACLASS")))
    big_tables.sort(key=lambda x: -x[1])
    lines.append(f"\n해당 leaf 들의 표 원본(markdown) 길이 top10:")
    for kind, ln, ac in big_tables[:10]:
        lines.append(f"  {kind:>15}  {ln:>8,}자  aclass={ac}")

    # 거대 chunk 의 줄 구성 (header + 데이터행)
    txt = biggest.text
    n_lines = txt.count("\n") + 1
    n_pipe_lines = sum(1 for ln in txt.split("\n") if ln.startswith("|"))
    longest_line_len = max((len(ln) for ln in txt.split("\n")), default=0)
    lines.append(f"\n삼성 max chunk 텍스트 구조:")
    lines.append(f"  전체 줄 수      : {n_lines}")
    lines.append(f"  | 로 시작 줄 수 : {n_pipe_lines}")
    lines.append(f"  최장 라인 길이  : {longest_line_len:,}자")

    text_out = "\n".join(lines) + "\n"
    (DEBUG / "A_problems" / "03_table_stats.txt").write_text(text_out, encoding="utf-8")
    return text_out


# ─────────────────────────────────────────────────────────────
# B. 파서 정제 결과 — chunk 분할 전 섹션별 통짜
# ─────────────────────────────────────────────────────────────
def dump_B():
    print("\n[B] 섹션별 통짜 텍스트 덤프 ...")
    for name, zp in ZIPS:
        root = _main_root(zp)
        sections = parse_section_tree(root)
        # SECTION-1 들
        buf = [f"# {name} — 메인 XML SECTION-1 통짜 (chunk 분할 전)\n"]
        for s1 in sections:
            buf.append(_collect_section1_dump(s1))
            buf.append("")
        out_path = DEBUG / "B_parsed" / f"{name}_sections.txt"
        out_path.write_text("\n".join(buf), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# C. 현재 청킹 결과 전체
# ─────────────────────────────────────────────────────────────
def dump_C():
    print("\n[C] chunk 전체 덤프 ...")
    for name, zp in ZIPS:
        chunks = Parser().parse(zp)
        sizes = [len(c.text) for c in chunks]
        n_table = sum(1 for c in chunks if c.metadata["has_table"])

        head = [
            f"# {name} — chunk 전체 덤프 ({zp})",
            "",
            f"총 chunk : {len(chunks)}",
            f"mean     : {statistics.mean(sizes):.0f}",
            f"median   : {statistics.median(sizes):.0f}",
            f"p95      : {sorted(sizes)[int(len(sizes)*0.95)]}",
            f"max      : {max(sizes)}",
            f"has_table 비율 : {n_table}/{len(chunks)} ({n_table/len(chunks)*100:.1f}%)",
            "",
            "=" * 70,
            "",
        ]
        body = []
        for i, c in enumerate(chunks):
            m = c.metadata
            body.append("═" * 55)
            body.append(f"chunk #{i:05d}")
            body.append(f"company   : {m.get('company')}")
            body.append(f"source    : {m.get('source_xml')}")
            body.append(f"section   : {m.get('section_path')}")
            body.append(f"size      : {len(c.text)}자")
            body.append(f"has_table : {m.get('has_table')}")
            body.append(f"aclass    : {m.get('aclass')}")
            body.append("─" * 55)
            body.append(c.text)
            body.append("═" * 55)
            body.append("")
        out_path = DEBUG / "C_chunks" / f"{name}_chunks.txt"
        out_path.write_text("\n".join(head + body), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# D. 청킹 파라미터 비교 (800/1500/3000)
# ─────────────────────────────────────────────────────────────
def dump_D():
    print("\n[D] 청킹 파라미터 비교 ...")
    zp = "data/00126380_20250311001085.zip"

    versions = [800, 1500, 3000]
    parsed = {v: Parser(max_chunk_chars=v).parse(zp) for v in versions}

    # 통계 표
    stat_lines = [
        "삼성전자 — max_chunk_chars 비교\n",
        f"{'max_chunk':>10} {'count':>7} {'mean':>7} {'median':>8} {'p95':>7} {'max':>8}",
    ]
    for v in versions:
        cs = parsed[v]
        sz = [len(c.text) for c in cs]
        stat_lines.append(
            f"{v:>10} {len(cs):>7} "
            f"{statistics.mean(sz):>7.0f} {statistics.median(sz):>8.0f} "
            f"{sorted(sz)[int(len(sz)*0.95)]:>7} {max(sz):>8}"
        )
    # 추가: 1500자 초과 비율
    stat_lines.append("")
    stat_lines.append(f"{'max_chunk':>10} {'>1500자':>8} {'>3000자':>8} {'>6000자':>8}")
    for v in versions:
        cs = parsed[v]
        n1 = sum(1 for c in cs if len(c.text) > 1500)
        n3 = sum(1 for c in cs if len(c.text) > 3000)
        n6 = sum(1 for c in cs if len(c.text) > 6000)
        stat_lines.append(f"{v:>10} {n1:>8} {n3:>8} {n6:>8}")
    (DEBUG / "D_compare" / "00_stats.txt").write_text(
        "\n".join(stat_lines) + "\n", encoding="utf-8"
    )

    # 같은 섹션 한 곳 비교 — "II. 사업의 내용" 으로 시작하는 것
    target_prefix = "II. 사업의 내용"
    buf = [f"# 섹션 비교 — '{target_prefix}' 로 시작하는 chunk\n"]
    for v in versions:
        cs = [c for c in parsed[v] if c.metadata["section_path"].startswith(target_prefix)]
        buf.append("\n" + "═" * 30 + f" max_chunk_chars = {v} " + "═" * 30)
        buf.append(f"해당 섹션 chunk 수: {len(cs)}\n")
        for i, c in enumerate(cs):
            buf.append(f"[chunk {i+1}/{len(cs)}] ({len(c.text)}자) "
                       f"section: {c.metadata['section_path']}  "
                       f"has_table: {c.metadata['has_table']}")
            buf.append(c.text)
            buf.append("")
    (DEBUG / "D_compare" / "samsung_section_compare.txt").write_text(
        "\n".join(buf), encoding="utf-8"
    )


# ─────────────────────────────────────────────────────────────
def main():
    DEBUG.mkdir(parents=True, exist_ok=True)
    for sub in ("A_problems", "B_parsed", "C_chunks", "D_compare"):
        (DEBUG / sub).mkdir(exist_ok=True)

    table_stats = dump_A()
    dump_B()
    dump_C()
    dump_D()

    print("\n" + "=" * 70)
    print("A_problems/03_table_stats.txt 내용:")
    print("=" * 70)
    print(table_stats)


if __name__ == "__main__":
    main()
