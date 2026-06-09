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
NORMALIZED_PATH = DATA_DIR / "outputs" / "normalized.json"

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
@app.get("/api/graph")
def get_graph():
    """data/outputs/normalized.json 그대로 반환."""
    if not NORMALIZED_PATH.exists():
        raise HTTPException(500, f"normalized.json 없음: {NORMALIZED_PATH} (먼저 재빌드 필요)")
    return json.loads(NORMALIZED_PATH.read_text())


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
    """src/normalize.py 실행 → 사전 편집 결과를 그래프에 반영(LLM 호출 없음)."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "src" / "normalize.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise HTTPException(500, f"normalize 실패:\n{proc.stderr or proc.stdout}")
    norm = json.loads(NORMALIZED_PATH.read_text())
    return {
        "ok": True,
        "nodes": len(norm.get("nodes", {})),
        "builds_on": len(norm.get("builds_on", [])),
        "stdout": proc.stdout,
    }
