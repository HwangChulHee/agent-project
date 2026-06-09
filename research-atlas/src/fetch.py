"""00 fetch: PAPER_IDS의 논문을 arXiv에서 data/pdfs/로. 3초 텀, 중복 skip."""
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

DELAY = 3.0          # arXiv 요청 간 텀(초)
MIN_BYTES = 10_000   # 이보다 작으면 다운 실패로 간주


def download_one(pid: str) -> tuple[bool, str]:
    dest = config.PDF_DIR / f"{pid}.pdf"
    if dest.exists() and dest.stat().st_size >= MIN_BYTES:
        return True, "skip(이미있음)"
    url = f"https://arxiv.org/pdf/{pid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if len(data) < MIN_BYTES:
            return False, f"too small ({len(data)}B)"
        dest.write_bytes(data)
        return True, f"{len(data)//1024}KB"
    except Exception as e:
        return False, f"error: {e}"


def main():
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for i, pid in enumerate(config.PAPER_IDS, 1):
        ok, msg = download_one(pid)
        print(f"[{i:2}/{len(config.PAPER_IDS)}] {pid}: {msg}")
        if not ok:
            failed.append(pid)
        if "skip" not in msg and i < len(config.PAPER_IDS):
            time.sleep(DELAY)   # 실제 다운로드한 경우만 텀
    print(f"\n완료: {len(config.PAPER_IDS) - len(failed)}/{len(config.PAPER_IDS)}")
    if failed:
        print(f"실패: {failed}")


if __name__ == "__main__":
    main()
