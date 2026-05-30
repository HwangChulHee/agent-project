import os, sys, argparse
from collections import defaultdict, Counter, deque
from itertools import combinations
import numpy as np
import networkx as nx

def load_drawing(folder):
    def load(name):
        return np.load(os.path.join(folder, name), allow_pickle=True)
    pid = os.path.basename(os.path.normpath(folder))
    return {
        "symbols": load(f"{pid}_symbols.npy"),   # [id, bbox, class]
        "lines":   load(f"{pid}_lines.npy"),      # [id, [x1,y1,x2,y2], pipe_tag, style]
        "words":   load(f"{pid}_words.npy"),      # [id, bbox, text, rot]
        "linker":  load(f"{pid}_linker.npy"),     # [symbol_id, [word/line ids...]]
    }

def _line_adjacency(lines, thresh):
    """끝점이 thresh 이내로 가까운 선분쌍을 인접으로 본다.
    반환: {line_id -> set(line_id)} 무방향 인접 리스트.
    thresh==0이면 정확 좌표 일치만 비교(빠른 경로)."""
    adj = defaultdict(set)
    if thresh == 0:
        # 좌표(정수/실수 동일) 키로 그룹화 → 같은 점을 공유하는 선분끼리 인접
        bucket = defaultdict(list)
        for lid, xy, *_ in lines:
            x1, y1, x2, y2 = xy
            bucket[(x1, y1)].append(lid)
            bucket[(x2, y2)].append(lid)
        for lids in bucket.values():
            for a, b in combinations(set(lids), 2):
                adj[a].add(b)
                adj[b].add(a)
        return adj

    # 근사 매칭: sweep
    pts = []
    for lid, xy, *_ in lines:
        x1, y1, x2, y2 = xy
        pts.append((float(x1), float(y1), lid))
        pts.append((float(x2), float(y2), lid))
    pts.sort()
    n = len(pts)
    t2 = thresh * thresh
    for i in range(n):
        xi, yi, li = pts[i]
        j = i + 1
        while j < n and pts[j][0] - xi <= thresh:
            xj, yj, lj = pts[j]
            if li != lj:
                dx = xj - xi
                dy = yj - yi
                if dx * dx + dy * dy <= t2:
                    adj[li].add(lj)
                    adj[lj].add(li)
            j += 1
    return adj

def _walk_neighbors(start_line, line_adj, terminals):
    """start_line에서 출발해 line_adj를 BFS.
    다른 terminal line t'에 닿으면 기록만 하고 그 너머로는 확장하지 않는다.
    (즉 terminal line은 destination이자 barrier.)"""
    seen = {start_line}
    found = set()
    q = deque()
    for nb in line_adj.get(start_line, ()):
        if nb not in seen:
            seen.add(nb)
            q.append(nb)
    while q:
        cur = q.popleft()
        if cur in terminals:
            found.add(cur)
            continue  # 너머로 확장 금지
        for nb in line_adj.get(cur, ()):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return found

def build_graph(folder, thresh=0.0):
    d = load_drawing(folder)
    G = nx.Graph()
    word_text = {row[0]: row[2] for row in d["words"]}   # word_id -> 텍스트
    pipe_tag  = {row[0]: row[2] for row in d["lines"]}   # line_id -> 배관태그

    # 1) 심볼 = 노드
    for sid, bbox, cls in d["symbols"]:
        G.add_node(sid, **{"class": int(cls), "bbox": ",".join(map(str, bbox)), "tag": ""})

    # 2) linker로 태그(word) 붙이고, 각 심볼의 말단선 매핑
    symbol_of_line = defaultdict(list)  # line_id -> [symbol_id, ...]
    for sid, refs in d["linker"]:
        words = [r for r in refs if str(r).startswith("word")]
        if sid in G and words:
            G.nodes[sid]["tag"] = " ".join(word_text.get(w, "") for w in words).strip()
        for r in refs:
            if str(r).startswith("line"):
                symbol_of_line[r].append(sid)

    terminals = set(symbol_of_line.keys())

    # 3) 선분 끝점 근접 → 선분 인접 그래프
    line_adj = _line_adjacency(d["lines"], thresh=thresh)

    # 진단용: 선분 인접 그래프의 연결성분 수
    seen_l = set()
    comp_count = 0
    for lid, *_ in [(row[0],) for row in d["lines"]]:
        if lid in seen_l:
            continue
        comp_count += 1
        stack = [lid]
        while stack:
            x = stack.pop()
            if x in seen_l:
                continue
            seen_l.add(x)
            stack.extend(line_adj.get(x, ()))

    # 4) terminal line을 destination·barrier로 보는 BFS → 인접 심볼 쌍 발견
    edges_added = 0
    neighbor_count = Counter()
    for t_line, syms in symbol_of_line.items():
        reached = _walk_neighbors(t_line, line_adj, terminals)
        # 같은 line에 2개 이상 심볼이 매달려 있으면 그것도 직접 연결
        if len(syms) >= 2:
            for a, b in combinations(syms, 2):
                if not G.has_edge(a, b):
                    G.add_edge(a, b, via=t_line, pipe=pipe_tag.get(t_line, ""))
                    edges_added += 1
        for s in syms:
            for t2 in reached:
                for s2 in symbol_of_line.get(t2, ()):
                    if s == s2:
                        continue
                    if not G.has_edge(s, s2):
                        G.add_edge(s, s2, via=t_line, pipe=pipe_tag.get(t_line, ""))
                        edges_added += 1
            neighbor_count[len(reached)] += 1

    diag = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "nodes_with_tag": sum(1 for _, t in G.nodes(data="tag") if t),
        "line_total": len(d["lines"]),
        "line_terminals": len(terminals),
        "line_components": comp_count,
        "neighbors_per_terminal_dist": dict(sorted(neighbor_count.items())),
        "thresh": thresh,
        "edges_added": edges_added,
    }
    return G, diag

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", nargs="?", default="data/dataset-pid/0/")
    ap.add_argument("--thresh", type=float, default=0.0,
                    help="선분 끝점 근접 임계값(px). 0이면 정확 일치만.")
    ap.add_argument("--out-dir", default="data/graphs")
    args = ap.parse_args()

    G, diag = build_graph(args.folder, thresh=args.thresh)
    print(f"[도면] {args.folder}")
    for k, v in diag.items():
        print(f"  {k:28s}: {v}")
    print("\n[샘플 노드 5]")
    for n, a in list(G.nodes(data=True))[:5]:
        print(f"  {n}: class={a['class']} tag='{a['tag']}' bbox={a['bbox']}")
    print("\n[샘플 엣지 5]")
    for u, v, a in list(G.edges(data=True))[:5]:
        cu = G.nodes[u].get("class")
        cv = G.nodes[v].get("class")
        print(f"  {u}(c{cu}) -- {v}(c{cv})  via={a['via']} pipe='{a['pipe']}'")

    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, f"{os.path.basename(os.path.normpath(args.folder))}.graphml")
    nx.write_graphml(G, out)
    print(f"\n[저장] {out}")

if __name__ == "__main__":
    main()
