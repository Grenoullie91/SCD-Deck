#!/usr/bin/env bash
#
#  SYSTEM DECK  ·  install.sh
#
#  Richtet das System Deck ein. Legt VOR jeder Änderung ein Backup an.
#  Ändert NICHTS an:
#     · dem bestehenden Command Deck (~/TerminalCommandWidget,
#       ~/.config/terminal-clipboard, ~/.config/autostart/command-deck.desktop)
#     · dem bestehenden Daily Deck (~/DailyDeck, ~/.config/daily-deck)
#     · dem Wallpaper / der Cinnamon-Konfiguration
#     · Cairo-Dock und dem Panel
#     · ~/.ssh und allen anderen Benutzerdaten
#
#  Aufruf:
#     ./install.sh                  Installation mit Autostart
#     ./install.sh --no-autostart   ohne Autostart
#     ./install.sh --force          vorhandene Befehlsliste überschreiben
#     ./install.sh --help
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$PROJECT_DIR")"
# Schwestern im Monorepo, sonst der Legacy-Ordner - immer nur gelesen.
COMMAND_DECK_DIR="$REPO_DIR/command-deck"
DAILY_DECK_DIR="$REPO_DIR/daily-deck"
[ -d "$COMMAND_DECK_DIR" ] || COMMAND_DECK_DIR="$HOME/TerminalCommandWidget"
[ -d "$DAILY_DECK_DIR" ]    || DAILY_DECK_DIR="$HOME/DailyDeck"
APP="$PROJECT_DIR/app/system_deck.py"
THEME="$PROJECT_DIR/assets/theme.css"
ICON="$PROJECT_DIR/assets/system-deck.svg"
SEED="$PROJECT_DIR/config/commands.json"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_DIR="$CONFIG_DIR/system-deck"
COMMANDS_FILE="$STATE_DIR/commands.json"
STATE_FILE="$STATE_DIR/state.json"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/system-deck.desktop"
MENU_DIR="$HOME/.local/share/applications"
MENU_FILE="$MENU_DIR/system-deck.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_FILE="$ICON_DIR/system-deck.svg"
BACKUP_ROOT="$STATE_DIR/backups"

USE_AUTOSTART=1
FORCE_COMMANDS=0

DECK_W=400
DECK_H=660
EDGE_MARGIN=14

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
printf '%s│  ◈ SYSTEM DECK  ·  Installation             │%s\n' "$CYN" "$OFF"
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
for f in "$APP" "$THEME" "$ICON" "$SEED"; do
    [ -f "$f" ] && cp -a "$f" "$BACKUP_DIR/$(basename "$f").src"
done
ok "Projektdateien gesichert (*.src)"

# Bestaetigungsprotokoll: Bestand der beiden anderen Decks festhalten
{
    echo "# System Deck Backup $STAMP"
    echo "command_deck_project_exists=$([ -d "$COMMAND_DECK_DIR" ] && echo yes || echo no)"
    echo "command_deck_state_exists=$([ -d "$CONFIG_DIR/terminal-clipboard" ] && echo yes || echo no)"
    echo "command_deck_autostart_exists=$([ -f "$AUTOSTART_DIR/command-deck.desktop" ] && echo yes || echo no)"
    echo "daily_deck_project_exists=$([ -d "$DAILY_DECK_DIR" ] && echo yes || echo no)"
    echo "daily_deck_state_exists=$([ -d "$CONFIG_DIR/daily-deck" ] && echo yes || echo no)"
    echo "daily_deck_autostart_exists=$([ -f "$AUTOSTART_DIR/daily-deck.desktop" ] && echo yes || echo no)"
    echo "cairo_dock_exists=$([ -x /usr/bin/cairo-dock ] && echo yes || echo no)"
    echo "wallpaper=unveraendert"
    echo "panel=unveraendert"
} > "$BACKUP_DIR/manifest.txt"
chmod 600 "$BACKUP_DIR/manifest.txt"
ok "Bestand von Command Deck / Daily Deck protokolliert"

# ---------------------------------------------------------- Abhaengigkeiten
h2 "2  Voraussetzungen"
for f in "$APP" "$THEME" "$ICON" "$SEED"; do
    [ -f "$f" ] || die "Projektdatei fehlt: $f"
done
command -v python3 >/dev/null || die "python3 fehlt"
python3 - <<'PY' || die "GTK3 (python3-gi) fehlt - Systempaket python3-gi + gir1.2-gtk-3.0"
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: F401
PY
ok "python3 + GTK3 (Systempakete, keine Installation nötig)"

if command -v gnome-terminal >/dev/null; then
    ok "Standard-Terminal: gnome-terminal"
else
    warn "gnome-terminal fehlt - es wird zur Laufzeit ein anderes Terminal gesucht"
fi

h2 "3  Erkannte Systemwerkzeuge (es wird Nichts installiert)"
MISSING=""
for t in systemctl journalctl df lsblk free ps ss ip sensors lspci lsusb \
         nmcli ufw apt lscpu pactl; do
    if command -v "$t" >/dev/null; then
        printf '    %s✔%s %-12s %s\n' "$GRN" "$OFF" "$t" "$(command -v "$t")"
    else
        printf '    %s·%s %-12s %s\n' "$YEL" "$OFF" "$t" "fehlt - Funktion wird als 'nicht verfügbar' gemeldet"
        MISSING="$MISSING $t"
    fi
done
[ -n "$MISSING" ] && info "optional fehlend:$MISSING"

# ------------------------------------------------------------------ Dateien
h2 "4  Konfiguration"
mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
if [ -f "$COMMANDS_FILE" ] && [ "$FORCE_COMMANDS" -eq 0 ]; then
    info "Befehlsliste bleibt erhalten: $COMMANDS_FILE"
    info "neu erzeugen mit:  ./install.sh --force"
else
    cp "$SEED" "$COMMANDS_FILE"
    ok "Befehlsliste angelegt: $COMMANDS_FILE"
fi

if [ ! -f "$STATE_FILE" ]; then
    POS="$(python3 - "$DECK_W" "$DECK_H" "$EDGE_MARGIN" <<'PY' || true
import sys
w, h, m = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
try:
    import gi
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk
    d = Gdk.Display.get_default()
    mon = d.get_primary_monitor() or d.get_monitor(0)
    a = mon.get_workarea()
    print("%d %d" % (max(a.x, a.x + a.width - w - m),
                     max(a.y, a.y + a.height - h - m)))
except Exception:
    print("-1 -1")
PY
)"
    set -- $POS
    PX="${1:--1}"; PY="${2:--1}"
    if [ "$PX" -ge 0 ] && [ "$PY" -ge 0 ]; then
        printf '{\n  "always_on_top": true,\n  "opacity": 0.95,\n  "x": %s,\n  "y": %s,\n  "width": %s,\n  "height": %s,\n  "positioned": true\n}\n' \
            "$PX" "$PY" "$DECK_W" "$DECK_H" > "$STATE_FILE"
        ok "Position unten rechts gesetzt: ${PX},${PY} (Arbeitsfläche des primären Monitors)"
    else
        printf '{\n  "always_on_top": true,\n  "opacity": 0.95,\n  "x": -1,\n  "y": -1,\n  "width": %s,\n  "height": %s,\n  "positioned": false\n}\n' \
            "$DECK_W" "$DECK_H" > "$STATE_FILE"
        warn "Bildschirmgeometrie nicht abfragbar - Position wird beim ersten Start berechnet"
    fi
else
    info "Fensterstatus bleibt erhalten: $STATE_FILE (Position bleibt gespeichert)"
fi
chmod 600 "$STATE_DIR"/*.json 2>/dev/null || true

# -------------------------------------------------------------------- Icon
h2 "5  Symbol"
mkdir -p "$ICON_DIR"
if [ -f "$ICON_FILE" ]; then
    cp -a "$ICON_FILE" "$BACKUP_DIR/icon-before.svg" 2>/dev/null || true
    info "Symbol vorhanden, wird ersetzt (Backup: $BACKUP_DIR/icon-before.svg)"
fi
cp "$ICON" "$ICON_FILE"
ok "Symbol installiert: $ICON_FILE"
command -v gtk-update-icon-cache >/dev/null \
    && gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true

# -------------------------------------------------------------- Menüeintrag
h2 "6  Menüeintrag"
mkdir -p "$MENU_DIR"
if [ -f "$MENU_FILE" ]; then
    cp -a "$MENU_FILE" "$BACKUP_DIR/menu-before.desktop"
    info "bestehender Menüeintrag wird ersetzt (Backup liegt vor)"
fi
cat > "$MENU_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=System Deck
GenericName=System-Cockpit
Comment=Wartung, Diagnose, Hardware, Netzwerk, Sicherheit
Exec=/usr/bin/python3 $APP
Icon=system-deck
Terminal=false
Categories=System;Utility;GTK;
Keywords:system;diagnose;hardware;network;maintenance;
StartupNotify=false
X-GNOME-UsesNotifications=false
EOF
chmod +x "$MENU_FILE"
ok "Menüeintrag: $MENU_FILE"

# ----------------------------------------------------------------- Autostart
h2 "7  Autostart"
mkdir -p "$AUTOSTART_DIR"
if [ "$USE_AUTOSTART" -eq 1 ]; then
    if [ -f "$AUTOSTART_FILE" ]; then
        cp -a "$AUTOSTART_FILE" "$BACKUP_DIR/autostart-before.desktop"
        info "System-Deck-Autostart existierte bereits, wird ersetzt"
    fi
    cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=System Deck
Comment=System Deck beim Anmelden starten
Exec=/usr/bin/python3 $APP
Icon=system-deck
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
X-Mint-Autostart-Phase=Applications
StartupNotify=false
EOF
    chmod +x "$AUTOSTART_FILE"
    ok "Autostart aktiv: $AUTOSTART_FILE"
else
    rm -f "$AUTOSTART_FILE"
    ok "Autostart nicht eingerichtet (--no-autostart)"
fi

# -------------------------------------------------------------------- Test
h2 "8  Prüfung"
if python3 "$APP" --selftest; then
    ok "Selbsttest bestanden"
else
    warn "Selbsttest meldet Probleme (siehe Ausgabe oben)"
fi

echo
python3 "$APP" --audit 2>/dev/null | sed -n '/Verteilung/,+3p' | sed 's/^/    /' || true

# ------------------------------------------------------------- Schutz-Check
h2 "9  Bestandsschutz"
for d in "command-deck:$COMMAND_DECK_DIR" \
         "command-deck-state:$CONFIG_DIR/terminal-clipboard" \
         "daily-deck:$DAILY_DECK_DIR" \
         "daily-deck-state:$CONFIG_DIR/daily-deck"; do
    label="${d%%:*}"; path="${d#*:}"
    if [ -e "$path" ]; then
        ok "$label unverändert: $path"
    else
        info "$label nicht vorhanden: $path"
    fi
done
for a in "$AUTOSTART_DIR/command-deck.desktop" "$AUTOSTART_DIR/daily-deck.desktop"; do
    [ -f "$a" ] && ok "Autostart unberührt: $a" || info "kein Autostart: $a"
done
ok "Wallpaper unverändert (kein Zugriff auf Hintergrundbilder)"
ok "Cairo-Dock unverändert (nur gelesen, nichts geschrieben)"
ok "Panel unverändert (kein Zugriff auf Cinnamon-Schemata)"

printf '\n%s✔ Installation abgeschlossen.%s\n' "$GRN" "$OFF"
printf '  Starten:          python3 %s\n' "$APP"
printf '  Beenden:          Strg+Q  oder  Rechtsklick -> Beenden\n'
printf '  Befehle ändern:   %s   → danach F5\n' "$COMMANDS_FILE"
printf '  Position:         Kopfzeile ziehen (wird gespeichert)\n'
printf '  Prüfen:           python3 %s --selftest | --audit\n' "$APP"
printf '  Entfernen:        %s/uninstall.sh\n\n' "$PROJECT_DIR"
