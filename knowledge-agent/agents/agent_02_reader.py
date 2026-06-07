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


# 본문 끝 경계 = References/부록 등. 첫 경계 이후를 통째로 버린다(본문 → 참고문헌 → 부록 순서 가정).
# 안전장치: 문서 후반부(절반 이후)에서만 경계를 찾는다 — 본문 중간 우연 매칭 방지.
_BOUNDARY_WORDS = ("reference", "bibliography", "acknowledgment", "acknowledgement",
                   "broader impact", "appendix", "supplementary")


def _norm_heading(h: str) -> str:
    h = h.lower()
    h = re.sub(r"\*+", "", h)                  # 마크다운 ** 제거
    h = re.sub(r"^\s*[\divxlc]+[\.\)]?\s+", "", h)  # 선행 번호/로마자 제거 (7 / 7. / IV)
    return h.strip()


def _is_boundary(h: str) -> bool:
    nh = _norm_heading(h)
    if any(nh.startswith(w) for w in _BOUNDARY_WORDS):
        return True
    # 부록 패턴: 단일 대문자로 시작 (A / A. / B.1 ...)
    if re.match(r"^[A-Z]([\.\s]|\.\d)", h.strip()):
        return True
    return False


def trim_back_matter(segs: list) -> list:
    """후반부에서 첫 경계 섹션을 찾아 그 이후를 모두 제거. 못 찾으면 원본 유지."""
    start = len(segs) // 2                       # 앞 절반은 무조건 본문으로 보존
    for i in range(start, len(segs)):
        if _is_boundary(segs[i]["heading"]):
            return segs[:i]
    return segs


def segment_file(md_path: str):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    segs = segment(text)
    segs = trim_back_matter(segs)                # References/부록 등 본문 외 절단
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
