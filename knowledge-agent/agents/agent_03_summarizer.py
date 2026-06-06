import re
import json
import argparse
from dotenv import load_dotenv
from openai import OpenAI
from agents.prompts.summarizer import SYSTEM

load_dotenv()  # .env에서 OPENAI_API_KEY 로드

MODEL = "gpt-4o-mini"
SEGMENTS_PATH = "data/parsed/2210.03629/2210.03629_02.segments.json"
OUT_PATH = "data/parsed/2210.03629/2210.03629_03.summaries.json"
SMOKE_INDICES = [1, 8, 13]  # ABSTRACT(짧음) / 4장(제일 김) / ETHICS(잡섹션)

client = OpenAI()


def summarize_one(seg: dict) -> str:
    user = f"## {seg['heading']}\n\n{seg['text']}"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


def _num_count(s: str) -> int:
    return len(re.findall(r"\d+(?:\.\d+)?", s))


def _has_hangul(s: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", s))


def run(full: bool):
    with open(SEGMENTS_PATH, encoding="utf-8") as f:
        segs = json.load(f)

    if not full:
        print("=== SMOKE (3 세그먼트) ===\n")
        ok = True
        for i in SMOKE_INDICES:
            seg = segs[i]
            summ = summarize_one(seg)
            empty = len(summ) == 0
            compressed = len(summ) < len(seg["text"])
            english = not _has_hangul(summ)
            passed = (not empty) and compressed and english
            ok = ok and passed
            print(f"[{i}] {seg['heading'][:40]}  {'PASS' if passed else 'FAIL'}")
            print(f"    원문 {len(seg['text'])}자(숫자 {_num_count(seg['text'])}개) "
                  f"→ 요약 {len(summ)}자(숫자 {_num_count(summ)}개)")
            print(f"    {summ}\n")
        print("=== " + ("SMOKE PASS — `--run`으로 전체 실행" if ok else "SMOKE FAIL — 위 확인") + " ===")
        return

    print(f"=== FULL ({len(segs)} 세그먼트) ===")
    out = []
    for i, seg in enumerate(segs):
        summ = summarize_one(seg)
        out.append({"heading": seg["heading"], "original_len": len(seg["text"]), "summary": summ})
        print(f"  [{i:2}] {seg['heading'][:40]:42} {len(seg['text']):5}자 → {len(summ):5}자")
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="전체 실행 (없으면 스모크)")
    run(ap.parse_args().run)
