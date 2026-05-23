"""발표용 시각화 5장 — docs/plots/ 저장."""
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from scipy.stats import spearmanr

OUT_DIR = Path("docs/plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

mpl.rcParams['font.family'] = 'DejaVu Sans'
mpl.rcParams['axes.unicode_minus'] = False

METRICS = ["context_precision", "context_recall", "faithfulness",
           "answer_relevancy", "answer_correctness"]
METRIC_SHORT = {
    "context_precision": "CP", "context_recall": "CR",
    "faithfulness": "Faith", "answer_relevancy": "Relev",
    "answer_correctness": "Correct",
}

SEPIA = "#8b6f47"
SEPIA_LIGHT = "#c4a878"
SEPIA_DARK = "#5c4628"
ACCENT = "#a83232"


def is_valid(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


gemma = json.loads(open("chroma_db/ragas_results_gemma.json").read())
mini  = json.loads(open("chroma_db/ragas_results_mini.json").read())


# ===========================================================================
# 1. Heatmap (Mini)
# ===========================================================================
ok = [x for x in mini if "answer" in x and "method" in x]
methods = sorted(set(x["method"] for x in ok))

data = np.zeros((len(methods), len(METRICS)))
for i, m in enumerate(methods):
    for j, metric in enumerate(METRICS):
        vs = [x[metric] for x in ok if x["method"] == m and is_valid(x.get(metric))]
        data[i, j] = sum(vs)/len(vs) if vs else np.nan

fig, ax = plt.subplots(figsize=(10, 7))
im = ax.imshow(data, cmap='YlOrBr', vmin=0.2, vmax=0.9, aspect='auto')
ax.set_xticks(range(len(METRICS)))
ax.set_xticklabels([METRIC_SHORT[m] for m in METRICS], fontsize=11)
ax.set_yticks(range(len(methods)))
ax.set_yticklabels(methods, fontsize=10)
for i in range(len(methods)):
    for j in range(len(METRICS)):
        v = data[i, j]
        color = "white" if v > 0.6 else "black"
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", color=color, fontsize=9)
plt.colorbar(im, ax=ax, label="Score")
ax.set_title("Matrix x Metric Score (Mini judge)", fontsize=13, pad=15)
plt.tight_layout()
plt.savefig(OUT_DIR / "01_heatmap.png", dpi=150, bbox_inches='tight')
plt.close()
print("✓ 01_heatmap.png")


# ===========================================================================
# 2. Score vs Error rate
# ===========================================================================
err_count = defaultdict(int)
for x in mini:
    if "error" in x:
        m = x.get("method") or f"{x.get('embed_strategy')}_{x.get('search_method')}"
        err_count[m] += 1

score_by_m = {}
for m in methods:
    avgs = []
    for metric in METRICS:
        vs = [x[metric] for x in ok if x["method"] == m and is_valid(x.get(metric))]
        if vs:
            avgs.append(sum(vs)/len(vs))
    score_by_m[m] = sum(avgs)/len(avgs) if avgs else 0

err_rates = [err_count.get(m, 0)/35*100 for m in methods]
scores = [score_by_m[m] for m in methods]

fig, ax1 = plt.subplots(figsize=(12, 6))
x = np.arange(len(methods))
width = 0.4

ax1.bar(x - width/2, scores, width, label='Score', color=SEPIA, edgecolor=SEPIA_DARK)
ax1.set_ylabel('Score (5-metric avg)', color=SEPIA_DARK, fontsize=12)
ax1.tick_params(axis='y', labelcolor=SEPIA_DARK)
ax1.set_ylim(0, 1.0)

ax2 = ax1.twinx()
ax2.bar(x + width/2, err_rates, width, label='Error %', color=ACCENT,
        edgecolor='#5c1818', alpha=0.85)
ax2.set_ylabel('Error rate (%)', color=ACCENT, fontsize=12)
ax2.tick_params(axis='y', labelcolor=ACCENT)
ax2.set_ylim(0, 40)

ax1.set_xticks(x)
ax1.set_xticklabels(methods, rotation=45, ha='right', fontsize=9)
ax1.set_title('Score vs Error Rate by Matrix', fontsize=13, pad=15)
ax1.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "02_score_vs_error.png", dpi=150, bbox_inches='tight')
plt.close()
print("✓ 02_score_vs_error.png")


# ===========================================================================
# 3. Category
# ===========================================================================
by_cat = defaultdict(lambda: defaultdict(list))
for x in ok:
    cat = x.get("category", "?")
    for m in METRICS:
        v = x.get(m)
        if is_valid(v):
            by_cat[cat][m].append(v)

categories = ["factoid", "concept", "metaphor", "background"]
cat_data = np.zeros((len(categories), len(METRICS)))
for i, cat in enumerate(categories):
    for j, m in enumerate(METRICS):
        vs = by_cat[cat][m]
        cat_data[i, j] = sum(vs)/len(vs) if vs else 0

fig, ax = plt.subplots(figsize=(11, 5.5))
x = np.arange(len(METRICS))
width = 0.2
colors = [SEPIA_DARK, SEPIA, SEPIA_LIGHT, ACCENT]
for i, cat in enumerate(categories):
    ax.bar(x + i*width, cat_data[i], width, label=cat,
           color=colors[i], edgecolor='black', linewidth=0.5)
ax.set_xticks(x + 1.5*width)
ax.set_xticklabels([METRIC_SHORT[m] for m in METRICS], fontsize=11)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('Score by Question Category (Mini judge)', fontsize=13, pad=15)
ax.set_ylim(0, 1.0)
ax.legend(loc='upper right', fontsize=10)
ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "03_category.png", dpi=150, bbox_inches='tight')
plt.close()
print("✓ 03_category.png")


# ===========================================================================
# 4. Timing
# ===========================================================================
ttft = defaultdict(list)
total = defaultdict(list)
for x in mini:
    if "answer" not in x:
        continue
    m = x["method"]
    if x.get("ttft_ms"):
        ttft[m].append(x["ttft_ms"])
    if x.get("total_ms"):
        total[m].append(x["total_ms"])

ttft_avg = [sum(ttft[m])/len(ttft[m]) if ttft[m] else 0 for m in methods]
total_avg = [sum(total[m])/len(total[m]) if total[m] else 0 for m in methods]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
ax1.barh(methods, ttft_avg, color=SEPIA, edgecolor=SEPIA_DARK)
ax1.set_xlabel('TTFT (ms)', fontsize=12)
ax1.set_title('Time to First Token', fontsize=13, pad=10)
ax1.invert_yaxis()
ax1.grid(axis='x', alpha=0.3)
for i, v in enumerate(ttft_avg):
    ax1.text(v + 2, i, f"{v:.0f}", va='center', fontsize=9)

ax2.barh(methods, total_avg, color=SEPIA_LIGHT, edgecolor=SEPIA_DARK)
ax2.set_xlabel('Total time (ms)', fontsize=12)
ax2.set_title('Total Response Time', fontsize=13, pad=10)
ax2.invert_yaxis()
ax2.grid(axis='x', alpha=0.3)
for i, v in enumerate(total_avg):
    ax2.text(v + 30, i, f"{v:.0f}", va='center', fontsize=9)
plt.tight_layout()
plt.savefig(OUT_DIR / "04_timing.png", dpi=150, bbox_inches='tight')
plt.close()
print("✓ 04_timing.png")


# ===========================================================================
# 5. Judge agreement
# ===========================================================================
gemma_ok = [x for x in gemma if "answer" in x and "method" in x]
gemma_score = {}
for m in methods:
    avgs = []
    for metric in METRICS:
        vs = [x[metric] for x in gemma_ok if x["method"] == m and is_valid(x.get(metric))]
        if vs:
            avgs.append(sum(vs)/len(vs))
    gemma_score[m] = sum(avgs)/len(avgs) if avgs else 0

gemma_vals = [gemma_score[m] for m in methods]
mini_vals  = [score_by_m[m] for m in methods]
rho, p = spearmanr(gemma_vals, mini_vals)

fig, ax = plt.subplots(figsize=(8, 8))
ax.scatter(gemma_vals, mini_vals, s=120, color=SEPIA, edgecolor=SEPIA_DARK,
           linewidth=1.5, zorder=3)
for i, m in enumerate(methods):
    ax.annotate(m, (gemma_vals[i], mini_vals[i]),
                xytext=(7, 4), textcoords='offset points',
                fontsize=8, alpha=0.85)
lo = min(min(gemma_vals), min(mini_vals)) - 0.05
hi = max(max(gemma_vals), max(mini_vals)) + 0.05
ax.plot([lo, hi], [lo, hi], '--', color='gray', alpha=0.5, label='y = x')
ax.set_xlabel('Gemma 26B (local sLLM)', fontsize=12)
ax.set_ylabel('GPT-5.4-mini (frontier API)', fontsize=12)
ax.set_title(f'Judge Agreement on Matrix Scores\nSpearman rho = {rho:.3f}  (p = {p:.4f})',
             fontsize=13, pad=15)
ax.grid(alpha=0.3)
ax.legend(loc='lower right')
ax.set_aspect('equal')
plt.tight_layout()
plt.savefig(OUT_DIR / "05_judge_agreement.png", dpi=150, bbox_inches='tight')
plt.close()
print("✓ 05_judge_agreement.png")


print()
print(f"━━ 5개 차트 저장됨: {OUT_DIR}")
print(subprocess.check_output(["ls", "-la", str(OUT_DIR)]).decode())
