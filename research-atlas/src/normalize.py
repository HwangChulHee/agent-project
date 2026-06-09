"""06 normalize: defines/builds_on → 노드+계보. 사전(status 장부) 기반.
   새 개념은 lexicon.json에 status 달아 영구 저장(기존 status는 보존)."""
import glob, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

LEX_PATH = config.DATA_DIR / "lexicon.json"


def canon(s): return " ".join(s.lower().replace("-", " ").split())


def load_lexicon():
    """반환: lex_raw(원본 dict), alias2rep(별칭canon→대표canon), rep_meta(대표canon→메타)"""
    lex = json.load(open(LEX_PATH))["techniques"]
    alias2rep, rep_meta = {}, {}
    for rep, meta in lex.items():
        rk = canon(rep)
        rep_meta[rk] = {"label": rep, **meta}
        alias2rep[rk] = rk
        for v in meta.get("aliases", []):
            alias2rep[canon(v)] = rk
    return lex, alias2rep, rep_meta


def save_lexicon(lex):
    json.dump({"techniques": lex}, open(LEX_PATH, "w"), ensure_ascii=False, indent=2)


# 노드 자격: 이 status만 맵에 노드로
NODE_OK = {"approved", "unreviewed"}


def main():
    lex, alias2rep, rep_meta = load_lexicon()
    nodes, builds, pending_log = {}, [], []
    new_count = {"unreviewed": 0, "pending": 0}

    def status_of(rk):
        return rep_meta.get(rk, {}).get("status", None)

    def resolve(name):
        k = canon(name)
        if k in alias2rep:
            rk = alias2rep[k]
            return rk, rep_meta[rk]["label"], rk
        return k, name, None  # 사전에 없음

    def add_to_lex(rk, label, status, source, pid, definition=""):
        """새 개념을 lexicon에 추가. 이미 있으면 건드리지 않음."""
        if rk in rep_meta:
            return  # 기존 개념 — 사람 결정 보존, 손대지 않음
        lex[label] = {"aliases": [], "status": status, "definition": definition,
                      "source": source, "first_seen": pid}
        rep_meta[rk] = {"label": label, "aliases": [], "status": status,
                        "definition": definition, "source": source, "first_seen": pid}
        alias2rep[rk] = rk
        new_count[status] += 1

    paper_node = {}

    # defines → 노드. 사전에 없으면 unreviewed로 추가.
    for f in sorted(glob.glob(str(config.OUT_DIR / "*.concepts.json"))):
        pid = Path(f).name.replace(".concepts.json", "")
        c = json.load(open(f))
        dom, ptype = c.get("domain", "general"), c.get("paper_type", "technique")
        defs = c.get("defines", [])
        if defs:
            for m in defs:
                rk, label, found = resolve(m["name"])
                if found is None:  # 새 개념
                    add_to_lex(rk, m["name"], "unreviewed", "defines", pid, m.get("definition",""))
                st = status_of(rk)
                if st in NODE_OK:
                    if rk not in nodes:
                        nodes[rk] = {"canonical": rep_meta[rk]["label"],
                                     "definition": m.get("definition","") or rep_meta[rk].get("definition",""),
                                     "def_source": pid, "papers": set(), "domain": dom,
                                     "ptype": ptype, "status": st}
                    nodes[rk]["papers"].add(pid)
            paper_node[pid] = resolve(defs[0]["name"])[0]
        else:
            rk = f"paper:{pid}"
            nodes[rk] = {"canonical": c.get("title", pid)[:40], "definition": c.get("problem",""),
                         "def_source": pid, "papers": {pid}, "domain": dom,
                         "ptype": ptype, "status": "approved"}
            paper_node[pid] = rk

    # builds_on → 계보. 사전에 없으면 pending으로 추가(노드는 안 만듦).
    for f in sorted(glob.glob(str(config.OUT_DIR / "*.relations.json"))):
        pid = Path(f).name.replace(".relations.json", "")
        r = json.load(open(f))
        src = paper_node.get(pid, f"paper:{pid}")
        for tgt in r.get("builds_on", []):
            rk, label, found = resolve(tgt)
            if found is None:  # 새 개념 → 대기줄
                add_to_lex(rk, tgt, "pending", "builds_on", pid)
            st = status_of(rk)
            if st in NODE_OK:
                if rk not in nodes:
                    nodes[rk] = {"canonical": rep_meta[rk]["label"], "definition": rep_meta[rk].get("definition",""),
                                 "def_source": "", "papers": set(), "domain": "general",
                                 "ptype": "technique", "status": st}
                builds.append({"from": src, "to": rk})
            else:  # pending/rejected → 보류 로그
                pending_log.append({"name": tgt, "paper": pid, "status": st})

    # 새 개념들 lexicon에 영구 저장
    save_lexicon(lex)

    # 출력
    node_out = {k: {"canonical": v["canonical"], "definition": v["definition"],
                    "def_source": v["def_source"], "papers": sorted(v["papers"]),
                    "domain": v.get("domain","general"), "ptype": v.get("ptype","technique"),
                    "status": v.get("status","approved"),
                    "def_status": ("ok" if v["definition"] and v.get("ptype")=="technique"
                                   else "n/a" if v.get("ptype") in ("analysis","benchmark","survey")
                                   else "placeholder")}
               for k, v in nodes.items()}
    seen, uniq = set(), []
    for b in builds:
        key = (b["from"], b["to"])
        if key not in seen and b["from"] in node_out and b["to"] in node_out:
            seen.add(key); uniq.append(b)

    (config.OUT_DIR / "normalized.json").write_text(
        json.dumps({"nodes": node_out, "builds_on": uniq}, ensure_ascii=False, indent=2))

    def lbl(k): return node_out[k]["canonical"] if k in node_out else k
    print(f"=== 노드 {len(node_out)}개 / 계보 {len(uniq)}개 ===")
    print(f"=== 사전에 새로 추가: unreviewed {new_count['unreviewed']} / pending {new_count['pending']} ===")
    st_count = {}
    for v in lex.values():
        st_count[v["status"]] = st_count.get(v["status"],0)+1
    print(f"=== 사전 현황: {st_count} ===")
    print(f"\n=== 보류(pending/rejected로 막힌 builds_on) {len(pending_log)}개 ===")
    from collections import Counter
    pc = Counter(p["name"] for p in pending_log)
    for name, cnt in pc.most_common():
        print(f"  ? {name:32} ({cnt}회 참조)")


if __name__ == "__main__":
    main()
