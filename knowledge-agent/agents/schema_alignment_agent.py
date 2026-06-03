"""
정렬/병합 (KARMA의 Entity Normalization).
타입이 같을 때만 병합 허용. 신규는 mastery=0.0, 기존 my_level 보존.
"""
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from kb.store import (
    load_map, save_map, new_map, add_node, add_edge,
    get_node, find_gaps, REL_TYPES,
)
from agents.entity_extraction_agent import extract

load_dotenv()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
MODEL = "gpt-4o-mini"

ALIGN_PROMPT = """너는 지식 그래프의 개념 정렬기다.
새 개념이 기존 개념 중 하나와 '같은 개념'인지 판단한다.

규칙:
- 표기나 언어가 달라도 의미가 같으면 같은 것으로 본다 (예: reranking = 리랭킹).
- 단, type이 다르면 절대 같다고 하지 마라.
- 한쪽이 다른 쪽의 한 종류/예시일 뿐이면 같은 것이 아니다 (신규로 둬라).
- 확실하지 않으면 신규로 둬라.

기존 개념(이름:type): {existing}
새 개념(이름:type): {new}

각 새 개념에 same_as(같은 기존 개념명, 없으면 null)와 reason을 붙여 JSON으로만:
{{"mappings": [{{"new": "...", "same_as": null, "reason": "..."}}]}}"""


def align(m, extracted, source):
    new_items = [(c["id"], c.get("type", "개념")) for c in extracted.get("concepts", [])]
    existing = [(cid, n.get("type", "개념")) for cid, n in m["nodes"].items()]

    if existing and new_items:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": ALIGN_PROMPT.format(
                existing=existing, new=new_items)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        mappings = json.loads(resp.choices[0].message.content).get("mappings", [])
    else:
        mappings = [{"new": c[0], "same_as": None} for c in new_items]

    # 정렬표: 같은 타입 + 기존에 존재할 때만 병합
    type_of = {cid: t for cid, t in existing}
    new_type = {cid: t for cid, t in new_items}
    remap = {}
    for mp in mappings:
        same = mp.get("same_as")
        if same in m["nodes"] and type_of.get(same) == new_type.get(mp["new"]):
            remap[mp["new"]] = same      # 타입 일치 → 병합
        else:
            remap[mp["new"]] = mp["new"]  # 그 외 → 신규

    added, merged = [], []
    for c in extracted.get("concepts", []):
        canon = remap.get(c["id"], c["id"])
        if canon == c["id"] and get_node(m, c["id"]) is None:
            add_node(m, c["id"], c.get("type", "개념"), mastery=0.0)
            added.append(c["id"])
        elif canon != c["id"]:
            merged.append((c["id"], canon))

    for r in extracted.get("relations", []):
        if r.get("rel") not in REL_TYPES:
            continue
        src = remap.get(r["from"], r["from"])
        dst = remap.get(r["to"], r["to"])
        add_edge(m, src, r["rel"], dst, source=source)

    return added, merged


if __name__ == "__main__":
    sample = (
        "Cross-encoder reranking improves retrieval quality in RAG systems "
        "by re-scoring the top candidates from an initial embedding-based "
        "retrieval."
    )
    try:
        m = load_map()
    except FileNotFoundError:
        m = new_map()
    extracted = extract(sample)
    print("추출:", [(c["id"], c["type"]) for c in extracted.get("concepts", [])])
    added, merged = align(m, extracted, source="sample-001")
    save_map(m)
    print("신규:", added)
    print("병합:", merged)
    print("갭:", find_gaps(m))
