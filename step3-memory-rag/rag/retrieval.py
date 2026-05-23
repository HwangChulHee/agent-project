"""통합 검색 함수 — 12 매트릭스 (3 임베딩 × 4 검색).

검색 기법:
  - dense       — chromadb 거리 기반
  - hybrid      — dense + bm25 (RRF 합산)
  - reranking   — dense top-K → cross-encoder (TODO)
  - hybrid_rr   — hybrid top-K → cross-encoder (TODO)

임베딩 전략:
  - baseline      — 큰 청크
  - hierarchical  — leaf + 인접 leaf 1개 답변
  - contextual    — leaf만 답변
"""
import pickle
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import chromadb
from rag.embed_api import SentenceTransformer

# Reranker
RERANKER_URL = "http://localhost:8005/v1/score"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

DB_DIR = Path("chroma_db")


# ============================================================
# BM25 인덱스 로드 (전역 캐시)
# ============================================================
_bm25_cache = {}


def get_bm25_index(name: str):
    """bm25_baseline.pkl 또는 bm25_leaf.pkl 로드."""
    if name not in _bm25_cache:
        path = DB_DIR / f"bm25_{name}.pkl"
        with path.open("rb") as f:
            _bm25_cache[name] = pickle.load(f)
    return _bm25_cache[name]


def tokenize_en(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


# ============================================================
# 검색 — Dense
# ============================================================
def search_dense(
    query: str,
    embed_model,
    nietzsche_col,
    commentary_col,
    top_k: int = 10,
) -> list[dict]:
    """두 컬렉션 검색 → 거리 기준 통합 정렬 → top_k.

    Returns:
        [{chunk_id, text, source, metadata, score, dense_rank}]
    """
    q_emb = embed_model.encode([query], convert_to_numpy=True).tolist()

    results = []
    for col, src in [(nietzsche_col, "nietzsche"), (commentary_col, "commentary")]:
        res = col.query(
            query_embeddings=q_emb,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        for cid, doc, md, dist in zip(
            res["ids"][0], res["documents"][0],
            res["metadatas"][0], res["distances"][0]
        ):
            results.append({
                "chunk_id": cid,
                "text": doc,
                "source": src,
                "metadata": md,
                "distance": dist,
                "score": 1.0 - dist,  # cosine sim
            })

    # 통합 정렬 (distance 작은 순)
    results.sort(key=lambda x: x["distance"])
    # 순위 부여
    for rank, r in enumerate(results):
        r["dense_rank"] = rank
    return results[:top_k]


# ============================================================
# 검색 — BM25 단독
# ============================================================
def search_bm25(
    query: str,
    bm25_index_name: str,
    top_k: int = 10,
) -> list[dict]:
    """bm25_baseline 또는 bm25_leaf 인덱스에서 top_k.

    Returns:
        [{chunk_id, text, source, metadata, bm25_score, bm25_rank}]
    """
    idx = get_bm25_index(bm25_index_name)
    query_tokens = tokenize_en(query)
    scores = idx["bm25"].get_scores(query_tokens)
    top_indices = scores.argsort()[-top_k:][::-1]

    results = []
    for rank, i in enumerate(top_indices):
        results.append({
            "chunk_id": idx["chunk_ids"][i],
            "text": idx["texts"][i],
            "source": idx["sources"][i],
            "metadata": idx["metadatas"][i],
            "bm25_score": float(scores[i]),
            "bm25_rank": rank,
        })
    return results


# ============================================================
# 검색 — Hybrid (RRF)
# ============================================================
def search_hybrid(
    query: str,
    embed_model,
    nietzsche_col,
    commentary_col,
    bm25_index_name: str,
    top_k: int = 10,
    rrf_k: int = 60,
) -> list[dict]:
    """Dense + BM25 RRF 합산.

    RRF score = 1/(k + dense_rank) + 1/(k + bm25_rank)
    """
    dense_results = search_dense(
        query, embed_model, nietzsche_col, commentary_col, top_k=top_k * 2
    )
    bm25_results = search_bm25(query, bm25_index_name, top_k=top_k * 2)

    # (source, chunk_id) 기준 통합 — 본문 leaf와 해설 leaf가 동일 id 충돌 방지
    combined = {}

    for r in dense_results:
        key = (r["source"], r["chunk_id"])
        combined[key] = {
            **r,
            "dense_rank": r["dense_rank"],
            "bm25_rank": None,
        }

    for r in bm25_results:
        key = (r["source"], r["chunk_id"])
        if key in combined:
            combined[key]["bm25_rank"] = r["bm25_rank"]
            combined[key]["bm25_score"] = r["bm25_score"]
        else:
            combined[key] = {
                **r,
                "dense_rank": None,
            }

    # RRF 합산
    for cid, r in combined.items():
        rrf = 0.0
        if r.get("dense_rank") is not None:
            rrf += 1.0 / (rrf_k + r["dense_rank"])
        if r.get("bm25_rank") is not None:
            rrf += 1.0 / (rrf_k + r["bm25_rank"])
        r["rrf_score"] = rrf

    # 정렬
    sorted_results = sorted(combined.values(), key=lambda x: -x["rrf_score"])
    return sorted_results[:top_k]


# ============================================================
# Reranking — cross-encoder 재정렬
# ============================================================
def rerank_with_cross_encoder(
    query: str,
    candidates: list[dict],
) -> list[dict]:
    """Reranker 서버에 (query, candidate_text) 쌍 보내서 재점수.

    Args:
        query: 사용자 쿼리
        candidates: search_dense/search_hybrid 결과

    Returns:
        candidates에 rerank_score 추가 + rerank_score 내림차순 정렬
    """
    if not candidates:
        return []

    texts = [c["text"] for c in candidates]
    payload = {
        "model": RERANKER_MODEL,
        "text_1": query,
        "text_2": texts,
    }
    resp = requests.post(RERANKER_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()["data"]

    # 응답 순서 = candidates 순서 보장 (vLLM 0.21 score endpoint)
    for c, d in zip(candidates, data):
        c["rerank_score"] = float(d["score"])

    # rerank_score 내림차순 정렬
    return sorted(candidates, key=lambda x: -x["rerank_score"])


# ============================================================
# 검색 — Reranking (Dense top-N → cross-encoder → top-K)
# ============================================================
def search_reranking(
    query: str,
    embed_model,
    nietzsche_col,
    commentary_col,
    top_k: int = 3,
    candidate_n: int = 20,
) -> list[dict]:
    """Dense top-N 후 cross-encoder로 top-K 재정렬."""
    candidates = search_dense(
        query, embed_model, nietzsche_col, commentary_col, top_k=candidate_n
    )
    reranked = rerank_with_cross_encoder(query, candidates)
    return reranked[:top_k]


# ============================================================
# 검색 — Hybrid + Reranking
# ============================================================
def search_hybrid_rerank(
    query: str,
    embed_model,
    nietzsche_col,
    commentary_col,
    bm25_index_name: str,
    top_k: int = 3,
    candidate_n: int = 20,
) -> list[dict]:
    """Hybrid top-N 후 cross-encoder로 top-K 재정렬."""
    candidates = search_hybrid(
        query, embed_model, nietzsche_col, commentary_col,
        bm25_index_name, top_k=candidate_n,
    )
    reranked = rerank_with_cross_encoder(query, candidates)
    return reranked[:top_k]


# ============================================================
# 답변 재료 hydration
# ============================================================
def hydrate_for_baseline(results: list[dict], top_k: int = 3) -> list[str]:
    """Baseline: 청크 그대로 top_k."""
    return [r["text"] for r in results[:top_k]]


def hydrate_for_hierarchical(
    results: list[dict],
    top_k: int = 3,
    parent_sidecar_path: str = None,
) -> list[str]:
    """Hierarchical: leaf + 인접 leaf 1개 (parent의 leaf 시퀀스에서).

    간단 구현: leaf 본문만. 인접 확장은 parent sidecar로 가능하나 일단 leaf만.
    (TODO: parent sidecar 활용해 인접 leaf 합치기)
    """
    return [r["text"] for r in results[:top_k]]


def hydrate_for_contextual(results: list[dict], top_k: int = 3) -> list[str]:
    """Contextual: leaf 본문만 (chromadb documents에 leaf 원본 저장됨)."""
    return [r["text"] for r in results[:top_k]]


# ============================================================
# 통합 인터페이스
# ============================================================
def retrieve(
    query: str,
    embed_strategy: str,   # baseline | hierarchical | contextual
    search_method: str,     # dense | hybrid | reranking | hybrid_rr
    embed_model,
    top_k: int = 3,
) -> dict:
    """12 매트릭스 통합 인터페이스.

    Returns:
        {
            "chunks": [str, ...],       # 답변 재료 (LLM에 prepend)
            "raw_results": [dict, ...], # 디버깅용 원본 결과
            "method": str,              # 사용된 기법 식별자
        }
    """
    client = chromadb.PersistentClient(path=str(DB_DIR))

    # 컬렉션 선택
    col_map = {
        "baseline":     ("nietzsche_baseline_en",     "commentary_baseline_en"),
        "hierarchical": ("nietzsche_hierarchical_en", "commentary_hierarchical_en"),
        "contextual":   ("nietzsche_contextual_en",   "commentary_contextual_en"),
    }
    nietzsche_col = client.get_collection(col_map[embed_strategy][0])
    commentary_col = client.get_collection(col_map[embed_strategy][1])

    # BM25 인덱스 선택
    bm25_name = "baseline" if embed_strategy == "baseline" else "leaf"

    # 검색
    if search_method == "dense":
        results = search_dense(
            query, embed_model, nietzsche_col, commentary_col, top_k=top_k
        )
    elif search_method == "hybrid":
        results = search_hybrid(
            query, embed_model, nietzsche_col, commentary_col,
            bm25_name, top_k=top_k,
        )
    elif search_method == "reranking":
        results = search_reranking(
            query, embed_model, nietzsche_col, commentary_col, top_k=top_k,
        )
    elif search_method == "hybrid_rr":
        results = search_hybrid_rerank(
            query, embed_model, nietzsche_col, commentary_col,
            bm25_name, top_k=top_k,
        )
    else:
        raise ValueError(f"Unknown search_method: {search_method}")

    # Hydration
    if embed_strategy == "baseline":
        chunks = hydrate_for_baseline(results, top_k=top_k)
    elif embed_strategy == "hierarchical":
        chunks = hydrate_for_hierarchical(results, top_k=top_k)
    elif embed_strategy == "contextual":
        chunks = hydrate_for_contextual(results, top_k=top_k)

    return {
        "chunks": chunks,
        "raw_results": results[:top_k],
        "method": f"{embed_strategy}_{search_method}",
    }
