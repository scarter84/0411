#!/usr/bin/env python3
"""
Whim.m v2.2 — Mobile web app with recorder, file library, wake word, and cloned voice chat.
Standalone HTTP server, runs on port 8089 by default.
Usage:
    python3 whim_m_v2.1.py [--port 8089]
"""

import argparse
import cgi
import io
import json
import math
import os
import shutil
import socket
import subprocess
import sys
import threading
import wave as wave_mod
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

UPLOAD_DIR = os.path.expanduser("~/Journal")
SHARED_DIR = os.path.expanduser("~/Shared")
XTTS_CONDA_PYTHON = os.path.expanduser("~/miniconda3/envs/xtts/bin/python")
XTTS_MODEL = "tts_models/multilingual/multi-dataset/xtts_v2"
VOICES_DIR = os.path.expanduser("~/voices")
ACTIVE_VOICE_FILE = os.path.join(VOICES_DIR, "active_voice.json")
TTS_OUTPUT_DIR = os.path.expanduser("~/xtts_tts_cache")
LOCATION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "device_locations.json")
DEFAULT_PORT = 8089

# In-memory device chat store (shared across all connected devices)
_device_chat_messages = []
_device_chat_lock = threading.Lock()
_CHAT_MAX_MESSAGES = 200

WHIM_ICON_B64 = ""
_icon_path = os.path.expanduser("~/.openclaw/Whim.png")
if os.path.isfile(_icon_path):
    import base64
    with open(_icon_path, "rb") as _f:
        WHIM_ICON_B64 = base64.b64encode(_f.read()).decode()

MANIFEST = json.dumps({
    "name": "Whim.m v2.1",
    "short_name": "Whim.m",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#1e1e1e",
    "theme_color": "#1e1e1e",
    "icons": [
        {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
})

SW_JS = "self.addEventListener('fetch',e=>e.respondWith(fetch(e.request).catch(()=>caches.match(e.request))));"

RECORDER_HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#1e1e1e">
<link rel="manifest" href="/manifest.json">
<title>Whim.m v2.2</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{--max-w:360px;--rec-size:72px;--rec-dot:28px;--rec-dot-stop:22px;--timer-sz:28px;
  --wave-h:80px;--export-pad:16px;--export-sz:17px;--logo-sz:48px;--h1-sz:20px;
  --health-sz:10px;--fab-sz:38px;--fab-icon:18px;--sub-sz:12px;--ver-sz:10px;
  --pick-pad:12px;--pick-sz:14px;--fitem-pad:10px 12px;--fname-sz:13px;--fsize-sz:11px;
  --status-sz:14px;--prog-h:6px;--gap:20px;--body-pt:40px;--logo-mt:12px}
@media(min-width:600px){
  :root{--max-w:90vw;--rec-size:140px;--rec-dot:56px;--rec-dot-stop:44px;--timer-sz:56px;
    --wave-h:140px;--export-pad:28px;--export-sz:26px;--logo-sz:64px;--h1-sz:32px;
    --health-sz:14px;--fab-sz:52px;--fab-icon:24px;--sub-sz:16px;--ver-sz:13px;
    --pick-pad:20px;--pick-sz:20px;--fitem-pad:16px 20px;--fname-sz:18px;--fsize-sz:15px;
    --status-sz:20px;--prog-h:10px;--gap:36px;--body-pt:52px;--logo-mt:12px}
}
body{background:#1e1e1e;color:#dce4ee;font-family:-apple-system,system-ui,'Segoe UI',sans-serif;
  height:100vh;margin:0;padding:0;overflow:hidden;display:flex;flex-direction:column}

/* Health bar */
.health-bar{position:fixed;top:0;left:0;right:0;display:flex;justify-content:center;gap:12px;
  padding:6px 12px;background:#2b2b2b;border-bottom:1px solid #3a3a3a;font-size:var(--health-sz);
  font-family:'Courier New',monospace;z-index:200}
.health-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px;vertical-align:middle}
.health-dot.ok{background:#2fa572}.health-dot.warn{background:#e0a030}.health-dot.fail{background:#d94040}

/* SS fab */
.ss-fab{position:fixed;top:8px;right:12px;z-index:300;width:var(--fab-sz);height:var(--fab-sz);
  border-radius:50%;background:#2b2b2b;border:1.5px solid #3a3a3a;cursor:pointer;display:flex;
  align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,.4)}
.ss-fab svg{width:var(--fab-icon);height:var(--fab-icon)}

/* Tab bar */
.tab-bar{display:flex;position:fixed;bottom:0;left:0;right:0;background:#2b2b2b;
  border-top:1px solid #3a3a3a;z-index:200;padding:4px 0 env(safe-area-inset-bottom,4px)}
.tab-btn{flex:1;display:flex;flex-direction:column;align-items:center;padding:8px 4px;
  background:none;border:none;color:#666;font-size:10px;cursor:pointer;font-family:inherit}
.tab-btn.active{color:#00ff00}
.tab-btn svg{width:20px;height:20px;margin-bottom:2px}
@media(min-width:600px){.tab-btn{font-size:14px;padding:12px 4px}.tab-btn svg{width:28px;height:28px}}

/* Tab content */
.tab-content{display:none;flex:1;overflow-y:auto;padding:48px 16px 72px;align-items:center}
.tab-content.active{display:flex;flex-direction:column;align-items:center}

/* Shared */
.logo{margin:var(--logo-mt) 0 4px}
.logo svg{width:var(--logo-sz);height:var(--logo-sz)}
h1{color:#00ff00;font-size:var(--h1-sz);font-family:'Courier New',monospace;margin-bottom:2px;letter-spacing:1px}
.version{color:#555;font-size:var(--ver-sz);font-family:'Courier New',monospace;margin-bottom:2px}
.sub{color:#666;font-size:var(--sub-sz);margin-bottom:16px}
.wave-vis{width:100%;max-width:var(--max-w);height:var(--wave-h);background:#2b2b2b;border:1px solid #3a3a3a;
  border-radius:10px;margin-bottom:16px;overflow:hidden}
.wave-vis canvas{width:100%;height:100%;display:block}
.controls{display:flex;gap:var(--gap);align-items:center;justify-content:center;margin-bottom:16px}
.rec-btn{width:var(--rec-size);height:var(--rec-size);border-radius:50%;
  border:3px solid #3a3a3a;background:#2b2b2b;cursor:pointer;display:flex;align-items:center;
  justify-content:center;transition:border-color .2s}
.rec-btn:active{transform:scale(0.95)}
.rec-btn .dot{width:var(--rec-dot);height:var(--rec-dot);border-radius:50%;background:#d94040;transition:all .2s}
.rec-btn.recording{border-color:#d94040;animation:pulse 1.5s infinite}
.rec-btn.recording .dot{border-radius:6px;width:var(--rec-dot-stop);height:var(--rec-dot-stop)}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(217,64,64,0.4)}50%{box-shadow:0 0 0 18px rgba(217,64,64,0)}}
.timer{font-family:'Courier New',monospace;font-size:var(--timer-sz);color:#dce4ee;min-width:100px;text-align:center;letter-spacing:2px}
.action-btn{width:100%;max-width:var(--max-w);padding:var(--export-pad);border:none;border-radius:10px;
  font-size:var(--export-sz);font-weight:600;cursor:pointer;transition:all .2s;margin-bottom:12px}
.action-btn.inactive{background:#333;color:#555;cursor:default}
.action-btn.ready{background:#2fa572;color:#fff}
.action-btn.ready:active{background:#248a5e;transform:scale(0.97)}
.action-btn.blue{background:#14507a;color:#fff}
.action-btn.blue:active{background:#0e3a58}
.action-btn.red{background:#d94040;color:#fff}
.action-btn.red:active{background:#b33030}
.progress{width:100%;max-width:var(--max-w);background:#333;border-radius:6px;height:var(--prog-h);
  margin-bottom:12px;overflow:hidden;display:none}
.progress-bar{height:100%;background:#14507a;transition:width .15s;width:0}
.status{text-align:center;padding:12px;border-radius:12px;font-size:var(--status-sz);
  margin-bottom:12px;display:none;max-width:var(--max-w);width:100%}
.status.ok{display:block;background:#1a3a2a;color:#2fa572}
.status.err{display:block;background:#3a1a1a;color:#d94040}
.flist{width:100%;max-width:var(--max-w)}
.flist h2{color:#555;font-size:var(--fsize-sz);text-transform:uppercase;letter-spacing:2px;margin-bottom:8px}
.fitem{background:#2b2b2b;border:1px solid #3a3a3a;border-radius:8px;padding:var(--fitem-pad);margin-bottom:6px;
  display:flex;justify-content:space-between;align-items:center;gap:8px}
.fname{font-size:var(--fname-sz);color:#aaa;word-break:break-all;flex:1}
.fsize{font-size:var(--fsize-sz);color:#555;white-space:nowrap}
.fbtn{background:#333;border:1px solid #3a3a3a;border-radius:6px;padding:6px 10px;cursor:pointer;color:#aaa;font-size:12px}
.fbtn:active{background:#444}
.pick-section{width:100%;max-width:var(--max-w);margin-bottom:12px}
.pick-btn{width:100%;padding:var(--pick-pad);background:#2b2b2b;color:#888;border:1px dashed #3a3a3a;
  border-radius:10px;font-size:var(--pick-sz);cursor:pointer;text-align:center}
.pick-btn:active{background:#333}
input[type=file]{display:none}

/* Wake word tab */
.ww-status-circle{width:120px;height:120px;border-radius:50%;border:3px solid #3a3a3a;
  display:flex;align-items:center;justify-content:center;margin:24px auto;transition:all .3s}
.ww-status-circle.listening{border-color:#2fa572;box-shadow:0 0 30px rgba(47,165,114,0.3)}
.ww-status-circle.detected{border-color:#00ff00;box-shadow:0 0 40px rgba(0,255,0,0.4);animation:pulse 1s infinite}
.ww-status-circle svg{width:48px;height:48px}
.ww-label{text-align:center;font-family:'Courier New',monospace;font-size:16px;color:#888;margin:12px 0}
@media(min-width:600px){.ww-status-circle{width:180px;height:180px;border-width:5px}.ww-status-circle svg{width:72px;height:72px}.ww-label{font-size:24px}}

/* Chat voice */
.chat-box{width:100%;max-width:var(--max-w);flex:1;display:flex;flex-direction:column;margin-top:8px}
.chat-messages{flex:1;overflow-y:auto;margin-bottom:8px;max-height:40vh}
.chat-msg{padding:10px 14px;margin-bottom:6px;border-radius:10px;font-size:14px;line-height:1.5}
.chat-msg.user{background:#14507a;color:#dce4ee;align-self:flex-end;margin-left:40px}
.chat-msg.assistant{background:#2b2b2b;border:1px solid #3a3a3a;color:#dce4ee;margin-right:20px}
.chat-msg .speak-btn{display:inline-block;margin-top:6px;padding:4px 12px;background:#333;
  border:1px solid #3a3a3a;border-radius:6px;cursor:pointer;color:#2fa572;font-size:12px}
.chat-msg .speak-btn:active{background:#444}
.chat-msg .speak-btn.loading{color:#e0a030}
.chat-input-row{display:flex;gap:8px;width:100%;max-width:var(--max-w)}
.chat-input-row input{flex:1;padding:12px;background:#2b2b2b;border:1px solid #3a3a3a;border-radius:10px;
  color:#dce4ee;font-size:14px;outline:none}
.chat-input-row input:focus{border-color:#14507a}
.chat-input-row button{padding:12px 16px;background:#2fa572;border:none;border-radius:10px;
  color:#fff;font-weight:600;cursor:pointer;font-size:14px}
.voice-label{color:#555;font-size:11px;text-align:center;margin-bottom:4px;font-family:'Courier New',monospace}

/* Device chat */
.dc-msg{padding:8px 12px;margin-bottom:6px;border-radius:10px;font-size:14px;line-height:1.4;
  background:#2b2b2b;border:1px solid #3a3a3a;color:#dce4ee;max-width:85%;word-break:break-word}
.dc-msg.dc-mine{background:#14507a;border-color:#14507a;margin-left:auto}
.dc-sender{color:#2fa572;font-weight:600;font-size:12px}
.dc-mine .dc-sender{color:#88ccff}
.dc-time{color:#555;font-size:11px}
.dc-file-link{color:#2fa572;text-decoration:underline;word-break:break-all}
</style></head><body>

<div class="health-bar" id="healthBar">
  <span><span class="health-dot" id="dotServer"></span>server</span>
  <span><span class="health-dot" id="dotMic"></span>mic</span>
</div>
<div class="ss-fab" id="ssFab" title="Screen Share">
  <svg viewBox="0 0 24 24" fill="none" stroke="#14507a" stroke-width="2">
  <path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
</div>

<!-- ========== TAB: RECORDER ========== -->
<div class="tab-content active" id="tabRecorder">
  <div class="logo"><svg viewBox="0 0 64 64" fill="none"><circle cx="32" cy="32" r="30" stroke="#00ff00" stroke-width="2" fill="none"/><path d="M16 32 Q20 18,24 32 Q28 46,32 32 Q36 18,40 32 Q44 46,48 32" stroke="#00ff00" stroke-width="2.5" fill="none" stroke-linecap="round"/></svg></div>
  <h1>Whim.m</h1>
  <div class="version">v2.2</div>
  <p class="sub">voice recorder</p>
  <div class="wave-vis"><canvas id="waveCanvas"></canvas></div>
  <div class="controls">
    <div class="timer" id="timer">00:00</div>
    <div class="rec-btn" id="recBtn"><div class="dot"></div></div>
  </div>
  <button class="action-btn inactive" id="exportBtn" disabled>EXPORT TO WHIM</button>
  <div class="pick-section">
    <input type="file" id="fileInput" accept="audio/*,.m4a,.aac,.ogg,.opus,.flac,.wav,.mp3,.3gp,.amr">
    <div class="pick-btn" onclick="document.getElementById('fileInput').click()">or choose an existing file</div>
  </div>
  <div class="progress" id="progress"><div class="progress-bar" id="progressBar"></div></div>
  <div class="status" id="recStatus"></div>
  <div class="flist" id="filesList"></div>
  <div id="audioPlayerWrap" style="width:100%;max-width:var(--max-w);margin-top:8px;display:none">
    <audio id="audioPlayer" controls style="width:100%;border-radius:8px"></audio>
  </div>
</div>

<!-- ========== TAB: LIBRARY ========== -->
<div class="tab-content" id="tabLibrary">
  <h1 style="margin-top:16px">Library</h1>
  <p class="sub">shared files across devices</p>
  <div class="pick-section">
    <input type="file" id="libFileInput" multiple>
    <div class="pick-btn" onclick="document.getElementById('libFileInput').click()">Upload file to library</div>
  </div>
  <div class="progress" id="libProgress"><div class="progress-bar" id="libProgressBar"></div></div>
  <div class="status" id="libStatus"></div>
  <div class="flist" id="libraryList"></div>
</div>

<!-- ========== TAB: WAKE WORD ========== -->
<div class="tab-content" id="tabWakeWord">
  <h1 style="margin-top:16px">Wake Word</h1>
  <p class="sub">"Hey Whim"</p>
  <div class="ww-status-circle" id="wwCircle">
    <svg viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" id="wwIcon">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  </div>
  <div class="ww-label" id="wwLabel">Tap to enable</div>
  <button class="action-btn blue" id="wwToggle" style="max-width:var(--max-w)">ENABLE WAKE WORD</button>
  <div class="status" id="wwStatus"></div>
  <div style="max-width:var(--max-w);width:100%;margin-top:24px">
    <h2 style="color:#555;font-size:var(--fsize-sz);text-transform:uppercase;letter-spacing:2px;margin-bottom:8px">Voice Chat</h2>
    <div class="voice-label" id="activeVoiceLabel">voice: loading...</div>
    <div class="chat-messages" id="chatMessages"></div>
    <div class="chat-input-row">
      <input type="text" id="chatInput" placeholder="Type or speak..." autocomplete="off">
      <button id="chatSendBtn">Send</button>
    </div>
  </div>
</div>

<!-- ========== TAB: DEVICE CHAT ========== -->
<div class="tab-content" id="tabDeviceChat">
  <h1 style="margin-top:16px">Device Chat</h1>
  <p class="sub">talk between your devices</p>
  <div id="dcNameSetup" style="width:100%;max-width:var(--max-w);text-align:center">
    <p style="color:#888;margin-bottom:12px">Set your device name to start chatting</p>
    <input type="text" id="dcNameInput" placeholder="e.g. Galaxy S9, Tablet..." style="width:100%;padding:12px;background:#2b2b2b;border:1px solid #3a3a3a;border-radius:10px;color:#dce4ee;font-size:14px;outline:none;margin-bottom:8px">
    <button class="action-btn blue" id="dcSaveBtn">JOIN CHAT</button>
  </div>
  <div id="dcChatArea" style="display:none;flex-direction:column;width:100%;max-width:var(--max-w);flex:1">
    <div id="dcMessages" style="flex:1;overflow-y:auto;max-height:50vh;margin-bottom:8px"></div>
    <div style="display:flex;gap:8px;align-items:center">
      <input type="text" id="dcInput" placeholder="Message all devices..." style="flex:1;padding:12px;background:#2b2b2b;border:1px solid #3a3a3a;border-radius:10px;color:#dce4ee;font-size:14px;outline:none" autocomplete="off">
      <label style="cursor:pointer;padding:10px;background:#333;border:1px solid #3a3a3a;border-radius:10px;display:flex;align-items:center">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#888" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
        <input type="file" id="dcFileInput" style="display:none">
      </label>
      <button id="dcSendBtn" style="padding:12px 16px;background:#2fa572;border:none;border-radius:10px;color:#fff;font-weight:600;cursor:pointer;font-size:14px">Send</button>
    </div>
  </div>
</div>

<!-- ========== TAB BAR ========== -->
<div class="tab-bar">
  <button class="tab-btn active" data-tab="tabRecorder">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>
    REC
  </button>
  <button class="tab-btn" data-tab="tabLibrary">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
    LIBRARY
  </button>
  <button class="tab-btn" data-tab="tabDeviceChat">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    CHAT
  </button>
  <button class="tab-btn" data-tab="tabWakeWord">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>
    WAKE
  </button>
</div>

<script>
// ========== TAB SWITCHING ==========
const tabBtns=document.querySelectorAll('.tab-btn');
const tabContents=document.querySelectorAll('.tab-content');
tabBtns.forEach(btn=>{btn.addEventListener('click',()=>{
  tabBtns.forEach(b=>b.classList.remove('active'));
  tabContents.forEach(t=>t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(btn.dataset.tab).classList.add('active');
  if(btn.dataset.tab==='tabRecorder'){setTimeout(()=>{resizeCanvas();drawIdle()},50)}
  if(btn.dataset.tab==='tabLibrary'){loadLibrary()}
  if(btn.dataset.tab==='tabWakeWord'){loadActiveVoice()}
  if(btn.dataset.tab==='tabDeviceChat'&&deviceName){startDCPoll()}
})});

// ========== HEALTH ==========
const dotServer=document.getElementById('dotServer'),dotMic=document.getElementById('dotMic');
async function checkHealth(){
  try{const ac=new AbortController();const tid=setTimeout(()=>ac.abort(),3000);
    const r=await fetch('/health',{signal:ac.signal});clearTimeout(tid);
    dotServer.className='health-dot '+(r.ok?'ok':'warn');
  }catch(e){dotServer.className='health-dot fail'}
  try{if(navigator.permissions&&navigator.permissions.query){
    const p=await navigator.permissions.query({name:'microphone'});
    dotMic.className='health-dot '+(p.state==='granted'?'ok':p.state==='prompt'?'warn':'fail');
  }}catch(e){dotMic.className='health-dot warn'}
}
checkHealth();setInterval(checkHealth,15000);

// ========== RECORDER ==========
const recBtn=document.getElementById('recBtn'),exportBtn=document.getElementById('exportBtn'),
  timerEl=document.getElementById('timer'),canvas=document.getElementById('waveCanvas'),
  progress=document.getElementById('progress'),progressBar=document.getElementById('progressBar'),
  recStatus=document.getElementById('recStatus'),fileInput=document.getElementById('fileInput'),
  audioPlayer=document.getElementById('audioPlayer'),audioPlayerWrap=document.getElementById('audioPlayerWrap');
const ctx=canvas.getContext('2d');
let mediaRec=null,chunks=[],recording=false,audioBlob=null,timerInt=null,startTime=0;
let audioCtx=null,analyser=null,animId=null,stream=null;

function resizeCanvas(){const ow=canvas.offsetWidth||360,oh=canvas.offsetHeight||80;
  const dpr=window.devicePixelRatio||1;canvas.width=ow*dpr;canvas.height=oh*dpr;ctx.setTransform(dpr,0,0,dpr,0,0)}
function ensureCanvas(){if(canvas.width===0||canvas.height===0)resizeCanvas()}
window.addEventListener('resize',resizeCanvas);
function logicalSize(){const d=window.devicePixelRatio||1;return{w:canvas.width/d,h:canvas.height/d}}
function drawIdle(){ensureCanvas();const{w,h}=logicalSize();ctx.clearRect(0,0,w,h);ctx.strokeStyle='#3a3a3a';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,h/2);ctx.lineTo(w,h/2);ctx.stroke()}
function drawWave(){if(!analyser){drawIdle();return}ensureCanvas();const{w,h}=logicalSize();
  const buf=analyser.frequencyBinCount,data=new Uint8Array(buf);analyser.getByteTimeDomainData(data);
  ctx.clearRect(0,0,w,h);ctx.strokeStyle='#00ff00';ctx.lineWidth=window.innerWidth>600?3:1.5;ctx.beginPath();
  const s=w/buf;for(let i=0;i<buf;i++){const v=data[i]/128,y=(v*h)/2;i===0?ctx.moveTo(0,y):ctx.lineTo(i*s,y)}
  ctx.stroke();if(recording)animId=requestAnimationFrame(drawWave)}
requestAnimationFrame(function(){resizeCanvas();drawIdle()});
function fmtTime(ms){const s=Math.floor(ms/1000),m=Math.floor(s/60);return String(m).padStart(2,'0')+':'+String(s%60).padStart(2,'0')}
function updateTimer(){timerEl.textContent=fmtTime(Date.now()-startTime)}

async function startRec(){
  try{stream=await navigator.mediaDevices.getUserMedia({audio:true});dotMic.className='health-dot ok';
    audioCtx=new(window.AudioContext||window.webkitAudioContext)();if(audioCtx.state==='suspended')await audioCtx.resume();
    const src=audioCtx.createMediaStreamSource(stream);analyser=audioCtx.createAnalyser();analyser.fftSize=2048;src.connect(analyser);
    mediaRec=new MediaRecorder(stream,{mimeType:MediaRecorder.isTypeSupported('audio/webm;codecs=opus')?'audio/webm;codecs=opus':'audio/webm'});
    chunks=[];mediaRec.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data)};
    mediaRec.onstop=()=>{audioBlob=new Blob(chunks,{type:mediaRec.mimeType});
      exportBtn.disabled=false;exportBtn.className='action-btn ready';
      stream.getTracks().forEach(t=>t.stop());stream=null;
      if(audioCtx){audioCtx.close();audioCtx=null;analyser=null}drawIdle()};
    mediaRec.start(200);recording=true;startTime=Date.now();timerInt=setInterval(updateTimer,200);
    setTimeout(()=>{resizeCanvas();drawWave()},50);recBtn.classList.add('recording');
  }catch(e){dotMic.className='health-dot fail';showStatus(recStatus,'Mic denied: '+e.message,'err')}
}
function stopRec(){if(mediaRec&&mediaRec.state!=='inactive'){mediaRec.stop();recording=false;
  clearInterval(timerInt);recBtn.classList.remove('recording');if(animId)cancelAnimationFrame(animId)}}
recBtn.addEventListener('click',()=>{recording?stopRec():startRec()});
fileInput.addEventListener('change',()=>{if(fileInput.files.length){audioBlob=fileInput.files[0];
  exportBtn.disabled=false;exportBtn.className='action-btn ready';timerEl.textContent=fileInput.files[0].name.substring(0,12)}});

exportBtn.addEventListener('click',()=>{if(!audioBlob)return;
  const fd=new FormData();
  const ext=audioBlob.type.includes('webm')?'.webm':audioBlob.type.includes('ogg')?'.ogg':
    audioBlob.type.includes('mp4')||audioBlob.type.includes('m4a')?'.m4a':'.wav';
  const fn='whim_rec_'+new Date().toISOString().replace(/[:.]/g,'-').substring(0,19)+ext;
  fd.append('audio',audioBlob,fn);
  const xhr=new XMLHttpRequest();progress.style.display='block';
  xhr.upload.addEventListener('progress',e=>{if(e.lengthComputable)progressBar.style.width=Math.round(e.loaded/e.total*100)+'%'});
  xhr.addEventListener('load',()=>{progress.style.display='none';
    if(xhr.status===200){showStatus(recStatus,'Exported to Whim!','ok');audioBlob=null;
      exportBtn.disabled=true;exportBtn.className='action-btn inactive';timerEl.textContent='00:00';loadFiles()}
    else showStatus(recStatus,'Export failed','err')});
  xhr.addEventListener('error',()=>{progress.style.display='none';showStatus(recStatus,'Network error','err')});
  xhr.open('POST','/upload');xhr.send(fd)});

function playAudio(name){audioPlayer.src='/audio/'+encodeURIComponent(name);audioPlayerWrap.style.display='block';audioPlayer.play()}

function loadFiles(){fetch('/files').then(r=>r.json()).then(files=>{
  const c=document.getElementById('filesList');if(!files.length){c.innerHTML='';return}
  c.innerHTML='<h2>Sent to Whim</h2>'+files.slice(0,15).map(f=>
    '<div class="fitem"><span class="fname">'+f.name+'</span><span class="fsize">'+f.size+'</span>'+
    '<span class="fbtn" onclick="playAudio(\''+f.name.replace(/'/g,"\\'")+'\')">&#9654;</span></div>'
  ).join('')}).catch(()=>{})}
loadFiles();

// ========== LIBRARY ==========
const libFileInput=document.getElementById('libFileInput'),libProgress=document.getElementById('libProgress'),
  libProgressBar=document.getElementById('libProgressBar'),libStatus=document.getElementById('libStatus');

libFileInput.addEventListener('change',()=>{if(!libFileInput.files.length)return;
  const fd=new FormData();fd.append('file',libFileInput.files[0]);
  const xhr=new XMLHttpRequest();libProgress.style.display='block';
  xhr.upload.addEventListener('progress',e=>{if(e.lengthComputable)libProgressBar.style.width=Math.round(e.loaded/e.total*100)+'%'});
  xhr.addEventListener('load',()=>{libProgress.style.display='none';
    if(xhr.status===200){showStatus(libStatus,'File uploaded!','ok');loadLibrary()}
    else showStatus(libStatus,'Upload failed','err')});
  xhr.addEventListener('error',()=>{libProgress.style.display='none';showStatus(libStatus,'Network error','err')});
  xhr.open('POST','/library/upload');xhr.send(fd)});

function loadLibrary(){fetch('/library').then(r=>r.json()).then(files=>{
  const c=document.getElementById('libraryList');if(!files.length){c.innerHTML='<p style="color:#555;text-align:center;margin-top:24px">No shared files yet</p>';return}
  c.innerHTML='<h2>Shared Files</h2>'+files.map(f=>
    '<div class="fitem"><span class="fname">'+f.name+'</span><span class="fsize">'+f.size+'</span>'+
    '<a class="fbtn" href="/library/download/'+encodeURIComponent(f.name)+'" download>DL</a></div>'
  ).join('')}).catch(()=>{})}

// ========== WAKE WORD ==========
const wwCircle=document.getElementById('wwCircle'),wwLabel=document.getElementById('wwLabel'),
  wwToggle=document.getElementById('wwToggle'),wwStatus=document.getElementById('wwStatus'),
  wwIcon=document.getElementById('wwIcon');
let wwActive=false,wwRecognition=null,wwContinuous=false;

function initWakeWord(){
  if(!('webkitSpeechRecognition' in window)&&!('SpeechRecognition' in window)){
    showStatus(wwStatus,'Speech recognition not supported on this browser','err');return false}
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  wwRecognition=new SR();wwRecognition.continuous=true;wwRecognition.interimResults=true;wwRecognition.lang='en-US';
  wwRecognition.onresult=e=>{
    for(let i=e.resultIndex;i<e.results.length;i++){
      const t=e.results[i][0].transcript.toLowerCase().trim();
      if(t.includes('hey whim')){
        wwCircle.className='ww-status-circle detected';wwLabel.textContent='Detected! Listening...';
        wwIcon.setAttribute('stroke','#00ff00');
        setTimeout(()=>{if(wwActive){wwCircle.className='ww-status-circle listening';
          wwLabel.textContent='Listening for "Hey Whim"...';wwIcon.setAttribute('stroke','#2fa572')}},2000);
        if(typeof WhimBridge!=='undefined'&&WhimBridge.onWakeWord){WhimBridge.onWakeWord()}
        startSpeechInput();
      }
    }
  };
  wwRecognition.onend=()=>{if(wwActive){try{wwRecognition.start()}catch(e){}}};
  wwRecognition.onerror=e=>{if(e.error!=='no-speech'&&e.error!=='aborted'){
    showStatus(wwStatus,'Recognition error: '+e.error,'err')}};
  return true;
}

function startSpeechInput(){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
  const cmd=new SR();cmd.continuous=false;cmd.interimResults=false;cmd.lang='en-US';
  cmd.onresult=e=>{const t=e.results[0][0].transcript;
    document.getElementById('chatInput').value=t;sendChat()};
  cmd.onerror=()=>{};cmd.onend=()=>{};
  try{wwRecognition.stop()}catch(e){}
  setTimeout(()=>{try{cmd.start()}catch(e){}},300);
  cmd.onend=()=>{if(wwActive){setTimeout(()=>{try{wwRecognition.start()}catch(e){}},300)}};
}

wwToggle.addEventListener('click',()=>{
  if(!wwActive){
    if(!wwRecognition&&!initWakeWord())return;
    wwActive=true;wwToggle.textContent='DISABLE WAKE WORD';wwToggle.className='action-btn red';
    wwCircle.className='ww-status-circle listening';wwLabel.textContent='Listening for "Hey Whim"...';
    wwIcon.setAttribute('stroke','#2fa572');
    try{wwRecognition.start()}catch(e){}
  }else{
    wwActive=false;wwToggle.textContent='ENABLE WAKE WORD';wwToggle.className='action-btn blue';
    wwCircle.className='ww-status-circle';wwLabel.textContent='Tap to enable';
    wwIcon.setAttribute('stroke','#666');
    try{wwRecognition.stop()}catch(e){}
  }
});

// ========== WHIM.AI VOICE CHAT ==========
const chatMessages=document.getElementById('chatMessages'),chatInput=document.getElementById('chatInput'),
  chatSendBtn=document.getElementById('chatSendBtn'),activeVoiceLabel=document.getElementById('activeVoiceLabel');
let chatHistory=[],currentVoice=null,autoSpeak=true;

function loadActiveVoice(){fetch('/active_voice').then(r=>r.json()).then(d=>{
  currentVoice=d;
  activeVoiceLabel.textContent='voice: '+(d.name||'none assigned — set in AVR LAB')
}).catch(()=>{activeVoiceLabel.textContent='voice: unavailable'})}
loadActiveVoice();

chatSendBtn.addEventListener('click',sendAIChat);
chatInput.addEventListener('keydown',e=>{if(e.key==='Enter')sendAIChat()});

function sendAIChat(){
  const text=chatInput.value.trim();if(!text)return;chatInput.value='';
  chatHistory.push({role:'user',content:text});
  appendAIChatMsg(text,'user');
  const body=JSON.stringify({messages:chatHistory});
  fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body})
    .then(r=>{const reader=r.body.getReader();const decoder=new TextDecoder();let full='';
      const msgEl=appendAIChatMsg('...','assistant');
      function read(){reader.read().then(({done,value})=>{if(done){
        chatHistory.push({role:'assistant',content:full});
        msgEl.querySelector('.msg-text').textContent=full;
        const sb=document.createElement('span');sb.className='speak-btn';sb.textContent='Speak';
        sb.onclick=()=>speakText(full,sb);msgEl.appendChild(sb);
        if(autoSpeak&&currentVoice&&currentVoice.name){speakText(full,sb)}
        return}
        const chunk=decoder.decode(value);
        chunk.split('\n').filter(l=>l.trim()).forEach(line=>{try{const j=JSON.parse(line);
          if(j.message&&j.message.content){full+=j.message.content;msgEl.querySelector('.msg-text').textContent=full}}catch(e){}});
        read()})}
      read()}).catch(e=>{appendAIChatMsg('Error: '+e.message,'assistant')});
}

function appendAIChatMsg(text,role){
  const d=document.createElement('div');d.className='chat-msg '+role;
  const s=document.createElement('span');s.className='msg-text';s.textContent=text;d.appendChild(s);
  chatMessages.appendChild(d);chatMessages.scrollTop=chatMessages.scrollHeight;return d}

function speakText(text,btn){
  if(!currentVoice||!currentVoice.file){
    showStatus(wwStatus,'No voice assigned. Set one in AVR LAB on desktop.','err');return}
  btn.textContent='Generating voice...';btn.className='speak-btn loading';
  const ttsText=text.length>500?text.substring(0,500)+'...':text;
  fetch('/api/tts',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({text:ttsText,voice_file:currentVoice.file})})
    .then(r=>{if(!r.ok)throw new Error('TTS server error '+r.status);return r.json()})
    .then(d=>{
      if(d.audio_url){
        const a=new Audio(d.audio_url);
        a.oncanplaythrough=()=>a.play();
        a.onerror=()=>{btn.textContent='Play failed';setTimeout(()=>{btn.textContent='Speak';btn.className='speak-btn'},2000)};
        a.onended=()=>{btn.textContent='Speak';btn.className='speak-btn'};
        btn.textContent='Playing...';btn.className='speak-btn';
      } else{
        btn.textContent=d.error||'TTS error';btn.className='speak-btn loading';
        setTimeout(()=>{btn.textContent='Speak';btn.className='speak-btn'},3000)}
    }).catch(e=>{btn.textContent='Error: '+e.message;
      setTimeout(()=>{btn.textContent='Speak';btn.className='speak-btn'},3000)});
}

// ========== DEVICE-TO-DEVICE CHAT ==========
let deviceName=localStorage.getItem('whim_device_name')||'';
let lastMsgId=0,dcPollTimer=null;
const dcNameInput=document.getElementById('dcNameInput'),dcSaveBtn=document.getElementById('dcSaveBtn'),
  dcMessages=document.getElementById('dcMessages'),dcInput=document.getElementById('dcInput'),
  dcSendBtn=document.getElementById('dcSendBtn'),dcFileInput=document.getElementById('dcFileInput'),
  dcNameSetup=document.getElementById('dcNameSetup'),dcChatArea=document.getElementById('dcChatArea');

if(deviceName){dcNameSetup.style.display='none';dcChatArea.style.display='flex';startDCPoll()}

dcSaveBtn.addEventListener('click',()=>{
  const n=dcNameInput.value.trim();if(!n)return;deviceName=n;localStorage.setItem('whim_device_name',n);
  dcNameSetup.style.display='none';dcChatArea.style.display='flex';startDCPoll()});

dcSendBtn.addEventListener('click',sendDCMsg);
dcInput.addEventListener('keydown',e=>{if(e.key==='Enter')sendDCMsg()});

function sendDCMsg(){
  const text=dcInput.value.trim();if(!text||!deviceName)return;dcInput.value='';
  fetch('/device/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({sender:deviceName,text:text,type:'text'})}).catch(()=>{})
}

dcFileInput.addEventListener('change',()=>{
  if(!dcFileInput.files.length||!deviceName)return;
  const fd=new FormData();fd.append('file',dcFileInput.files[0]);
  fetch('/library/upload',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
    if(d.file){fetch('/device/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({sender:deviceName,text:'Shared file: '+d.file,type:'file',
        file_url:'/library/download/'+encodeURIComponent(d.file)})}).catch(()=>{})}
  }).catch(()=>{})});

function pollDC(){
  fetch('/device/chat?since='+lastMsgId).then(r=>r.json()).then(msgs=>{
    msgs.forEach(m=>{
      lastMsgId=Math.max(lastMsgId,m.id);
      const d=document.createElement('div');
      d.className='dc-msg'+(m.sender===deviceName?' dc-mine':'');
      let html='<span class="dc-sender">'+m.sender+'</span> <span class="dc-time">'+m.time+'</span><br>';
      if(m.type==='file'&&m.file_url){html+='<a class="dc-file-link" href="'+m.file_url+'" download>'+m.text+'</a>'}
      else{html+='<span>'+m.text+'</span>'}
      d.innerHTML=html;dcMessages.appendChild(d);dcMessages.scrollTop=dcMessages.scrollHeight;
    })}).catch(()=>{})}

function startDCPoll(){if(dcPollTimer)return;pollDC();dcPollTimer=setInterval(pollDC,2000)}

// ========== UTIL ==========
function showStatus(el,msg,type){el.className='status '+type;el.textContent=msg;el.style.display='block';
  setTimeout(()=>{el.style.display='none'},4000)}

if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(()=>{})}
document.getElementById('ssFab').addEventListener('click',()=>{window.location.href='http://'+location.hostname+':8091'});
if(typeof WhimBridge!=='undefined'&&WhimBridge.onReady){try{WhimBridge.onReady()}catch(e){}}
</script></body></html>"""


def _get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _get_tailscale_ip():
    try:
        out = subprocess.check_output(
            ["tailscale", "ip", "-4"], timeout=5, stderr=subprocess.DEVNULL
        ).decode().strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


def _human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


class RecorderHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            import urllib.request as _ur
            ollama_ok = False
            try:
                with _ur.urlopen(_ur.Request("http://localhost:11434/api/tags"), timeout=3) as r:
                    ollama_ok = r.status == 200
            except Exception:
                pass
            self._json_response(200, {"status": "ok", "version": "2.2", "ollama": ollama_ok,
                                      "tail": "WHIM_M_TAIL_OK"})
        elif self.path == "/tail_verify":
            ts = datetime.now().strftime("%H:%M:%S")
            n = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]) if os.path.isdir(UPLOAD_DIR) else 0
            data = f"WHIM_M_TAIL_OK:{ts}:files={n}".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(data)))
            self._cors()
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/locations":
            self._serve_locations()
        elif self.path == "/files":
            self._serve_file_list()
        elif self.path == "/library":
            self._serve_library_list()
        elif self.path.startswith("/library/download/"):
            self._serve_library_file()
        elif self.path.startswith("/audio/"):
            self._serve_audio_file()
        elif self.path == "/voices":
            self._serve_voices()
        elif self.path == "/active_voice":
            self._serve_active_voice()
        elif self.path.startswith("/tts_audio/"):
            self._serve_tts_audio()
        elif self.path == "/device/chat":
            self._serve_device_chat()
        elif self.path == "/manifest.json":
            self._text_response(200, MANIFEST, "application/json")
        elif self.path == "/sw.js":
            self._text_response(200, SW_JS, "application/javascript")
        elif self.path in ("/icon-192.png", "/icon-512.png"):
            self._serve_pwa_icon(192 if "192" in self.path else 512)
        else:
            self._text_response(200, RECORDER_HTML, "text/html; charset=utf-8")

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
        "SIGNAL / DISCORD: sig.send, sig.recv, sig.contacts, disc.send, disc.react, disc.search.\n"
        "ARCHIVE & FILES: archive.new, archive.save, archive.open, journal, ingest.\n"
        "SYSTEM: You can read/write files, run shell commands, manage SmartThings devices, "
        "control Tailscale networking, manage sessions, and access all Whim subsystems.\n"
        "When the user issues a command, acknowledge it and describe what you would do. "
        "Be concise and direct. You are always ready to act."
    )

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        elif self.path == "/locations":
            self._handle_location_update()
        elif self.path == "/api/chat":
            self._handle_ai_chat()
        elif self.path == "/api/tts":
            self._handle_tts()
        elif self.path == "/library/upload":
            self._handle_library_upload()
        elif self.path == "/device/chat":
            self._handle_device_chat_post()
        else:
            self.send_error(404)

    def _handle_ai_chat(self):
        import urllib.request as _ur
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
            req = _ur.Request(
                "http://localhost:11434/api/chat",
                data=payload, method="POST",
                headers={"Content-Type": "application/json"})
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self._cors()
            self.end_headers()
            with _ur.urlopen(req, timeout=120) as resp:
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

    def _json_response(self, code, obj):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text_response(self, code, text, ctype):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_pwa_icon(self, size):
        try:
            from PIL import Image, ImageDraw
            bg = (20, 20, 22, 255)
            accent = (200, 210, 225, 255)
            glow = (100, 160, 220, 80)
            ring_c = (60, 70, 85, 255)
            img = Image.new("RGBA", (size, size), bg)
            d = ImageDraw.Draw(img)
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

    def _handle_location_update(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            update = json.loads(body)
            if os.path.isfile(LOCATION_FILE):
                with open(LOCATION_FILE, "r") as f:
                    data = json.load(f)
            else:
                data = {"devices": [], "updated": ""}
            device_name = update.get("name", "")
            for i, dev in enumerate(data.get("devices", [])):
                if dev.get("name") == device_name or dev.get("tailscale_ip") == update.get("tailscale_ip"):
                    data["devices"][i]["gps"] = update.get("gps")
                    break
            else:
                data["devices"].append(update)
            data["updated"] = datetime.now().isoformat() + "Z"
            os.makedirs(os.path.dirname(LOCATION_FILE), exist_ok=True)
            with open(LOCATION_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self._json_response(200, {"status": "ok"})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _serve_locations(self):
        if os.path.isfile(LOCATION_FILE):
            with open(LOCATION_FILE, "r") as f:
                data = f.read()
            self._text_response(200, data, "application/json")
        else:
            self._json_response(404, {"error": "No location data"})

    def _serve_file_list(self):
        files = []
        if os.path.isdir(UPLOAD_DIR):
            for fn in sorted(os.listdir(UPLOAD_DIR), reverse=True):
                fp = os.path.join(UPLOAD_DIR, fn)
                if os.path.isfile(fp):
                    files.append({"name": fn, "size": _human_size(os.path.getsize(fp))})
        self._json_response(200, files)

    # --- Library endpoints ---
    def _serve_library_list(self):
        files = []
        if os.path.isdir(SHARED_DIR):
            for fn in sorted(os.listdir(SHARED_DIR), reverse=True):
                fp = os.path.join(SHARED_DIR, fn)
                if os.path.isfile(fp):
                    files.append({"name": fn, "size": _human_size(os.path.getsize(fp))})
        self._json_response(200, files)

    def _serve_library_file(self):
        fname = os.path.basename(self.path.split("/library/download/", 1)[-1])
        fpath = os.path.join(SHARED_DIR, fname)
        if not os.path.isfile(fpath):
            self.send_error(404, "File not found")
            return
        self._stream_file(fpath, fname)

    def _handle_library_upload(self):
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
                keep_blank_values=True,
            )
            file_item = form["file"]
            if not file_item.filename:
                self.send_error(400, "No file uploaded")
                return
            safe_name = os.path.basename(file_item.filename)
            dest_path = os.path.join(SHARED_DIR, safe_name)
            os.makedirs(SHARED_DIR, exist_ok=True)
            with open(dest_path, "wb") as out:
                shutil.copyfileobj(file_item.file, out)
            self._json_response(200, {"status": "ok", "file": safe_name})
        except Exception as exc:
            self.send_error(500, str(exc))

    # --- Audio streaming endpoint ---
    def _serve_audio_file(self):
        fname = os.path.basename(self.path.split("/audio/", 1)[-1])
        fpath = os.path.join(UPLOAD_DIR, fname)
        if not os.path.isfile(fpath):
            self.send_error(404, "Audio file not found")
            return
        self._stream_file(fpath, fname)

    def _stream_file(self, fpath, fname):
        ext = os.path.splitext(fname)[1].lower()
        ctypes = {
            ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
            ".webm": "audio/webm", ".m4a": "audio/mp4", ".flac": "audio/flac",
            ".aac": "audio/aac", ".3gp": "audio/3gpp", ".amr": "audio/amr",
            ".opus": "audio/opus", ".pdf": "application/pdf",
            ".txt": "text/plain", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".mp4": "video/mp4",
        }
        ctype = ctypes.get(ext, "application/octet-stream")
        fsize = os.path.getsize(fpath)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(fsize))
        self.send_header("Content-Disposition", f'inline; filename="{fname}"')
        self._cors()
        self.end_headers()
        with open(fpath, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    # --- Voice / TTS endpoints ---
    def _serve_voices(self):
        voices = []
        if os.path.isdir(VOICES_DIR):
            for fn in sorted(os.listdir(VOICES_DIR)):
                fp = os.path.join(VOICES_DIR, fn)
                if os.path.isfile(fp) and fn.lower().endswith((".wav", ".mp3", ".flac", ".ogg")):
                    voices.append({"name": os.path.splitext(fn)[0], "file": fn})
        self._json_response(200, voices)

    def _serve_active_voice(self):
        if os.path.isfile(ACTIVE_VOICE_FILE):
            with open(ACTIVE_VOICE_FILE, "r") as f:
                data = json.load(f)
            self._json_response(200, data)
        else:
            self._json_response(200, {"name": None, "file": None})

    def _serve_tts_audio(self):
        fname = os.path.basename(self.path.split("/tts_audio/", 1)[-1])
        fpath = os.path.join(TTS_OUTPUT_DIR, fname)
        if not os.path.isfile(fpath):
            self.send_error(404, "TTS audio not found")
            return
        self._stream_file(fpath, fname)

    def _handle_tts(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            text = data.get("text", "").strip()
            voice_file = data.get("voice_file", "").strip()
            lang = data.get("language", "en")

            if not text:
                self._json_response(400, {"error": "No text provided"})
                return

            if not voice_file:
                if os.path.isfile(ACTIVE_VOICE_FILE):
                    with open(ACTIVE_VOICE_FILE, "r") as f:
                        av = json.load(f)
                    voice_file = av.get("file", "")

            if not voice_file:
                self._json_response(400, {"error": "No voice assigned. Set one in AVR LAB."})
                return

            ref_wav = os.path.join(VOICES_DIR, voice_file)
            if not os.path.isfile(ref_wav):
                self._json_response(404, {"error": f"Voice file not found: {voice_file}"})
                return
            if not os.path.isfile(XTTS_CONDA_PYTHON):
                self._json_response(500, {"error": "XTTS conda env not found"})
                return

            os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            out_fname = f"tts_{ts}.wav"
            out_path = os.path.join(TTS_OUTPUT_DIR, out_fname)

            script = (
                "import torch\n"
                "from TTS.tts.configs.xtts_config import XttsConfig\n"
                "from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs\n"
                "from TTS.config.shared_configs import BaseDatasetConfig\n"
                "torch.serialization.add_safe_globals([XttsConfig, XttsAudioConfig, XttsArgs, BaseDatasetConfig])\n"
                "from TTS.api import TTS\n"
                f"tts = TTS({XTTS_MODEL!r}, gpu=True)\n"
                f"tts.tts_to_file(text={text!r}, file_path={out_path!r}, "
                f"speaker_wav={ref_wav!r}, language={lang!r})\n"
                "print('OK')\n"
            )

            proc = subprocess.run(
                [XTTS_CONDA_PYTHON, "-c", script],
                capture_output=True, text=True, timeout=300
            )
            if proc.returncode != 0:
                self._json_response(500, {"error": proc.stderr.strip()[:500]})
                return

            self._json_response(200, {
                "status": "ok",
                "audio_url": f"/tts_audio/{out_fname}",
                "file": out_fname,
            })
        except subprocess.TimeoutExpired:
            self._json_response(500, {"error": "TTS generation timed out"})
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    # --- Device-to-device chat ---
    def _serve_device_chat(self):
        since = 0
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
            for part in qs.split("&"):
                if part.startswith("since="):
                    try:
                        since = int(part.split("=", 1)[1])
                    except ValueError:
                        pass
        with _device_chat_lock:
            msgs = [m for m in _device_chat_messages if m["id"] > since]
        self._json_response(200, msgs)

    def _handle_device_chat_post(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            sender = data.get("sender", "Unknown").strip()[:32]
            text = data.get("text", "").strip()
            msg_type = data.get("type", "text")
            file_url = data.get("file_url", "")
            if not text and not file_url:
                self._json_response(400, {"error": "Empty message"})
                return
            with _device_chat_lock:
                msg_id = len(_device_chat_messages) + 1
                msg = {
                    "id": msg_id,
                    "sender": sender,
                    "text": text,
                    "type": msg_type,
                    "file_url": file_url,
                    "time": datetime.now().strftime("%H:%M:%S"),
                }
                _device_chat_messages.append(msg)
                if len(_device_chat_messages) > _CHAT_MAX_MESSAGES:
                    _device_chat_messages[:] = _device_chat_messages[-_CHAT_MAX_MESSAGES:]
            self._json_response(200, msg)
        except Exception as e:
            self._json_response(500, {"error": str(e)})

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
                keep_blank_values=True,
            )
            file_item = form["audio"]
            if not file_item.filename:
                self.send_error(400, "No file uploaded")
                return
            safe_name = os.path.basename(file_item.filename)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_name = f"{ts}_{safe_name}"
            dest_path = os.path.join(UPLOAD_DIR, dest_name)
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            with open(dest_path, "wb") as out:
                shutil.copyfileobj(file_item.file, out)
            self._json_response(200, {"status": "ok", "file": dest_name})
        except Exception as exc:
            self.send_error(500, str(exc))


def preflight_checks():
    ts_ip = _get_tailscale_ip()
    lan_ip = _get_lan_ip()
    if ts_ip:
        print(f"  Tailscale IP : {ts_ip}")
    else:
        print("  Tailscale    : not detected (LAN-only mode)")
    print(f"  LAN IP       : {lan_ip}")
    for d, label in [(UPLOAD_DIR, "Upload dir"), (SHARED_DIR, "Shared dir"), (TTS_OUTPUT_DIR, "TTS cache")]:
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            print(f"  Created {label}: {d}")
        else:
            print(f"  {label:12s} : {d}")
    return ts_ip, lan_ip


def main():
    parser = argparse.ArgumentParser(description="Whim.m v2.2 — mobile server with recorder, library, TTS")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    print("=" * 50)
    print("  Whim.m v2.2 — Recorder + Library + Voice")
    print("=" * 50)
    ts_ip, lan_ip = preflight_checks()
    port = args.port

    server = HTTPServer(("0.0.0.0", port), RecorderHandler)
    print(f"\n  Listening on  : 0.0.0.0:{port}")
    print(f"  Open on phone : http://{lan_ip}:{port}")
    if ts_ip:
        print(f"  Via Tailscale : http://{ts_ip}:{port}")
    print(f"\n  NOTE: Use COLON before port, not a dot!")
    print(f"        Correct : http://{ts_ip or lan_ip}:{port}")
    print(f"        Wrong   : http://{ts_ip or lan_ip}.{port}")
    print("=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
