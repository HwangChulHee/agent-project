# 06 REA 2단계 프롬프트 — 1단계 문장을 is_a/part_of/none으로 매핑.
# depends_on은 이번 단계 제외 → 선수지식/uses/확장류는 none으로 떨어져 예외 로그로 간다.

STAGE2 = (
    "You classify the relationship of A to B into EXACTLY one label, based on the given "
    "sentence describing A in relation to B.\n\n"
    "Labels:\n"
    "1. is_a — A is a type, kind, or special case of B (A is subsumed by B).\n"
    "2. part_of — A is a component, module, or sub-part that B is composed of.\n"
    "3. none — anything else. This INCLUDES: A uses B, A builds on / extends / improves "
    "B, A combines with B, A contrasts with B, A is a prerequisite for B, or no relation. "
    "When unsure between a real label and none, choose none.\n\n"
    "Rules:\n"
    "1. Decide from the sentence only; do not infer beyond it.\n"
    "2. 'extends', 'is based on', 'advancement of', 'enhancement of' are NOT is_a — that is none.\n"
    "3. Keep the rationale to 12 words or fewer.\n\n"
    "Examples:\n"
    "- Sentence: \"Zero-shot CoT is a chain-of-thought variant ...\" (A=zero-shot CoT, "
    "B=chain-of-thought) -> {\"relation\": \"is_a\", \"rationale\": \"variant = a kind of CoT\"}\n"
    "- Sentence: \"The retriever is a module ReAct invokes to fetch evidence.\" "
    "(A=retriever, B=ReAct) -> {\"relation\": \"part_of\", \"rationale\": \"module ReAct is composed of\"}\n"
    "- Sentence: \"ReAct extends chain-of-thought by adding actions.\" (A=ReAct, "
    "B=chain-of-thought) -> {\"relation\": \"none\", \"rationale\": \"extends, not a kind of\"}\n\n"
    'Return strict JSON only: {"relation": "is_a|part_of|none", "rationale": "<=12 words"}'
)

# ──────────────────────────────────────────────
# [한글 번역] — 주석이라 import 시 STAGE2에 안 따라옴. 영어와 1:1 대응.
#
# 너는 A가 B에 대해 어떤 관계인지 서술한 문장을 근거로, 그 관계를 정확히 하나의
# 라벨로 분류한다.
#
# 라벨:
# 1. is_a — A가 B의 한 종류/유형/특수 사례 (A가 B에 포섭됨).
# 2. part_of — A가 B를 구성하는 구성요소/모듈/하위 부분.
# 3. none — 그 외 전부. 다음을 포함한다: A가 B를 사용, A가 B를 기반 확장/개선,
#    A가 B와 결합, A가 B와 대조, A가 B의 선수지식, 또는 무관계.
#    진짜 라벨과 none 사이에서 헷갈리면 none을 골라라.
#
# 규칙:
# 1. 문장만 보고 판단하라; 그 너머로 추론하지 마라.
# 2. '확장한다(extends)'나 '~에 기반한다'는 is_a가 아니다 — none이다.
# 3. rationale은 12단어 이하로 유지하라.
#
# 예시:
# - 문장: "Zero-shot CoT는 chain-of-thought 변형이다 ..." (A=zero-shot CoT,
#   B=chain-of-thought) -> {"relation": "is_a", "rationale": "변형 = CoT의 한 종류"}
# - 문장: "retriever는 ReAct가 근거를 가져오려 호출하는 모듈이다." (A=retriever,
#   B=ReAct) -> {"relation": "part_of", "rationale": "ReAct를 구성하는 모듈"}
# - 문장: "ReAct는 action을 더해 chain-of-thought를 확장한다." (A=ReAct,
#   B=chain-of-thought) -> {"relation": "none", "rationale": "확장이지 종류가 아님"}
#
# 엄격한 JSON만 반환하라: {"relation": "is_a|part_of|none", "rationale": "12단어 이하"}
# ──────────────────────────────────────────────

