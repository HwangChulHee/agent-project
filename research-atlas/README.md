# research-atlas

LLM/RAG/에이전트 연구 논문들의 **지형도(topology)**를 만드는 파이프라인 + 웹 UI.

논문에서 기법(노드)과 계보(`builds_on` 엣지)를 추출해 그래프로 그리고,
노드 후보는 **사전(lexicon)** 으로 거른다. 사전은 모든 개념의 "상태 장부"이며 사람이 승인/거부한다(HITL).

## 구성

- `src/` — 추출/정규화 파이프라인 (fetch → parse → extract → relate → normalize → build_graph)
- `data/lexicon.json` — 사전(상태 장부). 편집 대상.
- `data/outputs/` — 맵 결과 (`normalized.json` 등)
- `api/` — FastAPI 백엔드 (그래프 읽기 + 사전 편집 + 재빌드)
- `web/` — Vite + React UI (사전 편집 / 지형도 / 질의)

## 실행

```bash
# 1) 백엔드 (프로젝트 루트에서)
uv run uvicorn api.main:app --reload --port 8000

# 2) 프론트 (별도 터미널)
cd web
npm install
npm run dev        # Vite dev 서버 → http://localhost:5173
```

`web`의 `/api/*` 요청은 Vite proxy가 `localhost:8000`으로 전달한다.

## 화면

- **`/lexicon`** — 사전 편집. 보류(pending/unreviewed) 개념을 승인/거부/병합.
  status를 바꾼 뒤 **재빌드** 버튼을 눌러야 그래프에 반영된다.
- **`/graph`** — 지형도. 노드 색 = ptype, 빈 원 = 정의 없음, 엣지 = builds_on 계보.
- **`/search`** — 질의 (준비 중).

## API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/graph` | `normalized.json` 반환 |
| GET | `/api/lexicon` | 사전 개념 배열 반환 |
| PATCH | `/api/lexicon/{name}` | 개념 부분 업데이트 (status/aliases/definition…) |
| POST | `/api/lexicon/merge` | `{from, into}` — from을 into의 alias로 병합 후 삭제 |
| POST | `/api/rebuild` | `src/normalize.py` 실행 → 사전 편집을 그래프에 반영 (LLM 호출 없음) |
