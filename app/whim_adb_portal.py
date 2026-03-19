#!/usr/bin/env python3
"""
Whim ADB Portal — Desktop GUI for managing APK installs and Android emulators.
Matches Whim dark theme. Wraps ADB for push/install of APKs to Samsung devices.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    Image = ImageDraw = ImageTk = None

# ==================== PATHS ====================
WHIM_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOBILE_DIR = os.path.join(WHIM_ROOT, "mobile")
ASSETS_DIR = os.path.join(WHIM_ROOT, "assets")
ANDROID_SDK_ROOT = os.path.expanduser("~/Android/Sdk")
CMDLINE_TOOLS_DIR = os.path.join(ANDROID_SDK_ROOT, "cmdline-tools", "latest")
EMULATOR_BIN = os.path.join(ANDROID_SDK_ROOT, "emulator", "emulator")
AVD_MANAGER = os.path.join(CMDLINE_TOOLS_DIR, "bin", "avdmanager")
SDK_MANAGER = os.path.join(CMDLINE_TOOLS_DIR, "bin", "sdkmanager")
WHIM_ICON_PATH = os.path.expanduser("~/.openclaw/Whim.png")
PORTAL_ICON_PATH = os.path.join(ASSETS_DIR, "portal.png")
FIREHOOP_ICON_PATH = os.path.join(ASSETS_DIR, "firehoop.png")

# ==================== DARK THEME ====================
TH = {
    "bg":        "#2b2b2b",
    "card":      "#333333",
    "input":     "#1e1e1e",
    "border":    "#3a3a3a",
    "btn":       "#14507a",
    "btn_hover": "#0f3d5e",
    "fg":        "#dce4ee",
    "fg2":       "#888888",
    "fg_dim":    "#666666",
    "green":     "#2fa572",
    "red":       "#d94040",
    "yellow":    "#e0a030",
    "font":      ("Segoe UI", 10),
    "font_sm":   ("Segoe UI", 9),
    "font_xs":   ("Consolas", 8),
    "font_mono": ("Consolas", 9),
    "font_title": ("Segoe UI", 11, "bold"),
    "font_hero": ("Segoe UI", 18, "bold"),
}

# ==================== EMULATOR PROFILES ====================
DEVICE_PROFILES = {
    "Samsung Galaxy S9": {
        "avd_name": "Samsung_Galaxy_S9",
        "skin_w": 1440, "skin_h": 2960, "dpi": 570,
        "ram": 4096, "api": 30,
        "system_image": "system-images;android-30;google_apis;x86_64",
        "device_def": "pixel_4",  # closest AVD match
    },
    "Samsung Galaxy S22": {
        "avd_name": "Samsung_Galaxy_S22",
        "skin_w": 1080, "skin_h": 2340, "dpi": 425,
        "ram": 8192, "api": 33,
        "system_image": "system-images;android-33;google_apis;x86_64",
        "device_def": "pixel_6",
    },
}


def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def adb_devices():
    code, out, _ = _run(["adb", "devices", "-l"])
    if code != 0:
        return []
    devices = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line or "offline" in line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            state = parts[1]
            model = ""
            for p in parts[2:]:
                if p.startswith("model:"):
                    model = p.split(":", 1)[1]
            devices.append({"serial": serial, "state": state, "model": model})
    return devices


def _disable_verification(serial):
    _run(["adb", "-s", serial, "shell", "settings", "put", "global",
          "verifier_verify_adb_installs", "0"], timeout=10)
    _run(["adb", "-s", serial, "shell", "settings", "put", "global",
          "package_verifier_enable", "0"], timeout=10)


def adb_install(serial, apk_path, callback=None):
    def _worker():
        msg = f"Installing {os.path.basename(apk_path)} on {serial}..."
        if callback:
            callback("progress", msg)
        _disable_verification(serial)
        code, out, err = _run(
            ["adb", "-s", serial, "install", "-r", "-g", apk_path], timeout=120)
        if code == 0 and "Success" in out:
            if callback:
                callback("success", f"Installed {os.path.basename(apk_path)} on {serial}")
        else:
            detail = err or out
            if callback:
                callback("error", f"Install failed: {detail}")
    threading.Thread(target=_worker, daemon=True).start()


def adb_push(serial, local_path, remote_path, callback=None):
    def _worker():
        if callback:
            callback("progress", f"Pushing {os.path.basename(local_path)}...")
        code, out, err = _run(
            ["adb", "-s", serial, "push", local_path, remote_path], timeout=120)
        if code == 0:
            if callback:
                callback("success", f"Pushed to {remote_path}")
        else:
            if callback:
                callback("error", f"Push failed: {err or out}")
    threading.Thread(target=_worker, daemon=True).start()


def _find_whim_apks():
    apks = []
    for root_dir in [MOBILE_DIR, WHIM_ROOT, os.path.expanduser("~")]:
        if not os.path.isdir(root_dir):
            continue
        for fn in os.listdir(root_dir):
            if fn.endswith(".apk") and "whim" in fn.lower():
                fp = os.path.join(root_dir, fn)
                apks.append(fp)
    seen = set()
    unique = []
    for a in apks:
        real = os.path.realpath(a)
        if real not in seen:
            seen.add(real)
            unique.append(a)
    return sorted(unique)


class WhimADBPortal(tk.Tk):
    def __init__(self):
        super().__init__(className='Whim_adb_portal')
        self.title("Whim ADB Portal")
        self.geometry("780x820")
        self.configure(bg=TH["bg"])
        self.resizable(True, True)

        self._set_icon()

        self.devices = []
        self.apk_list = _find_whim_apks()

        self._build_ui()
        self._refresh_devices()

    def _set_icon(self):
        icon_path = PORTAL_ICON_PATH if os.path.isfile(PORTAL_ICON_PATH) else WHIM_ICON_PATH
        if Image and os.path.isfile(icon_path):
            try:
                img = Image.open(icon_path).convert("RGBA").resize((64, 64), Image.LANCZOS)
                self._icon_img = ImageTk.PhotoImage(img)
                self.iconphoto(False, self._icon_img)
            except Exception:
                pass

    def _build_ui(self):
        main = tk.Frame(self, bg=TH["bg"])
        main.pack(fill="both", expand=True, padx=16, pady=12)

        # Header
        hdr = tk.Frame(main, bg=TH["bg"])
        hdr.pack(fill="x", pady=(0, 12))
        self._header_icon_img = None
        if Image and os.path.isfile(PORTAL_ICON_PATH):
            try:
                hdr_img = Image.open(PORTAL_ICON_PATH).convert("RGBA").resize((32, 32), Image.LANCZOS)
                self._header_icon_img = ImageTk.PhotoImage(hdr_img)
                tk.Label(hdr, image=self._header_icon_img, bg=TH["bg"]).pack(side="left", padx=(0, 8))
            except Exception:
                pass
        tk.Label(hdr, text="Whim ADB Portal", font=TH["font_hero"],
                 fg="#00ff00", bg=TH["bg"]).pack(side="left")
        tk.Label(hdr, text="push / install / emulate",
                 font=TH["font_sm"], fg=TH["fg_dim"], bg=TH["bg"]).pack(side="left", padx=(12, 0))

        # ========== DEVICES SECTION ==========
        self._section_label(main, "CONNECTED DEVICES")
        dev_frame = tk.Frame(main, bg=TH["card"], highlightbackground=TH["border"],
                             highlightthickness=1)
        dev_frame.pack(fill="x", pady=(0, 12))

        ctrl = tk.Frame(dev_frame, bg=TH["card"])
        ctrl.pack(fill="x", padx=8, pady=6)
        self.btn_refresh = self._mk_btn(ctrl, "Refresh", self._refresh_devices)
        self.btn_refresh.pack(side="left")
        self.device_status = tk.Label(ctrl, text="scanning...", font=TH["font_xs"],
                                      fg=TH["fg2"], bg=TH["card"])
        self.device_status.pack(side="left", padx=8)

        self.device_listbox = tk.Listbox(
            dev_frame, height=4, bg=TH["input"], fg=TH["fg"],
            selectbackground=TH["btn"], selectforeground=TH["fg"],
            font=TH["font_mono"], borderwidth=0, highlightthickness=0,
            activestyle="none")
        self.device_listbox.pack(fill="x", padx=8, pady=(0, 8))

        # ========== APK SECTION ==========
        self._section_label(main, "WHIM APKs")
        apk_frame = tk.Frame(main, bg=TH["card"], highlightbackground=TH["border"],
                             highlightthickness=1)
        apk_frame.pack(fill="x", pady=(0, 12))

        self.apk_listbox = tk.Listbox(
            apk_frame, height=5, bg=TH["input"], fg=TH["fg"],
            selectbackground=TH["btn"], selectforeground=TH["fg"],
            font=TH["font_mono"], borderwidth=0, highlightthickness=0,
            activestyle="none")
        self.apk_listbox.pack(fill="x", padx=8, pady=8)
        self._populate_apk_list()

        btn_row = tk.Frame(apk_frame, bg=TH["card"])
        btn_row.pack(fill="x", padx=8, pady=(0, 8))
        self._mk_btn(btn_row, "Add APK...", self._add_apk).pack(side="left")
        self._mk_btn(btn_row, "Install to Device", self._install_selected,
                     bg=TH["green"]).pack(side="left", padx=6)
        self._mk_btn(btn_row, "Force Reinstall", self._force_reinstall,
                     bg=TH["yellow"]).pack(side="left")

        # ========== QUICK ACTIONS ==========
        self._section_label(main, "QUICK ACTIONS")
        qa_frame = tk.Frame(main, bg=TH["card"], highlightbackground=TH["border"],
                            highlightthickness=1)
        qa_frame.pack(fill="x", pady=(0, 12))
        qa_inner = tk.Frame(qa_frame, bg=TH["card"])
        qa_inner.pack(fill="x", padx=8, pady=8)

        self._mk_btn(qa_inner, "Install ALL Whim APKs", self._install_all,
                     bg=TH["green"]).pack(side="left")
        self._mk_btn(qa_inner, "Uninstall Whim", self._uninstall_whim,
                     bg=TH["red"]).pack(side="left", padx=6)
        self._mk_btn(qa_inner, "Open ADB Shell", self._adb_shell).pack(side="left")
        self._mk_btn(qa_inner, "Take Screenshot", self._take_screenshot).pack(side="left", padx=6)

        # ========== EMULATOR SECTION ==========
        self._section_label(main, "ANDROID EMULATOR")
        emu_frame = tk.Frame(main, bg=TH["card"], highlightbackground=TH["border"],
                             highlightthickness=1)
        emu_frame.pack(fill="x", pady=(0, 12))

        emu_top = tk.Frame(emu_frame, bg=TH["card"])
        emu_top.pack(fill="x", padx=8, pady=8)

        tk.Label(emu_top, text="Profile:", font=TH["font_sm"],
                 fg=TH["fg2"], bg=TH["card"]).pack(side="left")
        self.emu_profile = tk.StringVar(value=list(DEVICE_PROFILES.keys())[0])
        self.emu_combo = ttk.Combobox(emu_top, textvariable=self.emu_profile,
                                      values=list(DEVICE_PROFILES.keys()),
                                      state="readonly", width=25)
        self.emu_combo.pack(side="left", padx=6)

        emu_btns = tk.Frame(emu_frame, bg=TH["card"])
        emu_btns.pack(fill="x", padx=8, pady=(0, 8))

        self.btn_setup_sdk = self._mk_btn(emu_btns, "Setup Android SDK", self._setup_sdk)
        self.btn_setup_sdk.pack(side="left")
        self._mk_btn(emu_btns, "Create AVD", self._create_avd).pack(side="left", padx=6)
        self._mk_btn(emu_btns, "Launch Emulator", self._launch_emulator,
                     bg=TH["green"]).pack(side="left")
        self._mk_btn(emu_btns, "List AVDs", self._list_avds).pack(side="left", padx=6)

        self.emu_status = tk.Label(emu_frame, text="", font=TH["font_xs"],
                                   fg=TH["fg2"], bg=TH["card"], wraplength=700, justify="left")
        self.emu_status.pack(fill="x", padx=8, pady=(0, 8))

        self._check_sdk_status()

        # ========== LOG SECTION ==========
        self._section_label(main, "LOG")
        log_frame = tk.Frame(main, bg=TH["card"], highlightbackground=TH["border"],
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame, height=8, bg=TH["input"], fg=TH["fg"],
            font=TH["font_mono"], borderwidth=0, highlightthickness=0,
            insertbackground=TH["fg"], state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        self.log_text.tag_configure("ok", foreground=TH["green"])
        self.log_text.tag_configure("err", foreground=TH["red"])
        self.log_text.tag_configure("warn", foreground=TH["yellow"])
        self.log_text.tag_configure("info", foreground=TH["fg2"])

        self._log("info", "Whim ADB Portal ready.")

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, font=TH["font_xs"], fg=TH["fg_dim"],
                 bg=TH["bg"], anchor="w").pack(fill="x", pady=(4, 2))

    def _mk_btn(self, parent, text, command, bg=None):
        bg = bg or TH["btn"]
        btn = tk.Label(parent, text=text, font=TH["font_sm"], fg=TH["fg"],
                       bg=bg, padx=12, pady=4, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.configure(bg=TH["btn_hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    def _log(self, tag, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] ", "info")
        self.log_text.insert("end", msg + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _adb_callback(self, level, msg):
        tag_map = {"success": "ok", "error": "err", "progress": "warn"}
        self.after(0, lambda: self._log(tag_map.get(level, "info"), msg))

    # ========== DEVICE MANAGEMENT ==========
    def _refresh_devices(self):
        def _worker():
            devs = adb_devices()
            self.after(0, lambda: self._update_device_list(devs))
        self.device_status.configure(text="scanning...")
        threading.Thread(target=_worker, daemon=True).start()

    def _update_device_list(self, devs):
        self.devices = devs
        self.device_listbox.delete(0, "end")
        for d in devs:
            label = f"{d['serial']}  [{d['state']}]"
            if d["model"]:
                label += f"  {d['model']}"
            self.device_listbox.insert("end", label)
        count = len(devs)
        self.device_status.configure(
            text=f"{count} device{'s' if count != 1 else ''} connected"
            if count else "No devices found — enable USB debugging & connect")
        if count:
            self._log("ok", f"Found {count} device(s)")
        else:
            self._log("warn", "No ADB devices found")

    def _get_selected_device(self):
        sel = self.device_listbox.curselection()
        if not sel:
            if self.devices:
                return self.devices[0]["serial"]
            self._log("err", "No device selected or connected")
            return None
        return self.devices[sel[0]]["serial"]

    # ========== APK MANAGEMENT ==========
    def _populate_apk_list(self):
        self.apk_listbox.delete(0, "end")
        for apk in self.apk_list:
            sz = os.path.getsize(apk)
            label = f"{os.path.basename(apk)}  ({sz / 1024:.0f} KB)  — {os.path.dirname(apk)}"
            self.apk_listbox.insert("end", label)

    def _add_apk(self):
        path = filedialog.askopenfilename(
            title="Select APK",
            filetypes=[("Android APK", "*.apk"), ("All files", "*.*")],
            initialdir=MOBILE_DIR)
        if path and path not in self.apk_list:
            self.apk_list.append(path)
            self._populate_apk_list()
            self._log("ok", f"Added: {os.path.basename(path)}")

    def _get_selected_apk(self):
        sel = self.apk_listbox.curselection()
        if not sel:
            self._log("err", "No APK selected")
            return None
        return self.apk_list[sel[0]]

    def _install_selected(self):
        serial = self._get_selected_device()
        apk = self._get_selected_apk()
        if serial and apk:
            adb_install(serial, apk, self._adb_callback)

    def _force_reinstall(self):
        serial = self._get_selected_device()
        apk = self._get_selected_apk()
        if not serial or not apk:
            return

        def _worker():
            self._adb_callback("progress", f"Force reinstalling {os.path.basename(apk)}...")
            _run(["adb", "-s", serial, "uninstall", "com.whim.m"], timeout=30)
            code, out, err = _run(
                ["adb", "-s", serial, "install", "-r", "-g", "-d", apk], timeout=120)
            if code == 0 and "Success" in out:
                self._adb_callback("success", f"Force reinstalled {os.path.basename(apk)}")
            else:
                self._adb_callback("error", f"Failed: {err or out}")
        threading.Thread(target=_worker, daemon=True).start()

    def _install_all(self):
        serial = self._get_selected_device()
        if not serial:
            return
        for apk in self.apk_list:
            adb_install(serial, apk, self._adb_callback)

    def _uninstall_whim(self):
        serial = self._get_selected_device()
        if not serial:
            return

        def _worker():
            self._adb_callback("progress", "Uninstalling com.whim.m...")
            code, out, err = _run(
                ["adb", "-s", serial, "uninstall", "com.whim.m"], timeout=30)
            if code == 0:
                self._adb_callback("success", "Uninstalled com.whim.m")
            else:
                self._adb_callback("error", f"Uninstall: {err or out}")
        threading.Thread(target=_worker, daemon=True).start()

    def _adb_shell(self):
        serial = self._get_selected_device()
        if not serial:
            return
        try:
            subprocess.Popen(
                ["x-terminal-emulator", "-e", f"adb -s {serial} shell"],
                start_new_session=True)
            self._log("ok", f"Opened ADB shell for {serial}")
        except Exception:
            try:
                subprocess.Popen(
                    ["gnome-terminal", "--", "adb", "-s", serial, "shell"],
                    start_new_session=True)
                self._log("ok", f"Opened ADB shell for {serial}")
            except Exception as e:
                self._log("err", f"Cannot open terminal: {e}")

    def _take_screenshot(self):
        serial = self._get_selected_device()
        if not serial:
            return

        def _worker():
            self._adb_callback("progress", "Capturing screenshot...")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            remote = "/sdcard/whim_screenshot.png"
            local = os.path.expanduser(f"~/Pictures/whim_screenshot_{ts}.png")
            code1, _, err1 = _run(
                ["adb", "-s", serial, "shell", "screencap", "-p", remote], timeout=15)
            if code1 != 0:
                self._adb_callback("error", f"screencap failed: {err1}")
                return
            code2, _, err2 = _run(
                ["adb", "-s", serial, "pull", remote, local], timeout=15)
            if code2 == 0:
                self._adb_callback("success", f"Screenshot saved: {local}")
            else:
                self._adb_callback("error", f"pull failed: {err2}")
        threading.Thread(target=_worker, daemon=True).start()

    # ========== EMULATOR MANAGEMENT ==========
    def _check_sdk_status(self):
        if os.path.isfile(EMULATOR_BIN):
            self.emu_status.configure(text="Android SDK found. Emulator ready.", fg=TH["green"])
        elif os.path.isdir(ANDROID_SDK_ROOT):
            self.emu_status.configure(
                text="SDK partially installed. Click 'Setup Android SDK' to complete.",
                fg=TH["yellow"])
        else:
            self.emu_status.configure(
                text="Android SDK not installed. Click 'Setup Android SDK' to download (~2 GB).",
                fg=TH["fg2"])

    def _setup_sdk(self):
        def _worker():
            self._adb_callback("progress", "Setting up Android SDK command-line tools...")
            os.makedirs(ANDROID_SDK_ROOT, exist_ok=True)
            cmdline_zip = os.path.join(ANDROID_SDK_ROOT, "cmdline-tools.zip")

            if not os.path.isdir(CMDLINE_TOOLS_DIR):
                self._adb_callback("progress", "Downloading Android command-line tools...")
                url = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
                code, _, err = _run(
                    ["wget", "-q", "-O", cmdline_zip, url], timeout=300)
                if code != 0:
                    self._adb_callback("error", f"Download failed: {err}")
                    return

                self._adb_callback("progress", "Extracting command-line tools...")
                extract_dir = os.path.join(ANDROID_SDK_ROOT, "cmdline-tools")
                os.makedirs(extract_dir, exist_ok=True)
                code, _, err = _run(
                    ["unzip", "-o", "-q", cmdline_zip, "-d", extract_dir], timeout=120)
                if code != 0:
                    self._adb_callback("error", f"Extract failed: {err}")
                    return

                src = os.path.join(extract_dir, "cmdline-tools")
                if os.path.isdir(src) and not os.path.isdir(CMDLINE_TOOLS_DIR):
                    os.rename(src, CMDLINE_TOOLS_DIR)

                if os.path.isfile(cmdline_zip):
                    os.remove(cmdline_zip)

            if not os.path.isfile(SDK_MANAGER):
                self._adb_callback("error", "sdkmanager not found after extraction")
                return

            self._adb_callback("progress", "Accepting licenses...")
            proc = subprocess.Popen(
                [SDK_MANAGER, "--licenses", f"--sdk_root={ANDROID_SDK_ROOT}"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
            out, err = proc.communicate(input="y\n" * 20, timeout=60)

            packages = [
                "platform-tools",
                "emulator",
                "platforms;android-33",
                "platforms;android-30",
            ]
            for pkg in packages:
                self._adb_callback("progress", f"Installing {pkg}...")
                code, out, err = _run(
                    [SDK_MANAGER, "--install", pkg, f"--sdk_root={ANDROID_SDK_ROOT}"],
                    timeout=600)
                if code != 0:
                    self._adb_callback("warn", f"Warning installing {pkg}: {err[:200]}")

            self._adb_callback("success", "Android SDK setup complete!")
            self.after(0, self._check_sdk_status)

        threading.Thread(target=_worker, daemon=True).start()

    def _create_avd(self):
        profile_name = self.emu_profile.get()
        profile = DEVICE_PROFILES.get(profile_name)
        if not profile:
            self._log("err", "Unknown profile")
            return

        def _worker():
            sysimg = profile["system_image"]
            self._adb_callback("progress", f"Downloading system image: {sysimg}...")
            code, _, err = _run(
                [SDK_MANAGER, "--install", sysimg, f"--sdk_root={ANDROID_SDK_ROOT}"],
                timeout=900)
            if code != 0:
                self._adb_callback("warn", f"System image: {err[:200]}")

            avd = profile["avd_name"]
            self._adb_callback("progress", f"Creating AVD: {avd}...")
            cmd = [
                AVD_MANAGER, "create", "avd",
                "-n", avd,
                "-k", sysimg,
                "-d", profile["device_def"],
                "--force",
            ]
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                env={**os.environ, "ANDROID_SDK_ROOT": ANDROID_SDK_ROOT})
            out, err = proc.communicate(input="no\n", timeout=60)

            if proc.returncode == 0 or "already exists" in (out + err).lower():
                avd_ini = os.path.expanduser(f"~/.android/avd/{avd}.avd/config.ini")
                if os.path.isfile(avd_ini):
                    with open(avd_ini, "a") as f:
                        f.write(f"\nhw.lcd.density={profile['dpi']}\n")
                        f.write(f"hw.lcd.width={profile['skin_w']}\n")
                        f.write(f"hw.lcd.height={profile['skin_h']}\n")
                        f.write(f"hw.ramSize={profile['ram']}\n")
                        f.write(f"hw.device.name={profile_name}\n")
                self._adb_callback("success",
                    f"AVD '{avd}' created ({profile_name}: {profile['skin_w']}x{profile['skin_h']} @ {profile['dpi']}dpi)")
            else:
                self._adb_callback("error", f"AVD creation failed: {err or out}")

        threading.Thread(target=_worker, daemon=True).start()

    def _launch_emulator(self):
        profile_name = self.emu_profile.get()
        profile = DEVICE_PROFILES.get(profile_name)
        if not profile:
            self._log("err", "Unknown profile")
            return

        avd = profile["avd_name"]
        if not os.path.isfile(EMULATOR_BIN):
            self._log("err", "Emulator not installed. Run 'Setup Android SDK' first.")
            return

        try:
            env = {**os.environ, "ANDROID_SDK_ROOT": ANDROID_SDK_ROOT}
            subprocess.Popen(
                [EMULATOR_BIN, "-avd", avd, "-gpu", "auto", "-no-snapshot-load"],
                start_new_session=True, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._log("ok", f"Emulator launching: {profile_name} ({avd})")
            self._log("info", "Device will appear in 'Connected Devices' once booted (30-60s)")
        except Exception as e:
            self._log("err", f"Failed to launch emulator: {e}")

    def _list_avds(self):
        if not os.path.isfile(AVD_MANAGER):
            self._log("warn", "avdmanager not found. Run 'Setup Android SDK' first.")
            return

        def _worker():
            code, out, err = _run(
                [AVD_MANAGER, "list", "avd", "-c"],
                timeout=15)
            if code == 0 and out.strip():
                for avd in out.strip().splitlines():
                    self._adb_callback("info", f"  AVD: {avd.strip()}")
            else:
                self._adb_callback("warn", "No AVDs found. Create one first.")
        threading.Thread(target=_worker, daemon=True).start()


def main():
    app = WhimADBPortal()
    app.mainloop()


if __name__ == "__main__":
    main()
