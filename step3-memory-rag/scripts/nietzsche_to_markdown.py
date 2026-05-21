"""
Thus Spake Zarathustra (Project Gutenberg, Common 번역) 본문 → Markdown.

변환:
  FIRST PART. ZARATHUSTRA'S DISCOURSES.   →  # FIRST PART
  ZARATHUSTRA'S PROLOGUE.                  →  ## Prologue
  VII. READING AND WRITING.                →  ## VII. Reading and Writing
  ^N.$ (단독 절 번호)                       →  ### Section N
"""
import re
from pathlib import Path

SRC = Path("data/nietzsche/zarathustra_en_body.txt")
DST_DIR = Path("data/nietzsche_md")
DST_DIR.mkdir(parents=True, exist_ok=True)
DST = DST_DIR / "zarathustra_en.md"

# Part 헤더: "FIRST PART.", "FIRST PART. ZARATHUSTRA'S DISCOURSES." 등
PART_RE = re.compile(
    r"^(?:THUS SPAKE ZARATHUSTRA\.\s+)?"
    r"(FIRST|SECOND|THIRD|FOURTH(?:\s+AND\s+LAST)?)\s+PART\."
    r".*$",
    re.IGNORECASE,
)
# Prologue
PROLOGUE_RE = re.compile(r"^ZARATHUSTRA.S\s+PROLOGUE\.\s*$", re.IGNORECASE)
# 챕터: "VII. READING AND WRITING." — 로마숫자 + 점 + 영문 제목 + 마침표
CHAPTER_RE = re.compile(r"^([IVXLC]+)\.\s+([A-Z][A-Z .,;:\-''']+)\.\s*$")
# 단독 절 번호: "1." "10." 등
SECTION_NUM_RE = re.compile(r"^(\d+)\.\s*$")


def smart_title(s: str) -> str:
    """단순 title() — 'And', 'The', 'Of' 등도 대문자 되지만 차라투스트라엔 큰 문제 없음."""
    return s.strip().title()


def normalize_part(label: str) -> str:
    """'FOURTH AND LAST' → 'FOURTH PART'."""
    label = re.sub(r"\s+AND\s+LAST", "", label.strip(), flags=re.IGNORECASE)
    return label.upper() + " PART"


def convert(text: str) -> str:
    out = ["# Thus Spake Zarathustra", ""]
    out.append("> A Book for All and None — Friedrich Nietzsche (trans. Thomas Common, 1909)")
    out.append("")

    # 카운터 (메타 추출용)
    n_parts = n_prologue = n_chapters = n_sections = 0

    for raw in text.splitlines():
        line = raw.rstrip()

        m = PART_RE.match(line)
        if m:
            label = normalize_part(m.group(1))
            out.append(f"\n# {label}\n")
            n_parts += 1
            continue

        if PROLOGUE_RE.match(line):
            out.append("\n## Prologue\n")
            n_prologue += 1
            continue

        m = CHAPTER_RE.match(line)
        if m:
            roman, title = m.group(1), smart_title(m.group(2))
            out.append(f"\n## {roman}. {title}\n")
            n_chapters += 1
            continue

        m = SECTION_NUM_RE.match(line)
        if m:
            out.append(f"\n### Section {m.group(1)}\n")
            n_sections += 1
            continue

        out.append(line)

    # 연속 빈 줄 → 최대 1개로 압축 (이미 헤더 위아래에 의도 빈 줄 있음)
    result = "\n".join(out)
    result = re.sub(r"\n{3,}", "\n\n", result)

    print(f"Parts:    {n_parts}")
    print(f"Prologue: {n_prologue}")
    print(f"Chapters: {n_chapters}")
    print(f"Sections: {n_sections}")
    return result


def main():
    text = SRC.read_text(encoding="utf-8")
    md = convert(text)
    DST.write_text(md, encoding="utf-8")
    print(f"\nWrote {DST} ({len(md):,} chars)")


if __name__ == "__main__":
    main()
