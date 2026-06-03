"""
arXiv 수집기 — 최신 논문을 공통 포맷으로 가져옴.
공통 항목: {source_id, title, text, date, url}  (text=abstract)
판정/필터 없음 — 그냥 긁어오기. 거르기는 collector 상위에서.
"""
import time
import urllib.request
import urllib.parse
import feedparser

ARXIV_API = "http://export.arxiv.org/api/query"


def fetch(categories=("cs.CL", "cs.AI"), max_results=5):
    """최신 논문을 제출일 역순으로 가져옴."""
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    params = {
        "search_query": cat_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
    time.sleep(3)  # arXiv 권장 요청 간격
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
    return items


if __name__ == "__main__":
    papers = fetch(max_results=5)
    print(f"가져온 논문: {len(papers)}개\n")
    for p in papers:
        print(f"[{p['source_id']}] {p['date'][:10]}")
        print(f"  제목: {p['title']}")
        print(f"  abstract: {p['text'][:120]}...")
        print()
