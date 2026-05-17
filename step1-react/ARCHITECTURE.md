# Step 1 — ReAct 아키텍처와 구현 상세

## ReAct 패턴

ReAct는 2022년 논문 *"ReAct: Synergizing Reasoning and Acting in Language Models"* 에서
제안된 패턴이다. 핵심 통찰은 단순하다:

> LLM에게 행동만 하지 말고, 행동하기 전에 왜 그 행동을 하는지 글로 적게 하면
> 결과가 극적으로 좋아진다.

명시적인 추론 텍스트가 모델에게 자기 점검 기회를 주고, 우리(개발자)에게는
디버깅 단서를, 사용자에게는 신뢰도 평가를 가능케 한다.

### 한 사이클의 흐름

```
User question
    ↓
Thought    (LLM이 다음 행동을 추론)
    ↓
Action     (도구 호출 의도를 텍스트로 선언)
    ↓
[시스템이 도구 실행]
    ↓
Observation (도구 결과를 LLM에게 텍스트로 전달)
    ↓
Thought    (관찰 기반 재추론)
    ↓
... 반복 ...
    ↓
Final Answer
```

### LLM은 진짜로 "선택"하는 게 아니다

LLM은 어떤 도구를 호출할지 진짜로 결정하지 않는다. 우리가 시스템 프롬프트로
도구 목록과 형식을 알려주면, 모델은 학습된 텍스트 패턴 + 프롬프트 가이드에 따라
"calculator라는 토큰이 wikipedia_search보다 확률이 높다"는 식으로 텍스트를 생성한다.

진짜 함수 실행은 우리 Python 코드가 한다. LLM 출력은 본질적으로 텍스트일 뿐이다.

## 구현 결정

### 1. 도구 표현 — `@dataclass`

```python
@dataclass
class Tool:
    name: str
    description: str
    call: Callable[[str], str]
```

도구 메타데이터(LLM에게 알릴 정보)와 실행 함수를 한 객체에 묶었다.
이렇게 하면 도구 추가/수정 시 한 곳만 손대면 된다.

`run()` 메서드는 예외를 잡아서 에러 메시지를 문자열로 반환한다.
도구 실패가 에이전트를 죽이지 않고, 모델이 자기 교정할 수 있게 한다:

```
Action: calculator[2 + abc]
Observation: Error: SyntaxError: invalid syntax
Thought: 'abc'는 변수가 아니라서 안 되네. 다른 표현 시도하자.
Action: calculator[2 + 3]
```

### 2. 계산기 — AST 화이트리스트

`eval()`은 보안 재앙이다 (`__import__('os').system(...)` 같은 임의 코드 실행).
대신 `ast` 모듈로 표현식을 추상 구문 트리로 만든 다음, 허용된 노드 타입만 통과시킨다:

```python
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}
```

`BinOp`, `UnaryOp`, `Constant`만 허용. `Name`(변수), `Call`(함수 호출), `Attribute`(속성 접근)
같은 위험한 노드는 모두 거부.

### 3. Wikipedia — REST API 직접 호출

처음엔 `wikipedia` PyPI 패키지를 썼는데, 2014년에 마지막 업데이트라 위키미디어의
2024년 User-Agent 정책 강화에 대응 안 됨 (403 응답을 JSON으로 파싱 시도 → `JSONDecodeError`).

대안으로 `requests`로 위키 REST API를 직접 호출:

- `/api/rest_v1/page/summary/{title}` — 페이지 요약
- 404면 `/w/api.php?action=opensearch&...` 검색으로 fallback
- `User-Agent` 헤더 명시
- 응답 1000자로 자름 (LLM 컨텍스트 보호)
- 동음이의어 페이지는 후보 목록으로 변환

이 경험은 학습 가치가 컸다. 친절한 추상화일수록 깨졌을 때 디버깅이 어렵고,
외부 API 직접 호출 패턴은 에이전트 개발에서 매번 만난다.

### 4. 출력 형식 — ReAct 원본 그대로

```
Thought: [추론]
Action: tool_name[argument]
Observation: [결과]  ← 시스템이 채움
...
Final Answer: [최종 답변]
```

정규식 파싱이 단순하다:

```python
_ACTION_PATTERN = re.compile(r"Action:\s*(\w+)\[(.+?)\]", re.DOTALL)
_FINAL_PATTERN = re.compile(r"Final Answer:\s*(.+)", re.DOTALL)
```

`(.+?)` non-greedy가 중요: greedy로 하면 `wikipedia_search[Marie] and calc[12]` 같은
경우 첫 `]` 까지가 아니라 마지막 `]` 까지 잡힌다.

### 5. 한 호출 = 한 사이클 (stop sequence)

LLM에게 한 사이클(Thought + Action)만 출력하게 하고, Observation 직전에 멈추게 한다:

```python
STOP_SEQUENCES = ["Observation:", "\nObservation"]
```

vLLM의 `stop` 파라미터로 전달. 이게 안 통하면 LLM이 가짜 `Observation: 491`을
자기가 만들어내는 사고가 발생할 수 있다.

### 6. 메시지 누적 = 에이전트의 기억

LLM은 stateless다. 매 호출마다 모든 컨텍스트를 다시 보내야 한다.

```python
messages.append({"role": "assistant", "content": llm_output})
messages.append({"role": "user", "content": f"Observation: {observation}"})
```

사이클이 거듭될수록 messages가 길어진다. 사이클 1에서 했던 일을 사이클 5에서
LLM이 알 수 있는 건 이 누적 덕분이다.

## 결과 분석

### 쉬운 케이스 (T1~T3)

각 1~2 사이클로 깔끔히 끝남. 모델이 형식을 정확히 지킴.

### T4 — 9 사이클의 헛돌이

질문: *"What year was Albert Einstein born? Add 100 to that year."*

문제: 우리 wiki 도구는 5문장 요약만 반환하는데, Einstein 페이지의 요약에는
출생년도 1879가 없다.

모델의 행동:

1. wiki 검색 → 요약에 1879 없음 인지
2. `Albert Einstein birth year`로 재검색 → 404
3. **사이클 3에서 형식 어김**: 한 응답에 `Action`을 두 번 출력
   ("Wait, I already did that..." 같은 텍스트와 함께)
4. `biography`, `birth date`, `When was Einstein born?`, `Albert Einstein (physicist)` 등
   여러 변형 시도 → 모두 404
5. **사이클 8에서 결단**: "I actually know that Albert Einstein was born in 1879" →
   자기 지식으로 우회
6. `calculator[1879 + 100]` → 1979
7. Final Answer

### T4가 드러낸 것들

**도구 설계가 에이전트 동작을 좌우한다.**
문제의 진짜 원인은 모델이 아니라 wiki 도구가 약했던 것. 5문장 요약 + 정확한 제목 매치만
지원 → 모델이 정보를 못 찾고 헤맨다.

**텍스트 파싱 ReAct의 약점이 사이클 3에서 드러났다.**
모델이 자기 교정을 위해 한 응답 안에 여러 Action을 적었다. Stop sequence는
`Observation:` 문자열만 막을 뿐, 모델이 텍스트를 더 적는 건 못 막는다.
우리 정규식은 첫 매치만 잡으므로 후속 Action은 무시됨.

**자기 한계를 인지하는 메타 결정.**
사이클 8의 "도구로 못 찾는다 → 내부 지식 사용" 결정은 단순 도구 호출 LLM은
하지 못하는 일이다. 명시적 Thought 출력이 이런 결정을 가능케 한다.

**비효율은 인터페이스가 아닌 도구의 문제.**
9 사이클은 학습용으로는 가치 있지만 프로덕션 기준엔 부족. 다음 단계들
(메모리, RAG, 더 강력한 도구)이 이 문제를 해결한다.

## 다음 단계와의 비교

| 항목 | Step 1 (텍스트 파싱) | Step 2 (Function calling) |
|---|---|---|
| 도구 정보 전달 | 시스템 프롬프트 텍스트 | API `tools` 인자 (JSON Schema) |
| LLM 출력 | 자유 텍스트 | 별도 `tool_calls` 필드 |
| 파싱 | 우리 정규식 | API가 자동 |
| 형식 어김 | 자주 (사이클 3 사례) | 거의 없음 |
| Stop sequence | 필요 | 불필요 |
| 시스템 프롬프트 | ~2200자 | ~150자 |
| 단일/복수 인자 | 단일 문자열 | JSON 객체 (복수 가능) |
| 병렬 도구 호출 | 불가 | 가능 |

자세한 비교는 [step2의 ARCHITECTURE.md](../step2-function-calling/ARCHITECTURE.md) 참고.
