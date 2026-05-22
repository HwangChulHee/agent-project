"""docs/corpus_summary.md 생성 — 발표 슬라이드 1장용 간략 표.

3컬럼: # | 제목(한글) | 분량
출처별 그룹화. 상단에 통계.

실행:
  uv run python scripts/build_corpus_summary.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_commentary import SOURCES
from build_corpus_detailed import META

RAW_DIR = Path("data/commentary/raw")
OUT_PATH = Path("docs/corpus_summary.md")

GROUP_LABELS = {
    "wiki": "Wikipedia (영어)",
    "sep":  "Stanford SEP",
    "iep":  "IEP",
}


def fmt_bytes(n: int) -> str:
    """파일 용량. 32198 → '31KB', 162084 → '158KB', 1664461 → '1.6MB'."""
    if n >= 1024 * 1024:
        return f"{n/(1024*1024):.1f}MB"
    if n >= 1024:
        return f"{n//1024}KB"
    return f"{n}B"


def fmt_tokens(char_count: int) -> str:
    """영어 코퍼스 어림: 1토큰 ≈ 4자. 32198자 → '~8K'."""
    n = char_count // 4
    if n >= 1_000_000:
        return f"~{n/1_000_000:.1f}M"
    if n >= 1000:
        return f"~{n//1000}K"
    return f"~{n}"


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 그룹화
    groups = {"wiki": [], "sep": [], "iep": []}
    for src in SOURCES:
        groups[src["kind"]].append(src)

    # 분량 집계 (파일 용량 바이트 + 문자 수)
    total_bytes = 0
    total_chars = 0
    group_bytes = {"wiki": 0, "sep": 0, "iep": 0}
    group_chars = {"wiki": 0, "sep": 0, "iep": 0}
    for k, srcs in groups.items():
        for src in srcs:
            p = RAW_DIR / f"{src['slug']}.md"
            if p.exists():
                b = p.stat().st_size
                c = len(p.read_text(encoding="utf-8"))
                group_bytes[k] += b
                group_chars[k] += c
                total_bytes += b
                total_chars += c

    lines = []
    lines.append("# 해설 코퍼스 (Commentary Corpus)\n")

    # 한 줄 통계
    parts = [f"**총 {len(SOURCES)}편 · {fmt_bytes(total_bytes)} · {fmt_tokens(total_chars)} 토큰 (추정)**"]
    for k in ["wiki", "sep", "iep"]:
        parts.append(f"{GROUP_LABELS[k]} {len(groups[k])}편")
    lines.append(" · ".join(parts) + "\n")

    # 그룹별 표
    counter = 1
    for k in ["wiki", "sep", "iep"]:
        srcs = groups[k]
        label = GROUP_LABELS[k]
        lines.append(f"\n## {label} ({len(srcs)}편 · {fmt_bytes(group_bytes[k])} · {fmt_tokens(group_chars[k])} 토큰)\n")
        lines.append("| # | 항목 | 용량 | 토큰(추정) |")
        lines.append("|---:|---|---:|---:|")
        for src in srcs:
            slug = src["slug"]
            ko_title, _ = META.get(slug, ("(미매핑)", ""))
            p = RAW_DIR / f"{slug}.md"
            if p.exists():
                b = p.stat().st_size
                c = len(p.read_text(encoding="utf-8"))
            else:
                b, c = 0, 0
            lines.append(f"| {counter} | {ko_title} | {fmt_bytes(b)} | {fmt_tokens(c)} |")
            counter += 1

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ {OUT_PATH} 생성됨")
    print(f"  총 {len(SOURCES)}편 · {fmt_bytes(total_bytes)} · {fmt_tokens(total_chars)} 토큰(추정)")
    print(f"  문서 파일 크기: {OUT_PATH.stat().st_size:,} 바이트")


if __name__ == "__main__":
    main()
