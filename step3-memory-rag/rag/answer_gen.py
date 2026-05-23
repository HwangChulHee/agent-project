"""E2B로 한국어 답변 생성 (RAG context prepend).

비주얼 노벨 해설 모드 페르소나:
  - 해설자 톤
  - 자료에 없으면 추측 X
  - 1~3 문단

전제: E2B 서버 (8004) 가동 중
"""
import time
from typing import Optional

from openai import OpenAI

E2B_URL = "http://localhost:8004/v1"
E2B_MODEL = "google/gemma-4-E2B-it"

SYSTEM_PROMPT = """당신은 니체 철학 비주얼 노벨의 해설자입니다.
사용자가 '차라투스트라는 이렇게 말했다'를 읽으며 궁금한 점을 묻습니다.
참고 자료를 바탕으로 1~3 문단의 명료한 한국어로 답하세요.

원칙:
- 참고 자료에 없는 내용은 추측하지 마세요
- 학습자가 이해하기 쉬운 한국어로 설명
- 영어 자료를 참고하되 답변은 한국어로
- 핵심 개념은 원어와 한국어 표기 병기 (예: 위버멘쉬(Übermensch))
"""


def build_prompt(query: str, chunks: list[str]) -> str:
    """사용자 메시지 구성."""
    context = "\n\n---\n\n".join(
        f"[참고 자료 {i+1}]\n{c}" for i, c in enumerate(chunks)
    )
    return f"""다음은 사용자 질문에 답하기 위한 참고 자료입니다.

{context}

---

[학습자 질문]
{query}

위 자료를 바탕으로 한국어로 답하세요."""


def generate_answer(
    query: str,
    chunks: list[str],
    temperature: float = 0.3,
    max_tokens: int = 600,
    timeout: float = 60.0,
) -> dict:
    """E2B 답변 생성 + TTFT/총 시간 측정.

    Returns:
        {
            "answer": str,           # 생성된 한국어 답변
            "ttft_ms": float,        # 첫 토큰까지 시간
            "total_ms": float,       # 전체 시간
            "input_tokens": int,
            "output_tokens": int,
        }
    """
    client = OpenAI(base_url=E2B_URL, api_key="EMPTY", timeout=timeout)
    user_prompt = build_prompt(query, chunks)

    t0 = time.time()
    first_token_time = None
    chunks_out = []
    input_tokens = 0
    output_tokens = 0

    stream = client.chat.completions.create(
        model=E2B_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    for evt in stream:
        if evt.choices and evt.choices[0].delta.content:
            if first_token_time is None:
                first_token_time = time.time()
            chunks_out.append(evt.choices[0].delta.content)
        if evt.usage:
            input_tokens = evt.usage.prompt_tokens
            output_tokens = evt.usage.completion_tokens

    t_end = time.time()
    answer = "".join(chunks_out).strip()

    return {
        "answer": answer,
        "ttft_ms": (first_token_time - t0) * 1000 if first_token_time else None,
        "total_ms": (t_end - t0) * 1000,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
