"""rag/embed_api.py — vLLM OpenAI-compat embeddings as a SentenceTransformer-like client.

Drop-in replacement for the three calls the build scripts use:
  - SentenceTransformer(model)
  - .encode(texts, batch_size=..., normalize_embeddings=..., show_progress_bar=...)
  - .get_embedding_dimension() / .get_sentence_embedding_dimension()
"""
import os
from typing import Iterable
import numpy as np
import httpx

DEFAULT_URL = os.environ.get("EMBED_API_URL", "http://localhost:8003/v1/embeddings")
DEFAULT_TIMEOUT = 600.0  # large batches on long chunks can take a while


class ApiEmbedder:
    def __init__(self, model: str, url: str = DEFAULT_URL, timeout: float = DEFAULT_TIMEOUT):
        self.model = model
        self.url = url
        self._client = httpx.Client(timeout=timeout)
        self._dim: int | None = None

    def _post(self, batch: list[str]) -> list[list[float]]:
        r = self._client.post(self.url, json={"model": self.model, "input": batch})
        r.raise_for_status()
        data = r.json()["data"]
        # API may reorder; sort by index to be safe
        data.sort(key=lambda x: x["index"])
        return [d["embedding"] for d in data]

    def encode(
        self,
        texts: Iterable[str],
        batch_size: int = 16,
        normalize_embeddings: bool = False,
        show_progress_bar: bool = False,
        **_ignored,
    ) -> np.ndarray:
        texts = list(texts)
        out: list[list[float]] = []
        total = len(texts)
        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            out.extend(self._post(batch))
            if show_progress_bar:
                print(f"  encode {min(i + batch_size, total)}/{total}", flush=True)
        arr = np.array(out, dtype=np.float32)
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            arr = arr / norms
        if self._dim is None and arr.size:
            self._dim = arr.shape[1]
        return arr

    @property
    def tokenizer(self):
        if not hasattr(self, "_tok"):
            from transformers import AutoTokenizer
            self._tok = AutoTokenizer.from_pretrained(self.model)
        return self._tok

    def get_embedding_dimension(self) -> int:
        if self._dim is None:
            # Probe with a tiny call.
            self._dim = len(self._post(["probe"])[0])
        return self._dim

    # Backward-compat alias for the older SentenceTransformer method name.
    def get_sentence_embedding_dimension(self) -> int:
        return self.get_embedding_dimension()


# Drop-in name — build scripts can keep `SentenceTransformer(EMBED_MODEL)` calls.
SentenceTransformer = ApiEmbedder
