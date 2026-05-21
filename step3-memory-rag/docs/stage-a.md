# Stage A — Structure-aware Chunking + Parent-Child Hierarchy

## 목적

베이스라인 RAG의 두 한계를 공략:

1. **섹션 경계 무시** — 800자 고정 청킹이 의미 단위를 무시해 단일 청크에 무관한 주제가 섞임. 임베딩 벡터가 평균화되어 정밀도 저하.
2. **청크 크기 트레이드오프** — 큰 청크는 LLM 맥락에는 좋으나 검색 임베딩이 흐려짐. 작은 청크는 반대. 베이스라인 800자는 어정쩡한 절충.

## 적용 기법

### 1. Structure-aware chunking

Wikipedia 원문의 `== 헤더 ==` 문법을 Markdown `## 헤더`로 변환 후 `MarkdownNodeParser`로 섹션 단위 분할. 각 청크가 단일 주제(예: `## Awards and honors` 섹션 통째)를 담는다.

### 2. Parent-child hierarchical retrieval

섹션 parent와 sentence-level leaf의 2-tier 구조. ChromaDB에는 leaf만 임베딩되어 인덱싱되고, parent 텍스트는 사이드카 JSON에 보관. 검색 시 leaf hit → 메타데이터의 `parent_id` → 사이드카에서 parent 텍스트 hydration → LLM에 전달.

용어: LlamaIndex "auto-merging retrieval", LangChain "parent-document retrieval", 학계/블로그 "small-to-big retrieval". 동일 패턴.

## 구현

### 파이프라인

```
data/wikipedia/*.txt
    │
    ▼ scripts/convert_to_markdown.py  (== → ##)
data/wikipedia_md/*.md
    │
    ▼ scripts/build_index_hierarchical.py
    │   ├─ MarkdownNodeParser  → 292 section parents
    │   ├─ SentenceSplitter    → 584 leaves (MIN_LEAF_CHARS=80 필터)
    │   └─ SentenceTransformer → 384-dim 임베딩
    ▼
chroma_db/                    (collection: wikipedia_hierarchical)
chroma_db/hier_nodes.json     (parent 사이드카)
```

### 주요 파라미터

| 파라미터 | 값 | 비고 |
|---|---|---|
| `LEAF_CHUNK_SIZE` | 256자 | `SentenceSplitter` |
| `LEAF_OVERLAP` | 32자 | 문장 경계 보존 |
| `MIN_LEAF_CHARS` | 80자 | `## See also` 등 헤더-only 청크 제거 |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` | 베이스라인과 동일 (변수 통제) |
| Distance | cosine | ChromaDB HNSW |

### 라이브러리 위임 / 직접 구현 경계

- 위임: `llama-index-core==0.14.22` — chunking 알고리즘 (`MarkdownNodeParser`, `SentenceSplitter`)
- 유지: `chromadb`, `sentence-transformers` — 베이스라인과 동일
- 직접: 인덱서 인터페이스, 검증 스크립트, parent hydration 로직, 결과 분석

## 결과

### 인덱싱 통계

| | Baseline | Stage A |
|---|---|---|
| 청킹 기준 | 800자 고정 | 섹션 헤더 + 256자 sentence-split |
| 임베딩 청크 수 | 729 | 584 |
| 평균 청크 길이 | ~800자 | ~250-500자 (가변) |
| 메타데이터 | `doc_id` 누락 | `doc_id`, `parent_id` 보존 |
| Parent 사이드카 | — | 292 sections |

### 검증 쿼리 distance (top-1)

| 쿼리 | Baseline | Stage A | Δ |
|---|---|---|---|
| `Einstein Nobel` (en) | 0.2617 | 0.2806 | +7.2% |
| `퀴리 부인 원소` (ko) | 0.5145 | 0.5031 | -2.2% |

### Top-3 매칭 품질 (정성)

`Einstein Nobel` — **Baseline top-3**:

1. "1921 met the criteria set by Alfred Nobel..." (Nobel 위원회 절차 단편)
2. "formally awarded his PhD on 15 January 1906..." (Nobel 무관)
3. "Wave–particle duality... patent office..." (Nobel 무관)

`Einstein Nobel` — **Stage A top-3**:

1. "Einstein was formally awarded his PhD..." (1905 annus mirabilis 단락, 474자)
2. **`## Awards and honors` 섹션 통째 (522자) — "1922, he was awarded the 1921 Nobel Prize..."**
3. `#### Wave–particle duality` 섹션 헤더 포함

Stage A는 distance 절대값이 미세하게 높지만, top-2에서 `## Awards and honors` 섹션 전체를 응집된 단위로 적중. 베이스라인 top-3는 "Nobel" 단어가 들어간 파편들로, 의미 매칭보다 단어 매칭에 가까움.

### Parent hydration 검증

`Einstein Nobel` 쿼리:

| Hit | Leaf 길이 | Parent 길이 | 확장 비율 | Parent 섹션 |
|---|---|---|---|---|
| #1 | 474자 | 1205자 | 2.5× | `### First scientific papers (1900–1905)` |
| #2 | 522자 | 522자 | 1.0× | `## Awards and honors` (섹션 자체가 작음) |

Hit #1은 좁은 leaf(annus mirabilis 단락)가 넓은 parent 맥락(1900-1905 첫 논문 시기 전체)으로 확장. Hit #2는 섹션 자체가 작아 leaf=parent. 작은 섹션은 강제로 쪼개지 않는 자연스러운 동작.

## 분석

### 작동한 것

- **섹션 응집**: `## Awards and honors`가 통째로 단일 청크화 → 임베딩이 단일 주제 벡터
- **Parent hydration**: 좁은 leaf 검색 → 풍부한 parent 맥락으로 자동 확장 (평균 1.5~3배)
- **메타데이터 보존**: `doc_id`, `parent_id`가 검색 결과에 동행 → 추후 LLM 단계의 인용·트레이싱 가능

### 한계

- 영어 distance 절대값은 베이스라인 대비 +7% 악화. 256자 leaf가 800자 청크보다 의미 밀도 낮음. 정성 품질은 개선되었으나 정량 신호로는 명확히 안 잡힘.
- 한국어 쿼리는 distance 변화 거의 없음 (0.5031). 다국어 임베딩의 cross-lingual 약점은 Stage A 범위 밖.

### Stage B로 이월

- 한국어 쿼리 약점 → Contextual Retrieval로 청크에 LLM 요약 prepend
- 키워드 매칭(인명, 고유명사) 보강 → Stage C BM25 하이브리드

## 파일

```
scripts/
├── fetch_wikipedia.py             # 8개 인물 페이지 다운로드 (베이스라인과 공유)
├── build_index.py                 # 베이스라인 인덱서 (collection: wikipedia)
├── convert_to_markdown.py         # Stage A — == → ## 변환
├── build_index_hierarchical.py    # Stage A — 인덱서 (collection: wikipedia_hierarchical)
├── compare_stage_a.py             # 검증 — baseline vs Stage A distance 비교
└── verify_hydration.py            # 검증 — parent hydration 작동 확인

data/
├── wikipedia/*.txt                # Wikipedia 원문
└── wikipedia_md/*.md              # Markdown 변환

chroma_db/
├── chroma.sqlite3                 # baseline + Stage A 두 collection
└── hier_nodes.json                # Stage A parent 사이드카
```

## 재현

```bash
# 1. 데이터 준비
uv run python scripts/fetch_wikipedia.py
uv run python scripts/convert_to_markdown.py

# 2. 인덱싱 (베이스라인 + Stage A)
uv run python scripts/build_index.py
uv run python scripts/build_index_hierarchical.py

# 3. 검증
uv run python scripts/compare_stage_a.py
uv run python scripts/verify_hydration.py
```

## 다음 단계

Stage B — Contextual Retrieval (Anthropic, 2024). 각 leaf에 LLM이 생성한 한 줄 요약("이 청크가 어느 문서의 어느 부분이고 무엇을 다룸") prepend 후 임베딩. 한국어 쿼리 약점 직접 공략.