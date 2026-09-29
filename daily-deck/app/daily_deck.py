#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAILY DECK  ·  Persoenliches Alltags-Cockpit
=============================================

Kompaktes Desktop-Widget (GTK3) fuer alltaegliche Aktionen:
Programme starten, Verzeichnisse im Terminal oeffnen, SSH-Server
connecten, Systeminfos anzeigen.

Das Widget ist ein Geschwister des bestehenden "Command Deck" und benutzt
dieselbe Code- und Gestaltungssprache (identisches Theme, identische
Bedienlogik, identische Farbpalette) - nur die Art der Aktionen ist eine
andere: Alltag statt Entwicklerarbeit.

###############################################################################
#  SICHERHEITS- UND TRENNUNGS-GARANTIE
###############################################################################
#  1. Dieses Programm fasst das bestehende "Command Deck"
#     (~/TerminalCommandWidget, ~/.config/terminal-clipboard,
#      ~/.config/autostart/command-deck.desktop) NICHT an.
#     Eigenes Verzeichnis, eigener State-Ordner, eigener Autostart,
#     eigene Kopie des Themes (die Originaldatei wird nie geschrieben).
#
#  2. Jeder Button traegt eine sichtbare Typ-Kennung:
#        START     -> startet eine Desktop-Anwendung (argv-Liste, kein Shell)
#        TERMINAL  -> oeffnet das System-Terminal in einem Arbeitsverzeichnis
#                      und fuehrt optional einen Befehl darin aus
#        COPY      -> kopiert Text in die Zwischenablage, fuehrt NICHTS aus
#     Es gibt keinen versteckten Ausfuehrungspfad. Der Typ COPY kann
#     konstruktionsbedingt keinen Prozess starten.
#
#  3. Blockliste: destruktive Befehle (rm -rf, mkfs, dd, shred, fdisk,
#     shutdown, reboot, halt, poweroff, sudo, su, passwd, useradd, ... )
#     werden beim Laden der Konfiguration abgewiesen. Ein solcher Eintrag
#     wird als "gesperrt" markiert und ist nicht ausfuehrbar.
#
#  4. Es werden keine Passwoerter gespeichert, keine SSH-Keys kopiert und
#     ~/.ssh/config wird ausschliesslich gelesen (nie geschrieben).
#
#  5. Kein Zugriff auf Wallpaper, Cinnamon-Theme, Bildschirmaufloesung oder
#     irgendeine andere Desktop-Konfiguration.
#
#  Selbsttest:  ./daily_deck.py --selftest
###############################################################################
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

APP_NAME = "Daily Deck"
APP_ID = "daily-deck"
VERSION = "1.0.0"

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(PROJECT_ROOT, "assets")
SEED_DIR = os.path.join(PROJECT_ROOT, "config")

CONFIG_DIR = (os.environ.get("XDG_CONFIG_HOME")
              or os.path.join(os.path.expanduser("~"), ".config"))
STATE_DIR = os.path.join(CONFIG_DIR, APP_ID)
COMMANDS_FILE = os.path.join(STATE_DIR, "commands.json")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
LOCK_FILE = os.path.join(STATE_DIR, "instance.lock")

MIN_W, MIN_H = 300, 300
ACTION_FEEDBACK_MS = 1500
STATUS_RESET_MS = 2600

# ------------------------------------------------------------------- Palette
# identisch zum Command Deck (siehe assets/theme.css)
C_BG0 = (0x0B, 0x06, 0x12)
C_VIOLET_D = (0x6D, 0x28, 0xD9)
C_VIOLET = (0x8B, 0x5C, 0xF6)
C_NEON = (0xA8, 0x55, 0xF7)
C_NEON_LT = (0xC0, 0x84, 0xFC)

# Typ -> (Beschriftung auf dem Knopf, CSS-Klasse)
TYPE_INFO = {
    "START":    ("START",    "act-start"),
    "TERMINAL": ("TERMINAL", "act-terminal"),
    "COPY":     ("COPY",     "act-copy"),
}

DEFAULT_STATE = {
    "always_on_top": True,
    "opacity": 0.95,
    "x": 40,
    "y": 60,
    "width": 400,
    "height": 620,
    "favorites": [],
}

# ------------------------------------------------------------- Blockliste
BLOCKED = [
    r"\brm\b\s+(-[a-z]*[rf]|.*--recursive)",
    r"\bmkfs\b", r"\bfdisk\b", r"\bparted\b", r"\bdd\b", r"\bshred\b",
    r":\(\)\s*\{", r"\bsudo\b", r"\bsu\s+-", r"\bpasswd\b",
    r"\buseradd\b", r"\buserdel\b", r"\busermod\b", r"\bchown\b",
    r"\bchmod\b\s+777", r"\bshutdown\b", r"\breboot\b", r"\bhalt\b",
    r"\bpoweroff\b", r"\binit\s+0", r"\bkill\s+-9\b", r"\bkillall\b",
    r"\bmv\b\s+/\w", r">\s*/dev/sd", r"\bcurl\b.*\|\s*(ba)?sh",
    r"\bwget\b.*\|\s*(ba)?sh", r"\bnc\b\s+-\w*e", r"\bhistory\s+-c\b",
]
BLOCKED_RE = [re.compile(p) for p in BLOCKED]

HIGHLIGHT_BG = "#3A1E63"
HIGHLIGHT_FG = "#F3E8FF"


def is_blocked(text):
    if not text:
        return False
    return any(rx.search(text) for rx in BLOCKED_RE)


def log(*a):
    if os.environ.get("DAILY_DECK_DEBUG"):
        print("[daily-deck]", *a, file=sys.stderr)


def hexa(rgb, alpha):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha)


def escape_markup(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("'", "&#39;"))


def highlight(text, query):
    """Suchtreffer neon-violett markieren (Pango kennt kein <mark>-Tag)."""
    if not query:
        return escape_markup(text)
    out, low, q, i = [], text.lower(), query.lower(), 0
    while True:
        j = low.find(q, i)
        if j < 0:
            out.append(escape_markup(text[i:]))
            break
        out.append(escape_markup(text[i:j]))
        out.append('<span background="%s" foreground="%s"><b>%s</b></span>'
                   % (HIGHLIGHT_BG, HIGHLIGHT_FG,
                      escape_markup(text[j:j + len(q)])))
        i = j + len(q)
    return "".join(out)


def editor_command():
    for exe in ("gnome-text-editor", "gedit", "xed", "mousepad", "kate"):
        path = shutil.which(exe)
        if path:
            return path
    return None


def event_box():
    """Wie im Command Deck: eigenes GdkWindow, aber above_child=False,
    sonst kaelt das EventBox-Fenster die Klicks auf den Aktionsknopf ab."""
    box = Gtk.EventBox()
    box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                   | Gdk.EventMask.BUTTON_RELEASE_MASK
                   | Gdk.EventMask.POINTER_MOTION_MASK)
    box.set_above_child(False)
    return box


# ===========================================================================
#  Terminal-Erkennung  (nichts fest verdrahtet)
# ===========================================================================
def detect_terminal():
    """Ermittelt das tatsaechlich konfigurierte Standard-Terminal.

    1. org.cinnamon.desktop.default-applications.terminal
    2. org.gnome.desktop.default-applications.terminal
    3. $TERMINAL
    4. gnome-terminal / x-terminal-emulator / xterm
    """
    args = []

    def gsettings_get(schema, key):
        try:
            out = subprocess.run(
                ["gsettings", "get", schema, key],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=4)
        except (OSError, subprocess.SubprocessError):
            return None
        val = out.stdout.decode("utf-8", "replace").strip()
        if not val.startswith("'"):
            return None
        return val.strip("'")

    for schema in ("org.cinnamon.desktop.default-applications.terminal",
                   "org.gnome.desktop.default-applications.terminal"):
        exec_bin = gsettings_get(schema, "exec")
        if not exec_bin:
            continue
        exec_arg = gsettings_get(schema, "exec-arg") or ""
        tokens = shlex.split(exec_bin)
        if tokens and shutil.which(tokens[0]):
            extra = shlex.split(exec_arg) if exec_arg and exec_arg != "--" else []
            return tokens + extra

    env_term = os.environ.get("TERMINAL", "").strip()
    if env_term and shutil.which(env_term):
        return [env_term]

    for fallback in ("gnome-terminal", "x-terminal-emulator", "xterm"):
        if shutil.which(fallback):
            return [fallback]
    return []


def terminal_argv(term_argv, workdir=None, command=None):
    """Baut die Argumentliste fuer das erkannte Terminal.

    Nur Terminals mit bekanntem Flag-Schema bekommen Arbeitsverzeichnis
    und Befehl; sonst wird ueber die Shell gearbeitet.
    """
    if not term_argv:
        return []
    exe = os.path.basename(term_argv[0])
    argv = list(term_argv)
    finish = '; printf "\\n[Daily Deck] fertig - Fenster mit exit schliessen"; read -r'

    if exe in ("gnome-terminal", "kgx", "mate-terminal"):
        if command:
            argv += ["--", "bash", "-lc",
                     (('cd %s && ' % shlex.quote(workdir)) if workdir else "")
                     + command + finish]
        elif workdir:
            argv += ["--working-directory=" + workdir]
        return argv

    if exe == "xfce4-terminal":
        args = []
        if workdir:
            args.append("--directory=" + workdir)
        args += ["--command",
                 "bash -lc %s" % shlex.quote(
                     ((('cd %s && ' % shlex.quote(workdir)) if workdir else "")
                      + (command or "")) + finish)]
        return argv + args

    if exe == "konsole":
        args = ["-e"]
        if workdir:
            args += ["--workdir", workdir]
        args += ["bash", "-lc", command + finish] if command else ["bash"]
        return argv + args

    if exe in ("xterm", "uxterm"):
        args = ["-fa", "Monospace"]
        args += ["-e", "bash", "-lc",
                 ("cd %s && " % shlex.quote(workdir) if workdir else "")
                 + (command or "") + finish]
        return argv + args

    code = (("cd %s && " % shlex.quote(workdir)) if workdir else "") + (command or "")
    return argv + ["-e", "bash", "-lc", code + finish if code else "bash"]


def terminal_display(term_argv):
    return " ".join(os.path.basename(a) for a in term_argv) or "kein Terminal"


# ===========================================================================
#  SSH-Hosts aus ~/.ssh/config lesen  (nur lesend!)
# ===========================================================================
def ssh_hosts_with_meta(path=None):
    """-> [(alias, hostname, user)] aus ~/.ssh/config. Reine Leseoperation."""
    path = path or os.path.join(os.path.expanduser("~"), ".ssh", "config")
    out = []
    if not os.path.exists(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        log("ssh config nicht lesbar:", exc)
        return out
    current, info = [], {}
    for raw in lines + ["\n"]:
        line = raw.strip()
        if raw != "\n" and (not line or line.startswith("#")):
            continue
        parts = line.split(None, 1)
        if not parts:
            if current:
                for alias in current:
                    out.append((alias, info.get("hostname"), info.get("user")))
            current, info = [], {}
            continue
        key, value = parts[0].lower(), parts[1].strip()
        if key == "host":
            current += [t for t in shlex.split(value)
                        if t and not t.startswith(("!", "?", "*"))]
        elif key == "hostname" and current:
            info["hostname"] = value
        elif key == "user" and current:
            info["user"] = value
    return out


# ===========================================================================
#  Datenhaltung
# ===========================================================================
class Store(object):
    """commands.json (Befehle) und state.json (Geometrie, Favoriten)."""

    def __init__(self, commands_file=COMMANDS_FILE, state_file=STATE_FILE):
        self.commands_file = commands_file
        self.state_file = state_file
        self.config = {}
        self.state = dict(DEFAULT_STATE)
        self.state["favorites"] = []
        self.load_error = None
        self.ssh_hosts = []

    def ensure_dirs(self):
        os.makedirs(STATE_DIR, exist_ok=True)

    # ------------------------------------------------------------ commands.json
    def ensure_commands_file(self):
        if os.path.exists(self.commands_file):
            return
        self.ensure_dirs()
        src = os.path.join(SEED_DIR, "commands.json")
        if os.path.isfile(src):
            shutil.copyfile(src, self.commands_file)
            log("commands.json aus Vorlage angelegt:", self.commands_file)

    def load_commands(self):
        self.ensure_commands_file()
        self.config, self.load_error = {}, None
        try:
            with open(self.commands_file, "r", encoding="utf-8") as fh:
                self.config = json.load(fh)
        except Exception as exc:
            self.load_error = str(exc)
            log("commands.json nicht lesbar:", exc)
            return
        if not isinstance(self.config, dict):
            self.load_error = "kein JSON-Objekt gefunden"
            self.config = {}

    def save_commands(self, data):
        tmp = self.commands_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.commands_file)

    def setting(self, key, default=None):
        return (self.config.get("settings") or {}).get(key, default)

    # ---------------------------------------------------------------- state.json
    def load_state(self):
        self.state = dict(DEFAULT_STATE)
        self.state["favorites"] = []
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    for key, value in loaded.items():
                        if key in DEFAULT_STATE:
                            self.state[key] = value
                return self.state
            except Exception as exc:
                log("state.json unbrauchbar, starte frisch:", exc)
        return self.state

    def save_state(self, state=None):
        if state is not None:
            self.state = state
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            tmp = self.state_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.state_file)
        except Exception as exc:
            log("state.json nicht schreibbar:", exc)
        return self.state

    # ---------------------------------------------------------------- Favoriten
    @staticmethod
    def key_of(item):
        return "%s/%s" % (item.get("category", "?"), item.get("key_name", "?"))

    def is_fav(self, item):
        return self.key_of(item) in self.state.get("favorites", [])

    def toggle_fav(self, item):
        favs = self.state.setdefault("favorites", [])
        k = self.key_of(item)
        if k in favs:
            favs.remove(k)
            return False
        favs.append(k)
        return True

    # ------------------------------------------------------------------ Items
    def build_items(self, term_argv):
        """Flache, gerenderte Liste aller Eintraege inkl. SSH-Hosts."""
        items = []
        ssh_items = self.build_ssh_items(term_argv)
        ssh_cat = str(self.setting("ssh_category", "SERVER"))

        def finalize(entry, cat_name, cat_icon):
            entry["category"] = cat_name
            entry["category_icon"] = cat_icon
            entry["key_name"] = entry.get("key_name") or entry.get("name", "?")
            entry["type"] = entry["type"] if entry["type"] in TYPE_INFO else "COPY"

            probe = " ".join([str(entry.get("command") or ""),
                              str(entry.get("workdir") or ""),
                              " ".join(entry.get("argv") or [])])
            entry["blocked"] = is_blocked(probe)

            missing = [r for r in (entry.get("requires") or [])
                       if shutil.which(r) is None]
            if entry["type"] == "TERMINAL" and not term_argv:
                missing.append("Terminal")
            entry["missing"] = missing
            return entry

        categories = self.config.get("categories") or {}
        ordered = sorted(categories.items(),
                         key=lambda kv: (kv[1].get("order", 99)
                                         if isinstance(kv[1], dict) else 99))
        for cat_name, cat in ordered:
            if not isinstance(cat, dict) or cat.get("enabled") is False:
                continue
            cat_icon = cat.get("icon", "◈")
            for order, entry in enumerate(cat.get("entries") or []):
                if isinstance(entry, str):
                    entry = {"name": entry, "type": "COPY", "command": entry}
                if not isinstance(entry, dict) or entry.get("enabled") is False:
                    continue
                entry = dict(entry)
                entry.setdefault("type", "COPY")
                entry.setdefault("description", "")
                entry["order"] = order
                items.append(finalize(entry, cat_name, cat_icon))
            if cat_name == ssh_cat:
                for entry in ssh_items:
                    entry = dict(entry)
                    entry["order"] = 1000 + entry.get("order", 0)
                    items.append(finalize(entry, cat_name, cat_icon))
        return items

    def build_ssh_items(self, term_argv):
        """SERVER-Eintraege direkt aus ~/.ssh/config (kein Double-Pflege)."""
        items = []
        hosts = ssh_hosts_with_meta()
        self.ssh_hosts = [h[0] for h in hosts]
        home = os.path.expanduser("~")
        for order, (alias, hostname, user) in enumerate(hosts):
            desc = "ssh %s" % alias
            if hostname:
                desc += "  ->  %s" % hostname
            if user:
                desc += "  (%s@)" % user
            items.append({
                "name": "🌐 %s" % alias,
                "key_name": alias,
                "description": desc,
                "category": "SERVER",
                "category_icon": "🌐",
                "order": order,
                "type": "TERMINAL",
                "command": "ssh %s" % shlex.quote(alias),
                "workdir": self.setting("ssh_workdir") or home,
                "copy_text": "ssh %s" % alias,
                "from_ssh_config": True,
            })
        return items


# ===========================================================================
#  Hintergrund  (identisch zum Command Deck)
# ===========================================================================
def rounded(cr, x, y, w, h, r):
    if w <= 0 or h <= 0:
        return
    r = min(r, w / 2.0, h / 2.0)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.14159)
    cr.arc(x + r, y + r, r, 3.14159, 4.71239)
    cr.close_path()


class DeckBackground(Gtk.DrawingArea):
    """Glasflaeche, Verlauf, Rand, Eckakzente und Scanlines - alles mit Cairo."""

    def __init__(self, opacity=0.95):
        super(DeckBackground, self).__init__()
        self.opacity = opacity

    def set_opacity(self, value):
        try:
            self.opacity = max(0.55, min(1.0, float(value)))
        except (TypeError, ValueError):
            self.opacity = 0.95
        self.queue_draw()

    def draw(self, _widget, cr):
        w, h = self.get_allocated_width(), self.get_allocated_height()
        if w <= 2 or h <= 2:
            return
        a = self.opacity
        r = 14.0
        x, y, ww, hh = 0.5, 0.5, w - 1.0, h - 1.0

        # ---- Glasflaeche + Verlaeufe
        cr.save()
        rounded(cr, x, y, ww, hh, r)
        cr.clip()

        cr.set_source_rgba(*hexa(C_BG0, a))
        cr.paint_preserve()

        grad = cr.LinearGradient(0, 0, 0, h)
        grad.add_color_stop_rgba(0.0, *hexa(C_VIOLET_D, 0.20 * a))
        grad.add_color_stop_rgba(0.45, *hexa(C_BG0, 0.0))
        cr.set_source(grad)
        cr.paint()

        grad2 = cr.LinearGradient(0, 0, w, h)
        grad2.add_color_stop_rgba(0.0, *hexa(C_NEON, 0.08 * a))
        grad2.add_color_stop_rgba(0.40, *hexa(C_BG0, 0.0))
        cr.set_source(grad2)
        cr.paint()

        # ---- dezente Scanlines
        cr.set_source_rgba(*hexa(C_VIOLET, 0.028 * a))
        yy = 0.0
        while yy < h:
            cr.rectangle(0, yy, w, 1.0)
            yy += 3.0
        cr.fill()
        cr.restore()

        # ---- Rand
        cr.set_source_rgba(*hexa(C_VIOLET, 0.45 * a))
        cr.set_line_width(1.0)
        rounded(cr, x + 0.5, y + 0.5, ww - 1.0, hh - 1.0, r - 0.5)
        cr.stroke()

        # ---- Cyber-Eckakzente
        cr.set_source_rgba(*hexa(C_NEON_LT, 0.70 * a))
        cr.set_line_width(1.6)
        for cx, cy in ((x + r, y + r), (x + ww - r, y + r),
                       (x + r, y + hh - r), (x + ww - r, y + hh - r)):
            cr.arc(cx, cy, 5.0, 0, 2 * 3.14159)
            cr.stroke()

        # ---- dezenter Glow oben (Headerglanz)
        glow = cr.LinearGradient(0, 0, 0, 70)
        glow.add_color_stop_rgba(0.0, *hexa(C_NEON, 0.10 * a))
        glow.add_color_stop_rgba(1.0, *hexa(C_NEON, 0.0))
        cr.save()
        rounded(cr, x, y, ww, hh, r)
        cr.clip()
        cr.set_source(glow)
        cr.rectangle(0, 0, w, 70)
        cr.fill()
        cr.restore()


# ===========================================================================
#  Widget
# ===========================================================================
class DailyDeck(Gtk.Window):

    def __init__(self, store):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.store = store
        self.term_argv = detect_terminal()
        self._css = None
        self._flash_timer = None
        self._status_timer = None
        self._drag = None
        self._resize = None
        self._rows = []
        self._query = ""
        self._items = []

        st = store.state
        self.set_title(APP_NAME)
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(bool(st.get("always_on_top", True)))
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_gravity(Gdk.Gravity.NORTH_WEST)
        self.set_default_size(int(st.get("width", 400)),
                              int(st.get("height", 620)))
        self.set_size_request(MIN_W, MIN_H)
        self.move(int(st.get("x", 40)), int(st.get("y", 60)))

        # Translucenz braucht einen RGBA-Visual
        screen = Gdk.Screen.get_default()
        if screen is not None:
            rgba = screen.get_rgba_visual()
            if rgba is not None:
                self.set_visual(rgba)
        self.set_app_paintable(True)

        self._build_ui()
        self._apply_style()
        self._update_search_hint()
        self.reload_commands()
        self._clamp_to_screen()
        self._update_status()

        self.connect("configure-event", self._on_configure)
        self.connect("key-press-event", self._on_key)
        self.connect("delete-event", self._on_delete)

    # ------------------------------------------------------------------ Styling
    def _apply_style(self):
        provider = Gtk.CssProvider()
        path = os.path.join(ASSETS, "theme.css")
        try:
            provider.load_from_path(path)
        except Exception as exc:
            print("[daily-deck] theme.css nicht ladbar: %s" % exc, file=sys.stderr)
        screen = Gdk.Screen.get_default()
        if self._css is not None:
            Gtk.StyleContext.remove_provider_for_screen(screen, self._css)
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css = provider

    # ----------------------------------------------------------------------- UI
    def _build_ui(self):
        self.bg = DeckBackground(self.store.state.get("opacity", 0.95))
        overlay = Gtk.Overlay()
        overlay.add(self.bg)
        overlay.add_overlay(self._build_content())
        self.add(overlay)
        self.show_all()

    def _build_content(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_border_width(1)
        outer.pack_start(self._build_header(), False, False, 0)
        outer.pack_start(self._build_searchbar(), False, False, 0)

        # Gtk.Box statt Gtk.ListBox: GTK3 malt in listbox einen
        # undurchsichtigen Theme-Hintergrund, der sich per CSS nicht
        # abschalten laesst und die Glasflaeche verdecken wuerde.
        self.listbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.listbox.set_border_width(1)
        self.listbox.set_margin_start(7)
        self.listbox.set_margin_end(5)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_hexpand(True)
        self.scroll.set_vexpand(True)
        self.scroll.add(self.listbox)
        outer.pack_start(self.scroll, True, True, 0)
        outer.pack_end(self._build_footer(), False, False, 0)
        return outer

    def _build_header(self):
        self.header = event_box()
        self.header.get_style_context().add_class("header")

        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        hb.set_border_width(1)
        self.header.add(hb)

        glyph = Gtk.Label(label="◈")
        glyph.get_style_context().add_class("glyph")
        glyph.set_valign(Gtk.Align.START)
        hb.pack_start(glyph, False, False, 0)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label="DAILY DECK")
        title.get_style_context().add_class("title")
        sub = Gtk.Label(label="ALLTAG // QUICK LAUNCH")
        sub.get_style_context().add_class("subtitle")
        col.pack_start(title, False, False, 0)
        col.pack_start(sub, False, False, 0)
        hb.pack_start(col, True, True, 0)

        self.pin_label = Gtk.Label(label="PIN")
        self.pin_label.get_style_context().add_class("hint")
        self.pin_label.set_valign(Gtk.Align.CENTER)
        hb.pack_end(self.pin_label, False, False, 0)

        self.header.connect("button-press-event", self._on_header_press)
        self.header.connect("button-release-event", self._on_header_release)
        self.header.connect("motion-notify-event", self._on_header_motion)
        self.header.set_tooltip_text("Ziehen = verschieben  ·  Rechtsklick = Menü")
        return self.header

    def _build_searchbar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.set_border_width(1)
        box.set_margin_start(8)
        box.set_margin_end(7)
        box.set_margin_top(6)
        box.set_margin_bottom(2)

        ico = Gtk.Label(label="❯")
        ico.get_style_context().add_class("glyph")
        ico.set_valign(Gtk.Align.CENTER)
        box.pack_start(ico, False, False, 0)

        # Entry + eigener Hinweistext als Overlay, weil GTK 3.24 den
        # CSS-Selektor ::placeholder nicht unterstuetzt.
        stack = Gtk.Overlay()
        self.search = Gtk.Entry()
        self.search.get_style_context().add_class("search")
        self.search.set_hexpand(True)
        self.search.connect("changed", self._on_search_changed)
        self.search.connect("key-press-event", self._on_search_key)
        stack.add(self.search)

        self.search_hint = Gtk.Label(label="Search actions...")
        self.search_hint.get_style_context().add_class("search-hint")
        self.search_hint.set_halign(Gtk.Align.START)
        self.search_hint.set_valign(Gtk.Align.CENTER)
        self.search_hint.set_margin_start(9)
        self.search_hint.set_ellipsize(Pango.EllipsizeMode.END)
        self.search_hint_event = event_box()
        self.search_hint_event.add(self.search_hint)
        self.search_hint_event.set_halign(Gtk.Align.START)
        self.search_hint_event.connect("button-press-event", self._on_hint_press)
        stack.add_overlay(self.search_hint_event)
        box.pack_start(stack, True, True, 0)

        self.clear_btn = Gtk.Button(label="✕")
        self.clear_btn.set_tooltip_text("Suche leeren (Esc)")
        self.clear_btn.get_style_context().add_class("clear")
        self.clear_btn.set_valign(Gtk.Align.CENTER)
        self.clear_btn.connect("clicked", lambda *_: self._set_query(""))
        box.pack_start(self.clear_btn, False, False, 0)
        return box

    def _on_hint_press(self, _widget, _event):
        self.search.grab_focus()
        return True

    def _update_search_hint(self):
        empty = not self.search.get_text()
        self.search_hint_event.set_visible(empty)
        self.clear_btn.set_sensitive(not empty)

    def _build_footer(self):
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self.footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.footer.get_style_context().add_class("footer")

        self.status = Gtk.Label(label="")
        self.status.set_xalign(0.0)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.get_style_context().add_class("status")
        self.footer.pack_start(self.status, True, True, 0)

        self.aot_label = Gtk.Label(label="▲ PIN")
        self.aot_label.get_style_context().add_class("status-neon")
        self.footer.pack_end(self.aot_label, False, False, 0)

        self.grip = event_box()
        self.grip.get_style_context().add_class("grip")
        self.grip.set_size_request(11, 11)
        self.grip.set_tooltip_text("Ziehen = Größe ändern")
        self.grip.connect("button-press-event", self._on_grip_press)
        self.grip.connect("motion-notify-event", self._on_grip_motion)
        self.grip.connect("button-release-event", self._on_grip_release)

        align = Gtk.Box()
        align.set_halign(Gtk.Align.END)
        align.set_valign(Gtk.Align.END)
        align.set_border_width(2)
        align.add(self.grip)

        self.footer.pack_end(align, False, False, 0)
        hbox.pack_start(self.footer, True, True, 0)
        wrap.pack_start(hbox, False, False, 0)
        return wrap

    # ------------------------------------------------------------------ Befehle
    def reload_commands(self):
        self.store.load_commands()
        self._items = self.store.build_items(self.term_argv)
        self._rebuild_list()
        self._update_status()

    def _visible_groups(self):
        """-> [(name, icon, ist_favoriten, [item, ...]), ...]"""
        q = self._query.strip().lower()
        groups, fav_hits = [], []

        by_cat = {}
        for item in self._items:
            by_cat.setdefault((item["category"], item["category_icon"]),
                              []).append(item)

        for (name, icon), entries in by_cat.items():
            hay = lambda e: (e.get("name", "") + " " + e.get("description", "")
                             + " " + e.get("category", "")).lower()
            hits = [e for e in entries if not q or q in hay(e)]
            if not hits:
                continue
            starred = [e for e in hits if self.store.is_fav(e)]
            plain = [e for e in hits if not self.store.is_fav(e)]
            fav_hits.extend(starred)
            if plain:
                groups.append((name, icon, False, plain))

        if fav_hits:
            favs = self.store.state.get("favorites", [])
            fav_hits.sort(key=lambda e: favs.index(self.store.key_of(e))
                          if self.store.key_of(e) in favs else 10 ** 6)
            groups.insert(0, ("★ Favorites", "★", True, fav_hits))
        return groups

    def _rebuild_list(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        self._rows = []

        groups = self._visible_groups()
        if not groups:
            empty = Gtk.Label(label="keine Treffer für\n» %s «" % self._query)
            empty.get_style_context().add_class("hint")
            empty.set_justify(Gtk.Justification.CENTER)
            empty.set_margin_top(20)
            empty.set_margin_bottom(20)
            self.listbox.pack_start(empty, False, False, 0)
            self.listbox.show_all()
            self._update_status()
            return

        for name, icon, is_fav, items in groups:
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            head.get_style_context().add_class("cat")
            if is_fav:
                head.get_style_context().add_class("cat-fav")
            lbl = Gtk.Label(label="%s  %s" % (icon, name.upper()))
            lbl.get_style_context().add_class("cat-label")
            lbl.set_xalign(0.0)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            head.pack_start(lbl, True, True, 0)
            cnt = Gtk.Label(label="%02d" % len(items))
            cnt.get_style_context().add_class("cat-count")
            head.pack_end(cnt, False, False, 0)
            self.listbox.pack_start(head, False, False, 0)

            for item in items:
                row = self._build_row(item)
                self.listbox.pack_start(row, False, False, 0)
                self._rows.append((row, item))

        self.listbox.show_all()
        self._update_status()

    def _build_row(self, item):
        row = event_box()
        row.get_style_context().add_class("row")
        if item.get("blocked"):
            row.get_style_context().add_class("row-blocked")
        elif item.get("missing"):
            row.get_style_context().add_class("row-missing")
        row.set_tooltip_text(self._tooltip(item))

        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        row.add(hb)

        # ---- Favoriten-Stern
        starred = self.store.is_fav(item)
        star = Gtk.Label(label="★" if starred else "☆")
        star.get_style_context().add_class(
            "fav-star" if starred else "fav-star-off")
        star.set_valign(Gtk.Align.CENTER)
        star_event = event_box()
        star_event.add(star)
        star_event.set_tooltip_text(
            "Favorit entfernen" if starred else "Als Favorit markieren")
        star_event.connect("button-press-event", self._on_star_press, item)
        hb.pack_start(star_event, False, False, 0)

        # ---- Bezeichnung (Klick fuehrt ebenfalls aus)
        txt = Gtk.Label()
        txt.set_markup(highlight(item.get("name", "?"), self._query))
        txt.get_style_context().add_class("cmd")
        txt.set_xalign(0.0)
        txt.set_yalign(0.5)
        txt.set_ellipsize(Pango.EllipsizeMode.END)
        txt.set_hexpand(True)
        txt_event = event_box()
        txt_event.add(txt)
        txt_event.set_tooltip_text(item.get("description", ""))
        txt_event.connect("button-press-event", self._on_cmd_press, item)
        hb.pack_start(txt_event, True, True, 0)

        # ---- Aktionsknopf: der Typ steht als Text darauf
        label, cls = TYPE_INFO[item["type"]]
        btn = Gtk.Button(label=label)
        ctx = btn.get_style_context()
        ctx.add_class("act")
        ctx.add_class(cls)
        if item.get("blocked"):
            ctx.add_class("act-blocked")
        elif item.get("missing"):
            ctx.add_class("act-missing")
        btn.set_tooltip_text(self._tooltip(item))
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", self._on_action_clicked, item)
        hb.pack_end(btn, False, False, 0)
        return row

    def _tooltip(self, item):
        lines = [item.get("description") or item.get("name", ""),
                 "%s  ·  %s" % (item["type"], item.get("category", ""))]
        if item["type"] == "TERMINAL":
            lines.append("Terminal: %s" % terminal_display(self.term_argv))
            if item.get("workdir"):
                lines.append("Verzeichnis: %s"
                             % os.path.expanduser(item["workdir"]))
            if item.get("command"):
                lines.append("Befehl: %s" % item["command"])
        elif item["type"] == "START":
            lines.append("Programm: %s" % " ".join(item.get("argv") or []))
        else:
            lines.append("kopiert: %s" % (item.get("copy_text")
                                          or item.get("command", "")))
        if item.get("blocked"):
            lines.append("GESPERRT · destruktiver Befehl – nicht ausführbar")
        for miss in item.get("missing") or []:
            lines.append("NICHT VERFÜGBAR · %s fehlt (siehe README)" % miss)
        return "\n".join(lines)

    # -------------------------------------------------------------------- Suche
    def _on_search_changed(self, entry):
        self._set_query(entry.get_text(), from_entry=True)

    def _on_search_key(self, _entry, event):
        key = Gdk.keyval_name(event.keyval)
        if key in ("Escape", "Esc"):
            if self.search.get_text():
                self._set_query("")
                return True
            return False
        if key in ("Return", "KP_Enter", "Down", "Page_Down"):
            if self._rows:
                self.run_item(self._rows[0][1], None)
            return True
        return False

    def _set_query(self, text, from_entry=False):
        self._query = text or ""
        if not from_entry:
            if self.search.get_text() != self._query:
                self.search.set_text(self._query)
        self._update_search_hint()
        self._rebuild_list()

    # ------------------------------------------------------------------ Aktionen
    def _on_action_clicked(self, button, item):
        self.run_item(item, button)

    def _on_cmd_press(self, _widget, _event, item):
        self.run_item(item, None)
        return True

    def run_item(self, item, button=None):
        """Einziger Ausfuehrungspfad. START/TERMINAL oeffnen, COPY kopiert."""
        if item.get("blocked"):
            self.set_status("gesperrt: destruktiver Befehl – nicht ausgeführt",
                            warn=True)
            return
        if item.get("missing"):
            self.set_status("nicht verfügbar: %s fehlt"
                            % ", ".join(item["missing"]), warn=True)
            return

        etype = item.get("type", "COPY")
        name = item.get("name", "?")

        if etype == "COPY":
            text = item.get("copy_text") or item.get("command", "")
            if is_blocked(text):
                self.set_status("gesperrt: destruktiver Befehl", warn=True)
                return
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text, -1)
            clipboard.store()
            self._flash(button)
            self.set_status("kopiert: %s" % text)
            log("kopiert: %r" % text)
            return

        if etype == "START":
            argv = item.get("argv") or []
            if not argv or is_blocked(" ".join(argv)):
                self.set_status("gesperrt: ungültiges Kommando", warn=True)
                return
            ok, err = run_argv(argv)
            self._flash(button, ok)
            self.set_status("%s: %s" % ("gestartet" if ok else "FEHLER",
                                        " ".join(argv) if ok else err),
                            warn=not ok)
            return

        if etype == "TERMINAL":
            workdir = item.get("workdir")
            workdir = os.path.expanduser(workdir) if workdir else None
            if workdir and not os.path.isdir(workdir):
                workdir = os.path.expanduser("~")
            command = item.get("command") or ""
            if is_blocked(command):
                self.set_status("gesperrt: destruktiver Befehl", warn=True)
                return
            argv = terminal_argv(self.term_argv, workdir, command or None)
            if not argv:
                self.set_status("kein Terminal gefunden", warn=True)
                return
            ok, err = run_argv(argv)
            self._flash(button, ok)
            self.set_status("%s: %s" % ("Terminal" if ok else "FEHLER",
                                        command or workdir or "~"),
                            warn=not ok)
            return

        _ = name

    def _flash(self, button, ok=True, ms=ACTION_FEEDBACK_MS):
        if button is None:
            return
        if self._flash_timer is not None:
            GLib.source_remove(self._flash_timer)
            self._flash_timer = None
        old_label = button.get_label()
        ctx = button.get_style_context()
        ctx.add_class("ok")
        button.set_label("✓ OK" if ok else "✕")
        button.set_sensitive(False)
        button.queue_draw()

        def restore():
            if button.get_style_context() is None:
                return False
            ctx.remove_class("ok")
            button.set_label(old_label)
            button.set_sensitive(True)
            button.queue_draw()
            self._flash_timer = None
            return False

        self._flash_timer = GLib.timeout_add(ms, restore)

    # --------------------------------------------------------------- Favoriten
    def _on_star_press(self, _widget, _event, item):
        added = self.store.toggle_fav(item)
        self.store.save_state()
        self._rebuild_list()
        self.set_status("★ %s" % ("Favorit: %s" % item["name"] if added
                                  else "aus Favoriten entfernen"))
        return True

    # ------------------------------------------------------------------ Header
    def _on_header_press(self, _widget, event):
        if event.button == 3:
            self._show_menu(event)
            return True
        if event.button == 1:
            self._drag = [event.x_root, event.y_root,
                          self.get_position()[0], self.get_position()[1]]
        return True

    def _on_header_release(self, _widget, _event):
        if self._drag:
            self.store.state["x"], self.store.state["y"] = self.get_position()
            self.store.save_state()
        self._drag = None
        return False

    def _on_header_motion(self, _widget, event):
        if not self._drag or not (event.state & Gdk.ModifierType.BUTTON1_MASK):
            return False
        dx = int(event.x_root - self._drag[0])
        dy = int(event.y_root - self._drag[1])
        self.move(self._drag[2] + dx, self._drag[3] + dy)
        return True

    # -------------------------------------------------------------------- Grip
    def _on_grip_press(self, _widget, event):
        if event.button == 1:
            self._resize = [event.x_root, event.y_root,
                            self.get_size()[0], self.get_size()[1]]
        return True

    def _on_grip_motion(self, _widget, event):
        if not self._resize or not (event.state & Gdk.ModifierType.BUTTON1_MASK):
            return False
        dx = int(event.x_root - self._resize[0])
        dy = int(event.y_root - self._resize[1])
        self.resize(max(MIN_W, self._resize[2] + dx),
                    max(MIN_H, self._resize[3] + dy))
        return True

    def _on_grip_release(self, _widget, _event):
        if self._resize:
            w, h = self.get_size()
            self.store.state["width"], self.store.state["height"] = w, h
            self.store.save_state()
        self._resize = None
        return False

    # -------------------------------------------------------------------- Menue
    def _show_menu(self, event):
        menu = Gtk.Menu()
        menu.get_style_context().add_class("menu")

        def add(label, callback, radio=False, active=False):
            item = Gtk.MenuItem(label=label)
            if radio:
                item.set_draw_as_radio(True)
                item.set_active(active)
            item.connect("activate", callback)
            menu.append(item)

        add("Immer im Vordergrund", self._on_toggle_aot, True,
            bool(self.store.state.get("always_on_top")))
        add("Aktionen neu laden  (F5)", lambda *_: self.reload_commands())
        add("Aktionen bearbeiten …", self._on_edit)
        menu.append(Gtk.SeparatorMenuItem())
        add("Deck verbergen  (Strg+H)", lambda *_: self.hide())
        add("Position / Größe zurücksetzen", self._on_reset_geometry)
        menu.append(Gtk.SeparatorMenuItem())
        add("Beenden", lambda *_: self.quit())
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def _on_toggle_aot(self, item):
        value = self.set_on_top(bool(item.get_active()))
        self.set_status("Always-on-Top: %s" % ("AN" if value else "AUS"))

    def _on_edit(self, *_):
        """commands.json in einem Texteditor oeffnen (kein Befehl wird beruehrt)."""
        self.store.ensure_commands_file()
        exe = editor_command()
        if not exe:
            self.set_status("kein Texteditor – bitte %s bearbeiten"
                            % COMMANDS_FILE, warn=True)
            return
        try:
            subprocess.Popen([exe, COMMANDS_FILE],
                             cwd=os.path.dirname(COMMANDS_FILE))
            self.set_status("geöffnet: %s" % COMMANDS_FILE)
        except Exception as exc:
            self.set_status("Editor nicht startbar: %s" % exc, warn=True)

    def _on_reset_geometry(self, *_):
        st = self.store.state
        st.update({"x": 40, "y": 60, "width": 400, "height": 620})
        self.store.save_state()
        self.resize(st["width"], st["height"])
        self.move(st["x"], st["y"])
        self.set_status("Geometrie zurückgesetzt")

    # ------------------------------------------------------------------- Status
    def set_status(self, text, warn=False, sticky=True):
        self.status.set_label(text)
        ctx = self.status.get_style_context()
        ctx.remove_class("status")
        ctx.remove_class("status-warn")
        ctx.add_class("status-warn" if warn else "status")
        if self._status_timer is not None:
            GLib.source_remove(self._status_timer)
            self._status_timer = None
        if sticky:
            self._status_timer = GLib.timeout_add(STATUS_RESET_MS,
                                                 self._reset_status)

    def _reset_status(self):
        self._status_timer = None
        self._update_status()
        return False

    def _update_status(self):
        on_top = bool(self.store.state.get("always_on_top"))
        if self.store.load_error:
            self.set_status("commands.json: %s" % self.store.load_error,
                            warn=True, sticky=False)
        elif self._query.strip():
            n = sum(len(c) for _a, _b, _c, c in self._visible_groups())
            self.set_status("%d Treffer für » %s «" % (n, self._query.strip()),
                            sticky=False)
        else:
            cats = len({i["category"] for i in self._items})
            self.set_status("%d Aktionen · %d Kategorien · %d ★ · %d ssh"
                            % (len(self._items), cats,
                               len(self.store.state.get("favorites", [])),
                               len(self.store.ssh_hosts)), sticky=False)
        self.aot_label.set_label("▲ PIN" if on_top else "▽ NORMAL")
        self.pin_label.set_label("PIN" if on_top else "NORMAL")
        self.aot_label.set_tooltip_text(
            "Always-on-Top aktiv – Strg+T oder Rechtsklick zum Umschalten")

    # ----------------------------------------------------------------- Tastatur
    def _on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and key in ("f", "F"):
            self.search.grab_focus()
            self.search.select_region(0, -1)
            return True
        if ctrl and key in ("h", "H"):
            self.hide()
            return True
        if ctrl and key in ("q", "Q", "w", "W"):
            self.quit()
            return True
        if ctrl and key in ("t", "T"):
            value = self.set_on_top(not self.is_on_top())
            self.set_status("Always-on-Top: %s" % ("AN" if value else "AUS"))
            return True
        if key == "F5":
            self.reload_commands()
            self.set_status("Aktionen neu geladen")
            return True
        if key in ("Escape", "Esc") and self._query:
            self._set_query("")
            return True
        return False

    # --------------------------------------------------------------- Persistenz
    def _on_configure(self, _widget, _event):
        if not self.get_realized():
            return False
        x, y = self.get_position()
        w, h = self.get_size()
        self.store.state.update({"x": x, "y": y, "width": w, "height": h})
        return False

    def _clamp_to_screen(self):
        """Nicht teilweise aus dem Bildschirmbereich schieben."""
        try:
            display = Gdk.Display.get_default()
            monitor = (display.get_primary_monitor() if display
                       else None) or (display.get_monitor(0) if display else None)
            if monitor is None:
                return
            area = monitor.get_workarea()
        except Exception as exc:
            log("Workarea nicht abfragbar:", exc)
            return
        x, y = self.get_position()
        w, h = self.get_size()
        x = max(area.x, min(x, area.x + area.width - min(w, 140)))
        y = max(area.y, min(y, area.y + area.height - 60))
        self.move(x, y)

    def _on_delete(self, *_):
        self.quit()
        return True

    def is_on_top(self):
        try:
            return bool(self.get_property("keep-above"))
        except Exception:
            return bool(self.store.state.get("always_on_top", True))

    def set_on_top(self, value):
        value = bool(value)
        self.set_keep_above(value)
        self.store.state["always_on_top"] = value
        self.store.save_state()
        self._update_status()
        return value

    def quit(self):
        x, y = self.get_position()
        w, h = self.get_size()
        self.store.state.update({"x": x, "y": y, "width": w, "height": h})
        self.store.save_state()
        release_lock()
        Gtk.main_quit()


# ===========================================================================
#  Prozess / Zwischenablage
# ===========================================================================
def run_argv(argv):
    """Startet eine Anwendung ohne Shell."""
    try:
        subprocess.Popen(argv, close_fds=True)
        return True, ""
    except (OSError, ValueError) as exc:
        return False, str(exc)


# ===========================================================================
#  Instanz-Schutz
# ===========================================================================
def _read_lock():
    try:
        with open(LOCK_FILE, encoding="utf-8") as fh:
            return int(fh.read().strip())
    except Exception:
        return None


def instance_running():
    pid = _read_lock()
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def take_lock():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(LOCK_FILE, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except Exception as exc:
        log("Lock nicht schreibbar:", exc)


def release_lock():
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


def raise_existing():
    pid = _read_lock()
    if pid and shutil.which("wmctrl"):
        subprocess.run(["wmctrl", "-i", "-a", str(pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ===========================================================================
#  Selbsttest
# ===========================================================================
def selftest():
    ok = True

    def check(label, cond):
        nonlocal ok
        print("  %-46s %s" % (label, "OK" if cond else "FEHLER"))
        if not cond:
            ok = False

    print("Daily Deck Selbsttest")
    print("-" * 52)

    term = detect_terminal()
    check("Standard-Terminal erkannt: %s" % terminal_display(term), bool(term))

    store = Store()
    store.load_commands()
    items = store.build_items(term)
    check("commands.json lesbar / %d Eintraege" % len(items), bool(items))

    check("SSH-Hosts aus ~/.ssh/config: %d" % len(store.ssh_hosts), True)

    check("Blockliste: 'rm -rf /' gesperrt", is_blocked("rm -rf /"))
    check("Blockliste: 'sudo apt' gesperrt", is_blocked("sudo apt install x"))
    check("Blockliste: 'shutdown now' gesperrt", is_blocked("shutdown now"))
    check("Blockliste: 'ssh <SSH-ALIAS>' erlaubt",
          not is_blocked("ssh <SSH-ALIAS>"))
    check("Blockliste: 'ls -la' erlaubt", not is_blocked("ls -la"))
    check("Blockliste: 'neofetch' erlaubt", not is_blocked("neofetch"))
    check("Blockliste: 'cmatrix' erlaubt", not is_blocked("cmatrix"))
    check("kein aktiver Eintrag ist gesperrt",
          not [i for i in items if i["blocked"]])

    types = {i["type"] for i in items}
    check("Typen nur START/TERMINAL/COPY: %s" % sorted(types),
          types <= set(TYPE_INFO))

    check("theme.css vorhanden", os.path.exists(os.path.join(ASSETS,
                                                            "theme.css")))
    check("eigenes State-Verzeichnis (%s)" % STATE_DIR,
          STATE_DIR != os.path.join(CONFIG_DIR, "terminal-clipboard"))
    check("eigenes Autostart-Ziel",
          os.path.join(CONFIG_DIR, "autostart", "daily-deck.desktop")
          != os.path.join(CONFIG_DIR, "autostart", "command-deck.desktop"))

    print("-" * 52)
    print("Ergebnis: %s" % ("BESTANDEN" if ok else "FEHLGESCHLAGEN"))
    return 0 if ok else 1


# ===========================================================================
#  main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--selftest", action="store_true",
                        help="Konfiguration und Sicherheitsregeln pruefen")
    parser.add_argument("--raise", dest="raise_existing", action="store_true",
                        help="bereits laufende Instanz anheben")
    parser.add_argument("--print-config", action="store_true",
                        help="erkannte Befehle als Text ausgeben")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    if args.version:
        print("%s %s" % (APP_NAME, VERSION))
        return 0

    if args.selftest:
        return selftest()

    if args.print_config:
        store = Store()
        store.load_commands()
        term = detect_terminal()
        for item in store.build_items(term):
            miss = ("  FEHLT:%s" % ",".join(item["missing"])) if item["missing"] else ""
            blk = "  GESPERRT" if item["blocked"] else ""
            print("%-9s %-9s %-36s %s%s%s"
                  % (item["type"], item["category"], item["name"],
                     item.get("description", "")[:30], miss, blk))
        return 0

    if instance_running() and not args.raise_existing:
        raise_existing()
        return 0

    take_lock()
    store = Store()
    store.load_state()
    DailyDeck(store)
    Gtk.main()
    release_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
