#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYSTEM DECK  ·  tools/theme-check.py
====================================

Prüft, ob das System Deck really aus derselben Designfamilie besteht wie
Command Deck und Daily Deck - ohne dass eines der beiden verändert wird.

Verglichen wird der gemeinsame Grundblock (Variablen, .deck, .header,
.title, .glyph, .search, .row, .copy, .footer, .grip, menu, tooltip) der
drei theme.css. Nur die drei Decks-eigenen Abschnitte dürfen abweichen.

Aufruf:  python3 tools/theme-check.py
"""

import difflib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
REPO = os.path.dirname(PROJECT)
HOME = os.path.expanduser("~")


def sibling(subdir, legacy):
    """Schwester-Deck: im Monorepo neben diesem Deck, sonst am Legacy-Pfad."""
    candidate = os.path.join(REPO, subdir)
    return candidate if os.path.isdir(candidate) else os.path.join(HOME, legacy)


THEMES = [
    ("Command Deck", os.path.join(sibling("command-deck", "TerminalCommandWidget"),
                                  "assets/theme.css")),
    ("Daily Deck",   os.path.join(sibling("daily-deck", "DailyDeck"),
                                  "assets/theme.css")),
    ("System Deck",  os.path.join(PROJECT, "assets/theme.css")),
]

# Abschnitt, der in jedem Deck abweichen darf
CUSTOM = {
    "Command Deck": [],
    "Daily Deck": ["DAILY DECK :: Aktionsknöpfe"],
    "System Deck": ["AKTIONSKNÖPFEN", "SYSTEM DECK ::"],
}


# Ab dort beginnt der deckeigene Abschnitt - nur dieser darf abweichen.
CUSTOM_MARKER = {
    "Command Deck": None,                       # keine eigenen Abschnitte
    "Daily Deck": "DAILY DECK :: Aktionskn",
    "System Deck": "AKTIONSKN",
}


def shared_block(name, text):
    """Der Teil des Themes, der gemeinsam sein MUSS."""
    marker = CUSTOM_MARKER.get(name)
    if marker is None:
        return text
    idx = text.rfind(marker)          # letzte Vorkommen: die echte Sektion
    if idx < 0:
        return text
    # bis zum_beginn des Abschnitts-Kommentars zurückschneiden
    start = text.rfind("/* =====", 0, idx)
    return text[:start if start > 0 else idx]


def normalized(text):
    """Kommentare und Leerzeilen entfernen, Rest zeilenweise sortiert."""
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = [" ".join(l.split()) for l in body.splitlines()]
    return [l for l in lines if l]


def main():
    ok = True
    print("System Deck \u00b7 Theme-Abgleich")
    print("=" * 72)

    loaded = {}
    for name, path in THEMES:
        if not os.path.isfile(path):
            print("  ! %-14s nicht gefunden: %s" % (name, path))
            ok = False
            continue
        with open(path, "r", encoding="utf-8") as fh:
            loaded[name] = fh.read()
        print("  %-14s %s" % (name, path))
    if not loaded:
        return 1

    print("\n  1  Farbpalette (@define-color)")
    palettes = {name: dict(re.findall(
        r"@define-color\s+(\S+)\s+(#[0-9A-Fa-f]{6})", text))
        for name, text in loaded.items()}
    base = "Command Deck" if "Command Deck" in palettes else list(palettes)[0]
    for name, pal in palettes.items():
        same = pal == palettes[base]
        print("    %-14s %2d Farben  %s"
              % (name, len(pal), "identisch" if same else "ABWEICHUNG"))
        if not same:
            ok = False

    print("\n  2  Gemeinsamer Grundblock (Regeln vor dem eigenen Abschnitt)")
    base_lines = normalized(shared_block(base, loaded[base]))
    print("    Referenz: %s mit %d CSS-Zeilen" % (base, len(base_lines)))
    for name, text in loaded.items():
        if name == base:
            continue
        lines = normalized(shared_block(name, text))
        missing = [l for l in base_lines if l not in lines]
        if not missing:
            print("    %-14s %d Zeilen - vollstaendig identisch" % (name, len(lines)))
            continue
        ok = False
        print("    \u25b8 %-14s %d Zeilen - %d abweichend:"
              % (name, len(lines), len(missing)))
        for line in missing[:14]:
            print("        - %s" % line[:66])

    print("\n  3  Deckeigene Erweiterungen des System Decks")
    own = loaded.get("System Deck", "")
    idx = own.find(CUSTOM_MARKER["System Deck"])
    tail = own[idx:] if idx > 0 else ""
    classes = sorted(set(re.findall(r"^\.([a-z0-9-]+)", tail, re.M)))
    print("    Klassen    : %s" % ", ".join("." + c for c in classes))
    sizes = sorted(set(re.findall(r"font-size:\s*([0-9.]+px)", tail)))
    radii = sorted(set(re.findall(r"border-radius:\s*([0-9]+px)", tail)))
    fonts = sorted(set(re.findall(r'font-family:\s*"?([^";]+)', tail)))
    print("    Schriftgroesse: %s" % ", ".join(sizes))
    print("    Eckenradien  : %s" % ", ".join(radii))
    print("    Schrift       : %s" % fonts)
    print("    -> nur Werte, die im Grundblock bereits vorkommen: %s"
          % all(s in {"7px", "7.5px", "8.5px", "9px", "9.5px", "10px", "11px", "12px"}
              for s in sizes))

    print("\n" + "=" * 72)
    print("  Ergebnis: %s" % ("GEMEINSAME DESIGNFAMILIE BEST\u00c4TIGT"
                             if ok else "Abweichungen gefunden"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
