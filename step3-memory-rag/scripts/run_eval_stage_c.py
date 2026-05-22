"""scripts/run_eval_stage_c.py — Stage C evaluation (Zarathustra track).

Calls rag.stage_c.search() for each of 24 queries × 2 langs, judges top-3 with
the same prompt as run_eval_nietzsche.py, appends StageC-EN/StageC-KO to the
existing judge_results_nietzsche.json without touching the other 6 columns.

Usage:
  uv run python scripts/run_eval_stage_c.py            # smoke: 1 query/lang
  uv run python scripts/run_eval_stage_c.py --run      # full 24×2
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import argparse
import asyncio
import json
from pathlib import Path

from openai import AsyncOpenAI

from rag.queries_nietzsche import QUERIES
from rag.stage_c import search
from scripts.run_eval_nietzsche import JUDGE_PROMPT, parse_judge

# Reuse infra constants from run_eval_nietzsche.
VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
DB_DIR = Path("chroma_db")
TOP_K = 3
CONCURRENCY = 8
MAX_JUDGE_CHARS = 3000

OUT_PATH = DB_DIR / "judge_results_nietzsche.json"
LABELS = {"en": "StageC-EN", "ko": "StageC-KO"}


async def judge_one(client, sem, query, ground_truth, chunk):
    async with sem:
        prompt = JUDGE_PROMPT.format(
            query=query,
            ground_truth=ground_truth,
            chunk=chunk[:MAX_JUDGE_CHARS],
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
            return {"score": score, "reason": reason, "raw": raw}
        except Exception as e:
            return {"score": None, "reason": f"ERROR: {e}", "raw": ""}


async def run(smoke: bool = False):
    queries = QUERIES[:1] if smoke else QUERIES  # smoke: just first query

    client = AsyncOpenAI(base_url=VLLM_URL, api_key="EMPTY")
    sem = asyncio.Semaphore(CONCURRENCY)

    # Per-lang results: {query_idx: [hit_with_judge, ...]}
    results: dict[str, dict] = {LABELS[lang]: {} for lang in ["en", "ko"]}

    # First: run all retrievals (one search per query in its native language).
    print("━━ retrieval ━━")
    retrievals = []  # [(lang, q_idx, query_text, ground_truth, hits)]
    for q_idx, q in enumerate(queries):
        hits = search(q.text, q.lang, top_k=TOP_K)
        retrievals.append((q.lang, q_idx, q.text, q.answer_concept, hits))
        print(f"  q{q_idx:02d} {q.lang}: {len(hits)} hits  (top-1 score={hits[0].score:.3f})")

    # Then: judge all (query, hit) pairs concurrently.
    print(f"\n━━ judging ({sum(len(r[4]) for r in retrievals)} pairs, concurrency={CONCURRENCY}) ━━")
    tasks = []
    task_meta = []  # parallel list of (lang, q_idx, rank, hit) for unpacking results
    for lang, q_idx, q_text, gt, hits in retrievals:
        for rank, h in enumerate(hits):
            tasks.append(judge_one(client, sem, q_text, gt, h.parent or h.text))
            task_meta.append((lang, q_idx, rank, h, gt, q_text))

    judged = await asyncio.gather(*tasks)

    # Assemble result structure matching run_eval_nietzsche.py format.
    for (lang, q_idx, rank, hit, gt, q_text), verdict in zip(task_meta, judged):
        label = LABELS[lang]
        if q_idx not in results[label]:
            results[label][q_idx] = {
                "query": q_text,
                "ground_truth": gt,
                "results": [],
            }
        results[label][q_idx]["results"].append({
            "rank": rank,
            "leaf_id": hit.leaf_id,
            "score": verdict["score"],
            "reason": verdict["reason"],
            "rerank_score": hit.score,
            "chunk": hit.text,
            "header": hit.header,
            "parent": hit.parent,
        })

    # Merge into existing JSON (preserve other 6 columns).
    existing = json.loads(OUT_PATH.read_text("utf-8")) if OUT_PATH.exists() else {}
    for label in LABELS.values():
        existing[label] = results[label]

    OUT_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), "utf-8")
    print(f"\n[output] merged StageC-EN/StageC-KO into {OUT_PATH}")
    print(f"[output] file size: {OUT_PATH.stat().st_size:,} bytes")

    # Summary
    for label in LABELS.values():
        scores = [r["score"] for q in results[label].values() for r in q["results"]
                  if r["score"] is not None]
        if scores:
            print(f"  {label}: {len(scores)} judged, avg score={sum(scores)/len(scores):.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(smoke=not args.run))


if __name__ == "__main__":
    main()
