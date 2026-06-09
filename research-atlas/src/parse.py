"""01 parse: PDF → abstract+intro 텍스트 → {paper_id}.parsed.json
   섹션 경계로 자르되, 못 찾으면 HEAD_CHARS로 fallback."""
import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

HEAD_CHARS = 6000  # fallback

# "다음 섹션"이 시작되는 신호 (intro 다음). 줄 시작 기준.
NEXT_SECTION = re.compile(
    r"(?im)^\s*("
    r"2\s+[A-Z]"            # "2 Related..." (번호 + 대문자)
    r"|2\.\s+[A-Z]"         # "2. Related..."
    r"|##?\s*2\b"           # markdown "## 2"
    r"|related work"
    r"|background"
    r"|preliminaries"
    r"|2\s+related"
    r")"
)
ABSTRACT = re.compile(r"(?i)\babstract\b")


def find_cut(text: str) -> tuple[str, str]:
    """(잘린 텍스트, 사용된 방식) 반환."""
    # 시작점: Abstract 위치 (없으면 0)
    m_abs = ABSTRACT.search(text)
    start = m_abs.start() if m_abs else 0

    # 끝점: start 이후 첫 '다음 섹션' 헤더
    m_next = NEXT_SECTION.search(text, pos=start + 50)  # +50: abstract 단어 자체 회피
    if m_next:
        return text[start:m_next.start()], "section"
    # 못 찾으면 fallback
    return text[:HEAD_CHARS], "head6000"


def parse_one(paper_id: str) -> dict:
    pdf_path = config.PDF_DIR / f"{paper_id}.pdf"
    if not pdf_path.exists():
        return {"paper_id": paper_id, "ok": False, "reason": "PDF 없음", "text": ""}

    doc = pymupdf.open(str(pdf_path))
    # 앞쪽 몇 페이지면 abstract+intro 충분 (전체 안 읽음)
    parts, total = [], 0
    for page in doc:
        t = page.get_text()
        parts.append(t)
        total += len(t)
        if total >= 20000:  # 넉넉히 모아두고 그 안에서 경계 탐색
            break
    doc.close()
    full = "".join(parts)

    text, method = find_cut(full)
    return {
        "paper_id": paper_id,
        "ok": True,
        "cut_method": method,
        "char_count": len(text),
        "text": text,
    }


def main():
    for pid in config.PAPER_IDS:
        r = parse_one(pid)
        (config.OUT_DIR / f"{pid}.parsed.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=2)
        )
        if r["ok"]:
            print(f"{pid}: {r['char_count']}자 [{r['cut_method']}]")
        else:
            print(f"{pid}: 실패({r['reason']})")


if __name__ == "__main__":
    main()
