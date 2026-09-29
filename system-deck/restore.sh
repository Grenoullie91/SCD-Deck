#!/usr/bin/env bash
#
#  SYSTEM DECK  ·  restore.sh
#
#  Stellt eine Sicherung aus ~/.config/system-deck/backups/<Zeitstempel>
#  wieder her. Überschreibt NUR System-Deck-Dateien.
#
#  Aufruf:
#     ./restore.sh                 neuestes Backup verwenden
#     ./restore.sh --list          alle Backups auflisten
#     ./restore.sh <STAMP>         bestimmtes Backup verwenden
#     ./restore.sh --keep-project  nur die Konfiguration zurückschreiben,
#                                  der Projektordner bleibt wie er ist
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
BACKUP_ROOT="$STATE_DIR/backups"
AUTOSTART_DIR="$CONFIG_DIR/autostart"

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; CYN=$'\033[1;36m'; YEL=$'\033[1;33m'; OFF=$'\033[0m'
ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
die()  { printf '\n  FEHLER: %s\n\n' "$1" >&2; exit 1; }

KEEP_PROJECT=0

if [ "${1:-}" = "--list" ]; then
    printf '\n%s◈ Vorhandene Backups%s  (%s)\n' "$CYN" "$OFF" "$BACKUP_ROOT"
    [ -d "$BACKUP_ROOT" ] || die "kein Backup-Verzeichnis - ./install.sh aufrufen"
    for d in "$BACKUP_ROOT"/*/; do
        [ -d "$d" ] || continue
        printf '  %s  %s\n' "$(basename "$d")" "$(ls -1 "$d" 2>/dev/null | tr '\n' ' ')"
    done
    printf '\n'
    exit 0
fi

for a in "$@"; do
    [ "$a" = "--keep-project" ] && KEEP_PROJECT=1
done

STAMP=""
for a in "$@"; do
    case "$a" in --*) ;; *) STAMP="$a" ;; esac
done

if [ -z "$STAMP" ]; then
    STAMP="$(ls -1 "$BACKUP_ROOT" 2>/dev/null | sort | tail -n 1 || true)"
    [ -n "$STAMP" ] || die "kein Backup gefunden - erst ./install.sh ausführen"
    info "kein Zeitstempel angegeben, verwende neuestes: $STAMP"
fi

SRC="$BACKUP_ROOT/$STAMP"
[ -d "$SRC" ] || die "Backup nicht gefunden: $SRC"

printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$CYN" "$OFF"
printf '%s│  ◈ SYSTEM DECK  ·  Restore                  │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"
info "Quelle: $SRC"

# Vor dem Überschreiben den aktuellen Stand zusätzlich sichern
PRE="$BACKUP_ROOT/pre-restore-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$PRE"
cp -a "$STATE_DIR"/commands.json "$STATE_DIR"/state.json "$PRE"/ 2>/dev/null || true
ok "aktueller Stand zusätzlich gesichert (pre-restore-*)"

printf '\n  System Deck\n'
mkdir -p "$STATE_DIR"
if [ -f "$SRC/commands.json" ]; then
    cp -a "$SRC/commands.json" "$STATE_DIR/commands.json"; ok "commands.json"
else
    info "keine commands.json im Backup"
fi
if [ -f "$SRC/state.json" ]; then
    cp -a "$SRC/state.json" "$STATE_DIR/state.json";    ok "state.json (Position)"
else
    info "keine state.json im Backup"
fi

if [ "$KEEP_PROJECT" -eq 0 ]; then
    [ -f "$SRC/system_deck.py.src" ]  && { cp -a "$SRC/system_deck.py.src"  "$PROJECT_DIR/app/system_deck.py";  ok "app/system_deck.py"; }  || true
    [ -f "$SRC/theme.css.src" ]      && { cp -a "$SRC/theme.css.src"      "$PROJECT_DIR/assets/theme.css";     ok "assets/theme.css"; }     || true
    [ -f "$SRC/system-deck.svg.src" ] && { cp -a "$SRC/system-deck.svg.src" "$PROJECT_DIR/assets/system-deck.svg"; ok "assets/system-deck.svg"; } || true
    [ -f "$SRC/commands.json.src" ]  && { cp -a "$SRC/commands.json.src"  "$PROJECT_DIR/config/commands.json"; ok "config/commands.json"; } || true
    if [ -f "$SRC/icon-before.svg" ]; then
        mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"
        cp -a "$SRC/icon-before.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/system-deck.svg"
        ok "Symbol (vorheriger Stand)"
    fi
    if [ -f "$SRC/menu-before.desktop" ]; then
        mkdir -p "$HOME/.local/share/applications"
        cp -a "$SRC/menu-before.desktop" "$HOME/.local/share/applications/system-deck.desktop"
        ok "Menüeintrag (vorheriger Stand)"
    fi
    if [ -f "$SRC/autostart-before.desktop" ]; then
        mkdir -p "$AUTOSTART_DIR"
        cp -a "$SRC/autostart-before.desktop" "$AUTOSTART_DIR/system-deck.desktop"
        ok "Autostart (vorheriger Stand)"
    fi
else
    info "Projektordner unverändert (--keep-project)"
fi

if [ -f "$SRC/manifest.txt" ]; then
    printf '\n  %sBestand zum Zeitpunkt des Backups%s\n' "$YEL" "$OFF"
    sed 's/^/    /' "$SRC/manifest.txt"
fi

printf '\n  %sFremde Systeme%s\n' "$YEL" "$OFF"
info "Command Deck, Daily Deck, Cairo-Dock, Panel und Wallpaper bleiben unverändert"
[ -d "$COMMAND_DECK_DIR" ] && ok "Command Deck vorhanden: $COMMAND_DECK_DIR" || true
[ -d "$CONFIG_DIR/terminal-clipboard" ] && ok "~/.config/terminal-clipboard vorhanden" || true
[ -d "$DAILY_DECK_DIR" ] && ok "Daily Deck vorhanden: $DAILY_DECK_DIR" || true
[ -d "$CONFIG_DIR/daily-deck" ] && ok "~/.config/daily-deck vorhanden" || true

printf '\n%s✔ Restore abgeschlossen.%s  Neustart: python3 %s/app/system_deck.py\n\n' \
       "$GRN" "$OFF" "$PROJECT_DIR"
