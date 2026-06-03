"""
실제 arXiv abstract 여러 개를 차례로 맵에 통과시키는 미니 러너.
(나중에 collector가 이 자리를 대체)
기존 맵에 누적. 깨끗이 시작하려면 먼저: uv run python -m kb.store
"""
from kb.store import load_map, save_map, new_map, find_gaps
from agents.entity_extraction_agent import extract
from agents.schema_alignment_agent import align

SOURCES = [
    ("memreranker-2605.06132",
     "In agent memory systems, the reranking model serves as the critical "
     "bridge connecting user queries with long-term memory. MemReranker is a "
     "reranking model family built on Qwen3-Reranker through multi-stage LLM "
     "knowledge distillation. Multi-teacher pairwise comparisons generate "
     "calibrated soft labels, BCE pointwise distillation establishes "
     "well-distributed scores, and InfoNCE contrastive learning enhances "
     "hard-sample discrimination. On the memory retrieval benchmark, "
     "MemReranker substantially outperforms BGE-Reranker while maintaining "
     "low inference latency."),

    ("xmemory-2602.02007",
     "We propose xMemory, which builds a hierarchy of intact units and "
     "maintains a searchable yet faithful high-level node organisation via a "
     "sparsity-semantics objective that guides memory split and merge. At "
     "inference, xMemory retrieves top-down, selecting a compact, diverse set "
     "of themes and semantics for multi-fact queries, and expanding to "
     "episodes and raw messages only when it reduces the reader's uncertainty."),

    ("beyond-rag-2602.02007b",
     "Agent memory does not match the core RAG setting. RAG is designed for "
     "large, heterogeneous corpora where retrieved passages are diverse and "
     "the main failure mode is irrelevance. In contrast, an agent's memory "
     "forms a coherent and highly correlated stream, where many spans are "
     "near duplicates; similarity top-k retrieval can therefore collapse and "
     "retrieve redundant chunks. We organise memories into a hierarchy of "
     "intact units and perform structure-aware retrieval to produce a shorter "
     "but more answer-sufficient context."),
]


def main():
    try:
        m = load_map()
    except FileNotFoundError:
        m = new_map()

    for sid, text in SOURCES:
        print(f"\n{'='*55}\n[{sid}] 처리 중...\n{'='*55}")
        extracted = extract(text)
        concepts = [c["id"] for c in extracted.get("concepts", [])]
        print(f"추출된 개념 ({len(concepts)}개): {concepts}")

        added, merged = align(m, extracted, source=sid)
        print(f"  신규(my_level=0): {added}")
        print(f"  기존으로 병합:    {merged}")

    save_map(m)
    print(f"\n{'='*55}\n최종 상태\n{'='*55}")
    print(f"전체 노드 수: {len(m['nodes'])}")
    print(f"현재 갭(모르는 개념): {find_gaps(m)}")


if __name__ == "__main__":
    main()
