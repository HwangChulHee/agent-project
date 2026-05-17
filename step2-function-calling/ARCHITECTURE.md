# Step 2 — Function calling 아키텍처와 구현 상세

## Function calling이란

OpenAI가 2023년 도입하고 이후 거의 모든 LLM API가 채택한 표준이다. 핵심 변화:

> 도구 정보를 시스템 프롬프트의 자유 텍스트가 아니라 **API의 별도 인자**로 전달하고,
> LLM 응답도 자유 텍스트가 아니라 **별도의 구조화된 필드**로 받는다.

결과적으로:

- LLM이 형식을 어길 가능성이 거의 사라진다
- 파싱이 자동화된다 (vLLM이 처리)
- 다중 인자, 병렬 호출 같은 복잡한 시나리오가 자연스러워진다

ReAct 패턴 자체는 그대로다. Thought → Action → Observation → 반복. 단지 **표현 방식**이
구조화되었을 뿐이다.

## 업계 표준 — 거의 같은 형식

| 항목 | OpenAI | Anthropic Claude | vLLM | Google Gemini |
|---|---|---|---|---|
| 도구 정의 | `tools=[...]` | `tools=[...]` | `tools=[...]` | `tools=[...]` |
| 스키마 | JSON Schema | JSON Schema | JSON Schema | JSON Schema |
| 결정 모드 | `tool_choice` | `tool_choice` | `tool_choice` | `tool_config` |
| 응답 필드 | `tool_calls` | `content` 내 `tool_use` 블록 | `tool_calls` | `function_call` |

OpenAI가 사실상 표준이라 vLLM도 OpenAI 호환 API로 제공한다. 본 프로젝트의 코드는
`base_url`만 바꾸면 OpenAI API, Together AI, Groq 등 어디서나 동작한다.

## 구현 결정

### 1. Tool 클래스에 JSON Schema 추가

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON Schema
    call: Callable
    
    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
```

1단계 대비 `parameters` 필드가 추가됐다. JSON Schema 표준 형식:

```python
parameters={
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "Math expression to evaluate, e.g. '2 + 3 * 4'.",
        },
    },
    "required": ["expression"],
}
```

`description`이 두 위치에 들어가는 게 중요:
- 도구 자체의 description → "언제 이 도구를 쓰는가"
- 인자별 description → "이 인자에 무엇을 채우는가"

1단계에선 이걸 하나의 description에 우겨넣어야 했다.

### 2. `run()` 메서드가 `**kwargs`

```python
def run(self, **kwargs) -> str:
    try:
        return str(self.call(**kwargs))
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
```

LLM이 생성한 JSON `{"expression": "17*23+100"}`이 dict로 파싱되고
`**kwargs`로 펼쳐져서 `calculate(expression="17*23+100")`로 호출된다.

다중 인자도 자연스럽다. `{"city": "Seoul", "unit": "celsius"}` → `f(city="Seoul", unit="celsius")`.

### 3. LLM 호출 — 핵심 두 인자

```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=messages,
    tools=self._tools_schema,    # ← 도구 정보 별도 전달
    tool_choice="auto",           # ← 모델이 도구 사용 여부 자동 결정
    max_tokens=2048,
    extra_body=self._extra_body,  # thinking 모드용 (옵션)
)
```

`tool_choice` 옵션:
- `"none"`: 도구 호출 금지
- `"auto"`: 모델이 결정 ← 우리는 이것
- `{"name": "특정함수"}`: 강제 호출

`stop` 파라미터가 없는 것에 주목. Function calling에선 구조적으로 가짜 결과 생성이 불가능하므로 stop sequence 불필요.

### 4. 응답 처리 — 필드 분기

```python
message = response.choices[0].message

if not message.tool_calls:
    # 도구 호출 없음 → 최종 답변
    return message.content

# 도구 호출 있음 → 실행
for call in message.tool_calls:
    name = call.function.name
    args = json.loads(call.function.arguments)
    result = self.tools[name].run(**args)
    
    messages.append({
        "role": "tool",
        "tool_call_id": call.id,
        "content": result,
    })
```

`message.tool_calls`의 존재 여부로 깔끔히 분기. 정규식 없음.

새로 등장한 두 가지:
- `role: "tool"` — 도구 결과 전용 role
- `tool_call_id` — 어느 호출의 결과인지 명시 (병렬 호출 매칭용)

### 5. 시스템 프롬프트가 한 줄

```python
SYSTEM_PROMPT = (
    "You are a helpful assistant. Use the provided tools when needed "
    "to answer accurately. If you can answer without tools, do so.\n\n"
    "Before calling a tool, briefly explain in 1-2 sentences why you're "
    "calling it. Keep these explanations concise."
)
```

1단계의 2200자 → 150자. 도구 목록, 형식 가이드, few-shot 예시 모두 사라짐.
도구 정보는 `tools` 인자가 책임진다.

마지막 두 문장은 옵션이다 — Gemma 4 같은 모델은 도구 호출만 하고 추론 텍스트를
content에 안 적는 경향이 있어서, 디버깅을 위해 짧은 설명을 요구한다. 다만 양자화 모델은
이 가이드를 가끔 무시한다.

### 6. Gemma 4 Thinking 모드

vLLM 서버에 `--reasoning-parser gemma4` 옵션을 켜두면 Gemma 4의 native thinking 모드를
활용할 수 있다. 활성화는 요청 시:

```python
extra_body={"chat_template_kwargs": {"enable_thinking": True}}
```

활성화되면 응답의 `reasoning` 필드(또는 일부 환경에선 `reasoning_content`)에 모델의
내부 추론이 분리되어 들어온다:

```json
{
  "content": "The result is 491.",
  "reasoning": "The user wants 17 * 23 + 100. I need to use the calculator tool...",
  "tool_calls": [...]
}
```

**주의**: vLLM nightly는 `reasoning` 필드명을 쓰는데, 일부 모델 문서는 `reasoning_content`로
적혀있다. 실제 응답을 보고 확인해야 한다. 우리 코드는 `getattr(message, "reasoning", None)`
로 안전하게 접근.

## 결과 분석 — T4 비교

T4: *"What year was Albert Einstein born? Add 100 to that year."*
(wiki 도구의 5문장 요약에 birth year 1879가 없는 상황)

### Step 1 (텍스트 파싱) — 9 사이클

- 사이클 1: wiki 검색, 요약에 birth year 없음 인지
- 사이클 2~7: 다양한 검색어 변형 시도, 모두 실패
- **사이클 3에서 형식 어김**: 한 응답에 Action 두 번 출력
- 사이클 8: 결국 자기 지식 사용 결정, calculator 호출
- 사이클 9: Final Answer

### Step 2 thinking off — 6 사이클

- 사이클 1~3: wiki 검색 시도 (`Albert Einstein`, `birth date`, `Albert Einstein` 반복)
- 사이클 4: `biography` 시도, 실패
- 사이클 5: `Albert Einstein` 다시 시도, 실패
- 사이클 6: 자기 지식 + calculator + Final Answer 한 사이클에

content에 추론 텍스트가 거의 없어서 모델이 왜 그런 결정을 했는지 안 보임.
형식 어김은 없음.

### Step 2 thinking on — 5 사이클

`reasoning` 필드에 풍부한 사고 흐름:

```
[Thinking]
사용자가 두 가지를 묻고 있다: 1) 출생년도, 2) +100.
먼저 wiki로 출생년도를 찾자. 안 되면 내부 지식 쓰자.
```

사이클 3에서 명시적으로 갈등을 표현:
```
[Thinking]
내부 지식 쓸까... 하지만 명령은 도구 써야 한다고 했어.
"Albert Einstein" 다시? 했잖아.
"Albert Einstein biography"로 가자.
```

사이클 5에서 결단:
```
[Thinking]
Wikipedia 검색이 너무 구체적이거나 실패. 그냥 calculator에 1879로 가자.
```

추론은 풍부하지만 content와 tool_calls는 깔끔. 디버깅 가치가 가장 높다.

### 종합 비교

| 항목 | Step 1 | Step 2 off | Step 2 on |
|---|---|---|---|
| 총 사이클 (T4) | 9 | 6 | 5 |
| 헛도는 패턴 표현 | content에 섞임 | 침묵 | reasoning에 분리 |
| 자기 갈등 표현 | 형식 어김으로 이어짐 | 없음 | 깨끗이 분리 |
| 포기 결단 시점 | 사이클 8 | 사이클 6 | 사이클 5 |
| content 깨끗함 | 어김 있음 | 매우 깨끗 | 매우 깨끗 |
| 디버깅 가치 | 中 | 低 | 高 |

## 핵심 관찰

### 1. 인터페이스 개선 ≠ 본질 해결

사이클 수는 줄었지만 **wiki 도구의 정보 부족**이라는 본질 문제는 그대로다.
진짜 해결책은 도구를 개선하는 것 — birth year를 직접 추출하는 도구가 있었다면
1 사이클에 끝났다. 이게 다음 단계들(메모리, RAG, MCP)의 동기.

### 2. Thinking 모드의 가치

`reasoning` / `content` / `tool_calls` 세 채널 분리가 현대 에이전트의 표준 구조다.
OpenAI o1/o3, Claude의 extended thinking, Gemini의 thinking 모두 같은 패턴.

- `reasoning`: 깊은 사고 (디버깅·해석용)
- `content`: 사용자에게 보여줄 답변 (UX용)
- `tool_calls`: 도구 호출 (실행용)

1단계는 이 셋이 한 텍스트에 섞여서 형식 깨짐 위험 있었다. 2단계+thinking은 깔끔히 분리.

### 3. 양자화 모델의 실력

26B AWQ 4-bit가 다음을 모두 안정적으로 수행:
- JSON Schema 정확히 따르기
- Function calling 자연스러운 사용
- Thinking 모드 활용 (사고 흐름이 사람 같음)
- 자기 한계 인지 + 우회 결정

학습용으로 충분 이상. 31B Dense는 굳이 안 받아도 될 수준.

### 4. 시스템 프롬프트 가이드는 양자화 모델에 약함

`"Before calling a tool, briefly explain..."` 가이드를 추가했지만 양자화 모델은
가끔 무시하고 곧장 도구만 호출한다. 풀 정밀도 모델이라면 거의 확실히 따랐을 가이드.
Thinking 모드를 켜면 이 한계가 보완된다.

## 한계와 다음 단계

Function calling이 1단계의 형식 문제를 거의 모두 해결했지만, 여전히 남은 문제:

1. **메시지 누적 비대화**: 사이클이 많을수록 messages가 폭발. T4의 6 사이클 후
   messages는 ~14개. 30 사이클 작업이면 컨텍스트 한도 도달.
2. **반복 호출 캐싱 없음**: 사이클 3에서 1과 동일한 wiki 검색 반복.
3. **도구 자체의 정보 부족**: wiki 5문장 요약은 단순 정보엔 충분하지만 멀티스텝엔 부족.

이 문제들을 다음 단계가 다룬다:
- 메모리 + RAG: 더 풍부한 검색, 컨텍스트 압축
- LangGraph: 명시적 상태 관리, 캐싱 가능
- MCP: 표준 프로토콜로 도구 공유 가능
