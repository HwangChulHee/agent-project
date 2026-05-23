"""RAGAs 평가 어댑터 — 여러 judge 모델 지원.

Judge 옵션:
  - gemma: 로컬 vLLM Gemma 26B (포트 8000)
  - nano:  OpenAI gpt-5.4-nano
  - mini:  OpenAI gpt-5.4-mini

5메트릭:
  - context_precision, context_recall, faithfulness,
    answer_relevancy, answer_correctness
"""
import os
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
    answer_correctness,
)
from datasets import Dataset

VLLM_JUDGE_URL = "http://localhost:8000/v1"
VLLM_JUDGE_MODEL = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
VLLM_EMBED_URL = "http://localhost:8003/v1"
VLLM_EMBED_MODEL = "BAAI/bge-m3"

JUDGES = {
    "gemma": {"provider": "vllm",   "model": VLLM_JUDGE_MODEL},
    "nano":  {"provider": "openai", "model": "gpt-5.4-nano"},
    "mini":  {"provider": "openai", "model": "gpt-5.4-mini"},
}

_judge_llm = None
_judge_embed = None
_current_judge = None


def get_judge_llm(judge_key: str = "gemma"):
    """Judge LLM. judge_key별 캐시."""
    global _judge_llm, _current_judge
    if _judge_llm is None or _current_judge != judge_key:
        cfg = JUDGES[judge_key]
        if cfg["provider"] == "vllm":
            chat = ChatOpenAI(
                base_url=VLLM_JUDGE_URL,
                api_key="EMPTY",
                model=cfg["model"],
                temperature=0.0,
                max_tokens=2048,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        else:
            # GPT-5 reasoning model: temperature 1만 지원, max_tokens → max_completion_tokens 자동 변환
            chat = ChatOpenAI(
                model=cfg["model"],
                max_tokens=2048,
                reasoning_effort="none",
            )
        _judge_llm = LangchainLLMWrapper(chat)
        _current_judge = judge_key
    return _judge_llm


def get_judge_embed():
    """BGE-M3을 langchain OpenAIEmbeddings로 감쌈."""
    global _judge_embed
    if _judge_embed is None:
        os.environ.setdefault("OPENAI_API_KEY", "EMPTY")
        emb = OpenAIEmbeddings(
            base_url=VLLM_EMBED_URL,
            api_key="EMPTY",
            model=VLLM_EMBED_MODEL,
            check_embedding_ctx_length=False,
        )
        _judge_embed = LangchainEmbeddingsWrapper(emb)
    return _judge_embed


def evaluate_one(
    question: str,
    contexts: list[str],
    answer: str,
    ground_truth: str,
    judge_key: str = "gemma",
    metrics: Optional[list] = None,
) -> dict:
    """1 쿼리 채점 (디버그/스모크용)."""
    if metrics is None:
        metrics = [
            context_precision, context_recall, faithfulness,
            answer_relevancy, answer_correctness,
        ]
    dataset = Dataset.from_dict({
        "question":     [question],
        "contexts":     [contexts],
        "answer":       [answer],
        "ground_truth": [ground_truth],
    })
    result = evaluate(
        dataset,
        metrics=metrics,
        llm=get_judge_llm(judge_key),
        embeddings=get_judge_embed(),
        raise_exceptions=False,
        show_progress=False,
    )
    return {m.name: float(result[m.name][0]) if result[m.name][0] is not None else None
            for m in metrics}
