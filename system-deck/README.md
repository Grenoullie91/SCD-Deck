# ◈ SYSTEM DECK

**Wartungs-, Diagnose- & System-Control-Deck für Linux Mint**

Das dritte Geschwister im *Purple Cyber Desktop Control System*:

| Deck | Zweck |
|---|---|
| **Command Deck** | Entwicklerbefehle, Git, Build, Docker, Projekte |
| **Daily Deck** | Alltag: Programme, Verzeichnisse, SSH, Medien |
| **System Deck** | Wartung, Diagnose, Hardware, Netzwerk, Sicherheit |

### Ort im Repository

Dieses Deck liegt in `SCD-Deck/system-deck/`. Alle Pfade in dieser Datei sind
**relativ zum Repository-Root** gemeint (Ausnahme: `~/.config/...`, das ist der
Laufzeit-Zustand auf deinem Rechner). Das Deck ist **ortsunabhängig** — es läuft
aus jedem Verzeichnis, weil alle Skripte ihren eigenen Ort über `BASH_SOURCE`
bzw. `__file__` bestimmen.

```bash
git clone https://github.com/Grenoullie91/SCD-Deck.git
cd SCD-Deck/system-deck
./install.sh
```

Alle drei nutzen dieselbe Technik (Python 3 / GTK3), dieselbe Farbpalette,
denselben Eckenradius, dieselben Abstände, dieselbe Cairo-Glasfläche und
dieselbe Typografie (`Hack` / DejaVu Sans Mono). Das System Deck hat eine
**eigene Kopie** des Themes — die Originaldateien der beiden anderen Decks
werden nie geschrieben.

```
COMMAND DECK   = Developer Control
DAILY DECK     = Everyday Control
SYSTEM DECK    = System Control
```

---

## Inhalt

1. [Schnellstart](#1-schnellstart)
2. [Installation](#2-installation)
3. [Start / Stopp](#3-start--stopp)
4. [Autostart](#4-autostart)
5. [Position](#5-position)
6. [Bedienung](#6-bedienung)
7. [Oberfläche](#7-oberfläche)
8. [Aktionstypen: READ / COPY / TERM / ADMIN](#8-aktionstypen-read--copy--term--admin)
9. [Quick System Check](#9-quick-system-check)
10. [Kategorien und Befehle](#10-kategorien-und-befehle)
11. [Konfiguration (`commands.json`)](#11-konfiguration-commandsjson)
12. [Eigene Befehle hinzufügen](#12-eigene-befehle-hinzufügen)
13. [Sicherheitsmechanismen](#13-sicherheitsmechanismen)
14. [Verwendete Systemwerkzeuge](#14-verwendete-systemwerkzeuge)
15. [Nicht verfügbare Funktionen](#15-nicht-verfügbare-funktionen)
16. [Performance](#16-performance)
17. [Backup / Restore / Deinstallation](#17-backup--restore--deinstallation)
18. [Prüfwerkzeuge](#18-prüfwerkzeuge)
19. [Verzeichnisstruktur](#19-verzeichnisstruktur)
20. [Grenzen des Decks](#20-grenzen-des-decks)

---

## 1. Schnellstart

```bash
cd system-deck
./install.sh
python3 app/system_deck.py
```

Das Deck erscheint **unten rechts auf dem primären Bildschirm** und startet
künftig beim Anmelden mit.

---

## 2. Installation

```bash
./install.sh                  # Installation mit Autostart
./install.sh --no-autostart   # ohne Autostart
./install.sh --force          # vorhandene Befehlsliste überschreiben
./install.sh --help
```

Der Installer

1. legt **vor jeder Änderung** ein Backup unter
   `~/.config/system-deck/backups/<Zeitstempel>/` an und protokolliert
   darin den Bestand von Command Deck, Daily Deck, Cairo-Dock und Panel,
2. prüft `python3` und GTK3 (beides Systempakete — es wird **nichts
   installiert**),
3. listet alle erkannten Systemwerkzeuge und alle fehlenden auf,
4. legt `~/.config/system-deck/commands.json` an (bestehende Dateien
   werden **nicht** überschrieben),
5. berechnet die Position **unten rechts** aus der Arbeitsfläche des
   primären Monitors und schreibt sie nach `state.json`,
6. installiert Symbol, Menüeintrag und (optional) Autostart,
7. führt den Selbsttest und den Bestandsschutz-Nachweis aus.

Voraussetzungen: `python3`, `python3-gi`, `gir1.2-gtk-3.0` — auf Linux Mint
vorinstalliert.

---

## 3. Start / Stopp

| Aktion | Befehl |
|---|---|
| Starten | `python3 system-deck/app/system_deck.py` |
| Laufende Instanz anheben | `python3 system-deck/app/system_deck.py --raise` |
| Beenden | `Strg+Q` oder Rechtsklick auf die Kopfzeile → *Beenden* |
| Ausblenden | `Strg+H` oder Rechtsklick → *Deck verbergen* |
| Version | `python3 app/system_deck.py --version` |

Das Deck ist ein `skip-taskbar` DOCK-Fenster (`_NET_WM_TYPE_DOCK`),
erscheint also nicht in der Fensterleiste und nicht im Fensterwechsel.

---

## 4. Autostart

```bash
~/.config/autostart/system-deck.desktop      # aktiv (Delay 3 s)
```

Gleiches Konzept wie Command Deck (Delay 1 s) und Daily Deck (Delay 2 s).
Ausschalten: `rm ~/.config/autostart/system-deck.desktop` oder
`./install.sh --no-autostart`.

---

## 5. Position

* **Standard:** unten rechts in der Arbeitsfläche des **primären Monitors**
  (Abstand 14 px vom Rand).
* Die Position wird **einmal** berechnet und danach nur noch gespeichert.
  Beim nächsten Start wird sie **nicht** neu berechnet.
* **Verschieben:** Kopfzeile ziehen → wird sofort gespeichert.
* **Größe:** Griffe unten rechts ziehen → wird gespeichert.
* **Zurücksetzen:** Rechtsklick → *Position: unten rechts zurücksetzen*.

```json
// ~/.config/system-deck/state.json
{ "always_on_top": true, "opacity": 0.95,
  "x": 2146, "y": 1349, "width": 400, "height": 660, "positioned": true }
```

Berechnung:

```python
x = area.x + area.width  - width  - 14
y = area.y + area.height - height - 14
```

`area` ist die Arbeitsfläche des primären Monitors
(`Gdk.Monitor.get_workarea()`), berücksichtigt also Panel- und
Dock-Reserven. Ein Sicherheitsnetz (`_clamp_to_screen`) verhindert, dass
das Fenster teilweise aus dem Bildschirm geschoben wird.

---

## 6. Bedienung

| Eingabe | Wirkung |
|---|---|
| `READ` / `TERM` / `ADMIN` (Knopf) | Hauptaktion des Eintrags |
| `COPY` (zweiter Knopf) | kopiert den Befehl — führt nichts aus |
| Klick auf den **Namen** | dieselbe Aktion wie der Hauptknopf |
| Klick auf eine Kategorie | zeigt nur diese Kategorie |
| Klick auf ein Feld im Quick Check | führt den passenden Lesebefehl aus |
| Suchfeld `❯` | filtert Kategorien und Befehle, `Esc` leert |
| `⧉ ALL` in der Ausgabe | kopiert die gesamte Ausgabe |
| `✕` in der Ausgabe | schließt das Ausgabefenster |
| `↻` neben dem Check | rechnet den Quick System Check neu |
| Rechtsklick auf die Kopfzeile | Menü |
| `Strg+F` | Suchfeld |
| `F5` | Konfiguration neu laden / Systemcheck neu |
| `Strg+T` | Immer im Vordergrund umschalten |
| `Strg+H` / `Strg+Q` | ausblenden / beenden |

---

## 7. Oberfläche

```
┌──────────────────────────────────────┐
│ ◈ SYSTEM DECK                   ● PIN │
├──────────────────────────────────────┤
│ QUICK SYSTEM CHECK              ↻ 14:15│
│  OK SYSTEM  OK CPU      OK RAM        │
│  OK STORAGE OK NETWORK  ERR DIENSTE   │
│  INFO UPDATES OK TEMP     OK FIREWALL  │
├──────────────────────────────────────┤
│ ❯ [ Search categories & commands... ]✕│
│ SYSTEM TOOLS                  17 Kat.  │
│ [SYSTEM][HARDWARE][STORAGE][PERFORM.] │
│ [PROCESS][NETWORK][PORTS][UPDATES]    │
│ [CLEANUP][LOGS][SERVICES][SECURITY]   │
│ [FIREWALL][SENSORS][GPU][AUDIO]       │
│ [DIAGNOSTICS]                        │
├──────────────────────────────────────┤
│ ◈ SYSTEM                            10│
│ 🖥 Systemübersicht         [COPY][READ]│
│ 🎩 Linux Mint Version      [COPY][READ]│
│ …                                    │
├──────────────────────────────────────┤
│ AUSGABE · READ · SYSTEMÜBERSICHT ⧉ ✕ │
│ (Ausgabefenster, klappt sanft auf)   │
├──────────────────────────────────────┤
│ 121 Befehle · 17 Kategorien   ▲ PIN ▪ │
└──────────────────────────────────────┘
```

---

## 8. Aktionstypen: READ / COPY / TERM / ADMIN

Jeder Knopf trägt seinen Typ als **Text**. Es gibt keinen versteckten
Ausführungspfad.

| Typ | Was passiert | Was **nicht** passiert |
|---|---|---|
| **READ** | Lesebefehl wird **ohne Shell** über eine Argumentliste ausgeführt (Zeitlimit 10 s, Ausgabe gekürzt auf 500 Zeilen) und im Ausgabefenster gezeigt | kein `sudo`, kein Schreiben, kein Netzwerkzugriff |
| **COPY** | Der Text landet in der Zwischenablage | **nichts wird ausgeführt** — konstruktionsbedingt |
| **TERM** | Ein **sichtbares** Terminal öffnet sich mit dem Befehl | das Deck führt nichts selbst aus |
| **ADMIN** | Bestätigungsdialog zeigt den Befehl **wörtlich** → danach öffnet ein sichtbares Terminal | das Deck führt nie `sudo` aus, es gibt kein Passwortfeld |

Zusätzliche Knöpfe je Zeile:

* **COPY** steht immer **getrennt** vom Ausführungsknopf — ein Klick auf
  „kopieren" kann niemals etwas ausführen.
* `NICHT VERFÜGBAR` (grau): das benötigte Werkzeug fehlt. Der Tooltip
  nennt es.
* `GESPERRT` (rot): destruktiver oder verändernder Befehl — nicht ausführbar.

### Suchdialog

Einträge mit `prompt` fragen zuerst nach einem Suchbegriff
(Prozessname, Dienstname, Port, Journal-Begriff, Sensor).
Erlaubt sind nur Buchstaben, Ziffern und `. _ - @ : +`, höchstens 64
Zeichen. Der Begriff ersetzt genau ein Argument — keine Shell, kein
Verkettungszeichen.

---

## 9. Quick System Check

Neun Werte, **dynamisch ermittelt**, mit Cache (30 s), berechnet in einem
Thread, aktualisiert alle 20 s **nur solange das Fenster sichtbar ist**.

| Feld | Quelle | Logik |
|---|---|---|
| `SYSTEM` | `/etc/os-release` | immer OK, solange lesbar |
| `CPU` | Load Average / Kerne | ERR ≥ 95 %, WARN ≥ 75 % |
| `RAM` | `/proc/meminfo` | ERR < 5 % frei, WARN < 15 % |
| `STORAGE` | `statvfs` aller echten Mounts | ERR ≥ 92 %, WARN ≥ 82 % |
| `NETWORK` | `/sys/class/net`, `/proc/net/route` | ERR kein Interface up, WARN kein Gateway |
| `DIENSTE` | `systemctl --failed` | ERR wenn ≥ 1 Dienst fehlgeschlagen |
| `UPDATES` | `/var/lib/update-notifier/updates-available` | INFO mit Anzahl, OK wenn 0 |
| `TEMPERATUR` | `sensors -u` | ERR ≥ 88 °C, WARN ≥ 78 °C |
| `FIREWALL` | `ufw status`, sonst `systemctl is-active ufw` | OK aktiv, WARN inaktiv |

Farben (bewusst außerhalb der Purple-Familie, damit Zustände sofort
erkennbar bleiben):

```
OK    #4ADE80     WARN  #FBBF24     ERR  #F87171     INFO  #C084FC
```

Der Punkt oben rechts zeigt den **schlechtesten** der neun Werte.
Klick auf ein Feld führt den passenden Lesebefehl aus.

---

## 10. Kategorien und Befehle

17 Kategorien, 121 Einträge:

| # | Kategorie | Inhalt |
|---|---|---|
| 1 | 🖥 **SYSTEM** | Systeminfo, Mint-Version, Kernel, Desktop-Umgebung, Sitzungstyp, Uptime, Hostname, Benutzer, Architektur, letzte Starts |
| 2 | 🔧 **HARDWARE** | CPU, CPU-Kerne, Laufzeit, Mainboard, BIOS, USB, USB-Busse, PCI, DMI (Terminal) |
| 3 | 💾 **STORAGE** | Dateisysteme, Inodes, Blockgeräte, UUIDs, Mount-Tree, SMART (Terminal) |
| 4 | 📈 **PERFORMANCE** | CPU-Auslastung, RAM & Swap, Systemlast, Temperaturen, vmstat |
| 5 | ⚙ **PROCESSES** | Top CPU, Top RAM, alle Prozesse, Prozessbaum, Prozess-Suche, eigene Prozesse |
| 6 | 🌐 **NETWORK** | Interfaces, IP-Adressen, Routing/Gateway, WLAN, NetworkManager, DNS, resolv.conf, Verbindungstest |
| 7 | 🔌 **PORTS** | offene Ports, Listening TCP, aktive Verbindungen, Statistik, Port-Suche |
| 8 | 📦 **UPDATES** | Update-Status, verfügbare Updates, Sicherheitsupdates, Paketquellen, `apt update`/`apt upgrade` (nur COPY) |
| 9 | 🧹 **CLEANUP** | APT-Cache, Journal-Speicher, /tmp, /var/log, Papierkorb, Thumbnails, große Dateien, `apt clean` / `journalctl --vacuum` (nur COPY) |
| 10 | 📜 **LOGS** | Fehler, Warnungen, Kernel-Log, Boot-Log, Boot-Liste, Log-Suche, Fehlersuche, Live-Mitschnitt |
| 11 | 🧰 **SERVICES** | laufende Dienste, fehlgeschlagene, Zeitplaner, Systemzustand, Dienst-Status, Dienst-Log, starten/stoppen/neustarten (ADMIN), geschützte Dienste |
| 12 | 🛡 **SECURITY** | Benutzer, Gruppen, sudo-Rechte, Anmeldeverlauf, fehlgeschlagene Logins, SUID-Dateien, offene Ports, Sicherheitsmeldungen |
| 13 | 🔥 **FIREWALL** | Status, Regeln, Dienststatus, Firewall-Log, Hinweis „keine Regeländerung" |
| 14 | 🌡 **SENSORS** | alle Sensoren, Rohwerte, Temperaturfilter, Lüfter |
| 15 | 🎮 **GPU** | Modell, Treiber, DRM, `nvidia-smi` (Terminal), OpenGL (Terminal) |
| 16 | 🔊 **AUDIO** | Audio-Server, Ausgabe, Eingabe, Standard-Ausgabe, ALSA-Karten, Lautstärkemixer |
| 17 | 🩺 **DIAGNOSTICS** | System-Check, Fehlerdiagnose, Paketintegrität, Boot-Dauer, kritischer Pfad, USB-Fehler, Firmware, Bericht kopieren |

Verteilung: **93 READ · 18 TERM · 7 COPY · 3 ADMIN**

---

## 11. Konfiguration (`commands.json`)

```
~/.config/system-deck/commands.json     <- bearbeiten (die einzige Datei!)
system-deck/config/commands.json       <- Vorlage (nur für Neuinstallation)
```

Die Datei ist ausführlich kommentiert (Schlüssel `_readme`).

### Aufbau einer Kategorie

```json
"HARDWARE": {
  "icon": "🔧",
  "order": 20,
  "entries": [ … ]
}
```

`order` sortiert die Kategorien, `enabled: false` blendet sie aus.

### Aufbau eines Eintrags

| Feld | Bedeutung |
|---|---|
| `name` | Anzeigename (mit Emoji) |
| `description` | Tooltip-Zeile |
| `type` | `READ` \| `COPY` \| `TERM` \| `ADMIN` |
| `cmd` | Befehl als Text — Anzeige, Kopie, Terminal |
| `argv` | Argumentliste, **nur bei `READ`** |
| `admin_command` | nur bei `ADMIN` (sonst `cmd`) |
| `unit` | Dienstname → Schutz vor kritischen Diensten |
| `sudo` | `true` erlaubt `sudo` **nur bei `TERM`** und nur für Lesebefehle |
| `prompt` / `prompt_token` | Suchabfrage vor der Ausführung |
| `example` | Beispieltext im Suchdialog |
| `filter` / `filter_re` | filtert die Ausgabe in Python (kein `\|` in der Shell) |
| `package` | Paketname, falls das Werkzeug optional fehlt |
| `requires` | Werkzeuge, die installiert sein müssen |
| `timeout_s` | eigenes Zeitlimit für diesen Befehl (Standard 10 s) |
| `allow_rc` | Statuscodes, die **kein** Fehler sind, z. B. `[0, 1]` bei `du`/`find`, wenn geschützte Ordner nicht lesbar sind |
| `check` | verknüpft den Eintrag mit einem Feld des Quick System Check |
| `enabled` | `false` = ausblenden |

Platzhalter: `{user}` (aktueller Benutzer), `{home}` (Home-Verzeichnis),
`<query>` (Suchbegriff).

Nach dem Speichern: **F5** drücken oder Rechtsklick → *Befehle bearbeiten*
öffnet die Datei direkt im Texteditor.

---

## 12. Eigene Befehle hinzufügen

```json
{
  "name": "🗂 Log-Größe",
  "description": "Belegung von /var/log",
  "type": "READ",
  "cmd": "du -sh /var/log",
  "argv": ["du", "-sh", "/var/log"],
  "requires": ["du"]
}
```

Dann **F5** drücken. Die Zeile erscheint sofort.

Wichtig:

* Bei `READ` wird **immer `argv`** benutzt, nie `cmd`. Pipes sind dort
  nicht erlaubt — für Filtern gibt es `filter` / `filter_re`.
* `argv[0]` darf keine Shell sein (`sh`, `bash`, …) — solche Einträge
  werden abgewiesen.
* Verändernde Befehle (`rm`, `apt install`, `ufw allow`, `journalctl
  --vacuum`, …) sind **immer** gesperrt. Für alle drei Decks gilt dieselbe
  Blockliste.

---

## 13. Sicherheitsmechanismen

1. **Nur lesen als Standard.** 93 der 121 Einträge sind `READ` und laufen
   ohne Root, ohne Shell und ohne Schreibzugriff.
2. **Keine Shell beim Ausführen.** `READ` benutzt `subprocess` mit einer
   Argumentliste, `stdin` geschlossen, eigene Prozessgruppe, fest
   Zeitlimit (10 s), gekürzte Ausgabe (500 Zeilen / 90 KB).
3. **Zwei Sperrlisten.**
   * `BLOCKED` — destruktive Befehle (rm -rf, mkfs, dd, shred, fdisk,
     parted, `> /dev/sd*`, shutdown/reboot am Zeilenanfang, chmod 777,
     userdel, kill -9, `curl | sh`, `nc -e`, `history -c` …).
   * `MUTATION` — verändernde Aktionen (Paketinstall, Firewall-Regel,
     `iptables -F`, Journal-Aufräumen, `systemctl enable/disable/mask`,
     git push/reset/clean, docker prune …). **Diese Liste lässt sich durch
     kein Flag aufheben.**
4. **Kritische Systemdienste geschützt.** `ssh`, `sshd`, `NetworkManager`,
   `display-manager`, `cups`, `cron`, `dbus`, `polkit`, `accounts-daemon`,
   `upower`, `PackageKit`, `bluetooth`, `avahi-daemon`, `systemd-*` …
   können vom Deck **nie** per ADMIN verändert werden. Der Dienstname
   wird aus dem Befehl extrahiert und geprüft.
5. **sudo-Ausnahme nur für Sichtbares.** `sudo: true` ist ausschließlich
   bei `TYPE=TERM` erlaubt und hebt ausschließlich die sudo-Regel auf.
   Der Befehl landet im Terminal und wird dort bestätigt — das Deck
   führt ihn nie aus.
6. **ADMIN mit Bestätigung.** Der Dialog zeigt den Befehl wörtlich, nennt
   den erkannten Terminal und den Hinweis *„Es wird kein Passwort
   gespeichert und kein Passwortfeld angezeigt."*
7. **Veränderungen nur als COPY.** `apt update`, `apt upgrade`,
   `apt clean` und `journalctl --vacuum-time` stehen als **COPY**
   im Deck — zum bewussten Einfügen im Terminal, nie als Klickaktion.
8. **Keine Firewall-Regeländerungen.** UFW liefert nur Status und
   Regelliste (read-only). Das Deck sagt das ausdrücklich.
9. **Keine Updates ohne Klick.** Es gibt keinen automatischen
   Update-Lauf, keinen Hintergrund-Dienst, keinen Watcher.
10. **Keine Passwörter, keine Credentials.** Kein Passwortfeld, kein
    Keyring, kein SSH-Key-Zugriff, keine ~/.ssh-Berührung.
11. **Suchbegriffe werden geprüft.** Höchstens 64 Zeichen aus
    `[A-Za-z0-9_.@:+-]`; der Begriff ersetzt genau ein Argument.
12. **Kein Zugriff auf fremde Bestände.** Command Deck, Daily Deck,
    Wallpaper, Cinnamon-Schemata, Cairo-Dock und Panel werden
    **ausschließlich gelesen** — das Programm enthält keinen einzigen
    Schreibzugriff darauf.
13. **Lokale Arbeit.** Keine Telemetrie, keine Analytics, keine
    Cloud-Anbindung, kein Netzwerkzugriff aus dem Programm heraus.
14. **Begrenztes internes Log.** `~/.config/system-deck/system-deck.log`,
    256 KB, eine Rotation, nur Ereignisnamen (`READ Systemübersicht`),
    **keine** Befehlsausgaben, Passwörter, Keys oder Tokens.

Prüfen:

```bash
python3 app/system_deck.py --selftest     # 30 Sicherheits- und Konfigurationsprüfungen
```

---

## 14. Verwendete Systemwerkzeuge

Das Deck nutzt ausschließlich Werkzeuge, die zu Linux Mint gehören:

```
systemctl  journalctl  df  lsblk  free  ps  ss  ip  sensors  lspci
lsusb  nmcli  ufw  apt  apt-get  lscpu  lsb_release  hostnamectl
uptime  who  last  lastb  uname  arch  printenv  findmnt  du  find
grep  cat  getent  top  vmstat  pstree  dpkg  systemd-analyze  fwupdmgr
pactl  aplay  smartctl  hdparm  dmidecode  lshw  glxinfo  ping  gnome-terminal
```

Fehlt eines, meldet das Deck es als `NICHT VERFÜGBAR` und arbeitet ohne weiteres
darauf. Es wurde **kein einziges Paket installiert**, und das Deck installiert
auch keines.

---

## 15. Nicht verfügbare Funktionen

Das Deck prüft jedes Werkzeug beim Laden und meldet fehlende Werkzeuge
als **NICHT VERFÜGBAR** (Knopf und Zeile ausgegraut, Tooltip nennt das
Werkzeug). Nichts wird nachinstalliert.

| Funktion | Fehlendes Werkzeug | Optionales Paket | Zweck |
|---|---|---|---|
| 📊 NVIDIA (Modell, VRAM, Auslastung, Temperatur) | `nvidia-smi` | `nvidia-utils` | NVIDIA-Treiber-Verwaltung |
| 🔧 Volume im Terminal | `pavucontrol` | `pavucontrol` | PulseAudio-Mixer |
| 🩺 System-Check (Terminal) | `gnome-system-report` | `gnome-system-report` | Mint-Systembericht |
| — (nur Werkzeugliste) | `nvme`, `iostat`, `powertop` | `nvme-cli`, `sysstat`, `powertop` | NVMe-Details, I/O-Statistik, Energieanalyse |

Diese Funktionen sind optional. **Kein Befehl installiert das System Deck
jemals selbst.**

---

## 16. Performance

* **Keine Dauerabfrage im Hintergrund.** Der Quick System Check rechnet
  nur, solange das Fenster sichtbar ist — beim Einblenden, alle 20 s und
  auf `F5`. Beim Ausblenden wird der Timer entfernt.
* **Ergebnisse werden gecacht** (30 s), damit `systemctl --failed` und
  `sensors` nicht mehrfach pro Minute laufen.
* **Jeder Befehl hat ein Zeitlimit** (10 s) und wird bei Überschreitung
  beendet — keine Endlosschleifen, kein Hängenbleiben.
* **Alle Befehle laufen in einem Thread-Pool** (2 Arbeiter). Die
  Oberfläche bleibt jederzeit bedienbar.
* **Ausgaben werden gekürzt** auf 500 Zeilen bzw. 90 KB.

Gemessen (Leerlauf, Fenster sichtbar):

```
CPU über 8 s:  0,00 s Rechenzeit  →  0 % einer CPU
RAM:           ~80 MB (GTK3 + Python, normal)
```

---

## 17. Backup / Restore / Deinstallation

### Backup

`./install.sh` legt **vor jeder Änderung** automatisch ein Backup an:

```
~/.config/system-deck/backups/<Zeitstempel>/
├── commands.json          (nur falls vorhanden)
├── state.json             (nur falls vorhanden)
├── system_deck.py.src     Projektquellen
├── theme.css.src
├── system-deck.svg.src
├── commands.json.src
├── icon-before.svg        (nur falls ein Symbol existierte)
├── menu-before.desktop
├── autostart-before.desktop
└── manifest.txt           Bestand von Command Deck / Daily Deck / Dock
```

Bestehende Konfigurationen werden dabei **nie überschrieben**, nur
weggesichert.

### Restore

```bash
./restore.sh --list              # alle Backups anzeigen
./restore.sh                     # neuestes Backup
./restore.sh 20260929-140922     # bestimmtes Backup
./restore.sh --keep-project      # nur Konfiguration, Code bleibt
```

Vor dem Zurückschreiben wird der aktuelle Stand noch einmal als
`pre-restore-*` gesichert. Fremde Systeme bleiben immer unangetastet.

### Deinstallation

```bash
./uninstall.sh              # Menü, Icon, Autostart, Projektordner
./uninstall.sh --purge      # zusätzlich ~/.config/system-deck inkl. Backups
./uninstall.sh --keep-config
```

Entfernt **ausschließlich** System-Deck-Dateien. Keine Programme werden
deinstalliert, keine Systemkonfiguration geändert.

---

## 18. Prüfwerkzeuge

```bash
python3 app/system_deck.py --selftest     # Konfiguration + Sicherheitsregeln
python3 app/system_deck.py --audit        # alle Befehle mit Verfügbarkeit
python3 tools/uitest.py                   # UI-Rauchtest (nur lesend)
python3 tools/uitest.py --shot /tmp/sd.png  # + offscreen-Rendering
python3 tools/functest.py                 # Funktionsabnahme: alle READ-Befehle
python3 tools/functest.py --only LOGS     # nur eine Kategorie
python3 tools/theme-check.py              # Designfamilie gegen die Geschwister
```

`theme-check.py` vergleicht den **gemeinsamen Grundblock** aller drei
`theme.css` (252 CSS-Zeilen) sowie die 13 Farben — und ändert an den
Dateien der Geschwister **nichts**.

---

## 19. Verzeichnisstruktur

```
system-deck/
├── app/system_deck.py          Programm
├── assets/
│   ├── theme.css               Kopie des Geschwister-Themes + Ergänzungen
│   └── system-deck.svg         Symbol
├── config/commands.json        Vorlage der Befehlsliste
├── tools/
│   ├── uitest.py               UI-Rauchtest
│   └── theme-check.py          Design-Abgleich
├── install.sh
├── restore.sh
├── uninstall.sh
└── README.md

~/.config/system-deck/
├── commands.json               <- deine Konfiguration
├── state.json                  <- Position, Größe, Transparenz
├── instance.lock               einfacher Instanzschutz
├── system-deck.log             internes, begrenztes Log
└── backups/<Zeitstempel>/      automatische Sicherungen
```

---

## 20. Grenzen des Decks

* **Ändert nichts an** Command Deck, Daily Deck, Wallpaper, Cairo-Dock
  und Panel. Diese Dateien werden nur gelesen.
* **Installiert nie ein Paket.** Fehlende Werkzeuge werden gemeldet.
* **Führt nie `sudo` aus.** Root-Befehle öffnen ein sichtbares Terminal.
* **Kennt keine Telemetrie.** Alles läuft lokal.
* Das Deck ist ein **Fenster**, kein Systemdienst. Es läuft nur, solange
  die Sitzung läuft, und beendet sich mit dem Abmelden.

---

*◈ SYSTEM DECK — Teil des Purple Cyber Desktop Control Systems*
*Command Deck = Developer Control · Daily Deck = Everyday Control · System Deck = System Control*
