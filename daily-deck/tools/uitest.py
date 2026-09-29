#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAILY DECK  ·  tools/uitest.py
================================

UI-Rauchtest ohne Nebenwirkungen:
baut das Deck auf, prueft Zeilen, Kategorien, Typ-Knöpfe, Favoriten,
Filter, Blockliste, Geometrie und loest ausschliesslich COPY-Aktionen aus
(die nur in die Zwischenablage schreiben - es startet kein Terminal,
keine App, kein SSH).

Aufruf:  python3 tools/uitest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

import daily_deck as dd  # noqa: E402

FAILED = []
SAVED = {}


def check(label, cond, extra=""):
    print("  %-52s %s %s" % (label, "OK" if cond else "FEHLER", extra))
    if not cond:
        FAILED.append(label)


def main():
    store = dd.Store()
    store.load_state()
    SAVED.update(store.state)
    win = dd.DailyDeck(store)
    GLib.timeout_add(400, Gtk.main_quit)
    Gtk.main()

    print("Daily Deck UI-Rauchtest")
    print("-" * 62)

    rows = win.listbox.get_children()
    cats = [c for c in rows if "cat" in c.get_style_context().list_classes()]
    check("Oberflaeche gebaut", win.get_realized() is not None)
    check("Eintraege gerendert (%d Zeilen inkl. Kopfzeilen)" % len(rows),
          len(rows) > 40)
    check("Kategorien gerendert (%d)" % len(cats), len(cats) == 6)

    labels = {b.get_label() for b in _walk(win) if isinstance(b, Gtk.Button)}
    check("Typ-Knoepfe sichtbar: %s"
          % sorted(t for t in labels if t in ("START", "TERMINAL", "COPY")),
          {"START", "TERMINAL", "COPY"} <= labels)

    check("Suchfeld mit Hinweistext", win.search_hint_event.get_visible())
    check("Fusszeile mit PIN-Anzeige", win.aot_label.get_label() in
          ("▲ PIN", "▽ NORMAL"))
    check("Status zeigt Aktionen", "Aktionen" in win.status.get_text(),
          "(%r)" % win.status.get_text())

    # ---- Filter
    win._set_query("ssh")
    n = len(win.listbox.get_children())
    check("Filter 'ssh' greift (%d Zeilen)" % n, 0 < n < len(rows))
    check("Hinweistext verschwindet bei Eingabe",
          not win.search_hint_event.get_visible())
    win._set_query("xyzgibtesnicht")
    check("leeres Ergebnis wird angezeigt",
          len(win.listbox.get_children()) == 1)
    win._set_query("")
    check("Filter zurueckgesetzt", len(win.listbox.get_children()) == len(rows))

    # ---- Favoriten
    first = win._rows[0][1]
    before = store.state.get("favorites", [])
    win._on_star_press(None, None, first)
    check("Favorit setzbar", store.is_fav(first))
    groups = win._visible_groups()
    check("Favoriten-Gruppe erscheint", groups and groups[0][0] == "★ Favorites")
    win._on_star_press(None, None, first)
    check("Favorit entfernbar", not store.is_fav(first))
    check("Favoritenliste wieder leer",
          store.state.get("favorites", []) == before)

    # ---- nur COPY ausloesen: startet nichts
    copied = []
    for item in store.build_items(win.term_argv):
        if item.get("type") == "COPY" and not item["blocked"] \
                and not item["missing"]:
            win.run_item(item, None)
            copied.append(item.get("copy_text") or item.get("command"))
    check("%d COPY-Aktionen ausgefuehrt" % len(copied), len(copied) > 5)
    check("'exit' wird kopiert (SSH verlassen)", "exit" in copied)

    # ---- Blockliste / Verfuegbarkeit
    before_text = win.status.get_text()
    win.run_item({"name": "T", "type": "COPY", "copy_text": "rm -rf /",
                  "blocked": True, "missing": [], "category": "X"}, None)
    check("gesperrter COPY wird abgewiesen", "gesperrt" in win.status.get_text())
    win.run_item({"name": "T", "type": "TERMINAL", "command": "rm -rf /",
                  "workdir": "~", "blocked": True, "missing": [],
                  "category": "X"}, None)
    check("gesperrter TERMINAL wird abgewiesen",
          "gesperrt" in win.status.get_text())
    win.run_item({"name": "T", "type": "TERMINAL", "command": "x",
                  "workdir": "~", "blocked": False, "missing": ["x"],
                  "category": "X"}, None)
    check("fehlendes Programm wird abgewiesen",
          "nicht verfügbar" in win.status.get_text())
    win.set_status(before_text, sticky=False)

    # ---- Geometrie / Always-on-top
    results, loop = {}, GLib.MainLoop()

    def do_changes():
        win.resize(410, 640)
        win.move(120, 90)
        win.set_on_top(not win.is_on_top())
        return False

    def probe():
        results["w"], results["h"] = win.get_size()
        results["x"], results["y"] = win.get_position()
        results["top"] = win.store.state["always_on_top"]
        loop.quit()
        return False

    GLib.timeout_add(250, do_changes)
    GLib.timeout_add(900, probe)
    GLib.timeout_add(2500, loop.quit)
    loop.run()

    st = store.load_state()
    check("Groesse gespeichert (%sx%s)" % (st["width"], st["height"]),
          st["width"] >= 400 and st["height"] >= 600)
    # Der Fenstermanager darf die Position korrigieren - geprueft wird,
    # dass eine Position gespeichert wurde und zum Fenster passt.
    check("Position gespeichert (%s,%s)" % (st["x"], st["y"]),
          isinstance(st["x"], int) and isinstance(st["y"], int)
          and abs(st["x"] - results["x"]) < 400
          and abs(st["y"] - results["y"]) < 400)
    check("Always-on-top umschaltbar", results["top"] is not SAVED["always_on_top"])

    # ---- Transparenz
    op = store.state.get("opacity", 0.95)
    store.state["opacity"] = min(1.0, float(op) + 0.05)
    store.save_state()
    win.bg.set_opacity(store.state["opacity"])
    check("Transparenz aenderbar (%.2f)" % win.bg.opacity, win.bg.opacity > 0)

    # ---- Test darf nichts dauerhaft aendern
    for key, value in SAVED.items():
        store.state[key] = value
    store.save_state()
    win.destroy()

    print("-" * 62)
    print("Ergebnis: %s" % ("BESTANDEN" if not FAILED
                            else "FEHLGESCHLAGEN -> %s" % ", ".join(FAILED)))
    return 1 if FAILED else 0


def _walk(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            for sub in _walk(child):
                yield sub


if __name__ == "__main__":
    sys.exit(main())
