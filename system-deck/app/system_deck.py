#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYSTEM DECK  ·  Wartungs-, Diagnose- & System-Control-Deck
==========================================================

Drittes Geschwister im Purple-Cyber-Desktop-Control-System:

    Command Deck   →  Entwicklerbefehle, Git, Build, Docker, Projekte
    Daily Deck     →  Alltag: Programme, Verzeichnisse, SSH, Medien
    System Deck    →  Wartung, Diagnose, Hardware, Netzwerk, Sicherheit

Gleiche Codebasis, gleiches Theme, gleiche Formensprache wie die beiden
Geschwister (GTK3 / python3-gi, Cairo-Glasflaeche, theme.css, state.json).

###############################################################################
#  SICHERHEITS- UND TRENNUNGS-GARANTIE
###############################################################################
#  1. Dieses Programm fasst das bestehende "Command Deck"
#     (~/TerminalCommandWidget, ~/.config/terminal-clipboard,
#      ~/.config/autostart/command-deck.desktop) NICHT an.
#     Ebenso wenig das "Daily Deck" (~/DailyDeck, ~/.config/daily-deck).
#     Eigenes Verzeichnis, eigener State-Ordner, eigener Autostart,
#     eigene Kopie des Themes. Fremde Dateien werden nur GELESEN.
#
#  2. Vier Aktionstypen, jeder auf dem Knopf BESCHRIFTET:
#        READ   → führt einen Lesebefehl aus und zeigt das Ergebnis im
#                  eigenen Ausgabefenster. Kein Shell, feste Argumentliste,
#                  Zeitlimit, Ausgabekürzung.
#        COPY   → kopiert Text in die Zwischenablage. Führt NICHTS aus.
#        TERM   → öffnet ein SICHTBARES Terminal mit dem Befehl.
#        ADMIN  → öffnet ein SICHTBARES Terminal mit sudo-Befehl, aber
#                  erst nach einem Bestätigungsdialog, der den Befehl
#                  wörtlich zeigt. Das Deck selbst führt nie sudo aus.
#     Es gibt keinen versteckten Ausführungspfad und kein Passwortfeld.
#
#  3. Blockliste: destruktive Befehle (rm -rf, mkfs, dd, shred, fdisk,
#     parted, shutdown, reboot, userdel, chmod 777, > /dev/sd, ...)
#     werden beim Laden der Konfiguration abgewiesen und sind gesperrt.
#     Zusätzlich werden nur Lesebefehle tatsächlich ausgeführt - und auch
#     nur über eine Argumentliste, nie über eine Shell.
#
#  4. Kritische Systemdienste (systemd-*, ssh, NetworkManager, display-manager,
#     cups, ...) sind für ADMIN-Aktionen gesperrt und lassen sich nur mit
#     TERM im Terminal aufrufen.
#
#  5. Es werden keine Passwörter gespeichert, kein SSH-Key gelesen oder
#     kopiert, kein Keyring angefasst.
#
#  6. Kein Zugriff auf Wallpaper, Cinnamon-Theme, Cairo-Dock, Panel oder
#     irgendeine andere Desktop-Konfiguration. Keine Netzwerkkommunikation,
#     keine Telemetrie, keine Cloud.
#
#  7. Das Deck arbeitet lokal und ressourcenschonend: alle Befehle haben
#     ein Zeitlimit, Ausgaben werden gekürzt, jede Zeile läuft in einem
#     Thread, damit die Oberfläche nie einfriert. Es gibt KEINE
#     Dauerabfrage: nur der Quick System Check wird nach einem Intervall
#     neu berechnet, und nur solange das Fenster sichtbar ist.
#
#  Selbsttest:  python3 system_deck.py --selftest
#  Audit:      python3 system_deck.py --audit
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
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

APP_NAME = "System Deck"
APP_ID = "system-deck"
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
LOG_FILE = os.path.join(STATE_DIR, "system-deck.log")

MIN_W, MIN_H = 340, 420
DEFAULT_W, DEFAULT_H = 400, 660
EDGE_MARGIN = 14

ACTION_FEEDBACK_MS = 1500
STATUS_RESET_MS = 3200

CHECK_REFRESH_S = 20          # nur solange das Fenster sichtbar ist
CHECK_CACHE_S = 30            # Cache, damit nichts doppelt läuft
CMD_TIMEOUT_S = 10
MAX_OUT_LINES = 500
MAX_OUT_BYTES = 90 * 1024
LOG_MAX_BYTES = 256 * 1024

# ------------------------------------------------------------------- Palette
# identisch zum Command Deck und zum Daily Deck (siehe assets/theme.css)
C_BG0 = (0x0B, 0x06, 0x12)
C_VIOLET_D = (0x6D, 0x28, 0xD9)
C_VIOLET = (0x8B, 0x5C, 0xF6)
C_NEON = (0xA8, 0x55, 0xF7)
C_NEON_LT = (0xC0, 0x84, 0xFC)

# Status -> (Kurztext, CSS-Klasse)
STATUS_INFO = {
    "OK":   ("OK", "st-ok"),
    "WARN": ("WARN", "st-warn"),
    "ERR":  ("ERR", "st-err"),
    "INFO": ("INFO", "st-info"),
    "IDLE": ("--", "st-idle"),
}

# Typ -> (Beschriftung auf dem Knopf, CSS-Klasse)
TYPE_INFO = {
    "READ":  ("READ",  "act-read"),
    "COPY":  ("COPY",  "act-copy"),
    "TERM":  ("TERM",  "act-terminal"),
    "ADMIN": ("ADMIN", "act-admin"),
}

DEFAULT_STATE = {
    "always_on_top": True,
    "opacity": 0.95,
    "x": -1,
    "y": -1,
    "width": DEFAULT_W,
    "height": DEFAULT_H,
}

# ------------------------------------------------------------- Blockliste
# BLOCKED gilt für alles, was das Deck selbst anfasst oder in ein Terminal
# legt. Ausnahme: bei "sudo": true + TYPE=TERM wird ausschließlich die
# sudo-Regel großzügig behandelt (Befehl landet im sichtbaren Terminal).
BLOCKED = [
    r"\brm\b\s+(-[a-z]*[rf]|.*--recursive)",
    r"\bmkfs\b", r"\bfdisk\b", r"\bparted\b", r"\bdd\b", r"\bshred\b",
    r":\(\)\s*\{", r"\bsudo\b", r"\bsu\s+-", r"^\s*(sudo\s+)?passwd\b",
    r"\buseradd\b", r"\buserdel\b", r"\busermod\b", r"\bchown\b",
    r"\bchmod\b\s+777",
    r"^\s*(sudo\s+)?(shutdown|reboot|poweroff|halt)\b", r"\binit\s+0",
    r"\bkill\s+-9\b", r"\bkillall\b",
    r"\bmv\b\s+/\w", r">\s*/dev/sd", r"\bcurl\b.*\|\s*(ba)?sh",
    r"\bwget\b.*\|\s*(ba)?sh", r"\bnc\b\s+-\w*e", r"\bhistory\s+-c\b",
    r"\bapt(-get)?\s+(purge|remove|autoremove)", r"\bapt(-get)?\s+install\b",
    r"\bapt(-get)?\s+(full-)?upgrade\b",
    r"\bufw\s+(allow|deny|delete|reset|enable|disable|reload)",
    r"\biptables\b.*(-F|--flush|-X|--delete-chain)",
    r"\btruncate\b", r"\bwipefs\b", r"\bmkswap\b",
]
BLOCKED_RE = [re.compile(p) for p in BLOCKED]
# MUTATIONS verändern Daten oder Pakete. Diese Liste lässt sich durch
# KEIN Flag des Eintrags aufheben - auch nicht durch "sudo": true.
MUTATION = [
    r"\brm\b", r"\bmkfs\b", r"\bdd\b", r"\bshred\b", r"\bfdisk\b",
    r"\bparted\b", r"\bwipefs\b", r"\bmkswap\b", r"\btruncate\b",
    r"\bapt(-get)?\s+(install|purge|remove|autoremove|upgrade|dist-upgrade)",
    r"\bapt(-get)?\s+(auto)?clean\b", r"\baptitude\b",
    r"\bufw\s+(allow|deny|delete|reset|enable|disable|reload|insert)",
    r"\biptables\b.*(-F|--flush|-X|--delete-chain|-A|--append|-I|--insert)",
    r"\bjournalctl\b.*--vacuum", r"\blogrotate\b", r"\bsystemctl\b.*--user\b",
    r"\bsystemctl\b.*\b(mask|unmask|enable|disable|preset)\b",
    r"\buserdel\b", r"\bgroupdel\b", r"\bkillall\b", r"\bkill\s+-9\b",
    r"\bshutdown\b|\breboot\b|\bpoweroff\b|\bhalt\b",
    r"\bgit\s+(push|reset|clean|checkout)", r"\bdocker\s+(rm|rmi|system\s+prune)",
]
MUTATION_RE = [re.compile(p, re.IGNORECASE) for p in MUTATION]

# Programme, die als argv[0] bei einem READ-Befehl niemals auftauchen dürfen:
# Shells, Rechte-Eskalation, indirekte Ausführung.
FORBIDDEN_ARGV0 = {
    "sh", "bash", "zsh", "ksh", "dash", "csh", "tcsh", "fish", "busybox",
    "env", "xargs", "nohup", "setsid", "eval", "exec", "su", "sudo", "doas",
    "pkexec", "gdb", "strace", "perl", "python", "python3", "ruby", "php",
    "nc", "ncat", "socat", "telnet", "awk",
}
SAFE_ARGV0_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
# find darf nur lesen: keine -exec / -execdir / -delete / -ok*-Varianten
FIND_DANGER = {"-exec", "-execdir", "-delete", "-ok", "-okdir"}


# Dienste, die das System Deck niemals per ADMIN anfasst
CRITICAL_UNITS = {
    "ssh", "sshd", "networking", "networkmanager", "network-manager",
    "display-manager", "cups", "cups-browsed", "cron", "crond",
    "dbus", "polkit", "accounts-daemon", "upower", "packagekit",
    "modemmanager", "bluetooth", "avahi-daemon", "apparmor",
    "systemd-logind", "systemd-journald", "systemd-udevd",
    "systemd-resolved", "getty@", "user@", "snapd", "fail2ban",
}

# Werkzeuge, die das Deck prüft (nicht installiert!)
TOOLS = [
    "systemctl", "journalctl", "df", "lsblk", "free", "ps", "ss", "ip",
    "sensors", "lspci", "lsusb", "nmcli", "ufw", "apt", "apt-get",
    "lscpu", "lsb_release", "hostnamectl", "uptime", "who", "last",
    "uname", "findmnt", "du", "pactl", "aplay", "smartctl", "nvme",
    "mokutil", "upower", "dmidecode", "pstree", "glxinfo", "nvidia-smi",
    "iostat", "vmstat", "powertop", "hdparm", "fwupdmgr", "git",
]

HIGHLIGHT_BG = "#3A1E63"
HIGHLIGHT_FG = "#F3E8FF"


# ===========================================================================
#  Hilfsfunktionen
# ===========================================================================
def log(*a):
    if os.environ.get("SYSTEM_DECK_DEBUG"):
        print("[system-deck]", *a, file=sys.stderr)


def internal_log(text):
    """Begrenztes internes Log. Niemals Passwörter, Keys oder Tokens."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_BYTES:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write("%s  %s\n" % (stamp, text[:500]))
    except Exception:
        pass


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
    """Wie im Command Deck: eigenes GdkWindow, aber above_child=False."""
    box = Gtk.EventBox()
    box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                   | Gdk.EventMask.BUTTON_RELEASE_MASK
                   | Gdk.EventMask.POINTER_MOTION_MASK)
    box.set_above_child(False)
    return box


def is_blocked(text):
    if not text:
        return False
    return any(rx.search(text) for rx in BLOCKED_RE)


def is_mutation(text):
    if not text:
        return False
    return any(rx.search(text) for rx in MUTATION_RE)


def is_critical_unit(unit):
    unit = (unit or "").strip().lower()
    if unit in {u.lower() for u in CRITICAL_UNITS}:
        return True
    return unit.startswith("systemd-")



def which_all():
    return {t: shutil.which(t) for t in TOOLS}


def human_bytes(value):
    """1234567 -> '1,2 GB' (deutsche Schreibweise, ohne Sprachabhängigkeit)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return ("%d %s" % (round(value), unit) if unit == "B"
                    else ("%.1f %s" % (value, unit)).replace(".", ","))
        value /= 1024.0
    return "?"


def have(tool):
    return shutil.which(tool) is not None


def trim_output(raw, timeout=False, rc=None, err=None):
    """Ausgabe begrenzen: max. Zeilen und Bytes, Hinweis anhängen."""
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else (raw or "")
    lines = text.splitlines()
    note = []
    if len(lines) > MAX_OUT_LINES:
        lines = lines[-MAX_OUT_LINES:]
        note.append("… Ausgabe gekürzt: nur die letzten %d Zeilen." % MAX_OUT_LINES)
    if len(text) > MAX_OUT_BYTES:
        text = "\n".join(lines)
        note.append("… Ausgabe war %d KB groß." % (len(text) // 1024))
    if timeout:
        note.append("⚠ Zeitüberschreitung nach %d s - Befehl abgebrochen."
                    % CMD_TIMEOUT_S)
    if rc not in (None, 0):
        note.append("⚠ Befehl endete mit Status %d." % rc)
    if err:
        note.append("⚠ %s" % err)
    if note:
        lines = lines + ["", "───"] + note
    return "\n".join(lines).rstrip() or "(keine Ausgabe)"


def run_argv(argv, timeout=CMD_TIMEOUT_S, cwd=None):
    """Führt eine Argumentliste aus - OHNE Shell. Kein sudo, kein rm.

    Die Umgebung wird GEERBT (nicht Minimalsatz), damit Werkzeuge mit
    Session-Bezug funktionieren: pactl/systemctl --user/gsettings brauchen
    DBUS_SESSION_BUS_ADDRESS, XDG_RUNTIME_DIR und XAUTHORITY.
    Fest gesetzt werden nur Locale, Terminal-Typ und Spaltenbreite.

    Rückgabe: (returncode, stdout+stderr als str, timed_out, fehlertext)
    """
    env = dict(os.environ)
    env.update({
        "LANG": env.get("LANG") or "C.UTF-8",
        "LC_ALL": env.get("LC_ALL") or "C.UTF-8",
        "TERM": "dumb",
        "COLUMNS": "200",
        "GREP_COLORS": "",
    })
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, env=env, cwd=cwd,
            close_fds=True, start_new_session=True)
    except FileNotFoundError:
        return 127, "", False, "Programm %r ist nicht installiert." % argv[0]
    except (OSError, ValueError) as exc:
        return 126, "", False, str(exc)
    try:
        raw, _ = proc.communicate(timeout=timeout)
        return proc.returncode, raw or b"", False, ""
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            raw, _ = proc.communicate(timeout=3)
        except Exception:
            raw = b""
        return None, raw or b"", True, ""


def _kill_tree(proc):
    try:
        os.killpg(os.getpgid(proc.pid), 9)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ===========================================================================
#  Terminal-Erkennung  (nichts fest verdrahtet, identisch zum Daily Deck)
# ===========================================================================
def detect_terminal():
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
    """Baut die Argumentliste für das erkannte Terminal."""
    if not term_argv:
        return []
    exe = os.path.basename(term_argv[0])
    argv = list(term_argv)
    finish = ('; printf "\\n[System Deck] Befehl im Terminal ausgeführt.'
              ' Fenster zum Schließen einfach schließen."; ')

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
#  Datenhaltung
# ===========================================================================
class Store(object):
    """commands.json (Befehle) und state.json (Geometrie)."""

    def __init__(self, commands_file=COMMANDS_FILE, state_file=STATE_FILE):
        self.commands_file = commands_file
        self.state_file = state_file
        self.config = {}
        self.state = dict(DEFAULT_STATE)
        self.state["positioned"] = False
        self.load_error = None

    def ensure_dirs(self):
        os.makedirs(STATE_DIR, exist_ok=True)

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
        self.state["positioned"] = False
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                if isinstance(loaded, dict):
                    for key, value in loaded.items():
                        if key in DEFAULT_STATE or key == "positioned":
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

    # ------------------------------------------------------------------- Items
    @staticmethod
    def key_of(item):
        return "%s/%s" % (item.get("category", "?"), item.get("key_name", "?"))

    def build_items(self, term_argv):
        items = []
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
                    entry = {"name": entry, "type": "COPY", "cmd": entry}
                if not isinstance(entry, dict) or entry.get("enabled") is False:
                    continue
                entry = dict(entry)
                entry["category"] = cat_name
                entry["category_icon"] = cat_icon
                entry["key_name"] = entry.get("key_name") or entry.get("name", "?")
                entry["order"] = order
                entry["description"] = entry.get("description", "")
                entry["cmd"] = entry.get("cmd", "") or ""
                if entry.get("type") not in TYPE_INFO:
                    entry["type"] = "READ"

                probe = " ".join([entry.get("cmd") or ""]
                                 + [str(a) for a in (entry.get("argv") or [])])
                if entry["type"] == "COPY":
                    # Kopieren ist keine Aktion am System: der Text landet nur
                    # in der Zwischenablage. Verändernde Befehle werden hier
                    # trotzdem gekennzeichnet, aber nicht gesperrt.
                    entry["blocked"] = False
                    entry["mutating"] = is_mutation(probe)
                elif is_mutation(probe):
                    # Mutationen (Daten/Pakete/Dienste veraendern) sind IMMER
                    # gesperrt - unabhaengig von jedem Flag des Eintrags.
                    entry["blocked"] = True
                    entry["block_reason"] = ("verändernde Aktion - nur manuell "
                                             "im Terminal")
                else:
                    entry["block_reason"] = "destruktiver Befehl"
                    if entry.get("sudo") and entry["type"] == "TERM":
                        #Einzige Ausnahme: sudo bei reinen Lesebefehlen, die
                        # nur im sichtbaren Terminal landen und dort bestaetigt
                        # werden. Das Deck fuehrt sie nie selbst aus.
                        entry["blocked"] = any(
                            rx.search(probe) for rx in BLOCKED_RE
                            if rx.pattern != r"\bsudo\b")
                    elif entry["type"] == "ADMIN":
                        # Bei ADMIN ist sudo inherent und immer bestaetigt.
                        stripped = re.sub(r"^\s*sudo\s+", "", probe)
                        entry["blocked"] = is_blocked(stripped)
                    else:
                        entry["blocked"] = is_blocked(probe)

                missing = [r for r in (entry.get("requires") or [])
                           if shutil.which(r) is None]
                if entry["type"] == "TERM" and not term_argv:
                    missing.append("Terminal")
                if entry["type"] == "READ":
                    argv = [str(a) for a in (entry.get("argv") or [])]
                    if not argv:
                        missing.append("argv in commands.json")
                    else:
                        head = os.path.basename(argv[0])
                        bad = (head.lower() in FORBIDDEN_ARGV0
                               or not SAFE_ARGV0_RE.match(head))
                        if head.lower() == "find" and FIND_DANGER & set(argv):
                            bad = True
                            entry["block_reason"] = "find mit -exec/-delete"
                        if bad:
                            entry["blocked"] = True
                            entry.setdefault(
                                "block_reason",
                                "argv[0] ist keine erlaubte Lese-Programmdatei")
                        elif not shutil.which(head):
                            missing.append(head)
                if entry["type"] == "ADMIN":
                    unit = entry.get("unit") or ""
                    if unit and is_critical_unit(unit):
                        entry["critical"] = True
                entry["missing"] = missing
                items.append(entry)
        return items

    def categories(self):
        cats = []
        categories = self.config.get("categories") or {}
        for name, cat in sorted(categories.items(),
                                key=lambda kv: (kv[1].get("order", 99)
                                                if isinstance(kv[1], dict) else 99)):
            if not isinstance(cat, dict) or cat.get("enabled") is False:
                continue
            cats.append((name, cat.get("icon", "◈")))
        return cats


# ===========================================================================
#  Geometrie: einmal berechnen (unten rechts), danach nur noch speichern
# ===========================================================================
def default_geometry(width=DEFAULT_W, height=DEFAULT_H):
    """BOTTOM-RIGHT des primären Monitors, mit Sicherheitsabstand.

    Wird nur benutzt, wenn noch keine Position gespeichert ist.
    Berücksichtigt die Arbeitsfläche (Panel/Dock-Reserven).
    """
    geom = {"x": -1, "y": -1, "width": width, "height": height}
    try:
        import gi
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk as _Gdk
        display = _Gdk.Display.get_default()
        if display is None:
            return geom
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        if monitor is None:
            return geom
        area = monitor.get_workarea()
        x = area.x + area.width - width - EDGE_MARGIN
        y = area.y + area.height - height - EDGE_MARGIN
        geom["x"] = max(area.x, x)
        geom["y"] = max(area.y, y)
    except Exception as exc:
        log("Arbeitsfläche nicht abfragbar:", exc)
    return geom


# ===========================================================================
#  Quick System Check  (nur lesende Prüfungen, mit Cache)
# ===========================================================================
class QuickCheck(object):
    """Ermittelt die Statuswerte dynamisch. Liest nur, startet nichts."""

    def __init__(self):
        self.cache = {}
        self.lock = threading.Lock()

    # -------------------------------------------------------------- Helfer
    def _cached(self, key, fn, ttl=CHECK_CACHE_S):
        now = time.time()
        with self.lock:
            hit = self.cache.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
        value = fn()
        with self.lock:
            self.cache[key] = (now, value)
        return value

    def _read(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""

    # -------------------------------------------------------------- Prüfungen
    def meminfo(self):
        out = {}
        for line in self._read("/proc/meminfo").splitlines():
            m = re.match(r"^(\w+):\s+(\d+)", line)
            if m:
                out[m.group(1)] = int(m.group(2)) * 1024
        return out

    def system(self):
        try:
            pretty = ""
            for line in self._read("/etc/os-release").splitlines():
                if line.startswith("PRETTY_NAME="):
                    pretty = line.split("=", 1)[1].strip().strip('"')
            short = re.sub(r"^([A-Za-z ]+?)\s+[\d.]+.*$", r"\1",
                           (pretty or "Linux").split("(")[0].strip())
            short = short.replace("Linux", "").strip() or "Linux"
            desktop = "Wayland" if os.environ.get("WAYLAND_DISPLAY") else "Xorg"
            if "Mint" in pretty or "Cinnamon" in pretty:
                desktop = "Cinnamon"
            return "OK", "%s · %s" % (short[:14], desktop)
        except Exception as exc:
            return "ERR", "Systeminfo: %s" % exc

    def cpu(self):
        try:
            load = os.getloadavg()[0]
            cores = os.cpu_count() or 1
            pct = load / cores * 100
            if pct >= 95:
                st = "ERR"
            elif pct >= 75:
                st = "WARN"
            else:
                st = "OK"
            return st, "load %.2f / %d" % (load, cores)
        except Exception:
            return "INFO", "nicht verfügbar"

    def ram(self):
        m = self.meminfo()
        total = m.get("MemTotal", 0)
        avail = m.get("MemAvailable", m.get("MemFree", 0))
        if not total:
            return "INFO", "nicht verfügbar"
        free_pct = avail / total * 100
        swap_total = m.get("SwapTotal", 0)
        swap_used = swap_total - m.get("SwapFree", 0)
        text = "%d%% frei" % round(free_pct)
        self._ram_extra = ""
        if swap_total:
            self._ram_extra = "swap %d%% von %s" % (
                round(swap_used / swap_total * 100), human_bytes(swap_total))
        if free_pct < 5:
            st = "ERR"
        elif free_pct < 15:
            st = "WARN"
        else:
            st = "OK"
        return st, text

    def storage(self):
        worst, worst_mnt = 0.0, ""
        skip = ("/proc", "/sys", "/dev", "/run", "/snap", "/var/lib/docker",
                "/var/lib/flatpak", "tmpfs", "overlay", "squashfs", "/boot/efi")
        for line in self._read("/proc/mounts").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            mnt, fstype = parts[1], parts[2]
            if any(mnt.startswith(s) for s in skip):
                continue
            try:
                st = os.statvfs(mnt)
                if st.f_blocks == 0:
                    continue
                used = (st.f_blocks - st.f_bfree) / st.f_blocks * 100
            except OSError:
                continue
            if used > worst:
                worst, worst_mnt = used, mnt
        if not worst_mnt:
            return "INFO", "keine_partition"
        if worst >= 92:
            st = "ERR"
        elif worst >= 82:
            st = "WARN"
        else:
            st = "OK"
        return st, "%s %d%%" % (os.path.basename(worst_mnt) or worst_mnt,
                                round(worst))

    def network(self):
        up = []
        try:
            for name in os.listdir("/sys/class/net"):
                try:
                    state = self._read("/sys/class/net/%s/operstate" % name).strip()
                except OSError:
                    continue
                if state == "up":
                    up.append(name)
        except OSError:
            pass
        if not up:
            return "ERR", "kein Interface up"
        default_iface = ""
        try:
            with open("/proc/net/route", "r", encoding="utf-8") as fh:
                next(fh, None)
                for line in fh:
                    f = line.split()
                    if len(f) > 2 and f[1] == "00000000":
                        default_iface = f[0]
                        break
        except OSError:
            pass
        if default_iface and default_iface in up:
            return "OK", default_iface
        return "WARN", "%d up, kein gw" % len(up)

    def services(self):
        if not have("systemctl"):
            return "INFO", "systemctl fehlt"
        rc, out, _to, _e = run_argv(["systemctl", "--failed", "--no-legend",
                                     "--plain", "--no-pager"], timeout=6)
        if rc in (None, 126, 127):
            return "INFO", "nicht abfragbar"
        failed = [l for l in out.decode("utf-8", "replace").splitlines() if l.strip()]
        if rc != 0 and not failed:
            return "INFO", "nicht abfragbar"
        if failed:
            return "ERR", "%d fehlgeschlagen" % len(failed)
        return "OK", "keine Fehler"

    def updates(self):
        marker = "/var/lib/update-notifier/updates-available"
        if os.path.exists(marker):
            try:
                with open(marker, "r", encoding="utf-8") as fh:
                    n = int(fh.read().strip() or 0)
                return ("INFO", "%d verfügbar" % n) if n else ("OK", "aktuell")
            except (OSError, ValueError):
                pass
        # Mint 22 hat keinen update-notifier-Zähler: Alter der Paketlisten
        lists = "/var/lib/apt/lists"
        try:
            newest = max(
                os.path.getmtime(os.path.join(lists, n))
                for n in os.listdir(lists)
                if os.path.isfile(os.path.join(lists, n)))
            age_h = (time.time() - newest) / 3600.0
        except (OSError, ValueError):
            return "INFO", "nicht prüfbar"
        if age_h < 72:
            return "OK", "Index %.0f h alt" % age_h
        return "INFO", "Index %.1f d alt" % (age_h / 24.0)

    def temperature(self):
        if not have("sensors"):
            return "INFO", "lm-sensors fehlt"
        rc, out, _to, _e = run_argv(["sensors", "-u"], timeout=6)
        if rc in (None, 126, 127):
            return "INFO", "nicht lesbar"
        temps = []
        for m in re.finditer(r"temp\d+_input:\s*([0-9]+)", out.decode("utf-8", "replace")):
            temps.append(int(m.group(1)) / 1000.0)
        if not temps:
            return "INFO", "keine Sensoren"
        hottest = max(temps)
        if hottest >= 88:
            st = "ERR"
        elif hottest >= 78:
            st = "WARN"
        else:
            st = "OK"
        return st, "max %.0f°C" % hottest

    def firewall(self):
        if not have("ufw"):
            if have("firewalld"):
                return "INFO", "firewalld"
            return "INFO", "kein ufw"
        rc, out, _to, _e = run_argv(["ufw", "status"], timeout=6)
        text = out.decode("utf-8", "replace")
        low = text.lower()
        if "you need to be root" in low or "must be root" in low:
            # ohne Root nicht lesbar → Dienststatus als Ersatz
            if have("systemctl"):
                rc2, out2, _t, _e = run_argv(["systemctl", "is-active", "ufw"],
                                              timeout=5)
                state = out2.decode("utf-8", "replace").strip()
                if state == "active":
                    return "OK", "aktiv (Root nötig für Details)"
                return "INFO", "inaktiv"
            return "INFO", "Root nötig"
        if rc not in (None, 0):
            return "INFO", "nicht abfragbar"
        if "status: active" in low:
            return "OK", "aktiv"
        if "status: inactive" in low:
            return "WARN", "inaktiv"
        return "INFO", "unbekannt"

    # ------------------------------------------------------------------ Alle
    def all(self):
        return [
            ("SYSTEM", "System", lambda: self.system()),
            ("CPU", "CPU", lambda: self.cpu()),
            ("RAM", "RAM", lambda: self.ram()),
            ("STORAGE", "Storage", lambda: self.storage()),
            ("NETWORK", "Netzwerk", lambda: self.network()),
            ("SERVICES", "Dienste", lambda: self.services()),
            ("UPDATES", "Updates", lambda: self.updates()),
            ("TEMPERATUR", "Temperatur", lambda: self.temperature()),
            ("FIREWALL", "Firewall", lambda: self.firewall()),
        ]


QC = QuickCheck()


# ===========================================================================
#  Hintergrund  (identisch zu Command Deck / Daily Deck)
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
    """Glasfläche, Verlauf, Rand, Eckakzente und Scanlines - alles mit Cairo."""

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

        cr.set_source_rgba(*hexa(C_VIOLET, 0.028 * a))
        yy = 0.0
        while yy < h:
            cr.rectangle(0, yy, w, 1.0)
            yy += 3.0
        cr.fill()
        cr.restore()

        cr.set_source_rgba(*hexa(C_VIOLET, 0.45 * a))
        cr.set_line_width(1.0)
        rounded(cr, x + 0.5, y + 0.5, ww - 1.0, hh - 1.0, r - 0.5)
        cr.stroke()

        cr.set_source_rgba(*hexa(C_NEON_LT, 0.70 * a))
        cr.set_line_width(1.6)
        for cx, cy in ((x + r, y + r), (x + ww - r, y + r),
                       (x + r, y + hh - r), (x + ww - r, y + hh - r)):
            cr.arc(cx, cy, 5.0, 0, 2 * 3.14159)
            cr.stroke()

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
#  Asynchroner Runner  (keine blockierende Oberfläche)
# ===========================================================================
class AsyncRunner(object):
    def __init__(self, handler):
        self._pool = ThreadPoolExecutor(max_workers=2)
        self._handler = handler
        self._lock = threading.Lock()
        self._seq = 0
        self._seen = {}
        self._busy = set()

    def submit(self, token, fn):
        with self._lock:
            self._seq += 1
            sid = self._seq
            self._busy.add(token)

        def work():
            try:
                res = fn()
            except Exception as exc:            # niemals Exceptions nach außen
                res = (127, "", False, "Interner Fehler: %s" % exc)
            GLib.idle_add(self._deliver, token, sid, res)

        self._pool.submit(work)

    def _deliver(self, token, sid, res):
        with self._lock:
            if self._seen.get(token, 0) > sid:
                self._busy.discard(token)
                return False
            self._seen[token] = sid
            self._busy.discard(token)
        self._handler(token, res)
        return False

    def is_busy(self, token):
        with self._lock:
            return token in self._busy

    def forget(self, token):
        with self._lock:
            self._busy.discard(token)


# ===========================================================================
#  Widget
# ===========================================================================
class SystemDeck(Gtk.Window):

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
        self._index = {}
        self._category = None
        self._out_token = None
        self._out_text = ""
        self._check_timer = None
        self._check_busy = False
        self._pending_handlers = {}
        self.runner = AsyncRunner(self._on_async_result)

        st = store.state
        if not st.get("positioned") or st.get("x", -1) < 0:
            geo = default_geometry(int(st.get("width", DEFAULT_W)),
                                   int(st.get("height", DEFAULT_H)))
            st.update({"x": geo["x"], "y": geo["y"],
                       "width": geo["width"], "height": geo["height"],
                       "positioned": True})
            store.save_state(st)

        self.set_title(APP_NAME)
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(bool(st.get("always_on_top", True)))
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_gravity(Gdk.Gravity.NORTH_WEST)
        self.set_default_size(int(st.get("width", DEFAULT_W)),
                              int(st.get("height", DEFAULT_H)))
        self.set_size_request(MIN_W, MIN_H)
        self.move(int(st.get("x", 40)), int(st.get("y", 60)))

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
        self.connect("map-event", self._on_map)
        self.connect("unmap-event", self._on_unmap)

    # ------------------------------------------------------------------ Styling
    def _apply_style(self):
        provider = Gtk.CssProvider()
        path = os.path.join(ASSETS, "theme.css")
        try:
            provider.load_from_path(path)
        except Exception as exc:
            print("[system-deck] theme.css nicht ladbar: %s" % exc, file=sys.stderr)
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
        outer.pack_start(self._build_check(), False, False, 0)
        outer.pack_start(self._build_searchbar(), False, False, 0)
        outer.pack_start(self._build_catgrid(), False, False, 0)

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

        outer.pack_end(self._build_output(), False, False, 0)
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
        title = Gtk.Label(label="SYSTEM DECK")
        title.get_style_context().add_class("title")
        sub = Gtk.Label(label="MAINTENANCE // DIAGNOSTICS")
        sub.get_style_context().add_class("subtitle")
        col.pack_start(title, False, False, 0)
        col.pack_start(sub, False, False, 0)
        hb.pack_start(col, True, True, 0)

        self.health = Gtk.Label(label="●")
        self.health.get_style_context().add_class("st-idle")
        self.health.set_valign(Gtk.Align.CENTER)
        self.health.set_tooltip_text("Gesamtzustand des Quick System Check")
        hb.pack_end(self.health, False, False, 0)

        self.pin_label = Gtk.Label(label="PIN")
        self.pin_label.get_style_context().add_class("hint")
        self.pin_label.set_valign(Gtk.Align.CENTER)
        hb.pack_end(self.pin_label, False, False, 0)

        self.header.connect("button-press-event", self._on_header_press)
        self.header.connect("button-release-event", self._on_header_release)
        self.header.connect("motion-notify-event", self._on_header_motion)
        self.header.set_tooltip_text("Ziehen = verschieben  ·  Rechtsklick = Menü")
        return self.header

    # ---------------------------------------------------- Quick System Check
    def _build_check(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(1)
        box.set_margin_start(7)
        box.set_margin_end(6)
        box.set_margin_top(5)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        lbl = Gtk.Label(label="QUICK SYSTEM CHECK")
        lbl.get_style_context().add_class("check-title")
        lbl.set_xalign(0.0)
        head.pack_start(lbl, True, True, 0)

        self.check_stamp = Gtk.Label(label="")
        self.check_stamp.get_style_context().add_class("hint")
        head.pack_end(self.check_stamp, False, False, 0)

        self.refresh_btn = Gtk.Button(label="↻")
        self.refresh_btn.get_style_context().add_class("clear")
        self.refresh_btn.set_valign(Gtk.Align.CENTER)
        self.refresh_btn.set_tooltip_text("Quick System Check neu berechnen (F5)")
        self.refresh_btn.connect("clicked", lambda *_: self.refresh_check(True))
        head.pack_end(self.refresh_btn, False, False, 0)
        box.pack_start(head, False, False, 0)

        grid_outer = Gtk.Box()
        grid_outer.get_style_context().add_class("check")
        self.check_grid = Gtk.Grid(column_spacing=4, row_spacing=2)
        grid_outer.add(self.check_grid)
        box.pack_start(grid_outer, False, False, 0)

        legend = Gtk.Label(label="READ = nur lesen · COPY = kopiert · "
                                "TERM = Terminal · ADMIN = Bestätigung")
        legend.get_style_context().add_class("legend")
        legend.set_xalign(0.0)
        box.pack_start(legend, False, False, 0)
        return box

    def _check_cells(self):
        return [(w, key) for w, key, _f in QC.all()]

    def refresh_check(self, force=False, silent=False):
        if self._check_busy and not force:
            return
        self._check_busy = True
        if force:
            QC.cache.clear()
        checks = QC.all()

        def work():
            out = []
            for key, label, fn in checks:
                try:
                    status, text = fn()
                except Exception as exc:
                    status, text = "INFO", "Fehler: %s" % exc
                out.append((key, label, status, text))
            return out

        token = "quickcheck"

        def handler(_token, res):
            self._check_busy = False
            rc, payload, _to, err = res
            if rc == 0:
                self._render_check(payload)
            else:
                self.set_status("Systemcheck: %s" % (err or "unbekannt"), True)

        self._pending_handlers[token] = handler
        self.runner.submit(token, lambda: (0, work(), False, ""))

    def _render_check(self, results):
        for child in self.check_grid.get_children():
            self.check_grid.remove(child)
        worst = "OK"
        for idx, (key, label, status, text) in enumerate(results):
            worst = _worst_status(worst, status)
            cell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
            cell.get_style_context().add_class("check-item")
            cell.set_hexpand(True)

            dot = Gtk.Label(label="%s" % STATUS_INFO[status][0])
            dot.get_style_context().add_class(STATUS_INFO[status][1])
            dot.set_valign(Gtk.Align.CENTER)
            cell.pack_start(dot, False, False, 0)

            name = Gtk.Label(label=label.upper())
            name.get_style_context().add_class("check-name")
            name.set_valign(Gtk.Align.CENTER)
            cell.pack_start(name, False, False, 0)

            val = Gtk.Label(label=text)
            val.get_style_context().add_class("check-val")
            val.get_style_context().add_class(STATUS_INFO[status][1])
            val.set_valign(Gtk.Align.CENTER)
            val.set_ellipsize(Pango.EllipsizeMode.END)
            val.set_hexpand(True)
            val.set_xalign(1.0)
            cell.pack_end(val, True, True, 0)

            cell.set_tooltip_text("%s: %s\nKlick = zugehörigen Befehl ausführen"
                                  % (label, text))
            clickable = event_box()
            clickable.add(cell)
            clickable.connect("button-press-event", self._on_check_press, key)
            self.check_grid.attach(clickable, idx % 3, idx // 3, 1, 1)
        # Wichtig: diese Felder entstehen NACH show_all() des Fensters.
        self.check_grid.show_all()

        ctx = self.health.get_style_context()
        for cls in ("st-ok", "st-warn", "st-err", "st-info", "st-idle"):
            ctx.remove_class(cls)
        ctx.add_class(STATUS_INFO[worst][1])
        self.health.set_tooltip_text("Gesamtzustand: %s" % worst)
        self.check_stamp.set_label(time.strftime("%H:%M:%S"))

    def _on_check_press(self, _widget, _event, key):
        entry = self._index.get("CHECK/" + key.lower())
        if entry is None:
            for item in self._items:
                if item.get("check") == key:
                    entry = item
                    break
        if entry is None:
            self.set_status("kein Befehl für %s hinterlegt" % key, warn=True)
            return True
        self.run_read(entry, None)
        return True

    def _build_searchbar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        box.set_border_width(1)
        box.set_margin_start(8)
        box.set_margin_end(7)
        box.set_margin_top(5)
        box.set_margin_bottom(3)

        ico = Gtk.Label(label="❯")
        ico.get_style_context().add_class("glyph")
        ico.set_valign(Gtk.Align.CENTER)
        box.pack_start(ico, False, False, 0)

        stack = Gtk.Overlay()
        self.search = Gtk.Entry()
        self.search.get_style_context().add_class("search")
        self.search.set_hexpand(True)
        self.search.connect("changed", self._on_search_changed)
        self.search.connect("key-press-event", self._on_search_key)
        stack.add(self.search)

        self.search_hint = Gtk.Label(label="Search categories & commands...")
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
        box.pack_end(self.clear_btn, False, False, 0)
        return box

    def _on_hint_press(self, _widget, _event):
        self.search.grab_focus()
        return True

    def _update_search_hint(self):
        empty = not self.search.get_text()
        self.search_hint_event.set_visible(empty)
        self.clear_btn.set_sensitive(not empty)

    # ------------------------------------------------------- Kategorie-Raster
    def _build_catgrid(self):
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        wrap.set_border_width(1)
        wrap.set_margin_start(7)
        wrap.set_margin_end(6)
        wrap.set_margin_bottom(4)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        lbl = Gtk.Label(label="SYSTEM TOOLS")
        lbl.get_style_context().add_class("check-title")
        lbl.set_xalign(0.0)
        head.pack_start(lbl, True, True, 0)
        self.cat_count = Gtk.Label(label="")
        self.cat_count.get_style_context().add_class("hint")
        head.pack_end(self.cat_count, False, False, 0)
        wrap.pack_start(head, False, False, 0)

        self.grid = Gtk.Grid(column_spacing=4, row_spacing=3)
        self.grid.set_column_homogeneous(True)
        wrap.pack_start(self.grid, False, False, 0)
        self._cat_buttons = {}
        return wrap

    CAT_COLUMNS = 4

    def _render_catgrid(self):
        for child in self.grid.get_children():
            self.grid.remove(child)
        self._cat_buttons = {}
        cats = self.store.categories()
        for idx, (name, icon) in enumerate(cats):
            # Kein Emoji im Raster: die Buttons bleiben so niedrig und
            # monospace wie beim Command Deck. Das Icon steht in der Liste.
            btn = Gtk.Button(label=name)
            btn.get_style_context().add_class("catbtn")
            if name == self._category:
                btn.get_style_context().add_class("on")
            btn.set_tooltip_text("Kategorie %s anzeigen" % name)
            btn.connect("clicked", self._on_cat_clicked, name)
            self.grid.attach(btn, idx % self.CAT_COLUMNS,
                             idx // self.CAT_COLUMNS, 1, 1)
            self._cat_buttons[name] = btn
        self.cat_count.set_label("%d Kategorien" % len(cats))
        self.grid.show_all()

    def _on_cat_clicked(self, _button, name):
        self._category = None if self._category == name else name
        self._render_catgrid()
        self._rebuild_list()

    # ------------------------------------------------------------------ Befehle
    def reload_commands(self):
        self.store.load_commands()
        self._items = self.store.build_items(self.term_argv)
        self._index = {}
        for item in self._items:
            self._index[self.store.key_of(item)] = item
            if item.get("check"):
                self._index.setdefault("CHECK/" + str(item["check"]).lower(), item)
        if self._category and self._category not in [c[0]
                                                     for c in self.store.categories()]:
            self._category = None
        self._render_catgrid()
        self._rebuild_list()
        self._update_status()

    def _visible_items(self):
        q = self._query.strip().lower()
        out = []
        for item in self._items:
            if self._category and item["category"] != self._category:
                continue
            hay = ("%s %s %s" % (item.get("name", ""),
                                 item.get("description", ""),
                                 item.get("category", ""))).lower()
            if q and q not in hay:
                continue
            out.append(item)
        return out

    def _rebuild_list(self):
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        self._rows = []

        items = self._visible_items()
        if not items:
            empty = Gtk.Label(label="keine Treffer für\n» %s «" % self._query)
            empty.get_style_context().add_class("hint")
            empty.set_justify(Gtk.Justification.CENTER)
            empty.set_margin_top(18)
            empty.set_margin_bottom(18)
            self.listbox.pack_start(empty, False, False, 0)
            self.listbox.show_all()
            self._update_status()
            return

        current_cat = None
        for item in items:
            if item["category"] != current_cat:
                current_cat = item["category"]
                head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                head.get_style_context().add_class("cat")
                lbl = Gtk.Label(label="%s  %s" % (item.get("category_icon", "◈"),
                                                  current_cat.upper()))
                lbl.get_style_context().add_class("cat-label")
                lbl.set_xalign(0.0)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                head.pack_start(lbl, True, True, 0)
                cnt = Gtk.Label(label="%02d"
                                % sum(1 for i in items
                                      if i["category"] == current_cat))
                cnt.get_style_context().add_class("cat-count")
                head.pack_end(cnt, False, False, 0)
                self.listbox.pack_start(head, False, False, 0)
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
        if item.get("type") == "ADMIN":
            row.get_style_context().add_class("row-danger")
        row.set_tooltip_text(self._tooltip(item))

        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        row.add(hb)

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

        # zweiter Knopf: COPY ist immer getrennt von RUN/READ/TERM/ADMIN
        if item["type"] != "COPY":
            copy_btn = Gtk.Button(label="COPY")
            cctx = copy_btn.get_style_context()
            cctx.add_class("act")
            cctx.add_class("act-copy")
            if item.get("blocked"):
                cctx.add_class("act-blocked")
            copy_btn.set_tooltip_text(
                "Kopiert den Befehl - führt nichts aus")
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.connect("clicked", self._on_copy_clicked, item)
            hb.pack_end(copy_btn, False, False, 0)
        return row

    def _tooltip(self, item):
        lines = [item.get("description") or item.get("name", ""),
                 "%s  ·  %s" % (item["type"], item.get("category", ""))]
        if item.get("cmd"):
            lines.append("Befehl: %s" % item["cmd"])
        if item.get("argv"):
            lines.append("argv: %s" % " ".join(str(a) for a in item["argv"]))
        if item["type"] == "TERM":
            lines.append("Terminal: %s" % terminal_display(self.term_argv))
        if item["type"] == "ADMIN":
            lines.append("benötigt Root - wird im Terminal bestätigt")
        if item.get("blocked"):
            lines.append("GESPERRT · destruktiver Befehl - nicht ausführbar")
        if item.get("critical"):
            lines.append("KRITISCHER DIENST · vom System Deck gesperrt")
        for miss in item.get("missing") or []:
            lines.append("NICHT VERFÜGBAR · %s fehlt" % miss)
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
        if key in ("Return", "KP_Enter") and self._rows:
            self._on_action_clicked(None, self._rows[0][1])
            return True
        return False

    def _set_query(self, text, from_entry=False):
        self._query = text or ""
        if not from_entry:
            if self.search.get_text() != self._query:
                self.search.set_text(self._query)
        self._update_search_hint()
        self._rebuild_list()

    # --------------------------------------------------------- Ausgabe-Fenster
    def _build_output(self):
        self.output_revealer = Gtk.Revealer()
        try:
            self.output_revealer.set_transition_type(Gtk.RevealTransitionType.SLIDE_DOWN)
            self.output_revealer.set_transition_duration(160)
        except AttributeError:            # aeltere GTK3-Versionen
            self.output_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            self.output_revealer.set_transition_duration(160)
        self.output_revealer.set_reveal_child(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_start(6)
        box.set_margin_end(6)
        box.set_margin_bottom(4)

        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        bar.get_style_context().add_class("out-bar")
        self.out_title = Gtk.Label(label="AUSGABE")
        self.out_title.get_style_context().add_class("out-title")
        self.out_title.set_xalign(0.0)
        self.out_title.set_ellipsize(Pango.EllipsizeMode.END)
        bar.pack_start(self.out_title, True, True, 0)

        out_copy = Gtk.Button(label="⧉ ALL")
        out_copy.get_style_context().add_class("mini")
        out_copy.set_tooltip_text("Gesamte Ausgabe kopieren")
        out_copy.connect("clicked", lambda *_: self._copy_output())
        bar.pack_end(out_copy, False, False, 0)

        out_close = Gtk.Button(label="✕")
        out_close.get_style_context().add_class("mini")
        out_close.set_tooltip_text("Ausgabefenster schließen")
        out_close.connect("clicked", lambda *_: self.hide_output())
        bar.pack_end(out_close, False, False, 0)
        box.pack_start(bar, False, False, 0)

        frame = Gtk.Frame()
        frame.get_style_context().add_class("output")
        self.output_view = Gtk.TextView()
        self.output_view.set_editable(False)
        self.output_view.set_cursor_visible(True)
        self.output_view.set_monospace(True)
        self.output_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.output_view.set_left_margin(4)
        self.output_view.set_right_margin(4)
        self.output_view.set_top_margin(3)
        self.output_view.set_bottom_margin(3)
        self.output_view.get_style_context().add_class("output")
        frame.add(self.output_view)

        self.output_scroll = Gtk.ScrolledWindow()
        self.output_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.output_scroll.set_shadow_type(Gtk.ShadowType.NONE)
        self.output_scroll.set_min_content_height(110)
        frame.set_size_request(-1, 150)
        self.output_scroll.add(frame)
        box.pack_start(self.output_scroll, True, True, 0)

        self.output_revealer.add(box)
        return self.output_revealer

    def show_output(self, title, text):
        self.out_title.set_label(title)
        self._out_text = text
        buf = self.output_view.get_buffer()
        buf.set_text(text)
        self.output_scroll.set_vadjustment(None)
        self.output_revealer.set_reveal_child(True)

    def hide_output(self):
        self.output_revealer.set_reveal_child(False)

    def _copy_output(self):
        if not self._out_text:
            self.set_status("nichts zu kopieren", warn=True)
            return
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(self._out_text, -1)
        clip.store()
        self.set_status("Ausgabe kopiert (%d Zeichen)" % len(self._out_text))

    # -------------------------------------------------------------- Footer
    def _build_footer(self):
        self.footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

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

        self.footer.get_style_context().add_class("footer")
        return self.footer

    # ------------------------------------------------------------------ Aktionen
    def _on_action_clicked(self, button, item):
        etype = item.get("type", "READ")
        if etype == "READ":
            self.run_read(item, button)
        elif etype == "COPY":
            self._copy_item(item, button)
        elif etype == "TERM":
            self._open_terminal(item, button)
        elif etype == "ADMIN":
            self._confirm_admin(item, button)

    def _on_cmd_press(self, _widget, _event, item):
        self._on_action_clicked(None, item)
        return True

    def _on_copy_clicked(self, button, item):
        self._copy_item(item, button)

    # ------------------------------------------------------------------ READ
    def _resolve_prompt(self, item):
        """Fragt einen Suchbegriff ab (z.B. Prozessname, Dienstname).

        Rückgabe: (wert, ok) - bei Abbruch (wert=None, ok=False).
        """
        prompt = item.get("prompt")
        if not prompt:
            return "", True
        dialog = QueryDialog(self, prompt, item.get("prompt_token", "<query>"))
        return dialog.run()

    @staticmethod
    def _subst(text, token, value):
        """Ersetzt Suchbegriff und die Platzhalter {user} / {home}."""
        if not token:
            return text
        text = text.replace(token, value)
        return (text.replace("{user}", os.environ.get("USER", ""))
                    .replace("{home}", os.path.expanduser("~")))

    def _filter_output(self, text, item, value):
        """Filtert die Ausgabe in Python - ohne Pipe, ohne Shell."""
        pattern = None
        is_re = False
        if item.get("filter_re"):
            pattern, is_re = item["filter_re"], True
        elif item.get("filter"):
            pattern, is_re = item["filter"], False
        if not pattern:
            return text
        pattern = self._subst(pattern, item.get("prompt_token", "<query>"), value)
        if not pattern:
            return text
        try:
            rx = re.compile(pattern if is_re else re.escape(pattern), re.IGNORECASE)
        except re.error as exc:
            return text + "\n\n⚠ Ungültiges Suchmuster: %s" % exc
        lines = text.splitlines()
        hits = [l for l in lines if rx.search(l)]
        if not hits:
            return ("%s\n\nKeine Zeile passt zu » %s «.\n"
                    "(Filter: %s - gesamte Ausgabe oben)"
                    % (text[:400], pattern, pattern))
        return "\n".join(hits)

    def run_read(self, item, button=None):
        if item.get("blocked"):
            self.set_status("gesperrt: destruktiver Befehl - nicht ausgeführt", True)
            return
        if item.get("missing"):
            self.set_status("nicht verfügbar: %s"
                            % ", ".join(item["missing"]), True)
            self.show_output("SYSTEM CHECK",
                             "⚠ Could not run: %s\n\nReason:\n%s\n\n"
                             "No changes were made."
                             % (item.get("name", "?"),
                                "  · ".join(item["missing"])))
            return

        value = ""
        if item.get("prompt"):
            value, ok = self._resolve_prompt(item)
            if not ok:
                self.set_status("abgebrochen - keine Aktion ausgeführt")
                return

        token = item.get("prompt_token", "<query>")
        argv = [self._subst(str(a), token, value)
                for a in (item.get("argv") or [])]
        if is_mutation(" ".join(argv)) or \
                os.path.basename(argv[0]).lower() in FORBIDDEN_ARGV0 or \
                (os.path.basename(argv[0]).lower() == "find"
                 and FIND_DANGER & set(argv)):
            self.set_status("gesperrt: Befehl verändert das System", True)
            return
        key = "read:" + self.store.key_of(item)
        if self.runner.is_busy(key):
            self.set_status("läuft noch: %s" % item.get("name", "?"))
            return
        self.set_status("liest: %s …" % item.get("name", "?"), sticky=False)
        name = item.get("name", "?")
        self._flash(button)

        def work():
            timeout = int(item.get("timeout_s")
                          or self.store.setting("timeout_s", CMD_TIMEOUT_S))
            return run_argv(argv, timeout=timeout)

        def handler(tok, res):
            if tok != key:
                return
            rc, raw, timed_out, err = res
            allowed = [int(x) for x in (item.get("allow_rc") or [0])]
            text = trim_output(raw, timed_out, rc if rc not in allowed else 0, err)
            if timed_out or (rc not in (None,) + tuple(allowed)):
                self.show_output("READ · %s" % name.upper(), text)
                self.set_status("READ %s: siehe Ausgabe (Status %s)" % (name, rc),
                                True)
                return
            filtered = self._filter_output(text, item, value)
            title = "READ · %s" % name.upper()
            if value:
                title += "  [»%s«]" % value
            self.show_output(title, filtered)
            self.set_status("READ %s: %d Zeilen"
                            % (name, len(filtered.splitlines())))
            internal_log("READ %s" % name)

        self._pending_handlers[key] = handler
        self.runner.submit(key, work)

    # ------------------------------------------------------------------ COPY
    def _blocked_for(self, item, text):
        """Zweite Sicherheitsstufe vor dem Öffnen eines Terminals."""
        if is_mutation(text):
            return True
        if item.get("sudo") and item.get("type") == "TERM":
            return any(rx.search(text) for rx in BLOCKED_RE
                       if rx.pattern != r"\bsudo\b")
        return is_blocked(text)

    def _copy_item(self, item, button=None):
        text = item.get("cmd") or " ".join(str(a) for a in (item.get("argv") or []))
        if not text:
            self.set_status("nichts zu kopieren", True)
            return
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(text, -1)
        clip.store()
        self._flash(button)
        self.set_status("kopiert: %s" % text)
        internal_log("COPY %s" % item.get("name", "?"))

    # ------------------------------------------------------------------ TERM
    def _open_terminal(self, item, button=None):
        if item.get("blocked"):
            self.set_status("gesperrt: destruktiver Befehl", True)
            return
        if item.get("missing"):
            self.set_status("nicht verfügbar: %s"
                            % ", ".join(item["missing"]), True)
            return
        workdir = os.path.expanduser(item["workdir"]) if item.get("workdir") else None
        if workdir and not os.path.isdir(workdir):
            workdir = os.path.expanduser("~")
        command = item.get("cmd") or ""
        if item.get("prompt"):
            value, ok = self._resolve_prompt(item)
            if not ok:
                self.set_status("abgebrochen - keine Aktion ausgeführt")
                return
            command = self._subst(command, item.get("prompt_token", "<query>"), value)
        if self._blocked_for(item, command):
            self.set_status("gesperrt: destruktiver Befehl", True)
            return
        argv = terminal_argv(self.term_argv, workdir, command or None)
        if not argv:
            self.set_status("kein Terminal gefunden", True)
            return
        try:
            subprocess.Popen(argv, close_fds=True, start_new_session=True)
            ok = True
            err = ""
        except (OSError, ValueError) as exc:
            ok, err = False, str(exc)
        self._flash(button, ok)
        self.set_status(("Terminal geöffnet: " if ok else "FEHLER: ") + command
                        if ok else "FEHLER: %s" % err, warn=not ok)
        if ok:
            internal_log("TERM %s" % item.get("name", "?"))

    @staticmethod
    def _unit_of(command):
        """Sucht den Dienstnamen aus einem systemctl-Aufruf."""
        m = re.search(r"systemctl\s+(?:-\S+\s+)*"
                      r"(start|stop|restart|reload|enable|disable|mask|unmask)"
                      r"\s+([A-Za-z0-9_.@:-]+)", command or "")
        return m.group(2) if m else ""

    # ----------------------------------------------------------------- ADMIN
    def _confirm_admin(self, item, button=None):
        if item.get("blocked"):
            self.set_status("gesperrt: destruktiver Befehl", True)
            return
        if item.get("critical"):
            self.set_status("kritischer Dienst gesperrt - im Terminal öffnen "
                            "(TERM-Eintrag)", True)
            return
        if item.get("missing"):
            self.set_status("nicht verfügbar: %s"
                            % ", ".join(item["missing"]), True)
            return
        command = item.get("admin_command") or item.get("cmd") or ""
        if item.get("prompt"):
            value, ok = self._resolve_prompt(item)
            if not ok:
                self.set_status("abgebrochen - keine Aktion ausgeführt")
                return
            command = self._subst(command, item.get("prompt_token", "<query>"), value)
        if self._blocked_for(item, command):
            self.set_status("gesperrt: destruktiver Befehl", True)
            return
        if not command:
            self.set_status("kein Befehl hinterlegt", True)
            return
        unit = self._unit_of(command) or item.get("unit") or ""
        if unit and is_critical_unit(unit):
            self.set_status("KRITISCHER DIENST (%s) - vom System Deck gesperrt. "
                            "Nur bewusst im Terminal änderbar." % unit, True)
            internal_log("ADMIN abgelehnt (kritisch): %s" % unit)
            return
        dlg = AdminDialog(self, item, command, self.term_argv)
        dlg.run()
        if dlg.accepted:
            argv = terminal_argv(self.term_argv, None, command)
            if not argv:
                self.set_status("kein Terminal gefunden", True)
                return
            try:
                subprocess.Popen(argv, close_fds=True, start_new_session=True)
                self._flash(button, True)
                self.set_status("Terminal geöffnet - Bestätigung dort abwarten")
                internal_log("ADMIN %s" % item.get("name", "?"))
            except (OSError, ValueError) as exc:
                self.set_status("FEHLER: %s" % exc, True)

    # ------------------------------------------------------------------ Suche
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
            self.store.state["positioned"] = True
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

    # ------------------------------------------------------------------- Menü
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
        add("Systemcheck neu berechnen  (F5)",
            lambda *_: self.refresh_check(True))
        add("Alle Kategorien", self._on_show_all)
        add("Befehle bearbeiten …", self._on_edit)
        add("Position: unten rechts zurücksetzen", self._on_reset_geometry)
        menu.append(Gtk.SeparatorMenuItem())
        add("Deck verbergen  (Strg+H)", lambda *_: self.hide())
        add("Beenden", lambda *_: self.quit())
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def _on_show_all(self, *_):
        self._category = None
        self._render_catgrid()
        self._rebuild_list()

    def _on_toggle_aot(self, item):
        value = self.set_on_top(bool(item.get_active()))
        self.set_status("Always-on-Top: %s" % ("AN" if value else "AUS"))

    def _on_edit(self, *_):
        self.store.ensure_commands_file()
        exe = editor_command()
        if not exe:
            self.set_status("kein Texteditor - bitte %s bearbeiten"
                            % COMMANDS_FILE, True)
            return
        try:
            subprocess.Popen([exe, COMMANDS_FILE],
                             cwd=os.path.dirname(COMMANDS_FILE))
            self.set_status("geöffnet: %s" % COMMANDS_FILE)
        except Exception as exc:
            self.set_status("Editor nicht startbar: %s" % exc, True)

    def _on_reset_geometry(self, *_):
        geo = default_geometry(DEFAULT_W, DEFAULT_H)
        st = self.store.state
        st.update({"x": geo["x"], "y": geo["y"],
                   "width": geo["width"], "height": geo["height"],
                   "positioned": True})
        self.store.save_state()
        self.resize(st["width"], st["height"])
        self.move(st["x"], st["y"])
        self.set_status("Position: unten rechts (%d, %d)" % (st["x"], st["y"]))

    # ------------------------------------------------------------------ Status
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
        if self.store.load_error:
            self.set_status("commands.json: %s" % self.store.load_error,
                            warn=True, sticky=False)
        elif self._query.strip():
            self.set_status("%d Treffer für » %s «"
                            % (len(self._visible_items()), self._query.strip()),
                            sticky=False)
        else:
            tools_missing = sorted(t for t in TOOLS if not have(t))
            self.set_status("%d Befehle · %d Kategorien · %d Werkzeuge fehlen"
                            % (len(self._items), len(self.store.categories()),
                               len(tools_missing)), sticky=False)
        on_top = bool(self.store.state.get("always_on_top"))
        self.aot_label.set_label("▲ PIN" if on_top else "▽ NORMAL")
        self.pin_label.set_label("PIN" if on_top else "NORMAL")

    # ------------------------------------------------------------------ Tastatur
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
            self.refresh_check(True)
            self.set_status("Systemcheck neu berechnet")
            return True
        if key in ("Escape", "Esc") and self._query:
            self._set_query("")
            return True
        return False

    # --------------------------------------------------------- Sichtbarkeit
    def _on_map(self, _widget, _event):
        self.refresh_check()
        if self._check_timer is None:
            self._check_timer = GLib.timeout_add_seconds(
                CHECK_REFRESH_S, self._auto_refresh)
        return False

    def _on_unmap(self, _widget, _event):
        if self._check_timer is not None:
            GLib.source_remove(self._check_timer)
            self._check_timer = None
        return False

    def _auto_refresh(self):
        if not self.get_mapped():
            return True
        self.refresh_check()
        return True

    def _on_async_result(self, token, res):
        handler = getattr(self, "_pending_handlers", {}).pop(token, None)
        if handler is not None:
            handler(token, res)

    # --------------------------------------------------------------- Persistenz
    def _on_configure(self, _widget, _event):
        if not self.get_realized():
            return False
        x, y = self.get_position()
        w, h = self.get_size()
        self.store.state.update({"x": x, "y": y, "width": w, "height": h,
                                "positioned": True})
        return False

    def _clamp_to_screen(self):
        """Nicht teilweise aus den Bildschirmbereich schieben."""
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
        self.store.state.update({"x": x, "y": y, "width": w, "height": h,
                                "positioned": True})
        self.store.save_state()
        release_lock()
        Gtk.main_quit()


# ===========================================================================
#  Admin-Bestätigungsdialog
# ===========================================================================
class AdminDialog(object):
    """⚠ ADMIN ACTION - zeigt den Befehl wörtlich und verlangt Bestätigung."""

    def __init__(self, parent, item, command, term_argv):
        self.accepted = False
        dlg = Gtk.Dialog()
        self.dlg = dlg
        dlg.set_title("ADMIN ACTION")
        dlg.set_transient_for(parent)
        dlg.set_modal(True)
        dlg.set_decorated(False)
        dlg.set_resizable(False)
        dlg.get_style_context().add_class("sd-dialog")
        dlg.set_default_size(360, -1)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        dlg.get_content_area().add(outer)

        title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_bar.get_style_context().add_class("titlebar")
        glyph = Gtk.Label(label="⚠")
        glyph.get_style_context().add_class("glyph")
        title_bar.pack_start(glyph, False, False, 0)
        t = Gtk.Label(label="ADMIN ACTION")
        t.get_style_context().add_class("sd-title")
        title_bar.pack_start(t, True, True, 0)
        outer.pack_start(title_bar, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        body.get_style_context().add_class("sd-body")

        w1 = Gtk.Label(label="This operation requires elevated privileges.")
        w1.set_xalign(0.0)
        body.pack_start(w1, False, False, 0)

        w2 = Gtk.Label(label="Es wird nichts im System Deck ausgeführt. "
                             "Der Befehl öffnet sich in einem sichtbaren "
                             "Terminal und wird dort von Dir bestätigt.")
        w2.set_xalign(0.0)
        w2.set_line_wrap(True)
        w2.set_max_width_chars(44)
        body.pack_start(w2, False, False, 0)

        cmd_label = Gtk.Label()
        cmd_label.set_markup('<span font_family="Hack">%s</span>'
                             % escape_markup(command))
        cmd_label.get_style_context().add_class("sd-cmd")
        cmd_label.set_selectable(True)
        cmd_label.set_xalign(0.0)
        cmd_label.set_line_wrap(True)
        cmd_label.set_max_width_chars(44)
        body.pack_start(cmd_label, False, False, 0)

        term = Gtk.Label(label="Terminal: %s" % terminal_display(term_argv))
        term.get_style_context().add_class("legend")
        term.set_xalign(0.0)
        body.pack_start(term, False, False, 0)

        no_pw = Gtk.Label(label="Es wird kein Passwort gespeichert und kein "
                               "Passwortfeld angezeigt.")
        no_pw.get_style_context().add_class("legend")
        no_pw.set_xalign(0.0)
        body.pack_start(no_pw, False, False, 0)
        outer.pack_start(body, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_halign(Gtk.Align.END)
        buttons.set_border_width(6)
        cancel = Gtk.Button(label="ABBRECHEN")
        cancel.get_style_context().add_class("sd-ok")
        cancel.connect("clicked", self._cancel)
        buttons.pack_start(cancel, False, False, 0)
        go = Gtk.Button(label="IM TERMINAL ÖFFNEN")
        go.get_style_context().add_class("sd-ok")
        go.connect("clicked", self._accept)
        buttons.pack_start(go, False, False, 0)
        outer.pack_start(buttons, False, False, 0)

        screen = Gdk.Screen.get_default()
        if screen is not None:
            rgba = screen.get_rgba_visual()
            if rgba is not None:
                dlg.set_visual(rgba)
        dlg.set_app_paintable(True)

    def run(self):
        self.dlg.show_all()
        self.dlg.run()
        return self.accepted

    def _accept(self, _b):
        self.accepted = True
        self.dlg.response(1)
        self.dlg.destroy()

    def _cancel(self, _b):
        self.accepted = False
        self.dlg.response(0)
        self.dlg.destroy()


def _worst_status(a, b):
    order = {"IDLE": 0, "INFO": 1, "OK": 2, "WARN": 3, "ERR": 4}
    return a if order.get(a, 1) >= order.get(b, 1) else b


# ===========================================================================
#  Suchabfrage  (Prozessname, Dienstname, Port, Suchbegriff ...)
# ===========================================================================
class QueryDialog(object):
    """Fragt einen Suchbegriff ab. Es wird NICHTS ausgeführt, nur gefragt."""

    def __init__(self, parent, prompt, token="<query>", example=""):
        self.value = None
        dlg = Gtk.Dialog()
        self.dlg = dlg
        dlg.set_title("SYSTEM DECK - Suchbegriff")
        dlg.set_transient_for(parent)
        dlg.set_modal(True)
        dlg.set_decorated(False)
        dlg.set_resizable(False)
        dlg.get_style_context().add_class("sd-dialog")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        dlg.get_content_area().add(outer)

        title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_bar.get_style_context().add_class("titlebar")
        glyph = Gtk.Label(label="❯")
        glyph.get_style_context().add_class("glyph")
        title_bar.pack_start(glyph, False, False, 0)
        t = Gtk.Label(label="SUCHBEGRIFF")
        t.get_style_context().add_class("sd-title")
        title_bar.pack_start(t, True, True, 0)
        outer.pack_start(title_bar, False, False, 0)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        body.get_style_context().add_class("sd-body")

        lbl = Gtk.Label(label=prompt)
        lbl.set_xalign(0.0)
        lbl.set_line_wrap(True)
        lbl.set_max_width_chars(42)
        body.pack_start(lbl, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.get_style_context().add_class("search")
        self.entry.set_text("")
        self.entry.set_activates_default(True)
        self.entry.connect("changed", lambda w: self.error.set_label(""))
        body.pack_start(self.entry, False, False, 0)

        if example:
            hint = Gtk.Label(label="Beispiel: %s" % example)
            hint.get_style_context().add_class("legend")
            hint.set_xalign(0.0)
            body.pack_start(hint, False, False, 0)

        self.error = Gtk.Label(label="")
        self.error.get_style_context().add_class("status-warn")
        self.error.set_xalign(0.0)
        body.pack_start(self.error, False, False, 0)

        info = Gtk.Label(label="Der Begriff ersetzt %s im Befehl. "
                              "Es wird nichts am System verändert."
                              % token)
        info.get_style_context().add_class("legend")
        info.set_xalign(0.0)
        info.set_line_wrap(True)
        info.set_max_width_chars(42)
        body.pack_start(info, False, False, 0)
        outer.pack_start(body, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_halign(Gtk.Align.END)
        buttons.set_border_width(6)
        cancel = Gtk.Button(label="ABBRECHEN")
        cancel.get_style_context().add_class("sd-ok")
        cancel.connect("clicked", lambda *_: self._finish(None))
        buttons.pack_start(cancel, False, False, 0)
        go = Gtk.Button(label="ÜBERNEHMEN")
        go.get_style_context().add_class("sd-ok")
        go.connect("clicked", self._accept)
        buttons.pack_start(go, False, False, 0)
        dlg.set_default_response(1)
        outer.pack_start(buttons, False, False, 0)

        screen = Gdk.Screen.get_default()
        if screen is not None:
            rgba = screen.get_rgba_visual()
            if rgba is not None:
                dlg.set_visual(rgba)
        dlg.set_app_paintable(True)

    def run(self):
        self.dlg.show_all()
        self.entry.grab_focus()
        self.dlg.run()
        value = self.value
        self.dlg.destroy()
        if value is None:
            return None, False
        return value, True

    def _accept(self, _b):
        value = self.entry.get_text().strip()
        # Nur sichere Zeichen: der Begriff landet als EIN Argument in einer
        # Argumentliste bzw. als Teil einer Terminal-Zeile.
        if not value:
            self._finish(None)
            return
        if len(value) > 64 or not re.match(r"^[A-Za-z0-9_.@:+-]+$", value):
            self.error.set_label("Nur Buchstaben, Ziffern und . _ - @ : + erlaubt")
            return
        self._finish(value)

    def _finish(self, value):
        self.value = value
        self.dlg.response(1 if value else 0)
        self.dlg.destroy()


# ===========================================================================
#  Prozess / Instanz-Schutz
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
        print("  %-52s %s" % (label, "OK" if cond else "FEHLER"))
        if not cond:
            ok = False

    print("System Deck Selbsttest")
    print("-" * 62)

    term = detect_terminal()
    check("Standard-Terminal erkannt: %s" % terminal_display(term), bool(term))

    store = Store()
    store.load_commands()
    items = store.build_items(term)
    check("commands.json lesbar / %d Eintraege" % len(items), bool(items))

    types = {i["type"] for i in items}
    check("Typen nur READ/COPY/TERM/ADMIN: %s" % sorted(types),
          types <= set(TYPE_INFO))

    check("Blockliste: 'rm -rf /' gesperrt", is_blocked("rm -rf /"))
    check("Blockliste: 'sudo apt install x' gesperrt",
          is_blocked("sudo apt install x"))
    check("Blockliste: 'mkfs.ext4 /dev/sda' gesperrt",
          is_blocked("mkfs.ext4 /dev/sda"))
    check("Blockliste: 'reboot' gesperrt", is_blocked("reboot"))
    check("Blockliste: 'last -x reboot' erlaubt (Lesebefehl)",
          not is_blocked("last -x reboot"))
    check("Blockliste: 'getent passwd' erlaubt", not is_blocked("getent passwd"))
    check("Blockliste: 'journalctl -p err' erlaubt",
          not is_blocked("journalctl -p err"))
    check("Blockliste: 'df -h' erlaubt", not is_blocked("df -h"))

    check("Mutation: 'apt upgrade' gesperrt", is_mutation("sudo apt upgrade"))
    check("Mutation: 'ufw allow 22' gesperrt", is_mutation("sudo ufw allow 22"))
    check("Mutation: 'systemctl restart cups' erlaubt (nur Dienst)",
          not is_mutation("sudo systemctl restart cups"))
    check("Mutation: 'journalctl --vacuum-time=7d' gesperrt",
          is_mutation("sudo journalctl --vacuum-time=7d"))
    check("Mutation: 'ufw status verbose' erlaubt",
          not is_mutation("sudo ufw status verbose"))

    check("Kritische Dienste: ssh / NetworkManager erkannt",
          is_critical_unit("sshd") and is_critical_unit("NetworkManager"))
    check("Kritische Dienste: unbekannter Dienst erlaubt",
          not is_critical_unit("nginx"))

    check("kein aktiver Eintrag ist gesperrt",
          not [i for i in items if i["blocked"]])
    check("kein aktiver Eintrag verändert Daten",
          not [i for i in items
               if i["blocked"] and is_mutation(i.get("cmd") or "")])

    read_items = [i for i in items if i["type"] == "READ"]
    check("READ-Eintraege haben argv: %d/%d"
          % (sum(1 for i in read_items if i.get("argv")), len(read_items)),
          all(i.get("argv") for i in read_items))
    check("READ nutzt keine Shell als argv[0]",
          not [i for i in read_items
               if os.path.basename(str(i["argv"][0])).lower() in FORBIDDEN_ARGV0])
    check("READ nutzt kein sudo/rm",
          not [i for i in read_items
               if is_mutation(" ".join(str(a) for a in i["argv"]))
               or is_blocked(" ".join(str(a) for a in i["argv"]))])
    check("ADMIN braucht immer einen bestaetigten Befehl",
          all(i.get("admin_command") or i.get("cmd") for i in items
              if i["type"] == "ADMIN"))
    check("sudo-Ausnahme nur bei TYPE=TERM",
          not [i for i in items if i.get("sudo") and i["type"] != "TERM"])

    check("theme.css vorhanden", os.path.exists(os.path.join(ASSETS, "theme.css")))
    check("eigenes State-Verzeichnis (%s)" % STATE_DIR,
          STATE_DIR not in (os.path.join(CONFIG_DIR, "terminal-clipboard"),
                            os.path.join(CONFIG_DIR, "daily-deck")))
    check("eigener Autostart-Pfad",
          os.path.join(CONFIG_DIR, "autostart", "system-deck.desktop")
          != os.path.join(CONFIG_DIR, "autostart", "command-deck.desktop"))

    geo = default_geometry()
    check("Standardposition berechenbar: %sx%s @ %s,%s"
          % (geo["width"], geo["height"], geo["x"], geo["y"]),
          geo["x"] >= 0 and geo["y"] >= 0)

    results = QC.all()
    check("Quick Check liefert %d Werte" % len(results), len(results) == 9)

    print("-" * 62)
    print("Ergebnis: %s" % ("BESTANDEN" if ok else "FEHLGESCHLAGEN"))
    return 0 if ok else 1


# ===========================================================================
#  Audit
# ===========================================================================
def audit():
    store = Store()
    store.load_commands()
    term = detect_terminal()
    items = store.build_items(term)

    print("=" * 78)
    print(" SYSTEM DECK  ·  Konfigurations-Audit")
    print("=" * 78)
    print(" Konfiguration : %s" % store.commands_file)
    print(" Terminal      : %s" % " ".join(term))
    print(" Standardpos.  : %s" % default_geometry())
    print(" Eintraege     : %d" % len(items))
    print("=" * 78)

    missing_tools = sorted(t for t in TOOLS if not have(t))
    print(" Werkzeuge fehlen (nicht installiert, nur Info): %s"
          % (", ".join(missing_tools) or "keine"))
    print("-" * 78)

    counts = {}
    cur = None
    for it in items:
        if it["category"] != cur:
            cur = it["category"]
            print("\n  %s  %s" % (it.get("category_icon", ""), cur.upper()))
        counts[it["type"]] = counts.get(it["type"], 0) + 1
        flags = []
        if it.get("blocked"):
            flags.append("GESPERRT")
        if it.get("critical"):
            flags.append("KRITISCH")
        if it.get("missing"):
            flags.append("FEHLT: " + ",".join(it["missing"]))
        print("    %-6s %-34s %s %s"
              % (it["type"], it["name"][:34], it.get("cmd", "")[:24],
                 ("[" + " ".join(flags) + "]") if flags else ""))

    print("\n" + "=" * 78)
    print(" Verteilung : %s" % ", ".join("%s=%d" % kv
                                         for kv in sorted(counts.items())))
    print(" Kategorien : %d" % len(store.categories()))
    print("=" * 78)
    return 0


# ===========================================================================
#  main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--selftest", action="store_true",
                        help="Konfiguration und Sicherheitsregeln prüfen")
    parser.add_argument("--audit", action="store_true",
                        help="alle Befehle mit Verfügbarkeit auflisten")
    parser.add_argument("--raise", dest="raise_existing", action="store_true",
                        help="bereits laufende Instanz anheben")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args()

    if args.version:
        print("%s %s" % (APP_NAME, VERSION))
        return 0

    if args.selftest:
        return selftest()

    if args.audit:
        return audit()

    if instance_running() and not args.raise_existing:
        raise_existing()
        return 0

    take_lock()
    store = Store()
    store.load_state()
    SystemDeck(store)
    Gtk.main()
    release_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
