import numpy as np
from collections import defaultdict, Counter

F = "data/dataset-pid/0/"
linker = np.load(F+"0_linker.npy", allow_pickle=True)
lines  = np.load(F+"0_lines.npy", allow_pickle=True)

line_pipe = {row[0]: row[2] for row in lines}          # line_id -> pipe_tag

# 심볼이 물린 line의 pipe_tag별로 심볼 모으기
pipe_to_syms = defaultdict(list)
sym_line = {}
for sid, refs in linker:
    ln = next((r for r in refs if str(r).startswith("line")), None)
    sym_line[sid] = ln
    if ln in line_pipe:
        pipe_to_syms[line_pipe[ln]].append(sid)

sizes = Counter(len(v) for v in pipe_to_syms.values())
print("[pipe_tag별 심볼 수 분포]", dict(sorted(sizes.items())))
print("  (2 이상이면 그 pipe_tag로 그 심볼들이 연결된다는 뜻)")
edges_A = sum(len(v)*(len(v)-1)//2 for v in pipe_to_syms.values() if len(v) >= 2)
print(f"[길 A로 만들어질 엣지 수] {edges_A}")
print("\n[심볼이 여럿 묶인 pipe_tag 샘플 5]")
for tag, syms in [(t,s) for t,s in pipe_to_syms.items() if len(s)>=2][:5]:
    print(f"   '{tag}': {syms}")

# 빈 pipe_tag(라벨없는 선)이 얼마나 되나 — A의 사각지대
empty = sum(1 for sid in sym_line if line_pipe.get(sym_line[sid], "") == "")
print(f"\n[pipe_tag 빈 심볼 수] {empty} / {len(sym_line)}  (많으면 A가 이만큼 놓침)")
