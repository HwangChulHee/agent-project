# Step 1 — 텍스트 파싱 ReAct 에이전트

ReAct(Reasoning + Acting) 패턴을 프레임워크 없이 순수 Python으로 구현한다.
LLM 출력을 정규식으로 파싱해서 도구 호출을 추출하는 가장 본질적인 방식.

깊이 있는 설계 설명과 결과 분석은 [ARCHITECTURE.md](ARCHITECTURE.md) 참고.

## 무엇을 배우는가

- ReAct 패턴의 본질: Thought → Action → Observation 루프
- LLM에게 도구를 텍스트로 알리는 방법 (시스템 프롬프트)
- 모델 출력에서 도구 호출을 정규식으로 추출
- Stop sequence로 모델이 가짜 결과 만드는 걸 차단
- 메시지 누적으로 컨텍스트 유지

## 파일 구성

| 파일 | 역할 |
|---|---|
| `agent.py` | ReAct 메인 루프 (Agent 클래스) |
| `tools.py` | 도구 정의 (calculator, wikipedia_search) |
| `prompts.py` | 시스템 프롬프트 + few-shot 예시 |
| `run.py` | 테스트 케이스 4개 실행 |
| `smoke_test.py` | vLLM 연결 확인용 (학습 초기) |

## 사전 조건

- vLLM 서버가 `localhost:8000`에서 실행 중 (메인 README 참고)
- 가상환경 활성화

```bash
cd step1-react
uv sync              # 첫 실행이면 의존성 복원
source .venv/bin/activate
```

## 실행

전체 테스트:

```bash
python run.py
```

연결만 확인:

```bash
python smoke_test.py
```

특정 질문만 시도:

```python
from agent import Agent
agent = Agent(verbose=True)
answer = agent.run("What is 17 * 23 + 100?")
print(answer)
```

## 테스트 케이스

| 케이스 | 질문 | 의도 |
|---|---|---|
| T1 | "Hi, how are you today?" | 도구 없이 답변 |
| T2 | "What is 17 * 23 + 100?" | 계산기만 사용 |
| T3 | "Who is Marie Curie? Give me one sentence." | 위키만 사용 |
| T4 | "What year was Albert Einstein born? Add 100 to that year." | 두 도구 모두, 멀티스텝 |

## 핵심 결과

| 케이스 | 사이클 수 | 도구 호출 |
|---|---|---|
| T1 | 1 | 0 |
| T2 | 2 | 1 |
| T3 | 2 | 1 |
| T4 | 9 | 6 (헛도는 케이스, [ARCHITECTURE.md](ARCHITECTURE.md) 참고) |

T4가 9 사이클까지 간 이유와 모델의 자기 교정 과정에 대한 분석은
[ARCHITECTURE.md](ARCHITECTURE.md)의 "결과 분석" 섹션에 정리되어 있다.

## 약점 (다음 단계로 가는 동기)

- LLM이 출력 형식 어기면 정규식 파싱 실패
- Stop sequence가 완벽하지 않음 (한 응답에 여러 Action 가능)
- 단일 문자열 인자만 지원 (복합 인자 어색)
- 시스템 프롬프트가 길어짐 (~2200자)
- 양자화 모델의 미세한 출력 흔들림에 취약

이 약점들이 2단계(Function calling)에서 구조적으로 해결된다.
