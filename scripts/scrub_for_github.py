#!/usr/bin/env python3
"""
Scrub personal API keys, IP addresses, file paths, GPS coordinates,
phone numbers, and local history from the Whim project tree before
GitHub upload.

Creates a clean copy under ~/vaults/WHIM_GITHUB_CLEAN/ — never touches
the original files.

Usage:
    python3 ~/vaults/WHIM/scripts/scrub_for_github.py
    python3 ~/vaults/WHIM/scripts/scrub_for_github.py --dry-run   # preview only
"""

import argparse
import json
import os
import re
import shutil
import sys

SRC_ROOT = os.path.expanduser("~/vaults/WHIM")
DST_ROOT = os.path.expanduser("~/vaults/WHIM_GITHUB_CLEAN")

COPY_DIRS = ["app", "mobile", "scripts", "config", "assets", "theme", "docs"]
SKIP_DIRS = {".venv", "__pycache__", "node_modules", ".git", "backups"}
SKIP_EXTS = {".apk", ".idsig", ".keystore", ".pyc", ".pyo", ".dex",
             ".class", ".jar", ".aar",
             ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
             ".mp3", ".wav", ".ogg", ".webm", ".m4a", ".flac",
             ".mp4", ".mkv", ".avi", ".mov",
             ".pth", ".pt", ".gguf", ".bin", ".safetensors", ".onnx"}

# ── Text replacements (applied to .py, .json, .md, .txt, .html, .puml) ──

IP_REPLACEMENTS = {
    "YOUR_VPS_IP": "YOUR_VPS_IP",
    "YOUR_TAILSCALE_PC_IP":    "YOUR_TAILSCALE_PC_IP",
    "YOUR_TAILSCALE_PHONE1_IP":     "YOUR_TAILSCALE_PHONE1_IP",
    "YOUR_TAILSCALE_PHONE2_IP":     "YOUR_TAILSCALE_PHONE2_IP",
    "YOUR_TAILSCALE_TABLET_IP":  "YOUR_TAILSCALE_TABLET_IP",
    "YOUR_LAN_PC_IP":   "YOUR_LAN_PC_IP",
    "YOUR_LAN_PHONE1_IP":   "YOUR_LAN_PHONE1_IP",
    "YOUR_LAN_TABLET_IP":   "YOUR_LAN_TABLET_IP",
}

PHONE_NUMBER_RE = re.compile(r'\+1\d{10}')
GPS_COORD_RE = re.compile(
    r'"(lat|lon|alt_m)":\s*[-]?\d+\.\d+')
GPS_ACCURACY_RE = re.compile(
    r'"accuracy_m":\s*\d+\.?\d*')

SCRUB_PATTERNS = [
    # Discord bot token (72-char asterisked or real)
    (re.compile(r'("token":\s*")[^"]{20,}(")', re.I),
     r'\1REDACTED\2'),
    # Gateway auth token
    (re.compile(r'("token":\s*")[*]{10,}(")', re.I),
     r'\1REDACTED\2'),
    # Signal phone number
    (re.compile(r'("account":\s*")\+\d{11}(")', re.I),
     r'\1+10000000000\2'),
    # OpenAI key pattern
    (re.compile(r'(sk-[a-zA-Z0-9]{20,})'),
     'REDACTED_OPENAI_KEY'),
    # SmartThings PAT
    (re.compile(r'(smartthings.*?["\']\s*:\s*["\'])[a-f0-9-]{36}(["\'])', re.I),
     r'\1REDACTED\2'),
    # Notion token
    (re.compile(r'(secret_[a-zA-Z0-9]{20,})'),
     'REDACTED_NOTION_TOKEN'),
    # Generic long hex/base64 tokens in JSON (40+ chars)
    (re.compile(r'("(?:api_?key|apiKey|token|secret|password)":\s*")[a-zA-Z0-9+/=_-]{40,}(")', re.I),
     r'\1REDACTED\2'),
]

# Sandbox path hash
SANDBOX_RE = re.compile(r'agent-main-[a-f0-9]+')

# Locality / place names in JSON
LOCALITY_RE = re.compile(
    r'"locality":\s*"[^"]*"')
DESCRIPTION_GPS_RE = re.compile(
    r'"description":\s*"[^"]*location[^"]*"', re.I)
NOTE_GPS_RE = re.compile(
    r'"note":\s*"[^"]*GPS[^"]*"', re.I)

TEXTFILE_EXTS = {".py", ".json", ".md", ".txt", ".html", ".puml", ".csv",
                 ".sh", ".cfg", ".conf", ".yaml", ".yml", ".toml"}


def should_copy(rel_path):
    parts = rel_path.split(os.sep)
    for p in parts:
        if p in SKIP_DIRS:
            return False
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in SKIP_EXTS:
        return False
    return True


def scrub_text(content, filename=""):
    out = content

    # IP addresses
    for ip, placeholder in IP_REPLACEMENTS.items():
        out = out.replace(ip, placeholder)

    # Phone numbers
    out = PHONE_NUMBER_RE.sub("+10000000000", out)

    # GPS coordinates → zeroed
    out = GPS_COORD_RE.sub(lambda m: f'"{m.group(1)}": 0.0', out)
    out = GPS_ACCURACY_RE.sub('"accuracy_m": 0', out)

    # Locality strings
    out = LOCALITY_RE.sub('"locality": "REDACTED"', out)
    out = DESCRIPTION_GPS_RE.sub('"description": "REDACTED"', out)
    out = NOTE_GPS_RE.sub('"note": "REDACTED"', out)

    # Sandbox hashes
    out = SANDBOX_RE.sub("agent-main-XXXXXXXX", out)

    # Token / key patterns
    for pat, repl in SCRUB_PATTERNS:
        out = pat.sub(repl, out)

    return out


def scrub_json_file(src, dst):
    """Deeper scrub for JSON config files."""
    with open(src, "r") as f:
        raw = f.read()

    raw = scrub_text(raw, os.path.basename(src))

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        with open(dst, "w") as f:
            f.write(raw)
        return

    def walk(obj):
        if isinstance(obj, dict):
            for k in list(obj.keys()):
                kl = k.lower()
                if any(s in kl for s in ("token", "secret", "password",
                                          "api_key", "apikey")):
                    if isinstance(obj[k], str) and len(obj[k]) > 4:
                        obj[k] = "REDACTED"
                elif kl in ("lat", "lon", "alt_m"):
                    obj[k] = 0.0
                elif kl == "accuracy_m":
                    obj[k] = 0
                elif kl == "locality":
                    obj[k] = "REDACTED"
                elif kl == "account" and isinstance(obj[k], str) and obj[k].startswith("+"):
                    obj[k] = "+10000000000"
                else:
                    walk(obj[k])
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    with open(dst, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def process_tree(dry_run=False):
    if os.path.exists(DST_ROOT) and not dry_run:
        shutil.rmtree(DST_ROOT)

    copied = 0
    scrubbed = 0
    skipped = 0

    for subdir in COPY_DIRS:
        src_dir = os.path.join(SRC_ROOT, subdir)
        if not os.path.isdir(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                src_path = os.path.join(root, fname)
                rel = os.path.relpath(src_path, SRC_ROOT)

                if not should_copy(rel):
                    skipped += 1
                    continue

                dst_path = os.path.join(DST_ROOT, rel)
                ext = os.path.splitext(fname)[1].lower()

                if dry_run:
                    tag = "SCRUB" if ext in TEXTFILE_EXTS else "COPY"
                    print(f"  [{tag}] {rel}")
                    copied += 1
                    continue

                os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                if ext == ".json":
                    scrub_json_file(src_path, dst_path)
                    scrubbed += 1
                elif ext in TEXTFILE_EXTS:
                    with open(src_path, "r", errors="replace") as f:
                        content = f.read()
                    clean = scrub_text(content, fname)
                    with open(dst_path, "w") as f:
                        f.write(clean)
                    scrubbed += 1
                else:
                    shutil.copy2(src_path, dst_path)

                copied += 1

    # Copy .gitignore template to root
    if not dry_run:
        gi_src = os.path.join(SRC_ROOT, "scripts", "gitignore_template")
        gi_dst = os.path.join(DST_ROOT, ".gitignore")
        if os.path.isfile(gi_src):
            shutil.copy2(gi_src, gi_dst)

        # Create config templates (scrubbed versions with example values)
        tpl_dir = os.path.join(DST_ROOT, "config")
        os.makedirs(tpl_dir, exist_ok=True)

        openclaw_tpl = {
            "models": {
                "mode": "merge",
                "providers": {
                    "ollama": {
                        "baseUrl": "http://127.0.0.1:11434",
                        "api": "ollama"
                    }
                }
            },
            "agents": {
                "defaults": {
                    "model": {
                        "primary": "ollama/llama3.1:8b-16k",
                        "fallbacks": []
                    }
                }
            },
            "channels": {
                "signal": {
                    "enabled": False,
                    "account": "",
                    "httpUrl": "http://127.0.0.1:8080"
                },
                "discord": {
                    "enabled": False,
                    "token": ""
                }
            },
            "gateway": {
                "mode": "local",
                "auth": {"mode": "token", "token": ""}
            }
        }
        with open(os.path.join(tpl_dir, "openclaw.example.json"), "w") as f:
            json.dump(openclaw_tpl, f, indent=2)
            f.write("\n")

        devices_tpl = {
            "devices": [
                {"name": "PC", "tailscale_ip": "", "lan_ip": ""},
                {"name": "Phone", "tailscale_ip": "", "lan_ip": ""}
            ]
        }
        with open(os.path.join(tpl_dir, "device_locations.example.json"), "w") as f:
            json.dump(devices_tpl, f, indent=2)
            f.write("\n")

    return copied, scrubbed, skipped


def verify(dst_root):
    """Post-scrub verification: scan output for anything that looks leaked."""
    issues = []
    dangerous = [
        re.compile(r'104\.207\.\d+\.\d+'),
        re.compile(r'100\.(69|97|77|64)\.\d+\.\d+'),
        re.compile(r'192\.168\.1\.\d+'),
        re.compile(r'\+1\d{10}'),
        re.compile(r'sk-[a-zA-Z0-9]{20,}'),
        re.compile(r'secret_[a-zA-Z0-9]{20,}'),
        re.compile(r'agent-main-[a-f0-9]{8,}'),
    ]
    for root, dirs, files in os.walk(dst_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = os.path.join(root, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext not in TEXTFILE_EXTS:
                continue
            try:
                with open(fpath, "r", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        for pat in dangerous:
                            m = pat.search(line)
                            if m:
                                rel = os.path.relpath(fpath, dst_root)
                                issues.append((rel, lineno, m.group()))
            except Exception:
                pass
    return issues


def main():
    parser = argparse.ArgumentParser(description="Scrub WHIM project for GitHub")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be copied/scrubbed without writing")
    args = parser.parse_args()

    print(f"Source : {SRC_ROOT}")
    print(f"Output : {DST_ROOT}")
    print()

    if args.dry_run:
        print("=== DRY RUN — no files will be written ===\n")

    copied, scrubbed, skipped = process_tree(dry_run=args.dry_run)

    print(f"\n{'Would copy' if args.dry_run else 'Copied'}: {copied} files")
    print(f"{'Would scrub' if args.dry_run else 'Scrubbed'}: {scrubbed} text files")
    print(f"Skipped (binary/cache): {skipped}")

    if not args.dry_run:
        print("\nRunning post-scrub verification...")
        issues = verify(DST_ROOT)
        if issues:
            print(f"\n  WARNING: {len(issues)} potential leak(s) found:")
            for rel, lineno, match in issues[:20]:
                print(f"    {rel}:{lineno}  ->  {match}")
            print("\n  Review these before uploading to GitHub.")
        else:
            print("  CLEAN — no personal data patterns detected.")

        print(f"\nClean tree ready at: {DST_ROOT}")
    else:
        print("\nRe-run without --dry-run to create the clean copy.")


if __name__ == "__main__":
    main()
