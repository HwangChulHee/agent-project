"""
Stage A 마무리: leaf 검색 결과를 parent로 hydrate해서 LLM이 받을 맥락이 충분한지 확인.
"""
import json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
COLLECTION = "wikipedia_hierarchical"
SIDECAR = Path("chroma_db/hier_nodes.json")
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
QUERY = "Einstein Nobel"

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_collection(COLLECTION)
parents = json.loads(SIDECAR.read_text(encoding="utf-8"))
model = SentenceTransformer(EMBED_MODEL)

q_emb = model.encode(QUERY).tolist()
res = collection.query(query_embeddings=[q_emb], n_results=2)

for i, (leaf_text, meta, dist) in enumerate(zip(
    res["documents"][0], res["metadatas"][0], res["distances"][0]
)):
    pid = meta["parent_id"]
    parent = parents.get(pid)
    print("=" * 70)
    print(f"Hit #{i+1}  d={dist:.4f}  doc={meta['doc_id']}")
    print(f"\n--- LEAF ({len(leaf_text)} chars, what ChromaDB matched) ---")
    print(leaf_text)
    print(f"\n--- PARENT ({len(parent['text'])} chars, what goes to LLM) ---")
    print(parent["text"][:1500] + ("..." if len(parent["text"]) > 1500 else ""))
    print()
