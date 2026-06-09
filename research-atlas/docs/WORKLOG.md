# WORKLOG

세션 인계용 개선 로그. 최신이 위.

## 2026-06-09 — 웹 UI (FastAPI + React) 1차 구현

핸드오프 문서대로 결과물(그래프+사전) 웹 조회/편집 UI 구축. `src/` 파이프라인 미수정(normalize.py는 호출만).

**백엔드 `api/main.py` (FastAPI)**
- `GET /api/graph` — `data/outputs/normalized.json` 그대로 반환
- `GET /api/lexicon` — `lexicon.json`의 techniques를 배열로 변환
- `PATCH /api/lexicon/{name}` — 부분 업데이트(status/aliases/definition/source/first_seen)
- `POST /api/lexicon/merge` — `{from,into}`: from(+aliases)을 into의 alias로 흡수 후 from 삭제
- `POST /api/rebuild` — `src/normalize.py`를 subprocess 실행(cwd=루트, MAP 미설정), 노드/계보 수 반환
- CORS: localhost:5173 허용
- deps: `uv add fastapi "uvicorn[standard]"`

**프론트 `web/` (Vite + React + react-router + d3)**
- `/lexicon` (기본) — 표 + 필터(pending 기본)/검색/status 드롭다운(PATCH)/alias 칩 편집/definition textarea/병합(prompt로 대상 지정)/재빌드 버튼+토스트. AI 도우미 버튼은 disabled(준비 중).
- `/graph` — `build_graph.py`의 d3-force 이식. ptype 색, placeholder=빈 원, 엣지=from ptype 색+화살표, zoom/pan/drag, charge -900/link 160·0.3/collide 28. (problem 유사도 슬라이더는 범위 밖 → 제외)
- `/search` — coming soon placeholder
- Vite proxy로 `/api`→8000. `web/{node_modules,dist,.vite}` gitignore 추가.

**검증**: 백엔드 4개 엔드포인트 curl 통과(PATCH 왕복 후 lexicon git-clean 확인), `npm run build` 성공, 두 서버 띄워 5173→8000 프록시로 lexicon(144)/graph(66) 로드 확인.

**실행**: `uv run uvicorn api.main:app --reload --port 8000` + `cd web && npm install && npm run dev`

**남은 일(범위 밖, 미래)**: problem 유사도 슬라이더, /search 동작, AI 도우미 동작.
