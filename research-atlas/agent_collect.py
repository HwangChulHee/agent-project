"""수집 에이전트 (전환 4/4) — 의도 파싱 → 현황(개념+논문 두 각도) → 현황 보고 + 충분성 추천.

v2 이중 노드 임베딩(node_embeddings_v2.json) 위에서 동작.
- 개념 매칭(definition): "이 주제 관련 기법이 뭐 있나".
- 논문 매칭(problem): "같은 문제를 다룬 논문이 뭐 있나" (세렌디피티 씨앗).
arXiv 실제 수집/승인/분기는 다음 조각. 이번은 현황 보고까지만.

실행: uv run python agent_collect.py
"""
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import feedparser
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

# 기존 추출 파이프라인 재사용 (src/) — 호출만, 로직 수정 안 함
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import config  # noqa: E402
import extract  # noqa: E402
import fetch  # noqa: E402
import parse  # noqa: E402
import prompts  # noqa: E402
import relate  # noqa: E402

load_dotenv()
client = OpenAI()
MODEL = "gpt-5.4-mini"
EMBED_MODEL = "text-embedding-3-small"

ARXIV_API = "https://export.arxiv.org/api/query"
NORMALIZED_V2 = Path("data/outputs/normalized_v2.json")
PAPERS_LEDGER = Path("data/outputs/papers.json")
REJECT_VERDICTS = {"reject", "rejected", "drop"}  # 관문 탈락으로 보는 verdict

GATE_PROMPT_VER = "gate-v1"   # 관문 프롬프트 버전 — 바뀌면 재판정 판별용
MAX_EXTRACT = 2               # 스모크 추출 상한(실수로 수백 편 PDF 받는 사고 방지)

INTENT_TOOL = {
    "type": "function",
    "function": {
        "name": "report_intent",
        "description": "수집 명령의 의도를 구조화해 보고한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "수집 주제, 영어 연구용어로 (예: RAG robustness to retrieval noise)"},
                "topic_kr": {"type": "string", "description": "주제를 해석한 한국어 한 줄. 입력 문장을 복사하지 말고, 어떤 연구 주제로 이해했는지 풀어쓴다 (예: '검색된 문서에 노이즈가 섞여도 답변 품질을 유지하는 RAG 기법')"},
                "interpretation": {"type": "string", "description": "이 주제의 가능한 갈래들과 그중 어느 갈래로 좁혔는지 2~3문장. 모호한 부분이 있으면 명시 (예: '강건성은 검색 노이즈/적대적 공격/분포 변화로 갈리는데, RAG 맥락에선 보통 검색 노이즈를 뜻하므로 그쪽으로 해석')"},
                "period_from": {"type": "string", "description": "YYYY-MM. 명시 없으면 빈 문자열"},
                "period_to": {"type": "string", "description": "YYYY-MM. 명시 없으면 빈 문자열"},
            },
            "required": ["topic", "topic_kr", "interpretation"],
        },
    },
}


# --- 임베딩 로더 (v2, 타입 분리) ---
def load_embeddings():
    """node_embeddings_v2.json -> 타입별(개념/논문) 정규화 행렬로 분리.

    반환: model, norm(v2 nodes dict), (concept_keys, concept_mat), (paper_keys, paper_mat)
    """
    store = json.loads(Path("data/outputs/node_embeddings_v2.json").read_text())
    norm = json.loads(Path("data/outputs/normalized_v2.json").read_text())["nodes"]
    model = store["model"]

    def build(prefix):
        keys = [k for k in store["vectors"] if k.startswith(prefix)]
        if not keys:
            return [], None
        mat = np.array([store["vectors"][k] for k in keys], dtype=np.float32)
        mat /= np.linalg.norm(mat, axis=1, keepdims=True)
        return keys, mat

    return model, norm, build("concept:"), build("paper:")


# --- 두 각도 매칭 ---
def embed_query(topic, model):
    qv = client.embeddings.create(model=model, input=[topic]).data[0].embedding
    q = np.array(qv, dtype=np.float32)
    return q / np.linalg.norm(q)


def match(q, keys, mat, top=8, floor=0.30):
    """topic 벡터와 코사인 유사. floor 미만은 컷, 상위 top개만."""
    if mat is None:
        return []
    sims = mat @ q  # 코사인 (둘 다 정규화됨)
    order = np.argsort(-sims)[:top]
    return [(keys[i], float(sims[i])) for i in order if sims[i] >= floor]


def parse_intent(text):
    system = (
        "너는 논문 수집 에이전트의 의도 파싱기다. 사용자의 수집 명령을 report_intent로 보고한다. "
        "topic은 arXiv 검색에 쓸 영어 연구용어로, interpretation은 주제의 가능한 갈래와 좁힌 방향을 적는다."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
        tools=[INTENT_TOOL],
        tool_choice={"type": "function", "function": {"name": "report_intent"}},
    )
    return json.loads(resp.choices[0].message.tool_calls[0].function.arguments)


# --- 현황 보고 + 충분성 추천 (LLM 1회) ---
REPORT_SYSTEM = (
    "너는 논문 수집 에이전트의 현황 분석가다. 주어진 수집 주제에 대해, 이미 보유한 "
    "관련 기법(개념)과 같은 문제를 다룬 논문을 사람이 읽기 좋게 풀어 설명하고, "
    "이 주제가 현재 그래프에 얼마나 덮여 있는지 종합 판정과 충분성 추천을 낸다.\n"
    "아래 구조 그대로(한국어)로만 출력한다:\n"
    "  관련 기법(개념):\n"
    "  • <이름> — <이 주제 관점에서 한 줄 풀이> (<점수>)\n"
    "  같은 문제를 다룬 논문:\n"
    "  • <제목> — <problem 한 줄 요약> (<점수>)\n"
    "  종합: <어느 측면이 덮였고 어디가 비었나 1~2문장>\n"
    "  추천: <충분 | 부분적(수집 권장) | 비어있음(수집 강력 권장)> — <한 줄 근거>\n"
    "규칙: 단순 나열이 아니라 주제 관점의 풀이를 쓴다. 정의 미보유 개념은 '정의 미보유'로 짧게 적는다. "
    "점수는 괄호로 작게 병기하되 사람 문장이 주가 되게 한다. 추천은 세 등급 중 하나만 고른다. "
    "후보가 비었으면 솔직히 비었다고 적고 추천에 반영한다."
)


def _concept_line(key, score, norm):
    n = norm.get(key, {})
    name = n.get("canonical", key.split(":", 1)[-1])
    definition = (n.get("definition") or "").strip()
    if n.get("def_status") == "placeholder" or not definition:
        return f"- {name} (정의 미보유) [{score:.2f}]"
    return f"- {name}: {definition} [{score:.2f}]"


def _paper_line(key, score, norm):
    n = norm.get(key, {})
    title = n.get("title", key.split(":", 1)[-1])
    problem = (n.get("problem") or "").strip() or "(문제 설명 없음)"
    return f"- {title} — {problem} [{score:.2f}]"


def build_status_report(intent, cm_hits, pm_hits, norm):
    concepts = "\n".join(_concept_line(k, s, norm) for k, s in cm_hits) or "(매칭된 개념 없음)"
    papers = "\n".join(_paper_line(k, s, norm) for k, s in pm_hits) or "(매칭된 논문 없음)"
    user = (
        f"수집 주제: {intent['topic']} — {intent.get('topic_kr', '')}\n"
        f"해석: {intent.get('interpretation', '')}\n\n"
        f"[보유 개념 후보 — definition 매칭]\n{concepts}\n\n"
        f"[같은 문제 논문 후보 — problem 매칭]\n{papers}"
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": REPORT_SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content


# --- [3] 검색어 확장 ---
EXPAND_TOOL = {
    "type": "function",
    "function": {
        "name": "expand_queries",
        "description": "수집 주제를 arXiv 전문 검색에 쓸 검색어 묶음으로 확장한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5~8개의 영어 검색어. 동의어·인접 표현·상위/하위 개념을 포함하되 주제에서 벗어나지 않게. 단순 topic 반복 금지.",
                },
            },
            "required": ["queries"],
        },
    },
}


def expand_query(topic, related_terms=None):
    """topic을 arXiv 검색어 5~8개로 확장. related_terms(보유 개념/논문)는 맵 밀착 재료."""
    system = (
        "너는 arXiv 검색어 확장기다. 주어진 연구 주제를 arXiv 전문 검색에 쓸 영어 검색어 "
        "5~8개로 펼친다. 동의어·인접 표현·상위/하위 개념을 포함하되 주제에서 벗어나지 않게 한다. "
        "단순 반복은 금지. expand_queries로 보고한다."
    )
    user = f"주제: {topic}"
    if related_terms:
        user += "\n관련 보유 개념/논문(맵 밀착 검색어 재료): " + ", ".join(related_terms)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        tools=[EXPAND_TOOL],
        tool_choice={"type": "function", "function": {"name": "expand_queries"}},
    )
    args = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)
    out, seen = [], set()
    for q in args.get("queries", []):
        q = (q or "").strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


# --- [4] arXiv 검색 ---
def _norm_arxiv_id(raw):
    """'http://arxiv.org/abs/2401.12345v2' / '2401.12345v2' -> '2401.12345' (버전 접미사 제거)."""
    tail = (raw or "").rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", tail)


def search_arxiv(queries, period_from="", period_to="", max_per_query=50):
    """검색어 묶음으로 arXiv 메타 검색 → {arxivID: meta}. 검색어 간 ID로 dedup.

    rate limit: 요청 사이 3초 sleep(arXiv 규정), 순차. period(YYYY-MM)는 클라이언트단 필터.
    """
    found = {}
    for i, q in enumerate(queries):
        if i:
            time.sleep(3)  # arXiv rate limit
        params = urllib.parse.urlencode({
            # 구문(phrase) 검색: 따옴표로 묶어야 다단어가 AND/구문으로 잡힘.
            # 따옴표 없으면 all:이 토큰 OR로 풀려 submittedDate 정렬 시 무관 최신논문이 뜸.
            "search_query": f'all:"{q}"',
            "start": 0,
            "max_results": max_per_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        req = urllib.request.Request(
            f"{ARXIV_API}?{params}",
            headers={"User-Agent": "research-atlas/0.1 (collect agent)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
        except Exception as e:  # 네트워크/타임아웃 — 한 검색어 건너뛰고 계속
            print(f"  검색 실패 [{q}]: {e}", file=sys.stderr)
            continue
        feed = feedparser.parse(raw)
        for e in feed.entries:
            aid = _norm_arxiv_id(e.get("id", ""))
            if not aid:
                continue
            published = (e.get("published", "") or "")[:10]  # YYYY-MM-DD
            ym = published[:7]
            if period_from and ym and ym < period_from:
                continue
            if period_to and ym and ym > period_to:
                continue
            if aid in found:
                continue  # 다른 검색어에 이미 잡힘
            found[aid] = {
                "title": " ".join((e.get("title", "") or "").split()),
                "abstract": " ".join((e.get("summary", "") or "").split()),
                "published": published,
                "categories": [t.get("term") for t in e.get("tags", [])],
                "first_seen_query": q,
            }
    return found


# --- papers.json 장부 (논문 장부, lexicon의 논문판) ---
def load_ledger():
    if PAPERS_LEDGER.exists():
        return json.loads(PAPERS_LEDGER.read_text())
    return {}


def upsert_ledger(found):
    """검색 결과를 papers.json에 upsert. gate/extracted/first_seen_query는 기존값 보존."""
    ledger = load_ledger()
    for aid, meta in found.items():
        if aid in ledger:  # 메타만 갱신, 판정 이력 보존
            ledger[aid].update({
                "title": meta["title"], "abstract": meta["abstract"],
                "published": meta["published"], "categories": meta["categories"],
            })
        else:
            ledger[aid] = {
                "title": meta["title"], "abstract": meta["abstract"],
                "published": meta["published"], "categories": meta["categories"],
                "gate": None, "extracted": False,
                "first_seen_query": meta["first_seen_query"],
            }
    PAPERS_LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2))
    return ledger


# --- [5] 신규 후보 산출 (보유분/관문탈락 제외) ---
def load_owned_ids():
    """normalized_v2.json의 paper 노드 키에서 보유 arXiv ID 집합."""
    nodes = json.loads(NORMALIZED_V2.read_text())["nodes"]
    return {k.split("paper:", 1)[1] for k in nodes if k.startswith("paper:")}


def dedup_new_candidates(found, ledger):
    """found 중 (1)이미 지도 보유, (2)과거 관문 탈락 을 제외한 신규 후보 id + 카운트."""
    owned = load_owned_ids()
    new, owned_excl, gate_excl = [], 0, 0
    for aid in found:
        if aid in owned:
            owned_excl += 1
            continue
        gate = (ledger.get(aid) or {}).get("gate") or {}
        if str(gate.get("verdict", "")).lower() in REJECT_VERDICTS:
            gate_excl += 1
            continue
        new.append(aid)
    counts = {"found": len(found), "owned_excluded": owned_excl,
              "gate_excluded": gate_excl, "new": len(new)}
    return new, counts


def save_ledger(ledger):
    PAPERS_LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2))


# --- [7] 관문 (gate) — 초록만 보고 paper_type 분류, technique만 통과 ---
GATE_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_paper",
        "description": "제목/초록만 보고(PDF 없이) paper_type 하나로 분류한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string",
                         "enum": ["technique", "benchmark", "analysis", "survey", "other"]},
                "reason": {"type": "string", "description": "분류 근거 한 줄"},
            },
            "required": ["type", "reason"],
        },
    },
}


def gate_classify(title, abstract):
    """LLM 1회. PAPER_TYPE_CRITERIA(추출과 동일 기준)로 초록만 보고 분류."""
    system = (
        "너는 논문 관문 분류기다. 제목과 초록만 보고(PDF 없이) paper_type을 하나로 분류한다.\n"
        "paper_type 기준 — EXACTLY one of:\n" + prompts.PAPER_TYPE_CRITERIA +
        "\nclassify_paper로 보고한다."
    )
    user = f"Title: {title}\n\nAbstract: {abstract}"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        tools=[GATE_TOOL],
        tool_choice={"type": "function", "function": {"name": "classify_paper"}},
    )
    return json.loads(resp.choices[0].message.tool_calls[0].function.arguments)


def gate_one(aid, ledger):
    """ledger[aid]의 title/abstract로 관문. 같은 prompt_ver 캐시 있으면 재호출 안 함.

    반환: (verdict, passed(bool), cached(bool)). technique만 통과(이진).
    """
    entry = ledger[aid]
    g = entry.get("gate")
    if g and g.get("prompt_ver") == GATE_PROMPT_VER:
        return g["verdict"], g["verdict"] == "technique", True
    res = gate_classify(entry.get("title", ""), entry.get("abstract", ""))
    verdict = res["type"]
    entry["gate"] = {
        "verdict": verdict,
        "reason": res.get("reason", ""),
        "model": MODEL,
        "prompt_ver": GATE_PROMPT_VER,
        "date": datetime.date.today().isoformat(),
    }
    return verdict, verdict == "technique", False


# --- [8] 추출 (기존 파이프라인 재사용) ---
def extract_pipeline(aid, ledger):
    """관문 통과 논문 1편: PDF→parse→extract→relate→파일 생성, ledger.extracted=true.

    반환: (ok, msg, concepts|None). 실패 시 스킵용 (ok=False).
    """
    config.PDF_DIR.mkdir(parents=True, exist_ok=True)
    ok, msg = fetch.download_one(aid)
    if not ok:
        return False, f"download 실패({msg})", None
    parsed = parse.parse_one(aid)
    if not parsed.get("ok"):
        return False, f"parse 실패({parsed.get('reason')})", None
    (config.OUT_DIR / f"{aid}.parsed.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2))
    text = parsed["text"]
    concepts = extract.extract_one(text)
    (config.OUT_DIR / f"{aid}.concepts.json").write_text(
        json.dumps(concepts, ensure_ascii=False, indent=2))
    rel = relate.relate_one(concepts, text)
    (config.OUT_DIR / f"{aid}.relations.json").write_text(
        json.dumps(rel, ensure_ascii=False, indent=2))
    ledger[aid]["extracted"] = True
    return True, f"추출 완료({msg})", concepts


SMOKE = [
    "2024년 RAG 강건성 논문 가져와줘",
    "knowledge graph 만드는 논문들 찾아와",
    "멀티에이전트 협업 관련 최신 논문 수집해줘",
]


def intent_smoke():
    """[1][2] 스모크 — 의도파싱 + 현황확인 + 현황보고."""
    model, norm, (ck, cm), (pk, pm) = load_embeddings()
    try:
        assert model == EMBED_MODEL, f"model 불일치: {model}"
        assert len(ck) == 73, f"개념 임베딩 73 기대, 실제 {len(ck)}"
        assert len(pk) == 68, f"논문 임베딩 68 기대, 실제 {len(pk)}"
    except AssertionError as e:
        print(f"게이트 실패: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"게이트 통과: 개념 {len(ck)} + 논문 {len(pk)} (model={model})\n")
    for query in SMOKE:
        intent = parse_intent(query)
        q = embed_query(intent["topic"], model)
        cm_hits = match(q, ck, cm)
        pm_hits = match(q, pk, pm)
        report = build_status_report(intent, cm_hits, pm_hits, norm)
        print(f'"{query}"\n  topic: {intent["topic"]}')
        print(report)
        print()


def collect_smoke():
    """[3][4][5] 스모크 — 검색어 확장 → arXiv 검색 → 장부 upsert → 신규 후보."""
    model, norm, (ck, cm), (pk, pm) = load_embeddings()
    query = "RAG 강건성 논문 찾아줘"  # period 없음(전체 기간) — 결과 비어있지 않게
    intent = parse_intent(query)
    topic = intent["topic"]

    # [2] 관련어 추출 — 보유 개념/논문을 검색어 확장 재료로
    qv = embed_query(topic, model)
    cm_hits, pm_hits = match(qv, ck, cm), match(qv, pk, pm)
    related = [norm[k]["canonical"] for k, _ in cm_hits if k in norm]
    related += [norm[k].get("title", "") for k, _ in pm_hits if k in norm]
    related = [r for r in related if r][:10]

    queries = expand_query(topic, related)            # [3]
    found = search_arxiv(queries, intent.get("period_from", ""),
                         intent.get("period_to", ""))  # [4]
    ledger = upsert_ledger(found)
    new, counts = dedup_new_candidates(found, ledger)  # [5]

    # --- 출력 (게이트보다 먼저 — 실패해도 출력은 보이게) ---
    print(f'"{query}"  →  topic: {topic}\n')
    print(f"[3] 검색어 {len(queries)}개:")
    for q in queries:
        print(f"   • {q}")
    print(f"\n[4] arXiv 발견 {counts['found']}편 (검색어 {len(queries)}개, 검색어당 max 50)")
    print("   샘플 3편:")
    for aid in list(found)[:3]:
        m = found[aid]
        print(f"   • {aid} [{m['published']}] {m['title']}")
        print(f"     {m['abstract'][:160]}…")
    print(f"\n[5] dedup: 발견 {counts['found']} / 보유제외 {counts['owned_excluded']} / "
          f"관문탈락제외 {counts['gate_excluded']} / 신규 {counts['new']}")
    print(f"   장부: {PAPERS_LEDGER} (총 {len(ledger)}편 누적)")

    # --- 하드 게이트 ---
    try:
        assert isinstance(queries, list) and all(isinstance(x, str) for x in queries) \
            and len(queries) >= 3, f"검색어 확장 실패: {queries}"
        assert len(found) > 0, "arXiv 검색 결과 0편 (네트워크/파싱 실패 의심)"
        complete = sum(1 for m in found.values()
                       if m["title"] and m["abstract"] and m["published"])
        assert complete * 2 >= len(found), f"메타 완전성 과반 미달: {complete}/{len(found)}"
        assert isinstance(json.loads(PAPERS_LEDGER.read_text()), dict), "papers.json 파싱 실패"
    except AssertionError as e:
        print(f"\n게이트 실패: {e}", file=sys.stderr)
        sys.exit(1)
    print("\n게이트 통과: 검색어 확장·arXiv 검색·메타 완전성·장부 OK")


def collect_extract_smoke():
    """[3][4][5] → [6] 물량승인(CLI) → [7] 관문 → [8] 통과분 최대 MAX_EXTRACT편 추출."""
    model, norm, (ck, cm), (pk, pm) = load_embeddings()
    query = "RAG 강건성 논문 찾아줘"
    intent = parse_intent(query)
    topic = intent["topic"]

    qv = embed_query(topic, model)
    cm_hits, pm_hits = match(qv, ck, cm), match(qv, pk, pm)
    related = [norm[k]["canonical"] for k, _ in cm_hits if k in norm]
    related += [norm[k].get("title", "") for k, _ in pm_hits if k in norm]
    related = [r for r in related if r][:10]

    queries = expand_query(topic, related)
    found = search_arxiv(queries, intent.get("period_from", ""), intent.get("period_to", ""))
    ledger = upsert_ledger(found)
    new, counts = dedup_new_candidates(found, ledger)
    print(f'"{query}"  →  topic: {topic}')
    print(f"[3][4][5] 검색어 {len(queries)} / 발견 {counts['found']} / "
          f"보유제외 {counts['owned_excluded']} / 신규 {counts['new']}\n")

    # --- [6] 물량 승인 (CLI 임시) ---
    ans = input(f"신규 후보 {counts['new']}편 발견. 관문+추출 진행? (PDF를 받습니다) [y/N]: ").strip().lower()
    if ans != "y":
        print("중단 — 관문/추출 안 함.")
        return

    # --- [7] 관문: 후보 전체 분류 ---
    print("\n[7] 관문(초록만 보고 분류):")
    passed, gate_calls = [], 0
    for aid in new:
        verdict, ok, cached = gate_one(aid, ledger)
        gate_calls += 0 if cached else 1
        mark = "통과" if ok else "—"
        print(f"   {aid} [{verdict:9}] {mark}{' (캐시)' if cached else ''}  {ledger[aid]['title'][:58]}")
        if ok:
            passed.append(aid)
    save_ledger(ledger)
    print(f"   → 통과 {len(passed)}/{len(new)} (관문 LLM {gate_calls}회, 캐시 {len(new) - gate_calls}회)")

    # --- [8] 추출: 통과분 최대 MAX_EXTRACT편 ---
    to_extract = passed[:MAX_EXTRACT]
    if len(passed) > MAX_EXTRACT:
        print(f"\n   상한으로 {MAX_EXTRACT}편만 추출 (통과 {len(passed)}편 중 나머지는 관문 기록만)")
    print(f"\n[8] 추출 {len(to_extract)}편 (PDF 다운로드 시작):")
    extracted = []
    for aid in to_extract:
        ok, msg, concepts = extract_pipeline(aid, ledger)
        if ok:
            extracted.append(aid)
            print(f"   {aid}: {msg} — [{concepts['paper_type']}] "
                  f"defines={[m['name'] for m in concepts['defines']]}")
        else:
            print(f"   {aid}: {msg} (스킵)")  # 실패해도 중단 안 함
    save_ledger(ledger)
    print(f"\n추출 완료 {len(extracted)}편. 노드 반영 필요 시: uv run python src/normalize_v2.py")

    # --- 하드 게이트 ---
    try:
        assert new, "신규 후보 0편 — 관문/추출 검증 불가"
        assert all(ledger[a].get("gate") for a in new), "관문 미기록 후보 있음"
        assert len(extracted) <= MAX_EXTRACT, f"추출 상한 초과: {len(extracted)}"
        for a in extracted:
            assert (config.OUT_DIR / f"{a}.concepts.json").exists() \
                and (config.OUT_DIR / f"{a}.relations.json").exists(), f"{a} 추출 파일 없음"
    except AssertionError as e:
        print(f"\n게이트 실패: {e}", file=sys.stderr)
        sys.exit(1)
    print("게이트 통과: 관문 전체 기록·추출 상한·추출 파일 생성 OK")


if __name__ == "__main__":
    if "--collect-extract-smoke" in sys.argv:
        collect_extract_smoke()
    elif "--collect-smoke" in sys.argv:
        collect_smoke()
    else:
        intent_smoke()
