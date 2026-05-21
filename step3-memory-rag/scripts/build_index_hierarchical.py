"""
Stage A 인덱서 v2: 2-tier — section as parent, sentence-split as leaf.
"""
from pathlib import Path
import json
import chromadb
from sentence_transformers import SentenceTransformer
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

SRC_DIR = Path("data/wikipedia_md")
DB_DIR = Path("chroma_db")
COLLECTION_NAME = "wikipedia_hierarchical"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
LEAF_CHUNK_SIZE = 256
LEAF_OVERLAP = 32
MIN_LEAF_CHARS = 80

# 1) Documents
md_files = sorted(SRC_DIR.glob("*.md"))
docs = [
    Document(text=f.read_text(encoding="utf-8"), metadata={"doc_id": f.stem})
    for f in md_files
]
print(f"Loaded {len(docs)} markdown documents")

# 2) Section parents
md_parser = MarkdownNodeParser()
parents = md_parser.get_nodes_from_documents(docs)
lens = [len(p.text) for p in parents]
print(f"Section parents: {len(parents)}  "
      f"(len min={min(lens)} / avg={sum(lens)//len(lens)} / max={max(lens)})")

# 3) Sentence leaves per parent
splitter = SentenceSplitter(chunk_size=LEAF_CHUNK_SIZE, chunk_overlap=LEAF_OVERLAP)
leaves, parent_texts = [], {}
for p in parents:
    parent_texts[p.node_id] = {
        "text": p.text,
        "doc_id": p.metadata.get("doc_id", ""),
    }
    for lt in splitter.split_text(p.text):
        if len(lt.strip()) < MIN_LEAF_CHARS:
            continue
        leaves.append({
            "text": lt,
            "parent_id": p.node_id,
            "doc_id": p.metadata.get("doc_id", ""),
        })
print(f"Leaves after min-length filter ({MIN_LEAF_CHARS} chars): {len(leaves)}")

# 4) ChromaDB
client = chromadb.PersistentClient(path=str(DB_DIR))
try:
    client.delete_collection(COLLECTION_NAME)
    print(f"Dropped existing collection: {COLLECTION_NAME}")
except Exception:
    pass
collection = client.create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

# 5) Embed + insert
model = SentenceTransformer(EMBED_MODEL)
print(f"Embedding model: {EMBED_MODEL}")
texts = [l["text"] for l in leaves]
embeddings = model.encode(texts, show_progress_bar=True, batch_size=64).tolist()
ids = [f"leaf_{i:05d}" for i in range(len(leaves))]
metadatas = [{"doc_id": l["doc_id"], "parent_id": l["parent_id"]} for l in leaves]
collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
print(f"Indexed {len(ids)} leaves → collection '{COLLECTION_NAME}'")

# 6) Parent sidecar
sidecar_path = DB_DIR / "hier_nodes.json"
sidecar_path.write_text(json.dumps(parent_texts, ensure_ascii=False), encoding="utf-8")
print(f"Sidecar saved: {sidecar_path} ({len(parent_texts)} parents)")
