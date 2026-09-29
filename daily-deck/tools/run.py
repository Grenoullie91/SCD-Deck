#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAILY DECK  ·  tools/run.py
============================

Startet einen Daily-Deck-Eintrag per Namen - praktisch fuer
"wofuer wird das Deck benutzt?" und zum Testen einzelner Aktionen.

Aufruf:
    python3 tools/run.py --list
    python3 tools/run.py --show "Downloads"
    python3 tools/run.py "Home"          fuehrt die Aktion wirklich aus

Ohne --show/--list wird die Aktion ausgefuehrt (gleiche Logik wie ein Klick).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))

import daily_deck as dd  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="Teil des Eintragsnamens")
    ap.add_argument("--list", action="store_true", help="alle Eintraege listen")
    ap.add_argument("--show", metavar="NAME", help="nur anzeigen, nicht ausfuehren")
    ap.add_argument("--all", action="store_true", help="alle Treffer ausfuehren")
    args = ap.parse_args()

    store = dd.Store()
    store.load_commands()
    term = dd.detect_terminal()
    items = store.build_items(term)

    if args.list or (not args.name and not args.show):
        for it in items:
            miss = ("  [FEHLT: %s]" % ",".join(it["missing"])) if it["missing"] else ""
            blk = "  [GESPERRT]" if it["blocked"] else ""
            print("%-9s %-9s %-36s %s%s%s"
                  % (it["type"], it["category"], it["name"],
                     it.get("description", ""), miss, blk))
        return 0

    needle = (args.show or args.name).lower()
    hits = [it for it in items if needle in it["name"].lower()
            or needle in it.get("description", "").lower()]
    if not hits:
        print("kein Eintrag passt zu %r" % needle, file=sys.stderr)
        return 1

    for it in hits:
        print("== %s  [%s]  %s" % (it["name"], it["type"], it["description"]))
        if it["type"] == "TERMINAL":
            wd = os.path.expanduser(it.get("workdir") or "~")
            print("   Terminal : %s" % " ".join(dd.detect_terminal()))
            print("   Verzeichnis: %s" % wd)
            print("   Befehl  : %s" % (it.get("command") or "-"))
        elif it["type"] == "START":
            print("   Programm : %s" % " ".join(it.get("argv") or []))
        else:
            print("   kopiert  : %s" % (it.get("copy_text") or it.get("command")))
        if args.show:
            continue
        if it["blocked"]:
            print("   -> nicht ausgefuehrt (gesperrt)")
            continue
        if it["missing"]:
            print("   -> nicht ausgefuehrt (fehlt: %s)" % ", ".join(it["missing"]))
            continue
        if it["type"] == "COPY":
            print("   -> Text zum Kopieren: %s"
                  % (it.get("copy_text") or it.get("command")))
        elif it["type"] == "TERMINAL":
            wd = os.path.expanduser(it.get("workdir") or "~")
            argv = dd.terminal_argv(term, wd, it.get("command") or None)
            ok, err = dd.run_argv(argv)
            print("   -> %s" % ("gestartet" if ok else "FEHLER: " + err))
        else:
            ok, err = dd.run_argv(it.get("argv") or [])
            print("   -> %s" % ("gestartet" if ok else "FEHLER: " + err))
        if not args.all:
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
