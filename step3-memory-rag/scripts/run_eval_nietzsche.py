"""차라투스트라 평가 — 6 collection × 24 쿼리 × top-3, judge 채점."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import argparse, asyncio, json, re, time
from pathlib import Path
from collections import defaultdict
import chromadb
from sentence_transformers import SentenceTransformer
from openai import AsyncOpenAI
from rag.queries_nietzsche import QUERIES

VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
DB_DIR = "chroma_db"
EMBED_MODEL = "BAAI/bge-m3"
TOP_K = 3
CONCURRENCY = 8
OUT_PATH = Path(DB_DIR) / "judge_results_nietzsche.json"

# (collection_name, label, lang, hier_sidecar_path or None)
COLLECTIONS = [
    ("nietzsche_baseline_en",     "Baseline-EN",   "en", None),
    ("nietzsche_baseline_ko",     "Baseline-KO",   "ko", None),
    ("nietzsche_hierarchical_en", "StageA-EN",     "en", "chroma_db/hier_nodes_by_leaf_en.json"),
    ("nietzsche_hierarchical_ko", "StageA-KO",     "ko", "chroma_db/hier_nodes_by_leaf_ko.json"),
    ("nietzsche_contextual_en",   "StageB-EN",     "en", "chroma_db/hier_nodes_by_leaf_en.json"),
    ("nietzsche_contextual_ko",   "StageB-KO",     "ko", "chroma_db/hier_nodes_by_leaf_ko.json"),
]

JUDGE_PROMPT = """You are evaluating whether a retrieved chunk is useful as research material for an LLM answering the user's query.

User query: {query}

Topic anchor (reference only, NOT a strict matching template):
{ground_truth}

Retrieved chunk:
\"\"\"
{chunk}
\"\"\"

Rate the chunk's USEFULNESS as material for answering the query, on a 1-5 scale:

1 = USELESS — irrelevant to the query topic, may mislead the answer
2 = WEAK — tangentially related, contributes little to answering
3 = SUPPLEMENTARY — provides context, background, or partial info; useful when combined with other chunks
4 = USEFUL — contains direct answer material, primary-source quotation, or clear conceptual explanation
5 = IDEAL — multi-layered usefulness: direct answer + context + authoritative framing

Important judgment rules:
- A primary-text quotation (direct passage from Nietzsche\'s work) is valuable even if not phrased as an "answer".
- A commentary explanation is valuable even if it uses different wording from the topic anchor.
- Judge USEFULNESS for answer generation, NOT literal anchor-matching.
- The topic anchor is just a hint about what the query is about; the chunk does not need to repeat its wording.

Respond with ONLY a JSON object on a single line:
{{"score": <1-5>, "reason": "<one short sentence>"}}"""


def parse_judge(text):
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return None, text
    try:
        obj = json.loads(m.group(0))
        return int(obj["score"]), obj.get("reason", "")
    except Exception:
        return None, text


def hydrate(chunk, meta, parents, leaf_id=None):
    """Stage A/B: leaf_id로 sidecar lookup → parent text. Baseline: 청크 그대로."""
    if leaf_id and parents and leaf_id in parents:
        return parents[leaf_id]
    return chunk


async def judge_one(client, sem, key, query, ground_truth, chunk):
    async with sem:
        prompt = JUDGE_PROMPT.format(
            query=query, ground_truth=ground_truth, chunk=chunk[:3000]
        )
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=120,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            raw = (resp.choices[0].message.content or "").strip()
            score, reason = parse_judge(raw)
            return key, score, reason
        except Exception as e:
            return key, None, f"[ERROR: {e}]"


def build_tasks(client_db, embed_model, parents_by_path, lang_filter=None, smoke=False):
    """검색 + hydration → judge에 던질 (key, query, gt, chunk) 리스트 만들기."""
    tasks_data = []
    # 쿼리 임베딩 일괄
    queries = QUERIES if not smoke else QUERIES[:1]
    q_embs = embed_model.encode([q.text for q in queries], show_progress_bar=False).tolist()

    for qi, (q, qe) in enumerate(zip(queries, q_embs)):
        for col_name, label, col_lang, sidecar_path in COLLECTIONS:
            # 언어 일치하는 collection만 (cross-lingual 검색 의도 X)
            if q.lang != col_lang:
                continue
            try:
                col = client_db.get_collection(col_name)
            except Exception:
                continue
            parents = parents_by_path.get(sidecar_path) if sidecar_path else None
            n = 1 if smoke else TOP_K
            res = col.query(query_embeddings=[qe], n_results=n)
            for rank, (chunk, meta) in enumerate(zip(res["documents"][0], res["metadatas"][0])):
                leaf_id = res["ids"][0][rank]
                judge_text = hydrate(chunk, meta, parents, leaf_id=leaf_id)
                key = f"{col_name}|{qi}|{rank}"
                tasks_data.append((key, q.text, q.answer_concept, judge_text, label, q.category, q.lang, rank))
    return tasks_data


def load_parents():
    parents_by_path = {}
    for col_name, label, lang, sidecar_path in COLLECTIONS:
        if sidecar_path and sidecar_path not in parents_by_path:
            p = Path(sidecar_path)
            if p.exists():
                parents_by_path[sidecar_path] = json.loads(p.read_text(encoding="utf-8"))
    return parents_by_path


async def run_smoke():
    print("=" * 60)
    print("SMOKE — 1 query × 6 collections × top-1")
    print("=" * 60)
    client_db = chromadb.PersistentClient(path=DB_DIR)
    embed = SentenceTransformer(EMBED_MODEL)
    parents_by_path = load_parents()
    tasks_data = build_tasks(client_db, embed, parents_by_path, smoke=True)

    print(f"Tasks: {len(tasks_data)}")
    llm = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*[
        judge_one(llm, sem, key, q, gt, c)
        for (key, q, gt, c, *_) in tasks_data
    ])

    all_ok = True
    for (key, score, reason), (_, q, gt, c, label, *_) in zip(results, tasks_data):
        ok = score is not None and 1 <= score <= 5
        status = "✓" if ok else "✗"
        print(f"\n  [{status}] {label}  key={key}")
        print(f"    query: {q[:80]}")
        print(f"    chunk: {c[:120]!r}...")
        print(f"    score={score}  reason: {reason[:100]}")
        if not ok:
            all_ok = False

    print("\n" + ("✓ SMOKE PASSED" if all_ok else "✗ SMOKE FAILED"))
    return all_ok


async def run_full():
    client_db = chromadb.PersistentClient(path=DB_DIR)
    embed = SentenceTransformer(EMBED_MODEL)
    parents_by_path = load_parents()
    tasks_data = build_tasks(client_db, embed, parents_by_path)
    print(f"Tasks: {len(tasks_data)}  (24 queries × 3 collections per lang × top-3)")

    cache = {}
    if OUT_PATH.exists():
        cache = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print(f"Cache: {len(cache)} already done")
    todo = [d for d in tasks_data if d[0] not in cache]
    print(f"To judge: {len(todo)}")

    if todo:
        llm = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
        sem = asyncio.Semaphore(CONCURRENCY)
        t0 = time.time()
        done = 0
        tasks = [
            asyncio.create_task(judge_one(llm, sem, key, q, gt, c))
            for (key, q, gt, c, *_) in todo
        ]
        meta_by_key = {d[0]: d for d in todo}
        for coro in asyncio.as_completed(tasks):
            key, score, reason = await coro
            cache[key] = {
                "score": score,
                "reason": reason,
                "label": meta_by_key[key][4],
                "category": meta_by_key[key][5],
                "lang": meta_by_key[key][6],
                "rank": meta_by_key[key][7],
            }
            done += 1
            if done % 30 == 0 or done == len(todo):
                OUT_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                rate = done / (time.time() - t0)
                eta = (len(todo) - done) / rate if rate > 0 else 0
                print(f"  [{done:3d}/{len(todo)}]  {rate:.2f} judge/s  ETA={eta:.0f}s")

    aggregate(cache)


def aggregate(cache):
    """label × lang × category × metric 표 출력."""
    parse_fail = sum(1 for v in cache.values() if v["score"] is None)
    print(f"\nParse failures: {parse_fail}")

    # agg[label][category][rank_type] = [scores]
    # rank_type = "top1" or "topK"
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    # 키 단위로 묶어서 top1, topK 평균 계산
    by_qkey = defaultdict(list)
    for k, v in cache.items():
        col, qi, rank = k.split("|")
        by_qkey[(col, int(qi))].append((int(rank), v))

    for (col, qi), entries in by_qkey.items():
        entries.sort()
        scores = [v["score"] for _, v in entries if v["score"] is not None]
        if not scores:
            continue
        label = entries[0][1]["label"]
        cat = entries[0][1]["category"]
        lang = entries[0][1]["lang"]
        agg[label][cat]["top1"].append(scores[0])
        agg[label][cat]["topK"].append(sum(scores) / len(scores))
        agg[label]["all"]["top1"].append(scores[0])
        agg[label]["all"]["topK"].append(sum(scores) / len(scores))

    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    print(f"\n{'='*78}")
    print("  Judge scores — Gemma 4, scale 1-5, hydrated parent context")
    print(f"{'='*78}")
    cats = ["factoid", "concept", "metaphor", "all"]
    print(f"  {'Label':14s} {'metric':6s}  " + "  ".join(f"{c:>9s}" for c in cats))
    print(f"  {'-'*14} {'-'*6}  " + "  ".join("-"*9 for _ in cats))
    for label in [l for _, l, *_ in COLLECTIONS]:
        for metric in ["top1", "topK"]:
            cells = [f"{avg(agg[label][cat][metric]):>9.2f}" for cat in cats]
            print(f"  {label:14s} {metric:6s}  " + "  ".join(cells))
        print()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="본격 실행 (기본은 smoke)")
    args = ap.parse_args()

    if not args.run:
        ok = await run_smoke()
        sys.exit(0 if ok else 1)

    await run_full()


if __name__ == "__main__":
    asyncio.run(main())
