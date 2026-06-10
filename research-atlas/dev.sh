#!/usr/bin/env bash
# 데모 실행: 백엔드(FastAPI :8000) + 프론트(Vite :5173)를 한 번에 띄운다.
# 사용:  ./dev.sh   (또는  bash dev.sh)
# 종료:  Ctrl-C  → 백엔드/프론트 둘 다 정리됨.
set -euo pipefail
cd "$(dirname "$0")"

# 백엔드: vite proxy가 /api → :8000 으로 보내므로 포트 8000 고정.
# --reload 안 씀: 수집 흐름이 인메모리 세션(MemorySaver)이라 재시작되면 진행 중 흐름이 끊김.
uv run uvicorn api.main:app --port 8000 &
BACK=$!

cleanup() {
  echo ""
  echo "[dev] 종료 중… (백엔드 pid $BACK)"
  kill "$BACK" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev] 백엔드 기동 중 (uvicorn :8000, pid $BACK) — 그래프 컴파일에 몇 초 걸립니다."
echo "[dev] 잠시 후 프론트가 열립니다.  브라우저: http://localhost:5173"
echo ""

# 프론트(포그라운드). Ctrl-C 하면 trap이 백엔드까지 정리.
cd web
npm run dev
