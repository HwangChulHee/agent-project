#!/bin/bash
# ==============================================================================
# vLLM 학습 환경 셋업 + 자동 실행 스크립트
# ------------------------------------------------------------------------------
# 사용법:
#   bash setup-vllm.sh                          # 인터랙티브
#   bash setup-vllm.sh --auto                   # 자동 진행 (기존 환경 보존)
#   bash setup-vllm.sh --auto --reinstall-venv  # 자동 + vllm-env 강제 재설치
# ==============================================================================

set -e

AUTO_MODE=false
REINSTALL_VENV=false
for arg in "$@"; do
    case "$arg" in
        --auto|-y) AUTO_MODE=true ;;
        --reinstall-venv) REINSTALL_VENV=true ;;
    esac
done

# ── 헬퍼 ─────────────────────────────────────────────────────────
section() {
    echo ""
    echo "=============================================================="
    echo "$1"
    echo "=============================================================="
}

confirm() {
    [ "$AUTO_MODE" = true ] && return 0
    read -p "$1 [Y/n] " r
    case "$r" in [nN]*) return 1 ;; *) return 0 ;; esac
}

confirm_destructive() {
    [ "$AUTO_MODE" = true ] && return 1
    read -p "$1 [y/N] " r
    case "$r" in [yY]*) return 0 ;; *) return 1 ;; esac
}

# ── 0단계: 사전 확인 ────────────────────────────────────────────
section "사전 환경 확인"

[ ! -d "/workspace" ] && { echo "ERROR: /workspace 없음"; exit 1; }
command -v nvidia-smi >/dev/null || { echo "ERROR: GPU 인스턴스 아님"; exit 1; }

echo "✓ /workspace 존재"
df -h /workspace | tail -1
echo ""
echo "GPU:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

confirm "환경 확인 OK. 계속 진행할까요?" || exit 0

# ── 1단계: HuggingFace 토큰 입력 ────────────────────────────────
section "1단계: HuggingFace 토큰"

TOKEN_FILE="/workspace/.hf-token"

if [ -f "$TOKEN_FILE" ]; then
    HF_TOKEN=$(cat "$TOKEN_FILE")
    echo "✓ 저장된 토큰 사용 ($TOKEN_FILE)"
elif [ -f "/workspace/hf-cache/token" ]; then
    HF_TOKEN=$(cat "/workspace/hf-cache/token")
    cp "/workspace/hf-cache/token" "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    echo "✓ HF 캐시 토큰 발견 → $TOKEN_FILE 백업"
elif [ -f "$HOME/.cache/huggingface/token" ]; then
    HF_TOKEN=$(cat "$HOME/.cache/huggingface/token")
    cp "$HOME/.cache/huggingface/token" "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    echo "✓ ~/.cache 토큰 발견 → $TOKEN_FILE 백업"
else
    echo "HuggingFace 토큰이 필요합니다 (Read 권한)."
    echo "  발급: https://huggingface.co/settings/tokens"
    echo "  Gemma 라이선스: https://huggingface.co/google/gemma-4-26B-A4B-it"
    echo ""
    read -s -p "토큰 붙여넣기 (입력 중 표시 안 됨): " HF_TOKEN
    echo ""
    [ -z "$HF_TOKEN" ] && { echo "ERROR: 토큰이 비어있음"; exit 1; }

    echo "$HF_TOKEN" > "$TOKEN_FILE"
    chmod 600 "$TOKEN_FILE"
    echo "✓ 토큰 저장됨 ($TOKEN_FILE)"
fi
export HF_TOKEN

# ── 2단계: uv 설치 ──────────────────────────────────────────────
section "2단계: uv 설치 및 볼륨 영구화"

if [ -f "/workspace/.local/bin/uv" ]; then
    echo "✓ uv 이미 설치됨"
    /workspace/.local/bin/uv --version
else
    confirm "uv 설치?" || exit 0
    curl -LsSf https://astral.sh/uv/install.sh | sh
    mkdir -p /workspace/.local/bin
    cp $HOME/.local/bin/uv /workspace/.local/bin/
    cp $HOME/.local/bin/uvx /workspace/.local/bin/
    echo "✓ uv 설치 완료"
fi
export PATH="/workspace/.local/bin:$PATH"

# ── 3단계: .bashrc 환경변수 ─────────────────────────────────────
section "3단계: .bashrc 환경변수 영구 등록"

if grep -q "vLLM 학습 환경" ~/.bashrc 2>/dev/null; then
    echo "✓ 환경변수 이미 등록됨"
else
    confirm ".bashrc에 환경변수 추가?" || exit 0
    cat >> ~/.bashrc << 'BASHRC_EOF'

# === vLLM 학습 환경 (workspace 영구화) ===
export PATH="/workspace/.local/bin:$PATH"
export UV_PYTHON_INSTALL_DIR=/workspace/.python
export UV_CACHE_DIR=/workspace/.uv-cache
export HF_HOME=/workspace/hf-cache
export HF_HUB_CACHE=/workspace/hf-cache/hub
BASHRC_EOF
    cp ~/.bashrc /workspace/.bashrc.backup
    echo "✓ .bashrc 업데이트"
fi

export UV_PYTHON_INSTALL_DIR=/workspace/.python
export UV_CACHE_DIR=/workspace/.uv-cache
export HF_HOME=/workspace/hf-cache
export HF_HUB_CACHE=/workspace/hf-cache/hub

# ── 4단계: Python 3.12 ──────────────────────────────────────────
section "4단계: Python 3.12 설치"

if uv python list --only-installed 2>/dev/null | grep -q "/workspace/.python/cpython-3.12"; then
    echo "✓ Python 3.12 이미 설치됨"
else
    confirm "Python 3.12 설치?" || exit 0
    uv python install 3.12
fi

# ── 5단계: vllm-env + vLLM ──────────────────────────────────────
section "5단계: vllm-env 가상환경 + vLLM nightly"

if [ -d "/workspace/vllm-env" ]; then
    echo "✓ vllm-env 이미 존재"
    if [ "$REINSTALL_VENV" = true ]; then
        echo "  --reinstall-venv 플래그 감지 → 기존 환경 제거 후 재설치"
        rm -rf /workspace/vllm-env
    elif [ "$AUTO_MODE" = false ]; then
        if confirm_destructive "지우고 재설치? (기본값 N, y만 재설치)"; then
            rm -rf /workspace/vllm-env
        else
            echo "  유지함"
        fi
    else
        echo "  유지함 (재설치하려면 --reinstall-venv 플래그 추가)"
    fi
fi

if [ ! -d "/workspace/vllm-env" ]; then
    confirm "vllm-env + vLLM nightly 설치 (5~15분)?" || exit 0
    uv venv --python 3.12 /workspace/vllm-env
    source /workspace/vllm-env/bin/activate

    uv pip install -U vllm --pre \
        --extra-index-url https://wheels.vllm.ai/nightly/cu129 \
        --extra-index-url https://download.pytorch.org/whl/cu129 \
        --index-strategy unsafe-best-match
    uv pip install -U "huggingface_hub[cli]" || uv pip install -U huggingface_hub
    echo "✓ vLLM 설치 완료"
fi

source /workspace/vllm-env/bin/activate

# ── 6단계: 설치 검증 ────────────────────────────────────────────
section "6단계: 설치 검증"

python << 'PYEOF'
import torch, vllm, transformers
print(f"PyTorch:        {torch.__version__}")
print(f"vLLM:           {vllm.__version__}")
print(f"Transformers:   {transformers.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU:            {torch.cuda.get_device_name(0)}")
    print(f"VRAM:           {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
PYEOF

# ── 7단계: HF 자동 로그인 ───────────────────────────────────────
section "7단계: HuggingFace 자동 로그인"

if hf auth whoami 2>/dev/null || huggingface-cli whoami 2>/dev/null; then
    echo "✓ 이미 로그인됨"
else
    if command -v hf >/dev/null 2>&1; then
        hf auth login --token "$HF_TOKEN" --add-to-git-credential 2>/dev/null || \
            huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential
    else
        huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential
    fi
    echo "✓ 로그인 완료"
fi

# ── 8단계: 모델 다운로드 ────────────────────────────────────────
section "8단계: 모델 다운로드"

MODEL_26B="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
MODEL_E2B="google/gemma-4-E2B-it"
EMBED_MODEL="BAAI/bge-m3"
CACHE_DIR="${HF_HUB_CACHE:-/workspace/hf-cache/hub}"

check_model() {
    local repo="$1"
    local repo_path="${repo//\//--}"
    [ -d "$CACHE_DIR/models--$repo_path" ]
}

# LLM 26B
if check_model "$MODEL_26B"; then
    echo "✓ $MODEL_26B 이미 다운로드됨"
else
    if confirm "$MODEL_26B 다운로드 (~17GB)?"; then
        hf download "$MODEL_26B" 2>/dev/null || huggingface-cli download "$MODEL_26B"
    fi
fi

# LLM E2B (BF16, Google 공식)
if check_model "$MODEL_E2B"; then
    echo "✓ $MODEL_E2B 이미 다운로드됨"
else
    if confirm "$MODEL_E2B 다운로드 (~10GB)?"; then
        hf download "$MODEL_E2B" 2>/dev/null || huggingface-cli download "$MODEL_E2B"
    fi
fi

# 임베딩
if check_model "$EMBED_MODEL"; then
    echo "✓ $EMBED_MODEL 이미 다운로드됨"
else
    if confirm "$EMBED_MODEL 다운로드 (~2.3GB)?"; then
        hf download "$EMBED_MODEL" 2>/dev/null || huggingface-cli download "$EMBED_MODEL"
    fi
fi

# ── 9단계: vLLM 26B LLM 서버 백그라운드 실행 ───────────────────
section "9단계: vLLM 26B 서버 백그라운드 실행 (포트 8000)"

VLLM_LOG=/workspace/vllm.log
VLLM_PID_FILE=/workspace/vllm.pid

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ vLLM 26B 서버가 이미 실행 중입니다"
    [ -f "$VLLM_PID_FILE" ] && echo "  PID: $(cat $VLLM_PID_FILE)"
else
    if [ -f "$VLLM_PID_FILE" ]; then
        OLD_PID=$(cat "$VLLM_PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            echo "기존 프로세스 ($OLD_PID) 종료..."
            kill "$OLD_PID" || true
            sleep 3
        fi
        rm -f "$VLLM_PID_FILE"
    fi

    confirm "vLLM 26B 서버를 백그라운드로 띄울까요?" || exit 0

    echo "vLLM 26B 서버 시작 (로그: $VLLM_LOG)..."
    echo "  GPU 메모리 점유: 0.55 (E2B + 임베딩 자리 확보)"

    nohup vllm serve "$MODEL_26B" \
        --max-model-len 16384 \
        --max-num-batched-tokens 8192 \
        --gpu-memory-utilization 0.55 \
        --safetensors-load-strategy=eager \
        --enable-auto-tool-choice \
        --reasoning-parser gemma4 \
        --tool-call-parser gemma4 \
        --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
        --host 0.0.0.0 --port 8000 \
        > "$VLLM_LOG" 2>&1 &

    VLLM_PID=$!
    echo $VLLM_PID > "$VLLM_PID_FILE"
    disown $VLLM_PID

    echo "✓ 서버 시작됨 (PID: $VLLM_PID)"
    echo ""
    echo "헬스체크 대기 (FUSE 볼륨이라 weight 로딩 느림: 10~15분 예상, 최대 20분 타임아웃)..."
    echo ""

    SUCCESS=false
    for i in $(seq 1 240); do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            ELAPSED=$((i * 5))
            echo "✓ vLLM 26B 준비 완료 (${ELAPSED}초 소요)"
            SUCCESS=true
            break
        fi

        if ! kill -0 "$VLLM_PID" 2>/dev/null; then
            echo "ERROR: vLLM 26B 프로세스가 종료됨"
            echo "----- 로그 마지막 50줄 -----"
            tail -50 "$VLLM_LOG"
            exit 1
        fi

        if [ $((i % 6)) -eq 0 ]; then
            ELAPSED=$((i * 5))
            echo "  ... 대기 중 (${ELAPSED}초 경과)"
        fi

        sleep 5
    done

    if [ "$SUCCESS" = false ]; then
        echo ""
        echo "ERROR: 20분 타임아웃. 로그 확인:"
        echo "  tail -100 $VLLM_LOG"
        exit 1
    fi
fi

# ── 9.5단계: 임베딩 서버 (bge-m3) 백그라운드 실행 ──────────────
section "9.5단계: 임베딩 서버 백그라운드 실행 (포트 8003)"

EMBED_LOG=/workspace/embed.log
EMBED_PID_FILE=/workspace/embed.pid
EMBED_PORT=8003

# 진짜 정상 상태인지 strict 검증:
#   PID 파일 살아있음 + /health 통과 + 실제 임베딩 호출 통과
verify_embed_server() {
    [ ! -s "$EMBED_PID_FILE" ] && return 1
    local pid
    pid=$(cat "$EMBED_PID_FILE")
    kill -0 "$pid" 2>/dev/null || return 1
    curl -s http://localhost:$EMBED_PORT/health > /dev/null 2>&1 || return 1
    local resp
    resp=$(curl -s -X POST http://localhost:$EMBED_PORT/v1/embeddings \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"$EMBED_MODEL\", \"input\": [\"healthcheck\"]}" \
        --max-time 10 2>/dev/null)
    echo "$resp" | grep -q '"embedding"'
}

if verify_embed_server; then
    echo "✓ 임베딩 서버가 이미 정상 동작 중"
    echo "  PID: $(cat $EMBED_PID_FILE)"
else
    echo "임베딩 서버 미실행 또는 비정상 상태. 잔여 프로세스 정리 후 재시작..."

    if [ -f "$EMBED_PID_FILE" ]; then
        OLD_PID=$(cat "$EMBED_PID_FILE" 2>/dev/null)
        if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
            echo "  기존 PID ($OLD_PID) 종료..."
            kill "$OLD_PID" || true
            sleep 3
        fi
        rm -f "$EMBED_PID_FILE"
    fi

    ZOMBIE_PIDS=$(ps aux | grep "vllm serve $EMBED_MODEL" | grep -v grep | awk '{print $2}')
    if [ -n "$ZOMBIE_PIDS" ]; then
        echo "  PID 파일 없는 잔여 프로세스 정리: $ZOMBIE_PIDS"
        echo "$ZOMBIE_PIDS" | xargs -r kill 2>/dev/null || true
        sleep 3
    fi

    # 포트 점유 프로세스 강제 해제 (모델 이름 grep으로 못 잡는 좀비 대비)
    if ss -tln 2>/dev/null | grep -q ":$EMBED_PORT "; then
        echo "  포트 $EMBED_PORT 점유 프로세스 강제 해제..."
        fuser -k $EMBED_PORT/tcp 2>/dev/null || true
        sleep 3
    fi

    confirm "임베딩 서버를 백그라운드로 띄울까요?" || exit 0

    echo "임베딩 서버 시작 (로그: $EMBED_LOG)..."
    echo "  모델: $EMBED_MODEL"
    echo "  GPU 메모리 점유: 0.07"
    echo "  포트: $EMBED_PORT"

    nohup vllm serve "$EMBED_MODEL" \
        --runner pooling \
        --gpu-memory-utilization 0.07 \
        --safetensors-load-strategy=eager \
        --host 0.0.0.0 --port $EMBED_PORT \
        > "$EMBED_LOG" 2>&1 &

    EMBED_PID=$!
    echo $EMBED_PID > "$EMBED_PID_FILE"
    disown $EMBED_PID

    echo "✓ 서버 시작됨 (PID: $EMBED_PID)"
    echo ""
    echo "헬스체크 + 실제 임베딩 호출 검증 (3~7분 예상, 최대 10분 타임아웃)..."
    echo ""

    SUCCESS=false
    HEALTH_PASSED=false
    for i in $(seq 1 120); do
        if ! kill -0 "$EMBED_PID" 2>/dev/null; then
            echo ""
            echo "ERROR: 임베딩 프로세스가 종료됨"
            echo "----- 로그 마지막 80줄 -----"
            tail -80 "$EMBED_LOG"
            rm -f "$EMBED_PID_FILE"
            exit 1
        fi

        if [ "$HEALTH_PASSED" = false ]; then
            if curl -s http://localhost:$EMBED_PORT/health > /dev/null 2>&1; then
                HEALTH_PASSED=true
                ELAPSED=$((i * 5))
                echo "  /health 통과 (${ELAPSED}초). 실제 임베딩 호출 검증 중..."
            fi
        else
            if curl -s -X POST http://localhost:$EMBED_PORT/v1/embeddings \
                -H "Content-Type: application/json" \
                -d "{\"model\": \"$EMBED_MODEL\", \"input\": [\"test\"]}" \
                --max-time 10 2>/dev/null | grep -q '"embedding"'; then
                ELAPSED=$((i * 5))
                echo "✓ 임베딩 서버 준비 완료 (${ELAPSED}초, 실제 호출 검증 통과)"
                SUCCESS=true
                break
            fi
        fi

        if [ $((i % 6)) -eq 0 ]; then
            ELAPSED=$((i * 5))
            echo "  ... 대기 중 (${ELAPSED}초 경과)"
        fi

        sleep 5
    done

    if [ "$SUCCESS" = false ]; then
        echo ""
        echo "ERROR: 10분 타임아웃."
        echo "----- 로그 마지막 80줄 -----"
        tail -80 "$EMBED_LOG"
        echo ""
        echo "전체 로그: tail -200 $EMBED_LOG"
        exit 1
    fi
fi

# ── 9.7단계: Gemma 4 E2B 서버 백그라운드 실행 ──────────────────
section "9.7단계: Gemma 4 E2B 서버 백그라운드 실행 (포트 8004)"

E2B_LOG=/workspace/e2b.log
E2B_PID_FILE=/workspace/e2b.pid
E2B_PORT=8004

# 정상 동작 검증: PID 살아있음 + /health + 모델 목록 응답
verify_e2b_server() {
    [ ! -s "$E2B_PID_FILE" ] && return 1
    local pid
    pid=$(cat "$E2B_PID_FILE")
    kill -0 "$pid" 2>/dev/null || return 1
    curl -s http://localhost:$E2B_PORT/health > /dev/null 2>&1 || return 1
    curl -s http://localhost:$E2B_PORT/v1/models 2>/dev/null | grep -q "gemma-4-E2B"
}

if verify_e2b_server; then
    echo "✓ E2B 서버가 이미 정상 동작 중"
    echo "  PID: $(cat $E2B_PID_FILE)"
else
    echo "E2B 서버 미실행 또는 비정상 상태. 잔여 프로세스 정리 후 재시작..."

    if [ -f "$E2B_PID_FILE" ]; then
        OLD_PID=$(cat "$E2B_PID_FILE" 2>/dev/null)
        if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
            echo "  기존 PID ($OLD_PID) 종료..."
            kill "$OLD_PID" || true
            sleep 3
        fi
        rm -f "$E2B_PID_FILE"
    fi

    ZOMBIE_PIDS=$(ps aux | grep "vllm serve $MODEL_E2B" | grep -v grep | awk '{print $2}')
    if [ -n "$ZOMBIE_PIDS" ]; then
        echo "  PID 파일 없는 잔여 프로세스 정리: $ZOMBIE_PIDS"
        echo "$ZOMBIE_PIDS" | xargs -r kill 2>/dev/null || true
        sleep 3
    fi

    # 포트 점유 프로세스 강제 해제
    if ss -tln 2>/dev/null | grep -q ":$E2B_PORT "; then
        echo "  포트 $E2B_PORT 점유 프로세스 강제 해제..."
        fuser -k $E2B_PORT/tcp 2>/dev/null || true
        sleep 3
    fi

    confirm "E2B 서버를 백그라운드로 띄울까요?" || exit 0

    echo "E2B 서버 시작 (로그: $E2B_LOG)..."
    echo "  모델: $MODEL_E2B"
    echo "  GPU 메모리 점유: 0.30 (CUDA graph profiling 보정)"
    echo "  max-model-len: 4096"
    echo "  포트: $E2B_PORT"

    nohup vllm serve "$MODEL_E2B" \
        --max-model-len 4096 \
        --gpu-memory-utilization 0.30 \
        --safetensors-load-strategy=eager \
        --enable-auto-tool-choice \
        --reasoning-parser gemma4 \
        --tool-call-parser gemma4 \
        --limit-mm-per-prompt '{"image": 0, "audio": 0}' \
        --host 0.0.0.0 --port $E2B_PORT \
        > "$E2B_LOG" 2>&1 &

    E2B_PID=$!
    echo $E2B_PID > "$E2B_PID_FILE"
    disown $E2B_PID

    echo "✓ 서버 시작됨 (PID: $E2B_PID)"
    echo ""
    echo "헬스체크 대기 (3~7분 예상, 최대 10분 타임아웃)..."
    echo ""

    SUCCESS=false
    for i in $(seq 1 120); do
        if ! kill -0 "$E2B_PID" 2>/dev/null; then
            echo ""
            echo "ERROR: E2B 프로세스가 종료됨"
            echo "----- 로그 마지막 80줄 -----"
            tail -80 "$E2B_LOG"
            rm -f "$E2B_PID_FILE"
            exit 1
        fi

        if curl -s http://localhost:$E2B_PORT/health > /dev/null 2>&1; then
            # /health 통과 후 모델 목록까지 확인 (실제 로드 완료)
            if curl -s http://localhost:$E2B_PORT/v1/models 2>/dev/null | grep -q "gemma-4-E2B"; then
                ELAPSED=$((i * 5))
                echo "✓ E2B 서버 준비 완료 (${ELAPSED}초)"
                SUCCESS=true
                break
            fi
        fi

        if [ $((i % 6)) -eq 0 ]; then
            ELAPSED=$((i * 5))
            echo "  ... 대기 중 (${ELAPSED}초 경과)"
        fi

        sleep 5
    done

    if [ "$SUCCESS" = false ]; then
        echo ""
        echo "ERROR: 10분 타임아웃."
        echo "----- 로그 마지막 80줄 -----"
        tail -80 "$E2B_LOG"
        echo ""
        echo "전체 로그: tail -200 $E2B_LOG"
        exit 1
    fi
fi

# ── 완료 ────────────────────────────────────────────────────────
section "✅ 셋업 완료!"

VLLM_PID_DISPLAY=$(cat "$VLLM_PID_FILE" 2>/dev/null || echo "N/A")
EMBED_PID_DISPLAY=$(cat "$EMBED_PID_FILE" 2>/dev/null || echo "N/A")
E2B_PID_DISPLAY=$(cat "$E2B_PID_FILE" 2>/dev/null || echo "N/A")

cat << INFO_EOF

━━━ vLLM 26B 서버 ━━━
  URL:       http://localhost:8000
  PID:       $VLLM_PID_DISPLAY
  로그 파일: $VLLM_LOG
  모델:      $MODEL_26B
  GPU util:  0.55

━━━ 임베딩 서버 ━━━
  URL:       http://localhost:8003
  PID:       $EMBED_PID_DISPLAY
  로그 파일: $EMBED_LOG
  모델:      $EMBED_MODEL
  GPU util:  0.07

━━━ Gemma 4 E2B 서버 ━━━
  URL:       http://localhost:8004
  PID:       $E2B_PID_DISPLAY
  로그 파일: $E2B_LOG
  모델:      $MODEL_E2B
  GPU util:  0.30

━━━ 유용한 명령어 ━━━
  26B 로그:        tail -f $VLLM_LOG
  Embed 로그:      tail -f $EMBED_LOG
  E2B 로그:        tail -f $E2B_LOG
  26B 헬스체크:    curl http://localhost:8000/health
  Embed 헬스체크:  curl http://localhost:8003/health
  E2B 헬스체크:    curl http://localhost:8004/health
  모델 목록 (26B): curl http://localhost:8000/v1/models
  모델 목록 (E2B): curl http://localhost:8004/v1/models
  GPU 점유 확인:   nvidia-smi

━━━ 서버 종료 ━━━
  26B 종료:    kill \$(cat $VLLM_PID_FILE)
  Embed 종료:  kill \$(cat $EMBED_PID_FILE)
  E2B 종료:    kill \$(cat $E2B_PID_FILE)
  전부 종료:   kill \$(cat $VLLM_PID_FILE) \$(cat $EMBED_PID_FILE) \$(cat $E2B_PID_FILE)

━━━ 재시작 ━━━
  bash $0 --auto                       # 기존 환경 보존
  bash $0 --auto --reinstall-venv      # vllm-env 강제 재설치

━━━ 호출 예시 ━━━
  # 임베딩
  curl -s http://localhost:8003/v1/embeddings \\
    -H "Content-Type: application/json" \\
    -d '{"model": "$EMBED_MODEL", "input": ["테스트"]}'

  # E2B chat completion
  curl -s http://localhost:8004/v1/chat/completions \\
    -H "Content-Type: application/json" \\
    -d '{"model": "$MODEL_E2B", "messages": [{"role": "user", "content": "안녕"}]}'

INFO_EOF