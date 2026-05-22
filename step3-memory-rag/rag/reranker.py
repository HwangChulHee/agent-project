"""rag/reranker.py — Cross-encoder reranker via vLLM HTTP API (port 8005)."""
from __future__ import annotations
import os
from typing import Sequence
import httpx


DEFAULT_URL = os.environ.get("RERANK_API_URL", "http://localhost:8005/v1/score")
DEFAULT_MODEL = os.environ.get("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
DEFAULT_TIMEOUT = 120.0


class Reranker:
    def __init__(self, model: str = DEFAULT_MODEL, url: str = DEFAULT_URL,
                 timeout: float = DEFAULT_TIMEOUT):
        self.model = model
        self.url = url
        self._client = httpx.Client(timeout=timeout)

    def score(self, query: str, docs: Sequence[str], batch_size: int = 32) -> list[float]:
        """Return one score per (query, doc) pair. Higher = more relevant.
        vLLM handles batching internally; batch_size kept for API compat.
        """
        r = self._client.post(self.url, json={
            "model": self.model,
            "text_1": query,
            "text_2": list(docs),
        })
        r.raise_for_status()
        data = r.json()["data"]
        data.sort(key=lambda x: x["index"])
        return [d["score"] for d in data]


def smoke():
    cases = [
        {
            "lang": "EN",
            "query": "How old was Zarathustra when he left his home?",
            "docs": {
                "answer":   "When Zarathustra was thirty years old, he left his home and went into the mountains.",
                "related":  "Zarathustra spent ten years in the mountains, enjoying his spirit and solitude.",
                "unrelated":"On the olive-mount, winter sat with him as a bad guest.",
            },
        },
        {
            "lang": "KO",
            "query": "차라투스트라는 몇 살에 산으로 들어갔는가?",
            "docs": {
                "answer":   "차라투스트라가 서른 살 되던 해, 그는 고향과 그 고향의 호수를 떠나 산으로 들어갔다.",
                "related":  "그곳에서 그는 자신의 정신과 고독을 즐겼으며, 십 년 동안 그것에 지치지 않았다.",
                "unrelated":"올리브 산 위에는 겨울이 나쁜 손님처럼 그와 함께 앉아 있었다.",
            },
        },
    ]

    print(f"[client] {DEFAULT_URL}")
    rr = Reranker()

    all_pass = True
    for case in cases:
        labels = list(case["docs"].keys())
        texts = [case["docs"][k] for k in labels]
        scores = rr.score(case["query"], texts)
        ranked = sorted(zip(labels, scores), key=lambda x: -x[1])

        print(f"━━ {case['lang']}: {case['query']!r} ━━")
        for label, score in ranked:
            mark = "  ←" if label == "answer" and ranked[0][0] == "answer" else ""
            print(f"  {label:10s} score={score:.6f}{mark}")
        if ranked[0][0] != "answer":
            print(f"  ✗ FAIL — '{ranked[0][0]}' beat 'answer'")
            all_pass = False
        print()

    print("[smoke] ✓ PASS" if all_pass else "[smoke] ✗ FAIL")
    return all_pass


if __name__ == "__main__":
    import sys
    sys.exit(0 if smoke() else 1)
