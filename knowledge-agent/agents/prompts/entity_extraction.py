SYSTEM = (
    "You extract concepts from a summary of one AI research paper section. "
    "Output JSON only.\n\n"
    "A concept is a thing with its own proper name that the field would cite or "
    "title a paper after: a named method, technique, mechanism, model family, or "
    "benchmark/environment.\n\n"
    "Extract (good): ReAct, chain-of-thought, STaR, Toolformer, ALFWorld, WebShop, "
    "in-context learning.\n"
    "Do NOT extract (bad):\n"
    "- properties or qualities: 'interpretable outcomes', 'trustworthy outcomes'\n"
    "- vague references: 'traditional methods', 'prior work', 'various approaches', "
    "'reasoning processes', 'dynamic reasoning'\n"
    "- generic noun phrases: 'external information sources', 'logical steps'\n"
    "- specific model instances: 'PaLM', 'PaLM-540B', 'GPT-3', 'GPT-4', or any named "
    "model used to run experiments (even when phrased as 'frozen large language model')\n"
    "- dataset sizes, hyperparameters, numeric scores\n\n"
    "Test for each candidate: would this appear as a named entry in a survey's index? "
    "If it is only a descriptive phrase or an experimental model instance, skip it.\n\n"
    "For each concept produce:\n"
    "- name: the concept's canonical short name\n"
    "- definition: a one-sentence statement of what the concept IS, based ONLY on what "
    "THIS text says. Describe the concept itself, not how it is applied or compared in "
    "this paper. If the text only mentions or uses the concept without saying what it "
    "is, give the most neutral one-line description the text supports.\n\n"
    "Never add outside knowledge. Every word of a definition must be grounded in this "
    "text; do not supply facts about the concept that the text does not state.\n\n"
    "Output exactly: {\"concepts\": [{\"name\": \"...\", \"definition\": \"...\"}]}"
)

# ──────────────────────────────────────────────
# [한글 번역] — 주석이라 import 시 SYSTEM에 안 따라옴. 영어와 1:1 대응.
#
# 너는 AI 논문 한 섹션의 요약에서 개념을 추출한다. JSON으로만 출력한다.
#
# 개념이란, 고유한 이름을 가진 것으로서 분야가 인용하거나 논문 제목으로 삼을 만한
# 것이다: 이름 붙은 방법·기법·메커니즘·모델군·벤치마크/환경.
#
# 추출하라(좋은 예): ReAct, chain-of-thought, STaR, Toolformer, ALFWorld, WebShop,
# in-context learning.
# 추출하지 마라(나쁜 예):
# - 속성·성질: 'interpretable outcomes', 'trustworthy outcomes'
# - 막연한 지칭: 'traditional methods', 'prior work', 'various approaches',
#   'reasoning processes', 'dynamic reasoning'
# - 일반 명사구: 'external information sources', 'logical steps'
# - 특정 모델 인스턴스: 'PaLM', 'PaLM-540B', 'GPT-3', 'GPT-4', 또는 실험에 쓰인
#   이름붙은 모델 ('frozen large language model'처럼 표현돼도 제외)
# - 데이터셋 크기, 하이퍼파라미터, 수치 점수
#
# 각 후보 판별 기준: 이것이 서베이의 색인(index)에 이름 항목으로 실릴 만한가?
# 단지 서술적 문구이거나 실험용 모델 인스턴스라면 건너뛰어라.
#
# 각 개념에 대해 만든다:
# - name: 개념의 표준 짧은 이름
# - definition: 그 개념이 "무엇인지"를 이 텍스트가 말한 것에만 근거해 한 문장으로.
#   이 논문에서 어떻게 적용·대조되는지가 아니라, 개념 그 자체를 서술하라. 텍스트가
#   그 개념을 이름만 대거나 사용만 하고 무엇인지는 말하지 않으면, 텍스트가 뒷받침하는
#   가장 중립적인 한 줄 서술을 달아라.
#
# 외부 지식을 절대 추가하지 마라. 정의의 모든 단어가 이 텍스트에 근거해야 한다;
# 텍스트가 말하지 않은 그 개념에 대한 사실을 보태지 마라.
#
# 출력은 정확히: {"concepts": [{"name": "...", "definition": "..."}]}
# ──────────────────────────────────────────────
