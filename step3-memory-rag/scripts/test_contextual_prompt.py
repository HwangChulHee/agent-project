"""
Stage B substep 1: Contextual Retrieval 프롬프트 캘리브레이션.
단일 leaf로 Gemma 4 컨텍스트 생성 품질·길이·thinking 동작 확인.
"""
import time
from pathlib import Path
from openai import OpenAI

VLLM_URL = "http://localhost:8000/v1"
MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"

DOC_PATH = Path("data/wikipedia_md/Albert_Einstein.md")
TEST_LEAF = """## Awards and honors
Einstein received numerous awards and honors, and in 1922, he was awarded the 1921 Nobel Prize in Physics "for his services to Theoretical Physics, and especially for his discovery of the law of the photoelectric effect". The Nobel committee decided that none of the nominations in 1921 met the criteria set by Alfred Nobel, so the 1921 prize was carried forward and awarded to Einstein in 1922."""

document = DOC_PATH.read_text(encoding="utf-8")

# Anthropic Contextual Retrieval 원본 프롬프트 (2024)
PROMPT = f"""<document>
{document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{TEST_LEAF}
</chunk>

Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

print(f"Document: {DOC_PATH.name}  ({len(document):,} chars)")
print(f"Leaf: {len(TEST_LEAF)} chars")
print(f"Prompt total: {len(PROMPT):,} chars\n")

client = OpenAI(base_url=VLLM_URL, api_key="dummy")

t0 = time.time()
resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": PROMPT}],
    temperature=0.0,
    max_tokens=300,
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
elapsed = time.time() - t0

msg = resp.choices[0].message
context = (msg.content or "").strip()
reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None)

print("=" * 70)
print(f"CONTEXT ({len(context)} chars):")
print("=" * 70)
print(context)
print()

if reasoning:
    print("=" * 70)
    print(f"[!] thinking 활성 — reasoning {len(reasoning)} chars (요약 작업엔 불필요)")
    print("=" * 70)
    print(reasoning[:400] + ("..." if len(reasoning) > 400 else ""))
    print()

print(f"Elapsed: {elapsed:.1f}s")
print(f"Usage: prompt={resp.usage.prompt_tokens}  completion={resp.usage.completion_tokens}")
