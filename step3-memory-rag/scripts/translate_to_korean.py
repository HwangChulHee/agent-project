"""
영문 차라투스트라 markdown → 한국어 markdown.
- # / ## / ### 헤더 단위로 분할
- 각 섹션을 Gemma 4로 비동기 번역
- 헤더는 그대로 보존, 본문만 번역
- 챕터 제목(##)은 짧게 번역
"""
import asyncio, json, re, time
from pathlib import Path
from openai import AsyncOpenAI

VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
SRC = Path("data/nietzsche_md/zarathustra_en.md")
DST = Path("data/nietzsche_md/zarathustra_ko.md")
CACHE_PATH = Path("data/nietzsche_md/translation_cache.json")
CONCURRENCY = 8
SAVE_EVERY = 5

BODY_PROMPT = """다음은 니체의 "차라투스트라는 이렇게 말했다" 영문 텍스트의 한 부분이다. 시적 어조를 유지하며 한국어로 번역하라.

규칙:
- 마크다운 헤더(# ## ###)는 번역하지 말고 그대로 보존
- 헤더 줄 위치도 그대로 유지
- 단순 직역 X, 시적 한국어로 자연스럽게
- "Zarathustra" → "차라투스트라"
- 종교적 고풍체("thou", "hath" 등)는 한국어 문어체로 (예: 황문수 번역 톤)
- 답변은 번역된 텍스트만, 다른 설명 없이

영문:
\"\"\"
{text}
\"\"\""""

TITLE_PROMPT = """다음 영문 챕터 제목을 한국어로 짧고 시적으로 번역하라. 답변은 한국어 제목 한 줄만:

{title}"""


def split_by_header(text: str):
    """## 챕터 헤더를 기준으로 본문 분할. 각 청크는 [헤더라인, 본문라인들] 포함."""
    lines = text.splitlines()
    chunks = []
    cur = []
    cur_key = "preamble"
    for line in lines:
        # ## 헤더(=챕터) 또는 # 헤더(=Part) 만나면 새 청크
        if re.match(r"^#{1,2}\s", line):
            if cur:
                chunks.append((cur_key, "\n".join(cur)))
            cur_key = line.strip()
            cur = [line]
        else:
            cur.append(line)
    if cur:
        chunks.append((cur_key, "\n".join(cur)))
    return chunks


async def translate_one(client, sem, key, body_text):
    async with sem:
        try:
            resp = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": BODY_PROMPT.format(text=body_text)}],
                temperature=0.3,
                max_tokens=4000,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
            ko = (resp.choices[0].message.content or "").strip()
            # LLM이 가끔 ```markdown ... ``` 펜스로 감쌈 — 벗기기
            ko = re.sub(r"^```\w*\n?", "", ko)
            ko = re.sub(r"\n?```\s*$", "", ko)
            return key, ko, None
        except Exception as e:
            return key, None, str(e)


async def main():
    src_text = SRC.read_text(encoding="utf-8")
    chunks = split_by_header(src_text)
    print(f"Split into {len(chunks)} sections")

    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        print(f"Cache: {len(cache)} already translated")
    todo = [(k, t) for (k, t) in chunks if k not in cache]
    print(f"To translate: {len(todo)}")
    if not todo:
        print("All cached.")
    else:
        client = AsyncOpenAI(base_url=VLLM_URL, api_key="dummy")
        sem = asyncio.Semaphore(CONCURRENCY)
        t0 = time.time()
        done = 0
        tasks = [asyncio.create_task(translate_one(client, sem, k, t)) for k, t in todo]
        errors = []
        for coro in asyncio.as_completed(tasks):
            key, ko, err = await coro
            if err:
                errors.append((key, err))
            else:
                cache[key] = ko
            done += 1
            if done % SAVE_EVERY == 0 or done == len(todo):
                CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
                rate = done / (time.time() - t0)
                eta = (len(todo) - done) / rate if rate > 0 else 0
                print(f"  [{done:3d}/{len(todo)}]  {rate:.2f} sec/s  ETA={eta:.0f}s")
        if errors:
            print(f"\n⚠ {len(errors)} errors:")
            for k, e in errors[:5]:
                print(f"  - {k!r}: {e[:80]}")

    # 합치기 — 원본 순서 유지
    parts = []
    for k, _ in chunks:
        if k in cache:
            parts.append(cache[k])
        else:
            parts.append(f"\n<!-- 번역 누락: {k} -->\n")
    DST.write_text("\n\n".join(parts), encoding="utf-8")
    print(f"\nWrote {DST} ({DST.stat().st_size:,} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
