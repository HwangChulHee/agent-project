"""pending 1차 분류 일괄 적용. data/lexicon.json의 status를 바꾼다.

기본 = dry-run(검산 + 미리보기만). 실제 적용은 --apply.
검산: 계획(approve/reject/merge)이 현재 pending 전체를 빠짐없이 덮는지 확인.
      누락·오타가 있으면 적용하지 않고 중단.
"""
import json
import sys
from pathlib import Path

LEX = Path("data/lexicon.json")

APPROVE = [
    "adapter", "AgentVerse", "ALiBi", "AutoGPT", "BLOOM", "BM25", "BP-Transformer",
    "ChatDev", "Conv-KNRM", "DRMM", "DSSM", "Duet", "E5", "ELMo",
    "Few-shot chain-of-thought prompting", "GLM", "GPT-4", "GPT-NeoX", "GRU",
    "Jina Embeddings v1", "kNN-LM", "KNRM", "LangChain", "LSTM", "Mixture of Experts",
    "monoT5", "Monte Carlo Tree Search", "mT5", "OpenAI GPT", "OPT", "ORQA",
    "Pathways", "prefix-tuning", "RankNet", "Reformer", "RoBERTa", "RNN", "SayCan",
    "SNRM", "TF-IDF", "Transformer-XL", "WebGPT", "Zero-shot-CoT",
    "Zero-shot-Program-of-Thought Prompting",
]

REJECT = [
    "Brown et al. (2020)", "Cobbe et al. (2021)", "Kaplan et al.",
    "attention mechanisms", "fine-tuning", "beam search", "greedy decoding",
    "standard attention", "sparse attention", "approximate attention",
    "linear attention", "low-rank approximation", "ensemble-based approaches",
    "sample-and-rank", "retrieve-then-read",
    "Adaptive Span", "Compressive", "Sparse", "Routing", "Blockwise",
    "Dense retrieval", "structured state space models", "novelty search",
]

MERGE = [("Llama 1", "LLaMA")]  # (from, into): from을 into의 alias로 흡수 후 삭제


def main():
    do_apply = "--apply" in sys.argv
    lex = json.loads(LEX.read_text())
    tech = lex["techniques"]

    pending = {k for k, v in tech.items() if v["status"] == "pending"}
    planned = set(APPROVE) | set(REJECT) | {m[0] for m in MERGE}

    missing = sorted(k for k in planned if k not in tech)
    unplanned = sorted(pending - planned)
    not_pending = sorted(k for k in planned if k in tech and tech[k]["status"] != "pending")

    print(f"현재 pending {len(pending)}개 / 계획 {len(planned)}개 "
          f"(approve {len(APPROVE)} · reject {len(REJECT)} · merge {len(MERGE)})")
    if missing:
        print("  ✗ 사전에 없는 키(오타?):", missing)
    if unplanned:
        print("  ✗ 분류 안 된 pending:", unplanned)
    if not_pending:
        print("  ⚠ 이미 pending이 아님(무해, 건너뜀):", not_pending)

    if missing or unplanned:
        print("\n검산 실패 — 적용하지 않음. 위 항목 고치고 다시 실행.")
        sys.exit(1)
    print("\n검산 통과 ✓")

    if not do_apply:
        print("미리보기 모드. 실제 적용하려면:  uv run python apply_pending.py --apply")
        return

    for k in APPROVE:
        tech[k]["status"] = "approved"
    for k in REJECT:
        tech[k]["status"] = "rejected"
    for src, dst in MERGE:
        if src in tech and dst in tech:
            aliases = tech[dst].setdefault("aliases", [])
            for a in [src] + tech[src].get("aliases", []):
                if a not in aliases and a != dst:
                    aliases.append(a)
            del tech[src]

    LEX.write_text(json.dumps(lex, ensure_ascii=False, indent=2))
    counts = {}
    for v in tech.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print(f"적용 완료. 사전 현황: {counts}")
    print("다음: 재빌드(normalize)를 돌려야 그래프에 반영됨.")


if __name__ == "__main__":
    main()
