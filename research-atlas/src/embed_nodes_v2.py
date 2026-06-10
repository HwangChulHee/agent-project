"""embed_nodes_v2: 이중 노드 임베딩.
   개념 노드 -> definition 임베딩 (정의 있는 것만, 순수 정의 텍스트)
   논문 노드 -> problem 임베딩
   placeholder 개념(정의 없음)은 제외 — 수집으로 정의 채워지면 자동 합류.
   모델명 기록 -> 모델 같으면 영구 재사용, 바뀌면 전체 재생성.
   증분: 이미 임베딩된 id는 건너뜀. --force로 전체.
   실행: uv run python src/embed_nodes_v2.py [--force]
"""
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

load_dotenv()
client = OpenAI()

EMBED_MODEL = "text-embedding-3-small"
NORMALIZED = config.OUT_DIR / "normalized_v2.json"
EMB_PATH = config.OUT_DIR / "node_embeddings_v2.json"


def embed_text(node_id, node):
    if node["type"] == "concept":
        d = (node.get("definition") or "").strip()
        return d or None
    if node["type"] == "paper":
        p = (node.get("problem") or "").strip()
        return p or None
    return None


def main():
    force = "--force" in sys.argv
    nodes = json.loads(NORMALIZED.read_text())["nodes"]

    store = {"model": EMBED_MODEL, "dim": None, "vectors": {}}
    if EMB_PATH.exists() and not force:
        prev = json.loads(EMB_PATH.read_text())
        if prev.get("model") == EMBED_MODEL:
            store = prev
        else:
            print(f"모델 변경 ({prev.get('model')} -> {EMBED_MODEL}), 전체 재생성")

    todo, texts = [], []
    skipped_concept = 0
    for nid, node in nodes.items():
        t = embed_text(nid, node)
        if t is None:
            if node["type"] == "concept":
                skipped_concept += 1
            continue
        if nid in store["vectors"]:
            continue
        todo.append(nid)
        texts.append(t)

    n_paper = sum(1 for n in nodes.values() if n["type"] == "paper")
    n_concept = sum(1 for n in nodes.values() if n["type"] == "concept")
    print(f"노드: 논문 {n_paper} + 개념 {n_concept} / "
          f"정의 없는 개념 제외 {skipped_concept}개 / 신규 임베딩 {len(todo)}개")
    if not todo:
        print("할 일 없음.")
        return

    B = 256
    for i in range(0, len(todo), B):
        chunk_ids, chunk_txt = todo[i:i + B], texts[i:i + B]
        resp = client.embeddings.create(model=EMBED_MODEL, input=chunk_txt)
        for nid, item in zip(chunk_ids, resp.data):
            store["vectors"][nid] = item.embedding
        store["dim"] = len(resp.data[0].embedding)

    EMB_PATH.write_text(json.dumps(store, ensure_ascii=False))
    emb_paper = sum(1 for k in store["vectors"] if k.startswith("paper:"))
    emb_concept = sum(1 for k in store["vectors"] if k.startswith("concept:"))
    print(f"저장: {EMB_PATH.name} / 논문 {emb_paper} + 개념 {emb_concept} "
          f"= {len(store['vectors'])} / dim {store['dim']}")


if __name__ == "__main__":
    main()
