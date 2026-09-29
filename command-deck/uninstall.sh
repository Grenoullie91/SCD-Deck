#!/usr/bin/env bash
#
#  COMMAND DECK  ·  uninstall.sh
#
#  Entfernt Autostart, Menüeintrag, Symbol und (optional) die Konfiguration.
#  Andere Desktop-Einstellungen werden NICHT angefasst - es werden ausschliesslich
#  die Dateien geloescht, die install.sh selbst angelegt hat.
#
#  Aufruf:
#     ./uninstall.sh              Widget + Autostart entfernen, Konfiguration behalten
#     ./uninstall.sh --purge      zusaetzlich Befehlsliste und Zustand loeschen
#     ./uninstall.sh --keep-config mit --purge ignoriert
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$PROJECT_DIR/app/command_deck.py"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_STATE_DIR="$CONFIG_DIR/terminal-clipboard"
COMMANDS_FILE="$APP_STATE_DIR/commands.json"
STATE_FILE="$APP_STATE_DIR/state.json"
AUTOSTART_FILE="$CONFIG_DIR/autostart/command-deck.desktop"
MENU_FILE="$HOME/.local/share/applications/command-deck.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/scalable/apps/command-deck.svg"

PURGE=0

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; YEL=$'\033[1;33m'
CYN=$'\033[1;36m'; DIM=$'\033[2m';    BLD=$'\033[1m'; OFF=$'\033[0m'

ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
head2(){ printf '\n%s%s%s\n' "$BLD" "$1" "$OFF"; }

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --purge)       PURGE=1 ;;
        --keep-config) PURGE=0 ;;
        --help|-h)     usage ;;
        *) printf '\n  unbekannte Option: %s  (--help)\n\n' "$1" >&2; exit 1 ;;
    esac
    shift
done

printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$CYN" "$OFF"
printf '%s│  ◈ COMMAND DECK  ·  Deinstallation           │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"

# ------------------------------------------------------------------ laufendes Widget
head2 "1  Laufendes Widget beenden"
LOCK="$APP_STATE_DIR/instance.lock"
STOPPED=0
if [ -f "$LOCK" ]; then
    PID="$(cat "$LOCK" 2>/dev/null || true)"
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null && { ok "Prozess $PID beendet"; STOPPED=1; } || true
    else
        info "kein laufender Prozess (Lock veraltet)"
    fi
else
    info "kein Lock vorhanden – Widget läuft nicht"
fi
# Reserve: alle Prozesse, die wirklich dieses Skript ausführen
for p in $(pgrep -x python3 2>/dev/null || true); do
    if tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null \
       | grep -q "command_deck\.py"; then
        kill "$p" 2>/dev/null && { ok "Prozess $p beendet"; STOPPED=1; } || true
    fi
done
[ "$STOPPED" -eq 0 ] && info "nichts zu beenden"

# --------------------------------------------------------------------- Entfernen
head2 "2  Einträge entfernen"
rm_safe() {
    if [ -e "$1" ]; then
        rm -f "$1" && ok "entfernt: $1" || warn "konnte nicht entfernen: $1"
    else
        info "nicht vorhanden: $1"
    fi
}
rm_safe "$AUTOSTART_FILE"
rm_safe "$MENU_FILE"
rm_safe "$ICON_FILE"
rm_safe "$LOCK"
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

if [ "$PURGE" -eq 1 ]; then
    head2 "3  Konfiguration löschen (--purge)"
    if [ -d "$APP_STATE_DIR/backups" ]; then
        warn "Backups werden NICHT gelöscht:"
        ls -1 "$APP_STATE_DIR/backups" | sed 's/^/      /'
        info "mit ./restore.sh widerrufbar"
    fi
    for f in "$COMMANDS_FILE" "$STATE_FILE" "$APP_STATE_DIR/seed_favorites.json" \
             "$APP_STATE_DIR/selftest.log" "$APP_STATE_DIR/.last-backup"; do
        rm_safe "$f"
    done
    rmdir "$APP_STATE_DIR" 2>/dev/null \
        && ok "Verzeichnis entfernt: $APP_STATE_DIR" || true
else
    head2 "3  Konfiguration behalten"
    [ -d "$APP_STATE_DIR" ] && ok "deine Befehle und Favoriten bleiben erhalten:"
    info "$COMMANDS_FILE"
    [ -f "$STATE_FILE" ] && info "$STATE_FILE"
    info "vollständig löschen: ./uninstall.sh --purge"
fi

find "$PROJECT_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

head2 "Fertig"
if [ "$PURGE" -eq 1 ]; then
    cat <<EOF
  ${GRN}Command Deck vollständig entfernt.${OFF}

  ${DIM}Das Projektverzeichnis $PROJECT_DIR
  wurde bewusst NICHT gelöscht – löschen mit:
      rm -rf "$PROJECT_DIR"${OFF}
EOF
else
    cat <<EOF
  ${GRN}Command Deck deinstalliert (Daten bleiben erhalten).${OFF}

  ${DIM}Erneut installieren:      ./install.sh
  Befehlsliste ansehen:         $COMMANDS_FILE
  Alles inkl. Daten löschen:    ./uninstall.sh --purge${OFF}
EOF
fi
printf '\n'
