"""Stage 2.5: Hit Rate @ k + MRR 평가. baseline / hierarchical / contextual 비교."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json
from pathlib import Path
from collections import defaultdict
import chromadb
from sentence_transformers import SentenceTransformer
from rag.queries import QUERIES

DB_DIR = "chroma_db"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K_LIST = [1, 3, 5]
MRR_DEPTH = 10
COLLECTIONS = ["wikipedia", "wikipedia_hierarchical", "wikipedia_contextual"]
LABELS = {"wikipedia": "Baseline", "wikipedia_hierarchical": "Stage A",
          "wikipedia_contextual": "Stage B"}


def doc_of(meta):
    return meta.get("doc_id") or meta.get("source", "?")


def evaluate(collection, query_emb, answer_doc):
    res = collection.query(query_embeddings=[query_emb], n_results=MRR_DEPTH)
    docs = [doc_of(m) for m in res["metadatas"][0]]
    hits = {k: int(answer_doc in docs[:k]) for k in TOP_K_LIST}
    rr = next((1.0 / (i + 1) for i, d in enumerate(docs) if d == answer_doc), 0.0)
    return hits, rr, docs[0]


def main():
    client = chromadb.PersistentClient(path=DB_DIR)
    available = {c.name: c for c in client.list_collections()}
    cols = {n: available[n] for n in COLLECTIONS if n in available}
    missing = [n for n in COLLECTIONS if n not in available]
    if missing:
        print(f"WARN: missing collections: {missing}")

    print(f"Embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)

    # 쿼리 임베딩 일괄
    q_embs = model.encode([q.text for q in QUERIES], show_progress_bar=False).tolist()

    # 결과 집계: results[col][lang][metric]
    agg = {n: defaultdict(lambda: defaultdict(list)) for n in cols}
    per_query = []

    for q, q_emb in zip(QUERIES, q_embs):
        row = {"text": q.text, "lang": q.lang, "answer": q.answer_doc, "results": {}}
        for col_name, col in cols.items():
            hits, rr, top1_doc = evaluate(col, q_emb, q.answer_doc)
            row["results"][col_name] = {"hits": hits, "rr": rr, "top1_doc": top1_doc}
            for k, h in hits.items():
                agg[col_name][q.lang][f"hit@{k}"].append(h)
                agg[col_name]["all"][f"hit@{k}"].append(h)
            agg[col_name][q.lang]["mrr"].append(rr)
            agg[col_name]["all"]["mrr"].append(rr)
        per_query.append(row)

    # ── 표 출력 ──────────────────────────────────────────────
    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    metrics = [f"hit@{k}" for k in TOP_K_LIST] + ["mrr"]

    for lang_filter in ["en", "ko", "all"]:
        label = {"en": "English (n=8)", "ko": "Korean (n=8)", "all": "All (n=16)"}[lang_filter]
        print(f"\n{'='*72}")
        print(f"  {label}")
        print(f"{'='*72}")
        print(f"  {'Collection':22s} " + " ".join(f"{m:>8s}" for m in metrics))
        print(f"  {'-'*22} " + " ".join("-"*8 for _ in metrics))
        for col_name in cols:
            row_vals = [avg(agg[col_name][lang_filter][m]) for m in metrics]
            print(f"  {LABELS[col_name]:22s} " +
                  " ".join(f"{v:>8.3f}" for v in row_vals))

    # ── 실패 케이스 노출 ─────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  쿼리별 top-1 doc (정답: ✓, 오답: ✗)")
    print(f"{'='*72}")
    print(f"  {'Query':40s} {'ans':20s} BL  A   B")
    print(f"  {'-'*40} {'-'*20} -- -- --")
    for row in per_query:
        marks = []
        for col_name in cols:
            top1 = row["results"][col_name]["top1_doc"]
            marks.append("✓ " if top1 == row["answer"] else "✗ ")
        q_display = f"[{row['lang']}] {row['text']}"
        print(f"  {q_display:40s} {row['answer']:20s} " + " ".join(marks))

    # ── 저장 ─────────────────────────────────────────────────
    out = {
        "queries": per_query,
        "summary": {
            col_name: {lang: {m: avg(agg[col_name][lang][m]) for m in metrics}
                       for lang in ["en", "ko", "all"]}
            for col_name in cols
        },
    }
    out_path = Path(DB_DIR) / "eval_results.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
