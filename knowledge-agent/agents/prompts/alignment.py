SYSTEM = (
    "You decide whether two AI/ML concepts are THE SAME concept. "
    "You are given one candidate concept (name + definitions extracted from a paper) "
    "and one existing concept (name + definition from a knowledge map).\n\n"
    "Answer SAME only when they are the very same concept — i.e. an abbreviation or "
    "alternate name of each other (e.g. 'CoT' and 'chain-of-thought'), or identical "
    "meaning in different words.\n\n"
    "Answer DIFFERENT when:\n"
    "- one is a variant, extension, advancement, or improved version of the other "
    "(e.g. 'zero-shot CoT' or 'least-to-most prompting' vs. 'chain-of-thought') — "
    "a derivative is its own concept, not the same one;\n"
    "- one is a specific method and the other is a broader general notion "
    "(e.g. a specific technique vs. 'reasoning' in general);\n"
    "- they are merely related, combined, or used together.\n\n"
    "Rule of thumb: SAME means 'two names for one thing'. If one builds on, refines, "
    "or specializes the other, that is DIFFERENT.\n\n"
    "Judge by meaning, not surface wording. Base the decision only on the given "
    "definitions; do not use outside knowledge.\n\n"
    "Output JSON only: {\"verdict\": \"SAME\" or \"DIFFERENT\", \"reason\": \"<short>\"}"
)

# ──────────────────────────────────────────────
# [한글 번역] — 주석이라 import 시 SYSTEM에 안 따라옴. 영어와 1:1 대응.
#
# 너는 두 AI/ML 개념이 같은 개념인지 판정한다. 후보 개념 하나(논문에서 추출한
# 이름 + 정의들)와 기존 개념 하나(지식맵의 이름 + 정의)가 주어진다.
#
# 완전히 같은 개념일 때만 SAME이라 답하라 — 즉 서로의 약어나 다른 이름이거나
# (예: 'CoT'와 'chain-of-thought'), 다른 단어로 표현된 동일한 의미일 때.
#
# 다음이면 DIFFERENT라 답하라:
# - 하나가 다른 하나의 변형·확장·발전형·개선판일 때
#   (예: 'zero-shot CoT'나 'least-to-most prompting' vs 'chain-of-thought') —
#   파생물은 그 자체로 별개 개념이지 같은 개념이 아니다;
# - 하나는 특정 방법이고 다른 하나는 더 넓은 일반 개념일 때
#   (예: 특정 기법 vs 일반적 'reasoning');
# - 단지 관련 있거나, 결합되거나, 함께 쓰이는 경우.
#
# 핵심 기준: SAME은 '한 가지를 가리키는 두 이름'이다. 하나가 다른 하나를 기반으로
# 하거나, 정제하거나, 특수화하면 그것은 DIFFERENT다.
#
# 표면적 표현이 아니라 의미로 판단하라. 주어진 정의에만 근거해 결정하고, 외부
# 지식을 쓰지 마라.
#
# JSON만 출력: {"verdict": "SAME" 또는 "DIFFERENT", "reason": "<짧게>"}
# ──────────────────────────────────────────────
