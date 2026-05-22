"""차라투스트라 Stage A 인덱싱: MarkdownNodeParser parent + SentenceSplitter leaf."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json
import shutil
import statistics
import tempfile
from pathlib import Path
import chromadb
from rag.embed_api import SentenceTransformer
from rag.leaves import build_leaves

DB_DIR = Path("chroma_db")
EMBED_MODEL = "BAAI/bge-m3"
BGE_MAX_TOKENS = 8192

SOURCES = {
    "nietzsche_hierarchical_en": ("data/nietzsche_md/zarathustra_en.md", "en"),
    "nietzsche_hierarchical_ko": ("data/nietzsche_md/zarathustra_ko.md", "ko"),
}


def report_stats(leaves, tokenizer, lang):
    char_lens = [len(l["text"]) for l in leaves]
    token_lens = [len(tokenizer.encode(l["text"], add_special_tokens=False))
                  for l in leaves]

    def pct(xs, p):
        s = sorted(xs)
        return s[min(int(len(s) * p / 100), len(s) - 1)]

    print(f"  [{lang}] leaves={len(leaves)}")
    print(f"    chars  min={min(char_lens)}  mean={statistics.mean(char_lens):.0f}  "
          f"p50={pct(char_lens,50)}  p95={pct(char_lens,95)}  max={max(char_lens)}")
    print(f"    tokens min={min(token_lens)}  mean={statistics.mean(token_lens):.0f}  "
          f"p50={pct(token_lens,50)}  p95={pct(token_lens,95)}  max={max(token_lens)}")
    over = sum(1 for t in token_lens if t > BGE_MAX_TOKENS)
    print(f"    {'⚠' if over else '✓'} {over} leaves over {BGE_MAX_TOKENS} tokens")
    return token_lens


def index_one(model, tokenizer, client, col_name, src_md_path, lang):
    """단일 md 파일을 임시 dir에 격리 후 build_leaves → 인덱싱."""
    src = Path(src_md_path)
    if not src.exists():
        print(f"  SKIP: {src} 없음")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copy(src, tmpdir / src.name)
        leaves, parent_texts, _ = build_leaves(tmpdir)

    print(f"━━ {col_name}  ({src.name}) ━━")
    print(f"  Section parents: {len(parent_texts)}")
    report_stats(leaves, tokenizer, lang)

    # collection 재생성
    existing = [c.name for c in client.list_collections()]
    if col_name in existing:
        client.delete_collection(col_name)
    col = client.create_collection(col_name, metadata={"hnsw:space": "cosine"})

    # 임베딩 + 적재
    texts = [l["text"] for l in leaves]
    ids = [l["leaf_id"] for l in leaves]
    metadatas = [
        {"doc_id": l["doc_id"], "parent_id": l["parent_id"], "lang": lang}
        for l in leaves
    ]
    embeddings = model.encode(
        texts, batch_size=16, show_progress_bar=True, convert_to_numpy=True
    ).tolist()
    col.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    print(f"  Indexed {len(ids)} leaves → {col_name}")

    # parent sidecar 저장
    sidecar_path = DB_DIR / f"hier_nodes_{col_name.replace('nietzsche_hierarchical_', 'nietzsche_')}.json"
    sidecar_path.write_text(
        json.dumps(parent_texts, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  Sidecar: {sidecar_path} ({len(parent_texts)} parents)\n")


def main():
    print(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    tokenizer = model.tokenizer
    print(f"Embedding dim: {model.get_embedding_dimension()}\n")

    client = chromadb.PersistentClient(path=str(DB_DIR))

    for col_name, (src_path, lang) in SOURCES.items():
        index_one(model, tokenizer, client, col_name, src_path, lang)

    print("=" * 60)
    for c in client.list_collections():
        if c.name.startswith("nietzsche"):
            print(f"  {c.name:35s} count={c.count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
