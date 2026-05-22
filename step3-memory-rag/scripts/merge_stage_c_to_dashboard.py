"""scripts/merge_stage_c_to_dashboard.py — merge StageC results into dashboard JSON.

Reads chroma_db/judge_results_nietzsche.json (which now has StageC-EN/StageC-KO),
converts to the dashboard schema, merges into data/eval_dashboard.json by adding
stages['StageC-{LANG}'] to each matching query. Other stages untouched.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUDGE_PATH = ROOT / "chroma_db" / "judge_results_nietzsche.json"
DASHBOARD_PATH = ROOT / "data" / "eval_dashboard.json"


def convert_results(stage_results: dict) -> dict[int, dict]:
    """{q_idx_str: {results: [...]}} → {q_idx_int: {top1_score, topk_avg, results}}."""
    out = {}
    for q_idx_str, q_data in stage_results.items():
        q_idx = int(q_idx_str)
        results = sorted(q_data["results"], key=lambda r: r["rank"])
        # Convert keys: chunk→leaf. Keep parent/header from stage_c output.
        converted = [
            {
                "rank": r["rank"],
                "score": r["score"],
                "reason": r["reason"],
                "leaf": r["chunk"],
                "parent": r.get("parent"),
                "header": r.get("header"),
            }
            for r in results
        ]
        scores = [r["score"] for r in converted if r["score"] is not None]
        top1 = converted[0]["score"] if converted and converted[0]["score"] is not None else None
        topk = sum(scores) / len(scores) if scores else None
        out[q_idx] = {
            "top1_score": top1,
            "topk_avg": topk,
            "results": converted,
        }
    return out


def main():
    judge = json.loads(JUDGE_PATH.read_text("utf-8"))
    dash = json.loads(DASHBOARD_PATH.read_text("utf-8"))

    stage_c_en = convert_results(judge["StageC-EN"])
    stage_c_ko = convert_results(judge["StageC-KO"])

    # Merge into dash['queries'] by query idx; queries[i]['idx'] is the canonical id.
    added_en = added_ko = 0
    for q in dash["queries"]:
        q_idx = q["idx"]
        lang = q["lang"]
        if lang == "en" and q_idx in stage_c_en:
            q["stages"]["StageC-EN"] = stage_c_en[q_idx]
            added_en += 1
        elif lang == "ko" and q_idx in stage_c_ko:
            q["stages"]["StageC-KO"] = stage_c_ko[q_idx]
            added_ko += 1

    # Add StageC entries to collections list (for dashboard column rendering).
    existing_labels = {c["label"] for c in dash["collections"]}
    for label, lang in [("StageC-EN", "en"), ("StageC-KO", "ko")]:
        if label not in existing_labels:
            dash["collections"].append({"label": label, "lang": lang})

    DASHBOARD_PATH.write_text(json.dumps(dash, ensure_ascii=False, indent=2), "utf-8")
    print(f"[merge] StageC-EN: {added_en} queries added")
    print(f"[merge] StageC-KO: {added_ko} queries added")
    print(f"[merge] collections now: {[c['label'] for c in dash['collections']]}")
    print(f"[output] {DASHBOARD_PATH}  size={DASHBOARD_PATH.stat().st_size:,} chars")

    # Compare with other stages for sanity check.
    print("\n━━ comparison: avg topk_avg across stages ━━")
    for label in ["Baseline-EN", "StageA-EN", "StageB-EN", "StageC-EN",
                  "Baseline-KO", "StageA-KO", "StageB-KO", "StageC-KO"]:
        topk_vals = [q["stages"][label]["topk_avg"] for q in dash["queries"]
                     if label in q.get("stages", {}) and q["stages"][label]["topk_avg"] is not None]
        top1_vals = [q["stages"][label]["top1_score"] for q in dash["queries"]
                     if label in q.get("stages", {}) and q["stages"][label]["top1_score"] is not None]
        if topk_vals:
            print(f"  {label:14s}  topk_avg={sum(topk_vals)/len(topk_vals):.2f}  "
                  f"top1={sum(top1_vals)/len(top1_vals):.2f}  n={len(topk_vals)}")


if __name__ == "__main__":
    main()
