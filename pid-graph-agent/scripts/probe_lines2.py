import numpy as np
from collections import Counter

F = "data/dataset-pid/0/"
lines  = np.load(F+"0_lines.npy",  allow_pickle=True)   # 본선 186
lines2 = np.load(F+"0_lines2.npy", allow_pickle=True)   # 68, 좌표
linker = np.load(F+"0_linker.npy", allow_pickle=True)

# lines 끝점 모으기
def endpoints(arr, coord_idx):
    pts = []
    for row in arr:
        c = row[coord_idx]
        pts.append((c[0], c[1])); pts.append((c[2], c[3]))
    return pts

l1_pts = endpoints(lines, 1)                 # lines: 좌표가 인덱스 1
l2_pts = []
for row in lines2:                            # lines2: 앞 4개가 좌표
    l2_pts.append((int(row[0]), int(row[1]))); l2_pts.append((int(row[2]), int(row[3])))

print("[lines2 마지막 컬럼 값 분포]", dict(Counter(int(r[4]) for r in lines2)))
print("[lines2 좌표가 lines 끝점과 정확히 겹치는 점 수]",
      sum(1 for p in l2_pts if p in set(l1_pts)), "/", len(l2_pts))

# lines2의 (x1,y1)->(x2,y2)가 끝점 공유로 사슬을 이루나: 한 점에 몇 선분이 모이나
deg = Counter()
for row in lines2:
    deg[(int(row[0]),int(row[1]))]+=1; deg[(int(row[2]),int(row[3]))]+=1
print("[lines2 한 점에 모인 선분 수 분포]", dict(sorted(Counter(deg.values()).items())))

# 심볼이 물린 line_id가 lines2에도 등장하나 (id 매칭 가능?)
print("\n[lines2 한 행 전체]", lines2[0].tolist())
print("[lines  한 행 전체]", lines[0].tolist())
print("[linker 한 행]", linker[0].tolist())
