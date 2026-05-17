# 학습 흐름 개요

이 문서는 단계별 학습 내용을 가로지르며 보는 cross-cutting 자료다.
각 단계의 깊은 내용은 해당 폴더의 `ARCHITECTURE.md` 참고.

## 큰 그림 — 왜 이 순서인가

AI 에이전트는 짧은 시간에 빠르게 진화한 분야다. 학습 순서를
**역사적 진화 순서**로 따라가면 "왜 이런 패턴이 만들어졌는지" 자연스럽게 이해된다.

```
1. 텍스트 파싱 ReAct (2022, 학술적)
        ↓ 형식 안정성 부족
2. Function calling (2023, 산업 표준)
        ↓ 컨텍스트·도구 한계
3. 메모리 + RAG (벡터 검색으로 정보 풍부화)
        ↓ 복잡한 상태 관리 어려움
4. LangGraph (상태 그래프 기반 오케스트레이션)
        ↓ 도구 통합의 표준 부재
5. MCP (Model Context Protocol, 2024년 등장)
        ↓ 단일 에이전트의 한계
6. 멀티 에이전트 / 자율 실행
```

각 단계는 이전 단계가 풀지 못한 문제를 해결한다. 그래서 다음 단계의 동기가
명확히 드러난다.

## 단계 1 vs 단계 2 — 핵심 비교 매트릭스

| 항목 | Step 1 (텍스트 파싱) | Step 2 (Function calling) |
|---|---|---|
| **도구 정보 전달** | 시스템 프롬프트에 자연어로 | API `tools=[...]` 인자, JSON Schema |
| **도구 설명 분리** | 단일 description | 도구 + 인자별 description |
| **LLM 응답 형식** | 자유 텍스트 (`Action: tool[arg]`) | 구조화된 `tool_calls` 필드 |
| **응답 파싱** | 우리 정규식 | vLLM 자동 (`--tool-call-parser gemma4`) |
| **Stop sequence** | 필요 (`Observation:`) | 불필요 |
| **형식 어김 빈도** | 양자화 모델에서 자주 (사이클 3 사례) | 거의 없음 |
| **인자 형식** | 단일 문자열 | JSON 객체 (다중 인자) |
| **병렬 도구 호출** | 불가 | 가능 |
| **추론 채널** | content에 섞임 | `content`(답변) + `reasoning`(추론) 분리 |
| **시스템 프롬프트** | ~2200자 (도구 설명 + 형식 + few-shot) | ~150자 |
| **few-shot 예시** | 필수 (형식 안정화용) | 불필요 |
| **응답 자연스러움** | `Final Answer:` prefix 등 | 평범한 채팅 |
| **T4 사이클 수** | 9 | 5~6 |
| **디버깅 가치 (모델 사고 보기)** | 中 (content에 노출되나 형식 어김 동반) | 高 (thinking 모드 시) |

## T4로 보는 진화

같은 질문 *"What year was Albert Einstein born? Add 100 to that year."* 으로
세 모드 비교. wiki 도구의 5문장 요약에 1879가 없는 게 공통 함정.

| 모드 | 사이클 | 형식 어김 | 모델 사고 가시성 |
|---|---|---|---|
| Step 1 텍스트 파싱 | 9 | 사이클 3 (Action 두 번 출력) | content에 섞임 |
| Step 2 thinking off | 6 | 없음 | 거의 안 보임 |
| Step 2 thinking on | 5 | 없음 | reasoning 필드에 명시적 |

**핵심 통찰**: 사이클 수 감소(9→5)는 인터페이스 개선 덕분이지만,
**본질적 문제(도구 정보 부족)는 그대로**. 진짜 해결은 도구 자체를 개선하는 것 →
이게 다음 단계들의 동기.

## 변하지 않은 것 — ReAct 패턴 자체

두 단계 모두 본질은 같다:

```
Thought → Action → [도구 실행] → Observation → Thought → ... → Final Answer
```

Function calling은 ReAct를 **대체하지 않는다**. ReAct를 **표현하는 방식**을
표준화한 것뿐이다. 같은 패턴, 다른 인터페이스.

이는 학습 차원에서 중요하다: 새 기술이 옛 기술의 본질을 대체하는 경우는 드물고,
대부분은 **인터페이스가 진화**한다. 본질을 알면 어떤 인터페이스든 빠르게 적응 가능.

## 코드 양 비교

| 파일 | Step 1 | Step 2 |
|---|---|---|
| `agent.py` | ~140줄 | ~135줄 |
| `tools.py` | ~180줄 | ~180줄 |
| `prompts.py` | ~85줄 | (없음) |
| `run.py` | ~50줄 | ~60줄 |
| **합계** | **~455줄** | **~375줄** |

비슷한 분량이지만 Step 2 쪽이 단순하다 (prompts.py 통째로 사라짐, agent.py 내부도
정규식·stop sequence 처리 빠짐). 시스템 프롬프트가 짧아진 만큼 코드 책임이 줄었다.

## 양자화 모델(Gemma 4 26B-A4B AWQ 4-bit)의 실력

학습 전 우려: 4-bit 양자화 모델이 tool calling 정확도가 떨어지지 않을까?

실제 결과:
- ✅ JSON Schema 정확히 따름 (한 번도 형식 어김 없음)
- ✅ Function calling 자연스럽게 사용
- ✅ Thinking 모드 잘 동작 (사고 흐름이 사람 같음)
- ✅ 자기 한계 인지 + 우회 결정 (T4 사이클 5의 "그냥 내 지식 쓰자")
- ✅ 한국어 응답 가능
- ⚠️ 시스템 프롬프트의 미세 가이드는 가끔 무시 ("Before calling a tool, briefly explain...")

결론: 학습용으로는 31B Dense를 받을 필요 없다. 26B MoE AWQ면 충분.

## OpenAI 호환 API의 가치

코드가 vLLM이 아닌 다른 API로도 거의 그대로 동작한다:

```python
client = OpenAI(
    base_url="http://localhost:8000/v1",       # vLLM (지금)
    # base_url="https://api.openai.com/v1",   # OpenAI GPT-4o
    # base_url="https://api.together.xyz/v1", # Together AI
    # base_url="https://api.groq.com/openai/v1", # Groq
    api_key="...",
)
```

`tools=[...]`, `tool_choice="auto"`, `message.tool_calls` 모두 동일. 우리가 Step 2에서
짠 코드는 사실상 어디든 이식 가능하다.

Anthropic Claude API만 약간 다른 형식인데(`content` 안의 `tool_use` 블록), `litellm` 같은
호환 라이브러리로 추상화 가능.

## 다음 단계 예고

### 3단계: 메모리 + RAG

T4의 헛도는 검색 문제는 본질적으로 **도구 결과의 정보 부족**과 **반복 호출 캐싱 부재** 때문.
이걸 해결하는 패턴:

- **벡터 DB** (ChromaDB, Qdrant 등)로 풍부한 의미 검색
- **단기 메모리**: 사이클 내 캐싱
- **장기 메모리**: 세션 간 학습 결과 보존

### 4단계: LangGraph

지금까지 명령적 `for` 루프로 사이클을 돌렸지만, 복잡한 에이전트는 **상태 그래프**로
표현하는 게 깔끔하다. LangGraph는 현재 업계 사실상 표준.

### 5단계: MCP

도구를 코드 안에 박지 않고 **외부 서버**로 분리. 표준 프로토콜로 통신.
Claude Desktop, Cursor 등이 이미 채택한 표준.

### 6단계: 멀티 에이전트 / 자율 실행

한 에이전트가 모든 걸 하는 게 아니라 역할 분담 + 협업. 또는 사람 개입 없이
긴 작업 수행하는 자율 모드.

---

각 단계 진행 중 결정사항이나 발견은 [reflections.md](reflections.md)에 누적 기록.
