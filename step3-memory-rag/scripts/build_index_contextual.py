import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
"""
Stage B substep 3: contexts.json의 컨텍스트를 leaf에 prepend 후 임베딩 → wikipedia_contextual 컬렉션.
"""
import json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from rag.leaves import build_leaves

SRC_DIR = Path("data/wikipedia_md")
DB_DIR = Path("chroma_db")
CONTEXTS_PATH = DB_DIR / "contexts.json"
COLLECTION_NAME = "wikipedia_contextual"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# 1) Stage A와 동일 leaves
leaves, _, _ = build_leaves(SRC_DIR)
print(f"Leaves: {len(leaves)}")

# 2) 컨텍스트 로드
contexts = json.loads(CONTEXTS_PATH.read_text(encoding="utf-8"))
print(f"Contexts: {len(contexts)}")
missing = [l["leaf_id"] for l in leaves if l["leaf_id"] not in contexts]
if missing:
    raise SystemExit(f"ERROR: {len(missing)} leaves have no context (first: {missing[:3]})")

# 3) prepend → 임베딩 입력 만들기
embed_inputs = [f"{contexts[l['leaf_id']]}\n\n{l['text']}" for l in leaves]
print(f"Sample embed input [0] ({len(embed_inputs[0])} chars):")
print(embed_inputs[0][:300] + ("..." if len(embed_inputs[0]) > 300 else ""))
print()

# 4) ChromaDB
client = chromadb.PersistentClient(path=str(DB_DIR))
try:
    client.delete_collection(COLLECTION_NAME)
    print(f"Dropped existing collection: {COLLECTION_NAME}")
except Exception:
    pass
collection = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

# 5) 임베딩 + 적재
model = SentenceTransformer(EMBED_MODEL)
print(f"Embedding model: {EMBED_MODEL}")
embeddings = model.encode(embed_inputs, show_progress_bar=True, batch_size=64).tolist()

ids = [l["leaf_id"] for l in leaves]
documents = [l["text"] for l in leaves]  # 원본 leaf만 저장 (검색 결과 표시용)
metadatas = [
    {"doc_id": l["doc_id"], "parent_id": l["parent_id"],
     "context_len": len(contexts[l["leaf_id"]])}
    for l in leaves
]

collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
print(f"Indexed {len(ids)} contextual leaves → collection '{COLLECTION_NAME}'")
