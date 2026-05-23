"""ragas_results.json 분석 — 12 매트릭스 × 5 메트릭 × 4 카테고리 그리드.

산출: stdout 발표용 표
"""
import json
import math
from collections import defaultdict
from pathlib import Path

IN_PATH = Path("chroma_db/ragas_results.json")
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
    """NaN/None 제외."""
    if v is None:
        return False
    if isinstance(v, float) and math.isnan(v):
        return False
    return True


def mean(vals):
    valid = [v for v in vals if is_valid(v)]
    return sum(valid) / len(valid) if valid else None


def main():
    data = json.loads(IN_PATH.read_text())

    # 답변 성공/실패 분리
    ok = [x for x in data if "answer" in x and "method" in x]
    errors = [x for x in data if "error" in x]
    print(f"━━ 데이터 ━━")
    print(f"  답변 성공: {len(ok)}")
    print(f"  답변 실패: {len(errors)}")
    print()

    # ───────────────────────────────────────────────
    # 1) 매트릭스별 (12) × 5 메트릭
    # ───────────────────────────────────────────────
    print("━" * 90)
    print("① 매트릭스 × 메트릭 평균")
    print("━" * 90)
    by_method = defaultdict(lambda: defaultdict(list))
    for x in ok:
        for m in METRICS:
            v = x.get(m)
            if is_valid(v):
                by_method[x["method"]][m].append(v)

    header = f"{'매트릭스':30s} " + " ".join(f"{METRIC_SHORT[m]:>6s}" for m in METRICS) + f"  {'mean':>6s} {'n':>4s}"
    print(header)
    print("-" * len(header))

    rows = []
    for method in sorted(by_method.keys()):
        scores = [mean(by_method[method][m]) for m in METRICS]
        valid_scores = [s for s in scores if s is not None]
        overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0
        n = sum(1 for x in ok if x["method"] == method)
        rows.append((method, scores, overall, n))
        score_strs = [f"{s:.3f}" if s is not None else "  -  " for s in scores]
        print(f"{method:30s} " + " ".join(f"{s:>6s}" for s in score_strs) +
              f"  {overall:>6.3f} {n:>4d}")

    # ───────────────────────────────────────────────
    # 2) 종합 순위
    # ───────────────────────────────────────────────
    print()
    print("━" * 90)
    print("② 종합 순위 (5메트릭 평균)")
    print("━" * 90)
    for i, (method, _, overall, n) in enumerate(sorted(rows, key=lambda x: -x[2])):
        marker = "★" if i < 3 else " "
        print(f"  {marker} {overall:.3f}  {method:30s}  (n={n})")

    # ───────────────────────────────────────────────
    # 3) 임베딩 전략별 / 검색 기법별 평균
    # ───────────────────────────────────────────────
    print()
    print("━" * 90)
    print("③ 임베딩 전략별 / 검색 기법별 평균")
    print("━" * 90)

    by_emb = defaultdict(lambda: defaultdict(list))
    by_sm = defaultdict(lambda: defaultdict(list))
    for x in ok:
        for m in METRICS:
            v = x.get(m)
            if is_valid(v):
                by_emb[x["embed_strategy"]][m].append(v)
                by_sm[x["search_method"]][m].append(v)

    print("\n  [임베딩 전략]")
    print(f"  {'전략':16s} " + " ".join(f"{METRIC_SHORT[m]:>6s}" for m in METRICS) + f"  {'mean':>6s}")
    for emb in ["baseline", "hierarchical", "contextual"]:
        scores = [mean(by_emb[emb][m]) for m in METRICS]
        valid = [s for s in scores if s is not None]
        overall = sum(valid)/len(valid) if valid else 0
        ss = [f"{s:.3f}" if s is not None else "  -  " for s in scores]
        print(f"  {emb:16s} " + " ".join(f"{s:>6s}" for s in ss) + f"  {overall:>6.3f}")

    print("\n  [검색 기법]")
    print(f"  {'기법':16s} " + " ".join(f"{METRIC_SHORT[m]:>6s}" for m in METRICS) + f"  {'mean':>6s}")
    for sm in ["dense", "hybrid", "reranking", "hybrid_rr"]:
        scores = [mean(by_sm[sm][m]) for m in METRICS]
        valid = [s for s in scores if s is not None]
        overall = sum(valid)/len(valid) if valid else 0
        ss = [f"{s:.3f}" if s is not None else "  -  " for s in scores]
        print(f"  {sm:16s} " + " ".join(f"{s:>6s}" for s in ss) + f"  {overall:>6.3f}")

    # ───────────────────────────────────────────────
    # 4) 카테고리별 평균
    # ───────────────────────────────────────────────
    print()
    print("━" * 90)
    print("④ 카테고리별 평균")
    print("━" * 90)
    by_cat = defaultdict(lambda: defaultdict(list))
    for x in ok:
        cat = x.get("category", "?")
        for m in METRICS:
            v = x.get(m)
            if is_valid(v):
                by_cat[cat][m].append(v)

    print(f"\n  {'카테고리':16s} " + " ".join(f"{METRIC_SHORT[m]:>6s}" for m in METRICS) + f"  {'mean':>6s} {'n':>4s}")
    for cat in sorted(by_cat.keys()):
        scores = [mean(by_cat[cat][m]) for m in METRICS]
        valid = [s for s in scores if s is not None]
        overall = sum(valid)/len(valid) if valid else 0
        n = sum(1 for x in ok if x.get("category") == cat)
        ss = [f"{s:.3f}" if s is not None else "  -  " for s in scores]
        print(f"  {cat:16s} " + " ".join(f"{s:>6s}" for s in ss) + f"  {overall:>6.3f} {n:>4d}")

    # ───────────────────────────────────────────────
    # 5) 카테고리 × 매트릭스 그리드 (5메트릭 평균)
    # ───────────────────────────────────────────────
    print()
    print("━" * 90)
    print("⑤ 카테고리 × 매트릭스 (5메트릭 평균)")
    print("━" * 90)
    cat_method = defaultdict(lambda: defaultdict(list))
    for x in ok:
        cat = x.get("category", "?")
        valid_scores = [x[m] for m in METRICS if is_valid(x.get(m))]
        if valid_scores:
            cat_method[cat][x["method"]].append(sum(valid_scores)/len(valid_scores))

    cats = sorted(cat_method.keys())
    methods = sorted(by_method.keys())
    print(f"\n  {'매트릭스':30s} " + " ".join(f"{c[:10]:>10s}" for c in cats))
    print("  " + "-" * (30 + len(cats)*11))
    for method in methods:
        cells = []
        for cat in cats:
            vals = cat_method[cat][method]
            if vals:
                cells.append(f"{sum(vals)/len(vals):.3f}")
            else:
                cells.append("  -  ")
        print(f"  {method:30s} " + " ".join(f"{v:>10s}" for v in cells))

    # ───────────────────────────────────────────────
    # 6) 시간 비교 (TTFT / Total / errors)
    # ───────────────────────────────────────────────
    print()
    print("━" * 90)
    print("⑥ 매트릭스별 시간 + 오류율")
    print("━" * 90)
    ttft = defaultdict(list)
    total = defaultdict(list)
    err = defaultdict(int)
    for x in data:
        method = x.get("method") if "method" in x else f"{x.get('embed_strategy')}_{x.get('search_method')}"
        if "error" in x:
            err[method] += 1
        else:
            if x.get("ttft_ms"):
                ttft[method].append(x["ttft_ms"])
            if x.get("total_ms"):
                total[method].append(x["total_ms"])

    print(f"\n  {'매트릭스':30s} {'TTFT':>8s} {'Total':>8s} {'오류':>8s} {'성공':>5s}")
    for method in sorted(set(list(ttft.keys()) + list(err.keys()))):
        n_err = err.get(method, 0)
        n_ok = 35 - n_err
        ttft_avg = sum(ttft[method])/len(ttft[method]) if ttft[method] else 0
        total_avg = sum(total[method])/len(total[method]) if total[method] else 0
        print(f"  {method:30s} {ttft_avg:>5.0f}ms {total_avg:>6.0f}ms {n_err:>5d}/35 {n_ok:>5d}")

    # ───────────────────────────────────────────────
    # 7) NaN 비율 — 메트릭별
    # ───────────────────────────────────────────────
    print()
    print("━" * 90)
    print("⑦ 메트릭별 NaN 비율")
    print("━" * 90)
    print(f"\n  {'메트릭':25s} {'n_valid':>8s} {'n_nan':>8s} {'%':>8s}")
    for m in METRICS:
        n_valid = sum(1 for x in ok if is_valid(x.get(m)))
        n_nan = len(ok) - n_valid
        pct = n_nan / len(ok) * 100 if ok else 0
        print(f"  {m:25s} {n_valid:>8d} {n_nan:>8d} {pct:>7.1f}%")


if __name__ == "__main__":
    main()
