"""기존 sidecar (parent_id → text) 를 leaf_id → parent_text 매핑으로 변환.
build_leaves 재호출로 leaf와 parent의 관계 확보."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json, shutil, tempfile
from pathlib import Path
from rag.leaves import build_leaves

SOURCES = {
    "data/nietzsche_md/zarathustra_en.md": "chroma_db/hier_nodes_by_leaf_en.json",
    "data/nietzsche_md/zarathustra_ko.md": "chroma_db/hier_nodes_by_leaf_ko.json",
}


def main():
    for md_path, out_path in SOURCES.items():
        src = Path(md_path)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            shutil.copy(src, tmpdir / src.name)
            leaves, parent_texts, _ = build_leaves(tmpdir)

        # leaf_id → parent_text 매핑
        mapping = {}
        for leaf in leaves:
            pid = leaf["parent_id"]
            mapping[leaf["leaf_id"]] = parent_texts.get(pid, {}).get("text", "")

        Path(out_path).write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{out_path}: {len(mapping)} entries")


if __name__ == "__main__":
    main()
