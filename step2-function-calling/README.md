# Step 2 — Function calling ReAct 에이전트

같은 ReAct 패턴을 **Function calling** 방식으로 다시 구현한다.
도구를 JSON Schema로 정의하고, LLM은 별도 `tool_calls` 필드로 구조화된 호출을 반환한다.
1단계의 텍스트 파싱이 사라지고, 형식 안정성이 크게 올라간다.

깊이 있는 설계 설명과 1단계 비교는 [ARCHITECTURE.md](ARCHITECTURE.md) 참고.

## 무엇을 배우는가

- Function calling의 본질: 텍스트 파싱이 아닌 구조화된 API 채널
- JSON Schema로 도구 시그니처 정의하는 법
- OpenAI 호환 API의 `tools=[...]` + `tool_choice="auto"` 패턴
- `role: "tool"` 메시지와 `tool_call_id` 매칭
- Gemma 4 thinking 모드 (`reasoning` 필드) 활용
- 1단계와의 비교를 통한 두 방식의 trade-off 이해

## 파일 구성

| 파일 | 역할 |
|---|---|
| `agent.py` | Function calling 기반 ReAct 루프 |
| `tools.py` | 도구 정의 (JSON Schema 포함) |
| `run.py` | 1단계와 동일한 4개 테스트 케이스 |

`prompts.py`는 없다. 시스템 프롬프트가 한 줄로 줄어들어 `agent.py` 안에 상수로 둠.

## 사전 조건

vLLM 서버는 다음 옵션으로 떠 있어야 한다 (메인 README 참고):

```bash
vllm serve cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit \
  --enable-auto-tool-choice \
  --reasoning-parser gemma4 \
  --tool-call-parser gemma4 \
  ...
```

이 세 옵션이 Function calling + Gemma 4 thinking 모드 활성화의 핵심.

## 실행

```bash
cd step2-function-calling
uv sync
source .venv/bin/activate

# 기본 모드
python run.py

# Thinking 모드 (모델의 추론 과정 표시)
python run.py thinking
```

특정 질문 시도:

```python
from agent import Agent

# 기본 (간결)
agent = Agent(verbose=True)
answer = agent.run("What is 17 * 23 + 100?")

# Thinking 모드 (추론 과정 표시)
agent = Agent(verbose=True, show_reasoning=True)
answer = agent.run("What year was Albert Einstein born? Add 100 to that year.")
```

## 테스트 케이스 (1단계와 동일)

| 케이스 | 질문 | 의도 |
|---|---|---|
| T1 | "Hi, how are you today?" | 도구 없이 답변 |
| T2 | "What is 17 * 23 + 100?" | 계산기만 사용 |
| T3 | "Who is Marie Curie? Give me one sentence." | 위키만 사용 |
| T4 | "What year was Albert Einstein born? Add 100 to that year." | 두 도구 모두, 멀티스텝 |

## 핵심 결과

| 케이스 | Step 1 (텍스트 파싱) | Step 2 (FC, thinking off) | Step 2 (FC, thinking on) |
|---|---|---|---|
| T1 | 1 사이클 | 1 사이클 | 1 사이클 |
| T2 | 2 사이클 | 2 사이클 | 2 사이클 |
| T3 | 2 사이클 | 2 사이클 | 2 사이클 |
| **T4** | **9 사이클** | **6 사이클** | **5 사이클** |

T4의 헛도는 문제(wiki 요약에 birth year 없음)는 그대로지만, 사이클 수가 줄었다.
어려운 케이스에서만 인터페이스 차이가 드러난다. 자세한 분석은
[ARCHITECTURE.md](ARCHITECTURE.md) 참고.

## 1단계 대비 변화 요약

| 항목 | Step 1 | Step 2 |
|---|---|---|
| 도구 정보 전달 | 시스템 프롬프트 텍스트 | API `tools` 인자 |
| LLM 출력 | 자유 텍스트 (Action: tool[arg]) | `tool_calls` 필드 (구조화) |
| 파싱 | 우리 정규식 | API가 자동 처리 |
| Stop sequence | 필요 (`Observation:`) | 불필요 |
| 형식 어김 | 자주 발생 | 거의 없음 |
| 시스템 프롬프트 | ~2200자 | ~150자 |
| 인자 형식 | 단일 문자열 | JSON 객체 (복수 가능) |
| 병렬 도구 호출 | 불가 | 가능 |
| 추론 채널 | content에 섞임 | `reasoning` 필드로 분리 가능 |
| 응답 자연스러움 | `Final Answer:` prefix | 평범한 답변 |

## 다음 단계

T4가 보여준 본질적 한계는 인터페이스가 아니라 **도구의 정보 부족**이었다.
3단계 이후에서 다룬다:

- 3단계: 메모리 + RAG (도구 결과의 한계를 벡터 검색으로 보완)
- 4단계: LangGraph (상태 그래프 기반 에이전트 오케스트레이션)
- 5단계: MCP (도구를 표준 프로토콜로 외부화)
