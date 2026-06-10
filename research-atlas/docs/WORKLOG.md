# WORKLOG

세션 인계용 개선 로그. 최신이 위.

## 2026-06-10 — UI 개선: 라이트 테마 + 스케일업 + 레이아웃 정리

스타일·표시만. 채팅/필터/계보 동작 로직 미변경. `web/src/styles.css` · `routes/Graph.jsx`.

**라이트 테마(전역)** `styles.css`
- `:root` 교체(웜 오프화이트 `#f7f7f5`/패널 `#fff`/accent `#2563eb`). `--accent-fg`(accent 위 글씨)·`--hover`·`--shadow`·`--mono` 추가. 다크 하드코딩(#16161a/#1f1f26/#2a2a33/#14141a/#08121a 등) 전수 변수화. body 폰트 mono→system-ui 산세리프, 13→14px. badge/toast/matched 행은 라이트 톤(blue-100, green/red-100 등). /lexicon source·first_seen 열만 `--mono` 유지(arXiv ID).
- 노드색 라이트용 교체(Graph.jsx TYPE_COLOR): technique #2563eb / benchmark #d97706 / analysis #7c3aed / survey #059669.
- placeholder 노드: fill #fff + 점선 테두리(`stroke-dasharray "3 2"`, stroke=type색). 범례 dot도 흰 바탕+점선.

**스케일업** `Graph.jsx`
- 노드 r 10→12(focus 18, ~1.5× 유지), 라벨 11→13px·fill `--text`·x오프셋 13→16, `forceCollide` 28→30.

**필터 시 엣지 표시** `Graph.jsx highlight()`
- 비매칭 엣지를 opacity 0.06 → **`display:none`**(화살촉만 또렷이 남던 문제 해결). 매칭(양끝) 엣지만 표시, 비매칭 노드는 흐림 0.18(숨김 아님). reset 시 `display:null` 복원.

**레이아웃** `styles.css`
- 검색창 top-center→**좌상단**, 범례→**좌하단**, 노드 디테일 패널 우측 풀하이트→**좌측 카드**(검색창 아래, max-height로 범례와 비충돌), 활성 칩→상단 중앙. 오버레이 전부 border+`--shadow`로 분리. 오른쪽은 채팅 단독.

**검증**: `npm run build` 성공 + Playwright 스크린샷 3종 육안 확인 — (1) /graph·/lexicon 라이트, 다크 잔재 없음 (2) placeholder kNN-LM 흰 점선 원 (3) "벤치마크만" 필터 시 비매칭 노드 흐림·**화살표 전부 사라짐**·칩 표시·버블 "benchmark · 3개 강조".

## 2026-06-10 — `/graph` 채팅 패널(필터 에이전트 프론트)

핸드오프대로 프론트만. 백엔드 `POST /api/command`(이미 구현·검증)는 미수정.

**레이아웃** `web/src/routes/Graph.jsx` · `styles.css`
- `.graph-page`를 flex 가로 분할: `.graph-area`(flex 1, 기존 svg·검색·범례·디테일 패널을 그 안의 absolute 오버레이로 이동) + `.chat-panel`(320px 고정).
- 패널 접기 토글(`>`/`<`). 접으면 그래프 전체 폭. svg 크기는 `window.innerWidth` 대신 `.graph-area` 측정으로 변경하고 `ResizeObserver`로 접기/리사이즈 시 svg·forceCenter 갱신(`sim.alpha(0.2).restart()`).

**채팅→그래프** (LLM 추가 호출 없이 프론트 템플릿)
- `api.js`에 `postCommand(text)` 추가. 입력→사용자 버블→`/api/command`→대기「…」→tool 실행→에이전트 버블.
- `render()`가 `{sim, focus, names, highlight, resize}` 반환(기존 3개에 highlight·resize 추가). 강조=opacity만 입힘(매칭 1·비매칭 0.12, 엣지는 양끝 매칭 시만 0.65 아니면 0.06). 시뮬레이션 재시작 없음.
- `filter`: 노드 속성 AND 매칭. `date_after`는 papers의 arXiv ID 앞4자리→연월 중 **최소값** 기준, papers 빈 placeholder는 비매칭. 0개면 강조 변경 없이 「조건에 맞는 노드가 없음」.
- `focus_lineage`: `builds_on{from,to}`(to=조상) JS 순회, ancestors/descendants/both, visited로 사이클 방지. node 소문자화해 키 매칭, 없으면 메시지.
- `reset`: 강조 해제. 활성 조건은 좌상단 칩(✕=reset)으로 표시.
- `tool:null`/네트워크 실패는 에이전트 버블로 표시.

**검증**: `npm run build` 성공. `/api/command` 실제 응답 4종(filter ptype/date_after, focus_lineage, ) 프론트 기대 형태와 일치 확인. 데이터 정합: `rag` 키 존재, benchmark 3·date≥2024-01 20개 매칭. 브라우저 수용기준은 미실행(서버 기동 확인까지).

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
