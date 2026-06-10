"""노드 임베딩 생성 → data/outputs/node_embeddings.json.

각 노드의 텍스트(definition, 없으면 canonical+ptype 폴백)를 임베딩해 저장.
모델명을 함께 기록 — 모델이 바뀌면 전체 재생성, 같으면 영구 재사용.
증분: 이미 임베딩된 노드는 건너뛴다. --force로 전체 재생성.

실행: uv run python src/embed_nodes.py        (신규 노드만)
      uv run python src/embed_nodes.py --force (전체)
"""
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

import config  # OUT_DIR

load_dotenv()
client = OpenAI()

EMBED_MODEL = "text-embedding-3-small"
NORMALIZED = config.OUT_DIR / "normalized.json"
EMB_PATH = config.OUT_DIR / "node_embeddings.json"


def node_text(key, node):
    """임베딩할 텍스트. definition 우선, 없으면(placeholder) 이름+유형 폴백."""
    canonical = node.get("canonical", key)
    definition = (node.get("definition") or "").strip()
    if definition:
        return f"{canonical}: {definition}"
    return f"{canonical} ({node.get('ptype', 'technique')})"


def main():
    force = "--force" in sys.argv
    nodes = json.loads(NORMALIZED.read_text())["nodes"]

    store = {"model": EMBED_MODEL, "dim": None, "vectors": {}}
    if EMB_PATH.exists() and not force:
        prev = json.loads(EMB_PATH.read_text())
        if prev.get("model") == EMBED_MODEL:          # 같은 모델일 때만 재사용
            store = prev
        else:
            print(f"모델 변경 감지 ({prev.get('model')} -> {EMBED_MODEL}), 전체 재생성")

    todo = [k for k in nodes if k not in store["vectors"]]
    print(f"노드 {len(nodes)}개 / 신규 임베딩 대상 {len(todo)}개")
    if not todo:
        print("할 일 없음.")
        return

    # 배치로 한 번에 (text-embedding-3-small은 다중 입력 지원)
    texts = [node_text(k, nodes[k]) for k in todo]
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    for k, item in zip(todo, resp.data):
        store["vectors"][k] = item.embedding
    store["dim"] = len(resp.data[0].embedding)

    EMB_PATH.write_text(json.dumps(store, ensure_ascii=False))
    placeholders = sum(1 for k in todo if not (nodes[k].get("definition") or "").strip())
    print(f"저장 완료: {EMB_PATH.name} / 총 {len(store['vectors'])}개 "
          f"(이번 신규 중 placeholder 폴백 {placeholders}개) / dim {store['dim']}")


if __name__ == "__main__":
    main()
