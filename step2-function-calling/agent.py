"""ReAct 에이전트 — Function calling 버전.

Style A (1단계)와의 차이:
- 시스템 프롬프트가 짧아짐 (도구 정보는 tools 인자로 별도 전달)
- 정규식 파싱 없음 (response.tool_calls 필드 사용)
- Stop sequence 없음 (구조적으로 불필요)
- 메시지에 새 role "tool" 등장
"""
import json
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from openai import OpenAI

from tools import Tool, ALL_TOOLS, get_openai_tools_schema


load_dotenv()


# ============================================================
# 시스템 프롬프트 — 한 줄로 끝
# ============================================================
SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the provided tools when needed "
    "to answer accurately. If you can answer without tools, do so.\n\n"
    "Before calling a tool, briefly explain in 1-2 sentences why you're "
    "calling it. Keep these explanations concise."
)


@dataclass
class StepLog:
    """한 사이클의 로그."""
    iteration: int
    assistant_text: str | None = None
    tool_calls: list[dict] = field(default_factory=list)  # [{name, args, result}]
    final_answer: str | None = None


# ============================================================
# Agent
# ============================================================
@dataclass
class Agent:
    """Function calling 기반 ReAct 에이전트."""
    tools: dict[str, Tool] = field(default_factory=lambda: ALL_TOOLS)
    model: str = field(default_factory=lambda: os.getenv("MODEL_NAME"))
    max_iterations: int = 10
    temperature: float = 0.7
    verbose: bool = True
    show_reasoning: bool = False
    
    def __post_init__(self):
        self.client = OpenAI(
            base_url=os.getenv("VLLM_BASE_URL"),
            api_key=os.getenv("VLLM_API_KEY"),
        )
        self.logs: list[StepLog] = []
        # 도구 schema는 한 번만 생성해서 재사용
        self._tools_schema = get_openai_tools_schema(self.tools)
        self._extra_body = (
            {"chat_template_kwargs": {"enable_thinking": True}}
            if self.show_reasoning else {}
        )
    
    # --------------------------------------------------------
    def _call_llm(self, messages: list[dict]):
        """LLM 호출. 응답 message 객체 그대로 반환."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self._tools_schema,        # ← 도구 정보 별도 전달
            tool_choice="auto",               # ← "auto"가 핵심: 모델이 결정
            temperature=self.temperature,
            max_tokens=2048,
            extra_body=self._extra_body,
        )
        return response.choices[0].message
    
    # --------------------------------------------------------
    def _execute_tool_call(self, call) -> str:
        """단일 도구 호출 실행."""
        name = call.function.name
        args_json = call.function.arguments  # 항상 JSON 문자열
        
        # JSON 파싱
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError as e:
            return f"Error: invalid JSON arguments: {e}"
        
        # 도구 lookup
        tool = self.tools.get(name)
        if tool is None:
            return f"Error: tool '{name}' not found. Available: {list(self.tools.keys())}"
        
        return tool.run(**args)
    
    # --------------------------------------------------------
    def run(self, question: str) -> str:
        """질문을 받아 루프를 돌리고 최종 답변을 반환."""
        self.logs = []
        
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        
        if self.verbose:
            print(f"\n{'='*60}\nQUESTION: {question}\n{'='*60}")
        
        for i in range(1, self.max_iterations + 1):
            # 1) LLM 호출
            message = self._call_llm(messages)
            
            log = StepLog(iteration=i, assistant_text=message.content)
            
            if self.verbose:
                print(f"\n--- Iteration {i} ---")
                # Gemma 4 thinking 모드: reasoning_content가 있으면 표시
                # vLLM nightly가 OpenAI 컨벤션을 따라 "reasoning" 필드 사용
                # (일부 문서는 "reasoning_content"로 쓰지만 우리 환경에선 "reasoning")
                reasoning = getattr(message, "reasoning", None)
                if reasoning:
                    print(f"[Thinking] {reasoning}")
                if message.content:
                    print(f"Assistant: {message.content}")
            
            # 2) 종료 조건: 도구 호출이 없으면 최종 답변
            if not message.tool_calls:
                log.final_answer = message.content or ""
                self.logs.append(log)
                if self.verbose:
                    print(f"\n{'='*60}\nFINAL: {log.final_answer}\n{'='*60}")
                return log.final_answer
            
            # 3) assistant 메시지 그대로 추가 (tool_calls 포함된 채로)
            messages.append(message)
            
            # 4) 각 도구 호출 실행 → role="tool" 메시지로 결과 추가
            for call in message.tool_calls:
                result = self._execute_tool_call(call)
                
                log.tool_calls.append({
                    "name": call.function.name,
                    "args": call.function.arguments,
                    "result": result,
                })
                
                if self.verbose:
                    print(f"Tool: {call.function.name}({call.function.arguments})")
                    print(f"Result: {result}")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,    # 호출과 결과 매칭
                    "content": result,
                })
            
            self.logs.append(log)
        
        # max_iterations 초과
        if self.verbose:
            print(f"\n{'='*60}\nMAX ITERATIONS REACHED\n{'='*60}")
        return f"[max_iterations={self.max_iterations} reached without a final answer]"
