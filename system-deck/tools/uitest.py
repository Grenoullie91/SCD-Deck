#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYSTEM DECK  ·  tools/uitest.py
================================

UI-Rauchtest ohne Nebenwirkungen am System:

  * baut das Deck auf (gleicher Code wie der Normalbetrieb)
  * prüft Kategorien, Zeilen, Aktionsknöpfe, Blockliste, Verfügbarkeit
  * löst ausschließlich READ- und COPY-Aktionen aus - also reine
    Lesebefehle und Zwischenablage. Es wird KEIN Terminal geöffnet,
    kein Dienst gestartet, kein sudo verwendet, nichts verändert.
  * rendert das Deck offscreen in ein PNG (--shot DATEI), damit die
    Gestaltung ohne sichtbares Fenster geprüft werden kann

Aufruf:  python3 tools/uitest.py [--shot /tmp/system-deck.png]
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

import system_deck as sd  # noqa: E402

FAILED = []


def check(label, cond, extra=""):
    print("  %-54s %s %s" % (label, "OK" if cond else "FEHLER", extra))
    if not cond:
        FAILED.append(label)


def capture(deck, path, width=400, height=660):
    """Rendert den Deck-Inhalt offscreen in eine PNG-Datei."""
    content = deck.get_child()
    parent = content.get_parent()
    parent.remove(content)

    off = Gtk.OffscreenWindow()
    off.set_default_size(width, height)
    off.add(content)
    off.show_all()

    def grab():
        pb = off.get_pixbuf()
        if pb is None:
            print("  Offscreen-Render: FEHLGESCHLAGEN")
            FAILED.append("offscreen render")
        else:
            pb.savev(path, "png", [], [])
            print("  gerendert: %s  (%dx%d)" % (path, pb.get_width(), pb.get_height()))
        Gtk.main_quit()
        return False

    GLib.timeout_add(700, grab)
    Gtk.main()
    off.destroy()


def main():
    # WICHTIG: der Rauchtest darf die echte Position/Größe NICHT
    # überschreiben. state.json wird deshalb gesichert und
    # garantiert wiederhergestellt - auch im Fehlerfall.
    saved = None
    if os.path.exists(sd.STATE_FILE):
        with open(sd.STATE_FILE, "rb") as fh:
            saved = fh.read()
    try:
        return _run(sys.argv[1:])
    finally:
        if saved is not None:
            with open(sd.STATE_FILE, "wb") as fh:
                fh.write(saved)
            print("\n  state.json unverändert gelassen (Position des Decks)")


def _run(args):
    shot = None
    if "--shot" in args:
        shot = args[args.index("--shot") + 1]

    print("System Deck UI-Rauchtest")
    print("-" * 68)

    store = sd.Store()
    store.load_commands()
    store.load_state()
    deck = sd.SystemDeck(store)

    # ---------------------------------------------------------- Grundaufbau
    check("Fenster erzeugt / undekoriert", not deck.get_decorated())
    check("Position gespeichert (%s, %s)"
          % (store.state.get("x"), store.state.get("y")),
          store.state.get("positioned") and int(store.state.get("x")) >= 0)
    check("Theme geladen", deck._css is not None)
    check("%d Befehle geladen" % len(deck._items), len(deck._items) > 50)
    check("%d Kategorien im Raster" % len(deck._cat_buttons),
          len(deck._cat_buttons) >= 15)
    check("Suchfeld vorhanden", deck.search is not None)
    check("Ausgabefenster vorhanden (zu Beginn geschlossen)",
          deck.output_revealer.get_reveal_child() is False)
    quick = [(k, l, *fn()) for k, l, fn in sd.QC.all()]
    deck._render_check(quick)
    check("Standard-Quick-Check: 9 Felder",
          len(deck.check_grid.get_children()) == 9)
    print("      " + "  ".join("%s=%s" % (k, s) for k, _l, s, _t in quick))

    # ------------------------------------------------------------- Zeilen
    deck._rebuild_list()
    check("Listenansicht gefüllt (%d Zeilen)" % len(deck._rows), len(deck._rows) > 0)

    labels = []
    for row, item in deck._rows:
        for child in row.get_children():
            for btn in _walk_buttons(child):
                labels.append((btn.get_label(), item))
    types = {label for label, _ in labels}
    check("Nur KNOPF-Beschriftungen: %s" % sorted(types),
          types <= {"READ", "COPY", "TERM", "ADMIN"})
    check("Jede Zeile hat einen Hauptknopf",
          len(labels) >= len(deck._rows))

    # --------------------------------------------------------- Kategorien
    deck._on_cat_clicked(None, "LOGS")
    check("Kategorie LOGS gefiltert",
          all(i["category"] == "LOGS" for _r, i in deck._rows))
    check("LOGS-Knopf aktiv markiert",
          "on" in deck._cat_buttons["LOGS"].get_style_context().list_classes())
    deck._on_cat_clicked(None, "LOGS")
    check("Zweite Auswahl hebt Filter wieder auf", deck._category is None)

    # -------------------------------------------------------------- Suche
    deck._set_query("sensors")
    check("Suche 'sensors' findet Treffer", len(deck._rows) > 0)
    deck._set_query("___nix___")
    check("Suche ohne Treffer zeigt Hinweis", len(deck._rows) == 0)
    deck._set_query("")

    # --------------------------------------------------------- READ / COPY
    read_items = [i for i in deck._items if i["type"] == "READ"]
    free = [i for i in read_items if not i["missing"] and not i["blocked"]]
    target = next(i for i in free if "uname" in (i.get("cmd") or ""))
    loop = GLib.MainLoop()
    results = {}

    def on_result(token, res):
        results[token] = res
        loop.quit()
        return False

    deck.runner = sd.AsyncRunner(on_result)
    deck._pending_handlers[deck.store.key_of(target)] = lambda t, r: None
    deck.runner.submit("t", lambda: sd.run_argv(target["argv"], timeout=5))
    GLib.timeout_add(4000, lambda: (loop.quit(), False)[1])
    loop.run()
    rc, raw = results.get("t", (None, b""))[0], results.get("t", (0, b""))[1]
    check("READ führt ohne Shell aus (Status %s)" % rc, rc == 0 and b"Linux" in raw)

    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    deck._copy_item(target)
    text = clipboard.wait_for_text()
    check("COPY kopiert nur den Text", (text or "").startswith("uname"))

    # ------------------------------------------------- Ausgabe-Fenster
    deck.show_output("READ · TEST", "Zeile 1\nZeile 2\nZeile 3")
    check("Ausgabefenster öffnet",
          deck.output_revealer.get_reveal_child() is True)
    buf = deck.output_view.get_buffer()
    check("Ausgabe im Fenster sichtbar",
          buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
          == "Zeile 1\nZeile 2\nZeile 3")
    deck.hide_output()
    check("Ausgabefenster schließt wieder",
          deck.output_revealer.get_reveal_child() is False)

    # ------------------------------------------------- Sicherheitsregeln
    check("kein Eintrag gesperrt", not [i for i in deck._items if i["blocked"]])
    mutating = [i for i in deck._items
                if sd.is_mutation("%s %s" % (i.get("cmd") or "",
                                             " ".join(str(a) for a in
                                                      (i.get("argv") or []))))]
    check("verändernde Befehle werden nie ausgeführt (%d markiert)"
          % len(mutating),
          all(i["blocked"] or (i["type"] == "COPY" and i.get("mutating"))
              for i in mutating))
    check("READ/TERM/ADMIN sind nie mutierend ohne Sperre",
          not [i for i in mutating if i["type"] != "COPY" and not i["blocked"]])
    check("ADMIN-Einträge bestätigen sich (3 vorhanden)",
          len([i for i in deck._items if i["type"] == "ADMIN"]) == 3)
    check("Fehlende Werkzeuge werden als 'nicht verfügbar' gemeldet",
          len([i for i in deck._items if i["missing"]]) > 0)

    # ------------------------------------------------------ Schnellcheck
    check("Quick System Check liefert dynamische Werte",
          all(s in sd.STATUS_INFO for _k, _l, s, _t in quick))
    deck._render_check(quick)

    # ------------------------------------------------------------ Render
    if shot:
        capture(deck, shot)

    deck.destroy()
    print("-" * 68)
    print("Ergebnis: %s" % ("BESTANDEN" if not FAILED else
                            "FEHLGESCHLAGEN -> " + ", ".join(FAILED)))
    return 0 if not FAILED else 1


def _walk_buttons(widget):
    out = []
    if isinstance(widget, Gtk.Button):
        out.append(widget)
    if hasattr(widget, "get_children"):
        for child in widget.get_children():
            out.extend(_walk_buttons(child))
    return out


if __name__ == "__main__":
    sys.exit(main())
