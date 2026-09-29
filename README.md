<div align="center">

# ◈ SCD-DECK

**Purple Cyber Desktop Control System**

Drei Desktop-Decks für Linux Mint — ein Widget, drei Blickwinkel auf deinen Rechner.

[![License: MIT](https://img.shields.io/badge/License-MIT-a78bfa.svg)](LICENSE)
![Python 3](https://img.shields.io/badge/Python-3-4B8BBE.svg)
![GTK 3](https://img.shields.io/badge/GTK-3-7C5299.svg)
![Plattform](https://img.shields.io/badge/Plattform-Linux%20Mint%20%2F%20Cinnamon-C084FC.svg)
![Lizenz](https://img.shields.io/badge/Codepassend_README-4ADE80.svg)

</div>

---

## Was ist das?

Drei schwebende Panels am Bildschirmrand. Kein App-Grid, keine Dock-Symbole,
kein Startmenü-Eintrag, den man suchen muss — die drei Decks liegen einfach da
und tun das, wofür man sie gebaut hat:

```
┌─ COMMAND DECK ─────┐  ┌─ DAILY DECK ───────┐  ┌─ SYSTEM DECK ─────┐
│  Developer Control │  │  Everyday Control  │  │  System Control   │
│  git, build,       │  │  Programme, Pfade, │  │  Wartung, Diagnose│
│  docker, deploy    │  │  SSH, Medien       │  │  Hardware, Netz   │
└────────────────────┘  └────────────────────┘  └────────────────────┘
      kopiert              öffnet/verbindet         liest/diagnostiziert
    niemals ausführen
```

| Deck | Ordner | Zweck | Was ein Klick tut |
|---|---|---|---|
| ◈ **Command Deck** | [`command-deck/`](command-deck) | Entwicklerbefehle, Git, Build, Docker, Projekte | **kopiert** den Befehl — führt ihn nie aus |
| ◈ **Daily Deck** | [`daily-deck/`](daily-deck) | Alltag: Programme, Verzeichnisse, SSH, Medien | **öffnet** ein Fenster, verbindet, zeigt |
| ◈ **System Deck** | [`system-deck/`](system-deck) | Wartung, Diagnose, Hardware, Netzwerk, Sicherheit | **liest** und zeigt — ohne Shell, ohne `sudo` |

Gebaut für **Linux Mint 22.3 Cinnamon**, geschrieben in **Python 3 / GTK3**.
Keine einzige externe Python-Abhängigkeit, keine installierten Pakete,
kein Netzwerkzugriff aus dem Programm heraus.

---

## Installation

```bash
git clone https://github.com/Grenoullie91/SCD-Deck.git
cd SCD-Deck

./system-deck/install.sh     # System Deck   (17 Kategorien, 121 Befehle)
./daily-deck/install.sh      # Daily Deck    (6 Kategorien,  36 Befehle)
./command-deck/install.sh    # Command Deck  (8 Kategorien,  93 Befehle)
```

Jeder Installer

* prüft `python3` und GTK3 (beides Systempakete — es wird **nichts installiert**),
* legt **vor jeder Änderung** ein Backup unter `~/.config/<deck>/backups/<Zeitstempel>/` an,
* überschreibt **keine** vorhandene Konfiguration (außer mit `--force`),
* fasst die beiden anderen Decks **nicht** an — die werden nur gelesen,
* richtet Symbol, Menüeintrag und Autostart ein,
* läuft danach den Selbsttest und den Bestandsschutz-Nachweis aus.

Nach der Installation startet jedes Deck bei der nächsten Anmeldung von selbst.

<details>
<summary>Optionen aller Installer</summary>

```
./install.sh                  Installation mit Autostart
./install.sh --no-autostart   ohne Autostart
./install.sh --force          vorhandene Befehlsliste überschreiben
./install.sh --help           Hilfe
```

</details>

Jedes Deck ist **ortsunabhängig**: alle Skripte bestimmen ihren eigenen Pfad über
`BASH_SOURCE` bzw. `__file__`. Du kannst das Repo also auch in
`~/Dokumente/`, `/opt/` oder einem anderen Checkout-Pfad betreiben.

---

## Die Decks im Detail

### ◈ Command Deck — kopiert, führt nie aus

> Ein Klick kopiert den Befehl in die Zwischenablage. **Sonst passiert nichts.**

93 Befehle in 8 Kategorien: Git, Node/npm, Docker, Deploy, Netz, Shell/CI,
Dateien, System. Jedes Ziel ist ein Platzhalter (`<HOST>`, `<USER>`, `<FILE>` …)
— die Vorlage nennt keine Server, keine Pfade, keine Projektstruktur.
Favoriten, Volltextsuche, Position und Größe werden gespeichert.

```bash
python3 command-deck/app/command_deck.py --audit
# 0 verbotene Aufrufe (system/popen/exec*/fork/pty/eval/exec/shell=True)
```

**[Vollständige Dokumentation →](command-deck/README.md)**

### ◈ Daily Deck — öffnet, verbindet, zeigt

> Kein Entwickler-Deck. Keine Git-/Docker-Befehle, keine Code-Snippets.

36 Einträge in 6 Kategorien: Programme starten, XDG-Ordner öffnen, SSH-Hosts
verbinden (aus `~/.ssh/config` gelesen, nie geschrieben), Musik (`ncmpcpp`/MPD),
Systeminformation. SSH-Einträge aus `~/.ssh/config` kommen **dynamisch** dazu —
deshalb meldet der Selbsttest je nach System 37 statt 36. Das Standard-Terminal
wird zur Laufzeit über GSettings ermittelt, nicht fest verdrahtet.

**[Vollständige Dokumentation →](daily-deck/README.md)**

### ◈ System Deck — liest, ohne Shell

> 121 Befehle, 17 Kategorien, 93 davon `READ` — ohne Root, ohne Shell, ohne Schreibzugriff.

Oben ein **Quick System Check** mit neun live ermittelten Werten (CPU, RAM,
Storage, Netzwerk, Dienste, Updates, Temperatur, Firewall). Fehlende Werkzeuge
werden als `NICHT VERFÜGBAR` gemeldet — es wird **nie** etwas nachinstalliert.

```bash
python3 system-deck/app/system_deck.py --selftest
python3 system-deck/app/system_deck.py --audit
```

**[Vollständige Dokumentation →](system-deck/README.md)**

---

## Aktionstypen

Jeder Knopf trägt seinen Typ als **Text**. Es gibt keinen versteckten
Ausführungspfad.

| Typ | Was passiert | Was **nicht** passiert |
|---|---|---|
| **READ** | Lesebefehl über eine Argumentliste, **ohne Shell** (Limit 10 s, 500 Zeilen) | kein `sudo`, kein Schreiben, kein Netzwerk |
| **COPY** | Text landet in der Zwischenablage | **nichts wird ausgeführt** — konstruktionsbedingt |
| **START** | Programm starten (Daily Deck) | keine Shell, kein Befehl |
| **TERM** | ein **sichtbares** Terminal öffnet sich mit dem Befehl | das Deck führt nichts selbst aus |
| **ADMIN** | Bestätigungsdialog zeigt den Befehl **wörtlich**, danach sichtbares Terminal | das Deck führt nie `sudo` aus, es gibt kein Passwortfeld |

**[→ Vollständiges Sicherheitsmodell](docs/SICHERHEIT.md)**

---

## Designfamilie

Alle drei Decks teilen dieselbe technische Basis und dieselbe Optik:

* dieselbe Cairo-Glasfläche, derselbe Eckenradius, dieselben Abstände
* dieselbe 13-teilige Farbpalette (`Dark Purple` / `Neon Violet` / `Cyber`)
* dieselbe Typografie: `Hack`, Fallback `DejaVu Sans Mono`
* gemeinsamer Theme-Grundblock: 252 CSS-Zeilen, bei allen drei **identisch**
* Statusfarben bewusst außerhalb der Purple-Familie, damit Zustände sofort
  erkennbar bleiben: `OK #4ADE80` · `WARN #FBBF24` · `ERR #F87171` · `INFO #C084FC`

```bash
python3 system-deck/tools/theme-check.py
# → GEMEINSAME DESIGNFAMILIE BESTÄTIGT
```

**[→ Architektur im Detail](docs/ARCHITEKTUR.md)**

---

## Konfiguration

Jedes Deck hat **genau eine** Datei, die du bearbeitest:

| Deck | Datei (Laufzeit) | Vorlage im Repo |
|---|---|---|
| Command Deck | `~/.config/terminal-clipboard/commands.json` | `command-deck/config/commands.json` |
| Daily Deck | `~/.config/daily-deck/commands.json` | `daily-deck/config/commands.json` |
| System Deck | `~/.config/system-deck/commands.json` | `system-deck/config/commands.json` |

Diese Dateien sind ausführlich kommentiert (Schlüssel `_readme`) und JSON ohne
Trailing Commas. Nach dem Speichern **`F5`** drücken — oder Rechtsklick →
*Befehle bearbeiten*, das öffnet die Dateigroße im Texteditor.

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

---

## Qualitätssicherung

```bash
./check.sh              # alles: Selbsttests + Audits + Designabgleich
./check.sh selftest     # nur --selftest der drei Decks
./check.sh audit        # nur Konfigurations-Audits
./check.sh design       # nur Theme-/Familienabgleich
```

`check.sh` verändert **nichts** — kein Installationsschritt, kein Schreibzugriff
außer dem eigenen Python-Bytecode-Cache.

Weitere Werkzeuge je Deck:

| Werkzeug | Zweck |
|---|---|
| `command-deck/app/command_deck.py --audit` | beweist maschinell: kein Aufruf von `system`/`popen`/`exec*`/`shell=True` |
| `daily-deck/tools/audit.py` | Konfigurations-Audit: Typ, Ziel, Verfügbarkeit je Eintrag |
| `daily-deck/tools/run.py` | einzelnen Eintrag per Namen ausführen |
| `system-deck/tools/functest.py` | Funktionsabnahme: führt alle `READ`-Befehle wirklich aus |
| `system-deck/tools/uitest.py` | UI-Rauchtest (nur lesend), optional `--shot /tmp/s.png` |
| `*/restore.sh --list` | vorhandene Backups auflisten |

---

## Verzeichnisstruktur

```
SCD-Deck/
├── README.md              ← diese Datei
├── LICENSE                MIT
├── CHANGELOG.md
├── check.sh               Prüflauf für alle drei Decks
├── docs/
│   ├── ARCHITEKTUR.md     gemeinsame Basis, Fenster, Datenfluss
│   ├── SICHERHEIT.md      Blocklisten, Schutzdienste, Versprechen
│   └── BEITRAGEN.md       wie du beiträgst
├── command-deck/          ◈ Developer Control
│   ├── app/command_deck.py
│   ├── assets/{theme.css,command-deck.svg}
│   ├── config/{commands.json,seed_favorites.json}
│   └── {install,restore,uninstall}.sh
├── daily-deck/            ◈ Everyday Control
│   ├── app/daily_deck.py
│   ├── assets/{theme.css,daily-deck.svg}
│   ├── config/commands.json
│   ├── tools/{audit,run,uitest}.py
│   └── {install,restore,uninstall,backup}.sh
└── system-deck/           ◈ System Control
    ├── app/system_deck.py
    ├── assets/{theme.css,system-deck.svg}
    ├── config/commands.json
    ├── tools/{functest,theme-check,uitest}.py
    └── {install,restore,uninstall}.sh
```

Laufzeit-Zustand liegt **nicht** im Repo, sondern in `~/.config/`:

```
~/.config/terminal-clipboard/   Command Deck  (commands.json, state.json, backups/)
~/.config/daily-deck/           Daily Deck    (commands.json, state.json, backups/)
~/.config/system-deck/          System Deck   (commands.json, state.json, *.log, backups/)
```

---

## Backup / Restore / Deinstallation

```bash
# Listen
./system-deck/restore.sh --list
# Neuestes Backup zurückspielen
./system-deck/restore.sh
# Bestimmtes Backup
./system-deck/restore.sh 20260929-140922
# Nur Konfiguration, Code bleibt
./system-deck/restore.sh --keep-project

# Entfernen (nur Dateien, die der Installer selbst angelegt hat)
./system-deck/uninstall.sh
./system-deck/uninstall.sh --purge        # zusätzlich inkl. Backups
```

`install.sh` legt vor **jeder** Änderung automatisch ein Backup an. `restore.sh`
sichert den aktuellen Stand vorher noch einmal als `pre-restore-*`.
Kein Deinstallationsschritt deinstalliert Programme oder verändert
Systemkonfiguration.

---

## Was die Decks nicht tun

* **Installieren nie ein Paket.** Fehlende Werkzeuge werden gemeldet, nicht beschafft.
* **Führen nie `sudo` aus.** Root-Befehle öffnen ein sichtbares Terminal zur Bestätigung.
* **Schreiben nie in fremde Bestände.** Command Deck, Daily Deck, Wallpaper,
  Cinnamon-Schemata, Cairo-Dock und Panel werden ausschließlich gelesen.
* **Kennen keine Telemetrie.** Keine Analytics, keine Cloud, keine Netzwerkzugriffe
  aus dem Programm heraus.
* **Speichern kein Passwort.** Kein Passwortfeld, kein Keyring, kein Zugriff auf `~/.ssh`.
* **Ändern keine Firewall-Regeln.** UFW liefert nur Status und Regelliste (read-only).

---

## Beitragen

Issues, Fehlerberichte und Erweiterungen sind willkommen — siehe
**[docs/BEITRAGEN.md](docs/BEITRAGEN.md)**. Bitte vor einem Pull Request:

```bash
./check.sh          # muss vollständig grün sein
```

Befehle mit `READ`, `TERM` oder `ADMIN` brauchen im PR eine Begründung, warum
sie in die Blockliste des jeweiligen Decks gehören oder warum sie unbedenklich
sind. Neue Befehlsarten werden **nie** ohne sichtbaren Bestätigungsdialog
eingeführt.

---

## Lizenz

[MIT](LICENSE) © 2026 Grenoullie91 — freie Nutzung, Änderung und Weitergabe
gestattet.

```
◈ SCD-DECK
Command Deck = Developer Control
Daily Deck   = Everyday Control
System Deck  = System Control
```
