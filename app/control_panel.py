#!/usr/bin/env python3
"""
Unified Control Panel — Windows 2000-style settings hub for Linux Mint Cinnamon.
All system preferences, administration, and hardware tools in one tabbed window.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk
from datetime import datetime

AZURE_THEME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "theme", "Azure-ttk-theme")
if not os.path.isdir(AZURE_THEME_DIR):
    AZURE_THEME_DIR = os.path.expanduser("~/Azure-ttk-theme")

TH = {
    "bg":        "#2b2b2b",
    "card":      "#333333",
    "card_hover":"#3d3d3d",
    "input":     "#1e1e1e",
    "border":    "#3a3a3a",
    "accent":    "#14507a",
    "fg":        "#dce4ee",
    "fg2":       "#aaaaaa",
    "fg_dim":    "#666666",
    "green":     "#2fa572",
    "red":       "#d94040",
    "yellow":    "#e0a030",
    "font":      ("Segoe UI", 10),
    "font_sm":   ("Segoe UI", 9),
    "font_btn":  ("Segoe UI", 9),
    "font_title":("Segoe UI", 12, "bold"),
    "font_hero": ("Segoe UI", 16, "bold"),
    "font_mono": ("Consolas", 9),
    "font_tab":  ("Segoe UI", 10),
}

TABS = {
    "Display": [
        ("Display",            "cinnamon-settings display"),
        ("Backgrounds",        "cinnamon-settings backgrounds"),
        ("Themes",             "cinnamon-settings themes"),
        ("Fonts",              "cinnamon-settings fonts"),
        ("Effects",            "cinnamon-settings effects"),
        ("Night Light",        "cinnamon-settings nightlight"),
        ("Screensaver",        "cinnamon-settings screensaver"),
        ("Desktop",            "cinnamon-settings desktop"),
        ("NVIDIA Settings",    "nvidia-settings"),
        ("Color Profiles",     "cinnamon-settings color"),
    ],
    "Sound": [
        ("Sound",              "cinnamon-settings sound"),
    ],
    "Network": [
        ("Network",                "cinnamon-settings network"),
        ("Advanced Network",       "nm-connection-editor"),
        ("Bluetooth Manager",      "blueman-manager"),
        ("Bluetooth Adapters",     "blueman-adapters"),
        ("Firewall",               "gufw"),
        ("Online Accounts",        "gnome-online-accounts-gtk"),
    ],
    "Input": [
        ("Mouse & Touchpad",   "cinnamon-settings mouse"),
        ("Keyboard",           "cinnamon-settings keyboard"),
        ("Keyboard Layout",    "gkbd-keyboard-display"),
        ("Graphics Tablet",    "cinnamon-settings wacom"),
        ("Gestures",           "cinnamon-settings gestures"),
        ("Input Method",       "mintlocale-im"),
        ("IBus Preferences",   "ibus-setup"),
        ("Onboard Settings",   "onboard-settings"),
    ],
    "Hardware": [
        ("Printers",           "system-config-printer"),
        ("Power Management",   "cinnamon-settings power"),
        ("Power Statistics",   "gnome-power-statistics"),
        ("Disks",              "gnome-disks"),
        ("Disk Usage",         "baobab"),
        ("Thunderbolt",        "cinnamon-settings thunderbolt"),
        ("USB Image Writer",   "mintstick -m iso"),
        ("USB Formatter",      "mintstick -m format"),
        ("HP LaserJet Fix",    "/usr/share/foo2zjs/hplj10xx_gui.tcl"),
    ],
    "System": [
        ("System Monitor",     "gnome-system-monitor"),
        ("System Information", "mintreport"),
        ("Users & Groups",     "cinnamon-settings-users"),
        ("Account Details",    "cinnamon-settings user"),
        ("Fingerprints",       "fingwit"),
        ("Timeshift Backup",   "timeshift-launcher"),
        ("Login Window",       "pkexec lightdm-settings"),
        ("Startup Apps",       "cinnamon-settings startup"),
        ("Date & Time",        "cinnamon-settings calendar"),
        ("Languages",          "mintlocale"),
        ("Preferred Apps",     "cinnamon-settings default"),
        ("Accessibility",      "cinnamon-settings accessibility"),
        ("Terminal Prefs",     "gnome-terminal --preferences"),
    ],
    "Software": [
        ("Update Manager",     "mintupdate"),
        ("Software Manager",   "mintinstall"),
        ("Software Sources",   "pkexec mintsources"),
        ("Driver Manager",     "driver-manager"),
        ("Backup Tool",        "mintbackup"),
        ("System Admin",       "pkexec mintsysadm"),
        ("Package Installer",  "captain"),
        ("Web Apps",           "webapp-manager"),
    ],
    "Desktop": [
        ("Panel",              "cinnamon-settings panel"),
        ("Applets",            "cinnamon-settings applets"),
        ("Desklets",           "cinnamon-settings desklets"),
        ("Extensions",         "cinnamon-settings extensions"),
        ("Hot Corners",        "cinnamon-settings hotcorner"),
        ("Actions",            "cinnamon-settings actions"),
        ("Windows",            "cinnamon-settings windows"),
        ("Workspaces",         "cinnamon-settings workspaces"),
        ("Notifications",      "cinnamon-settings notifications"),
        ("General",            "cinnamon-settings general"),
        ("Menu Editor",        "cinnamon-menu-editor"),
    ],
    "Security": [
        ("Firewall",           "gufw"),
        ("Passwords & Keys",   "seahorse"),
        ("Privacy",            "cinnamon-settings privacy"),
    ],
    "Whim": [
        ("Start Whim.m",       "python3 ~/vaults/WHIM/mobile/whim_m_v2.1.py &"),
        ("Tailscale Status",   "tailscale status"),
        ("Tailscale Up",       "sudo tailscale up"),
        ("Tailscale Down",     "sudo tailscale down"),
        ("VPS Tunnel Check",   "curl -s --max-time 3 http://YOUR_VPS_IP:8089/health"),
        ("Open Whim (Browser)","xdg-open http://YOUR_TAILSCALE_PC_IP:8089"),
    ],
}

ICON_MAP = {
    "Display":             "\U0001F5B5",
    "Backgrounds":         "\U0001F5BC",
    "Themes":              "\U0001F3A8",
    "Fonts":               "\U0001F520",
    "Effects":             "\u2728",
    "Night Light":         "\U0001F319",
    "Screensaver":         "\U0001F4FA",
    "Desktop":             "\U0001F5A5",
    "NVIDIA Settings":     "\U0001F3AE",
    "Color Profiles":      None,
    "Sound":               "\U0001F50A",
    "Network":             "\U0001F310",
    "Advanced Network":    "\U0001F4E1",
    "Bluetooth Manager":   "\U0001F4F6",
    "Bluetooth Adapters":  "\U0001F4F6",
    "Firewall":            "\U0001F6E1",
    "Online Accounts":     "\U0001F465",
    "Mouse & Touchpad":    "\U0001F5B1",
    "Keyboard":            "\u2328",
    "Keyboard Layout":     "\u2328",
    "Graphics Tablet":     "\u270D",
    "Gestures":            "\U0001F44B",
    "Input Method":        "\U0001F4DD",
    "IBus Preferences":    "\U0001F4DD",
    "Onboard Settings":    "\u2328",
    "Printers":            "\U0001F5A8",
    "Power Management":    "\U0001F50B",
    "Power Statistics":    "\U0001F4CA",
    "Disks":               "\U0001F4BF",
    "Disk Usage":          "\U0001F4CA",
    "Thunderbolt":         "\u26A1",
    "USB Image Writer":    "\U0001F4BE",
    "USB Formatter":       "\U0001F4BE",
    "HP LaserJet Fix":     "\U0001F5A8",
    "System Monitor":      "\U0001F4BB",
    "System Information":  "\u2139",
    "Users & Groups":      "\U0001F465",
    "Account Details":     "\U0001F464",
    "Fingerprints":        "\U0001F91A",
    "Timeshift Backup":    "\u23F0",
    "Login Window":        "\U0001F510",
    "Startup Apps":        "\U0001F680",
    "Date & Time":         "\U0001F4C5",
    "Languages":           "\U0001F30D",
    "Preferred Apps":      "\u2B50",
    "Accessibility":       "\u267F",
    "Terminal Prefs":      "\U0001F4DF",
    "Update Manager":      "\U0001F504",
    "Software Manager":    "\U0001F4E6",
    "Software Sources":    "\U0001F4C2",
    "Driver Manager":      "\U0001F527",
    "Backup Tool":         "\U0001F4BE",
    "System Admin":        "\U0001F6E0",
    "Package Installer":   "\U0001F4E6",
    "Web Apps":            "\U0001F310",
    "Panel":               "\u2630",
    "Applets":             "\U0001F9E9",
    "Desklets":            "\U0001F9E9",
    "Extensions":          "\U0001F9E9",
    "Hot Corners":         "\U0001F4CD",
    "Actions":             "\u26A1",
    "Windows":             "\U0001FA9F",
    "Workspaces":          "\U0001F4CB",
    "Notifications":       "\U0001F514",
    "General":             "\u2699",
    "Menu Editor":         "\U0001F4DD",
    "Passwords & Keys":    "\U0001F511",
    "Privacy":             "\U0001F6E1",
    "Start Whim.m":        "\U0001F680",
    "Tailscale Status":    "\U0001F4F6",
    "Tailscale Up":        "\u2B06",
    "Tailscale Down":      "\u2B07",
    "VPS Tunnel Check":    "\U0001F310",
    "Open Whim (Browser)": "\U0001F5A5",
}

PNG_ICON_MAP = {
    "Color Profiles": os.path.expanduser("~/.local/share/icons/color-prism.gif"),
}

TAB_ICONS = {
    "Display":  "\U0001F5B5",
    "Sound":    "\U0001F50A",
    "Network":  "\U0001F310",
    "Input":    "\U0001F5B1",
    "Hardware": "\U0001F527",
    "System":   "\U0001F4BB",
    "Software": "\U0001F4E6",
    "Desktop":  "\U0001F5A5",
    "Security": "\U0001F512",
    "Whim":     "\U0001F4E1",
}


_running = {}

def launch(cmd, status_var, log_text):
    ts = datetime.now().strftime("%H:%M:%S")
    prev = _running.get(cmd)
    if prev is not None and prev.poll() is None:
        status_var.set(f"Already running: {cmd}")
        _log(log_text, "warn", f"[{ts}] Already running: {cmd}")
        return
    status_var.set(f"Launched: {cmd}")
    _log(log_text, "ok", f"[{ts}] Launched: {cmd}")
    try:
        proc = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
        _running[cmd] = proc
    except Exception as e:
        _log(log_text, "err", f"[{ts}] Failed: {e}")
        status_var.set(f"Failed: {e}")


def _log(log_text, tag, msg):
    log_text.configure(state="normal")
    log_text.insert("end", msg + "\n", tag)
    log_text.see("end")
    log_text.configure(state="disabled")


class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Control Panel")
        self.geometry("960x720")
        self.minsize(720, 500)
        self.configure(bg=TH["bg"])

        self._try_set_icon()
        self._apply_theme()

        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()

    def _try_set_icon(self):
        try:
            from PIL import Image, ImageTk
            icon_path = os.path.expanduser("~/.openclaw/Whim.png")
            if os.path.isfile(icon_path):
                img = Image.open(icon_path).resize((64, 64))
                self._icon_img = ImageTk.PhotoImage(img)
                self.iconphoto(False, self._icon_img)
        except Exception:
            pass

    def _apply_theme(self):
        style = ttk.Style(self)
        azure_tcl = os.path.join(AZURE_THEME_DIR, "azure.tcl")
        if os.path.isfile(azure_tcl):
            try:
                self.tk.call("source", azure_tcl)
                self.tk.call("set_theme", "dark")
                return
            except Exception:
                pass
        style.theme_use("clam")
        style.configure(".", background=TH["bg"], foreground=TH["fg"],
                        fieldbackground=TH["input"], bordercolor=TH["border"])
        style.configure("TNotebook", background=TH["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=TH["card"], foreground=TH["fg"],
                        padding=[12, 6], font=TH["font_tab"])
        style.map("TNotebook.Tab",
                  background=[("selected", TH["accent"])],
                  foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background=TH["bg"])
        style.configure("TLabel", background=TH["bg"], foreground=TH["fg"])

    def _build_ui(self):
        main = tk.Frame(self, bg=TH["bg"])
        main.pack(fill="both", expand=True)

        hdr = tk.Frame(main, bg=TH["bg"])
        hdr.pack(fill="x", padx=16, pady=(12, 4))
        tk.Label(hdr, text="Control Panel", font=TH["font_hero"],
                 fg="#00ff00", bg=TH["bg"]).pack(side="left")
        tk.Label(hdr, text="System Preferences & Administration",
                 font=TH["font_sm"], fg=TH["fg_dim"], bg=TH["bg"]).pack(side="left", padx=(16, 0))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_frame = tk.Frame(hdr, bg=TH["bg"])
        search_frame.pack(side="right")
        tk.Label(search_frame, text="Search:", font=TH["font_sm"],
                 fg=TH["fg2"], bg=TH["bg"]).pack(side="left", padx=(0, 4))
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                     bg=TH["input"], fg=TH["fg"], insertbackground=TH["fg"],
                                     font=TH["font"], relief="flat", width=20,
                                     highlightthickness=1, highlightcolor=TH["accent"],
                                     highlightbackground=TH["border"])
        self.search_entry.pack(side="left")

        sep = tk.Frame(main, bg=TH["border"], height=1)
        sep.pack(fill="x", padx=16, pady=(8, 0))

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        self._init_tab_drag()

        self.tab_frames = {}
        self.all_buttons = []

        for tab_name, items in TABS.items():
            tab_icon = TAB_ICONS.get(tab_name, "")
            tab_label = f" {tab_icon} {tab_name} "

            outer = ttk.Frame(self.notebook)
            self.notebook.add(outer, text=tab_label)

            canvas = tk.Canvas(outer, bg=TH["bg"], highlightthickness=0)
            scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            scroll_frame = tk.Frame(canvas, bg=TH["bg"])

            scroll_frame.bind("<Configure>",
                              lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            canvas.bind_all("<MouseWheel>",
                            lambda e, c=canvas: c.yview_scroll(int(-1 * (e.delta / 120)), "units"))

            self.tab_frames[tab_name] = (scroll_frame, items, canvas)
            self._populate_tab(scroll_frame, items, tab_name)

            if tab_name == "Whim":
                self._build_whim_status_panel(scroll_frame)

        self.search_tab_outer = ttk.Frame(self.notebook)
        search_canvas = tk.Canvas(self.search_tab_outer, bg=TH["bg"], highlightthickness=0)
        search_scrollbar = ttk.Scrollbar(self.search_tab_outer, orient="vertical",
                                         command=search_canvas.yview)
        self.search_frame = tk.Frame(search_canvas, bg=TH["bg"])
        self.search_frame.bind("<Configure>",
                               lambda e: search_canvas.configure(scrollregion=search_canvas.bbox("all")))
        search_canvas.create_window((0, 0), window=self.search_frame, anchor="nw")
        search_canvas.configure(yscrollcommand=search_scrollbar.set)
        search_canvas.pack(side="left", fill="both", expand=True)
        search_scrollbar.pack(side="right", fill="y")
        self.search_canvas = search_canvas

        bottom = tk.Frame(main, bg=TH["bg"])
        bottom.pack(fill="x", side="bottom")

        self.log_text = tk.Text(bottom, height=3, bg=TH["input"], fg=TH["fg"],
                                font=TH["font_mono"], borderwidth=0, highlightthickness=0,
                                insertbackground=TH["fg"], state="disabled", wrap="word")
        self.log_text.pack(fill="x", padx=8, pady=(0, 2))
        self.log_text.tag_configure("ok", foreground=TH["green"])
        self.log_text.tag_configure("err", foreground=TH["red"])
        self.log_text.tag_configure("warn", foreground=TH["yellow"])

        status_bar = tk.Frame(main, bg=TH["card"], height=24)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)
        tk.Label(status_bar, textvariable=self.status_var, font=TH["font_sm"],
                 fg=TH["fg2"], bg=TH["card"], anchor="w").pack(fill="x", padx=8)

    def _init_tab_drag(self):
        self._drag_start_idx = None
        self.notebook.bind("<ButtonPress-1>", self._tab_drag_start)
        self.notebook.bind("<B1-Motion>", self._tab_drag_motion)
        self.notebook.bind("<ButtonRelease-1>", self._tab_drag_end)

    def _tab_drag_start(self, event):
        try:
            idx = self.notebook.index(f"@{event.x},{event.y}")
            self._drag_start_idx = idx
            self.notebook.configure(cursor="fleur")
        except tk.TclError:
            self._drag_start_idx = None

    def _tab_drag_motion(self, event):
        if self._drag_start_idx is None:
            return
        try:
            target_idx = self.notebook.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return
        if target_idx == self._drag_start_idx:
            return
        tab_id = self.notebook.tabs()[self._drag_start_idx]
        self.notebook.insert(target_idx, tab_id)
        self._drag_start_idx = target_idx

    def _tab_drag_end(self, event):
        self._drag_start_idx = None
        self.notebook.configure(cursor="")

    def _populate_tab(self, parent, items, tab_name):
        COLS = 4
        for idx, (name, cmd) in enumerate(items):
            row, col = divmod(idx, COLS)
            icon_char = ICON_MAP.get(name, "\u2699")
            btn = self._make_item_button(parent, icon_char, name, cmd)
            btn.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.all_buttons.append((name, cmd, tab_name))

        for c in range(COLS):
            parent.columnconfigure(c, weight=1, uniform="col")

    def _make_item_button(self, parent, icon_char, name, cmd):
        frame = tk.Frame(parent, bg=TH["card"], cursor="hand2",
                         highlightbackground=TH["border"], highlightthickness=1)
        frame.configure(width=180, height=90)
        frame.pack_propagate(False)

        img_path = PNG_ICON_MAP.get(name)
        if img_path and os.path.isfile(img_path):
            try:
                tk_img = tk.PhotoImage(file=img_path)
                icon_lbl = tk.Label(frame, image=tk_img, bg=TH["card"])
                icon_lbl._tk_img = tk_img
            except Exception:
                icon_lbl = tk.Label(frame, text=icon_char or "\u2699",
                                    font=("Segoe UI Emoji", 24), fg=TH["fg"], bg=TH["card"])
        else:
            icon_lbl = tk.Label(frame, text=icon_char or "\u2699",
                                font=("Segoe UI Emoji", 24), fg=TH["fg"], bg=TH["card"])
        icon_lbl.pack(pady=(12, 2))

        name_lbl = tk.Label(frame, text=name, font=TH["font_btn"],
                            fg=TH["fg2"], bg=TH["card"], wraplength=160)
        name_lbl.pack(pady=(0, 8))

        def on_enter(e):
            frame.configure(bg=TH["card_hover"])
            icon_lbl.configure(bg=TH["card_hover"])
            name_lbl.configure(bg=TH["card_hover"])

        def on_leave(e):
            frame.configure(bg=TH["card"])
            icon_lbl.configure(bg=TH["card"])
            name_lbl.configure(bg=TH["card"])

        def on_click(e):
            launch(cmd, self.status_var, self.log_text)

        for widget in (frame, icon_lbl, name_lbl):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

        return frame

    def _build_whim_status_panel(self, parent):
        import json as _json
        import urllib.request as _ur

        sep = tk.Frame(parent, bg=TH["border"], height=1)
        sep.grid(row=10, column=0, columnspan=4, sticky="ew", padx=8, pady=(16, 8))

        status_frame = tk.Frame(parent, bg=TH["card"], highlightbackground=TH["border"],
                                highlightthickness=1)
        status_frame.grid(row=11, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 8))

        tk.Label(status_frame, text="Whim Connection Status", font=TH["font_title"],
                 fg="#00ff00", bg=TH["card"]).pack(anchor="w", padx=12, pady=(10, 4))

        indicators = tk.Frame(status_frame, bg=TH["card"])
        indicators.pack(fill="x", padx=12, pady=4)

        self._whim_dots = {}
        for col, (key, label) in enumerate([
            ("tunnel", "VPS Tunnel"), ("tailscale", "Tailscale"),
            ("server", "Whim.m Server"), ("ollama", "Ollama")
        ]):
            f = tk.Frame(indicators, bg=TH["card"])
            f.grid(row=0, column=col, padx=12, pady=4)
            dot = tk.Label(f, text="\u25CF", font=("Segoe UI", 14),
                           fg=TH["fg_dim"], bg=TH["card"])
            dot.pack()
            tk.Label(f, text=label, font=TH["font_sm"],
                     fg=TH["fg2"], bg=TH["card"]).pack()
            self._whim_dots[key] = dot

        mode_frame = tk.Frame(status_frame, bg=TH["card"])
        mode_frame.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(mode_frame, text="Connection Mode:", font=TH["font"],
                 fg=TH["fg"], bg=TH["card"]).pack(side="left")

        self._conn_mode_var = tk.StringVar(value="tunnel")
        for val, text in [("tunnel", "VPS Tunnel"), ("tailscale", "Tailscale"), ("auto", "Auto-detect")]:
            rb = tk.Radiobutton(mode_frame, text=text, variable=self._conn_mode_var,
                                value=val, font=TH["font_sm"], fg=TH["fg2"], bg=TH["card"],
                                selectcolor=TH["input"], activebackground=TH["card"],
                                activeforeground=TH["green"],
                                command=self._set_whim_conn_mode)
            rb.pack(side="left", padx=(12, 0))

        info_frame = tk.Frame(status_frame, bg=TH["card"])
        info_frame.pack(fill="x", padx=12, pady=(4, 10))

        self._whim_info_var = tk.StringVar(value="Checking status...")
        tk.Label(info_frame, textvariable=self._whim_info_var, font=TH["font_mono"],
                 fg=TH["fg_dim"], bg=TH["card"], anchor="w", justify="left").pack(fill="x")

        self._whim_poll_status()

    def _whim_poll_status(self):
        import json as _json
        import urllib.request as _ur

        def _check():
            ts_running = False
            try:
                r = subprocess.run(["tailscale", "status", "--json"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    d = _json.loads(r.stdout)
                    ts_running = d.get("BackendState") == "Running"
            except Exception:
                try:
                    r = subprocess.run(["ip", "addr", "show"],
                                       capture_output=True, text=True, timeout=3)
                    ts_running = "100." in r.stdout
                except Exception:
                    pass

            server_ok = False
            ollama_ok = False
            conn_mode = "tunnel"
            try:
                req = _ur.Request("http://localhost:8089/health")
                with _ur.urlopen(req, timeout=3) as resp:
                    if resp.status == 200:
                        server_ok = True
                        data = _json.loads(resp.read())
                        ollama_ok = data.get("ollama", False)
                        conn_mode = data.get("connection_mode", "tunnel")
            except Exception:
                pass

            tunnel_ok = False
            try:
                req = _ur.Request("http://YOUR_VPS_IP:8089/health")
                with _ur.urlopen(req, timeout=4) as resp:
                    tunnel_ok = resp.status == 200
            except Exception:
                pass

            def _update():
                g, r, d = TH["green"], TH["red"], TH["fg_dim"]
                self._whim_dots["tunnel"].config(fg=g if tunnel_ok else r)
                self._whim_dots["tailscale"].config(fg=g if ts_running else d)
                self._whim_dots["server"].config(fg=g if server_ok else r)
                self._whim_dots["ollama"].config(fg=g if ollama_ok else r)
                self._conn_mode_var.set(conn_mode)
                lines = []
                lines.append(f"Mode: {conn_mode.upper()}")
                lines.append(f"VPS: {'OK' if tunnel_ok else 'DOWN'}  |  "
                             f"Tailscale: {'ACTIVE (YOUR_TAILSCALE_PC_IP)' if ts_running else 'OFF'}  |  "
                             f"Server: {'OK' if server_ok else 'DOWN'}  |  "
                             f"Ollama: {'OK' if ollama_ok else 'DOWN'}")
                self._whim_info_var.set("\n".join(lines))

            self.after(0, _update)

        threading.Thread(target=_check, daemon=True).start()
        self.after(10000, self._whim_poll_status)

    def _set_whim_conn_mode(self):
        import json as _json
        import urllib.request as _ur

        mode = self._conn_mode_var.get()

        def _send():
            try:
                payload = _json.dumps({"mode": mode}).encode("utf-8")
                req = _ur.Request("http://localhost:8089/connection_mode",
                                  data=payload, method="POST",
                                  headers={"Content-Type": "application/json"})
                with _ur.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = _json.loads(resp.read())
                        self.after(0, lambda: _log(self.log_text, "ok",
                            f"[{datetime.now().strftime('%H:%M:%S')}] Connection mode set to: {mode.upper()}"))
                        self.after(0, lambda: self.status_var.set(f"Whim connection: {mode.upper()}"))
            except Exception as e:
                self.after(0, lambda: _log(self.log_text, "err",
                    f"[{datetime.now().strftime('%H:%M:%S')}] Failed to set mode: {e}"))

        threading.Thread(target=_send, daemon=True).start()

    def _on_search(self, *args):
        query = self.search_var.get().strip().lower()
        if not query:
            try:
                idx = self.notebook.index(self.search_tab_outer)
                self.notebook.forget(idx)
            except Exception:
                pass
            return

        for widget in self.search_frame.winfo_children():
            widget.destroy()

        matches = [(name, cmd, tab) for name, cmd, tab in self.all_buttons
                   if query in name.lower() or query in cmd.lower() or query in tab.lower()]

        if not matches:
            tk.Label(self.search_frame, text="No results found.", font=TH["font"],
                     fg=TH["fg_dim"], bg=TH["bg"]).grid(row=0, column=0, padx=20, pady=20)
        else:
            COLS = 4
            for idx, (name, cmd, tab) in enumerate(matches):
                row, col = divmod(idx, COLS)
                icon_char = ICON_MAP.get(name, "\u2699")
                btn = self._make_item_button(self.search_frame, icon_char, name, cmd)
                btn.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            for c in range(COLS):
                self.search_frame.columnconfigure(c, weight=1, uniform="col")

        try:
            self.notebook.index(self.search_tab_outer)
        except Exception:
            self.notebook.add(self.search_tab_outer, text=" \U0001F50D Search ")

        self.notebook.select(self.search_tab_outer)


LOCK_FILE = os.path.expanduser("~/.cache/control-panel.lock")

def _acquire_lock():
    if os.path.isfile(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            if os.path.isdir(f"/proc/{old_pid}"):
                subprocess.Popen(
                    ["wmctrl", "-a", "Control Panel"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return False
        except Exception:
            pass
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True

def _release_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

def main():
    if not _acquire_lock():
        sys.exit(0)
    try:
        app = ControlPanel()
        app.mainloop()
    finally:
        _release_lock()


if __name__ == "__main__":
    main()
