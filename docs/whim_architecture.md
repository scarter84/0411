# Whim — System Architecture & Network Topology (Hybrid)

```
 OPERATOR (Tommy)
     |
     v
+====================================================================+
|  PC: carraramint  (YOUR_LAN_PC_IP / TS: YOUR_TAILSCALE_PC_IP)              |
|                                                                    |
|  +---------------------------+   +-----------------------------+   |
|  | Whim Terminal (Tkinter)   |   | OpenClaw AI Gateway         |   |
|  |  openclaw_tkui.py         |-->|  WS :18789 (JSON-RPC)       |   |
|  |  +- 18 Tabs (2 rows)     |   |  Ollama :11434              |   |
|  |  +- LLM Model Dropdown   |   |   deepseek-r1:32b           |   |
|  |  +- Settings Tab (API    |   |   llama3.1:8b-16k           |   |
|  |     keys, models, prefs) |   |   llama3.1:8b               |   |
|  |  +- Voice Engine Tab     |   +-----------------------------+   |
|  |  +- Tray Icon (pystray)  |                                     |
|  |  +- Control Panel (Whim  |                                     |
|  |     tab: TS/Tunnel ctrl) |                                     |
|  +---------------------------+                                     |
|       |           |           |                                    |
|       v           v           v                                    |
|  +-----------+ +----------+ +----------+ +-------------------+     |
|  | Whim.m    | | Journal  | | Screen-  | | XTTS v2 (Coqui)  |     |
|  | Server    | | Ingest   | | shot Srv | | TTS via conda env |     |
|  | HTTP:8089 | | Flask    | | :8091    | +-------------------+     |
|  | (5-Tab    | | :8088    | +----------+                           |
|  |  Web App) | +----+-----+            +-------------------+       |
|  | Hybrid:   |      |                  | Messaging         |       |
|  |  VPS tun  |      v                  |  Signal Desktop   |       |
|  |  Tailscale|~/Journal/               |  Discord Bot      |       |
|  |  Auto-det |~/ARCHIVE/               +-------------------+       |
|  +-----+-----+~/TableReads/                                       |
|        |                                                           |
|  +-----+---------+   +-------------------------------+             |
|  | ADB Portal    |   | SSH Tunnel Service            |             |
|  | (whim_adb_    |   | autossh (whim-tunnel.service) |             |
|  |  portal.py)   |   | ssh -R 8089:localhost:8089    |             |
|  +---------------+   +---------------+---------------+             |
|                       | Tailscale (always-on daemon)  |             |
|                       | YOUR_TAILSCALE_PC_IP:8089             |             |
|                       +-------------------------------+             |
+====================================================================+
              |                                     |
    outbound SSH tunnel                     Tailscale mesh VPN
              |                              (WireGuard, direct)
              v                                     v
+===============================+     +=============================+
|  VPS: YOUR_VPS_IP         |     | Tailscale Network           |
|  Reverse SSH Tunnel Relay     |     | PC:     YOUR_TAILSCALE_PC_IP        |
|  Port 8089 forwarded          |     | S9:     YOUR_TAILSCALE_PHONE1_IP         |
|  SSH key auth only            |     | S22:    YOUR_TAILSCALE_PHONE2_IP         |
+===============================+     | Tablet: YOUR_TAILSCALE_TABLET_IP      |
           |            |            | +=============================+
  HTTP :8089|            |            |           |
           v            v            v           v
     +----------+  +-----------+  +-------------+
     | Samsung  |  | Samsung   |  | Lenovo      |
     | Galaxy   |  | Galaxy    |  | TB311FU     |
     | S9       |  | S22       |  | (Tablet)    |
     | LAN: .198|  | TS:       |  | LAN: .112   |
     | TS: .x.x|  | YOUR_TS.   |  | TS: .x.x|
     +----------+  |  59.2     |  +-------------+
                   +-----------+
         |              |               |
         v              v               v
     +==========================================+
     |  Whim.m v3.2 APK (WebView)              |
     |  Connection mode: VPS / Tailscale / Auto |
     |  Default: VPS (YOUR_VPS_IP:8089)     |
     |  Fallback: Tailscale (YOUR_TAILSCALE_PC_IP:8089) |
     |  5 tabs: REC, LIBRARY, CHAT, WAKE, DEV  |
     |  Health: tunnel/server/mic/ollama/TS     |
     |  Auto-reconnect w/ exponential backoff   |
     +==========================================+
```

## Component Summary

| Component | Location | Port | Role |
|---|---|---|---|
| **openclaw_tkui.py** | PC | — | Main desktop UI (Tkinter), 18 tabs in 2 rows, LLM model dropdown, Persona, Settings |
| **OpenClaw Gateway** | PC | ws://127.0.0.1:18789 | AI agent gateway (JSON-RPC WebSocket) |
| **Ollama** | PC | http://127.0.0.1:11434 | LLM inference (deepseek-r1:32b, llama3.1:8b-16k, llama3.1:8b), switchable from header dropdown |
| **Whim.m v3.2** | PC | http://:8089 | Mobile app: recorder, library, AI chat (Whim.ai), wake word, device chat, TTS, hybrid connection |
| **Journal Ingest** | PC | http://:8088 | Flask service, saves uploads to ~/Journal |
| **Screenshot Server** | PC | :8091 | Screen capture service |
| **XTTS v2** | PC | — | Text-to-speech (Coqui, conda env) |
| **Voice Engine** | PC | — | Wake word tuning: live spectrogram (Whim-Scope), gain/HPF/AGC/parametric EQ, wake sensitivity, VAD, spectral subtraction |
| **Audio Capture** | PC | — | Floating tool: captures system audio (HDMI/speakers) via PipeWire monitor, outputs MP3/Opus/OGG/M4A/WAV to ~/Journal/audio_captures |
| **Persona** | PC | — | Voice personality manager: coined response playlists per voice clone, confidence-gated, context-aware, pre-rendered via XTTS |
| **Signal Desktop** | PC | — | Messaging channel for OpenClaw |
| **Discord Bot** | PC | — | Messaging channel for OpenClaw |
| **ADB Portal** | PC | — | APK install/emulator management GUI |
| **whim-tunnel.service** | PC | — | autossh reverse SSH tunnel to VPS |
| **Whim.m v3.2** | Android | — | Native APK (WebView), recorder + AI chat + library + wake word + device chat, hybrid VPS/Tailscale |
| **Control Panel** | PC | — | System settings hub with Whim tab for Tunnel/Tailscale controls and live status |

## Network Topology

| Device | LAN IP | Tailscale IP | Role | Connects via |
|---|---|---|---|---|
| PC (carraramint) | YOUR_LAN_PC_IP | YOUR_TAILSCALE_PC_IP | Server hub | localhost / LAN |
| Samsung Galaxy S9 | YOUR_LAN_PHONE1_IP | YOUR_TAILSCALE_PHONE1_IP | Recorder client | VPS tunnel (default) or Tailscale (fallback) |
| Samsung Galaxy S22 | — | YOUR_TAILSCALE_PHONE2_IP | Recorder client | VPS tunnel (default) or Tailscale (fallback) |
| Lenovo TB311FU | YOUR_LAN_TABLET_IP | YOUR_TAILSCALE_TABLET_IP | Recorder client (tablet) | VPS tunnel (default) or Tailscale (fallback) |

## Hybrid Connection Strategy

Whim uses a two-mode connection strategy: VPS tunnel as the always-on primary, with Tailscale as an opt-in fallback for rock-solid stability when needed.

### Connection Modes

| Mode | Default | How it works |
|---|---|---|
| **VPS Tunnel** | YES | Phone → VPS:8089 → SSH tunnel → PC:8089. Works everywhere, no client software needed. |
| **Tailscale** | NO (opt-in) | Phone → YOUR_TAILSCALE_PC_IP:8089 direct via WireGuard mesh. Handles WiFi↔cellular handoffs natively. |
| **Auto-detect** | NO (opt-in) | On startup, checks if Tailscale 100.x.x.x IP is reachable; uses it if available, otherwise falls back to VPS tunnel. |

### Switching Modes

- **Mobile app**: Connection mode dropdown (top-right of health bar) — VPS Tunnel / Tailscale / Auto-detect
- **Desktop Control Panel**: Whim tab → radio buttons push mode changes to running Whim.m server via `/connection_mode` API
- **Config persistence**: Mode saved to `config/connection_mode.json`

### Auto-Reconnect

When connection drops (any mode), the client retries with exponential backoff:
- Base delay: 3 seconds (+ 0-2s random jitter)
- Doubles each attempt: 3s → 6s → 12s → 24s → 30s (capped)
- Max delay: 30 seconds
- Visible "Connection lost — reconnecting..." banner in the mobile app
- All HTTP requests use `fetchWithRetry` wrapper (up to 3 attempts)

### VPS Tunnel Infrastructure

| Item | Value |
|---|---|
| VPS | YOUR_VPS_IP (Vultr) |
| Tunnel port | 8089 |
| Service | whim-tunnel.service (systemd) |
| Tool | autossh -M 0 -N -R 8089:localhost:8089 |
| Auth | SSH key (~/.ssh/id_ed25519), no passwords |
| Firewall | ufw: ports 22 + 8089 |
| sshd config | GatewayPorts yes |
| Keepalive | ServerAliveInterval 30, ServerAliveCountMax 3 |

### Tailscale Infrastructure

| Item | Value |
|---|---|
| PC IP | YOUR_TAILSCALE_PC_IP |
| Galaxy S9 | YOUR_TAILSCALE_PHONE1_IP |
| Galaxy S22 | YOUR_TAILSCALE_PHONE2_IP |
| Lenovo Tablet | YOUR_TAILSCALE_TABLET_IP |
| Daemon | Always running on PC (systemd) |
| Protocol | WireGuard (direct mesh, NAT traversal) |
| Port | 8089 (same as tunnel) |

Traffic flow (VPS): **Phone → VPS:8089 → SSH tunnel → PC:8089**
Traffic flow (Tailscale): **Phone → YOUR_TAILSCALE_PC_IP:8089 → PC:8089 (direct)**

## Data Flow

1. **Recording**: Android APK records audio/video locally
2. **Upload**: APK sends HTTP POST to http://YOUR_VPS_IP:8089/upload
3. **VPS relay**: VPS forwards the request through the reverse SSH tunnel to CARRAMint:8089
4. **Whim.m**: PC receives upload, saves to ~/Journal
5. **Processing**: Desktop UI can transcribe (Whisper), TTS (XTTS), archive
6. **AI**: OpenClaw gateway provides LLM interaction via Ollama
7. **Whim.ai Chat**: Mobile CHAT tab proxies to Ollama for AI conversations
8. **Device Chat**: Cross-device messaging via DEVICES tab

## Health Indicators

### Desktop (Whim Terminal)
- **Tunnel dot** (header bar): green if whim-tunnel.service is active AND VPS:8089 is reachable
- **Whim dot** (header bar): green if localhost:8089 (Whim.m server) is responding
- **Tray icon**: appears when tunnel is connected, shows combined status

### Desktop (Control Panel — Whim Tab)
- **VPS Tunnel dot**: green if VPS:8089 reachable, red if down
- **Tailscale dot**: green if Tailscale daemon is running, grey if off
- **Whim.m Server dot**: green if localhost:8089 responds, red if down
- **Ollama dot**: green if Ollama reachable, red if down
- **Connection mode radio buttons**: switch between VPS Tunnel / Tailscale / Auto-detect
- **Status line**: shows current mode, all service states, Tailscale IP
- Polls every 10 seconds in a background thread

### Mobile (Whim.m)
- **tunnel**: green if /health endpoint responds (proves end-to-end tunnel connectivity)
- **server**: green if /health returns HTTP 200
- **mic**: green if microphone permission is granted
- **ollama**: green if Ollama is reachable on the PC
- **TS**: green if Tailscale is running on the PC, grey if off
- **Connection mode dropdown**: top-right, switch between VPS Tunnel / Tailscale / Auto-detect
- **Reconnect banner**: pulsing red "Connection lost — reconnecting..." when disconnected

### API Endpoints (Hybrid)
- `GET /health` — returns `{tailscale: bool, connection_mode: str, tailscale_ip: str}`
- `GET /connection_mode` — returns current mode + Tailscale reachability status
- `POST /connection_mode` — set mode (`tunnel`, `tailscale`, `auto`), persists to config

## Voice Engine

The VOICE ENGINE tab in the Whim Terminal provides a full audio diagnostics and wake word tuning environment, designed for use in noisy environments (vehicles, outdoor).

### Whim-Scope (Live Spectrogram)
- Real-time frequency heatmap: 300 Hz – 8 kHz range
- 16 kHz mono, 16-bit PCM, 512-point Hanning FFT
- **Confidence Ghost Bar**: vertical bar on scope edge — grey (<50%), blue (50%+), green (90%+ trigger)
- **1–3 kHz intelligibility band highlight**: cyan tint + dashed boundary lines over the critical voice band
- Wake word detection overlay flashes when trigger fires

### Column A: Gain & Noise Floor
| Control | Description |
|---|---|
| Dynamic Gain | 0.1x – 5.0x input amplification before processing |
| Noise Floor Gate | -80 to 0 dB silence threshold; ignores sub-threshold audio |
| High-Pass Filter | Cuts below 150 Hz (engine/road rumble). Hotkey: H |
| Spectral Subtraction | Learns ambient noise profile and subtracts it from mic input |
| Automatic Gain Control | Auto-levels gain by ambient noise (louder env → less gain) |
| Parametric EQ (400 Hz) | Narrow notch dip (-24 to 0 dB) to cut cabin reverb "boxiness" |

### Column B: Wake Word Sensitivity
| Control | Description |
|---|---|
| Sensitivity Threshold | 0.0 – 1.0 (low = must shout, high = whispers trigger). Hotkey: S |
| Phonetic Trigger Delay | 200 – 1500 ms wait between "Hey" and "Whim" |
| Voice Activity Detection | Only runs AI inference on speech-like audio patterns |
| Wake Word Engine | Selector: placeholder / openWakeWord / Porcupine |
| Intelligibility Band | Toggle 1–3 kHz highlight on Whim-Scope |

### Column C: Optimization & Hardware
| Stat | Value |
|---|---|
| Sample Rate | 16,000 Hz (16 kHz) |
| Bit Depth | 16-bit PCM Mono |
| FFT Window | 512-point Hanning |
| Freq Range | 300 – 8,000 Hz |
| Buffer Size | Adjustable 256 – 4096 frames |

Live readouts: inference latency (ms), buffer frame count, CPU usage, audio device name.
Hotkeys: G (cycle gain), S (cycle sensitivity), H (toggle HPF).
Config persists to `~/.openclaw/voice_engine.json`.
