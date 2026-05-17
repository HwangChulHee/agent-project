"""ReAct 에이전트의 시스템 프롬프트.

이 모듈의 핵심은 build_system_prompt() 함수다.
도구 목록을 받아 LLM에게 보여줄 시스템 프롬프트 전체를 만든다.

설계 결정 (자세한 내용은 학습 노트 참고):
- 출력 형식: Thought / Action: tool[arg] / Observation / Final Answer
- 한 호출 = 한 사이클 (stop sequence로 Observation 직전에 끊음)
- Action 형식: tool_name[argument]  (단일 문자열 인자만)
- Few-shot 예시 1개
"""
from tools import Tool, ALL_TOOLS, format_tools_for_prompt


# ============================================================
# Stop sequence — agent.py에서 사용
# ============================================================
# LLM이 "Observation:"을 만들기 시작하면 멈추게 한다.
# 왜? Observation은 우리가(도구 실행 결과로) 채우는 부분이지,
# LLM이 hallucinate하면 안 되니까.
STOP_SEQUENCES = ["Observation:", "\nObservation"]


# ============================================================
# Few-shot 예시 — 시스템 프롬프트에 끼워넣을 동작 시범
# ============================================================
# 이 예시 하나로 LLM이 패턴을 학습한다:
# - Thought 먼저, Action 다음 순서
# - Action 형식: tool_name[argument]
# - 여러 사이클 가능
# - 마지막엔 Final Answer
_FEW_SHOT_EXAMPLE = """\
Example interaction:

Question: What is the capital of the country where Marie Curie was born, and what is 12 * 13?

Thought: I need two pieces of information. First, the birthplace country of Marie Curie. Let me search Wikipedia.
Action: wikipedia_search[Marie Curie]
Observation: [Marie Curie] Maria Salomea Skłodowska Curie was a Polish and naturalised-French physicist and chemist...

Thought: She was Polish, so she was born in Poland. The capital of Poland is Warsaw. Now I need to calculate 12 * 13.
Action: calculator[12 * 13]
Observation: 156

Thought: I have both pieces of information now.
Final Answer: Marie Curie was born in Poland, whose capital is Warsaw. 12 * 13 = 156.
"""


# ============================================================
# 시스템 프롬프트 본체
# ============================================================
_SYSTEM_PROMPT_TEMPLATE = """\
You are a ReAct (Reasoning + Acting) agent. You solve tasks by alternating between thinking and taking actions.

You have access to the following tools:

{tools_description}

Use the following format for your responses:

Thought: [your reasoning about what to do next]
Action: tool_name[argument]

After your Action, the system will execute the tool and return:

Observation: [the tool's output]

Then continue with another Thought and Action, or finish with:

Final Answer: [your answer to the original question]

Important rules:
- Output ONE Thought + Action per turn, then STOP and wait for the Observation.
- Do NOT write the Observation yourself. The system provides it.
- Action must use exactly this format: tool_name[argument]
- The argument is a single string, no quotes around it.
- If you can answer without tools, write Final Answer directly.
- If a tool returns an error, read it carefully and adjust your next Action.

{few_shot}
Now begin. Stay strict with the format."""


def build_system_prompt(tools: dict[str, Tool] = ALL_TOOLS) -> str:
    """주어진 도구 셋으로 시스템 프롬프트 전체를 생성한다.
    
    Args:
        tools: 이 에이전트가 쓸 수 있는 도구들. 기본은 ALL_TOOLS.
    
    Returns:
        LLM에 system role로 전달할 완성된 프롬프트 문자열.
    """
    return _SYSTEM_PROMPT_TEMPLATE.format(
        tools_description=format_tools_for_prompt(tools),
        few_shot=_FEW_SHOT_EXAMPLE,
    )
