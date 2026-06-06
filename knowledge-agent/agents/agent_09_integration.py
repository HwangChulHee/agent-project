"""
09 통합 (Integration) — 판정 산출물(05 노드, 06 엣지)을 실제 맵에 쓴다.
산출: 09a(디버그, 정의 더미 보존) / 09b(운영, 정의 단수 객체).

정의 단위 = {"text", "source", "pub_date"}  (맨 문자열 아님 — 출처·시점 보존).
원칙:
  - mastery 불개입(new=0, merge/seed=유지) · new id=05 name · type=None(SAA 일).
  - 정의 병합 = append + text 완전일치 dedup (FUSE/의미dedup 금지).
  - locked=true → SELECT/갱신 대상 아님. 수동 정의 고정(이번 논문 정의 무시, 로그만).
  - SELECT는 (맵 기존 정의 + 더미)에서 깨끗한 1개. 날짜 가중치는 미구현
    (논문 vs 논문 케이스 = 두 번째 논문 때 데이터 보고 규칙 확정). 지금은 신호만 보존.
"""
import json
import argparse
from datetime import date

from dotenv import load_dotenv
from openai import OpenAI

from agents.prompts.definition_select import SELECT as SELECT_PROMPT
from agents.paths import paper_paths, pub_date_from_id, MAP_PATH

load_dotenv()

SELECT_MODEL = "gpt-4o-mini"
REL_TYPES = {"is_a", "part_of", "depends_on"}

client = OpenAI(timeout=30, max_retries=3)


def _mk_def(text, source, pub_date):
    return {"text": text, "source": source, "pub_date": pub_date}


def _normalize_existing(d):
    """맵의 기존 정의를 정의-객체로. 첫 통합 전엔 문자열(시드), 이후엔 객체."""
    if isinstance(d, dict):
        return dict(d)
    return _mk_def(d, "seed", None)          # 시드 부트스트랩 정의


def _append_defs(node, new_defs):
    """append + text 완전일치 dedup (순서 보존)."""
    seen = {d["text"] for d in node["definitions"]}
    for d in new_defs:
        if d["text"] not in seen:
            node["definitions"].append(d)
            seen.add(d["text"])


# ── 노드 패스 (순수, LLM 없음) ──────────────────────────────
def node_pass(kmap, aligned, paper, pub):
    """반환: (nodes, merged_from, locked_skipped)."""
    nodes, merged_from, locked_skipped = {}, {}, []
    for nid, n in kmap["nodes"].items():
        nodes[nid] = {
            "type": n.get("type"),
            "definitions": [_normalize_existing(n["definition"])] if "definition" in n else [],
            "mastery": n.get("mastery", 0.0),
            "locked": n.get("locked", False),
            "_seed_intent": n.get("_seed_intent"),
            "last_touched": n.get("last_touched"),
            "last_probed": n.get("last_probed"),
        }
    for c in aligned:
        paper_defs = [_mk_def(t, paper, pub) for t in c["definitions"]]
        if c["verdict"] == "merge":
            tgt = c["matched_node"]
            if tgt not in nodes:
                nodes[tgt] = _blank_node()
            if nodes[tgt]["locked"]:                       # 잠긴 노드 = 동결
                locked_skipped.append({"node": tgt, "from": c["name"]})
                continue
            _append_defs(nodes[tgt], paper_defs)
            nodes[tgt]["last_touched"] = date.today().isoformat()
            merged_from.setdefault(tgt, []).append(c["name"])
        else:
            nid = c["name"]
            if nid in nodes:
                _append_defs(nodes[nid], paper_defs)
            else:
                node = _blank_node()
                _append_defs(node, paper_defs)
                nodes[nid] = node
    return nodes, merged_from, locked_skipped


def _blank_node():
    return {"type": None, "definitions": [], "mastery": 0.0, "locked": False,
            "_seed_intent": None, "last_touched": date.today().isoformat(),
            "last_probed": None}


# ── SELECT (유일한 LLM 부분) ────────────────────────────────
def select_definition(name, defs):
    """더미(정의-객체 리스트)에서 best 1개. 1개면 그대로. 실패 시 0 fallback.
    날짜 가중치 미구현 — 깨끗함만 본다(LLM)."""
    if len(defs) <= 1:
        return (defs[0] if defs else None), 0
    listing = "\n".join(f"  {i}. \"{d['text']}\"" for i, d in enumerate(defs))
    user = f"Concept: {name}\n{listing}"
    try:
        resp = client.chat.completions.create(
            model=SELECT_MODEL,
            messages=[{"role": "system", "content": SELECT_PROMPT},
                      {"role": "user", "content": user}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        idx = json.loads(resp.choices[0].message.content).get("index", 0)
        if not isinstance(idx, int) or not (0 <= idx < len(defs)):
            print(f"  ! SELECT 잘못된 인덱스({idx}) → 0 fallback: {name}")
            idx = 0
    except Exception as e:
        print(f"  ! SELECT 오류({e}) → 0 fallback: {name}")
        idx = 0
    return defs[idx], idx


# ── 엣지 패스 (순수, LLM 없음) ──────────────────────────────
def edge_pass(relations, node_ids, paper):
    edges, dangling, seen = [], [], set()
    for r in relations:
        src, rel, dst = r["src"], r["rel"], r["dst"]
        if rel not in REL_TYPES:
            dangling.append({**r, "_skip": f"rel '{rel}' not in whitelist"}); continue
        miss = [e for e in (src, dst) if e not in node_ids]
        if miss:
            dangling.append({**r, "_skip": f"endpoint missing: {miss}"}); continue
        key = (src, rel, dst)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from": src, "rel": rel, "to": dst,
                      "source": paper, "confidence": 1.0, "evidence": r.get("evidence", "")})
    return edges, dangling


# ── 오케스트레이션 ─────────────────────────────────────────
def main(paper, do_select):
    P = paper_paths(paper)
    pub = pub_date_from_id(paper)
    kmap = json.load(open(MAP_PATH, encoding="utf-8"))
    aligned = json.load(open(P["05"], encoding="utf-8"))
    relations = json.load(open(P["06_relations"], encoding="utf-8"))

    nodes, merged_from, locked_skipped = node_pass(kmap, aligned, paper, pub)
    edges, dangling = edge_pass(relations, set(nodes.keys()), paper)

    print(f"=== SELECT ({'LLM' if do_select else 'STUB idx0'}) — multi-def 노드만 ===")
    final_nodes, debug_nodes = {}, {}
    for nid, n in nodes.items():
        defs = n["definitions"]
        if n["locked"]:                                    # 동결 — SELECT 안 함
            chosen, idx = (defs[0] if defs else None), 0
        elif do_select:
            chosen, idx = select_definition(nid, defs)
        else:
            chosen, idx = (defs[0] if defs else None), 0
        if len(defs) > 1 and not n["locked"]:
            print(f"  {nid[:28]:30} {len(defs)}개 → #{idx}  ({chosen['source']})")
        final_nodes[nid] = {
            "type": n["type"], "definition": chosen, "mastery": n["mastery"],
            "locked": n["locked"], "_seed_intent": n["_seed_intent"],
            "last_touched": n["last_touched"], "last_probed": n["last_probed"],
        }
        debug_nodes[nid] = {
            "definitions": defs, "selected_index": idx, "selected": chosen,
            "merged_from": merged_from.get(nid, []), "n_defs": len(defs),
            "locked": n["locked"],
        }

    if do_select:
        json.dump({"nodes": debug_nodes}, open(P["09a"], "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        json.dump({"nodes": final_nodes, "edges": edges},
                  open(MAP_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"\n=== 통합 후 점검 ===")
    print(f"  노드 {len(final_nodes)}  (시드 {len(kmap['nodes'])} + new "
          f"{len(final_nodes) - len(kmap['nodes'])})")
    print(f"  엣지 {len(edges)}")
    for e in edges:
        print(f"    {e['from']} --{e['rel']}--> {e['to']}  [{e['evidence']}]")
    print(f"  dangling/skip {len(dangling)}")
    for d in dangling:
        print(f"    {d.get('src')} {d.get('rel')} {d.get('dst')} — {d['_skip']}")
    print(f"  merge 흡수: " + (", ".join(f"{k}←{len(v)}" for k, v in merged_from.items()) or "없음"))
    if locked_skipped:
        print(f"  locked 동결(이번 논문 정의 무시): {locked_skipped}")
    if do_select:
        print(f"\n저장: 09a {P['09a']}\n      09b {MAP_PATH}")
    else:
        print(f"\n(스텁 — 파일 안 씀. 카운트 맞으면 --run 으로 실제 SELECT 실행)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True)
    ap.add_argument("--run", action="store_true",
                    help="실제 SELECT(LLM) 실행. 없으면 스텁(0번)으로 결정성만 검증.")
    args = ap.parse_args()
    main(args.paper, args.run)
