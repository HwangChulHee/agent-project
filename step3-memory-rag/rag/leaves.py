"""Stage A/B 공통: Wikipedia .md → section parents → sentence leaves."""
from pathlib import Path
from llama_index.core import Document
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

LEAF_CHUNK_SIZE = 256
LEAF_OVERLAP = 32
MIN_LEAF_CHARS = 80


def build_leaves(src_dir: Path):
    """동일 입력에 동일 leaf 시퀀스를 보장. doc_id 정렬 NOT 적용 (호출자가 필요시 정렬)."""
    md_files = sorted(src_dir.glob("*.md"))
    docs = [
        Document(text=f.read_text(encoding="utf-8"), metadata={"doc_id": f.stem})
        for f in md_files
    ]
    doc_texts = {d.metadata["doc_id"]: d.text for d in docs}

    md_parser = MarkdownNodeParser()
    parents = md_parser.get_nodes_from_documents(docs)
    parent_texts = {
        p.node_id: {"text": p.text, "doc_id": p.metadata.get("doc_id", "")}
        for p in parents
    }

    splitter = SentenceSplitter(chunk_size=LEAF_CHUNK_SIZE, chunk_overlap=LEAF_OVERLAP)
    leaves = []
    for p in parents:
        for lt in splitter.split_text(p.text):
            if len(lt.strip()) < MIN_LEAF_CHARS:
                continue
            leaves.append({
                "leaf_id": f"leaf_{len(leaves):05d}",
                "text": lt,
                "doc_id": p.metadata.get("doc_id", ""),
                "parent_id": p.node_id,
            })
    return leaves, parent_texts, doc_texts
