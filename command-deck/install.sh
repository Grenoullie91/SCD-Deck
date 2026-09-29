#!/usr/bin/env bash
#
#  COMMAND DECK  ·  install.sh
#
#  Installiert den Autostart-Eintrag und die Menue-Verknuepfung.
#  Legt VOR jeder Aenderung ein Backup an.
#
#  Aufruf:
#     ./install.sh                  normale Installation (mit Autostart)
#     ./install.sh --no-autostart   ohne Autostart
#     ./install.sh --force          vorhandene Befehlsliste ueberschreiben
#     ./install.sh --help
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$PROJECT_DIR/app/command_deck.py"
THEME="$PROJECT_DIR/assets/theme.css"
ICON="$PROJECT_DIR/assets/command-deck.svg"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_STATE_DIR="$CONFIG_DIR/terminal-clipboard"
COMMANDS_FILE="$APP_STATE_DIR/commands.json"
AUTOSTART_DIR="$CONFIG_DIR/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/command-deck.desktop"
MENU_DIR="$HOME/.local/share/applications"
MENU_FILE="$MENU_DIR/command-deck.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_FILE="$ICON_DIR/command-deck.svg"
BACKUP_ROOT="$APP_STATE_DIR/backups"

USE_AUTOSTART=1
FORCE_COMMANDS=0

RED=$'\033[1;31m'; GRN=$'\033[1;32m'; YEL=$'\033[1;33m'
CYN=$'\033[1;36m'; DIM=$'\033[2m';    BLD=$'\033[1m'; OFF=$'\033[0m'

ok()   { printf '  %s✔%s %s\n' "$GRN" "$OFF" "$1"; }
info() { printf '  %s·%s %s\n' "$CYN" "$OFF" "$1"; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$1"; }
die()  { printf '\n  %sFEHLER:%s %s\n\n' "$RED" "$OFF" "$1" >&2; exit 1; }
head2(){ printf '\n%s%s%s\n' "$BLD" "$1" "$OFF"; }

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

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
printf '%s│  ◈ COMMAND DECK  ·  Installation              │%s\n' "$CYN" "$OFF"
printf '%s╰──────────────────────────────────────────────╯%s\n' "$CYN" "$OFF"

# ------------------------------------------------------------------ Voraussetzungen
head2 "1  Voraussetzungen prüfen"
[ -f "$APP" ]  || die "app/command_deck.py nicht gefunden: $PROJECT_DIR"
[ -f "$THEME" ] || die "assets/theme.css nicht gefunden"

PYTHON="$(command -v python3)" || die "python3 nicht gefunden"
ok "python3: $PYTHON ($("$PYTHON" -V 2>&1))"

if ! "$PYTHON" -c 'import gi; gi.require_version("Gtk","3.0")' 2>/dev/null; then
    die "PyGObject/GTK3 fehlt.  Installation:  sudo apt install python3-gi gir1.2-gtk-3.0"
fi
ok "GTK3 (PyGObject) verfügbar – keine weiteren Pakete nötig"

chmod +x "$APP" 2>/dev/null || true
ok "app/command_deck.py ausführbar"

# ------------------------------------------------------------------------- Backup
head2 "2  Backup anlegen"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$STAMP"
mkdir -p "$BACKUP_DIR"
ok "Backup-Verzeichnis: $BACKUP_DIR"

if [ -f "$COMMANDS_FILE" ]; then
    cp -a "$COMMANDS_FILE" "$BACKUP_DIR/commands.json"
    ok "gesichert: $COMMANDS_FILE"
else
    : > "$BACKUP_DIR/commands.json.absent"
    info "keine bestehende Befehlsliste (wird neu angelegt)"
fi
[ -f "$APP_STATE_DIR/state.json" ] && { cp -a "$APP_STATE_DIR/state.json" \
    "$BACKUP_DIR/state.json"; ok "gesichert: state.json"; } || true
[ -f "$AUTOSTART_FILE" ] && { cp -a "$AUTOSTART_FILE" "$BACKUP_DIR/autostart.desktop"
    ok "gesichert: $AUTOSTART_FILE"; } || true
[ -f "$MENU_FILE" ] && { cp -a "$MENU_FILE" "$BACKUP_DIR/menu.desktop"
    ok "gesichert: $MENU_FILE"; } || true
printf '%s' "$STAMP" > "$APP_STATE_DIR/.last-backup"
ok "Backup-Pfad gemerkt (siehe restore.sh --list)"

# ------------------------------------------------------------------ Konfiguration
head2 "3  Konfiguration"
mkdir -p "$APP_STATE_DIR"
if [ -f "$COMMANDS_FILE" ] && [ "$FORCE_COMMANDS" -eq 0 ]; then
    CNT=$("$PYTHON" - "$COMMANDS_FILE" <<'PY' 2>/dev/null || echo "?"
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    print(sum(len(v.get("commands", v) if isinstance(v, dict) else v)
              for k, v in d.get("categories", {}).items() if not k.startswith("_")))
except Exception:
    print("?")
PY
)
    ok "bestehende Befehlsliste bleibt erhalten ($CNT Befehle)"
    info "ändern: $COMMANDS_FILE"
    info "zurücksetzen: ./install.sh --force"
elif [ "$FORCE_COMMANDS" -eq 1 ] && [ -f "$PROJECT_DIR/config/commands.json" ]; then
    cp "$PROJECT_DIR/config/commands.json" "$COMMANDS_FILE"
    ok "Befehlsliste aus Vorlage neu geschrieben"
else
    cp "$PROJECT_DIR/config/commands.json" "$COMMANDS_FILE"
    ok "Befehlsliste angelegt: $COMMANDS_FILE"
fi
[ -f "$APP_STATE_DIR/seed_favorites.json" ] || \
    cp "$PROJECT_DIR/config/seed_favorites.json" "$APP_STATE_DIR/seed_favorites.json" 2>/dev/null || true

# --------------------------------------------------------------------- Desktop-Entry
head2 "4  Menüeintrag"
mkdir -p "$MENU_DIR" "$ICON_DIR"
[ -f "$ICON" ] && cp "$ICON" "$ICON_FILE" && ok "Symbol installiert: $ICON_FILE"
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

cat > "$MENU_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Command Deck
GenericName=Terminal-Befehle Clipboard
Comment=Häufig genutzte Terminal-Befehle per Klick kopieren (führt nichts aus)
Exec=$PYTHON $APP
Icon=command-deck
Terminal=false
Categories=Development;GTK;
Keywords=terminal;commands;clipboard;git;docker;cheatsheet;
StartupNotify=false
X-GNOME-UsesNotifications=false
EOF
chmod +x "$MENU_FILE"
ok "Menüeintrag: $MENU_FILE"

# -------------------------------------------------------------------- Autostart
head2 "5  Autostart"
if [ "$USE_AUTOSTART" -eq 1 ]; then
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Command Deck
Comment=Terminal Command Deck beim Anmelden starten
Exec=$PYTHON $APP
Icon=command-deck
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=1
X-Mint-Autostart-Phase=Applications
StartupNotify=false
EOF
    chmod +x "$AUTOSTART_FILE"
    ok "Autostart: $AUTOSTART_FILE"
    info "erscheint in: Systemverwaltung → Startprogramme"
else
    info "Autostart übersprungen (--no-autostart)"
fi

# ------------------------------------------------------------------- Selbsttest
head2 "6  Selbsttest"
if "$PYTHON" "$APP" --selftest > "$APP_STATE_DIR/selftest.log" 2>&1; then
    ok "Selbsttest bestanden  →  $APP_STATE_DIR/selftest.log"
else
    warn "Selbsttest meldet Probleme: $APP_STATE_DIR/selftest.log"
    tail -n 20 "$APP_STATE_DIR/selftest.log"
fi
if "$PYTHON" "$APP" --audit > /dev/null 2>&1; then
    ok "Sicherheits-Audit: 0 verbotene Aufrufe (kopiert, führt nie aus)"
else
    die "Sicherheits-Audit fehlgeschlagen – Installation abgebrochen"
fi

# --------------------------------------------------------------------- Aufräumen
find "$PROJECT_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

head2 "Fertig"
cat <<EOF
  ${GRN}Installation abgeschlossen.${OFF}

  Starten:      $PYTHON $APP
                oder über das Anwendungsmenü: ${BLD}Command Deck${OFF}
  Befehle:      $COMMANDS_FILE
                Rechtsklick im Widget → ${BLD}Befehle bearbeiten …${OFF}
                danach ${BLD}F5${OFF} zum Neuladen
  Zustand:      $APP_STATE_DIR/state.json
                (Position, Größe, Favoriten, Always-on-Top)
  Backup:       $BACKUP_DIR
                zurückrollen mit: ${BLD}./restore.sh${OFF}
  Entfernen:    ${BLD}./uninstall.sh${OFF}

  ${DIM}Strg+F Suche · F5 neu laden · Strg+T immer im Vordergrund
  Strg+H verbergen · Esc Suche leeren · Stern = Favorit${OFF}

  ${YEL}Das Widget kopiert ausschließlich Text in die Zwischenablage.
  Es führt niemals Befehle aus.${OFF}
EOF
printf '\n'
