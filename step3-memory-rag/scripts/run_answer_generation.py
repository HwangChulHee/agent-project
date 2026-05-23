"""Stage A: 35 쿼리 × 12 매트릭스 = 420 답변 생성.

산출: chroma_db/answers.json
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.embed_api import SentenceTransformer
from rag.retrieval import retrieve
from rag.answer_gen import generate_answer
from rag.queries_nietzsche import QUERIES

OUT_PATH = Path("chroma_db/answers.json")

STRATEGIES = ["baseline", "hierarchical", "contextual"]
METHODS = ["dense", "hybrid", "reranking", "hybrid_rr"]


def main():
    model = SentenceTransformer("BAAI/bge-m3")

    total = len(QUERIES) * len(STRATEGIES) * len(METHODS)
    print(f"━━ Stage A: 답변 생성 ━━")
    print(f"  쿼리: {len(QUERIES)}")
    print(f"  매트릭스: {len(STRATEGIES)} × {len(METHODS)} = {len(STRATEGIES)*len(METHODS)}")
    print(f"  총 답변: {total}")
    print()

    print("Warmup E2B...")
    _ = generate_answer("test", ["test context"])
    print("  ✓ ready\n")

    results = []
    done = 0
    t_start = time.time()

    for q_idx, q in enumerate(QUERIES):
        qid = f"q{q_idx+1:02d}"
        for emb in STRATEGIES:
            for sm in METHODS:
                t_q0 = time.time()
                try:
                    r = retrieve(q.text, emb, sm, model, top_k=3)
                    ans = generate_answer(q.text, r["chunks"])
                    results.append({
                        "query_id": qid,
                        "query": q.text,
                        "ground_truth_en": q.ground_truth_en,
                        "category": q.category,
                        "episode": q.episode,
                        "method": r["method"],
                        "embed_strategy": emb,
                        "search_method": sm,
                        "chunks": r["chunks"],
                        "raw_chunk_ids": [
                            {"source": x["source"], "id": x["chunk_id"]}
                            for x in r["raw_results"]
                        ],
                        "answer": ans["answer"],
                        "ttft_ms": ans["ttft_ms"],
                        "total_ms": ans["total_ms"],
                        "in_tokens": ans["input_tokens"],
                        "out_tokens": ans["output_tokens"],
                    })
                except Exception as e:
                    print(f"\n  ✗ {qid} / {emb}_{sm}: {str(e)[:100]}")
                    results.append({
                        "query_id": qid,
                        "query": q.text,
                        "method": f"{emb}_{sm}",
                        "embed_strategy": emb,
                        "search_method": sm,
                        "error": str(e)[:200],
                    })

                done += 1
                elapsed = time.time() - t_start
                eta = (elapsed / done) * (total - done)
                t_q = time.time() - t_q0
                line = (f"  [{done:3d}/{total}] {qid} {emb[:8]:12s} {sm:10s} "
                        f"{t_q:5.1f}s   "
                        f"경과 {elapsed/60:5.1f}분 / ETA {eta/60:5.1f}분")
                if done % 12 == 0:
                    print(line, flush=True)
                else:
                    print(line, end="\r", flush=True)

    print()
    n_ok = sum(1 for x in results if "answer" in x)
    n_err = sum(1 for x in results if "error" in x)
    print(f"\n━━ 완료 ━━")
    print(f"  답변: {n_ok}/{total}")
    print(f"  오류: {n_err}/{total}")
    print(f"  총 시간: {(time.time()-t_start)/60:.1f}분")

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"  ✓ {OUT_PATH} ({OUT_PATH.stat().st_size:,} 바이트)")


if __name__ == "__main__":
    main()
