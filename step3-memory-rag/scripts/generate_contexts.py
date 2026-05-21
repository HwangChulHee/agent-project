"""
Stage B substep 2: 모든 leaf에 대해 Contextual Retrieval 컨텍스트 생성.
- AsyncOpenAI로 vLLM 병렬 호출 (concurrency=8)
- 같은 doc의 leaves를 인접 처리해 vLLM prefix cache 활용
- 점진적 JSON 저장 (중단 복구 가능)
"""
import asyncio
import json
import time
from pathlib import Path
from openai import AsyncOpenAI
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
SRC_DIR = Path("data/wikipedia_md")
OUT_PATH = Path("chroma_db/contexts.json")
LEAF_CHUNK_SIZE = 256
LEAF_OVERLAP = 32
MIN_LEAF_CHARS = 80
CONCURRENCY = 8
SAVE_EVERY = 10

PROMPT_TMPL = """<document>
{document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""


def rebuild_leaves():
    """Stage A 인덱싱과 동일 파이프라인으로 leaves 재구성."""
    md_files = sorted(SRC_DIR.glob("*.md"))
    docs = [
        Document(text=f.read_text(encoding="utf-8"), metadata={"doc_id": f.stem})
        for f in md_files
    ]
    doc_texts = {d.metadata["doc_id"]: d.text for d in docs}

    md_parser = MarkdownNodeParser()
    parents = md_parser.get_nodes_from_documents(docs)
    splitter = SentenceSplitter(chunk_size=LEAF_CHUNK_SIZE, chunk_overlap=LEAF_OVERLAP)

    leaves = []
    for p in parents:
        doc_id = p.metadata.get("doc_id", "")
        for lt in splitter.split_text(p.text):
            if len(lt.strip()) < MIN_LEAF_CHARS:
                continue
            # Stage A와 동일한 leaf id 부여 순서
            leaves.append({
                "leaf_id": f"leaf_{len(leaves):05d}",
                "text": lt,
                "doc_id": doc_id,
                "parent_id": p.node_id,
            })
    return leaves, doc_texts


async def gen_one(client, sem, leaf, doc_text):
    async with sem:
        prompt = PROMPT_TMPL.format(document=doc_text, chunk=leaf["text"])
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            ctx = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            ctx = f"[ERROR: {e}]"
        return leaf["leaf_id"], ctx


async def main():
    leaves, doc_texts = rebuild_leaves()
    # doc_id 순으로 정렬 → 같은 document 연속 처리로 prefix cache 활용
    leaves.sort(key=lambda l: l["doc_id"])
    print(f"Leaves to process: {len(leaves)}  (across {len(doc_texts)} documents)")

    # 기존 캐시 불러오기
    cache = {}
    if OUT_PATH.exists():
        cache = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        print(f"Resuming from cache: {len(cache)} already done")
    todo = [l for l in leaves if l["leaf_id"] not in cache]
    print(f"To generate: {len(todo)}")
    if not todo:
        print("All cached. Nothing to do.")
        return

    client = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
    sem = asyncio.Semaphore(CONCURRENCY)

    t0 = time.time()
    done_count = 0
    tasks = [asyncio.create_task(gen_one(client, sem, l, doc_texts[l["doc_id"]]))
             for l in todo]

    for coro in asyncio.as_completed(tasks):
        leaf_id, ctx = await coro
        cache[leaf_id] = ctx
        done_count += 1

        if done_count % SAVE_EVERY == 0 or done_count == len(todo):
            OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUT_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            elapsed = time.time() - t0
            rate = done_count / elapsed if elapsed > 0 else 0
            eta = (len(todo) - done_count) / rate if rate > 0 else 0
            print(f"  [{done_count:4d}/{len(todo)}]  {rate:.2f} leaf/s  "
                  f"elapsed={elapsed:.0f}s  ETA={eta:.0f}s")

    print(f"\nDone: {len(cache)} contexts saved to {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
