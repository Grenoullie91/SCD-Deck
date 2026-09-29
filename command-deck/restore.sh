#!/usr/bin/env bash
#
#  COMMAND DECK  ·  restore.sh
#
#  Setzt den Zustand vor der letzten Installation wieder her.
#  Betroffen sind nur Dateien, die install.sh angelegt hat.
#
#  Aufruf:
#     ./restore.sh                 Backup der letzten Installation verwenden
#     ./restore.sh --list          alle vorhandenen Backups auflisten
#     ./restore.sh <stempel>       ein bestimmtes Backup verwenden
#                                 (z. B. ./restore.sh 20260929-101530)
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
BACKUP_ROOT="$APP_STATE_DIR/backups"
LAST_POINTER="$APP_STATE_DIR/.last-backup"

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; YEL=$'\033[1;33m'
CYN=$'\033[1;36m'; DIM=$'\033[2m';    BLD=$'\033[1m'; OFF=$'\033[0m'

ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
die()  { printf '\n  FEHLER: %s\n\n' "$1" >&2; exit 1; }
head2(){ printf '\n%s%s%s\n' "$BLD" "$1" "$OFF"; }

list_backups() {
    if [ ! -d "$BACKUP_ROOT" ] || [ -z "$(ls -A "$BACKUP_ROOT" 2>/dev/null)" ]; then
        info "keine Backups vorhanden"
        return 0
    fi
    printf '\n  %sVerfügbare Backups:%s\n' "$BLD" "$OFF"
    for d in $(ls -1 "$BACKUP_ROOT" | sort -r); do
        what=""
        [ -f "$BACKUP_ROOT/$d/commands.json" ] && what="$what Befehlsliste"
        [ -f "$BACKUP_ROOT/$d/state.json" ]   && what="$what Zustand"
        [ -f "$BACKUP_ROOT/$d/autostart.desktop" ] && what="$what Autostart"
        [ -f "$BACKUP_ROOT/$d/menu.desktop" ]  && what="$what Menüeintrag"
        printf '    %s%-20s%s enthaelt:%s\n' "$BLD" "$d" "$OFF" "${what:- (leer)}"
    done
    printf '\n  Wiederherstellen:  ./restore.sh <stempel>\n\n'
}

if [ "${1:-}" = "--list" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    list_backups
    exit 0
fi

printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$CYN" "$OFF"
printf '%s│  ◈ COMMAND DECK  ·  Wiederherstellung         │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"

STAMP="${1:-}"
if [ -z "$STAMP" ] && [ -f "$LAST_POINTER" ]; then
    STAMP="$(cat "$LAST_POINTER")"
fi
# Der Zeiger kann einen vollen Pfad enthalten (aeltere Installationen) -
# restore.sh erwartet aber nur den Ordnernamen.
STAMP="${STAMP##*/}"
STAMP="${STAMP%/}"
[ -n "${STAMP:-}" ] || { list_backups; die "kein Backup angegeben und kein letztes Backup gefunden"; }
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
[ -d "$BACKUP_DIR" ] || { list_backups; die "Backup nicht gefunden: $BACKUP_DIR"; }

head2 "Wiederherstellen aus $BACKUP_DIR"

# Vor dem Ueberschreiben erneut sichern, damit nichts verloren geht
SAFETY="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)-vor-restore"
mkdir -p "$SAFETY"
[ -f "$COMMANDS_FILE" ] && cp -a "$COMMANDS_FILE" "$SAFETY/commands.json" || true
[ -f "$STATE_FILE" ]   && cp -a "$STATE_FILE"   "$SAFETY/state.json"   || true
ok "Sicherheitskopie des aktuellen Zustands: $SAFETY"

restore_one() {
    local src="$1" dst="$2" label="$3"
    if [ -f "$src" ]; then
        mkdir -p "$(dirname "$dst")"
        cp -a "$src" "$dst"
        ok "$label wiederhergestellt: $dst"
    elif [ -f "$src.absent" ]; then
        rm -f "$dst"
        ok "$label entfernt (war vorher nicht vorhanden)"
    else
        info "$label: im Backup nicht enthalten - unverändert"
    fi
}

# Laufendes Widget stoppen, damit es die Datei nicht beim Beenden überschreibt
if [ -f "$APP_STATE_DIR/instance.lock" ]; then
    PID="$(cat "$APP_STATE_DIR/instance.lock" 2>/dev/null || true)"
    if [ -n "${PID:-}" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null && ok "laufendes Widget (PID $PID) beendet"
        sleep 1
    fi
fi

restore_one "$BACKUP_DIR/commands.json"       "$COMMANDS_FILE"     "Befehlsliste"
restore_one "$BACKUP_DIR/state.json"         "$STATE_FILE"        "Zustand"
restore_one "$BACKUP_DIR/autostart.desktop"  "$AUTOSTART_FILE"    "Autostart"
restore_one "$BACKUP_DIR/menu.desktop"       "$MENU_FILE"         "Menüeintrag"

head2 "Fertig"
cat <<EOF
  ${GRN}Wiederherstellung abgeschlossen.${OFF}

  ${DIM}Widget neu starten:  $APP
  Liste der Backups:       ./restore.sh --list${OFF}
EOF
printf '\n'
