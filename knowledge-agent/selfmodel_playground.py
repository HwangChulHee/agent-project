"""
self-model 갱신 격리 실험 — LLM 없이 점수 시퀀스로 mastery 수렴 관찰.
부드러운 수렴(지수이동평균). 근거: 사용자 답의 진폭 흡수(한 번 막혀도 추세로).
"""

ALPHA = 0.7  # 옛값 유지 비율. 높을수록 안정적·느리게 반영


def update_mastery(old, score):
    """점수(0~1) 한 번으로 mastery 갱신. 한 번에 안 휘둘리고 추세로."""
    return ALPHA * old + (1 - ALPHA) * score


if __name__ == "__main__":
    print(f"ALPHA(옛값 유지)={ALPHA}\n")

    # 네 시나리오: 만점1.0 / 반점0.5 / 빵점0.0
    # 예시 흐름: 처음 잘하다 한 번 막히고 회복
    scores = [1.0, 1.0, 0.0, 0.5, 1.0]

    mastery = 0.0  # 신규 개념은 0에서 시작
    print(f"시작 mastery: {mastery:.3f}")
    for i, s in enumerate(scores, 1):
        mastery = update_mastery(mastery, s)
        print(f"  {i}. 점수 {s:.1f} → mastery {mastery:.3f}")
