"""RAG 검색 도구 (LLM에게 노출)."""

from __future__ import annotations

from rag.retriever import Retriever


# 모듈 레벨 싱글톤: 모델 로딩이 비싸서 매번 새로 만들지 않음
_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever


# ── JSON Schema (step2 패턴) ─────────────────────────────────
RAG_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "rag_search",
        "description": (
            "Search the local Wikipedia knowledge base by semantic similarity. "
            "Returns the top-k most relevant text chunks with their source. "
            "Use this for factual questions about historical figures, scientists, "
            "or topics likely to be in Wikipedia (faster and more focused than wikipedia_search)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query in natural language. Can be in any language.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of chunks to return (default 3, max 5).",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
}


def rag_search(query: str, top_k: int = 3) -> str:
    """LLM 친화적 문자열로 검색 결과 포맷."""
    top_k = max(1, min(top_k, 5))  # 1~5 클램프
    results = get_retriever().search(query, top_k=top_k)

    if not results:
        return "No relevant chunks found in the knowledge base."

    lines = [f"Found {len(results)} chunks:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"--- Result {i} (source: {r.source}, distance: {r.distance:.3f}) ---")
        lines.append(r.chunk)
        lines.append("")
    return "\n".join(lines)
