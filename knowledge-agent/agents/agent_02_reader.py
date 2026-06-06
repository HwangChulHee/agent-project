import re
import json
import argparse

from agents.paths import paper_paths

HEADER = re.compile(r"^#{1,6}\s+(.*)$")


def segment(text: str) -> list:
    """마크다운 헤더마다 세그먼트 분할. 관련성 판단 없음 — 쪼개기만."""
    segs, heading, buf = [], None, []

    def flush():
        # 헤더 이전 빈 preamble은 버림
        if heading is None and not "\n".join(buf).strip():
            return
        segs.append({"heading": heading or "(preamble)", "text": "\n".join(buf).strip()})

    for ln in text.split("\n"):
        m = HEADER.match(ln.strip())
        if m:
            flush()
            heading, buf = m.group(1).strip(), []
        else:
            buf.append(ln)
    flush()
    return segs


def segment_file(md_path: str):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    segs = segment(text)
    # {paper}_01.md → {paper}_02.segments.json (같은 폴더)
    out_path = md_path.replace("_01.md", "_02.segments.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False, indent=2)
    return segs, out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    segs, out = segment_file(paper_paths(ap.parse_args().paper)["01_md"])
    print(f"segments: {len(segs)}  ->  {out}\n")
    for i, s in enumerate(segs):
        print(f"{i:2} | {len(s['text']):5}자 | {s['heading'][:55]}")
