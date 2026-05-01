# Whim Dash — S7865 Head Unit Integration

Setup files for running Whim + local AI on the 13.6" Android 14 (S7865) head unit.

## What This Does

- Installs Ollama on the dash via Termux (uses the 12GB RAM for local inference)
- Creates a `0411-droid` model with PCM pinout knowledge baked in
- Auto-starts Ollama on ignition via Termux:Boot
- Connects to Whim.m on your PC over Tailscale

## Install

```bash
# On the S7865 head unit, in Termux:
git clone https://github.com/scarter84/0411.git ~/0411
bash ~/0411/dash/install_dash.sh
```

## Files

| File | Purpose |
|------|---------|
| `install_dash.sh` | One-shot installer for Termux on the S7865 |
| `termux_boot.sh` | Auto-start script (copies to ~/.termux/boot/) |
| `0411.modelfile` | Ollama model definition with PCM knowledge |

## Architecture

```
S7865 Head Unit (12GB/256GB)
├── Termux
│   ├── Ollama (phi3 / 0411-droid)  ← local fallback AI
│   └── Boot script (auto-start)
├── Tailscale                        ← mesh VPN to home PC
└── Browser → YOUR_TAILSCALE_PC_IP:8089  ← Whim.m (full UI)
```

When Tailscale is reachable, the dash uses the PC's Ollama (deepseek-r1:32b, llama3.1:8b-16k).
When offline, it falls back to the local phi3 model on the dash itself.
