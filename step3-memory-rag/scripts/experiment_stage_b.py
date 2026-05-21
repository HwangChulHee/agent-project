"""Stage B substep 4: 2축 실험 — 검색(Baseline/A/B) × 응답(leaf-only/parent-hydration)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
PARENTS_PATH = Path(DB_DIR) / "hier_nodes.json"
QUERIES = ["Einstein Nobel", "퀴리 부인 원소"]
TOP_K = 1   # LLM 텍스트 길이 비교에 집중 — 노이즈 줄이려 top-1만

client = chromadb.PersistentClient(path=DB_DIR)
cols = {c.name: c for c in client.list_collections()}
parents = json.loads(PARENTS_PATH.read_text(encoding="utf-8"))
model = SentenceTransformer(EMBED_MODEL)


def search(col_name, q_emb):
    res = cols[col_name].query(query_embeddings=[q_emb], n_results=TOP_K)
    return {
        "doc": res["documents"][0][0],
        "meta": res["metadatas"][0][0],
        "dist": res["distances"][0][0],
    }


def parent_text_of(meta):
    pid = meta.get("parent_id")
    if not pid or pid not in parents:
        return None
    return parents[pid]["text"]


def show_row(label, hit, llm_text, hypothesis_note=""):
    print(f"  {label:6s}  d={hit['dist']:.4f}  "
          f"doc={hit['meta'].get('doc_id','?'):16s}  "
          f"LLM_len={len(llm_text):>5d}  {hypothesis_note}")


for q in QUERIES:
    print(f"\n{'='*80}\n=== Query: {q!r}\n{'='*80}")
    q_emb = model.encode(q).tolist()

    bl   = search("wikipedia",              q_emb)
    a    = search("wikipedia_hierarchical", q_emb)
    b    = search("wikipedia_contextual",   q_emb)

    rows = [
        ("BL",  bl, bl["doc"],                       "(baseline = 검색·응답 동일)"),
        ("A-L", a,  a["doc"],                        "Stage A 임베딩 + leaf만 응답"),
        ("A-P", a,  parent_text_of(a["meta"]) or a["doc"], "Stage A 정식 (parent)"),
        ("B-L", b,  b["doc"],                        "Stage B 임베딩 + leaf만 응답"),
        ("B-P", b,  parent_text_of(b["meta"]) or b["doc"], "Stage B 정식 (parent)"),
    ]

    print(f"\n  {'ID':6s}  {'distance':9s} {'doc':24s} {'LLM_len':>8s}  hypothesis")
    print(f"  {'-'*6}  {'-'*9} {'-'*24} {'-'*8}  {'-'*40}")
    for label, hit, llm_text, note in rows:
        show_row(label, hit, llm_text, note)

    # 매칭 leaf와 LLM 컨텍스트 일부 노출 (정성 평가)
    print(f"\n  --- 매칭 leaf 텍스트 (top-1) ---")
    print(f"  BL  : {bl['doc'][:140].strip()}...")
    print(f"  A   : {a['doc'][:140].strip()}...")
    print(f"  B   : {b['doc'][:140].strip()}...")

    # B-P가 LLM에 넘기는 parent (정식 Stage B 응답 맥락)
    bp_parent = parent_text_of(b["meta"])
    if bp_parent:
        print(f"\n  --- B-P가 LLM에 전달할 parent ({len(bp_parent)}자) ---")
        print(f"  {bp_parent[:300].strip()}...")


print(f"\n{'='*80}\n가설 검증 read:")
print(f"  H1 (context가 검색 강화):   A-P d  vs  B-P d   (낮으면 H1 지지)")
print(f"  H1 다른 각도:                A-L d  vs  B-L d")
print(f"  H2 (parent 필요한가):        B-L LLM_len  vs  B-P LLM_len + 매칭 품질")
