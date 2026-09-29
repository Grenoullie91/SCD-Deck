#!/usr/bin/env bash
#
#  DAILY DECK  ·  backup.sh
#
#  Erstellt eine Sicherung der Daily-Deck-Konfiguration UND protokolliert
#  den Zustand der geschützten Fremdsysteme (Command Deck, SSH, Cinnamon,
#  MPD/ncmpcpp, Wallpaper) - ohne diese zu verändern.
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$PROJECT_DIR")"
# Schwestern im Monorepo, sonst der Legacy-Ordner - immer nur gelesen.
COMMAND_DECK_DIR="$REPO_DIR/command-deck"
[ -d "$COMMAND_DECK_DIR" ] || COMMAND_DECK_DIR="$HOME/TerminalCommandWidget"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_DIR="$CONFIG_DIR/daily-deck"
BACKUP_ROOT="$STATE_DIR/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_ROOT/$STAMP"

GRN=$'\033[1;32m'; CYN=$'\033[1;36m'; YEL=$'\033[1;33m'; OFF=$'\033[0m'
ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }

printf '\n%s◈ DAILY DECK  ·  Backup%s  →  %s\n\n' "$CYN" "$OFF" "$DEST"
mkdir -p "$DEST"
chmod 700 "$DEST"

# --- eigene Dateien -------------------------------------------------------
for f in commands.json state.json; do
    if [ -f "$STATE_DIR/$f" ]; then
        cp -a "$STATE_DIR/$f" "$DEST/$f" && ok "gesichert: $f"
    else
        info "nicht vorhanden: $f"
    fi
done
for f in app/daily_deck.py assets/theme.css assets/daily-deck.svg config/commands.json; do
    [ -f "$PROJECT_DIR/$f" ] && cp -a "$PROJECT_DIR/$f" "$DEST/$(basename "$f").src" && ok "gesichert: $f (Quellstand)"
done
[ -f "$CONFIG_DIR/autostart/daily-deck.desktop" ] \
    && cp -a "$CONFIG_DIR/autostart/daily-deck.desktop" "$DEST/autostart-daily-deck.desktop" \
    && ok "gesichert: Autostart-Eintrag"
[ -f "$HOME/.local/share/applications/daily-deck.desktop" ] \
    && cp -a "$HOME/.local/share/applications/daily-deck.desktop" "$DEST/menu-daily-deck.desktop" \
    && ok "gesichert: Menüeintrag"

# --- geschützte Fremdsysteme nur erfassen (nicht kopieren) ----------------
{
    echo "# Daily Deck Bestandsaufnahme $STAMP"
    echo
    echo "## Command Deck (nur Status, nichts kopiert)"
    for p in "$COMMAND_DECK_DIR" \
             "$CONFIG_DIR/terminal-clipboard" \
             "$CONFIG_DIR/autostart/command-deck.desktop" \
             "$HOME/.local/share/applications/command-deck.desktop" \
             "$HOME/.local/share/icons/hicolor/scalable/apps/command-deck.svg"; do
        echo "  $p : $([ -e "$p" ] && echo vorhanden || echo fehlt)"
    done
    echo
    echo "## SSH (nur Pfad, Inhalt nicht gespeichert)"
    echo "  ~/.ssh/config : $([ -f "$HOME/.ssh/config" ] && echo vorhanden || echo fehlt)"
    echo "  ~/.ssh/config Rechte : $(stat -c '%a' "$HOME/.ssh/config" 2>/dev/null || echo '-')"
    echo
    echo "## MPD / ncmpcpp"
    echo "  mpd     : $(command -v mpd || echo nicht installiert)"
    echo "  ncmpcpp : $(command -v ncmpcpp || echo nicht installiert)"
    echo "  ~/.config/mpd : $([ -d "$HOME/.config/mpd" ] && echo vorhanden || echo fehlt)"
    echo
    echo "## Cinnamon / Desktop (nur gsettings-Werte, unverändert)"
    echo "  terminal  : $(gsettings get org.cinnamon.desktop.default-applications.terminal exec 2>/dev/null || echo '-')"
    echo "  wallpaper : $(gsettings get org.cinnamon.desktop.background picture-uri 2>/dev/null || echo '-')"
    echo "  theme     : $(gsettings get org.cinnamon.desktop.interface gtk-theme 2>/dev/null || echo '-')"
} > "$DEST/manifest.txt"
chmod 600 "$DEST/manifest.txt"
ok "Bestandsaufnahme: manifest.txt"

# --- Fremde Systeme inhaltlich sichern, wenn ausdrücklich gewünscht -------
if [ "${1:-}" = "--full" ]; then
    warn "--full: sensible Dateien werden mitgesichert (enthält ggf. ~/.ssh/config)"
    mkdir -p "$DEST/external"
    chmod 700 "$DEST/external"
    [ -d "$COMMAND_DECK_DIR" ] \
        && cp -a "$COMMAND_DECK_DIR" "$DEST/external/command-deck" \
        && ok "gesichert: Command Deck ($COMMAND_DECK_DIR)"
    [ -d "$CONFIG_DIR/terminal-clipboard" ] \
        && cp -a "$CONFIG_DIR/terminal-clipboard" "$DEST/external/terminal-clipboard" \
        && ok "gesichert: ~/.config/terminal-clipboard"
    [ -f "$HOME/.ssh/config" ] \
        && cp -a "$HOME/.ssh/config" "$DEST/external/ssh-config" \
        && ok "gesichert: ~/.ssh/config"
    [ -f "$CONFIG_DIR/autostart/command-deck.desktop" ] \
        && cp -a "$CONFIG_DIR/autostart/command-deck.desktop" "$DEST/external/command-deck.desktop" \
        && ok "gesichert: Command-Deck-Autostart"
    [ -d "$HOME/.config/mpd" ] \
        && cp -a "$HOME/.config/mpd" "$DEST/external/mpd" \
        && ok "gesichert: ~/.config/mpd"
    chmod -R go-rwx "$DEST/external"
fi

printf '\n%s✔ Backup fertig: %s%s\n' "$GRN" "$DEST" "$OFF"
printf '  Wiederherstellen:  %s/restore.sh %s\n\n' "$PROJECT_DIR" "$STAMP"
