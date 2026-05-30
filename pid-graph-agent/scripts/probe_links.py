import numpy as np
from collections import Counter

F = "data/dataset-pid/0/"
linker = np.load(F+"0_linker.npy", allow_pickle=True)
lines  = np.load(F+"0_lines.npy", allow_pickle=True)

# 1) linker refs 안에 뭐가 들어있나 — 접두어 종류와 개수 분포
kinds = Counter()
ref_counts = Counter()
sym_in_refs = 0
for sid, refs in linker:
    kinds.update(str(r).split("_")[0] for r in refs)
    ref_counts[len(refs)] += 1
    if any(str(r).startswith("symbol") for r in refs): sym_in_refs += 1
print("[linker refs 접두어 종류]", dict(kinds))
print("[refs 개수 분포]", dict(sorted(ref_counts.items())))
print("[refs에 symbol 등장하는 심볼 수]", sym_in_refs)
print("[linker 샘플 3]")
for row in linker[:3]: print("   ", row[0], "->", row[1])

# 2) 한 line이 linker에서 몇 번 참조되나 (2번이면 두 심볼이 공유한다는 뜻)
line_ref = Counter()
for sid, refs in linker:
    line_ref.update(r for r in refs if str(r).startswith("line"))
print("\n[line이 linker에서 참조된 횟수 분포]", dict(Counter(line_ref.values())))

# 3) lines2 정체 + lines의 pipe_tag 공유 확인
l2 = np.load(F+"0_lines2.npy", allow_pickle=True)
print("\n[lines2 shape]", l2.shape, "sample:", l2[:3].tolist())
pipe = Counter(row[2] for row in lines)
print("[같은 pipe_tag를 2개+ line이 공유하는 경우 수]", sum(1 for v in pipe.values() if v>=2))
