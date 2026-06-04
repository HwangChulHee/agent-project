# KARMA 에이전트 매핑

이 프로젝트(knowledge-agent)는 KARMA의 멀티에이전트 파이프라인을 참고해 구성한다.
KARMA는 "논문을 읽어 지식 그래프에 자동으로 쌓는" 시스템으로, 각 단계가 전담 에이전트 하나로 나뉜다.
이 문서는 KARMA의 9개 에이전트가 각각 무슨 일을 하는지, 그리고 우리 코드의 어느 파일에 대응하는지를 정리한다.

> 출처: Lu & Wang, *KARMA: Leveraging Multi-Agent LLMs for Automated Knowledge Graph Enrichment* (arXiv:2502.06472)

---

## 전체 흐름

```
논문 가져오기 → 읽고 거르기 → 요약 → 개념 추출 → 관계 추출
   → 기존 그래프에 정렬 → 모순 해소 → 통합 결정
```

KARMA는 이 흐름의 각 단계를 독립 에이전트로 두고, Central Controller가 작업을 분배한다.
우리는 abstract 입력이라 일부 단계를 합치거나 생략하고, self-model(이해도)·추천이라는 고유 층을 더한다.

---

## KARMA 9개 에이전트

### 1. Ingestion Agent (수집)
- **하는 일:** 입력 문서를 가져와 정규화(제목·초록·저자·날짜 등으로 분리). 다운스트림이 다루기 쉬운 형태로 정리해 큐에 넣는다.
- **우리 대응:** `agents/collectors/arxiv.py`
- **상태:** ✅ — arXiv API로 최신 논문을 `{source_id, title, text, date, url}` 공통 포맷으로 가져옴.

### 2. Reader Agent (관련성 필터)
- **하는 일:** 문서를 문단 단위로 쪼개고, 각 조각의 "현재 그래프에 대한 관련성 점수"를 매긴다. 점수가 임계값 δ보다 낮으면 버린다(감사말·참고문헌 등 비관련 내용 제거).
- **우리 대응:** `agents/evaluator_agent.py` (일부 — 관련성 판정 부분)
- **상태:** △ — "이 논문이 LLM 에이전트 분야 안인가, 무관(irrelevant)인가"를 판정. 단 이름 매칭 기반이라 거침("new 후함" 문제). 정밀화 시 설명 임베딩 + 관련성 임계값 컷 필요.

### 3. Summarizer Agent (요약)
- **하는 일:** 관련성 높은 문단을 간결한 요약으로 압축하되, 핵심 기술 디테일(기법명·수치)은 보존. 추출기가 다루기 쉽게.
- **우리 대응:** 없음
- **상태:** ✗ 생략 — 우리는 abstract(이미 짧은 요약)를 입력으로 써서 더 요약할 게 없음. 논문 전문(PDF)을 다루게 되면 부활.

### 4. Entity Extraction Agent (개념 추출)
- **하는 일:** 요약된 텍스트에서 엔티티(개념)를 few-shot으로 식별하고, 기존 그래프의 표준형(canonical form)에 정규화. KARMA는 임베딩 정렬(ontology-guided embedding alignment)로 정규화.
- **우리 대응:** `agents/entity_extraction_agent.py`
- **상태:** ✅ — abstract에서 개념(기법/개념)을 추출. 타입 중심 필터로 잡개념·모델명 제외.

### 5. Relationship Extraction Agent (관계 추출)
- **하는 일:** 엔티티 쌍 사이의 관계를 추론(multi-label, 중첩 관계 허용).
- **우리 대응:** `agents/entity_extraction_agent.py` (위와 같은 파일이 겸함)
- **상태:** ✅ — extractor가 개념과 함께 관계(is_a/part_of/depends_on)도 추출. KARMA는 별도 에이전트지만 우리는 한 파일이 4+5번을 겸함.

### 6. Schema Alignment Agent (스키마 정렬)
- **하는 일:** 새 엔티티/관계를 기존 그래프 스키마(타입)에 매핑. "이게 기존의 어느 개념과 같은가? 새 거면 추가하거나 온톨로지 확장 플래그."
- **우리 대응:** `agents/schema_alignment_agent.py`
- **상태:** ✅ — 새 개념이 기존 노드와 같은지 LLM으로 판단해 병합/신규 결정. 타입 다르면 병합 금지. mastery 보존.

### 7. Conflict Resolution Agent (모순 해소)
- **하는 일:** 새 정보가 기존 그래프와 논리적으로 충돌하면(상반된 triplet) 토론(debate) 메커니즘으로 해소.
- **우리 대응:** 없음
- **상태:** ✗ 후순위 — belief/모순 처리. LLM 도메인이 수렴적이라 모순이 약하다고 판단해 뒤로 미룸. 고도화 시 추가.

### 8. Evaluator Agent (통합 결정)
- **하는 일:** 최종 품질 관문. confidence·relevance·clarity·coherence를 가중 결합한 통합 신뢰도로 "이 개념을 그래프에 통합할지" 결정.
- **우리 대응:** `agents/evaluator_agent.py` (일부 — 가치 판정/통합 결정 부분)
- **상태:** △ 판정만 — 논문의 가치(extend/new/contradict/known/irrelevant + 점수)를 판정. 단 통과한 논문을 실제로 맵에 통합(4→5→6으로 흘려보내기)하는 연결이 아직 없음 = 핵심 미완 과제.

### 9. Central Controller Agent (작업 분배)
- **하는 일:** 여러 에이전트에 작업을 분배하고 우선순위를 정함(multi-armed bandit으로 워크로드 균형).
- **우리 대응:** 없음
- **상태:** ✗ 불필요 — 우리는 단일 순차 흐름이라 관리자 불필요. 진짜 멀티에이전트로 고도화할 때 오케스트레이터로 부활.

---

## 우리 고유 (KARMA에 없음)

KARMA는 "분야 지식 그래프 구축"이 목적이라 사용자가 없다.
우리는 그 위에 **self-model(내 이해도)**과 **추천**을 더한다 — 이것이 차별점.

### prober (`agents/prober.py`)
- **하는 일:** self-model 측정. 개념에 대해 LLM이 서술형 질문 생성 → 사용자 답 → CoT 채점(5등분) → 부드러운 수렴으로 mastery 갱신.
- **KARMA 대응:** 없음. self-model은 우리 고유 기여.
- **참고:** BKT 검토 후 폐기(서술형엔 guess/slip 전제 안 맞음), 점진 수렴만 채택.

### digest (`agents/digest.py`)
- **하는 일:** 추천. mastery + depends_on 구조만으로 "지금 배우기 좋은 개념"(프론티어 = 모르는데 선수지식 충족)을 계산.
- **KARMA 대응:** 없음. 추천은 우리 고유.

---

## 한눈에 보는 표

| # | KARMA 에이전트 | 우리 파일 | 상태 |
|---|---|---|---|
| 1 | Ingestion (수집) | `collectors/arxiv.py` | ✅ |
| 2 | Reader (관련성 필터) | `evaluator_agent.py` (겸) | △ 거침 |
| 3 | Summarizer (요약) | — | ✗ abstract라 생략 |
| 4 | Entity Extraction (개념) | `entity_extraction_agent.py` (겸) | ✅ |
| 5 | Relationship Extraction (관계) | `entity_extraction_agent.py` (겸) | ✅ |
| 6 | Schema Alignment (정렬) | `schema_alignment_agent.py` | ✅ |
| 7 | Conflict Resolution (모순) | — | ✗ 후순위 |
| 8 | Evaluator (통합 결정) | `evaluator_agent.py` (겸) | △ 판정만 |
| 9 | Central Controller (분배) | — | ✗ 단일 흐름이라 불필요 |
| — | **self-model 측정** | `prober.py` | ✅ 우리 고유 |
| — | **추천** | `digest.py` | ✅ 우리 고유 |

---

## 우리 구현이 KARMA와 다른 점

1. **부품이 더 적다 (겸직).** `entity_extraction_agent`가 4+5를, `evaluator_agent`가 2+8을 겸함. abstract 입력이라 잘게 쪼갤 필요가 없음. 진짜 멀티에이전트로 고도화할 때 분리 가능.
2. **셋을 의도적으로 비움.** Summarizer(abstract라 불필요), Conflict Resolution(belief 후순위), Central Controller(단일 흐름).
3. **고유 층을 더함.** prober(self-model), digest(추천) — KARMA엔 사용자 개념이 없음.
4. **목적이 다름.** KARMA는 "분야 그래프를 정확히 완성", 우리는 "분야 그래프를 발판으로 나에게 새롭고 도전적인 걸 큐레이션".

## 현재 핵심 미완 과제

부품은 다 있으나 **흐름이 끊겨 있다.** 특히 Evaluator(8)가 "통합하자" 판정한 논문이
Entity Extraction(4)으로 넘어가는 연결이 없음. KARMA의 진짜 가치는 9개 에이전트가
*파이프라인으로 연결*돼 흐른다는 것 — 다음 과제는 새 부품 만들기가 아니라 있는 부품을
KARMA 흐름대로 잇는 것:

```
evaluator(통과 판정) → entity_extraction(개념·관계 추출)
   → schema_alignment(맵에 병합) → 위상 해석("이건 네가 아는 X의 확장")
```