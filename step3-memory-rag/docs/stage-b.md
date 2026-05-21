# Stage B — Contextual Retrieval

## 목적

Stage A의 두 한계 공략:

1. **검색 시 어휘 매칭 의존** — leaf 텍스트 자체에 인명/주제어가 부족하면 임베딩이 일반적인 좌표로 머무름. 정답 섹션이 있어도 단어 단편이 더 가까운 거리로 잡힘.
2. **다국어 cross-lingual 약점** — `paraphrase-multilingual-MiniLM-L12-v2`가 "퀴리 부인" ↔ "Marie Curie" 같은 1:1 인명 번역은 어느 정도 잡지만, "원소" ↔ "polonium, radium" 같은 일반어 → 고유명사 매칭은 약함.

## 적용 기법

### Contextual Retrieval (Anthropic, 2024)

각 leaf에 대해 LLM이 "이 청크가 어느 문서의 어느 부분이고 무엇을 다룸"을 한두 문장으로 생성. 이 컨텍스트를 leaf 앞에 prepend한 텍스트를 **임베딩 입력**으로 사용. ChromaDB에 저장되는 `documents` 필드는 여전히 원본 leaf — 컨텍스트는 임베딩 좌표 보정용으로만 쓰이고 LLM에 전달되지 않음.

핵심 메커니즘: 컨텍스트 문장이 인명/섹션명/주제어를 풀어쓴 영어로 들어가서, (context + leaf)의 임베딩이 의미공간에서 쿼리 벡터에 더 가까운 좌표로 끌려감.

원본 프롬프트:
```
<document>
{전체 문서}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{leaf 텍스트}
</chunk>

Please give a short succinct context to situate this chunk within
the overall document for the purposes of improving search retrieval
of the chunk. Answer only with the succinct context and nothing else.
```

## 구현

### 파이프라인

```
data/wikipedia_md/*.md
    │
    ▼ rag/leaves.py::build_leaves()  (Stage A와 공유)
584 leaves
    │
    ▼ scripts/generate_contexts.py
    │   - AsyncOpenAI, concurrency=8
    │   - doc_id 정렬로 vLLM prefix cache 활용
    │   - 점진적 JSON 저장 (중단 복구)
    ▼
chroma_db/contexts.json          (584 contexts, ~70초 소요)
    │
    ▼ scripts/build_index_contextual.py
    │   - embed_input = f"{context}\n\n{leaf_text}"
    │   - ChromaDB documents 필드는 원본 leaf만 저장
    ▼
chroma_db/                       (collection: wikipedia_contextual)
```

### 주요 파라미터

| 파라미터 | 값 | 비고 |
|---|---|---|
| LLM | `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit` | vLLM 로컬, thinking off |
| Concurrency | 8 | AsyncOpenAI Semaphore |
| Max output tokens | 200 | 컨텍스트 평균 ~150자 |
| Embedding model | `paraphrase-multilingual-MiniLM-L12-v2` | Stage A와 동일 (변수 통제) |
| Prepend 형식 | `{context}\n\n{leaf}` | 빈 줄로 분리 |

### 라이브러리 위임 / 직접 구현 경계

- 위임: `openai` AsyncClient (vLLM 호출), 임베딩 라이브러리 (Stage A와 동일)
- 직접: 비동기 배치 오케스트레이션, prefix cache 활용 위한 정렬, 점진 저장 로직, 2축 실험 설계

### 리팩토링

- `rag/leaves.py` 신설 — Stage A 인덱서와 Stage B 컨텍스트 생성기/인덱서가 동일 leaf 시퀀스를 보장하도록 공통 함수로 추출.
- Stage A 인덱서도 이 모듈로 마이그레이션.

## 결과

### 컨텍스트 생성 통계

| 항목 | 값 |
|---|---|
| Leaves 처리 | 584 |
| 총 소요 시간 | 70초 |
| 처리 속도 | 8.3 leaf/s |
| 평균 컨텍스트 길이 | 220자 |
| 단일 leaf 호출 시간 (캘리브레이션) | 8.3초 |
| 가속 비율 | ~58배 (concurrency 8 + prefix cache) |

### 2축 실험 설계

가설을 분리하기 위해 5가지 (검색 × LLM 응답) 조합을 비교:

| ID | Embedding | LLM 컨텍스트 | 가설 |
|---|---|---|---|
| BL | Baseline 800자 | 매칭 800자 그대로 | 기준선 |
| A-L | Stage A (leaf 256) | leaf만 | A 임베딩만 평가 |
| A-P | Stage A | parent hydration | Stage A 정식 |
| B-L | Stage B (context+leaf) | leaf만 | H2 검증 |
| B-P | Stage B | parent hydration | Stage B 정식 |

핵심 비교쌍:
- A-P vs B-P: H1 (context prepend가 검색 강화?)
- B-L vs B-P: H2 (parent hydration 여전히 필요?)

### Distance 결과 (top-1)

쿼리 `"Einstein Nobel"`:

| ID | distance | doc | LLM_len |
|---|---|---|---|
| BL | 0.2617 | ? | 800 |
| A-L | 0.2806 | Albert_Einstein | 474 |
| A-P | 0.2806 | Albert_Einstein | 1205 |
| B-L | 0.2708 | Albert_Einstein | 522 |
| B-P | 0.2708 | Albert_Einstein | 522 |

쿼리 `"퀴리 부인 원소"`:

| ID | distance | doc | LLM_len |
|---|---|---|---|
| BL | 0.5145 | ? | 800 |
| A-L | 0.5031 | Marie_Curie | 654 |
| A-P | 0.5031 | Marie_Curie | 2079 |
| B-L | 0.5182 | Marie_Curie | 804 |
| B-P | 0.5182 | Marie_Curie | 804 |

### 정성 분석 — 매칭 leaf 비교

**`"Einstein Nobel"`:**

- **Baseline top-1**: "...1921 met the criteria set by Alfred Nobel, so the 1921 prize was carried forward..." — Nobel 위원회 절차 부스러기
- **Stage A top-1**: "(Einstein was formally awarded his PhD on 15 January 1906.) Four other pieces of work..." — 1905 박사 학위, Nobel 무관
- **Stage B top-1**: "## Awards and honors  Einstein received numerous awards and honors, and in 1922, he was awarded the 1921 Nobel Prize in Physics..." — **정답 섹션 통째**

Distance 절대값은 BL이 가장 낮지만, BL은 "Nobel" 단어 매칭일 뿐 무관 단편. Stage B만이 Nobel 수상 사실을 직접 다루는 섹션을 1순위로 잡음. **검색 정확도는 distance가 아니라 매칭 leaf 자체로 판단해야 함.**

**`"퀴리 부인 원소"`:**

- **Baseline top-1**: "Quinn, Susan (1996). Marie Curie: A Life. Da Capo Press..." — 참고문헌
- **Stage A top-1**: "### Nonfiction  Curie, Eve (2001). Madame Curie: A Biography..." — 참고문헌
- **Stage B top-1**: "# Marie Curie  Maria Salomea Skłodowska Curie (Polish: ...; 7 November 1867 – 4 July 1934)..." — 인물 introduction

원하는 답은 polonium/radium 발견 섹션이지만 셋 다 빗나감. Stage B는 참고문헌 → introduction으로 옮겨갔지만 여전히 "원소" 다루는 본문에 닿지 못함.

## 분석

### 작동한 것

- **영어 쿼리 검색 정확도 ↑**: Einstein 쿼리에서 Stage B가 `## Awards and honors` 섹션을 정조준. 어휘 매칭(BL) → 단락 매칭(A) → 섹션 매칭(B)으로 의미 단위가 커지는 패턴.
- **vLLM 비동기 + prefix cache**: 단순 sync로 58분 걸릴 작업을 70초로 단축. 같은 document를 공유하는 leaves를 인접 호출하도록 정렬한 효과.
- **공통 leaf 모듈 (`rag/leaves.py`)**: Stage A/B의 leaf 시퀀스 일치 보장. Stage 간 비교가 의미 있어짐.

### 한계

- **한국어 cross-lingual은 개선 미미**: Stage B의 영어 컨텍스트는 "Marie Curie + biography + life" 같은 인물 개요 키워드를 강하게 prepend하지만, polonium/radium 같은 도메인 키워드는 약하게 들어감. "원소" → "elements" → "polonium" 어휘 도약은 임베딩 매칭으로 못 잡음.
- **Distance를 단일 지표로 쓸 수 없음**: 0.26 vs 0.28 같은 미세 차이는 실제 검색 품질과 무관할 수 있음. BL이 가장 낮은 distance를 보이지만 매칭 내용은 가장 빈약. 정량 평가에 distance 단독 사용은 misleading.
- **평가 표본 부족**: 2개 쿼리(영 1, 한 1)로는 Stage 효과를 통계적으로 판단 불가. 매번 정성 분석에 의존하는 구조 — Stage C 진입 전 평가 인프라 필요.

### Stage C로 이월

- "원소" ↔ "polonium" 같은 어휘적 도약 → **BM25 하이브리드** (Stage C). 정확 단어 매칭이 임베딩의 약점 보강.
- 검색 결과 재랭킹 (BGE Reranker) — top-k 후보를 cross-encoder로 다시 점수.
- Stage B의 효과는 Stage C에서 합쳐졌을 때 더 명확해질 가능성. 단독으론 한국어 약점 못 잡았지만 어휘 매칭과 결합되면 의미+어휘 양쪽 강화.

### 평가 인프라 분리 (Stage 2.5로 별도 진행)

Stage B 작업 중 명확해진 점: distance 단독으로는 stage 효과 판단 불가. Stage C 진입 전 별도 substep으로 평가 framework 구축:

- 10~15개 쿼리 셋 (영/한 균형, 인물별 다양한 주제)
- 정답 doc + 정답 섹션 라벨링
- Hit Rate @ k, MRR 자동 계산
- Baseline/A/B/C 결과 표 자동 생성

LangFuse 트레이싱 도입도 같이. Capstone 2 reasoning 에이전트의 QA 평가에도 재활용 가능.

## 파일

```
rag/
└── leaves.py                          # Stage A/B 공유 leaf 생성 모듈

scripts/
├── test_contextual_prompt.py          # Stage B substep 1: 프롬프트 캘리브레이션
├── generate_contexts.py               # Stage B substep 2: 584 컨텍스트 비동기 배치 생성
├── build_index_contextual.py          # Stage B substep 3: prepend 후 재인덱싱
└── experiment_stage_b.py              # Stage B substep 4: 2축 5조합 비교

chroma_db/
├── chroma.sqlite3                     # baseline + Stage A + Stage B 세 collection
├── contexts.json                      # 584 leaves의 LLM 생성 컨텍스트 캐시
└── hier_nodes.json                    # parent 사이드카 (Stage A에서 생성, B와 공유)
```

## 재현

```bash
# 1. 데이터 준비 (Stage A에서 완료된 상태 가정)
uv run python scripts/fetch_wikipedia.py
uv run python scripts/convert_to_markdown.py

# 2. Stage A 인덱싱 (Stage B의 parent 사이드카 의존)
uv run python scripts/build_index_hierarchical.py

# 3. Stage B 컨텍스트 생성 (vLLM 서버 필요)
curl -s http://localhost:8000/health    # 헬스체크
uv run python scripts/generate_contexts.py

# 4. Stage B 인덱싱
uv run python scripts/build_index_contextual.py

# 5. 2축 실험
uv run python scripts/experiment_stage_b.py
```

## 다음 단계

**Stage 2.5 — 평가 인프라 (신설)**. 10~15개 쿼리 셋 + 정답 라벨링 + Hit Rate @ k, MRR 자동 계산. Baseline/A/B/C 비교를 정성에서 정량으로 전환. LangFuse 트레이싱 도입.

**Stage C — Hybrid + Reranking**. BM25 (어휘) + 벡터 검색 (의미) 결합, RRF 융합, BGE 리랭커로 top-k 재정렬.