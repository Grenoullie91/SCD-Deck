#!/usr/bin/env bash
#
#  DAILY DECK  ·  restore.sh
#
#  Stellt eine Sicherung aus ~/.config/daily-deck/backups/<Zeitstempel> wieder her.
#  Überschreibt NUR Daily-Deck-Dateien. Fremde Systeme werden nur gelesen
#  und nur mit --external zurückgeschrieben.
#
#  Aufruf:
#     ./restore.sh                 menü/letztes Backup verwenden
#     ./restore.sh --list          alle Backups auflisten
#     ./restore.sh <STAMP>         bestimmtes Backup verwenden
#     ./restore.sh <STAMP> --external   auch Command Deck / SSH / MPD zurückschreiben
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_DIR="$CONFIG_DIR/daily-deck"
BACKUP_ROOT="$STATE_DIR/backups"
AUTOSTART_DIR="$CONFIG_DIR/autostart"

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; CYN=$'\033[1;36m'; YEL=$'\033[1;33m'; OFF=$'\033[0m'
ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
die()  { printf '\n  FEHLER: %s\n\n' "$1" >&2; exit 1; }

EXTERNAL=0
if [ "${1:-}" = "--list" ]; then
    printf '\n%s◈ Vorhandene Backups%s  (%s)\n' "$CYN" "$OFF" "$BACKUP_ROOT"
    [ -d "$BACKUP_ROOT" ] || die "kein Backup-Verzeichnis - ./backup.sh aufrufen"
    for d in "$BACKUP_ROOT"/*/; do
        [ -d "$d" ] || continue
        printf '  %s  %s\n' "$(basename "$d")" "$(ls -1 "$d" 2>/dev/null | tr '\n' ' ')"
    done
    printf '\n'
    exit 0
fi

for a in "$@"; do
    [ "$a" = "--external" ] && EXTERNAL=1
done

STAMP="${1:-}"
if [ -z "$STAMP" ] || [ "$STAMP" = "--external" ]; then
    STAMP="$(ls -1 "$BACKUP_ROOT" 2>/dev/null | sort | tail -n 1 || true)"
    [ -n "$STAMP" ] || die "kein Backup gefunden - erst ./backup.sh ausführen"
    info "kein Zeitstempel angegeben, verwende neuestes: $STAMP"
fi

SRC="$BACKUP_ROOT/$STAMP"
[ -d "$SRC" ] || die "Backup nicht gefunden: $SRC"

printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$CYN" "$OFF"
printf '%s│  ◈ DAILY DECK  ·  Restore                   │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"
info "Quelle: $SRC"

# Vor dem Überschreiben erneut eine Sicherung des aktuellen Stands anlegen
if [ -d "$BACKUP_ROOT" ] && [ "$STAMP" != "$(date +%Y%m%d-%H%M%S)" ]; then
    mkdir -p "$BACKUP_ROOT/pre-restore-$(date +%Y%m%d-%H%M%S)"
    cp -a "$STATE_DIR"/commands.json "$STATE_DIR"/state.json \
          "$BACKUP_ROOT/pre-restore-$(date +%Y%m%d-%H%M%S)"/ 2>/dev/null || true
    ok "aktueller Stand zusätzlich gesichert (pre-restore-*)"
fi

printf '\n  Daily Deck\n'
[ -f "$SRC/commands.json" ] && { cp -a "$SRC/commands.json" "$STATE_DIR/commands.json"; ok "commands.json"; } || info "keine commands.json im Backup"
[ -f "$SRC/state.json" ]    && { cp -a "$SRC/state.json"    "$STATE_DIR/state.json";    ok "state.json"; }    || info "keine state.json im Backup"
[ -f "$SRC/autostart-daily-deck.desktop" ] && { mkdir -p "$AUTOSTART_DIR"; cp -a "$SRC/autostart-daily-deck.desktop" "$AUTOSTART_DIR/daily-deck.desktop"; ok "Autostart-Eintrag"; } || true
[ -f "$SRC/menu-daily-deck.desktop" ] && { mkdir -p "$HOME/.local/share/applications"; cp -a "$SRC/menu-daily-deck.desktop" "$HOME/.local/share/applications/daily-deck.desktop"; ok "Menüeintrag"; } || true

# Quellstand-Dateien zurück in das Projektverzeichnis
[ -f "$SRC/daily_deck.py.src" ]     && { cp -a "$SRC/daily_deck.py.src"     "$PROJECT_DIR/app/daily_deck.py";     ok "app/daily_deck.py"; }     || true
[ -f "$SRC/theme.css.src" ]         && { cp -a "$SRC/theme.css.src"         "$PROJECT_DIR/assets/theme.css";      ok "assets/theme.css"; }      || true
[ -f "$SRC/daily-deck.svg.src" ]    && { cp -a "$SRC/daily-deck.svg.src"    "$PROJECT_DIR/assets/daily-deck.svg"; ok "assets/daily-deck.svg"; } || true
[ -f "$SRC/commands.json.src" ]     && { cp -a "$SRC/commands.json.src"     "$PROJECT_DIR/config/commands.json";  ok "config/commands.json"; }  || true
[ -f "$SRC/daily-deck.svg" ]        && { mkdir -p "$HOME/.local/share/icons/hicolor/scalable/apps"; cp -a "$SRC/daily-deck.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/daily-deck.svg"; ok "Symbol"; } || true

if [ "$EXTERNAL" -eq 1 ]; then
    printf '\n  %sExterne Systeme%s\n' "$YEL" "$OFF"
    EXT="$SRC/external"
    if [ -d "$EXT" ]; then
        if [ -d "$EXT/command-deck" ]; then
            cp -a "$EXT/command-deck" "$HOME/TerminalCommandWidget" && ok "Command Deck"
        elif [ -d "$EXT/TerminalCommandWidget" ]; then   # Backup vor dem Umzug
            cp -a "$EXT/TerminalCommandWidget" "$HOME/" && ok "~/TerminalCommandWidget"
        fi
        [ -d "$EXT/terminal-clipboard" ]   && { cp -a "$EXT/terminal-clipboard"   "$CONFIG_DIR/"; ok "~/.config/terminal-clipboard"; } || true
        [ -f "$EXT/command-deck.desktop" ] && { cp -a "$EXT/command-deck.desktop" "$AUTOSTART_DIR/command-deck.desktop"; ok "Command-Deck-Autostart"; } || true
        [ -f "$EXT/ssh-config" ]          && { cp -a "$EXT/ssh-config"          "$HOME/.ssh/config"; chmod 600 "$HOME/.ssh/config"; ok "~/.ssh/config"; } || true
        [ -d "$EXT/mpd" ]                 && { cp -a "$EXT/mpd"                 "$HOME/.config/"; ok "~/.config/mpd"; } || true
    else
        warn "kein external/-Ordner in diesem Backup - unverändert gelassen"
    fi
else
    printf '\n'
    info "externe Systeme unverändert (nur mit --external zurückschreiben)"
fi

printf '\n%s✔ Restore abgeschlossen.%s  Neustart: python3 %s/app/daily_deck.py\n\n' \
       "$GRN" "$OFF" "$PROJECT_DIR"
