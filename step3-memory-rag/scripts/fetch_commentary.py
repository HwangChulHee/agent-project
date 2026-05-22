"""해설 자료(위키 영어 + Stanford SEP + IEP) 15편 fetch → 마크다운 저장.

사용법:
  uv run python scripts/fetch_commentary.py            # 스모크 3편
  uv run python scripts/fetch_commentary.py --run      # 전체 15편

출력:
  data/commentary/raw/{slug}.md
"""
import argparse
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT_DIR = Path("data/commentary/raw")
UA = "ZarathustraCapstone/1.0 (academic; agent-project)"

# ============================================================
# SOURCES — slug가 파일명, kind가 fetcher 분기
# ============================================================
SOURCES = [
    # Wikipedia 영어 (11편)
    {"kind": "wiki", "lang": "en", "title": "Thus_Spoke_Zarathustra",  "slug": "wiki_en_zarathustra"},
    {"kind": "wiki", "lang": "en", "title": "Friedrich_Nietzsche",      "slug": "wiki_en_nietzsche"},
    {"kind": "wiki", "lang": "en", "title": "Übermensch",               "slug": "wiki_en_ubermensch"},
    {"kind": "wiki", "lang": "en", "title": "Eternal_return",           "slug": "wiki_en_eternal_return"},
    {"kind": "wiki", "lang": "en", "title": "God_is_dead",              "slug": "wiki_en_god_dead"},
    {"kind": "wiki", "lang": "en", "title": "Will_to_power",            "slug": "wiki_en_will_to_power"},
    {"kind": "wiki", "lang": "en", "title": "Last_man",                 "slug": "wiki_en_last_man"},
    {"kind": "wiki", "lang": "en", "title": "Apollonian_and_Dionysian", "slug": "wiki_en_apollonian"},
    {"kind": "wiki", "lang": "en", "title": "Master–slave_morality",    "slug": "wiki_en_master_slave"},
    {"kind": "wiki", "lang": "en", "title": "Nihilism",                 "slug": "wiki_en_nihilism"},
    {"kind": "wiki", "lang": "en", "title": "Zoroaster",                "slug": "wiki_en_zoroaster"},
    {"kind": "wiki", "lang": "en", "title": "The_Gay_Science",          "slug": "wiki_en_gay_science"},
    {"kind": "wiki", "lang": "en", "title": "The_Birth_of_Tragedy",     "slug": "wiki_en_birth_of_tragedy"},
    {"kind": "wiki", "lang": "en", "title": "Ressentiment",             "slug": "wiki_en_ressentiment"},
    {"kind": "wiki", "lang": "en", "title": "Beyond_Good_and_Evil",     "slug": "wiki_en_beyond_good_evil"},
    {"kind": "wiki", "lang": "en", "title": "On_the_Genealogy_of_Morality", "slug": "wiki_en_genealogy_morality"},
    {"kind": "wiki", "lang": "en", "title": "Amor_fati",                "slug": "wiki_en_amor_fati"},

    # Stanford Encyclopedia of Philosophy (5편)
    {"kind": "sep", "path": "nietzsche",                 "slug": "sep_nietzsche"},
    {"kind": "sep", "path": "nietzsche-life-works",      "slug": "sep_nietzsche_life_works"},
    {"kind": "sep", "path": "nietzsche-moral-political", "slug": "sep_nietzsche_moral_political"},
    {"kind": "sep", "path": "nietzsche-aesthetics",      "slug": "sep_nietzsche_aesthetics"},
    {"kind": "sep", "path": "existentialism",            "slug": "sep_existentialism"},
    {"kind": "sep", "path": "schopenhauer",              "slug": "sep_schopenhauer"},

    # Internet Encyclopedia of Philosophy (4편)
    {"kind": "iep", "path": "nietzsch", "slug": "iep_nietzsche"},
    {"kind": "iep", "path": "nihilism", "slug": "iep_nihilism"},
    {"kind": "iep", "path": "schopenh", "slug": "iep_schopenhauer"},
    {"kind": "iep", "path": "germidea", "slug": "iep_germ_idealism"},
]

SMOKE_SLUGS = ["wiki_en_zarathustra", "sep_nietzsche", "iep_nietzsche"]


# ============================================================
# Fetcher
# ============================================================
def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_one(src: dict) -> str:
    if src["kind"] == "wiki":
        title = urllib.parse.quote(src["title"], safe="")
        url = f"https://{src['lang']}.wikipedia.org/api/rest_v1/page/html/{title}"
    elif src["kind"] == "sep":
        url = f"https://plato.stanford.edu/entries/{src['path']}/"
    elif src["kind"] == "iep":
        url = f"https://iep.utm.edu/{src['path']}/"
    else:
        raise ValueError(f"unknown kind: {src['kind']}")

    html = fetch_html(url)
    return clean_html(html)


# ============================================================
# HTML → Markdown (정규식 기반, zero-deps)
# ============================================================
NOISE_CLASSES = [
    "infobox", "sidebar", "navbox", "reflist", "reference",
    "mw-editsection", "hatnote", "ambox", "thumb",
    "navigation-not-searchable", "metadata",
]

HTML_ENT = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&apos;": "'",
    "&mdash;": "—", "&ndash;": "–", "&hellip;": "…",
}


def clean_html(html: str) -> str:
    s = html

    # script/style/주석 제거
    s = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1>", "", s, flags=re.I)
    s = re.sub(r"<!--[\s\S]*?-->", "", s)

    # 정형 노이즈 클래스 제거
    for cls in NOISE_CLASSES:
        pat = rf'<(\w+)\b[^>]*class="[^"]*\b{cls}\b[^"]*"[^>]*>[\s\S]*?</\1>'
        s = re.sub(pat, "", s, flags=re.I)

    # 표·그림·이미지
    s = re.sub(r"<table\b[^>]*>[\s\S]*?</table>", "", s, flags=re.I)
    s = re.sub(r"<figure\b[^>]*>[\s\S]*?</figure>", "", s, flags=re.I)
    s = re.sub(r"<img\b[^>]*/?>", "", s, flags=re.I)

    # 각주
    s = re.sub(r'<sup\b[^>]*class="[^"]*reference[^"]*"[^>]*>[\s\S]*?</sup>',
               "", s, flags=re.I)
    s = re.sub(r"\[\d+\]", "", s)

    # 헤더
    s = re.sub(r"<h1\b[^>]*>([\s\S]*?)</h1>", r"\n\n# \1\n\n", s, flags=re.I)
    s = re.sub(r"<h2\b[^>]*>([\s\S]*?)</h2>", r"\n\n## \1\n\n", s, flags=re.I)
    s = re.sub(r"<h3\b[^>]*>([\s\S]*?)</h3>", r"\n\n### \1\n\n", s, flags=re.I)
    s = re.sub(r"<h4\b[^>]*>([\s\S]*?)</h4>", r"\n\n#### \1\n\n", s, flags=re.I)

    # 단락·리스트·br
    s = re.sub(r"<p\b[^>]*>([\s\S]*?)</p>", r"\n\n\1\n\n", s, flags=re.I)
    s = re.sub(r"<li\b[^>]*>([\s\S]*?)</li>", r"\n- \1", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)

    # 강조
    s = re.sub(r"</?(strong|b)>", "**", s, flags=re.I)
    s = re.sub(r"</?(em|i)>", "*", s, flags=re.I)

    # 링크는 텍스트만
    s = re.sub(r"<a\b[^>]*>([\s\S]*?)</a>", r"\1", s, flags=re.I)

    # 남은 태그 제거
    s = re.sub(r"<[^>]+>", "", s)

    # HTML 엔티티
    def repl_ent(m):
        v = m.group(0)
        if v in HTML_ENT:
            return HTML_ENT[v]
        num = re.match(r"^&#(\d+);$", v)
        if num:
            return chr(int(num.group(1)))
        return v
    s = re.sub(r"&[a-z]+;|&#\d+;", repl_ent, s, flags=re.I)

    # 공백 정리
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ============================================================
# Main
# ============================================================
def process_one(src: dict, skip_existing: bool = True) -> dict:
    out_path = OUT_DIR / f"{src['slug']}.md"
    if skip_existing and out_path.exists() and out_path.stat().st_size > 500:
        md = out_path.read_text(encoding="utf-8")
        if re.search(r"^#+\s", md, re.M):
            return {"slug": src["slug"], "len": len(md), "has_header": True,
                    "ok": True, "skipped": True}
    md = fetch_one(src)
    out_path.write_text(md, encoding="utf-8")
    has_header = bool(re.search(r"^#+\s", md, re.M))
    return {
        "slug": src["slug"], "len": len(md), "has_header": has_header,
        "ok": len(md) > 500 and has_header, "skipped": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="store_true")
    args = p.parse_args()

    targets = SOURCES if args.run else [s for s in SOURCES if s["slug"] in SMOKE_SLUGS]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mode = "RUN" if args.run else "SMOKE"
    print(f"[fetch] mode={mode} targets={len(targets)}\n")

    results = []
    for src in targets:
        print(f"  {src['slug']:35s} ... ", end="", flush=True)
        try:
            r = process_one(src)
            tag = "SKIP" if r.get("skipped") else ("OK  " if r["ok"] else "FAIL")
            print(f"{tag} ({r['len']} chars)")
            results.append(r)
        except Exception as e:
            print(f"ERROR {e}")
            results.append({"slug": src["slug"], "ok": False})
        time.sleep(1.0)  # rate limit

    ok = sum(1 for r in results if r["ok"])
    print(f"\n[done] {ok}/{len(results)} ok")

    if not args.run:
        if ok < len(SMOKE_SLUGS):
            print("[smoke FAIL] 위 에러부터 해결.")
            raise SystemExit(1)
        print("[smoke PASS] 전체 실행: uv run python scripts/fetch_commentary.py --run")


if __name__ == "__main__":
    main()
