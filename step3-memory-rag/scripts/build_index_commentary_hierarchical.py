"""해설 자료 Stage A 인덱싱 (build_leaves 재사용).

흐름:
  1. data/commentary/raw/*.md 27편 읽기
  2. 메타 섹션(References, Bibliography 등) 제거 → 정제된 md를 임시 dir에 복사
  3. build_leaves() 호출 → leaf + parent
  4. chromadb 적재 + parent sidecar 저장

전제: BGE-M3 서버 (8003) 가동 중
사용: uv run python scripts/build_index_commentary_hierarchical.py
"""
import json
import re
import shutil
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb
from rag.embed_api import SentenceTransformer
from rag.leaves import build_leaves

# chunk_commentary.py의 메타 섹션 필터 재사용
sys.path.insert(0, str(Path(__file__).resolve().parent))
from chunk_commentary import (
    clean_text,
    is_meta_section,
    is_bib_break,
)

RAW_DIR = Path("data/commentary/raw")
DB_DIR = Path("chroma_db")
COLLECTION = "commentary_hierarchical_en"
EMBED_MODEL = "BAAI/bge-m3"


def _strip_h1_pages(md_text: str) -> str:
    """페이지 헤더 H1(Internet Encyclopedia of Philosophy 등) 제거.
    H1 본문은 보통 alphabet nav, 페이지 푸터 — 모두 노이즈.
    실제 본문 시작은 두 번째 H1 또는 첫 H2부터.
    """
    lines = md_text.split("\n")
    h1_count = 0
    body_start = 0
    for i, ln in enumerate(lines):
        if re.match(r"^# [^#]", ln):
            h1_count += 1
            if h1_count >= 2:
                body_start = i
                break
        elif re.match(r"^## ", ln) and h1_count >= 1:
            body_start = i
            break
    if body_start > 0:
        return "\n".join(lines[body_start:])
    return md_text


def _strip_h3_meta(md_text: str) -> str:
    """H3 메타 섹션 제거. 'Table of Contents' 같은 헤더 만나면 다음 H2까지 통째 제거.
    (ToC 뒤에 헤더 없는 참고문헌 평문이 길게 이어지는 경우 대비)
    """
    lines = md_text.split("\n")
    out = []
    skip_until_h2 = False
    for ln in lines:
        if skip_until_h2:
            if re.match(r"^## ", ln):
                skip_until_h2 = False
                out.append(ln)
            continue
        m = re.match(r"^(### .+)$", ln)
        if m and is_meta_section(m.group(1)):
            skip_until_h2 = True
            continue
        out.append(ln)
    return "\n".join(out)


def strip_meta_sections(md_text: str) -> str:
    """H1 페이지 노이즈 → H2 메타·Bibliography → H3 메타 순으로 제거."""
    md_text = _strip_h1_pages(md_text)

    # H2 단위
    parts = re.split(r"^(## .+)$", md_text, flags=re.M)
    # parts[0]은 첫 H2 이전의 본문 (intro 부분). 여기에도 H3 메타 필터 적용
    out = [_strip_h3_meta(parts[0])] if parts and parts[0].strip() else []
    bib_reached = False
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if bib_reached:
            continue
        if is_bib_break(header):
            bib_reached = True
            continue
        if is_meta_section(header):
            continue
        out.append(header)
        out.append(_strip_h3_meta(body))

    return "\n".join(out).strip()


def prepare_cleaned_dir(out_dir: Path):
    """raw md 27편을 정제(메타 제거 + HTML 엔티티 정리)해서 임시 디렉토리에 저장."""
    count = 0
    for src in RAW_DIR.glob("*.md"):
        text = src.read_text(encoding="utf-8")
        text = clean_text(text)
        text = strip_meta_sections(text)
        if len(text) < 200:
            print(f"  ⚠ SKIP {src.name} (정제 후 너무 짧음: {len(text)}자)")
            continue
        (out_dir / src.name).write_text(text, encoding="utf-8")
        count += 1
    return count


def report_stats(leaves, tokenizer):
    char_lens = [len(l["text"]) for l in leaves]
    token_lens = [len(tokenizer.encode(l["text"], add_special_tokens=False))
                  for l in leaves]

    def pct(xs, p):
        s = sorted(xs)
        return s[min(int(len(s) * p / 100), len(s) - 1)]

    print(f"  leaves={len(leaves)}")
    print(f"    chars  min={min(char_lens)}  mean={statistics.mean(char_lens):.0f}  "
          f"p50={pct(char_lens, 50)}  p95={pct(char_lens, 95)}  max={max(char_lens)}")
    print(f"    tokens min={min(token_lens)}  mean={statistics.mean(token_lens):.0f}  "
          f"p50={pct(token_lens, 50)}  p95={pct(token_lens, 95)}  max={max(token_lens)}")


def main():
    print(f"임베딩 모델: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)
    tokenizer = model.tokenizer
    print(f"  임베딩 차원: {model.get_sentence_embedding_dimension()}\n")

    # 1) 정제된 md를 임시 디렉토리로
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        n_files = prepare_cleaned_dir(tmpdir)
        print(f"정제된 파일: {n_files}편 (메타 섹션 제거 + HTML 엔티티 정리)\n")

        # 2) build_leaves 호출
        leaves, parent_texts, _ = build_leaves(tmpdir)

        print(f"━━ {COLLECTION} ━━")
        print(f"  Section parents: {len(parent_texts)}")
        report_stats(leaves, tokenizer)

        # 3) chromadb 적재
        client = chromadb.PersistentClient(path=str(DB_DIR))
        if COLLECTION in [c.name for c in client.list_collections()]:
            client.delete_collection(COLLECTION)
        col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

        texts = [l["text"] for l in leaves]
        ids = [l["leaf_id"] for l in leaves]
        metadatas = [
            {"doc_id": l["doc_id"], "parent_id": l["parent_id"], "lang": "en",
             "source_type": "commentary"}
            for l in leaves
        ]
        embeddings = model.encode(
            texts, batch_size=16, show_progress_bar=True, convert_to_numpy=True
        ).tolist()

        # 분할 적재
        BATCH = 500
        for i in range(0, len(leaves), BATCH):
            end = min(i + BATCH, len(leaves))
            col.add(
                ids=ids[i:end],
                documents=texts[i:end],
                embeddings=embeddings[i:end],
                metadatas=metadatas[i:end],
            )
        print(f"  Indexed {len(ids)} leaves → {COLLECTION}")

        # 4) parent sidecar
        sidecar = DB_DIR / "hier_nodes_commentary.json"
        sidecar.write_text(
            json.dumps(parent_texts, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  Sidecar: {sidecar} ({len(parent_texts)} parents)\n")

    # 검증
    print("=" * 60)
    for c in client.list_collections():
        print(f"  {c.name:35s} count={c.count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
