"""
한국어 번역 후처리: translation_glossary.json의 치환 사전 적용.
- 원본은 .before_postprocess 백업
- --dry-run 으로 미리 확인 가능
"""
import argparse
import json
import shutil
from pathlib import Path

TARGET = Path("data/nietzsche_md/zarathustra_ko.md")
GLOSSARY = Path("data/nietzsche/translation_glossary.json")
BACKUP_SUFFIX = ".before_postprocess"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="치환하지 않고 어떤 부분이 바뀔지만 출력")
    args = ap.parse_args()

    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    text = TARGET.read_text(encoding="utf-8")
    original = text

    print(f"Glossary entries: {len(glossary['replacements'])}")
    print(f"Target file: {TARGET} ({len(text):,} chars)\n")

    total_hits = 0
    for entry in glossary["replacements"]:
        frm, to, reason = entry["from"], entry["to"], entry["reason"]
        count = text.count(frm)
        if count == 0:
            print(f"  - {frm!r} → {to!r} : 0 hits ({reason})")
            continue
        print(f"  ✓ {frm!r} → {to!r} : {count} hits ({reason})")

        if args.dry_run:
            # 첫 hit 주변 80자 컨텍스트 보여주기
            idx = text.find(frm)
            ctx_start = max(0, idx - 30)
            ctx_end = min(len(text), idx + len(frm) + 30)
            preview = text[ctx_start:ctx_end].replace("\n", "\\n")
            print(f"    preview: ...{preview}...")
        else:
            text = text.replace(frm, to)
        total_hits += count

    print(f"\nTotal replacements: {total_hits}")

    if args.dry_run:
        print("\n[DRY RUN] No file changed.")
        return

    if text == original:
        print("No changes needed.")
        return

    backup_path = TARGET.with_suffix(TARGET.suffix + BACKUP_SUFFIX)
    if not backup_path.exists():
        shutil.copy(TARGET, backup_path)
        print(f"Backup created: {backup_path}")
    TARGET.write_text(text, encoding="utf-8")
    print(f"Updated: {TARGET} ({len(text):,} chars)")


if __name__ == "__main__":
    main()
