import json, glob, os

# 이 스크립트(tools/)의 위치 기준으로 프로젝트 루트를 잡아 절대경로로 읽는다.
# 그래서 어느 디렉터리에서 실행하든 동작한다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER = "2210.03629"
BASE = os.path.join(ROOT, "data", "parsed", PAPER)

def describe(x, depth=0, max_items=3):
    pad = "  " * depth
    if isinstance(x, dict):
        keys = list(x.keys())
        print(f"{pad}dict (keys={len(keys)}): {keys[:8]}")
        for k in keys[:max_items]:
            print(f"{pad}  └ {k!r}:")
            describe(x[k], depth + 2, max_items)
    elif isinstance(x, list):
        print(f"{pad}list (len={len(x)})")
        if x:
            print(f"{pad}  └ [0]:")
            describe(x[0], depth + 2, max_items)
    else:
        s = str(x)
        s = s[:120] + ("..." if len(s) > 120 else "")
        print(f"{pad}{type(x).__name__}: {s}")

def show(tag, pattern):
    matches = sorted(glob.glob(os.path.join(BASE, pattern)))
    print(f"\n{'='*60}\n{tag}  (matched: {matches})\n{'='*60}")
    if not matches:
        print(f"  !! 파일 못 찾음 — 확인 경로: {os.path.join(BASE, pattern)}")
        return
    with open(matches[0], encoding="utf-8") as f:
        data = json.load(f)
    print("[top-level 구조]")
    describe(data)
    print("\n[첫 항목 raw 샘플 (600자)]")
    if isinstance(data, dict):
        k0 = list(data.keys())[0]
        first = {k0: data[k0]}
    elif isinstance(data, list) and data:
        first = data[0]
    else:
        first = data
    print(json.dumps(first, ensure_ascii=False, indent=2)[:600])

print(f"[BASE] {BASE}")
show("03 SUMMARIES", "*_03*.json")
show("05 ALIGNED", "*_05*.json")
