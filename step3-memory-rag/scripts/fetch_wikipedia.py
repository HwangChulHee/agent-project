"""Wikipedia 본문 수집 스크립트.

영어 Wikipedia의 인물 페이지 본문을 받아 data/wikipedia/ 에 텍스트로 저장한다.
인덱싱 단계에서 이 파일들을 청크로 쪼개 ChromaDB에 넣는다.

사용법:
    uv run python scripts/fetch_wikipedia.py
"""

import sys
import time
from pathlib import Path

import requests

# step1과 동일한 패턴: 외부 래퍼 없이 REST API 직접 호출
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

PAGES = [
    "Albert_Einstein",
    "Marie_Curie",
    "Isaac_Newton",
    "Charles_Darwin",
    "Alan_Turing",
    "Ada_Lovelace",
    "Nikola_Tesla",
    "Richard_Feynman",
]

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "wikipedia"


def fetch_page_extract(title: str) -> str:
    """Wikipedia 페이지의 plain-text 본문을 반환."""
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": "1",   # HTML 제외, 순수 텍스트
        "redirects": "1",     # 리다이렉트 자동 추적
    }
    headers = {
        # Wikipedia API 정책: User-Agent 필수
        "User-Agent": "agent-project-step3/0.1 (learning project)",
    }
    response = requests.get(WIKIPEDIA_API, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    pages = data["query"]["pages"]
    # pages는 {page_id: {...}} 형태. 첫 번째 (그리고 유일한) 값 추출
    page = next(iter(pages.values()))

    if "missing" in page:
        raise ValueError(f"Page not found: {title}")

    return page.get("extract", "")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = []

    for title in PAGES:
        output_path = OUTPUT_DIR / f"{title}.txt"

        if output_path.exists():
            print(f"  skip   {title:25s} (already exists, {output_path.stat().st_size:,} bytes)")
            success += 1
            continue

        print(f"  fetch  {title:25s} ", end="", flush=True)
        try:
            text = fetch_page_extract(title)
            if not text:
                print("EMPTY")
                failed.append(title)
                continue

            output_path.write_text(text, encoding="utf-8")
            print(f"OK ({len(text):,} chars)")
            success += 1
            # Wikipedia API 매너: 연속 호출 사이 약간 쉬기
            time.sleep(0.5)
        except Exception as e:
            print(f"FAIL ({e})")
            failed.append(title)

    print()
    print(f"Done: {success}/{len(PAGES)} pages saved to {OUTPUT_DIR}")
    if failed:
        print(f"Failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
