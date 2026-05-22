"""eval/build_dashboard.py — augment eval JSON with borrow map + stats, inject into HTML."""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "eval_dashboard.json"
TEMPLATE_PATH = ROOT / "eval" / "dashboard.template.html"
OUTPUT_PATH = ROOT / "eval" / "dashboard.html"
PLACEHOLDER = "/* __DATA_PLACEHOLDER__ */"

STAGES = ["Baseline", "StageA", "StageB", "StageC"]
LANGS = ["EN", "KO"]


def build_borrow_map(queries):
    borrow = {}
    for q in queries:
        lang = q["lang"]
        for stage in q["stages"].values():
            for r in stage.get("results", []):
                if r.get("parent") and r.get("leaf"):
                    key = (lang, r["leaf"])
                    if key not in borrow:
                        borrow[key] = {"parent": r["parent"], "header": r.get("header")}
    return borrow


def augment(queries, borrow):
    hits = missing = 0
    for q in queries:
        lang = q["lang"]
        for stage in q["stages"].values():
            for r in stage.get("results", []):
                if r.get("parent") is None:
                    missing += 1
                    key = (lang, r.get("leaf", ""))
                    if key in borrow:
                        r["parent_borrowed"] = borrow[key]["parent"]
                        r["header_borrowed"] = borrow[key]["header"]
                        hits += 1
    return hits, missing


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def compute_stats(queries):
    """Return {overall: [{label, lang, top1, topk, n}], by_category: {cat: [...]}}.
    Stages keyed as '{Stage}-{LANG}'. n = number of queries that contributed.
    """
    overall_buckets = defaultdict(lambda: {"top1": [], "topk": []})
    cat_buckets = defaultdict(lambda: defaultdict(lambda: {"top1": [], "topk": []}))

    for q in queries:
        lang = q["lang"].upper()
        cat = q["category"]
        for stage_name, stage in q["stages"].items():
            key = (stage_name, lang)
            overall_buckets[key]["top1"].append(stage.get("top1_score"))
            overall_buckets[key]["topk"].append(stage.get("topk_avg"))
            cat_buckets[cat][key]["top1"].append(stage.get("top1_score"))
            cat_buckets[cat][key]["topk"].append(stage.get("topk_avg"))

    # Fixed row order: Baseline-EN, StageA-EN, StageB-EN, Baseline-KO, ...
    rows = [(f"{s}-{l}", l) for l in LANGS for s in STAGES]

    overall = []
    for label, lang in rows:
        key = (label.replace(f"-{lang}", ""), lang)  # ('Baseline','EN') etc.
        # Note: stage_name in queries is already 'Baseline-EN' style → reuse directly
        full_key = (label, lang)
        b = overall_buckets.get(full_key, {"top1": [], "topk": []})
        n = sum(1 for x in b["top1"] if x is not None)
        overall.append({
            "label": label, "lang": lang,
            "top1": _mean(b["top1"]), "topk": _mean(b["topk"]), "n": n,
        })

    by_category = {}
    for cat in sorted(cat_buckets.keys()):
        rows_cat = []
        for label, lang in rows:
            full_key = (label, lang)
            b = cat_buckets[cat].get(full_key, {"top1": [], "topk": []})
            n = sum(1 for x in b["top1"] if x is not None)
            rows_cat.append({
                "label": label, "lang": lang,
                "top1": _mean(b["top1"]), "topk": _mean(b["topk"]), "n": n,
            })
        by_category[cat] = rows_cat

    return {"overall": overall, "by_category": by_category}


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    queries = data["queries"]

    borrow = build_borrow_map(queries)
    hits, missing = augment(queries, borrow)
    pct = (100 * hits / missing) if missing else 0
    print(f"[borrow] map size={len(borrow)} unique leaves")
    print(f"[borrow] coverage: {hits}/{missing} parent-missing results filled ({pct:.1f}%)")

    data["stats"] = compute_stats(queries)
    print(f"[stats] overall rows={len(data['stats']['overall'])} "
          f"categories={list(data['stats']['by_category'].keys())}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise RuntimeError(f"Placeholder {PLACEHOLDER!r} not found in template")

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    output = template.replace(PLACEHOLDER, payload)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"[output] {OUTPUT_PATH}  size={len(output):,} chars")


if __name__ == "__main__":
    main()
