"""05 relate: builds_on + applies → {pid}.relations.json."""
import argparse, json, sys
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config, prompts

client = OpenAI()


def relate_one(concepts: dict, text: str) -> dict:
    defines = ", ".join(m["name"] for m in concepts.get("defines", [])) or "(none)"
    resp = client.chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "system", "content": prompts.RELATE_SYSTEM},
            {"role": "user", "content": prompts.RELATE_USER.format(
                defines=defines, domain=concepts.get("domain", "general"),
                problem=concepts.get("problem", ""), text=text)},
        ],
        response_format={"type": "json_schema", "json_schema": prompts.RELATE_SCHEMA},
    )
    return json.loads(resp.choices[0].message.content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ids = config.PAPER_IDS if args.run else config.PAPER_IDS[:2]
    n_new = n_skip = 0
    for pid in ids:
        out = config.OUT_DIR / f"{pid}.relations.json"
        if args.run and out.exists() and not args.force:
            n_skip += 1; print(f"{pid}: skip"); continue
        concepts = json.loads((config.OUT_DIR / f"{pid}.concepts.json").read_text())
        text = json.loads((config.OUT_DIR / f"{pid}.parsed.json").read_text())["text"]
        r = relate_one(concepts, text)
        if args.run:
            out.write_text(json.dumps(r, ensure_ascii=False, indent=2)); n_new += 1
        print(f"{pid}: builds_on={r['builds_on']}")
    if args.run:
        print(f"\n신규 {n_new}, skip {n_skip}")


if __name__ == "__main__":
    main()
