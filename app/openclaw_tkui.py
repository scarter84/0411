import asyncio
import json
import shutil
import subprocess
import threading
import queue
import uuid
import tkinter as tk
import tkinter.font as tkFont
from tkinter import ttk, filedialog, colorchooser, messagebox
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
import io
import socket
import qrcode
import os
import sys
import math
import re
import fnmatch
import pystray
import base64
import time
try:
    import pystay
except ImportError:
    pystay = None
from PIL import Image, ImageOps, ImageDraw, ImageTk
import numpy as np
import webbrowser
try:
    import sounddevice as sd
except ImportError:
    sd = None


# ------------------ CONFIG ------------------
DEFAULT_WS_URL = "ws://127.0.0.1:18789"
DEFAULT_TOKEN = ""
DEFAULT_INGEST_PORT = "8088"
DEFAULT_SS_PORT = 8091
XTTS_CONDA_PYTHON = os.path.expanduser("~/miniconda3/envs/xtts/bin/python")
XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_VOICES_DIR = os.path.expanduser("~/voices")
XTTS_DEFAULT_OUT = os.path.expanduser("~/xtts_out.wav")
TABLE_READS_DIR = os.path.expanduser("~/TableReads")
LOGO_PATH = os.path.expanduser("~/Incoming/fire.png")
SETTINGS_ICON_PATH = os.path.expanduser("~/settings.png")
JOURNAL_DIR = os.path.expanduser("~/Journal")
TRANSCRIPT_DIR = os.path.expanduser("~/TRANSCRIPT")
TRANSCRIBE_SCRIPT = os.path.expanduser("~/.openclaw/sandboxes/agent-main-XXXXXXXX/skills/openai-whisper-api/scripts/transcribe.sh")

OPENCLAW_CONFIG = os.path.expanduser("~/.openclaw/openclaw.json")
ARCHIVE_DIR = os.path.expanduser("~/ARCHIVE")
WHIM_FONTS_DIR = os.path.expanduser("~/.openclaw/WhimUI/fonts")
SESSIONS_STORE = os.path.expanduser("~/.openclaw/whim_sessions.json")
VOICE_ENGINE_CONFIG = os.path.expanduser("~/.openclaw/voice_engine.json")
WHIM_SETTINGS_FILE = os.path.expanduser("~/.openclaw/whim_settings.json")

DEFAULT_MODELS = [
    "llama3.1:8b-16k",
    "llama3.1:8b",
    "deepseek-r1:32b",
]
AUDIO_CAPTURE_DIR = os.path.expanduser("~/Journal/audio_captures")
PERSONA_DIR = os.path.expanduser("~/voices/personas")
PERSONA_CONFIG = os.path.expanduser("~/voices/personas/personas.json")

WHIM_TERMINAL_VERSION = "3.3.0"
WHIM_M_VERSION = "3.3.0"
WHIM_APK_DIR = os.path.expanduser("~/vaults/WHIM/mobile/whim_m")

WHIM_VERSION_HISTORY = [
    ("3.3.0", "2026-03-18", "Tailscale OTA updates via Library. GitHub Manual moved to Library tab. Native overlay removed."),
    ("3.2.0", "2026-03-18", "Version display on Terminal and mobile. Update Devices button. Updates tab."),
    ("3.1.0", "2026-03-18", "Keyboard-aware input rows — text box and send button stay visible when soft keyboard opens on all devices."),
    ("3.0.0", "2026-03-17", "Full tunnel migration. VPS reverse SSH tunnel replaces Tailscale for mobile connectivity. Health bar and connection toggle."),
]

_WHIM_ICON_B64 = ""
_whim_icon_path = os.path.expanduser("~/.openclaw/Whim.png")
if os.path.isfile(_whim_icon_path):
    with open(_whim_icon_path, "rb") as _f:
        _WHIM_ICON_B64 = base64.b64encode(_f.read()).decode()

def _make_whim_tray_icon():
    if os.path.isfile(_whim_icon_path):
        img = Image.open(_whim_icon_path).convert("RGBA").resize((64, 64))
        return img
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(30, 100, 220, 255))
    draw.text((22, 18), "W", fill=(255, 255, 255, 255))
    return img

VPS_HOST = "YOUR_VPS_IP"
VPS_TUNNEL_PORT = 8089

def _make_tunnel_icon(tunnel_up=False, whim_up=False):
    """Three states: grey=tunnel down, yellow=tunnel up but whim unreachable, bright green=both up."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if tunnel_up and whim_up:
        ring = (0, 255, 70, 255)
        disc = (0, 220, 60, 255)
        dot = (255, 255, 255, 255)
    elif tunnel_up:
        ring = (230, 180, 0, 255)
        disc = (200, 160, 0, 255)
        dot = (255, 255, 255, 255)
    else:
        ring = (80, 80, 80, 255)
        disc = (50, 50, 50, 255)
        dot = (100, 100, 100, 255)
    draw.ellipse([4, 4, 60, 60], fill=ring)
    draw.ellipse([10, 10, 54, 54], fill=disc)
    draw.ellipse([18, 18, 30, 30], fill=dot)
    draw.ellipse([34, 18, 46, 30], fill=dot)
    draw.ellipse([26, 34, 38, 46], fill=dot)
    return img

def _check_tunnel_and_whim():
    """Returns (tunnel_up: bool, whim_reachable: bool)."""
    tunnel_up = False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "whim-tunnel.service"],
            capture_output=True, text=True, timeout=5)
        if result.stdout.strip() == "active":
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((VPS_HOST, VPS_TUNNEL_PORT))
            s.close()
            tunnel_up = True
    except Exception:
        pass
    if not tunnel_up:
        return False, False
    whim_up = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", int(DEFAULT_INGEST_PORT)))
        s.close()
        whim_up = True
    except Exception:
        pass
    return tunnel_up, whim_up

def _tunnel_tray_label(tunnel_up, whim_up):
    if tunnel_up and whim_up:
        return "Tunnel: Connected | Whim: Online"
    elif tunnel_up:
        return "Tunnel: Connected | Whim: Offline"
    else:
        return "Tunnel: Down | Whim: Offline"

incoming = queue.Queue()
outgoing = queue.Queue()

# ==================== DARK THEME PALETTE ====================
TH = {
    "bg":          "#2b2b2b",
    "card":        "#333333",
    "input":       "#1e1e1e",
    "border":      "#3a3a3a",
    "border_hi":   "#444444",
    "btn":         "#14507a",
    "btn_hover":   "#0f3d5e",
    "btn_border":  "#3a3a3a",
    "fg":          "#dce4ee",
    "fg2":         "#888888",
    "fg_dim":      "#666666",
    "green":       "#2fa572",
    "red":         "#d94040",
    "yellow":      "#e0a030",
    "blue_text":   "#14507a",
    "select_bg":   "#264f78",
    "font":        ("Segoe UI", 10),
    "font_sm":     ("Segoe UI", 9),
    "font_xs":     ("Consolas", 8),
    "font_mono":   ("Consolas", 9),
    "font_title":  ("Segoe UI", 11, "bold"),
    "font_hero":   ("Segoe UI", 18, "bold"),
}


class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, text="", variable=None, width=50, height=24,
                 on_color=TH["green"], off_color="#555555", bg=None, font=TH["font_sm"], **kw):
        try:
            pbg = parent["bg"]
        except (tk.TclError, KeyError):
            pbg = TH["bg"]
        bg = bg or pbg
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0, **kw)
        self._sw = width
        self._sh = height
        self._on_color = on_color
        self._off_color = off_color
        self._var = variable or tk.BooleanVar(value=False)
        self._text = text
        self._font = font
        self._draw()
        self.bind("<Button-1>", self._toggle)
        self.config(cursor="hand2")

    def _draw(self):
        self.delete("all")
        on = self._var.get()
        r = self._sh // 2
        fill = self._on_color if on else self._off_color
        self.create_oval(0, 0, self._sh, self._sh, fill=fill, outline="")
        self.create_oval(self._sw - self._sh, 0, self._sw, self._sh, fill=fill, outline="")
        self.create_rectangle(r, 0, self._sw - r, self._sh, fill=fill, outline="")
        knob_x = self._sw - self._sh + 2 if on else 2
        self.create_oval(knob_x, 2, knob_x + self._sh - 4, self._sh - 2,
                         fill="#ffffff", outline="")

    def _toggle(self, event=None):
        self._var.set(not self._var.get())
        self._draw()

    def get(self):
        return self._var.get()


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text="", command=None, radius=6,
                 bg=TH["btn"], fg=TH["fg"], hover_bg=TH["btn_hover"],
                 border_color=TH["btn_border"], font=TH["font_sm"],
                 padx=14, pady=5, **kw):
        self._cmd = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._border = border_color
        self._radius = radius
        self._font = font

        tmp = tk.Label(parent, text=text, font=font)
        tw = tmp.winfo_reqwidth() + padx * 2
        th = tmp.winfo_reqheight() + pady * 2
        tmp.destroy()

        try:
            pbg = parent["bg"]
        except (tk.TclError, KeyError):
            pbg = TH["bg"]
        super().__init__(parent, width=tw, height=th, bg=pbg,
                         highlightthickness=0, bd=0, **kw)
        self._w_val = tw
        self._h_val = th
        self._text = text
        self._draw(bg)
        self.bind("<Enter>", lambda e: self._draw(hover_bg))
        self.bind("<Leave>", lambda e: self._draw(bg))
        self.bind("<ButtonRelease-1>", lambda e: self._cmd() if self._cmd else None)
        self.config(cursor="hand2")

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        points = [
            x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y1+r,
            x2, y2-r, x2, y2-r, x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r, x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kw)

    def _draw(self, fill):
        self.delete("all")
        self._round_rect(1, 1, self._w_val-1, self._h_val-1, self._radius,
                          fill=fill, outline=self._border, width=1)
        self.create_text(self._w_val//2, self._h_val//2, text=self._text,
                         fill=self._fg, font=self._font)

    def config(self, **kw):
        if "state" in kw:
            st = kw.pop("state")
            if st == "disabled":
                self._draw(TH["border_hi"])
                self.unbind("<ButtonRelease-1>")
                self.config(cursor="")
            elif st == "normal":
                self._draw(self._bg)
                self.bind("<ButtonRelease-1>", lambda e: self._cmd() if self._cmd else None)
                self.config(cursor="hand2")
        super().config(**kw)

    configure = config


def jdump(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)

def new_id(prefix="req"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"

class GatewayClient:
    async def connect(self, ws_url, token, scopes):
        async with websockets.connect(ws_url) as ws:
            challenge = json.loads(await ws.recv())
            incoming.put(("event", challenge))
            nonce = challenge["payload"]["nonce"]
            ts = challenge["payload"]["ts"]
            connect_req = {
                "type": "req", "id": new_id("connect"), "method": "connect",
                "params": {
                    "minProtocol": 3, "maxProtocol": 3,
                    "client": {"id": "tkui", "version": "0.2.0", "platform": "linux", "mode": "operator"},
                    "role": "operator", "scopes": scopes,
                    "auth": {"token": token} if token else {},
                    "locale": "en-US",
                    "userAgent": "whim/0.2.0",
                    "device": {"id": "tkui-local", "publicKey": "", "signature": "", "signedAt": ts, "nonce": nonce},
                }
            }
            await ws.send(json.dumps(connect_req))
            while True:
                try:
                    while True:
                        msg = outgoing.get_nowait()
                        await ws.send(json.dumps(msg))
                except queue.Empty: pass
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    packet = json.loads(raw)
                    incoming.put(("ws", packet))
                except asyncio.TimeoutError: pass

def start_ws_thread(ws_url, token, scopes):
    threading.Thread(target=lambda: asyncio.run(GatewayClient().connect(ws_url, token, scopes)), daemon=True).start()


# ==================== LAN AUDIO UPLOAD SERVER ====================
UPLOAD_DIR = os.path.expanduser("~/Journal")

WHIM_M_MANIFEST = json.dumps({
    "name": "Whim.m",
    "short_name": "Whim.m",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#1e1e1e",
    "theme_color": "#1e1e1e",
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}]
})

WHIM_M_SW = """self.addEventListener('fetch',e=>e.respondWith(fetch(e.request).catch(()=>caches.match(e.request))));"""

MOBILE_UPLOAD_HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#1e1e1e">
<link rel="manifest" href="/manifest.json">
<title>Whim.m</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:#1e1e1e;color:#dce4ee;font-family:-apple-system,system-ui,'Segoe UI',sans-serif;
  height:100dvh;height:100vh;margin:0;padding:0;overflow:hidden;display:flex;flex-direction:column}
.health-bar{position:fixed;top:0;left:0;right:0;display:flex;justify-content:center;gap:12px;
  padding:6px 12px;background:#2b2b2b;border-bottom:1px solid #3a3a3a;font-size:10px;
  font-family:'Courier New',monospace;z-index:200}
.health-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px;vertical-align:middle}
.health-dot.ok{background:#2fa572}
.health-dot.warn{background:#e0a030}
.health-dot.fail{background:#d94040}
.ai-fab{position:fixed;top:8px;right:12px;z-index:300;width:38px;height:38px;border-radius:50%;
  background:#2b2b2b;border:1.5px solid #3a3a3a;cursor:pointer;display:flex;align-items:center;
  justify-content:center;transition:all .2s;box-shadow:0 2px 8px rgba(0,0,0,.4)}
.ai-fab:active{transform:scale(0.92)}
.ai-fab.active{border-color:#00ff00;background:#1a2a1a}
.ai-fab svg{width:18px;height:18px}
.ss-fab{position:fixed;top:8px;right:58px;z-index:300;width:38px;height:38px;border-radius:50%;
  background:#2b2b2b;border:1.5px solid #3a3a3a;cursor:pointer;display:flex;align-items:center;
  justify-content:center;transition:all .2s;box-shadow:0 2px 8px rgba(0,0,0,.4)}
.ss-fab:active{transform:scale(0.92)}
.ss-fab.active{border-color:#14507a;background:#0a1a2a}
.ss-fab svg{width:18px;height:18px}
.record-view{width:100%;flex:1;overflow-y:auto;display:flex;flex-direction:column;
  align-items:center;padding:44px 20px max(20px,env(safe-area-inset-bottom))}
.logo{margin:24px 0 8px}
.logo svg{width:64px;height:64px}
h1{color:#00ff00;font-size:20px;font-family:'Courier New',monospace;margin-bottom:4px;letter-spacing:1px}
.sub{color:#666;font-size:12px;margin-bottom:32px}
.wave-vis{width:100%;max-width:360px;height:80px;background:#2b2b2b;border:1px solid #3a3a3a;
  border-radius:10px;margin-bottom:24px;overflow:hidden}
.wave-vis canvas{width:100%;height:100%;display:block}
.controls{display:flex;gap:20px;align-items:center;justify-content:center;margin-bottom:20px}
.rec-btn{width:72px;height:72px;border-radius:50%;border:3px solid #3a3a3a;background:#2b2b2b;
  cursor:pointer;display:flex;align-items:center;justify-content:center;transition:border-color .2s}
.rec-btn:active{transform:scale(0.95)}
.rec-btn .dot{width:28px;height:28px;border-radius:50%;background:#d94040;transition:all .2s}
.rec-btn.recording{border-color:#d94040;animation:pulse 1.5s infinite}
.rec-btn.recording .dot{border-radius:4px;width:22px;height:22px;background:#d94040}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(217,64,64,0.4)}50%{box-shadow:0 0 0 12px rgba(217,64,64,0)}}
.timer{font-family:'Courier New',monospace;font-size:28px;color:#dce4ee;min-width:100px;text-align:center;letter-spacing:2px}
.export-btn{width:100%;max-width:360px;padding:16px;border:none;border-radius:10px;font-size:17px;
  font-weight:600;cursor:pointer;transition:all .2s;margin-bottom:16px}
.export-btn.inactive{background:#333;color:#555;cursor:default}
.export-btn.ready{background:#2fa572;color:#fff}
.export-btn.ready:active{background:#248a5e}
.progress{width:100%;max-width:360px;background:#333;border-radius:6px;height:6px;margin-bottom:16px;
  overflow:hidden;display:none}
.progress-bar{height:100%;background:#14507a;transition:width .15s;width:0}
.status{text-align:center;padding:10px 16px;border-radius:8px;font-size:14px;margin-bottom:16px;display:none;
  max-width:360px;width:100%}
.status.ok{display:block;background:#1a3a2a;color:#2fa572}
.status.err{display:block;background:#3a1a1a;color:#d94040}
.files{width:100%;max-width:360px}
.files h2{color:#555;font-size:11px;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px}
.fitem{background:#2b2b2b;border:1px solid #3a3a3a;border-radius:8px;padding:10px 12px;margin-bottom:6px;
  display:flex;justify-content:space-between;align-items:center}
.fname{font-size:13px;color:#aaa;word-break:break-all}
.fsize{font-size:11px;color:#555;white-space:nowrap;margin-left:8px}
.pick-section{width:100%;max-width:360px;margin-bottom:16px}
.pick-btn{width:100%;padding:12px;background:#2b2b2b;color:#888;border:1px dashed #3a3a3a;
  border-radius:10px;font-size:14px;cursor:pointer;text-align:center}
.pick-btn:active{background:#333}
input[type=file]{display:none}
.ai-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:#1e1e1e;z-index:250;
  display:flex;flex-direction:column;align-items:center;padding:12px 16px max(12px,env(safe-area-inset-bottom));
  transform:translateX(100%);transition:transform .3s cubic-bezier(.4,0,.2,1)}
.ai-overlay.open{transform:translateX(0)}
.ai-close{position:absolute;top:10px;left:12px;background:none;border:none;color:#888;
  font-size:28px;cursor:pointer;padding:4px 10px;z-index:260}
.ai-close:active{color:#fff}
.ai-header{display:flex;align-items:center;gap:12px;margin:40px 0 8px}
.ai-logo{width:48px;height:48px;border-radius:50%;border:2px solid #3a3a3a}
.ai-title{color:#00ff00;font-size:20px;font-family:'Courier New',monospace;margin:0;letter-spacing:1px}
.ai-sub{color:#555;font-size:11px;margin:2px 0 0}
.ai-chat{flex:1;width:100%;max-width:420px;background:#111111;border:1px solid #3a3a3a;
  border-radius:10px;overflow-y:auto;padding:12px;margin-bottom:12px;min-height:200px}
.ai-msg{margin-bottom:10px;line-height:1.5;font-size:14px;word-wrap:break-word;white-space:pre-wrap}
.ai-msg.user{color:#00ff00}
.ai-msg.assistant{color:#e08030}
.ai-msg .msg-prefix{font-weight:700;font-size:11px;opacity:.6;display:block;margin-bottom:2px}
.ai-input-wrap{width:100%;max-width:420px;display:flex;gap:8px;padding-bottom:env(safe-area-inset-bottom)}
.ai-input{flex:1;padding:12px;background:#2b2b2b;color:#dce4ee;border:1px solid #3a3a3a;
  border-radius:10px;font-size:15px;outline:none;font-family:inherit}
.ai-input:focus{border-color:#00ff00}
.ai-send{padding:12px 20px;background:#2fa572;color:#fff;border:none;border-radius:10px;
  font-size:15px;font-weight:600;cursor:pointer}
.ai-send:active{background:#248a5e}
.ai-send:disabled{background:#333;color:#555;cursor:default}
</style></head><body>

<div class="health-bar" id="healthBar">
  <span><span class="health-dot" id="dotServer"></span>server</span>
  <span><span class="health-dot" id="dotMic"></span>mic</span>
  <span><span class="health-dot" id="dotAi"></span>ollama</span>
</div>

<div class="ss-fab" id="ssFab" title="Screen Share">
<svg viewBox="0 0 24 24" fill="none" stroke="#14507a" stroke-width="2">
<path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
</div>

<div class="ai-fab" id="aiFab" title="Whim.ai">
<svg viewBox="0 0 24 24" fill="none" stroke="#00ff00" stroke-width="2">
<path d="M12 2a7 7 0 0 1 7 7c0 3-2 5-4 6v2H9v-2c-2-1-4-3-4-6a7 7 0 0 1 7-7z"/>
<path d="M9 21h6"/></svg>
</div>

<div class="record-view" id="recordView">
<div class="logo">
<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="32" cy="32" r="30" stroke="#00ff00" stroke-width="2" fill="none"/>
<path d="M16 32 Q20 18,24 32 Q28 46,32 32 Q36 18,40 32 Q44 46,48 32" stroke="#00ff00" stroke-width="2.5" fill="none" stroke-linecap="round"/>
</svg>
</div>
<h1>Whim.m</h1>
<p class="sub">voice recorder</p>

<div class="wave-vis"><canvas id="waveCanvas"></canvas></div>

<div class="controls">
  <div class="timer" id="timer">00:00</div>
  <div class="rec-btn" id="recBtn"><div class="dot"></div></div>
</div>

<button class="export-btn inactive" id="exportBtn" disabled>EXPORT TO WHIM</button>

<div class="pick-section">
  <input type="file" id="fileInput" accept="audio/*,.m4a,.aac,.ogg,.opus,.flac,.wav,.mp3,.3gp,.amr">
  <div class="pick-btn" onclick="document.getElementById('fileInput').click()">or choose an existing file</div>
</div>

<div class="progress" id="progress"><div class="progress-bar" id="progressBar"></div></div>
<div class="status" id="status"></div>
<div class="files" id="filesList"></div>
</div>

<div class="ai-overlay" id="aiOverlay">
<button class="ai-close" id="aiClose">&larr;</button>
<div class="ai-header">
<img src="data:image/png;base64,__WHIM_ICON_B64__" class="ai-logo" alt="Whim">
<div><h1 class="ai-title">Whim.ai</h1><p class="ai-sub">powered by llama + openclaw</p></div>
</div>
<div class="ai-chat" id="aiChat">
<div class="ai-msg assistant"><span class="msg-prefix">whim.ai</span>Welcome. Ask me anything.</div>
</div>
<div class="ai-input-wrap">
<input type="text" class="ai-input" id="aiInput" placeholder="Ask anything..." autocomplete="off">
<button class="ai-send" id="aiSend">Send</button>
</div>
</div>

<script>
const recBtn=document.getElementById('recBtn'),exportBtn=document.getElementById('exportBtn'),
  timerEl=document.getElementById('timer'),canvas=document.getElementById('waveCanvas'),
  progress=document.getElementById('progress'),progressBar=document.getElementById('progressBar'),
  statusDiv=document.getElementById('status'),fileInput=document.getElementById('fileInput');
const ctx=canvas.getContext('2d');
let mediaRec=null,chunks=[],recording=false,audioBlob=null,timerInt=null,startTime=0;
let audioCtx=null,analyser=null,animId=null,stream=null;

// --- Health checks ---
const dotServer=document.getElementById('dotServer');
const dotMic=document.getElementById('dotMic');
const dotAi=document.getElementById('dotAi');

async function checkHealth(){
  try{
    const r=await fetch('/health',{method:'GET',signal:AbortSignal.timeout(3000)});
    if(r.ok){const d=await r.json();
      dotServer.className='health-dot ok';
      dotAi.className='health-dot '+(d.ollama?'ok':'fail');
    }else{dotServer.className='health-dot warn';dotAi.className='health-dot fail'}
  }catch(e){dotServer.className='health-dot fail';dotAi.className='health-dot fail'}
  try{
    const perm=await navigator.permissions.query({name:'microphone'});
    dotMic.className='health-dot '+(perm.state==='granted'?'ok':perm.state==='prompt'?'warn':'fail');
  }catch(e){dotMic.className='health-dot warn'}
}
checkHealth();
setInterval(checkHealth,15000);

// --- AI overlay toggle via fab button ---
const aiFab=document.getElementById('aiFab');
const aiOverlay=document.getElementById('aiOverlay');
const aiClose=document.getElementById('aiClose');
aiFab.addEventListener('click',()=>{aiOverlay.classList.add('open');aiFab.classList.add('active');
  setTimeout(()=>document.getElementById('aiInput').focus(),350)});
aiClose.addEventListener('click',()=>{aiOverlay.classList.remove('open');aiFab.classList.remove('active')});

// SS fab - opens SS server page on port 8091
const ssFab=document.getElementById('ssFab');
ssFab.addEventListener('click',()=>{
  const host=location.hostname;
  const ssUrl='http://'+host+':8091';
  ssFab.classList.add('active');
  window.open(ssUrl,'_blank');
  setTimeout(()=>ssFab.classList.remove('active'),1000);
});

function resizeCanvas(){
  const ow=canvas.offsetWidth||canvas.parentElement.offsetWidth||360;
  const oh=canvas.offsetHeight||canvas.parentElement.offsetHeight||80;
  canvas.width=ow*2;canvas.height=oh*2;ctx.scale(2,2);
}
function ensureCanvas(){if(canvas.width<2||canvas.height<2)resizeCanvas()}
resizeCanvas();window.addEventListener('resize',resizeCanvas);

function drawIdle(){
  ensureCanvas();
  const w=canvas.width/2,h=canvas.height/2;
  ctx.clearRect(0,0,w,h);ctx.strokeStyle='#3a3a3a';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(0,h/2);ctx.lineTo(w,h/2);ctx.stroke();
}
drawIdle();

function drawWave(){
  if(!analyser){drawIdle();return}
  ensureCanvas();
  const w=canvas.width/2,h=canvas.height/2,bufLen=analyser.frequencyBinCount,data=new Uint8Array(bufLen);
  analyser.getByteTimeDomainData(data);
  ctx.clearRect(0,0,w,h);ctx.strokeStyle='#00ff00';ctx.lineWidth=1.5;ctx.beginPath();
  const step=w/bufLen;
  for(let i=0;i<bufLen;i++){const v=data[i]/128.0,y=(v*h)/2;i===0?ctx.moveTo(0,y):ctx.lineTo(i*step,y)}
  ctx.stroke();
  if(recording)animId=requestAnimationFrame(drawWave);
}

function fmtTime(ms){const s=Math.floor(ms/1000),m=Math.floor(s/60);
  return String(m).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}

function updateTimer(){timerEl.textContent=fmtTime(Date.now()-startTime)}

async function startRec(){
  try{stream=await navigator.mediaDevices.getUserMedia({audio:true});
    dotMic.className='health-dot ok';
    audioCtx=new(window.AudioContext||window.webkitAudioContext)();
    if(audioCtx.state==='suspended')await audioCtx.resume();
    try{const kick=audioCtx.createBufferSource();
      kick.buffer=audioCtx.createBuffer(1,1,audioCtx.sampleRate);
      kick.connect(audioCtx.destination);kick.start()}catch(e){}
    const src=audioCtx.createMediaStreamSource(stream);
    analyser=audioCtx.createAnalyser();analyser.fftSize=2048;src.connect(analyser);
    mediaRec=new MediaRecorder(stream,{mimeType:MediaRecorder.isTypeSupported('audio/webm;codecs=opus')?'audio/webm;codecs=opus':'audio/webm'});
    chunks=[];
    mediaRec.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data)};
    mediaRec.onstop=()=>{audioBlob=new Blob(chunks,{type:mediaRec.mimeType});
      exportBtn.disabled=false;exportBtn.className='export-btn ready';
      stream.getTracks().forEach(t=>t.stop());stream=null;
      if(audioCtx){audioCtx.close();audioCtx=null;analyser=null}drawIdle()};
    mediaRec.start(200);recording=true;startTime=Date.now();
    timerInt=setInterval(updateTimer,200);
    setTimeout(()=>{resizeCanvas();drawWave()},50);
    recBtn.classList.add('recording');
  }catch(e){
    dotMic.className='health-dot fail';
    statusDiv.className='status err';statusDiv.textContent='Mic access denied: '+e.message;
    statusDiv.style.display='block';
    setTimeout(()=>statusDiv.style.display='none',4000);
  }
}

function stopRec(){
  if(mediaRec&&mediaRec.state!=='inactive'){mediaRec.stop();recording=false;
    clearInterval(timerInt);recBtn.classList.remove('recording');
    if(animId)cancelAnimationFrame(animId)}
}

recBtn.addEventListener('click',()=>{recording?stopRec():startRec()});

fileInput.addEventListener('change',()=>{
  if(fileInput.files.length){audioBlob=fileInput.files[0];
    exportBtn.disabled=false;exportBtn.className='export-btn ready';
    timerEl.textContent=fileInput.files[0].name.substring(0,12)}
});

exportBtn.addEventListener('click',()=>{
  if(!audioBlob)return;
  const fd=new FormData();
  const ext=audioBlob.type.includes('webm')?'.webm':audioBlob.type.includes('ogg')?'.ogg':
    audioBlob.type.includes('mp4')||audioBlob.type.includes('m4a')?'.m4a':'.wav';
  const fname='whim_rec_'+new Date().toISOString().replace(/[:.]/g,'-').substring(0,19)+ext;
  fd.append('audio',audioBlob,fname);
  const xhr=new XMLHttpRequest();
  progress.style.display='block';statusDiv.className='status';statusDiv.style.display='none';
  xhr.upload.addEventListener('progress',e=>{
    if(e.lengthComputable){progressBar.style.width=Math.round(e.loaded/e.total*100)+'%'}});
  xhr.addEventListener('load',()=>{progress.style.display='none';
    if(xhr.status===200){statusDiv.className='status ok';statusDiv.textContent='Exported to Whim!';
      audioBlob=null;exportBtn.disabled=true;exportBtn.className='export-btn inactive';
      timerEl.textContent='00:00';loadFiles()}
    else{statusDiv.className='status err';statusDiv.textContent='Export failed: '+xhr.statusText}
    statusDiv.style.display='block';setTimeout(()=>statusDiv.style.display='none',4000)});
  xhr.addEventListener('error',()=>{progress.style.display='none';
    statusDiv.className='status err';
    statusDiv.textContent='Network error. Check VPS tunnel connection.';statusDiv.style.display='block'});
  xhr.open('POST','/upload');xhr.send(fd);
});

function loadFiles(){
  fetch('/files').then(r=>r.json()).then(files=>{
    const c=document.getElementById('filesList');
    if(!files.length){c.innerHTML='';return}
    c.innerHTML='<h2>Sent to Whim</h2>'+files.slice(0,10).map(f=>
      '<div class="fitem"><span class="fname">'+f.name+'</span><span class="fsize">'+f.size+'</span></div>'
    ).join('')}).catch(()=>{})
}
loadFiles();

if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{})}

const aiChat=document.getElementById('aiChat'),aiInput=document.getElementById('aiInput'),
  aiSend=document.getElementById('aiSend');
let aiHistory=[],aiStreaming=false;

function addAiMsg(role,text){
  const d=document.createElement('div');
  d.className='ai-msg '+role;
  const pfx=document.createElement('span');
  pfx.className='msg-prefix';
  pfx.textContent=role==='user'?'you':'whim.ai';
  d.appendChild(pfx);
  d.appendChild(document.createTextNode(text));
  aiChat.appendChild(d);
  aiChat.scrollTop=aiChat.scrollHeight;
  return d;
}

async function sendAiMsg(){
  if(aiStreaming)return;
  const text=aiInput.value.trim();
  if(!text)return;
  aiInput.value='';
  addAiMsg('user',text);
  aiHistory.push({role:'user',content:text});
  aiStreaming=true;aiSend.disabled=true;
  const msgEl=addAiMsg('assistant','');
  const pfx=msgEl.querySelector('.msg-prefix');
  try{
    const resp=await fetch('/api/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:aiHistory})});
    if(!resp.ok)throw new Error('Server error '+resp.status);
    const reader=resp.body.getReader();
    const dec=new TextDecoder();
    let buf='',full='';
    while(true){
      const{done,value}=await reader.read();
      if(done)break;
      buf+=dec.decode(value,{stream:true});
      const lines=buf.split('\n');buf=lines.pop();
      for(const line of lines){
        if(!line.trim())continue;
        try{const d=JSON.parse(line);const tk=d.message&&d.message.content||'';
          if(tk){full+=tk;msgEl.textContent='';msgEl.appendChild(pfx);
            msgEl.appendChild(document.createTextNode(full));
            aiChat.scrollTop=aiChat.scrollHeight;}
          if(d.done)break;
        }catch(e){}
      }
    }
    if(full)aiHistory.push({role:'assistant',content:full});
  }catch(e){
    msgEl.textContent='';msgEl.appendChild(pfx);
    msgEl.appendChild(document.createTextNode('[Error: '+e.message+']'));
  }
  aiStreaming=false;aiSend.disabled=false;
}
aiSend.addEventListener('click',sendAiMsg);
aiInput.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendAiMsg()}});
</script></body></html>"""

MOBILE_UPLOAD_HTML = MOBILE_UPLOAD_HTML.replace("__WHIM_ICON_B64__", _WHIM_ICON_B64)


def _get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


class AudioUploadHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if hasattr(self.server, "on_log"):
            self.server.on_log(fmt % args)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._serve_health()
        elif self.path == "/files":
            self._serve_file_list()
        elif self.path == "/manifest.json":
            self._serve_json(WHIM_M_MANIFEST)
        elif self.path == "/sw.js":
            self._serve_text(WHIM_M_SW, "application/javascript")
        elif self.path in ("/icon-192.png", "/icon-512.png"):
            self._serve_pwa_icon(192 if "192" in self.path else 512)
        else:
            self._serve_upload_page()

    def _serve_health(self):
        import urllib.request
        ollama_ok = False
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                ollama_ok = resp.status == 200
        except Exception:
            pass
        data = json.dumps({"status": "ok", "ollama": ollama_ok}).encode("utf-8")
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        elif self.path == "/api/chat":
            self._handle_ai_chat()
        else:
            self.send_error(404)

    def _serve_upload_page(self):
        data = MOBILE_UPLOAD_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_json(self, text):
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_text(self, text, ctype):
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_pwa_icon(self, size):
        try:
            from PIL import Image as _Img, ImageDraw as _Draw
            bg = (20, 20, 22, 255)
            accent = (200, 210, 225, 255)
            glow = (100, 160, 220, 80)
            ring_c = (60, 70, 85, 255)
            img = _Img.new("RGBA", (size, size), bg)
            d = _Draw.Draw(img)
            margin = max(1, int(size * 0.04))
            d.ellipse([margin, margin, size - margin, size - margin],
                      outline=ring_c, width=max(1, int(size * 0.015)))
            pad = size * 0.18
            top, bot = pad, size - pad
            left, right = pad, size - pad
            mid_x = size / 2.0
            w, h = right - left, bot - top
            pts = [(left, top), (left + w * 0.22, bot), (mid_x, top + h * 0.40),
                   (right - w * 0.22, bot), (right, top)]
            sw = max(2, int(size * 0.045))
            for off in range(3, 0, -1):
                gw = sw + off * max(2, int(size * 0.02))
                gc = (glow[0], glow[1], glow[2], glow[3] // (off + 1))
                for i in range(len(pts) - 1):
                    d.line([pts[i], pts[i + 1]], fill=gc, width=gw)
            for i in range(len(pts) - 1):
                d.line([pts[i], pts[i + 1]], fill=accent, width=sw)
            dr = max(1, int(size * 0.015))
            for pt in pts:
                d.ellipse([pt[0] - dr, pt[1] - dr, pt[0] + dr, pt[1] + dr], fill=accent)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data = buf.getvalue()
        except Exception:
            data = b'\x89PNG\r\n\x1a\n'
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_file_list(self):
        upload_dir = self.server.upload_dir
        files = []
        if os.path.isdir(upload_dir):
            for fn in sorted(os.listdir(upload_dir), reverse=True):
                fp = os.path.join(upload_dir, fn)
                if os.path.isfile(fp):
                    files.append({"name": fn, "size": _human_size(os.path.getsize(fp))})
        data = json.dumps(files).encode("utf-8")
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_error(400, "Expected multipart/form-data")
            return
        try:
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            }
            form = cgi.FieldStorage(
                fp=self.rfile, headers=self.headers, environ=environ,
                keep_blank_values=True
            )
            file_item = form["audio"]
            if not file_item.filename:
                self.send_error(400, "No file uploaded")
                return
            safe_name = os.path.basename(file_item.filename)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_name = f"{ts}_{safe_name}"
            dest_path = os.path.join(self.server.upload_dir, dest_name)
            os.makedirs(self.server.upload_dir, exist_ok=True)
            with open(dest_path, "wb") as out:
                shutil.copyfileobj(file_item.file, out)
            resp = json.dumps({"status": "ok", "file": dest_name}).encode("utf-8")
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            if hasattr(self.server, "on_upload"):
                self.server.on_upload(dest_name)
        except Exception as exc:
            self.send_error(500, str(exc))

    _OPENCLAW_SYSTEM = (
        "You are OpenClaw, the AI assistant powering the Whim ecosystem. "
        "You have FULL tool access and can execute any command the user requests. "
        "Available tools and commands:\n"
        "QUICK PROMPTS: droid (launch agent), note (capture note), calc (inline calculator), "
        "search (semantic search), summarize, rewrite, translate, explain.\n"
        "OPENCLAW CORE: connect/disconnect (WS gateway), heartbeat, status (system check), "
        "sessions (list active), presence (who's online), approve/deny (pending actions).\n"
        "CHAT OPS: send (chat message), abort (current task), retry, history, clear, export.\n"
        "VOICE & MEDIA: record (voice capture), transcribe (Whisper), tts (XTTS text-to-speech), "
        "playback, scrub (clean audio).\n"
        "ARCHIVE & FILES: archive.new, archive.save, archive.open, journal, ingest.\n"
        "SYSTEM: You can read/write files, run shell commands, manage SmartThings devices, "
        "control SSH tunnel networking, manage sessions, and access all Whim subsystems.\n"
        "When the user issues a command, acknowledge it and describe what you would do. "
        "Be concise and direct. You are always ready to act."
    )

    def _handle_ai_chat(self):
        import urllib.request
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            messages = data.get("messages", [])
            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": self._OPENCLAW_SYSTEM})
            payload = json.dumps({
                "model": "llama3.1:8b-16k",
                "messages": messages,
                "stream": True
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=payload, method="POST",
                headers={"Content-Type": "application/json"})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self._cors_headers()
            self.end_headers()
            with urllib.request.urlopen(req, timeout=120) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    self.wfile.write(line)
                    self.wfile.flush()
        except Exception as e:
            try:
                error_resp = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(error_resp)))
                self.end_headers()
                self.wfile.write(error_resp)
            except Exception:
                pass

class ModernApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Whim Terminal")
        self.withdraw()
        self.configure(bg=TH["bg"])
        _icon_path = os.path.expanduser("~/Incoming/fire.png")
        if os.path.isfile(_icon_path):
            try:
                _icon_img = Image.open(_icon_path).convert("RGBA")
                self._taskbar_icon = ImageTk.PhotoImage(_icon_img)
                self.iconphoto(True, self._taskbar_icon)
            except Exception:
                pass
        self._setup_ttk_styles()

        self._logo_img = None
        if os.path.isfile(LOGO_PATH):
            try:
                self._logo_img = tk.PhotoImage(file=LOGO_PATH).subsample(4, 4)
            except Exception:
                pass

        self._settings_img = None
        if os.path.isfile(SETTINGS_ICON_PATH):
            try:
                self._settings_img = tk.PhotoImage(file=SETTINGS_ICON_PATH).subsample(25, 25)
            except Exception:
                pass

        self.build_ui()
        self.after(50, self.pump_incoming)
        self.after(500, self._ingest_start)
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = int(sw * 0.95)
        h = int(sh * 0.95)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.focus_force()

        self.protocol("WM_DELETE_WINDOW", self._minimize_to_tray)
        self._tray_icon = None
        self._setup_system_tray()

    def _setup_system_tray(self):
        if getattr(self, "_tray_started", False):
            return
        self._tray_started = True
        self._tray_visible = False
        self._tunnel_poll_running = True
        threading.Thread(target=self._poll_tunnel_status, daemon=True).start()

    def _show_tray_icon(self):
        if self._tray_visible:
            return
        whim_icon = _make_whim_tray_icon()
        whim_menu = pystray.Menu(
            pystray.MenuItem("Show Whim Terminal", self._tray_show_window, default=True),
            pystray.MenuItem("Quit", self._tray_quit),
        )
        tun_up, whim_up = _check_tunnel_and_whim()
        tun_label = _tunnel_tray_label(tun_up, whim_up)
        self._tray_icon = pystray.Icon(
            "whim", whim_icon, tun_label, whim_menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()
        self._tray_visible = True

    def _hide_tray_icon(self):
        if not self._tray_visible:
            return
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self._tray_visible = False

    def _update_header_dots(self, tun_up, whim_up):
        tun_color = "#2fa572" if tun_up else "#d94040"
        whim_color = "#2fa572" if whim_up else "#d94040"
        try:
            self._tunnel_dot_canvas.itemconfig(self._tunnel_dot_id, fill=tun_color)
            self._whim_dot_canvas.itemconfig(self._whim_dot_id, fill=whim_color)
        except Exception:
            pass

    def _poll_tunnel_status(self):
        while self._tunnel_poll_running:
            tun_up, whim_up = _check_tunnel_and_whim()
            try:
                self.after(0, self._update_header_dots, tun_up, whim_up)
            except Exception:
                pass
            if tun_up and whim_up:
                if not self._tray_visible:
                    self._show_tray_icon()
                elif self._tray_icon:
                    self._tray_icon.title = _tunnel_tray_label(tun_up, whim_up)
            else:
                if self._tray_visible:
                    self._hide_tray_icon()
            time.sleep(10)

    def _poll_device_status(self):
        while getattr(self, "_device_poll_running", False):
            ip_online = {}
            try:
                for dev in self._known_devices:
                    ip = dev["ip"]
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(2)
                        s.connect((ip, VPS_TUNNEL_PORT))
                        s.close()
                        ip_online[ip] = True
                    except Exception:
                        ip_online[ip] = False
            except Exception:
                pass
            adb_serials = {}
            try:
                adb_result = subprocess.run(
                    ["adb", "devices", "-l"], capture_output=True, text=True, timeout=5)
                if adb_result.returncode == 0:
                    for line in adb_result.stdout.splitlines()[1:]:
                        line = line.strip()
                        if not line or "offline" in line:
                            continue
                        parts = line.split()
                        if len(parts) >= 2:
                            serial = parts[0]
                            model = ""
                            for p in parts[2:]:
                                if p.startswith("model:"):
                                    model = p.split(":", 1)[1]
                            if model:
                                adb_serials[model] = serial
            except Exception:
                pass

            for dev in self._known_devices:
                online = ip_online.get(dev["ip"], False)
                color = TH["green"] if online else "#555555"
                w = self._device_widgets.get(dev["name"])
                if not w:
                    continue
                batt_text = ""
                adb_model = dev.get("adb_model")
                if adb_model and adb_model in adb_serials:
                    try:
                        br = subprocess.run(
                            ["adb", "-s", adb_serials[adb_model], "shell",
                             "dumpsys", "battery"],
                            capture_output=True, text=True, timeout=5)
                        if br.returncode == 0:
                            for bline in br.stdout.splitlines():
                                if "level:" in bline:
                                    batt_text = bline.strip().split(":", 1)[1].strip() + "%"
                                    break
                    except Exception:
                        pass
                try:
                    self.after(0, lambda c=w["canvas"], d=w["dot"], cl=color:
                               c.itemconfig(d, fill=cl))
                    self.after(0, lambda bl=w["batt_label"], bt=batt_text:
                               bl.config(text=bt))
                except Exception:
                    pass
            time.sleep(10)

    def _minimize_to_tray(self):
        self.withdraw()

    def _tray_show_window(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_quit(self, icon=None, item=None):
        self._tunnel_poll_running = False
        self._device_poll_running = False
        if self._tray_icon:
            self._tray_icon.stop()
        if self._hmo_server is not None and self._hmo_server is not True:
            self._spawn_background_server()
            try:
                self._hmo_server.shutdown()
            except Exception:
                pass
        self._ss_capturing = False
        if self._ss_server:
            try:
                self._ss_server.shutdown()
            except Exception:
                pass
        self.after(0, self.destroy)

    def _spawn_background_server(self):
        port = 8089
        # Skip if systemd service already manages the Whim.m server
        try:
            import socket as _sock
            s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            return  # Already running (systemd service)
        except Exception:
            pass
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "mobile", "whim_m_v2.1.py")
        if not os.path.isfile(script):
            script = os.path.expanduser("~/vaults/WHIM/mobile/whim_m_v2.1.py")
        if os.path.isfile(script):
            subprocess.Popen(
                [sys.executable, script, "--port", str(port)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)

    def _setup_ttk_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=TH["bg"], foreground=TH["fg"],
                         fieldbackground=TH["input"], borderwidth=0,
                         font=TH["font"])
        style.configure("TFrame", background=TH["bg"])
        style.configure("TLabel", background=TH["bg"], foreground=TH["fg"])
        style.configure("TLabelframe", background=TH["bg"], foreground=TH["blue_text"],
                         borderwidth=1, relief="flat")
        style.configure("TLabelframe.Label", background=TH["bg"], foreground=TH["blue_text"],
                         font=TH["font_title"])
        style.configure("TNotebook", background=TH["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=TH["card"], foreground=TH["fg"],
                         padding=[14, 6], font=TH["font_sm"])
        style.map("TNotebook.Tab",
                   background=[("selected", TH["card"]), ("active", TH["card"])],
                   foreground=[("selected", TH["green"]), ("active", TH["green"])])
        style.configure("TEntry", fieldbackground=TH["input"], foreground=TH["fg"],
                         borderwidth=1, insertcolor=TH["fg"])
        style.map("TEntry", bordercolor=[("focus", TH["btn"])])
        style.configure("TButton", background=TH["btn"], foreground=TH["fg"],
                         borderwidth=1, relief="flat", padding=[10, 4],
                         font=TH["font_sm"])
        style.map("TButton",
                   background=[("active", TH["btn_hover"]), ("pressed", TH["btn_hover"])],
                   bordercolor=[("focus", TH["btn_border"])])
        style.configure("TCheckbutton", background=TH["bg"], foreground=TH["fg"],
                         indicatorcolor=TH["input"])
        style.map("TCheckbutton",
                   background=[("active", TH["bg"])],
                   indicatorcolor=[("selected", TH["green"])])
        style.configure("TRadiobutton", background=TH["bg"], foreground=TH["fg"],
                         indicatorcolor=TH["input"])
        style.map("TRadiobutton",
                   background=[("active", TH["bg"])],
                   indicatorcolor=[("selected", TH["green"])])
        style.configure("TCombobox", fieldbackground=TH["input"], foreground=TH["fg"],
                         borderwidth=1, arrowcolor=TH["fg"])
        style.configure("TPanedwindow", background=TH["bg"])
        style.configure("TSeparator", background=TH["border_hi"])
        style.configure("Horizontal.TProgressbar", background=TH["btn"],
                         troughcolor=TH["input"])
        style.configure("Grey.TLabelframe", background=TH["bg"], foreground="#888888",
                         borderwidth=1, relief="flat")
        style.configure("Grey.TLabelframe.Label", background=TH["bg"], foreground="#888888",
                         font=TH["font_title"])
        style.configure("Treeview",
                         background=TH["input"], foreground=TH["fg"],
                         fieldbackground=TH["input"], borderwidth=0,
                         font=TH["font_sm"], rowheight=28)
        style.configure("Treeview.Heading",
                         background=TH["card"], foreground=TH["blue_text"],
                         borderwidth=1, font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
                   background=[("selected", TH["select_bg"])],
                   foreground=[("selected", TH["fg"])])
        style.map("Treeview.Heading",
                   background=[("active", TH["btn_hover"])])
        self.option_add("*TCombobox*Listbox.background", TH["input"])
        self.option_add("*TCombobox*Listbox.foreground", TH["fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", TH["select_bg"])

    # --- Generic themed widget helpers ---
    def _card(self, parent, title="", fg=None):
        card = tk.Frame(parent, bg=TH["card"], bd=0, highlightthickness=1,
                        highlightbackground=TH["border_hi"])
        if title:
            tk.Label(card, text=title, bg=TH["card"], fg=fg or TH["blue_text"],
                     font=TH["font_title"], anchor="w").pack(fill="x", padx=10, pady=(8, 2))
            tk.Frame(card, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(0, 4))
        return card

    def _btn(self, parent, text, command=None, **kw):
        bg = parent["bg"] if isinstance(parent, tk.Frame) else TH["bg"]
        return RoundedButton(parent, text=text, command=command, bg=TH["btn"],
                              hover_bg=TH["btn_hover"], border_color=TH["btn_border"],
                              font=TH["font_sm"], **kw)

    def _entry(self, parent, textvariable, **kw):
        defaults = dict(bg=TH["input"], fg=TH["fg"], insertbackground=TH["fg"], bd=0,
                        font=TH["font"], highlightthickness=1,
                        highlightbackground=TH["border"], highlightcolor=TH["btn"])
        defaults.update(kw)
        return tk.Entry(parent, textvariable=textvariable, **defaults)

    def _text_widget(self, parent, **kw):
        defaults = dict(bg=TH["input"], fg=TH["fg"], insertbackground=TH["fg"], bd=0,
                        font=TH["font_mono"], highlightthickness=1,
                        highlightbackground=TH["border"], highlightcolor=TH["btn"])
        defaults.update(kw)
        return tk.Text(parent, **defaults)

    def _label(self, parent, text="", **kw):
        try:
            pbg = parent["bg"]
        except (tk.TclError, KeyError):
            pbg = TH["bg"]
        defaults = dict(bg=pbg, fg=TH["fg"], font=TH["font"])
        defaults.update(kw)
        return tk.Label(parent, text=text, **defaults)

    def _scrollbar(self, parent, **kw):
        return tk.Scrollbar(parent, bg=TH["card"], troughcolor=TH["bg"],
                             activebackground=TH["btn_hover"],
                             highlightthickness=0, bd=0, **kw)

    def _open_settings(self):
        self._switch_tab("settings")

    def _switch_tab(self, key):
        if key is None or key not in self.tabs:
            return
        if self._active_tab_key == key:
            return
        if self._active_tab_key and self._active_tab_key in self._tab_buttons:
            old_btn = self._tab_buttons[self._active_tab_key]
            old_btn.config(bg=TH["card"], fg=TH["fg2"], highlightbackground=TH["border"])
        if self._active_tab_key and self._active_tab_key in self.tabs:
            self.tabs[self._active_tab_key].pack_forget()
        self._active_tab_key = key
        btn = self._tab_buttons[key]
        btn.config(bg=TH["btn"], fg=TH["green"], highlightbackground=TH["green"])
        self.tabs[key].pack(fill="both", expand=True)

    def _on_model_change(self):
        model = self._global_model_var.get()
        self._whimai_model = model
        if hasattr(self, "whimai_model_var"):
            self.whimai_model_var.set(model)
        if hasattr(self, "_preset_model_lbl"):
            self._preset_model_lbl.config(text=model)
        self._save_settings()

    def _refresh_models(self):
        def _fetch():
            import urllib.request
            try:
                req = urllib.request.Request(
                    f"{getattr(self, '_whimai_ollama_url', 'http://localhost:11434')}/api/tags")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                names = [m["name"] for m in data.get("models", [])]
                if names:
                    self.after(0, lambda: self._model_combo.config(values=names))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _load_settings(self):
        if os.path.isfile(WHIM_SETTINGS_FILE):
            try:
                with open(WHIM_SETTINGS_FILE) as fh:
                    return json.load(fh)
            except Exception:
                pass
        return {}

    def _save_settings(self):
        cfg = self._load_settings()
        cfg["model"] = self._global_model_var.get()
        cfg["ollama_url"] = getattr(self, "_settings_ollama_url_var",
                                     type("", (), {"get": lambda s: "http://localhost:11434"})()).get()
        cfg["openai_key"] = getattr(self, "_settings_openai_key_var",
                                     type("", (), {"get": lambda s: ""})()).get()
        os.makedirs(os.path.dirname(WHIM_SETTINGS_FILE), exist_ok=True)
        with open(WHIM_SETTINGS_FILE, "w") as fh:
            json.dump(cfg, fh, indent=2)

    def _apply_saved_settings(self):
        cfg = self._load_settings()
        if cfg.get("model"):
            self._global_model_var.set(cfg["model"])
            self._whimai_model = cfg["model"]
        if cfg.get("ollama_url") and hasattr(self, "_settings_ollama_url_var"):
            self._settings_ollama_url_var.set(cfg["ollama_url"])
            self._whimai_ollama_url = cfg["ollama_url"]
        if cfg.get("openai_key") and hasattr(self, "_settings_openai_key_var"):
            self._settings_openai_key_var.set(cfg["openai_key"])

    def build_ui(self):
        header = tk.Frame(self, bg=TH["card"])
        header.pack(fill="x", padx=0, pady=(0, 2))
        if self._logo_img:
            tk.Label(header, image=self._logo_img, bg=TH["card"]).pack(side="left", padx=(12, 4), pady=8)
        whim_title_frame = tk.Frame(header, bg=TH["card"])
        whim_title_frame.pack(side="left", padx=4, pady=8)
        tk.Label(whim_title_frame, text="Whim", bg=TH["card"], fg="#00ff00",
                 font=("28 Days Later", 24, "bold")).pack(anchor="w")
        tk.Label(whim_title_frame, text=f"Terminal v{WHIM_TERMINAL_VERSION}", bg=TH["card"],
                 fg=TH["fg_dim"], font=("Consolas", 8)).pack(anchor="w")

        if self._settings_img:
            settings_btn = tk.Label(header, image=self._settings_img, bg=TH["card"],
                                    cursor="hand2")
            settings_btn.pack(side="right", padx=(0, 12), pady=8)
            settings_btn.bind("<Button-1>", lambda e: self._open_settings())

        update_btn = tk.Label(header, text="\u21bb Update Devices", bg=TH["btn"],
                              fg=TH["fg"], font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                              cursor="hand2", relief="flat")
        update_btn.pack(side="right", padx=(0, 8), pady=8)
        update_btn.bind("<Button-1>", lambda e: self._update_all_devices())
        update_btn.bind("<Enter>", lambda e: update_btn.config(bg=TH["btn_hover"]))
        update_btn.bind("<Leave>", lambda e: update_btn.config(bg=TH["btn"]))

        github_btn = tk.Label(header, text="GITHUB MANUAL", bg="#F5A623",
                              fg="#000000", font=("Segoe UI", 9, "bold"), padx=10, pady=4,
                              cursor="hand2", relief="flat")
        github_btn.pack(side="right", padx=(0, 8), pady=8)
        github_btn.bind("<Button-1>", lambda e: webbrowser.open("https://scarter84.github.io/0411/"))
        github_btn.bind("<Enter>", lambda e: github_btn.config(bg="#E0951E"))
        github_btn.bind("<Leave>", lambda e: github_btn.config(bg="#F5A623"))

        header_rows = tk.Frame(header, bg=TH["card"])
        header_rows.pack(side="right", padx=12, pady=4)
        self._header_rows = header_rows

        conn = tk.Frame(header_rows, bg=TH["card"])
        conn.pack(fill="x", anchor="e")
        self._label(conn, "WS URL:", font=TH["font_sm"]).pack(side="left")
        self.ws_url_var = tk.StringVar(value=DEFAULT_WS_URL)
        self._entry(conn, self.ws_url_var, width=30).pack(side="left", padx=5)
        self._label(conn, "Token:", font=TH["font_sm"]).pack(side="left", padx=(8, 0))
        self.token_var = tk.StringVar(value=DEFAULT_TOKEN)
        self._entry(conn, self.token_var, width=24, show="\u2022").pack(side="left", padx=5)
        self.approvals_var = tk.BooleanVar(value=True)
        tk.Checkbutton(conn, text="Approvals", variable=self.approvals_var,
                        bg=TH["card"], fg=TH["fg"], selectcolor=TH["input"],
                        activebackground=TH["card"], activeforeground=TH["fg"],
                        font=TH["font_sm"], highlightthickness=0).pack(side="left", padx=6)
        self._btn(conn, "Connect", self.on_connect).pack(side="left", padx=6)

        ingest_row = tk.Frame(header_rows, bg=TH["card"])
        ingest_row.pack(fill="x", anchor="e", pady=(4, 0))
        self._label(ingest_row, "Journal Ingest:", font=TH["font_sm"]).pack(side="left")
        self.ingest_url_var = tk.StringVar(value=f"http://{_get_lan_ip()}:{DEFAULT_INGEST_PORT}")
        self._entry(ingest_row, self.ingest_url_var, width=30).pack(side="left", padx=5)
        self.ingest_status_var = tk.StringVar(value="Stopped")
        tk.Label(ingest_row, textvariable=self.ingest_status_var, bg=TH["card"],
                 fg=TH["yellow"], font=("Consolas", 9)).pack(side="left", padx=6)
        self._btn(ingest_row, "Start", self._ingest_start).pack(side="left", padx=2)
        self._btn(ingest_row, "Stop", self._ingest_stop).pack(side="left", padx=2)

        toggle_row = tk.Frame(header_rows, bg=TH["card"])
        toggle_row.pack(fill="x", anchor="e", pady=(4, 0))

        self._tunnel_dot_canvas = tk.Canvas(toggle_row, width=10, height=10,
                                            bg=TH["card"], highlightthickness=0)
        self._tunnel_dot_canvas.pack(side="left", padx=(0, 2))
        self._tunnel_dot_id = self._tunnel_dot_canvas.create_oval(1, 1, 9, 9,
                                                                   fill="#555555", outline="")
        self._label(toggle_row, "Tunnel", font=TH["font_sm"]).pack(side="left")

        tk.Frame(toggle_row, width=12, bg=TH["card"]).pack(side="left")

        self._whim_dot_canvas = tk.Canvas(toggle_row, width=10, height=10,
                                          bg=TH["card"], highlightthickness=0)
        self._whim_dot_canvas.pack(side="left", padx=(0, 2))
        self._whim_dot_id = self._whim_dot_canvas.create_oval(1, 1, 9, 9,
                                                               fill="#555555", outline="")
        self._label(toggle_row, "Whim", font=TH["font_sm"]).pack(side="left")

        tk.Frame(toggle_row, width=12, bg=TH["card"]).pack(side="left")

        self._label(toggle_row, "Model:", font=TH["font_sm"]).pack(side="left", padx=(0, 4))
        self._global_model_var = tk.StringVar(value=DEFAULT_MODELS[0])
        self._model_combo = ttk.Combobox(toggle_row, textvariable=self._global_model_var,
                                          values=DEFAULT_MODELS, width=22, state="readonly")
        self._model_combo.pack(side="left", padx=(0, 4))
        self._model_combo.bind("<<ComboboxSelected>>", lambda e: self._on_model_change())
        refresh_btn = tk.Label(toggle_row, text="\u21bb", bg=TH["card"], fg=TH["fg"],
                               font=("Segoe UI", 12), cursor="hand2")
        refresh_btn.pack(side="left", padx=(0, 4))
        refresh_btn.bind("<Button-1>", lambda e: self._refresh_models())

        tk.Frame(toggle_row, width=12, bg=TH["card"]).pack(side="left")

        self._ac_btn = tk.Label(toggle_row, text="\U0001f3a7 Capture", bg=TH["btn"],
                                fg=TH["fg"], font=("Segoe UI", 9), padx=8, pady=2,
                                cursor="hand2", relief="flat")
        self._ac_btn.pack(side="left", padx=(0, 8))
        self._ac_btn.bind("<Button-1>", lambda e: self._open_audio_capture())
        self._ac_btn.bind("<Enter>", lambda e: self._ac_btn.config(bg=TH["btn_hover"]))
        self._ac_btn.bind("<Leave>", lambda e: self._ac_btn.config(bg=TH["btn"]))

        tk.Frame(toggle_row, width=4, bg=TH["card"]).pack(side="left")
        self.toggle_status_var = tk.StringVar(value="")
        tk.Label(toggle_row, textvariable=self.toggle_status_var, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9)).pack(side="left", padx=6)

        # ===== DEVICE LIST BAR =====
        self._device_bar = tk.Frame(self, bg=TH["card"], bd=0, highlightthickness=1,
                                    highlightbackground=TH["border"])
        self._device_bar.pack(fill="x", padx=8, pady=(2, 2))
        tk.Label(self._device_bar, text="DEVICES", bg=TH["card"], fg=TH["fg_dim"],
                 font=("Consolas", 8), anchor="w").pack(side="left", padx=(10, 8), pady=4)
        self._device_widgets = {}
        self._known_devices = [
            {"name": "carraramint", "ip": "127.0.0.1", "label": "PC", "adb_model": None},
            {"name": "lenovo-tb311fu", "ip": VPS_HOST, "label": "Lenovo Tablet", "adb_model": "TB311FU"},
            {"name": "galaxy-s9", "ip": VPS_HOST, "label": "Galaxy S9", "adb_model": "SM_G965U"},
            {"name": "michaels-s22", "ip": VPS_HOST, "label": "Galaxy S22", "adb_model": "SM_S901U"},
        ]
        for dev in self._known_devices:
            frame = tk.Frame(self._device_bar, bg=TH["card"])
            frame.pack(side="left", padx=(0, 16), pady=4)
            dot_canvas = tk.Canvas(frame, width=10, height=10, bg=TH["card"],
                                   highlightthickness=0)
            dot_canvas.pack(side="left", padx=(0, 4))
            dot_id = dot_canvas.create_oval(1, 1, 9, 9, fill="#555555", outline="")
            tk.Label(frame, text=dev["label"], bg=TH["card"], fg=TH["fg"],
                     font=("Consolas", 9)).pack(side="left")
            batt_label = tk.Label(frame, text="", bg=TH["card"], fg=TH["green"],
                                  font=("Consolas", 8))
            batt_label.pack(side="left", padx=(4, 0))
            self._device_widgets[dev["name"]] = {"canvas": dot_canvas, "dot": dot_id,
                                                  "batt_label": batt_label}
        self._device_poll_running = True
        threading.Thread(target=self._poll_device_status, daemon=True).start()

        tab_data = [
            ("chat", "CHAT"), ("whimai", "WHIM.AI"), ("smartthings", "SMARTTHINGS"), ("presence", "SYS STATUS"),
            ("xtts", "AVR LAB"), ("voice_engine", "VOICE ENGINE"), ("ss", "LIVE"), ("hearmeout", "TRV CIPHER"),
            ("cursor", "CURSOR"), ("library", "LIBRARY"), ("archive", "ARCHIVE"),
            ("sessions", "SESSIONS"), ("events", "EVENTS/DEBUG"), ("persona", "PERSONA"), ("updates", "UPDATES"), ("settings", "SETTINGS"),
        ]

        tab_bar_outer = tk.Frame(self, bg=TH["bg"])
        tab_bar_outer.pack(fill="x", padx=8, pady=(2, 0))

        mid = (len(tab_data) + 1) // 2
        row1_data = tab_data[:mid]
        row2_data = tab_data[mid:]

        self._tab_buttons = {}
        self._active_tab_key = None

        row1_frame = tk.Frame(tab_bar_outer, bg=TH["bg"])
        row1_frame.pack(fill="x")
        row2_frame = tk.Frame(tab_bar_outer, bg=TH["bg"])
        row2_frame.pack(fill="x", pady=(1, 0))

        for ri, (row_frame, row_data) in enumerate([(row1_frame, row1_data), (row2_frame, row2_data)]):
            for ci, (key, label) in enumerate(row_data):
                row_frame.columnconfigure(ci, weight=1)
                btn = tk.Label(row_frame, text=label, bg=TH["card"], fg=TH["fg2"],
                               font=("Segoe UI", 9), padx=8, pady=5, cursor="hand2",
                               anchor="center", relief="flat",
                               highlightthickness=1, highlightbackground=TH["border"])
                btn.grid(row=0, column=ci, sticky="ew", padx=1)
                btn.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=TH["btn_hover"], fg=TH["fg"]))
                btn.bind("<Leave>", lambda e, b=btn, k=key: b.config(
                    bg=TH["btn"] if k == self._active_tab_key else TH["card"],
                    fg=TH["green"] if k == self._active_tab_key else TH["fg2"]))
                self._tab_buttons[key] = btn

        self._tab_container = tk.Frame(self, bg=TH["bg"])
        self._tab_container.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        self.tabs = {}
        for key, label in tab_data:
            frame = tk.Frame(self._tab_container, bg=TH["bg"])
            self.tabs[key] = frame

        # Keep self.nb as a compatibility shim so existing code referencing it doesn't break
        self.nb = type('_FakeNB', (), {
            'select': lambda s, tab: self._switch_tab(
                next((k for k, v in self.tabs.items() if v is tab), None)),
        })()

        self._switch_tab("chat")

        self.build_chat()
        self.build_whimai()
        self.build_smartthings()
        self.build_sessions()
        self.after(500, self._sess_check_crash_recovery)
        self.build_presence()
        self.build_xtts()
        self.build_voice_engine()
        self.build_cursor()
        self.build_library()
        self.build_hearmeout()
        self.build_archive()
        self.build_ss()
        self.build_events()
        self.build_persona()
        self.build_updates()
        self.build_settings()
        self._apply_saved_settings()
        self._refresh_models()

    def _init_tab_drag(self):
        pass

    def build_chat(self):
        f = self.tabs["chat"]
        self._chat_device_name = "Whim PC"
        self._chat_last_id = 0
        self._chat_poll_url = "http://127.0.0.1:8089/device/chat"
        self._chat_poll_active = False

        header = tk.Frame(f, bg=TH["bg"])
        header.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(header, text="Cross-Device Chat", font=TH["font_title"],
                 fg="#00ff00", bg=TH["bg"]).pack(side="left")
        self._chat_status_lbl = tk.Label(header, text="", font=TH["font_sm"],
                                         fg=TH["fg_dim"], bg=TH["bg"])
        self._chat_status_lbl.pack(side="right")

        wrap = tk.Frame(f, bg=TH["bg"])
        wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.chat_log = self._text_widget(wrap, wrap="word", font=("Segoe UI", 10), state="disabled")
        chat_scroll = self._scrollbar(wrap, command=self.chat_log.yview)
        self.chat_log.configure(yscrollcommand=chat_scroll.set)
        self.chat_log.pack(side="left", fill="both", expand=True)
        chat_scroll.pack(side="right", fill="y")
        self.chat_log.tag_config("sender", foreground="#2fa572", font=("Segoe UI", 10, "bold"))
        self.chat_log.tag_config("time", foreground="#555555", font=("Consolas", 9))
        self.chat_log.tag_config("mine", foreground="#00ddff")
        self.chat_log.tag_config("other", foreground="#dce4ee")
        self.chat_log.tag_config("file", foreground="#2fa572", underline=True)
        self.chat_log.tag_config("system", foreground="#e0a030")

        bottom = tk.Frame(f, bg=TH["bg"])
        bottom.pack(fill="x", padx=12, pady=(0, 10))
        self.chat_entry_var = tk.StringVar()
        self.chat_entry = self._entry(bottom, self.chat_entry_var, font=("Segoe UI", 11))
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=4)
        self.chat_entry.bind("<Return>", lambda e: self.chat_send())
        self._btn(bottom, "Send", self.chat_send).pack(side="left", padx=(0, 4))
        self._btn(bottom, "AI Chat", self._chat_send_to_ai).pack(side="left", padx=(0, 4))
        self._btn(bottom, "Abort", self.chat_abort).pack(side="left")

        self._chat_start_poll()

    def _chat_start_poll(self):
        if self._chat_poll_active:
            return
        self._chat_poll_active = True
        self._chat_status_lbl.config(text="connected", fg=TH["green"])
        self._chat_poll_tick()

    def _chat_poll_tick(self):
        if not self._chat_poll_active:
            return
        threading.Thread(target=self._chat_poll_fetch, daemon=True).start()
        self.after(2000, self._chat_poll_tick)

    def _chat_poll_fetch(self):
        import urllib.request
        try:
            url = f"{self._chat_poll_url}?since={self._chat_last_id}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                msgs = json.loads(resp.read().decode())
            for m in msgs:
                mid = m.get("id", 0)
                if mid > self._chat_last_id:
                    self._chat_last_id = mid
                self.after(0, self._chat_display_msg, m)
            self.after(0, lambda: self._chat_status_lbl.config(text="connected", fg=TH["green"]))
        except Exception:
            self.after(0, lambda: self._chat_status_lbl.config(text="offline", fg=TH["red"]))

    def _chat_display_msg(self, m):
        sender = m.get("sender", "?")
        text = m.get("text", "")
        ts = m.get("time", "")
        msg_type = m.get("type", "text")
        is_mine = sender == self._chat_device_name
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", f"{sender}", "sender")
        self.chat_log.insert("end", f"  {ts}\n", "time")
        if msg_type == "file":
            self.chat_log.insert("end", f"  {text}\n", "file")
        else:
            self.chat_log.insert("end", f"  {text}\n", "mine" if is_mine else "other")
        self.chat_log.see("end")
        self.chat_log.config(state="disabled")

    def chat_send(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")
        threading.Thread(target=self._chat_post_msg, args=(text,), daemon=True).start()

    def _chat_post_msg(self, text):
        import urllib.request
        try:
            payload = json.dumps({"sender": self._chat_device_name, "text": text, "type": "text"}).encode()
            req = urllib.request.Request(self._chat_poll_url, data=payload, method="POST",
                                        headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            self.after(0, lambda: self.append_chat(f"[Send failed: {e}]\n", "#d94040"))

    def _chat_send_to_ai(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self.chat_entry.delete(0, "end")
        req = {"type": "req", "id": new_id("chatSend"), "method": "chat.send",
               "params": {"text": text, "idempotencyKey": uuid.uuid4().hex}}
        outgoing.put(req)
        self.append_chat(f"> [AI] {text}\n", "#00ddff")

    def chat_abort(self):
        outgoing.put({"type": "req", "id": new_id("chatAbort"), "method": "chat.abort", "params": {}})
        self.append_chat("[Abort requested]\n", "#ff5555")

    def append_chat(self, text, color="#d4d4d4"):
        self.chat_log.config(state="normal")
        self.chat_log.tag_config(color, foreground=color)
        self.chat_log.insert("end", text, color)
        self.chat_log.see("end")
        self.chat_log.config(state="disabled")

    def build_whimai(self):
        f = self.tabs["whimai"]
        self._whimai_line_counter = 0
        self._whimai_placeholder_active = True
        self._whimai_chat_history = []
        self._whimai_streaming = False
        self._whimai_model = "llama3.1:8b-16k"
        self._whimai_ollama_url = "http://localhost:11434"

        wrap = tk.Frame(f, bg=TH["bg"])
        wrap.pack(fill="both", expand=True, padx=12, pady=12)

        self.whimai_status_var = tk.StringVar(value="Ready")

        self._whimai_presets = {
            "Default": {"model": "llama3.1:8b-16k", "ctx": 16384, "temp": 0.7, "tools": "all", "system": ""},
            "Creative": {"model": "llama3.1:8b-16k", "ctx": 16384, "temp": 1.2, "tools": "all", "system": "You are a creative writing assistant. Be vivid and expressive."},
            "Code": {"model": "llama3.1:8b-16k", "ctx": 16384, "temp": 0.2, "tools": "code", "system": "You are a concise code assistant. Return code with minimal explanation."},
            "Analyst": {"model": "llama3.1:8b-16k", "ctx": 8192, "temp": 0.3, "tools": "search,calc", "system": "You are a data analyst. Be factual and precise."},
            "Minimal": {"model": "llama3.1:8b-16k", "ctx": 4096, "temp": 0.5, "tools": "none", "system": "Answer in as few words as possible."},
        }
        self._whimai_active_preset = "Default"

        self._whimai_turn_data = []
        self._whimai_total_prompt_tokens = 0
        self._whimai_total_eval_tokens = 0
        self._whimai_dropped_msgs = []
        self._whimai_sys_telemetry = {"cpu": 0.0, "ram_mb": 0, "vram_mb": 0, "gpu_util": 0}
        self._whimai_telemetry_polling = False

        body = tk.Frame(wrap, bg=TH["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # ========== LEFT: AI Chat (swapped to left, 40%) ==========
        left_col = tk.Frame(body, bg=TH["bg"])
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        chat_card = self._card(left_col, "AI CHAT", fg="#888888")
        chat_card.pack(fill="both", expand=True)

        chat_body = tk.Frame(chat_card, bg=TH["card"])
        chat_body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Line-number gutter + chat log side by side
        self.whimai_gutter = tk.Text(chat_body, bg="#1a1a1a", fg="#555555",
                                      font=("Consolas", 10), width=4, bd=0,
                                      highlightthickness=0, state="disabled",
                                      padx=4, pady=4, takefocus=0)
        self.whimai_gutter.pack(side="left", fill="y")

        log_frame = tk.Frame(chat_body, bg=TH["card"])
        log_frame.pack(side="left", fill="both", expand=True)

        self.whimai_log = tk.Text(log_frame, bg=TH["input"], fg=TH["fg"],
                                   font=("Consolas", 10, "bold"), wrap="word",
                                   state="disabled", bd=0, highlightthickness=1,
                                   highlightbackground=TH["border"],
                                   highlightcolor=TH["btn"], padx=6, pady=4)
        ai_scroll = self._scrollbar(log_frame, command=self._whimai_scroll_both)
        self.whimai_log.configure(yscrollcommand=self._whimai_sync_scroll)
        self.whimai_log.pack(side="left", fill="both", expand=True)
        ai_scroll.pack(side="right", fill="y")

        self.whimai_log.tag_config("ai", foreground="#e08030", font=("Consolas", 10, "bold"))
        self.whimai_log.tag_config("user", foreground="#40e0d0", font=("Consolas", 10, "bold"))

        afford_row = tk.Frame(left_col, bg=TH["bg"])
        afford_row.pack(fill="x", pady=(4, 0))
        for lbl, cmd in [("Edit Last", self._whimai_edit_last),
                         ("Regen", self._whimai_regenerate),
                         ("Copy MD", self._whimai_copy_md),
                         ("Send to Page", self._whimai_send_to_page),
                         ("Make Task", self._whimai_make_task)]:
            self._btn(afford_row, lbl, cmd).pack(side="left", padx=2)
        tk.Label(afford_row, textvariable=self.whimai_status_var, bg=TH["bg"],
                 fg=TH["green"], font=("Consolas", 9)).pack(side="right", padx=4)

        # -- Live token / context meter --
        meter_frame = tk.Frame(left_col, bg=TH["card"], highlightthickness=1,
                               highlightbackground=TH["border_hi"])
        meter_frame.pack(fill="x", pady=(4, 0))

        meter_top = tk.Frame(meter_frame, bg=TH["card"])
        meter_top.pack(fill="x", padx=6, pady=(4, 0))
        tk.Label(meter_top, text="CONTEXT", bg=TH["card"], fg="#888888",
                 font=("Consolas", 8, "bold")).pack(side="left")
        self._whimai_ctx_lbl = tk.Label(meter_top, text="0 / 16384 tokens",
                                         bg=TH["card"], fg=TH["fg"],
                                         font=("Consolas", 8))
        self._whimai_ctx_lbl.pack(side="left", padx=(6, 0))
        self._whimai_dropped_lbl = tk.Label(meter_top, text="", bg=TH["card"],
                                             fg=TH["yellow"], font=("Consolas", 8))
        self._whimai_dropped_lbl.pack(side="right")

        self._whimai_ctx_canvas = tk.Canvas(meter_frame, bg=TH["input"],
                                             height=10, highlightthickness=0, bd=0)
        self._whimai_ctx_canvas.pack(fill="x", padx=6, pady=(2, 2))

        meter_per = tk.Frame(meter_frame, bg=TH["card"])
        meter_per.pack(fill="x", padx=6, pady=(0, 4))
        tk.Label(meter_per, text="LAST TURN", bg=TH["card"], fg="#555555",
                 font=("Consolas", 7, "bold")).pack(side="left")
        self._whimai_turn_prompt_lbl = tk.Label(meter_per, text="prompt: --",
                                                 bg=TH["card"], fg=TH["fg2"],
                                                 font=("Consolas", 7))
        self._whimai_turn_prompt_lbl.pack(side="left", padx=(6, 0))
        self._whimai_turn_eval_lbl = tk.Label(meter_per, text="eval: --",
                                               bg=TH["card"], fg=TH["fg2"],
                                               font=("Consolas", 7))
        self._whimai_turn_eval_lbl.pack(side="left", padx=(6, 0))
        self._whimai_turn_tps_lbl = tk.Label(meter_per, text="tok/s: --",
                                              bg=TH["card"], fg=TH["fg2"],
                                              font=("Consolas", 7))
        self._whimai_turn_tps_lbl.pack(side="left", padx=(6, 0))

        # Multi-line input (3 visible lines, up to 200)
        input_frame = tk.Frame(left_col, bg=TH["bg"])
        input_frame.pack(fill="x", pady=(8, 0))

        self.whimai_entry = tk.Text(input_frame, bg=TH["input"], fg="#e08030",
                                     font=("Consolas", 11), height=3, wrap="word",
                                     bd=0, highlightthickness=1, insertbackground=TH["fg"],
                                     highlightbackground=TH["border"],
                                     highlightcolor=TH["btn"], padx=6, pady=4,
                                     undo=True)
        self.whimai_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._btn(input_frame, "Send", self._whimai_send).pack(side="left", anchor="s")

        # Placeholder text
        self.whimai_entry.insert("1.0", "Upto 200 lines input")
        self.whimai_entry.config(fg="#888888")
        self.whimai_entry.bind("<FocusIn>", self._whimai_clear_placeholder)
        self.whimai_entry.bind("<FocusOut>", self._whimai_restore_placeholder)
        self.whimai_entry.bind("<Return>", self._whimai_on_enter)

        # -- Capture buttons --
        cap_frame = tk.Frame(left_col, bg=TH["card"], highlightthickness=1,
                             highlightbackground=TH["border_hi"])
        cap_frame.pack(fill="x", pady=(4, 0))
        cap_hdr = tk.Frame(cap_frame, bg=TH["card"])
        cap_hdr.pack(fill="x", padx=6, pady=(4, 2))
        tk.Label(cap_hdr, text="CAPTURE", bg=TH["card"], fg="#888888",
                 font=("Consolas", 8, "bold")).pack(side="left")

        cap_row1 = tk.Frame(cap_frame, bg=TH["card"])
        cap_row1.pack(fill="x", padx=6, pady=(0, 2))
        for lbl, cmd in [("Quick Note", self._whimai_capture_note),
                         ("Journal Entry", self._whimai_capture_journal),
                         ("Action Items", self._whimai_capture_actions)]:
            self._btn(cap_row1, lbl, cmd).pack(side="left", padx=2)

        cap_row2 = tk.Frame(cap_frame, bg=TH["card"])
        cap_row2.pack(fill="x", padx=6, pady=(0, 4))
        for lbl, cmd in [("Export ODT", self._whimai_export_odt),
                         ("Save to TableReads", self._whimai_save_audio_tr)]:
            self._btn(cap_row2, lbl, cmd).pack(side="left", padx=2)

        # -- Drop zone --
        self._whimai_drop_zone = tk.Label(
            left_col, text="Drop files here  (logs / screenshots / audio)\nor paste from clipboard",
            bg="#1a1a1a", fg="#555555", font=("Consolas", 9),
            relief="groove", bd=1, height=3, cursor="hand2",
            highlightthickness=1, highlightbackground=TH["border"])
        self._whimai_drop_zone.pack(fill="x", pady=(4, 0))
        self._whimai_drop_zone.bind("<Button-1>", lambda e: self._whimai_drop_browse())
        self._whimai_drop_zone.bind("<Button-3>", lambda e: self._whimai_drop_paste())
        self._whimai_drop_zone.bind("<Enter>",
            lambda e: self._whimai_drop_zone.config(bg="#222222", fg="#888888"))
        self._whimai_drop_zone.bind("<Leave>",
            lambda e: self._whimai_drop_zone.config(bg="#1a1a1a", fg="#555555"))

        # ========== RIGHT: Presets + Observability + Tools & Commands ==========
        right_col = tk.Frame(body, bg=TH["bg"])
        right_col.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right_col.rowconfigure(1, weight=1)
        right_col.rowconfigure(2, weight=0)
        right_col.rowconfigure(3, weight=2)
        right_col.columnconfigure(0, weight=1)

        # -- Model / Session Presets --
        presets_card = self._card(right_col, "PRESETS", fg="#888888")
        presets_card.grid(row=0, column=0, sticky="new", pady=(0, 4))

        self.whimai_model_var = tk.StringVar(value=self._whimai_model)

        preset_sel = tk.Frame(presets_card, bg=TH["card"])
        preset_sel.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(preset_sel, text="PROFILE:", bg=TH["card"], fg="#888888",
                 font=("Consolas", 9, "bold")).pack(side="left", padx=4)
        self._whimai_preset_var = tk.StringVar(value=self._whimai_active_preset)
        preset_combo = ttk.Combobox(preset_sel, textvariable=self._whimai_preset_var,
                                     values=list(self._whimai_presets.keys()), width=14,
                                     state="readonly")
        preset_combo.pack(side="left", padx=4)
        preset_combo.bind("<<ComboboxSelected>>", lambda e: self._whimai_apply_preset())

        info_frame = tk.Frame(presets_card, bg=TH["card"])
        info_frame.pack(fill="x", padx=10, pady=(0, 6))

        r1 = tk.Frame(info_frame, bg=TH["card"])
        r1.pack(fill="x", pady=1)
        tk.Label(r1, text="MODEL:", bg=TH["card"], fg="#555555",
                 font=("Consolas", 8, "bold"), width=8, anchor="w").pack(side="left")
        self._preset_model_lbl = tk.Label(r1, text=self._whimai_model, bg=TH["card"],
                                           fg=TH["fg"], font=("Consolas", 9))
        self._preset_model_lbl.pack(side="left")

        r2 = tk.Frame(info_frame, bg=TH["card"])
        r2.pack(fill="x", pady=1)
        tk.Label(r2, text="CTX:", bg=TH["card"], fg="#555555",
                 font=("Consolas", 8, "bold"), width=8, anchor="w").pack(side="left")
        self._preset_ctx_lbl = tk.Label(r2, text="16384", bg=TH["card"],
                                         fg=TH["fg"], font=("Consolas", 9))
        self._preset_ctx_lbl.pack(side="left")
        tk.Label(r2, text="  TEMP:", bg=TH["card"], fg="#555555",
                 font=("Consolas", 8, "bold")).pack(side="left", padx=(8, 0))
        self._preset_temp_lbl = tk.Label(r2, text="0.7", bg=TH["card"],
                                          fg=TH["fg"], font=("Consolas", 9))
        self._preset_temp_lbl.pack(side="left")

        r3 = tk.Frame(info_frame, bg=TH["card"])
        r3.pack(fill="x", pady=1)
        tk.Label(r3, text="TOOLS:", bg=TH["card"], fg="#555555",
                 font=("Consolas", 8, "bold"), width=8, anchor="w").pack(side="left")
        self._preset_tools_lbl = tk.Label(r3, text="all", bg=TH["card"],
                                           fg=TH["green"], font=("Consolas", 9))
        self._preset_tools_lbl.pack(side="left")

        r4 = tk.Frame(info_frame, bg=TH["card"])
        r4.pack(fill="x", pady=(1, 4))
        tk.Label(r4, text="SYSTEM:", bg=TH["card"], fg="#555555",
                 font=("Consolas", 8, "bold"), width=8, anchor="w").pack(side="left")
        self._preset_sys_lbl = tk.Label(r4, text="(none)", bg=TH["card"],
                                         fg=TH["fg2"], font=("Consolas", 8),
                                         wraplength=220, justify="left", anchor="w")
        self._preset_sys_lbl.pack(side="left", fill="x", expand=True)

        # -- Observability panel --
        obs_card = self._card(right_col, "OBSERVABILITY", fg="#888888")
        obs_card.grid(row=1, column=0, sticky="nsew", pady=(0, 4))

        obs_inner = tk.Frame(obs_card, bg=TH["card"])
        obs_inner.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        obs_canvas = tk.Canvas(obs_inner, bg=TH["input"], highlightthickness=0, bd=0)
        obs_sb = self._scrollbar(obs_inner, command=obs_canvas.yview)
        self._obs_frame = tk.Frame(obs_canvas, bg=TH["input"])
        self._obs_frame.bind("<Configure>",
            lambda e: obs_canvas.configure(scrollregion=obs_canvas.bbox("all")))
        obs_canvas.create_window((0, 0), window=self._obs_frame, anchor="nw")
        obs_canvas.configure(yscrollcommand=obs_sb.set)
        obs_canvas.pack(side="left", fill="both", expand=True)
        obs_sb.pack(side="right", fill="y")
        def _obs_scroll(event):
            obs_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        obs_canvas.bind("<Button-4>", _obs_scroll)
        obs_canvas.bind("<Button-5>", _obs_scroll)
        self._obs_frame.bind("<Button-4>", _obs_scroll)
        self._obs_frame.bind("<Button-5>", _obs_scroll)
        self._obs_canvas = obs_canvas

        # Cost / Perf telemetry row (always visible)
        perf_hdr = tk.Frame(self._obs_frame, bg=TH["input"])
        perf_hdr.pack(fill="x", padx=4, pady=(6, 2))
        tk.Label(perf_hdr, text="PERF / TELEMETRY", bg=TH["input"], fg=TH["blue_text"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        perf_grid = tk.Frame(self._obs_frame, bg=TH["input"])
        perf_grid.pack(fill="x", padx=4, pady=(0, 4))

        metrics = [
            ("tok/s:", "_obs_tps", "--"),
            ("latency:", "_obs_latency", "--"),
            ("prompt eval:", "_obs_prompt_lat", "--"),
            ("GPU VRAM:", "_obs_vram", "--"),
            ("GPU util:", "_obs_gpu", "--"),
            ("CPU:", "_obs_cpu", "--"),
            ("RAM:", "_obs_ram", "--"),
        ]
        for i, (label, attr, default) in enumerate(metrics):
            r, c = divmod(i, 2)
            cell = tk.Frame(perf_grid, bg=TH["input"])
            cell.grid(row=r, column=c, sticky="w", padx=(0, 12), pady=1)
            tk.Label(cell, text=label, bg=TH["input"], fg="#555555",
                     font=("Consolas", 8, "bold"), anchor="w").pack(side="left")
            lbl = tk.Label(cell, text=default, bg=TH["input"], fg=TH["fg"],
                           font=("Consolas", 8))
            lbl.pack(side="left", padx=(4, 0))
            setattr(self, attr, lbl)
        perf_grid.columnconfigure(0, weight=1)
        perf_grid.columnconfigure(1, weight=1)

        tk.Frame(self._obs_frame, bg=TH["border_hi"], height=1).pack(
            fill="x", padx=4, pady=(4, 4))

        # Tool trace section header
        trace_hdr = tk.Frame(self._obs_frame, bg=TH["input"])
        trace_hdr.pack(fill="x", padx=4, pady=(0, 2))
        tk.Label(trace_hdr, text="TOOL TRACE (per turn)", bg=TH["input"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")

        # Container for turn-by-turn trace entries (collapsed by default)
        self._obs_trace_container = tk.Frame(self._obs_frame, bg=TH["input"])
        self._obs_trace_container.pack(fill="x", padx=4, pady=(0, 4))

        self._whimai_start_telemetry_poll()

        # -- Output Templates --
        tpl_card = self._card(right_col, "OUTPUT TEMPLATES", fg="#888888")
        tpl_card.grid(row=2, column=0, sticky="new", pady=(0, 4))

        self._whimai_templates = {
            "Weekly Recap": (
                "## Weekly Recap  —  {date}\n\n"
                "### Accomplishments\n- \n\n"
                "### In Progress\n- \n\n"
                "### Blockers\n- \n\n"
                "### Goals for Next Week\n- \n"
            ),
            "Meeting Summary": (
                "## Meeting Summary  —  {date}\n\n"
                "**Attendees:** \n\n"
                "### Agenda\n1. \n\n"
                "### Discussion\n- \n\n"
                "### Decisions\n- \n\n"
                "### Action Items\n- [ ] \n"
            ),
            "Script Draft": (
                "# SCRIPT DRAFT  —  {date}\n\n"
                "**Working Title:** \n"
                "**Logline:** \n\n"
                "---\n\n"
                "## ACT I\n\n"
                "INT. LOCATION — TIME\n\n"
                "Description.\n\n"
                "CHARACTER\n"
                "Dialogue.\n\n"
                "## ACT II\n\n\n"
                "## ACT III\n\n"
            ),
            "Debug Report": (
                "## Debug Report  —  {date}\n\n"
                "**Component:** \n"
                "**Severity:** \n"
                "**Repro Steps:**\n1. \n\n"
                "**Expected:** \n"
                "**Actual:** \n\n"
                "### Logs\n```\n\n```\n\n"
                "### Root Cause\n\n\n"
                "### Fix\n\n"
            ),
        }

        tpl_inner = tk.Frame(tpl_card, bg=TH["card"])
        tpl_inner.pack(fill="x", padx=10, pady=(0, 8))

        tpl_row = tk.Frame(tpl_inner, bg=TH["card"])
        tpl_row.pack(fill="x")
        for name in self._whimai_templates:
            b = self._btn(tpl_row, name,
                          lambda n=name: self._whimai_apply_template(n))
            b.pack(side="left", padx=2, pady=2)

        # -- Tools & Commands (scrollable, fills rest of right) --
        tools_card = self._card(right_col, "TOOLS & COMMANDS", fg="#888888")
        tools_card.grid(row=3, column=0, sticky="nsew")

        tools_inner = tk.Frame(tools_card, bg=TH["card"])
        tools_inner.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tools_canvas = tk.Canvas(tools_inner, bg=TH["input"], highlightthickness=0, bd=0)
        tools_sb = self._scrollbar(tools_inner, command=tools_canvas.yview)
        tools_frame = tk.Frame(tools_canvas, bg=TH["input"])
        tools_frame.bind("<Configure>",
            lambda e: tools_canvas.configure(scrollregion=tools_canvas.bbox("all")))
        tools_canvas.create_window((0, 0), window=tools_frame, anchor="nw")
        tools_canvas.configure(yscrollcommand=tools_sb.set)
        tools_canvas.pack(side="left", fill="both", expand=True)
        tools_sb.pack(side="right", fill="y")

        def _tools_scroll(event):
            tools_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")
        tools_canvas.bind("<Button-4>", _tools_scroll)
        tools_canvas.bind("<Button-5>", _tools_scroll)
        tools_frame.bind("<Button-4>", _tools_scroll)
        tools_frame.bind("<Button-5>", _tools_scroll)

        BLOB = "\u2B24"
        commands = [
            ("QUICK PROMPTS", None),
            ("droid", "Launch droid agent"),
            ("note", "Quick capture note"),
            ("calc", "Inline calculator"),
            ("search", "Semantic search"),
            ("summarize", "Summarize selection"),
            ("rewrite", "Rewrite / rephrase"),
            ("translate", "Translate text"),
            ("explain", "Explain like I'm 5"),
            ("", None),
            ("OPENCLAW CORE", None),
            ("connect", "WS gateway connect"),
            ("disconnect", "Drop gateway session"),
            ("heartbeat", "Ping gateway"),
            ("status", "System status check"),
            ("sessions", "List active sessions"),
            ("presence", "Who's online"),
            ("approve", "Approve pending action"),
            ("deny", "Deny pending action"),
            ("", None),
            ("CHAT OPS", None),
            ("send", "Send chat message"),
            ("abort", "Abort current task"),
            ("retry", "Retry last request"),
            ("history", "Show chat history"),
            ("clear", "Clear chat log"),
            ("export", "Export conversation"),
            ("", None),
            ("VOICE & MEDIA", None),
            ("record", "Start voice capture"),
            ("transcribe", "Whisper transcribe"),
            ("tts", "Text-to-speech (XTTS)"),
            ("playback", "Play last audio"),
            ("scrub", "Scrub & clean audio"),
            ("", None),
            ("ARCHIVE & FILES", None),
            ("archive.new", "New document"),
            ("archive.save", "Save document"),
            ("archive.open", "Open from archive"),
            ("journal", "Open journal dir"),
            ("ingest", "Start ingest server"),
        ]

        for cmd, desc in commands:
            if cmd == "":
                tk.Frame(tools_frame, bg=TH["input"], height=6).pack(fill="x")
                continue
            if desc is None:
                tk.Label(tools_frame, text=cmd, bg=TH["input"], fg=TH["blue_text"],
                         font=("Segoe UI", 10, "bold"), anchor="w").pack(
                    fill="x", padx=6, pady=(8, 2))
                tk.Frame(tools_frame, bg=TH["border_hi"], height=1).pack(
                    fill="x", padx=6, pady=(0, 4))
                continue
            row = tk.Frame(tools_frame, bg=TH["input"])
            row.pack(fill="x", padx=6, pady=1)
            tk.Label(row, text=BLOB, bg=TH["input"], fg="#555555",
                     font=("Segoe UI", 6)).pack(side="left", padx=(4, 6), pady=2)
            cmd_lbl = tk.Label(row, text=cmd, bg=TH["input"], fg="#00ff00",
                               font=("Consolas", 10, "bold"), cursor="hand2")
            cmd_lbl.pack(side="left")
            tk.Label(row, text=f"  {desc}", bg=TH["input"], fg=TH["fg2"],
                     font=("Segoe UI", 9)).pack(side="left")
            cmd_lbl.bind("<Button-1>",
                lambda e, c=cmd: self._whimai_insert_cmd(c))
            cmd_lbl.bind("<Enter>", lambda e, w=cmd_lbl: w.config(fg="#00dd00"))
            cmd_lbl.bind("<Leave>", lambda e, w=cmd_lbl: w.config(fg="#00ff00"))
            for child in row.winfo_children():
                child.bind("<Button-4>", _tools_scroll)
                child.bind("<Button-5>", _tools_scroll)

    def _whimai_scroll_both(self, *args):
        self.whimai_log.yview(*args)
        self.whimai_gutter.yview(*args)

    def _whimai_sync_scroll(self, *args):
        self.whimai_gutter.yview_moveto(args[0])

    def _whimai_update_gutter(self):
        self.whimai_gutter.config(state="normal")
        self.whimai_gutter.delete("1.0", "end")
        line_count = int(self.whimai_log.index("end-1c").split(".")[0])
        for i in range(1, line_count + 1):
            self.whimai_gutter.insert("end", f"{i}\n")
        self.whimai_gutter.config(state="disabled")

    def _whimai_clear_placeholder(self, event=None):
        if self._whimai_placeholder_active:
            self.whimai_entry.delete("1.0", "end")
            self.whimai_entry.config(fg="#40e0d0")
            self._whimai_placeholder_active = False

    def _whimai_restore_placeholder(self, event=None):
        content = self.whimai_entry.get("1.0", "end-1c").strip()
        if not content:
            self._whimai_placeholder_active = True
            self.whimai_entry.config(fg="#888888")
            self.whimai_entry.insert("1.0", "Upto 200 lines input")

    def _whimai_on_enter(self, event):
        lines = self.whimai_entry.get("1.0", "end-1c").count("\n") + 1
        if lines >= 200:
            return "break"
        if not (event.state & 0x1):
            self._whimai_send()
            return "break"

    def _whimai_insert_cmd(self, cmd):
        if self._whimai_placeholder_active:
            self._whimai_clear_placeholder()
        self.whimai_entry.delete("1.0", "end")
        self.whimai_entry.insert("1.0", cmd)
        self.whimai_entry.config(fg="#40e0d0")
        self.whimai_entry.focus_set()

    def _whimai_send(self):
        if self._whimai_placeholder_active:
            return
        if self._whimai_streaming:
            return
        text = self.whimai_entry.get("1.0", "end-1c").strip()
        if not text:
            return
        self.whimai_entry.delete("1.0", "end")
        self._whimai_placeholder_active = False
        self.whimai_entry.config(fg="#40e0d0")
        self._whimai_append(f"> {text}\n", "user")
        self._whimai_chat_history.append({"role": "user", "content": text})
        self._whimai_update_ctx_meter()
        self._whimai_streaming = True
        self.whimai_status_var.set("Thinking...")
        threading.Thread(target=self._whimai_ollama_stream, daemon=True).start()

    def _whimai_ollama_stream(self):
        import urllib.request
        import time as _time
        turn = {
            "model": self._whimai_model,
            "prompt_tokens": 0, "eval_tokens": 0,
            "prompt_eval_ms": 0, "eval_ms": 0, "total_ms": 0,
            "tokens_per_sec": 0, "failed": False, "error": "",
            "dropped_count": 0,
        }
        wall_start = _time.time()
        try:
            self.after(0, self._whimai_check_context_overflow)
            turn["dropped_count"] = len(self._whimai_dropped_msgs)
            preset = self._whimai_presets.get(self._whimai_active_preset, {})
            temperature = preset.get("temp", 0.7)
            num_ctx = preset.get("ctx", 16384)
            sys_prompt = preset.get("system", "")
            messages = list(self._whimai_chat_history)
            if sys_prompt and (not messages or messages[0].get("role") != "system"):
                messages.insert(0, {"role": "system", "content": sys_prompt})
            payload = json.dumps({
                "model": self._whimai_model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": temperature, "num_ctx": num_ctx}
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{self._whimai_ollama_url}/api/chat",
                data=payload, method="POST",
                headers={"Content-Type": "application/json"})
            self.after(0, lambda: self._whimai_append("", "ai"))
            full_response = []
            final_data = {}
            with urllib.request.urlopen(req, timeout=120) as resp:
                buf = b""
                while True:
                    chunk = resp.read(1)
                    if not chunk:
                        break
                    buf += chunk
                    if chunk == b"\n" and buf.strip():
                        try:
                            data = json.loads(buf.strip())
                            token = data.get("message", {}).get("content", "")
                            if token:
                                full_response.append(token)
                                self.after(0, lambda t=token: self._whimai_append(t, "ai"))
                            if data.get("done", False):
                                final_data = data
                                break
                        except (json.JSONDecodeError, ValueError):
                            pass
                        buf = b""
            assistant_text = "".join(full_response)
            self._whimai_chat_history.append({"role": "assistant", "content": assistant_text})
            wall_ms = (_time.time() - wall_start) * 1000.0
            turn["prompt_tokens"] = final_data.get("prompt_eval_count", 0)
            turn["eval_tokens"] = final_data.get("eval_count", 0)
            p_dur = final_data.get("prompt_eval_duration", 0)
            e_dur = final_data.get("eval_duration", 0)
            turn["prompt_eval_ms"] = p_dur / 1e6 if p_dur else 0
            turn["eval_ms"] = e_dur / 1e6 if e_dur else 0
            turn["total_ms"] = wall_ms
            if turn["eval_ms"] > 0 and turn["eval_tokens"] > 0:
                turn["tokens_per_sec"] = turn["eval_tokens"] / (turn["eval_ms"] / 1000.0)
            self._whimai_total_prompt_tokens += turn["prompt_tokens"]
            self._whimai_total_eval_tokens += turn["eval_tokens"]
            self._whimai_turn_data.append(turn)
            turn_idx = len(self._whimai_turn_data)
            self.after(0, lambda: self._whimai_append("\n", "ai"))
            self.after(0, lambda: self.whimai_status_var.set("Ready"))
            self.after(0, lambda: self._whimai_update_turn_labels(turn))
            self.after(0, lambda: self._whimai_update_perf_panel(turn))
            self.after(0, lambda: self._whimai_add_trace_entry(turn_idx, turn))
            self.after(0, self._whimai_update_ctx_meter)
        except Exception as e:
            wall_ms = (_time.time() - wall_start) * 1000.0
            turn["failed"] = True
            turn["error"] = str(e)
            turn["total_ms"] = wall_ms
            self._whimai_turn_data.append(turn)
            turn_idx = len(self._whimai_turn_data)
            self.after(0, lambda: self._whimai_append(f"\n[Error: {e}]\n", "ai"))
            self.after(0, lambda: self.whimai_status_var.set("Error"))
            self.after(0, lambda: self._whimai_update_turn_labels(turn))
            self.after(0, lambda: self._whimai_update_perf_panel(turn))
            self.after(0, lambda: self._whimai_add_trace_entry(turn_idx, turn))
            self.after(0, self._whimai_update_ctx_meter)
        finally:
            self._whimai_streaming = False

    def _whimai_append(self, text, tag="ai"):
        self.whimai_log.config(state="normal")
        self.whimai_log.insert("end", text, tag)
        self.whimai_log.see("end")
        self.whimai_log.config(state="disabled")
        self._whimai_update_gutter()

    def _whimai_defrag(self):
        pass

    def _whimai_apply_preset(self):
        name = self._whimai_preset_var.get()
        p = self._whimai_presets.get(name)
        if not p:
            return
        self._whimai_active_preset = name
        self._whimai_model = p["model"]
        self.whimai_model_var.set(p["model"])
        self._global_model_var.set(p["model"])
        self._preset_model_lbl.config(text=p["model"])
        self._preset_ctx_lbl.config(text=str(p["ctx"]))
        self._preset_temp_lbl.config(text=str(p["temp"]))
        self._preset_tools_lbl.config(text=p["tools"])
        sys_text = p["system"] if p["system"] else "(none)"
        self._preset_sys_lbl.config(text=sys_text, fg=TH["fg"] if p["system"] else TH["fg2"])
        self.whimai_status_var.set(f"Preset: {name}")

    def _whimai_edit_last(self):
        for msg in reversed(self._whimai_chat_history):
            if msg["role"] == "user":
                if self._whimai_placeholder_active:
                    self._whimai_clear_placeholder()
                self.whimai_entry.delete("1.0", "end")
                self.whimai_entry.insert("1.0", msg["content"])
                self.whimai_entry.config(fg="#40e0d0")
                self.whimai_entry.focus_set()
                return

    def _whimai_regenerate(self):
        if self._whimai_streaming:
            return
        last_user = None
        for msg in reversed(self._whimai_chat_history):
            if msg["role"] == "user":
                last_user = msg["content"]
                break
        if not last_user:
            return
        if (self._whimai_chat_history and
                self._whimai_chat_history[-1]["role"] == "assistant"):
            self._whimai_chat_history.pop()
        self._whimai_append(f"> (regen) {last_user}\n", "user")
        self._whimai_streaming = True
        self.whimai_status_var.set("Regenerating...")
        threading.Thread(target=self._whimai_ollama_stream, daemon=True).start()

    def _whimai_copy_md(self):
        lines = []
        for msg in self._whimai_chat_history:
            prefix = "**You:**" if msg["role"] == "user" else "**Whim.ai:**"
            lines.append(f"{prefix} {msg['content']}")
        md = "\n\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(md)
        self.whimai_status_var.set("Copied as Markdown")

    def _whimai_send_to_page(self):
        if not self._whimai_chat_history:
            return
        last = self._whimai_chat_history[-1].get("content", "")
        outgoing.put({
            "type": "req", "id": new_id("sendToPage"),
            "method": "page.append",
            "params": {"text": last, "source": "whimai"}
        })
        self.whimai_status_var.set("Sent to page")

    def _whimai_make_task(self):
        if not self._whimai_chat_history:
            return
        last = self._whimai_chat_history[-1].get("content", "")
        summary = last[:120].replace("\n", " ").strip()
        if len(last) > 120:
            summary += "..."
        outgoing.put({
            "type": "req", "id": new_id("makeTask"),
            "method": "tasks.create",
            "params": {"title": summary, "body": last, "source": "whimai"}
        })
        self.whimai_status_var.set("Task created")

    # ---------- Observability helpers ----------

    def _whimai_estimate_tokens(self, text):
        return max(1, int(len(text) / 3.5))

    def _whimai_update_ctx_meter(self):
        preset = self._whimai_presets.get(self._whimai_active_preset, {})
        ctx_limit = preset.get("ctx", 16384)
        total_tokens = 0
        for msg in self._whimai_chat_history:
            total_tokens += self._whimai_estimate_tokens(msg.get("content", ""))
        sys_prompt = preset.get("system", "")
        if sys_prompt:
            total_tokens += self._whimai_estimate_tokens(sys_prompt)
        pct = min(1.0, total_tokens / max(ctx_limit, 1))
        self._whimai_ctx_lbl.config(text=f"{total_tokens} / {ctx_limit} tokens")
        c = self._whimai_ctx_canvas
        c.delete("all")
        c.update_idletasks()
        w = max(c.winfo_width(), 10)
        h = max(c.winfo_height(), 6)
        if pct < 0.7:
            color = TH["green"]
        elif pct < 0.9:
            color = TH["yellow"]
        else:
            color = TH["red"]
        c.create_rectangle(0, 0, int(w * pct), h, fill=color, outline="")
        if self._whimai_dropped_msgs:
            n = len(self._whimai_dropped_msgs)
            self._whimai_dropped_lbl.config(
                text=f"{n} msg{'s' if n != 1 else ''} dropped")
        else:
            self._whimai_dropped_lbl.config(text="")

    def _whimai_check_context_overflow(self):
        preset = self._whimai_presets.get(self._whimai_active_preset, {})
        ctx_limit = preset.get("ctx", 16384)
        total = 0
        for msg in self._whimai_chat_history:
            total += self._whimai_estimate_tokens(msg.get("content", ""))
        while total > ctx_limit * 0.95 and len(self._whimai_chat_history) > 2:
            dropped = self._whimai_chat_history.pop(0)
            drop_toks = self._whimai_estimate_tokens(dropped.get("content", ""))
            total -= drop_toks
            self._whimai_dropped_msgs.append({
                "role": dropped["role"],
                "tokens": drop_toks,
                "preview": dropped.get("content", "")[:80]
            })

    def _whimai_update_turn_labels(self, turn):
        pt = turn.get("prompt_tokens", 0)
        et = turn.get("eval_tokens", 0)
        tps = turn.get("tokens_per_sec", 0)
        self._whimai_turn_prompt_lbl.config(text=f"prompt: {pt}")
        self._whimai_turn_eval_lbl.config(text=f"eval: {et}")
        self._whimai_turn_tps_lbl.config(
            text=f"tok/s: {tps:.1f}" if tps else "tok/s: --")

    def _whimai_update_perf_panel(self, turn):
        tps = turn.get("tokens_per_sec", 0)
        self._obs_tps.config(text=f"{tps:.1f}" if tps else "--")
        lat = turn.get("total_ms", 0)
        self._obs_latency.config(text=f"{lat:.0f}ms" if lat else "--")
        plat = turn.get("prompt_eval_ms", 0)
        self._obs_prompt_lat.config(text=f"{plat:.0f}ms" if plat else "--")

    def _whimai_add_trace_entry(self, turn_index, turn):
        container = self._obs_trace_container
        entry_frame = tk.Frame(container, bg=TH["input"])
        entry_frame.pack(fill="x", pady=(0, 2))

        header = tk.Frame(entry_frame, bg="#2a2a2a")
        header.pack(fill="x")

        tps = turn.get("tokens_per_sec", 0)
        pt = turn.get("prompt_tokens", 0)
        et = turn.get("eval_tokens", 0)
        elapsed_ms = turn.get("total_ms", 0)
        failed = turn.get("failed", False)

        status_color = TH["red"] if failed else TH["green"]
        status_char = "x" if failed else "o"
        hdr_text = (f"  Turn {turn_index}  |  "
                    f"prompt:{pt}  eval:{et}  "
                    f"{elapsed_ms:.0f}ms  {tps:.1f}t/s")

        tk.Label(header, text=status_char, bg="#2a2a2a", fg=status_color,
                 font=("Consolas", 9, "bold")).pack(side="left", padx=(4, 0))
        hdr_label = tk.Label(header, text=hdr_text, bg="#2a2a2a", fg=TH["fg"],
                             font=("Consolas", 8), anchor="w", cursor="hand2")
        hdr_label.pack(side="left", fill="x", expand=True)

        toggle_lbl = tk.Label(header, text="[+]", bg="#2a2a2a", fg=TH["fg2"],
                              font=("Consolas", 8), cursor="hand2")
        toggle_lbl.pack(side="right", padx=(0, 4))

        detail = tk.Frame(entry_frame, bg=TH["input"])
        detail._visible = False

        detail_text = tk.Text(detail, bg=TH["input"], fg=TH["fg2"],
                              font=("Consolas", 7), height=6, wrap="word", bd=0,
                              highlightthickness=0, state="disabled")
        detail_text.pack(fill="x", padx=4, pady=2)

        lines = []
        lines.append(f"Model: {turn.get('model', self._whimai_model)}")
        lines.append(f"Prompt tokens: {pt}")
        lines.append(f"Eval tokens:   {et}")
        lines.append(f"Prompt eval:   {turn.get('prompt_eval_ms', 0):.0f}ms")
        lines.append(f"Token gen:     {turn.get('eval_ms', 0):.0f}ms")
        lines.append(f"Total time:    {elapsed_ms:.0f}ms")
        lines.append(f"Tokens/sec:    {tps:.1f}")
        if failed:
            lines.append(f"ERROR: {turn.get('error', 'unknown')}")
        if turn.get("dropped_count", 0):
            lines.append(f"Context dropped: {turn['dropped_count']} messages")
        snap = self._whimai_sys_telemetry
        lines.append(f"CPU: {snap['cpu']:.0f}%  RAM: {snap['ram_mb']}MB  "
                      f"VRAM: {snap['vram_mb']}MB  GPU: {snap['gpu_util']}%")

        detail_text.config(state="normal")
        detail_text.insert("1.0", "\n".join(lines))
        detail_text.config(state="disabled")

        def toggle(e=None):
            if detail._visible:
                detail.pack_forget()
                toggle_lbl.config(text="[+]")
                detail._visible = False
            else:
                detail.pack(fill="x", after=header)
                toggle_lbl.config(text="[-]")
                detail._visible = True
        hdr_label.bind("<Button-1>", toggle)
        toggle_lbl.bind("<Button-1>", toggle)
        header.bind("<Button-1>", toggle)

        for child in entry_frame.winfo_children():
            child.bind("<Button-4>", lambda e: self._obs_canvas.yview_scroll(-1, "units"))
            child.bind("<Button-5>", lambda e: self._obs_canvas.yview_scroll(1, "units"))

    def _whimai_update_sys_telemetry(self):
        try:
            import subprocess as _sp
            snap = dict(self._whimai_sys_telemetry)
            try:
                import os as _os
                loadavg = _os.getloadavg()
                snap["cpu"] = loadavg[0] * 100.0 / max(_os.cpu_count() or 1, 1)
            except Exception:
                snap["cpu"] = 0.0
            try:
                with open("/proc/meminfo", "r") as mf:
                    lines = mf.readlines()
                mem = {}
                for ln in lines[:5]:
                    parts = ln.split()
                    if len(parts) >= 2:
                        mem[parts[0].rstrip(":")] = int(parts[1])
                total_kb = mem.get("MemTotal", 0)
                avail_kb = mem.get("MemAvailable", mem.get("MemFree", 0))
                snap["ram_mb"] = (total_kb - avail_kb) // 1024
            except Exception:
                snap["ram_mb"] = 0
            try:
                out = _sp.check_output(
                    ["nvidia-smi",
                     "--query-gpu=memory.used,utilization.gpu",
                     "--format=csv,noheader,nounits"],
                    timeout=5, text=True).strip()
                if out:
                    parts = out.split(",")
                    snap["vram_mb"] = int(parts[0].strip())
                    snap["gpu_util"] = int(parts[1].strip())
            except Exception:
                snap["vram_mb"] = 0
                snap["gpu_util"] = 0
            self._whimai_sys_telemetry = snap
        except Exception:
            pass

    def _whimai_refresh_sys_telemetry_ui(self):
        s = self._whimai_sys_telemetry
        self._obs_vram.config(text=f"{s['vram_mb']}MB")
        self._obs_gpu.config(text=f"{s['gpu_util']}%")
        self._obs_cpu.config(text=f"{s['cpu']:.0f}%")
        self._obs_ram.config(text=f"{s['ram_mb']}MB")

    def _whimai_telemetry_poll_tick(self):
        if not self._whimai_telemetry_polling:
            return
        threading.Thread(target=self._whimai_update_sys_telemetry, daemon=True).start()
        self.after(100, self._whimai_refresh_sys_telemetry_ui)
        self.after(3000, self._whimai_telemetry_poll_tick)

    def _whimai_start_telemetry_poll(self):
        if self._whimai_telemetry_polling:
            return
        self._whimai_telemetry_polling = True
        self._whimai_telemetry_poll_tick()

    # ---------- Capture helpers ----------

    def _whimai_capture_note(self):
        text = self._whimai_get_last_assistant_text()
        if not text:
            text = self.whimai_entry.get("1.0", "end-1c").strip()
        if not text:
            self.whimai_status_var.set("Nothing to capture")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(JOURNAL_DIR, f"note_{ts}.txt")
        os.makedirs(JOURNAL_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(f"Quick Note  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(text + "\n")
        self.whimai_status_var.set(f"Note saved: {os.path.basename(path)}")

    def _whimai_capture_journal(self):
        lines = []
        for msg in self._whimai_chat_history:
            role = "You" if msg["role"] == "user" else "Whim.ai"
            lines.append(f"[{role}]\n{msg['content']}\n")
        if not lines:
            self.whimai_status_var.set("No conversation to capture")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(JOURNAL_DIR, f"journal_{ts}.txt")
        os.makedirs(JOURNAL_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(f"Journal Entry  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 50 + "\n\n")
            f.write("\n".join(lines))
        self.whimai_status_var.set(f"Journal saved: {os.path.basename(path)}")

    def _whimai_capture_actions(self):
        text = self._whimai_get_last_assistant_text()
        if not text:
            self.whimai_status_var.set("No response to extract from")
            return
        action_lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped and (
                stripped.startswith(("- [ ]", "- [x]", "* [ ]", "* [x]"))
                or re.match(r"^\d+[\.\)]\s", stripped)
                or stripped.lower().startswith(("todo:", "action:", "task:"))
                or stripped.startswith("- ")
            ):
                action_lines.append(stripped)
        if not action_lines:
            action_lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            action_lines = [f"- [ ] {ln}" for ln in action_lines[:20]]
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(JOURNAL_DIR, f"actions_{ts}.md")
        os.makedirs(JOURNAL_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(f"# Action Items  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write("\n".join(action_lines) + "\n")
        self.whimai_status_var.set(f"Actions saved: {os.path.basename(path)}")

    def _whimai_export_odt(self):
        lines = []
        for msg in self._whimai_chat_history:
            role = "You" if msg["role"] == "user" else "Whim.ai"
            lines.append(f"[{role}]\n{msg['content']}\n")
        if not lines:
            self.whimai_status_var.set("No conversation to export")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        body_text = "\n".join(lines)
        try:
            from odf.opendocument import OpenDocumentText
            from odf.text import P, H
            from odf import style as odf_style
            doc = OpenDocumentText()
            h_style = odf_style.Style(name="Heading", family="paragraph")
            h_style.addElement(odf_style.TextProperties(
                attributes={"fontsize": "14pt", "fontweight": "bold"}))
            doc.styles.addElement(h_style)
            doc.text.addElement(H(
                outlinelevel=1, stylename=h_style,
                text=f"Whim.ai Transcript  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}"))
            for msg in self._whimai_chat_history:
                role = "You" if msg["role"] == "user" else "Whim.ai"
                doc.text.addElement(P(text=f"[{role}]"))
                for para in msg["content"].split("\n"):
                    doc.text.addElement(P(text=para))
                doc.text.addElement(P(text=""))
            path = os.path.join(TRANSCRIPT_DIR, f"whimai_transcript_{ts}.odt")
            os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
            doc.save(path)
            self.whimai_status_var.set(f"ODT exported: {os.path.basename(path)}")
        except ImportError:
            path = os.path.join(TRANSCRIPT_DIR, f"whimai_transcript_{ts}.txt")
            os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
            with open(path, "w") as f:
                f.write(f"Whim.ai Transcript  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write("=" * 50 + "\n\n")
                f.write(body_text)
            self.whimai_status_var.set(f"odf not installed — saved as TXT: {os.path.basename(path)}")

    def _whimai_save_audio_tr(self):
        path = filedialog.askopenfilename(
            title="Select audio to save to Table Reads",
            filetypes=[("Audio files", "*.wav *.mp3 *.flac *.ogg *.webm *.m4a"),
                       ("All files", "*.*")])
        if not path:
            return
        os.makedirs(TABLE_READS_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(path)[1] or ".wav"
        dest = os.path.join(TABLE_READS_DIR, f"whimai_{ts}{ext}")
        shutil.copy2(path, dest)
        self.whimai_status_var.set(f"Audio saved: {os.path.basename(dest)}")

    def _whimai_get_last_assistant_text(self):
        for msg in reversed(self._whimai_chat_history):
            if msg["role"] == "assistant":
                return msg.get("content", "")
        return ""

    # ---------- Drop zone helpers ----------

    _ROUTE_RULES = {
        "BURNDOWN": {
            "ext": {".log", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml",
                    ".md", ".rst", ".ini", ".conf", ".cfg"},
            "desc": "log / text file",
        },
        "VOICE": {
            "ext": {".wav", ".mp3", ".flac", ".ogg", ".webm", ".m4a", ".aac",
                    ".opus", ".3gp", ".amr"},
            "desc": "audio file",
        },
        "CLONE ROOT": {
            "ext": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".svg",
                    ".webp", ".ico"},
            "desc": "image / screenshot",
        },
    }

    def _whimai_classify_file(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        for route, info in self._ROUTE_RULES.items():
            if ext in info["ext"]:
                return route, info["desc"]
        return "BURNDOWN", "unknown file type"

    def _whimai_route_file(self, filepath):
        route, desc = self._whimai_classify_file(filepath)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        basename = os.path.basename(filepath)
        if route == "VOICE":
            dest_dir = TABLE_READS_DIR
        elif route == "CLONE ROOT":
            dest_dir = os.path.join(ARCHIVE_DIR, "screenshots")
        else:
            dest_dir = JOURNAL_DIR
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{ts}_{basename}")
        shutil.copy2(filepath, dest)
        return route, dest, desc

    def _whimai_drop_browse(self):
        paths = filedialog.askopenfilenames(
            title="Select files to import into Whim",
            filetypes=[
                ("All supported", "*.log *.txt *.csv *.json *.md *.wav *.mp3 *.flac "
                 "*.ogg *.webm *.m4a *.png *.jpg *.jpeg *.gif *.bmp *.svg"),
                ("Logs & Text", "*.log *.txt *.csv *.json *.xml *.yaml *.yml *.md"),
                ("Audio", "*.wav *.mp3 *.flac *.ogg *.webm *.m4a *.aac"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.svg *.webp"),
                ("All files", "*.*"),
            ])
        if not paths:
            return
        results = []
        for p in paths:
            try:
                route, dest, desc = self._whimai_route_file(p)
                results.append(f"{route}: {os.path.basename(dest)} ({desc})")
            except Exception as exc:
                results.append(f"ERROR: {os.path.basename(p)} — {exc}")
        summary = "\n".join(results)
        self._whimai_append(f"\n[Drop import]\n{summary}\n", "ai")
        self.whimai_status_var.set(f"{len(paths)} file(s) imported")
        self._whimai_drop_zone.config(
            text=f"{len(paths)} file(s) routed  — click to add more",
            fg=TH["green"])
        self.after(4000, lambda: self._whimai_drop_zone.config(
            text="Drop files here  (logs / screenshots / audio)\nor paste from clipboard",
            fg="#555555"))

    def _whimai_drop_paste(self):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            self.whimai_status_var.set("Clipboard empty")
            return
        if not clip or not clip.strip():
            self.whimai_status_var.set("Clipboard empty")
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(JOURNAL_DIR, f"clipboard_{ts}.txt")
        os.makedirs(JOURNAL_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(clip)
        self._whimai_append(f"\n[Clipboard paste saved: {os.path.basename(path)}]\n", "ai")
        self.whimai_status_var.set(f"Clipboard saved: {os.path.basename(path)}")

    # ---------- Output template helpers ----------

    def _whimai_apply_template(self, name):
        tpl = self._whimai_templates.get(name)
        if not tpl:
            return
        filled = tpl.replace("{date}", datetime.now().strftime("%Y-%m-%d"))
        last_ai = self._whimai_get_last_assistant_text()
        if last_ai:
            filled += f"\n---\n\n### Source (Whim.ai)\n{last_ai}\n"
        if self._whimai_placeholder_active:
            self._whimai_clear_placeholder()
        self.whimai_entry.delete("1.0", "end")
        self.whimai_entry.insert("1.0", filled)
        self.whimai_entry.config(fg="#40e0d0")
        self.whimai_entry.focus_set()
        self.whimai_status_var.set(f"Template: {name}")

    _ST_CAP_FILTERS = [
        "ALL", "switch", "lock", "thermostat", "motion", "contact",
        "battery", "light", "valve", "alarm", "presence", "sensor"
    ]

    def build_smartthings(self):
        f = self.tabs["smartthings"]
        self._st_devices = []
        self._st_filtered_ids = []
        self._st_favorites = set()
        self._st_recently_controlled = []
        self._st_auto_refresh = False
        self._st_auto_interval = 30
        self._st_last_scan = None
        self._st_scan_errors = 0
        self._st_load_favorites()

        # === Top: scan controls + status ===
        top_bar = tk.Frame(f, bg=TH["bg"])
        top_bar.pack(fill="x", padx=12, pady=(8, 4))

        self._btn(top_bar, "Scan Devices", self._st_scan).pack(side="left", padx=(0, 4))

        self._st_auto_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top_bar, text="Auto-refresh", variable=self._st_auto_var,
                       bg=TH["bg"], fg=TH["fg"], selectcolor=TH["input"],
                       activebackground=TH["bg"], activeforeground=TH["fg"],
                       font=TH["font_sm"], highlightthickness=0,
                       command=self._st_toggle_auto).pack(side="left", padx=(8, 2))

        self._label(top_bar, "every", font=TH["font_xs"]).pack(side="left")
        self._st_interval_var = tk.StringVar(value="30")
        self._entry(top_bar, self._st_interval_var, width=4).pack(side="left", padx=(2, 1))
        self._label(top_bar, "s", font=TH["font_xs"]).pack(side="left", padx=(0, 8))

        tk.Frame(top_bar, bg=TH["border_hi"], width=1).pack(
            side="left", fill="y", padx=6, pady=2)

        self._st_status_label = tk.Label(top_bar, text="Last scan: never", bg=TH["bg"],
                                          fg=TH["fg2"], font=TH["font_xs"])
        self._st_status_label.pack(side="left", padx=4)

        self._st_count_label = tk.Label(top_bar, text="0 devices", bg=TH["bg"],
                                         fg=TH["green"], font=TH["font_xs"])
        self._st_count_label.pack(side="left", padx=4)

        self._st_error_label = tk.Label(top_bar, text="", bg=TH["bg"],
                                         fg=TH["red"], font=TH["font_xs"])
        self._st_error_label.pack(side="left", padx=4)

        self._st_rate_label = tk.Label(top_bar, text="", bg=TH["bg"],
                                        fg=TH["yellow"], font=TH["font_xs"])
        self._st_rate_label.pack(side="right")

        # === Filter bar ===
        filter_bar = tk.Frame(f, bg=TH["bg"])
        filter_bar.pack(fill="x", padx=12, pady=(0, 4))

        self._label(filter_bar, "Search:", font=TH["font_xs"]).pack(side="left")
        self._st_search_var = tk.StringVar()
        self._st_search_entry = self._entry(filter_bar, self._st_search_var, width=22)
        self._st_search_entry.pack(side="left", padx=(2, 6))
        self._st_search_var.trace_add("write", lambda *_: self._st_apply_filters())

        self._label(filter_bar, "Room:", font=TH["font_xs"]).pack(side="left")
        self._st_room_var = tk.StringVar(value="ALL")
        self._st_room_combo = ttk.Combobox(filter_bar, textvariable=self._st_room_var,
                                            values=["ALL"], width=14, state="readonly")
        self._st_room_combo.pack(side="left", padx=(2, 6))
        self._st_room_combo.bind("<<ComboboxSelected>>", lambda e: self._st_apply_filters())

        self._label(filter_bar, "Capability:", font=TH["font_xs"]).pack(side="left")
        self._st_cap_var = tk.StringVar(value="ALL")
        ttk.Combobox(filter_bar, textvariable=self._st_cap_var,
                     values=self._ST_CAP_FILTERS, width=12, state="readonly"
                     ).pack(side="left", padx=(2, 6))
        self._st_cap_var.trace_add("write", lambda *_: self._st_apply_filters())

        self._st_offline_var = tk.BooleanVar(value=False)
        tk.Checkbutton(filter_bar, text="Offline only", variable=self._st_offline_var,
                       bg=TH["bg"], fg=TH["fg"], selectcolor=TH["input"],
                       activebackground=TH["bg"], activeforeground=TH["fg"],
                       font=TH["font_xs"], highlightthickness=0,
                       command=self._st_apply_filters).pack(side="left", padx=4)

        self._st_lowbat_var = tk.BooleanVar(value=False)
        tk.Checkbutton(filter_bar, text="Battery < 20%", variable=self._st_lowbat_var,
                       bg=TH["bg"], fg=TH["fg"], selectcolor=TH["input"],
                       activebackground=TH["bg"], activeforeground=TH["fg"],
                       font=TH["font_xs"], highlightthickness=0,
                       command=self._st_apply_filters).pack(side="left", padx=4)

        self._st_fav_only_var = tk.BooleanVar(value=False)
        tk.Checkbutton(filter_bar, text="Favorites only", variable=self._st_fav_only_var,
                       bg=TH["bg"], fg=TH["fg"], selectcolor=TH["input"],
                       activebackground=TH["bg"], activeforeground=TH["fg"],
                       font=TH["font_xs"], highlightthickness=0,
                       command=self._st_apply_filters).pack(side="left", padx=4)

        self._btn(filter_bar, "Clear Filters", self._st_clear_filters).pack(side="left", padx=6)

        self._st_match_label = tk.Label(filter_bar, text="", bg=TH["bg"],
                                         fg=TH["fg2"], font=TH["font_xs"])
        self._st_match_label.pack(side="right")

        # === Main pane: device table (top) + detail/favorites (bottom) ===
        pane = ttk.PanedWindow(f, orient="vertical")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # -- Device table --
        top = tk.Frame(pane, bg=TH["bg"])

        cols = ("fav", "name", "room", "type", "online", "battery",
                "health", "last_event", "capabilities")
        col_widths = {"fav": 30, "name": 160, "room": 100, "type": 90,
                      "online": 55, "battery": 55, "health": 65,
                      "last_event": 130, "capabilities": 220}

        self._st_tree = ttk.Treeview(top, columns=cols, show="headings", selectmode="browse")
        headings = {"fav": "\u2605", "name": "Name", "room": "Room", "type": "Type",
                    "online": "Online", "battery": "Bat%", "health": "Health",
                    "last_event": "Last Event", "capabilities": "Capabilities"}
        for c in cols:
            self._st_tree.heading(c, text=headings[c],
                                  command=lambda _c=c: self._st_sort_column(_c))
            self._st_tree.column(c, width=col_widths.get(c, 100), minwidth=30)
        self._st_tree.column("fav", anchor="center")
        self._st_tree.column("online", anchor="center")
        self._st_tree.column("battery", anchor="center")

        tree_scroll_y = self._scrollbar(top, command=self._st_tree.yview)
        tree_scroll_x = tk.Scrollbar(top, orient="horizontal", command=self._st_tree.xview,
                                      bg=TH["card"], troughcolor=TH["bg"],
                                      activebackground=TH["btn_hover"],
                                      highlightthickness=0, bd=0)
        self._st_tree.configure(yscrollcommand=tree_scroll_y.set,
                                xscrollcommand=tree_scroll_x.set)

        self._st_tree.pack(side="left", fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")

        self._st_tree.bind("<<TreeviewSelect>>", self._st_on_select)
        self._st_tree.bind("<Double-1>", self._st_toggle_favorite)

        self._st_sort_col = "name"
        self._st_sort_rev = False

        pane.add(top, weight=3)

        # -- Bottom: detail + favorites/recent --
        bottom = tk.Frame(pane, bg=TH["bg"])

        bottom_nb = ttk.Notebook(bottom)
        bottom_nb.pack(fill="both", expand=True)

        # Detail tab
        detail_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(detail_frame, text="  DEVICE DETAIL  ")

        detail_inner = tk.Frame(detail_frame, bg=TH["bg"])
        detail_inner.pack(fill="both", expand=True, padx=8, pady=8)

        self._st_detail_name = tk.Label(detail_inner, text="(select a device)", bg=TH["bg"],
                                         fg=TH["green"], font=TH["font_title"])
        self._st_detail_name.pack(anchor="w")

        detail_grid = tk.Frame(detail_inner, bg=TH["bg"])
        detail_grid.pack(fill="x", pady=(4, 8))

        self._st_detail_fields = {}
        for i, lbl in enumerate(["ID", "Room", "Type", "Online", "Battery",
                                  "Health", "Last Event", "Capabilities"]):
            tk.Label(detail_grid, text=f"{lbl}:", bg=TH["bg"], fg=TH["fg2"],
                     font=TH["font_sm"], anchor="e", width=12).grid(
                         row=i, column=0, sticky="e", padx=(0, 6), pady=1)
            val_fg = TH["green"] if lbl == "Battery" else TH["fg"]
            val = tk.Label(detail_grid, text="--", bg=TH["bg"], fg=val_fg,
                           font=TH["font_sm"], anchor="w")
            val.grid(row=i, column=1, sticky="w", pady=1)
            self._st_detail_fields[lbl] = val

        detail_btn_row = tk.Frame(detail_inner, bg=TH["bg"])
        detail_btn_row.pack(fill="x", pady=(4, 0))
        self._btn(detail_btn_row, "Toggle Favorite", self._st_fav_selected).pack(side="left", padx=2)
        self._btn(detail_btn_row, "Refresh This", self._st_refresh_selected).pack(side="left", padx=2)

        # Favorites tab
        fav_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(fav_frame, text="  FAVORITES  ")

        fav_inner = tk.Frame(fav_frame, bg=TH["bg"])
        fav_inner.pack(fill="both", expand=True, padx=8, pady=8)

        fav_cols = ("name", "room", "type", "online", "battery")
        self._st_fav_tree = ttk.Treeview(fav_inner, columns=fav_cols,
                                          show="headings", height=6)
        for c in fav_cols:
            self._st_fav_tree.heading(c, text=c.title())
        self._st_fav_tree.column("name", width=180)
        self._st_fav_tree.column("room", width=100)
        self._st_fav_tree.column("type", width=90)
        self._st_fav_tree.column("online", width=55, anchor="center")
        self._st_fav_tree.column("battery", width=55, anchor="center")

        fav_scroll = self._scrollbar(fav_inner, command=self._st_fav_tree.yview)
        self._st_fav_tree.configure(yscrollcommand=fav_scroll.set)
        self._st_fav_tree.pack(side="left", fill="both", expand=True)
        fav_scroll.pack(side="right", fill="y")

        # Recently controlled tab
        recent_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(recent_frame, text="  RECENTLY CONTROLLED  ")

        recent_inner = tk.Frame(recent_frame, bg=TH["bg"])
        recent_inner.pack(fill="both", expand=True, padx=8, pady=8)

        recent_cols = ("time", "name", "action")
        self._st_recent_tree = ttk.Treeview(recent_inner, columns=recent_cols,
                                              show="headings", height=6)
        self._st_recent_tree.heading("time", text="Time")
        self._st_recent_tree.heading("name", text="Device")
        self._st_recent_tree.heading("action", text="Action")
        self._st_recent_tree.column("time", width=120)
        self._st_recent_tree.column("name", width=180)
        self._st_recent_tree.column("action", width=200)

        recent_scroll = self._scrollbar(recent_inner, command=self._st_recent_tree.yview)
        self._st_recent_tree.configure(yscrollcommand=recent_scroll.set)
        self._st_recent_tree.pack(side="left", fill="both", expand=True)
        recent_scroll.pack(side="right", fill="y")

        pane.add(bottom, weight=2)

    # -- SmartThings helpers --

    def _st_favorites_path(self):
        return os.path.expanduser("~/.openclaw/st_favorites.json")

    def _st_load_favorites(self):
        try:
            with open(self._st_favorites_path(), "r") as fh:
                data = json.load(fh)
                self._st_favorites = set(data.get("favorites", []))
        except Exception:
            self._st_favorites = set()

    def _st_save_favorites(self):
        try:
            os.makedirs(os.path.dirname(self._st_favorites_path()), exist_ok=True)
            with open(self._st_favorites_path(), "w") as fh:
                json.dump({"favorites": list(self._st_favorites)}, fh)
        except Exception:
            pass

    def _st_scan(self):
        self._st_status_label.configure(text="Scanning...", fg=TH["yellow"])
        self._st_error_label.configure(text="")
        outgoing.put({"type": "req", "id": new_id("stScan"),
                      "method": "smartthings.list", "params": {}})
        self._st_last_scan = datetime.now()
        self.after(500, self._st_check_scan_result)

    def _st_check_scan_result(self):
        ts = self._st_last_scan.strftime("%H:%M:%S") if self._st_last_scan else "?"
        self._st_status_label.configure(text=f"Last scan: {ts}", fg=TH["fg2"])

    def _st_toggle_auto(self):
        self._st_auto_refresh = self._st_auto_var.get()
        if self._st_auto_refresh:
            self._st_auto_tick()

    def _st_auto_tick(self):
        if not self._st_auto_refresh:
            return
        self._st_scan()
        try:
            interval = int(self._st_interval_var.get()) * 1000
        except ValueError:
            interval = 30000
        interval = max(interval, 5000)
        self.after(interval, self._st_auto_tick)

    def smartthings_list(self):
        self._st_scan()

    def st_populate(self, devices):
        self._st_devices = devices if isinstance(devices, list) else []
        self._st_scan_errors = 0
        rooms = sorted(set(d.get("room", "Unknown") for d in self._st_devices))
        self._st_room_combo.configure(values=["ALL"] + rooms)
        ts = self._st_last_scan.strftime("%H:%M:%S") if self._st_last_scan else "now"
        self._st_status_label.configure(text=f"Last scan: {ts}", fg=TH["fg2"])
        self._st_count_label.configure(text=f"{len(self._st_devices)} devices")
        self._st_error_label.configure(text="")
        self._st_apply_filters()
        self._st_refresh_favorites_tree()

    def st_populate_error(self, error_msg, rate_limited=False):
        self._st_scan_errors += 1
        self._st_error_label.configure(text=f"Errors: {self._st_scan_errors}")
        if rate_limited:
            self._st_rate_label.configure(text=f"Rate-limited: {error_msg}")
        else:
            self._st_rate_label.configure(text="")
        ts = self._st_last_scan.strftime("%H:%M:%S") if self._st_last_scan else "?"
        self._st_status_label.configure(text=f"Last scan: {ts} (error)", fg=TH["red"])

    def _st_apply_filters(self):
        search = self._st_search_var.get().strip().lower()
        room = self._st_room_var.get()
        cap = self._st_cap_var.get()
        offline_only = self._st_offline_var.get()
        lowbat = self._st_lowbat_var.get()
        fav_only = self._st_fav_only_var.get()

        for row in self._st_tree.get_children():
            self._st_tree.delete(row)
        self._st_filtered_ids = []

        for dev in self._st_devices:
            did = dev.get("id", "")
            name = dev.get("name", "Unknown")
            d_room = dev.get("room", "Unknown")
            d_type = dev.get("type", "")
            online = dev.get("online", None)
            battery = dev.get("battery", None)
            health = dev.get("health", "")
            last_evt = dev.get("lastEvent", "")
            caps = dev.get("capabilities", [])
            caps_str = ", ".join(caps) if isinstance(caps, list) else str(caps)

            if search and search not in name.lower() and search not in d_room.lower() \
                    and search not in d_type.lower() and search not in caps_str.lower():
                continue
            if room != "ALL" and d_room != room:
                continue
            if cap != "ALL" and cap.lower() not in [c.lower() for c in (caps if isinstance(caps, list) else [])]:
                continue
            if offline_only and online is not False:
                continue
            if lowbat:
                if battery is None or (isinstance(battery, (int, float)) and battery >= 20):
                    continue
            if fav_only and did not in self._st_favorites:
                continue

            fav_marker = "\u2605" if did in self._st_favorites else ""
            online_str = "\u2713" if online else ("\u2717" if online is False else "?")
            bat_str = f"{battery}%" if battery is not None else "--"

            self._st_tree.insert("", "end", iid=did, values=(
                fav_marker, name, d_room, d_type, online_str,
                bat_str, health, last_evt, caps_str))
            self._st_filtered_ids.append(did)

        total = len(self._st_devices)
        shown = len(self._st_filtered_ids)
        if shown < total:
            self._st_match_label.configure(text=f"Showing {shown} of {total}")
        else:
            self._st_match_label.configure(text="")

    def _st_sort_column(self, col):
        if self._st_sort_col == col:
            self._st_sort_rev = not self._st_sort_rev
        else:
            self._st_sort_col = col
            self._st_sort_rev = False

        col_idx = ("fav", "name", "room", "type", "online", "battery",
                   "health", "last_event", "capabilities").index(col)
        items = [(self._st_tree.set(k, col), k) for k in self._st_tree.get_children("")]
        try:
            items.sort(key=lambda t: t[0].lower(), reverse=self._st_sort_rev)
        except Exception:
            items.sort(key=lambda t: str(t[0]), reverse=self._st_sort_rev)
        for idx, (_, k) in enumerate(items):
            self._st_tree.move(k, "", idx)

    def _st_clear_filters(self):
        self._st_search_var.set("")
        self._st_room_var.set("ALL")
        self._st_cap_var.set("ALL")
        self._st_offline_var.set(False)
        self._st_lowbat_var.set(False)
        self._st_fav_only_var.set(False)
        self._st_apply_filters()

    def _st_on_select(self, event=None):
        sel = self._st_tree.selection()
        if not sel:
            return
        did = sel[0]
        dev = next((d for d in self._st_devices if d.get("id") == did), None)
        if not dev:
            return
        self._st_detail_name.configure(text=dev.get("name", "Unknown"))
        caps = dev.get("capabilities", [])
        caps_str = ", ".join(caps) if isinstance(caps, list) else str(caps)
        mapping = {
            "ID": dev.get("id", "--"),
            "Room": dev.get("room", "--"),
            "Type": dev.get("type", "--"),
            "Online": "\u2713 Yes" if dev.get("online") else ("\u2717 No" if dev.get("online") is False else "Unknown"),
            "Battery": f"{dev.get('battery')}%" if dev.get("battery") is not None else "--",
            "Health": dev.get("health", "--"),
            "Last Event": dev.get("lastEvent", "--"),
            "Capabilities": caps_str or "--",
        }
        for lbl, val_widget in self._st_detail_fields.items():
            val_widget.configure(text=mapping.get(lbl, "--"))

    def _st_toggle_favorite(self, event=None):
        sel = self._st_tree.selection()
        if not sel:
            return
        did = sel[0]
        if did in self._st_favorites:
            self._st_favorites.discard(did)
        else:
            self._st_favorites.add(did)
        self._st_save_favorites()
        self._st_apply_filters()
        self._st_refresh_favorites_tree()

    def _st_fav_selected(self):
        self._st_toggle_favorite()

    def _st_refresh_selected(self):
        self._st_scan()

    def _st_refresh_favorites_tree(self):
        for row in self._st_fav_tree.get_children():
            self._st_fav_tree.delete(row)
        for dev in self._st_devices:
            did = dev.get("id", "")
            if did not in self._st_favorites:
                continue
            online_str = "\u2713" if dev.get("online") else ("\u2717" if dev.get("online") is False else "?")
            bat_str = f"{dev.get('battery')}%" if dev.get("battery") is not None else "--"
            self._st_fav_tree.insert("", "end", values=(
                dev.get("name", "?"), dev.get("room", "?"),
                dev.get("type", "?"), online_str, bat_str))

    def st_record_control(self, device_name, action):
        ts = datetime.now().strftime("%H:%M:%S")
        self._st_recently_controlled.append({"time": ts, "name": device_name, "action": action})
        if len(self._st_recently_controlled) > 100:
            self._st_recently_controlled = self._st_recently_controlled[-100:]
        self._st_recent_tree.insert("", 0, values=(ts, device_name, action))

    # ==================== SESSIONS TAB ====================

    _SESSION_PRESETS = {
        "TRV Cipher Review": {"type": "trv", "tags": ["cipher", "review"],
            "note": "TRV cipher decryption review session"},
        "AVR Table Read Batch": {"type": "avr", "tags": ["table-read", "batch"],
            "note": "Batch voice generation for table reads"},
        "Whim.ai Chat": {"type": "whimai", "tags": ["chat", "ai"],
            "note": "General Whim.ai assistant session"},
        "Ingest Pipeline": {"type": "avr", "tags": ["ingest", "transcribe"],
            "note": "Audio ingest and transcription pipeline"},
    }

    def _sess_store_load(self):
        try:
            with open(SESSIONS_STORE, "r") as fh:
                return json.load(fh)
        except Exception:
            return {"sessions_meta": {}, "presets": {}}

    def _sess_store_save(self, store):
        try:
            os.makedirs(os.path.dirname(SESSIONS_STORE), exist_ok=True)
            with open(SESSIONS_STORE, "w") as fh:
                json.dump(store, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _sess_meta_get(self, sid):
        store = self._sess_store_load()
        return store.get("sessions_meta", {}).get(sid, {
            "notes": "", "tags": [], "pinned": False, "artifacts": []
        })

    def _sess_meta_set(self, sid, meta):
        store = self._sess_store_load()
        store.setdefault("sessions_meta", {})[sid] = meta
        self._sess_store_save(store)

    def build_sessions(self):
        f = self.tabs["sessions"]
        self._sessions_data = []
        self._sessions_telemetry = {}
        self._sessions_polling = False

        # -- Top toolbar --
        bar = tk.Frame(f, bg=TH["bg"])
        bar.pack(fill="x", padx=12, pady=8)
        self._btn(bar, "Refresh Sessions", self.sessions_refresh).pack(side="left")
        self._btn(bar, "Auto-Refresh", self._sessions_toggle_poll).pack(side="left", padx=6)
        self._sessions_poll_label = tk.Label(bar, text="OFF", bg=TH["bg"],
                                              fg=TH["red"], font=TH["font_xs"])
        self._sessions_poll_label.pack(side="left", padx=4)

        tk.Frame(bar, bg=TH["border_hi"], width=1).pack(side="left", fill="y", padx=8, pady=2)

        tk.Label(bar, text="Preset:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(0, 4))
        self._sess_preset_var = tk.StringVar(value="")
        preset_combo = ttk.Combobox(bar, textvariable=self._sess_preset_var,
                                     values=list(self._SESSION_PRESETS.keys()),
                                     width=22, state="readonly")
        preset_combo.pack(side="left", padx=(0, 4))
        self._btn(bar, "Load Preset", self._sess_apply_preset).pack(side="left", padx=2)
        self._btn(bar, "Save as Preset", self._sess_save_custom_preset).pack(side="left", padx=2)

        tk.Frame(bar, bg=TH["border_hi"], width=1).pack(side="left", fill="y", padx=8, pady=2)

        self._btn(bar, "Create Notion Entry", self._sess_create_notion_entry).pack(side="left", padx=2)

        # -- Paned: top=table, bottom=detail --
        pane = ttk.PanedWindow(f, orient="vertical")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # === TOP: Session table ===
        top_frame = tk.Frame(pane, bg=TH["bg"])

        cols = ("pin", "name", "type", "status", "started", "last_activity", "duration", "tags")
        col_labels = {"pin": "", "name": "Session Name", "type": "Type",
                      "status": "Status", "started": "Started",
                      "last_activity": "Last Activity", "duration": "Duration",
                      "tags": "Tags"}
        col_widths = {"pin": 30, "name": 200, "type": 100, "status": 80,
                      "started": 140, "last_activity": 140, "duration": 90, "tags": 160}

        tree_frame = tk.Frame(top_frame, bg=TH["bg"])
        tree_frame.pack(fill="both", expand=True)

        self.sessions_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                           selectmode="browse")
        for c in cols:
            self.sessions_tree.heading(c, text=col_labels[c])
            anchor = "center" if c in ("pin", "type", "status", "duration") else "w"
            self.sessions_tree.column(c, width=col_widths[c], anchor=anchor, minwidth=30)

        tree_sb = self._scrollbar(tree_frame, command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=tree_sb.set)
        self.sessions_tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")
        self.sessions_tree.bind("<<TreeviewSelect>>", self._sessions_on_select)
        self.sessions_tree.bind("<Double-1>", self._sess_toggle_pin)

        self.sessions_tree.tag_configure("running", foreground=TH["green"])
        self.sessions_tree.tag_configure("idle", foreground=TH["yellow"])
        self.sessions_tree.tag_configure("stopped", foreground=TH["red"])
        self.sessions_tree.tag_configure("pinned", background="#1a2a1a")

        pane.add(top_frame, weight=3)

        # === BOTTOM: Detail panels ===
        bottom_frame = tk.Frame(pane, bg=TH["bg"])

        detail_nb = ttk.Notebook(bottom_frame)
        detail_nb.pack(fill="both", expand=True)

        # -- Tab 1: Health / Resources --
        health_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(health_tab, text="  HEALTH  ")

        detail_hdr = tk.Frame(health_tab, bg=TH["card"])
        detail_hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(detail_hdr, text="HEALTH / RESOURCES", bg=TH["card"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._sess_detail_name = tk.Label(detail_hdr, text="", bg=TH["card"],
                                           fg=TH["fg"], font=TH["font_sm"])
        self._sess_detail_name.pack(side="right")

        tk.Frame(health_tab, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(0, 6))

        badge_row = tk.Frame(health_tab, bg=TH["card"])
        badge_row.pack(fill="x", padx=10, pady=(0, 8))

        badge_defs = [
            ("CPU", "_sess_badge_cpu"),
            ("RAM", "_sess_badge_ram"),
            ("GPU VRAM", "_sess_badge_vram"),
            ("tok/s", "_sess_badge_tps"),
            ("Queue", "_sess_badge_queue"),
        ]
        for label_text, attr in badge_defs:
            cell = tk.Frame(badge_row, bg=TH["input"], highlightthickness=1,
                            highlightbackground=TH["border"], padx=8, pady=4)
            cell.pack(side="left", padx=(0, 8))
            tk.Label(cell, text=label_text, bg=TH["input"], fg="#555555",
                     font=("Consolas", 8, "bold")).pack(side="left")
            val = tk.Label(cell, text="--", bg=TH["input"], fg=TH["fg"],
                           font=("Consolas", 9))
            val.pack(side="left", padx=(6, 0))
            setattr(self, attr, val)

        # -- Tab 2: Artifacts --
        art_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(art_tab, text="  ARTIFACTS  ")

        art_bar = tk.Frame(art_tab, bg=TH["card"])
        art_bar.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(art_bar, text="ATTACHED OUTPUTS", bg=TH["card"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._btn(art_bar, "Attach File", self._sess_attach_artifact).pack(side="right", padx=2)
        self._btn(art_bar, "Remove", self._sess_remove_artifact).pack(side="right", padx=2)
        self._btn(art_bar, "Open", self._sess_open_artifact).pack(side="right", padx=2)

        tk.Frame(art_tab, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(0, 4))

        art_list_frame = tk.Frame(art_tab, bg=TH["card"])
        art_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        art_cols = ("filename", "type", "size", "added")
        art_labels = {"filename": "File", "type": "Type", "size": "Size", "added": "Added"}
        art_widths = {"filename": 300, "type": 80, "size": 80, "added": 150}

        self._sess_art_tree = ttk.Treeview(art_list_frame, columns=art_cols,
                                            show="headings", selectmode="browse", height=5)
        for c in art_cols:
            self._sess_art_tree.heading(c, text=art_labels[c])
            self._sess_art_tree.column(c, width=art_widths[c], minwidth=40)
        art_sb = self._scrollbar(art_list_frame, command=self._sess_art_tree.yview)
        self._sess_art_tree.configure(yscrollcommand=art_sb.set)
        self._sess_art_tree.pack(side="left", fill="both", expand=True)
        art_sb.pack(side="right", fill="y")

        # -- Tab 3: Notes + Tags --
        notes_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(notes_tab, text="  NOTES / TAGS  ")

        notes_top = tk.Frame(notes_tab, bg=TH["card"])
        notes_top.pack(fill="x", padx=10, pady=(8, 4))

        tag_row = tk.Frame(notes_top, bg=TH["card"])
        tag_row.pack(fill="x", pady=(0, 4))
        tk.Label(tag_row, text="TAGS:", bg=TH["card"], fg=TH["blue_text"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._sess_tags_var = tk.StringVar()
        self._sess_tags_entry = self._entry(tag_row, self._sess_tags_var, width=40)
        self._sess_tags_entry.pack(side="left", padx=(6, 4), fill="x", expand=True)
        self._btn(tag_row, "Save Tags", self._sess_save_tags).pack(side="left", padx=2)
        self._btn(tag_row, "Pin / Unpin", self._sess_toggle_pin_btn).pack(side="left", padx=2)
        self._sess_pin_indicator = tk.Label(tag_row, text="", bg=TH["card"],
                                             fg=TH["yellow"], font=("Consolas", 9))
        self._sess_pin_indicator.pack(side="left", padx=4)

        tk.Frame(notes_tab, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(0, 4))

        notes_lbl = tk.Frame(notes_tab, bg=TH["card"])
        notes_lbl.pack(fill="x", padx=10)
        tk.Label(notes_lbl, text="SESSION NOTES:", bg=TH["card"], fg=TH["blue_text"],
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self._btn(notes_lbl, "Save Notes", self._sess_save_notes).pack(side="right", padx=2)

        notes_wrap = tk.Frame(notes_tab, bg=TH["card"])
        notes_wrap.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self._sess_notes_box = self._text_widget(notes_wrap, font=("Consolas", 9),
                                                  wrap="word", height=5)
        notes_sb = self._scrollbar(notes_wrap, command=self._sess_notes_box.yview)
        self._sess_notes_box.configure(yscrollcommand=notes_sb.set)
        self._sess_notes_box.pack(side="left", fill="both", expand=True)
        notes_sb.pack(side="right", fill="y")

        pane.add(bottom_frame, weight=2)

    # -- Session presets --

    def _sess_apply_preset(self):
        name = self._sess_preset_var.get()
        if not name:
            return
        preset = self._SESSION_PRESETS.get(name)
        if not preset:
            store = self._sess_store_load()
            preset = store.get("presets", {}).get(name)
        if not preset:
            return
        sid = f"preset-{uuid.uuid4().hex[:8]}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        meta = {
            "notes": preset.get("note", ""),
            "tags": list(preset.get("tags", [])),
            "pinned": False,
            "artifacts": [],
        }
        self._sess_meta_set(sid, meta)
        tag_str = ", ".join(meta["tags"])
        self.sessions_tree.insert("", 0, iid=sid,
                                   values=("", name, preset.get("type", "").upper(),
                                           "Idle", now_str, "--", "--", tag_str),
                                   tags=("idle",))
        self.sessions_tree.selection_set(sid)
        self._sessions_on_select()

    def _sess_save_custom_preset(self):
        sel = self.sessions_tree.selection()
        if not sel:
            return
        sid = sel[0]
        vals = self.sessions_tree.item(sid, "values")
        meta = self._sess_meta_get(sid)
        dlg = tk.Toplevel(self)
        dlg.title("Save Session Preset")
        dlg.configure(bg=TH["bg"])
        dlg.geometry("360x180")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Preset Name:", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font"]).pack(padx=12, pady=(12, 4), anchor="w")
        name_var = tk.StringVar(value=vals[1] if vals else "")
        self._entry(dlg, name_var, width=40).pack(padx=12, fill="x")

        tk.Label(dlg, text="Tags (comma-separated):", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font"]).pack(padx=12, pady=(8, 4), anchor="w")
        tags_var = tk.StringVar(value=", ".join(meta.get("tags", [])))
        self._entry(dlg, tags_var, width=40).pack(padx=12, fill="x")

        def do_save():
            pname = name_var.get().strip()
            if not pname:
                dlg.destroy()
                return
            store = self._sess_store_load()
            store.setdefault("presets", {})[pname] = {
                "type": vals[2].lower() if vals else "",
                "tags": [t.strip() for t in tags_var.get().split(",") if t.strip()],
                "note": meta.get("notes", ""),
            }
            self._sess_store_save(store)
            all_names = list(self._SESSION_PRESETS.keys()) + list(store.get("presets", {}).keys())
            self._sess_preset_var.set(pname)
            # update combobox values - walk the bar children
            for w in self.tabs["sessions"].winfo_children():
                for ch in w.winfo_children():
                    if isinstance(ch, ttk.Combobox):
                        ch["values"] = all_names
                        break
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=TH["bg"])
        btn_row.pack(fill="x", padx=12, pady=(10, 12))
        self._btn(btn_row, "Save", do_save).pack(side="left")
        self._btn(btn_row, "Cancel", dlg.destroy).pack(side="left", padx=6)

    # -- Artifacts --

    def _sess_selected_sid(self):
        sel = self.sessions_tree.selection()
        return sel[0] if sel else None

    def _sess_attach_artifact(self):
        sid = self._sess_selected_sid()
        if not sid:
            return
        paths = filedialog.askopenfilenames(
            title="Attach artifacts to session",
            filetypes=[
                ("All supported", "*.wav *.mp3 *.flac *.odt *.txt *.csv *.json *.md *.pdf *.png *.jpg"),
                ("Audio", "*.wav *.mp3 *.flac *.ogg"),
                ("Documents", "*.odt *.txt *.csv *.json *.md *.pdf"),
                ("All files", "*.*"),
            ])
        if not paths:
            return
        meta = self._sess_meta_get(sid)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for p in paths:
            entry = {
                "path": p,
                "filename": os.path.basename(p),
                "added": now_str,
            }
            try:
                sz = os.path.getsize(p)
                if sz < 1024:
                    entry["size"] = f"{sz}B"
                elif sz < 1024 * 1024:
                    entry["size"] = f"{sz // 1024}KB"
                else:
                    entry["size"] = f"{sz // (1024 * 1024)}MB"
            except Exception:
                entry["size"] = "--"
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            type_map = {"wav": "Audio", "mp3": "Audio", "flac": "Audio", "ogg": "Audio",
                        "odt": "Document", "txt": "Text", "csv": "Data", "json": "Data",
                        "md": "Text", "pdf": "Document", "png": "Image", "jpg": "Image"}
            entry["type"] = type_map.get(ext, ext.upper() or "File")
            meta.setdefault("artifacts", []).append(entry)
        self._sess_meta_set(sid, meta)
        self._sess_refresh_artifacts(sid)

    def _sess_refresh_artifacts(self, sid):
        for item in self._sess_art_tree.get_children():
            self._sess_art_tree.delete(item)
        if not sid:
            return
        meta = self._sess_meta_get(sid)
        for i, art in enumerate(meta.get("artifacts", [])):
            self._sess_art_tree.insert("", "end", iid=str(i),
                                        values=(art.get("filename", ""),
                                                art.get("type", ""),
                                                art.get("size", "--"),
                                                art.get("added", "")))

    def _sess_remove_artifact(self):
        sid = self._sess_selected_sid()
        if not sid:
            return
        sel = self._sess_art_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        meta = self._sess_meta_get(sid)
        arts = meta.get("artifacts", [])
        if 0 <= idx < len(arts):
            arts.pop(idx)
            self._sess_meta_set(sid, meta)
            self._sess_refresh_artifacts(sid)

    def _sess_open_artifact(self):
        sel = self._sess_art_tree.selection()
        if not sel:
            return
        sid = self._sess_selected_sid()
        if not sid:
            return
        idx = int(sel[0])
        meta = self._sess_meta_get(sid)
        arts = meta.get("artifacts", [])
        if 0 <= idx < len(arts):
            path = arts[idx].get("path", "")
            if path and os.path.isfile(path):
                try:
                    subprocess.Popen(["xdg-open", path])
                except Exception:
                    pass

    # -- Notes + Tags --

    def _sess_save_tags(self):
        sid = self._sess_selected_sid()
        if not sid:
            return
        meta = self._sess_meta_get(sid)
        raw = self._sess_tags_var.get()
        meta["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
        self._sess_meta_set(sid, meta)
        tag_str = ", ".join(meta["tags"])
        vals = list(self.sessions_tree.item(sid, "values"))
        if len(vals) >= 8:
            vals[7] = tag_str
            self.sessions_tree.item(sid, values=vals)

    def _sess_save_notes(self):
        sid = self._sess_selected_sid()
        if not sid:
            return
        meta = self._sess_meta_get(sid)
        meta["notes"] = self._sess_notes_box.get("1.0", "end-1c")
        self._sess_meta_set(sid, meta)

    def _sess_toggle_pin_btn(self):
        sid = self._sess_selected_sid()
        if sid:
            self._sess_do_pin_toggle(sid)

    def _sess_toggle_pin(self, event=None):
        region = self.sessions_tree.identify_region(event.x, event.y)
        col = self.sessions_tree.identify_column(event.x)
        if col == "#1":
            item = self.sessions_tree.identify_row(event.y)
            if item:
                self._sess_do_pin_toggle(item)

    def _sess_do_pin_toggle(self, sid):
        meta = self._sess_meta_get(sid)
        meta["pinned"] = not meta.get("pinned", False)
        self._sess_meta_set(sid, meta)
        vals = list(self.sessions_tree.item(sid, "values"))
        if len(vals) >= 1:
            vals[0] = "\u25cf" if meta["pinned"] else ""
            self.sessions_tree.item(sid, values=vals)
        cur_tags = list(self.sessions_tree.item(sid, "tags"))
        if meta["pinned"]:
            if "pinned" not in cur_tags:
                cur_tags.append("pinned")
            self.sessions_tree.move(sid, "", 0)
        else:
            if "pinned" in cur_tags:
                cur_tags.remove("pinned")
        self.sessions_tree.item(sid, tags=cur_tags)
        self._sess_update_pin_indicator(meta["pinned"])

    def _sess_update_pin_indicator(self, pinned):
        self._sess_pin_indicator.config(
            text="PINNED" if pinned else "",
            fg=TH["yellow"] if pinned else TH["fg_dim"])

    # -- Selection handler (loads detail panels) --

    def _sessions_on_select(self, event=None):
        sel = self.sessions_tree.selection()
        if not sel:
            self._sess_detail_name.config(text="")
            self._sess_tags_var.set("")
            self._sess_notes_box.delete("1.0", "end")
            self._sess_update_pin_indicator(False)
            self._sess_refresh_artifacts(None)
            return
        sid = sel[0]
        vals = self.sessions_tree.item(sid, "values")
        self._sess_detail_name.config(text=vals[1] if len(vals) > 1 else "")
        self._sessions_refresh_badges()

        meta = self._sess_meta_get(sid)
        self._sess_tags_var.set(", ".join(meta.get("tags", [])))
        self._sess_notes_box.delete("1.0", "end")
        self._sess_notes_box.insert("1.0", meta.get("notes", ""))
        self._sess_update_pin_indicator(meta.get("pinned", False))
        self._sess_refresh_artifacts(sid)

    # -- Status / time helpers --

    def _sessions_status_tag(self, status):
        s = (status or "").lower()
        if s == "running":
            return "running"
        if s == "idle":
            return "idle"
        return "stopped"

    def _sessions_format_time(self, ts):
        if not ts:
            return "--"
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            else:
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt = datetime.strptime(str(ts), fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return str(ts)[:19]
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(ts)[:19]

    def _sessions_calc_duration(self, started, last_activity=None):
        try:
            def _parse(v):
                if isinstance(v, (int, float)):
                    return datetime.fromtimestamp(v)
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(str(v), fmt)
                    except ValueError:
                        continue
                return None
            start_dt = _parse(started)
            end_dt = _parse(last_activity) if last_activity else datetime.now()
            if not start_dt or not end_dt:
                return "--"
            delta = end_dt - start_dt
            secs = int(delta.total_seconds())
            if secs < 0:
                return "--"
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            if h > 0:
                return f"{h}h {m}m"
            if m > 0:
                return f"{m}m {s}s"
            return f"{s}s"
        except Exception:
            return "--"

    # -- Refresh / telemetry --

    def sessions_refresh(self):
        outgoing.put({"type": "req", "id": new_id("sessionsList"),
                      "method": "sessions.list", "params": {}})
        self._sessions_collect_local()

    def _sessions_collect_local(self):
        threading.Thread(target=self._sessions_gather_telemetry, daemon=True).start()

    def _sessions_gather_telemetry(self):
        snap = {"cpu": 0.0, "ram_mb": 0, "vram_mb": 0, "gpu_util": 0}
        try:
            loadavg = os.getloadavg()
            snap["cpu"] = loadavg[0] * 100.0 / max(os.cpu_count() or 1, 1)
        except Exception:
            pass
        try:
            with open("/proc/meminfo", "r") as mf:
                lines = mf.readlines()
            mem = {}
            for ln in lines[:5]:
                parts = ln.split()
                if len(parts) >= 2:
                    mem[parts[0].rstrip(":")] = int(parts[1])
            total_kb = mem.get("MemTotal", 0)
            avail_kb = mem.get("MemAvailable", mem.get("MemFree", 0))
            snap["ram_mb"] = (total_kb - avail_kb) // 1024
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
                 "--format=csv,noheader,nounits"], timeout=5, text=True).strip()
            if out:
                parts = out.split(",")
                snap["vram_mb"] = int(parts[0].strip())
                snap["gpu_util"] = int(parts[1].strip())
        except Exception:
            pass
        self._sessions_telemetry["_system"] = snap
        self.after(0, self._sessions_refresh_badges)

    def _sessions_refresh_badges(self):
        sel = self.sessions_tree.selection()
        sid = sel[0] if sel else None
        telem = self._sessions_telemetry.get("_system", {})
        if sid and sid in self._sessions_telemetry:
            telem = self._sessions_telemetry[sid]
        cpu = telem.get("cpu", 0)
        cpu_color = TH["green"] if cpu < 60 else TH["yellow"] if cpu < 85 else TH["red"]
        self._sess_badge_cpu.config(text=f"{cpu:.0f}%", fg=cpu_color)

        ram = telem.get("ram_mb", 0)
        ram_color = TH["green"] if ram < 8000 else TH["yellow"] if ram < 14000 else TH["red"]
        self._sess_badge_ram.config(text=f"{ram}MB", fg=ram_color)

        vram = telem.get("vram_mb", 0)
        vram_color = TH["green"] if vram < 6000 else TH["yellow"] if vram < 10000 else TH["red"]
        self._sess_badge_vram.config(text=f"{vram}MB", fg=vram_color)

        tps = telem.get("tokens_per_sec", None)
        self._sess_badge_tps.config(
            text=f"{tps:.1f}" if tps is not None else "--",
            fg=TH["green"] if tps and tps > 10 else TH["yellow"] if tps else TH["fg_dim"])

        qdepth = telem.get("queue_depth", None)
        self._sess_badge_queue.config(
            text=str(qdepth) if qdepth is not None else "--",
            fg=TH["green"] if qdepth is not None and qdepth < 5 else
               TH["yellow"] if qdepth is not None and qdepth < 20 else
               TH["red"] if qdepth is not None else TH["fg_dim"])

    # -- Populate from gateway response --

    def sessions_populate(self, sessions):
        self._sessions_data = sessions or []
        store = self._sess_store_load()
        all_meta = store.get("sessions_meta", {})

        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)

        type_map = {"whim.ai": "Whim.ai", "whimai": "Whim.ai", "avr": "AVR",
                    "trv": "TRV"}

        pinned_ids = []
        unpinned_ids = []

        for sess in self._sessions_data:
            name = sess.get("name", sess.get("id", "unknown"))
            raw_type = str(sess.get("type", "")).lower()
            stype = type_map.get(raw_type, raw_type.upper() if raw_type else "--")
            status = sess.get("status", "stopped")
            started = self._sessions_format_time(sess.get("started", sess.get("startedAt")))
            last_act = self._sessions_format_time(
                sess.get("lastActivity", sess.get("last_activity")))
            duration = self._sessions_calc_duration(
                sess.get("started", sess.get("startedAt")),
                sess.get("lastActivity", sess.get("last_activity")))
            tag = self._sessions_status_tag(status)
            sid = sess.get("id", name)

            meta = all_meta.get(sid, {})
            is_pinned = meta.get("pinned", False)
            tag_str = ", ".join(meta.get("tags", []))
            pin_marker = "\u25cf" if is_pinned else ""

            tags = [tag]
            if is_pinned:
                tags.append("pinned")

            self.sessions_tree.insert("", "end", iid=sid,
                                       values=(pin_marker, name, stype,
                                               status.capitalize(), started,
                                               last_act, duration, tag_str),
                                       tags=tags)
            if "telemetry" in sess:
                self._sessions_telemetry[sid] = sess["telemetry"]

            if is_pinned:
                pinned_ids.append(sid)
            else:
                unpinned_ids.append(sid)

            if status.lower() in ("running", "idle"):
                self._sess_mark_active(sid, name, stype)
            else:
                self._sess_mark_closed(sid)

        for i, sid in enumerate(pinned_ids):
            self.sessions_tree.move(sid, "", i)

    # -- Auto-refresh --

    def _sessions_toggle_poll(self):
        self._sessions_polling = not self._sessions_polling
        if self._sessions_polling:
            self._sessions_poll_label.config(text="ON", fg=TH["green"])
            self._sessions_poll_tick()
        else:
            self._sessions_poll_label.config(text="OFF", fg=TH["red"])

    def _sessions_poll_tick(self):
        if not self._sessions_polling:
            return
        self.sessions_refresh()
        self.after(5000, self._sessions_poll_tick)

    # -- Create Notion entry (markdown export) --

    def _sess_create_notion_entry(self):
        sid = self._sess_selected_sid()
        if not sid:
            return
        vals = self.sessions_tree.item(sid, "values")
        meta = self._sess_meta_get(sid)
        if not vals or len(vals) < 8:
            return

        name = vals[1]
        stype = vals[2]
        status = vals[3]
        started = vals[4]
        last_act = vals[5]
        duration = vals[6]
        tags = vals[7]

        lines = []
        lines.append(f"# {name}")
        lines.append("")
        lines.append(f"**Type:** {stype}  ")
        lines.append(f"**Status:** {status}  ")
        lines.append(f"**Started:** {started}  ")
        lines.append(f"**Last Activity:** {last_act}  ")
        lines.append(f"**Duration:** {duration}  ")
        if tags:
            tag_list = " ".join(f"`{t.strip()}`" for t in tags.split(",") if t.strip())
            lines.append(f"**Tags:** {tag_list}  ")
        lines.append("")

        notes = meta.get("notes", "").strip()
        if notes:
            lines.append("## Notes")
            lines.append("")
            lines.append(notes)
            lines.append("")

        artifacts = meta.get("artifacts", [])
        if artifacts:
            lines.append("## Artifacts")
            lines.append("")
            lines.append("| File | Type | Size | Added |")
            lines.append("|------|------|------|-------|")
            for art in artifacts:
                fn = art.get("filename", "")
                atype = art.get("type", "")
                size = art.get("size", "--")
                added = art.get("added", "")
                path = art.get("path", "")
                link = f"[{fn}](file://{path})" if path else fn
                lines.append(f"| {link} | {atype} | {size} | {added} |")
            lines.append("")

        lines.append("---")
        lines.append(f"*Exported from Whim Sessions at "
                     f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        md_text = "\n".join(lines)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-]', '_', name)
        filename = f"session_{safe_name}_{ts}.md"
        out_path = os.path.join(JOURNAL_DIR, filename)
        os.makedirs(JOURNAL_DIR, exist_ok=True)
        with open(out_path, "w") as fh:
            fh.write(md_text)

        try:
            self.clipboard_clear()
            self.clipboard_append(md_text)
        except Exception:
            pass

        dlg = tk.Toplevel(self)
        dlg.title("Notion Entry Created")
        dlg.configure(bg=TH["bg"])
        dlg.geometry("600x420")
        dlg.transient(self)
        dlg.grab_set()

        hdr = tk.Frame(dlg, bg=TH["bg"])
        hdr.pack(fill="x", padx=12, pady=(12, 4))
        tk.Label(hdr, text="Markdown copied to clipboard + saved to Journal",
                 bg=TH["bg"], fg=TH["green"], font=TH["font_title"]).pack(side="left")

        tk.Label(dlg, text=f"File: {out_path}", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(padx=12, anchor="w")

        preview_frame = tk.Frame(dlg, bg=TH["bg"])
        preview_frame.pack(fill="both", expand=True, padx=12, pady=(6, 4))
        preview = self._text_widget(preview_frame, font=("Consolas", 9),
                                     wrap="word", state="normal")
        psb = self._scrollbar(preview_frame, command=preview.yview)
        preview.configure(yscrollcommand=psb.set)
        preview.pack(side="left", fill="both", expand=True)
        psb.pack(side="right", fill="y")
        preview.insert("1.0", md_text)
        preview.config(state="disabled")

        btn_row = tk.Frame(dlg, bg=TH["bg"])
        btn_row.pack(fill="x", padx=12, pady=(4, 12))
        self._btn(btn_row, "Open in Editor",
                  lambda: subprocess.Popen(["xdg-open", out_path])).pack(side="left", padx=2)
        self._btn(btn_row, "Copy Again",
                  lambda: (self.clipboard_clear(), self.clipboard_append(md_text))).pack(
                      side="left", padx=2)
        self._btn(btn_row, "Close", dlg.destroy).pack(side="right", padx=2)

    # -- Crash recovery --

    def _sess_mark_active(self, sid, name="", stype=""):
        store = self._sess_store_load()
        active = store.setdefault("active_sessions", {})
        active[sid] = {
            "name": name,
            "type": stype,
            "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
        }
        self._sess_store_save(store)

    def _sess_mark_closed(self, sid):
        store = self._sess_store_load()
        active = store.get("active_sessions", {})
        active.pop(sid, None)
        store["active_sessions"] = active
        self._sess_store_save(store)

    def _sess_check_crash_recovery(self):
        store = self._sess_store_load()
        active = store.get("active_sessions", {})
        if not active:
            return

        stale = {}
        for sid, info in list(active.items()):
            pid = info.get("pid", 0)
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, 0)
            except OSError:
                stale[sid] = info

        if not stale:
            return

        dlg = tk.Toplevel(self)
        dlg.title("Crash Recovery")
        dlg.configure(bg=TH["bg"])
        dlg.geometry("620x440")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Incomplete Sessions Detected",
                 bg=TH["bg"], fg=TH["yellow"],
                 font=TH["font_title"]).pack(padx=12, pady=(12, 4), anchor="w")

        tk.Label(dlg, text="The following sessions were running when Whim last exited "
                 "unexpectedly. You can restore them to the session list or discard them.",
                 bg=TH["bg"], fg=TH["fg2"], font=TH["font_sm"],
                 wraplength=580, justify="left").pack(padx=12, pady=(0, 8), anchor="w")

        list_frame = tk.Frame(dlg, bg=TH["bg"])
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 4))

        cr_cols = ("name", "type", "started", "pid")
        cr_tree = ttk.Treeview(list_frame, columns=cr_cols, show="headings",
                                selectmode="extended", height=6)
        cr_tree.heading("name", text="Session Name")
        cr_tree.heading("type", text="Type")
        cr_tree.heading("started", text="Started")
        cr_tree.heading("pid", text="Old PID")
        cr_tree.column("name", width=220)
        cr_tree.column("type", width=100, anchor="center")
        cr_tree.column("started", width=160)
        cr_tree.column("pid", width=80, anchor="center")
        cr_sb = self._scrollbar(list_frame, command=cr_tree.yview)
        cr_tree.configure(yscrollcommand=cr_sb.set)
        cr_tree.pack(side="left", fill="both", expand=True)
        cr_sb.pack(side="right", fill="y")

        for sid, info in stale.items():
            cr_tree.insert("", "end", iid=sid,
                           values=(info.get("name", sid),
                                   info.get("type", "--"),
                                   info.get("started", "--"),
                                   info.get("pid", "--")))

        log_label = tk.Label(dlg, text="Last known logs:", bg=TH["bg"],
                              fg=TH["fg2"], font=TH["font_xs"])
        log_label.pack(padx=12, anchor="w", pady=(4, 0))

        log_frame = tk.Frame(dlg, bg=TH["bg"])
        log_frame.pack(fill="x", padx=12, pady=(0, 4))
        cr_log = self._text_widget(log_frame, font=("Consolas", 8), height=5,
                                    state="disabled", wrap="word")
        log_sb = self._scrollbar(log_frame, command=cr_log.yview)
        cr_log.configure(yscrollcommand=log_sb.set)
        cr_log.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        self._sess_cr_load_logs(cr_log, stale)

        def on_cr_select(event=None):
            sel = cr_tree.selection()
            if sel:
                self._sess_cr_load_logs(cr_log, {s: stale[s] for s in sel if s in stale})

        cr_tree.bind("<<TreeviewSelect>>", on_cr_select)

        btn_row = tk.Frame(dlg, bg=TH["bg"])
        btn_row.pack(fill="x", padx=12, pady=(4, 12))

        def do_restore():
            sel = cr_tree.selection() or list(stale.keys())
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for sid in sel:
                if sid not in stale:
                    continue
                info = stale[sid]
                meta = self._sess_meta_get(sid)
                old_notes = meta.get("notes", "")
                recovery_note = (f"[Recovered {now}] Session was interrupted "
                                 f"(PID {info.get('pid', '?')}, "
                                 f"started {info.get('started', '?')})")
                meta["notes"] = (recovery_note + "\n" + old_notes).strip()
                meta.setdefault("tags", [])
                if "recovered" not in meta["tags"]:
                    meta["tags"].append("recovered")
                self._sess_meta_set(sid, meta)

                tag_str = ", ".join(meta.get("tags", []))
                pin = "\u25cf" if meta.get("pinned", False) else ""
                tags_list = ["idle"]
                if meta.get("pinned"):
                    tags_list.append("pinned")
                try:
                    self.sessions_tree.insert("", 0, iid=sid,
                                               values=(pin, info.get("name", sid),
                                                       info.get("type", "--").upper(),
                                                       "Recovered",
                                                       info.get("started", "--"),
                                                       now, "--", tag_str),
                                               tags=tags_list)
                except tk.TclError:
                    pass
            self._sess_cr_discard_active(list(sel))
            dlg.destroy()

        def do_discard():
            sel = cr_tree.selection() or list(stale.keys())
            self._sess_cr_discard_active(list(sel))
            dlg.destroy()

        self._btn(btn_row, "Restore Selected", do_restore).pack(side="left", padx=2)
        self._btn(btn_row, "Restore All",
                  lambda: (cr_tree.selection_set(list(stale.keys())),
                           do_restore())).pack(side="left", padx=2)
        self._btn(btn_row, "Discard Selected", do_discard).pack(side="left", padx=8)
        self._btn(btn_row, "Discard All",
                  lambda: (cr_tree.selection_set(list(stale.keys())),
                           do_discard())).pack(side="left", padx=2)

    def _sess_cr_load_logs(self, text_widget, stale_map):
        text_widget.config(state="normal")
        text_widget.delete("1.0", "end")
        log_lines = []
        for sid, info in stale_map.items():
            log_lines.append(f"--- {info.get('name', sid)} (PID {info.get('pid', '?')}) ---")
            meta = self._sess_meta_get(sid)
            notes = meta.get("notes", "")
            if notes:
                log_lines.append(notes[:500])
            log_sources = [
                os.path.expanduser("~/.openclaw/gateway.log"),
            ]
            for lp in log_sources:
                if os.path.isfile(lp):
                    try:
                        with open(lp, "r") as fh:
                            tail = fh.readlines()[-20:]
                        log_lines.append(f"\n[{os.path.basename(lp)} tail]")
                        log_lines.extend(l.rstrip() for l in tail)
                    except Exception:
                        pass
                    break
            else:
                log_lines.append("(no log files found)")
            log_lines.append("")
        text_widget.insert("1.0", "\n".join(log_lines))
        text_widget.config(state="disabled")

    def _sess_cr_discard_active(self, sids):
        store = self._sess_store_load()
        active = store.get("active_sessions", {})
        for sid in sids:
            active.pop(sid, None)
        store["active_sessions"] = active
        self._sess_store_save(store)

    def sessions_list(self):
        outgoing.put({"type": "req", "id": new_id("sessionsList"),
                      "method": "sessions.list", "params": {}})

    # ==================== PRESENCE TAB ====================

    _PRESENCE_COMPONENTS = [
        {"id": "whim-ui",       "name": "WHIM UI",          "kind": "client"},
        {"id": "whim-ai",       "name": "Whim.ai",          "kind": "agent"},
        {"id": "gateway",       "name": "Gateway",          "kind": "gateway"},
        {"id": "ingest",        "name": "Ingest Service",   "kind": "agent"},
    ]

    def build_presence(self):
        f = self.tabs["presence"]
        self._pres_data = {}
        self._pres_heartbeats = {}
        self._pres_hb_send_times = {}
        self._pres_polling = False

        # -- Toolbar --
        bar = tk.Frame(f, bg=TH["bg"])
        bar.pack(fill="x", padx=12, pady=8)
        self._btn(bar, "Refresh Presence", self._pres_refresh).pack(side="left")
        self._btn(bar, "Ping All", self._pres_ping_all).pack(side="left", padx=6)
        self._btn(bar, "Auto-Poll", self._pres_toggle_poll).pack(side="left", padx=6)
        self._pres_poll_label = tk.Label(bar, text="OFF", bg=TH["bg"],
                                          fg=TH["red"], font=TH["font_xs"])
        self._pres_poll_label.pack(side="left", padx=4)
        self._pres_last_refresh = tk.Label(bar, text="", bg=TH["bg"],
                                            fg=TH["fg_dim"], font=TH["font_xs"])
        self._pres_last_refresh.pack(side="right")

        # -- Paned: top=roster, bottom=detail --
        pane = ttk.PanedWindow(f, orient="vertical")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # === TOP: Online roster ===
        top = tk.Frame(pane, bg=TH["bg"])

        cols = ("name", "kind", "status", "last_seen", "uptime")
        col_labels = {"name": "Component", "kind": "Type", "status": "Status",
                      "last_seen": "Last Seen", "uptime": "Uptime"}
        col_widths = {"name": 200, "kind": 100, "status": 110,
                      "last_seen": 180, "uptime": 120}

        tree_frame = tk.Frame(top, bg=TH["bg"])
        tree_frame.pack(fill="both", expand=True)

        self._pres_tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                        selectmode="browse")
        for c in cols:
            self._pres_tree.heading(c, text=col_labels[c])
            anchor = "center" if c in ("kind", "status", "uptime") else "w"
            self._pres_tree.column(c, width=col_widths[c], anchor=anchor, minwidth=60)

        tree_sb = self._scrollbar(tree_frame, command=self._pres_tree.yview)
        self._pres_tree.configure(yscrollcommand=tree_sb.set)
        self._pres_tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")
        self._pres_tree.bind("<<TreeviewSelect>>", self._pres_on_select)

        self._pres_tree.tag_configure("connected", foreground=TH["green"])
        self._pres_tree.tag_configure("idle", foreground=TH["yellow"])
        self._pres_tree.tag_configure("busy", foreground="#e08020")
        self._pres_tree.tag_configure("error", foreground=TH["red"])
        self._pres_tree.tag_configure("reconnecting", foreground="#c060c0")
        self._pres_tree.tag_configure("offline", foreground=TH["fg_dim"])

        for comp in self._PRESENCE_COMPONENTS:
            self._pres_tree.insert("", "end", iid=comp["id"],
                                    values=(comp["name"], comp["kind"].capitalize(),
                                            "Unknown", "--", "--"),
                                    tags=("offline",))

        pane.add(top, weight=3)

        # === BOTTOM: Detail + Heartbeat ===
        bottom = tk.Frame(pane, bg=TH["bg"])

        detail_nb = ttk.Notebook(bottom)
        detail_nb.pack(fill="both", expand=True)

        # -- Tab 1: Status detail --
        status_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(status_tab, text="  STATUS  ")

        status_hdr = tk.Frame(status_tab, bg=TH["card"])
        status_hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(status_hdr, text="COMPONENT DETAIL", bg=TH["card"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._pres_detail_name = tk.Label(status_hdr, text="", bg=TH["card"],
                                           fg=TH["fg"], font=TH["font_sm"])
        self._pres_detail_name.pack(side="right")

        tk.Frame(status_tab, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(0, 6))

        detail_grid = tk.Frame(status_tab, bg=TH["card"])
        detail_grid.pack(fill="x", padx=10, pady=(0, 8))

        detail_fields = [
            ("Status:", "_pres_d_status"),
            ("Connected Since:", "_pres_d_connected"),
            ("Last Seen:", "_pres_d_lastseen"),
            ("Uptime:", "_pres_d_uptime"),
            ("Version:", "_pres_d_version"),
            ("Endpoint:", "_pres_d_endpoint"),
            ("Error:", "_pres_d_error"),
        ]
        for i, (label_text, attr) in enumerate(detail_fields):
            r, c = divmod(i, 2)
            cell = tk.Frame(detail_grid, bg=TH["card"])
            cell.grid(row=r, column=c, sticky="w", padx=(0, 20), pady=2)
            tk.Label(cell, text=label_text, bg=TH["card"], fg="#555555",
                     font=("Consolas", 8, "bold")).pack(side="left")
            val = tk.Label(cell, text="--", bg=TH["card"], fg=TH["fg"],
                           font=("Consolas", 9))
            val.pack(side="left", padx=(6, 0))
            setattr(self, attr, val)
        detail_grid.columnconfigure(0, weight=1)
        detail_grid.columnconfigure(1, weight=1)

        # -- Tab 2: Heartbeat --
        hb_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(hb_tab, text="  HEARTBEAT  ")

        hb_hdr = tk.Frame(hb_tab, bg=TH["card"])
        hb_hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(hb_hdr, text="HEARTBEAT MONITOR", bg=TH["card"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._btn(hb_hdr, "Ping Selected", self._pres_ping_selected).pack(side="right", padx=2)

        tk.Frame(hb_tab, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(0, 6))

        hb_grid = tk.Frame(hb_tab, bg=TH["card"])
        hb_grid.pack(fill="x", padx=10, pady=(0, 8))

        self._pres_hb_widgets = {}
        for i, comp in enumerate(self._PRESENCE_COMPONENTS):
            row = tk.Frame(hb_grid, bg=TH["card"])
            row.pack(fill="x", pady=2)

            name_lbl = tk.Label(row, text=comp["name"], bg=TH["card"],
                                fg=TH["fg"], font=("Consolas", 9, "bold"), width=20,
                                anchor="w")
            name_lbl.pack(side="left")

            dot = tk.Label(row, text="\u25cf", bg=TH["card"],
                           fg=TH["fg_dim"], font=("Consolas", 12))
            dot.pack(side="left", padx=(4, 8))

            ts_lbl = tk.Label(row, text="Last HB: --", bg=TH["card"],
                              fg=TH["fg2"], font=("Consolas", 8))
            ts_lbl.pack(side="left", padx=(0, 12))

            rtt_lbl = tk.Label(row, text="RTT: --", bg=TH["card"],
                               fg=TH["fg2"], font=("Consolas", 8))
            rtt_lbl.pack(side="left", padx=(0, 12))

            streak_lbl = tk.Label(row, text="", bg=TH["card"],
                                  fg=TH["fg_dim"], font=("Consolas", 8))
            streak_lbl.pack(side="left")

            self._pres_hb_widgets[comp["id"]] = {
                "dot": dot, "ts": ts_lbl, "rtt": rtt_lbl, "streak": streak_lbl
            }
            self._pres_heartbeats[comp["id"]] = {
                "last_ts": None, "rtt_ms": None, "ok_streak": 0, "fail_streak": 0
            }

        # -- Tab 3: Presence Map --
        map_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(map_tab, text="  MAP  ")

        self._pres_map_canvas = tk.Canvas(map_tab, bg=TH["input"], highlightthickness=0)
        self._pres_map_canvas.pack(fill="both", expand=True, padx=10, pady=8)
        self._pres_map_canvas.bind("<Configure>", lambda e: self._pres_draw_map())
        self._pres_map_node_positions = {}

        # -- Tab 4: What Changed? --
        changes_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(changes_tab, text="  CHANGES  ")

        changes_hdr = tk.Frame(changes_tab, bg=TH["card"])
        changes_hdr.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(changes_hdr, text="WHAT CHANGED?", bg=TH["card"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._pres_changes_count = tk.Label(changes_hdr, text="", bg=TH["card"],
                                             fg=TH["fg2"], font=TH["font_xs"])
        self._pres_changes_count.pack(side="right")
        self._btn(changes_hdr, "Clear", self._pres_clear_changes).pack(side="right", padx=6)

        tk.Frame(changes_tab, bg=TH["border_hi"], height=1).pack(
            fill="x", padx=10, pady=(0, 4))

        changes_wrap = tk.Frame(changes_tab, bg=TH["card"])
        changes_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._pres_changes_box = self._text_widget(changes_wrap, font=("Consolas", 9),
                                                    state="disabled", wrap="word")
        ch_sb = self._scrollbar(changes_wrap, command=self._pres_changes_box.yview)
        self._pres_changes_box.configure(yscrollcommand=ch_sb.set)
        self._pres_changes_box.pack(side="left", fill="both", expand=True)
        ch_sb.pack(side="right", fill="y")

        self._pres_changes_box.tag_configure("new_conn", foreground=TH["green"])
        self._pres_changes_box.tag_configure("disconnect", foreground=TH["red"])
        self._pres_changes_box.tag_configure("error", foreground=TH["red"],
                                              font=("Consolas", 9, "bold"))
        self._pres_changes_box.tag_configure("status_change", foreground=TH["yellow"])
        self._pres_changes_box.tag_configure("ts", foreground=TH["fg_dim"])

        self._pres_prev_statuses = {}
        self._pres_change_count = 0

        # -- Tab 5: Raw log --
        raw_tab = tk.Frame(detail_nb, bg=TH["card"])
        detail_nb.add(raw_tab, text="  RAW  ")
        raw_wrap = tk.Frame(raw_tab, bg=TH["card"])
        raw_wrap.pack(fill="both", expand=True, padx=10, pady=8)
        self._pres_raw_box = self._text_widget(raw_wrap, font=("Consolas", 9),
                                                state="disabled", wrap="word")
        raw_sb = self._scrollbar(raw_wrap, command=self._pres_raw_box.yview)
        self._pres_raw_box.configure(yscrollcommand=raw_sb.set)
        self._pres_raw_box.pack(side="left", fill="both", expand=True)
        raw_sb.pack(side="right", fill="y")

        pane.add(bottom, weight=2)

    # -- Presence refresh --

    def _pres_refresh(self):
        outgoing.put({"type": "req", "id": new_id("presence"),
                      "method": "system-presence", "params": {}})
        self._pres_last_refresh.config(
            text=f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")

    def _pres_toggle_poll(self):
        self._pres_polling = not self._pres_polling
        if self._pres_polling:
            self._pres_poll_label.config(text="ON", fg=TH["green"])
            self._pres_poll_tick()
        else:
            self._pres_poll_label.config(text="OFF", fg=TH["red"])

    def _pres_poll_tick(self):
        if not self._pres_polling:
            return
        self._pres_refresh()
        self.after(5000, self._pres_poll_tick)

    # -- Ping / Heartbeat --

    def _pres_ping_all(self):
        for comp in self._PRESENCE_COMPONENTS:
            self._pres_send_ping(comp["id"])

    def _pres_ping_selected(self):
        sel = self._pres_tree.selection()
        if sel:
            self._pres_send_ping(sel[0])

    def _pres_send_ping(self, comp_id):
        self._pres_hb_send_times[comp_id] = time.monotonic()
        outgoing.put({"type": "req", "id": new_id(f"hb-{comp_id}"),
                      "method": "system-ping", "params": {"target": comp_id}})

    def _pres_handle_pong(self, comp_id, payload):
        now = time.monotonic()
        send_t = self._pres_hb_send_times.pop(comp_id, None)
        hb = self._pres_heartbeats.get(comp_id, {})
        hb["last_ts"] = datetime.now().strftime("%H:%M:%S")

        if send_t is not None:
            rtt = (now - send_t) * 1000
            hb["rtt_ms"] = rtt
        else:
            hb["rtt_ms"] = None

        success = payload.get("status", "ok") != "error"
        if success:
            hb["ok_streak"] = hb.get("ok_streak", 0) + 1
            hb["fail_streak"] = 0
        else:
            hb["fail_streak"] = hb.get("fail_streak", 0) + 1
            hb["ok_streak"] = 0

        self._pres_heartbeats[comp_id] = hb
        self._pres_refresh_hb_widget(comp_id)

    def _pres_refresh_hb_widget(self, comp_id):
        w = self._pres_hb_widgets.get(comp_id)
        if not w:
            return
        hb = self._pres_heartbeats.get(comp_id, {})

        last_ts = hb.get("last_ts")
        w["ts"].config(text=f"Last HB: {last_ts}" if last_ts else "Last HB: --")

        rtt = hb.get("rtt_ms")
        if rtt is not None:
            rtt_color = TH["green"] if rtt < 100 else TH["yellow"] if rtt < 500 else TH["red"]
            w["rtt"].config(text=f"RTT: {rtt:.0f}ms", fg=rtt_color)
        else:
            w["rtt"].config(text="RTT: --", fg=TH["fg2"])

        ok = hb.get("ok_streak", 0)
        fail = hb.get("fail_streak", 0)
        if fail > 0:
            w["dot"].config(fg=TH["red"])
            w["streak"].config(text=f"FAIL x{fail}", fg=TH["red"])
        elif ok > 0:
            w["dot"].config(fg=TH["green"])
            w["streak"].config(text=f"OK x{ok}", fg=TH["green"])
        else:
            w["dot"].config(fg=TH["fg_dim"])
            w["streak"].config(text="")

    # -- Populate roster from gateway response --

    def _pres_populate(self, data):
        self._pres_data = data if isinstance(data, dict) else {}

        known_ids = {c["id"] for c in self._PRESENCE_COMPONENTS}

        if isinstance(data, list):
            entries = data
        elif isinstance(data, dict):
            entries = data.get("components", data.get("clients", []))
            if not entries and any(k in data for k in known_ids):
                entries = [{"id": k, **v} if isinstance(v, dict) else {"id": k}
                           for k, v in data.items() if k in known_ids]
        else:
            entries = []

        entry_map = {}
        for e in entries:
            if isinstance(e, dict):
                eid = e.get("id", e.get("name", ""))
                norm = self._pres_normalize_id(eid)
                if norm:
                    entry_map[norm] = e

        status_order = {"error": 0, "reconnecting": 1, "busy": 2,
                        "connected": 3, "idle": 4}

        for comp in self._PRESENCE_COMPONENTS:
            cid = comp["id"]
            entry = entry_map.get(cid, {})

            raw_status = str(entry.get("status", entry.get("state", "offline"))).lower()
            status = self._pres_normalize_status(raw_status)
            tag = status

            last_seen = entry.get("lastSeen", entry.get("last_seen",
                        entry.get("lastActivity", "")))
            last_seen_str = self._pres_format_ts(last_seen) if last_seen else "--"

            connected = entry.get("connectedSince", entry.get("connected_since",
                        entry.get("startedAt", "")))
            uptime_str = "--"
            if connected:
                uptime_str = self._pres_calc_uptime(connected)

            self._pres_tree.item(cid, values=(comp["name"], comp["kind"].capitalize(),
                                               status.capitalize(), last_seen_str,
                                               uptime_str),
                                  tags=(tag,))

            self._pres_data[cid] = entry

        self._pres_append_raw(jdump(data if not isinstance(data, dict) else
                                     {k: v for k, v in data.items()
                                      if k != "_raw"}) if data else "(empty response)")

        new_statuses = {}
        for comp in self._PRESENCE_COMPONENTS:
            cid = comp["id"]
            entry = entry_map.get(cid, {})
            raw_status = str(entry.get("status", entry.get("state", "offline"))).lower()
            new_statuses[cid] = self._pres_normalize_status(raw_status)

        if self._pres_prev_statuses:
            changes = self._pres_compute_diff(new_statuses)
            self._pres_append_changes(changes)
        else:
            self._pres_prev_statuses = dict(new_statuses)

        self._pres_draw_map()

    def _pres_normalize_id(self, raw):
        raw = str(raw).lower().strip()
        aliases = {
            "whim-ui": ["whim-ui", "whim_ui", "whimui", "ui"],
            "whim-ai": ["whim-ai", "whim_ai", "whimai", "whim.ai", "ai"],
            "gateway": ["gateway", "gw", "openclaw-gateway"],
            "ingest": ["ingest", "ingest-service", "ingest_service",
                       "journal-ingest", "transcribe"],
        }
        for cid, names in aliases.items():
            if raw in names:
                return cid
        for cid, names in aliases.items():
            for n in names:
                if n in raw or raw in n:
                    return cid
        return ""

    def _pres_normalize_status(self, raw):
        raw = raw.lower().strip()
        if raw in ("connected", "online", "ok", "up", "active"):
            return "connected"
        if raw in ("idle", "standby", "waiting"):
            return "idle"
        if raw in ("busy", "processing", "working"):
            return "busy"
        if raw in ("error", "err", "failed", "crashed"):
            return "error"
        if raw in ("reconnecting", "connecting", "retrying"):
            return "reconnecting"
        return "offline"

    def _pres_format_ts(self, ts):
        if not ts:
            return "--"
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts)
            else:
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        dt = datetime.strptime(str(ts), fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return str(ts)[:19]
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(ts)[:19]

    def _pres_calc_uptime(self, connected):
        try:
            if isinstance(connected, (int, float)):
                start = datetime.fromtimestamp(connected)
            else:
                start = None
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S"):
                    try:
                        start = datetime.strptime(str(connected), fmt)
                        break
                    except ValueError:
                        continue
            if not start:
                return "--"
            delta = datetime.now() - start
            secs = int(delta.total_seconds())
            if secs < 0:
                return "--"
            d, rem = divmod(secs, 86400)
            h, rem = divmod(rem, 3600)
            m, _ = divmod(rem, 60)
            if d > 0:
                return f"{d}d {h}h {m}m"
            if h > 0:
                return f"{h}h {m}m"
            return f"{m}m"
        except Exception:
            return "--"

    # -- Selection handler --

    def _pres_on_select(self, event=None):
        sel = self._pres_tree.selection()
        if not sel:
            self._pres_detail_name.config(text="")
            for attr in ("_pres_d_status", "_pres_d_connected", "_pres_d_lastseen",
                         "_pres_d_uptime", "_pres_d_version", "_pres_d_endpoint",
                         "_pres_d_error"):
                getattr(self, attr).config(text="--")
            return
        cid = sel[0]
        comp_name = next((c["name"] for c in self._PRESENCE_COMPONENTS
                          if c["id"] == cid), cid)
        self._pres_detail_name.config(text=comp_name)

        entry = self._pres_data.get(cid, {}) if isinstance(self._pres_data, dict) else {}
        raw_status = str(entry.get("status", entry.get("state", "offline"))).lower()
        status = self._pres_normalize_status(raw_status)

        status_colors = {"connected": TH["green"], "idle": TH["yellow"],
                         "busy": "#e08020", "error": TH["red"],
                         "reconnecting": "#c060c0", "offline": TH["fg_dim"]}
        self._pres_d_status.config(text=status.capitalize(),
                                    fg=status_colors.get(status, TH["fg"]))

        connected = entry.get("connectedSince", entry.get("connected_since",
                    entry.get("startedAt", "")))
        self._pres_d_connected.config(
            text=self._pres_format_ts(connected) if connected else "--")

        last_seen = entry.get("lastSeen", entry.get("last_seen",
                    entry.get("lastActivity", "")))
        self._pres_d_lastseen.config(
            text=self._pres_format_ts(last_seen) if last_seen else "--")

        self._pres_d_uptime.config(
            text=self._pres_calc_uptime(connected) if connected else "--")

        self._pres_d_version.config(
            text=entry.get("version", entry.get("ver", "--")))

        self._pres_d_endpoint.config(
            text=entry.get("endpoint", entry.get("url",
                 entry.get("address", "--"))))

        err = entry.get("error", entry.get("lastError", ""))
        self._pres_d_error.config(text=str(err)[:120] if err else "--",
                                   fg=TH["red"] if err else TH["fg_dim"])

    # -- Raw log append --

    def _pres_append_raw(self, text):
        self._pres_raw_box.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self._pres_raw_box.insert("end", f"[{ts}] {text}\n\n")
        self._pres_raw_box.see("end")
        self._pres_raw_box.config(state="disabled")

    # -- Presence Map --

    _PRES_MAP_TOPOLOGY = [
        ("whim-ui",       "gateway"),
        ("whim-ai",       "gateway"),
        ("gateway",       "ingest"),
    ]

    _PRES_MAP_LAYOUT = {
        "whim-ui":       (0.15, 0.25),
        "whim-ai":       (0.15, 0.75),
        "gateway":       (0.50, 0.50),
        "ingest":        (0.85, 0.50),
    }

    def _pres_draw_map(self):
        c = self._pres_map_canvas
        c.delete("all")
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 50 or ch < 50:
            return

        node_r = 28
        self._pres_map_node_positions = {}

        comp_map = {comp["id"]: comp for comp in self._PRESENCE_COMPONENTS}
        status_colors = {
            "connected": TH["green"], "idle": TH["yellow"], "busy": "#e08020",
            "error": TH["red"], "reconnecting": "#c060c0", "offline": TH["fg_dim"],
        }

        def get_status(cid):
            vals = self._pres_tree.item(cid, "values")
            return self._pres_normalize_status(vals[2].lower()) if vals and len(vals) > 2 else "offline"

        for cid, (fx, fy) in self._PRES_MAP_LAYOUT.items():
            x = int(cw * fx)
            y = int(ch * fy)
            self._pres_map_node_positions[cid] = (x, y)

        for src, dst in self._PRES_MAP_TOPOLOGY:
            if src not in self._pres_map_node_positions or dst not in self._pres_map_node_positions:
                continue
            x1, y1 = self._pres_map_node_positions[src]
            x2, y2 = self._pres_map_node_positions[dst]
            src_st = get_status(src)
            dst_st = get_status(dst)

            if src_st == "error" or dst_st == "error":
                link_color = TH["red"]
                dash = (6, 4)
            elif src_st == "offline" or dst_st == "offline":
                link_color = TH["fg_dim"]
                dash = (4, 4)
            elif src_st == "reconnecting" or dst_st == "reconnecting":
                link_color = "#c060c0"
                dash = (6, 3)
            elif src_st in ("connected", "idle", "busy") and dst_st in ("connected", "idle", "busy"):
                link_color = TH["green"]
                dash = ()
            else:
                link_color = TH["yellow"]
                dash = (8, 4)

            c.create_line(x1, y1, x2, y2, fill=link_color, width=2, dash=dash)

            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            c.create_text(mx, my - 8, text="\u2194 WS", fill=link_color,
                          font=("Consolas", 7))

        for cid, (x, y) in self._pres_map_node_positions.items():
            comp = comp_map.get(cid, {})
            status = get_status(cid)
            color = status_colors.get(status, TH["fg_dim"])
            fill = TH["card"]

            c.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                          fill=fill, outline=color, width=3)

            c.create_text(x, y - 4, text=comp.get("name", cid),
                          fill=TH["fg"], font=("Segoe UI", 8, "bold"),
                          width=node_r * 2.2)

            c.create_text(x, y + node_r + 10, text=status.upper(),
                          fill=color, font=("Consolas", 7, "bold"))

        legend_x = 10
        legend_y = ch - 60
        legend_items = [
            (TH["green"], "\u2500\u2500", "Healthy"),
            (TH["yellow"], "- - -", "Degraded"),
            (TH["red"], "- - -", "Error"),
            (TH["fg_dim"], "\u00b7\u00b7\u00b7", "Offline"),
        ]
        for i, (lc, ls, lt) in enumerate(legend_items):
            ly = legend_y + i * 14
            c.create_text(legend_x, ly, text=f"{ls} {lt}", fill=lc,
                          font=("Consolas", 7), anchor="w")

    # -- What Changed? diff --

    def _pres_compute_diff(self, new_statuses):
        changes = []
        now_str = datetime.now().strftime("%H:%M:%S")
        prev = self._pres_prev_statuses

        for cid in {*prev.keys(), *new_statuses.keys()}:
            old_st = prev.get(cid, "offline")
            new_st = new_statuses.get(cid, "offline")

            if old_st == new_st:
                continue

            comp_name = next((c["name"] for c in self._PRESENCE_COMPONENTS
                              if c["id"] == cid), cid)

            if old_st == "offline" and new_st in ("connected", "idle", "busy"):
                changes.append(("new_conn", now_str,
                                f"+ {comp_name} connected ({new_st})"))
            elif new_st == "offline" and old_st in ("connected", "idle", "busy"):
                changes.append(("disconnect", now_str,
                                f"- {comp_name} disconnected (was {old_st})"))
            elif new_st == "error":
                changes.append(("error", now_str,
                                f"! {comp_name} ERROR (was {old_st})"))
            elif old_st == "error" and new_st != "error":
                changes.append(("new_conn", now_str,
                                f"+ {comp_name} recovered -> {new_st}"))
            else:
                changes.append(("status_change", now_str,
                                f"~ {comp_name}: {old_st} -> {new_st}"))

        self._pres_prev_statuses = dict(new_statuses)
        return changes

    def _pres_append_changes(self, changes):
        if not changes:
            return
        self._pres_change_count += len(changes)
        self._pres_changes_count.config(
            text=f"{self._pres_change_count} change(s)")

        box = self._pres_changes_box
        box.config(state="normal")
        for tag, ts, text in changes:
            box.insert("end", f"[{ts}] ", "ts")
            box.insert("end", f"{text}\n", tag)
        box.insert("end", "\n")
        box.see("end")
        box.config(state="disabled")

    def _pres_clear_changes(self):
        self._pres_change_count = 0
        self._pres_changes_count.config(text="")
        self._pres_changes_box.config(state="normal")
        self._pres_changes_box.delete("1.0", "end")
        self._pres_changes_box.config(state="disabled")

    def presence_list(self):
        self._pres_refresh()

    # ==================== XTTS VOICE TAB ====================
    def build_xtts(self):
        f = self.tabs["xtts"]
        self.xtts_generating = False
        self._xtts_playing_proc = None
        self._xtts_playing_file = None
        os.makedirs(XTTS_VOICES_DIR, exist_ok=True)
        os.makedirs(os.path.join(XTTS_VOICES_DIR, "Discarded"), exist_ok=True)
        os.makedirs(TABLE_READS_DIR, exist_ok=True)

        root = tk.Frame(f, bg=TH["bg"])
        root.pack(fill="both", expand=True, padx=8, pady=8)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=2)
        root.columnconfigure(2, weight=1)
        root.rowconfigure(0, weight=1)

        # --- Left panel: voice list ---
        left = tk.Frame(root, bg=TH["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        v_card = self._card(left, "VOICES", fg="#888888")
        v_card.pack(fill="both", expand=True)

        v_btns = tk.Frame(v_card, bg=TH["card"])
        v_btns.pack(fill="x", padx=10, pady=4)
        self._btn(v_btns, "+ Add Voice", self._xtts_add_voice).pack(side="right")
        self._btn(v_btns, "- Remove Voice", self._xtts_remove_voice).pack(side="right", padx=(0, 4))
        self._btn(v_btns, "Refresh", self._xtts_refresh_voices).pack(side="right", padx=(0, 4))
        self._btn(v_btns, "Apply Voice", self._xtts_apply_voice).pack(side="right", padx=(0, 4))

        self.xtts_voice_list = tk.Listbox(
            v_card, bg=TH["input"], fg=TH["fg"], font=TH["font"],
            selectmode="single", activestyle="dotbox", bd=0,
            highlightthickness=1, highlightbackground=TH["border"],
            selectbackground=TH["select_bg"], selectforeground="#ffffff")
        self.xtts_voice_list.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.xtts_voice_list.bind("<<ListboxSelect>>", self._xtts_on_voice_select)

        v_info = tk.Frame(v_card, bg=TH["card"])
        v_info.pack(fill="x", padx=10, pady=(0, 8))
        self.xtts_voice_path_var = tk.StringVar(value="")
        tk.Label(v_info, textvariable=self.xtts_voice_path_var, bg=TH["card"],
                 fg=TH["fg2"], font=TH["font_xs"]).pack(anchor="w")
        self._btn(v_info, "Preview", self._xtts_preview_voice).pack(anchor="w", pady=2)

        self.xtts_active_voice_var = tk.StringVar(value="current voice: none")
        tk.Label(v_info, textvariable=self.xtts_active_voice_var, bg=TH["card"],
                 fg="#00ff00", font=TH["font_xs"]).pack(anchor="w", pady=(4, 0))

        # --- Center panel: generation controls ---
        center = tk.Frame(root, bg=TH["bg"])
        center.grid(row=0, column=1, sticky="nsew", padx=4)

        gen_card = self._card(center, "GENERATE", fg="#888888")
        gen_card.pack(fill="x", pady=(0, 6))

        out_row = tk.Frame(gen_card, bg=TH["card"])
        out_row.pack(fill="x", padx=10, pady=4)
        self._label(out_row, "Output WAV:", font=TH["font_sm"]).pack(side="left")
        self.xtts_out_var = tk.StringVar(value=XTTS_DEFAULT_OUT)
        self._entry(out_row, self.xtts_out_var).pack(side="left", fill="x", expand=True, padx=6)
        self._btn(out_row, "Browse...", self._xtts_browse_out).pack(side="left")

        opt_row = tk.Frame(gen_card, bg=TH["card"])
        opt_row.pack(fill="x", padx=10, pady=4)
        self._label(opt_row, "Language:", font=TH["font_sm"]).pack(side="left")
        self.xtts_lang_var = tk.StringVar(value="en")
        ttk.Combobox(opt_row, textvariable=self.xtts_lang_var, width=6,
                     values=["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru",
                             "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"]).pack(side="left", padx=8)
        self.xtts_gpu_var = tk.BooleanVar(value=True)
        tk.Checkbutton(opt_row, text="GPU", variable=self.xtts_gpu_var,
                        bg=TH["card"], fg=TH["fg"], selectcolor=TH["input"],
                        activebackground=TH["card"], activeforeground=TH["fg"],
                        font=TH["font_sm"], highlightthickness=0).pack(side="left", padx=8)

        self._label(gen_card, "Text to speak:", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(4, 0))
        self.xtts_text = self._text_widget(gen_card, font=("Segoe UI", 11), height=4, wrap="word")
        self.xtts_text.pack(fill="x", padx=10, pady=4)
        self.xtts_text.insert("1.0", "Hello from Whim")

        btn_row = tk.Frame(gen_card, bg=TH["card"])
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        self.xtts_gen_btn = self._btn(btn_row, "Generate", self._xtts_generate)
        self.xtts_gen_btn.pack(side="left", padx=(0, 4))
        self._btn(btn_row, "Play Output", self._xtts_play).pack(side="left", padx=(0, 4))
        self._btn(btn_row, "Save to TableReads", self._xtts_save_tableread).pack(side="left")

        # --- Voice Shaping ---
        shape_card = self._card(center, "VOICE SHAPING", fg="#888888")
        shape_card.pack(fill="x", pady=(0, 6))

        self._xtts_shape_vars = {}
        shape_defs = [
            ("temperature",       "Temperature",       0.1, 1.5, 0.65, 0.05,
             "Creativity / emotion. Higher = more expressive, lower = more stable"),
            ("speed",             "Speed",             0.5, 2.0, 1.0,  0.05,
             "Playback rate. <1 slower, >1 faster (artifacts beyond 0.7-1.3)"),
            ("repetition_penalty","Rep. Penalty",      1.0, 5.0, 2.0,  0.1,
             "Prevents loops & repeated syllables. Higher = stricter"),
            ("length_penalty",    "Length Penalty",     0.5, 2.0, 1.0,  0.1,
             "Controls output length. >1 longer phrases, <1 shorter"),
            ("top_p",             "Top-P",             0.1, 1.0, 0.8,  0.05,
             "Nucleus sampling. Lower = safer / flatter delivery"),
            ("top_k",             "Top-K",             1,   100, 50,   1,
             "Token diversity. Lower = more predictable"),
        ]

        for key, label, lo, hi, default, res, tip in shape_defs:
            row = tk.Frame(shape_card, bg=TH["card"])
            row.pack(fill="x", padx=10, pady=1)
            lbl = tk.Label(row, text=label, bg=TH["card"], fg=TH["fg2"],
                           font=TH["font_xs"], width=12, anchor="w")
            lbl.pack(side="left")
            var = tk.DoubleVar(value=default)
            self._xtts_shape_vars[key] = (var, default)
            val_lbl = tk.Label(row, text=f"{default:.2f}" if isinstance(default, float) else str(int(default)),
                               bg=TH["card"], fg=TH["green"], font=TH["font_xs"], width=5)
            val_lbl.pack(side="right")
            scale = tk.Scale(row, variable=var, from_=lo, to=hi, resolution=res,
                             orient="horizontal", bg=TH["card"], fg=TH["fg"],
                             troughcolor=TH["input"], highlightthickness=0,
                             sliderrelief="flat", bd=0, showvalue=False,
                             activebackground=TH["btn_hover"],
                             command=lambda v, vl=val_lbl, k=key: vl.config(
                                 text=f"{float(v):.2f}" if k != "top_k" else str(int(float(v)))))
            scale.pack(side="left", fill="x", expand=True, padx=4)
            lbl.bind("<Enter>", lambda e, t=tip, w=lbl: self._xtts_show_tip(w, t))
            lbl.bind("<Leave>", lambda e: self._xtts_hide_tip())

        tk.Frame(shape_card, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(4, 2))

        post_label = tk.Label(shape_card, text="POST-PROCESSING (ffmpeg)", bg=TH["card"],
                              fg=TH["fg2"], font=TH["font_xs"], anchor="w")
        post_label.pack(fill="x", padx=10)

        self._xtts_post_vars = {}
        post_defs = [
            ("warmth",     "Warmth",       0, 100, 0, 1,
             "Low-frequency boost for a warmer, fuller sound"),
            ("brightness", "Brightness",   0, 100, 0, 1,
             "High-frequency lift for clarity and air"),
            ("reverb",     "Reverb",       0, 100, 0, 1,
             "Room ambience (dry=0, cathedral=100)"),
            ("compression","Compression",  0, 100, 0, 1,
             "Dynamic range compression for a more even, broadcast feel"),
            ("pause_pre",  "Pause Before", 0, 3000, 0, 50,
             "Silence in ms inserted before speech"),
            ("pause_post", "Pause After",  0, 3000, 0, 50,
             "Silence in ms appended after speech"),
        ]

        for key, label, lo, hi, default, res, tip in post_defs:
            row = tk.Frame(shape_card, bg=TH["card"])
            row.pack(fill="x", padx=10, pady=1)
            lbl = tk.Label(row, text=label, bg=TH["card"], fg=TH["fg2"],
                           font=TH["font_xs"], width=12, anchor="w")
            lbl.pack(side="left")
            var = tk.IntVar(value=default)
            self._xtts_post_vars[key] = (var, default)
            unit = "ms" if "pause" in key else "%"
            val_lbl = tk.Label(row, text=f"{default}{unit}",
                               bg=TH["card"], fg=TH["green"], font=TH["font_xs"], width=6)
            val_lbl.pack(side="right")
            scale = tk.Scale(row, variable=var, from_=lo, to=hi, resolution=res,
                             orient="horizontal", bg=TH["card"], fg=TH["fg"],
                             troughcolor=TH["input"], highlightthickness=0,
                             sliderrelief="flat", bd=0, showvalue=False,
                             activebackground=TH["btn_hover"],
                             command=lambda v, vl=val_lbl, u=unit: vl.config(
                                 text=f"{int(float(v))}{u}"))
            scale.pack(side="left", fill="x", expand=True, padx=4)
            lbl.bind("<Enter>", lambda e, t=tip, w=lbl: self._xtts_show_tip(w, t))
            lbl.bind("<Leave>", lambda e: self._xtts_hide_tip())

        tk.Frame(shape_card, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(4, 2))

        preset_row = tk.Frame(shape_card, bg=TH["card"])
        preset_row.pack(fill="x", padx=10, pady=(2, 6))
        presets = [
            ("Neutral",  dict(temperature=0.65, speed=1.0, repetition_penalty=2.0,
                              length_penalty=1.0, top_p=0.8, top_k=50,
                              warmth=0, brightness=0, reverb=0, compression=0,
                              pause_pre=0, pause_post=0)),
            ("Warm",     dict(temperature=0.75, speed=0.92, repetition_penalty=2.0,
                              length_penalty=1.1, top_p=0.85, top_k=60,
                              warmth=55, brightness=10, reverb=15, compression=20,
                              pause_pre=0, pause_post=0)),
            ("Lively",   dict(temperature=0.90, speed=1.08, repetition_penalty=1.8,
                              length_penalty=1.0, top_p=0.90, top_k=70,
                              warmth=15, brightness=45, reverb=5, compression=30,
                              pause_pre=0, pause_post=0)),
            ("Dry",      dict(temperature=0.50, speed=1.0, repetition_penalty=2.5,
                              length_penalty=1.0, top_p=0.70, top_k=40,
                              warmth=0, brightness=0, reverb=0, compression=40,
                              pause_pre=0, pause_post=0)),
            ("Gentle",   dict(temperature=0.60, speed=0.88, repetition_penalty=2.2,
                              length_penalty=1.2, top_p=0.80, top_k=50,
                              warmth=40, brightness=5, reverb=25, compression=15,
                              pause_pre=200, pause_post=300)),
            ("Dramatic",  dict(temperature=1.00, speed=0.85, repetition_penalty=1.5,
                               length_penalty=1.3, top_p=0.92, top_k=80,
                               warmth=35, brightness=30, reverb=40, compression=10,
                               pause_pre=400, pause_post=500)),
        ]
        self._xtts_presets = presets
        for name, vals in presets:
            self._btn(preset_row, name, lambda v=vals: self._xtts_apply_preset(v)).pack(
                side="left", padx=(0, 3))
        self._btn(preset_row, "Reset", self._xtts_reset_shaping).pack(side="right")

        self._xtts_tip_win = None

        # Spectrogram
        spec_card = self._card(center, "SPECTROGRAM", fg="#888888")
        spec_card.pack(fill="both", expand=True, pady=(0, 6))
        self.xtts_spec_canvas = tk.Canvas(spec_card, bg=TH["input"], height=120,
                                           highlightthickness=0, bd=0)
        self.xtts_spec_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.xtts_spec_canvas.create_text(
            200, 60, text="Generate or play audio to see spectrogram",
            fill=TH["fg_dim"], font=TH["font_sm"], anchor="center")

        # Output log
        log_card = self._card(center, "OUTPUT", fg="#888888")
        log_card.pack(fill="both", expand=True)
        log_inner = tk.Frame(log_card, bg=TH["card"])
        log_inner.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.xtts_log = self._text_widget(log_inner, fg=TH["fg2"], state="disabled")
        xtts_sb = self._scrollbar(log_inner, command=self.xtts_log.yview)
        self.xtts_log.configure(yscrollcommand=xtts_sb.set)
        self.xtts_log.pack(side="left", fill="both", expand=True)
        xtts_sb.pack(side="right", fill="y")

        # --- Right panel: TableReads ---
        right = tk.Frame(root, bg=TH["bg"])
        right.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        tr_card = self._card(right, "TABLE READS", fg="#888888")
        tr_card.pack(fill="both", expand=True)

        tr_btns = tk.Frame(tr_card, bg=TH["card"])
        tr_btns.pack(fill="x", padx=10, pady=4)
        self._btn(tr_btns, "Refresh", self._tr_refresh).pack(side="right")

        tr_scroll_frame = tk.Frame(tr_card, bg=TH["card"])
        tr_scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tr_canvas = tk.Canvas(tr_scroll_frame, bg=TH["input"], highlightthickness=0, bd=0)
        tr_scrollbar = self._scrollbar(tr_scroll_frame, command=self.tr_canvas.yview)
        self.tr_inner = tk.Frame(self.tr_canvas, bg=TH["input"])

        self.tr_inner.bind("<Configure>", lambda e: self.tr_canvas.configure(scrollregion=self.tr_canvas.bbox("all")))
        self.tr_canvas.create_window((0, 0), window=self.tr_inner, anchor="nw")
        self.tr_canvas.configure(yscrollcommand=tr_scrollbar.set)

        self.tr_canvas.pack(side="left", fill="both", expand=True)
        tr_scrollbar.pack(side="right", fill="y")

        self.tr_canvas.bind_all("<Button-4>", lambda e: self.tr_canvas.yview_scroll(-1, "units"))
        self.tr_canvas.bind_all("<Button-5>", lambda e: self.tr_canvas.yview_scroll(1, "units"))

        self._xtts_refresh_voices()
        self._tr_refresh()
        self._xtts_load_active_voice_label()

    def _xtts_load_active_voice_label(self):
        active_voice_file = os.path.join(XTTS_VOICES_DIR, "active_voice.json")
        try:
            if os.path.isfile(active_voice_file):
                with open(active_voice_file, "r") as f:
                    data = json.load(f)
                name = data.get("name", "")
                if name:
                    self.xtts_active_voice_var.set(f"current voice: {name}")
                    return
        except Exception:
            pass
        self.xtts_active_voice_var.set("current voice: none")

    def _xtts_apply_voice(self):
        sel = self.xtts_voice_list.curselection()
        if not sel:
            self._xtts_log_msg("No voice selected to apply.")
            return
        name = self.xtts_voice_list.get(sel[0])
        self._xtts_save_active_voice(name)
        self.xtts_active_voice_var.set(f"current voice: {name}")
        self._xtts_log_msg(f"Applied voice: {name}")

    def _xtts_scan_voices(self):
        voices = {}
        for d in [XTTS_VOICES_DIR, os.path.expanduser("~")]:
            if not os.path.isdir(d):
                continue
            for fname in sorted(os.listdir(d)):
                if fname.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
                    name = os.path.splitext(fname)[0]
                    if name not in voices:
                        voices[name] = os.path.join(d, fname)
        return voices

    def _xtts_refresh_voices(self):
        self.xtts_voices = self._xtts_scan_voices()
        self.xtts_voice_list.delete(0, "end")
        for name in self.xtts_voices:
            self.xtts_voice_list.insert("end", name)
        if self.xtts_voices:
            self.xtts_voice_list.selection_set(0)
            self._xtts_on_voice_select(None)
        self._xtts_log_msg(f"🔄 Found {len(self.xtts_voices)} voice(s)")

    def _xtts_on_voice_select(self, _event):
        sel = self.xtts_voice_list.curselection()
        if not sel:
            self.xtts_voice_path_var.set("")
            return
        name = self.xtts_voice_list.get(sel[0])
        self.xtts_voice_path_var.set(self.xtts_voices.get(name, ""))
        self._xtts_save_active_voice(name)

    def _xtts_save_active_voice(self, name):
        path = self.xtts_voices.get(name, "")
        if not path:
            return
        active_voice_file = os.path.join(XTTS_VOICES_DIR, "active_voice.json")
        try:
            data = {"name": name, "file": os.path.basename(path)}
            with open(active_voice_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _xtts_get_selected_voice(self):
        sel = self.xtts_voice_list.curselection()
        if not sel:
            return None
        return self.xtts_voices.get(self.xtts_voice_list.get(sel[0]))

    def _xtts_add_voice(self):
        paths = filedialog.askopenfilenames(
            title="Select voice reference audio",
            filetypes=[("Audio files", "*.wav *.mp3 *.flac *.ogg"), ("All files", "*.*")])
        if not paths:
            return
        for src in paths:
            dst = os.path.join(XTTS_VOICES_DIR, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
            self._xtts_log_msg(f"➕ Added voice: {os.path.basename(src)}")
        self._xtts_refresh_voices()

    def _xtts_remove_voice(self):
        sel = self.xtts_voice_list.curselection()
        if not sel:
            self._xtts_log_msg("❌ No voice selected to remove.")
            return
        name = self.xtts_voice_list.get(sel[0])
        path = self.xtts_voices.get(name)
        if not path or not os.path.isfile(path):
            self._xtts_log_msg("❌ Voice file not found.")
            return
        discard_dir = os.path.join(XTTS_VOICES_DIR, "Discarded")
        os.makedirs(discard_dir, exist_ok=True)
        dest = os.path.join(discard_dir, os.path.basename(path))
        shutil.move(path, dest)
        self._xtts_log_msg(f"🗑 Removed voice: {name} → Discarded/")
        self._xtts_refresh_voices()

    def _xtts_preview_voice(self):
        path = self._xtts_get_selected_voice()
        if not path or not os.path.isfile(path):
            self._xtts_log_msg("❌ No voice selected or file missing.")
            return
        self._xtts_log_msg(f"▶ Previewing {os.path.basename(path)}…")
        threading.Thread(
            target=lambda: subprocess.run(
                ["ffplay", "-autoexit", "-nodisp", path], capture_output=True),
            daemon=True).start()

    def _xtts_browse_out(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".wav", filetypes=[("WAV files", "*.wav")])
        if path:
            self.xtts_out_var.set(path)

    def _xtts_log_msg(self, msg):
        self.xtts_log.config(state="normal")
        self.xtts_log.insert("end", msg + "\n")
        self.xtts_log.see("end")
        self.xtts_log.config(state="disabled")

    def _xtts_generate(self):
        if self.xtts_generating:
            return
        text = self.xtts_text.get("1.0", "end").strip()
        ref_wav = self._xtts_get_selected_voice()
        out_wav = self.xtts_out_var.get().strip()
        lang = self.xtts_lang_var.get().strip()
        gpu = self.xtts_gpu_var.get()

        if not text:
            self._xtts_log_msg("❌ No text entered.")
            return
        if not ref_wav or not os.path.isfile(ref_wav):
            self._xtts_log_msg("❌ No voice selected or reference file missing.")
            return
        if not os.path.isfile(XTTS_CONDA_PYTHON):
            self._xtts_log_msg(f"❌ Conda xtts python not found: {XTTS_CONDA_PYTHON}")
            return

        shape = self._xtts_get_shape_params()
        self.xtts_generating = True
        self.xtts_gen_btn.config(state="disabled")
        shape_info = (f"temp={shape['temperature']:.2f} spd={shape['speed']:.2f} "
                      f"rep={shape['repetition_penalty']:.1f} len={shape['length_penalty']:.1f} "
                      f"p={shape['top_p']:.2f} k={int(shape['top_k'])}")
        self._xtts_log_msg(f"⏳ Generating ({len(text)} chars, voice={os.path.basename(ref_wav)}, "
                           f"lang={lang})\n   {shape_info}")

        script = (
            "import sys, time, torch, torchaudio\n"
            "from TTS.tts.configs.xtts_config import XttsConfig\n"
            "from TTS.tts.models.xtts import Xtts, XttsAudioConfig, XttsArgs\n"
            "from TTS.config.shared_configs import BaseDatasetConfig\n"
            "torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])\n"
            "config = XttsConfig()\n"
            "from TTS.api import TTS as _TTS\n"
            f"_t = _TTS({XTTS_MODEL!r}, gpu={gpu})\n"
            "model = _t.synthesizer.tts_model\n"
            f"gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(audio_path=[{ref_wav!r}])\n"
            "t0 = time.time()\n"
            "out = model.inference(\n"
            f"    {text!r},\n"
            f"    {lang!r},\n"
            "    gpt_cond_latent,\n"
            "    speaker_embedding,\n"
            f"    temperature={shape['temperature']},\n"
            f"    speed={shape['speed']},\n"
            f"    length_penalty={shape['length_penalty']},\n"
            f"    repetition_penalty={shape['repetition_penalty']},\n"
            f"    top_p={shape['top_p']},\n"
            f"    top_k={int(shape['top_k'])},\n"
            "    enable_text_splitting=True,\n"
            ")\n"
            "wav = torch.tensor(out['wav']).unsqueeze(0)\n"
            f"torchaudio.save({out_wav!r}, wav, 24000)\n"
            "elapsed = time.time() - t0\n"
            "audio_dur = wav.shape[-1] / 24000\n"
            "rtf = elapsed / audio_dur if audio_dur > 0 else 0\n"
            f"print('Wrote ' + {out_wav!r})\n"
            "print(f'processing time: {elapsed:.2f}sec')\n"
            "print(f'real-time factor: {rtf:.2f}')\n"
        )

        def run():
            try:
                proc = subprocess.run(
                    [XTTS_CONDA_PYTHON, "-c", script],
                    capture_output=True, text=True, timeout=300)
                if proc.returncode == 0:
                    self.after(0, lambda: self._xtts_log_msg(f"✅ Generated: {out_wav}"))
                    if proc.stdout.strip():
                        self.after(0, lambda: self._xtts_log_msg(proc.stdout.strip()))
                    pp_ok = self._xtts_postprocess(out_wav)
                    if pp_ok:
                        pp = self._xtts_get_post_params()
                        if any(pp[k] for k in pp):
                            self.after(0, lambda: self._xtts_log_msg("✅ Post-processing applied"))
                else:
                    err = proc.stderr.strip()
                    self.after(0, lambda: self._xtts_log_msg(f"❌ Error (exit {proc.returncode}):\n{err}"))
            except subprocess.TimeoutExpired:
                self.after(0, lambda: self._xtts_log_msg("❌ Generation timed out (5 min)."))
            except Exception as e:
                self.after(0, lambda: self._xtts_log_msg(f"❌ {e}"))
            finally:
                self.after(0, self._xtts_gen_done)

        threading.Thread(target=run, daemon=True).start()

    def _xtts_gen_done(self):
        self.xtts_generating = False
        self.xtts_gen_btn.config(state="normal")
        self._xtts_draw_spectrogram()

    def _xtts_apply_preset(self, vals):
        for key, (var, _default) in self._xtts_shape_vars.items():
            if key in vals:
                var.set(vals[key])
        for key, (var, _default) in self._xtts_post_vars.items():
            if key in vals:
                var.set(vals[key])
        self._xtts_log_msg("Preset applied")

    def _xtts_reset_shaping(self):
        for key, (var, default) in self._xtts_shape_vars.items():
            var.set(default)
        for key, (var, default) in self._xtts_post_vars.items():
            var.set(default)
        self._xtts_log_msg("Voice shaping reset to defaults")

    def _xtts_show_tip(self, widget, text):
        self._xtts_hide_tip()
        x = widget.winfo_rootx() + widget.winfo_width()
        y = widget.winfo_rooty()
        self._xtts_tip_win = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x+4}+{y}")
        lbl = tk.Label(tw, text=text, bg="#1a1a2e", fg="#e0e0e0",
                       font=("Segoe UI", 8), padx=6, pady=3, relief="solid", bd=1)
        lbl.pack()

    def _xtts_hide_tip(self):
        if self._xtts_tip_win:
            self._xtts_tip_win.destroy()
            self._xtts_tip_win = None

    def _xtts_get_shape_params(self):
        return {k: var.get() for k, (var, _) in self._xtts_shape_vars.items()}

    def _xtts_get_post_params(self):
        return {k: var.get() for k, (var, _) in self._xtts_post_vars.items()}

    def _xtts_postprocess(self, wav_path):
        pp = self._xtts_get_post_params()
        warmth = pp["warmth"]
        brightness = pp["brightness"]
        reverb = pp["reverb"]
        compression = pp["compression"]
        pause_pre = pp["pause_pre"]
        pause_post = pp["pause_post"]

        if not any([warmth, brightness, reverb, compression, pause_pre, pause_post]):
            return True

        tmp_path = wav_path + ".tmp.wav"
        filters = []

        if warmth > 0:
            gain = warmth * 0.08
            filters.append(f"lowshelf=g={gain:.1f}:f=300:t=s")
        if brightness > 0:
            gain = brightness * 0.06
            filters.append(f"highshelf=g={gain:.1f}:f=4000:t=s")
        if compression > 0:
            threshold = max(-40, -40 + (100 - compression) * 0.35)
            ratio = 2 + compression * 0.06
            filters.append(f"acompressor=threshold={threshold:.0f}dB:ratio={ratio:.1f}:attack=5:release=50")
        if reverb > 0:
            wet = reverb / 100.0
            delays = int(20 + reverb * 0.6)
            decays = min(0.7, reverb * 0.007)
            filters.append(f"aecho=0.8:{wet:.2f}:{delays}:{decays:.2f}")

        pad_parts = []
        if pause_pre > 0:
            pad_parts.append(f"adelay={pause_pre}|{pause_pre}")
        if pause_post > 0:
            pad_parts.append(f"apad=pad_dur={pause_post / 1000.0:.3f}")
        filters.extend(pad_parts)

        if not filters:
            return True

        af = ",".join(filters)
        cmd = ["ffmpeg", "-y", "-i", wav_path, "-af", af, tmp_path]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                shutil.move(tmp_path, wav_path)
                return True
            else:
                self.after(0, lambda: self._xtts_log_msg(
                    f"Post-processing error: {proc.stderr.strip()[-200:]}"))
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
                return False
        except Exception as e:
            self.after(0, lambda: self._xtts_log_msg(f"Post-processing failed: {e}"))
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
            return False

    def _xtts_draw_spectrogram(self, wav_path=None):
        if wav_path is None:
            wav_path = self.xtts_out_var.get().strip()
        if not wav_path or not os.path.isfile(wav_path):
            return
        self._spec_index_line = None
        try:
            import wave
            import numpy as np
            with wave.open(wav_path, "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                fr = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
            self._spec_audio_duration = nframes / fr if fr > 0 else 0
            dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sw, np.int16)
            samples = np.frombuffer(raw, dtype=dtype).astype(np.float64)
            if nch > 1:
                samples = samples[::nch]
            canvas = self.xtts_spec_canvas
            canvas.update_idletasks()
            cw = max(canvas.winfo_width(), 200)
            ch = max(canvas.winfo_height(), 80)
            canvas.delete("all")
            # Compute spectrogram via STFT
            win_size = 512
            hop = win_size // 2
            n_bins = win_size // 2
            n_steps = max(1, (len(samples) - win_size) // hop)
            window = np.hanning(win_size)
            spec = np.zeros((n_bins, n_steps))
            for i in range(n_steps):
                seg = samples[i * hop: i * hop + win_size]
                if len(seg) < win_size:
                    break
                fft = np.abs(np.fft.rfft(seg * window))[:n_bins]
                spec[:, i] = fft
            spec = np.log1p(spec)
            if spec.max() > 0:
                spec = spec / spec.max()
            # Render as colored vertical lines
            x_scale = cw / max(n_steps, 1)
            y_scale = ch / max(n_bins, 1)
            for xi in range(0, cw, 2):
                col_idx = int(xi / x_scale)
                if col_idx >= n_steps:
                    break
                column = spec[:, col_idx]
                for yi in range(0, ch, 3):
                    bin_idx = n_bins - 1 - int(yi / y_scale)
                    if bin_idx < 0:
                        break
                    val = column[bin_idx]
                    r = int(20 + val * 100)
                    g = int(80 + val * 100)
                    b = int(50 + val * 150)
                    color = f"#{min(r,255):02x}{min(g,255):02x}{min(b,255):02x}"
                    canvas.create_rectangle(xi, yi, xi+2, yi+3, fill=color, outline="")
        except Exception as e:
            self.xtts_spec_canvas.delete("all")
            self.xtts_spec_canvas.create_text(
                100, 40, text=f"Spectrogram error: {e}",
                fill=TH["red"], font=TH["font_xs"], anchor="w")

    def _spec_animate_index(self):
        import time
        canvas = self.xtts_spec_canvas
        if not hasattr(self, '_spec_play_start') or not hasattr(self, '_spec_audio_duration'):
            return
        duration = self._spec_audio_duration
        if duration <= 0:
            return
        elapsed = time.time() - self._spec_play_start
        if elapsed > duration:
            if self._spec_index_line:
                canvas.delete(self._spec_index_line)
                self._spec_index_line = None
            return
        canvas.update_idletasks()
        cw = max(canvas.winfo_width(), 200)
        ch = max(canvas.winfo_height(), 80)
        x = int((elapsed / duration) * cw)
        if self._spec_index_line:
            canvas.delete(self._spec_index_line)
        self._spec_index_line = canvas.create_line(x, 0, x, ch, fill="#ff3333", width=2)
        self.after(33, self._spec_animate_index)

    def _xtts_play(self):
        import time as _time
        out_wav = self.xtts_out_var.get().strip()
        if not os.path.isfile(out_wav):
            self._xtts_log_msg(f"❌ Output file not found: {out_wav}")
            return
        self._xtts_draw_spectrogram(out_wav)
        self._xtts_log_msg(f"▶ Playing {out_wav}…")
        self._spec_play_start = _time.time()
        self._spec_animate_index()
        threading.Thread(
            target=lambda: subprocess.run(
                ["ffplay", "-autoexit", "-nodisp", out_wav], capture_output=True),
            daemon=True).start()

    def _xtts_save_tableread(self):
        out_wav = self.xtts_out_var.get().strip()
        if not os.path.isfile(out_wav):
            self._xtts_log_msg("❌ No output file to save.")
            return
        sel = self.xtts_voice_list.curselection()
        voice_name = self.xtts_voice_list.get(sel[0]) if sel else "unknown"
        voice_name = voice_name.lower().replace(" ", "_")
        existing = [f for f in os.listdir(TABLE_READS_DIR)
                    if f.startswith(f"tableread_{voice_name}_") and f.endswith(".wav")]
        next_num = len(existing) + 1
        dest = os.path.join(TABLE_READS_DIR, f"tableread_{voice_name}_{next_num:03d}.wav")
        shutil.copy2(out_wav, dest)
        self._xtts_log_msg(f"💾 Saved to {dest}")
        self._tr_refresh()

    def _tr_refresh(self):
        for widget in self.tr_inner.winfo_children():
            widget.destroy()
        if not os.path.isdir(TABLE_READS_DIR):
            return
        files = sorted(
            [f for f in os.listdir(TABLE_READS_DIR) if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg"))],
            reverse=True)
        if not files:
            tk.Label(self.tr_inner, text="No saved reads yet.", bg=TH["input"],
                     fg=TH["fg2"], font=TH["font_sm"]).pack(anchor="w", padx=4, pady=4)
            return
        for fname in files:
            fpath = os.path.join(TABLE_READS_DIR, fname)
            row = tk.Frame(self.tr_inner, bg=TH["input"])
            row.pack(fill="x", padx=4, pady=2)
            tk.Label(row, text=fname, bg=TH["input"], fg="#cccccc",
                     font=TH["font_xs"], anchor="w").pack(side="left", fill="x", expand=True)
            self._btn(row, "Play", lambda p=fpath: self._tr_play_pause(p)).pack(side="right", padx=2)

    def _tr_play_pause(self, filepath):
        if self._xtts_playing_proc and self._xtts_playing_proc.poll() is None:
            if self._xtts_playing_file == filepath:
                self._xtts_playing_proc.terminate()
                self._xtts_playing_proc = None
                self._xtts_playing_file = None
                self._xtts_log_msg(f"⏸ Stopped {os.path.basename(filepath)}")
                return
            else:
                self._xtts_playing_proc.terminate()
                self._xtts_playing_proc = None
                self._xtts_playing_file = None
        self._xtts_log_msg(f"▶ Playing {os.path.basename(filepath)}…")
        self._xtts_playing_file = filepath
        self._xtts_playing_proc = subprocess.Popen(
            ["ffplay", "-autoexit", "-nodisp", filepath],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ==================== HEAR ME OUT TAB ====================
    AUDIO_JR_DIR = os.path.expanduser("~/audioJR")
    _hmo_server = None
    _hmo_server_thread = None
    _hmo_playing_proc = None
    _hmo_paused = False
    _hmo_exported = False

    _HMO_ICON_PNG = os.path.expanduser(
        "~/.openclaw/WhimUI/icons/audio-volume-zero-panel-24.png")

    def build_hearmeout(self):
        f = self.tabs["hearmeout"]

        root_frame = tk.Frame(f, bg=TH["bg"])
        root_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.hmo_server_status = tk.StringVar(value="Stopped")
        self.hmo_server_url = tk.StringVar(value="")
        self.hmo_port_var = tk.StringVar(value=DEFAULT_INGEST_PORT)
        self.hmo_scrub_status = tk.StringVar(value="")
        self.hmo_export_status = tk.StringVar(value="")

        # -- Top header bar --
        header_bar = tk.Frame(root_frame, bg=TH["card"], height=42)
        header_bar.pack(fill="x", pady=(0, 4))

        self._hmo_icon_img = None
        if os.path.isfile(self._HMO_ICON_PNG):
            try:
                self._hmo_icon_img = tk.PhotoImage(file=self._HMO_ICON_PNG)
            except Exception:
                pass
        if self._hmo_icon_img:
            self._hmo_icon_label = tk.Label(header_bar, image=self._hmo_icon_img,
                                             bg=TH["card"], bd=0)
        else:
            self._hmo_icon_label = tk.Label(header_bar, text="\U0001F50A",
                                             bg=TH["card"], font=("Segoe UI", 14), bd=0)
        self._hmo_icon_label.pack(side="left", padx=(12, 8), pady=8)
        self._hmo_icon_label.config(cursor="")

        self._btn(header_bar, "Upload from Phone", self._hmo_show_upload_dialog).pack(
            side="left", padx=4, pady=6)
        self._btn(header_bar, "Refresh Journal", self._hmo_refresh_files).pack(
            side="left", padx=4, pady=6)

        tk.Label(header_bar, textvariable=self.hmo_server_status, bg=TH["card"],
                 fg=TH["yellow"], font=("Consolas", 9)).pack(side="right", padx=6, pady=6)
        tk.Label(header_bar, textvariable=self.hmo_server_url, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9)).pack(side="right", padx=4, pady=6)

        # -- Three-column layout --
        columns = tk.Frame(root_frame, bg=TH["bg"])
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=1)
        columns.columnconfigure(1, weight=2)
        columns.columnconfigure(2, weight=1)
        columns.rowconfigure(0, weight=1)

        # ========== LEFT COLUMN: Audio Files ==========
        left_col = tk.Frame(columns, bg=TH["bg"])
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left_col.rowconfigure(0, weight=1)

        files_card = self._card(left_col, "AUDIO FILES", fg="#888888")
        files_card.pack(fill="both", expand=True)

        list_frame = tk.Frame(files_card, bg=TH["card"])
        list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.hmo_file_list = tk.Listbox(list_frame, bg=TH["input"], fg=TH["fg"],
                                         font=TH["font_mono"], bd=0,
                                         highlightthickness=1,
                                         highlightbackground=TH["border"],
                                         highlightcolor=TH["btn"],
                                         selectbackground=TH["select_bg"],
                                         selectforeground=TH["fg"])
        sb = self._scrollbar(list_frame)
        self.hmo_file_list.config(yscrollcommand=sb.set)
        sb.config(command=self.hmo_file_list.yview)
        self.hmo_file_list.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.hmo_file_list.bind("<<ListboxSelect>>", self._hmo_on_file_select)

        # ========== CENTER COLUMN: Spectrogram + Transport + Transcript ==========
        center_col = tk.Frame(columns, bg=TH["bg"])
        center_col.grid(row=0, column=1, sticky="nsew", padx=4)
        center_col.rowconfigure(0, weight=2)
        center_col.rowconfigure(2, weight=3)
        center_col.columnconfigure(0, weight=1)

        spec_card = self._card(center_col, "SPECTROGRAM", fg="#888888")
        spec_card.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        self.hmo_spectrogram = tk.Canvas(spec_card, bg=TH["input"], bd=0,
                                          highlightthickness=1,
                                          highlightbackground=TH["border"])
        self.hmo_spectrogram.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.hmo_spectrogram.create_text(200, 60, text="[ select an audio file ]",
                                          fill=TH["fg_dim"], font=TH["font_mono"])

        # -- Transport bar --
        transport = tk.Frame(center_col, bg=TH["card"], height=40)
        transport.grid(row=1, column=0, sticky="ew", pady=2)

        transport_inner = tk.Frame(transport, bg=TH["card"])
        transport_inner.pack(pady=6)

        _icons_dir = os.path.expanduser("~/.openclaw/WhimUI/icons")
        self._hmo_transport_imgs = {}
        for key, fname in [("play", "transport-play-28.png"),
                            ("pause", "transport-pause-28.png"),
                            ("stop", "transport-stop-28.png")]:
            p = os.path.join(_icons_dir, fname)
            if os.path.isfile(p):
                try:
                    self._hmo_transport_imgs[key] = tk.PhotoImage(file=p)
                except Exception:
                    pass

        def _make_transport_btn(parent, key, command):
            if key in self._hmo_transport_imgs:
                lbl = tk.Label(parent, image=self._hmo_transport_imgs[key],
                               bg=TH["card"], bd=0, cursor="hand2")
            else:
                fallback = {"play": "\u25B6", "pause": "\u2016", "stop": "\u25A0"}
                lbl = tk.Label(parent, text=fallback.get(key, "?"),
                               bg=TH["card"], fg=TH["fg"], font=("Segoe UI", 14),
                               bd=0, cursor="hand2")
            lbl.pack(side="left", padx=4)
            lbl.bind("<Button-1>", lambda e: command())
            return lbl

        self.hmo_play_btn = _make_transport_btn(transport_inner, "play", self._hmo_play)
        self.hmo_pause_btn = _make_transport_btn(transport_inner, "pause", self._hmo_pause)
        self.hmo_stop_btn = _make_transport_btn(transport_inner, "stop", self._hmo_stop)

        self.hmo_scrub_btn = RoundedButton(
            transport_inner, text="SCRUB", command=self._hmo_scrub,
            bg="#e08020", hover_bg="#c06a10",
            border_color=TH["btn_border"], font=TH["font_sm"])
        self.hmo_scrub_btn.pack(side="left", padx=(12, 4))

        tk.Label(transport_inner, textvariable=self.hmo_scrub_status, bg=TH["card"],
                 fg=TH["yellow"], font=("Consolas", 9)).pack(side="left", padx=6)

        # -- Transcript --
        transcript_card = self._card(center_col, "TRANSCRIPT", fg="#888888")
        transcript_card.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

        self.hmo_transcript_box = self._text_widget(transcript_card, wrap="word")
        t_sb = self._scrollbar(transcript_card)
        self.hmo_transcript_box.config(yscrollcommand=t_sb.set)
        t_sb.config(command=self.hmo_transcript_box.yview)
        t_sb.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))
        self.hmo_transcript_box.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.hmo_transcript_box.insert("1.0", "(select an audio file to view transcript)")
        self.hmo_transcript_box.config(state="disabled")

        # ========== RIGHT COLUMN: Actions + Transcript Names ==========
        right_col = tk.Frame(columns, bg=TH["bg"])
        right_col.grid(row=0, column=2, sticky="nsew", padx=(4, 0))
        right_col.rowconfigure(1, weight=1)
        right_col.columnconfigure(0, weight=1)

        export_card = self._card(right_col, "ACTIONS", fg="#888888")
        export_card.grid(row=0, column=0, sticky="new", pady=(0, 4))

        export_btn_row = tk.Frame(export_card, bg=TH["card"])
        export_btn_row.pack(fill="x", padx=10, pady=(4, 2))
        self.hmo_export_btn = RoundedButton(
            export_btn_row, text="EXPORT", command=self._hmo_export_transcript,
            bg=TH["border_hi"], hover_bg=TH["border_hi"],
            border_color=TH["btn_border"], font=TH["font_sm"])
        self.hmo_export_btn.pack(side="left", padx=(0, 4))
        self.hmo_export_btn.config(state="disabled")
        self._label(export_btn_row, text="Save transcript as .odt",
                     font=TH["font_sm"], fg=TH["fg2"]).pack(side="left", padx=6)

        export_status_row = tk.Frame(export_card, bg=TH["card"])
        export_status_row.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(export_status_row, textvariable=self.hmo_export_status, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9), anchor="w").pack(fill="x")

        lo_btn_row = tk.Frame(export_card, bg=TH["card"])
        lo_btn_row.pack(fill="x", padx=10, pady=(0, 4))
        _msword_icon_path = os.path.join(
            os.path.expanduser("~/.openclaw/WhimUI/icons/Mint-Y/apps/32/ms-word.png"))
        self._hmo_word_img = None
        if os.path.isfile(_msword_icon_path):
            try:
                self._hmo_word_img = tk.PhotoImage(file=_msword_icon_path)
            except Exception:
                pass
        if self._hmo_word_img:
            self.hmo_lo_btn = tk.Label(lo_btn_row, image=self._hmo_word_img,
                                        bg=TH["card"], cursor="hand2", bd=0)
        else:
            self.hmo_lo_btn = tk.Label(lo_btn_row, text="W", bg=TH["card"],
                                        fg=TH["btn"], font=("Segoe UI", 18, "bold"),
                                        cursor="hand2", bd=0)
        self.hmo_lo_btn.pack(side="left")
        self.hmo_lo_btn.config(state="disabled", cursor="")
        self._label(lo_btn_row, text="Open in Writer",
                     font=TH["font_sm"], fg=TH["fg_dim"]).pack(side="left", padx=6)

        del_btn_row = tk.Frame(export_card, bg=TH["card"])
        del_btn_row.pack(fill="x", padx=10, pady=(0, 10))
        self.hmo_delete_btn = RoundedButton(
            del_btn_row, text="DELETE", command=self._hmo_delete_selected,
            bg=TH["border_hi"], hover_bg=TH["border_hi"],
            border_color=TH["btn_border"], font=TH["font_sm"])
        self.hmo_delete_btn.pack(side="left")
        self.hmo_delete_btn.config(state="disabled")

        names_card = self._card(right_col, "TRANSCRIPT NAMES", fg="#888888")
        names_card.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        names_frame = tk.Frame(names_card, bg=TH["card"])
        names_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        names_frame.rowconfigure(0, weight=1)
        names_frame.columnconfigure(0, weight=1)

        self.hmo_transcript_names = tk.Listbox(names_frame, bg=TH["input"], fg=TH["fg"],
                                                font=TH["font_mono"], bd=0,
                                                highlightthickness=1,
                                                highlightbackground=TH["border"],
                                                highlightcolor=TH["btn"],
                                                selectbackground=TH["select_bg"],
                                                selectforeground=TH["fg"])
        n_sb = self._scrollbar(names_frame)
        self.hmo_transcript_names.config(yscrollcommand=n_sb.set)
        n_sb.config(command=self.hmo_transcript_names.yview)
        self.hmo_transcript_names.grid(row=0, column=0, sticky="nsew")
        n_sb.grid(row=0, column=1, sticky="ns")
        self.hmo_transcript_names.bind("<<ListboxSelect>>", self._hmo_on_transcript_select)

        self._hmo_refresh_files()

    # -- Hear Me Out handlers --
    def _hmo_refresh_files(self):
        self.hmo_file_list.delete(0, "end")
        self.hmo_transcript_names.delete(0, "end")
        self._hmo_file_paths = {}
        audio_exts = (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac",
                      ".opus", ".3gp", ".amr", ".wma", ".webm")
        dirs = [UPLOAD_DIR, self.AUDIO_JR_DIR]
        all_files = []
        for d in dirs:
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                fp = os.path.join(d, fn)
                if os.path.isfile(fp) and fn.lower().endswith(audio_exts):
                    all_files.append((fn, fp))
        all_files.sort(key=lambda x: x[0], reverse=True)
        if not all_files:
            self.hmo_file_list.insert("end", "(no audio files found)")
            return
        for fn, fp in all_files:
            self.hmo_file_list.insert("end", fn)
            self._hmo_file_paths[fn] = fp
            base, _ = os.path.splitext(fn)
            self.hmo_transcript_names.insert("end", base + ".odt")

    def _hmo_get_selected_path(self):
        sel = self.hmo_file_list.curselection()
        if not sel:
            return None
        name = self.hmo_file_list.get(sel[0])
        return self._hmo_file_paths.get(name)

    def _hmo_on_file_select(self, _event):
        path = self._hmo_get_selected_path()
        if path and os.path.isfile(path):
            self._hmo_draw_spectrogram(path)

    def _hmo_draw_spectrogram(self, wav_path):
        canvas = self.hmo_spectrogram
        canvas.delete("all")
        if not wav_path or not os.path.isfile(wav_path):
            canvas.create_text(200, 60, text="[ select an audio file ]",
                               fill=TH["fg_dim"], font=TH["font_mono"])
            return
        canvas.update_idletasks()
        target_w = max(canvas.winfo_width(), 200)
        target_h = max(canvas.winfo_height(), 80)

        def do_draw():
            try:
                tmp_wav = wav_path
                if not wav_path.lower().endswith(".wav"):
                    import tempfile
                    fd, tmp_wav = tempfile.mkstemp(suffix=".wav", prefix="hmo_spec_")
                    os.close(fd)
                    proc = subprocess.run(
                        ["ffmpeg", "-y", "-i", wav_path, "-ac", "1", "-ar", "16000", tmp_wav],
                        capture_output=True, timeout=30)
                    if proc.returncode != 0:
                        self.after(0, lambda: canvas.create_text(
                            200, 40, text="Could not decode audio",
                            fill=TH["red"], font=TH["font_xs"]))
                        return
                import wave
                import numpy as np
                with wave.open(tmp_wav, "rb") as wf:
                    nch = wf.getnchannels()
                    sw = wf.getsampwidth()
                    nframes = wf.getnframes()
                    raw = wf.readframes(nframes)
                if tmp_wav != wav_path and os.path.isfile(tmp_wav):
                    os.unlink(tmp_wav)
                dtype = {1: np.int8, 2: np.int16, 4: np.int32}.get(sw, np.int16)
                samples = np.frombuffer(raw, dtype=dtype).astype(np.float64)
                if nch > 1:
                    samples = samples[::nch]
                cw, ch = target_w, target_h
                win_size = 512
                hop = win_size // 2
                n_bins = win_size // 2
                n_steps = max(1, (len(samples) - win_size) // hop)
                window = np.hanning(win_size)
                spec = np.zeros((n_bins, n_steps))
                for i in range(n_steps):
                    seg = samples[i * hop: i * hop + win_size]
                    if len(seg) < win_size:
                        break
                    fft = np.abs(np.fft.rfft(seg * window))[:n_bins]
                    spec[:, i] = fft
                spec = np.log1p(spec)
                if spec.max() > 0:
                    spec = spec / spec.max()
                img_array = np.zeros((ch, cw, 3), dtype=np.uint8)
                x_scale = max(n_steps, 1) / cw
                y_scale = max(n_bins, 1) / ch
                for xi in range(cw):
                    col_idx = min(int(xi * x_scale), n_steps - 1)
                    column = spec[:, col_idx]
                    for yi in range(ch):
                        bin_idx = n_bins - 1 - min(int(yi * y_scale), n_bins - 1)
                        val = column[bin_idx]
                        img_array[yi, xi, 0] = min(int(20 + val * 100), 255)
                        img_array[yi, xi, 1] = min(int(80 + val * 100), 255)
                        img_array[yi, xi, 2] = min(int(50 + val * 150), 255)
                pil_img = Image.fromarray(img_array, "RGB")
                tk_img = ImageTk.PhotoImage(pil_img)

                def render():
                    canvas.delete("all")
                    self._hmo_spec_img = tk_img
                    canvas.create_image(0, 0, anchor="nw", image=tk_img)
                self.after(0, render)
            except Exception as e:
                self.after(0, lambda: canvas.create_text(
                    200, 40, text=f"Spectrogram error: {e}",
                    fill=TH["red"], font=TH["font_xs"]))
        canvas.create_text(200, 60, text="Loading spectrogram...",
                           fill=TH["fg_dim"], font=TH["font_mono"])
        threading.Thread(target=do_draw, daemon=True).start()

    def _hmo_on_transcript_select(self, _event):
        sel = self.hmo_transcript_names.curselection()
        if sel:
            self.hmo_lo_btn.config(state="normal", cursor="hand2")
            self.hmo_lo_btn.bind("<Button-1>", lambda e: self._hmo_open_libreoffice())
        else:
            self.hmo_lo_btn.config(state="disabled", cursor="")
            self.hmo_lo_btn.unbind("<Button-1>")
        self._hmo_update_delete_state()

    def _hmo_open_libreoffice(self):
        sel = self.hmo_transcript_names.curselection()
        if not sel:
            return
        odt_name = self.hmo_transcript_names.get(sel[0])
        odt_path = os.path.join(TRANSCRIPT_DIR, odt_name)
        if os.path.isfile(odt_path):
            subprocess.Popen(["libreoffice", "--writer", odt_path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self.hmo_export_status.set(f"Not found: {odt_name}")

    def _hmo_has_active_transcript(self):
        text = self.hmo_transcript_box.get("1.0", "end").strip()
        if not text:
            return False
        if text.startswith("Transcript has exported to "):
            return False
        if text == "(select an audio file to view transcript)":
            return False
        return True

    def _hmo_update_delete_state(self):
        has_transcript = self._hmo_has_active_transcript()
        odt_sel = self.hmo_transcript_names.curselection()
        has_odt_sel = bool(odt_sel)
        can_delete_odt = has_odt_sel and not has_transcript
        if has_transcript or can_delete_odt:
            self.hmo_delete_btn._bg = TH["red"]
            self.hmo_delete_btn._hover_bg = "#b33030"
            self.hmo_delete_btn._draw(TH["red"])
            self.hmo_delete_btn.config(state="normal")
        else:
            self.hmo_delete_btn._bg = TH["border_hi"]
            self.hmo_delete_btn._hover_bg = TH["border_hi"]
            self.hmo_delete_btn._draw(TH["border_hi"])
            self.hmo_delete_btn.config(state="disabled")

    def _hmo_delete_selected(self):
        has_transcript = self._hmo_has_active_transcript()
        if has_transcript:
            self.hmo_transcript_box.config(state="normal")
            self.hmo_transcript_box.delete("1.0", "end")
            self.hmo_transcript_box.insert("1.0", "(select an audio file to view transcript)")
            self.hmo_transcript_box.config(state="disabled")
            self._hmo_exported = False
            self.hmo_export_btn._bg = TH["border_hi"]
            self.hmo_export_btn._hover_bg = TH["border_hi"]
            self.hmo_export_btn._draw(TH["border_hi"])
            self.hmo_export_btn.config(state="disabled")
            self._hmo_update_delete_state()
            return
        odt_sel = self.hmo_transcript_names.curselection()
        if odt_sel:
            odt_name = self.hmo_transcript_names.get(odt_sel[0])
            odt_path = os.path.join(TRANSCRIPT_DIR, odt_name)
            if os.path.isfile(odt_path):
                try:
                    os.remove(odt_path)
                    self.hmo_export_status.set(f"Deleted: {odt_name}")
                except Exception as e:
                    self.hmo_export_status.set(f"Error: {str(e)[:40]}")
            self._hmo_update_delete_state()

    def _hmo_play(self):
        path = self._hmo_get_selected_path()
        if not path:
            return
        if self._hmo_playing_proc and self._hmo_playing_proc.poll() is None:
            self._hmo_playing_proc.terminate()
        self._hmo_playing_proc = subprocess.Popen(
            ["ffplay", "-autoexit", "-nodisp", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._hmo_paused = False

    def _hmo_pause(self):
        import signal as _sig
        if self._hmo_playing_proc and self._hmo_playing_proc.poll() is None:
            if self._hmo_paused:
                self._hmo_playing_proc.send_signal(_sig.SIGCONT)
                self._hmo_paused = False
            else:
                self._hmo_playing_proc.send_signal(_sig.SIGSTOP)
                self._hmo_paused = True

    def _hmo_stop(self):
        if self._hmo_playing_proc and self._hmo_playing_proc.poll() is None:
            self._hmo_playing_proc.terminate()
            self._hmo_playing_proc = None
        self._hmo_paused = False

    def _hmo_scrub(self):
        path = self._hmo_get_selected_path()
        if not path:
            self.hmo_scrub_status.set("No file selected")
            return
        self.hmo_scrub_status.set("Transcribing...")
        self.hmo_scrub_btn.config(state="disabled")
        self.hmo_transcript_box.config(state="normal")
        self.hmo_transcript_box.delete("1.0", "end")
        self.hmo_transcript_box.config(state="disabled")

        def run():
            transcript = None
            error = None
            try:
                import whisper
                if not hasattr(self, "_whisper_model"):
                    self.after(0, lambda: self.hmo_scrub_status.set("Loading Whisper model..."))
                    self._whisper_model = whisper.load_model("base")
                result = self._whisper_model.transcribe(path)
                transcript = result.get("text", "").strip()
            except Exception as e:
                error = str(e)
            finally:
                self.after(0, lambda: self._hmo_scrub_done(transcript, error))

        threading.Thread(target=run, daemon=True).start()

    def _hmo_scrub_done(self, transcript, error):
        self.hmo_scrub_btn.config(state="normal")
        if error:
            self.hmo_scrub_status.set(f"Error: {error[:60]}")
            return
        self.hmo_scrub_status.set("Done")
        self._hmo_exported = False
        self.hmo_transcript_box.config(state="normal", fg=TH["fg"])
        self.hmo_transcript_box.delete("1.0", "end")
        self.hmo_transcript_box.insert("1.0", transcript)
        self.hmo_transcript_box.config(state="disabled")
        self.hmo_export_btn._bg = TH["green"]
        self.hmo_export_btn._hover_bg = "#248a5e"
        self.hmo_export_btn._draw(TH["green"])
        self.hmo_export_btn.config(state="normal")
        self._hmo_update_delete_state()

    def _hmo_export_transcript(self):
        transcript = self.hmo_transcript_box.get("1.0", "end").strip()
        if not transcript or self._hmo_exported:
            return
        os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
        sel = self.hmo_file_list.curselection()
        if sel:
            base = os.path.splitext(self.hmo_file_list.get(sel[0]))[0]
        else:
            base = datetime.now().strftime("%Y%m%d_%H%M%S_transcript")
        dest = os.path.join(TRANSCRIPT_DIR, base + ".odt")
        odt_name = os.path.basename(dest)
        try:
            from odf.opendocument import OpenDocumentText
            from odf.text import P
            doc = OpenDocumentText()
            for line in transcript.split("\n"):
                doc.text.addElement(P(text=line))
            doc.save(dest)
            self.hmo_export_status.set(f"Saved: {odt_name}")
            self._hmo_exported = True
            self.hmo_transcript_box.config(state="normal")
            self.hmo_transcript_box.delete("1.0", "end")
            self.hmo_transcript_box.insert("1.0", f"Transcript has exported to {odt_name}")
            self.hmo_transcript_box.config(fg=TH["fg_dim"], state="disabled")
            self.hmo_export_btn._bg = TH["border_hi"]
            self.hmo_export_btn._hover_bg = TH["border_hi"]
            self.hmo_export_btn._draw(TH["border_hi"])
            self.hmo_export_btn.config(state="disabled")
            self._hmo_update_delete_state()
        except Exception as e:
            self.hmo_export_status.set(f"Export error: {str(e)[:50]}")

    # -- LAN Upload Server --
    def _hmo_start_server(self):
        self._ingest_start()

    def _hmo_stop_server(self):
        self._ingest_stop()

    def _hmo_on_upload(self, filename):
        self._hmo_refresh_files()
        if hasattr(self, "_upload_dialog_files_label"):
            try:
                count = len([f for f in os.listdir(UPLOAD_DIR)
                             if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
                self._upload_dialog_files_label.config(
                    text=f"Last received: {filename}\n{count} file(s) in Journal")
            except Exception:
                pass

    def _hmo_show_upload_dialog(self):
        if self._hmo_server is None:
            self._ingest_start()
        url = self.hmo_server_url.get()
        if not url:
            url = self.ingest_url_var.get()

        win = tk.Toplevel(self, bg=TH["bg"])
        win.title("Upload from Phone")
        win.transient(self)
        win.resizable(False, False)

        tk.Label(win, text="Scan this QR code with your phone", bg=TH["bg"],
                 fg=TH["fg"], font=("Segoe UI", 14, "bold")).pack(padx=24, pady=(20, 4))
        tk.Label(win, text="or open the URL in your phone's browser",
                 bg=TH["bg"], fg=TH["fg2"], font=TH["font_sm"]).pack(padx=24, pady=(0, 12))

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                            box_size=1, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        rows = len(matrix)
        cols = len(matrix[0]) if rows else 0
        cell = 8
        qr_w = cols * cell
        qr_h = rows * cell

        qr_canvas = tk.Canvas(win, width=qr_w, height=qr_h, bg="#ffffff",
                               highlightthickness=2, highlightbackground=TH["border_hi"])
        qr_canvas.pack(padx=24, pady=(0, 12))
        for r, row in enumerate(matrix):
            for c, val in enumerate(row):
                if val:
                    x0, y0 = c * cell, r * cell
                    qr_canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell,
                                                fill="#000000", outline="")

        url_frame = tk.Frame(win, bg=TH["card"], highlightthickness=1,
                              highlightbackground=TH["border_hi"])
        url_frame.pack(fill="x", padx=24, pady=(0, 12))
        url_label = tk.Label(url_frame, text=url, bg=TH["card"], fg=TH["green"],
                              font=("Consolas", 13, "bold"), cursor="hand2")
        url_label.pack(padx=12, pady=10)

        def copy_url():
            self.clipboard_clear()
            self.clipboard_append(url)
            copy_btn_text.set("Copied!")
            win.after(1500, lambda: copy_btn_text.set("Copy URL"))

        copy_btn_text = tk.StringVar(value="Copy URL")
        copy_btn = tk.Button(url_frame, textvariable=copy_btn_text, bg=TH["btn"],
                              fg=TH["fg"], font=TH["font_sm"], bd=0, cursor="hand2",
                              activebackground=TH["btn_hover"], command=copy_url)
        copy_btn.pack(pady=(0, 8))

        status_frame = tk.Frame(win, bg=TH["bg"])
        status_frame.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(status_frame, text="Server:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        tk.Label(status_frame, textvariable=self.hmo_server_status, bg=TH["bg"],
                 fg=TH["green"], font=("Consolas", 10, "bold")).pack(side="left", padx=6)

        self._upload_dialog_files_label = tk.Label(
            win, text="Waiting for uploads...", bg=TH["bg"], fg=TH["fg2"],
            font=TH["font_sm"])
        self._upload_dialog_files_label.pack(padx=24, pady=(0, 8))

        btn_row = tk.Frame(win, bg=TH["bg"])
        btn_row.pack(fill="x", padx=24, pady=(0, 16))
        self._btn(btn_row, "Close", win.destroy).pack(side="right")
        self._btn(btn_row, "Restart Server", lambda: [self._ingest_stop(),
                  self.after(300, self._ingest_start)]).pack(side="right", padx=(0, 8))

    def _ingest_update_status(self, running, url=""):
        status = "Running" if running else "Stopped"
        color = TH["green"] if running else TH["yellow"]
        self.ingest_status_var.set(status)
        self.hmo_server_status.set(status)
        self.hmo_server_url.set(url)
        if running:
            self.ingest_url_var.set(url)

    def _ingest_is_running(self, port=None):
        if port is None:
            port = int(self.hmo_port_var.get().strip() or DEFAULT_INGEST_PORT)
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _ingest_start(self):
        url_str = self.ingest_url_var.get().strip()
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url_str)
            port = parsed.port or int(DEFAULT_INGEST_PORT)
        except Exception:
            port = int(self.hmo_port_var.get().strip() or DEFAULT_INGEST_PORT)
        self.hmo_port_var.set(str(port))
        if self._ingest_is_running(port):
            self._hmo_server = True
            lan_ip = _get_lan_ip()
            url = f"http://{lan_ip}:{port}"
            self._ingest_update_status(True, url)
            return
        try:
            server = HTTPServer(("0.0.0.0", port), AudioUploadHandler)
            server.upload_dir = UPLOAD_DIR
            server.on_upload = lambda name: self.after(0, self._hmo_on_upload, name)
            server.on_log = lambda msg: None
            self._hmo_server = server
            self._hmo_server_thread = threading.Thread(
                target=server.serve_forever, daemon=False)
            self._hmo_server_thread.start()
            lan_ip = _get_lan_ip()
            url = f"http://{lan_ip}:{port}"
            self._ingest_update_status(True, url)
        except Exception as e:
            self._ingest_update_status(False)
            self.ingest_status_var.set(f"Error: {e}")
            self._hmo_server = None

    def _ingest_stop(self):
        if self._hmo_server is not None and self._hmo_server is not True:
            threading.Thread(target=self._hmo_server.shutdown, daemon=True).start()
        self._hmo_server = None
        self._hmo_server_thread = None
        self._ingest_update_status(False)

    def _apply_toggles(self):
        tun_up, whim_up = _check_tunnel_and_whim()
        self._update_header_dots(tun_up, whim_up)
        tun = "on" if tun_up else "off"
        wh = "on" if whim_up else "off"
        self.toggle_status_var.set(f"tunnel {tun}, whim {wh}")
        if self._tray_icon:
            self._tray_icon.title = _tunnel_tray_label(tun_up, whim_up)

    # ==================== ARCHIVE TAB ====================
    def _arc_scan_fonts(self):
        families = set()
        families.update(["Segoe UI", "Consolas", "Courier New", "Arial",
                         "Helvetica", "Times New Roman", "Georgia"])
        if os.path.isdir(WHIM_FONTS_DIR):
            for fn in os.listdir(WHIM_FONTS_DIR):
                if fn.lower().endswith((".ttf", ".otf")):
                    name = os.path.splitext(fn)[0]
                    try:
                        self.tk.call("font", "create", f"arc_{name}",
                                     "-family", name, "-size", 11)
                    except tk.TclError:
                        pass
                    families.add(name)
        families.update(tkFont.families())
        return sorted(families, key=str.lower)

    # ------------------------------------------------------------------ LIBRARY
    # ==================== VOICE ENGINE ====================

    _VE_SAMPLE_RATE = 16000
    _VE_BLOCK_SIZE = 1024
    _VE_FFT_SIZE = 512
    _VE_FREQ_MIN = 300
    _VE_FREQ_MAX = 8000
    _VE_SPEC_ROWS = 40
    _VE_SPEC_COLS = 80
    _VE_SPEC_HISTORY = 80

    def build_voice_engine(self):
        f = self.tabs["voice_engine"]
        self._ve_running = False
        self._ve_stream = None
        self._ve_spec_data = []
        self._ve_last_confidence = 0.0
        self._ve_trigger_flash = 0
        self._ve_latency_ms = 0
        self._ve_peak_db = -60
        self._ve_frame_count = 0

        root = tk.Frame(f, bg=TH["bg"])
        root.pack(fill="both", expand=True, padx=8, pady=8)
        root.rowconfigure(0, weight=3)
        root.rowconfigure(1, weight=2)
        root.columnconfigure(0, weight=1)

        # ---- TOP: Whim-Scope (Live Spectrogram) ----
        scope_card = self._card(root, "WHIM-SCOPE  —  Real-Time Frequency Spectrogram (300 Hz – 8 kHz)", fg="#00ff00")
        scope_card.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        scope_toolbar = tk.Frame(scope_card, bg=TH["card"])
        scope_toolbar.pack(fill="x", padx=10, pady=(4, 2))

        self._ve_status_var = tk.StringVar(value="STOPPED")
        tk.Label(scope_toolbar, textvariable=self._ve_status_var, bg=TH["card"],
                 fg=TH["red"], font=("Consolas", 10, "bold")).pack(side="left")

        self._ve_peak_var = tk.StringVar(value="peak: — dB")
        tk.Label(scope_toolbar, textvariable=self._ve_peak_var, bg=TH["card"],
                 fg=TH["fg2"], font=("Consolas", 9)).pack(side="left", padx=(16, 0))

        self._ve_latency_var = tk.StringVar(value="latency: — ms")
        tk.Label(scope_toolbar, textvariable=self._ve_latency_var, bg=TH["card"],
                 fg=TH["fg2"], font=("Consolas", 9)).pack(side="left", padx=(16, 0))

        self._ve_conf_var = tk.StringVar(value="wake: 0.00")
        self._ve_conf_label = tk.Label(scope_toolbar, textvariable=self._ve_conf_var, bg=TH["card"],
                                        fg=TH["fg_dim"], font=("Consolas", 10, "bold"))
        self._ve_conf_label.pack(side="left", padx=(16, 0))

        self._ve_start_btn = self._btn(scope_toolbar, "START", self._ve_toggle)
        self._ve_start_btn.pack(side="right")

        self.ve_scope_canvas = tk.Canvas(scope_card, bg="#0a0a0a", highlightthickness=0, bd=0)
        self.ve_scope_canvas.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.ve_scope_canvas.create_text(
            400, 100, text="Press START to activate Whim-Scope\n16 kHz Mono  |  FFT 512pt  |  300–8000 Hz",
            fill=TH["fg_dim"], font=("Consolas", 11), anchor="center", justify="center")

        # ---- BOTTOM: Three-Column Controls ----
        bottom = tk.Frame(root, bg=TH["bg"])
        bottom.grid(row=1, column=0, sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.columnconfigure(2, weight=1)
        bottom.rowconfigure(0, weight=1)

        # === Column A: Gain & Noise Floor ===
        col_a = self._card(bottom, "GAIN & NOISE FLOOR", fg="#e0a030")
        col_a.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self._label(col_a, "Dynamic Gain Control", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(6, 0))
        gain_row = tk.Frame(col_a, bg=TH["card"])
        gain_row.pack(fill="x", padx=10, pady=2)
        self._ve_gain_var = tk.DoubleVar(value=1.0)
        tk.Scale(gain_row, from_=0.1, to=5.0, resolution=0.1, orient="horizontal",
                 variable=self._ve_gain_var, bg=TH["card"], fg=TH["fg"],
                 troughcolor=TH["input"], highlightthickness=0, font=("Consolas", 8),
                 activebackground=TH["btn_hover"], length=200).pack(fill="x")
        self._label(col_a, "Adjusts input volume before processing", font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_a, "Noise Floor Gate (dB)", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        nf_row = tk.Frame(col_a, bg=TH["card"])
        nf_row.pack(fill="x", padx=10, pady=2)
        self._ve_noise_floor_var = tk.DoubleVar(value=-40.0)
        tk.Scale(nf_row, from_=-80.0, to=0.0, resolution=1.0, orient="horizontal",
                 variable=self._ve_noise_floor_var, bg=TH["card"], fg=TH["fg"],
                 troughcolor=TH["input"], highlightthickness=0, font=("Consolas", 8),
                 activebackground=TH["btn_hover"], length=200).pack(fill="x")
        self._label(col_a, "Below this threshold = silence (prevents hallucinations)", font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_a, "High-Pass Filter", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        hpf_row = tk.Frame(col_a, bg=TH["card"])
        hpf_row.pack(fill="x", padx=10, pady=2)
        self._ve_hpf_var = tk.BooleanVar(value=True)
        self._ve_hpf_toggle = ToggleSwitch(hpf_row, text="HPF 150 Hz (Hotkey: H)", variable=self._ve_hpf_var,
                                            bg=TH["card"])
        self._ve_hpf_toggle.pack(anchor="w")
        self._label(col_a, "Cuts engine/road rumble below 150 Hz", font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_a, "Spectral Subtraction", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        ss_row = tk.Frame(col_a, bg=TH["card"])
        ss_row.pack(fill="x", padx=10, pady=2)
        self._ve_spectral_sub_var = tk.BooleanVar(value=False)
        ToggleSwitch(ss_row, text="Learn & subtract noise profile", variable=self._ve_spectral_sub_var,
                     bg=TH["card"]).pack(anchor="w")
        ss_btn_row = tk.Frame(col_a, bg=TH["card"])
        ss_btn_row.pack(fill="x", padx=10, pady=2)
        self._btn(ss_btn_row, "Capture Noise Profile", self._ve_capture_noise).pack(anchor="w")
        self._ve_noise_profile = None
        self._label(col_a, "Learns keyboard/ambient sound and subtracts it", font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_a, "Automatic Gain Control (AGC)", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        agc_row = tk.Frame(col_a, bg=TH["card"])
        agc_row.pack(fill="x", padx=10, pady=2)
        self._ve_agc_var = tk.BooleanVar(value=False)
        ToggleSwitch(agc_row, text="Auto-level gain by ambient noise", variable=self._ve_agc_var,
                     bg=TH["card"]).pack(anchor="w")
        self._label(col_a, "Raises gain at highway speed, lowers at idle", font=TH["font_xs"]).pack(anchor="w", padx=10)
        self._ve_agc_target_db = -20.0
        self._ve_agc_smoothed = 1.0

        self._label(col_a, "Parametric EQ (400 Hz notch)", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        peq_row = tk.Frame(col_a, bg=TH["card"])
        peq_row.pack(fill="x", padx=10, pady=2)
        self._ve_peq_var = tk.BooleanVar(value=False)
        ToggleSwitch(peq_row, text="Notch dip at ~400 Hz (cabin boxiness)", variable=self._ve_peq_var,
                     bg=TH["card"]).pack(anchor="w")
        peq_depth_row = tk.Frame(col_a, bg=TH["card"])
        peq_depth_row.pack(fill="x", padx=10, pady=2)
        self._ve_peq_depth_var = tk.DoubleVar(value=-12.0)
        tk.Scale(peq_depth_row, from_=-24.0, to=0.0, resolution=1.0, orient="horizontal",
                 variable=self._ve_peq_depth_var, bg=TH["card"], fg=TH["fg"],
                 troughcolor=TH["input"], highlightthickness=0, font=("Consolas", 8),
                 activebackground=TH["btn_hover"], length=200, label="Notch depth (dB)").pack(fill="x")
        self._label(col_a, "Reduces 350-450 Hz cabin reverb that masks 'W' in Whim", font=TH["font_xs"]).pack(anchor="w", padx=10, pady=(0, 8))

        # === Column B: Wake Word Sensitivity ===
        col_b = self._card(bottom, "\"HEY WHIM\" SENSITIVITY", fg="#2fa572")
        col_b.grid(row=0, column=1, sticky="nsew", padx=4)

        self._label(col_b, "Sensitivity Threshold (Hotkey: S)", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(6, 0))
        sens_row = tk.Frame(col_b, bg=TH["card"])
        sens_row.pack(fill="x", padx=10, pady=2)
        self._ve_sensitivity_var = tk.DoubleVar(value=0.5)
        tk.Scale(sens_row, from_=0.0, to=1.0, resolution=0.05, orient="horizontal",
                 variable=self._ve_sensitivity_var, bg=TH["card"], fg=TH["fg"],
                 troughcolor=TH["input"], highlightthickness=0, font=("Consolas", 8),
                 activebackground=TH["btn_hover"], length=200).pack(fill="x")
        sens_desc = tk.Frame(col_b, bg=TH["card"])
        sens_desc.pack(fill="x", padx=10)
        tk.Label(sens_desc, text="LOW = fewer false starts, must shout", bg=TH["card"],
                 fg=TH["yellow"], font=TH["font_xs"]).pack(anchor="w")
        tk.Label(sens_desc, text="HIGH = hears whispers, sneezes may trigger", bg=TH["card"],
                 fg=TH["yellow"], font=TH["font_xs"]).pack(anchor="w")

        self._label(col_b, "Phonetic Trigger Delay (ms)", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        delay_row = tk.Frame(col_b, bg=TH["card"])
        delay_row.pack(fill="x", padx=10, pady=2)
        self._ve_trigger_delay_var = tk.IntVar(value=500)
        tk.Scale(delay_row, from_=200, to=1500, resolution=50, orient="horizontal",
                 variable=self._ve_trigger_delay_var, bg=TH["card"], fg=TH["fg"],
                 troughcolor=TH["input"], highlightthickness=0, font=("Consolas", 8),
                 activebackground=TH["btn_hover"], length=200).pack(fill="x")
        self._label(col_b, "Wait time after 'Hey' to hear 'Whim' (~500-800ms for slow speech)",
                    font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_b, "Voice Activity Detection", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        vad_row = tk.Frame(col_b, bg=TH["card"])
        vad_row.pack(fill="x", padx=10, pady=2)
        self._ve_vad_var = tk.BooleanVar(value=True)
        ToggleSwitch(vad_row, text="VAD (only run AI on speech-like patterns)",
                     variable=self._ve_vad_var, bg=TH["card"]).pack(anchor="w")
        self._label(col_b, "Skips AI inference on non-speech audio to save CPU", font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_b, "Wake Word Engine", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        engine_row = tk.Frame(col_b, bg=TH["card"])
        engine_row.pack(fill="x", padx=10, pady=2)
        self._ve_engine_var = tk.StringVar(value="placeholder")
        ttk.Combobox(engine_row, textvariable=self._ve_engine_var, width=20,
                     values=["placeholder", "openWakeWord", "Porcupine"],
                     state="readonly").pack(anchor="w")
        self._label(col_b, "openWakeWord or Porcupine recommended for custom 'Hey Whim'",
                    font=TH["font_xs"]).pack(anchor="w", padx=10)

        self._label(col_b, "Intelligibility Band Highlight", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(10, 0))
        intl_row = tk.Frame(col_b, bg=TH["card"])
        intl_row.pack(fill="x", padx=10, pady=2)
        self._ve_intelli_var = tk.BooleanVar(value=True)
        ToggleSwitch(intl_row, text="Highlight 1–3 kHz on scope",
                     variable=self._ve_intelli_var, bg=TH["card"]).pack(anchor="w")
        self._label(col_b, "1–3 kHz = peak voice intelligibility; if 'M' in Whim\nis lost, low-end noise is masking nasal resonance",
                    font=TH["font_xs"]).pack(anchor="w", padx=10, pady=(0, 8))

        # === Column C: Optimization & Hardware Stats ===
        col_c = self._card(bottom, "OPTIMIZATION & HARDWARE", fg="#14507a")
        col_c.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        stats = [
            ("Sample Rate", "16,000 Hz (16 kHz) — optimal for voice"),
            ("Bit Depth", "16-bit PCM Mono"),
            ("FFT Window", "512-point Hanning"),
            ("Freq Range", "300 Hz – 8,000 Hz"),
        ]
        for label, value in stats:
            row = tk.Frame(col_c, bg=TH["card"])
            row.pack(fill="x", padx=10, pady=2)
            tk.Label(row, text=f"{label}:", bg=TH["card"], fg=TH["fg2"],
                     font=("Consolas", 9), width=14, anchor="e").pack(side="left")
            tk.Label(row, text=value, bg=TH["card"], fg=TH["green"],
                     font=("Consolas", 9), anchor="w").pack(side="left", padx=(6, 0))

        tk.Frame(col_c, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(8, 4))

        self._label(col_c, "Live Stats", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(4, 0))

        self._ve_inference_var = tk.StringVar(value="Last Trigger: — ms")
        tk.Label(col_c, textvariable=self._ve_inference_var, bg=TH["card"],
                 fg=TH["fg"], font=("Consolas", 9)).pack(anchor="w", padx=10, pady=1)

        self._ve_buffer_var = tk.StringVar(value="Buffer: 0 frames")
        tk.Label(col_c, textvariable=self._ve_buffer_var, bg=TH["card"],
                 fg=TH["fg"], font=("Consolas", 9)).pack(anchor="w", padx=10, pady=1)

        self._ve_cpu_var = tk.StringVar(value="CPU: — %")
        tk.Label(col_c, textvariable=self._ve_cpu_var, bg=TH["card"],
                 fg=TH["fg"], font=("Consolas", 9)).pack(anchor="w", padx=10, pady=1)

        self._ve_device_var = tk.StringVar(value="Audio Device: —")
        tk.Label(col_c, textvariable=self._ve_device_var, bg=TH["card"],
                 fg=TH["fg"], font=("Consolas", 9)).pack(anchor="w", padx=10, pady=1)

        tk.Frame(col_c, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(8, 4))

        self._label(col_c, "Buffer Size (frames)", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(4, 0))
        buf_row = tk.Frame(col_c, bg=TH["card"])
        buf_row.pack(fill="x", padx=10, pady=2)
        self._ve_bufsize_var = tk.IntVar(value=self._VE_BLOCK_SIZE)
        tk.Scale(buf_row, from_=256, to=4096, resolution=256, orient="horizontal",
                 variable=self._ve_bufsize_var, bg=TH["card"], fg=TH["fg"],
                 troughcolor=TH["input"], highlightthickness=0, font=("Consolas", 8),
                 activebackground=TH["btn_hover"], length=200).pack(fill="x")
        self._label(col_c, "80–100ms standard; larger = more latency, less CPU", font=TH["font_xs"]).pack(anchor="w", padx=10)

        tk.Frame(col_c, bg=TH["border_hi"], height=1).pack(fill="x", padx=10, pady=(8, 4))

        self._label(col_c, "Hotkeys", font=TH["font_sm"]).pack(anchor="w", padx=10, pady=(4, 0))
        for key, desc in [("G", "Cycle Gain (0.5 → 1.0 → 2.0 → 5.0)"),
                          ("S", "Cycle Sensitivity (0.3 → 0.5 → 0.7 → 0.9)"),
                          ("H", "Toggle High-Pass Filter")]:
            hk = tk.Frame(col_c, bg=TH["card"])
            hk.pack(fill="x", padx=10, pady=1)
            tk.Label(hk, text=f"  [{key}]", bg=TH["card"], fg="#00ff00",
                     font=("Consolas", 9), width=6, anchor="w").pack(side="left")
            tk.Label(hk, text=desc, bg=TH["card"], fg=TH["fg2"],
                     font=("Consolas", 8), anchor="w").pack(side="left", padx=(4, 0))

        self._label(col_c, "", font=TH["font_xs"]).pack(anchor="w", padx=10, pady=(0, 8))

        self._ve_load_config()
        self._ve_bind_hotkeys(f)

    def _ve_bind_hotkeys(self, frame):
        def _on_g(e):
            vals = [0.5, 1.0, 2.0, 5.0]
            cur = self._ve_gain_var.get()
            nxt = vals[(vals.index(min(vals, key=lambda v: abs(v - cur))) + 1) % len(vals)]
            self._ve_gain_var.set(nxt)
        def _on_s(e):
            vals = [0.3, 0.5, 0.7, 0.9]
            cur = self._ve_sensitivity_var.get()
            nxt = vals[(vals.index(min(vals, key=lambda v: abs(v - cur))) + 1) % len(vals)]
            self._ve_sensitivity_var.set(nxt)
        def _on_h(e):
            self._ve_hpf_var.set(not self._ve_hpf_var.get())
            self._ve_hpf_toggle._draw()
        frame.bind_all("<KeyPress-g>", _on_g)
        frame.bind_all("<KeyPress-s>", _on_s)
        frame.bind_all("<KeyPress-h>", _on_h)

    def _ve_toggle(self):
        if self._ve_running:
            self._ve_stop()
        else:
            self._ve_start()

    def _ve_start(self):
        if sd is None:
            self._ve_status_var.set("ERROR: sounddevice not installed")
            return
        try:
            dev_info = sd.query_devices(kind='input')
            self._ve_device_var.set(f"Audio Device: {dev_info['name']}")
        except Exception as e:
            self._ve_status_var.set(f"ERROR: {e}")
            return

        self._ve_spec_data = []
        self._ve_running = True
        self._ve_status_var.set("LISTENING")
        self._ve_start_btn.configure(text="STOP")

        block = self._ve_bufsize_var.get()

        def _audio_callback(indata, frames, time_info, status):
            if not self._ve_running:
                return
            t0 = time.time()
            audio = indata[:, 0].copy()
            audio *= self._ve_gain_var.get()

            if self._ve_hpf_var.get():
                alpha = 0.95
                if not hasattr(self, '_ve_hpf_prev'):
                    self._ve_hpf_prev = 0.0
                filtered = np.zeros_like(audio)
                for i in range(len(audio)):
                    filtered[i] = alpha * (self._ve_hpf_prev + audio[i] - (audio[i - 1] if i > 0 else 0))
                    self._ve_hpf_prev = filtered[i]
                audio = filtered

            if self._ve_peq_var.get():
                n = len(audio)
                fft_eq = np.fft.rfft(audio, n=n)
                freqs_eq = np.fft.rfftfreq(n, 1.0 / self._VE_SAMPLE_RATE)
                depth_lin = 10 ** (self._ve_peq_depth_var.get() / 20.0)
                bw = 50.0
                notch = 1.0 - (1.0 - depth_lin) * np.exp(-0.5 * ((freqs_eq - 400.0) / bw) ** 2)
                fft_eq *= notch
                audio = np.fft.irfft(fft_eq, n=n)

            if self._ve_agc_var.get():
                rms_now = np.sqrt(np.mean(audio ** 2)) + 1e-10
                current_db = 20 * np.log10(rms_now)
                desired_gain = 10 ** ((self._ve_agc_target_db - current_db) / 20.0)
                desired_gain = max(0.1, min(desired_gain, 10.0))
                smooth = 0.05
                self._ve_agc_smoothed = self._ve_agc_smoothed * (1 - smooth) + desired_gain * smooth
                audio *= self._ve_agc_smoothed

            if self._ve_spectral_sub_var.get() and self._ve_noise_profile is not None:
                fft_full = np.fft.rfft(audio, n=len(audio))
                mag = np.abs(fft_full)
                noise = self._ve_noise_profile
                if len(noise) != len(mag):
                    noise = np.interp(np.linspace(0, 1, len(mag)),
                                      np.linspace(0, 1, len(noise)), noise)
                mag = np.maximum(mag - noise * 1.5, 0)
                audio = np.fft.irfft(mag * np.exp(1j * np.angle(fft_full)), n=len(audio))

            window = np.hanning(min(self._VE_FFT_SIZE, len(audio)))
            segment = audio[:len(window)] * window
            fft_data = np.abs(np.fft.rfft(segment, n=self._VE_FFT_SIZE))
            fft_db = 20 * np.log10(fft_data + 1e-10)

            freqs = np.fft.rfftfreq(self._VE_FFT_SIZE, 1.0 / self._VE_SAMPLE_RATE)
            mask = (freqs >= self._VE_FREQ_MIN) & (freqs <= self._VE_FREQ_MAX)
            band = fft_db[mask]

            if len(band) > self._VE_SPEC_ROWS:
                indices = np.linspace(0, len(band) - 1, self._VE_SPEC_ROWS, dtype=int)
                band = band[indices]

            self._ve_spec_data.append(band)
            if len(self._ve_spec_data) > self._VE_SPEC_HISTORY:
                self._ve_spec_data = self._ve_spec_data[-self._VE_SPEC_HISTORY:]

            rms = np.sqrt(np.mean(audio ** 2))
            self._ve_peak_db = 20 * np.log10(rms + 1e-10)

            confidence = 0.0
            if self._ve_vad_var.get():
                if self._ve_peak_db > self._ve_noise_floor_var.get():
                    confidence = self._ve_detect_wake_word(audio)
            else:
                confidence = self._ve_detect_wake_word(audio)

            self._ve_last_confidence = confidence
            if confidence >= self._ve_sensitivity_var.get():
                self._ve_trigger_flash = 8

            self._ve_latency_ms = int((time.time() - t0) * 1000)
            self._ve_frame_count += 1

        try:
            self._ve_stream = sd.InputStream(
                samplerate=self._VE_SAMPLE_RATE,
                channels=1,
                dtype='float32',
                blocksize=block,
                callback=_audio_callback
            )
            self._ve_stream.start()
            self._ve_update_scope()
        except Exception as e:
            self._ve_running = False
            self._ve_status_var.set(f"ERROR: {e}")

    def _ve_stop(self):
        self._ve_running = False
        if self._ve_stream:
            try:
                self._ve_stream.stop()
                self._ve_stream.close()
            except Exception:
                pass
            self._ve_stream = None
        self._ve_status_var.set("STOPPED")
        self._ve_start_btn.configure(text="START")
        self._ve_save_config()

    def _ve_detect_wake_word(self, audio_buffer):
        rms = np.sqrt(np.mean(audio_buffer ** 2))
        energy = min(rms * 10, 1.0)
        return energy * 0.3

    def _ve_update_scope(self):
        if not self._ve_running:
            return
        canvas = self.ve_scope_canvas
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(50, self._ve_update_scope)
            return

        canvas.delete("all")

        data = list(self._ve_spec_data)
        if not data:
            self.after(50, self._ve_update_scope)
            return

        cols = len(data)
        rows = len(data[0]) if data else 0
        if rows == 0 or cols == 0:
            self.after(50, self._ve_update_scope)
            return

        cell_w = max(cw / cols, 1)
        cell_h = max(ch / rows, 1)

        intelli_on = self._ve_intelli_var.get()
        freq_range = self._VE_FREQ_MAX - self._VE_FREQ_MIN
        intelli_lo = (1000 - self._VE_FREQ_MIN) / freq_range
        intelli_hi = (3000 - self._VE_FREQ_MIN) / freq_range

        for ci, column in enumerate(data):
            x = int(ci * cell_w)
            for ri, val in enumerate(column):
                y = ch - int((ri + 1) * cell_h)
                norm = max(0.0, min(1.0, (val + 80) / 80))
                frac_ri = ri / max(rows - 1, 1)
                in_intelli = intelli_on and intelli_lo <= frac_ri <= intelli_hi
                if self._ve_trigger_flash > 0 and norm > 0.6:
                    r = int(255 * norm)
                    g = int(255)
                    b = 0
                elif in_intelli:
                    r = int(norm * 80)
                    g = int(norm * 220)
                    b = int(norm * 255)
                else:
                    r = int(norm * 255)
                    g = int(norm * 180)
                    b = int((1.0 - norm) * 40)
                color = f"#{r:02x}{g:02x}{b:02x}"
                canvas.create_rectangle(x, y, x + int(cell_w) + 1, y + int(cell_h) + 1,
                                        fill=color, outline="")

        conf = self._ve_last_confidence
        thresh = self._ve_sensitivity_var.get()
        ghost_x = cw - 24
        ghost_h = int(conf * ch)
        ghost_y = ch - ghost_h
        if conf >= thresh:
            ghost_color = "#00ff00"
        elif conf >= thresh * 0.5:
            ghost_color = "#3388ff"
        else:
            ghost_color = "#333333"
        canvas.create_rectangle(ghost_x, ghost_y, ghost_x + 16, ch,
                                fill=ghost_color, outline="#555555", width=1)
        canvas.create_text(ghost_x + 8, ghost_y - 8, text=f"{conf:.0%}",
                           fill=ghost_color, font=("Consolas", 8), anchor="center")

        if self._ve_trigger_flash > 0:
            canvas.create_text(cw // 2, 16, text=">>> WAKE WORD DETECTED <<<",
                               fill="#00ff00", font=("Consolas", 12, "bold"))
            self._ve_trigger_flash -= 1

        freq_labels = [300, 1000, 2000, 4000, 6000, 8000]
        for freq in freq_labels:
            frac = (freq - self._VE_FREQ_MIN) / freq_range
            y = ch - int(frac * ch)
            label_color = "#446688" if (intelli_on and 1000 <= freq <= 3000) else "#444444"
            canvas.create_text(4, y, text=f"{freq}Hz", fill=label_color,
                               font=("Consolas", 7), anchor="w")

        if intelli_on:
            y_lo = ch - int(intelli_lo * ch)
            y_hi = ch - int(intelli_hi * ch)
            canvas.create_line(0, y_lo, cw - 30, y_lo, fill="#335577", dash=(4, 4))
            canvas.create_line(0, y_hi, cw - 30, y_hi, fill="#335577", dash=(4, 4))
            mid_y = (y_lo + y_hi) // 2
            canvas.create_text(cw - 32, mid_y, text="1-3k", fill="#446688",
                               font=("Consolas", 7), anchor="e")

        self._ve_peak_var.set(f"peak: {self._ve_peak_db:.1f} dB")
        self._ve_latency_var.set(f"latency: {self._ve_latency_ms} ms")
        conf = self._ve_last_confidence
        thresh = self._ve_sensitivity_var.get()
        self._ve_conf_var.set(f"wake: {conf:.2f}")
        self._ve_conf_label.config(fg="#00ff00" if conf >= thresh else TH["fg_dim"])
        self._ve_inference_var.set(f"Last Trigger: {self._ve_latency_ms} ms")
        self._ve_buffer_var.set(f"Buffer: {self._ve_frame_count} frames")

        try:
            import psutil
            self._ve_cpu_var.set(f"CPU: {psutil.cpu_percent():.1f}%")
        except ImportError:
            self._ve_cpu_var.set(f"CPU: N/A (install psutil)")

        self.after(50, self._ve_update_scope)

    def _ve_capture_noise(self):
        if not self._ve_running or not self._ve_spec_data:
            return
        recent = self._ve_spec_data[-10:] if len(self._ve_spec_data) >= 10 else self._ve_spec_data
        avg = np.mean([col for col in recent], axis=0)
        self._ve_noise_profile = np.power(10, avg / 20)
        self.log_events("Voice Engine: Noise profile captured", module="AVR", level="INFO")

    def _ve_save_config(self):
        cfg = {
            "gain": self._ve_gain_var.get(),
            "noise_floor": self._ve_noise_floor_var.get(),
            "hpf": self._ve_hpf_var.get(),
            "spectral_sub": self._ve_spectral_sub_var.get(),
            "agc": self._ve_agc_var.get(),
            "peq": self._ve_peq_var.get(),
            "peq_depth": self._ve_peq_depth_var.get(),
            "sensitivity": self._ve_sensitivity_var.get(),
            "trigger_delay": self._ve_trigger_delay_var.get(),
            "vad": self._ve_vad_var.get(),
            "intelli_band": self._ve_intelli_var.get(),
            "engine": self._ve_engine_var.get(),
            "buffer_size": self._ve_bufsize_var.get(),
        }
        try:
            with open(VOICE_ENGINE_CONFIG, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _ve_load_config(self):
        if not os.path.isfile(VOICE_ENGINE_CONFIG):
            return
        try:
            with open(VOICE_ENGINE_CONFIG, "r") as f:
                cfg = json.load(f)
            self._ve_gain_var.set(cfg.get("gain", 1.0))
            self._ve_noise_floor_var.set(cfg.get("noise_floor", -40.0))
            self._ve_hpf_var.set(cfg.get("hpf", True))
            self._ve_spectral_sub_var.set(cfg.get("spectral_sub", False))
            self._ve_agc_var.set(cfg.get("agc", False))
            self._ve_peq_var.set(cfg.get("peq", False))
            self._ve_peq_depth_var.set(cfg.get("peq_depth", -12.0))
            self._ve_sensitivity_var.set(cfg.get("sensitivity", 0.5))
            self._ve_trigger_delay_var.set(cfg.get("trigger_delay", 500))
            self._ve_vad_var.set(cfg.get("vad", True))
            self._ve_intelli_var.set(cfg.get("intelli_band", True))
            self._ve_engine_var.set(cfg.get("engine", "placeholder"))
            self._ve_bufsize_var.set(cfg.get("buffer_size", self._VE_BLOCK_SIZE))
        except Exception:
            pass

    # ------------------------------------------------------------------ CURSOR
    _CURSOR_DEFAULT_DIR = os.path.expanduser("~/vaults/WHIM")

    def build_cursor(self):
        f = self.tabs["cursor"]
        self._cursor_file_path = None
        self._cursor_dirty = False
        self._cursor_chat_history = []

        root = tk.Frame(f, bg=TH["bg"])
        root.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Top bar: model selector + file actions ──
        top = tk.Frame(root, bg=TH["card"], height=42)
        top.pack(fill="x", pady=(0, 4))

        tk.Label(top, text="CURSOR", bg=TH["card"], fg=TH["green"],
                 font=("JetBrains Mono", 12, "bold")).pack(side="left", padx=10, pady=6)

        tk.Frame(top, width=1, bg=TH["border"], height=24).pack(side="left", fill="y", padx=6, pady=6)

        tk.Label(top, text="Model:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(4, 4))
        self._cursor_model_var = tk.StringVar(value=DEFAULT_MODELS[0])
        self._cursor_model_combo = ttk.Combobox(top, textvariable=self._cursor_model_var,
                                                  values=DEFAULT_MODELS, width=24, state="readonly")
        self._cursor_model_combo.pack(side="left", padx=(0, 4))
        self._cursor_ram_lbl = tk.Label(top, text="", bg=TH["card"], fg=TH["fg2"],
                                         font=("Consolas", 8))
        self._cursor_ram_lbl.pack(side="left", padx=(0, 8))
        self._cursor_model_combo.bind("<<ComboboxSelected>>", lambda e: self._cursor_update_ram_label())

        tk.Frame(top, width=1, bg=TH["border"], height=24).pack(side="left", fill="y", padx=4, pady=6)

        self._btn(top, "Open", self._cursor_open_file).pack(side="left", padx=2, pady=4)
        self._btn(top, "Save", self._cursor_save_file).pack(side="left", padx=2, pady=4)
        self._btn(top, "Save As", self._cursor_save_as).pack(side="left", padx=2, pady=4)
        self._btn(top, "New", self._cursor_new_file).pack(side="left", padx=2, pady=4)

        self._cursor_status = tk.StringVar(value="No file open")
        tk.Label(top, textvariable=self._cursor_status, bg=TH["card"], fg=TH["green"],
                 font=("Consolas", 9)).pack(side="right", padx=10, pady=6)

        # ── Three columns: file tree | editor | AI assist ──
        paned = tk.PanedWindow(root, orient="horizontal", bg=TH["bg"],
                                sashwidth=4, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # ── Left: file browser ──
        left = tk.Frame(paned, bg=TH["card"], width=200)
        paned.add(left, minsize=140, width=200)

        fb_top = tk.Frame(left, bg=TH["card"])
        fb_top.pack(fill="x")
        tk.Label(fb_top, text="FILES", bg=TH["card"], fg=TH["fg_dim"],
                 font=("Consolas", 9)).pack(side="left", padx=8, pady=4)
        self._btn(fb_top, "\u21bb", self._cursor_refresh_tree).pack(side="right", padx=4, pady=2)

        self._cursor_dir_var = tk.StringVar(value=self._CURSOR_DEFAULT_DIR)
        dir_entry = self._entry(left, self._cursor_dir_var, font=("Consolas", 8))
        dir_entry.pack(fill="x", padx=4, pady=2)
        dir_entry.bind("<Return>", lambda e: self._cursor_refresh_tree())

        tree_frame = tk.Frame(left, bg=TH["bg"])
        tree_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self._cursor_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._cursor_tree.yview)
        self._cursor_tree.configure(yscrollcommand=vsb.set)
        self._cursor_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._cursor_tree.bind("<<TreeviewOpen>>", self._cursor_tree_expand)
        self._cursor_tree.bind("<Double-1>", self._cursor_tree_open)

        # ── Center: code editor with line gutter ──
        center = tk.Frame(paned, bg=TH["bg"])
        paned.add(center, minsize=300)

        self._cursor_file_lbl = tk.Label(center, text="untitled", bg=TH["bg"], fg=TH["fg_dim"],
                                          font=("Consolas", 9), anchor="w")
        self._cursor_file_lbl.pack(fill="x", padx=4, pady=(2, 0))

        editor_frame = tk.Frame(center, bg=TH["bg"])
        editor_frame.pack(fill="both", expand=True)

        self._cursor_gutter = tk.Text(editor_frame, width=5, bg="#111111", fg="#555555",
                                       font=("JetBrains Mono", 11), bd=0,
                                       highlightthickness=0, padx=4, state="disabled",
                                       takefocus=0)
        self._cursor_gutter.pack(side="left", fill="y")

        self._cursor_editor = tk.Text(editor_frame, bg="#0e0e0e", fg=TH["fg"],
                                       font=("JetBrains Mono", 11), bd=0,
                                       insertbackground=TH["green"], highlightthickness=0,
                                       wrap="none", undo=True, maxundo=-1,
                                       tabs=("4c",))
        self._cursor_editor.pack(side="left", fill="both", expand=True)

        e_vsb = ttk.Scrollbar(editor_frame, orient="vertical", command=self._cursor_editor.yview)
        self._cursor_editor.configure(yscrollcommand=e_vsb.set)
        e_vsb.pack(side="right", fill="y")

        e_hsb = ttk.Scrollbar(center, orient="horizontal", command=self._cursor_editor.xview)
        self._cursor_editor.configure(xscrollcommand=e_hsb.set)
        e_hsb.pack(fill="x")

        self._cursor_editor.bind("<KeyRelease>", lambda e: self._cursor_update_gutter())
        self._cursor_editor.bind("<<Modified>>", self._cursor_on_modified)

        # syntax tag colours
        self._cursor_editor.tag_configure("keyword", foreground="#c678dd")
        self._cursor_editor.tag_configure("builtin", foreground="#56b6c2")
        self._cursor_editor.tag_configure("string", foreground="#98c379")
        self._cursor_editor.tag_configure("comment", foreground="#5c6370", font=("JetBrains Mono", 11, "italic"))
        self._cursor_editor.tag_configure("decorator", foreground="#e5c07b")
        self._cursor_editor.tag_configure("number", foreground="#d19a66")
        self._cursor_editor.tag_configure("self_kw", foreground="#e06c75")

        # ── Right: AI assist ──
        right = tk.Frame(paned, bg=TH["card"], width=320)
        paned.add(right, minsize=200, width=320)

        tk.Label(right, text="AI ASSIST", bg=TH["card"], fg=TH["fg_dim"],
                 font=("Consolas", 9)).pack(anchor="w", padx=8, pady=(6, 2))

        assist_btns = tk.Frame(right, bg=TH["card"])
        assist_btns.pack(fill="x", padx=4, pady=2)
        self._btn(assist_btns, "Explain", lambda: self._cursor_ai_action("explain")).pack(side="left", padx=2, pady=2)
        self._btn(assist_btns, "Fix Bugs", lambda: self._cursor_ai_action("fix")).pack(side="left", padx=2, pady=2)
        self._btn(assist_btns, "Refactor", lambda: self._cursor_ai_action("refactor")).pack(side="left", padx=2, pady=2)
        self._btn(assist_btns, "Docstring", lambda: self._cursor_ai_action("docstring")).pack(side="left", padx=2, pady=2)

        assist_btns2 = tk.Frame(right, bg=TH["card"])
        assist_btns2.pack(fill="x", padx=4, pady=(0, 2))
        self._btn(assist_btns2, "Complete", lambda: self._cursor_ai_action("complete")).pack(side="left", padx=2, pady=2)
        self._btn(assist_btns2, "Tests", lambda: self._cursor_ai_action("tests")).pack(side="left", padx=2, pady=2)
        self._btn(assist_btns2, "Apply Diff", self._cursor_apply_diff).pack(side="left", padx=2, pady=2)
        self._btn(assist_btns2, "Clear", self._cursor_clear_chat).pack(side="left", padx=2, pady=2)

        self._cursor_chat_log = tk.Text(right, bg="#111111", fg=TH["fg"],
                                         font=("JetBrains Mono", 10), bd=0,
                                         highlightthickness=0, wrap="word",
                                         state="disabled")
        self._cursor_chat_log.pack(fill="both", expand=True, padx=4, pady=2)
        self._cursor_chat_log.tag_configure("user", foreground=TH["green"])
        self._cursor_chat_log.tag_configure("ai", foreground="#dce4ee")
        self._cursor_chat_log.tag_configure("system", foreground="#888888", font=("JetBrains Mono", 9, "italic"))

        input_frame = tk.Frame(right, bg=TH["card"])
        input_frame.pack(fill="x", padx=4, pady=(2, 6))
        self._cursor_input_var = tk.StringVar()
        inp = self._entry(input_frame, self._cursor_input_var, font=("JetBrains Mono", 10))
        inp.pack(side="left", fill="x", expand=True, padx=(0, 4))
        inp.bind("<Return>", lambda e: self._cursor_send_chat())
        self._btn(input_frame, "Send", self._cursor_send_chat).pack(side="right", padx=2, pady=2)

        self._cursor_refresh_tree()
        self._cursor_refresh_models()
        self._cursor_update_ram_label()

    def _cursor_refresh_models(self):
        def _fetch():
            import urllib.request as _ur
            try:
                with _ur.urlopen(_ur.Request(
                    f"{getattr(self, '_whimai_ollama_url', 'http://localhost:11434')}/api/tags"),
                    timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                models = data.get("models", [])
                names = [m["name"] for m in models]
                self._cursor_model_info = {m["name"]: m for m in models}
                if names:
                    self.after(0, lambda: self._cursor_model_combo.config(values=names))
                    self.after(0, self._cursor_update_ram_label)
            except Exception:
                pass
        self._cursor_model_info = {}
        threading.Thread(target=_fetch, daemon=True).start()

    def _cursor_update_ram_label(self):
        name = self._cursor_model_var.get()
        info = getattr(self, "_cursor_model_info", {}).get(name, {})
        size_gb = info.get("size", 0) / 1e9
        params = info.get("details", {}).get("parameter_size", "")
        quant = info.get("details", {}).get("quantization_level", "")
        parts = []
        if size_gb > 0:
            parts.append(f"{size_gb:.1f}GB")
        if params:
            parts.append(params)
        if quant:
            parts.append(quant)
        try:
            import psutil
            ram = psutil.virtual_memory()
            parts.append(f"RAM:{ram.available / 1e9:.0f}GB free")
        except ImportError:
            pass
        self._cursor_ram_lbl.config(text="  ".join(parts) if parts else "")

    # ── File browser ──
    def _cursor_refresh_tree(self):
        self._cursor_tree.delete(*self._cursor_tree.get_children())
        root_dir = self._cursor_dir_var.get().strip()
        if not os.path.isdir(root_dir):
            return
        self._cursor_populate_node("", root_dir)

    def _cursor_populate_node(self, parent, path):
        skip = {".venv", "__pycache__", "node_modules", ".git", "obj", "gen"}
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        dirs = [e for e in entries if os.path.isdir(os.path.join(path, e)) and e not in skip]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        for d in dirs:
            full = os.path.join(path, d)
            node = self._cursor_tree.insert(parent, "end", text=f"\U0001f4c1 {d}",
                                             values=(full,), open=False)
            self._cursor_tree.insert(node, "end", text="...")  # placeholder
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in (".py", ".js", ".json", ".html", ".css", ".sh", ".md",
                       ".txt", ".yaml", ".yml", ".toml", ".xml", ".java", ".go",
                       ".cfg", ".conf", ".csv", ".sql"):
                full = os.path.join(path, fn)
                self._cursor_tree.insert(parent, "end", text=f"  {fn}", values=(full,))

    def _cursor_tree_expand(self, event):
        node = self._cursor_tree.focus()
        children = self._cursor_tree.get_children(node)
        if len(children) == 1 and self._cursor_tree.item(children[0], "text") == "...":
            self._cursor_tree.delete(children[0])
            vals = self._cursor_tree.item(node, "values")
            if vals:
                self._cursor_populate_node(node, vals[0])

    def _cursor_tree_open(self, event):
        node = self._cursor_tree.focus()
        vals = self._cursor_tree.item(node, "values")
        if vals and os.path.isfile(vals[0]):
            self._cursor_load_file(vals[0])

    def _cursor_load_file(self, path):
        try:
            with open(path, "r", errors="replace") as fh:
                content = fh.read()
        except Exception as e:
            self._cursor_status.set(f"Error: {e}")
            return
        self._cursor_file_path = path
        self._cursor_editor.delete("1.0", "end")
        self._cursor_editor.insert("1.0", content)
        self._cursor_editor.edit_reset()
        self._cursor_editor.edit_modified(False)
        self._cursor_dirty = False
        fname = os.path.basename(path)
        self._cursor_file_lbl.config(text=path)
        self._cursor_status.set(fname)
        self._cursor_update_gutter()
        self._cursor_highlight_syntax()

    def _cursor_open_file(self):
        path = filedialog.askopenfilename(
            title="Open file",
            initialdir=self._cursor_dir_var.get(),
            filetypes=[("Python", "*.py"), ("All text", "*.*")])
        if path:
            self._cursor_load_file(path)

    def _cursor_save_file(self):
        if not self._cursor_file_path:
            self._cursor_save_as()
            return
        try:
            content = self._cursor_editor.get("1.0", "end-1c")
            with open(self._cursor_file_path, "w") as fh:
                fh.write(content)
            self._cursor_dirty = False
            self._cursor_editor.edit_modified(False)
            self._cursor_status.set(f"Saved {os.path.basename(self._cursor_file_path)}")
        except Exception as e:
            self._cursor_status.set(f"Error: {e}")

    def _cursor_save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save as",
            initialdir=self._cursor_dir_var.get(),
            defaultextension=".py",
            filetypes=[("Python", "*.py"), ("All", "*.*")])
        if path:
            self._cursor_file_path = path
            self._cursor_file_lbl.config(text=path)
            self._cursor_save_file()

    def _cursor_new_file(self):
        self._cursor_file_path = None
        self._cursor_editor.delete("1.0", "end")
        self._cursor_editor.edit_reset()
        self._cursor_editor.edit_modified(False)
        self._cursor_dirty = False
        self._cursor_file_lbl.config(text="untitled")
        self._cursor_status.set("New file")
        self._cursor_update_gutter()

    def _cursor_on_modified(self, event=None):
        if self._cursor_editor.edit_modified():
            self._cursor_dirty = True
            if self._cursor_file_path:
                name = os.path.basename(self._cursor_file_path)
                self._cursor_status.set(f"{name} (modified)")
            self._cursor_highlight_syntax()

    def _cursor_update_gutter(self):
        self._cursor_gutter.config(state="normal")
        self._cursor_gutter.delete("1.0", "end")
        line_count = int(self._cursor_editor.index("end-1c").split(".")[0])
        nums = "\n".join(str(i) for i in range(1, line_count + 1))
        self._cursor_gutter.insert("1.0", nums)
        self._cursor_gutter.config(state="disabled")

    _PY_KEYWORDS = {
        "False", "None", "True", "and", "as", "assert", "async", "await",
        "break", "class", "continue", "def", "del", "elif", "else", "except",
        "finally", "for", "from", "global", "if", "import", "in", "is",
        "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
        "try", "while", "with", "yield",
    }
    _PY_BUILTINS = {
        "print", "len", "range", "int", "str", "float", "list", "dict",
        "set", "tuple", "bool", "type", "isinstance", "hasattr", "getattr",
        "setattr", "open", "super", "enumerate", "zip", "map", "filter",
        "sorted", "reversed", "any", "all", "min", "max", "sum", "abs",
        "input", "format", "repr", "id", "hex", "oct", "bin", "chr", "ord",
        "staticmethod", "classmethod", "property", "Exception", "ValueError",
        "TypeError", "KeyError", "IndexError", "AttributeError", "OSError",
        "FileNotFoundError", "RuntimeError", "StopIteration", "NotImplementedError",
    }

    def _cursor_highlight_syntax(self):
        import re as _re
        editor = self._cursor_editor
        for tag in ("keyword", "builtin", "string", "comment", "decorator", "number", "self_kw"):
            editor.tag_remove(tag, "1.0", "end")
        content = editor.get("1.0", "end")
        patterns = [
            ("comment", _re.compile(r'#[^\n]*')),
            ("string", _re.compile(r'(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')')),
            ("decorator", _re.compile(r'@\w+')),
            ("number", _re.compile(r'\b\d+\.?\d*(?:e[+-]?\d+)?\b')),
            ("self_kw", _re.compile(r'\bself\b')),
            ("keyword", _re.compile(r'\b(?:' + "|".join(self._PY_KEYWORDS) + r')\b')),
            ("builtin", _re.compile(r'\b(?:' + "|".join(self._PY_BUILTINS) + r')\b')),
        ]
        for tag_name, pat in patterns:
            for m in pat.finditer(content):
                start_idx = f"1.0+{m.start()}c"
                end_idx = f"1.0+{m.end()}c"
                editor.tag_add(tag_name, start_idx, end_idx)

    # ── AI assist ──
    _CURSOR_PROMPTS = {
        "explain": "Explain the following code concisely. Focus on what it does and any notable patterns:\n\n```\n{code}\n```",
        "fix": "Find and fix bugs in this code. Return the corrected code with brief comments on what was wrong:\n\n```\n{code}\n```",
        "refactor": "Refactor this code to be cleaner and more maintainable. Preserve functionality:\n\n```\n{code}\n```",
        "docstring": "Add docstrings/comments to this code. Return the full code with documentation added:\n\n```\n{code}\n```",
        "complete": "Complete this code. Continue writing from where it ends. Return only the new code to append:\n\n```\n{code}\n```",
        "tests": "Write unit tests for this code using pytest. Return only the test code:\n\n```\n{code}\n```",
    }

    def _cursor_get_context(self):
        try:
            sel = self._cursor_editor.get("sel.first", "sel.last")
            if sel.strip():
                return sel
        except tk.TclError:
            pass
        return self._cursor_editor.get("1.0", "end-1c")

    def _cursor_ai_action(self, action):
        code = self._cursor_get_context()
        if not code.strip():
            self._cursor_chat_append("No code in editor.\n", "system")
            return
        prompt = self._CURSOR_PROMPTS.get(action, "{code}").format(code=code)
        self._cursor_chat_append(f"[{action.upper()}] using {self._cursor_model_var.get()}\n", "system")
        self._cursor_stream_ollama(prompt)

    def _cursor_send_chat(self):
        text = self._cursor_input_var.get().strip()
        if not text:
            return
        self._cursor_input_var.set("")
        code = self._cursor_get_context()
        if code.strip():
            full_prompt = f"{text}\n\nHere is the code I'm working with:\n```\n{code}\n```"
        else:
            full_prompt = text
        self._cursor_chat_append(f"You: {text}\n", "user")
        self._cursor_stream_ollama(full_prompt)

    def _cursor_chat_append(self, text, tag="ai"):
        self._cursor_chat_log.config(state="normal")
        self._cursor_chat_log.insert("end", text, tag)
        self._cursor_chat_log.see("end")
        self._cursor_chat_log.config(state="disabled")

    def _cursor_clear_chat(self):
        self._cursor_chat_log.config(state="normal")
        self._cursor_chat_log.delete("1.0", "end")
        self._cursor_chat_log.config(state="disabled")
        self._cursor_chat_history = []

    def _cursor_stream_ollama(self, prompt):
        model = self._cursor_model_var.get()
        self._cursor_chat_history.append({"role": "user", "content": prompt})
        sys_msg = (
            "You are a concise code assistant embedded in the Whim IDE. "
            "When returning code, use fenced code blocks. Be direct and brief."
        )
        messages = [{"role": "system", "content": sys_msg}] + list(self._cursor_chat_history)

        def _stream():
            import urllib.request as _ur
            try:
                payload = json.dumps({
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": 0.3, "num_ctx": 16384}
                }).encode()
                req = _ur.Request(
                    f"{getattr(self, '_whimai_ollama_url', 'http://localhost:11434')}/api/chat",
                    data=payload, method="POST",
                    headers={"Content-Type": "application/json"})
                full = []
                with _ur.urlopen(req, timeout=180) as resp:
                    buf = b""
                    while True:
                        chunk = resp.read(1)
                        if not chunk:
                            break
                        buf += chunk
                        if chunk == b"\n" and buf.strip():
                            try:
                                data = json.loads(buf.strip())
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    full.append(token)
                                    self.after(0, lambda t=token: self._cursor_chat_append(t, "ai"))
                                if data.get("done"):
                                    break
                            except (json.JSONDecodeError, ValueError):
                                pass
                            buf = b""
                response_text = "".join(full)
                self._cursor_chat_history.append({"role": "assistant", "content": response_text})
                self.after(0, lambda: self._cursor_chat_append("\n\n", "ai"))
                self.after(0, lambda: self._cursor_status.set("Ready"))
            except Exception as e:
                self.after(0, lambda: self._cursor_chat_append(f"\n[Error: {e}]\n", "system"))
                self.after(0, lambda: self._cursor_status.set("Error"))

        self._cursor_status.set(f"Streaming {model}...")
        threading.Thread(target=_stream, daemon=True).start()

    def _cursor_apply_diff(self):
        chat_text = self._cursor_chat_log.get("1.0", "end")
        import re as _re
        blocks = _re.findall(r'```(?:python)?\n(.*?)```', chat_text, _re.DOTALL)
        if not blocks:
            self._cursor_chat_append("No code block found in AI response to apply.\n", "system")
            return
        code = blocks[-1].strip()
        confirm = messagebox.askyesno("Apply Code",
                                       f"Replace editor contents with AI-generated code?\n\n"
                                       f"({len(code)} characters, {code.count(chr(10))+1} lines)")
        if confirm:
            self._cursor_editor.delete("1.0", "end")
            self._cursor_editor.insert("1.0", code)
            self._cursor_update_gutter()
            self._cursor_highlight_syntax()
            self._cursor_chat_append("Applied code to editor.\n", "system")

    # ------------------------------------------------------------------ LIBRARY
    _LIB_DIR = os.path.expanduser("~/Shared")

    def build_library(self):
        f = self.tabs["library"]
        os.makedirs(self._LIB_DIR, exist_ok=True)

        self._lib_view_mode = "list"

        root_frame = tk.Frame(f, bg=TH["bg"])
        root_frame.pack(fill="both", expand=True, padx=8, pady=8)

        header = tk.Frame(root_frame, bg=TH["card"], height=42)
        header.pack(fill="x", pady=(0, 6))
        tk.Label(header, text="Library — Shared Files",
                 bg=TH["card"], fg=TH["fg"],
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=12, pady=8)
        self._lib_status_var = tk.StringVar(value="Ready")
        tk.Label(header, textvariable=self._lib_status_var, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9)).pack(side="right", padx=12, pady=8)

        action_bar = tk.Frame(root_frame, bg=TH["card"], height=36)
        action_bar.pack(fill="x", pady=(0, 6))
        self._btn(action_bar, "Upload Files", self._lib_upload).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Download Selected", self._lib_download).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Preview", self._lib_preview).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Rename", self._lib_rename).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Delete Selected", self._lib_delete).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Refresh", self._lib_refresh).pack(side="left", padx=4, pady=4)

        rhs = tk.Frame(action_bar, bg=TH["card"])
        rhs.pack(side="right")
        self._btn(rhs, "\u2630 List", lambda: self._lib_set_view("list")).pack(side="left", padx=2, pady=4)
        self._btn(rhs, "\u25a6 Grid", lambda: self._lib_set_view("grid")).pack(side="left", padx=2, pady=4)
        self._btn(rhs, "\u25eb Detail", lambda: self._lib_set_view("detail")).pack(side="left", padx=2, pady=4)
        self._btn(rhs, "Open Folder", self._lib_open_folder).pack(side="left", padx=(8, 4), pady=4)

        self._lib_content_frame = tk.Frame(root_frame, bg=TH["bg"])
        self._lib_content_frame.pack(fill="both", expand=True)

        self._lib_build_list_view()
        self._lib_refresh()

    def _lib_build_list_view(self):
        for w in self._lib_content_frame.winfo_children():
            w.destroy()

        cols = ("name", "size", "type")
        list_frame = tk.Frame(self._lib_content_frame, bg=TH["bg"])
        list_frame.pack(fill="both", expand=True)

        self._lib_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                       selectmode="extended")
        self._lib_tree.heading("name", text="Name", anchor="w")
        self._lib_tree.heading("size", text="Size", anchor="w")
        self._lib_tree.heading("type", text="Type", anchor="w")
        self._lib_tree.column("name", width=400, minwidth=200)
        self._lib_tree.column("size", width=100, minwidth=60)
        self._lib_tree.column("type", width=100, minwidth=60)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._lib_tree.yview)
        self._lib_tree.configure(yscrollcommand=vsb.set)
        self._lib_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._lib_tree.bind("<Double-1>", lambda e: self._lib_preview())

    def _lib_build_grid_view(self):
        for w in self._lib_content_frame.winfo_children():
            w.destroy()

        canvas = tk.Canvas(self._lib_content_frame, bg=TH["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self._lib_content_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        grid_inner = tk.Frame(canvas, bg=TH["bg"])
        canvas.create_window((0, 0), window=grid_inner, anchor="nw")
        self._lib_grid_inner = grid_inner
        self._lib_grid_canvas = canvas

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        grid_inner.bind("<Configure>", _on_frame_configure)

        def _on_canvas_configure(e):
            canvas.itemconfig(canvas.find_all()[0], width=e.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        self._lib_tree = None

    def _lib_build_detail_view(self):
        for w in self._lib_content_frame.winfo_children():
            w.destroy()

        cols = ("name", "size", "type", "modified")
        list_frame = tk.Frame(self._lib_content_frame, bg=TH["bg"])
        list_frame.pack(fill="both", expand=True)

        self._lib_tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                       selectmode="extended")
        self._lib_tree.heading("name", text="Name", anchor="w")
        self._lib_tree.heading("size", text="Size", anchor="w")
        self._lib_tree.heading("type", text="Type", anchor="w")
        self._lib_tree.heading("modified", text="Modified", anchor="w")
        self._lib_tree.column("name", width=350, minwidth=200)
        self._lib_tree.column("size", width=80, minwidth=50)
        self._lib_tree.column("type", width=80, minwidth=50)
        self._lib_tree.column("modified", width=150, minwidth=100)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._lib_tree.yview)
        self._lib_tree.configure(yscrollcommand=vsb.set)
        self._lib_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._lib_tree.bind("<Double-1>", lambda e: self._lib_preview())

    def _lib_set_view(self, mode):
        self._lib_view_mode = mode
        if mode == "list":
            self._lib_build_list_view()
        elif mode == "grid":
            self._lib_build_grid_view()
        elif mode == "detail":
            self._lib_build_detail_view()
        self._lib_refresh()

    def _lib_get_selected_names(self):
        if self._lib_view_mode == "grid":
            name = getattr(self, "_lib_grid_selected", None)
            return [name] if name else []
        if self._lib_tree is None:
            return []
        sel = self._lib_tree.selection()
        return [self._lib_tree.item(i, "values")[0] for i in sel]

    def _lib_rename(self):
        names = self._lib_get_selected_names()
        if not names:
            self._lib_status_var.set("No file selected")
            return
        old_name = names[0]
        old_path = os.path.join(self._LIB_DIR, old_name)
        if not os.path.isfile(old_path):
            self._lib_status_var.set("File not found")
            return
        from tkinter import simpledialog
        new_name = simpledialog.askstring("Rename File", "New filename:",
                                           initialvalue=old_name, parent=self)
        if not new_name or new_name == old_name:
            return
        new_path = os.path.join(self._LIB_DIR, new_name)
        if os.path.exists(new_path):
            self._lib_status_var.set("A file with that name already exists")
            return
        try:
            os.rename(old_path, new_path)
            self._lib_status_var.set(f"Renamed to {new_name}")
            self._lib_refresh()
        except Exception as e:
            self._lib_status_var.set(f"Error: {e}")

    def _lib_preview_path(self, fpath, name):
        ftype = self._lib_file_type(name)
        if ftype == "Image":
            self._lib_show_image(fpath, name)
        else:
            try:
                subprocess.Popen(["xdg-open", fpath])
            except Exception:
                self._lib_status_var.set("Cannot open file")

    def _lib_human_size(self, nbytes):
        for unit in ("B", "KB", "MB", "GB"):
            if nbytes < 1024:
                return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
            nbytes /= 1024
        return f"{nbytes:.1f} TB"

    def _lib_file_type(self, name):
        ext = os.path.splitext(name)[1].lower()
        types = {
            ".jpg": "Image", ".jpeg": "Image", ".png": "Image", ".gif": "Image",
            ".bmp": "Image", ".webp": "Image",
            ".mp4": "Video", ".mkv": "Video", ".avi": "Video", ".mov": "Video",
            ".wav": "Audio", ".mp3": "Audio", ".ogg": "Audio", ".flac": "Audio",
            ".m4a": "Audio", ".aac": "Audio", ".webm": "Audio", ".opus": "Audio",
            ".pdf": "PDF", ".txt": "Text", ".md": "Text",
        }
        return types.get(ext, "File")

    def _lib_refresh(self):
        if not os.path.isdir(self._LIB_DIR):
            return

        entries = []
        for fn in sorted(os.listdir(self._LIB_DIR), reverse=True):
            fp = os.path.join(self._LIB_DIR, fn)
            if os.path.isfile(fp):
                entries.append((fn, fp))

        if self._lib_view_mode == "grid":
            for w in self._lib_grid_inner.winfo_children():
                w.destroy()
            col = 0
            row = 0
            cols_per_row = 5
            for fn, fp in entries:
                sz = self._lib_human_size(os.path.getsize(fp))
                ftype = self._lib_file_type(fn)
                cell = tk.Frame(self._lib_grid_inner, bg=TH["card"], bd=1,
                                relief="solid", highlightbackground=TH["border"],
                                highlightthickness=1)
                cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
                self._lib_grid_inner.columnconfigure(col, weight=1)

                icon_map = {"Image": "\U0001f5bc", "Video": "\U0001f3ac",
                            "Audio": "\U0001f3b5", "PDF": "\U0001f4c4",
                            "Text": "\U0001f4dd"}
                icon = icon_map.get(ftype, "\U0001f4c1")
                tk.Label(cell, text=icon, bg=TH["card"], fg=TH["fg"],
                         font=("Segoe UI", 24)).pack(pady=(8, 2))
                tk.Label(cell, text=fn, bg=TH["card"], fg=TH["fg"],
                         font=("Segoe UI", 9), wraplength=120).pack(padx=4)
                tk.Label(cell, text=sz, bg=TH["card"], fg=TH["fg2"],
                         font=("Consolas", 8)).pack(pady=(0, 6))

                def _sel(e, name=fn):
                    self._lib_grid_selected = name
                cell.bind("<Button-1>", _sel)
                for child in cell.winfo_children():
                    child.bind("<Button-1>", _sel)
                cell.bind("<Double-1>", lambda e, path=fp: self._lib_preview_path(path, os.path.basename(path)))

                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1
            self._lib_grid_canvas.update_idletasks()
            self._lib_grid_canvas.configure(scrollregion=self._lib_grid_canvas.bbox("all"))
        elif self._lib_view_mode == "detail":
            import time as _time
            self._lib_tree.delete(*self._lib_tree.get_children())
            for fn, fp in entries:
                sz = self._lib_human_size(os.path.getsize(fp))
                ftype = self._lib_file_type(fn)
                mtime = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(os.path.getmtime(fp)))
                self._lib_tree.insert("", "end", values=(fn, sz, ftype, mtime))
        else:
            self._lib_tree.delete(*self._lib_tree.get_children())
            for fn, fp in entries:
                sz = self._lib_human_size(os.path.getsize(fp))
                ftype = self._lib_file_type(fn)
                self._lib_tree.insert("", "end", values=(fn, sz, ftype))

        self._lib_status_var.set(f"{len(entries)} file(s)")

    def _lib_upload(self):
        paths = filedialog.askopenfilenames(
            title="Select files to upload to Library",
            initialdir=os.path.expanduser("~"))
        if not paths:
            return
        copied = 0
        for p in paths:
            dst = os.path.join(self._LIB_DIR, os.path.basename(p))
            try:
                shutil.copy2(p, dst)
                copied += 1
            except Exception as e:
                self._lib_status_var.set(f"Error: {e}")
        if copied:
            self._lib_status_var.set(f"Uploaded {copied} file(s)")
        self._lib_refresh()

    def _lib_download(self):
        names = self._lib_get_selected_names()
        if not names:
            self._lib_status_var.set("No file selected")
            return
        downloads_dir = os.path.expanduser("~/Downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        saved = 0
        for name in names:
            src = os.path.join(self._LIB_DIR, name)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, os.path.join(downloads_dir, name))
                    saved += 1
                except Exception as e:
                    self._lib_status_var.set(f"Error: {e}")
        self._lib_status_var.set(f"Downloaded {saved} file(s) to Downloads")

    def _lib_delete(self):
        names = self._lib_get_selected_names()
        if not names:
            self._lib_status_var.set("No file selected")
            return
        confirm = messagebox.askyesno(
            "Delete Files",
            f"Delete {len(names)} file(s) from Library?\n\n" + "\n".join(names[:10]))
        if not confirm:
            return
        removed = 0
        for name in names:
            fp = os.path.join(self._LIB_DIR, name)
            try:
                os.remove(fp)
                removed += 1
            except Exception:
                pass
        self._lib_status_var.set(f"Deleted {removed} file(s)")
        self._lib_refresh()

    def _lib_open_folder(self):
        try:
            subprocess.Popen(["xdg-open", self._LIB_DIR])
        except Exception:
            self._lib_status_var.set("Cannot open folder")

    def _lib_preview(self):
        names = self._lib_get_selected_names()
        if not names:
            self._lib_status_var.set("No file selected")
            return
        name = names[0]
        fpath = os.path.join(self._LIB_DIR, name)
        self._lib_preview_path(fpath, name)

    def _lib_show_image(self, fpath, name):
        win = tk.Toplevel(self)
        win.title(f"Library — {name}")
        win.configure(bg="#0e0e0e")
        win.geometry("900x700")
        win.transient(self)

        toolbar = tk.Frame(win, bg=TH["card"], height=36)
        toolbar.pack(fill="x")
        tk.Label(toolbar, text=name, bg=TH["card"], fg=TH["fg"],
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=12, pady=6)
        fsize = self._lib_human_size(os.path.getsize(fpath))
        tk.Label(toolbar, text=fsize, bg=TH["card"], fg=TH["fg2"],
                 font=("Consolas", 9)).pack(side="left", padx=8, pady=6)

        zoom_var = tk.DoubleVar(value=1.0)
        zoom_label = tk.Label(toolbar, text="100%", bg=TH["card"], fg=TH["green"],
                              font=("Consolas", 9))
        zoom_label.pack(side="right", padx=12, pady=6)

        canvas = tk.Canvas(win, bg="#0e0e0e", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        try:
            orig_img = Image.open(fpath).convert("RGBA")
        except Exception as e:
            tk.Label(win, text=f"Cannot load image: {e}", bg="#0e0e0e", fg=TH["red"],
                     font=TH["font"]).pack(pady=20)
            return

        win._orig_img = orig_img
        win._tk_img = None

        def render(event=None):
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw < 2 or ch < 2:
                return
            z = zoom_var.get()
            iw, ih = orig_img.size
            scale = min(cw / iw, ch / ih) * z
            nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
            resized = orig_img.resize((nw, nh), Image.LANCZOS)
            win._tk_img = ImageTk.PhotoImage(resized)
            canvas.delete("all")
            canvas.create_image(cw // 2, ch // 2, image=win._tk_img, anchor="center")
            zoom_label.config(text=f"{int(z * 100)}%")

        canvas.bind("<Configure>", render)

        def on_scroll(event):
            z = zoom_var.get()
            if event.delta > 0 or event.num == 4:
                z = min(z * 1.15, 10.0)
            else:
                z = max(z / 1.15, 0.1)
            zoom_var.set(z)
            render()

        canvas.bind("<MouseWheel>", on_scroll)
        canvas.bind("<Button-4>", on_scroll)
        canvas.bind("<Button-5>", on_scroll)

        win.after(50, render)

    def build_archive(self):
        f = self.tabs["archive"]
        os.makedirs(ARCHIVE_DIR, exist_ok=True)

        root_frame = tk.Frame(f, bg=TH["bg"])
        root_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # -- Header bar --
        header_bar = tk.Frame(root_frame, bg=TH["card"], height=42)
        header_bar.pack(fill="x", pady=(0, 6))
        tk.Label(header_bar, text="Archive — Read / Write / Publish",
                 bg=TH["card"], fg=TH["fg"],
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=12, pady=8)

        self.arc_status_var = tk.StringVar(value="Ready")
        tk.Label(header_bar, textvariable=self.arc_status_var, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9)).pack(side="right", padx=12, pady=8)

        # -- Document action buttons --
        action_bar = tk.Frame(root_frame, bg=TH["card"], height=36)
        action_bar.pack(fill="x", pady=(0, 6))
        for txt, cmd in [("New", self._arc_new), ("Open", self._arc_open),
                         ("Save", self._arc_save), ("Save As", self._arc_save_as),
                         ("Publish", self._arc_publish), ("Delete", self._arc_delete)]:
            self._btn(action_bar, txt, cmd).pack(side="left", padx=4, pady=4)

        tk.Frame(action_bar, bg=TH["border_hi"], width=2).pack(
            side="left", fill="y", padx=8, pady=6)

        self._btn(action_bar, "Undo", self._arc_undo).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Redo", self._arc_redo).pack(side="left", padx=4, pady=4)
        self._btn(action_bar, "Find / Replace", self._arc_find_replace).pack(
            side="left", padx=4, pady=4)
        self._btn(action_bar, "Word Count", self._arc_word_count).pack(
            side="left", padx=4, pady=4)
        self._btn(action_bar, "Print Preview", self._arc_print_preview).pack(
            side="left", padx=4, pady=4)

        # -- Formatting toolbar --
        fmt_bar = tk.Frame(root_frame, bg=TH["card"], height=34)
        fmt_bar.pack(fill="x", pady=(0, 6))

        # Font family
        tk.Label(fmt_bar, text="Font:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(8, 2), pady=4)
        self.arc_font_families = self._arc_scan_fonts()
        self.arc_font_var = tk.StringVar(value="Segoe UI")
        self.arc_font_combo = ttk.Combobox(fmt_bar, textvariable=self.arc_font_var,
                                            values=self.arc_font_families,
                                            width=20, state="readonly")
        self.arc_font_combo.pack(side="left", padx=2, pady=4)
        self.arc_font_combo.bind("<<ComboboxSelected>>", lambda e: self._arc_apply_font())

        # Font size
        tk.Label(fmt_bar, text="Size:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(8, 2), pady=4)
        self.arc_size_var = tk.StringVar(value="11")
        size_vals = [str(s) for s in range(8, 25)]
        self.arc_size_combo = ttk.Combobox(fmt_bar, textvariable=self.arc_size_var,
                                            values=size_vals, width=4, state="readonly")
        self.arc_size_combo.pack(side="left", padx=2, pady=4)
        self.arc_size_combo.bind("<<ComboboxSelected>>", lambda e: self._arc_apply_font())

        tk.Frame(fmt_bar, bg=TH["border_hi"], width=2).pack(
            side="left", fill="y", padx=6, pady=6)

        # Bold / Italic / Underline
        for txt, cmd in [("B", self._arc_toggle_bold),
                         ("I", self._arc_toggle_italic),
                         ("U", self._arc_toggle_underline)]:
            self._btn(fmt_bar, txt, cmd).pack(side="left", padx=2, pady=4)

        # Highlight
        self._btn(fmt_bar, "Highlight", self._arc_toggle_highlight).pack(
            side="left", padx=2, pady=4)

        tk.Frame(fmt_bar, bg=TH["border_hi"], width=2).pack(
            side="left", fill="y", padx=6, pady=6)

        # Alignment
        for txt, cmd in [("Left", self._arc_align_left),
                         ("Center", self._arc_align_center),
                         ("Right", self._arc_align_right)]:
            self._btn(fmt_bar, txt, cmd).pack(side="left", padx=2, pady=4)

        tk.Frame(fmt_bar, bg=TH["border_hi"], width=2).pack(
            side="left", fill="y", padx=6, pady=6)

        # Font color
        tk.Label(fmt_bar, text="Color:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(4, 2), pady=4)
        self.arc_color_var = tk.StringVar(value="#dce4ee")
        self._arc_basic_colors = [
            "#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FFFF00",
            "#FF00FF", "#00FFFF", "#800000", "#008000", "#000080", "#808000",
            "#800080", "#008080", "#C0C0C0", "#808080"
        ]
        self.arc_color_combo = ttk.Combobox(fmt_bar, textvariable=self.arc_color_var,
                                             values=self._arc_basic_colors,
                                             width=9, state="readonly")
        self.arc_color_combo.pack(side="left", padx=2, pady=4)
        self.arc_color_combo.bind("<<ComboboxSelected>>", lambda e: self._arc_apply_color())
        self._btn(fmt_bar, "Pick...", self._arc_pick_color).pack(
            side="left", padx=2, pady=4)

        tk.Frame(fmt_bar, bg=TH["border_hi"], width=2).pack(
            side="left", fill="y", padx=6, pady=6)

        # Bullet lists
        tk.Label(fmt_bar, text="List:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(4, 2), pady=4)
        self.arc_bullet_var = tk.StringVar(value="\u2022  Bullet")
        bullet_opts = ["\u2022  Bullet", "\u2013  Dash", "\u25CB  Circle",
                       "\u25A0  Square", "\u2023  Triangle", "1.  Numbered"]
        self.arc_bullet_combo = ttk.Combobox(fmt_bar, textvariable=self.arc_bullet_var,
                                              values=bullet_opts, width=14,
                                              state="readonly")
        self.arc_bullet_combo.pack(side="left", padx=2, pady=4)
        self._btn(fmt_bar, "Insert List", self._arc_insert_bullet).pack(
            side="left", padx=2, pady=4)

        # -- Two-column body: editor left, file browser right --
        body = tk.Frame(root_frame, bg=TH["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # ========== LEFT: Editor ==========
        left_col = tk.Frame(body, bg=TH["bg"])
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        left_col.rowconfigure(1, weight=1)
        left_col.columnconfigure(0, weight=1)

        # Metadata row
        meta_card = self._card(left_col, "DOCUMENT INFO", fg="#888888")
        meta_card.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        meta_inner = tk.Frame(meta_card, bg=TH["card"])
        meta_inner.pack(fill="x", padx=10, pady=(2, 8))

        tk.Label(meta_inner, text="Title:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self.arc_title_var = tk.StringVar(value="")
        self._entry(meta_inner, self.arc_title_var, width=30).pack(
            side="left", padx=(4, 12))

        tk.Label(meta_inner, text="Date:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self.arc_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self._entry(meta_inner, self.arc_date_var, width=12).pack(
            side="left", padx=(4, 12))

        tk.Label(meta_inner, text="Notes:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self.arc_notes_var = tk.StringVar(value="")
        self._entry(meta_inner, self.arc_notes_var, width=40).pack(
            side="left", padx=(4, 0), fill="x", expand=True)

        # Editor text area
        editor_card = self._card(left_col, "EDITOR", fg="#888888")
        editor_card.grid(row=1, column=0, sticky="nsew")
        editor_inner = tk.Frame(editor_card, bg=TH["card"])
        editor_inner.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        editor_inner.rowconfigure(0, weight=1)
        editor_inner.columnconfigure(0, weight=1)

        self.arc_editor = tk.Text(editor_inner, bg=TH["input"], fg=TH["fg"],
                                   insertbackground=TH["fg"], bd=0,
                                   font=("Segoe UI", 11), wrap="word",
                                   undo=True, maxundo=-1, autoseparators=True,
                                   highlightthickness=1,
                                   highlightbackground=TH["border"],
                                   highlightcolor=TH["btn"],
                                   padx=12, pady=10)
        e_sb = self._scrollbar(editor_inner)
        self.arc_editor.config(yscrollcommand=e_sb.set)
        e_sb.config(command=self.arc_editor.yview)
        self.arc_editor.grid(row=0, column=0, sticky="nsew")
        e_sb.grid(row=0, column=1, sticky="ns")

        self._arc_setup_tags()

        # ========== RIGHT: File Browser ==========
        right_col = tk.Frame(body, bg=TH["bg"])
        right_col.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        right_col.rowconfigure(1, weight=1)
        right_col.columnconfigure(0, weight=1)

        # Saved files
        files_card = self._card(right_col, "ARCHIVE FILES", fg="#888888")
        files_card.grid(row=0, column=0, rowspan=2, sticky="nsew")

        fb_btns = tk.Frame(files_card, bg=TH["card"])
        fb_btns.pack(fill="x", padx=8, pady=4)
        self._btn(fb_btns, "Refresh", self._arc_refresh_files).pack(
            side="left", padx=(0, 4))
        self._btn(fb_btns, "Open Selected", self._arc_open_selected).pack(
            side="left", padx=4)

        file_frame = tk.Frame(files_card, bg=TH["card"])
        file_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        file_frame.rowconfigure(0, weight=1)
        file_frame.columnconfigure(0, weight=1)

        self.arc_file_list = tk.Listbox(file_frame, bg=TH["input"], fg=TH["fg"],
                                         font=TH["font_mono"], bd=0,
                                         highlightthickness=1,
                                         highlightbackground=TH["border"],
                                         highlightcolor=TH["btn"],
                                         selectbackground=TH["select_bg"],
                                         selectforeground=TH["fg"])
        f_sb = self._scrollbar(file_frame)
        self.arc_file_list.config(yscrollcommand=f_sb.set)
        f_sb.config(command=self.arc_file_list.yview)
        self.arc_file_list.grid(row=0, column=0, sticky="nsew")
        f_sb.grid(row=0, column=1, sticky="ns")
        self.arc_file_list.bind("<Double-Button-1>", lambda e: self._arc_open_selected())

        # Changelog / version log at bottom of right column
        log_card = self._card(right_col, "CHANGELOG", fg="#888888")
        log_card.grid(row=2, column=0, sticky="sew", pady=(4, 0))

        self.arc_changelog = tk.Text(log_card, bg=TH["input"], fg=TH["fg2"],
                                      font=TH["font_xs"], wrap="word", height=6,
                                      bd=0, highlightthickness=1,
                                      highlightbackground=TH["border"],
                                      highlightcolor=TH["btn"])
        self.arc_changelog.pack(fill="x", padx=6, pady=(0, 6))
        self.arc_changelog.insert("1.0", "(changelog will appear here)\n")
        self.arc_changelog.config(state="disabled")

        self.arc_current_file = None
        self._arc_refresh_files()

    def _arc_setup_tags(self):
        self.arc_editor.tag_configure("bold", font=("Segoe UI", 11, "bold"))
        self.arc_editor.tag_configure("italic", font=("Segoe UI", 11, "italic"))
        self.arc_editor.tag_configure("underline", underline=True)
        self.arc_editor.tag_configure("highlight", background="#e0a030",
                                       foreground="#000000")
        self.arc_editor.tag_configure("left", justify="left")
        self.arc_editor.tag_configure("center", justify="center")
        self.arc_editor.tag_configure("right", justify="right")

    # -- Document actions --
    def _arc_new(self):
        self.arc_editor.delete("1.0", "end")
        self.arc_title_var.set("")
        self.arc_date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.arc_notes_var.set("")
        self.arc_current_file = None
        self.arc_status_var.set("New document")
        self._arc_changelog_append("New document created")

    def _arc_open(self):
        path = filedialog.askopenfilename(
            initialdir=ARCHIVE_DIR,
            filetypes=[("Text files", "*.txt"), ("ODT files", "*.odt"),
                       ("All files", "*.*")])
        if path:
            self._arc_load_file(path)

    def _arc_load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            self.arc_editor.delete("1.0", "end")
            self.arc_editor.insert("1.0", content)
            self.arc_current_file = path
            base = os.path.basename(path)
            self.arc_title_var.set(os.path.splitext(base)[0])
            self.arc_status_var.set(f"Opened: {base}")
            self._arc_changelog_append(f"Opened {base}")
        except Exception as exc:
            self.arc_status_var.set(f"Error: {exc}")

    def _arc_save(self):
        if self.arc_current_file:
            self._arc_write_file(self.arc_current_file)
        else:
            self._arc_save_as()

    def _arc_save_as(self):
        title = self.arc_title_var.get().strip() or "Untitled"
        date_str = self.arc_date_var.get().strip()
        default_name = f"{date_str}_{title}.txt" if date_str else f"{title}.txt"
        path = filedialog.asksaveasfilename(
            initialdir=ARCHIVE_DIR, initialfile=default_name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("ODT files", "*.odt"),
                       ("All files", "*.*")])
        if path:
            self._arc_write_file(path)

    def _arc_write_file(self, path):
        try:
            content = self.arc_editor.get("1.0", "end-1c")
            notes = self.arc_notes_var.get().strip()
            date_str = self.arc_date_var.get().strip()
            header = f"--- Archive Entry ---\nDate: {date_str}\nNotes: {notes}\n---\n\n"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(header + content)
            self.arc_current_file = path
            base = os.path.basename(path)
            self.arc_status_var.set(f"Saved: {base}")
            self._arc_changelog_append(f"Saved {base}")
            self._arc_refresh_files()
        except Exception as exc:
            self.arc_status_var.set(f"Save error: {exc}")

    def _arc_publish(self):
        if not self.arc_current_file:
            self._arc_save_as()
        if self.arc_current_file:
            base = os.path.basename(self.arc_current_file)
            self.arc_status_var.set(f"Published: {base}")
            self._arc_changelog_append(f"Published {base} at {datetime.now().strftime('%H:%M:%S')}")

    def _arc_delete(self):
        sel = self.arc_file_list.curselection()
        if not sel:
            self.arc_status_var.set("Select a file to delete")
            return
        name = self.arc_file_list.get(sel[0])
        path = os.path.join(ARCHIVE_DIR, name)
        if os.path.isfile(path):
            os.remove(path)
            self._arc_changelog_append(f"Deleted {name}")
            self._arc_refresh_files()
            if self.arc_current_file == path:
                self._arc_new()

    def _arc_undo(self):
        try:
            self.arc_editor.edit_undo()
        except tk.TclError:
            pass

    def _arc_redo(self):
        try:
            self.arc_editor.edit_redo()
        except tk.TclError:
            pass

    def _arc_find_replace(self):
        win = tk.Toplevel(self, bg=TH["bg"])
        win.title("Find / Replace")
        win.geometry("400x160")
        win.transient(self)

        tk.Label(win, text="Find:", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font_sm"]).grid(row=0, column=0, padx=8, pady=6, sticky="e")
        find_var = tk.StringVar()
        self._entry(win, find_var, width=30).grid(row=0, column=1, padx=4, pady=6)

        tk.Label(win, text="Replace:", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font_sm"]).grid(row=1, column=0, padx=8, pady=6, sticky="e")
        repl_var = tk.StringVar()
        self._entry(win, repl_var, width=30).grid(row=1, column=1, padx=4, pady=6)

        btn_row = tk.Frame(win, bg=TH["bg"])
        btn_row.grid(row=2, column=0, columnspan=2, pady=10)

        def do_find():
            self.arc_editor.tag_remove("sel", "1.0", "end")
            txt = find_var.get()
            if not txt:
                return
            idx = self.arc_editor.search(txt, "1.0", stopindex="end")
            if idx:
                end_idx = f"{idx}+{len(txt)}c"
                self.arc_editor.tag_add("sel", idx, end_idx)
                self.arc_editor.mark_set("insert", end_idx)
                self.arc_editor.see(idx)

        def do_replace_all():
            txt = find_var.get()
            repl = repl_var.get()
            if not txt:
                return
            content = self.arc_editor.get("1.0", "end-1c")
            new_content = content.replace(txt, repl)
            self.arc_editor.delete("1.0", "end")
            self.arc_editor.insert("1.0", new_content)

        self._btn(btn_row, "Find", do_find).pack(side="left", padx=4)
        self._btn(btn_row, "Replace All", do_replace_all).pack(side="left", padx=4)
        self._btn(btn_row, "Close", win.destroy).pack(side="left", padx=4)

    def _arc_word_count(self):
        content = self.arc_editor.get("1.0", "end-1c")
        words = len(content.split())
        chars = len(content)
        lines = content.count("\n") + 1
        self.arc_status_var.set(f"Words: {words}  |  Chars: {chars}  |  Lines: {lines}")

    def _arc_print_preview(self):
        self.arc_status_var.set("Print preview not yet implemented")

    # -- Formatting --
    def _arc_apply_tag_toggle(self, tag_name):
        try:
            sel_range = self.arc_editor.tag_ranges("sel")
            if sel_range:
                start, end = sel_range[0], sel_range[1]
                current_tags = self.arc_editor.tag_names(start)
                if tag_name in current_tags:
                    self.arc_editor.tag_remove(tag_name, start, end)
                else:
                    self.arc_editor.tag_add(tag_name, start, end)
        except tk.TclError:
            pass

    def _arc_toggle_bold(self):
        self._arc_apply_tag_toggle("bold")

    def _arc_toggle_italic(self):
        self._arc_apply_tag_toggle("italic")

    def _arc_toggle_underline(self):
        self._arc_apply_tag_toggle("underline")

    def _arc_toggle_highlight(self):
        self._arc_apply_tag_toggle("highlight")

    def _arc_apply_font(self):
        family = self.arc_font_var.get()
        size = int(self.arc_size_var.get())
        self.arc_editor.config(font=(family, size))
        self._arc_setup_tags()

    def _arc_align_left(self):
        self._arc_set_alignment("left")

    def _arc_align_center(self):
        self._arc_set_alignment("center")

    def _arc_align_right(self):
        self._arc_set_alignment("right")

    def _arc_set_alignment(self, align):
        try:
            sel_range = self.arc_editor.tag_ranges("sel")
            if sel_range:
                start, end = sel_range[0], sel_range[1]
            else:
                start = "insert linestart"
                end = "insert lineend"
            for a in ("left", "center", "right"):
                self.arc_editor.tag_remove(a, start, end)
            self.arc_editor.tag_add(align, start, end)
        except tk.TclError:
            pass

    def _arc_apply_color(self):
        color = self.arc_color_var.get()
        try:
            sel_range = self.arc_editor.tag_ranges("sel")
            if sel_range:
                tag_name = f"color_{color.replace('#', '')}"
                self.arc_editor.tag_configure(tag_name, foreground=color)
                self.arc_editor.tag_add(tag_name, sel_range[0], sel_range[1])
        except tk.TclError:
            pass

    def _arc_pick_color(self):
        result = colorchooser.askcolor(initialcolor=self.arc_color_var.get(),
                                        title="Choose font color")
        if result and result[1]:
            self.arc_color_var.set(result[1])
            self._arc_apply_color()

    def _arc_insert_bullet(self):
        choice = self.arc_bullet_var.get()
        prefix_map = {
            "\u2022  Bullet": "\u2022 ",
            "\u2013  Dash": "\u2013 ",
            "\u25CB  Circle": "\u25CB ",
            "\u25A0  Square": "\u25A0 ",
            "\u2023  Triangle": "\u2023 ",
            "1.  Numbered": None,
        }
        prefix = prefix_map.get(choice, "\u2022 ")
        try:
            sel_range = self.arc_editor.tag_ranges("sel")
            if sel_range:
                start_line = int(str(sel_range[0]).split(".")[0])
                end_line = int(str(sel_range[1]).split(".")[0])
            else:
                start_line = int(self.arc_editor.index("insert").split(".")[0])
                end_line = start_line
            for i, line_no in enumerate(range(start_line, end_line + 1)):
                line_start = f"{line_no}.0"
                if prefix is None:
                    self.arc_editor.insert(line_start, f"{i + 1}. ")
                else:
                    self.arc_editor.insert(line_start, prefix)
        except tk.TclError:
            pass

    # -- File browser --
    def _arc_refresh_files(self):
        self.arc_file_list.delete(0, "end")
        if not os.path.isdir(ARCHIVE_DIR):
            self.arc_file_list.insert("end", "(ARCHIVE folder not found)")
            return
        files = sorted(os.listdir(ARCHIVE_DIR), reverse=True)
        files = [fn for fn in files if os.path.isfile(os.path.join(ARCHIVE_DIR, fn))]
        if not files:
            self.arc_file_list.insert("end", "(empty)")
            return
        for fn in files:
            self.arc_file_list.insert("end", fn)

    def _arc_open_selected(self):
        sel = self.arc_file_list.curselection()
        if not sel:
            self.arc_status_var.set("Select a file first")
            return
        name = self.arc_file_list.get(sel[0])
        if name.startswith("("):
            return
        path = os.path.join(ARCHIVE_DIR, name)
        self._arc_load_file(path)

    def _arc_changelog_append(self, msg):
        self.arc_changelog.config(state="normal")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.arc_changelog.insert("end", f"[{ts}] {msg}\n")
        self.arc_changelog.see("end")
        self.arc_changelog.config(state="disabled")

    # ==================== SS (SCREEN SHARE) TAB ====================

    _ss_server = None
    _ss_server_thread = None
    _ss_capture_thread = None
    _ss_capturing = False
    _ss_latest_desktop_jpeg = b""
    _ss_latest_phone_jpeg = b""
    _ss_phone_feeds = {}
    _ss_phone_last_ts = 0
    _ss_connected_clients = 0
    _ss_fps = 10
    _ss_quality = 40
    _SS_HTTPS_PORT = 8092
    _ss_ssl_ctx = None

    SS_MOBILE_HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#1e1e1e">
<title>Whim SS</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:#1e1e1e;color:#dce4ee;font-family:-apple-system,system-ui,'Segoe UI',sans-serif;
  height:100vh;overflow:hidden;display:flex;flex-direction:column}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;
  background:#2b2b2b;border-bottom:1px solid #3a3a3a;font-size:11px;font-family:'Courier New',monospace}
.topbar .dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px;vertical-align:middle}
.dot.ok{background:#2fa572}.dot.warn{background:#e0a030}.dot.fail{background:#d94040}
.mode-tabs{display:flex;gap:0;background:#2b2b2b;border-bottom:1px solid #3a3a3a}
.mode-tab{flex:1;text-align:center;padding:10px 0;font-size:13px;font-weight:600;
  color:#666;cursor:pointer;border-bottom:2px solid transparent;transition:all .2s}
.mode-tab.active{color:#00ff00;border-bottom-color:#00ff00}
.view{display:none;flex:1;flex-direction:column;overflow:hidden}
.view.active{display:flex}
.stream-area{flex:1;display:flex;align-items:center;justify-content:center;background:#111;
  position:relative;overflow:hidden}
.stream-area img,.stream-area video{max-width:100%;max-height:100%;object-fit:contain}
.stream-placeholder{color:#555;font-size:14px;font-family:'Courier New',monospace;text-align:center;padding:20px}
.cam-controls{display:flex;gap:12px;justify-content:center;align-items:center;
  padding:12px;background:#2b2b2b;border-top:1px solid #3a3a3a}
.cam-btn{width:56px;height:56px;border-radius:50%;border:2px solid #3a3a3a;background:#1e1e1e;
  cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .2s}
.cam-btn:active{transform:scale(.92)}
.cam-btn.active{border-color:#2fa572;background:#1a2a1a}
.cam-btn svg{width:24px;height:24px}
.cam-btn.stop{border-color:#d94040}
.cam-btn.stop svg{stroke:#d94040}
.cam-switch{padding:8px 16px;background:#14507a;color:#fff;border:none;border-radius:6px;
  font-size:12px;cursor:pointer}
.cam-switch:active{background:#0f3d5e}
.status-bar{padding:4px 12px;background:#2b2b2b;font-size:10px;color:#555;
  font-family:'Courier New',monospace;text-align:center;border-top:1px solid #3a3a3a}
.sec-warning{background:#2a1a0a;border:1px solid #e0a030;border-radius:8px;padding:12px 16px;
  margin:12px;font-size:12px;color:#e0a030;line-height:1.5;display:none}
.sec-warning a{color:#00ff00}
.sec-warning code{background:#1e1e1e;padding:2px 6px;border-radius:3px;font-size:11px}
.device-id{font-size:9px;color:#555;font-family:'Courier New',monospace}
</style></head><body>

<div class="topbar">
  <span><span class="dot" id="dotConn"></span>connection</span>
  <span><span class="dot" id="dotCam"></span>camera</span>
  <span style="color:#00ff00;font-weight:bold">WHIM SS</span>
  <span class="device-id" id="deviceId"></span>
</div>

<div class="mode-tabs">
  <div class="mode-tab active" data-mode="watch">WATCH DESKTOP</div>
  <div class="mode-tab" data-mode="share">SHARE CAMERA</div>
</div>

<div class="view active" id="watchView">
  <div class="stream-area" id="desktopStream">
    <span class="stream-placeholder" id="watchPlaceholder">tap to connect</span>
    <img id="desktopImg" style="display:none" alt="Desktop stream">
  </div>
  <div class="status-bar" id="watchStatus">disconnected</div>
</div>

<div class="view" id="shareView">
  <div class="sec-warning" id="secWarning">
    <strong>Camera blocked — HTTP not secure enough</strong><br>
    On Samsung, open Chrome and go to:<br>
    <code>chrome://flags/#unsafely-treat-insecure-origin-as-secure</code><br>
    Add this server URL, tap <em>Enabled</em>, then <em>Relaunch</em>.<br>
    Or connect via <code>https://</code> (port 8092).
  </div>
  <div class="stream-area" id="camPreview">
    <video id="camVideo" playsinline autoplay muted style="display:none"></video>
    <canvas id="camCanvas" style="display:none"></canvas>
    <span class="stream-placeholder" id="camPlaceholder">tap start to share camera</span>
  </div>
  <div class="cam-controls">
    <div class="cam-btn" id="camStartBtn">
      <svg viewBox="0 0 24 24" fill="none" stroke="#2fa572" stroke-width="2">
        <path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
    </div>
    <div class="cam-btn stop" id="camStopBtn" style="display:none">
      <svg viewBox="0 0 24 24" fill="none" stroke="#d94040" stroke-width="2">
        <rect x="6" y="6" width="12" height="12" rx="1"/></svg>
    </div>
    <button class="cam-switch" id="camFlipBtn">FLIP</button>
  </div>
  <div class="status-bar" id="camStatus">camera idle</div>
</div>

<script>
const BASE=location.origin;
const DEVICE_ID='phone_'+Math.random().toString(36).substring(2,8);
document.getElementById('deviceId').textContent=DEVICE_ID;
let camStream=null,camSending=false,facingMode='environment',sendInterval=null;

// Mode tabs
document.querySelectorAll('.mode-tab').forEach(tab=>{
  tab.addEventListener('click',()=>{
    document.querySelectorAll('.mode-tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.mode==='watch'?'watchView':'shareView').classList.add('active');
  });
});

// Desktop watch
const desktopImg=document.getElementById('desktopImg');
const watchPlaceholder=document.getElementById('watchPlaceholder');
const watchStatus=document.getElementById('watchStatus');
const dotConn=document.getElementById('dotConn');

function startWatch(){
  desktopImg.src=BASE+'/desktop_stream?t='+Date.now();
  desktopImg.style.display='block';
  watchPlaceholder.style.display='none';
  desktopImg.onerror=()=>{
    dotConn.className='dot fail';
    watchStatus.textContent='stream disconnected';
    desktopImg.style.display='none';
    watchPlaceholder.style.display='';
    watchPlaceholder.textContent='stream ended — tap to reconnect';
  };
  desktopImg.onload=()=>{dotConn.className='dot ok';watchStatus.textContent='streaming'};
  dotConn.className='dot warn';
  watchStatus.textContent='connecting...';
}
document.getElementById('desktopStream').addEventListener('click',startWatch);

// Health check
async function checkConn(){
  try{const r=await fetch(BASE+'/ss_health',{signal:AbortSignal.timeout(3000)});
    if(r.ok){dotConn.className='dot ok'}else{dotConn.className='dot warn'}
  }catch(e){dotConn.className='dot fail'}
}
checkConn();setInterval(checkConn,10000);

// Secure context check
const isSecure=location.protocol==='https:'||location.hostname==='localhost'||location.hostname==='127.0.0.1';
if(!isSecure){document.getElementById('secWarning').style.display='block'}

// Camera share
const camVideo=document.getElementById('camVideo');
const camCanvas=document.getElementById('camCanvas');
const camCtx=camCanvas.getContext('2d');
const camPlaceholder=document.getElementById('camPlaceholder');
const camStatus=document.getElementById('camStatus');
const dotCam=document.getElementById('dotCam');
const camStartBtn=document.getElementById('camStartBtn');
const camStopBtn=document.getElementById('camStopBtn');
const camFlipBtn=document.getElementById('camFlipBtn');

async function startCam(){
  if(!isSecure&&!navigator.mediaDevices){
    camStatus.textContent='camera requires HTTPS — see instructions above';
    dotCam.className='dot fail';return;
  }
  try{
    if(camStream){camStream.getTracks().forEach(t=>t.stop())}
    camStream=await navigator.mediaDevices.getUserMedia({
      video:{facingMode:facingMode,width:{ideal:640},height:{ideal:480}},audio:false});
    camVideo.srcObject=camStream;
    await camVideo.play();
    camVideo.style.display='block';
    camPlaceholder.style.display='none';
    if(!isSecure){document.getElementById('secWarning').style.display='none'}
    dotCam.className='dot ok';
    camStartBtn.style.display='none';
    camStopBtn.style.display='flex';
    camStatus.textContent='sharing camera ['+DEVICE_ID+']';
    camSending=true;
    function waitReady(){
      if(camVideo.videoWidth>0&&camVideo.videoHeight>0){
        sendInterval=setInterval(sendFrame,100);
        camStatus.textContent='sharing ('+camVideo.videoWidth+'x'+camVideo.videoHeight+') ['+DEVICE_ID+']';
      }else{setTimeout(waitReady,100)}
    }
    waitReady();
  }catch(e){
    dotCam.className='dot fail';
    camStatus.textContent='camera denied: '+e.message;
    if(e.name==='NotAllowedError'||e.name==='SecurityError'){
      document.getElementById('secWarning').style.display='block';
    }
  }
}

function stopCam(){
  camSending=false;
  if(sendInterval){clearInterval(sendInterval);sendInterval=null}
  if(camStream){camStream.getTracks().forEach(t=>t.stop());camStream=null}
  camVideo.style.display='none';
  camPlaceholder.style.display='';
  camPlaceholder.textContent='camera stopped';
  camStartBtn.style.display='flex';
  camStopBtn.style.display='none';
  dotCam.className='dot warn';
  camStatus.textContent='camera idle';
}

function sendFrame(){
  if(!camSending||!camStream)return;
  const vw=camVideo.videoWidth,vh=camVideo.videoHeight;
  if(!vw||!vh)return;
  camCanvas.width=vw;camCanvas.height=vh;
  camCtx.drawImage(camVideo,0,0,vw,vh);
  camCanvas.toBlob(blob=>{
    if(!blob||!camSending)return;
    fetch(BASE+'/phone_frame',{method:'POST',
      headers:{'Content-Type':'image/jpeg','X-Device-Id':DEVICE_ID},body:blob})
      .catch(()=>{});
  },'image/jpeg',0.6);
}

camStartBtn.addEventListener('click',startCam);
camStopBtn.addEventListener('click',stopCam);
camFlipBtn.addEventListener('click',()=>{
  facingMode=facingMode==='environment'?'user':'environment';
  if(camSending)startCam();
});
</script></body></html>"""

    def build_ss(self):
        f = self.tabs["ss"]

        root_frame = tk.Frame(f, bg=TH["bg"])
        root_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._ss_status_var = tk.StringVar(value="Stopped")
        self._ss_url_var = tk.StringVar(value="")
        self._ss_fps_var = tk.StringVar(value=str(self._ss_fps))
        self._ss_quality_var = tk.StringVar(value=str(self._ss_quality))
        self._ss_cam_var = tk.StringVar(value="(none)")
        self._ss_clients_var = tk.StringVar(value="0 clients")

        # -- Header bar --
        header = tk.Frame(root_frame, bg=TH["card"], height=42)
        header.pack(fill="x", pady=(0, 4))

        tk.Label(header, text="\U0001F4F9", bg=TH["card"], font=("Segoe UI", 14), bd=0
                 ).pack(side="left", padx=(12, 8), pady=8)
        tk.Label(header, text="SCREEN SHARE", bg=TH["card"], fg=TH["green"],
                 font=TH["font_title"]).pack(side="left", padx=(0, 12), pady=8)

        self._btn(header, "Start Server", self._ss_start_server).pack(side="left", padx=4, pady=6)
        self._btn(header, "Stop Server", self._ss_stop_server).pack(side="left", padx=4, pady=6)
        self._btn(header, "Detect Cameras", self._ss_detect_cameras).pack(side="left", padx=4, pady=6)
        tk.Label(header, text="COMING SOON", bg=TH["card"],
                 fg=TH["yellow"], font=("Consolas", 9, "bold")).pack(side="left", padx=(8, 2), pady=6)
        tk.Label(header, text="previous beta mobile tailscale weak bandwidth, tunnel yet to test", bg=TH["card"],
                 fg=TH["fg_dim"], font=("Consolas", 8)).pack(side="left", padx=(2, 8), pady=6)

        tk.Label(header, textvariable=self._ss_status_var, bg=TH["card"],
                 fg=TH["yellow"], font=("Consolas", 9)).pack(side="right", padx=6, pady=6)
        tk.Label(header, textvariable=self._ss_clients_var, bg=TH["card"],
                 fg=TH["fg2"], font=("Consolas", 9)).pack(side="right", padx=4, pady=6)
        tk.Label(header, textvariable=self._ss_url_var, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9)).pack(side="right", padx=4, pady=6)

        # -- Main layout: left=settings+QR, center=phone cam, right=desktop preview --
        columns = tk.Frame(root_frame, bg=TH["bg"])
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=1)
        columns.columnconfigure(1, weight=3)
        columns.columnconfigure(2, weight=2)
        columns.rowconfigure(0, weight=1)

        # === LEFT: Settings + QR ===
        left = tk.Frame(columns, bg=TH["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        settings_card = self._card(left, "SETTINGS", fg="#888888")
        settings_card.pack(fill="x", pady=(0, 4))

        row1 = tk.Frame(settings_card, bg=TH["card"])
        row1.pack(fill="x", padx=10, pady=4)
        tk.Label(row1, text="FPS:", bg=TH["card"], fg=TH["fg2"], font=TH["font_sm"]
                 ).pack(side="left")
        fps_entry = self._entry(row1, self._ss_fps_var, width=4)
        fps_entry.pack(side="left", padx=4)

        row2 = tk.Frame(settings_card, bg=TH["card"])
        row2.pack(fill="x", padx=10, pady=4)
        tk.Label(row2, text="Quality:", bg=TH["card"], fg=TH["fg2"], font=TH["font_sm"]
                 ).pack(side="left")
        qual_entry = self._entry(row2, self._ss_quality_var, width=4)
        qual_entry.pack(side="left", padx=4)
        tk.Label(row2, text="(1-95)", bg=TH["card"], fg=TH["fg_dim"], font=TH["font_xs"]
                 ).pack(side="left", padx=4)

        row3 = tk.Frame(settings_card, bg=TH["card"])
        row3.pack(fill="x", padx=10, pady=(4, 8))
        tk.Label(row3, text="Camera:", bg=TH["card"], fg=TH["fg2"], font=TH["font_sm"]
                 ).pack(side="left")
        self._ss_cam_combo = ttk.Combobox(row3, textvariable=self._ss_cam_var,
                                           values=["(none)"], width=14, state="readonly")
        self._ss_cam_combo.pack(side="left", padx=4)

        qr_card = self._card(left, "QR CODE", fg="#888888")
        qr_card.pack(fill="both", expand=True, pady=(4, 0))

        self._ss_qr_canvas = tk.Canvas(qr_card, bg=TH["input"], bd=0,
                                        highlightthickness=1,
                                        highlightbackground=TH["border"])
        self._ss_qr_canvas.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._ss_qr_img = None

        # === CENTER: Phone camera feed ===
        center = tk.Frame(columns, bg=TH["bg"])
        center.grid(row=0, column=1, sticky="nsew", padx=4)

        phone_card = self._card(center, "PHONE CAMERA FEED", fg="#888888")
        phone_card.pack(fill="both", expand=True)

        self._ss_phone_canvas = tk.Canvas(phone_card, bg=TH["input"], bd=0,
                                           highlightthickness=1,
                                           highlightbackground=TH["border"])
        self._ss_phone_canvas.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._ss_phone_canvas.create_text(200, 120, text="[ waiting for phone camera ]",
                                           fill=TH["fg_dim"], font=TH["font_mono"])
        self._ss_phone_photo = None

        # === RIGHT: Desktop preview ===
        right = tk.Frame(columns, bg=TH["bg"])
        right.grid(row=0, column=2, sticky="nsew", padx=(4, 0))

        preview_card = self._card(right, "DESKTOP PREVIEW", fg="#888888")
        preview_card.pack(fill="both", expand=True)

        self._ss_preview_canvas = tk.Canvas(preview_card, bg=TH["input"], bd=0,
                                             highlightthickness=1,
                                             highlightbackground=TH["border"])
        self._ss_preview_canvas.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._ss_preview_canvas.create_text(150, 100, text="[ preview ]",
                                             fill=TH["fg_dim"], font=TH["font_mono"])
        self._ss_preview_photo = None

        self._ss_detect_cameras()

    def _ss_detect_cameras(self):
        cams = ["(none)"]
        v4l_dir = "/sys/class/video4linux"
        if os.path.isdir(v4l_dir):
            for dev in sorted(os.listdir(v4l_dir)):
                name_path = os.path.join(v4l_dir, dev, "name")
                label = dev
                if os.path.isfile(name_path):
                    try:
                        with open(name_path) as nf:
                            label = f"{dev} ({nf.read().strip()})"
                    except Exception:
                        pass
                cams.append(label)
        self._ss_cam_combo.configure(values=cams)
        if len(cams) > 1:
            self._ss_cam_var.set(cams[1])
        else:
            self._ss_cam_var.set("(none)")
        self._ss_status_var.set(f"{len(cams)-1} camera(s) found")

    def _ss_start_server(self):
        if self._ss_server is not None:
            self._ss_status_var.set("Already running")
            return
        try:
            self._ss_fps = max(1, min(30, int(self._ss_fps_var.get())))
        except ValueError:
            self._ss_fps = 10
        try:
            self._ss_quality = max(1, min(95, int(self._ss_quality_var.get())))
        except ValueError:
            self._ss_quality = 40

        app_ref = self

        class SSHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if self.path == "/" or self.path.startswith("/?"):
                    data = app_ref.SS_MOBILE_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path.startswith("/desktop_stream"):
                    self.send_response(200)
                    self.send_header("Content-Type",
                                     "multipart/x-mixed-replace; boundary=frame")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    try:
                        while app_ref._ss_capturing:
                            frame = app_ref._ss_latest_desktop_jpeg
                            if frame:
                                self.wfile.write(b"--frame\r\n")
                                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                                self.wfile.write(
                                    f"Content-Length: {len(frame)}\r\n\r\n".encode())
                                self.wfile.write(frame)
                                self.wfile.write(b"\r\n")
                                self.wfile.flush()
                            time.sleep(1.0 / app_ref._ss_fps)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                elif self.path == "/ss_health":
                    import json as _j
                    feeds = {k: round(time.time()-v[1],1) for k,v in app_ref._ss_phone_feeds.items()
                             if time.time()-v[1] < 30}
                    data = _j.dumps({"status": "ok", "capturing": app_ref._ss_capturing,
                                     "phones": feeds, "tail": "WHIM_SS_TAIL_OK"}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                elif self.path.startswith("/phone_stream"):
                    import urllib.parse as _up
                    qs = _up.urlparse(self.path).query
                    params = _up.parse_qs(qs)
                    dev_id = params.get("device", [None])[0]
                    self.send_response(200)
                    self.send_header("Content-Type",
                                     "multipart/x-mixed-replace; boundary=pframe")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    try:
                        while app_ref._ss_server is not None:
                            frame = None
                            if dev_id and dev_id in app_ref._ss_phone_feeds:
                                frame = app_ref._ss_phone_feeds[dev_id][0]
                            elif app_ref._ss_latest_phone_jpeg:
                                frame = app_ref._ss_latest_phone_jpeg
                            if frame:
                                self.wfile.write(b"--pframe\r\n")
                                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                                self.wfile.write(
                                    f"Content-Length: {len(frame)}\r\n\r\n".encode())
                                self.wfile.write(frame)
                                self.wfile.write(b"\r\n")
                                self.wfile.flush()
                            time.sleep(0.1)
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                elif self.path == "/tail_verify":
                    tail = "WHIM_SS_TAIL_OK:{}:phones={}".format(
                        datetime.now().strftime("%H:%M:%S"),
                        len([k for k,v in app_ref._ss_phone_feeds.items()
                             if time.time()-v[1]<30])).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(tail)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(tail)
                else:
                    self.send_error(404)

            def do_POST(self):
                if self.path == "/phone_frame":
                    length = int(self.headers.get("Content-Length", 0))
                    dev_id = self.headers.get("X-Device-Id", "unknown")
                    if length > 0 and length < 5_000_000:
                        data = self.rfile.read(length)
                        app_ref._ss_latest_phone_jpeg = data
                        app_ref._ss_phone_last_ts = time.time()
                        app_ref._ss_phone_feeds[dev_id] = (data, time.time())
                    self.send_response(200)
                    self.send_header("Content-Length", "0")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                else:
                    self.send_error(404)

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Device-Id")
                self.end_headers()

        try:
            self._ss_server = HTTPServer(("0.0.0.0", DEFAULT_SS_PORT), SSHandler)
        except OSError as e:
            self._ss_status_var.set(f"Port {DEFAULT_SS_PORT} in use")
            return

        self._ss_server_thread = threading.Thread(
            target=self._ss_server.serve_forever, daemon=True)
        self._ss_server_thread.start()

        # Start HTTPS server for camera access on phones
        self._ss_https_server = None
        try:
            import ssl
            cert_path = os.path.expanduser("~/.openclaw/ss_cert.pem")
            key_path = os.path.expanduser("~/.openclaw/ss_key.pem")
            if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
                subprocess.run([
                    "openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", key_path, "-out", cert_path,
                    "-days", "3650", "-nodes",
                    "-subj", "/CN=whim-ss/O=Whim/C=US"
                ], capture_output=True, timeout=10)
            if os.path.isfile(cert_path) and os.path.isfile(key_path):
                https_srv = HTTPServer(("0.0.0.0", self._SS_HTTPS_PORT), SSHandler)
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(cert_path, key_path)
                https_srv.socket = ctx.wrap_socket(https_srv.socket, server_side=True)
                self._ss_https_server = https_srv
                threading.Thread(target=https_srv.serve_forever, daemon=True).start()
        except Exception:
            pass

        self._ss_capturing = True
        self._ss_phone_feeds = {}
        self._ss_capture_thread = threading.Thread(
            target=self._ss_capture_loop, daemon=True)
        self._ss_capture_thread.start()

        lan_ip = _get_lan_ip()
        url = f"http://{lan_ip}:{DEFAULT_SS_PORT}"
        https_url = f"https://{lan_ip}:{self._SS_HTTPS_PORT}"
        self._ss_url_var.set(f"{url}  |  {https_url}")
        self._ss_status_var.set("Streaming (HTTP+HTTPS)")
        self._ss_generate_qr(https_url)
        self._ss_poll_phone_feed()

    def _ss_stop_server(self):
        self._ss_capturing = False
        if self._ss_server:
            try:
                self._ss_server.shutdown()
            except Exception:
                pass
            self._ss_server = None
        if self._ss_https_server:
            try:
                self._ss_https_server.shutdown()
            except Exception:
                pass
            self._ss_https_server = None
        self._ss_server_thread = None
        self._ss_capture_thread = None
        self._ss_status_var.set("Stopped")
        self._ss_url_var.set("")
        self._ss_clients_var.set("0 clients")
        self._ss_latest_desktop_jpeg = b""
        self._ss_latest_phone_jpeg = b""
        self._ss_phone_feeds = {}

    def _ss_capture_loop(self):
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                while self._ss_capturing:
                    img = sct.grab(monitor)
                    pil_img = Image.frombytes("RGB", img.size,
                                              img.bgra, "raw", "BGRX")
                    max_w = 1280
                    if pil_img.width > max_w:
                        ratio = max_w / pil_img.width
                        pil_img = pil_img.resize(
                            (max_w, int(pil_img.height * ratio)),
                            Image.LANCZOS)
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG",
                                 quality=self._ss_quality)
                    self._ss_latest_desktop_jpeg = buf.getvalue()
                    self.after(0, self._ss_update_preview)
                    time.sleep(1.0 / self._ss_fps)
        except Exception as e:
            self.after(0, lambda: self._ss_status_var.set(f"Capture error: {e}"))
            self._ss_capturing = False

    def _ss_update_preview(self):
        frame = self._ss_latest_desktop_jpeg
        if not frame:
            return
        try:
            pil_img = Image.open(io.BytesIO(frame))
            canvas = self._ss_preview_canvas
            canvas.update_idletasks()
            cw = max(canvas.winfo_width(), 100)
            ch = max(canvas.winfo_height(), 80)
            ratio = min(cw / pil_img.width, ch / pil_img.height)
            new_w = max(1, int(pil_img.width * ratio))
            new_h = max(1, int(pil_img.height * ratio))
            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
            self._ss_preview_photo = ImageTk.PhotoImage(pil_img)
            canvas.delete("all")
            canvas.create_image(cw // 2, ch // 2, image=self._ss_preview_photo)
        except Exception:
            pass

    def _ss_poll_phone_feed(self):
        if not self._ss_capturing and self._ss_server is None:
            return
        # Show count of active phone feeds
        active = [k for k,v in self._ss_phone_feeds.items() if time.time()-v[1] < 5]
        if active:
            self._ss_clients_var.set(f"{len(active)} phone(s): {', '.join(active)}")
        frame = self._ss_latest_phone_jpeg
        if frame and (time.time() - self._ss_phone_last_ts) < 5:
            try:
                pil_img = Image.open(io.BytesIO(frame))
                canvas = self._ss_phone_canvas
                canvas.update_idletasks()
                cw = max(canvas.winfo_width(), 100)
                ch = max(canvas.winfo_height(), 80)
                ratio = min(cw / pil_img.width, ch / pil_img.height)
                new_w = max(1, int(pil_img.width * ratio))
                new_h = max(1, int(pil_img.height * ratio))
                pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                self._ss_phone_photo = ImageTk.PhotoImage(pil_img)
                canvas.delete("all")
                canvas.create_image(cw // 2, ch // 2, image=self._ss_phone_photo)
            except Exception:
                pass
        self.after(100, self._ss_poll_phone_feed)

    def _ss_generate_qr(self, url):
        try:
            qr_img = qrcode.make(url, box_size=4, border=2)
            qr_img = qr_img.convert("RGB")
            canvas = self._ss_qr_canvas
            canvas.update_idletasks()
            cw = max(canvas.winfo_width(), 100)
            ch = max(canvas.winfo_height(), 100)
            sz = min(cw, ch) - 10
            if sz > 10:
                qr_img = qr_img.resize((sz, sz), Image.LANCZOS)
            self._ss_qr_img = ImageTk.PhotoImage(qr_img)
            canvas.delete("all")
            canvas.create_image(cw // 2, ch // 2, image=self._ss_qr_img)
        except Exception:
            self._ss_qr_canvas.delete("all")
            self._ss_qr_canvas.create_text(80, 80, text=url,
                                            fill=TH["green"], font=TH["font_xs"])

    # ==================== EVENTS / DEBUG TAB ====================

    _LOG_MODULES = ["ALL", "WS", "Gateway", "AVR", "TRV",
                    "Whim.ai", "UI", "Ingest", "System"]
    _LOG_LEVELS = ["ALL", "TRACE", "DEBUG", "INFO", "WARN", "ERROR"]
    _LOG_LEVEL_ORDER = {"TRACE": 0, "DEBUG": 1, "INFO": 2, "WARN": 3, "ERROR": 4}
    _LOG_MAX_ENTRIES = 5000

    def build_events(self):
        f = self.tabs["events"]
        self._log_entries = []
        self._log_filtered_ids = []
        self._log_search_history = []
        self._log_autoscroll = True
        self._log_paused = False
        self._log_saved_queries = self._log_load_saved_queries()

        # -- Top filter bar --
        bar = tk.Frame(f, bg=TH["bg"])
        bar.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(bar, text="Module:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(side="left")
        self._log_module_var = tk.StringVar(value="ALL")
        mod_combo = ttk.Combobox(bar, textvariable=self._log_module_var,
                                  values=self._LOG_MODULES, width=10, state="readonly")
        mod_combo.pack(side="left", padx=(2, 6))
        mod_combo.bind("<<ComboboxSelected>>", lambda e: self._log_apply_filters())

        tk.Label(bar, text="Level:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(side="left")
        self._log_level_var = tk.StringVar(value="ALL")
        lvl_combo = ttk.Combobox(bar, textvariable=self._log_level_var,
                                  values=self._LOG_LEVELS, width=8, state="readonly")
        lvl_combo.pack(side="left", padx=(2, 6))
        lvl_combo.bind("<<ComboboxSelected>>", lambda e: self._log_apply_filters())

        tk.Label(bar, text="Session:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(side="left")
        self._log_session_var = tk.StringVar()
        self._entry(bar, self._log_session_var, width=12).pack(side="left", padx=(2, 6))

        tk.Label(bar, text="Req ID:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(side="left")
        self._log_reqid_var = tk.StringVar()
        self._entry(bar, self._log_reqid_var, width=14).pack(side="left", padx=(2, 6))

        self._btn(bar, "Filter", self._log_apply_filters).pack(side="left", padx=2)
        self._btn(bar, "Clear Filters", self._log_clear_filters).pack(side="left", padx=2)

        # -- Search bar --
        search_bar = tk.Frame(f, bg=TH["bg"])
        search_bar.pack(fill="x", padx=12, pady=(0, 4))

        tk.Label(search_bar, text="Search:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(side="left")
        self._log_search_var = tk.StringVar()
        self._log_search_entry = self._entry(search_bar, self._log_search_var, width=30)
        self._log_search_entry.pack(side="left", padx=(2, 4))
        self._log_search_entry.bind("<Return>", lambda e: self._log_do_search())
        self._btn(search_bar, "Find", self._log_do_search).pack(side="left", padx=2)
        self._btn(search_bar, "Next", self._log_search_next).pack(side="left", padx=2)
        self._btn(search_bar, "Clear", self._log_search_clear).pack(side="left", padx=2)

        tk.Frame(search_bar, bg=TH["border_hi"], width=1).pack(
            side="left", fill="y", padx=8, pady=2)

        tk.Label(search_bar, text="Saved:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_xs"]).pack(side="left")
        self._log_saved_var = tk.StringVar()
        self._log_saved_combo = ttk.Combobox(
            search_bar, textvariable=self._log_saved_var,
            values=list(self._log_saved_queries.keys()), width=18, state="readonly")
        self._log_saved_combo.pack(side="left", padx=(2, 4))
        self._btn(search_bar, "Load", self._log_load_query).pack(side="left", padx=2)
        self._btn(search_bar, "Save Query", self._log_save_query).pack(side="left", padx=2)
        self._btn(search_bar, "Delete", self._log_delete_query).pack(side="left", padx=2)

        # -- Controls --
        ctrl_bar = tk.Frame(f, bg=TH["bg"])
        ctrl_bar.pack(fill="x", padx=12, pady=(0, 4))

        self._log_pause_btn_text = tk.StringVar(value="Pause")
        self._btn(ctrl_bar, "Pause", self._log_toggle_pause).pack(side="left", padx=2)
        self._log_pause_label = tk.Label(ctrl_bar, text="LIVE", bg=TH["bg"],
                                          fg=TH["green"], font=TH["font_xs"])
        self._log_pause_label.pack(side="left", padx=4)

        self._btn(ctrl_bar, "Clear Log", self._log_clear_all).pack(side="left", padx=6)
        self._btn(ctrl_bar, "Export Log", self._log_export).pack(side="left", padx=2)

        self._log_count_label = tk.Label(ctrl_bar, text="0 entries", bg=TH["bg"],
                                          fg=TH["fg_dim"], font=TH["font_xs"])
        self._log_count_label.pack(side="right")

        self._log_match_label = tk.Label(ctrl_bar, text="", bg=TH["bg"],
                                          fg=TH["yellow"], font=TH["font_xs"])
        self._log_match_label.pack(side="right", padx=8)

        # -- Paned: top=log list, bottom=detail --
        pane = ttk.PanedWindow(f, orient="vertical")
        pane.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        # === TOP: Log treeview ===
        top = tk.Frame(pane, bg=TH["bg"])

        cols = ("time", "level", "module", "message")
        col_widths = {"time": 90, "level": 60, "module": 90, "message": 600}

        self._log_tree = ttk.Treeview(top, columns=cols, show="headings",
                                       selectmode="browse")
        for c in cols:
            self._log_tree.heading(c, text=c.capitalize())
            anchor = "w" if c == "message" else "center"
            self._log_tree.column(c, width=col_widths[c], anchor=anchor,
                                   minwidth=40)

        tree_sb = self._scrollbar(top, command=self._log_tree.yview)
        self._log_tree.configure(yscrollcommand=tree_sb.set)
        self._log_tree.pack(side="left", fill="both", expand=True)
        tree_sb.pack(side="right", fill="y")
        self._log_tree.bind("<<TreeviewSelect>>", self._log_on_select)

        self._log_tree.tag_configure("TRACE", foreground=TH["fg_dim"])
        self._log_tree.tag_configure("DEBUG", foreground=TH["fg2"])
        self._log_tree.tag_configure("INFO", foreground=TH["fg"])
        self._log_tree.tag_configure("WARN", foreground=TH["yellow"])
        self._log_tree.tag_configure("ERROR", foreground=TH["red"])
        self._log_tree.tag_configure("search_hit", background="#3a3a00")

        pane.add(top, weight=3)

        # === BOTTOM: Detail view ===
        bottom = tk.Frame(pane, bg=TH["bg"])

        detail_wrap = tk.Frame(bottom, bg=TH["card"], highlightthickness=1,
                                highlightbackground=TH["border_hi"])
        detail_wrap.pack(fill="both", expand=True)

        detail_hdr = tk.Frame(detail_wrap, bg=TH["card"])
        detail_hdr.pack(fill="x", padx=10, pady=(6, 2))
        tk.Label(detail_hdr, text="LOG DETAIL", bg=TH["card"],
                 fg=TH["blue_text"], font=("Segoe UI", 9, "bold")).pack(side="left")
        self._log_detail_meta = tk.Label(detail_hdr, text="", bg=TH["card"],
                                          fg=TH["fg2"], font=TH["font_xs"])
        self._log_detail_meta.pack(side="right")

        tk.Frame(detail_wrap, bg=TH["border_hi"], height=1).pack(
            fill="x", padx=10, pady=(0, 4))

        detail_body = tk.Frame(detail_wrap, bg=TH["card"])
        detail_body.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._log_detail_box = self._text_widget(detail_body, font=("Consolas", 9),
                                                  wrap="word", state="disabled")
        detail_sb = self._scrollbar(detail_body, command=self._log_detail_box.yview)
        self._log_detail_box.configure(yscrollcommand=detail_sb.set)
        self._log_detail_box.pack(side="left", fill="both", expand=True)
        detail_sb.pack(side="right", fill="y")

        self._log_detail_box.tag_configure("key", foreground=TH["blue_text"],
                                            font=("Consolas", 9, "bold"))
        self._log_detail_box.tag_configure("highlight",
                                            background="#5a5a00", foreground="#ffffff")

        pane.add(bottom, weight=2)

        # keep compat: events_box reference for any external code
        self.events_box = None

    # -- Structured log entry --

    _REDACT_PATTERNS = [
        (re.compile(r'("token"\s*:\s*")[^"]{6,}(")', re.IGNORECASE),
         r'\1***REDACTED***\2'),
        (re.compile(r'("(?:api[_-]?key|apikey|secret|password|authorization|auth)"\s*:\s*")[^"]{4,}(")', re.IGNORECASE),
         r'\1***REDACTED***\2'),
        (re.compile(r'(?<![0-9])(\+?1?\s*[-.(]?\s*\d{3}\s*[-.)]\s*\d{3}\s*[-.]?\s*\d{4})(?![0-9])'),
         "***PHONE***"),
        (re.compile(r'(?<![0-9])(\+\d{7,15})(?![0-9])'),
         "***PHONE***"),
        (re.compile(r'("(?:account[_-]?id|accountId|userId|user_id|channelId|guildId)"\s*:\s*")\d{10,}(")', re.IGNORECASE),
         r'\1***ID***\2'),
        (re.compile(r'(https?://(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|127\.0\.0\.1|localhost)(?::\d+)?(?:/[^\s"]*)?)', re.IGNORECASE),
         "***PRIVATE_ENDPOINT***"),
        (re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'),
         "***TOKEN***"),
        (re.compile(r'(?:Bearer|Basic)\s+\S{8,}', re.IGNORECASE),
         "***AUTH_HEADER***"),
        (re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'),
         "***EMAIL***"),
    ]

    @staticmethod
    def _log_redact(text):
        for pattern, repl in ModernApp._REDACT_PATTERNS:
            text = pattern.sub(repl, text)
        return text

    def log_events(self, msg, module="System", level="INFO",
                   session_id="", request_id=""):
        ts = datetime.now().strftime("%H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"

        msg = self._log_redact(msg)

        if module == "System" and isinstance(msg, str):
            module, level = self._log_guess_module_level(msg)

        short = msg if len(msg) <= 200 else msg[:197] + "..."
        short = short.replace("\n", " ")

        entry = {
            "idx": len(self._log_entries),
            "ts": ts,
            "level": level.upper(),
            "module": module,
            "message": short,
            "full": msg,
            "session_id": session_id,
            "request_id": request_id,
        }
        self._log_entries.append(entry)

        if len(self._log_entries) > self._LOG_MAX_ENTRIES:
            self._log_entries = self._log_entries[-self._LOG_MAX_ENTRIES:]

        if not self._log_paused and self._log_entry_matches(entry):
            iid = str(entry["idx"])
            self._log_tree.insert("", "end", iid=iid,
                                   values=(ts, entry["level"], module, short),
                                   tags=(entry["level"],))
            self._log_filtered_ids.append(iid)
            if self._log_autoscroll:
                self._log_tree.see(iid)

        self._log_count_label.config(
            text=f"{len(self._log_entries)} entries "
                 f"({len(self._log_filtered_ids)} shown)")

    def _log_guess_module_level(self, msg):
        ml = msg.lower()
        module = "System"
        level = "INFO"

        mod_hints = [
            ("whim.ai", "Whim.ai"), ("whimai", "Whim.ai"),
            ("gateway", "Gateway"), ("ws", "WS"), ("websocket", "WS"),
            ("xtts", "AVR"), ("avr", "AVR"), ("tts", "AVR"),
            ("trv", "TRV"), ("cipher", "TRV"), ("hearmeout", "TRV"),
            ("ingest", "Ingest"), ("transcri", "Ingest"),
        ]
        for hint, mod in mod_hints:
            if hint in ml:
                module = mod
                break

        if any(w in ml for w in ("error", "fail", "exception", "crash", "❌")):
            level = "ERROR"
        elif any(w in ml for w in ("warn", "⚠", "timeout", "retry")):
            level = "WARN"
        elif any(w in ml for w in ("debug", "trace", "verbose")):
            level = "DEBUG"
        elif any(w in ml for w in ("connect", "🔌", "start", "stop", "✅")):
            level = "INFO"

        return module, level

    def _log_entry_matches(self, entry):
        mod_filter = self._log_module_var.get()
        if mod_filter != "ALL" and entry["module"] != mod_filter:
            return False

        lvl_filter = self._log_level_var.get()
        if lvl_filter != "ALL":
            min_order = self._LOG_LEVEL_ORDER.get(lvl_filter, 0)
            entry_order = self._LOG_LEVEL_ORDER.get(entry["level"], 2)
            if entry_order < min_order:
                return False

        sess_filter = self._log_session_var.get().strip()
        if sess_filter and sess_filter not in entry.get("session_id", ""):
            return False

        reqid_filter = self._log_reqid_var.get().strip()
        if reqid_filter and reqid_filter not in entry.get("request_id", ""):
            return False

        return True

    # -- Filter / rebuild --

    def _log_apply_filters(self):
        for item in self._log_tree.get_children():
            self._log_tree.delete(item)
        self._log_filtered_ids = []

        for entry in self._log_entries:
            if self._log_entry_matches(entry):
                iid = str(entry["idx"])
                self._log_tree.insert("", "end", iid=iid,
                                       values=(entry["ts"], entry["level"],
                                               entry["module"], entry["message"]),
                                       tags=(entry["level"],))
                self._log_filtered_ids.append(iid)

        self._log_count_label.config(
            text=f"{len(self._log_entries)} entries "
                 f"({len(self._log_filtered_ids)} shown)")

        if self._log_filtered_ids:
            self._log_tree.see(self._log_filtered_ids[-1])

    def _log_clear_filters(self):
        self._log_module_var.set("ALL")
        self._log_level_var.set("ALL")
        self._log_session_var.set("")
        self._log_reqid_var.set("")
        self._log_apply_filters()

    # -- Selection / detail --

    def _log_on_select(self, event=None):
        sel = self._log_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        entry = None
        for e in self._log_entries:
            if e["idx"] == idx:
                entry = e
                break
        if not entry:
            return

        meta_parts = [entry["level"], entry["module"], entry["ts"]]
        if entry.get("session_id"):
            meta_parts.append(f"sid={entry['session_id']}")
        if entry.get("request_id"):
            meta_parts.append(f"rid={entry['request_id']}")
        self._log_detail_meta.config(text="  |  ".join(meta_parts))

        self._log_detail_box.config(state="normal")
        self._log_detail_box.delete("1.0", "end")

        self._log_detail_box.insert("end", "TIME: ", "key")
        self._log_detail_box.insert("end", entry["ts"] + "\n")
        self._log_detail_box.insert("end", "LEVEL: ", "key")
        self._log_detail_box.insert("end", entry["level"] + "\n")
        self._log_detail_box.insert("end", "MODULE: ", "key")
        self._log_detail_box.insert("end", entry["module"] + "\n")
        if entry.get("session_id"):
            self._log_detail_box.insert("end", "SESSION: ", "key")
            self._log_detail_box.insert("end", entry["session_id"] + "\n")
        if entry.get("request_id"):
            self._log_detail_box.insert("end", "REQUEST: ", "key")
            self._log_detail_box.insert("end", entry["request_id"] + "\n")
        self._log_detail_box.insert("end", "\n")
        self._log_detail_box.insert("end", entry["full"])

        search_q = self._log_search_var.get().strip()
        if search_q:
            self._log_highlight_in_detail(search_q)

        self._log_detail_box.config(state="disabled")

    def _log_highlight_in_detail(self, query):
        self._log_detail_box.tag_remove("highlight", "1.0", "end")
        if not query:
            return
        start = "1.0"
        ql = query.lower()
        while True:
            pos = self._log_detail_box.search(query, start, stopindex="end",
                                               nocase=True)
            if not pos:
                break
            end_pos = f"{pos}+{len(query)}c"
            self._log_detail_box.tag_add("highlight", pos, end_pos)
            start = end_pos

    # -- Search --

    def _log_do_search(self):
        query = self._log_search_var.get().strip()
        if not query:
            return

        if query not in self._log_search_history:
            self._log_search_history.append(query)

        self._log_tree.tag_remove("search_hit")
        for iid in self._log_tree.get_children():
            self._log_tree.tag_remove("search_hit", iid)

        ql = query.lower()
        hits = []
        for iid in self._log_filtered_ids:
            try:
                idx = int(iid)
            except ValueError:
                continue
            entry = None
            for e in self._log_entries:
                if e["idx"] == idx:
                    entry = e
                    break
            if entry and (ql in entry["full"].lower() or
                          ql in entry["module"].lower() or
                          ql in entry.get("request_id", "").lower()):
                self._log_tree.item(iid, tags=(entry["level"], "search_hit"))
                hits.append(iid)

        self._log_search_hits = hits
        self._log_search_pos = 0
        self._log_match_label.config(
            text=f"{len(hits)} match(es)" if hits else "No matches")

        if hits:
            self._log_tree.selection_set(hits[0])
            self._log_tree.see(hits[0])
            self._log_on_select()

    def _log_search_next(self):
        if not hasattr(self, "_log_search_hits") or not self._log_search_hits:
            return
        self._log_search_pos = (self._log_search_pos + 1) % len(self._log_search_hits)
        iid = self._log_search_hits[self._log_search_pos]
        self._log_tree.selection_set(iid)
        self._log_tree.see(iid)
        self._log_on_select()
        self._log_match_label.config(
            text=f"Match {self._log_search_pos + 1}/{len(self._log_search_hits)}")

    def _log_search_clear(self):
        self._log_search_var.set("")
        self._log_match_label.config(text="")
        for iid in self._log_tree.get_children():
            try:
                idx = int(iid)
            except ValueError:
                continue
            entry = None
            for e in self._log_entries:
                if e["idx"] == idx:
                    entry = e
                    break
            if entry:
                self._log_tree.item(iid, tags=(entry["level"],))
        self._log_search_hits = []
        self._log_search_pos = 0

    # -- Saved queries --

    def _log_queries_path(self):
        return os.path.expanduser("~/.openclaw/whim_log_queries.json")

    def _log_load_saved_queries(self):
        try:
            with open(self._log_queries_path(), "r") as fh:
                return json.load(fh)
        except Exception:
            return {}

    def _log_save_queries_file(self, queries):
        try:
            os.makedirs(os.path.dirname(self._log_queries_path()), exist_ok=True)
            with open(self._log_queries_path(), "w") as fh:
                json.dump(queries, fh, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _log_save_query(self):
        query = self._log_search_var.get().strip()
        if not query:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Save Search Query")
        dlg.configure(bg=TH["bg"])
        dlg.geometry("340x130")
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text="Query name:", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font"]).pack(padx=12, pady=(12, 4), anchor="w")
        name_var = tk.StringVar(value=query[:30])
        self._entry(dlg, name_var, width=36).pack(padx=12, fill="x")

        def do_save():
            name = name_var.get().strip()
            if not name:
                dlg.destroy()
                return
            self._log_saved_queries[name] = {
                "search": query,
                "module": self._log_module_var.get(),
                "level": self._log_level_var.get(),
            }
            self._log_save_queries_file(self._log_saved_queries)
            self._log_saved_combo["values"] = list(self._log_saved_queries.keys())
            self._log_saved_var.set(name)
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=TH["bg"])
        btn_row.pack(fill="x", padx=12, pady=(8, 12))
        self._btn(btn_row, "Save", do_save).pack(side="left")
        self._btn(btn_row, "Cancel", dlg.destroy).pack(side="left", padx=6)

    def _log_load_query(self):
        name = self._log_saved_var.get()
        q = self._log_saved_queries.get(name)
        if not q:
            return
        self._log_search_var.set(q.get("search", ""))
        self._log_module_var.set(q.get("module", "ALL"))
        self._log_level_var.set(q.get("level", "ALL"))
        self._log_apply_filters()
        if q.get("search"):
            self._log_do_search()

    def _log_delete_query(self):
        name = self._log_saved_var.get()
        if name and name in self._log_saved_queries:
            del self._log_saved_queries[name]
            self._log_save_queries_file(self._log_saved_queries)
            self._log_saved_combo["values"] = list(self._log_saved_queries.keys())
            self._log_saved_var.set("")

    # -- Pause / clear / export --

    def _log_toggle_pause(self):
        self._log_paused = not self._log_paused
        if self._log_paused:
            self._log_pause_label.config(text="PAUSED", fg=TH["yellow"])
        else:
            self._log_pause_label.config(text="LIVE", fg=TH["green"])
            self._log_apply_filters()

    def _log_clear_all(self):
        self._log_entries.clear()
        self._log_filtered_ids.clear()
        for item in self._log_tree.get_children():
            self._log_tree.delete(item)
        self._log_count_label.config(text="0 entries (0 shown)")
        self._log_detail_box.config(state="normal")
        self._log_detail_box.delete("1.0", "end")
        self._log_detail_box.config(state="disabled")
        self._log_detail_meta.config(text="")

    def _log_export(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = filedialog.asksaveasfilename(
            initialdir=os.path.expanduser("~"),
            initialfile=f"whim_debug_log_{ts}.txt",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON", "*.json"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            if path.endswith(".json"):
                export = []
                for e in self._log_entries:
                    if self._log_entry_matches(e):
                        export.append({
                            "time": e["ts"], "level": e["level"],
                            "module": e["module"], "message": e["full"],
                            "session_id": e.get("session_id", ""),
                            "request_id": e.get("request_id", ""),
                        })
                with open(path, "w") as fh:
                    json.dump(export, fh, indent=2, ensure_ascii=False)
            else:
                with open(path, "w") as fh:
                    for e in self._log_entries:
                        if self._log_entry_matches(e):
                            fh.write(f"[{e['ts']}] [{e['level']}] "
                                     f"[{e['module']}] {e['full']}\n")
            self.log_events(f"Log exported to {path}", module="UI", level="INFO")
        except Exception as ex:
            self.log_events(f"Export failed: {ex}", module="UI", level="ERROR")

    # ================================================================
    # PERSONA — Voice Personality & Coined Response Manager
    # ================================================================

    _PERSONA_CATEGORIES = [
        ("wake", "Wake Word", "#00ff00"),
        ("acknowledge", "Acknowledgment", "#40e0d0"),
        ("misheard", "Misheard / Low Confidence", "#ffaa00"),
        ("error", "Error / Failure", "#ff4444"),
        ("narrative", "Narrative / Table Read", "#cc66ff"),
        ("ambient", "Ambient / Idle", "#888888"),
        ("custom", "Custom", "#3388ff"),
    ]

    def build_persona(self):
        f = self.tabs["persona"]

        self._persona_data = self._persona_load()
        self._persona_current = None

        wrap = tk.Frame(f, bg=TH["bg"])
        wrap.pack(fill="both", expand=True, padx=12, pady=8)

        tk.Label(wrap, text="PERSONA", bg=TH["bg"], fg=TH["green"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(wrap, text="Voice personalities with coined responses — playlists that make each voice feel alive",
                 bg=TH["bg"], fg=TH["fg2"], font=("Consolas", 9)).pack(anchor="w", pady=(0, 8))

        body = tk.Frame(wrap, bg=TH["bg"])
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=0)
        body.rowconfigure(0, weight=1)

        # ---- Column 1: Persona selector ----
        left = tk.Frame(body, bg=TH["bg"], width=200)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        sel_card = self._card(left, "VOICES", fg="#888888")
        sel_card.pack(fill="both", expand=True)
        sel_inner = tk.Frame(sel_card, bg=TH["card"])
        sel_inner.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._persona_list = tk.Listbox(sel_inner, bg=TH["input"], fg=TH["fg"],
                                         font=("Consolas", 11), height=10,
                                         selectbackground=TH["select_bg"],
                                         highlightthickness=0, bd=0, relief="flat",
                                         activestyle="none")
        self._persona_list.pack(fill="both", expand=True, pady=(0, 4))
        self._persona_list.bind("<<ListboxSelect>>", lambda e: self._persona_on_select())

        btn_row = tk.Frame(sel_inner, bg=TH["card"])
        btn_row.pack(fill="x")
        self._btn(btn_row, "+ New", self._persona_new).pack(side="left", padx=2)
        self._btn(btn_row, "Duplicate", self._persona_duplicate).pack(side="left", padx=2)
        self._btn(btn_row, "Delete", self._persona_delete).pack(side="left", padx=2)

        # Active persona indicator
        self._persona_active_var = tk.StringVar(value="Active: none")
        tk.Label(sel_inner, textvariable=self._persona_active_var, bg=TH["card"],
                 fg=TH["green"], font=("Consolas", 9)).pack(anchor="w", pady=(4, 0))
        self._btn(sel_inner, "Set Active", self._persona_set_active).pack(anchor="w", pady=4)

        # ---- Column 2: Response playlist ----
        mid = tk.Frame(body, bg=TH["bg"])
        mid.grid(row=0, column=1, sticky="nsew", padx=6)

        playlist_card = self._card(mid, "RESPONSE PLAYLIST", fg="#888888")
        playlist_card.pack(fill="both", expand=True)
        pl_inner = tk.Frame(playlist_card, bg=TH["card"])
        pl_inner.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Category filter bar
        cat_bar = tk.Frame(pl_inner, bg=TH["card"])
        cat_bar.pack(fill="x", pady=(0, 4))
        tk.Label(cat_bar, text="Category:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._persona_cat_var = tk.StringVar(value="All")
        cat_values = ["All"] + [c[1] for c in self._PERSONA_CATEGORIES]
        self._persona_cat_combo = ttk.Combobox(cat_bar, textvariable=self._persona_cat_var,
                                                values=cat_values, width=22, state="readonly")
        self._persona_cat_combo.pack(side="left", padx=4)
        self._persona_cat_combo.bind("<<ComboboxSelected>>",
            lambda e: self._persona_refresh_playlist())

        # Playlist tree
        cols = ("trigger", "category", "response", "cached")
        self._persona_tree = ttk.Treeview(pl_inner, columns=cols, show="headings",
                                           height=14, selectmode="browse")
        self._persona_tree.heading("trigger", text="Trigger")
        self._persona_tree.heading("category", text="Category")
        self._persona_tree.heading("response", text="Response Text")
        self._persona_tree.heading("cached", text="Audio")
        self._persona_tree.column("trigger", width=140, minwidth=100)
        self._persona_tree.column("category", width=120, minwidth=80)
        self._persona_tree.column("response", width=320, minwidth=200)
        self._persona_tree.column("cached", width=60, minwidth=50)
        self._persona_tree.pack(fill="both", expand=True, pady=(0, 4))
        self._persona_tree.bind("<<TreeviewSelect>>", lambda e: self._persona_on_entry_select())

        pl_sb = self._scrollbar(pl_inner, command=self._persona_tree.yview)
        self._persona_tree.configure(yscrollcommand=pl_sb.set)

        # Playlist action buttons
        pl_btns = tk.Frame(pl_inner, bg=TH["card"])
        pl_btns.pack(fill="x")
        self._btn(pl_btns, "+ Add Response", self._persona_add_response).pack(side="left", padx=2)
        self._btn(pl_btns, "Edit", self._persona_edit_response).pack(side="left", padx=2)
        self._btn(pl_btns, "Remove", self._persona_remove_response).pack(side="left", padx=2)
        tk.Frame(pl_btns, width=16, bg=TH["card"]).pack(side="left")
        self._btn(pl_btns, "\u25b6 Preview", self._persona_preview).pack(side="left", padx=2)
        self._btn(pl_btns, "Render All", self._persona_render_all).pack(side="left", padx=2)

        # ---- Column 3: Editor / Details panel ----
        right = tk.Frame(body, bg=TH["bg"], width=260)
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        # Entry editor
        edit_card = self._card(right, "RESPONSE EDITOR", fg="#888888")
        edit_card.pack(fill="x")
        ed = tk.Frame(edit_card, bg=TH["card"])
        ed.pack(fill="x", padx=8, pady=(0, 8))

        r = tk.Frame(ed, bg=TH["card"])
        r.pack(fill="x", pady=2)
        tk.Label(r, text="Trigger:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=10, anchor="w").pack(side="left")
        self._pe_trigger_var = tk.StringVar()
        self._entry(r, self._pe_trigger_var, width=24).pack(side="left", padx=2)

        r = tk.Frame(ed, bg=TH["card"])
        r.pack(fill="x", pady=2)
        tk.Label(r, text="Category:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=10, anchor="w").pack(side="left")
        self._pe_cat_var = tk.StringVar(value="acknowledge")
        ttk.Combobox(r, textvariable=self._pe_cat_var,
                      values=[c[0] for c in self._PERSONA_CATEGORIES],
                      width=18, state="readonly").pack(side="left", padx=2)

        r = tk.Frame(ed, bg=TH["card"])
        r.pack(fill="x", pady=2)
        tk.Label(r, text="Response:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=10, anchor="nw").pack(side="left")
        self._pe_response_text = self._text_widget(ed, height=3, width=28)
        self._pe_response_text.pack(fill="x", padx=2, pady=2)

        r = tk.Frame(ed, bg=TH["card"])
        r.pack(fill="x", pady=2)
        tk.Label(r, text="Confidence:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=10, anchor="w").pack(side="left")
        self._pe_conf_min_var = tk.StringVar(value="0")
        self._entry(r, self._pe_conf_min_var, width=4).pack(side="left")
        tk.Label(r, text="–", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=2)
        self._pe_conf_max_var = tk.StringVar(value="100")
        self._entry(r, self._pe_conf_max_var, width=4).pack(side="left")
        tk.Label(r, text="%", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")

        r = tk.Frame(ed, bg=TH["card"])
        r.pack(fill="x", pady=2)
        tk.Label(r, text="Context:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=10, anchor="w").pack(side="left")
        self._pe_context_var = tk.StringVar(value="any")
        ttk.Combobox(r, textvariable=self._pe_context_var,
                      values=["any", "driving", "idle", "morning", "night",
                              "recording", "table_read", "error", "reconnect"],
                      width=16, state="readonly").pack(side="left", padx=2)

        ed_btns = tk.Frame(ed, bg=TH["card"])
        ed_btns.pack(fill="x", pady=(6, 2))
        self._btn(ed_btns, "Save Entry", self._persona_save_entry).pack(side="left", padx=2)
        self._btn(ed_btns, "Render This", self._persona_render_one).pack(side="left", padx=2)

        # Stats card
        stats_card = self._card(right, "PERSONA STATS", fg="#888888")
        stats_card.pack(fill="x", pady=(6, 0))
        st = tk.Frame(stats_card, bg=TH["card"])
        st.pack(fill="x", padx=8, pady=(0, 8))

        self._persona_stat_lines = {}
        for key, label in [("total", "Total Responses"), ("cached", "Pre-Rendered"),
                           ("categories", "Categories"), ("voice", "Voice Clone"),
                           ("size", "Cache Size")]:
            r = tk.Frame(st, bg=TH["card"])
            r.pack(fill="x", pady=1)
            tk.Label(r, text=f"{label}:", bg=TH["card"], fg=TH["fg2"],
                     font=("Consolas", 8), width=16, anchor="w").pack(side="left")
            lbl = tk.Label(r, text="—", bg=TH["card"], fg=TH["fg"],
                           font=("Consolas", 9))
            lbl.pack(side="left")
            self._persona_stat_lines[key] = lbl

        # Render status
        self._persona_render_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._persona_render_var, bg=TH["bg"],
                 fg=TH["yellow"], font=("Consolas", 9)).pack(anchor="w", pady=(4, 0))

        self._persona_refresh_list()

    # ---- Persona data I/O ----
    def _persona_load(self):
        if os.path.isfile(PERSONA_CONFIG):
            try:
                with open(PERSONA_CONFIG) as fh:
                    return json.load(fh)
            except Exception:
                pass
        return {"active": None, "personas": {}}

    def _persona_save(self):
        os.makedirs(os.path.dirname(PERSONA_CONFIG), exist_ok=True)
        with open(PERSONA_CONFIG, "w") as fh:
            json.dump(self._persona_data, fh, indent=2)

    def _persona_get(self, name):
        return self._persona_data.get("personas", {}).get(name)

    # ---- Persona list management ----
    def _persona_refresh_list(self):
        self._persona_list.delete(0, "end")
        for name in sorted(self._persona_data.get("personas", {}).keys()):
            prefix = "\u2605 " if name == self._persona_data.get("active") else "  "
            self._persona_list.insert("end", f"{prefix}{name}")
        active = self._persona_data.get("active", "none")
        self._persona_active_var.set(f"Active: {active}")

    def _persona_on_select(self):
        sel = self._persona_list.curselection()
        if not sel:
            return
        raw = self._persona_list.get(sel[0]).strip()
        name = raw.lstrip("\u2605 ").strip()
        self._persona_current = name
        self._persona_refresh_playlist()
        self._persona_update_stats()

    def _persona_new(self):
        win = tk.Toplevel(self)
        win.title("New Persona")
        win.configure(bg=TH["bg"])
        win.attributes("-topmost", True)
        win.geometry("340x200")

        tk.Label(win, text="Persona Name:", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font_sm"]).pack(pady=(12, 2))
        name_var = tk.StringVar()
        self._entry(win, name_var, width=28).pack(pady=2)

        tk.Label(win, text="Voice Clone:", bg=TH["bg"], fg=TH["fg"],
                 font=TH["font_sm"]).pack(pady=(8, 2))
        voice_var = tk.StringVar()
        voices = []
        try:
            for fn in os.listdir(XTTS_VOICES_DIR):
                if fn.endswith((".wav", ".mp3")) and fn != "active_voice.json":
                    voices.append(fn.rsplit(".", 1)[0])
        except Exception:
            pass
        combo = ttk.Combobox(win, textvariable=voice_var, values=voices, width=24,
                              state="readonly")
        combo.pack(pady=2)

        def _create():
            n = name_var.get().strip()
            v = voice_var.get().strip()
            if not n:
                return
            personas = self._persona_data.setdefault("personas", {})
            personas[n] = {"voice": v, "responses": []}
            self._persona_save()
            self._persona_refresh_list()
            win.destroy()

        self._btn(win, "Create", _create).pack(pady=10)

    def _persona_duplicate(self):
        if not self._persona_current:
            return
        src = self._persona_get(self._persona_current)
        if not src:
            return
        new_name = f"{self._persona_current}_copy"
        import copy
        self._persona_data["personas"][new_name] = copy.deepcopy(src)
        self._persona_save()
        self._persona_refresh_list()

    def _persona_delete(self):
        if not self._persona_current:
            return
        name = self._persona_current
        self._persona_data.get("personas", {}).pop(name, None)
        if self._persona_data.get("active") == name:
            self._persona_data["active"] = None
        self._persona_current = None
        self._persona_save()
        self._persona_refresh_list()
        self._persona_tree.delete(*self._persona_tree.get_children())

    def _persona_set_active(self):
        if not self._persona_current:
            return
        self._persona_data["active"] = self._persona_current
        self._persona_save()
        self._persona_refresh_list()

    # ---- Playlist management ----
    def _persona_refresh_playlist(self):
        self._persona_tree.delete(*self._persona_tree.get_children())
        if not self._persona_current:
            return
        persona = self._persona_get(self._persona_current)
        if not persona:
            return
        cat_filter = self._persona_cat_var.get()
        cat_key_map = {c[1]: c[0] for c in self._PERSONA_CATEGORIES}
        for i, entry in enumerate(persona.get("responses", [])):
            cat = entry.get("category", "custom")
            if cat_filter != "All" and cat != cat_key_map.get(cat_filter, cat_filter):
                continue
            trigger = entry.get("trigger", "")
            response = entry.get("text", "")
            cache_dir = os.path.join(PERSONA_DIR, self._persona_current, "cache")
            cache_file = os.path.join(cache_dir, f"{i:04d}.wav")
            cached = "\u2713" if os.path.isfile(cache_file) else ""
            cat_label = cat
            for c in self._PERSONA_CATEGORIES:
                if c[0] == cat:
                    cat_label = c[1]
                    break
            self._persona_tree.insert("", "end", iid=str(i),
                                       values=(trigger, cat_label, response, cached))

    def _persona_on_entry_select(self):
        sel = self._persona_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        persona = self._persona_get(self._persona_current)
        if not persona:
            return
        entries = persona.get("responses", [])
        if idx >= len(entries):
            return
        entry = entries[idx]
        self._pe_trigger_var.set(entry.get("trigger", ""))
        self._pe_cat_var.set(entry.get("category", "custom"))
        self._pe_response_text.delete("1.0", "end")
        self._pe_response_text.insert("1.0", entry.get("text", ""))
        conf = entry.get("confidence", [0, 100])
        self._pe_conf_min_var.set(str(conf[0]))
        self._pe_conf_max_var.set(str(conf[1]))
        self._pe_context_var.set(entry.get("context", "any"))

    def _persona_add_response(self):
        if not self._persona_current:
            return
        persona = self._persona_get(self._persona_current)
        if not persona:
            return
        persona.setdefault("responses", []).append({
            "trigger": "new_trigger",
            "category": "custom",
            "text": "",
            "confidence": [0, 100],
            "context": "any",
        })
        self._persona_save()
        self._persona_refresh_playlist()

    def _persona_edit_response(self):
        self._persona_save_entry()

    def _persona_remove_response(self):
        sel = self._persona_tree.selection()
        if not sel or not self._persona_current:
            return
        idx = int(sel[0])
        persona = self._persona_get(self._persona_current)
        if persona and idx < len(persona.get("responses", [])):
            persona["responses"].pop(idx)
            self._persona_save()
            self._persona_refresh_playlist()

    def _persona_save_entry(self):
        sel = self._persona_tree.selection()
        if not sel or not self._persona_current:
            return
        idx = int(sel[0])
        persona = self._persona_get(self._persona_current)
        if not persona or idx >= len(persona.get("responses", [])):
            return
        entry = persona["responses"][idx]
        entry["trigger"] = self._pe_trigger_var.get().strip()
        entry["category"] = self._pe_cat_var.get()
        entry["text"] = self._pe_response_text.get("1.0", "end").strip()
        try:
            entry["confidence"] = [int(self._pe_conf_min_var.get()),
                                    int(self._pe_conf_max_var.get())]
        except ValueError:
            entry["confidence"] = [0, 100]
        entry["context"] = self._pe_context_var.get()
        self._persona_save()
        self._persona_refresh_playlist()

    # ---- Audio preview / render ----
    def _persona_preview(self):
        sel = self._persona_tree.selection()
        if not sel or not self._persona_current:
            return
        idx = int(sel[0])
        cache_dir = os.path.join(PERSONA_DIR, self._persona_current, "cache")
        cache_file = os.path.join(cache_dir, f"{idx:04d}.wav")
        if os.path.isfile(cache_file):
            subprocess.Popen(["ffplay", "-nodisp", "-autoexit", cache_file],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            self._persona_render_var.set("Not rendered yet — click Render This")

    def _persona_render_one(self):
        sel = self._persona_tree.selection()
        if not sel or not self._persona_current:
            return
        idx = int(sel[0])
        persona = self._persona_get(self._persona_current)
        if not persona:
            return
        entries = persona.get("responses", [])
        if idx >= len(entries):
            return
        text = entries[idx].get("text", "")
        if not text:
            self._persona_render_var.set("No response text to render")
            return
        voice = persona.get("voice", "")
        ref_wav = None
        for ext in (".wav", ".mp3"):
            p = os.path.join(XTTS_VOICES_DIR, voice + ext)
            if os.path.isfile(p):
                ref_wav = p
                break
        if not ref_wav:
            self._persona_render_var.set(f"Voice file not found: {voice}")
            return
        cache_dir = os.path.join(PERSONA_DIR, self._persona_current, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        out_wav = os.path.join(cache_dir, f"{idx:04d}.wav")
        self._persona_render_var.set(f"Rendering {idx:04d}...")
        self._persona_xtts_render(text, ref_wav, out_wav,
            lambda ok: self.after(0, lambda: self._persona_render_done(ok, idx)))

    def _persona_render_all(self):
        if not self._persona_current:
            return
        persona = self._persona_get(self._persona_current)
        if not persona:
            return
        voice = persona.get("voice", "")
        ref_wav = None
        for ext in (".wav", ".mp3"):
            p = os.path.join(XTTS_VOICES_DIR, voice + ext)
            if os.path.isfile(p):
                ref_wav = p
                break
        if not ref_wav:
            self._persona_render_var.set(f"Voice file not found: {voice}")
            return
        entries = persona.get("responses", [])
        cache_dir = os.path.join(PERSONA_DIR, self._persona_current, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        total = len(entries)
        self._persona_render_var.set(f"Rendering 0/{total}...")

        def _batch():
            for i, entry in enumerate(entries):
                text = entry.get("text", "")
                if not text:
                    continue
                out_wav = os.path.join(cache_dir, f"{i:04d}.wav")
                if os.path.isfile(out_wav):
                    continue
                self.after(0, lambda ii=i: self._persona_render_var.set(
                    f"Rendering {ii + 1}/{total}..."))
                self._persona_xtts_render_sync(text, ref_wav, out_wav)
            self.after(0, lambda: self._persona_render_var.set(
                f"Done — {total} responses rendered"))
            self.after(0, self._persona_refresh_playlist)
            self.after(0, self._persona_update_stats)
        threading.Thread(target=_batch, daemon=True).start()

    def _persona_xtts_render(self, text, ref_wav, out_wav, callback):
        def _run():
            ok = self._persona_xtts_render_sync(text, ref_wav, out_wav)
            callback(ok)
        threading.Thread(target=_run, daemon=True).start()

    def _persona_xtts_render_sync(self, text, ref_wav, out_wav):
        if not os.path.isfile(XTTS_CONDA_PYTHON):
            return False
        script = (
            "import torch, wave\n"
            "from TTS.tts.configs.xtts_config import XttsConfig\n"
            "from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs\n"
            "from TTS.config.shared_configs import BaseDatasetConfig\n"
            "torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])\n"
            "from TTS.api import TTS\n"
            f"tts = TTS({XTTS_MODEL!r}, gpu=True)\n"
            f"tts.tts_to_file(text={text!r}, file_path={out_wav!r}, "
            f"speaker_wav={ref_wav!r}, language='en')\n"
            "print('OK')\n"
        )
        try:
            proc = subprocess.run(
                [XTTS_CONDA_PYTHON, "-c", script],
                capture_output=True, text=True, timeout=120)
            return proc.returncode == 0
        except Exception:
            return False

    def _persona_render_done(self, ok, idx):
        if ok:
            self._persona_render_var.set(f"Rendered entry {idx:04d}")
            self._persona_refresh_playlist()
            self._persona_update_stats()
        else:
            self._persona_render_var.set(f"Render failed for {idx:04d}")

    def _persona_update_stats(self):
        if not self._persona_current:
            return
        persona = self._persona_get(self._persona_current)
        if not persona:
            return
        entries = persona.get("responses", [])
        cache_dir = os.path.join(PERSONA_DIR, self._persona_current, "cache")
        cached_count = 0
        cache_size = 0
        for i in range(len(entries)):
            cf = os.path.join(cache_dir, f"{i:04d}.wav")
            if os.path.isfile(cf):
                cached_count += 1
                cache_size += os.path.getsize(cf)
        cats = set(e.get("category", "custom") for e in entries)
        self._persona_stat_lines["total"].config(text=str(len(entries)))
        self._persona_stat_lines["cached"].config(
            text=f"{cached_count}/{len(entries)}",
            fg=TH["green"] if cached_count == len(entries) and entries else TH["yellow"])
        self._persona_stat_lines["categories"].config(text=str(len(cats)))
        self._persona_stat_lines["voice"].config(text=persona.get("voice", "none"))
        if cache_size < 1024 * 1024:
            self._persona_stat_lines["size"].config(text=f"{cache_size / 1024:.0f} KB")
        else:
            self._persona_stat_lines["size"].config(text=f"{cache_size / (1024*1024):.1f} MB")

    # ================================================================
    # AUDIO CAPTURE — floating always-on-top tool
    # ================================================================
    def _open_audio_capture(self):
        if hasattr(self, "_ac_win") and self._ac_win and self._ac_win.winfo_exists():
            self._ac_win.lift()
            self._ac_win.focus_force()
            return
        win = tk.Toplevel(self)
        win.title("Audio Capture")
        win.configure(bg=TH["bg"])
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.geometry("380x420")
        win.protocol("WM_DELETE_WINDOW", lambda: self._ac_close(win))
        self._ac_win = win
        self._ac_process = None
        self._ac_recording = False
        self._ac_start_time = None
        self._ac_output_path = None
        self._ac_peak_val = 0.0

        pad = dict(padx=12, pady=4)

        tk.Label(win, text="\U0001f3a7 AUDIO CAPTURE", bg=TH["bg"], fg=TH["green"],
                 font=("Segoe UI", 14, "bold")).pack(pady=(10, 6))
        tk.Label(win, text="Capture system audio (no video)", bg=TH["bg"],
                 fg=TH["fg2"], font=("Consolas", 9)).pack()

        src_frame = tk.Frame(win, bg=TH["bg"])
        src_frame.pack(fill="x", **pad)
        tk.Label(src_frame, text="Source:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._ac_source_var = tk.StringVar()
        self._ac_source_combo = ttk.Combobox(src_frame, textvariable=self._ac_source_var,
                                              width=34, state="readonly")
        self._ac_source_combo.pack(side="left", padx=4)

        fmt_frame = tk.Frame(win, bg=TH["bg"])
        fmt_frame.pack(fill="x", **pad)
        tk.Label(fmt_frame, text="Format:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._ac_format_var = tk.StringVar(value="mp3")
        ttk.Combobox(fmt_frame, textvariable=self._ac_format_var,
                      values=["mp3", "opus", "ogg", "m4a", "wav"], width=8,
                      state="readonly").pack(side="left", padx=4)
        tk.Label(fmt_frame, text="Bitrate:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left", padx=(8, 0))
        self._ac_bitrate_var = tk.StringVar(value="128k")
        ttk.Combobox(fmt_frame, textvariable=self._ac_bitrate_var,
                      values=["64k", "96k", "128k", "192k", "256k", "320k"], width=6,
                      state="readonly").pack(side="left", padx=4)

        # VU meter
        vu_frame = tk.Frame(win, bg=TH["bg"])
        vu_frame.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(vu_frame, text="Level:", bg=TH["bg"], fg=TH["fg2"],
                 font=("Consolas", 8)).pack(side="left")
        self._ac_vu_canvas = tk.Canvas(vu_frame, bg=TH["input"], height=14,
                                        highlightthickness=0, bd=0)
        self._ac_vu_canvas.pack(side="left", fill="x", expand=True, padx=4)
        self._ac_vu_bar = self._ac_vu_canvas.create_rectangle(0, 0, 0, 14,
                                                                fill=TH["green"], outline="")

        # Timer + file size
        info_frame = tk.Frame(win, bg=TH["bg"])
        info_frame.pack(fill="x", **pad)
        self._ac_timer_var = tk.StringVar(value="00:00:00")
        tk.Label(info_frame, textvariable=self._ac_timer_var, bg=TH["bg"], fg=TH["fg"],
                 font=("Consolas", 20, "bold")).pack(side="left")
        self._ac_size_var = tk.StringVar(value="")
        tk.Label(info_frame, textvariable=self._ac_size_var, bg=TH["bg"], fg=TH["fg2"],
                 font=("Consolas", 10)).pack(side="right")

        # Record / Stop / Rename buttons
        btn_frame = tk.Frame(win, bg=TH["bg"])
        btn_frame.pack(fill="x", **pad)
        self._ac_rec_btn = self._btn(btn_frame, "\u25cf  Record", self._ac_start)
        self._ac_rec_btn.pack(side="left", padx=4)
        self._ac_stop_btn = self._btn(btn_frame, "\u25a0  Stop", self._ac_stop)
        self._ac_stop_btn.pack(side="left", padx=4)
        self._ac_stop_btn.config(state="disabled")

        # Filename / output
        name_frame = tk.Frame(win, bg=TH["bg"])
        name_frame.pack(fill="x", **pad)
        tk.Label(name_frame, text="Name:", bg=TH["bg"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._ac_name_var = tk.StringVar()
        self._ac_name_entry = self._entry(name_frame, self._ac_name_var, width=28)
        self._ac_name_entry.pack(side="left", padx=4)
        self._btn(name_frame, "Rename", self._ac_rename).pack(side="left", padx=2)

        # Output folder link
        out_frame = tk.Frame(win, bg=TH["bg"])
        out_frame.pack(fill="x", padx=12, pady=(2, 4))
        tk.Label(out_frame, text="Saves to:", bg=TH["bg"], fg=TH["fg2"],
                 font=("Consolas", 8)).pack(side="left")
        folder_lbl = tk.Label(out_frame, text=AUDIO_CAPTURE_DIR, bg=TH["bg"],
                               fg=TH["blue_text"], font=("Consolas", 8), cursor="hand2")
        folder_lbl.pack(side="left", padx=4)
        folder_lbl.bind("<Button-1>", lambda e: subprocess.Popen(
            ["xdg-open", AUDIO_CAPTURE_DIR]))

        # Status
        self._ac_status_var = tk.StringVar(value="Ready")
        tk.Label(win, textvariable=self._ac_status_var, bg=TH["bg"], fg=TH["yellow"],
                 font=("Consolas", 9)).pack(pady=(0, 8))

        self._ac_refresh_sources()

    def _ac_refresh_sources(self):
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True, text=True, timeout=5)
            sources = []
            source_map = {}
            for line in result.stdout.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 2 and ".monitor" in parts[1]:
                    name = parts[1]
                    desc_result = subprocess.run(
                        ["pactl", "list", "sources"],
                        capture_output=True, text=True, timeout=5)
                    desc = name
                    for block in desc_result.stdout.split("Source #"):
                        if name in block:
                            for dl in block.splitlines():
                                if "Description:" in dl:
                                    desc = dl.split("Description:")[-1].strip()
                                    break
                            break
                    sources.append(desc)
                    source_map[desc] = name
            self._ac_source_map = source_map
            self._ac_source_combo.config(values=sources)
            for desc in sources:
                if "hdmi" in desc.lower() or "HDMI" in desc:
                    self._ac_source_var.set(desc)
                    break
            if not self._ac_source_var.get() and sources:
                self._ac_source_var.set(sources[0])
        except Exception:
            self._ac_source_combo.config(values=["default"])
            self._ac_source_map = {"default": "default"}
            self._ac_source_var.set("default")

    def _ac_start(self):
        if self._ac_recording:
            return
        source_desc = self._ac_source_var.get()
        source_name = self._ac_source_map.get(source_desc, "default")
        fmt = self._ac_format_var.get()
        bitrate = self._ac_bitrate_var.get()
        os.makedirs(AUDIO_CAPTURE_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        ext = fmt if fmt != "m4a" else "m4a"
        filename = f"capture_{ts}.{ext}"
        self._ac_output_path = os.path.join(AUDIO_CAPTURE_DIR, filename)
        self._ac_name_var.set(filename)

        codec_args = []
        if fmt == "mp3":
            codec_args = ["-c:a", "libmp3lame", "-b:a", bitrate]
        elif fmt == "opus":
            codec_args = ["-c:a", "libopus", "-b:a", bitrate]
            self._ac_output_path = self._ac_output_path.replace(".opus", ".ogg")
            self._ac_name_var.set(filename.replace(".opus", ".ogg"))
        elif fmt == "ogg":
            codec_args = ["-c:a", "libvorbis", "-b:a", bitrate]
        elif fmt == "m4a":
            codec_args = ["-c:a", "aac", "-b:a", bitrate]
        elif fmt == "wav":
            codec_args = ["-c:a", "pcm_s16le"]

        cmd = [
            "ffmpeg", "-y",
            "-f", "pulse", "-i", source_name,
            *codec_args,
            "-af", "aresample=async=1",
            "-progress", "pipe:2",
            self._ac_output_path,
        ]
        try:
            self._ac_process = subprocess.Popen(
                cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stdin=subprocess.PIPE)
        except FileNotFoundError:
            self._ac_status_var.set("Error: ffmpeg not found")
            return
        except Exception as ex:
            self._ac_status_var.set(f"Error: {ex}")
            return

        self._ac_recording = True
        self._ac_start_time = time.time()
        self._ac_rec_btn.config(state="disabled")
        self._ac_stop_btn.config(state="normal")
        self._ac_status_var.set("Recording...")
        self._ac_btn.config(fg="#ff4444", text="\U0001f534 REC")
        threading.Thread(target=self._ac_read_progress, daemon=True).start()
        self._ac_tick()

    def _ac_read_progress(self):
        proc = self._ac_process
        if not proc or not proc.stderr:
            return
        try:
            while self._ac_recording and proc.poll() is None:
                line = proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if "size=" in text:
                    for part in text.split():
                        if part.startswith("size="):
                            self._ac_peak_val = min(1.0, max(0.0, self._ac_peak_val + 0.05))
        except Exception:
            pass

    def _ac_tick(self):
        if not self._ac_recording:
            return
        if not hasattr(self, "_ac_win") or not self._ac_win.winfo_exists():
            return
        elapsed = time.time() - self._ac_start_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self._ac_timer_var.set(f"{h:02d}:{m:02d}:{s:02d}")

        if self._ac_output_path and os.path.isfile(self._ac_output_path):
            size = os.path.getsize(self._ac_output_path)
            if size < 1024 * 1024:
                self._ac_size_var.set(f"{size / 1024:.0f} KB")
            else:
                self._ac_size_var.set(f"{size / (1024 * 1024):.1f} MB")

        # Animate VU meter based on elapsed time (pulsing)
        import math
        level = 0.3 + 0.4 * abs(math.sin(elapsed * 2.5))
        self._ac_peak_val = level
        canvas_w = self._ac_vu_canvas.winfo_width()
        bar_w = int(canvas_w * self._ac_peak_val)
        color = TH["green"] if self._ac_peak_val < 0.75 else TH["yellow"] if self._ac_peak_val < 0.9 else "#ff4444"
        self._ac_vu_canvas.coords(self._ac_vu_bar, 0, 0, bar_w, 14)
        self._ac_vu_canvas.itemconfig(self._ac_vu_bar, fill=color)

        self._ac_win.after(200, self._ac_tick)

    def _ac_stop(self):
        if not self._ac_recording:
            return
        self._ac_recording = False
        if self._ac_process:
            try:
                self._ac_process.stdin.write(b"q")
                self._ac_process.stdin.flush()
            except Exception:
                pass
            try:
                self._ac_process.wait(timeout=5)
            except Exception:
                self._ac_process.kill()
            self._ac_process = None
        self._ac_rec_btn.config(state="normal")
        self._ac_stop_btn.config(state="disabled")
        self._ac_btn.config(fg=TH["fg"], text="\U0001f3a7 Capture")
        if self._ac_output_path and os.path.isfile(self._ac_output_path):
            size = os.path.getsize(self._ac_output_path)
            if size < 1024 * 1024:
                size_str = f"{size / 1024:.0f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"
            self._ac_status_var.set(f"Saved: {os.path.basename(self._ac_output_path)} ({size_str})")
        else:
            self._ac_status_var.set("Stopped (no file)")
        self._ac_vu_canvas.coords(self._ac_vu_bar, 0, 0, 0, 14)

    def _ac_rename(self):
        if not self._ac_output_path or not os.path.isfile(self._ac_output_path):
            self._ac_status_var.set("No file to rename")
            return
        new_name = self._ac_name_var.get().strip()
        if not new_name:
            return
        new_path = os.path.join(os.path.dirname(self._ac_output_path), new_name)
        try:
            os.rename(self._ac_output_path, new_path)
            self._ac_output_path = new_path
            self._ac_status_var.set(f"Renamed to {new_name}")
        except Exception as ex:
            self._ac_status_var.set(f"Rename failed: {ex}")

    def _ac_close(self, win):
        if self._ac_recording:
            self._ac_stop()
        win.destroy()
        self._ac_win = None

    def build_updates(self):
        f = self.tabs["updates"]
        wrap = tk.Frame(f, bg=TH["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(wrap, text="UPDATES", bg=TH["bg"], fg=TH["green"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(wrap, text=f"Whim Terminal v{WHIM_TERMINAL_VERSION}  |  Whim.m v{WHIM_M_VERSION}",
                 bg=TH["bg"], fg=TH["fg_dim"], font=("Consolas", 10)).pack(anchor="w", pady=(0, 12))

        self._btn(wrap, "\u21bb Update All Devices", self._update_all_devices).pack(anchor="w", pady=(0, 16))

        self._update_log = tk.Text(wrap, bg=TH["input"], fg=TH["fg"], font=("Consolas", 9),
                                   height=6, bd=0, highlightthickness=1,
                                   highlightbackground=TH["border"], state="disabled")
        self._update_log.pack(fill="x", pady=(0, 16))

        tk.Label(wrap, text="VERSION HISTORY", bg=TH["bg"], fg=TH["fg2"],
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

        history_frame = tk.Frame(wrap, bg=TH["bg"])
        history_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(history_frame, bg=TH["bg"], highlightthickness=0)
        scrollbar = self._scrollbar(history_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=TH["bg"])

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for ver, date, desc in WHIM_VERSION_HISTORY:
            row = tk.Frame(inner, bg=TH["card"], bd=0, highlightthickness=1,
                           highlightbackground=TH["border"])
            row.pack(fill="x", pady=(0, 4), padx=(0, 8))
            tk.Label(row, text=f"v{ver}", bg=TH["card"], fg=TH["green"],
                     font=("Consolas", 11, "bold")).pack(side="left", padx=(10, 8), pady=6)
            tk.Label(row, text=date, bg=TH["card"], fg=TH["fg_dim"],
                     font=("Consolas", 9)).pack(side="left", padx=(0, 12), pady=6)
            tk.Label(row, text=desc, bg=TH["card"], fg=TH["fg"],
                     font=("Segoe UI", 9), wraplength=600, anchor="w", justify="left").pack(
                         side="left", fill="x", expand=True, padx=(0, 10), pady=6)

    def _update_all_devices(self):
        self._switch_tab("updates")
        log = self._update_log
        log.config(state="normal")
        log.delete("1.0", "end")
        log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] Starting device update...\n")
        log.config(state="disabled")
        threading.Thread(target=self._do_update_devices, daemon=True).start()

    def _do_update_devices(self):
        def append(msg):
            ts = datetime.now().strftime('%H:%M:%S')
            self.after(0, lambda: self._update_log_append(f"[{ts}] {msg}\n"))

        try:
            result = subprocess.run(["adb", "devices", "-l"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                append("ERROR: adb not available")
                return
        except Exception as e:
            append(f"ERROR: {e}")
            return

        device_map = {}
        for line in result.stdout.splitlines()[1:]:
            line = line.strip()
            if not line or "offline" in line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                model = ""
                for p in parts[2:]:
                    if p.startswith("model:"):
                        model = p.split(":", 1)[1]
                if model:
                    device_map[model] = serial

        phone_apk = os.path.join(WHIM_APK_DIR, "whim_m_v3.3_phone.apk")
        tablet_apk = os.path.join(WHIM_APK_DIR, "whim_m_v3.3_tablet.apk")

        targets = [
            ("SM_G965U", "Galaxy S9", phone_apk),
            ("SM_S901U", "Galaxy S22", phone_apk),
            ("TB311FU", "Lenovo Tablet", tablet_apk),
        ]

        updated = 0
        for adb_model, label, apk_path in targets:
            serial = device_map.get(adb_model)
            if not serial:
                append(f"{label}: not connected (skipped)")
                continue
            if not os.path.isfile(apk_path):
                append(f"{label}: APK not found at {apk_path}")
                continue
            append(f"{label}: installing {os.path.basename(apk_path)}...")
            try:
                ir = subprocess.run(
                    ["adb", "-s", serial, "install", "-r", apk_path],
                    capture_output=True, text=True, timeout=60)
                if ir.returncode == 0 and "Success" in ir.stdout:
                    append(f"{label}: SUCCESS")
                    updated += 1
                else:
                    append(f"{label}: FAILED — {ir.stdout.strip()} {ir.stderr.strip()}")
            except Exception as e:
                append(f"{label}: ERROR — {e}")

        append(f"Done. {updated} device(s) updated.")

    def _update_log_append(self, msg):
        self._update_log.config(state="normal")
        self._update_log.insert("end", msg)
        self._update_log.see("end")
        self._update_log.config(state="disabled")

    def build_settings(self):
        f = self.tabs["settings"]
        wrap = tk.Frame(f, bg=TH["bg"])
        wrap.pack(fill="both", expand=True, padx=16, pady=12)

        tk.Label(wrap, text="SETTINGS", bg=TH["bg"], fg=TH["green"],
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 12))

        cols = tk.Frame(wrap, bg=TH["bg"])
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=1)
        cols.columnconfigure(2, weight=1)
        cols.rowconfigure(0, weight=1)

        # ---- Column 1: API Keys & Endpoints ----
        c1 = tk.Frame(cols, bg=TH["bg"])
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        api_card = self._card(c1, "API KEYS & ENDPOINTS", fg="#888888")
        api_card.pack(fill="x")
        api_inner = tk.Frame(api_card, bg=TH["card"])
        api_inner.pack(fill="x", padx=10, pady=(0, 10))

        r = tk.Frame(api_inner, bg=TH["card"])
        r.pack(fill="x", pady=4)
        tk.Label(r, text="Ollama URL:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=14, anchor="w").pack(side="left")
        self._settings_ollama_url_var = tk.StringVar(
            value=getattr(self, "_whimai_ollama_url", "http://localhost:11434"))
        self._entry(r, self._settings_ollama_url_var, width=30).pack(side="left", padx=4)

        r = tk.Frame(api_inner, bg=TH["card"])
        r.pack(fill="x", pady=4)
        tk.Label(r, text="OpenAI API Key:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=14, anchor="w").pack(side="left")
        self._settings_openai_key_var = tk.StringVar(value="")
        self._entry(r, self._settings_openai_key_var, width=30, show="\u2022").pack(side="left", padx=4)

        r = tk.Frame(api_inner, bg=TH["card"])
        r.pack(fill="x", pady=4)
        tk.Label(r, text="SmartThings:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=14, anchor="w").pack(side="left")
        self._settings_st_key_var = tk.StringVar(value="")
        self._entry(r, self._settings_st_key_var, width=30, show="\u2022").pack(side="left", padx=4)

        r = tk.Frame(api_inner, bg=TH["card"])
        r.pack(fill="x", pady=4)
        tk.Label(r, text="Notion Token:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"], width=14, anchor="w").pack(side="left")
        self._settings_notion_var = tk.StringVar(value="")
        self._entry(r, self._settings_notion_var, width=30, show="\u2022").pack(side="left", padx=4)

        # ---- Column 2: Model Management ----
        c2 = tk.Frame(cols, bg=TH["bg"])
        c2.grid(row=0, column=1, sticky="nsew", padx=8)

        model_card = self._card(c2, "MODEL MANAGEMENT", fg="#888888")
        model_card.pack(fill="x")
        model_inner = tk.Frame(model_card, bg=TH["card"])
        model_inner.pack(fill="x", padx=10, pady=(0, 10))

        r = tk.Frame(model_inner, bg=TH["card"])
        r.pack(fill="x", pady=4)
        tk.Label(r, text="Default Model:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._settings_default_model_var = tk.StringVar(value=self._global_model_var.get())
        self._settings_model_combo = ttk.Combobox(
            r, textvariable=self._settings_default_model_var,
            values=DEFAULT_MODELS, width=24, state="readonly")
        self._settings_model_combo.pack(side="left", padx=4)
        self._settings_model_combo.bind("<<ComboboxSelected>>",
            lambda e: self._settings_apply_default_model())

        tk.Label(model_inner, text="Available Models (from Ollama):", bg=TH["card"],
                 fg=TH["fg2"], font=TH["font_sm"]).pack(anchor="w", pady=(8, 2))
        self._settings_model_list = tk.Listbox(model_inner, bg=TH["input"], fg=TH["fg"],
                                                font=("Consolas", 10), height=8,
                                                selectbackground=TH["select_bg"],
                                                highlightthickness=0, bd=1,
                                                relief="flat")
        self._settings_model_list.pack(fill="x", pady=2)

        btn_row = tk.Frame(model_inner, bg=TH["card"])
        btn_row.pack(fill="x", pady=4)
        self._btn(btn_row, "Refresh", self._settings_refresh_models).pack(side="left", padx=2)
        self._btn(btn_row, "Pull Model", self._settings_pull_model).pack(side="left", padx=2)
        self._btn(btn_row, "Delete Model", self._settings_delete_model).pack(side="left", padx=2)

        pull_row = tk.Frame(model_inner, bg=TH["card"])
        pull_row.pack(fill="x", pady=4)
        tk.Label(pull_row, text="Model name:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._settings_pull_var = tk.StringVar()
        self._entry(pull_row, self._settings_pull_var, width=24).pack(side="left", padx=4)

        self._settings_model_status = tk.Label(model_inner, text="", bg=TH["card"],
                                                fg=TH["yellow"], font=("Consolas", 9))
        self._settings_model_status.pack(anchor="w", pady=2)

        # ---- Column 3: Preferences ----
        c3 = tk.Frame(cols, bg=TH["bg"])
        c3.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        pref_card = self._card(c3, "APP PREFERENCES", fg="#888888")
        pref_card.pack(fill="x")
        pref_inner = tk.Frame(pref_card, bg=TH["card"])
        pref_inner.pack(fill="x", padx=10, pady=(0, 10))

        self._settings_autostart_ingest = tk.BooleanVar(value=True)
        tk.Checkbutton(pref_inner, text="Auto-start Journal Ingest on launch",
                        variable=self._settings_autostart_ingest,
                        bg=TH["card"], fg=TH["fg"], selectcolor=TH["input"],
                        activebackground=TH["card"], activeforeground=TH["fg"],
                        font=TH["font_sm"], highlightthickness=0).pack(anchor="w", pady=4)

        self._settings_auto_connect = tk.BooleanVar(value=False)
        tk.Checkbutton(pref_inner, text="Auto-connect to OpenClaw Gateway",
                        variable=self._settings_auto_connect,
                        bg=TH["card"], fg=TH["fg"], selectcolor=TH["input"],
                        activebackground=TH["card"], activeforeground=TH["fg"],
                        font=TH["font_sm"], highlightthickness=0).pack(anchor="w", pady=4)

        self._settings_auto_tunnel_check = tk.BooleanVar(value=True)
        tk.Checkbutton(pref_inner, text="Monitor tunnel & Whim.m status",
                        variable=self._settings_auto_tunnel_check,
                        bg=TH["card"], fg=TH["fg"], selectcolor=TH["input"],
                        activebackground=TH["card"], activeforeground=TH["fg"],
                        font=TH["font_sm"], highlightthickness=0).pack(anchor="w", pady=4)

        r = tk.Frame(pref_inner, bg=TH["card"])
        r.pack(fill="x", pady=8)
        tk.Label(r, text="Theme:", bg=TH["card"], fg=TH["fg2"],
                 font=TH["font_sm"]).pack(side="left")
        self._settings_theme_var = tk.StringVar(value="Dark (Whim)")
        ttk.Combobox(r, textvariable=self._settings_theme_var,
                      values=["Dark (Whim)", "Midnight", "Solarized Dark"],
                      width=18, state="readonly").pack(side="left", padx=4)

        tk.Frame(pref_inner, bg=TH["border"], height=1).pack(fill="x", pady=8)

        # Paths
        paths_lbl = tk.Label(pref_inner, text="PATHS", bg=TH["card"], fg="#888888",
                              font=("Consolas", 9, "bold"))
        paths_lbl.pack(anchor="w", pady=(0, 4))

        for label, path in [
            ("Journal:", os.path.expanduser("~/Journal")),
            ("Archive:", os.path.expanduser("~/ARCHIVE")),
            ("Config:", os.path.dirname(WHIM_SETTINGS_FILE)),
            ("Voice Engine:", VOICE_ENGINE_CONFIG),
        ]:
            r = tk.Frame(pref_inner, bg=TH["card"])
            r.pack(fill="x", pady=1)
            tk.Label(r, text=label, bg=TH["card"], fg=TH["fg2"],
                     font=("Consolas", 8), width=14, anchor="w").pack(side="left")
            tk.Label(r, text=path, bg=TH["card"], fg=TH["fg"],
                     font=("Consolas", 8), anchor="w").pack(side="left")

        # ---- Save button row ----
        save_row = tk.Frame(wrap, bg=TH["bg"])
        save_row.pack(fill="x", pady=(12, 0))
        self._btn(save_row, "Save Settings", self._settings_save_all).pack(side="left", padx=4)
        self._settings_save_lbl = tk.Label(save_row, text="", bg=TH["bg"],
                                            fg=TH["green"], font=("Consolas", 9))
        self._settings_save_lbl.pack(side="left", padx=8)

        self._settings_load_all()
        self.after(500, self._settings_refresh_models)

    def _settings_apply_default_model(self):
        model = self._settings_default_model_var.get()
        self._global_model_var.set(model)
        self._on_model_change()

    def _settings_refresh_models(self):
        def _fetch():
            import urllib.request
            url = self._settings_ollama_url_var.get().strip().rstrip("/")
            try:
                req = urllib.request.Request(f"{url}/api/tags")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                models = data.get("models", [])
                names = [m["name"] for m in models]
                def _update():
                    self._settings_model_list.delete(0, "end")
                    for m in models:
                        size_gb = m.get("size", 0) / 1e9
                        self._settings_model_list.insert("end",
                            f"  {m['name']:40s} {size_gb:.1f} GB")
                    if names:
                        self._settings_model_combo.config(values=names)
                        self._model_combo.config(values=names)
                    self._settings_model_status.config(
                        text=f"{len(names)} model(s) loaded", fg=TH["green"])
                self.after(0, _update)
            except Exception as ex:
                self.after(0, lambda: self._settings_model_status.config(
                    text=f"Error: {ex}", fg="#ff4444"))
        threading.Thread(target=_fetch, daemon=True).start()

    def _settings_pull_model(self):
        name = self._settings_pull_var.get().strip()
        if not name:
            return
        self._settings_model_status.config(text=f"Pulling {name}...", fg=TH["yellow"])
        def _pull():
            import urllib.request
            url = self._settings_ollama_url_var.get().strip().rstrip("/")
            try:
                payload = json.dumps({"name": name, "stream": False}).encode()
                req = urllib.request.Request(f"{url}/api/pull", data=payload,
                                             method="POST",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=600) as resp:
                    resp.read()
                self.after(0, lambda: self._settings_model_status.config(
                    text=f"Pulled {name}", fg=TH["green"]))
                self.after(100, self._settings_refresh_models)
            except Exception as ex:
                self.after(0, lambda: self._settings_model_status.config(
                    text=f"Pull failed: {ex}", fg="#ff4444"))
        threading.Thread(target=_pull, daemon=True).start()

    def _settings_delete_model(self):
        sel = self._settings_model_list.curselection()
        if not sel:
            return
        line = self._settings_model_list.get(sel[0]).strip()
        name = line.split()[0] if line else ""
        if not name:
            return
        self._settings_model_status.config(text=f"Deleting {name}...", fg=TH["yellow"])
        def _del():
            import urllib.request
            url = self._settings_ollama_url_var.get().strip().rstrip("/")
            try:
                payload = json.dumps({"name": name}).encode()
                req = urllib.request.Request(f"{url}/api/delete", data=payload,
                                             method="DELETE",
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp.read()
                self.after(0, lambda: self._settings_model_status.config(
                    text=f"Deleted {name}", fg=TH["green"]))
                self.after(100, self._settings_refresh_models)
            except Exception as ex:
                self.after(0, lambda: self._settings_model_status.config(
                    text=f"Delete failed: {ex}", fg="#ff4444"))
        threading.Thread(target=_del, daemon=True).start()

    def _settings_save_all(self):
        cfg = self._load_settings()
        cfg["model"] = self._global_model_var.get()
        cfg["ollama_url"] = self._settings_ollama_url_var.get().strip()
        cfg["openai_key"] = self._settings_openai_key_var.get()
        cfg["smartthings_key"] = self._settings_st_key_var.get()
        cfg["notion_token"] = self._settings_notion_var.get()
        cfg["autostart_ingest"] = self._settings_autostart_ingest.get()
        cfg["auto_connect"] = self._settings_auto_connect.get()
        cfg["auto_tunnel_check"] = self._settings_auto_tunnel_check.get()
        cfg["theme"] = self._settings_theme_var.get()
        os.makedirs(os.path.dirname(WHIM_SETTINGS_FILE), exist_ok=True)
        with open(WHIM_SETTINGS_FILE, "w") as fh:
            json.dump(cfg, fh, indent=2)
        self._whimai_ollama_url = cfg["ollama_url"]
        self._settings_save_lbl.config(text="Settings saved")
        self.after(3000, lambda: self._settings_save_lbl.config(text=""))

    def _settings_load_all(self):
        cfg = self._load_settings()
        if cfg.get("ollama_url"):
            self._settings_ollama_url_var.set(cfg["ollama_url"])
        if cfg.get("openai_key"):
            self._settings_openai_key_var.set(cfg["openai_key"])
        if cfg.get("smartthings_key"):
            self._settings_st_key_var.set(cfg["smartthings_key"])
        if cfg.get("notion_token"):
            self._settings_notion_var.set(cfg["notion_token"])
        if "autostart_ingest" in cfg:
            self._settings_autostart_ingest.set(cfg["autostart_ingest"])
        if "auto_connect" in cfg:
            self._settings_auto_connect.set(cfg["auto_connect"])
        if "auto_tunnel_check" in cfg:
            self._settings_auto_tunnel_check.set(cfg["auto_tunnel_check"])
        if cfg.get("theme"):
            self._settings_theme_var.set(cfg["theme"])

    def on_connect(self):
        scopes = ["operator.read", "operator.write"]
        if self.approvals_var.get():
            scopes.append("operator.approvals")
        start_ws_thread(self.ws_url_var.get().strip(), self.token_var.get().strip(), scopes)
        self.log_events("🔌 Connecting...", module="WS", level="INFO")

    def pump_incoming(self):
        try:
            while True:
                kind, payload = incoming.get_nowait()
                if kind in ("event", "ws"):
                    if isinstance(payload, dict):
                        rid = payload.get("id", "")
                        method = payload.get("method", "")
                        req_id = rid if isinstance(rid, str) else ""
                        sess_id = ""
                        if isinstance(payload.get("params"), dict):
                            sess_id = payload["params"].get("sessionId",
                                      payload["params"].get("session_id", ""))

                        module = "WS"
                        level = "INFO"
                        if method:
                            if "smart" in method.lower():
                                module = "Gateway"
                            elif "session" in method.lower():
                                module = "Gateway"
                            elif "presence" in method.lower() or "ping" in method.lower():
                                module = "Gateway"
                            elif "chat" in method.lower():
                                module = "Whim.ai"
                        if payload.get("error"):
                            level = "ERROR"

                        self.log_events(jdump(payload), module=module,
                                        level=level, session_id=sess_id,
                                        request_id=req_id)

                        if isinstance(rid, str) and rid.startswith("sessionsList"):
                            result = payload.get("result", payload.get("params", {}))
                            sessions = result if isinstance(result, list) else result.get("sessions", [])
                            self.sessions_populate(sessions)
                        elif isinstance(rid, str) and rid.startswith("presence"):
                            result = payload.get("result", payload.get("params", {}))
                            self._pres_populate(result)
                        elif isinstance(rid, str) and rid.startswith("hb-"):
                            suffix = rid[3:]
                            comp_id = suffix[:suffix.rfind("-")] if "-" in suffix else suffix
                            result = payload.get("result", payload.get("params", {}))
                            self._pres_handle_pong(comp_id, result if isinstance(result, dict) else {})
                    else:
                        self.log_events(jdump(payload), module="WS", level="DEBUG")
                elif kind == "log":
                    self.log_events(str(payload), module="System", level="INFO")
        except queue.Empty:
            pass
        self.after(50, self.pump_incoming)

_SINGLETON_PORT = 48891

def _try_singleton_lock():
    """Bind a TCP port as a singleton lock. Returns the socket if we're first, None otherwise."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind(("127.0.0.1", _SINGLETON_PORT))
        s.listen(1)
        return s
    except OSError:
        return None

def _signal_existing_instance():
    """Tell the already-running instance to show its window."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", _SINGLETON_PORT))
        s.sendall(b"SHOW")
        s.close()
    except Exception:
        pass

if __name__ == "__main__":
    lock_sock = _try_singleton_lock()
    if lock_sock is None:
        _signal_existing_instance()
        sys.exit(0)
    app = ModernApp()
    def _singleton_listener():
        while True:
            try:
                conn, _ = lock_sock.accept()
                data = conn.recv(16)
                conn.close()
                if data == b"SHOW":
                    app.after(0, app._restore_window)
            except Exception:
                break
    threading.Thread(target=_singleton_listener, daemon=True).start()
    app.mainloop()
