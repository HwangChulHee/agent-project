"""해설 코퍼스 27편 → 청크 JSONL.

분할 계층: H2 → 너무 크면 H3 → 너무 크면 단락.
청크 크기: 300~3500자 (목표 1200~2800).
메타 섹션(References 등)은 통째로 skip.
HTML 엔티티 잔여(&rsquo; 등) 정리.

출력: data/commentary/chunks.jsonl + 콘솔 통계.

사용:
  uv run python scripts/chunk_commentary.py
"""
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_commentary import SOURCES
from build_corpus_detailed import META

RAW_DIR = Path("data/commentary/raw")
OUT_PATH = Path("data/commentary/chunks.jsonl")

# 청크 크기 정책 (자)
MIN_CHARS = 300
MAX_CHARS = 3500
TARGET_HI = 2800

# ============================================================
# 메타 섹션 블랙리스트 (H2 제목 정규화 후 비교)
# ============================================================
META_SECTION_KEYWORDS = {
    # Wikipedia
    "references", "reference", "notes", "note", "citations", "citation",
    "bibliography", "further reading", "see also", "external links",
    "external link", "works cited", "sources", "selected editions",
    # Stanford SEP
    "academic tools", "academic tool", "other internet resources",
    "other internet resource", "related entries", "related entry",
    "acknowledgments",
    # IEP
    "author information", "references and further reading",
    # 페이지 푸터류
    "browse by topic", "an encyclopedia of philosophy articles written by professional philosophers",
    "internet encyclopedia of philosophy", "table of contents",
}

# Bibliography 이후 모든 섹션 차단용 (SEP 끝 부분이 길게 이어짐)
BIB_BREAK_KEYWORDS = {"bibliography", "references", "references and further reading"}


# ============================================================
# HTML 엔티티 잔여 정리
# ============================================================
HTML_ENT_LEFTOVER = {
    "&rsquo;": "'", "&lsquo;": "'",
    "&ldquo;": '"', "&rdquo;": '"',
    "&hellip;": "…", "&ndash;": "–", "&mdash;": "—",
    "&laquo;": "«", "&raquo;": "»",
    "&middot;": "·",
}


def clean_text(s: str) -> str:
    for k, v in HTML_ENT_LEFTOVER.items():
        s = s.replace(k, v)
    # 숫자 엔티티 잔여
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    return s


def normalize_header(h: str) -> str:
    """## 1.1 Foo Bar → 'foo bar'. 번호·기호 제거 + 소문자."""
    s = re.sub(r"^#+\s*", "", h)
    s = re.sub(r"^\d+(\.\d+)*\s*\.?\s*", "", s)  # 1, 1.1, 1.1.1
    s = clean_text(s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def is_meta_section(header: str) -> bool:
    norm = normalize_header(header)
    if norm in META_SECTION_KEYWORDS:
        return True
    # 부분 매치 (예: "selected editions" 등 변형)
    for kw in META_SECTION_KEYWORDS:
        if norm == kw or norm.startswith(kw + " ") or norm.endswith(" " + kw):
            return True
    return False


def is_bib_break(header: str) -> bool:
    """이 H2 등장 이후의 모든 섹션은 skip."""
    norm = normalize_header(header)
    return norm in BIB_BREAK_KEYWORDS


# ============================================================
# 분할 함수
# ============================================================
def split_by_header(text: str, level: int) -> list[tuple[str, str]]:
    """level=2 → ##, level=3 → ###. 반환: [(header_line, body), ...].
    첫 헤더 이전 본문은 ('', body)로.
    """
    pattern = r"^(#{" + str(level) + r"} .+)$"
    parts = re.split(pattern, text, flags=re.M)
    out = []
    if parts[0].strip():
        out.append(("", parts[0].strip()))
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        out.append((header, body))
    return out


def split_by_paragraph(text: str) -> list[str]:
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if p.strip()]


def pack_paragraphs(text: str, prefix: str = "") -> list[str]:
    """단락들을 TARGET_HI 한도로 packing. 헤더 프리픽스는 각 청크 앞에."""
    paras = split_by_paragraph(text)
    out = []
    buf = []
    buf_len = 0
    pre_len = len(prefix) + 2 if prefix else 0

    for p in paras:
        if buf_len + len(p) + 2 > TARGET_HI and buf:
            joined = "\n\n".join(buf)
            full = f"{prefix}\n\n{joined}" if prefix else joined
            out.append(full)
            buf = [p]
            buf_len = len(p) + pre_len
        else:
            buf.append(p)
            buf_len += len(p) + 2
    if buf:
        joined = "\n\n".join(buf)
        full = f"{prefix}\n\n{joined}" if prefix else joined
        out.append(full)
    return out


def merge_small_chunks(chunks: list[dict]) -> list[dict]:
    if not chunks:
        return []
    out = [chunks[0]]
    for c in chunks[1:]:
        if len(out[-1]["text"]) < MIN_CHARS:
            out[-1]["text"] = out[-1]["text"] + "\n\n" + c["text"]
        else:
            out.append(c)
    if len(out) > 1 and len(out[-1]["text"]) < MIN_CHARS:
        last = out.pop()
        out[-1]["text"] = out[-1]["text"] + "\n\n" + last["text"]
    return out


# ============================================================
# 메인 청킹
# ============================================================
def chunk_document(md_text: str) -> list[dict]:
    h2_sections = split_by_header(md_text, 2)
    chunks = []
    bib_reached = False  # Bibliography 만나면 이후 모두 skip

    for h2_header, h2_body in h2_sections:
        if bib_reached:
            continue

        if h2_header:
            if is_bib_break(h2_header):
                bib_reached = True
                continue
            if is_meta_section(h2_header):
                continue

        h2_body = clean_text(h2_body)
        if not h2_body and not h2_header:
            continue
        h2_header_clean = clean_text(h2_header) if h2_header else ""

        h2_text = (f"{h2_header_clean}\n\n{h2_body}"
                   if h2_header_clean else h2_body).strip()
        if not h2_text or len(h2_text) < 50:
            continue

        if len(h2_text) <= MAX_CHARS:
            chunks.append({
                "section_path": h2_header_clean or "(intro)",
                "text": h2_text,
            })
            continue

        # H2 너무 큼 → H3 분할
        h3_sections = split_by_header(h2_body, 3)
        if len(h3_sections) <= 1:
            for para_chunk in pack_paragraphs(h2_body, prefix=h2_header_clean):
                chunks.append({
                    "section_path": h2_header_clean or "(intro)",
                    "text": para_chunk,
                })
            continue

        for h3_header, h3_body in h3_sections:
            h3_header_clean = clean_text(h3_header) if h3_header else ""
            h3_body = clean_text(h3_body)
            if h3_header_clean and is_meta_section(h3_header_clean):
                continue
            sec_path = (f"{h2_header_clean} > {h3_header_clean}"
                        if h3_header_clean else h2_header_clean)

            h3_text = (f"{h2_header_clean}\n{h3_header_clean}\n\n{h3_body}"
                       if h3_header_clean else f"{h2_header_clean}\n\n{h3_body}").strip()
            if not h3_text or len(h3_text) < 50:
                continue

            if len(h3_text) <= MAX_CHARS:
                chunks.append({"section_path": sec_path, "text": h3_text})
            else:
                prefix = (f"{h2_header_clean}\n{h3_header_clean}"
                          if h3_header_clean else h2_header_clean)
                for para_chunk in pack_paragraphs(h3_body, prefix=prefix):
                    chunks.append({"section_path": sec_path, "text": para_chunk})

    return merge_small_chunks(chunks)


# ============================================================
# Main
# ============================================================
def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_chunks = []
    per_doc = []

    for src in SOURCES:
        slug = src["slug"]
        md_path = RAW_DIR / f"{slug}.md"
        if not md_path.exists():
            print(f"  SKIP {slug} (파일 없음)")
            continue

        md = md_path.read_text(encoding="utf-8")
        chunks = chunk_document(md)
        ko_title, _ = META.get(slug, ("(미매핑)", ""))

        for i, c in enumerate(chunks):
            all_chunks.append({
                "chunk_id": f"{slug}_{i:04d}",
                "source_id": slug,
                "source_type": "commentary",
                "title_ko": ko_title,
                "section_path": c["section_path"],
                "lang": "en",
                "text": c["text"],
                "char_count": len(c["text"]),
            })

        if chunks:
            char_lens = [len(c["text"]) for c in chunks]
            per_doc.append({
                "slug": slug,
                "n_chunks": len(chunks),
                "avg_chars": int(statistics.mean(char_lens)),
                "min_chars": min(char_lens),
                "max_chars": max(char_lens),
            })
        else:
            per_doc.append({"slug": slug, "n_chunks": 0,
                            "avg_chars": 0, "min_chars": 0, "max_chars": 0})

    # JSONL 저장
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # 통계
    print(f"\n━━ 문서별 ━━")
    print(f"{'slug':40s} {'n':>4} {'avg':>5} {'min':>5} {'max':>5}")
    print("-" * 65)
    for d in per_doc:
        print(f"{d['slug']:40s} {d['n_chunks']:>4} {d['avg_chars']:>5} "
              f"{d['min_chars']:>5} {d['max_chars']:>5}")

    print(f"\n━━ 전체 ━━")
    print(f"  총 청크 수: {len(all_chunks)}")
    if all_chunks:
        char_lens = [c["char_count"] for c in all_chunks]
        print(f"  자 수: min={min(char_lens)}  mean={statistics.mean(char_lens):.0f}  "
              f"p50={statistics.median(char_lens):.0f}  max={max(char_lens)}")
        over = sum(1 for n in char_lens if n > MAX_CHARS)
        under = sum(1 for n in char_lens if n < MIN_CHARS)
        print(f"  MAX_CHARS({MAX_CHARS}) 초과: {over}")
        print(f"  MIN_CHARS({MIN_CHARS}) 미만: {under}")

    print(f"\n  출력: {OUT_PATH} ({OUT_PATH.stat().st_size:,} 바이트)")


if __name__ == "__main__":
    main()
