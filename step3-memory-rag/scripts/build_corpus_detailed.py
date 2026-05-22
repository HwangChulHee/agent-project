"""docs/corpus_detailed.md 생성 — 코퍼스 27편 검수용 상세 문서.

각 항목:
  - 원제 / 한국어 제목 / URL / 분량 / 관련 에피소드
  - 요약 (자동 추출: 첫 단락에서 1~2줄)
  - 첫 단락 발췌 (200자)

실행:
  uv run python scripts/build_corpus_detailed.py
"""
import re
import urllib.parse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
# fetch_commentary.py 의 SOURCES 재사용
from fetch_commentary import SOURCES

RAW_DIR = Path("data/commentary/raw")
OUT_PATH = Path("docs/corpus_detailed.md")

# ============================================================
# slug → 한국어 제목 + 관련 에피소드 매핑 (수동)
# ============================================================
META = {
    # Wikipedia 영어
    "wiki_en_zarathustra":        ("차라투스트라는 이렇게 말했다", "Ep 1 + Ep 2 (작품 전체)"),
    "wiki_en_nietzsche":          ("프리드리히 니체", "Ep 1~2 (저자 배경)"),
    "wiki_en_ubermensch":         ("위버멘쉬 (초인)", "Ep 1 #5, Ep 2 #4 (직격)"),
    "wiki_en_eternal_return":     ("영원회귀", "Ep 1~2 외 (차라 3부 핵심)"),
    "wiki_en_god_dead":           ("신은 죽었다", "Ep 1 #5 고정 질문 직격"),
    "wiki_en_will_to_power":      ("힘에의 의지", "Ep 1~2 외 (후기 개념)"),
    "wiki_en_last_man":           ("마지막 인간 (종말인)", "Ep 2 #4 직격"),
    "wiki_en_apollonian":         ("아폴론적/디오니소스적", "Ep 1~2 외 (비극의 탄생)"),
    "wiki_en_master_slave":       ("주인-노예 도덕", "Ep 1~2 외 (도덕의 계보)"),
    "wiki_en_nihilism":           ("니힐리즘 (허무주의)", "Ep 1~2 배경 (신 죽음의 귀결)"),
    "wiki_en_zoroaster":          ("조로아스터", "Ep 1 #1 (주인공 이름의 유래)"),
    "wiki_en_gay_science":        ("즐거운 학문", "Ep 1 (§125 '신은 죽었다' 원출처)"),
    "wiki_en_birth_of_tragedy":   ("비극의 탄생", "Ep 1~2 외 (초기 미학)"),
    "wiki_en_ressentiment":       ("르상티망 (원한)", "Ep 1~2 외 (도덕의 계보 개념)"),
    "wiki_en_beyond_good_evil":   ("선악의 저편", "Ep 1~2 외 (차라 후속작)"),
    "wiki_en_genealogy_morality": ("도덕의 계보", "Ep 1~2 외 (도덕 비판)"),
    "wiki_en_amor_fati":          ("아모르 파티 (운명애)", "Ep 1~2 외 (영원회귀 정서적 짝)"),

    # Stanford Encyclopedia of Philosophy
    "sep_nietzsche":                 ("니체 (메인 항목)", "Ep 1~2 (학술 권위)"),
    "sep_nietzsche_life_works":      ("니체의 생애와 저작", "Ep 1~2 (전기적 배경)"),
    "sep_nietzsche_moral_political": ("니체의 도덕·정치 철학", "Ep 1~2 외 (도덕 비판)"),
    "sep_nietzsche_aesthetics":      ("니체의 미학", "Ep 1~2 외 (비극·바그너·디오니소스)"),
    "sep_existentialism":            ("실존주의", "Ep 1~2 배경 (니체의 사상사적 위치)"),
    "sep_schopenhauer":              ("쇼펜하우어", "Ep 1~2 외 (사상적 출발점)"),

    # Internet Encyclopedia of Philosophy
    "iep_nietzsche":     ("니체 (IEP)", "Ep 1~2 (중급 학술 해설)"),
    "iep_nihilism":      ("니힐리즘 (IEP)", "Ep 1~2 배경"),
    "iep_schopenhauer":  ("쇼펜하우어 (IEP)", "Ep 1~2 외 (사상적 출발점)"),
    "iep_germ_idealism": ("독일 관념론 (IEP)", "Ep 1~2 외 (학문적 배경)"),
}

SECTION_TITLES = {
    "wiki": ("Wikipedia (영어)", "wiki_en"),
    "sep":  ("Stanford Encyclopedia of Philosophy (SEP)", "sep_"),
    "iep":  ("Internet Encyclopedia of Philosophy (IEP)", "iep_"),
}


# ============================================================
# URL 재구성 (SOURCES의 kind/title/path에서)
# ============================================================
def build_url(src: dict) -> str:
    if src["kind"] == "wiki":
        t = urllib.parse.quote(src["title"], safe="")
        return f"https://{src['lang']}.wikipedia.org/wiki/{t}"
    if src["kind"] == "sep":
        return f"https://plato.stanford.edu/entries/{src['path']}/"
    if src["kind"] == "iep":
        return f"https://iep.utm.edu/{src['path']}/"
    return "?"


# ============================================================
# 요약 + 첫 단락 추출
# ============================================================
def extract_summary(md_path: Path) -> tuple[str, str]:
    """반환: (요약 1~2줄, 첫 단락 발췌 ~200자)."""
    if not md_path.exists():
        return ("(파일 없음)", "")

    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 헤더 다음 첫 본문 단락 찾기
    paras = []
    buf = []
    in_para = False
    for ln in lines:
        if re.match(r"^#+\s", ln):
            if buf:
                paras.append(" ".join(buf).strip())
                buf = []
            continue
        s = ln.strip()
        if not s:
            if buf:
                paras.append(" ".join(buf).strip())
                buf = []
            continue
        if s.startswith("- "):
            continue  # 리스트 단락 스킵
        buf.append(s)
    if buf:
        paras.append(" ".join(buf).strip())

    # 첫 충분한 단락 (50자 이상) 골라냄
    first = next((p for p in paras if len(p) >= 50), paras[0] if paras else "")

    # 발췌 200자
    excerpt = first[:200].rstrip() + ("…" if len(first) > 200 else "")

    # 요약 — 첫 1~2 문장
    sents = re.split(r"(?<=[.!?])\s+", first)
    summary_sents = []
    total = 0
    for s in sents:
        if total + len(s) > 220:
            break
        summary_sents.append(s)
        total += len(s)
        if len(summary_sents) >= 2:
            break
    summary = " ".join(summary_sents).strip()
    if not summary:
        summary = "(요약 추출 실패)"

    return (summary, excerpt)


# ============================================================
# Main — 마크다운 생성
# ============================================================
def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 그룹화
    groups = {"wiki": [], "sep": [], "iep": []}
    for src in SOURCES:
        groups[src["kind"]].append(src)

    # 통계
    total_chars = 0
    group_chars = {"wiki": 0, "sep": 0, "iep": 0}
    for k, srcs in groups.items():
        for src in srcs:
            p = RAW_DIR / f"{src['slug']}.md"
            if p.exists():
                n = len(p.read_text(encoding="utf-8"))
                total_chars += n
                group_chars[k] += n

    lines = []
    lines.append("# 해설 코퍼스 상세 (Commentary Corpus — Detailed)\n")
    lines.append("> 개인 검수·작업용. 발표 자료용 간략 버전은 별도.\n")
    lines.append(f"- **수집일**: 2026-05-23")
    lines.append(f"- **총 편수**: {len(SOURCES)}편")
    lines.append(f"- **총 분량**: {total_chars:,}자")
    lines.append(f"- **수집 스크립트**: `scripts/fetch_commentary.py`")
    lines.append(f"- **원본 위치**: `data/commentary/raw/`\n")

    lines.append("## 통계\n")
    lines.append("| 출처 | 편수 | 분량 | 비중 |")
    lines.append("|---|---:|---:|---:|")
    for k in ["wiki", "sep", "iep"]:
        name = SECTION_TITLES[k][0]
        n = len(groups[k])
        c = group_chars[k]
        pct = c / total_chars * 100 if total_chars else 0
        lines.append(f"| {name} | {n}편 | {c:,}자 | {pct:.1f}% |")
    lines.append("")

    # 그룹별 상세
    section_num = 0
    for k in ["wiki", "sep", "iep"]:
        section_num += 1
        name = SECTION_TITLES[k][0]
        srcs = groups[k]
        lines.append(f"\n---\n\n## {section_num}. {name} ({len(srcs)}편)\n")

        for i, src in enumerate(srcs, 1):
            slug = src["slug"]
            md_path = RAW_DIR / f"{slug}.md"
            ko_title, episode = META.get(slug, ("(미매핑)", "(미매핑)"))
            url = build_url(src)
            char_count = len(md_path.read_text(encoding="utf-8")) if md_path.exists() else 0
            summary, excerpt = extract_summary(md_path)

            # 원제 — wiki는 title, sep/iep는 path 변형
            if src["kind"] == "wiki":
                orig = src["title"].replace("_", " ")
            else:
                orig = src["path"]

            lines.append(f"### {section_num}.{i} `{slug}`\n")
            lines.append(f"- **원제**: {orig}")
            lines.append(f"- **한국어 제목**: {ko_title}")
            lines.append(f"- **URL**: <{url}>")
            lines.append(f"- **분량**: {char_count:,}자")
            lines.append(f"- **관련 에피소드**: {episode}")
            lines.append(f"- **요약**: {summary}")
            lines.append("")
            lines.append(f"<details><summary>첫 단락 발췌</summary>\n")
            lines.append(f"> {excerpt}\n")
            lines.append("</details>\n")

    # 부록
    lines.append("\n---\n\n## 부록 — 의도적으로 제외한 항목\n")
    lines.append("- **한국어 위키 9편**: 영어 대비 깊이 얕음. 전체 번역 검토했으나 시간·검증 비용 부담으로 영어 원문 유지.")
    lines.append("- **Mencken (1908) 『The Philosophy of Friedrich Nietzsche』**: 첫 영어권 해설서지만 학술 신뢰도 낮고 시대 색 짙어 RAG 노이즈 위험.")
    lines.append("- **Stanford 단독 항목 부재 4편**: `nihilism`, `tragedy`, `wagner`, `existentialism`(IEP 측). Stanford엔 niche 항목 별도 없음, 대신 `nietzsche-aesthetics`로 비극·바그너·디오니소스 흡수.")
    lines.append("- **인물 항목** (Lou Salomé, Paul Rée 등): 작품 자체와 무관, RAG 노이즈.")
    lines.append("- **후기 저작 항목** (The Antichrist, Twilight of the Idols, Ecce Homo): Ep 1~2 시점(1881 직후)과 시대 일관성 깨짐.\n")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ {OUT_PATH} 생성됨")
    print(f"  총 {len(SOURCES)}편 / {total_chars:,}자")
    print(f"  파일 크기: {OUT_PATH.stat().st_size:,} 바이트")


if __name__ == "__main__":
    main()
