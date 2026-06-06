import pymupdf4llm

PDF = "data/raw_papers/react_2210.03629.pdf"

# 텍스트 PDF라 OCR 불필요. use_ocr/ocr 옵션을 끄고 시도.
try:
    md = pymupdf4llm.to_markdown(PDF, use_ocr=False)
except TypeError:
    # 이 버전이 use_ocr 인자를 모르면 ocr=False로 재시도
    md = pymupdf4llm.to_markdown(PDF, ocr=False)

lines = md.split("\n")

print(f"=== TOTAL: {len(md)} chars, {len(lines)} lines ===\n")

print("=== HEADER-LIKE LINES (md헤더 + 볼드만 + 짧은 대문자) ===")
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s:
        continue
    is_md_header = s.startswith("#")
    is_bold_only = s.startswith("**") and s.endswith("**") and len(s) < 60
    is_caps = s.isupper() and 3 < len(s) < 40
    if is_md_header or is_bold_only or is_caps:
        print(f"{i:5} | {s[:70]}")

print("\n=== SECTION KEYWORDS (references / appendix / acknowled) ===")
for i, ln in enumerate(lines):
    low = ln.lower()
    if any(k in low for k in ["reference", "appendix", "acknowled"]):
        print(f"{i:5} | {ln.strip()[:70]}")

print("\n=== FIRST 1500 CHARS (헤더 모양 샘플) ===")
print(md[:1500])
