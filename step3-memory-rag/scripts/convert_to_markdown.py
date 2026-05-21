"""
Wikipedia text → Markdown 변환기.
== Section ==     →  ## Section
=== Subsection === → ### Subsection
==== Subsubsection ==== → #### Subsubsection
"""
import re
from pathlib import Path

SRC_DIR = Path("data/wikipedia")
DST_DIR = Path("data/wikipedia_md")
DST_DIR.mkdir(parents=True, exist_ok=True)

# == 가장 긴 것부터 매칭해야 안전 (==== 가 == 두 번으로 잘못 잡히지 않게)
HEADER_PATTERNS = [
    (re.compile(r"^==== (.+?) ====\s*$"), r"#### \1"),
    (re.compile(r"^=== (.+?) ===\s*$"),   r"### \1"),
    (re.compile(r"^== (.+?) ==\s*$"),      r"## \1"),
]

def convert(text: str, title: str) -> str:
    lines = text.splitlines()
    out = [f"# {title}", ""]  # 문서 제목을 H1로
    for line in lines:
        converted = line
        for pat, repl in HEADER_PATTERNS:
            new = pat.sub(repl, converted)
            if new != converted:
                converted = new
                break
        out.append(converted)
    return "\n".join(out)

def main():
    src_files = sorted(SRC_DIR.glob("*.txt"))
    if not src_files:
        print(f"ERROR: {SRC_DIR}에 .txt 파일 없음")
        return

    for src in src_files:
        title = src.stem.replace("_", " ")
        dst = DST_DIR / f"{src.stem}.md"
        md_text = convert(src.read_text(encoding="utf-8"), title)
        dst.write_text(md_text, encoding="utf-8")

        # 헤더 개수 카운트
        n_h2 = md_text.count("\n## ")
        n_h3 = md_text.count("\n### ")
        n_h4 = md_text.count("\n#### ")
        print(f"  {src.stem:30s}  H2={n_h2:3d}  H3={n_h3:3d}  H4={n_h4:3d}  ({len(md_text):,} chars)")

    print(f"\nDone: {len(src_files)} files → {DST_DIR}/")

if __name__ == "__main__":
    main()
