"""scripts/build_bm25.py — Build contextualized BM25 indexes for EN/KO leaves.

Each leaf's BM25 text is `contexts[leaf_id] + "\n\n" + leaf_body` so the lexical
inventory matches Stage B's contextual dense inventory. Tokenization:
whitespace+lowercase for EN, kiwipiepy morphemes for KO.

Outputs chroma_db/bm25_{lang}.pkl with {bm25, leaf_ids, texts}.

Usage:
  uv run python scripts/build_bm25.py            # smoke (EN, 50 leaves)
  uv run python scripts/build_bm25.py --run      # full EN+KO + save
"""
import argparse
import json
import pickle
import re
import sys
from pathlib import Path

from rank_bm25 import BM25Okapi

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "chroma_db"
LANGS = ["en", "ko"]


# ─── tokenizers ────────────────────────────────────────────────────────────
_EN_TOKEN_RE = re.compile(r"[a-z0-9]+")

def tokenize_en(text: str) -> list[str]:
    return _EN_TOKEN_RE.findall(text.lower())


_KIWI = None

def tokenize_ko(text: str) -> list[str]:
    global _KIWI
    if _KIWI is None:
        from kiwipiepy import Kiwi
        _KIWI = Kiwi()
    return [tok.form for tok in _KIWI.tokenize(text)]


TOKENIZERS = {"en": tokenize_en, "ko": tokenize_ko}


# ─── corpus load ───────────────────────────────────────────────────────────
def load_corpus(lang: str) -> tuple[list[str], list[str]]:
    leaves = json.loads((DB / f"hier_nodes_by_leaf_{lang}.json").read_text("utf-8"))
    contexts = json.loads((DB / f"contexts_nietzsche_{lang}.json").read_text("utf-8"))
    if len(leaves) != len(contexts):
        print(f"[warn] leaves={len(leaves)} != contexts={len(contexts)}",
              file=sys.stderr)

    leaf_ids, texts = [], []
    for leaf_id, info in leaves.items():
        body = info.get("leaf", info) if isinstance(info, dict) else info
        ctx = contexts.get(leaf_id, "")
        joined = f"{ctx}\n\n{body}" if ctx else body
        leaf_ids.append(leaf_id)
        texts.append(joined)
    return leaf_ids, texts


def build_index(lang: str, texts: list[str]):
    tok = TOKENIZERS[lang]
    corpus = [tok(t) for t in texts]
    return BM25Okapi(corpus), corpus


# ─── smoke ─────────────────────────────────────────────────────────────────
def smoke() -> bool:
    """EN-only with 50 leaves; assert 'thirty' lands in top-5 for a known query."""
    leaf_ids, texts = load_corpus("en")
    n = min(50, len(leaf_ids))
    leaf_ids, texts = leaf_ids[:n], texts[:n]
    bm25, _ = build_index("en", texts)
    print(f"[smoke] built EN index with {n} leaves")

    query = "thirty years old Zarathustra mountain"
    scores = bm25.get_scores(tokenize_en(query))
    top = sorted(enumerate(scores), key=lambda x: -x[1])[:5]
    print(f"[smoke] query: {query!r}")
    for rank, (idx, score) in enumerate(top):
        snippet = texts[idx][:80].replace("\n", " ")
        print(f"  rank {rank}  score={score:.3f}  {leaf_ids[idx]}  '{snippet}...'")

    found = any("thirty" in texts[idx].lower() for idx, _ in top)
    print("[smoke] ✓ PASS" if found else "[smoke] ✗ FAIL — 'thirty' missing in top-5")
    return found


# ─── full build ────────────────────────────────────────────────────────────
def run():
    for lang in LANGS:
        print(f"━━ {lang} ━━")
        leaf_ids, texts = load_corpus(lang)
        bm25, corpus = build_index(lang, texts)
        out = DB / f"bm25_{lang}.pkl"
        with out.open("wb") as f:
            pickle.dump({"bm25": bm25, "leaf_ids": leaf_ids, "texts": texts}, f)
        token_counts = [len(c) for c in corpus]
        avg = sum(token_counts) / len(token_counts)
        print(f"  leaves={len(leaf_ids)}  avg_tokens={avg:.1f}  "
              f"min={min(token_counts)}  max={max(token_counts)}")
        print(f"  ✓ saved → {out.relative_to(ROOT)}  ({out.stat().st_size:,} bytes)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true",
                        help="full EN+KO build + save (default: smoke EN only)")
    args = parser.parse_args()
    if args.run:
        run()
    else:
        if not smoke():
            raise SystemExit(1)
        print("\n[smoke] OK — rerun with --run for full build")


if __name__ == "__main__":
    main()
