"""해설 자료 Stage B: context prepend + bge-m3 임베딩.

본문 build_index_nietzsche_contextual.py 패턴 차용.
정제(메타 섹션 제거)된 leaves 사용, contexts_commentary.json prepend.

전제: BGE-M3 서버 (8003) 가동 중
사용: uv run python scripts/build_index_commentary_contextual.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chromadb
from rag.embed_api import SentenceTransformer
from rag.leaves import build_leaves
from build_index_commentary_hierarchical import prepare_cleaned_dir

DB_DIR = Path("chroma_db")
COLLECTION = "commentary_contextual_en"
CONTEXTS_PATH = DB_DIR / "contexts_commentary.json"
EMBED_MODEL = "BAAI/bge-m3"
ADD_BATCH = 500


def main():
    print(f"임베딩 모델: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    print(f"  임베딩 차원: {model.get_sentence_embedding_dimension()}\n")

    # 1) 정제된 디렉토리에서 leaves
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        n_files = prepare_cleaned_dir(tmpdir)
        print(f"정제 파일: {n_files}편")
        leaves, _, _ = build_leaves(tmpdir)

    # 2) contexts 로드
    contexts = json.loads(CONTEXTS_PATH.read_text(encoding="utf-8"))
    print(f"Leaves: {len(leaves)}, Contexts: {len(contexts)}")

    # 3) 매핑 확인
    missing = [l["leaf_id"] for l in leaves if l["leaf_id"] not in contexts]
    if missing:
        print(f"  ⚠ {len(missing)} leaves missing context (first 3: {missing[:3]})")
        return
    print(f"  ✓ 모든 leaf에 context 매핑됨\n")

    # 4) 임베딩 입력: context + leaf 본문
    embed_inputs = [
        f"{contexts[l['leaf_id']]}\n\n{l['text']}" for l in leaves
    ]
    sample = embed_inputs[0]
    print(f"  Sample embed input ({len(sample)} chars):")
    print(f"    {sample[:200]!r}...\n")

    # 5) 컬렉션 재생성
    client = chromadb.PersistentClient(path=str(DB_DIR))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    # 6) 임베딩
    print(f"임베딩 {len(embed_inputs)}개...")
    embeddings = model.encode(
        embed_inputs, batch_size=16, show_progress_bar=True, convert_to_numpy=True
    ).tolist()

    # 7) chromadb 적재 (분할). documents는 leaf 원본만 저장
    ids = [l["leaf_id"] for l in leaves]
    documents = [l["text"] for l in leaves]
    metadatas = [
        {
            "doc_id": l["doc_id"],
            "parent_id": l["parent_id"],
            "lang": "en",
            "source_type": "commentary",
            "context_len": len(contexts[l["leaf_id"]]),
        }
        for l in leaves
    ]
    print(f"\nchromadb 적재 (분할 {ADD_BATCH}개씩)...")
    for i in range(0, len(leaves), ADD_BATCH):
        end = min(i + ADD_BATCH, len(leaves))
        col.add(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )
        print(f"  {end}/{len(leaves)}")

    # 8) 검증
    print(f"\n━━ 결과 ━━")
    print(f"  컬렉션: {COLLECTION}")
    print(f"  count:  {col.count()}")

    # 샘플 검색
    print(f"\n━━ 샘플 검색 — 'What is the Übermensch?' ━━")
    q_emb = model.encode(
        ["What is the Übermensch?"], convert_to_numpy=True
    ).tolist()
    res = col.query(query_embeddings=q_emb, n_results=3,
                    include=["metadatas", "distances"])
    for i, (md, dist) in enumerate(zip(res["metadatas"][0], res["distances"][0])):
        print(f"  [{i+1}] dist={dist:.3f}  {md['doc_id']}")

    print(f"\n=" * 30)
    for c in client.list_collections():
        print(f"  {c.name:35s} count={c.count()}")


if __name__ == "__main__":
    main()
