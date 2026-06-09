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

## 2026-06-09 — 웹 UI 2차: 노드/사전 검색·이동·정렬

핸드오프 v2 3건. 백엔드(`api/`)·파이프라인(`src/`) 미수정, 프론트만.

**`/graph` 노드 검색→이동(핵심)** `web/src/routes/Graph.jsx`
- svg 상단 중앙 검색창(`form`). `canonical` 부분일치(대소문자 무시).
- `render()`가 `{sim, focus, names}` 반환하도록 변경(기존엔 sim만). `zoom` 핸들러를 변수로 잡아 `focus(id)`에서 `zoom.transform`을 500ms transition으로 호출 → 해당 노드를 화면 중앙(scale 1.5)으로 이동. 강조: 해당 circle만 stroke-width 5·r 15.
- 매칭 0=「없음」, 1=바로 이동, 여러개=검색창 아래 매칭 목록(클릭 이동) + 같은 검색어로 Enter 반복 시 다음 매칭 순회. 이동 시 사이드 패널(`setSelected`)도 갱신.
- 노드 키는 canon 소문자(`n.id`)로 focus, 검색·표시는 `n.canonical`.

**`/lexicon` 정렬** `web/src/routes/Lexicon.jsx`
- 헤더 클릭 정렬(name/status/source/first_seen) 오름/내림 토글 + ▲/▼ 표시. aliases·definition·액션은 비정렬.
- 정렬은 현재 status 필터 적용 후의 목록에 대해 동작.

**`/lexicon` 검색 강화**
- 검색을 **숨김 필터 → 강조 방식**으로 변경: 비매칭을 숨기지 않고 매칭 행에 `.matched`(배경 강조) + 첫 매칭으로 `scrollIntoView`(smooth, center). 툴바에 「N건 매칭/매칭 없음」 표시.
- 검색+정렬+상태필터 동시 동작(필터→정렬된 목록 안에서 강조).

**검증**: `npm run build` 성공. `normalized.json` 노드 키=canon소문자·`canonical`=표시명 확인(focus 로직 전제 일치).
