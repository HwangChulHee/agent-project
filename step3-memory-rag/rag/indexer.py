"""Wikipedia 텍스트 → 청크 → 임베딩 → ChromaDB 인덱싱.

오프라인 단계 (1회성). 옵션 A: 매 실행마다 컬렉션 통째 삭제 후 재구축.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


# ── 설정 ────────────────────────────────────────────────────
CHUNK_SIZE = 800       # 자 단위
CHUNK_OVERLAP = 100     # 자 단위

DEFAULT_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
DEFAULT_COLLECTION = os.getenv("CHROMA_COLLECTION", "wikipedia")
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


# ── 청킹 ────────────────────────────────────────────────────
def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> Iterator[str]:
    """텍스트를 size 자씩 자르되 overlap 자만큼 겹치게."""
    if size <= overlap:
        raise ValueError("size must be greater than overlap")

    stride = size - overlap
    text = text.strip()
    start = 0
    while start < len(text):
        chunk = text[start : start + size].strip()
        if chunk:
            yield chunk
        start += stride


# ── 인덱서 ──────────────────────────────────────────────────
class Indexer:
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        collection_name: str = DEFAULT_COLLECTION,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.db_path = db_path
        self.collection_name = collection_name

        print(f"[indexer] Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        self.dim = self.model.get_embedding_dimension()
        print(f"[indexer] Embedding dim: {self.dim}")

        # PersistentClient: db_path에 SQLite + parquet 영속
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )

    def rebuild_collection(self) -> chromadb.Collection:
        """옵션 A: 기존 컬렉션 삭제 후 새로 생성."""
        existing = [c.name for c in self.client.list_collections()]
        if self.collection_name in existing:
            print(f"[indexer] Dropping existing collection: {self.collection_name}")
            self.client.delete_collection(self.collection_name)

        collection = self.client.create_collection(
            name=self.collection_name,
            # cosine similarity. 기본은 L2.
            metadata={"hnsw:space": "cosine"},
        )
        return collection

    def index_directory(self, data_dir: Path) -> dict:
        """data_dir/*.txt 전체를 인덱싱."""
        files = sorted(data_dir.glob("*.txt"))
        if not files:
            raise FileNotFoundError(f"No .txt files in {data_dir}")

        collection = self.rebuild_collection()

        total_chunks = 0
        for txt_file in files:
            source = txt_file.stem  # "Albert_Einstein"
            text = txt_file.read_text(encoding="utf-8")
            chunks = list(chunk_text(text))

            ids = [f"{source}_{i:04d}" for i in range(len(chunks))]
            metadatas = [{"source": source, "chunk_index": i} for i in range(len(chunks))]

            # 배치 임베딩 (sentence-transformers는 list 입력 받음)
            embeddings = self.model.encode(
                chunks,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
            ).tolist()

            collection.add(
                ids=ids,
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_chunks += len(chunks)
            print(f"[indexer]   {source:25s} {len(chunks):4d} chunks")

        print(f"[indexer] Done. Total chunks: {total_chunks}")
        return {
            "files": len(files),
            "chunks": total_chunks,
            "collection": self.collection_name,
            "db_path": self.db_path,
        }
