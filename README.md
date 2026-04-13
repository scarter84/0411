# Whim

**Local-first desktop + mobile ecosystem for voice, AI, connectivity, and automation.**

Whim is a Python desktop terminal and Android mobile companion that runs entirely on your own hardware. No cloud APIs required. No telemetry. ~2 MB of code.

[Full Manual with Screenshots](https://scarter84.github.io/0411/)

---

## What's in it

| Component | Description |
|-----------|-------------|
| **Whim Terminal** | Tkinter desktop app with 18 tabs: AI chat, voice cloning, wake word, SmartThings IoT, Signal/Discord, screen share, Doppler weather radar, APRS/HAM monitor, geofence tracker, archive editor, audio capture, and more |
| **CURSOR tab** | Built-in code editor with file browser, syntax highlighting, and AI assist. Pick any local Ollama model from a dropdown, hit Explain/Fix/Refactor/Complete/Tests, stream the response, apply diffs |
| **Whim.AI** | Streaming Ollama chat with presets, observability (tokens/s, VRAM, context meter), tool trace, export |
| **AVR Lab** | XTTS v2 voice cloning with speaker references and spectrogram visualization |
| **Voice Engine** | Wake word ("Hey Whim") with live spectrogram, HPF/AGC/parametric EQ, VAD, confidence ghost bar |
| **Persona** | Coined response playlists per voice clone — pre-rendered WAV for <100ms playback |
| **Whim.m** | Android mobile app: voice recorder, file library, device chat, AI chat via Ollama proxy |
| **Networking** | Reverse SSH tunnel to VPS (primary) + Tailscale mesh VPN (fallback) |

## Stack

- Python 3.12 + Tkinter (desktop)
- Ollama (local LLM inference)
- Coqui XTTS v2 (voice cloning, conda env)
- FFmpeg (audio processing)
- autossh + systemd (tunnel)
- ADB (Android device management)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/scarter84/0411.git
cd 0411

# 2. Install AI models (optional — app works without them)
bash scripts/setup_models.sh --status   # check what you have
bash scripts/setup_models.sh --ollama   # install Ollama + pull llama3.1:8b-16k (~5 GB)
bash scripts/setup_models.sh --xtts     # install XTTS v2 voice synthesis (~10 GB)

# 3. Copy config templates
cp config/openclaw.example.json ~/.openclaw/openclaw.json
cp config/device_locations.example.json config/device_locations.json

# 4. Run the desktop terminal
python3 app/openclaw_tkui.py

# 5. Run the mobile server (optional)
python3 whim_m_v2.1.py --port 8089
```

## Code vs. Weights

The repo is **~2 MB of code**. All AI models install separately:

| Component | Size | Install |
|-----------|------|---------|
| Whim code | ~2 MB | `git clone` |
| llama3.1:8b-16k | 4.9 GB | `ollama pull llama3.1:8b-16k` |
| deepseek-r1:32b | 19 GB | `ollama pull deepseek-r1:32b` |
| XTTS v2 | ~10 GB | `bash scripts/setup_models.sh --xtts` |

The app works without any models — AI tabs show connection errors but everything else functions normally.

## It's not perfect

This is a one-person project built for daily use. There are rough edges. But the codebase is small enough that you can point Cursor, Factory droids, Aider, or any AI coding tool at it and they can reason about the whole thing.

Fork it. Assign a droid to it. Steal the parts you like.

## License

MIT
