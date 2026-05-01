#!/data/data/com.termux/files/usr/bin/sh
# ──────────────────────────────────────────────────────────────────────
# Whim Dash — S7865 Head Unit Setup
#
# Run this in Termux on the 13.6" Android 14 dash unit.
# Prerequisites: Termux + Termux:Boot installed from F-Droid
# ──────────────────────────────────────────────────────────────────────
set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[+]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*"; }

echo "================================="
echo "  Whim Dash — S7865 Installer"
echo "================================="
echo ""

# 1. Update Termux packages
info "Updating Termux..."
pkg update -y && pkg upgrade -y

# 2. Install dependencies
info "Installing packages..."
pkg install -y python curl git termux-api

# 3. Install Ollama (ARM64)
if [ ! -f "$HOME/ollama" ]; then
    info "Downloading Ollama for ARM64..."
    curl -L https://ollama.com/download/ollama-linux-arm64 -o $HOME/ollama
    chmod +x $HOME/ollama
else
    info "Ollama already installed."
fi

# 4. Copy the 0411 model file
info "Installing 0411 model definition..."
cp "$(dirname "$0")/0411.modelfile" $HOME/0411.modelfile

# 5. Set up Termux:Boot
info "Configuring boot script..."
mkdir -p $HOME/.termux/boot
cp "$(dirname "$0")/termux_boot.sh" $HOME/.termux/boot/start-whim-dash.sh
chmod +x $HOME/.termux/boot/start-whim-dash.sh

# 6. Start Ollama and pull the base model
info "Starting Ollama for first-time model pull..."
$HOME/ollama serve > $HOME/ollama.log 2>&1 &
sleep 8

info "Pulling phi3 model (~2.2 GB)..."
$HOME/ollama pull phi3

info "Creating 0411-droid model..."
$HOME/ollama create 0411-droid -f $HOME/0411.modelfile

# 7. Disable battery optimization reminder
echo ""
info "INSTALL COMPLETE."
echo ""
echo "Manual steps remaining:"
echo "  1. Install Tailscale from Play Store or F-Droid"
echo "  2. Log into your Tailscale network"
echo "  3. Android Settings > Apps > Termux > Battery > Unrestricted"
echo "  4. Open browser to YOUR_TAILSCALE_PC_IP:8089 for Whim.m"
echo "  5. Reboot the head unit to test auto-start"
echo ""
echo "Local AI:  http://localhost:11434 (Ollama)"
echo "0411 Droid: ollama run 0411-droid"
echo ""
