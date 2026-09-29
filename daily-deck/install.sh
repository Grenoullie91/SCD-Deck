#!/usr/bin/env bash
#
#  DAILY DECK  ·  install.sh
#
#  Richtet das Daily Deck ein. Legt VOR jeder Aenderung ein Backup an.
#  Aendert NICHTS an:
#     · dem bestehenden Command Deck (~/TerminalCommandWidget,
#       ~/.config/terminal-clipboard, ~/.config/autostart/command-deck.desktop)
#     · dem Wallpaper / der Desktop-Konfiguration
#     · der SSH-Konfiguration (~/.ssh)
#     · der MPD-/ncmpcpp-Konfiguration
#
#  Aufruf:
#     ./install.sh                  Installation mit Autostart
#     ./install.sh --no-autostart   ohne Autostart
#     ./install.sh --force          vorhandene Befehlsliste ueberschreiben
#     ./install.sh --help
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$PROJECT_DIR")"
# Schwestern im Monorepo, sonst der Legacy-Ordner - immer nur gelesen.
COMMAND_DECK_DIR="$REPO_DIR/command-deck"
[ -d "$COMMAND_DECK_DIR" ] || COMMAND_DECK_DIR="$HOME/TerminalCommandWidget"
APP="$PROJECT_DIR/app/daily_deck.py"
THEME="$PROJECT_DIR/assets/theme.css"
ICON="$PROJECT_DIR/assets/daily-deck.svg"
SEED="$PROJECT_DIR/config/commands.json"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_DIR="$CONFIG_DIR/daily-deck"
COMMANDS_FILE="$STATE_DIR/commands.json"
STATE_FILE="$STATE_DIR/state.json"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/daily-deck.desktop"
MENU_DIR="$HOME/.local/share/applications"
MENU_FILE="$MENU_DIR/daily-deck.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_FILE="$ICON_DIR/daily-deck.svg"
BACKUP_ROOT="$STATE_DIR/backups"

USE_AUTOSTART=1
FORCE_COMMANDS=0

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; YEL=$'\033[1;33m'
CYN=$'\033[1;36m'; DIM=$'\033[2m';    BLD=$'\033[1m'; OFF=$'\033[0m'

ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
die()  { printf '\n  %sFEHLER:%s %s\n\n' "$RED" "$OFF" "$1" >&2; exit 1; }
h2()   { printf '\n%s%s%s\n' "$BLD" "$1" "$OFF"; }

usage() { sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --no-autostart) USE_AUTOSTART=0 ;;
        --force)        FORCE_COMMANDS=1 ;;
        --help|-h)      usage ;;
        *)              die "unbekannte Option: $1  (--help anzeigen)" ;;
    esac
    shift
done

printf '\n%s╭──────────────────────────────────────────────╮%s\n' "$CYN" "$OFF"
printf '%s│  ◈ DAILY DECK  ·  Installation              │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"

# ------------------------------------------------------------------ Backup
h2 "1  Backup"
mkdir -p "$BACKUP_ROOT"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR"
ok "Backup-Ziel: $BACKUP_DIR"

if [ -f "$COMMANDS_FILE" ]; then
    cp -a "$COMMANDS_FILE" "$BACKUP_DIR/commands.json"
    ok "gesichert: $COMMANDS_FILE"
else
    info "keine bestehende Befehlsliste (wird neu angelegt)"
fi
if [ -f "$STATE_FILE" ]; then
    cp -a "$STATE_FILE" "$BACKUP_DIR/state.json"
    ok "gesichert: $STATE_FILE"
fi
# Bestaehigungsprotokoll: Existenz des anderen Decks festhalten
{
    echo "# Daily Deck Backup $STAMP"
    echo "command_deck_widget_exists=$([ -d "$COMMAND_DECK_DIR" ] && echo yes || echo no)"
    echo "command_deck_autostart_exists=$([ -f "$AUTOSTART_DIR/command-deck.desktop" ] && echo yes || echo no)"
    echo "command_deck_state_exists=$([ -d "$CONFIG_DIR/terminal-clipboard" ] && echo yes || echo no)"
} > "$BACKUP_DIR/manifest.txt"
chmod 600 "$BACKUP_DIR/manifest.txt"
ok "Bestand des Command Decks protokolliert"

# ---------------------------------------------------------- Abhaengigkeiten
h2 "2  Voraussetzungen"
for f in "$APP" "$THEME" "$ICON" "$SEED"; do
    [ -f "$f" ] || die "Projektdatei fehlt: $f"
done
command -v python3 >/dev/null || die "python3 fehlt"
python3 - <<'PY' || die "GTK3 (python3-gi) fehlt - Paket 'python3-gi gir1.2-gtk-3.0'"
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: F401
PY
ok "python3 + GTK3 (Systempakete, keine Installation nötig)"

if command -v gnome-terminal >/dev/null; then
    ok "Standard-Terminal: gnome-terminal"
elif [ -n "$(ls /usr/bin/*term* 2>/dev/null | head -1)" ]; then
    warn "gnome-terminal fehlt - es wird zur Laufzeit ein anderes Terminal gesucht"
else
    warn "kein GTK-Terminal gefunden - TERMINAL-Aktionen könnten ausfallen"
fi

# ------------------------------------------------------------------ Dateien
h2 "3  Konfiguration"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
if [ -f "$COMMANDS_FILE" ] && [ "$FORCE_COMMANDS" -eq 0 ]; then
    info "Befehlsliste bleibt erhalten: $COMMANDS_FILE"
    info "neu erzeugen mit:  ./install.sh --force"
else
    cp "$SEED" "$COMMANDS_FILE"
    ok "Befehlsliste angelegt: $COMMANDS_FILE"
fi
[ -f "$STATE_FILE" ] || printf '%s\n' '{ "always_on_top": true, "opacity": 0.94, "x": 40, "y": 60, "width": 380, "height": 560 }' > "$STATE_FILE"
ok "Fensterstatus: $STATE_FILE"
chmod 600 "$STATE_DIR"/*.json 2>/dev/null || true

# ------------------------------------------------------------------ Icon
h2 "4  Symbol"
mkdir -p "$ICON_DIR"
if [ -f "$ICON_FILE" ]; then
    cp -a "$ICON_FILE" "$BACKUP_DIR/icon-before.svg" 2>/dev/null || true
    info "Symbol vorhanden, wird ersetzt (Backup: $BACKUP_DIR/icon-before.svg)"
fi
cp "$ICON" "$ICON_FILE"
ok "Symbol installiert: $ICON_FILE"
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

# -------------------------------------------------------------- Menüeintrag
h2 "5  Menüeintrag"
mkdir -p "$MENU_DIR"
if [ -f "$MENU_FILE" ]; then
    cp -a "$MENU_FILE" "$BACKUP_DIR/menu-before.desktop"
    info "bestehender Menüeintrag wird ersetzt (Backup liegt vor)"
fi
cat > "$MENU_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Daily Deck
GenericName=Alltags-Cockpit
Comment=Alltags-Aktionen: Programme, Verzeichnisse, SSH-Server, Systeminfos
Exec=/usr/bin/python3 $APP
Icon=daily-deck
Terminal=false
Categories=System;Utility;GTK;
Keywords=daily;terminal;ssh;nemo;ncmpcpp;cmatrix;
StartupNotify=false
X-GNOME-UsesNotifications=false
EOF
chmod +x "$MENU_FILE"
ok "Menüeintrag: $MENU_FILE"

# ------------------------------------------------------------------ Autostart
h2 "6  Autostart"
mkdir -p "$AUTOSTART_DIR"
if [ "$USE_AUTOSTART" -eq 1 ]; then
    if [ -f "$AUTOSTART_FILE" ]; then
        cp -a "$AUTOSTART_FILE" "$BACKUP_DIR/autostart-before.desktop"
        info "Daily-Deck-Autostart existierte bereits, wird ersetzt"
    fi
    cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Daily Deck
Comment=Daily Deck beim Anmelden starten
Exec=/usr/bin/python3 $APP
Icon=daily-deck
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=2
X-Mint-Autostart-Phase=Applications
StartupNotify=false
EOF
    chmod +x "$AUTOSTART_FILE"
    ok "Autostart aktiv: $AUTOSTART_FILE"
else
    rm -f "$AUTOSTART_FILE"
    ok "Autostart nicht eingerichtet (--no-autostart)"
fi

# ------------------------------------------------------------------ Test
h2 "7  Prüfung"
if python3 "$APP" --selftest; then
    ok "Selbsttest bestanden"
else
    warn "Selbsttest meldet Probleme (siehe Ausgabe oben)"
fi

echo
python3 "$APP" --print-config 2>/dev/null | sed 's/^/    /' || true

# ------------------------------------------------------------- Schutz-Check
h2 "8  Bestandsschutz"
if [ -f "$AUTOSTART_DIR/command-deck.desktop" ]; then
    ok "Command Deck Autostart unberührt: $AUTOSTART_DIR/command-deck.desktop"
else
    warn "Command Deck Autostart nicht gefunden (unverändert gelassen)"
fi
if [ -d "$CONFIG_DIR/terminal-clipboard" ]; then
    ok "Command Deck State unberührt: $CONFIG_DIR/terminal-clipboard"
fi
if [ -d "$COMMAND_DECK_DIR" ]; then
    ok "Command Deck Projektordner unberührt: $COMMAND_DECK_DIR"
fi
ok "Wallpaper wurde nicht angefasst (kein Zugriff auf Hintergrundbilder)"

printf '\n%s✔ Installation abgeschlossen.%s\n' "$GRN" "$OFF"
printf '  Starten:        python3 %s\n' "$APP"
printf '  Beenden:        Strg+Q  oder  ✕ (schließt nur das Fenster)\n'
printf '  Befehle ändern:  %s   → danach F5\n' "$COMMANDS_FILE"
printf '  Entfernen:      %s/uninstall.sh\n\n' "$PROJECT_DIR"
