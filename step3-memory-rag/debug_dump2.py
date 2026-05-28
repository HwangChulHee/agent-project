"""Phase 2 디버그 덤프 (2차) — 원문 XML 열람 (E/F/G).

파서 코드는 수정하지 않고 호출만. 결과는 data/debug/{E,F,G}/.
"""
from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree as ET

from parser import Parser, COMPANY_MAP
from parser.xml_loader import load_xmls_from_zip, classify_xml_file, parse_xml
from parser.section_tree import parse_section_tree
from parser.models import SectionNode

ZIPS = [
    ("삼성전자",   "data/00126380_20250311001085.zip"),
    ("SK하이닉스", "data/00164779_20250319000665.zip"),
    ("한미반도체", "data/00161383_20250313001171.zip"),
]
DEBUG = Path("data/debug")


# ─────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────
def _read_xmls(zip_path: str) -> list[tuple[str, str, bytes]]:
    """[(filename, source_type, raw_bytes)] — sanitize 전 원본."""
    results = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.lower().endswith(".xml"):
                continue
            raw = zf.read(info.filename)
            stype = classify_xml_file(info.filename)
            results.append((info.filename, stype, raw))
    return results


def _safe_filename(s: str, maxlen: int = 20) -> str:
    """파일명 안전화 — 공백 압축, 일부 특수문자 제거."""
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("/", "_").replace("\\", "_").replace(":", "").replace("*", "")
    s = s.replace("?", "").replace('"', "").replace("<", "").replace(">", "")
    s = s.replace("|", "").replace("【", "").replace("】", "")
    if len(s) > maxlen:
        s = s[:maxlen]
    return s.strip() or "untitled"


def _section_title(elem) -> str:
    t = elem.find("TITLE")
    return (t.text or "").strip() if t is not None and t.text else ""


# ─────────────────────────────────────────────────────────────
# E. 인벤토리
# ─────────────────────────────────────────────────────────────
def dump_E():
    print("\n[E] 원문 XML 인벤토리 ...")
    SOURCE_LABEL = {
        "main": "메인 사업보고서",
        "audit_separate": "별도 감사보고서",
        "audit_consolidated": "연결 감사보고서",
    }

    lines = []
    lines.append("=" * 90)
    lines.append("원문 XML 인벤토리 (3사 × 3 XML = 9개)")
    lines.append("=" * 90)
    lines.append(f"{'회사':<10} {'종류':<18} {'파일명':<32} {'크기(bytes)':>12} {'줄수':>8}")
    lines.append("-" * 90)

    headers = []  # (회사, filename, root) 저장 → 메타 출력용
    for name, zp in ZIPS:
        items = _read_xmls(zp)
        for filename, stype, raw in items:
            n_lines = raw.count(b"\n") + 1
            size = len(raw)
            label = SOURCE_LABEL.get(stype, stype)
            short_fn = Path(filename).name
            lines.append(
                f"{name:<10} {label:<18} {short_fn:<32} {size:>12,} {n_lines:>8,}"
            )
            try:
                root = parse_xml(raw)
            except Exception as e:
                root = None
            headers.append((name, short_fn, stype, root))

    lines.append("")
    lines.append("=" * 90)
    lines.append("각 XML 의 루트 메타 + 최상위 SECTION-1 개수")
    lines.append("=" * 90)

    for name, fn, stype, root in headers:
        lines.append(f"\n[{name} / {fn}]")
        if root is None:
            lines.append("  (파싱 실패)")
            continue
        doc_name = root.find("DOCUMENT-NAME")
        comp = root.find("COMPANY-NAME")
        formula = root.find("FORMULA-VERSION")
        if doc_name is not None:
            acode = doc_name.get("ACODE")
            lines.append(
                f"  <DOCUMENT-NAME> : {(doc_name.text or '').strip()}"
                + (f"  (ACODE={acode})" if acode else "")
            )
        if comp is not None:
            cik = comp.get("AREGCIK")
            lines.append(
                f"  <COMPANY-NAME>  : {(comp.text or '').strip()}"
                + (f"  (AREGCIK={cik})" if cik else "")
            )
        if formula is not None:
            adate = formula.get("ADATE")
            lines.append(
                f"  <FORMULA-VERSION>: {(formula.text or '').strip()}"
                + (f"  (ADATE={adate})" if adate else "")
            )
        n_sec1 = len(list(root.iter("SECTION-1")))
        n_sec2 = len(list(root.iter("SECTION-2")))
        n_sec3 = len(list(root.iter("SECTION-3")))
        n_table = len(list(root.iter("TABLE")))
        n_group = len(list(root.iter("TABLE-GROUP")))
        lines.append(
            f"  SECTION-1/2/3 : {n_sec1} / {n_sec2} / {n_sec3}   "
            f"TABLE: {n_table}   TABLE-GROUP: {n_group}"
        )

    out = "\n".join(lines) + "\n"
    (DEBUG / "E_inventory").mkdir(exist_ok=True, parents=True)
    (DEBUG / "E_inventory" / "00_inventory.txt").write_text(out, encoding="utf-8")
    return out


# ─────────────────────────────────────────────────────────────
# F. raw XML pretty-print
# ─────────────────────────────────────────────────────────────
def dump_F():
    print("\n[F] raw XML pretty-print ...")
    parser_pretty = ET.XMLParser(recover=True, remove_blank_text=True)

    for name, zp in ZIPS:
        out_dir = DEBUG / "F_raw_xml" / name
        out_dir.mkdir(exist_ok=True, parents=True)

        items = _read_xmls(zp)
        for filename, stype, raw in items:
            # sanitize (xml_loader 와 동일 패턴) — &amp 처리
            sanitized = re.sub(
                rb"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)",
                b"&amp;",
                raw,
            )
            try:
                root = ET.fromstring(sanitized, parser_pretty)
            except Exception as e:
                (out_dir / f"_PARSE_ERROR_{Path(filename).name}.txt").write_text(
                    f"parse 실패: {e}\n", encoding="utf-8"
                )
                continue

            if stype == "main":
                # 00_전체개요 — DOCUMENT 루트의 직접 자식 중 SECTION-1/BODY 안의 SECTION-1 외
                # = 헤더(DOCUMENT-NAME, COMPANY-NAME, FORMULA-VERSION, SUMMARY) + BODY 자식 중 비-SECTION
                overview_buf = [
                    f"# {name} — DOCUMENT 헤더 + BODY 직속 비-SECTION 요소들\n",
                    f"# 원본 파일: {Path(filename).name}\n",
                ]
                for child in root:
                    tag = child.tag
                    if not isinstance(tag, str):
                        continue
                    if tag in ("BODY",):
                        # BODY 자식 중 SECTION-1 이 아닌 것만 (COVER, TOC 등)
                        overview_buf.append(f"\n--- <{tag}> 직속 비-SECTION 요소들 ---")
                        for gc in child:
                            gt = gc.tag
                            if not isinstance(gt, str):
                                continue
                            if gt == "SECTION-1":
                                continue
                            if gt == "LIBRARY":
                                # LIBRARY 내부에 SECTION-1 있을 수 있음 — 비-SECTION 부분만
                                lib_buf = []
                                for ggc in gc:
                                    if isinstance(ggc.tag, str) and ggc.tag == "SECTION-1":
                                        continue
                                    lib_buf.append(
                                        ET.tostring(ggc, pretty_print=True, encoding="unicode")
                                    )
                                if lib_buf:
                                    overview_buf.append(f"\n[<LIBRARY> 내부 비-SECTION-1]")
                                    overview_buf.extend(lib_buf)
                                continue
                            overview_buf.append(
                                ET.tostring(gc, pretty_print=True, encoding="unicode")
                            )
                    else:
                        overview_buf.append(
                            ET.tostring(child, pretty_print=True, encoding="unicode")
                        )
                (out_dir / "00_전체개요.txt").write_text(
                    "\n".join(overview_buf), encoding="utf-8"
                )

                # SECTION-1 들 — top-level만 (LIBRARY 투명 통과)
                # parse_section_tree 와 동일하게 root.iter("SECTION-1") 쓰되 중첩 SECTION-1 제외
                # DART 데이터에서 SECTION-1 은 중첩되지 않으므로 iter 결과를 그대로 사용
                section1_list = list(root.iter("SECTION-1"))
                titles_seen = []
                for i, sec in enumerate(section1_list, 1):
                    title = _section_title(sec) or f"section{i}"
                    safe = _safe_filename(title, maxlen=20)
                    titles_seen.append(safe)
                    pretty = ET.tostring(
                        sec, pretty_print=True, encoding="unicode"
                    )
                    fname = f"{i:02d}_{safe}.xml"
                    (out_dir / fname).write_text(pretty, encoding="utf-8")

            elif stype == "audit_separate":
                pretty = ET.tostring(root, pretty_print=True, encoding="unicode")
                (out_dir / "audit_별도.xml").write_text(pretty, encoding="utf-8")
            elif stype == "audit_consolidated":
                pretty = ET.tostring(root, pretty_print=True, encoding="unicode")
                (out_dir / "audit_연결.xml").write_text(pretty, encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# G. 섹션 목차 outline
# ─────────────────────────────────────────────────────────────
def _walk_outline(node: SectionNode, depth: int, buf: list[str], stats_by_path: dict, path: list[str]):
    cur_path = path + [node.title] if node.title else path
    indent = "  " * depth
    title = node.title or "(no title)"
    stat_str = ""
    key = " > ".join(cur_path)
    if key in stats_by_path:
        s = stats_by_path[key]
        stat_str = f"   [chunks={s['chunks']}, tables={s['tables']}]"
    buf.append(f"{indent}{title}{stat_str}")
    for ch in node.children:
        _walk_outline(ch, depth + 1, buf, stats_by_path, cur_path)


def dump_G():
    print("\n[G] 섹션 목차 outline ...")
    out_dir = DEBUG / "G_outline"
    out_dir.mkdir(exist_ok=True, parents=True)

    for name, zp in ZIPS:
        # 메인 XML root 가져오기
        root_main = None
        for fn, st, root in load_xmls_from_zip(zp):
            if st == "main":
                root_main = root
                break
        if root_main is None:
            continue
        sections = parse_section_tree(root_main)

        # chunk 통계를 path 단위로 — Parser 로 메인만 추리기 어려우므로 전체에서 main 필터
        chunks = Parser().parse(zp)
        main_chunks = [c for c in chunks if c.metadata["source_xml"] == "main"]
        stats_by_path: dict[str, dict] = {}
        for c in main_chunks:
            p = c.metadata["section_path"]
            d = stats_by_path.setdefault(p, {"chunks": 0, "tables": 0})
            d["chunks"] += 1
            if c.metadata["has_table"]:
                d["tables"] += 1

        buf = [f"[{name} 사업보고서 목차]", ""]
        for s in sections:
            _walk_outline(s, depth=0, buf=buf, stats_by_path=stats_by_path, path=[])
            buf.append("")
        (out_dir / f"{name}_목차.txt").write_text("\n".join(buf), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
def main():
    DEBUG.mkdir(parents=True, exist_ok=True)
    inv = dump_E()
    dump_F()
    dump_G()

    print("\n" + "=" * 70)
    print("E_inventory/00_inventory.txt 내용:")
    print("=" * 70)
    print(inv)


if __name__ == "__main__":
    main()
