#!/usr/bin/env python3
"""
Whim.V — Vehicle Dashboard
Vertical touch-optimized web UI for 1200x1920 (or any resolution).
Runs as a Flask server; open in browser on tablet or vehicle display.

Features:
  - GeoF geofence map with collar tracking
  - Doppler / NWS radar overlay
  - AI Chat via Ollama
  - LibreOffice headless document/spreadsheet viewer
  - System logs and vehicle status
  - High-contrast dark theme for driving

Usage:
    python3 whim_v.py [--port 8099] [--host 0.0.0.0]
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import (Flask, render_template_string, request, jsonify,
                   send_file, send_from_directory, Response)
import requests as http_req

# ── Config ──
HOME = os.path.expanduser("~")
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
FENCE_CONFIG = os.path.join(HOME, ".openclaw", "fence_config.json")
GEOF_PINS = os.path.join(HOME, ".openclaw", "geof_pins.json")
WHIM_SETTINGS = os.path.join(HOME, ".openclaw", "whim_settings.json")
DOCS_DIR = os.path.join(HOME, "Documents")
INCOMING_DIR = os.path.join(HOME, "Incoming")
JOURNAL_DIR = os.path.join(HOME, "Journal")
ARCHIVE_DIR = os.path.join(HOME, "ARCHIVE")

WHIM_V_VERSION = "1.0.0"

app = Flask(__name__)

# ── LibreOffice document conversion ──

def convert_document(filepath):
    """Convert a document/spreadsheet to PDF using LibreOffice headless."""
    outdir = tempfile.mkdtemp(prefix="whimv_doc_")
    try:
        result = subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf",
             "--outdir", outdir, filepath],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            name = Path(filepath).stem + ".pdf"
            pdf_path = os.path.join(outdir, name)
            if os.path.isfile(pdf_path):
                return pdf_path
    except Exception:
        pass
    return None


# ── Ollama helpers ──

def ollama_models():
    try:
        r = http_req.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []

def ollama_chat_stream(model, messages, temperature=0.7):
    """Generator that yields streamed Ollama response chunks."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature}
    }
    try:
        r = http_req.post(f"{OLLAMA_URL}/api/chat", json=payload, stream=True, timeout=120)
        for line in r.iter_lines():
            if line:
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break
    except Exception as e:
        yield f"\n[ERROR: {e}]"


# ── GeoF data ──

def load_fence():
    if os.path.isfile(FENCE_CONFIG):
        try:
            with open(FENCE_CONFIG) as f:
                return json.load(f)
        except Exception:
            pass
    return {"vertices": [], "center": [36.35, -93.2], "zoom": 12}

def load_pins():
    if os.path.isfile(GEOF_PINS):
        try:
            with open(GEOF_PINS) as f:
                return json.load(f)
        except Exception:
            pass
    return []


# ── File browser ──

def list_documents(directory, extensions=None):
    """List files in a directory, optionally filtered by extension."""
    if not os.path.isdir(directory):
        return []
    exts = extensions or [".xlsx", ".xls", ".ods", ".csv", ".doc", ".docx",
                          ".odt", ".pdf", ".txt", ".md"]
    files = []
    for f in sorted(os.listdir(directory)):
        fp = os.path.join(directory, f)
        if os.path.isfile(fp):
            ext = os.path.splitext(f)[1].lower()
            if ext in exts:
                stat = os.stat(fp)
                files.append({
                    "name": f,
                    "path": fp,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "ext": ext
                })
    return files


# ════════════════════════════════════════════════════════════
#  DASHBOARD HTML (single-page vertical layout)
# ════════════════════════════════════════════════════════════

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>Whim.V</title>
<style>
:root {
  --bg: #141210;
  --card: #2a2420;
  --input: #0c0a08;
  --border: #3a3228;
  --btn: #e8793a;
  --btn-hover: #c4382a;
  --fg: #f5e6d3;
  --fg2: #8a7a6a;
  --green: #2fa572;
  --red: #c4382a;
  --yellow: #e8a83a;
  --accent: #e8793a;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg); color: var(--fg);
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 15px; overflow-x: hidden;
  -webkit-tap-highlight-color: transparent;
  -webkit-user-select: none; user-select: none;
}

/* Header */
.header {
  background: var(--card); padding: 12px 16px;
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 2px solid var(--accent);
  position: sticky; top: 0; z-index: 100;
}
.header h1 { font-size: 22px; font-weight: 800; color: var(--accent); letter-spacing: 2px; }
.header .version { font-size: 11px; color: var(--fg2); margin-left: 8px; }
.header .status { display: flex; gap: 10px; align-items: center; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.status-dot.online { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.offline { background: var(--red); }
.status-label { font-size: 11px; color: var(--fg2); }

/* Tab bar */
.tab-bar {
  display: flex; background: var(--card); border-bottom: 1px solid var(--border);
  overflow-x: auto; -webkit-overflow-scrolling: touch;
}
.tab-btn {
  flex: 1; min-width: 80px; padding: 12px 8px; text-align: center;
  font-size: 12px; font-weight: 700; color: var(--fg2); cursor: pointer;
  border-bottom: 3px solid transparent; transition: all 0.15s;
  white-space: nowrap; text-transform: uppercase; letter-spacing: 1px;
}
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); background: var(--bg); }
.tab-btn:active { background: rgba(232,121,58,0.1); }

/* Panels */
.panel { display: none; padding: 12px; min-height: calc(100vh - 110px); }
.panel.active { display: block; }

/* Cards */
.v-card {
  background: var(--card); border-radius: 8px; padding: 14px;
  margin-bottom: 12px; border: 1px solid var(--border);
}
.v-card h3 {
  font-size: 13px; font-weight: 700; color: var(--accent);
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;
}

/* Map */
#geof-map {
  width: 100%; height: 50vh; background: var(--input);
  border-radius: 6px; border: 1px solid var(--border); position: relative;
  overflow: hidden; touch-action: none;
}
#geof-map canvas { width: 100%; height: 100%; }

/* Collar table */
.collar-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.collar-table th {
  background: var(--input); color: var(--accent); padding: 8px 6px;
  text-align: left; font-weight: 700; text-transform: uppercase;
  font-size: 11px; letter-spacing: 1px; position: sticky; top: 0;
}
.collar-table td { padding: 8px 6px; border-bottom: 1px solid var(--border); }
.collar-table tr:active { background: rgba(232,121,58,0.1); }

/* Chat */
#chat-log {
  background: var(--input); border-radius: 6px; padding: 12px;
  height: 55vh; overflow-y: auto; font-size: 14px; line-height: 1.6;
  border: 1px solid var(--border); scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
}
#chat-log .msg-user { color: var(--accent); margin: 8px 0 4px; font-weight: 600; }
#chat-log .msg-ai { color: var(--fg); margin: 4px 0 12px; white-space: pre-wrap; }
.chat-input-row { display: flex; gap: 8px; margin-top: 10px; }
.chat-input-row input {
  flex: 1; background: var(--input); border: 1px solid var(--border);
  color: var(--fg); padding: 12px 14px; border-radius: 6px; font-size: 15px;
  outline: none;
}
.chat-input-row input:focus { border-color: var(--accent); }
.chat-input-row button, .v-btn {
  background: var(--btn); color: #141210; border: none; padding: 12px 20px;
  border-radius: 6px; font-weight: 700; font-size: 14px; cursor: pointer;
  transition: background 0.15s; min-width: 44px; min-height: 44px;
}
.chat-input-row button:active, .v-btn:active { background: var(--btn-hover); }

/* Document viewer */
#doc-viewer {
  width: 100%; height: 65vh; border: 1px solid var(--border);
  border-radius: 6px; background: #fff;
}
.file-list { max-height: 30vh; overflow-y: auto; }
.file-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-bottom: 1px solid var(--border); cursor: pointer;
}
.file-item:active { background: rgba(232,121,58,0.15); }
.file-name { color: var(--fg); font-size: 14px; }
.file-meta { color: var(--fg2); font-size: 11px; }

/* Logs */
#log-output {
  background: var(--input); color: var(--green); font-family: 'Courier New', monospace;
  font-size: 12px; padding: 12px; border-radius: 6px; height: 60vh;
  overflow-y: auto; white-space: pre-wrap; border: 1px solid var(--border);
  -webkit-overflow-scrolling: touch;
}

/* Radar */
#radar-frame {
  width: 100%; height: 60vh; border: none; border-radius: 6px;
  background: var(--input);
}

/* Model selector */
.model-select {
  background: var(--input); color: var(--fg); border: 1px solid var(--border);
  padding: 8px 12px; border-radius: 6px; font-size: 13px; width: 100%;
  margin-bottom: 10px;
}

/* Responsive touches */
@media (min-width: 800px) {
  .panel { padding: 16px 24px; }
  .tab-btn { font-size: 13px; padding: 14px 12px; }
}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div style="display:flex;align-items:baseline;">
    <h1>WHIM.V</h1>
    <span class="version">v{{ version }}</span>
  </div>
  <div class="status">
    <span class="status-dot" id="ollama-dot"></span>
    <span class="status-label" id="ollama-label">Checking...</span>
    <span style="color:var(--fg2);font-size:11px;" id="clock"></span>
  </div>
</div>

<!-- TAB BAR -->
<div class="tab-bar">
  <div class="tab-btn active" data-tab="geof">GEOF</div>
  <div class="tab-btn" data-tab="radar">RADAR</div>
  <div class="tab-btn" data-tab="docs">DOCS</div>
  <div class="tab-btn" data-tab="chat">AI</div>
  <div class="tab-btn" data-tab="logs">LOGS</div>
</div>

<!-- ═══════ GEOF PANEL ═══════ -->
<div class="panel active" id="panel-geof">
  <div class="v-card">
    <h3>Geofence Tracker</h3>
    <div id="geof-map"><canvas id="geof-canvas"></canvas></div>
    <div style="display:flex;justify-content:space-between;margin-top:8px;">
      <span style="font-size:12px;color:var(--fg2);" id="geof-info">Center: 36.35, -93.20 | Zoom: 12</span>
      <div style="display:flex;gap:6px;">
        <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="geof.zoomIn()">+</button>
        <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="geof.zoomOut()">-</button>
        <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="geof.refresh()">Refresh</button>
      </div>
    </div>
  </div>
  <div class="v-card">
    <h3>Collar Status</h3>
    <div style="overflow-x:auto;">
      <table class="collar-table">
        <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Bat</th><th>Lat</th><th>Lon</th><th>Last Seen</th></tr></thead>
        <tbody id="collar-tbody"><tr><td colspan="7" style="color:var(--fg2);text-align:center;">No collars detected</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ═══════ RADAR PANEL ═══════ -->
<div class="panel" id="panel-radar">
  <div class="v-card">
    <h3>Doppler Radar — NWS</h3>
    <iframe id="radar-frame"
      src="https://radar.weather.gov/station/KSRX/standard"
      loading="lazy" allowfullscreen></iframe>
    <div style="margin-top:8px;display:flex;gap:8px;">
      <button class="v-btn" style="padding:8px 14px;font-size:12px;"
        onclick="document.getElementById('radar-frame').src='https://radar.weather.gov/station/KSRX/standard'">
        KSRX (Ozarks)</button>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;"
        onclick="document.getElementById('radar-frame').src='https://radar.weather.gov/station/KLZK/standard'">
        KLZK (Little Rock)</button>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;"
        onclick="document.getElementById('radar-frame').src='https://radar.weather.gov/station/KSGF/standard'">
        KSGF (Springfield)</button>
    </div>
  </div>
</div>

<!-- ═══════ DOCS PANEL ═══════ -->
<div class="panel" id="panel-docs">
  <div class="v-card">
    <h3>Document Viewer</h3>
    <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;">
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="docs.loadDir('home')">Home</button>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="docs.loadDir('documents')">Documents</button>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="docs.loadDir('incoming')">Incoming</button>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="docs.loadDir('journal')">Journal</button>
    </div>
    <div class="file-list" id="file-list"></div>
  </div>
  <div class="v-card" id="doc-viewer-card" style="display:none;">
    <h3 id="doc-title">—</h3>
    <iframe id="doc-viewer" src="about:blank"></iframe>
  </div>
</div>

<!-- ═══════ AI CHAT PANEL ═══════ -->
<div class="panel" id="panel-chat">
  <div class="v-card" style="display:flex;flex-direction:column;height:calc(100vh - 130px);">
    <h3>Whim.AI</h3>
    <select class="model-select" id="model-select"></select>
    <div id="chat-log" style="flex:1;"></div>
    <div class="chat-input-row">
      <input type="text" id="chat-input" placeholder="Ask anything..." autocomplete="off"
        onkeydown="if(event.key==='Enter')chat.send()">
      <button onclick="chat.send()">Send</button>
    </div>
  </div>
</div>

<!-- ═══════ LOGS PANEL ═══════ -->
<div class="panel" id="panel-logs">
  <div class="v-card">
    <h3>System Status</h3>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="logs.refresh()">Refresh</button>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="logs.clear()">Clear</button>
    </div>
    <div id="log-output">Loading system status...</div>
  </div>
</div>

<script>
// ── Tab switching ──
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Clock ──
setInterval(() => {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}, 1000);
document.getElementById('clock').textContent = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});

// ── Ollama status ──
async function checkOllama() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const dot = document.getElementById('ollama-dot');
    const lbl = document.getElementById('ollama-label');
    if (d.ollama) {
      dot.className = 'status-dot online';
      lbl.textContent = 'Ollama: Online (' + d.models + ' models)';
    } else {
      dot.className = 'status-dot offline';
      lbl.textContent = 'Ollama: Offline';
    }
  } catch(e) { /* ignore */ }
}
checkOllama();
setInterval(checkOllama, 30000);

// ══════════ GEOF ══════════
const geof = {
  center: [36.35, -93.2], zoom: 12, pins: [], fence: [],
  canvas: null, ctx: null, dragging: false, lastTouch: null,

  init() {
    this.canvas = document.getElementById('geof-canvas');
    this.ctx = this.canvas.getContext('2d');
    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.canvas.addEventListener('touchstart', e => this.onTouchStart(e), {passive:false});
    this.canvas.addEventListener('touchmove', e => this.onTouchMove(e), {passive:false});
    this.canvas.addEventListener('touchend', () => this.dragging = false);
    this.canvas.addEventListener('mousedown', e => { this.dragging = true; this.lastTouch = {x:e.clientX, y:e.clientY}; });
    this.canvas.addEventListener('mousemove', e => { if(this.dragging) this.pan(e.clientX, e.clientY); });
    this.canvas.addEventListener('mouseup', () => this.dragging = false);
    this.canvas.addEventListener('wheel', e => { e.preventDefault(); this.zoom += e.deltaY > 0 ? -1 : 1; this.zoom = Math.max(4, Math.min(18, this.zoom)); this.draw(); });
    this.refresh();
  },
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
    this.draw();
  },
  onTouchStart(e) { e.preventDefault(); if(e.touches.length===1){ this.dragging=true; this.lastTouch={x:e.touches[0].clientX,y:e.touches[0].clientY}; }},
  onTouchMove(e) { e.preventDefault(); if(this.dragging && e.touches.length===1){ this.pan(e.touches[0].clientX, e.touches[0].clientY); }},
  pan(x, y) {
    if(!this.lastTouch) return;
    const scale = 360 / Math.pow(2, this.zoom) / this.canvas.width;
    this.center[1] -= (x - this.lastTouch.x) * scale;
    this.center[0] += (y - this.lastTouch.y) * scale;
    this.lastTouch = {x, y};
    this.draw();
  },
  zoomIn() { this.zoom = Math.min(18, this.zoom + 1); this.draw(); },
  zoomOut() { this.zoom = Math.max(4, this.zoom - 1); this.draw(); },
  latLonToXY(lat, lon) {
    const scale = Math.pow(2, this.zoom);
    const w = this.canvas.width, h = this.canvas.height;
    const cx = w/2, cy = h/2;
    const dx = (lon - this.center[1]) * scale * w / 360;
    const latRad = lat * Math.PI / 180;
    const cLatRad = this.center[0] * Math.PI / 180;
    const dy = -(Math.log(Math.tan(Math.PI/4 + latRad/2)) - Math.log(Math.tan(Math.PI/4 + cLatRad/2))) * scale * w / (2*Math.PI);
    return [cx + dx, cy + dy];
  },
  draw() {
    const c = this.ctx, w = this.canvas.width, h = this.canvas.height;
    c.fillStyle = '#0c0a08'; c.fillRect(0,0,w,h);

    // Grid
    c.strokeStyle = '#1a1816'; c.lineWidth = 0.5;
    const gridStep = Math.pow(2, this.zoom) * 2;
    for(let i=0;i<w;i+=w/gridStep*10){ c.beginPath();c.moveTo(i,0);c.lineTo(i,h);c.stroke(); }
    for(let i=0;i<h;i+=h/gridStep*10){ c.beginPath();c.moveTo(0,i);c.lineTo(w,i);c.stroke(); }

    // Fence polygon
    if(this.fence.length > 2) {
      c.beginPath();
      this.fence.forEach((v,i) => {
        const [x,y] = this.latLonToXY(v[0], v[1]);
        i === 0 ? c.moveTo(x,y) : c.lineTo(x,y);
      });
      c.closePath();
      c.fillStyle = 'rgba(47,165,114,0.12)';
      c.fill();
      c.strokeStyle = '#2fa572'; c.lineWidth = 2; c.stroke();
    }

    // Pins (collars)
    this.pins.forEach(p => {
      const [x,y] = this.latLonToXY(p.lat, p.lon);
      const inFence = p.in_fence !== false;
      c.beginPath(); c.arc(x,y,8,0,Math.PI*2);
      c.fillStyle = inFence ? '#2fa572' : '#c4382a'; c.fill();
      c.strokeStyle = '#f5e6d3'; c.lineWidth = 2; c.stroke();
      c.fillStyle = '#f5e6d3'; c.font = 'bold 11px sans-serif';
      c.textAlign = 'center'; c.fillText(p.name || p.id || '?', x, y - 14);
    });

    // Center crosshair
    c.strokeStyle = 'rgba(232,121,58,0.3)'; c.lineWidth = 1;
    c.beginPath(); c.moveTo(w/2-15,h/2); c.lineTo(w/2+15,h/2); c.stroke();
    c.beginPath(); c.moveTo(w/2,h/2-15); c.lineTo(w/2,h/2+15); c.stroke();

    document.getElementById('geof-info').textContent =
      `Center: ${this.center[0].toFixed(4)}, ${this.center[1].toFixed(4)} | Zoom: ${this.zoom} | Pins: ${this.pins.length}`;
  },
  async refresh() {
    try {
      const r = await fetch('/api/geof');
      const d = await r.json();
      this.fence = d.fence || [];
      this.pins = d.pins || [];
      if(d.center) this.center = d.center;
      if(d.zoom) this.zoom = d.zoom;
      this.draw();
      // Update collar table
      const tbody = document.getElementById('collar-tbody');
      if(this.pins.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="color:var(--fg2);text-align:center;">No collars detected</td></tr>';
      } else {
        tbody.innerHTML = this.pins.map(p =>
          `<tr><td>${p.id||'—'}</td><td>${p.name||'—'}</td>` +
          `<td style="color:${p.in_fence!==false?'var(--green)':'var(--red)'}">${p.in_fence!==false?'IN':'OUT'}</td>` +
          `<td>${p.battery||'—'}%</td><td>${(p.lat||0).toFixed(5)}</td>` +
          `<td>${(p.lon||0).toFixed(5)}</td><td>${p.last_seen||'—'}</td></tr>`
        ).join('');
      }
    } catch(e) { console.error('GeoF refresh error:', e); }
  }
};

// ══════════ DOCS ══════════
const docs = {
  async loadDir(key) {
    try {
      const r = await fetch('/api/docs/list?dir=' + key);
      const files = await r.json();
      const list = document.getElementById('file-list');
      if(files.length === 0) {
        list.innerHTML = '<div style="padding:14px;color:var(--fg2);text-align:center;">No documents found</div>';
        return;
      }
      list.innerHTML = files.map(f =>
        `<div class="file-item" onclick="docs.open('${encodeURIComponent(f.path)}','${f.name}')">` +
        `<div><div class="file-name">${f.name}</div>` +
        `<div class="file-meta">${f.ext} &middot; ${(f.size/1024).toFixed(1)} KB &middot; ${f.modified}</div></div>` +
        `<div style="color:var(--accent);font-size:20px;">&rarr;</div></div>`
      ).join('');
    } catch(e) { console.error(e); }
  },
  async open(pathEnc, name) {
    document.getElementById('doc-viewer-card').style.display = 'block';
    document.getElementById('doc-title').textContent = decodeURIComponent(name);
    document.getElementById('doc-viewer').src = '/api/docs/view?path=' + pathEnc;
  }
};

// ══════════ CHAT ══════════
const chat = {
  messages: [],
  async init() {
    try {
      const r = await fetch('/api/models');
      const models = await r.json();
      const sel = document.getElementById('model-select');
      sel.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
      if(models.length > 0) sel.value = models[0];
    } catch(e) { /* ignore */ }
  },
  async send() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if(!text) return;
    input.value = '';

    const log = document.getElementById('chat-log');
    log.innerHTML += `<div class="msg-user">&gt; ${text}</div>`;
    this.messages.push({role: 'user', content: text});

    const aiDiv = document.createElement('div');
    aiDiv.className = 'msg-ai';
    log.appendChild(aiDiv);

    const model = document.getElementById('model-select').value;
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({model, messages: this.messages})
      });
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let full = '';
      while(true) {
        const {done, value} = await reader.read();
        if(done) break;
        const chunk = dec.decode(value);
        full += chunk;
        aiDiv.textContent = full;
        log.scrollTop = log.scrollHeight;
      }
      this.messages.push({role: 'assistant', content: full});
    } catch(e) {
      aiDiv.textContent = '[Error: ' + e.message + ']';
    }
    log.scrollTop = log.scrollHeight;
  }
};

// ══════════ LOGS ══════════
const logs = {
  async refresh() {
    try {
      const r = await fetch('/api/logs');
      const d = await r.json();
      document.getElementById('log-output').textContent = d.text;
    } catch(e) { document.getElementById('log-output').textContent = 'Error fetching logs'; }
  },
  clear() { document.getElementById('log-output').textContent = ''; }
};

// ── Init ──
geof.init();
chat.init();
logs.refresh();
docs.loadDir('home');
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML, version=WHIM_V_VERSION)

@app.route("/api/status")
def api_status():
    try:
        r = http_req.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = r.json().get("models", [])
        return jsonify({"ollama": True, "models": len(models)})
    except Exception:
        return jsonify({"ollama": False, "models": 0})

@app.route("/api/models")
def api_models():
    return jsonify(ollama_models())

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json
    model = data.get("model", "llama3.1:8b-16k")
    messages = data.get("messages", [])
    temperature = data.get("temperature", 0.7)

    def generate():
        for chunk in ollama_chat_stream(model, messages, temperature):
            yield chunk

    return Response(generate(), mimetype="text/plain")

@app.route("/api/geof")
def api_geof():
    fence_data = load_fence()
    pins = load_pins()
    return jsonify({
        "fence": fence_data.get("vertices", []),
        "center": fence_data.get("center", [36.35, -93.2]),
        "zoom": fence_data.get("zoom", 12),
        "pins": pins
    })

@app.route("/api/docs/list")
def api_docs_list():
    dir_key = request.args.get("dir", "home")
    dir_map = {
        "home": HOME,
        "documents": DOCS_DIR,
        "incoming": INCOMING_DIR,
        "journal": JOURNAL_DIR,
        "archive": ARCHIVE_DIR,
    }
    directory = dir_map.get(dir_key, HOME)
    return jsonify(list_documents(directory))

@app.route("/api/docs/view")
def api_docs_view():
    filepath = request.args.get("path", "")
    if not filepath or not os.path.isfile(filepath):
        return "File not found", 404

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        return send_file(filepath, mimetype="application/pdf")
    elif ext in (".txt", ".md", ".csv"):
        return send_file(filepath, mimetype="text/plain")
    elif ext in (".xlsx", ".xls", ".ods", ".doc", ".docx", ".odt"):
        pdf_path = convert_document(filepath)
        if pdf_path:
            return send_file(pdf_path, mimetype="application/pdf")
        return "Conversion failed", 500
    else:
        return send_file(filepath)

@app.route("/api/logs")
def api_logs():
    lines = []
    lines.append(f"Whim.V v{WHIM_V_VERSION}")
    lines.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Ollama
    try:
        r = http_req.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        lines.append(f"[OK] Ollama: {len(models)} model(s) loaded")
        for m in models:
            lines.append(f"     - {m}")
    except Exception:
        lines.append("[!!] Ollama: Not reachable")
    lines.append("")

    # Tailscale
    try:
        result = subprocess.run(["tailscale", "status", "--json"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ts = json.loads(result.stdout)
            self_name = ts.get("Self", {}).get("HostName", "?")
            peers = ts.get("Peer", {})
            lines.append(f"[OK] Tailscale: {self_name} ({len(peers)} peers)")
            for pid, p in peers.items():
                online = "online" if p.get("Online") else "offline"
                lines.append(f"     - {p.get('HostName','?')}: {online}")
        else:
            lines.append("[!!] Tailscale: Not connected")
    except Exception:
        lines.append("[!!] Tailscale: Not available")
    lines.append("")

    # Disk
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 5:
                lines.append(f"[OK] Disk: {parts[2]} used / {parts[1]} total ({parts[4]})")
    except Exception:
        pass

    # Uptime
    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        lines.append(f"[OK] {result.stdout.strip()}")
    except Exception:
        pass

    return jsonify({"text": "\n".join(lines)})


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Whim.V — Vehicle Dashboard")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    print()
    print("=" * 50)
    print("  Whim.V — Vehicle Dashboard")
    print(f"  v{WHIM_V_VERSION}")
    print("=" * 50)
    print()
    print(f"  Server: http://{args.host}:{args.port}")
    print(f"  Ollama: {OLLAMA_URL}")
    print(f"  LibreOffice: {subprocess.getoutput('libreoffice --version')}")
    print()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
