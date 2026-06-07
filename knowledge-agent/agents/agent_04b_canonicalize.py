"""
04b 정규화 (Canonicalize) — 04가 뽑은 개념 중 '같은 개념을 다르게 표기한 것'을 묶는다.
05 align 앞단. 논문 간 비교(05)와 달리, 여기는 한 논문 안 표기 변형을 모으는 일.
규칙 기반(LLM 없음, 결정적):
  - 문자열 정규화: 소문자 / 괄호 제거 / 하이픈·슬래시→공백 / 복수 s 제거(ss 보존)
  - 약어 흡수: 'Tree of Thoughts (ToT)'가 약어 ToT를 선언 → 단독 'ToT' 노드를 흡수.
    같은 약어를 여러 풀네임이 선언하면 단어 수 적은 쪽 우선(약어는 기본 개념을 가리킴).
  - 대표 이름 = 클러스터에서 first-seen 원본 이름. 나머지는 aliases로 보존.
  - 정의는 묶기만(append + text 완전일치 dedup). 정의 충돌 판단은 05/SELECT 몫.
산출: _04.canonical.json — 05가 _04 대신 이걸 읽는다.
"""
import re
import json
import argparse
from agents.paths import paper_paths


def norm_key(name: str) -> str:
    """묶기 판단용 임시 키. 원본 이름은 안 바꾼다(이건 비교용으로만 쓰고 버림)."""
    s = name.lower().strip()
    s = re.sub(r"\([^)]*\)", " ", s)          # 괄호와 그 안 내용 제거
    s = re.sub(r"[-_/]", " ", s)              # 하이픈/슬래시/언더바 → 공백
    s = re.sub(r"\s+", " ", s).strip()
    out = []
    for w in s.split():
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]                        # 복수 s 제거. ss(process 등)·짧은말(IO)은 보존
        out.append(w)
    return " ".join(out)


# 구조 접미어: 'X prompting'/'X method'는 보통 'X'의 표기 변형 — 같은 개념.
# 단, 베이스 'X'가 같은 논문에 개념으로 실재할 때만 흡수(과병합 방지).
STRUCT_SUFFIXES = {"prompting", "method", "framework", "approach", "paradigm"}


def strip_struct_suffix(key: str):
    """norm_key 끝의 구조 접미어 한 단어 제거. 'chain of thought prompting'
    → 'chain of thought'. 접미어 없거나 베이스가 비면 None."""
    parts = key.split()
    if len(parts) >= 2 and parts[-1] in STRUCT_SUFFIXES:
        base = " ".join(parts[:-1]).strip()
        return base or None
    return None


def paren_abbrev(name: str):
    """이름 속 괄호 약어 추출. 단일 토큰만 인정 — '(GSM8k, StrategyQA)' 같은 목록은 제외."""
    m = re.search(r"\(([^)]+)\)", name)
    if not m:
        return None
    inside = m.group(1).strip()
    if " " in inside or "," in inside:
        return None
    return re.sub(r"[-_/]", " ", inside.lower()).strip()


def canonicalize(concepts: list) -> list:
    """concepts: [{"name","definitions":[...]}, ...] → 클러스터 묶은 같은 형식 + aliases."""
    # 1단계: 약어맵. 같은 약어를 여러 풀네임이 선언하면 우선순위:
    #   ① 머리글자가 약어와 일치(ToT == Tree-of-Thoughts) ② 단어 수 적은 것 ③ first-seen
    #   → 'thought process (ToT)' 같은 오추출이 약어 주인을 가로채지 못하게.
    abbrev_cands = {}
    for c in concepts:
        ab = paren_abbrev(c["name"])
        if ab:
            abbrev_cands.setdefault(ab, []).append(norm_key(c["name"]))

    def _initials(key):
        return "".join(w[0] for w in key.split() if w)

    abbrev_map = {}
    for ab, keys in abbrev_cands.items():
        ab_flat = ab.replace(" ", "")
        abbrev_map[ab] = max(keys, key=lambda k: (_initials(k) == ab_flat,
                                                  -len(k.split())))

    # 약어 선언(괄호)이 없어도 풀네임 머리글자로 약어를 생성해 단독 약어 토큰을 흡수.
    #   'Chain of Thought'(머리글자 cot) ← 단독 'CoT'. 구조접미어를 떼고 계산해
    #   'input-output prompting'(→'input output'→io) ← 'IO'도 잡는다.
    #   괄호 선언이 우선(더 신뢰) — 이미 있는 약어는 안 덮어씀. 충돌 시 first-seen.
    for c in concepts:
        k = norm_key(c["name"])
        core = strip_struct_suffix(k) or k
        if len(core.split()) < 2:                  # 머리글자 약어는 2단어 이상에서만
            continue
        acro = _initials(core)
        if len(acro) >= 2 and acro not in abbrev_map:
            abbrev_map[acro] = k                   # 약어 토큰 -> 풀네임 norm_key

    # 1.5단계: 표기-변형 흡수용 베이스 키 집합. 약어 해소까지 반영한 각 개념의 키를
    #   모은 뒤, 'X prompting' 같은 변형은 베이스 'X'가 이 집합에 있을 때만 흡수.
    #   (예: 'chain of thought prompting' → 'chain of thought' 베이스 존재 → 흡수.
    #    'input output prompting' → 'input output' 베이스 없음 → 그대로 분리.)
    resolved = [abbrev_map.get(norm_key(c["name"]), norm_key(c["name"])) for c in concepts]
    key_set = set(resolved)

    # 2단계: 각 개념 → 클러스터 키. 이름 자체가 약어 토큰이면 풀네임 클러스터로 흡수.
    clusters = {}  # cluster_key -> {"name", "aliases":[], "definitions":[]}
    for c, k in zip(concepts, resolved):
        base = strip_struct_suffix(k)
        if base and base in key_set:               # 변형 → 실재하는 베이스로 흡수
            k = base
        if k not in clusters:
            clusters[k] = {"name": c["name"], "aliases": [], "definitions": []}
        else:
            clusters[k]["aliases"].append(c["name"])
        for d in c.get("definitions", []):
            if d not in clusters[k]["definitions"]:
                clusters[k]["definitions"].append(d)
    return list(clusters.values())


def run(paper: str, write: bool):
    P = paper_paths(paper)
    with open(P["04"], encoding="utf-8") as f:
        concepts = json.load(f)

    out = canonicalize(concepts)
    merged = [c for c in out if c["aliases"]]

    print(f"=== CANONICALIZE: {len(concepts)}개 개념 → {len(out)}개 클러스터 "
          f"({len(merged)}개 묶임) ===\n")
    for c in sorted(out, key=lambda x: -len(x["aliases"])):
        if c["aliases"]:
            print(f"  ★ {c['name']}")
            print(f"       + {c['aliases']}")
    print(f"\n  (단일 개념 {len(out) - len(merged)}개는 생략)")

    if not write:
        print("\n=== SMOKE 끝 — 묶임 형식 OK면 `--run`으로 저장 ===")
        return

    with open(P["04b"], "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {P['04b']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--run", action="store_true", help="저장 (없으면 클러스터만 출력)")
    args = ap.parse_args()
    run(args.paper, args.run)
