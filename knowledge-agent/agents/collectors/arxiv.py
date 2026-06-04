"""
arXiv 수집기 — 최신 논문을 공통 포맷으로 가져옴.
공통 항목: {source_id, title, text, date, url}  (text=abstract)
판정/필터 없음 — 그냥 긁어오기. 거르기는 collector 상위에서.
"""
import time

_last_call = [0.0]  # 마지막 요청 시각 (요청 사이 간격 보장용)
import urllib.request
import urllib.parse
import feedparser

ARXIV_API = "https://export.arxiv.org/api/query"


import json as _json
import os as _os

_CACHE = _os.path.join(_os.path.dirname(__file__), "_arxiv_cache.json")


def fetch(categories=("cs.CL", "cs.AI"), max_results=5, cache=True):
    # 캐시가 있으면 arXiv 안 때리고 그걸 씀 (개발 중 429 회피)
    if cache and _os.path.exists(_CACHE):
        with open(_CACHE, encoding="utf-8") as f:
            cached = _json.load(f)
        if len(cached) >= max_results:
            print(f"(캐시 사용: {_CACHE})")
            return cached[:max_results]
    return _fetch_live(categories, max_results)


def _fetch_live(categories=("cs.CL", "cs.AI"), max_results=5):
    """최신 논문을 제출일 역순으로 가져옴."""
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    params = {
        "search_query": cat_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    # arXiv 권장: 요청 사이 최소 3초 간격
    elapsed = time.time() - _last_call[0]
    if elapsed < 3:
        time.sleep(3 - elapsed)
    _last_call[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "knowledge-agent/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        feed = feedparser.parse(resp.read())

    items = []
    for e in feed.entries:
        items.append({
            "source_id": e.id.split("/abs/")[-1],   # 예: 2602.01234v1
            "title": e.title.strip().replace("\n", " "),
            "text": e.summary.strip().replace("\n", " "),  # abstract
            "date": e.published,
            "url": e.id,
        })
    with open(_CACHE, "w", encoding="utf-8") as f:
        _json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"(arXiv에서 {len(items)}개 긁어 캐시 저장: {_CACHE})")
    return items


if __name__ == "__main__":
    papers = fetch(max_results=5)
    print(f"가져온 논문: {len(papers)}개\n")
    for p in papers:
        print(f"[{p['source_id']}] {p['date'][:10]}")
        print(f"  제목: {p['title']}")
        print(f"  abstract: {p['text'][:120]}...")
        print()
