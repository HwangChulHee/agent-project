"""
Stage A 검증: baseline vs hierarchical 같은 쿼리로 distance 비교.
"""
import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
QUERIES = ["Einstein Nobel", "퀴리 부인 원소"]
TOP_K = 3

client = chromadb.PersistentClient(path=DB_DIR)
collections = {c.name: c for c in client.list_collections()}
print(f"Collections in DB: {list(collections.keys())}\n")

# baseline = hierarchical 아닌 첫 collection
baseline_name = next((n for n in collections if "hierarchical" not in n), None)
hier_name = "wikipedia_hierarchical"
if baseline_name is None or hier_name not in collections:
    raise SystemExit(f"ERROR: baseline 또는 {hier_name} collection 없음")

print(f"Baseline: {baseline_name}  (count={collections[baseline_name].count()})")
print(f"Stage A:  {hier_name}  (count={collections[hier_name].count()})\n")

model = SentenceTransformer(EMBED_MODEL)

def show_results(label, collection, query_emb):
    res = collection.query(query_embeddings=[query_emb], n_results=TOP_K)
    print(f"  [{label}]")
    for i, (doc, meta, dist) in enumerate(zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    )):
        doc_id = meta.get("doc_id", "?")
        snippet = " ".join(doc.split())[:80]
        print(f"    {i+1}. d={dist:.4f}  [{doc_id:18s}]  {snippet}...")
    return res["distances"][0][0]

for q in QUERIES:
    print(f"=== Query: {q!r} ===")
    q_emb = model.encode(q).tolist()
    best_base = show_results("Baseline", collections[baseline_name], q_emb)
    print()
    best_hier = show_results("Stage A ", collections[hier_name], q_emb)
    delta = best_hier - best_base
    pct = (delta / best_base * 100) if best_base else 0
    arrow = "↓ 개선" if delta < 0 else "↑ 악화"
    print(f"\n  Δ best: {best_base:.4f} → {best_hier:.4f}  ({delta:+.4f}, {arrow} {abs(pct):.1f}%)")
    print()
