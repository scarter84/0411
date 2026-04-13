# Whim

**Local-first desktop, mobile & vehicle ecosystem for AI, geofencing, weather radar, HAM radio, voice, and automation.**

Whim is a three-tier Python ecosystem — desktop terminal, mobile companion, and vehicle dashboard — that runs entirely on your own hardware. No cloud APIs required. No telemetry. ~2 MB of code.

[Full Manual with Screenshots](https://scarter84.github.io/0411/)

---

## The Ecosystem

| Platform | App | Description |
|----------|-----|-------------|
| **Desktop** | **Whim Terminal v3.4** | Tkinter app with 18 tabs: AI chat, voice cloning (XTTS v2), wake word engine, GeoF geofence tracker with LoRa collar integration, Doppler weather radar with NWS NEXRAD, HAM/APRS monitor with Direwolf, SmartThings IoT, Signal/Discord, NodeFlow visual editor, screen share, archive editor, and more |
| **Mobile** | **Whim.m v3.4** | Android companion (APK + PWA) with five tabs: REC, LIBRARY, CHAT, WAKE, DEVICES. Voice recording, AI chat via Ollama proxy, wake word commands, cross-device file sharing. Runs on Galaxy S22, S9, Lenovo tablet |
| **Vehicle** | **Whim.V v1.0** | Touch-optimized dashboard for 13.6" Tesla-style displays (Ubuntu) or Android tablets. GeoF map, Doppler radar, LibreOffice document viewer, AI chat, system logs. Flask server + WebView APK |

## Key Features

| Component | Description |
|-----------|-------------|
| **GeoF** | Geofence tracker with canvas map, LoRa collar bridge (ESP32 gateway), 20-minute heartbeat, in/out detection, battery tracking — built for livestock and pet tracking across Ozark terrain |
| **Doppler** | NWS NEXRAD base reflectivity on OSM tiles, Open-Meteo 7-day forecast, anemometer, NWR audio (web stream + RTL-SDR), severe weather alerts pushed to mobile |
| **HAM/APRS** | APRS station monitor with embedded tile map, Direwolf integration (KISS/AGWPE/simulate), distance-filtered station list, raw packet log |
| **Whim.AI** | Streaming Ollama chat with presets, observability (tokens/s, VRAM, context meter), tool trace, export |
| **AVR Lab** | XTTS v2 voice cloning with speaker references and spectrogram visualization |
| **Voice Engine** | Wake word ("Hey Whim") with live spectrogram, HPF/AGC/parametric EQ, VAD, confidence ghost bar |
| **Persona** | Coined response playlists per voice clone — pre-rendered WAV for <100ms playback |
| **Networking** | Reverse SSH tunnel to VPS (primary) + Tailscale mesh VPN (fallback) + LAN/ADB. Desktop :18789, Mobile :8089, Vehicle :8099 |

## Stack

- Python 3.12 + Tkinter (desktop) + Flask (vehicle)
- Ollama (local LLM inference — DeepSeek R1:32B, Llama 3.1:8B-16K, Qwen3-Coder:32B)
- Coqui XTTS v2 (voice cloning, conda env)
- LibreOffice headless (document/spreadsheet rendering for Whim.V)
- FFmpeg (audio processing)
- autossh + systemd (tunnel) + Tailscale (mesh VPN)
- ADB (Android device management)
- ESP32 + LoRa (GeoF collar gateway)
- Direwolf + RTL-SDR (HAM/APRS decode)

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

# 6. Run the vehicle dashboard (optional)
python3 vehicle/whim_v.py --port 8099
# Then open http://<your-ip>:8099 on a tablet or vehicle display
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

## Downloads

Pre-built zip packages for quick setup:

| Package | Platform |
|---------|----------|
| [Whim-Terminal-Linux.zip](releases/Whim-Terminal-Linux.zip) | Linux (Python 3.10+ / Tkinter) |
| [Whim-Terminal-Windows.zip](releases/Whim-Terminal-Windows.zip) | Windows 11 (includes setup scripts) |
| [Whim-Terminal-macOS.zip](releases/Whim-Terminal-macOS.zip) | macOS (Homebrew Python) |
| [Whim-Mobile.zip](releases/Whim-Mobile.zip) | Whim.m mobile companion + Android source |
| [Whim-Vehicle.zip](releases/Whim-Vehicle.zip) | Whim.V vehicle dashboard + APK |

## It's not perfect

This is a one-person project built for daily use. There are rough edges. But the codebase is small enough that you can point Cursor, Factory droids, Aider, or any AI coding tool at it and they can reason about the whole thing.

Fork it. Assign a droid to it. Steal the parts you like.

## License

MIT
