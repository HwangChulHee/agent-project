"""해설 자료 Stage B: leaves에 contextual retrieval context 생성.

build_index_commentary_hierarchical.py에서 strip_meta_sections + prepare_cleaned_dir 재사용.

사용:
  uv run python scripts/generate_contexts_commentary.py            # 스모크 3개
  uv run python scripts/generate_contexts_commentary.py --run      # 전체
"""
import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from openai import AsyncOpenAI
from rag.leaves import build_leaves
from build_index_commentary_hierarchical import strip_meta_sections, prepare_cleaned_dir
from chunk_commentary import clean_text

OUT_PATH = Path("chroma_db/contexts_commentary.json")
VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
CONCURRENCY = 8
SAVE_EVERY = 50

PROMPT_TMPL = """The following is one section from a commentary or encyclopedia article about Friedrich Nietzsche or related philosophy:

<section>
{parent}
</section>

Here is a chunk extracted from that section:
<chunk>
{chunk}
</chunk>

Please give a short succinct context (1-2 sentences in English) describing where this chunk sits and what concept it addresses. Mention the article topic, section heading if identifiable, and the key concept or figure. Answer only with the succinct context, nothing else."""


async def gen_one(client, sem, leaf, parent_text):
    async with sem:
        prompt = PROMPT_TMPL.format(parent=parent_text[:4000], chunk=leaf["text"])
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            return leaf["leaf_id"], (resp.choices[0].message.content or "").strip()
        except Exception as e:
            return leaf["leaf_id"], f"[ERROR: {e}]"


async def main_async(smoke: bool):
    # 1) 정제된 디렉토리에서 leaves
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        n_files = prepare_cleaned_dir(tmpdir)
        print(f"정제 파일: {n_files}편")
        leaves, parent_texts, _ = build_leaves(tmpdir)
        print(f"Leaves: {len(leaves)}, Parents: {len(parent_texts)}")

    # 2) 기존 결과 로드 (있으면 이어서)
    existing = {}
    if OUT_PATH.exists():
        existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print(f"기존 contexts: {len(existing)} (이어서 진행)")

    # 3) 처리 대상 결정
    todo = [l for l in leaves if l["leaf_id"] not in existing]
    if smoke:
        todo = todo[:3]
    print(f"처리 대상: {len(todo)} leaves\n")

    if not todo:
        print("이미 다 처리됨.")
        return

    # 4) async 호출
    client = AsyncOpenAI(base_url=VLLM_URL, api_key="EMPTY")
    sem = asyncio.Semaphore(CONCURRENCY)

    t0 = time.time()
    contexts = dict(existing)
    completed = 0

    tasks = []
    for leaf in todo:
        parent_id = leaf["parent_id"]
        parent_text = parent_texts.get(parent_id, {}).get("text", "")
        tasks.append(gen_one(client, sem, leaf, parent_text))

    for batch_start in range(0, len(tasks), CONCURRENCY * 2):
        batch = tasks[batch_start:batch_start + CONCURRENCY * 2]
        results = await asyncio.gather(*batch)
        for leaf_id, ctx in results:
            contexts[leaf_id] = ctx
            completed += 1

        if completed % SAVE_EVERY == 0 or completed == len(todo):
            OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUT_PATH.write_text(
                json.dumps(contexts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        elapsed = time.time() - t0
        rate = completed / elapsed if elapsed > 0 else 0
        eta = (len(todo) - completed) / rate if rate > 0 else 0
        print(f"  {completed}/{len(todo)}  ({rate:.1f}/s, ETA {eta:.0f}s)")

    OUT_PATH.write_text(
        json.dumps(contexts, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n✓ 완료: {len(contexts)} contexts → {OUT_PATH}")
    print(f"  파일 크기: {OUT_PATH.stat().st_size:,} 바이트")

    if smoke:
        print(f"\n━━ 스모크 결과 (3개 샘플) ━━")
        for lid in list(contexts.keys())[-3:]:
            print(f"  {lid}:")
            print(f"    {contexts[lid][:200]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="store_true")
    args = p.parse_args()
    asyncio.run(main_async(smoke=not args.run))


if __name__ == "__main__":
    main()
