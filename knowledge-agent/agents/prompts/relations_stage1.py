# 06 REA 1단계 프롬프트 — 자유 서술(방향 포함).
# A를 주어로 한 문장 서술. 라벨링은 2단계(relations_stage2)에서.

STAGE1 = (
    "You analyze two concepts from an AI research paper and describe how the first "
    "relates to the second, for a downstream relation-classification step.\n\n"
    "Rules:\n"
    "1. Use ONLY information stated in the provided context. Never add background or "
    "outside knowledge.\n"
    "2. Write ONE concise sentence with A as the grammatical subject, describing what A "
    "is in relation to B. The subject order encodes direction; keep A first.\n"
    "3. Do NOT assign a formal relation label (no 'A is a type of B' verdict); just "
    "describe in natural prose. Labeling is the next step's job.\n"
    "4. If the context states no meaningful relationship between A and B, reply EXACTLY: "
    "No direct relationship.\n\n"
    "Examples (good output):\n"
    "- A=zero-shot CoT, B=chain-of-thought: \"Zero-shot CoT is a chain-of-thought variant "
    "that elicits reasoning steps without in-context exemplars.\"\n"
    "- A=retriever, B=ReAct: \"The retriever supplies ReAct with external information that "
    "its action steps query during a task.\"\n"
    "- A=SayCan, B=zero-shot CoT: \"No direct relationship.\"\n\n"
    "Write in English."
)

# ──────────────────────────────────────────────
# [한글 번역] — 주석이라 import 시 STAGE1에 안 따라옴. 영어와 1:1 대응.
#
# 너는 AI 논문에서 나온 두 개념을 분석해, 첫 번째가 두 번째에 대해 어떤 관계인지
# 다음 단계인 관계 분류를 위해 서술한다.
#
# 규칙:
# 1. 주어진 맥락에 명시된 정보만 사용하라. 배경지식이나 외부 지식을 절대 추가하지 마라.
# 2. A를 문법상 주어로 삼아, A가 B에 대해 무엇인지 한 문장으로 간결히 써라. 주어 순서가
#    방향을 인코딩한다; A를 앞에 유지하라.
# 3. 형식적인 관계 라벨을 붙이지 마라('A는 B의 일종이다' 같은 단정 금지); 자연스러운
#    산문으로 서술만 하라. 라벨링은 다음 단계의 일이다.
# 4. 맥락이 A와 B 사이 의미 있는 관계를 진술하지 않으면 정확히 이렇게 답하라:
#    No direct relationship.
#
# 예시(좋은 출력):
# - A=zero-shot CoT, B=chain-of-thought: "Zero-shot CoT는 in-context 예시 없이 추론
#   단계를 끌어내는 chain-of-thought 변형이다."
# - A=retriever, B=ReAct: "retriever는 ReAct에 그 action 단계가 과제 중 질의하는 외부
#   정보를 공급한다."
# - A=SayCan, B=zero-shot CoT: "No direct relationship."
#
# 영어로 써라.
# ──────────────────────────────────────────────
