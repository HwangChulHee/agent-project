"""rag/stage_c.py — Stage C pipeline: dense + BM25 → RRF → rerank → top-3.

Inventory: contextualized leaves (same as Stage B).
- Dense:    chroma collection nietzsche_contextual_{lang}, bge-m3 embeddings.
- BM25:     chroma_db/bm25_{lang}.pkl (contextualized text, lang tokenizer).
- Rerank:   bge-reranker-v2-m3 on raw leaf body only (faster, more accurate).
"""
from __future__ import annotations
import json
import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import chromadb

from rag.embed_api import ApiEmbedder
from rag.reranker import Reranker

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "chroma_db"

EMBED_MODEL = "BAAI/bge-m3"
COLLECTIONS = {"en": "nietzsche_contextual_en", "ko": "nietzsche_contextual_ko"}

# Pipeline knobs.
N_DENSE = 30      # candidates from dense retrieval
N_BM25 = 30       # candidates from BM25
RRF_K = 60        # standard reciprocal-rank-fusion constant
TOP_K = 3         # final results returned


@dataclass
class Hit:
    leaf_id: str
    score: float        # reranker score (0~1 sigmoid)
    text: str           # leaf body (for display)
    parent: str | None
    header: str | None


# ─── component loaders (cached, lazy) ──────────────────────────────────────
@lru_cache(maxsize=2)
def _chroma_collection(lang: str):
    client = chromadb.PersistentClient(path=str(DB))
    return client.get_collection(COLLECTIONS[lang])

@lru_cache(maxsize=1)
def _embedder():
    return ApiEmbedder(EMBED_MODEL)

@lru_cache(maxsize=2)
def _bm25_index(lang: str):
    with (DB / f"bm25_{lang}.pkl").open("rb") as f:
        return pickle.load(f)  # {bm25, leaf_ids, texts}

@lru_cache(maxsize=2)
def _leaf_lookup(lang: str) -> dict[str, dict]:
    """leaf_id → {leaf, parent, header}.

    Parent lookup goes via the HIERARCHICAL collection's metadata, not the
    contextual collection. build_leaves issues fresh parent UUIDs per index
    build, so contextual's parent_ids don't match hier_nodes_nietzsche_*.json —
    only hierarchical's do (they were saved at hierarchical build time).
    Same leaf_id space across both collections, so we cross-reference safely.
    """
    bodies = json.loads(
        (DB / f"hier_nodes_by_leaf_{lang}.json").read_text("utf-8")
    )
    parents = json.loads(
        (DB / f"hier_nodes_nietzsche_{lang}.json").read_text("utf-8")
    )

    client = chromadb.PersistentClient(path=str(DB))
    hier_col = client.get_collection(f"nietzsche_hierarchical_{lang}")
    n = hier_col.count()
    meta_dump = hier_col.get(limit=n, include=["metadatas"])
    leaf_to_parent_uuid = {
        lid: meta.get("parent_id")
        for lid, meta in zip(meta_dump["ids"], meta_dump["metadatas"])
    }

    lookup: dict[str, dict] = {}
    for leaf_id, body in bodies.items():
        parent_uuid = leaf_to_parent_uuid.get(leaf_id)
        parent_text = parents.get(parent_uuid, {}).get("text") if parent_uuid else None
        lookup[leaf_id] = {"leaf": body, "parent": parent_text, "header": None}
    return lookup

@lru_cache(maxsize=1)
def _reranker():
    return Reranker()


# ─── components ────────────────────────────────────────────────────────────
def _dense_search(query: str, lang: str, n: int) -> list[str]:
    """Return top-n leaf_ids ranked by dense similarity."""
    qvec = _embedder().encode([query])
    col = _chroma_collection(lang)
    result = col.query(query_embeddings=qvec.tolist(), n_results=n)
    return result["ids"][0]


def _bm25_search(query: str, lang: str, n: int) -> list[str]:
    """Return top-n leaf_ids ranked by BM25 score on contextualized text."""
    from scripts.build_bm25 import TOKENIZERS
    idx = _bm25_index(lang)
    tokens = TOKENIZERS[lang](query)
    scores = idx["bm25"].get_scores(tokens)
    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:n]
    return [idx["leaf_ids"][i] for i in order]


def _rrf_fuse(rank_lists: list[list[str]], k: int = RRF_K) -> list[str]:
    """Reciprocal Rank Fusion: score = sum(1 / (k + rank)) across lists."""
    scores: dict[str, float] = {}
    for ranks in rank_lists:
        for rank, leaf_id in enumerate(ranks):
            scores[leaf_id] = scores.get(leaf_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.keys(), key=lambda lid: -scores[lid])


# ─── main pipeline ─────────────────────────────────────────────────────────
def search(query: str, lang: str, top_k: int = TOP_K) -> list[Hit]:
    """Stage C: dense + BM25 → RRF → cross-encoder rerank → top-k hits."""
    dense_ids = _dense_search(query, lang, N_DENSE)
    bm25_ids = _bm25_search(query, lang, N_BM25)
    fused_ids = _rrf_fuse([dense_ids, bm25_ids])

    lookup = _leaf_lookup(lang)
    # Dedup by leaf body — build_leaves bug yields multiple leaf_ids per identical
    # body. Keep first occurrence (RRF preserves rank order).
    seen_bodies: set[str] = set()
    candidates = []
    for lid in fused_ids:
        info = lookup.get(lid, {})
        body = info.get("leaf", "")
        if body in seen_bodies:
            continue
        seen_bodies.add(body)
        candidates.append((lid, info))
    docs = [c[1].get("leaf", "") for c in candidates]

    rerank_scores = _reranker().score(query, docs)
    ranked = sorted(zip(candidates, rerank_scores), key=lambda x: -x[1])[:top_k]

    return [
        Hit(
            leaf_id=lid,
            score=float(score),
            text=info.get("leaf", ""),
            parent=info.get("parent"),
            header=info.get("header"),
        )
        for (lid, info), score in ranked
    ]


def _smoke():
    cases = [
        ("en", "How old was Zarathustra when he left his home?"),
        ("ko", "차라투스트라는 몇 살에 산으로 들어갔는가?"),
    ]
    for lang, query in cases:
        print(f"━━ {lang}: {query!r} ━━")
        hits = search(query, lang)
        for rank, h in enumerate(hits):
            snippet = h.text[:100].replace("\n", " ")
            print(f"  rank {rank}  score={h.score:.3f}  {h.leaf_id}")
            print(f"    header: {h.header}")
            print(f"    leaf:   '{snippet}...'")
        print()


if __name__ == "__main__":
    _smoke()
