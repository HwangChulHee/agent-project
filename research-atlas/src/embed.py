"""07 embed: 노드의 define/problem/task 임베딩 → 쌍별 유사도 → similarity.json
   분포 확인용 출력 포함. OpenAI text-embedding-3-small."""
import glob, json, sys, itertools
from pathlib import Path
import numpy as np
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

client = OpenAI()
EMBED_MODEL = "text-embedding-3-small"


def canon(s): return " ".join(s.lower().replace("-", " ").split())


def embed_batch(texts):
    """빈 텍스트는 None 자리로. 나머지만 임베딩."""
    idx = [i for i, t in enumerate(texts) if t and t.strip()]
    if not idx:
        return [None] * len(texts)
    resp = client.embeddings.create(model=EMBED_MODEL, input=[texts[i] for i in idx])
    vecs = [None] * len(texts)
    for j, i in enumerate(idx):
        vecs[i] = np.array(resp.data[j].embedding)
    return vecs


def cos(a, b):
    if a is None or b is None: return None
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    # 노드별 3필드 텍스트 수집 (defines 기준 노드 + 논문노드)
    norm = json.load(open(config.OUT_DIR / "normalized.json"))
    # concepts에서 problem/task/definition 끌어오기
    field = {}  # node_key → {define, problem, task}
    for f in sorted(glob.glob(str(config.OUT_DIR / "*.concepts.json"))):
        pid = Path(f).name.replace(".concepts.json", "")
        c = json.load(open(f))
        prob = c.get("problem", "")
        task = " ".join(c.get("task", []))
        defs = c.get("defines", [])
        if defs:
            for m in defs:
                k = canon(m["name"])
                field[k] = {"define": m.get("definition",""), "problem": prob, "task": task,
                            "label": m["name"]}
        else:
            k = f"paper:{pid}"
            field[k] = {"define": c.get("title",""), "problem": prob, "task": task,
                        "label": c.get("title","")[:30]}

    keys = [k for k in field if k in norm["nodes"]]  # 맵에 실제 있는 노드만
    labels = {k: field[k]["label"] for k in keys}

    # 3필드 각각 임베딩
    emb = {}
    for fld in ("define", "problem", "task"):
        vecs = embed_batch([field[k][fld] for k in keys])
        emb[fld] = {k: v for k, v in zip(keys, vecs)}

    # 쌍별 유사도
    sims = {"define": [], "problem": [], "task": []}
    for a, b in itertools.combinations(keys, 2):
        for fld in ("define", "problem", "task"):
            s = cos(emb[fld][a], emb[fld][b])
            if s is not None:
                sims[fld].append({"a": a, "b": b, "sim": round(s, 3)})

    # 저장
    out = {"labels": labels, "sims": sims}
    (config.OUT_DIR / "similarity.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))

    # === 분포 + 형제 확인 ===
    import statistics as st
    print("=== 유사도 분포 (필드별) ===")
    for fld in ("define", "problem", "task"):
        vals = [x["sim"] for x in sims[fld]]
        if vals:
            print(f"  {fld:8} 쌍{len(vals)}  min {min(vals):.2f} / 평균 {st.mean(vals):.2f} / "
                  f"중앙 {st.median(vals):.2f} / max {max(vals):.2f}")
            # 상위 5쌍
            top = sorted(sims[fld], key=lambda x:-x["sim"])[:5]
            for t in top:
                print(f"      {t['sim']:.2f}  {labels[t['a']][:22]:24} ~ {labels[t['b']][:22]}")
    # 형제 확인: GraphRAG 계열끼리
    print("\n=== 형제 후보 (그래프기반 RAG끼리 define 유사도) ===")
    fam = [k for k in keys if any(w in labels[k].lower() for w in ['graphrag','lightrag','hipporag','hypergraph'])]
    for a, b in itertools.combinations(fam, 2):
        s = cos(emb["define"][a], emb["define"][b])
        if s is not None:
            print(f"  {s:.2f}  {labels[a][:20]:22} ~ {labels[b][:20]}")


if __name__ == "__main__":
    main()
