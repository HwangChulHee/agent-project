#!/bin/bash
# ==============================================================================
# vLLM 학습 환경 셋업 스크립트
# ------------------------------------------------------------------------------
# 이 스크립트는 런팟 인스턴스에서 처음부터 vLLM + Gemma 4 환경을 재구축합니다.
#
# 사전 조건 (README 참고):
#   1. 런팟 PyTorch 2.x 템플릿 + GPU (RTX 6000 Ada 48GB 추천)
#   2. Network Volume 200GB+ /workspace에 마운트
#   3. HuggingFace 계정 + 토큰 + Gemma 4 라이선스 동의
#
# 사용법:
#   bash setup-vllm.sh           # 인터랙티브 (각 단계 확인)
#   bash setup-vllm.sh --auto    # 자동 실행 (확인 없이 전부)
# ==============================================================================

set -e  # 에러 발생 시 즉시 종료

AUTO_MODE=false
if [[ "$1" == "--auto" || "$1" == "-y" ]]; then
    AUTO_MODE=true
fi

# ------------------------------------------------------------------------------
# 헬퍼 함수
# ------------------------------------------------------------------------------
print_section() {
    echo ""
    echo "=============================================================="
    echo "$1"
    echo "=============================================================="
}

confirm() {
    if [ "$AUTO_MODE" = true ]; then
        return 0
    fi
    read -p "$1 [Y/n] " response
    case "$response" in
        [nN][oO]|[nN])
            return 1
            ;;
        *)
            return 0
            ;;
    esac
}

# ------------------------------------------------------------------------------
# 사전 확인
# ------------------------------------------------------------------------------
print_section "사전 환경 확인"

if [ ! -d "/workspace" ]; then
    echo "ERROR: /workspace가 존재하지 않습니다. 런팟 볼륨이 마운트됐는지 확인하세요."
    exit 1
fi

echo "✓ /workspace 존재"
df -h /workspace | tail -1

if ! command -v nvidia-smi &> /dev/null; then
    echo "ERROR: nvidia-smi 명령을 찾을 수 없습니다. GPU 인스턴스인지 확인하세요."
    exit 1
fi

echo ""
echo "GPU 정보:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

confirm "환경 확인 OK. 계속 진행할까요?" || exit 0

# ------------------------------------------------------------------------------
# 1. uv 설치 (볼륨에 영구화)
# ------------------------------------------------------------------------------
print_section "1단계: uv 설치 및 볼륨 영구화"

if [ -f "/workspace/.local/bin/uv" ]; then
    echo "✓ uv가 이미 /workspace/.local/bin/uv에 있습니다."
    /workspace/.local/bin/uv --version
else
    confirm "uv를 설치하고 /workspace에 영구화합니다. 진행할까요?" || exit 0
    
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    mkdir -p /workspace/.local/bin
    cp $HOME/.local/bin/uv /workspace/.local/bin/
    cp $HOME/.local/bin/uvx /workspace/.local/bin/
    
    echo "✓ uv 설치 완료: $(/workspace/.local/bin/uv --version)"
fi

export PATH="/workspace/.local/bin:$PATH"

# ------------------------------------------------------------------------------
# 2. .bashrc 환경변수 영구 등록
# ------------------------------------------------------------------------------
print_section "2단계: 환경변수 영구 등록"

if grep -q "vLLM 학습 환경" ~/.bashrc 2>/dev/null; then
    echo "✓ 환경변수가 이미 .bashrc에 등록돼 있습니다."
else
    confirm ".bashrc에 환경변수 블록을 추가합니다. 진행할까요?" || exit 0
    
    cat >> ~/.bashrc << 'BASHRC_EOF'

# === vLLM 학습 환경 (workspace 영구화) ===
export PATH="/workspace/.local/bin:$PATH"
export UV_PYTHON_INSTALL_DIR=/workspace/.python
export UV_CACHE_DIR=/workspace/.uv-cache
export HF_HOME=/workspace/hf-cache
export HF_HUB_CACHE=/workspace/hf-cache/hub
BASHRC_EOF
    
    cp ~/.bashrc /workspace/.bashrc.backup
    echo "✓ .bashrc 업데이트 + /workspace/.bashrc.backup 저장"
fi

# 현재 셸에 환경변수 적용
export UV_PYTHON_INSTALL_DIR=/workspace/.python
export UV_CACHE_DIR=/workspace/.uv-cache
export HF_HOME=/workspace/hf-cache
export HF_HUB_CACHE=/workspace/hf-cache/hub

# ------------------------------------------------------------------------------
# 3. Python 3.12 설치 (볼륨)
# ------------------------------------------------------------------------------
print_section "3단계: Python 3.12 설치 (볼륨에)"

if uv python list --only-installed 2>/dev/null | grep -q "/workspace/.python/cpython-3.12"; then
    echo "✓ Python 3.12가 이미 /workspace/.python에 설치돼 있습니다."
else
    confirm "Python 3.12를 /workspace/.python에 설치합니다. 진행할까요?" || exit 0
    
    uv python install 3.12
    echo "✓ Python 3.12 설치 완료"
fi

# ------------------------------------------------------------------------------
# 4. vllm-env 가상환경 + vLLM 설치
# ------------------------------------------------------------------------------
print_section "4단계: vllm-env 가상환경 + vLLM nightly 설치"

if [ -d "/workspace/vllm-env" ]; then
    echo "/workspace/vllm-env가 이미 존재합니다."
    if confirm "기존 환경을 지우고 다시 설치할까요? (no면 그대로 둠)"; then
        rm -rf /workspace/vllm-env
    else
        echo "→ 기존 환경 유지, 4단계 건너뜀"
    fi
fi

if [ ! -d "/workspace/vllm-env" ]; then
    confirm "vllm-env를 만들고 vLLM nightly + transformers를 설치합니다. (5~15분 소요) 진행할까요?" || exit 0
    
    uv venv --python 3.12 /workspace/vllm-env
    source /workspace/vllm-env/bin/activate
    
    echo ""
    echo "→ vLLM nightly + PyTorch cu129 설치 중... (시간 걸림)"
    uv pip install -U vllm --pre \
        --extra-index-url https://wheels.vllm.ai/nightly/cu129 \
        --extra-index-url https://download.pytorch.org/whl/cu129 \
        --index-strategy unsafe-best-match
    
    echo "→ HuggingFace CLI 설치 중..."
    uv pip install -U "huggingface_hub[cli]" || uv pip install -U huggingface_hub
    
    echo "✓ vLLM 설치 완료"
fi

source /workspace/vllm-env/bin/activate

# ------------------------------------------------------------------------------
# 5. 설치 검증
# ------------------------------------------------------------------------------
print_section "5단계: 설치 검증"

python << 'PYEOF'
import torch
import vllm
import transformers

print(f"PyTorch:        {torch.__version__}")
print(f"vLLM:           {vllm.__version__}")
print(f"Transformers:   {transformers.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU:            {torch.cuda.get_device_name(0)}")
    print(f"VRAM:           {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
PYEOF

# ------------------------------------------------------------------------------
# 6. HuggingFace 로그인 안내
# ------------------------------------------------------------------------------
print_section "6단계: HuggingFace 로그인"

if [ -f "/workspace/hf-cache/token" ]; then
    echo "✓ HF 토큰이 /workspace/hf-cache/token에 이미 저장돼 있습니다."
    hf auth whoami 2>/dev/null || huggingface-cli whoami 2>/dev/null || echo "(인증 정보 확인 실패)"
else
    echo "HuggingFace 토큰이 필요합니다."
    echo "사전 조건:"
    echo "  1) https://huggingface.co/settings/tokens 에서 Read 토큰 발급"
    echo "  2) https://huggingface.co/google/gemma-4-26B-A4B-it 라이선스 동의"
    echo "  3) 사용할 양자화 모델 페이지도 라이선스 확인"
    echo ""
    if confirm "지금 hf auth login을 실행할까요?"; then
        hf auth login || huggingface-cli login
    else
        echo "→ 나중에 수동으로 'hf auth login' 실행하세요."
    fi
fi

# ------------------------------------------------------------------------------
# 7. 모델 다운로드 (옵션)
# ------------------------------------------------------------------------------
print_section "7단계: 모델 다운로드 (옵션)"

MODEL_26B="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
MODEL_31B="QuantTrio/gemma-4-31B-it-AWQ"

CACHE_DIR="${HF_HUB_CACHE:-/workspace/hf-cache/hub}"

check_model() {
    local repo="$1"
    local repo_path="${repo//\//--}"
    if [ -d "$CACHE_DIR/models--$repo_path" ]; then
        return 0
    else
        return 1
    fi
}

echo "다운로드 가능한 모델:"
echo "  - $MODEL_26B (~17GB, 추천)"
echo "  - $MODEL_31B (~18GB, 옵션)"
echo ""

if check_model "$MODEL_26B"; then
    echo "✓ $MODEL_26B 이미 다운로드됨"
else
    if confirm "26B AWQ 모델을 다운로드할까요? (~17GB, 1~5분)"; then
        hf download "$MODEL_26B" || huggingface-cli download "$MODEL_26B"
    fi
fi

if check_model "$MODEL_31B"; then
    echo "✓ $MODEL_31B 이미 다운로드됨"
else
    if confirm "31B AWQ 모델도 다운로드할까요? (~18GB, 옵션)"; then
        hf download "$MODEL_31B" || huggingface-cli download "$MODEL_31B"
    fi
fi

# ------------------------------------------------------------------------------
# 8. vLLM 서버 실행 명령어 안내
# ------------------------------------------------------------------------------
print_section "셋업 완료!"

cat << 'INFO_EOF'

다음 단계:

1) vLLM 서버 띄우기 (별도 터미널 권장):

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
   
   첫 로딩에 5~10분, "Application startup complete" 뜨면 준비 완료.

2) 동작 확인 (또 다른 터미널):

   curl http://localhost:8000/health
   # → 200

3) 에이전트 코드 실행:

   cd /workspace/agent-project/step1-react
   source .venv/bin/activate  # 첫 실행이면 uv sync 먼저
   python run.py

INFO_EOF
