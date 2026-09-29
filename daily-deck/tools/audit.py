#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAILY DECK  ·  tools/audit.py
================================

Prueft die geladene Konfiguration, ohne etwas auszufuehren.

  * meldet Typ, Ziel und Verfuegbarkeit jedes Eintrags
  * zeigt, welches Terminal erkannt wurde und mit welchen Argumenten
    ein TERMINAL-Eintrag tatsaechlich gestartet wuerde
  * weist gesperrte (destruktive) Befehle aus
  * listet die aus ~/.ssh/config gelesenen Aliase (ohne Schluessel/Passwoerter)

Aufruf:  python3 tools/audit.py
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))

import daily_deck as dd  # noqa: E402


def main():
    store = dd.Store()
    store.load_commands()
    term = dd.detect_terminal()
    items = store.build_items(term)

    print("=" * 78)
    print(" DAILY DECK  ·  Konfigurations-Audit")
    print("=" * 78)
    print(" Konfiguration : %s" % store.commands_file)
    print(" Terminal      : %s" % " ".join(term))
    print(" SSH-Aliase    : %s" % (", ".join(store.ssh_hosts) or "keine"))
    print(" Eintraege     : %d" % len(items))
    print("=" * 78)

    cur = None
    counts = {}
    problems = []

    for it in items:
        if it["category"] != cur:
            cur = it["category"]
            print("\n  %s  %s"  % (it.get("category_icon", ""), cur.upper()))
        counts[it["type"]] = counts.get(it["type"], 0) + 1

        flags = []
        if it.get("blocked"):
            flags.append("GESPERRT")
        if it.get("missing"):
            flags.append("FEHLT: " + ",".join(it["missing"]))

        print("    %-9s %-34s %s %s"
              % (it["type"], it["name"][:34],
                 it.get("description", "")[:26], ("[" + " ".join(flags) + "]")
                 if flags else ""))

        if it.get("blocked"):
            problems.append("gesperrt: %s" % it["name"])
        if it["type"] == "TERMINAL":
            wd = os.path.expanduser(it.get("workdir") or "~")
            argv = dd.terminal_argv(term, wd, it.get("command") or None)
            print("              -> %s" % " ".join(argv))
            if not argv:
                problems.append("kein Terminal-Argv: %s" % it["name"])
            if not os.path.isdir(wd):
                print("              !! Arbeitsverzeichnis fehlt: %s" % wd)
        elif it["type"] == "START":
            argv = it.get("argv") or []
            print("              -> %s   (geprueft: %s)"
                  % (" ".join(argv),
                     "ja" if argv and dd.shutil.which(argv[0]) else "NEIN"))
            if not argv:
                problems.append("START ohne argv: %s" % it["name"])

    print("\n" + "=" * 78)
    print(" Verteilung: %s" % ", ".join("%s=%d" % kv for kv in sorted(counts.items())))
    print(" SSH-Quelle : ~/.ssh/config (nur gelesen, nie geschrieben)")
    print(" Probleme   : %s" % (", ".join(problems) if problems else "keine"))
    print("=" * 78)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
