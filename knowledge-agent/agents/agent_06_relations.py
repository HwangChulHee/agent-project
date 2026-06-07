import json, os, argparse, random

from agents.paths import paper_paths

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = "gpt-4o-mini"

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))
from openai import OpenAI
client = OpenAI()

from agents.prompts.p06_relations_stage1 import STAGE1
from agents.prompts.p06_relations_stage2 import STAGE2

def llm(content):
    r = client.chat.completions.create(model=MODEL, temperature=0,
                                       messages=[{"role": "user", "content": content}])
    return r.choices[0].message.content.strip()

def load_inputs(paper):
    P = paper_paths(paper)
    summaries = json.load(open(P["03"], encoding="utf-8"))
    nodes = json.load(open(P["05"], encoding="utf-8"))
    return summaries, nodes

def endpoint_id(node):
    # merge 노드는 끝점을 시드노드(matched_node)로, new는 자기 이름으로
    if node.get("verdict") == "merge" and node.get("matched_node"):
        return node["matched_node"]
    return node["name"]

def find_pairs(summaries, nodes):
    name2node = {n["name"]: n for n in nodes}
    names = list(name2node)
    pairs = {}  # frozenset({A,B}) -> evidence
    for sec in summaries:
        text = (sec.get("summary") or "").lower()
        present = [nm for nm in names if nm.lower() in text]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                key = frozenset((present[i], present[j]))
                pairs.setdefault(key, {"heading": sec.get("heading", ""), "summary": sec.get("summary", "")})
    return name2node, pairs

def stage1(a, b, ev):
    return llm(STAGE1 + f"\n\nA = {a}\nB = {b}\nContext: {ev['summary']}")

def stage2(sentence, a, b):
    out = llm(STAGE2 + f"\n\nSentence: {sentence}\nA = {a}\nB = {b}")
    try:
        d = json.loads(out[out.index("{"): out.rindex("}") + 1])
        rel = d.get("relation", "none")
        return (rel if rel in ("is_a", "part_of", "none") else "none"), d.get("rationale", "")
    except Exception:
        return "none", "parse_error"

def process_pair(name2node, key, ev):
    a_name, b_name = tuple(key)
    edges, exceptions, stage1_recs = [], [], []
    for A, B in ((a_name, b_name), (b_name, a_name)):
        # merge로 끝점이 같아진 쌍(self-pair)은 무의미한 자기루프라 건너뜀
        if endpoint_id(name2node[A]) == endpoint_id(name2node[B]):
            continue
        sent = stage1(A, B, ev)
        # 1단계는 결과와 무관하게 항상 기록 (날것 서술 보존)
        stage1_recs.append({"a": A, "b": B, "direction": f"{A}->{B}",
                            "stage1_sentence": sent, "evidence": ev["heading"]})
        if "no direct relationship" in sent.lower():
            continue
        rel, why = stage2(sent, A, B)
        src, dst = endpoint_id(name2node[A]), endpoint_id(name2node[B])
        if rel in ("is_a", "part_of"):
            edges.append({"src": src, "rel": rel, "dst": dst, "direction": f"{A}->{B}",
                          "stage1_sentence": sent, "stage2_rationale": why, "evidence": ev["heading"]})
        else:
            exceptions.append({"a": src, "b": dst, "direction": f"{A}->{B}",
                               "stage1_sentence": sent, "stage2_label": "none",
                               "stage2_rationale": why, "evidence": ev["heading"]})
    return edges, exceptions, stage1_recs

def run(paper, smoke=True):
    summaries, nodes = load_inputs(paper)
    name2node, pairs = find_pairs(summaries, nodes)
    items = list(pairs.items())
    print(f"[nodes] {len(nodes)}  [unique co-occurring pairs] {len(items)}")
    if smoke:
        random.seed(0)
        ok = True
        for key, ev in random.sample(items, min(3, len(items))):
            edges, exc, s1 = process_pair(name2node, key, ev)
            if any(e["rel"] not in ("is_a", "part_of") for e in edges):
                ok = False
            print(f"  pair {tuple(key)} -> edges={len(edges)} exc={len(exc)} stage1={len(s1)}")
        print("SMOKE PASS" if ok else "SMOKE FAIL")
        if ok:
            print("=> 전체 실행은 --run")
        return
    all_edges, all_exc, all_s1 = [], [], []
    for i, (key, ev) in enumerate(items, 1):
        print(f"  [{i}/{len(items)}] {tuple(key)}", flush=True)
        e, x, s = process_pair(name2node, key, ev)
        all_edges += e
        all_exc += x
        all_s1 += s
    P = paper_paths(paper)
    dump = lambda key, obj: json.dump(obj, open(P[key], "w", encoding="utf-8"),
                                      ensure_ascii=False, indent=2)
    dump("06_stage1", all_s1)
    dump("06_relations", all_edges)
    dump("06_exceptions", all_exc)
    print(f"[done] stage1={len(all_s1)}  edges={len(all_edges)}  exceptions={len(all_exc)}")
    print(f"  -> _06.stage1.json / _06.relations.json / _06.exceptions.json")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--run", action="store_true", help="전체 실행 (기본은 smoke 3쌍)")
    args = ap.parse_args()
    run(args.paper, smoke=not args.run)
