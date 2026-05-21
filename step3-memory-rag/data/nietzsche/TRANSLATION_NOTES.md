# 번역 이슈 (Gemma 4 자동 번역 한계)

## 확인된 오역/평탄화

| 위치 | 영문 원문 | Gemma 번역 | 표준 번역 (황문수) |
|---|---|---|---|
| Prologue §2 | the old saint | 노인 | 성자 |
| II. Academic Chairs of Virtue | (제목) | 미덕의 학술석 | 미덕의 강좌 |

## 보정 정책
- Phase 1 RAG 실험: 그대로 사용 (의미 매칭 영향 미미)
- Capstone 시스템 배포: 핵심 용어 사전 만들어 후처리 치환

## 표준 번역어 사전 (TODO)
- saint → 성자 (not 노인)
- Übermensch / Superman → 초인
- "go down" / "down-going" → 몰락(하다)
- last man → 종말인

## 1차 사전 후 남은 보정 대상 (후속 작업)

- `학술석` (line 295, 305, 311 본문) — Chair 표준역 "강좌"로 바꾸려면 컨텍스트 패턴 필요 (whole-phrase whole-line만 안전)
- `마지막 인간` (1 hit) — last man 표준역 "종말인". 정책 A2/B2 모두 만족하므로 다음 사전 업데이트 시 추가 검토
