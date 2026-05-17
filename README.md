# AI 에이전트 학습 프로젝트

LLM 기반 AI 에이전트의 핵심 패턴들을 단계적으로 직접 구현하며 학습하는 프로젝트.
프레임워크를 쓰지 않고 순수 Python + OpenAI 호환 API로 본질부터 만든다.

## 학습 목표

- 에이전트 동작 원리를 코드 수준에서 이해
- 텍스트 파싱 ReAct부터 Function calling, MCP까지 현대 표준의 진화 경험
- 로컬 LLM (vLLM + Gemma 4)으로 비용 부담 없이 실험

## 학습 진행 현황

| 단계 | 주제 | 상태 |
|---|---|---|
| 1 | 텍스트 파싱 ReAct 에이전트 | ✅ 완료 |
| 2 | Function calling ReAct 에이전트 | ✅ 완료 |
| 3 | 메모리 + RAG | ⬜ 예정 |
| 4 | LangGraph 도입 | ⬜ 예정 |
| 5 | MCP (Model Context Protocol) | ⬜ 예정 |
| 6 | 멀티 에이전트 / 자율 실행 | ⬜ 예정 |

이후 단계 구성은 학습 진행에 따라 조정될 수 있다.

## 환경 사양

| 항목 | 내용 |
|---|---|
| 인프라 | RunPod RTX 6000 Ada 48GB (또는 동등 GPU) |
| OS | Ubuntu 22.04 (런팟 PyTorch 템플릿) |
| Python | 3.12 (uv가 관리) |
| LLM 서버 | vLLM nightly (CUDA 12.9 빌드) |
| 모델 | `cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit` (~17GB) |
| 패키지 관리 | uv |
| 볼륨 | 200GB Network Volume (`/workspace`) |

핵심 라이브러리는 각 단계의 `pyproject.toml` 참고.

## 처음부터 재구축하기

이 프로젝트는 모든 환경이 `/workspace` 볼륨에 자급자족되도록 설계됐다.
런팟 인스턴스를 새로 만들어도 빠르게 복원 가능.

### 1. RunPod 인스턴스 생성

- 템플릿: **RunPod PyTorch 2.x** (CUDA 12.4 이상 포함된 것)
- GPU: **RTX 6000 Ada 48GB** 추천 (A6000 48GB, A100 80GB도 가능)
- 디스크: **Network Volume 200GB+** 를 `/workspace`에 마운트
- 노출 포트: HTTP Service **Port 8000** 추가 (vLLM API용)

### 2. SSH 접속 후 사전 확인

```bash
nvidia-smi              # GPU 인식, CUDA 12.4+ 확인
df -h /workspace        # 볼륨 마운트 확인
python3 --version       # 3.10 이상
```

### 3. HuggingFace 사전 준비 (브라우저에서)

1. https://huggingface.co/settings/tokens 에서 Read 권한 토큰 발급
2. 사용할 모델 페이지에서 라이선스 동의:
   - https://huggingface.co/google/gemma-4-26B-A4B-it (원본, 권장)
   - https://huggingface.co/cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit (양자화)

### 4. 리포 클론 + setup 스크립트 실행

```bash
cd /workspace
git clone https://github.com/HwangChulHee/agent-project.git
cd agent-project

# 인터랙티브 모드 (각 단계 확인)
bash setup-vllm.sh

# 또는 자동 모드 (한 번에 끝까지)
bash setup-vllm.sh --auto
```

스크립트가 처리하는 것:
- uv 설치 + 볼륨 영구화
- `.bashrc` 환경변수 등록
- Python 3.12 설치 (볼륨)
- `vllm-env` 가상환경 + vLLM nightly 설치
- 설치 검증
- HuggingFace 로그인
- 모델 다운로드 (옵션)

### 5. vLLM 서버 실행

별도 터미널에서:

```bash
source /workspace/vllm-env/bin/activate

vllm serve cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit \
  --max-model-len 32768 \
  --max-num-batched-tokens 8192 \
  --gpu-memory-utilization 0.90 \
  --enable-auto-tool-choice \
  --reasoning-parser gemma4 \
  --tool-call-parser gemma4 \
  --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
  --host 0.0.0.0 --port 8000
```

첫 로딩에 5~10분. `Application startup complete` 메시지가 나오면 준비 완료.

동작 확인:

```bash
curl http://localhost:8000/health   # → 200
```

### 6. 에이전트 코드 실행

```bash
cd /workspace/agent-project/step2-function-calling
uv sync                              # 의존성 복원 (.venv 생성)
source .venv/bin/activate
python run.py                        # 전체 테스트 케이스 실행
```

## 디렉토리 구조

```
agent-project/
├── README.md                    # 이 문서
├── setup-vllm.sh                # 환경 재구축 스크립트
├── .gitignore
├── docs/
│   ├── overview.md              # 단계 간 비교, 전체 흐름
│   └── reflections.md           # 학습 회고
├── step1-react/                 # 1단계: 텍스트 파싱 ReAct
│   ├── README.md                # 실행법
│   ├── ARCHITECTURE.md          # 패턴/구현 상세
│   ├── agent.py                 # 메인 루프
│   ├── tools.py                 # 도구 정의 (calculator, wikipedia)
│   ├── prompts.py               # 시스템 프롬프트
│   ├── run.py                   # 테스트 케이스
│   ├── smoke_test.py            # 연결 확인용
│   ├── pyproject.toml
│   └── uv.lock
└── step2-function-calling/      # 2단계: Function calling ReAct
    ├── README.md
    ├── ARCHITECTURE.md
    ├── agent.py
    ├── tools.py
    ├── run.py
    ├── pyproject.toml
    └── uv.lock
```

## 각 단계 자세히

- **1단계 텍스트 파싱 ReAct**: [README](step1-react/README.md) | [ARCHITECTURE](step1-react/ARCHITECTURE.md)
- **2단계 Function calling**: [README](step2-function-calling/README.md) | [ARCHITECTURE](step2-function-calling/ARCHITECTURE.md)
- **전체 흐름**: [overview](docs/overview.md)
- **학습 회고**: [reflections](docs/reflections.md)

## 참고 자료

- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — ReAct 패턴 원논문
- [vLLM Documentation](https://docs.vllm.ai/)
- [Gemma 4 Model Card](https://huggingface.co/google/gemma-4-26B-A4B-it)

## 라이선스

MIT