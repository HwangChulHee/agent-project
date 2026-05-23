"""BM25 인덱스 빌드 — RAG Hybrid 검색용.

2개 인덱스:
  bm25_baseline.pkl   본문 baseline 청크 + 해설 baseline 청크 (763개)
  bm25_leaf.pkl       본문 leaf + 해설 leaf (1943개, Hier+Contextual 공용)

영어 단순 토크나이저: re.findall(r'\\w+', text.lower())

사용: uv run python scripts/build_bm25_indices.py
"""
import json
import pickle
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chromadb
from rank_bm25 import BM25Okapi
from rag.leaves import build_leaves
from build_index_commentary_hierarchical import prepare_cleaned_dir

DB_DIR = Path("chroma_db")
NIETZSCHE_MD = Path("data/nietzsche_md/zarathustra_en.md")
COMMENTARY_CHUNKS = Path("data/commentary/chunks.jsonl")


def tokenize_en(text: str) -> list[str]:
    """영어 단순 토크나이저: 소문자 + 단어 추출."""
    return re.findall(r"\w+", text.lower())


def build_baseline_index():
    """본문 baseline 청크 (chromadb에서 가져옴) + 해설 baseline (jsonl)."""
    print("━━ bm25_baseline.pkl ━━")

    # 1) chromadb에서 본문 baseline 청크 가져옴
    client = chromadb.PersistentClient(path=str(DB_DIR))
    nietzsche_col = client.get_collection("nietzsche_baseline_en")
    nietzsche_data = nietzsche_col.get(include=["documents", "metadatas"])
    nietzsche_chunks = [
        {
            "chunk_id": cid,
            "text": doc,
            "source": "nietzsche",
            "metadata": md,
        }
        for cid, doc, md in zip(
            nietzsche_data["ids"],
            nietzsche_data["documents"],
            nietzsche_data["metadatas"],
        )
    ]
    print(f"  본문 청크: {len(nietzsche_chunks)}")

    # 2) 해설 chunks.jsonl
    commentary_chunks = []
    with COMMENTARY_CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            commentary_chunks.append({
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "source": "commentary",
                "metadata": {
                    "source_id": c["source_id"],
                    "source_type": c["source_type"],
                    "title_ko": c["title_ko"],
                    "section_path": c["section_path"],
                },
            })
    print(f"  해설 청크: {len(commentary_chunks)}")

    # 3) 통합
    all_chunks = nietzsche_chunks + commentary_chunks
    print(f"  총: {len(all_chunks)}")

    # 4) BM25 인덱싱
    tokenized = [tokenize_en(c["text"]) for c in all_chunks]
    print(f"  토큰화 완료. BM25 빌드 중...")
    bm25 = BM25Okapi(tokenized)

    # 5) 저장 (bm25 객체 + chunk_id 매핑)
    out = {
        "bm25": bm25,
        "chunk_ids": [c["chunk_id"] for c in all_chunks],
        "sources": [c["source"] for c in all_chunks],
        "metadatas": [c["metadata"] for c in all_chunks],
        "texts": [c["text"] for c in all_chunks],
    }
    path = DB_DIR / "bm25_baseline.pkl"
    with path.open("wb") as f:
        pickle.dump(out, f)
    print(f"  ✓ {path} ({path.stat().st_size:,} 바이트)\n")


def build_leaf_index():
    """본문 leaves + 해설 leaves (Hier+Contextual 공용)."""
    print("━━ bm25_leaf.pkl ━━")

    # 1) 본문 leaves — build_leaves 호출
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copy(NIETZSCHE_MD, tmpdir / NIETZSCHE_MD.name)
        nietzsche_leaves, _, _ = build_leaves(tmpdir)
    nietzsche_data = [
        {
            "chunk_id": l["leaf_id"],
            "text": l["text"],
            "source": "nietzsche",
            "metadata": {"doc_id": l["doc_id"], "parent_id": l["parent_id"]},
        }
        for l in nietzsche_leaves
    ]
    # leaf_id 충돌 방지: 본문 leaf_id에 prefix
    for d in nietzsche_data:
        d["chunk_id"] = f"nietzsche_{d['chunk_id']}"
    print(f"  본문 leaves: {len(nietzsche_data)}")

    # 2) 해설 leaves — 정제 + build_leaves
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        n_files = prepare_cleaned_dir(tmpdir)
        commentary_leaves, _, _ = build_leaves(tmpdir)
    commentary_data = [
        {
            "chunk_id": f"commentary_{l['leaf_id']}",
            "text": l["text"],
            "source": "commentary",
            "metadata": {"doc_id": l["doc_id"], "parent_id": l["parent_id"]},
        }
        for l in commentary_leaves
    ]
    print(f"  해설 leaves: {len(commentary_data)}")

    # 3) 통합
    all_data = nietzsche_data + commentary_data
    print(f"  총: {len(all_data)}")

    # 4) BM25
    tokenized = [tokenize_en(d["text"]) for d in all_data]
    print(f"  토큰화 완료. BM25 빌드 중...")
    bm25 = BM25Okapi(tokenized)

    # 5) 저장
    out = {
        "bm25": bm25,
        "chunk_ids": [d["chunk_id"] for d in all_data],
        "sources": [d["source"] for d in all_data],
        "metadatas": [d["metadata"] for d in all_data],
        "texts": [d["text"] for d in all_data],
    }
    path = DB_DIR / "bm25_leaf.pkl"
    with path.open("wb") as f:
        pickle.dump(out, f)
    print(f"  ✓ {path} ({path.stat().st_size:,} 바이트)\n")


def verify():
    """샘플 쿼리로 검증."""
    print("━━ 검증 — 'What is the Übermensch?' ━━")
    for name in ["bm25_baseline.pkl", "bm25_leaf.pkl"]:
        path = DB_DIR / name
        with path.open("rb") as f:
            idx = pickle.load(f)

        query_tokens = tokenize_en("What is the Übermensch?")
        scores = idx["bm25"].get_scores(query_tokens)
        top_indices = scores.argsort()[-3:][::-1]

        print(f"\n  {name}:")
        for i in top_indices:
            print(f"    [{idx['sources'][i]}] score={scores[i]:.2f}  "
                  f"id={idx['chunk_ids'][i][:30]}")
            print(f"      {idx['texts'][i][:100]}...")


def main():
    DB_DIR.mkdir(exist_ok=True)
    build_baseline_index()
    build_leaf_index()
    verify()


if __name__ == "__main__":
    main()
