"""research-atlas 웹 UI 백엔드.

그래프(읽기 전용)와 사전(편집)을 서빙한다.
파이프라인(src/)은 건드리지 않고, /api/rebuild만 src/normalize.py를 subprocess로 호출한다.

실행:  uv run uvicorn api.main:app --reload --port 8000
"""
import json
import subprocess
import sys
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LEX_PATH = DATA_DIR / "lexicon.json"
NORMALIZED_PATH = DATA_DIR / "outputs" / "normalized.json"        # v1 (롤백용으로만 생성 유지)
NORMALIZED_V2_PATH = DATA_DIR / "outputs" / "normalized_v2.json"  # v2 이중 노드 — 현재 소스

app = FastAPI(title="research-atlas")

# Vite dev 서버(들)에서의 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- lexicon 입출력 헬퍼 ---
def load_lexicon() -> dict:
    """lexicon.json 전체(dict). techniques 키 하위에 개념들."""
    if not LEX_PATH.exists():
        raise HTTPException(500, f"lexicon.json 없음: {LEX_PATH}")
    return json.loads(LEX_PATH.read_text())


def save_lexicon(lex: dict) -> None:
    LEX_PATH.write_text(json.dumps(lex, ensure_ascii=False, indent=2))


# --- 그래프 ---
def _strip(nid: str) -> str:
    """'concept:rk' / 'paper:id' -> 접두사 제거. 접두사 없으면 그대로."""
    return nid.split(":", 1)[1] if ":" in nid else nid


def build_graph_view(include_papers: bool) -> dict:
    """normalized_v2.json(이중 노드) -> 개념 주도 v1 호환 형태로 변환.

    기본(include_papers=False): 개념 노드만 + 개념간 builds_on(유도).
      v1 normalized.json과 호환되는 키/필드 → 프론트 기존 코드 그대로 동작.
    include_papers=True: 위에 더해 논문 노드(paper: 접두사 유지)와 defines 엣지 추가.
    """
    if not NORMALIZED_V2_PATH.exists():
        raise HTTPException(500, f"normalized_v2.json 없음: {NORMALIZED_V2_PATH} (먼저 재빌드 필요)")
    raw = json.loads(NORMALIZED_V2_PATH.read_text())
    v2_nodes, edges = raw["nodes"], raw["edges"]
    papers_meta = {pid: n for pid, n in v2_nodes.items() if n["type"] == "paper"}

    # 개념 노드 → v1 호환 키(접두사 제거)
    out_nodes = {}
    for cid, n in v2_nodes.items():
        if n["type"] != "concept":
            continue
        out_nodes[_strip(cid)] = {
            "canonical": n["canonical"],
            "definition": n.get("definition", ""),
            "def_status": n.get("def_status", "ok"),
            "status": n.get("status"),
            "papers": [],          # 아래에서 채움
            "ptype": "technique",  # defines 논문 paper_type로 유도(없으면 기본)
            "domain": "general",
        }

    # 엣지 순회: 개념별 papers/유도용 그룹 수집
    concept_papers = {}        # rk -> [paper id(접두사 제거), 순서/중복제거]
    concept_home_paper = {}    # rk -> 처음 defines한 paper:id (ptype/domain 유도용)
    defines_first = {}         # paper:id -> 그 논문이 처음 defines한 개념 rk (builds_on source)
    builds_by_paper = {}       # paper:id -> [builds_on 대상 개념 rk]

    for e in edges:
        pid_full, cid_full = e["from"], e["to"]
        pid, rk = _strip(pid_full), _strip(cid_full)
        lst = concept_papers.setdefault(rk, [])
        if pid not in lst:
            lst.append(pid)
        if e["type"] == "defines":
            concept_home_paper.setdefault(rk, pid_full)
            defines_first.setdefault(pid_full, rk)
        elif e["type"] == "builds_on":
            builds_by_paper.setdefault(pid_full, []).append(rk)

    # 개념 노드에 papers/ptype/domain 채우기
    for rk, node in out_nodes.items():
        node["papers"] = concept_papers.get(rk, [])
        home = concept_home_paper.get(rk)
        if home and home in papers_meta:
            node["ptype"] = papers_meta[home].get("paper_type") or "technique"
            node["domain"] = papers_meta[home].get("domain") or "general"

    # 개념간 builds_on 유도: 각 논문의 '첫 정의 개념' → builds_on 대상들.
    # (v1 normalize.py와 동일 규칙: home concept = defs[0]. 자기 루프 제외, 중복 제거)
    seen, builds_on = set(), []
    for pid_full, targets in builds_by_paper.items():
        src = defines_first.get(pid_full)
        if src is None:          # defines 없는 논문 → 개념간 계보 없음
            continue
        for tgt in targets:
            if tgt == src or tgt not in out_nodes:
                continue
            key = (src, tgt)
            if key not in seen:
                seen.add(key)
                builds_on.append({"from": src, "to": tgt})

    view = {"nodes": out_nodes, "builds_on": builds_on}

    if include_papers:
        for pid, n in papers_meta.items():  # pid 예: "paper:1706.03762"
            view["nodes"][pid] = {
                "type": "paper",
                "title": n.get("title", ""),
                "paper_type": n.get("paper_type", "other"),
                "domain": n.get("domain", "general"),
                "problem": n.get("problem", ""),
            }
        defines = []
        for e in edges:
            if e["type"] == "defines" and _strip(e["to"]) in out_nodes:
                defines.append({"from": e["from"], "to": _strip(e["to"])})
        view["defines"] = defines

        # 정의 없는 논문(survey/analysis 등)은 defines 엣지가 없어 고립됨.
        # 그런 논문만 builds_on(논문→개념)으로 닻을 내려준다(이미 연결된 논문은 화면 유지).
        papers_with_defines = {e["from"] for e in edges if e["type"] == "defines"}
        paper_builds_on = []
        for e in edges:
            if (e["type"] == "builds_on"
                    and e["from"] not in papers_with_defines
                    and _strip(e["to"]) in out_nodes):
                paper_builds_on.append({"from": e["from"], "to": _strip(e["to"])})
        view["paper_builds_on"] = paper_builds_on

    return view


@app.get("/api/graph")
def get_graph(papers: bool = False):
    """normalized_v2.json을 개념 주도 형태로 변환해 반환.

    ?papers=true 면 논문 노드 + defines 엣지 추가(토글 표시용).
    """
    return build_graph_view(include_papers=papers)


# --- 사전 ---
@app.get("/api/lexicon")
def get_lexicon():
    """techniques를 배열로 변환해 반환(프론트 편의)."""
    lex = load_lexicon()
    techniques = lex.get("techniques", {})
    return [
        {
            "name": name,
            "aliases": meta.get("aliases", []),
            "status": meta.get("status", "unreviewed"),
            "definition": meta.get("definition", ""),
            "source": meta.get("source", ""),
            "first_seen": meta.get("first_seen", ""),
        }
        for name, meta in techniques.items()
    ]


@app.patch("/api/lexicon/{name}")
def patch_lexicon(name: str, patch: dict = Body(...)):
    """한 개념의 부분 업데이트. 전달된 필드만 수정."""
    lex = load_lexicon()
    techniques = lex.get("techniques", {})
    if name not in techniques:
        raise HTTPException(404, f"개념 없음: {name}")
    editable = {"status", "aliases", "definition", "source", "first_seen"}
    for key, value in patch.items():
        if key in editable:
            techniques[name][key] = value
    save_lexicon(lex)
    return {"ok": True, "name": name, **techniques[name]}


@app.post("/api/lexicon/merge")
def merge_lexicon(body: dict = Body(...)):
    """`from` 개념을 `into`의 alias로 병합하고 `from`은 삭제."""
    src = body.get("from")
    dst = body.get("into")
    if not src or not dst:
        raise HTTPException(400, "from/into 필요")
    if src == dst:
        raise HTTPException(400, "from과 into가 같음")
    lex = load_lexicon()
    techniques = lex.get("techniques", {})
    if src not in techniques:
        raise HTTPException(404, f"from 개념 없음: {src}")
    if dst not in techniques:
        raise HTTPException(404, f"into 개념 없음: {dst}")

    dst_aliases = techniques[dst].get("aliases", [])
    # from 이름 + from의 aliases를 into의 aliases로 흡수(중복 제거, 순서 보존)
    incoming = [src] + techniques[src].get("aliases", [])
    for alias in incoming:
        if alias not in dst_aliases and alias != dst:
            dst_aliases.append(alias)
    techniques[dst]["aliases"] = dst_aliases
    del techniques[src]
    save_lexicon(lex)
    return {"ok": True, "into": dst, "aliases": dst_aliases}


# --- 재빌드 ---
@app.post("/api/rebuild")
def rebuild():
    """normalize.py(v1) + normalize_v2.py(v2) 실행 → 사전 편집을 그래프에 반영(LLM 없음).

    v1 normalized.json도 함께 생성해 롤백 가능 상태 유지. 화면은 v2 변환을 본다.
    """
    for script in ("normalize.py", "normalize_v2.py"):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise HTTPException(500, f"{script} 실패:\n{proc.stderr or proc.stdout}")
    view = build_graph_view(include_papers=False)
    return {
        "ok": True,
        "nodes": len(view["nodes"]),
        "builds_on": len(view["builds_on"]),
    }


# --- 자연어 명령 (필터 에이전트) ---
sys.path.insert(0, str(ROOT))  # agent_filter import용 (uvicorn 실행 위치 무관하게)
from dotenv import load_dotenv
from openai import OpenAI

from agent_filter import TOOLS, build_system_prompt

load_dotenv(ROOT / ".env")
_oai = OpenAI()
COMMAND_MODEL = "gpt-5.4-mini"


@app.post("/api/command")
def command(payload: dict = Body(...)):
    """자연어 명령 -> tool call 번역. 실행은 프론트가 한다.

    반환: {"tool": "filter|focus_lineage|reset", "args": {...}}
          tool call이 안 나오면 {"tool": null, "message": "..."}
    """
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text가 비어 있음")

    view = build_graph_view(include_papers=False)
    names = sorted(v["canonical"] for v in view["nodes"].values())

    resp = _oai.chat.completions.create(
        model=COMMAND_MODEL,
        messages=[
            {"role": "system", "content": build_system_prompt(names)},
            {"role": "user", "content": text},
        ],
        tools=TOOLS,
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return {"tool": None, "message": (msg.content or "")[:200]}

    tc = msg.tool_calls[0]
    try:
        args = json.loads(tc.function.arguments or "{}")
    except json.JSONDecodeError:
        raise HTTPException(502, f"tool 인자 파싱 실패: {tc.function.arguments}")

    # focus_lineage의 node가 실재하는지 백엔드에서 한 번 더 검증
    if tc.function.name == "focus_lineage":
        canon_set = {n.lower() for n in names}
        if (args.get("node") or "").lower() not in canon_set:
            return {"tool": None, "message": f"'{args.get('node')}' 노드를 찾지 못함"}

    return {"tool": tc.function.name, "args": args}
