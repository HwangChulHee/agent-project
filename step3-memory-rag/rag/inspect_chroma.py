"""rag/inspect_chroma.py — list chroma collections and sample chunk docs."""
from pathlib import Path
import chromadb

ROOT = Path(__file__).resolve().parent.parent

# Most common paths — edit if your chroma_db lives elsewhere.
CANDIDATES = [
    ROOT / "chroma_db",
    ROOT / "data" / "chroma_db",
    ROOT / "rag" / "chroma_db",
    ROOT / "data" / "chroma",
]


def main():
    path = next((p for p in CANDIDATES if p.exists()), None)
    if path is None:
        print("[error] Chroma DB not found. Tried:")
        for p in CANDIDATES:
            print(f"  - {p}")
        print("[hint] Edit CANDIDATES at the top of this file with the correct path.")
        return

    print(f"[chroma] path: {path}\n")
    client = chromadb.PersistentClient(path=str(path))
    collections = client.list_collections()
    print(f"[chroma] {len(collections)} collections:\n")

    for c in collections:
        n = c.count()
        peek = c.peek(limit=1)
        sample_id = peek["ids"][0] if peek["ids"] else "<empty>"
        sample_doc = peek["documents"][0] if peek["documents"] else "<no doc>"
        sample_meta = peek["metadatas"][0] if peek["metadatas"] else None
        if isinstance(sample_doc, str) and len(sample_doc) > 120:
            sample_doc = sample_doc[:120] + "..."
        print(f"  - {c.name}  ({n} docs)")
        print(f"      sample id:   {sample_id!r}")
        print(f"      sample doc:  {sample_doc!r}")
        print(f"      sample meta: {sample_meta}\n")


if __name__ == "__main__":
    main()
