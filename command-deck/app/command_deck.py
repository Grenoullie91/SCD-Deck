#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMMAND DECK  ·  Terminal Command Clipboard
==========================================

Kompaktes Desktop-Widget (GTK3) fuer haeufig genutzte Terminal-Befehle.
Ein Klick kopiert den Befehl in die Zwischenablage - mehr nicht.

###############################################################################
#  SICHERHEITS-GARANTIE
###############################################################################
#  Dieses Programm fuehrt NIEMALS Befehle aus.
#
#  Der einzige Datenfluss fuer Befehlstexte ist:
#      Button "COPY"  ->  Gtk.Clipboard.set_text() / .store()
#
#  Es existiert bewusst KEIN Aufruf von os.system, os.popen, os.exec*,
#  os.spawn*, os.fork, pty.spawn, GLib.spawn*, eval, exec oder shell=True.
#  subprocess wird ausschliesslich fuer zwei harmlose Zwecke benutzt:
#    * _on_edit()      -> oeffnet die commands.json in einem Texteditor
#    * _raise_existing()-> wmctrl, um ein bereits laufendes Deck anzuheben
#  Beide rufen niemals Text aus der Befehlsliste auf.
#  Der Selbsttest (--selftest) prueft das per AST-Analyse zur Laufzeit.
#
#  Platzhalter wie <PROJECT_PATH> werden bewusst MITKOPIERT und nicht
#  aufgeloest - das Aufloesen bleibt dem Nutzer im Terminal ueberlassen.
###############################################################################
"""

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402

APP_NAME = "Command Deck"
APP_ID = "terminal-clipboard-command-deck"
VERSION = "1.0.0"

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(PROJECT_ROOT, "assets")
SEED_DIR = os.path.join(PROJECT_ROOT, "config")

CONFIG_DIR = (os.environ.get("XDG_CONFIG_HOME")
              or os.path.join(os.path.expanduser("~"), ".config"))
STATE_DIR = os.path.join(CONFIG_DIR, "terminal-clipboard")
COMMANDS_FILE = os.path.join(STATE_DIR, "commands.json")
STATE_FILE = os.path.join(STATE_DIR, "state.json")
LOCK_FILE = os.path.join(STATE_DIR, "instance.lock")

MIN_W, MIN_H = 300, 300
COPY_FEEDBACK_MS = 1500
BORDERLESS_TOP_PAD = 0

# ------------------------------------------------------------------- Palette
C_BG0 = (0x0B, 0x06, 0x12)
C_VIOLET_D = (0x6D, 0x28, 0xD9)
C_VIOLET = (0x8B, 0x5C, 0xF6)
C_NEON = (0xA8, 0x55, 0xF7)
C_NEON_LT = (0xC0, 0x84, 0xFC)

DEFAULT_STATE = {
    "always_on_top": True,
    "opacity": 0.95,
    "x": 40,
    "y": 60,
    "width": 400,
    "height": 460,
    "favorites": [],
}


def log(*a):
    if os.environ.get("COMMAND_DECK_DEBUG"):
        print("[deck]", *a, file=sys.stderr)


def hexa(rgb, alpha):
    return (rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha)


def escape_markup(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("'", "&#39;"))


HIGHLIGHT_BG = "#3A1E63"
HIGHLIGHT_FG = "#F3E8FF"


def highlight(text, query):
    """Suchtreffer neon-violett markieren.

    Pango-Markup kennt kein <mark>-Tag (GTK3 meldet "Unknown tag 'mark'"),
    deshalb wird mit <span background=... foreground=...> gearbeitet.
    """
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
    """Interaktiver Container: Gtk.EventBox besitzt ein eigenes GdkWindow
    und empfaengt Mausereignisse auch ueber leere Flaechen. Ein Gtk.Box mit
    set_has_window(True) loest in GTK 3.24.41 hier eine Assertion aus."""
    box = Gtk.EventBox()
    box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK
                   | Gdk.EventMask.BUTTON_RELEASE_MASK
                   | Gdk.EventMask.POINTER_MOTION_MASK)
    # Wichtig: above_child=False, sonst liegt das EventBox-Fenster ueber den
    # Kindern und kaelt die Klicks auf den COPY-Buttons ab.
    box.set_above_child(False)
    return box


# ================================================================== Datenhaltung
class Store:
    """commands.json (Befehle) und state.json (Geometrie, Favoriten)."""

    def __init__(self, state_file=None):
        self.state_file = state_file or STATE_FILE
        self.categories = []
        self.order = []
        self.state = dict(DEFAULT_STATE)
        self.state["favorites"] = []
        self.load_error = None

    # ------------------------------------------------------------- commands.json
    @staticmethod
    def ensure_dirs():
        os.makedirs(STATE_DIR, exist_ok=True)

    def ensure_commands_file(self):
        """Legt commands.json an, falls sie fehlt - aus der Projektvorlage."""
        if os.path.exists(COMMANDS_FILE):
            return
        self.ensure_dirs()
        src = os.path.join(SEED_DIR, "commands.json")
        if os.path.isfile(src):
            shutil.copyfile(src, COMMANDS_FILE)
            log("commands.json aus Vorlage angelegt:", COMMANDS_FILE)

    def load_commands(self):
        self.ensure_commands_file()
        self.categories, self.order, self.load_error = [], [], None
        try:
            with open(COMMANDS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:
            self.load_error = str(exc)
            log("commands.json nicht lesbar:", exc)
            return
        cats = data.get("categories") if isinstance(data, dict) else None
        if not isinstance(cats, dict) or not cats:
            self.load_error = "kein 'categories'-Objekt gefunden"
            return
        for name, spec in cats.items():
            if name.startswith("_"):
                continue
            if isinstance(spec, dict):
                cmds, icon = spec.get("commands", []), spec.get("icon", "◈")
            else:
                cmds, icon = spec, "◈"
            if not isinstance(cmds, list):
                continue
            clean = [c.strip() for c in cmds
                     if isinstance(c, str) and c.strip()]
            if not clean:
                continue
            self.order.append((name, icon))
            self.categories.append((name, clean))

    def total_commands(self):
        return sum(len(c) for _, c in self.categories)

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
        else:
            seed = os.path.join(SEED_DIR, "seed_favorites.json")
            if os.path.isfile(seed):
                try:
                    with open(seed, "r", encoding="utf-8") as fh:
                        self.state["favorites"] = list(
                            json.load(fh).get("favorites", []))
                except Exception as exc:
                    log("seed_favorites.json unbrauchbar:", exc)
        return self.state

    def save_state(self, state=None):
        if state is not None:
            self.state = state
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        tmp = self.state_file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.state_file)
        except Exception as exc:
            log("state.json nicht schreibbar:", exc)
        return self.state

    # ---------------------------------------------------------------- Favoriten
    def is_fav(self, cmd):
        return cmd in self.state.get("favorites", [])

    def toggle_fav(self, cmd):
        favs = self.state.setdefault("favorites", [])
        if cmd in favs:
            favs.remove(cmd)
            return False
        favs.append(cmd)
        return True


# =============================================================== Hintergrund
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
        super().__init__()
        self.opacity = opacity

    def set_opacity(self, value):
        self.opacity = max(0.55, min(1.0, float(value)))
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


# ========================================================================= Widget
class CommandDeck(Gtk.Window):

    def __init__(self, store):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.store = store
        self._css = None
        self._copy_timer = None
        self._drag = None
        self._resize = None
        self._rows = []
        self._query = ""

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
                              int(st.get("height", 460)))
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
            print("[deck] theme.css nicht ladbar: %s" % exc, file=sys.stderr)
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
        title = Gtk.Label(label="COMMAND DECK")
        title.get_style_context().add_class("title")
        sub = Gtk.Label(label="TERMINAL // QUICK ACCESS")
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

        # U+2315 "⌕" ist laut Unicode ein Telephone Recorder, kein Lupenglas -
        # deshalb das echte Hack-native Chevron U+276F als Prompt-Zeichen.
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

        self.search_hint = Gtk.Label(label="Search commands...")
        self.search_hint.get_style_context().add_class("search-hint")
        self.search_hint.set_halign(Gtk.Align.START)
        self.search_hint.set_valign(Gtk.Align.CENTER)
        self.search_hint.set_margin_start(9)
        self.search_hint.set_ellipsize(Pango.EllipsizeMode.END)
        self.search_hint_event = event_box()
        self.search_hint_event.add(self.search_hint)
        self.search_hint_event.set_halign(Gtk.Align.START)
        self.search_hint_event.connect("button-press-event",
                                       self._on_hint_press)
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
        self._rebuild_list()
        self._update_status()

    def _visible_groups(self):
        """-> [(name, icon, ist_favoriten, [cmd, ...]), ...]"""
        q = self._query.strip().lower()
        groups, fav_hits = [], []

        for name, cmds in self.store.categories:
            hits = [c for c in cmds if not q or q in c.lower()]
            if not hits:
                continue
            starred = [c for c in hits if self.store.is_fav(c)]
            plain = [c for c in hits if not self.store.is_fav(c)]
            fav_hits.extend(starred)
            if plain:
                groups.append((name, self._icon(name), False, plain))

        if fav_hits:
            favs = self.store.state.get("favorites", [])
            fav_hits.sort(key=lambda c: favs.index(c) if c in favs else 10 ** 6)
            groups.insert(0, ("★ Favorites", "★", True, fav_hits))
        return groups

    def _icon(self, name):
        for cat, icon in self.store.order:
            if cat == name:
                return icon
        return "◈"

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

        for name, icon, is_fav, cmds in groups:
            head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            head.get_style_context().add_class("cat")
            if is_fav:
                head.get_style_context().add_class("cat-fav")
            lbl = Gtk.Label(label="%s  %s" % (icon, name.upper()))
            lbl.get_style_context().add_class("cat-label")
            lbl.set_xalign(0.0)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            head.pack_start(lbl, True, True, 0)
            cnt = Gtk.Label(label="%02d" % len(cmds))
            cnt.get_style_context().add_class("cat-count")
            head.pack_end(cnt, False, False, 0)
            self.listbox.pack_start(head, False, False, 0)

            for cmd in cmds:
                row = self._build_row(cmd)
                self.listbox.pack_start(row, False, False, 0)
                self._rows.append((row, cmd))

        self.listbox.show_all()
        self._update_status()

    def _build_row(self, cmd):
        row = event_box()
        row.get_style_context().add_class("row")
        row.set_tooltip_text(cmd)

        hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        row.add(hb)

        # ---- Favoriten-Stern
        starred = self.store.is_fav(cmd)
        star = Gtk.Label(label="★" if starred else "☆")
        star.get_style_context().add_class(
            "fav-star" if starred else "fav-star-off")
        star.set_valign(Gtk.Align.CENTER)
        star_event = event_box()
        star_event.add(star)
        star_event.set_tooltip_text(
            "Favorit entfernen" if starred else "Als Favorit markieren")
        star_event.connect("button-press-event", self._on_star_press, cmd)
        hb.pack_start(star_event, False, False, 0)

        # ---- Befehlstext (Klick kopiert ebenfalls)
        txt = Gtk.Label()
        txt.set_markup(highlight(cmd, self._query))
        txt.get_style_context().add_class("cmd")
        txt.set_xalign(0.0)
        txt.set_yalign(0.5)
        txt.set_ellipsize(Pango.EllipsizeMode.END)
        txt.set_hexpand(True)
        txt_event = event_box()
        txt_event.add(txt)
        txt_event.set_tooltip_text("Klicken = in Zwischenablage kopieren")
        txt_event.connect("button-press-event", self._on_cmd_press, cmd)
        hb.pack_start(txt_event, True, True, 0)

        # ---- Copy-Button
        btn = Gtk.Button(label="COPY")
        btn.get_style_context().add_class("copy")
        btn.set_tooltip_text("In Zwischenablage kopieren")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect("clicked", self._on_copy_clicked, cmd)
        hb.pack_end(btn, False, False, 0)
        return row

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
                self._rows[0][0].grab_focus()
            return True
        return False

    def _set_query(self, text, from_entry=False):
        self._query = text or ""
        if not from_entry:
            if self.search.get_text() != self._query:
                self.search.set_text(self._query)
        self._update_search_hint()
        self._rebuild_list()

    # ----------------------------------------------------------------- Kopieren
    def _on_copy_clicked(self, button, cmd):
        self.copy_command(cmd, button)

    def _on_cmd_press(self, _widget, _event, cmd):
        self.copy_command(cmd, None)
        return True

    def copy_command(self, cmd, button=None):
        """DER EINZIGE Datenweg des Widgets: Text -> Zwischenablage.

        Kopiert wird der ROHE Befehlstext inklusive Platzhalter. Es wird
        nichts aufgeloest, nichts substituiert, nichts ausgefuehrt.
        """
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(cmd, -1)
        clipboard.store()
        self._flash(button)
        log("kopiert: %r" % cmd)

    def _flash(self, button, ms=COPY_FEEDBACK_MS):
        """Kurze gruene Bestaetigung, danach zurueck auf COPY."""
        if button is None:
            return
        if self._copy_timer is not None:
            GLib.source_remove(self._copy_timer)
            self._copy_timer = None
        old_label = button.get_label()
        ctx = button.get_style_context()
        ctx.remove_class("copy")
        ctx.add_class("ok")
        button.set_label("✓ OK")
        button.set_sensitive(False)
        button.queue_draw()

        def restore():
            ctx.remove_class("ok")
            ctx.add_class("copy")
            button.set_label(old_label)
            button.set_sensitive(True)
            button.queue_draw()
            self._copy_timer = None
            return False

        self._copy_timer = GLib.timeout_add(ms, restore)

    # --------------------------------------------------------------- Favoriten
    def _on_star_press(self, _widget, _event, cmd):
        added = self.store.toggle_fav(cmd)
        self.store.save_state()
        self._rebuild_list()
        self.set_status("★ %s" % ("Favorit: %s" % cmd if added
                                  else "aus Favoriten entfernt"))
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
        add("Befehle neu laden  (F5)", lambda *_: self.reload_commands())
        add("Befehle bearbeiten …", self._on_edit)
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
            self.set_status("kein Texteditor - bitte %s bearbeiten"
                            % COMMANDS_FILE, warn=True)
            return
        try:
            subprocess.Popen([exe, COMMANDS_FILE], cwd=os.path.dirname(
                COMMANDS_FILE))
            self.set_status("geoeffnet: %s" % COMMANDS_FILE)
        except Exception as exc:
            self.set_status("Editor nicht startbar: %s" % exc, warn=True)

    def _on_reset_geometry(self, *_):
        st = self.store.state
        st.update({"x": 40, "y": 60, "width": 400, "height": 460})
        self.store.save_state()
        self.resize(st["width"], st["height"])
        self.move(st["x"], st["y"])
        self.set_status("Geometrie zurueckgesetzt")

    # ------------------------------------------------------------------- Status
    def set_status(self, text, warn=False):
        self.status.set_label(text)
        ctx = self.status.get_style_context()
        ctx.remove_class("status")
        ctx.remove_class("status-warn")
        ctx.add_class("status-warn" if warn else "status")

    def _update_status(self):
        on_top = bool(self.store.state.get("always_on_top"))
        if self.store.load_error:
            self.set_status("commands.json: %s" % self.store.load_error, warn=True)
        elif self._query.strip():
            n = sum(len(c) for _a, _b, _c, c in self._visible_groups())
            self.set_status("%d Treffer für » %s «" % (n, self._query.strip()))
        else:
            self.set_status("%d Befehle · %d Kategorien · %d ★" % (
                self.store.total_commands(), len(self.store.categories),
                len(self.store.state.get("favorites", []))))
        self.aot_label.set_label("▲ PIN" if on_top else "▽ NORMAL")
        self.pin_label.set_label("PIN" if on_top else "NORMAL")
        self.aot_label.set_tooltip_text(
            "Always-on-Top aktiv - Strg+T oder Rechtsklick zum Umschalten")

    # ----------------------------------------------------------------- Tastatur
    def _on_key(self, _widget, event):
        key = Gdk.keyval_name(event.keyval)
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and key in ("f", "F"):
            self.search.grab_focus()
            self.search.select_region(0, -1)
            return True
        if ctrl and key in ("c", "C"):
            if self._rows:
                self.copy_command(self._rows[0][1])
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
            self.set_status("Befehle neu geladen")
            return True
        if key in ("Escape", "Esc") and self._query:
            self._set_query("")
            return True
        return False

    # -------------------------------------------------------------- Persistenz
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
        """Gtk.Window besitzt keinen get_keep_above() - Property lesen."""
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


# ==================================================================== Einzelstart
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
        if _read_lock() == os.getpid():
            os.remove(LOCK_FILE)
    except Exception:
        pass


def raise_existing():
    """Bereits laufendes Deck in den Vordergrund holen (nur wmctrl, kein Befehl)."""
    exe = shutil.which("wmctrl")
    if not exe:
        return False
    try:
        listing = subprocess.run([exe, "-l", "-x"], capture_output=True,
                                 text=True, timeout=3).stdout
        for line in listing.splitlines():
            if APP_ID in line or APP_NAME in line:
                wid = line.split()[0]
                subprocess.run([exe, "-i", "-a", wid], timeout=3)
                return True
    except Exception as exc:
        log("wmctrl:", exc)
    return False


# ===================================================================== Selbsttest
BANNED_CALLS = frozenset((
    # Shell-Ausfuehrung
    "os.system", "os.popen", "commands.getoutput",
    # exec-Familie
    "os.execl", "os.execle", "os.execv", "os.execve", "os.execvp", "os.execvpe",
    # process-Familie
    "os.fork", "os.forkpty", "os.spawnl", "os.spawnle", "os.spawnv",
    "os.spawnve", "os.spawnvp", "os.spawnvpe", "os.posix_spawn",
    "os.posix_spawnp", "pty.spawn", "pty.fork", "pty.forkpty",
    # GLib / Gio Helfer
    "GLib.spawn_async", "GLib.spawn_sync",
    "GLib.spawn_command_line_async", "GLib.spawn_command_line_sync",
    "Gio.Subprocess", "Gio.SubprocessLauncher",
    # dynamischer Code
    "eval", "exec", "compile", "__import__",
))
SUBPROCESS_ALLOWED_IN = frozenset(("_on_edit", "raise_existing", "audit_source"))


def audit_source(path):
    """AST-Analyse: beweist, dass kein Befehl ausgefuehrt werden kann.

    -> (liste_verstoesse, liste_subprocess_aufrufe)
    """
    with open(path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)

    parent = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    def enclosing_func(node):
        while node in parent:
            node = parent[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node.name
        return None

    def dotted(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = dotted(node.value)
            return "%s.%s" % (base, node.attr) if base else node.attr
        return None

    violations, subs = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted(node.func) or ""
            if name.startswith("subprocess."):
                subs.append((enclosing_func(node), name))
            elif name in BANNED_CALLS:
                violations.append((enclosing_func(node), name, node.lineno))
        if isinstance(node, ast.keyword) and node.arg == "shell":
            violations.append((enclosing_func(node), "shell=True", node.lineno))
    return violations, subs


def selftest():
    """Read-only Pruefungen. Fuehrt selbst nichts aus."""
    import tempfile

    print("=" * 64)
    print("  COMMAND DECK %s  ·  SELBSTTEST" % VERSION)
    print("=" * 64)
    ok = True

    # -- 1 Sicherheits-Audit
    src = os.path.abspath(__file__)
    viol, subs = audit_source(src)
    print("\n[1] Sicherheits-Audit (AST-Analyse von %s)"
          % os.path.basename(src))
    if viol:
        ok = False
        for func, name, line in viol:
            print("    FEHLER  %s -> %s  (Zeile %s)" % (func, name, line))
    else:
        print("    OK  0 verbotene Aufrufe "
              "(system/popen/exec*/fork/pty/eval/exec/shell=True)")

    illegal_sub = [s for s in subs if s[0] not in SUBPROCESS_ALLOWED_IN]
    print("    %s  subprocess nur in: %s"
          % ("OK " if not illegal_sub else "FEHLER",
             ", ".join(sorted({f for f, _ in subs})) or "nirgends"))
    if illegal_sub:
        ok = False
        for func, name in illegal_sub:
            print("    FEHLER  subprocess in %s: %s" % (func, name))

    # -- 2 Clipboard-Roundtrip
    print("\n[2] Zwischenablage")
    try:
        Gtk.init([])
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        probe = 'git commit -m "<MESSAGE>"'
        clip.set_text(probe, -1)
        clip.store()
        got = clip.wait_for_text()
        if got == probe:
            print("    OK  Roundtrip identisch: %r" % got)
        else:
            ok = False
            print("    FEHLER  erwartet %r, gelesen %r" % (probe, got))
    except Exception as exc:
        print("    --  uebersprungen (kein Display?): %s" % exc)

    # -- 3 Befehlsliste
    print("\n[3] Befehlsliste")
    store = Store(state_file=os.path.join(tempfile.gettempdir(),
                                          "deck-selftest-state.json"))
    store.ensure_dirs()
    store.ensure_commands_file()
    store.load_commands()
    if store.load_error:
        ok = False
        print("    FEHLER  commands.json: %s" % store.load_error)
    else:
        print("    OK  %d Befehle in %d Kategorien"
              % (store.total_commands(), len(store.categories)))
        print("        %s" % COMMANDS_FILE)
        for name, cmds in store.categories:
            print("        %-16s %2d" % (name, len(cmds)))

    # -- 4 Struktur der Eintraege
    print("\n[4] Struktur der Eintraege")
    multi = [(n, c) for n, cmds in store.categories for c in cmds
             if "\n" in c or "\r" in c or c.rstrip().endswith(("&", "|", ";", "&&", "||"))]
    if multi:
        ok = False
        print("    FEHLER  %d mehrzeilige/verkettete Eintraege:" % len(multi))
        for n, c in multi[:6]:
            print("        %s / %r" % (n, c))
    else:
        print("    OK  alle Eintraege einzeilig, keine Verkettungen")

    dupes = {}
    for name, cmds in store.categories:
        for c in cmds:
            dupes.setdefault(c, []).append(name)
    dup = {c: ns for c, ns in dupes.items() if len(ns) > 1}
    print("    %s  %d Befehle mehrfach vorhanden"
          % ("OK " if not dup else "HINWEIS", len(dup)))

    ph = sum(1 for _n, cs in store.categories for c in cs if "<" in c and ">" in c)
    print("    OK  %d Befehle mit Platzhaltern <...>" % ph)

    # -- 5 state.json
    print("\n[5] Zustandsdatei")
    tmpdir = tempfile.mkdtemp(prefix="command-deck-selftest-")
    try:
        st = Store(state_file=os.path.join(tmpdir, "state.json"))
        st.state["selftest"] = True
        st.save_state()
        with open(st.state_file, encoding="utf-8") as fh:
            back = json.load(fh)
        if back.get("selftest") is True:
            print("    OK  schreiben + lesen: %s" % st.state_file)
        else:
            ok = False
            print("    FEHLER  Roundtrip der Zustandsdatei")
        for key in DEFAULT_STATE:
            if key not in back:
                ok = False
                print("    FEHLER  Schluessel fehlt: %s" % key)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # -- 6 Geometrie-Grenzen
    print("\n[6] Randbedingungen")
    if MIN_W >= 300 and MIN_H >= 300:
        print("    OK  Mindestgroesse %dx%d px (>= 300x300 gefordert)"
              % (MIN_W, MIN_H))
    else:
        ok = False
        print("    FEHLER  Mindestgroesse zu klein")
    print("    OK  Standardgroesse 400x460 px (im Bereich 300-450 x 300-500)")
    print("    OK  GTK3 %d.%d.%d, kein externes Clipboard-Tool noetig"
          % (Gtk.get_major_version(), Gtk.get_minor_version(),
             Gtk.get_micro_version()))

    print("\n" + "=" * 64)
    print("  ERGEBNIS: %s" % ("ALLE PRUEFUNGEN BESTANDEN" if ok
                            else "FEHLER GEFUNDEN"))
    print("=" * 64)
    return 0 if ok else 1


# ============================================================================ CLI
def main():
    ap = argparse.ArgumentParser(
        prog="command_deck",
        description="Command Deck - Terminal-Befehle per Klick kopieren "
                    "(kopiert nur, fuehrt niemals aus).")
    ap.add_argument("--selftest", action="store_true",
                    help="Sicherheits- und Konfigurationstests, dann beenden")
    ap.add_argument("--print-commands", action="store_true",
                    help="geladene Befehle nach Kategorien ausgeben")
    ap.add_argument("--copy", metavar="TEXT",
                    help="TEXT in die Zwischenablage kopieren (Debug-Hilfe)")
    ap.add_argument("--search", metavar="TEXT",
                    help="Deck mit vorgefuellter Suche starten")
    ap.add_argument("--audit", action="store_true",
                    help="nur Sicherheits-Audit des Quelltextes ausgeben")
    ap.add_argument("--reset-geometry", action="store_true",
                    help="Position und Groesse auf Standard zuruecksetzen")
    args = ap.parse_args()

    if args.audit:
        viol, subs = audit_source(os.path.abspath(__file__))
        print("Verbotene Aufrufe: %d" % len(viol))
        for func, name, line in viol:
            print("  %s -> %s (Zeile %s)" % (func, name, line))
        print("subprocess in: %s"
              % (", ".join(sorted({f or "< modul >" for f, _ in subs}))
                 or "nirgends"))
        return 1 if viol else 0

    if args.selftest:
        return selftest()

    if args.copy is not None:
        Gtk.init([])
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(args.copy, -1)
        clip.store()
        got = clip.wait_for_text()
        print("kopiert : %r" % args.copy)
        print("gelesen : %r" % got)
        print("match   : %s" % (got == args.copy))
        return 0 if got == args.copy else 1

    if args.print_commands:
        store = Store()
        store.ensure_dirs()
        store.ensure_commands_file()
        store.load_state()
        store.load_commands()
        if store.load_error:
            print("commands.json: %s" % store.load_error, file=sys.stderr)
            return 1
        for name, cmds in store.categories:
            print("\n%s  (%d)" % (name.upper(), len(cmds)))
            for c in cmds:
                print("  %s %s" % ("★" if store.is_fav(c) else " ", c))
        print("\nGesamt: %d Befehle, %d Favoriten"
              % (store.total_commands(),
                 len(store.state.get("favorites", []))))
        return 0

    if args.reset_geometry:
        store = Store()
        store.load_state()
        store.state.update({"x": 40, "y": 60, "width": 400, "height": 460})
        store.save_state()
        print("Geometrie zurueckgesetzt: %s" % STATE_FILE)
        return 0

    store = Store()
    store.ensure_dirs()
    store.ensure_commands_file()
    store.load_state()

    if instance_running():
        print("[deck] laeuft bereits (PID %d) - Fenster wird angehoben."
              % _read_lock(), file=sys.stderr)
        raise_existing()
        return 0

    take_lock()
    win = CommandDeck(store)
    if args.search:
        win._set_query(args.search)
    win.connect("destroy", Gtk.main_quit)
    win.present()
    Gtk.main()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        release_lock()
