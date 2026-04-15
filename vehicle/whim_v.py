#!/usr/bin/env python3
"""
Whim.V — Vehicle Dashboard
Vertical touch-optimized web UI for 1200x1920 (or any resolution).
Runs as a Flask server; open in browser on tablet or vehicle display.

Features:
  - GeoF geofence map with Leaflet satellite tiles and collar tracking
  - Doppler / NWS radar overlay (7 regional stations)
  - Named locations with address geocoding and per-site geofences
  - AI Chat via Ollama
  - LibreOffice headless document/spreadsheet viewer
  - System logs and vehicle status
  - Service Worker for offline caching
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
LOCATIONS_FILE = os.path.join(HOME, ".openclaw", "whimv_locations.json")
DOCS_DIR = os.path.join(HOME, "Documents")
INCOMING_DIR = os.path.join(HOME, "Incoming")
JOURNAL_DIR = os.path.join(HOME, "Journal")
ARCHIVE_DIR = os.path.join(HOME, "ARCHIVE")

WHIM_V_VERSION = "1.1.0"

app = Flask(__name__)

# ── Default named locations ──
DEFAULT_LOCATIONS = [
    {
        "id": "parents_house",
        "name": "Parents' House",
        "lat": 39.6335,
        "lon": -92.0033,
        "address": "",
        "fence_type": "rectangle",
        "acres": 1,
        "direction": "ns"
    },
    {
        "id": "lake_house",
        "name": "Parents' Lake House",
        "lat": 39.6965089,
        "lon": -92.015889,
        "address": "Lake of the Ozarks, MO",
        "fence_type": "rectangle",
        "acres": 2,
        "direction": "ns"
    },
    {
        "id": "jasons_house",
        "name": "Jason's House",
        "lat": 39.325519892068,
        "lon": -92.41546784880909,
        "address": "",
        "fence_type": "square",
        "acres": 5,
        "direction": "ns"
    }
]


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
    return {"vertices": [], "center": [39.6335, -92.0033], "zoom": 16}

def load_pins():
    if os.path.isfile(GEOF_PINS):
        try:
            with open(GEOF_PINS) as f:
                return json.load(f)
        except Exception:
            pass
    return []


# ── Locations ──

def load_locations():
    if os.path.isfile(LOCATIONS_FILE):
        try:
            with open(LOCATIONS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return list(DEFAULT_LOCATIONS)

def save_locations(locs):
    os.makedirs(os.path.dirname(LOCATIONS_FILE), exist_ok=True)
    with open(LOCATIONS_FILE, "w") as f:
        json.dump(locs, f, indent=2)


# ── File browser ──

def list_documents(directory, extensions=None):
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
#  SERVICE WORKER
# ════════════════════════════════════════════════════════════

SERVICE_WORKER_JS = """
const CACHE_NAME = 'whimv-cache-v1';
const STATIC_ASSETS = [
  '/',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.url.includes('/api/')) return;
  event.respondWith(
    caches.match(event.request).then(cached => {
      const fetched = fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => cached);
      return cached || fetched;
    })
  );
});
"""


# ════════════════════════════════════════════════════════════
#  DASHBOARD HTML
# ════════════════════════════════════════════════════════════

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>Whim.V</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
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

.panel { display: none; padding: 12px; min-height: calc(100vh - 110px); }
.panel.active { display: block; }

.v-card {
  background: var(--card); border-radius: 8px; padding: 14px;
  margin-bottom: 12px; border: 1px solid var(--border);
}
.v-card h3 {
  font-size: 13px; font-weight: 700; color: var(--accent);
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;
}

#geof-map {
  width: 100%; height: 50vh; background: var(--input);
  border-radius: 6px; border: 1px solid var(--border);
  z-index: 1;
}

.collar-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.collar-table th {
  background: var(--input); color: var(--accent); padding: 8px 6px;
  text-align: left; font-weight: 700; text-transform: uppercase;
  font-size: 11px; letter-spacing: 1px; position: sticky; top: 0;
}
.collar-table td { padding: 8px 6px; border-bottom: 1px solid var(--border); }
.collar-table tr:active { background: rgba(232,121,58,0.1); }

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
.v-btn.secondary { background: var(--card); color: var(--fg); border: 1px solid var(--border); }
.v-btn.secondary:active { background: var(--input); }
.v-btn.danger { background: var(--red); }

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

#log-output {
  background: var(--input); color: var(--green); font-family: 'Courier New', monospace;
  font-size: 12px; padding: 12px; border-radius: 6px; height: 60vh;
  overflow-y: auto; white-space: pre-wrap; border: 1px solid var(--border);
  -webkit-overflow-scrolling: touch;
}

.radar-container {
  width: 100%; aspect-ratio: 4/3; position: relative;
  border-radius: 6px; overflow: hidden; background: var(--input);
}
.radar-container iframe {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  border: none;
}

.radar-btn-grid {
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;
}
.radar-btn-grid .v-btn { padding: 8px 12px; font-size: 11px; flex: 1; min-width: 100px; text-align: center; }
.radar-btn-grid .v-btn.active-station { border: 2px solid var(--accent); }

.model-select {
  background: var(--input); color: var(--fg); border: 1px solid var(--border);
  padding: 8px 12px; border-radius: 6px; font-size: 13px; width: 100%;
  margin-bottom: 10px;
}

.loc-select {
  background: var(--input); color: var(--fg); border: 1px solid var(--border);
  padding: 8px 12px; border-radius: 6px; font-size: 13px; width: 100%;
}

/* Location manager modal */
.modal-overlay {
  display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.7); z-index: 500; align-items: center;
  justify-content: center;
}
.modal-overlay.open { display: flex; }
.modal-box {
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 20px; width: 90%; max-width: 500px; max-height: 85vh;
  overflow-y: auto;
}
.modal-box h3 { color: var(--accent); margin-bottom: 14px; }
.modal-field { margin-bottom: 10px; }
.modal-field label { display: block; font-size: 12px; color: var(--fg2); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 1px; }
.modal-field input, .modal-field select {
  width: 100%; background: var(--input); border: 1px solid var(--border);
  color: var(--fg); padding: 10px 12px; border-radius: 6px; font-size: 14px;
}
.modal-field input:focus { border-color: var(--accent); outline: none; }
.modal-actions { display: flex; gap: 8px; margin-top: 14px; }
.modal-actions .v-btn { flex: 1; text-align: center; }

.loc-card {
  background: var(--input); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px; margin-bottom: 8px; display: flex;
  justify-content: space-between; align-items: center; cursor: pointer;
}
.loc-card:active { border-color: var(--accent); }
.loc-card .lc-name { font-weight: 700; color: var(--fg); font-size: 14px; }
.loc-card .lc-coords { font-size: 11px; color: var(--fg2); font-family: 'Courier New', monospace; }
.loc-card .lc-address { font-size: 11px; color: var(--fg2); }
.loc-card .lc-meta { font-size: 11px; color: var(--accent); }
.loc-card-actions { display: flex; gap: 6px; }
.loc-card-actions .v-btn { padding: 6px 10px; font-size: 11px; min-width: 32px; min-height: 32px; }

.geof-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 8px; flex-wrap: wrap; gap: 6px;
}
.geof-toolbar .left { display: flex; gap: 6px; flex: 1; align-items: center; flex-wrap: wrap; }
.geof-toolbar .right { display: flex; gap: 6px; }

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
    <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
      <select class="loc-select" id="geof-loc-select" style="flex:1;min-width:160px;" onchange="geof.goToLocation(this.value)">
        <option value="">-- Select Location --</option>
      </select>
      <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="locMgr.openModal()">Manage</button>
    </div>
    <div id="geof-map"></div>
    <div class="geof-toolbar">
      <div class="left">
        <span style="font-size:12px;color:var(--fg2);" id="geof-info">Loading...</span>
      </div>
      <div class="right">
        <button class="v-btn" style="padding:8px 14px;font-size:12px;" onclick="geof.toggleTiles()">Tiles</button>
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
    <div class="radar-container">
      <iframe id="radar-frame"
        src="https://radar.weather.gov/station/KSGF/standard"
        loading="lazy" allowfullscreen></iframe>
    </div>
    <div class="radar-btn-grid" id="radar-btns">
      <button class="v-btn active-station" data-station="KSGF" onclick="radar.set('KSGF',this)">KSGF Springfield</button>
      <button class="v-btn" data-station="KSRX" onclick="radar.set('KSRX',this)">KSRX Ozarks</button>
      <button class="v-btn" data-station="KEAX" onclick="radar.set('KEAX',this)">KEAX Kansas City</button>
      <button class="v-btn" data-station="KLSX" onclick="radar.set('KLSX',this)">KLSX St. Louis</button>
      <button class="v-btn" data-station="KILX" onclick="radar.set('KILX',this)">KILX Quincy/Lincoln</button>
      <button class="v-btn" data-station="KEAX" onclick="radar.set('KEAX',this)">KEAX Columbia</button>
      <button class="v-btn" data-station="KLZK" onclick="radar.set('KLZK',this)">KLZK Little Rock</button>
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
    <h3 id="doc-title">-</h3>
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

<!-- ═══════ LOCATION MANAGER MODAL ═══════ -->
<div class="modal-overlay" id="loc-modal">
  <div class="modal-box">
    <h3 id="loc-modal-title">Manage Locations</h3>

    <div id="loc-list-view">
      <div id="loc-list-container"></div>
      <div style="margin-top:12px;">
        <button class="v-btn" style="width:100%;text-align:center;" onclick="locMgr.showAddForm()">+ Add Location</button>
      </div>
      <div style="margin-top:8px;">
        <button class="v-btn secondary" style="width:100%;text-align:center;" onclick="locMgr.closeModal()">Close</button>
      </div>
    </div>

    <div id="loc-form-view" style="display:none;">
      <div class="modal-field">
        <label>Name</label>
        <input type="text" id="loc-name" placeholder="e.g. Jason's House">
      </div>
      <div class="modal-field">
        <label>Address (auto-fills GPS)</label>
        <div style="display:flex;gap:6px;">
          <input type="text" id="loc-address" placeholder="123 Main St, City, MO" style="flex:1;">
          <button class="v-btn" style="padding:8px 12px;font-size:12px;" onclick="locMgr.geocode()">Lookup</button>
        </div>
      </div>
      <div class="modal-field" style="display:flex;gap:8px;">
        <div style="flex:1;">
          <label>Latitude</label>
          <input type="number" step="any" id="loc-lat" placeholder="39.6965">
        </div>
        <div style="flex:1;">
          <label>Longitude</label>
          <input type="number" step="any" id="loc-lon" placeholder="-92.0158">
        </div>
      </div>
      <div class="modal-field" style="display:flex;gap:8px;">
        <div style="flex:1;">
          <label>Fence Shape</label>
          <select id="loc-fence-type">
            <option value="rectangle">Rectangle</option>
            <option value="square">Square</option>
            <option value="none">None</option>
          </select>
        </div>
        <div style="flex:1;">
          <label>Acres</label>
          <input type="number" step="0.1" id="loc-acres" value="2" placeholder="2">
        </div>
      </div>
      <div id="loc-geocode-status" style="font-size:12px;color:var(--fg2);margin-bottom:8px;"></div>
      <input type="hidden" id="loc-edit-id">
      <div class="modal-actions">
        <button class="v-btn secondary" onclick="locMgr.showList()">Cancel</button>
        <button class="v-btn" onclick="locMgr.save()">Save</button>
      </div>
    </div>
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
    if (btn.dataset.tab === 'geof' && geof.map) geof.map.invalidateSize();
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
  } catch(e) {}
}
checkOllama();
setInterval(checkOllama, 30000);

// ══════════ LOCATIONS ══════════
let _locations = [];

async function loadLocations() {
  try {
    const r = await fetch('/api/locations');
    _locations = await r.json();
  } catch(e) { _locations = []; }
  updateLocationSelects();
}

function updateLocationSelects() {
  const sel = document.getElementById('geof-loc-select');
  const val = sel.value;
  sel.innerHTML = '<option value="">-- Select Location --</option>';
  _locations.forEach(l => {
    const opt = document.createElement('option');
    opt.value = l.id;
    opt.textContent = l.name + ' (' + l.lat.toFixed(4) + ', ' + l.lon.toFixed(4) + ')';
    sel.appendChild(opt);
  });
  if (val) sel.value = val;
}

// ══════════ GEOF (Leaflet) ══════════
const geof = {
  map: null, tileLayer: null, useSatellite: true,
  fenceLayer: null, pinMarkers: [], locationFences: [],

  init() {
    this.map = L.map('geof-map', {
      center: [39.6335, -92.0033],
      zoom: 16,
      zoomControl: false
    });
    this.setTiles();
    L.control.zoom({ position: 'topright' }).addTo(this.map);
    this.fenceLayer = L.layerGroup().addTo(this.map);
    this.map.on('moveend', () => this.updateInfo());
    this.refresh();
  },

  setTiles() {
    if (this.tileLayer) this.map.removeLayer(this.tileLayer);
    if (this.useSatellite) {
      this.tileLayer = L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { attribution: 'Esri Satellite', maxZoom: 19 }
      );
    } else {
      this.tileLayer = L.tileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        { attribution: 'OSM', maxZoom: 19 }
      );
    }
    this.tileLayer.addTo(this.map);
  },

  toggleTiles() {
    this.useSatellite = !this.useSatellite;
    this.setTiles();
  },

  updateInfo() {
    const c = this.map.getCenter();
    const z = this.map.getZoom();
    document.getElementById('geof-info').textContent =
      'Center: ' + c.lat.toFixed(5) + ', ' + c.lng.toFixed(5) + ' | Zoom: ' + z + ' | Pins: ' + this.pinMarkers.length;
  },

  goToLocation(locId) {
    if (!locId) return;
    const loc = _locations.find(l => l.id === locId);
    if (loc) {
      this.map.setView([loc.lat, loc.lon], 17);
    }
  },

  drawLocationFences() {
    this.locationFences.forEach(l => this.fenceLayer.removeLayer(l));
    this.locationFences = [];
    _locations.forEach(loc => {
      if (loc.fence_type === 'none') return;
      const acres = loc.acres || 2;
      const sqMeters = acres * 4046.86;
      let latDelta, lonDelta;
      if (loc.fence_type === 'square') {
        const side = Math.sqrt(sqMeters);
        latDelta = (side / 2) / 111320;
        lonDelta = (side / 2) / (111320 * Math.cos(loc.lat * Math.PI / 180));
      } else {
        const ratio = (loc.direction === 'ew') ? 0.5 : 2.0;
        const h = Math.sqrt(sqMeters * ratio);
        const w = sqMeters / h;
        latDelta = (h / 2) / 111320;
        lonDelta = (w / 2) / (111320 * Math.cos(loc.lat * Math.PI / 180));
      }
      const bounds = [
        [loc.lat - latDelta, loc.lon - lonDelta],
        [loc.lat + latDelta, loc.lon + lonDelta]
      ];
      const rect = L.rectangle(bounds, {
        color: '#e8793a', weight: 2, opacity: 0.8,
        fillColor: '#e8793a', fillOpacity: 0.1, dashArray: '6 4'
      });
      rect.bindTooltip(loc.name + (loc.address ? '<br>' + loc.address : '') +
        '<br>' + loc.lat.toFixed(5) + ', ' + loc.lon.toFixed(5) +
        '<br>' + acres + ' acres (' + loc.fence_type + ')',
        { sticky: true });
      this.fenceLayer.addLayer(rect);
      this.locationFences.push(rect);

      const marker = L.circleMarker([loc.lat, loc.lon], {
        radius: 6, color: '#e8793a', fillColor: '#e8793a',
        fillOpacity: 0.9, weight: 2
      });
      marker.bindTooltip(loc.name, { permanent: false, direction: 'top' });
      this.fenceLayer.addLayer(marker);
      this.locationFences.push(marker);
    });
  },

  async refresh() {
    try {
      const r = await fetch('/api/geof');
      const d = await r.json();

      // Clear old markers
      this.pinMarkers.forEach(m => this.map.removeLayer(m));
      this.pinMarkers = [];

      // Draw main fence polygon
      this.fenceLayer.clearLayers();
      const fence = d.fence || [];
      if (fence.length > 2) {
        const latlngs = fence.map(v => [v[0], v[1]]);
        L.polygon(latlngs, {
          color: '#2fa572', weight: 2, fillColor: '#2fa572', fillOpacity: 0.12
        }).addTo(this.fenceLayer);
      }

      // Draw location fences
      this.drawLocationFences();

      // Collar pins
      const pins = d.pins || [];
      pins.forEach(p => {
        const inFence = p.in_fence !== false;
        const marker = L.circleMarker([p.lat, p.lon], {
          radius: 10,
          color: '#f5e6d3',
          fillColor: inFence ? '#2fa572' : '#c4382a',
          fillOpacity: 0.9, weight: 2
        });
        marker.bindTooltip((p.name || p.id || '?') + (inFence ? ' (IN)' : ' (OUT)'), {
          permanent: true, direction: 'top',
          className: 'collar-tooltip'
        });
        marker.addTo(this.map);
        this.pinMarkers.push(marker);
      });

      // Collar table
      const tbody = document.getElementById('collar-tbody');
      if (pins.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="color:var(--fg2);text-align:center;">No collars detected</td></tr>';
      } else {
        tbody.innerHTML = pins.map(p =>
          '<tr><td>' + (p.id||'-') + '</td><td>' + (p.name||'-') + '</td>' +
          '<td style="color:' + (p.in_fence!==false?'var(--green)':'var(--red)') + '">' +
          (p.in_fence!==false?'IN':'OUT') + '</td>' +
          '<td>' + (p.battery||'-') + '%</td><td>' + (p.lat||0).toFixed(5) + '</td>' +
          '<td>' + (p.lon||0).toFixed(5) + '</td><td>' + (p.last_seen||'-') + '</td></tr>'
        ).join('');
      }

      this.updateInfo();
    } catch(e) { console.error('GeoF refresh error:', e); }
  }
};

// ══════════ RADAR ══════════
const radar = {
  set(station, btn) {
    document.getElementById('radar-frame').src =
      'https://radar.weather.gov/station/' + station + '/standard';
    document.querySelectorAll('#radar-btns .v-btn').forEach(b => b.classList.remove('active-station'));
    if (btn) btn.classList.add('active-station');
  }
};

// ══════════ LOCATION MANAGER ══════════
const locMgr = {
  openModal() {
    document.getElementById('loc-modal').classList.add('open');
    this.showList();
    this.renderList();
  },
  closeModal() {
    document.getElementById('loc-modal').classList.remove('open');
  },
  showList() {
    document.getElementById('loc-list-view').style.display = '';
    document.getElementById('loc-form-view').style.display = 'none';
    document.getElementById('loc-modal-title').textContent = 'Manage Locations';
    this.renderList();
  },
  showAddForm(editLoc) {
    document.getElementById('loc-list-view').style.display = 'none';
    document.getElementById('loc-form-view').style.display = '';
    document.getElementById('loc-geocode-status').textContent = '';
    if (editLoc) {
      document.getElementById('loc-modal-title').textContent = 'Edit Location';
      document.getElementById('loc-edit-id').value = editLoc.id;
      document.getElementById('loc-name').value = editLoc.name || '';
      document.getElementById('loc-address').value = editLoc.address || '';
      document.getElementById('loc-lat').value = editLoc.lat || '';
      document.getElementById('loc-lon').value = editLoc.lon || '';
      document.getElementById('loc-fence-type').value = editLoc.fence_type || 'rectangle';
      document.getElementById('loc-acres').value = editLoc.acres || 2;
    } else {
      document.getElementById('loc-modal-title').textContent = 'Add Location';
      document.getElementById('loc-edit-id').value = '';
      document.getElementById('loc-name').value = '';
      document.getElementById('loc-address').value = '';
      document.getElementById('loc-lat').value = '';
      document.getElementById('loc-lon').value = '';
      document.getElementById('loc-fence-type').value = 'rectangle';
      document.getElementById('loc-acres').value = 2;
    }
  },
  renderList() {
    const cont = document.getElementById('loc-list-container');
    if (_locations.length === 0) {
      cont.innerHTML = '<div style="padding:14px;color:var(--fg2);text-align:center;">No locations saved</div>';
      return;
    }
    cont.innerHTML = _locations.map(l =>
      '<div class="loc-card">' +
        '<div onclick="locMgr.showAddForm(' + JSON.stringify(l).replace(/"/g, '&quot;') + ')" style="flex:1;">' +
          '<div class="lc-name">' + l.name + '</div>' +
          '<div class="lc-coords">' + l.lat.toFixed(5) + ', ' + l.lon.toFixed(5) + '</div>' +
          (l.address ? '<div class="lc-address">' + l.address + '</div>' : '') +
          '<div class="lc-meta">' + (l.fence_type||'none') + ' | ' + (l.acres||0) + ' acres</div>' +
        '</div>' +
        '<div class="loc-card-actions">' +
          '<button class="v-btn danger" style="padding:6px 10px;font-size:11px;" onclick="locMgr.remove(\'' + l.id + '\')">X</button>' +
        '</div>' +
      '</div>'
    ).join('');
  },
  async geocode() {
    const addr = document.getElementById('loc-address').value.trim();
    if (!addr) return;
    const status = document.getElementById('loc-geocode-status');
    status.textContent = 'Looking up...';
    status.style.color = 'var(--fg2)';
    try {
      const r = await fetch('/api/geocode?q=' + encodeURIComponent(addr));
      const d = await r.json();
      if (d.error) {
        status.textContent = 'Not found: ' + d.error;
        status.style.color = 'var(--red)';
        return;
      }
      document.getElementById('loc-lat').value = d.lat;
      document.getElementById('loc-lon').value = d.lon;
      status.textContent = 'Found: ' + d.display;
      status.style.color = 'var(--green)';
    } catch(e) {
      status.textContent = 'Lookup failed';
      status.style.color = 'var(--red)';
    }
  },
  async save() {
    const data = {
      id: document.getElementById('loc-edit-id').value || ('loc_' + Date.now()),
      name: document.getElementById('loc-name').value.trim(),
      lat: parseFloat(document.getElementById('loc-lat').value),
      lon: parseFloat(document.getElementById('loc-lon').value),
      address: document.getElementById('loc-address').value.trim(),
      fence_type: document.getElementById('loc-fence-type').value,
      acres: parseFloat(document.getElementById('loc-acres').value) || 2
    };
    if (!data.name || isNaN(data.lat) || isNaN(data.lon)) {
      document.getElementById('loc-geocode-status').textContent = 'Name and valid coordinates required';
      document.getElementById('loc-geocode-status').style.color = 'var(--red)';
      return;
    }
    try {
      await fetch('/api/locations', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
      });
      await loadLocations();
      geof.drawLocationFences();
      this.showList();
    } catch(e) { console.error(e); }
  },
  async remove(id) {
    try {
      await fetch('/api/locations/' + id, { method: 'DELETE' });
      await loadLocations();
      geof.drawLocationFences();
      this.renderList();
    } catch(e) { console.error(e); }
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
        '<div class="file-item" onclick="docs.open(\'' + encodeURIComponent(f.path) + '\',\'' + f.name.replace(/'/g,"\\'") + '\')">' +
        '<div><div class="file-name">' + f.name + '</div>' +
        '<div class="file-meta">' + f.ext + ' &middot; ' + (f.size/1024).toFixed(1) + ' KB &middot; ' + f.modified + '</div></div>' +
        '<div style="color:var(--accent);font-size:20px;">&rarr;</div></div>'
      ).join('');
    } catch(e) { console.error(e); }
  },
  open(pathEnc, name) {
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
      sel.innerHTML = models.map(m => '<option value="' + m + '">' + m + '</option>').join('');
      if(models.length > 0) sel.value = models[0];
    } catch(e) {}
  },
  async send() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if(!text) return;
    input.value = '';

    const log = document.getElementById('chat-log');
    log.innerHTML += '<div class="msg-user">&gt; ' + text + '</div>';
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
        full += dec.decode(value);
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
(async function() {
  await loadLocations();
  geof.init();
  chat.init();
  logs.refresh();
  docs.loadDir('home');
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
})();
</script>
</body>
</html>"""


# ════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML, version=WHIM_V_VERSION)

@app.route("/sw.js")
def service_worker():
    return Response(SERVICE_WORKER_JS, mimetype="application/javascript")

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
    pins = fence_data.get("collars", [])
    if not pins:
        pins = load_pins()
    return jsonify({
        "fence": fence_data.get("vertices", []),
        "center": fence_data.get("center", [39.6335, -92.0033]),
        "zoom": fence_data.get("zoom", 16),
        "pins": pins
    })

@app.route("/api/locations")
def api_locations_get():
    return jsonify(load_locations())

@app.route("/api/locations", methods=["POST"])
def api_locations_save():
    data = request.json
    locs = load_locations()
    existing = next((l for l in locs if l["id"] == data.get("id")), None)
    if existing:
        existing.update(data)
    else:
        if not data.get("id"):
            data["id"] = f"loc_{int(time.time())}"
        locs.append(data)
    save_locations(locs)
    return jsonify({"ok": True})

@app.route("/api/locations/<loc_id>", methods=["DELETE"])
def api_locations_delete(loc_id):
    locs = [l for l in load_locations() if l["id"] != loc_id]
    save_locations(locs)
    return jsonify({"ok": True})

@app.route("/api/geocode")
def api_geocode():
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "No query"}), 400
    try:
        r = http_req.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "WhimV/1.1"},
            timeout=10
        )
        results = r.json()
        if results:
            return jsonify({
                "lat": float(results[0]["lat"]),
                "lon": float(results[0]["lon"]),
                "display": results[0].get("display_name", "")
            })
        return jsonify({"error": "No results"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

    try:
        r = http_req.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        models = [m["name"] for m in r.json().get("models", [])]
        lines.append(f"[OK] Ollama: {len(models)} model(s) loaded")
        for m in models:
            lines.append(f"     - {m}")
    except Exception:
        lines.append("[!!] Ollama: Not reachable")
    lines.append("")

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

    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 5:
                lines.append(f"[OK] Disk: {parts[2]} used / {parts[1]} total ({parts[4]})")
    except Exception:
        pass

    try:
        result = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        lines.append(f"[OK] {result.stdout.strip()}")
    except Exception:
        pass

    locs = load_locations()
    lines.append("")
    lines.append(f"[OK] Locations: {len(locs)} saved")
    for loc in locs:
        lines.append(f"     - {loc['name']}: {loc['lat']:.5f}, {loc['lon']:.5f}")

    return jsonify({"text": "\n".join(lines)})


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Whim.V - Vehicle Dashboard")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if not os.path.isfile(LOCATIONS_FILE):
        save_locations(DEFAULT_LOCATIONS)

    print()
    print("=" * 50)
    print("  Whim.V - Vehicle Dashboard")
    print(f"  v{WHIM_V_VERSION}")
    print("=" * 50)
    print()
    print(f"  Server: http://{args.host}:{args.port}")
    print(f"  Ollama: {OLLAMA_URL}")
    try:
        print(f"  LibreOffice: {subprocess.getoutput('libreoffice --version')}")
    except Exception:
        print("  LibreOffice: not found")
    print(f"  Locations: {len(load_locations())} saved")
    print()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
