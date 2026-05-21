"""대시보드용 데이터 가공: judge 결과 + ChromaDB 청크 + parent + ground truth → 1 JSON."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import argparse, json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer
from rag.queries_nietzsche import QUERIES

EMBED_MODEL = "BAAI/bge-m3"
DB_DIR = "chroma_db"
JUDGE_PATH = "chroma_db/judge_results_nietzsche.json"
OUT_PATH = "data/eval_dashboard.json"
TOP_K = 3

COLLECTIONS = [
    ("nietzsche_baseline_en",     "Baseline-EN", "en", None),
    ("nietzsche_baseline_ko",     "Baseline-KO", "ko", None),
    ("nietzsche_hierarchical_en", "StageA-EN",   "en", "chroma_db/hier_nodes_by_leaf_en.json"),
    ("nietzsche_hierarchical_ko", "StageA-KO",   "ko", "chroma_db/hier_nodes_by_leaf_ko.json"),
    ("nietzsche_contextual_en",   "StageB-EN",   "en", "chroma_db/hier_nodes_by_leaf_en.json"),
    ("nietzsche_contextual_ko",   "StageB-KO",   "ko", "chroma_db/hier_nodes_by_leaf_ko.json"),
]


def load_sidecars():
    out = {}
    for _, _, _, path in COLLECTIONS:
        if path and path not in out:
            out[path] = json.loads(Path(path).read_text(encoding="utf-8"))
    return out


def process_query(qi, q, qe, client, judge, sidecars, smoke=False):
    """한 query에 대해 3 collection × top-K 결과 조립."""
    entry = {
        "idx": qi,
        "text": q.text,
        "lang": q.lang,
        "category": q.category,
        "answer_chapter": q.answer_chapter,
        "answer_concept": q.answer_concept,
        "stages": {},
    }
    for col_name, label, col_lang, sidecar_path in COLLECTIONS:
        if q.lang != col_lang:
            continue
        try:
            col = client.get_collection(col_name)
        except Exception:
            continue
        res = col.query(query_embeddings=[qe], n_results=TOP_K)
        parents = sidecars.get(sidecar_path) if sidecar_path else None

        results = []
        scores = []
        for rank in range(len(res["documents"][0])):
            leaf = res["documents"][0][rank]
            meta = res["metadatas"][0][rank]
            leaf_id = res["ids"][0][rank]
            parent_text = parents.get(leaf_id) if parents else None
            header = parent_text.split("\n")[0] if parent_text else meta.get("header")

            key = f"{col_name}|{qi}|{rank}"
            jrec = judge.get(key, {})
            score = jrec.get("score")
            results.append({
                "rank": rank,
                "score": score,
                "reason": jrec.get("reason", ""),
                "leaf": leaf,
                "parent": parent_text,
                "header": header,
            })
            if score is not None:
                scores.append(score)

        entry["stages"][label] = {
            "top1_score": scores[0] if scores else None,
            "topk_avg": round(sum(scores) / len(scores), 2) if scores else None,
            "results": results,
        }
    return entry


def smoke_test():
    print("=" * 60)
    print("SMOKE — 1 query (idx=0)만 처리해 JSON 구조 검증")
    print("=" * 60)
    client = chromadb.PersistentClient(path=DB_DIR)
    model = SentenceTransformer(EMBED_MODEL)
    judge = json.loads(Path(JUDGE_PATH).read_text(encoding="utf-8"))
    sidecars = load_sidecars()

    q = QUERIES[0]
    qe = model.encode([q.text]).tolist()[0]
    entry = process_query(0, q, qe, client, judge, sidecars, smoke=True)

    issues = []
    if not entry["stages"]:
        issues.append("stages가 비어있음 — collection lang 매칭 문제")
    for label, st in entry["stages"].items():
        if not st["results"]:
            issues.append(f"{label}: results 비어있음")
            continue
        r0 = st["results"][0]
        if r0["score"] is None:
            issues.append(f"{label}: judge score 누락 (key 매칭 실패)")
        if "Stage" in label and r0["parent"] is None:
            issues.append(f"{label}: parent text 누락 (sidecar 매칭 실패)")
        if not r0["leaf"]:
            issues.append(f"{label}: leaf 텍스트 비어있음")

    print(f"\nQuery: {q.text}")
    print(f"Stages: {list(entry['stages'].keys())}")
    for label, st in entry["stages"].items():
        print(f"\n  {label}:  top1={st['top1_score']}  topk_avg={st['topk_avg']}")
        r0 = st["results"][0]
        print(f"    [rank 0] score={r0['score']}")
        print(f"      leaf  ({len(r0['leaf'])} chars): {r0['leaf'][:80]!r}...")
        if r0["parent"]:
            print(f"      parent ({len(r0['parent'])} chars): {r0['parent'][:80]!r}...")
        else:
            print(f"      parent: None (Baseline)")
        print(f"      reason: {r0['reason'][:100]}")

    print("\n" + "=" * 60)
    if issues:
        print("✗ SMOKE FAILED:")
        for iss in issues:
            print(f"  - {iss}")
        return False
    print("✓ SMOKE PASSED")
    return True


def run_full():
    client = chromadb.PersistentClient(path=DB_DIR)
    model = SentenceTransformer(EMBED_MODEL)
    judge = json.loads(Path(JUDGE_PATH).read_text(encoding="utf-8"))
    sidecars = load_sidecars()
    print(f"Judge entries: {len(judge)}")
    print(f"Sidecars: {[Path(p).name for p in sidecars]}")

    print(f"\nEmbedding {len(QUERIES)} queries...")
    q_embs = model.encode([q.text for q in QUERIES], show_progress_bar=True).tolist()

    queries_data = []
    for qi, (q, qe) in enumerate(zip(QUERIES, q_embs)):
        entry = process_query(qi, q, qe, client, judge, sidecars)
        queries_data.append(entry)

    out = {
        "queries": queries_data,
        "collections": [
            {"label": label, "lang": lang}
            for _, label, lang, _ in COLLECTIONS
        ],
    }
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT_PATH).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nWrote {OUT_PATH} ({Path(OUT_PATH).stat().st_size:,} bytes)")
    print(f"Queries: {len(queries_data)}")
    n_results = sum(len(st["results"])
                    for q in queries_data for st in q["stages"].values())
    print(f"Total result entries: {n_results}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    if not args.run:
        ok = smoke_test()
        sys.exit(0 if ok else 1)
    run_full()


if __name__ == "__main__":
    main()
