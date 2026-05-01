#!/data/data/com.termux/files/usr/bin/sh
# ──────────────────────────────────────────────────────────────────────
# Whim Dash — Termux Boot Script
# Copy to ~/.termux/boot/start-whim-dash.sh on the S7865 head unit
#
# Requires: Termux, Termux:Boot (from F-Droid), Ollama, Tailscale
# ──────────────────────────────────────────────────────────────────────

# Keep the CPU alive while services run
termux-wake-lock

echo "[$(date '+%H:%M:%S')] Starting Whim Dash..."

# Start Ollama in the background
if [ -f "$HOME/ollama" ]; then
    echo "[$(date '+%H:%M:%S')] Starting Ollama..."
    $HOME/ollama serve > $HOME/ollama.log 2>&1 &
    sleep 8

    # Create the 0411 model if it doesn't exist
    if ! $HOME/ollama list 2>/dev/null | grep -q "0411-droid"; then
        echo "[$(date '+%H:%M:%S')] Creating 0411-droid model..."
        $HOME/ollama create 0411-droid -f $HOME/0411.modelfile
    fi

    # Pre-warm the model into RAM
    echo "[$(date '+%H:%M:%S')] Pre-warming 0411-droid..."
    echo "/bye" | $HOME/ollama run 0411-droid 2>/dev/null
fi

echo "[$(date '+%H:%M:%S')] Whim Dash ready."
echo "[$(date '+%H:%M:%S')] Tailscale: $(tailscale ip -4 2>/dev/null || echo 'not running')"
echo "[$(date '+%H:%M:%S')] Ollama: http://localhost:11434"
echo "[$(date '+%H:%M:%S')] Whim.m: open browser to YOUR_TAILSCALE_PC_IP:8089"
