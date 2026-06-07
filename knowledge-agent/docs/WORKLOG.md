# WORKLOG

> 이 파일만 읽어도 **무엇을 왜 개선했는지 + 현재 상태 + 다음 할 일**을 파악할 수 있게 유지한다.
> 다른 LLM 세션이 컨텍스트 없이 이어받는 진입점. 새 항목은 **맨 위(역순)**에 추가.
> 프로젝트 목적·철학은 `CLAUDE.md`, 단계별 정책은 `docs/PIPELINE_POLICY.md` 참조.

---

## 현재 상태 (2026-06-08 기준)

- 맵(`data/knowledge_map.json`): **2편**. RW 제외 후 재실행 상태(29노드)지만 **비결정성 노이즈 회귀**(CoT 3조각·Act/IO 가짜허브·GPT-4)로 **운영맵으로 신뢰 안 함** — 아래 RW 항목 참조. 직전 깨끗한 기준점은 `/tmp/ka_snapshots/pre_rwdrop`(33노드).
- merge 경로 실증 완료. CoT 정확히 merge, **CoT-SC 파편화도 "이름 보기"로 해소**(①). 단 **전체 재실행이 새 파편화를 만든다**는 게 드러남 → 다음 표적 = 추출 비결정성/merge 안정성.
- **진행 중인 큰 그림 — 사용자와 합의된 2단계 계획:**
  - **① 이름 보기 merge (완료)** — 정의가 오염돼도 이름/약어가 같으면 SAME. CoT-SC 해결.
  - **② 정의 없는 노드 + 엣지 게이트 (다음)** — 관계로만 서술된 개념은 *틀린 정의 저장 대신 정의를 비워서* 노드로 넣고, **엣지가 붙는 것만** 남긴다(2차 바). 오염 저장 방지 + 섬(교차연결) 완화 동시 공략. ①이 전제(빈 정의 노드는 이름으로만 매칭 가능).
  - 이후: 측정→추천/순서 레이어.

### 열린 질문 — 선수지식(builds_on)/온톨로지 (실측으로 닫아야, 양방향 미검증)
- 06 exception 206건 분석: 버려진 관계 중 **무관 0건**, 대부분 `builds on/enhances`(81)·`uses`(69) = 진짜 관계인데 is_a/part_of에 안 맞아 폐기됨. "ToT builds on CoT"는 is_a도 part_of도 아닌 **선수관계**(미적분 builds_on 대수) — 목적(학습 순서)에 직결.
- 정책은 `depends_on`을 **의도적 폐기**(70쌍 실측): "한 편 추출 = 방향오류·엣지폭발·불안정, 선수지식은 맵 위상에서". **재검토 결과: 정책의 "06 단일추출 안 함"은 견고(✅), 그러나 대체책 "is_a/정의로 유도"는 미검증 + 우리 de-contamination이 정의 속 관계참조를 지워 충돌(⚠️).**
- **즉 "builds_on 한다"도 "안 한다"도 양쪽 미검증.** 유력 제3안 = **교차논문 교차검증**(여러 논문이 같은 방향으로 말할 때만 builds_on 엣지 승격 → 단일 노이즈 걸러짐) + 공출현 비대칭. **논문 더 쌓이면 실측으로 닫기.** 단일 06 엣지로는 안 함.
- 결론: 선수지식은 **측정→추천 레이어에서 토폴로지/교차검증으로** 푼다. 그 전까지 06은 is_a/part_of 유지.

### 열린 이슈 (실측됨, 미해결)
- **교차논문 엣지 0 (구조적)**: 06은 한 논문 내부 노드쌍만 관계 추출 → 새 논문 개념과 기존 맵 개념을 잇는 엣지가 안 생김. **world-model 교차연결은 전적으로 노드 merge에만 의존** → merge 한 번 놓치면 섬.
- **Related Work 관계서술형 정의**: 04 가드를 뚫고 "ReAct builds upon"/"complements ReAct" 류가 통과(`Inner Monologue` 등). **merge 깨짐 증상은 ①(이름 보기)로 해소**됐으나, *아직 맵에 없는* 개념이 관계정의만 갖고 단독 노드로 들어오는 문제는 남음 → **②(빈 정의로 저장)가 정공법.**
- **엣지 recall 희소 + 품질**: 34노드에 엣지 6개(`agent_06` `random` 샘플링). 일부 의심 엣지(`REACT part_of Acting-only prompts`는 역방향/오추출로 보임).
- **cycle 자가생성 간헐적**: 06 양방향 추출 시. ReAct 런에선 0건.
- **SELECT 기권(-1)은 의미적 오염엔 약함**: 도메인지식 없어 미묘한 오염 미인지. 노골적 타개념 풀에만 발동.
- **추출 노이즈**: ToT 런의 `GPT-4`는 제거함. ReAct 런에선 명시적 모델 인스턴스 오추출 없었음(GPT-4 노이즈는 체계적이라기보단 산발적일 가능성).
- **측정→추천/순서 레이어 미구현**: `kb/store.py`에 `find_gaps()`뿐. 프로젝트 최종 목적의 빈 곳.

---

## 2026-06-08 — Related Work 섹션 제외 (02) + 재실행이 드러낸 비결정성

**변경:** `agent_02_reader.py`에 `drop_sections()` 추가 — References처럼 RW를 본문 외 잡음원으로 제거(단 trim_back_matter와 달리 "그 섹션만", 뒤 Discussion/Conclusion 보존). 근거: RW = 공출현 엣지 폭발 + 인용-stub 변두리 개념 + 관계서술 정의의 핫스팟.
**✅ 깨끗한 성과(귀속 가능):** 변두리 RW 개념 제거됨 — STaR/SayCan/Selection-Inference/WebGPT/least-to-most/zero-shot CoT. 가짜 RW 공출현 엣지 소멸.
**⚠️ 그러나 — 전체 재실행이 비결정성 노이즈를 새로 생성:** 노드 33→29, 엣지 6→23, 고립 70%→24%로 보이지만 **엣지 23개 중 진짜는 ~6개**(ToT 컴포넌트 part_of ToT). 나머지는:
- 개념 파편화: CoT 3조각(`CoT`/`Chain-of-Thought (CoT)`/`Chain of Thought`), `IO`(←input-output prompting), `Act`(←ReAct) 분리.
- 가짜 허브: `Act`(part_of HotPotQA/FEVER/… ~8개 엉터리), `IO`(part_of thought decomposition/… ~5개).
- `GPT-4` 노드 재등장 + `System 1 part_of GPT-4` 난센스 엣지.
**진짜 원인(다음 표적):** **전체 재실행 = 비결정성 복권.** 03/04/06이 매번 다르게 뽑아 돌릴 때마다 새 파편화+노이즈+가짜엣지 생성. ①로 CoT-SC 고쳐도 **재실행이 CoT를 다시 쪼갬.** 맵이 재실행에 불안정 → **추출 비결정성 + merge 안정성**이 RW/builds_on보다 시급한 문제로 부상.
**처리:** RW 제외 코드만 커밋(정확함). 이 재실행 맵은 노이즈 회귀라 운영맵으로 안 박음(precision-first).

## 2026-06-08 — 이름 보기 merge (① — CoT-SC 파편화 해소)

**문제:** ReAct의 `CoT-SC`가 ToT 맵의 `self-consistency with chain-of-thought`와 같은 개념인데 **new로 빠져 2노드로 파편화**(직전 항목). 원인 = ReAct가 뽑은 정의가 관계서술형 오염("complements ReAct…")이라, 정의만 비교하는 05 판정기가 DIFFERENT 판정.
**해결:** `prompts/alignment.py` 판정 규칙에 **"이름 보기"** 추가 — 정의가 오염·역할기반이어도 **두 이름이 같은 개념(약어/풀네임/어순변경)이면 SAME**. 단 수식어 붙은 변형(zero-shot CoT 등)은 DIFFERENT 유지. "이름만 먼저 비교" 절차 + 구체 예시로 gpt-4o-mini 안정화. **외부지식 금지는 "merge 판단의 이름 동일성 인식"에만 한정 완화 — 저장 정의는 순수 유지.**
**검증:** judge 단위 테스트 7/7(프롬프트에 없는 RLHF 약어·Auto-CoT 변형 일반화 포함). end-to-end: ToT 18노드 맵에 ReAct 재통합 → **34→33노드**, self-consistency 계열 1노드로 통합, 흡수 후 **깨끗한 ToT 정의 유지**(SELECT가 오염 ReAct 정의 대신 선택), 변형 과병합 0.
**코드:** `prompts/alignment.py`만 변경.

## 2026-06-08 — ReAct(2210.03629) 투입 + merge/align 경로 첫 실증

**목표:** 2번째 논문을 기존 ToT 맵에 통합하며, 지금껏 안 탄 merge 경로를 실증·분석.
**실행:** 01~08 전체. ReAct 18개념 추출 → 05에서 기존 18노드와 대조 → 08 통합. 결과 **34노드/엣지6/충돌0**.

**merge 판정 결과:**
- ✅ `Chain-of-thought prompting`(sim 0.720)·`CoT`(0.668) → 둘 다 `Chain of Thought`로 정확히 merge. 병합 후 정의도 깨끗 유지(재오염 없음).
- ✅ `zero-shot CoT`·`least-to-most prompting`(0.596) → new. 변형은 별개로 유지(정책대로).
- ❌ **`CoT-SC`(0.635) → new (누락 merge)**. ToT의 `self-consistency with chain-of-thought`와 동일 개념인데 안 붙어 **2노드로 파편화**.

**핵심 발견 (실측):**
1. **프레이밍 오염이 merge를 깬다.** CoT-SC 누락 원인 = ReAct가 뽑은 정의 *"complements ReAct…reduce hallucination"*(개념 자체 아닌 ReAct와의 관계 서술). `judge_same`에 깨끗한 정의를 넣으면 SAME(merge), 오염 정의면 DIFFERENT(new)임을 확증. → **정의 오염은 노드 하나가 아니라 world-model 교차연결을 깨뜨린다.**
2. **Related Work가 오염 핫스팟.** 04 새 가드를 뚫고 `Inner Monologue`="A work…that ReAct builds upon", CoT-SC 후보가 통과. 관계서술형 정의가 RW 섹션에서 반복.
3. **교차논문 엣지 0 (구조적).** 6개 엣지 전부 논문 내부. 두 논문 서브그래프는 **섬**이고 merge된 `Chain of Thought` 노드 하나로만 연결(그나마 ReAct쪽 CoT 엣지 없음). 06이 논문 내부 관계만 추출하므로 교차연결은 노드 merge에만 의존.

**함의:** 다중논문에서 정의 오염의 비용이 단일논문보다 크다(파편화). Related Work 프레이밍 가드 + 교차논문 연결이 다음 후보. (코드 무변경, 데이터 산출물만 추가)

## 2026-06-08 — ToT 맵 단일논문 베이스 정합화 (`94dbede`)

**왜:** 다중논문 실증 전에 분석 기준점을 깨끗이. 직전 오염 수정(fixed2)이 04만 고치고 06 미재실행 → 노드명 어긋나 엣지가 dangling 6개로 퇴화한 상태였음.
**변경:** `GPT-4` 노이즈 노드를 04/04b/05 산출물에서 제거 → 맵 비우고 06→07→08 재실행해 엣지 일관 재구성.
**결과:** 18 노드, 엣지 4(전부 유효), 충돌 0, CoT 정의 깨끗 유지. 데이터 산출물만 변경(코드 무변경).

## 2026-06-08 — CLAUDE.md 신설 (`ad25265`)

프로젝트 목적(**측정→학습 추천/순서 결정**)·설계 철학·파이프라인 개요를 레포 진입 문서로 명문화.

## 2026-06-08 — 노드 정의 오염 방지 (`8d744bb`)

**증상:** `Chain of Thought` 정의에 ToT 설명이 박힘(완전 오염). DFS/state-eval 등은 크로스워드·passage 과제에 묶여 서술(프레이밍 오염).
**원인(실측):** 03 요약(Abstract)이 "A builds on B" 문장에서 B(ToT)의 성질을 A(CoT) 이름 옆에 모호하게 붙임 → 04 추출이 그 절을 CoT에 오귀속. 프레이밍은 03 과제섹션을 04가 그대로 전사. SELECT는 깨끗한 후보가 풀에 없어 구제 불가.
**변경(4개 방어):**
1. `agent_08`+`p08_definition_select`: SELECT 기권(-1) → 운영맵에 `confidence:low + flagged`.
2. `agent_04`+`entity_extraction`: 주어귀속 가드("A builds on B"의 성질은 A의 것) + 섹션 heading 입력 주입.
3. `entity_extraction`: 과제비계 제거(letter/passage/crossword→일반어; 도메인명사 목록+예시).
4. `agent_04b`: `'X prompting'→'X'` 변형병합(베이스 실재 시에만, 결정적).

**실측 교훈 (동일세션 baseline vs fixed 비교 — 무엇이 실제로 일했나):**
- **결정적 = 해결책4(04b 풀통합).** 깨끗한 정의를 SELECT 같은 풀에 넣으니 SELECT가 골라냄. CoT 후보 2→4개.
- 해결책1(기권)은 의미오염엔 무력(위 열린 이슈 참조), 노골적 케이스에만.
- 해결책2(주어가드)는 gpt-4o-mini에서 약함 — Abstract 오염 후보를 여전히 재추출.
- 해결책3(과제비계)은 도메인명사 목록+예시 박은 뒤 발동(passage→output).
- 결론: **방어 깊이 실효 4 > 3 > 1·2.**
