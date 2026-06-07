"""
07 CRA (Conflict Detection) — 새 논문 엣지가 기존 맵 엣지와 모순되는지 감지.

핵심: **감지만 한다. 엣지를 빼거나 바꾸지 않는다.** 반영/보류는 08 통합 몫.
LLM 안 씀 — (from, to) 끝점 비교라 순수 코드로 충분하고 결정적.

모순 규칙 (감지 키 = (from, to) 쌍):
  케이스1 rel_mismatch : 같은 (from, to)인데 rel이 다름 (is_a vs part_of)
  케이스2 cycle        : 방향 뒤집힌 같은 rel 동시 존재 (A is_a B & B is_a A)
  모순 아님            : (from, to)가 다르면 정상. 끝점이 다르면 둘 다 참 가능.
                        예) "ReAct is_a 기법" + "ReAct part_of 시스템" → 충돌 아님.

detect는 두 방향을 본다:
  - 새 엣지 vs 기존 맵 엣지   → 보류 대상 = 새 엣지만 (보수적: 기존은 항상 유지)
  - 새 엣지 vs 새 엣지(동일 논문 내) → 둘 다 새 거라 우선순위 없음 → 둘 다 보류
"""


def _conflict_kind(e1, e2):
    """e1, e2가 모순이면 kind 문자열, 아니면 None. (순수 비교)"""
    # 케이스1: 같은 (from, to), rel만 다름
    if e1["from"] == e2["from"] and e1["to"] == e2["to"] and e1["rel"] != e2["rel"]:
        return "rel_mismatch"
    # 케이스2: 방향 뒤집힘 + 같은 rel (A is_a B & B is_a A → 사이클)
    if e1["from"] == e2["to"] and e1["to"] == e2["from"] and e1["rel"] == e2["rel"]:
        return "cycle"
    return None


def detect(new_edges, map_edges):
    """반환: conflicts 리스트. 각 항목:
        {"pair": [from, to], "kind": "rel_mismatch"|"cycle",
         "edges": [기존/먼저, 새/나중], "held": [보류할 새 엣지...]}
    held는 08이 "맵에 안 넣고 대기열로 보낼 새 엣지"를 고를 때 쓴다.
    """
    conflicts = []

    # 새 엣지 vs 기존 맵 엣지 — 보류는 새 엣지만 (기존은 보수적으로 유지)
    for ne in new_edges:
        for me in map_edges:
            kind = _conflict_kind(ne, me)
            if kind:
                conflicts.append({
                    "pair": [ne["from"], ne["to"]],
                    "kind": kind,
                    "edges": [me, ne],     # [기존, 새]
                    "held": [ne],
                })

    # 새 엣지 vs 새 엣지(동일 논문) — 둘 다 새라 우선순위 없음 → 둘 다 보류
    for i in range(len(new_edges)):
        for j in range(i + 1, len(new_edges)):
            kind = _conflict_kind(new_edges[i], new_edges[j])
            if kind:
                conflicts.append({
                    "pair": [new_edges[i]["from"], new_edges[i]["to"]],
                    "kind": kind,
                    "edges": [new_edges[i], new_edges[j]],
                    "held": [new_edges[i], new_edges[j]],
                })

    return conflicts


def resolve(conflicts):
    # TODO: 실제 충돌이 쌓이면 결정. 사이클=자동, is_a/part_of 애매=locked 수작업,
    #       LLM은 그 사이. 지금은 충돌 사례 0건이라 방식을 정할 데이터가 없다.
    raise NotImplementedError
