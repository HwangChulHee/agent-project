"""차라투스트라 Stage B 인덱싱: context prepend + bge-m3 임베딩."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json
import shutil
import tempfile
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from rag.leaves import build_leaves

DB_DIR = Path("chroma_db")
EMBED_MODEL = "BAAI/bge-m3"

SOURCES = {
    "nietzsche_contextual_en": {
        "md": "data/nietzsche_md/zarathustra_en.md",
        "contexts": "chroma_db/contexts_nietzsche_en.json",
        "lang": "en",
    },
    "nietzsche_contextual_ko": {
        "md": "data/nietzsche_md/zarathustra_ko.md",
        "contexts": "chroma_db/contexts_nietzsche_ko.json",
        "lang": "ko",
    },
}


def load_leaves(md_path):
    src = Path(md_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copy(src, tmpdir / src.name)
        leaves, _, _ = build_leaves(tmpdir)
    return leaves


def index_one(model, client, col_name, cfg):
    print(f"━━ {col_name} ━━")
    leaves = load_leaves(cfg["md"])
    contexts = json.loads(Path(cfg["contexts"]).read_text(encoding="utf-8"))

    # leaf와 context 일치 확인
    missing = [l["leaf_id"] for l in leaves if l["leaf_id"] not in contexts]
    if missing:
        print(f"  ERROR: {len(missing)} leaves missing context (first 3: {missing[:3]})")
        return
    print(f"  Leaves: {len(leaves)}, contexts: {len(contexts)}")

    # 임베딩 입력 구성: context + leaf
    embed_inputs = [
        f"{contexts[l['leaf_id']]}\n\n{l['text']}" for l in leaves
    ]
    sample = embed_inputs[0]
    print(f"  Sample embed input ({len(sample)} chars):")
    print(f"    {sample[:200]!r}...")

    # collection 재생성
    existing = [c.name for c in client.list_collections()]
    if col_name in existing:
        client.delete_collection(col_name)
    col = client.create_collection(col_name, metadata={"hnsw:space": "cosine"})

    # 임베딩
    embeddings = model.encode(
        embed_inputs, batch_size=16, show_progress_bar=True, convert_to_numpy=True
    ).tolist()

    ids = [l["leaf_id"] for l in leaves]
    documents = [l["text"] for l in leaves]  # ← 원본 leaf만 저장
    metadatas = [
        {
            "doc_id": l["doc_id"],
            "parent_id": l["parent_id"],
            "lang": cfg["lang"],
            "context_len": len(contexts[l["leaf_id"]]),
        }
        for l in leaves
    ]
    col.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"  Indexed {len(ids)} contextual leaves → {col_name}\n")


def main():
    print(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    print(f"Embedding dim: {model.get_embedding_dimension()}\n")

    client = chromadb.PersistentClient(path=str(DB_DIR))

    for col_name, cfg in SOURCES.items():
        index_one(model, client, col_name, cfg)

    print("=" * 60)
    for c in client.list_collections():
        if c.name.startswith("nietzsche"):
            print(f"  {c.name:35s} count={c.count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
