#!/usr/bin/env bash
#
#  SCD-DECK  ·  check.sh
#
#  Fuehrt alle vorhandenen Pruefwerkzeuge der drei Decks aus.
#  Aendert NICHTS: kein Installationsschritt, kein Schreibzugriff ausser dem
#  eigenen Bytecode-Cache (__pycache__) der Python-Dateien.
#
#  Aufruf:
#     ./check.sh                 alle Pruefungen
#     ./check.sh selftest        nur --selftest der drei Decks
#     ./check.sh audit           nur Konfigurations-Audits
#     ./check.sh design          nur Design-/Theme-Abgleich
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHAT="${1:-all}"

GRN=$'\033[1;32m'; RED=$'\033[1;31m'; CYN=$'\033[1;36m'
YEL=$'\033[1;33m'; BLD=$'\033[1m';    OFF=$'\033[0m'
FAILED=0

h2() { printf '\n%s%s%s\n' "$BLD" "$1" "$OFF"; }
run() {
    local label="$1"; shift
    printf '\n%s--- %s%s\n' "$CYN" "$label" "$OFF"
    if "$@"; then
        printf '%s  OK%s  %s\n' "$GRN" "$OFF" "$label"
    else
        printf '%s  FEHLGESCHLAGEN%s  %s\n' "$RED" "$OFF" "$label"
        FAILED=1
    fi
}
skip() { printf '\n%s--- %s (uebersprungen)%s\n' "$YEL" "$1" "$OFF"; }

printf '%s\n' "$BLD"
printf '  ◈ SCD-DECK  ·  Prueflauf\n'
printf '  Repository: %s\n' "$ROOT"
printf '  Python:     %s\n' "$(python3 --version 2>&1)"
printf '  GTK3:       %s\n' "$(python3 -c 'import gi; gi.require_version("Gtk","3.0"); from gi.repository import Gtk; print("GTK", Gtk.get_major_version(), Gtk.get_minor_version())' 2>&1 | tail -1)"
printf '%s\n' "$OFF"

if [ "$WHAT" = all ] || [ "$WHAT" = selftest ]; then
    h2 "Selbsttests (Konfiguration + Sicherheitsregeln)"
    run "Command Deck  --selftest" python3 "$ROOT/command-deck/app/command_deck.py" --selftest
    run "Daily Deck    --selftest" python3 "$ROOT/daily-deck/app/daily_deck.py" --selftest
    run "System Deck   --selftest" python3 "$ROOT/system-deck/app/system_deck.py" --selftest
fi

if [ "$WHAT" = all ] || [ "$WHAT" = audit ]; then
    h2 "Konfigurations-Audits (nur lesend)"
    run "Command Deck  --audit"    python3 "$ROOT/command-deck/app/command_deck.py" --audit
    run "Daily Deck    tools/audit.py" python3 "$ROOT/daily-deck/tools/audit.py"
    run "System Deck   --audit"    python3 "$ROOT/system-deck/app/system_deck.py" --audit
fi

if [ "$WHAT" = all ] || [ "$WHAT" = design ]; then
    h2 "Design-Familie"
    run "Theme-Abgleich aller drei Decks" python3 "$ROOT/system-deck/tools/theme-check.py"
fi

printf '\n'
if [ "$FAILED" -eq 0 ]; then
    printf '%s✔ Prueflauf beendet - alles gruen.%s\n\n' "$GRN" "$OFF"
else
    printf '%s! Prueflauf beendet - mindestens eine Pruefung ist fehlgeschlagen.%s\n\n' "$RED" "$OFF"
    exit 1
fi
