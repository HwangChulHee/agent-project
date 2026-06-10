# WORKLOG

세션 인계용 개선 로그. 최신이 위.

## 2026-06-11 — 수집 에이전트 [3][4][5]: 검색어 확장 + arXiv 검색 + 장부/중복제거

의도 파싱(topic) → arXiv 신규 후보 목록까지. PDF·관문·추출은 다음 조각.

- **[3] `expand_query(topic, related_terms)`**: LLM 1회로 topic을 arXiv 검색어 5~8개로 확장. [2] 현황확인의 보유 개념/논문 canonical을 재료로 넘겨 맵 밀착.
- **[4] `search_arxiv(queries, period_from, period_to, max_per_query=50)`**: export.arxiv.org Atom API(feedparser 파싱). 요청 사이 3초 sleep(rate limit), 순차. arXiv ID 버전접미사(`v\d+`) 제거 정규화, 검색어 간 ID dedup, period는 클라이언트단 필터.
  - **함정 발견·수정**: 핸드오프 스펙 `all:<검색어>`(따옴표 없음)는 다단어를 토큰 OR로 풀어, submittedDate 정렬 시 **무관한 최신 논문 firehose**가 떴음(첫 스모크 184편 전부 노이즈: Low-Light Video, Lattice QCD…). → **구문 검색 `all:"<검색어>"`**(따옴표)로 수정. 재스모크 22편 전부 RAG robustness 관련. 변형 A/B/C 직접 대조로 확인.
- **papers.json 장부**(신규): "한 번이라도 검색에 걸린 논문" 장부(lexicon의 논문판). upsert로 메타 갱신, gate/extracted/first_seen_query 보존.
- **[5] `dedup_new_candidates`**: found에서 (1)지도 보유(normalized_v2 paper 노드), (2)관문 탈락(gate.verdict∈reject) 제외 → 신규 후보 + 카운트.
- `--collect-smoke` 플래그로 [1][2] 스모크(`intent_smoke`)와 분리.

**스모크 결과**: 검색어 8개(robust RAG·failure modes·self-correcting·benchmarking reliability 등 다양). arXiv 발견 22편, 샘플 3편 모두 RAG robustness 주제, 메타 정상. dedup: 발견 22/보유제외 0/신규 22. 게이트 4종 통과. 보유 dedup은 이번 검색에 보유 논문이 안 걸려 자연 관찰 불가 → **주입 테스트로 로직 검증**(보유 1706.03762 제외·관문탈락 제외·신규 산출 OK).

다음 조각: [6]물량승인 + [7]관문 + [8]추출(PDF 받기 시작). papers.json의 gate/extracted를 거기서 채움.

## 2026-06-11 — 논문 보기: 정의없는 논문 닻 내리기

"논문 보기 ON인데 일부 논문이 안 보인다" 지적. 원인: 논문은 `defines`(논문→개념)로만 그래프에 붙는데, survey/analysis처럼 새 기법을 정의하지 않는 논문 4편은 엣지가 없어 고립(라벨 없는 r6 회색 점이라 사실상 안 보임).

- 기준 명확화: 논문 연결 = `defines`. 64편은 정의로 연결, 4편(2001.08361·2312.10997·2401.14887·2408.08921)은 정의 없음.
- 수정(`api/main.py`): `?papers=true`에 **정의없는 논문만** `builds_on`(논문→개념)으로 닻 내리는 `paper_builds_on` 추가. 이미 연결된 64편은 그대로(화면 회귀 0). 결과: 3편 닻 내림, 2001.08361만 데이터상 정의·참조 둘 다 없어 고립 잔존.
- 프론트(`Graph.jsx`): 링크 스타일을 `kind==='builds_on'`(개념↔개념=색 실선+화살표) vs 그 외(`defines`·`paper_builds_on`=옅은 점선)로 정리.

**검증**: build 성공. `?papers=true` → defines 73 · paper_builds_on 3 · 고립 1(2001.08361). 기본뷰엔 paper_builds_on 키 없음.

## 2026-06-11 — 수집 에이전트 v2 재배치 (전환 4/4)

`agent_collect.py`를 v2 이중 노드 임베딩 위로 옮기고, 현황 확인을 **두 각도**로 확장 + **현황 보고 + 충분성 추천** 생성. arXiv 실제 수집은 다음 조각.

- 임베딩 로더 v1→v2: `node_embeddings_v2.json`을 개념(`concept:`)·논문(`paper:`)으로 **타입 분리**해 각각 정규화 행렬. v1 파일(node_embeddings.json·normalized.json) 더는 안 읽음.
- 두 각도 매칭: topic 임베딩 1회 → **개념(definition) 매칭** "관련 기법이 뭐 있나" + **논문(problem) 매칭** "같은 문제 다룬 논문이 뭐 있나"(세렌디피티). floor=0.30 컷, top=8.
- `build_status_report()`(LLM 1회): 매칭 상위의 definition/problem을 묶어 주제 관점 풀이 + 종합 판정 + 충분성 추천(충분/부분적/비어있음). placeholder 개념은 "정의 미보유"로 짧게. `confirm_message()` 대체.
- 스모크를 **하드 게이트**로: model·개념73·논문68 assert 실패 시 exit 1.

**스모크 결과**(쿼리당 LLM 2회 + 임베딩 1):
- 게이트 통과: 개념 73 + 논문 68.
- "knowledge graph 만들기" → 개념 상위에 **GraphRAG(0.54)·HippoRAG(0.51)·LightRAG(0.43)·HyperGraphRAG** 등장(v2 definition 매칭의 핵심 증거).
- 논문(problem) 매칭이 개념과 **다른 항목**도 포착: RAG강건성에서 "The Power of Noise"·RAGBench, 멀티에이전트에서 Switch Transformers·Constitutional AI 등 — problem 각도가 definition과 다른 정보 제공.
- 보고가 나열이 아닌 풀이+종합+추천 형태, floor 아래(<0.30) 노드 미혼입(최저 0.34).

다음 조각: 실제 arXiv 검색/수집/승인 + LangGraph 분기(설명/수집/수정). 충분성은 이번엔 **추천만**, 자동 결정 아님.

## 2026-06-11 — API·프론트 v1→v2 전환 (전환 3/4)

API가 `normalized_v2.json`(이중 노드)을 읽어 **개념 주도 v1 호환 형태로 변환**해 서빙. 프론트는 최소 수정 + "논문 보기" 토글. 회귀 최소화 우선.

**API (`api/main.py`)**
- `build_graph_view(include_papers)` 신설: v2 → 개념 노드(접두사 제거) + 개념간 builds_on 유도.
  - **builds_on 유도 결정**: 핸드오프는 D×B 교차곱을 명시했으나, v1 normalize.py는 실제로 **'첫 정의 개념'(defs[0])만 source**로 씀을 확인. 교차곱은 v1과 +17 엣지(다중정의 논문 9개에서) 차이 → 시각 회귀. 사용자 확인 후 **첫 정의(defs[0]×B)** 채택. 결과 113 엣지 = v1과 113/113 정확 일치(파생-only 0). v1-only 4는 paper 의사노드 소스 3 + `replug→replug` 자기루프 1(v2가 올바르게 제거).
  - ptype/domain: 그 개념을 defines한 첫 home 논문의 paper_type/domain(없으면 technique/general). papers: defines·builds_on로 언급한 논문 id.
- `GET /api/graph?papers=true`: 논문 노드(`paper:` 접두사 유지) + defines 엣지 추가. 기본 응답엔 defines 키 없음.
- `/api/rebuild`: normalize.py + normalize_v2.py **둘 다** 실행(v1 normalized.json도 생성 → 롤백 가능). `/api/command`: 노드명 소스를 v1 normalized.json → v2 변환본으로 교체. **코드가 더는 v1 파일을 읽지 않음**(NORMALIZED_PATH는 정의만 남음).

**프론트 (`web/src/`)**
- `api.js`: `getGraph(withPapers)` → `?papers=`.
- `Graph.jsx`: "논문 보기" 토글(범례 내, 기본 OFF). ON이면 재로드 → 논문=작은 회색 점(r6), defines=옅은 점선. 논문 클릭 시 디테일 패널에 title/paper_type/problem/arXiv. 검색·필터·계보는 **개념만**(applyFilter가 `type==='paper'` 스킵, names 개념만). 토글 시 강조/선택 초기화.

**검증**: `npm run build` 성공. 라이브 서버: 기본 `/api/graph` = 개념 122·builds_on 113·defines 키 없음·paper 키 없음. `?papers=true` = 논문 68·defines 73. `/api/command` 다보여줘→reset, RAG 계보→focus_lineage(RAG), asdf→tool:null. 보호 파일(normalize*.py·normalized.json·lexicon.json·v1 임베딩) 무변경.
- **기본뷰 122 vs v1 126 = 의사노드 4 차이**: v1이 개념처럼 그리던 define-없는 논문 4개(2001.08361·2312.10997·2401.14887·2408.08921)가 이제 "논문 보기" 토글의 진짜 논문 노드로 이동. 개념 지형도는 동일 — 전환의 의도된 결과.

다음: 수집 에이전트 재배치(4/4) — agent_collect.py를 v2 위에, 현황 확인을 개념+논문 이중 매칭으로.

## 2026-06-10 — embed_nodes_v2: 이중 노드 타입별 임베딩 (전환 2/4)

`normalized_v2.json`(190노드)를 타입별로 임베딩. 개념→definition, 논문→problem.

- `src/embed_nodes_v2.py` 신규. 개념 노드는 **순수 definition 텍스트만** 임베딩(canonical 이름 미부착 — "RAG" 류 철자 오염 방지), 논문 노드는 problem 임베딩.
- placeholder 개념(정의 없음, 49개)은 제외. 수집으로 정의 채워지면 자동 합류(증분).
- 모델명을 파일에 기록 → 같은 모델이면 영구 재사용, 바뀌면 전체 재생성(Neo4j 이관 시 재계산 불필요). 증분 캐시: 이미 임베딩된 id 건너뜀, `--force`로 전체.
- 출력: `data/outputs/node_embeddings_v2.json` = `{model, dim, vectors}`. v1 `node_embeddings.json`은 무변경(3/4에서 전환).

**검증**: `uv run python src/embed_nodes_v2.py` → 논문 68 + 개념 73 = 141 / dim 1536. 수용 기준 6종 통과: 임베딩 개념수=정의있는개념수(73=122−49), 임베딩 논문수=전체논문(68), dim 1536, model 기록됨, 재실행 시 "신규 0개", `--force`로 141개 재생성. normalize.py·normalized.json·lexicon.json 무변경.

다음: API/프론트 v1→v2 전환(3/4) → 수집 재배치(4/4).

## 2026-06-10 — normalize_v2: 이중 노드(논문+개념) 데이터 토대 (전환 1/4)

개념 단일 노드 → **이중 노드(paper + concept)** 전환의 데이터 재조립 단계. LLM 호출 없음, 기존 파일 무변경.

- `src/normalize_v2.py` 신규. `*.concepts.json`(논문 속성)·`*.relations.json`(builds_on)을 재조립해 `data/outputs/normalized_v2.json` 생성.
- problem→논문 노드, definition→개념 노드로 귀속 분리. id에 `paper:`/`concept:` 접두사, 엣지는 `{type, from, to}` 단일 배열(defines·builds_on). 모든 엣지 `paper:* → concept:*` 방향.
- 거름망은 개념에만(lexicon status approved/unreviewed). 논문은 전부 노드. 빈 링 개념은 `def_status=placeholder`로 계보 보존.
- `normalize.py`에서 canon/load_lexicon/save_lexicon/NODE_OK import 재사용(규칙 단일 출처). normalize.py 무수정.

**검증**: `uv run python src/normalize_v2.py` → 논문 68 + 개념 122 = 노드 190 / 엣지 191(defines 73·builds_on 118) / 빈 링 49 / **사전 신규 {unreviewed:0, pending:0}**. 수용 기준 6종 통과: 논문수=concepts파일수(68), 엣지 방향 위반 0, paper 노드 problem/title·concept 노드 canonical/definition 보유, `lexicon.json`·`normalized.json` git diff 무변경(롤백 가능).

다음: 임베딩 분리(2/4) → API/프론트(3/4) → 수집 재배치(4/4).

## 2026-06-10 — UI 개선 4종: 그래프 자동맞춤·노드 디테일·채팅 예시칩·사전 zebra

`web/src/routes/Graph.jsx` · `styles.css`. 사용자가 4개 모두 선택.

**1) 그래프 자동 맞춤** — `render()`에 `fitView(animate)` 추가(노드 x/y bbox→줌 transform, 라벨 여백 위해 padX 160·padY 90, k 상한 1.6). 로드 시 sim `alphaDecay(0.05)`로 ~2초 빨리 안정 후 `on("end")` 1회 자동 맞춤(드래그 재안정 땐 `didFit` 가드로 재맞춤 안 함). 좌상단 svg 위 "⤢ 전체 보기" 버튼이 `apiRef.fitView()` 호출.
  - 시행착오: 동기 `sim.tick()` 루프 사전안정은 forceCenter만으론 비연결 노드가 멀리 튀어(blow-out→speck) 폐기. forceX/Y(0.05) 복원력은 charge를 눌러 클럼프 붕괴→폐기. 원래 force(-900) 유지 + alphaDecay만 올려 timer-driven end 맞춤이 정답(스샷 확인 양호).
**2) 노드 디테일** — 미선택 시 카드 숨김(기존 "지형도/클릭하세요" 제거). type 색 배지(`.type-badge`), papers를 arXiv 링크(`https://arxiv.org/abs/{id}`), 닫기 ✕(`detail-close`).
**3) 채팅 예시 칩** — 빈 상태에 클릭 가능한 예시 4종(벤치마크/RAG 계보/2024 이후/다 보여줘). `sendCommand`를 `runCommand(text)`+`onSubmit`으로 분리해 칩이 직접 실행.
**4) 사전 가독성** — tbody 짝수행 zebra(`#f1f1ec`), sticky th 그림자.

**검증**: build 성공 + Playwright 스샷 — 자동맞춤(전체 노드 프레이밍), 디테일(InstructGPT 배지+arXiv 링크+닫기), 예시칩 클릭→필터 적용(칩+버블+노드 강조), 사전 zebra 확인.

## 2026-06-10 — UI 미세조정: 뷰포트 꽉채움 + 채팅 확대 + 브랜드 확대

`styles.css`만. 스크롤바/잘림 원인은 `.graph-page`의 `width:100vw`(스크롤바 폭 포함→가로바)와 하드코딩 `calc(100vh-41px)`(14px 폰트로 nav 실제 높이>41px→세로 오버플로).
- 앱 셸을 세로 플렉스로: `html,body,#root{height:100%}`, `body{overflow:hidden}`, `#root{display:flex;flex-direction:column}`. nav `flex:0 0 auto`. 라우트 컨테이너(`.graph-page`/`.lex-wrap`/`.center-msg`)는 `flex:1; min-height:0`로 잔여 공간 정확히 채우고 내부 스크롤. `.graph-page`의 100vw·calc 제거 → `width:100%`.
- Playwright로 /graph·/lexicon 모두 scrollWidth==clientWidth·scrollHeight==clientHeight(오버플로 없음) 확인.
- 채팅 패널 320→420px. 브랜드 `.nav .brand` 19px bold.

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
