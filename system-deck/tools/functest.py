#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYSTEM DECK  ·  tools/functest.py
==================================

Funktionsabnahme. Führt JEDEN Eintrag mit TYPE=READ genau einmal aus -
mit exakt demselben Codeweg wie das Deck (ohne Shell, mit Zeitlimit).

Es werden ausschließlich Lesebefehle ausgeführt. Es wird kein Terminal
geöffnet, kein sudo verwendet, nichts verändert. COPY/TERM/ADMIN werden
nur geprüft, nicht ausgeführt.

Aufruf:  python3 tools/functest.py [--only KATEGORIE]
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))

import system_deck as sd  # noqa: E402

GREEN, YELLOW, RED, DIM, OFF = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].upper()

    store = sd.Store()
    store.load_commands()
    term = sd.detect_terminal()
    items = store.build_items(term)
    items = [i for i in items if not only or i["category"] == only]

    print("System Deck · Funktionsabnahme (nur TYPE=READ)")
    print("=" * 78)

    ok = warn = err = skip = 0
    slow = []
    cur = None
    started = time.time()

    for item in items:
        if item["category"] != cur:
            cur = item["category"]
            print("\n  %s" % cur.upper())
        name = item["name"][:38]
        etype = item["type"]

        if etype != "READ":
            print("    %s·%s %-38s %-6s %s"
                  % (YELLOW, OFF, name, etype, "geprüft, nicht ausgeführt"))
            continue
        if item["blocked"]:
            print("    %s!%s %-38s %s" % (RED, OFF, name, "GESPERRT"))
            continue
        if item.get("prompt"):
            print("    %s·%s %-38s %s" % (YELLOW, OFF, name,
                                          "braucht Suchbegriff - übersprungen"))
            continue
        if item["missing"]:
            print("    %s·%s %-38s %s" % (YELLOW, OFF, name,
                                          "nicht verfügbar: %s"
                                          % ", ".join(item["missing"])))
            skip += 1
            continue

        t0 = time.time()
        # Platzhalter genau so ersetzen wie das Deck es tut
        argv = [str(a).replace("{user}", os.environ.get("USER", ""))
                .replace("{home}", os.path.expanduser("~"))
                for a in item["argv"]]
        rc, raw, timed_out, error = sd.run_argv(
            argv,
            timeout=int(item.get("timeout_s") or store.setting("timeout_s", 10)))
        allowed = [int(x) for x in (item.get("allow_rc") or [0])]
        dt = time.time() - t0
        text = (raw or b"").decode("utf-8", "replace")
        lines = [l for l in text.splitlines() if l.strip()]

        if timed_out:
            print("    %s!%s %-38s %s" % (RED, OFF, name, "TIMEOUT nach %ds" % sd.CMD_TIMEOUT_S))
            err += 1
        elif rc in allowed and lines:
            print("    %s✔%s %-38s %-9s %3d Zeilen"
                  % (GREEN, OFF, name, "%.1fs" % dt, len(lines)))
            ok += 1
        elif rc in allowed:
            print("    %s✔%s %-38s %-9s (leer, aber erfolgreich)"
                  % (GREEN, OFF, name, "%.1fs" % dt))
            ok += 1
        else:
            reason = (error or (lines[0] if lines else "unbekannt"))[:30]
            print("    %s✕%s %-38s %-9s Status %s: %s"
                  % (RED, OFF, name, "%.1fs" % dt, rc, reason))
            err += 1
        if dt > 3:
            slow.append((dt, name))

    print("\n" + "=" * 78)
    print("  erfolgreich   : %d" % ok)
    print("  nicht verfügbar: %d  (Werkzeug fehlt - kein Fehler)" % skip)
    print("  Fehler        : %d" % err)
    print("  Dauer         : %.1f s" % (time.time() - started))
    if slow:
        print("  langsam (>3 s): %s"
              % ", ".join("%s (%.1fs)" % (n, d) for d, n in
                          sorted(slow, reverse=True)))
    print("=" * 78)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
