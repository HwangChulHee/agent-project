"""
다이제스트 — 맵을 읽어 '지금 읽을 가치 높은 개념'을 우선순위로 정리.
LLM 없음. mastery + depends_on 구조만으로 계산.
"""
from kb.store import load_map, get_node, prerequisites, GAP_THRESHOLD

PREREQ_MET = 0.5  # 선수지식 mastery가 이 이상이면 '충족'


def prereqs_met(m, concept_id):
    pres = prerequisites(m, concept_id)
    if not pres:
        return None
    return all((get_node(m, p) or {}).get("mastery", 0) >= PREREQ_MET for p in pres)


def digest(m):
    frontier, locked, unknown_prereq = [], [], []
    for cid, node in m["nodes"].items():
        if node["mastery"] >= GAP_THRESHOLD:
            continue  # 이미 아는 건 제외
        met = prereqs_met(m, cid)
        if met is True:
            frontier.append(cid)
        elif met is False:
            missing = [p for p in prerequisites(m, cid)
                       if (get_node(m, p) or {}).get("mastery", 0) < PREREQ_MET]
            locked.append((cid, missing))
        else:
            unknown_prereq.append(cid)
    return frontier, locked, unknown_prereq


if __name__ == "__main__":
    m = load_map()
    frontier, locked, unknown_prereq = digest(m)
    print("🎯 지금 배우기 좋음:", frontier or "(없음)")
    print("🔒 선수지식 먼저:", [f"{c}←{mi}" for c, mi in locked] or "(없음)")
    print("❓ 선수지식 정보 없음:", unknown_prereq or "(없음)")
