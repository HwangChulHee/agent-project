# KARMA 논문 레퍼런스

> 이 문서는 **KARMA 논문 자체**를 정리한 레퍼런스다.
> "우리가 어떻게 구현/변형했나"는 `docs/PIPELINE_POLICY.md`에 있다 (역할 분리).
>
> 출처: Lu, Wu, Zhao, Peng, Wang, *KARMA: Leveraging Multi-Agent LLMs for
> Automated Knowledge Graph Enrichment* (arXiv:2502.06472, NeurIPS 2025).

---

## 한 줄 요약

KARMA는 **비정형 텍스트(논문)를 읽어 기존 지식 그래프(KG)를 자동으로 풍부하게(enrich)**
만드는 멀티에이전트 LLM 프레임워크다. 9개의 전담 에이전트가 협업하며, 문서를 파싱하고
지식을 추출·검증해 기존 그래프 구조에 통합한다.

핵심: **"새 KG를 짓는 게 아니라 기존 KG를 enrich한다."** G(예: Wikidata, DBpedia)가
주어지고, 논문에서 뽑은 새 트리플을 거기 더한다.

실험: PubMed 1,200편(유전체·단백질체·대사체 3도메인)으로, 최대 38,230개 신규 엔티티 식별,
LLM 검증 정확도 83.1%, 충돌 엣지 18.6% 감소.

---

## 문제 정의 (formal)

- 기존 KG: `G = (V, E)`. V = 엔티티, E = 방향 엣지(관계).
- 관계 = 트리플 `t = (e_h, r, e_t)`.
- 입력: 논문 코퍼스 `P = {p_1, ..., p_n}`.
- 목표: 각 논문에서 기존에 없던 트리플 `t ∉ E`를 추출해 통합 → `G_new`.
- 각 후보 트리플은 통합 전 LLM 검증을 거친다.

---

## 9개 에이전트

Central Controller가 작업을 분배하고, 각 에이전트는 전용 프롬프트·하이퍼파라미터를 가진다.

### 1. Ingestion Agent (IA)
- 문서 검색 + 포맷 정규화 + 메타데이터(저널·날짜·저자) 추출.
- `IA(p) = (normalize(p), metadata(p))`. normalize는 LLM 프롬프트 P_ingest로 OCR 오류·구조 불일치 처리.
- 출력을 Reader용 큐에 넣음.

### 2. Reader Agent (RA)
- 정규화 문서를 세그먼트(abstract, methods, results 등)로 분할 + 관련성 필터.
- 각 세그먼트 `s_j`에 관련성 점수: `R(s_j) = LLM_reader(s_j, G)` — **현재 그래프 G에 비춰** 평가.
- `R(s_j) < δ`(도메인 보정 임계값)면 버림. 살아남은 세그먼트만 SA로.

### 3. Summarizer Agent (SA)
- 세그먼트를 간결한 요약 `u_j`로 압축: `u_j = LLM_summ(s_j, P_summ)`.
- P_summ은 **핵심 엔티티·관계·도메인 용어를 보존**하도록 지시. 추출기에 "고신호·저노이즈" 입력 제공.
- (부록 B.5 프롬프트: gene/chemical 이름·수치 데이터는 verbatim 보존, 100단어 미만 권장, 저관련 세그먼트는 `[OMITTED]`.)

### 4. Entity Extraction Agent (EEA)
- LLM 기반 NER로 엔티티 식별 + 사전/온톨로지 필터로 거짓양성 제거.
- **정규화:** 추출 엔티티 `e`를 임베딩 공간에서 기존 KG 엔티티와 매칭.
  `ê = argmin_v d(φ(e), ψ(v))` — φ는 멘션을, ψ는 KG 엔티티를 같은 공간으로 매핑(예: BERT 계열).
  거리가 ρ보다 크면 신규로 표시해 후보 집합 V+에 추가.
  (예: "acetylsalicylic acid" → "Aspirin"으로 정규화.) **이름 기반 임베딩.**

### 5. Relationship Extraction Agent (REA)
- 정규화된 엔티티 쌍 `(ê_i, ê_j)`을 LLM 분류기에 넣어 관계 확률 `p(r | ê_i, ê_j, u_j)` 계산.
- 임계값 θ_r 넘는 관계로 트리플 형성. multi-label 허용(한 구절에 여러 관계 가능).
- **입력이 "정규화된 엔티티 쌍"** — 즉 EEA가 엔티티를 확정한 *후*에 작동.

### 6. Schema Alignment Agent (SAA)
- 새 엔티티/관계가 기존 KG 타입과 안 맞으면 도메인 분류 수행.
- 엔티티: `τ* = argmax_τ LLM_SAA(v, τ, P_align)`, T = 유효 타입 집합(Disease, Drug, Gene 등).
- 새 관계도 기존 관계 타입에 매핑. 적절한 매치 없으면 후보 추가로 플래그.

### 7. Conflict Resolution Agent (CRA)
- 새 트리플이 기존과 논리적으로 모순되면 LLM 토론(debate) 프롬프트로 Agree/Contradict 판정.
- Contradict면 폐기하거나 전문가 검토 큐로.

### 8. Evaluator Agent (EA)
- 최종 통합 관문. 트리플마다 confidence·clarity·relevance를 시그모이드 가중 결합으로 산출.
- `integrate(t) = 1 if mean(C, Cl, R) ≥ Θ else 0`. 평균이 임계값 넘는 트리플만 통합.

### 9. Central Controller
- 에이전트들에 작업 분배·우선순위 결정(워크로드 균형).

---

## 흐름

```
Ingest → Read(분할+관련성컷) → Summarize → Extract(엔티티+정규화)
   → Relate(관계) → Align(스키마) → Resolve(충돌) → Evaluate(통합결정) → Store
```

3대 혁신 (논문 주장):
1. 멀티에이전트 교차검증 (REA가 SAA 출력으로 후보 엔티티 검증 등).
2. 도메인 적응형 프롬프팅 (분야별 정확도).
3. LLM 기반 검증으로 환각·스키마 불일치 완화.

---

## Ablation (어느 에이전트가 중요한가)

| 제거한 에이전트 | 효과 |
|---|---|
| Summarizer 제거 | 품질 지표 큰 하락 (정확도 ~22.9%↓ 등) — 요약 단계의 가치 입증 |
| Conflict Resolution 제거 | 모순 엣지 증가, 정확도 하락 |
| Evaluator 제거 | 필터 없이 통합 → 품질 하락 |

> 주의: "Summarizer 제거 시 하락"은 **요약 단계의 가치**이지, Reader/Summarizer를
> 두 에이전트로 *분리*하라는 근거가 아니다. (우리 설계에서 이 점 주의 — PIPELINE_POLICY 03 참조.)

---

## 우리 프로젝트가 참고하는 방식

- **9개를 그대로 따르지 않음.** 목적이 다름(KARMA=정확한 분야 그래프 / 우리=내 커버리지 지형도 + self-model + 추천).
- 핵심 차용: 멀티에이전트 파이프라인 구조(파싱→분할→요약→추출→정규화→...), 임베딩+LLM 다단계 검증 정신.
- 핵심 변형: **이름 임베딩 → 정의문 임베딩** (AI 개념엔 도메인 임베딩 모델이 없어서). 이로 인해 KARMA엔 없는 "정의 출처·품질" 문제를 새로 다룸.
- 자세한 대응·차이는 `docs/PIPELINE_POLICY.md` 참조.