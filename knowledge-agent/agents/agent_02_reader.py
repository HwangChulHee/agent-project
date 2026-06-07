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
# 강한 경계 = References/Bibliography/Acknowledgements/Checklist — 본문 섹션명으로는 거의
#   안 쓰여 위치 무관하게 신뢰. 부록이 거대해 본문 절반을 넘는 논문(예: CoT 2201.11903은
#   50섹션 중 References가 14번째)도 본문만 남기려면 "절반 이후" 가드 없이 첫 등장에서 절단.
# 약한 경계 = appendix/supplementary 등 + 단일대문자 패턴 — 본문 중간 우연매칭 위험이 있어
#   강한 경계가 없을 때만, 그리고 후반부에서만 적용.
_STRONG_BOUNDARY = ("reference", "bibliography", "acknowledgment", "acknowledgement",
                    "checklist")
_WEAK_BOUNDARY = ("broader impact", "appendix", "supplementary")


def _norm_heading(h: str) -> str:
    h = h.lower()
    h = re.sub(r"\*+", "", h)                  # 마크다운 ** 제거
    h = re.sub(r"^\s*[\divxlc]+[\.\)]?\s+", "", h)  # 선행 번호/로마자 제거 (7 / 7. / IV)
    return h.strip()


def _is_strong_boundary(h: str) -> bool:
    return any(_norm_heading(h).startswith(w) for w in _STRONG_BOUNDARY)


def _is_weak_boundary(h: str) -> bool:
    nh = _norm_heading(h)
    if any(nh.startswith(w) for w in _WEAK_BOUNDARY):
        return True
    # 부록 패턴: 단일 대문자로 시작 (A / A. / B.1 ...)
    if re.match(r"^[A-Z]([\.\s]|\.\d)", h.strip()):
        return True
    return False


def trim_back_matter(segs: list) -> list:
    """본문 외(참고문헌·부록 등) 절단. 강한 경계는 위치 무관 첫 등장에서, 없으면
    약한 경계를 후반부에서만 찾는다. 못 찾으면 원본 유지."""
    for i, s in enumerate(segs):                 # 강한 경계: 위치 무관 (부록 거대 논문 대응)
        if _is_strong_boundary(s["heading"]):
            return segs[:i]
    start = len(segs) // 2                        # 약한 경계: 앞 절반은 본문으로 보존
    for i in range(start, len(segs)):
        if _is_weak_boundary(segs[i]["heading"]):
            return segs[:i]
    return segs


# Related Work는 본문 중간(Conclusion 앞)이라 trim_back_matter로는 못 자른다(뒤 본문까지 날아감).
# → "그 섹션만" 콕 제거. 근거: RW는 (1) 공출현 엣지 폭발 (2) 인용-stub 변두리 개념
# (3) 관계서술 정의의 핫스팟. 실제 개념은 본문에서 정의되므로 손실 적음(enrichment).
_DROP_SECTIONS = ("related work", "related works")


def _is_dropped_section(h: str) -> bool:
    return any(_norm_heading(h).startswith(w) for w in _DROP_SECTIONS)


def drop_sections(segs: list) -> list:
    """본문 외 잡음 섹션(Related Work)만 골라 제거. 나머지 순서·내용 보존."""
    return [s for s in segs if not _is_dropped_section(s["heading"])]


def segment_file(md_path: str):
    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    segs = segment(text)
    segs = trim_back_matter(segs)                # References/부록 등 본문 외 절단
    segs = drop_sections(segs)                   # Related Work 섹션 제거(잡음원)
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
