"""ReAct 에이전트 메인 루프.

핵심 흐름:
  user question
    → LLM (Thought + Action) [stop: "Observation:"]
    → 파싱: Final Answer면 종료, Action이면 도구 실행
    → Observation 메시지 추가 → 다시 LLM
"""
import os
import re
from dataclasses import dataclass, field
from dotenv import load_dotenv
from openai import OpenAI

from tools import Tool, ALL_TOOLS
from prompts import build_system_prompt, STOP_SEQUENCES


load_dotenv()


# ============================================================
# 파싱 헬퍼
# ============================================================
# Action: tool_name[argument]  형식 매칭
# - (\w+) : 도구 이름 (영숫자 + 언더스코어)
# - \[(.+?)\] : 대괄호 안 내용 (non-greedy로 첫 ']'까지)
# - re.DOTALL : argument 안에 줄바꿈 허용
_ACTION_PATTERN = re.compile(r"Action:\s*(\w+)\[(.+?)\]", re.DOTALL)

# Final Answer: ... 매칭 — 콜론 뒤 모든 내용
_FINAL_PATTERN = re.compile(r"Final Answer:\s*(.+)", re.DOTALL)


@dataclass
class StepLog:
    """한 사이클의 로그."""
    iteration: int
    llm_output: str
    action_name: str | None = None
    action_input: str | None = None
    observation: str | None = None
    final_answer: str | None = None


# ============================================================
# Agent
# ============================================================
@dataclass
class Agent:
    """ReAct 패턴으로 동작하는 단순 에이전트.
    
    Attributes:
        tools: 사용 가능한 도구. {name: Tool}
        model: 모델 식별자 (vLLM에 등록된 이름)
        max_iterations: 최대 사이클 (무한 루프 방지)
        temperature: 샘플링 온도
        verbose: 각 사이클 출력 여부
    """
    tools: dict[str, Tool] = field(default_factory=lambda: ALL_TOOLS)
    model: str = field(default_factory=lambda: os.getenv("MODEL_NAME"))
    max_iterations: int = 10
    temperature: float = 0.7
    verbose: bool = True
    
    def __post_init__(self):
        """dataclass 생성 후 OpenAI 클라이언트 초기화."""
        self.client = OpenAI(
            base_url=os.getenv("VLLM_BASE_URL"),
            api_key=os.getenv("VLLM_API_KEY"),
        )
        self.logs: list[StepLog] = []
    
    # --------------------------------------------------------
    # 단일 LLM 호출
    # --------------------------------------------------------
    def _call_llm(self, messages: list[dict]) -> str:
        """vLLM에 한 번 요청하고 응답 텍스트를 반환."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            stop=STOP_SEQUENCES,  # Observation: 직전에 멈춤
            max_tokens=512,        # Thought + Action 한 사이클 분량
        )
        return response.choices[0].message.content
    
    # --------------------------------------------------------
    # 응답 파싱
    # --------------------------------------------------------
    @staticmethod
    def _parse_response(text: str) -> tuple[str | None, str | None, str | None]:
        """LLM 출력에서 action 또는 final answer를 추출.
        
        Returns:
            (action_name, action_input, final_answer)
            셋 중 적절한 것만 채워지고 나머지는 None.
        """
        # Final Answer가 있으면 그게 우선
        final_match = _FINAL_PATTERN.search(text)
        if final_match:
            return None, None, final_match.group(1).strip()
        
        # Action 파싱
        action_match = _ACTION_PATTERN.search(text)
        if action_match:
            return action_match.group(1).strip(), action_match.group(2).strip(), None
        
        return None, None, None
    
    # --------------------------------------------------------
    # 메인 루프
    # --------------------------------------------------------
    def run(self, question: str) -> str:
        """질문을 받아 ReAct 루프를 돌리고 최종 답변을 반환."""
        self.logs = []  # 이력 초기화
        
        messages: list[dict] = [
            {"role": "system", "content": build_system_prompt(self.tools)},
            {"role": "user", "content": f"Question: {question}"},
        ]
        
        if self.verbose:
            print(f"\n{'='*60}\nQUESTION: {question}\n{'='*60}")
        
        for i in range(1, self.max_iterations + 1):
            # 1) LLM 호출
            llm_output = self._call_llm(messages)
            
            if self.verbose:
                print(f"\n--- Iteration {i} ---")
                print(llm_output)
            
            # 2) 파싱
            action_name, action_input, final_answer = self._parse_response(llm_output)
            
            log = StepLog(iteration=i, llm_output=llm_output)
            
            # 3) 종료 조건
            if final_answer is not None:
                log.final_answer = final_answer
                self.logs.append(log)
                if self.verbose:
                    print(f"\n{'='*60}\nFINAL: {final_answer}\n{'='*60}")
                return final_answer
            
            # 4) 액션이 없으면 에러 (LLM이 형식 어김)
            if action_name is None:
                error_msg = (
                    "Your response had no Action or Final Answer. "
                    "Please follow the format strictly: "
                    "either 'Action: tool[arg]' or 'Final Answer: ...'."
                )
                messages.append({"role": "assistant", "content": llm_output})
                messages.append({"role": "user", "content": f"Observation: {error_msg}"})
                log.observation = error_msg
                self.logs.append(log)
                continue
            
            # 5) 도구 실행
            log.action_name = action_name
            log.action_input = action_input
            
            tool = self.tools.get(action_name)
            if tool is None:
                observation = (
                    f"Error: tool '{action_name}' not found. "
                    f"Available: {list(self.tools.keys())}."
                )
            else:
                observation = tool.run(action_input)
            
            log.observation = observation
            self.logs.append(log)
            
            if self.verbose:
                print(f"Observation: {observation}")
            
            # 6) 이력에 추가하고 다음 사이클
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
        
        # 7) max_iterations 초과
        if self.verbose:
            print(f"\n{'='*60}\nMAX ITERATIONS REACHED\n{'='*60}")
        return f"[max_iterations={self.max_iterations} reached without a final answer]"
