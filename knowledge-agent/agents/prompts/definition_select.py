# 09 통합 — definition SELECT 프롬프트.
# 한 개념에 정의가 여러 개 모였을 때(더미), 그중 "개념 자체를 가장 깨끗하게 서술한"
# 하나를 고른다. 합치지(FUSE) 않는다 — 고르기(SELECT)만. 나머지는 더미에 보존.
# 출력은 인덱스 하나뿐 — 근거(rationale)는 일부러 안 받는다(과부하/불안정 회피).

SELECT = (
    "You are given a concept name and a numbered list of candidate definitions, "
    "all extracted from one paper. Pick the SINGLE definition that best states "
    "what the concept fundamentally IS — general, self-contained, and reusable "
    "outside this paper.\n\n"
    "Prefer a definition that:\n"
    "1. Describes the concept itself, not its role/use/comparison in this paper.\n"
    "2. Is clean — no implementation artifacts (code, model names like GPT-3), "
    "no experiment-specific detail.\n"
    "3. Would fit as a glossary entry someone could read with no other context.\n\n"
    "Avoid a definition that:\n"
    "- Frames the concept only relative to another method "
    "(\"the approach X is compared against\").\n"
    "- Is contaminated with paper/code specifics.\n"
    "- Is narrower than the concept (describes one use, not the concept).\n\n"
    "Examples:\n"
    "Concept: Chain-of-Thought\n"
    "  0. \"CoT is the reasoning approach that ReAct is compared against.\"\n"
    "  1. \"A foundational method that enables language models to articulate "
    "their reasoning processes.\"\n"
    "  2. \"Focuses solely on reasoning without actions or observations.\"\n"
    '  -> {"index": 1}   (0 is paper-relative, 2 is contrast-framed)\n\n'
    "Concept: ReAct\n"
    "  0. \"ReAct interleaves reasoning traces with task-specific actions to "
    "enhance LLM performance in understanding and decision making.\"\n"
    "  1. \"ReAct is a prompting code associated with the GPT-3 model that "
    "enables replication of findings.\"\n"
    '  -> {"index": 0}   (1 is code/model-contaminated)\n\n'
    "Return strict JSON only, the index of the best definition: "
    '{"index": <integer>}'
)

# ──────────────────────────────────────────────
# [한글 번역] — 주석이라 import 시 SELECT에 안 따라옴. 영어와 1:1 대응.
#
# 한 개념 이름과 번호 매긴 후보 정의 목록이 주어진다(모두 한 논문에서 추출됨).
# 그중 "이 개념이 근본적으로 무엇인가"를 가장 잘 서술한 정의 하나를 골라라
# — 일반적이고, 자체로 완결되며, 이 논문 밖에서도 재사용 가능한 것.
#
# 다음과 같은 정의를 선호하라:
# 1. 이 논문에서의 역할/사용/대조가 아니라, 개념 그 자체를 서술한 것.
# 2. 깨끗한 것 — 구현 잔해(코드, GPT-3 같은 모델명)나 실험 특정 디테일이 없는 것.
# 3. 다른 맥락 없이 읽어도 되는, 용어집 항목으로 쓸 만한 것.
#
# 다음과 같은 정의는 피하라:
# - 다른 방법과의 상대적 위치로만 서술된 것("X가 비교 대상으로 삼는 접근").
# - 논문/코드 특정 내용으로 오염된 것.
# - 개념보다 좁은 것(개념이 아니라 한 가지 용례를 서술).
#
# 예시:
# 개념: Chain-of-Thought
#   0. "CoT는 ReAct가 비교 대상으로 삼는 reasoning 접근이다."
#   1. "언어모델이 자신의 reasoning 과정을 명시하도록 하는 foundational method."
#   2. "action이나 observation 없이 reasoning에만 집중한다."
#   -> {"index": 1}   (0은 논문 상대적, 2는 대조 프레임)
#
# 개념: ReAct
#   0. "ReAct는 reasoning trace와 task-specific action을 교차시켜 언어 이해·
#       의사결정에서 LLM 성능을 높인다."
#   1. "ReAct는 GPT-3 모델에 연결된 prompting code로, 결과 복제를 가능하게 한다."
#   -> {"index": 0}   (1은 코드/모델로 오염됨)
#
# 엄격한 JSON만, best 정의의 인덱스로 반환하라: {"index": <정수>}
# ──────────────────────────────────────────────
