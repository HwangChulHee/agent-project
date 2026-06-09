"""04 extract: parsed → 내용(defines/uses/task/problem/domain)."""
import argparse, json, sys
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config, prompts

client = OpenAI()


def extract_one(text: str) -> dict:
    resp = client.chat.completions.create(
        model=config.MODEL,
        messages=[
            {"role": "system", "content": prompts.EXTRACT_SYSTEM},
            {"role": "user", "content": prompts.EXTRACT_USER.format(text=text)},
        ],
        response_format={"type": "json_schema", "json_schema": prompts.EXTRACT_SCHEMA},
    )
    return json.loads(resp.choices[0].message.content)


def load_text(pid: str) -> str:
    return json.loads((config.OUT_DIR / f"{pid}.parsed.json").read_text())["text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    ids = config.PAPER_IDS if args.run else config.PAPER_IDS[:2]
    n_new = n_skip = 0
    for pid in ids:
        out = config.OUT_DIR / f"{pid}.concepts.json"
        if args.run and out.exists() and not args.force:
            n_skip += 1; print(f"{pid}: skip"); continue
        c = extract_one(load_text(pid))
        if args.run:
            out.write_text(json.dumps(c, ensure_ascii=False, indent=2)); n_new += 1
        print(f"{pid}: [{c['paper_type']}] defines={[m['name'] for m in c['defines']]} domain={c['domain']}")
    if args.run:
        print(f"\n신규 {n_new}, skip {n_skip}")


if __name__ == "__main__":
    main()
