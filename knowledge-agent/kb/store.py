"""
지식 맵 — 노드(개념 + mastery) + 엣지(관계 + 출처 + 신뢰도)를 JSON으로 관리.
mastery: 0.0~1.0 연속값 (0=모름 ~ 1=완전 숙달). 프로빙으로 채워짐.
"""
import json
import os
from datetime import date

REL_TYPES = {"is_a", "part_of", "depends_on"}  # 관계 화이트리스트
GAP_THRESHOLD = 0.5  # mastery가 이 미만이면 '아직 모름(갭)'으로 봄

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_PATH = os.path.join(_ROOT, "data", "knowledge_map.json")


def new_map():
    return {"nodes": {}, "edges": []}


def load_map(path=MAP_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_map(m, path=MAP_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def add_node(m, concept_id, ntype, mastery=0.0):
    m["nodes"][concept_id] = {
        "type": ntype,
        "mastery": mastery,
        "last_touched": date.today().isoformat(),
        "last_probed": None,
    }


def add_edge(m, src, rel, dst, source="seed", confidence=1.0):
    if rel not in REL_TYPES:
        raise ValueError(f"알 수 없는 관계: {rel} (가능: {REL_TYPES})")
    m["edges"].append({
        "from": src, "rel": rel, "to": dst,
        "source": source, "confidence": confidence,
    })


def get_node(m, concept_id):
    return m["nodes"].get(concept_id)


def find_gaps(m):
    """mastery가 GAP_THRESHOLD 미만 = 아직 모르는 개념(갭)."""
    return [cid for cid, n in m["nodes"].items() if n["mastery"] < GAP_THRESHOLD]


def prerequisites(m, concept_id):
    """이 개념이 depends_on으로 가리키는 선수지식."""
    return [e["to"] for e in m["edges"]
            if e["from"] == concept_id and e["rel"] == "depends_on"]


if __name__ == "__main__":
    # 시드 — mastery는 대략의 자기보고 (3→0.9, 2→0.6, 0→0.0)
    m = new_map()
    add_node(m, "LLM 에이전트", "개념", mastery=0.6)
    add_node(m, "ReAct", "기법", mastery=0.9)
    add_node(m, "function calling", "기법", mastery=0.6)
    add_node(m, "RAG", "기법", mastery=0.9)
    add_node(m, "리랭킹", "기법", mastery=0.0)        # 갭!
    add_node(m, "임베딩검색", "기법", mastery=0.9)

    add_edge(m, "ReAct", "is_a", "LLM 에이전트")
    add_edge(m, "function calling", "is_a", "LLM 에이전트")
    add_edge(m, "리랭킹", "part_of", "RAG")
    add_edge(m, "임베딩검색", "part_of", "RAG")
    add_edge(m, "리랭킹", "depends_on", "임베딩검색")

    save_map(m)
    print(f"=== 노드 {len(m['nodes'])}개, 엣지 {len(m['edges'])}개 ===")
    print("내 갭(mastery<0.5):", find_gaps(m))
    pre = prerequisites(m, "리랭킹")
    print("리랭킹 선수지식:", pre)
    print("선수지식 mastery:", {p: get_node(m, p)["mastery"] for p in pre})
