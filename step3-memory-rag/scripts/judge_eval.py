"""Stage 2.5 substep 3a: LLM-as-judge로 검색 청크 적합도 채점."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import asyncio, json, re, time
from pathlib import Path
from collections import defaultdict
import chromadb
from sentence_transformers import SentenceTransformer
from openai import AsyncOpenAI
from rag.queries import QUERIES

VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
DB_DIR = "chroma_db"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 3
CONCURRENCY = 8
OUT_PATH = Path(DB_DIR) / "judge_results.json"

COLLECTIONS = ["wikipedia", "wikipedia_hierarchical", "wikipedia_contextual"]
LABELS = {"wikipedia": "Baseline", "wikipedia_hierarchical": "Stage A",
          "wikipedia_contextual": "Stage B"}

JUDGE_PROMPT = """You are evaluating a retrieved chunk against a user query for a RAG system.

User query: {query}

Retrieved chunk:
\"\"\"
{chunk}
\"\"\"

Rate how well this chunk answers the query on a 1-5 scale:
1 = completely irrelevant
2 = weakly related, no real answer
3 = partially relevant, missing key info
4 = directly relevant, contains answer
5 = ideal — directly and completely answers the query

Respond with ONLY a JSON object on a single line, no other text:
{{"score": <1-5>, "reason": "<one short sentence>"}}"""


def parse_judge(text):
    """JSON 추출 — 모델이 가끔 코드 펜스나 잡음 붙임."""
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if not m:
        return None, text
    try:
        obj = json.loads(m.group(0))
        return int(obj["score"]), obj.get("reason", "")
    except Exception:
        return None, text


async def judge_one(client, sem, key, query, chunk):
    async with sem:
        prompt = JUDGE_PROMPT.format(query=query, chunk=chunk[:1500])
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
            return key, score, reason, raw
        except Exception as e:
            return key, None, f"[ERROR: {e}]", ""


async def main():
    # 1) 검색 결과 수집
    client_db = chromadb.PersistentClient(path=DB_DIR)
    cols = {n: client_db.get_collection(n) for n in COLLECTIONS}
    embed = SentenceTransformer(EMBED_MODEL)
    q_embs = embed.encode([q.text for q in QUERIES], show_progress_bar=False).tolist()

    tasks_data = []  # (key, query_text, chunk)
    for qi, (q, qe) in enumerate(zip(QUERIES, q_embs)):
        for col_name, col in cols.items():
            res = col.query(query_embeddings=[qe], n_results=TOP_K)
            for rank, chunk in enumerate(res["documents"][0]):
                key = f"{col_name}|{qi}|{rank}"
                tasks_data.append((key, q.text, chunk))

    print(f"Total judge calls: {len(tasks_data)}  "
          f"({len(QUERIES)} queries × {len(cols)} cols × top-{TOP_K})")

    # 2) 캐시 로드
    cache = {}
    if OUT_PATH.exists():
        cache = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print(f"Resuming from cache: {len(cache)} already judged")
    todo = [(k, q, c) for (k, q, c) in tasks_data if k not in cache]
    print(f"To judge: {len(todo)}")

    # 3) 비동기 judge
    if todo:
        llm = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
        sem = asyncio.Semaphore(CONCURRENCY)
        t0 = time.time()
        done = 0
        tasks = [asyncio.create_task(judge_one(llm, sem, k, q, c)) for k, q, c in todo]
        for coro in asyncio.as_completed(tasks):
            key, score, reason, raw = await coro
            cache[key] = {"score": score, "reason": reason}
            done += 1
            if done % 20 == 0 or done == len(todo):
                OUT_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
                rate = done / (time.time() - t0)
                eta = (len(todo) - done) / rate if rate > 0 else 0
                print(f"  [{done:3d}/{len(todo)}]  {rate:.2f} judge/s  ETA={eta:.0f}s")
        OUT_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    # 4) 집계
    agg = defaultdict(lambda: defaultdict(list))  # [col][lang] = [scores]
    parse_fail = 0
    for qi, q in enumerate(QUERIES):
        for col_name in cols:
            scores = []
            for rank in range(TOP_K):
                rec = cache.get(f"{col_name}|{qi}|{rank}", {})
                if rec.get("score") is None:
                    parse_fail += 1
                    continue
                scores.append(rec["score"])
            if scores:
                # top-1 = first, top-3 mean = avg
                agg[col_name]["top1"].append((q.lang, scores[0]))
                agg[col_name]["topK_mean"].append((q.lang, sum(scores) / len(scores)))

    def filt_avg(pairs, lang=None):
        xs = [s for (l, s) in pairs if (lang is None or l == lang)]
        return sum(xs) / len(xs) if xs else 0.0

    print(f"\nParse failures: {parse_fail}")
    print(f"\n{'='*72}")
    print(f"  LLM-as-judge scores (Gemma 4, scale 1-5)")
    print(f"{'='*72}")
    print(f"  {'Collection':14s}  {'metric':12s}  "
          f"{'EN(n=8)':>9s}  {'KO(n=8)':>9s}  {'All(n=16)':>11s}")
    print(f"  {'-'*14}  {'-'*12}  {'-'*9}  {'-'*9}  {'-'*11}")
    for col_name in cols:
        for metric in ["top1", "topK_mean"]:
            print(f"  {LABELS[col_name]:14s}  {metric:12s}  "
                  f"{filt_avg(agg[col_name][metric], 'en'):>9.2f}  "
                  f"{filt_avg(agg[col_name][metric], 'ko'):>9.2f}  "
                  f"{filt_avg(agg[col_name][metric]):>11.2f}")


if __name__ == "__main__":
    asyncio.run(main())
