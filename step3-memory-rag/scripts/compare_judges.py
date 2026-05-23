"""Judge별 점수 비교 분석.

산출: stdout
  - judge별 전체 평균
  - 12 매트릭스 × judge 그리드
  - Spearman correlation (judge 간 순위 일치)
"""
import json
import math
from collections import defaultdict
from pathlib import Path

METRICS = ["context_precision", "context_recall", "faithfulness",
           "answer_relevancy", "answer_correctness"]
METRIC_SHORT = {
    "context_precision": "CP",
    "context_recall": "CR",
    "faithfulness": "F",
    "answer_relevancy": "AR",
    "answer_correctness": "AC",
}


def is_valid(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


def load_judge(judge):
    path = Path(f"chroma_db/ragas_results_{judge}.json")
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main():
    # 가용 judge 자동 감지
    judges = {}
    for j in ["gemma", "nano", "mini", "sonnet"]:
        data = load_judge(j)
        if data:
            judges[j] = data
            print(f"  ✓ {j}: {len(data)} rows")
    if not judges:
        print("결과 파일 없음")
        return

    print()
    print("━" * 80)
    print("① 전체 평균 (judge 비교)")
    print("━" * 80)
    print(f"  {'judge':10s} " + " ".join(f"{METRIC_SHORT[m]:>7s}" for m in METRICS))
    for jname, data in judges.items():
        ok = [x for x in data if "answer" in x and "method" in x]
        avgs = []
        for m in METRICS:
            vs = [x[m] for x in ok if is_valid(x.get(m))]
            avgs.append(sum(vs)/len(vs) if vs else None)
        avg_strs = [f"{a:.3f}" if a is not None else "  -  " for a in avgs]
        print(f"  {jname:10s} " + " ".join(f"{a:>7s}" for a in avg_strs))

    # 매트릭스 × judge (5메트릭 평균)
    print()
    print("━" * 80)
    print("② 매트릭스 × judge (5메트릭 평균)")
    print("━" * 80)
    methods = set()
    matrix_judge = defaultdict(dict)
    for jname, data in judges.items():
        ok = [x for x in data if "answer" in x and "method" in x]
        by_method = defaultdict(list)
        for x in ok:
            valid = [x[m] for m in METRICS if is_valid(x.get(m))]
            if valid:
                by_method[x["method"]].append(sum(valid)/len(valid))
        for m, vs in by_method.items():
            matrix_judge[m][jname] = sum(vs)/len(vs) if vs else None
            methods.add(m)

    methods = sorted(methods)
    print(f"\n  {'매트릭스':30s} " + " ".join(f"{j:>8s}" for j in judges.keys()))
    for m in methods:
        cells = []
        for j in judges.keys():
            v = matrix_judge[m].get(j)
            cells.append(f"{v:.3f}" if v is not None else "  -  ")
        print(f"  {m:30s} " + " ".join(f"{c:>8s}" for c in cells))

    # judge별 매트릭스 순위 → 상관관계
    if len(judges) >= 2:
        print()
        print("━" * 80)
        print("③ judge 간 매트릭스 순위 일치도 (Spearman)")
        print("━" * 80)
        try:
            from scipy.stats import spearmanr
        except ImportError:
            print("  (scipy 없음 — 순위 비교 생략)")
            return

        judge_list = list(judges.keys())
        # 각 judge가 매트릭스를 어떻게 순위
        rankings = {}
        for j in judge_list:
            scores = [(m, matrix_judge[m].get(j) or 0) for m in methods]
            scores.sort(key=lambda x: -x[1])
            rankings[j] = {m: i for i, (m, _) in enumerate(scores)}

        for i, j1 in enumerate(judge_list):
            for j2 in judge_list[i+1:]:
                r1 = [rankings[j1][m] for m in methods]
                r2 = [rankings[j2][m] for m in methods]
                rho, p = spearmanr(r1, r2)
                print(f"  {j1:10s} vs {j2:10s}: Spearman ρ = {rho:.3f}  (p={p:.3f})")


if __name__ == "__main__":
    main()
