"""eval/inspect_data.py — confirm schema of data/eval_dashboard.json.

Output: top-level structure + first-entry pretty-print sample (truncated).
"""
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_dashboard.json"
SAMPLE_CHARS = 1200      # first-entry pretty-print cap
MAX_DEPTH = 5            # recursion cap in describe()
MAX_KEYS_SHOWN = 10      # truncate long key lists


def describe(obj, depth=0):
    indent = "  " * depth
    if depth > MAX_DEPTH:
        return f"{indent}... (depth cap)"

    if isinstance(obj, dict):
        keys = list(obj.keys())
        head = f"{indent}dict (keys={len(keys)}): {keys[:MAX_KEYS_SHOWN]}"
        if len(keys) > MAX_KEYS_SHOWN:
            head += f" + {len(keys) - MAX_KEYS_SHOWN} more"
        if not keys:
            return head
        first = keys[0]
        return "\n".join([
            head,
            f"{indent}  └ first key '{first}':",
            describe(obj[first], depth + 2),
        ])

    if isinstance(obj, list):
        head = f"{indent}list (len={len(obj)})"
        if not obj:
            return head
        return "\n".join([
            head,
            f"{indent}  └ [0]:",
            describe(obj[0], depth + 2),
        ])

    if isinstance(obj, str):
        preview = obj if len(obj) <= 80 else obj[:80] + "..."
        return f"{indent}str (len={len(obj)}): {preview!r}"

    return f"{indent}{type(obj).__name__}: {obj!r}"


def main():
    raw = DATA_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    print(f"[File] {DATA_PATH}")
    print(f"       size={len(raw):,} chars  type={type(data).__name__}")
    print()

    print("[Top-level structure]")
    print(describe(data))
    print()

    # Pretty-print first entry, truncated.
    print(f"[First-entry sample (max {SAMPLE_CHARS} chars)]")
    if isinstance(data, dict):
        first_key = next(iter(data))
        sample = data[first_key]
        print(f"key='{first_key}':")
    elif isinstance(data, list):
        sample = data[0] if data else None
        print("[0]:")
    else:
        sample = data

    text = json.dumps(sample, ensure_ascii=False, indent=2)
    if len(text) > SAMPLE_CHARS:
        text = text[:SAMPLE_CHARS] + f"\n... (truncated, full length={len(text):,} chars)"
    print(text)


if __name__ == "__main__":
    main()
