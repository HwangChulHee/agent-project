"""차라투스트라 베이스라인 인덱싱 (의미 단위 청킹, bge-m3, 언어별 collection)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import re
from pathlib import Path
import statistics
import chromadb
from rag.embed_api import SentenceTransformer

DB_DIR = Path("chroma_db")
EMBED_MODEL = "BAAI/bge-m3"
BGE_MAX_TOKENS = 8192   # bge-m3 max sequence length

SOURCES = {
    "nietzsche_baseline_en": ("data/nietzsche_md/zarathustra_en.md", "en"),
    "nietzsche_baseline_ko": ("data/nietzsche_md/zarathustra_ko.md", "ko"),
}


def chunk_by_semantic_units(text: str):
    """
    헤더 기반 의미 단위 청킹:
      # Part           → 구조 헤더 (청크 아님)
      ## Chapter       → 1 청크 (해당 챕터의 본문)
      ## Prologue      → 자식 ### Section만 청크 (Prologue 자체는 청크 아님)
      ### Section      → 1 청크

    반환: [{"id": ..., "text": ..., "header": ..., "kind": "chapter"|"section"}]
    """
    lines = text.splitlines()
    chunks = []
    current = {"header": None, "kind": None, "buffer": []}
    parent_chapter = None  # 가장 가까운 ## 헤더 (Prologue 같은 경우 추적용)

    def flush(min_chars=20):
        nonlocal current
        if current["header"] is None:
            current = {"header": None, "kind": None, "buffer": []}
            return
        body = "\n".join(current["buffer"]).strip()
        if len(body) < min_chars:
            current = {"header": None, "kind": None, "buffer": []}
            return
        # 청크 텍스트 = 헤더 + 본문 (검색 시 헤더 키워드 효과)
        full_text = f"{current['header']}\n\n{body}"
        chunks.append({
            "header": current["header"],
            "kind": current["kind"],
            "text": full_text,
        })
        current = {"header": None, "kind": None, "buffer": []}

    for line in lines:
        m_h1 = re.match(r"^#\s+(.+)$", line)
        m_h2 = re.match(r"^##\s+(.+)$", line)
        m_h3 = re.match(r"^###\s+(.+)$", line)

        if m_h1:
            flush()  # Part 진입 시 직전 챕터/섹션 마감
            parent_chapter = None
            continue

        if m_h2:
            flush()
            parent_chapter = line.strip()
            # Prologue/preamble 종류 헤더는 청크 만들지 않고 자식 ### 만 청크
            if re.search(r"prologue|머리말|서문|preamble", line, re.IGNORECASE):
                # 다음에 ###가 나오면 그것만 청크. 본문 직접 X
                current = {"header": None, "kind": None, "buffer": []}
            else:
                # 일반 챕터 — 헤더부터 다음 헤더까지 모아서 1 청크
                current = {"header": line.strip(), "kind": "chapter", "buffer": []}
            continue

        if m_h3:
            flush()
            current = {"header": line.strip(), "kind": "section", "buffer": []}
            continue

        # 본문 라인 — 현재 청크에 누적
        if current["header"] is not None:
            current["buffer"].append(line)

    flush()
    return chunks


def report_stats(chunks, tokenizer, lang):
    """청크별 크기/토큰 통계 + 한계 초과 점검."""
    char_lens = [len(c["text"]) for c in chunks]
    token_lens = [len(tokenizer.encode(c["text"], add_special_tokens=False))
                  for c in chunks]

    def pct(xs, p):
        s = sorted(xs)
        idx = int(len(s) * p / 100)
        return s[min(idx, len(s) - 1)]

    print(f"  [{lang}] chunks={len(chunks)}  "
          f"chapter={sum(1 for c in chunks if c['kind']=='chapter')}  "
          f"section={sum(1 for c in chunks if c['kind']=='section')}")
    print(f"    chars  min={min(char_lens)}  mean={statistics.mean(char_lens):.0f}  "
          f"p50={pct(char_lens,50)}  p95={pct(char_lens,95)}  max={max(char_lens)}")
    print(f"    tokens min={min(token_lens)}  mean={statistics.mean(token_lens):.0f}  "
          f"p50={pct(token_lens,50)}  p95={pct(token_lens,95)}  max={max(token_lens)}")

    over = [(i, c, t) for i, (c, t) in enumerate(zip(chunks, token_lens))
            if t > BGE_MAX_TOKENS]
    if over:
        print(f"    ⚠ {len(over)} chunks exceed bge-m3 max_seq={BGE_MAX_TOKENS} (will be truncated):")
        for i, c, t in over[:5]:
            print(f"      [{i}] tokens={t}  {c['header']!r}")
    else:
        print(f"    ✓ all under {BGE_MAX_TOKENS} tokens")
    return token_lens


def main():
    print(f"Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    dim = model.get_sentence_embedding_dimension()
    tokenizer = model.tokenizer
    print(f"Embedding dim: {dim}\n")

    client = chromadb.PersistentClient(path=str(DB_DIR))

    for col_name, (src_path, lang) in SOURCES.items():
        src = Path(src_path)
        if not src.exists():
            print(f"  SKIP: {src} 없음")
            continue
        print(f"━━ {col_name}  ({src}) ━━")
        text = src.read_text(encoding="utf-8")
        chunks = chunk_by_semantic_units(text)

        report_stats(chunks, tokenizer, lang)

        # collection 재생성
        existing = [c.name for c in client.list_collections()]
        if col_name in existing:
            client.delete_collection(col_name)
        col = client.create_collection(col_name, metadata={"hnsw:space": "cosine"})

        # 임베딩 + 적재
        doc_id = src.stem
        texts = [c["text"] for c in chunks]
        ids = [f"{doc_id}_{i:04d}" for i in range(len(chunks))]
        metadatas = [
            {"source": doc_id, "doc_id": doc_id, "lang": lang,
             "chunk_index": i, "kind": c["kind"], "header": c["header"]}
            for i, c in enumerate(chunks)
        ]
        embeddings = model.encode(
            texts, batch_size=16, show_progress_bar=True, convert_to_numpy=True
        ).tolist()
        col.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        print(f"  Indexed → {col_name}\n")

    print("=" * 60)
    for c in client.list_collections():
        if c.name.startswith("nietzsche_baseline"):
            print(f"  {c.name:30s} count={c.count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
