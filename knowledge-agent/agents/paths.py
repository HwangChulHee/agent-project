"""파이프라인 경로·메타 중앙 집중.
경로 규칙(data/parsed/{id}/{id}_0N.*)을 한 곳에만 둔다 — 8개 스크립트가 공유.
산출물 이름 바꿀 일 생기면 여기만 고침. 각 스크립트는 --paper 받아 paper_paths(id) 호출.
"""
import os
import re
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_PATH = os.path.join(ROOT, "data", "knowledge_map.json")
RAW_DIR = os.path.join(ROOT, "data", "raw_papers")
PARSED_DIR = os.path.join(ROOT, "data", "parsed")


def paper_paths(paper_id: str) -> dict:
    base = os.path.join(PARSED_DIR, paper_id)
    p = lambda suf: os.path.join(base, f"{paper_id}_{suf}")
    return {
        "base": base,
        "01_md": p("01.md"),
        "02": p("02.segments.json"),
        "03": p("03.summaries.json"),
        "04": p("04.concepts.json"),
        "05": p("05.aligned.json"),
        "06_stage1": p("06.stage1.json"),
        "06_relations": p("06.relations.json"),
        "06_exceptions": p("06.exceptions.json"),
        "07_conflicts": p("07.conflicts.json"),
        "08a": p("08.integrated.json"),
    }


def find_pdf(paper_id: str) -> str:
    """data/raw_papers 안에서 arxiv id 포함하는 PDF 찾기 (파일명 prefix 허용)."""
    hits = glob.glob(os.path.join(RAW_DIR, f"*{paper_id}*.pdf"))
    if not hits:
        raise FileNotFoundError(f"PDF 못 찾음: {RAW_DIR}/*{paper_id}*.pdf")
    return hits[0]


def pub_date_from_id(paper_id: str) -> str:
    """arxiv id의 YYMM → 'YYYY-MM'. 예: '2210.03629' → '2022-10'.
    신형 id(2007.04+) 가정. 구형/비표준이면 None."""
    m = re.match(r"^(\d{2})(\d{2})\.", paper_id)
    if not m:
        return None
    yy, mm = m.group(1), m.group(2)
    return f"20{yy}-{mm}"


def ensure_base(paper_id: str):
    os.makedirs(paper_paths(paper_id)["base"], exist_ok=True)
