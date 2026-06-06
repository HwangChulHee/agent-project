import re
import os
from collections import Counter
import pymupdf4llm

CUT_HEADER = re.compile(r"^##\s+REFERENCES\b", re.IGNORECASE)
PARSED_DIR = "data/parsed"

# 캡션(Figure N:/Table N:)을 지울지. False = 살림(개념 이름 보존, 추천)
DROP_CAPTIONS = False


def _parse_pdf(pdf_path: str) -> str:
    try:
        return pymupdf4llm.to_markdown(pdf_path, use_ocr=False)
    except TypeError:
        return pymupdf4llm.to_markdown(pdf_path, ocr=False)


def _cut_references(md: str) -> str:
    lines = md.split("\n")
    for i, ln in enumerate(lines):
        if CUT_HEADER.match(ln.strip()):
            return "\n".join(lines[:i]).rstrip()
    return md


def _strip_noise(md: str, drop_captions: bool = DROP_CAPTIONS) -> str:
    """깨진 표·그림·페이지 가구 제거. 인라인 수치는 안 건드림(SA가 처리)."""
    lines = md.split("\n")

    # 러닝 헤더 = 4회 이상 반복되는 짧은 줄 (예: "Published as a conference...")
    freq = Counter(ln.strip() for ln in lines if ln.strip())
    running = {s for s, c in freq.items() if c >= 4 and len(s) < 80}

    out, in_picture = [], False
    for ln in lines:
        s = ln.strip()

        # 그림 텍스트 블록: Start~End 통째 제거 (� 덩어리)
        if "Start of picture text" in s:
            in_picture = True
            continue
        if in_picture:
            if "End of picture text" in s:
                in_picture = False
            continue

        if "intentionally omitted" in s:      # 그림 자리표시자
            continue
        if s.startswith("|"):                  # 깨진 표 행
            continue
        if re.fullmatch(r"\d+", s):            # 페이지 번호만 있는 줄
            continue
        if s in running:                       # 반복 러닝 헤더
            continue
        if drop_captions and re.match(r"^(Figure|Table)\s+\d+", s):
            continue

        out.append(ln)

    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)     # 빈 줄 3+ → 2
    return text.strip()


def _arxiv_id_from_name(pdf_path: str) -> str:
    name = pdf_path.rsplit("/", 1)[-1]
    m = re.search(r"(\d{4}\.\d{4,5})", name)
    return m.group(1) if m else ""


def ingest(pdf_path: str) -> dict:
    raw = _parse_pdf(pdf_path)
    body = _strip_noise(_cut_references(raw))
    arxiv_id = _arxiv_id_from_name(pdf_path)

    out_name = arxiv_id or pdf_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    paper_dir = os.path.join(PARSED_DIR, out_name)
    os.makedirs(paper_dir, exist_ok=True)
    parsed_path = os.path.join(paper_dir, f"{out_name}_01.md")
    with open(parsed_path, "w", encoding="utf-8") as f:
        f.write(body)

    return {
        "text": body,
        "arxiv_id": arxiv_id,
        "source_file": pdf_path.rsplit("/", 1)[-1],
        "parsed_path": parsed_path,
    }


if __name__ == "__main__":
    PDF = "data/raw_papers/react_2210.03629.pdf"
    doc = ingest(PDF)
    print(f"arxiv_id    : {doc['arxiv_id']}")
    print(f"parsed_path : {doc['parsed_path']}")
    print(f"body length : {len(doc['text'])} chars, {len(doc['text'].splitlines())} lines")
    print(f"\n남은 '|' 줄 수: {sum(1 for l in doc['text'].splitlines() if l.strip().startswith('|'))}  (0이어야 표 제거 성공)")
    print(f"남은 '�' 개수: {doc['text'].count(chr(0xFFFD))}  (0이어야 그림 잔해 제거 성공)")
