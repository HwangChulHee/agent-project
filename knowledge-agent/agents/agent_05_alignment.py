import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from agents.prompts.alignment import SYSTEM as JUDGE_SYSTEM

load_dotenv()

EMBED_MODEL = "text-embedding-3-small"
JUDGE_MODEL = "gpt-4o-mini"
CONCEPTS_PATH = "data/parsed/2210.03629/2210.03629_04.concepts.json"
MAP_PATH = "data/knowledge_map.json"
OUT_PATH = "data/parsed/2210.03629/2210.03629_05.aligned.json"
CANDIDATE_FLOOR = 0.40
TOP_K = 2

client = OpenAI()


def embed(texts):
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def judge_same(cand_name, cand_defs, node_name, node_def):
    user = (f"Candidate: {cand_name}\nDefinitions:\n- " + "\n- ".join(cand_defs) +
            f"\n\nExisting: {node_name}\nDefinition: {node_def}")
    resp = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": JUDGE_SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content)
    return data.get("verdict") == "SAME", data.get("reason", "")


def run():
    concepts = json.load(open(CONCEPTS_PATH, encoding="utf-8"))
    kmap = json.load(open(MAP_PATH, encoding="utf-8"))

    map_names = list(kmap["nodes"].keys())
    map_defs = [kmap["nodes"][n]["definition"] for n in map_names]
    map_embs = embed(map_defs)

    flat, owner = [], []
    for ci, c in enumerate(concepts):
        for d in c["definitions"]:
            flat.append(d); owner.append(ci)
    flat_embs = embed(flat)

    print(f"=== ALIGN: 임베딩 후보(top{TOP_K}, ≥{CANDIDATE_FLOOR}) → LLM 판정 ===\n")
    aligned = []  # 저장용
    for ci, c in enumerate(concepts):
        node_best = {}
        for fe, own in zip(flat_embs, owner):
            if own != ci:
                continue
            for ni, me in enumerate(map_embs):
                s = cosine(fe, me)
                if s > node_best.get(ni, -1):
                    node_best[ni] = s
        ranked = sorted(node_best.items(), key=lambda x: x[1], reverse=True)
        cands = [(ni, s) for ni, s in ranked[:TOP_K] if s >= CANDIDATE_FLOOR]

        verdict, matched, reason = "new", None, ""
        topsim = ranked[0][1] if ranked else 0.0
        for ni, s in cands:
            same, why = judge_same(c["name"], c["definitions"],
                                   map_names[ni], map_defs[ni])
            if same:
                verdict, matched, reason = "merge", map_names[ni], why
                break

        aligned.append({
            "name": c["name"],
            "definitions": c["definitions"],
            "verdict": verdict,
            "matched_node": matched,
            "top_similarity": round(topsim, 3),
            "reason": reason,
        })
        tag = f"merge→{matched}" if verdict == "merge" else "new"
        print(f"  {c['name'][:26]:28} top {topsim:.3f}  {tag}")
        if reason:
            print(f"       └ {reason[:70]}")

    n_merge = sum(1 for a in aligned if a["verdict"] == "merge")
    print(f"\nmerge {n_merge} / new {len(aligned) - n_merge}")

    print("\n=== 채점 (시드 의도 vs 붙은 것) ===")
    intent = {n: kmap["nodes"][n].get("_seed_intent", "?") for n in map_names}
    merged_to = {}
    for a in aligned:
        if a["verdict"] == "merge":
            merged_to.setdefault(a["matched_node"], []).append(a["name"])
    for node in map_names:
        hits = merged_to.get(node, [])
        mark = "← " + ", ".join(h[:18] for h in hits) if hits else ""
        print(f"  [{intent[node]:8}] {node:30} {mark}")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(aligned, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    run()
