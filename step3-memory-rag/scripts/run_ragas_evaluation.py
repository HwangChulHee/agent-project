"""Stage B: answers.json → RAGAs 5메트릭 일괄 채점.

사용:
    uv run python scripts/run_ragas_evaluation.py --judge mini
    uv run python scripts/run_ragas_evaluation.py --judge nano
    uv run python scripts/run_ragas_evaluation.py --judge gemma

산출: chroma_db/ragas_results_{judge}.json
"""
import argparse
import json
import math
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
    answer_correctness,
)
from rag.ragas_eval import get_judge_llm, get_judge_embed, JUDGES

IN_PATH = Path("chroma_db/answers.json")

METRICS = [
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
    answer_correctness,
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", default="mini",
                        choices=list(JUDGES.keys()),
                        help="Judge 모델 (gemma/nano/mini)")
    parser.add_argument("--workers", type=int, default=16,
                        help="동시 호출 수")
    args = parser.parse_args()

    out_path = Path(f"chroma_db/ragas_results_{args.judge}.json")

    print(f"━━ Stage B: RAGAs 채점 ━━")
    print(f"  Judge: {args.judge} ({JUDGES[args.judge]['provider']}/{JUDGES[args.judge]['model']})")
    print(f"  Output: {out_path}")
    print(f"  Workers: {args.workers}\n")

    data = json.loads(IN_PATH.read_text())
    answers = [x for x in data if "answer" in x and x["answer"].strip()]
    errors = [x for x in data if "error" in x or not x.get("answer", "").strip()]
    print(f"  채점 대상: {len(answers)} / 오류 제외: {len(errors)}\n")

    dataset = Dataset.from_dict({
        "question":     [x["query"]           for x in answers],
        "contexts":     [x["chunks"]          for x in answers],
        "answer":       [x["answer"]          for x in answers],
        "ground_truth": [x["ground_truth_en"] for x in answers],
    })

    print(f"RAGAs evaluate() — {args.judge} judge")
    print(f"  메트릭 {len(METRICS)}개 × {len(answers)} answers\n")

    t0 = time.time()
    result = evaluate(
        dataset,
        metrics=METRICS,
        llm=get_judge_llm(args.judge),
        embeddings=get_judge_embed(),
        raise_exceptions=False,
        show_progress=True,
        run_config=RunConfig(
            max_workers=args.workers,
            timeout=300,
            max_retries=5,
        ),
    )
    elapsed = time.time() - t0
    print(f"\n  ✓ 완료. {elapsed/60:.1f}분\n")

    # 저장
    output = []
    for i, x in enumerate(answers):
        row = dict(x)
        for m in METRICS:
            v = result[m.name][i]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                row[m.name] = float(v)
            else:
                row[m.name] = None
        output.append(row)
    output.extend(errors)

    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"  ✓ {out_path} ({out_path.stat().st_size:,} 바이트)\n")

    # 요약
    print("━━ 전체 평균 ━━")
    for m in METRICS:
        scores = [r[m.name] for r in output if r.get(m.name) is not None]
        if scores:
            print(f"  {m.name:25s}: {sum(scores)/len(scores):.3f}  (n={len(scores)})")


if __name__ == "__main__":
    main()
