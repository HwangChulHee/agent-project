"""
부트스트랩 임포터 — 프론티어 LLM이 그린 개념지도(JSON)를 맵으로 앉힘.
mastery는 전부 0.0 (self는 나중에 사용자가 채움). dangling 엣지 검증.
"""
import json
import sys
from kb.store import new_map, add_node, add_edge, save_map, REL_TYPES


def import_bootstrap(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    m = new_map()

    # 1) 개념 → 노드 (mastery 0.0)
    for c in data.get("concepts", []):
        add_node(m, c["id"], c.get("type", "개념"), mastery=c.get("mastery", 0.0))

    node_ids = set(m["nodes"].keys())

    # 2) 관계 → 엣지 (화이트리스트 + dangling 검증)
    added, skipped_rel, dangling = 0, [], []
    for r in data.get("relations", []):
        if r.get("rel") not in REL_TYPES:
            skipped_rel.append(r)
            continue
        if r["from"] not in node_ids or r["to"] not in node_ids:
            dangling.append(r)   # 끝점이 노드에 없음
            continue
        add_edge(m, r["from"], r["rel"], r["to"], source="bootstrap")
        added += 1

    save_map(m)

    print(f"노드 {len(m['nodes'])}개, 엣지 {added}개 임포트")
    if skipped_rel:
        print(f"⚠ 화이트리스트 밖 관계 {len(skipped_rel)}개 건너뜀: {[r['rel'] for r in skipped_rel]}")
    if dangling:
        print(f"⚠ dangling 엣지 {len(dangling)}개 (끝점이 개념 목록에 없음):")
        for r in dangling:
            print(f"    {r['from']} -{r['rel']}-> {r['to']}")
    if not skipped_rel and not dangling:
        print("✓ 모든 관계 정상 (dangling 없음)")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/bootstrap.json"
    import_bootstrap(path)
