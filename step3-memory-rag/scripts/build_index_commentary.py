"""해설 청크 588개 → BGE-M3 임베딩 → chromadb 적재.

전제: vLLM BGE-M3 서버 (포트 8003) 가동 중.

사용:
  uv run python scripts/build_index_commentary.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb
from rag.embed_api import SentenceTransformer

CHUNKS_PATH = Path("data/commentary/chunks.jsonl")
DB_DIR = Path("chroma_db")
COLLECTION = "commentary_baseline_en"
EMBED_MODEL = "BAAI/bge-m3"
BATCH_SIZE = 16
ADD_BATCH = 500  # chroma add 호출 분할


def main():
    # 1) 청크 로드
    chunks = []
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    print(f"청크 로드: {len(chunks)}개")

    # 2) 임베딩 모델
    print(f"임베딩 모델: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    dim = model.get_sentence_embedding_dimension()
    print(f"  임베딩 차원: {dim}")

    # 3) chromadb 컬렉션 재생성
    client = chromadb.PersistentClient(path=str(DB_DIR))
    if COLLECTION in [c.name for c in client.list_collections()]:
        print(f"기존 컬렉션 삭제: {COLLECTION}")
        client.delete_collection(COLLECTION)
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    # 4) 임베딩
    texts = [c["text"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [
        {
            "source_id":    c["source_id"],
            "source_type":  c["source_type"],
            "title_ko":     c["title_ko"],
            "section_path": c["section_path"],
            "lang":         c["lang"],
            "char_count":   c["char_count"],
        }
        for c in chunks
    ]

    print(f"\n임베딩 {len(texts)}개 (batch_size={BATCH_SIZE})...")
    embeddings = model.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).tolist()

    # 5) chromadb 적재 (분할)
    print(f"\nchromadb 적재 (분할 {ADD_BATCH}개씩)...")
    for i in range(0, len(chunks), ADD_BATCH):
        end = min(i + ADD_BATCH, len(chunks))
        col.add(
            ids=ids[i:end],
            documents=texts[i:end],
            embeddings=embeddings[i:end],
            metadatas=metadatas[i:end],
        )
        print(f"  {end}/{len(chunks)}")

    # 6) 검증
    print(f"\n━━ 결과 ━━")
    print(f"  컬렉션: {COLLECTION}")
    print(f"  count:  {col.count()}")

    # 샘플 검색 한 번
    print(f"\n━━ 샘플 검색 — 'What is the Übermensch?' ━━")
    q_emb = model.encode(
        ["What is the Übermensch?"], convert_to_numpy=True
    ).tolist()
    res = col.query(query_embeddings=q_emb, n_results=3,
                    include=["metadatas", "distances"])
    for i, (md, dist) in enumerate(zip(res["metadatas"][0], res["distances"][0])):
        print(f"  [{i+1}] dist={dist:.3f}  {md['source_id']}")
        print(f"      path: {md['section_path']!r}")

    print(f"\n✓ 완료")


if __name__ == "__main__":
    main()
