"""차라투스트라 Stage B: leaves에 contextual retrieval context 생성 (parent 기반).

v2 변경점:
- Document 전체 prepend → parent 섹션만 (token 한계 회피)
- --smoke 옵션: 언어당 3개만 호출, 검증 후 종료
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import argparse, asyncio, json, shutil, tempfile, time
from pathlib import Path
from openai import AsyncOpenAI
from rag.leaves import build_leaves

VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
CONCURRENCY = 8
SAVE_EVERY = 20

SOURCES = {
    "en": {
        "md": "data/nietzsche_md/zarathustra_en.md",
        "out": "chroma_db/contexts_nietzsche_en.json",
        "prompt": """The following is one section of Nietzsche's "Thus Spake Zarathustra":

<section>
{parent}
</section>

Here is a chunk extracted from that section:
<chunk>
{chunk}
</chunk>

Please give a short succinct context (1-2 sentences in English) describing where this chunk sits in the book and what it addresses. Mention the chapter/section name if identifiable, and the key concept or symbol. Answer only with the succinct context, nothing else.""",
    },
    "ko": {
        "md": "data/nietzsche_md/zarathustra_ko.md",
        "out": "chroma_db/contexts_nietzsche_ko.json",
        "prompt": """다음은 니체의 "차라투스트라는 이렇게 말했다" 한국어 번역본의 한 섹션이다:

<section>
{parent}
</section>

여기서 추출된 청크:
<chunk>
{chunk}
</chunk>

이 청크가 책의 어느 부/장/절에서 무엇을 다루는지 한두 문장의 한국어로 간결히 설명하라. 검색 정확도 향상이 목적이므로 인명·개념·장 제목을 명시적으로 포함하라.

답변은 한국어 컨텍스트 문장만, 다른 설명 없이.""",
    },
}


def load_leaves(md_path):
    """단일 md 파일을 임시 dir에 격리 후 build_leaves 호출."""
    src = Path(md_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copy(src, tmpdir / src.name)
        leaves, parent_texts, _ = build_leaves(tmpdir)
    return leaves, parent_texts


async def gen_one(client, sem, leaf, parent_text, prompt_tmpl):
    async with sem:
        prompt = prompt_tmpl.format(parent=parent_text, chunk=leaf["text"])
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


def is_korean(s):
    return any(0xAC00 <= ord(c) <= 0xD7A3 for c in s)


def validate_sample(lang, leaf, ctx):
    """스모크 테스트 검증."""
    issues = []
    if ctx.startswith("[ERROR"):
        issues.append(f"ERROR returned: {ctx[:120]}")
        return issues
    if len(ctx) < 30:
        issues.append(f"too short ({len(ctx)} chars)")
    if len(ctx) > 500:
        issues.append(f"too long ({len(ctx)} chars)")
    has_ko = is_korean(ctx)
    if lang == "ko" and not has_ko:
        issues.append("expected Korean response but got non-Korean")
    if lang == "en" and has_ko:
        issues.append("expected English response but got Korean")
    return issues


async def smoke_test():
    """언어당 3개 leaf만 호출하고 결과 검증."""
    print("=" * 60)
    print("SMOKE TEST — 언어당 3개 leaf만 호출")
    print("=" * 60)

    client = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
    sem = asyncio.Semaphore(CONCURRENCY)
    all_ok = True

    for lang, cfg in SOURCES.items():
        print(f"\n━━ {lang} 스모크 ━━")
        leaves, parent_texts = load_leaves(cfg["md"])
        # 다양한 위치에서 3개 샘플: 처음, 중간, 끝
        sample_idx = [0, len(leaves) // 2, len(leaves) - 1]
        samples = [leaves[i] for i in sample_idx]
        print(f"  Leaves: {len(leaves)}, sampling indices: {sample_idx}")

        tasks = []
        for leaf in samples:
            parent = parent_texts.get(leaf["parent_id"], {}).get("text", "")
            if not parent:
                print(f"  ⚠ leaf {leaf['leaf_id']}: parent_id {leaf['parent_id']} 없음")
                continue
            tasks.append(gen_one(client, sem, leaf, parent, cfg["prompt"]))

        results = await asyncio.gather(*tasks)
        for (leaf_id, ctx), leaf in zip(results, samples):
            issues = validate_sample(lang, leaf, ctx)
            status = "✓" if not issues else "✗"
            print(f"\n  [{status}] {leaf_id}")
            print(f"    leaf: {leaf['text'][:100]!r}...")
            print(f"    ctx ({len(ctx)} chars): {ctx[:200]!r}")
            if issues:
                all_ok = False
                for iss in issues:
                    print(f"    ⚠ {iss}")

    print("\n" + "=" * 60)
    if all_ok:
        print("✓ SMOKE PASSED — 본격 실행하려면 --run 옵션으로 재실행")
    else:
        print("✗ SMOKE FAILED — 위 issue 검토 후 프롬프트/로직 수정 필요")
    print("=" * 60)
    return all_ok


async def process_lang(lang, cfg):
    print(f"\n━━ {lang} 본격 실행 ━━")
    leaves, parent_texts = load_leaves(cfg["md"])
    leaves.sort(key=lambda l: l["doc_id"])
    print(f"  Leaves: {len(leaves)}  Parents: {len(parent_texts)}")

    out_path = Path(cfg["out"])
    cache = {}
    if out_path.exists():
        cache = json.loads(out_path.read_text(encoding="utf-8"))
        # ERROR 항목은 재처리 대상
        cache = {k: v for k, v in cache.items() if not v.startswith("[ERROR")}
        print(f"  Cache (ERROR 제외): {len(cache)} already done")
    todo = [l for l in leaves if l["leaf_id"] not in cache]
    print(f"  To generate: {len(todo)}")
    if not todo:
        return

    client = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
    sem = asyncio.Semaphore(CONCURRENCY)
    t0 = time.time()
    done = 0
    tasks = []
    for l in todo:
        parent = parent_texts.get(l["parent_id"], {}).get("text", "")
        if not parent:
            cache[l["leaf_id"]] = "[ERROR: no parent text]"
            done += 1
            continue
        tasks.append(asyncio.create_task(gen_one(client, sem, l, parent, cfg["prompt"])))

    for coro in asyncio.as_completed(tasks):
        leaf_id, ctx = await coro
        cache[leaf_id] = ctx
        done += 1
        if done % SAVE_EVERY == 0 or done == len(todo):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (len(todo) - done) / rate if rate > 0 else 0
            print(f"    [{done:4d}/{len(todo)}]  {rate:.2f} leaf/s  elapsed={elapsed:.0f}s  ETA={eta:.0f}s")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="본격 실행 (기본은 smoke만)")
    args = ap.parse_args()

    if not args.run:
        ok = await smoke_test()
        sys.exit(0 if ok else 1)

    for lang, cfg in SOURCES.items():
        await process_lang(lang, cfg)


if __name__ == "__main__":
    asyncio.run(main())
