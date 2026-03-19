#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# Whim — Model Setup (separate from core app)
#
# The Whim app itself is lightweight (~2 MB of Python).
# This script installs the optional AI model backends:
#
#   1. Ollama      — local LLM inference    (~5-20 GB per model)
#   2. XTTS v2     — voice cloning / TTS    (~1.8 GB model + conda env)
#
# Both are accessed by Whim over HTTP / subprocess — no models are
# bundled inside the app code.
#
# Usage:
#   bash scripts/setup_models.sh              # install everything
#   bash scripts/setup_models.sh --ollama     # Ollama only
#   bash scripts/setup_models.sh --xtts       # XTTS only
#   bash scripts/setup_models.sh --status     # check what's installed
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[x]${NC} $*"; }
dim()   { echo -e "${DIM}    $*${NC}"; }

# ── Status check ─────────────────────────────────────────────────────

status_check() {
    echo ""
    echo "=============================="
    echo "  Whim — Model Status"
    echo "=============================="
    echo ""

    # Ollama
    if command -v ollama &>/dev/null; then
        info "Ollama binary: $(which ollama)"
        if systemctl is-active --quiet ollama 2>/dev/null || pgrep -x ollama &>/dev/null; then
            info "Ollama service: running"
            echo ""
            dim "Installed models:"
            ollama list 2>/dev/null | while IFS= read -r line; do dim "  $line"; done
            OLLAMA_SIZE=$(du -sh /usr/share/ollama 2>/dev/null | cut -f1 || echo "?")
            dim "Total disk: ${OLLAMA_SIZE}"
        else
            warn "Ollama installed but not running"
            dim "Start with: sudo systemctl start ollama"
        fi
    else
        err "Ollama: not installed"
        dim "Install: curl -fsSL https://ollama.com/install.sh | sh"
    fi

    echo ""

    # XTTS conda env
    XTTS_PY="${HOME}/miniconda3/envs/xtts/bin/python"
    if [ -f "$XTTS_PY" ]; then
        info "XTTS conda env: found"
        XTTS_SIZE=$(du -sh "${HOME}/miniconda3/envs/xtts" 2>/dev/null | cut -f1 || echo "?")
        dim "Env size: ${XTTS_SIZE}"
        # Check for cached model weights
        TTS_CACHE="${HOME}/.local/share/tts"
        if [ -d "$TTS_CACHE" ]; then
            MODEL_SIZE=$(du -sh "$TTS_CACHE" 2>/dev/null | cut -f1 || echo "?")
            info "XTTS model cache: ${MODEL_SIZE}"
            dim "Path: ${TTS_CACHE}"
        else
            warn "XTTS model not yet downloaded (will auto-download on first use)"
        fi
    else
        err "XTTS conda env: not found"
        dim "Expected at: ${XTTS_PY}"
    fi

    echo ""

    # Voices directory
    VOICES_DIR="${HOME}/voices"
    if [ -d "$VOICES_DIR" ]; then
        VOICE_COUNT=$(find "$VOICES_DIR" -maxdepth 1 -name "*.wav" 2>/dev/null | wc -l)
        info "Voice references: ${VOICE_COUNT} WAV file(s) in ~/voices"
    else
        warn "No ~/voices directory (XTTS voice cloning won't work without reference audio)"
    fi

    echo ""
    echo "=============================="
    echo ""

    # Summary
    echo "Whim core app:  ~2 MB  (always included)"
    echo "Ollama models:  5-25 GB per model (optional, runs as service)"
    echo "XTTS v2:        ~10 GB total (optional conda env + model)"
    echo ""
    echo "The core app works without any models — AI tabs will show"
    echo "connection errors but everything else functions normally."
    echo ""
}

# ── Ollama setup ─────────────────────────────────────────────────────

setup_ollama() {
    echo ""
    info "Setting up Ollama..."
    echo ""

    if command -v ollama &>/dev/null; then
        info "Ollama already installed: $(ollama --version 2>&1 | head -1)"
    else
        info "Installing Ollama..."
        curl -fsSL https://ollama.com/install.sh | sh
    fi

    # Ensure service is running
    if ! systemctl is-active --quiet ollama 2>/dev/null; then
        info "Starting Ollama service..."
        sudo systemctl enable ollama 2>/dev/null || true
        sudo systemctl start ollama 2>/dev/null || true
        sleep 2
    fi

    # Pull the default model (smallest first)
    info "Pulling default model: llama3.1:8b-16k (~4.9 GB)..."
    dim "This is the default for Whim.AI chat. Skip with Ctrl+C if you already have it."
    ollama pull llama3.1:8b-16k || warn "Failed to pull model (maybe already present)"

    echo ""
    info "Ollama setup complete."
    dim "Optional larger model: ollama pull deepseek-r1:32b  (~19 GB)"
    echo ""
}

# ── XTTS setup ───────────────────────────────────────────────────────

setup_xtts() {
    echo ""
    info "Setting up XTTS v2 (Coqui TTS) voice synthesis..."
    echo ""

    CONDA_BASE="${HOME}/miniconda3"
    XTTS_ENV="${CONDA_BASE}/envs/xtts"
    XTTS_PY="${XTTS_ENV}/bin/python"

    # Check for conda/miniconda
    if [ ! -d "$CONDA_BASE" ]; then
        warn "Miniconda not found at ${CONDA_BASE}"
        info "Installing Miniconda..."
        INSTALLER="/tmp/miniconda_installer.sh"
        curl -fsSL "https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh" -o "$INSTALLER"
        bash "$INSTALLER" -b -p "$CONDA_BASE"
        rm -f "$INSTALLER"
        info "Miniconda installed to ${CONDA_BASE}"
    fi

    # Source conda
    eval "$("${CONDA_BASE}/bin/conda" shell.bash hook)"

    # Create env if missing
    if [ ! -d "$XTTS_ENV" ]; then
        info "Creating conda env 'xtts' with Python 3.10..."
        conda create -y -n xtts python=3.10
    else
        info "Conda env 'xtts' already exists"
    fi

    # Install TTS + PyTorch with CUDA
    info "Installing TTS and PyTorch (this may take a while)..."
    conda run -n xtts pip install --upgrade \
        TTS \
        torch torchaudio torchvision \
        --extra-index-url https://download.pytorch.org/whl/cu126 \
        2>&1 | tail -5

    # Pre-download the XTTS v2 model weights
    info "Pre-downloading XTTS v2 model weights (~1.8 GB)..."
    conda run -n xtts python -c "
from TTS.api import TTS
tts = TTS('tts_models/multilingual/multi-dataset/xtts_v2', gpu=False)
print('Model downloaded successfully')
" 2>&1 | tail -3

    echo ""
    info "XTTS setup complete."
    dim "Model weights cached at: ~/.local/share/tts/"
    dim "Voice references go in: ~/voices/"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────

DO_OLLAMA=false
DO_XTTS=false
DO_STATUS=false

if [ $# -eq 0 ]; then
    DO_OLLAMA=true
    DO_XTTS=true
fi

for arg in "$@"; do
    case "$arg" in
        --ollama)  DO_OLLAMA=true ;;
        --xtts)    DO_XTTS=true ;;
        --status)  DO_STATUS=true ;;
        --help|-h)
            echo "Usage: $0 [--ollama] [--xtts] [--status]"
            echo ""
            echo "  --ollama   Install/update Ollama + pull default LLM"
            echo "  --xtts     Install/update XTTS v2 conda env + model"
            echo "  --status   Show what's currently installed"
            echo "  (no args)  Install everything"
            exit 0
            ;;
        *)
            err "Unknown option: $arg"
            exit 1
            ;;
    esac
done

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  Whim — AI Model Setup                  ║"
echo "║  (separate from the ~2 MB core app)     ║"
echo "╚══════════════════════════════════════════╝"

if $DO_STATUS; then
    status_check
    exit 0
fi

if $DO_OLLAMA; then setup_ollama; fi
if $DO_XTTS;   then setup_xtts; fi

echo ""
info "Done. Run '$0 --status' to verify."
echo ""
