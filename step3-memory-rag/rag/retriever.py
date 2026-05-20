"""ChromaDB 의미 검색."""

from __future__ import annotations

import os
from dataclasses import dataclass

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


DEFAULT_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
DEFAULT_COLLECTION = os.getenv("CHROMA_COLLECTION", "wikipedia")
DEFAULT_EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


@dataclass
class SearchResult:
    chunk: str
    source: str
    chunk_index: int
    distance: float  # 0에 가까울수록 유사 (cosine)


class Retriever:
    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        collection_name: str = DEFAULT_COLLECTION,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        # 인덱싱 때와 반드시 같은 모델 사용 (의미 공간 일치)
        self.model = SentenceTransformer(embedding_model)
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_collection(collection_name)

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """쿼리 → 임베딩 → top-k 청크."""
        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
        ).tolist()

        raw = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
        )

        # raw는 각 필드가 list[list[...]] 형태 (배치 쿼리 지원이라). 첫 쿼리만 꺼냄.
        results = []
        for chunk, meta, distance in zip(
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0],
        ):
            results.append(SearchResult(
                chunk=chunk,
                source=meta["source"],
                chunk_index=meta["chunk_index"],
                distance=distance,
            ))
        return results
