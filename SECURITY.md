# SECURITY — Whim Ecosystem Exposure Report

**Audit Date:** April 13, 2026
**Auditor:** Claude Opus 4.6 (automated deep scan)
**Scope:** Full codebase — Whim Terminal v3.4, Whim.m v3.4, Whim.V v1.0, supporting services
**Method:** Static analysis of all source files, HTTP endpoint review, subprocess/eval audit, config review

> This report is published intentionally as part of Whim's radical transparency philosophy.
> Every vulnerability is documented so users know exactly what they're running.

---

## Summary

| Severity | Terminal | Whim.m | Whim.V | Support | Total |
|----------|:-------:|:------:|:------:|:-------:|:-----:|
| CRITICAL | 3 | 3 | 3 | 2 | **11** |
| HIGH | 8 | 5 | 4 | 5 | **22** |
| MEDIUM | 7 | 5 | 5 | 6 | **23** |
| LOW | 4 | 2 | 2 | 5 | **13** |
| INFO | 3 | 1 | 1 | 5 | **10** |
| **Total** | **25** | **16** | **15** | **23** | **79** |

---

## Top 10 Critical & High Priority Findings

### 1. CRITICAL — No Authentication on Any Server

**Affects:** Whim.m (:8089), Whim.V (:8099), Journal Ingest (:8088), Screen Share (:8091)

All HTTP servers bind to `0.0.0.0` with zero authentication. Anyone on the network — LAN, Tailscale, or VPS tunnel — has full access to upload files, chat with AI, browse the filesystem, view geofence/collar GPS data, and issue system commands.

```python
# whim_m_v2.1.py
server = HTTPServer(("0.0.0.0", port), RecorderHandler)

# whim_v.py
app.run(host="0.0.0.0", port=args.port, debug=False, threaded=True)
```

**Recommendation:** Add token-based or HTTP Basic authentication to all endpoints. For VPS-exposed servers, this is the #1 priority.

---

### 2. CRITICAL — eval()/exec() on User Input (Terminal)

**Affects:** openclaw_tkui.py, lines ~9180, 9201, 9710, 9728, 9787–9792

The RyvenCore/Ryven Editor tabs use `eval()` and `exec()` to execute user-provided code directly. While intended for a code editor, any network-connected feature that can inject content into these fields enables remote code execution.

**Recommendation:** Sandbox code execution in a subprocess with restricted permissions. Never use `eval()`/`exec()` on anything that could be influenced by network input.

---

### 3. CRITICAL — Arbitrary File Read via Path Traversal (Whim.V)

**Affects:** whim_v.py `/api/docs/view` endpoint

The document viewer accepts a `path` query parameter and serves any file on disk with no directory validation:

```python
filepath = request.args.get("path", "")
if not filepath or not os.path.isfile(filepath):
    return "File not found", 404
return send_file(filepath)  # Can serve /etc/passwd, ~/.ssh/id_rsa, etc.
```

**Recommendation:** Validate that `os.path.realpath(filepath)` starts with an allowed directory. Never pass raw user input to `send_file()`.

---

### 4. CRITICAL — Code Injection via TTS Script Generation (Whim.m)

**Affects:** whim_m_v2.1.py `_handle_tts`, line ~1746

The TTS handler builds a Python script string from user-controlled text and voice file parameters using `{text!r}` interpolation, then executes it via subprocess. While `!r` provides some escaping, crafted payloads could potentially escape repr quoting.

```python
script = f"tts.tts_to_file(text={text!r}, file_path={out_path!r}, speaker_wav={ref_wav!r}, ...)"
proc = subprocess.run([XTTS_CONDA_PYTHON, "-c", script], ...)
```

**Recommendation:** Write parameters to a JSON file and have the subprocess read from it instead of building Python source from user input.

---

### 5. CRITICAL — Unauthenticated WebSocket Sync with File Write (whim_sync.py)

**Affects:** whim_sync.py — WebSocket sync listeners on `0.0.0.0`

The sync service accepts file write commands from any WebSocket peer without authentication. A remote attacker can write arbitrary files to attacker-controlled paths.

**Recommendation:** Add peer authentication (shared secret or certificate). Validate all file paths against an allowlist.

---

### 6. HIGH — Arbitrary File Read/Exfiltration (Whim.m)

**Affects:** whim_m_v2.1.py `send_file` command, `_handle_file_search`

The `send_file` command walks `~/` recursively and copies matching files to the shared library. The `/search_files` endpoint exposes full file paths across multiple home directories. Both are unauthenticated.

**Recommendation:** Restrict file operations to specific safe directories. Require authentication. Never walk `~/` recursively for unauthenticated users.

---

### 7. HIGH — CORS Wildcard on All Endpoints

**Affects:** Whim.m (all endpoints), Terminal (ingest server)

```python
self.send_header("Access-Control-Allow-Origin", "*")
```

Any website on the internet can make cross-origin requests to these servers. Combined with no authentication, a malicious webpage can upload files, exfiltrate data, or issue commands.

**Recommendation:** Restrict CORS to specific known origins or remove the wildcard entirely.

---

### 8. HIGH — Command Injection via AI Prompt (Whim.m)

**Affects:** whim_m_v2.1.py — AI-generated `whim-cmd` JSON blocks execute server actions

The AI system prompt instructs the LLM to generate executable command blocks, and certain actions (like `open_maps`) call `subprocess.Popen()` directly. Prompt injection could trick the LLM into generating harmful commands.

**Recommendation:** Validate all command actions with a strict allowlist. Never let AI output trigger subprocess calls without explicit user approval.

---

### 9. HIGH — Cleartext HTTP Everywhere (No TLS)

**Affects:** All servers — Terminal, Whim.m, Whim.V

All traffic including file uploads, AI chat, geofence GPS data, and system commands is transmitted in cleartext. Vulnerable to eavesdropping and MITM attacks.

**Recommendation:** Deploy TLS via reverse proxy (nginx/caddy) or `ssl_context`. Critical for VPS tunnel exposure.

---

### 10. HIGH — ADB Shell Command Injection (Terminal)

**Affects:** openclaw_tkui.py — ADB portal, whim_adb_portal.py

ADB commands are constructed with string formatting that may include unsanitized device names or package identifiers. If device input is attacker-controlled, this enables command injection on the host.

**Recommendation:** Use `shlex.quote()` for all user-provided values in subprocess arguments. Use list-form `subprocess.run()` exclusively.

---

## Full Findings by Component

### Whim Terminal (`openclaw_tkui.py`)

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| T-01 | CRITICAL | Code Execution | `eval()`/`exec()` in RyvenCore/Ryven Editor on user code |
| T-02 | CRITICAL | No Auth | 3 HTTP servers on `0.0.0.0` (8088, 8091, 8092) with no auth |
| T-03 | CRITICAL | Code Execution | XTTS voice synthesis builds Python source from user input |
| T-04 | HIGH | CORS | `Access-Control-Allow-Origin: *` on ingest server |
| T-05 | HIGH | SSRF | AI chat proxies to Ollama — URL could be redirected |
| T-06 | HIGH | Command Injection | ADB shell commands with string-formatted device input |
| T-07 | HIGH | Credential Storage | API keys stored in cleartext JSON config |
| T-08 | HIGH | Code Injection | XTTS script interpolation via string formatting |
| T-09 | HIGH | No Auth | Screen share POST endpoint unauthenticated |
| T-10 | HIGH | WebSocket Auth | WebSocket auth uses empty default token |
| T-11 | HIGH | Tar Extraction | `tarfile.extractall()` without member validation |
| T-12 | MEDIUM | Path Traversal | Upload file paths use basename but no realpath validation |
| T-13 | MEDIUM | Self-signed TLS | Generated certs not pinned or verified |
| T-14 | MEDIUM | Upload Size | No upload size limit on ingest server |
| T-15 | MEDIUM | Info Disclosure | Error messages expose internal paths |
| T-16 | MEDIUM | No Rate Limit | AI chat and TTS endpoints unlimited |
| T-17 | MEDIUM | No CSRF | POST endpoints lack CSRF tokens |
| T-18 | MEDIUM | Subprocess | Several `subprocess.Popen` calls without timeout |
| T-19 | LOW | Empty Token | Default WebSocket token is empty string |
| T-20 | LOW | Temp Files | Temp file creation without explicit cleanup |
| T-21 | LOW | Signal Logging | Signal CLI commands may log message content |
| T-22 | LOW | Pipe Buffer | Unbounded subprocess stdout pipe |
| T-23 | INFO | ADB Pattern | ADB commands use safe list-form (positive finding) |
| T-24 | INFO | Screen Capture | Desktop capture has no privacy indicator |
| T-25 | INFO | File Perms | Settings file readable by all local users |

### Whim.m (`whim_m_v2.1.py`)

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| M-01 | CRITICAL | No Auth | HTTP server on `0.0.0.0:8089` with zero authentication |
| M-02 | CRITICAL | Code Injection | TTS handler builds Python source from user text |
| M-03 | CRITICAL | File Upload | Unrestricted file upload — no type/size validation |
| M-04 | HIGH | File Exfil | `send_file` command walks `~/` and copies any matching file |
| M-05 | HIGH | Info Disclosure | `/search_files` returns full paths across home directories |
| M-06 | HIGH | Dir Listing | `/browse` exposes `~/Incoming`, `~/Downloads`, `~/vaults` |
| M-07 | HIGH | Prompt Injection | AI-generated commands execute server-side actions |
| M-08 | HIGH | CORS | `Access-Control-Allow-Origin: *` on all endpoints |
| M-09 | MEDIUM | No TLS | All traffic in cleartext HTTP |
| M-10 | MEDIUM | Hardcoded Infra | VPS/Tailscale IPs as source-code placeholders |
| M-11 | MEDIUM | No CSRF | POST endpoints lack CSRF protection |
| M-12 | MEDIUM | No Rate Limit | AI chat and TTS endpoints unlimited |
| M-13 | MEDIUM | Log Injection | `/api/cmd_report` writes arbitrary JSON to log |
| M-14 | MEDIUM | Info Disclosure | `/diagnose` exposes Ollama models, PIDs, disk, configs |
| M-15 | LOW | No Integrity | APK self-update serves unsigned APKs |
| M-16 | LOW | SSRF | Ollama proxy URL could be redirected via env var |
| M-17 | INFO | Leakage | Health endpoint exposes Tailscale IP and version |

### Whim.V (`whim_v.py`)

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| V-01 | CRITICAL | No Auth | Flask server on `0.0.0.0:8099` with no authentication |
| V-02 | CRITICAL | Path Traversal | `/api/docs/view` serves any file on disk |
| V-03 | CRITICAL | Command Injection | LibreOffice converts attacker-controlled file paths |
| V-04 | HIGH | Dir Listing | `/api/docs/list` exposes entire `~/` directory |
| V-05 | HIGH | No Rate Limit | AI chat endpoint unlimited |
| V-06 | HIGH | Input Validation | User-controlled model name passed to Ollama |
| V-07 | HIGH | No TLS | All traffic in cleartext |
| V-08 | MEDIUM | No CSRF | POST endpoints lack CSRF protection |
| V-09 | MEDIUM | Info Disclosure | `/api/logs` exposes Tailscale peers, Ollama models |
| V-10 | MEDIUM | Error Leakage | Raw exceptions yielded to client |
| V-11 | MEDIUM | Temp Files | Document conversion temp dirs never cleaned up |
| V-12 | MEDIUM | XSS | Filenames inserted into HTML without escaping |
| V-13 | LOW | SSRF | Ollama URL from env var could be redirected |
| V-14 | LOW | Debug Mode | `debug=False` is correct (informational) |
| V-15 | INFO | Hardcoded Paths | Config paths reveal application structure |

### Supporting Files

| # | Severity | File | Category | Description |
|---|----------|------|----------|-------------|
| S-01 | CRITICAL | whim_sync.py | No Auth + File Write | Unauthenticated WebSocket sync allows arbitrary file write |
| S-02 | CRITICAL | whim_sync.py | Path Traversal | Sync file paths not validated against directory allowlist |
| S-03 | HIGH | whim_sync.py | shell=True | Some subprocess calls use `shell=True` |
| S-04 | HIGH | whim_sync.py | No Auth Mirror | Unauthenticated mirror mode replicates all state |
| S-05 | HIGH | whim_sync.py | SSH MITM | SSH tunnel setup without host key verification |
| S-06 | HIGH | whim_sync.py | Destructive Rsync | `rsync --delete` can wipe target directories |
| S-07 | HIGH | .gitignore | Missing Entries | No exclusions for `.env`, SSH keys, sync state files |
| S-08 | MEDIUM | whim_adb_portal.py | Command Args | ADB commands with string-formatted device input |
| S-09 | MEDIUM | control_panel.py | Subprocess | Multiple subprocess calls without full input validation |
| S-10 | MEDIUM | lora_bridge.py | Serial Input | LoRa serial data parsed without full validation |
| S-11 | MEDIUM | control_panel.py | No Auth | Control panel HTTP endpoints without authentication |
| S-12 | MEDIUM | platform_compat.py | Subprocess | `subprocess.run` with user-influenced paths |
| S-13 | MEDIUM | whim_adb_portal.py | Info Disclosure | ADB device info exposed without auth |
| S-14 | LOW | config/openclaw.example.json | Placeholder Creds | Template has placeholder fields for API keys |
| S-15 | LOW | lora_bridge.py | No Encryption | LoRa communication in cleartext |
| S-16 | LOW | control_panel.py | Logging | Debug output may contain sensitive device info |
| S-17 | LOW | whim_sync.py | Error Handling | Broad exception catches mask errors |
| S-18 | LOW | device_locations.example.json | GPS Exposure | Template shows GPS coordinate format |
| S-19 | INFO | .gitignore | Good Coverage | Excludes model weights, user data, audio, APKs |
| S-20 | INFO | platform_compat.py | Safe Pattern | Uses list-form subprocess (positive) |
| S-21 | INFO | config/ | Templates | Example configs use placeholder values (correct) |
| S-22 | INFO | lora_bridge.py | Architecture | Runs as managed subprocess (safe isolation) |
| S-23 | INFO | .gitignore | Gap | Missing `.env`, `*.pem`, `*.key`, `id_rsa*`, `sync_state.json` |

---

## Recommended .gitignore Additions

```
# Security-sensitive files missing from current .gitignore
.env
.env.*
*.pem
*.key
*.crt
id_rsa*
authorized_keys
sync_state.json
whim_v.keystore
```

---

## Hardening Priority Order

1. **Add authentication** to all HTTP/WebSocket servers (token, Basic Auth, or mTLS)
2. **Validate file paths** — use `os.path.realpath()` + `startswith()` checks in all file-serving endpoints
3. **Remove eval()/exec()** — sandbox code execution in isolated subprocesses
4. **Restrict CORS** — replace `*` with specific allowed origins
5. **Add TLS** — reverse proxy (nginx/caddy) or `ssl_context` for all servers
6. **Sanitize subprocess args** — use `shlex.quote()`, never `shell=True` with user input
7. **Add rate limiting** — protect AI chat and TTS endpoints from abuse
8. **Validate uploads** — allowlist file extensions, enforce size limits
9. **Fix .gitignore** — add `.env`, `*.pem`, `*.key`, SSH keys, sync state
10. **Sandbox LibreOffice** — run conversions in firejail/Docker with `--norestore --nolockcheck`

---

## Disclaimer

This audit was performed via static analysis by Claude Opus 4.6. It identifies code-level vulnerabilities but does not include:
- Dynamic/runtime testing
- Penetration testing against live instances
- Binary analysis or memory safety review
- Third-party dependency vulnerability scanning (e.g., CVEs in Flask, Ollama, LibreOffice)

For a production deployment, a professional penetration test is recommended.

---

*This report is published as part of Whim's open-source transparency commitment. Every user deserves to know exactly what risks exist in the software they run.*
