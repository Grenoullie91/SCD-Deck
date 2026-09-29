#!/usr/bin/env bash
#
#  SYSTEM DECK  ·  uninstall.sh
#
#  Entfernt AUSSCHLIESSLICH Dateien des System Deck.
#  Deinstalliert KEINE Programme.
#  Ändert NICHT:
#     · das bestehende Command Deck
#     · das bestehende Daily Deck
#     · das Wallpaper, Cairo-Dock oder das Panel
#
#  Aufruf:
#     ./uninstall.sh              entfernt Menü, Icon, Autostart, Projekt
#     ./uninstall.sh --purge      zusätzlich: ~/.config/system-deck inkl. Backups
#     ./uninstall.sh --keep-config  behält ~/.config/system-deck komplett
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$PROJECT_DIR")"
COMMAND_DECK_DIR="$REPO_DIR/command-deck"
DAILY_DECK_DIR="$REPO_DIR/daily-deck"
[ -d "$COMMAND_DECK_DIR" ] || COMMAND_DECK_DIR="$HOME/TerminalCommandWidget"
[ -d "$DAILY_DECK_DIR" ]    || DAILY_DECK_DIR="$HOME/DailyDeck"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_DIR="$CONFIG_DIR/system-deck"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/system-deck.desktop"
MENU_FILE="$HOME/.local/share/applications/system-deck.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/scalable/apps/system-deck.svg"
LOCK_FILE="$STATE_DIR/instance.lock"

PURGE=0
KEEP_CONFIG=0

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; YEL=$'\033[1;33m'
CYN=$'\033[1;36m'; BLD=$'\033[1m';    OFF=$'\033[0m'

ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
h2()   { printf '\n%s%s%s\n' "$BLD" "$1" "$OFF"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --purge)        PURGE=1 ;;
        --keep-config)  KEEP_CONFIG=1 ;;
        --help|-h)      sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unbekannte Option: %s\n' "$1" >&2; exit 1 ;;
    esac
    shift
done

printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$CYN" "$OFF"
printf '%s│  ◈ SYSTEM DECK  ·  Deinstallation           │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"

# ------------------------------------------------------------------ Stoppen
h2 "1  Laufende Instanz beenden"
if [ -f "$LOCK_FILE" ]; then
    PID="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null && ok "Prozess $PID beendet" \
            || warn "Prozess $PID ließ sich nicht beenden"
    else
        info "keine laufende Instanz"
    fi
    rm -f "$LOCK_FILE"
else
    info "kein Lockfile vorhanden"
fi

# ------------------------------------------------------------------ Dateien
h2 "2  System-Deck-Dateien entfernen"
rm -f "$MENU_FILE"  && ok "Menüeintrag entfernt"  || info "kein Menüeintrag"
rm -f "$ICON_FILE"  && ok "Symbol entfernt"       || info "kein System-Deck-Symbol"
if [ -f "$AUTOSTART_FILE" ]; then
    rm -f "$AUTOSTART_FILE"
    ok "Autostart entfernt ($AUTOSTART_FILE)"
else
    info "kein System-Deck-Autostart vorhanden"
fi
command -v gtk-update-icon-cache >/dev/null \
    && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

# ------------------------------------------------------------------ Projekt
h2 "3  Projektverzeichnis"
if [ "$KEEP_CONFIG" -eq 1 ]; then
    ok "bleibt erhalten: $PROJECT_DIR und $STATE_DIR (--keep-config)"
elif [ "$PURGE" -eq 0 ]; then
    ok "bleibt erhalten: $PROJECT_DIR (Quellcode + Befehlsvorlage)"
else
    cd /
    rm -rf "$PROJECT_DIR"
    ok "entfernt: $PROJECT_DIR"
fi

if [ "$PURGE" -eq 1 ] && [ "$KEEP_CONFIG" -eq 0 ]; then
    cd /
    rm -rf "$STATE_DIR"
    ok "entfernt: $STATE_DIR (inkl. Befehlsliste und Backups)"
else
    [ -d "$STATE_DIR" ] && ok "bleibt erhalten: $STATE_DIR"
fi

# ------------------------------------------------------------------- Schutz
h2 "4  Bestandsschutz bestätigt"
for d in "Command Deck (Projekt):$COMMAND_DECK_DIR" \
         "Command Deck (Konfiguration):$CONFIG_DIR/terminal-clipboard" \
         "Command Deck (Autostart):$AUTOSTART_DIR/command-deck.desktop" \
         "Daily Deck (Projekt):$DAILY_DECK_DIR" \
         "Daily Deck (Konfiguration):$CONFIG_DIR/daily-deck" \
         "Daily Deck (Autostart):$AUTOSTART_DIR/daily-deck.desktop"; do
    label="${d%%:*}"; path="${d#*:}"
    [ -e "$path" ] && ok "$label weiterhin vorhanden" || info "$label nicht vorhanden (unberührt)"
done
ok "Wallpaper unverändert"
ok "Cairo-Dock unverändert"
ok "Panel unverändert"
ok "Keine Programme deinstalliert"
ok "Keine Systemkonfiguration geändert"

printf '\n%s✔ Deinstallation abgeschlossen.%s\n' "$GRN" "$OFF"
printf '  Die Deinstallation läuft sauber zurück - ./install.sh stellt alles wieder her.\n\n'
