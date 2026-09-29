# ◈ COMMAND DECK

**Terminal Command Deck** — ein kleines Desktop-Widget, das deine wichtigsten
Terminal-Befehle immer griffbereit hält. Ein Klick kopiert den Befehl in die
Zwischenablage. **Sonst passiert nichts.**

> **Sicherheits-Garantie:** Dieses Werkzeug führt *niemals* Befehle aus.
> Es kopiert ausschließlich Text. Kein `sudo`, kein `rm`, kein `npm install`,
> kein `systemctl restart` — nichts davon wird auch nur angefasst.
> Maschinell nachweisbar über `python3 app/command_deck.py --audit`.

### Ort im Repository

Dieses Deck liegt in `SCD-Deck/command-deck/`. Alle Pfade in dieser Datei sind
**relativ zum Repository-Root** gemeint (Ausnahme: `~/.config/terminal-clipboard`,
das ist der Laufzeit-Zustand auf deinem Rechner). Das Deck ist **ortsunabhängig**
— es läuft aus jedem Verzeichnis.

```bash
git clone https://github.com/Grenoullie91/SCD-Deck.git
cd SCD-Deck/command-deck
./install.sh
```

---

## Schnellstart

```bash
cd command-deck
./install.sh          # installiert, legt Backup an, startet Autostart ein
python3 app/command_deck.py     # sofort starten
```

Nach der Installation startet das Widget bei jeder Anmeldung automatisch
und taucht zusätzlich im Anwendungsmenü als **Command Deck** auf.

---

## Bedienung

| Aktion | Wie |
|---|---|
| Befehl kopieren | `COPY` anklicken **oder** direkt auf den Befehlstext klicken |
| Bestätigung | Button wird für 1,5 s grün mit `✓ OK` |
| Favorit | Stern `☆` anklicken → erscheint oben im Abschnitt `★ FAVORITES` |
| Suchen | `Strg+F` oder in das Suchfeld klicken, tippen: `git`, `docker`, `sudo` … |
| Suche leeren | `Esc` oder `✕` |
| Fenster verschieben | Header mit „COMMAND DECK" anfassen und ziehen |
| Größe ändern | violettes Quadrat unten rechts ziehen (min. 300×300) |
| Menü | Rechtsklick auf den Header |
| Immer im Vordergrund | `Strg+T` oder Rechtsklick → „Immer im Vordergrund" |
| Befehle bearbeiten | Rechtsklick → „Befehle bearbeiten …", danach `F5` |
| Neu laden | `F5` |
| Ausblenden | `Strg+H` |
| Beenden | `Strg+Q` oder Rechtsklick → „Beenden" |

Position, Größe, Favoriten und Always-on-Top werden bei jedem Beenden gespeichert
und beim nächsten Start wiederhergestellt.

---

## Eigene Befehle hinzufügen

Die Befehlsliste liegt **nicht** im Programmcode, sondern in:

```
~/.config/terminal-clipboard/commands.json
```

Format:

```json
{
  "categories": {
    "Git": {
      "icon": "◈",
      "commands": [
        "git status --short --branch",
        "git commit -m \"<MESSAGE>\""
      ]
    },
    "MeineKategorie": {
      "icon": "★",
      "commands": ["befehl eins", "befehl zwei"]
    }
  }
}
```

* Reihenfolge der Kategorien = Reihenfolge im Widget.
* `icon` ist optional (Standard `◈`).
* Kategorien, die mit `_` beginnen, werden ignoriert — dort kannst du dir Notizen machen.
* Nach dem Speichern `F5` drücken oder das Widget neu starten.

Nach dem Bearbeiten prüfen (meldet JSON-Fehler verständlich):

```bash
python3 command-deck/app/command_deck.py --selftest
```

### Platzhalter

Platzhalter in spitzen Klammern werden **bewusst mitkopiert** und nicht ersetzt:

```
git commit -m "<MESSAGE>"
cd <PROJECT_PATH>
sudo apt install <PACKAGE>
```

Du ersetzt sie im Terminal nach dem Einfügen — so kannst du sie auch als
Merksatz für Formulare nutzen, die du ausfüllen willst.

---

## Die Befehlsliste

Die 93 Befehle in 8 Kategorien sind eine **Vorlage**, kein persönliches Profil.
Sie decken die Werkzeuge ab, die in der Entwicklung täglich vorkommen — Git,
Node, Docker, Remote, Netz, Shell, Dateien, System:

| Kategorie | Befehle | Inhalt |
|---|---|---|
| Git | 23 | Status, Log, Diff, Staging, Branches, Fetch, Push, Reset, SHA-Abfragen |
| Node / npm | 12 | Install, Dev, Build, Test, Lint, Script-Auflistung, `npx` |
| Docker | 13 | Compose und klassisch: Status, Logs, Images, Inspect, Stats |
| Deploy / Remote | 6 | SSH, Port-Forward, `rsync`, `scp` — alle Ziele als Platzhalter |
| Netz / Health | 7 | offene Ports, HTTP-Health, `curl`, `ping`, `dig`, `traceroute` |
| Shell / CI | 8 | `set -Eeuo pipefail`, `test -z`, Pfade, Prüfsummen, Zeitstempel |
| Dateien | 15 | Aufräumen, Kopieren, Suchen, Lesen, Platzbelegung |
| System | 10 | Pakete, Dienste, Prozesse, Speicher, Journal |

Alles Persönliche ist durch Platzhalter ersetzt. Die Vorlage nennt **keine**
Servernamen, keine Benutzernamen, keine Pfade und keine Projektstruktur:

| Platzhalter | Bedeutung |
|---|---|
| `<USER>` / `<HOST>` / `<REMOTE_PATH>` | Ziele von `ssh`, `rsync`, `scp` |
| `<LOCAL_PORT>` / `<REMOTE_HOST>` / `<REMOTE_PORT>` | Port-Forward |
| `<FILE>` / `<DIR>` / `<PATTERN>` / `<FOLDER>` | allgemeine Dateireferenzen |
| `<SERVICE>` / `<PACKAGE>` | Dienste und Pakete |
| `<BRANCH>` / `<SHA>` / `<MESSAGE>` / `<N>` | Git-Argumente |
| `<LOCAL_FILE>` / `<SRC>` / `<DEST>` | Kopierziele |

**So passt jeder seine eigene Liste an.** Platzhalter werden **mitkopiert**,
nicht ersetzt — der Befehl landet fertig in der Zwischenablage, damit er im
Terminal gegen den echten Wert eingetippt wird. Ein Deck, das Pfade fest
verdrahtet, wäre auf einem fremden Rechner nutzlos und würde beim Teilen
fremde Infrastruktur nennen.

Dieselbe Liste liegt zweimal vor, und das ist Absicht:

| Datei | Zweck |
|---|---|
| `command-deck/config/commands.json` | die Vorlage, die in diesem Repo liegt |
| `~/.config/terminal-clipboard/commands.json` | **deine** Liste auf deinem Rechner |

`install.sh` legt die Vorlage nur an, wenn noch keine existiert. Ab dann wird
die Laufzeitkonfiguration nie überschrieben — außer mit `./install.sh --force`.

**Eigene Befehle ergänzen?** Genau dafür ist `commands.json` da. Eine Zeile
in der passenden Kategorie, `F5` drücken, fertig. Details in
[Bereich „Eigene Befehle"](#eigene-befehle-hinzufügen).

---

## Warum ein Fenster und kein echtes Cinnamon-Widget?

**Cinnamon-Desklets wurden in Cinnamon 6 entfernt.** Auf einem aktuellen Mint
gibt es sie nicht mehr:

```bash
ls /usr/lib/cinnamon/*.so | grep -i desklet    # → keine Treffer
```

Ein echtes Desklet ist also nicht verfügbar. Stattdessen: ein rahmenloses,
halbtransparentes GTK3-Fenster vom Typ `_NET_WM_WINDOW_TYPE_DOCK`, das sich
optisch wie ein Widget verhält. Verifiziert:

```
_NET_WM_WINDOW_TYPE      = _NET_WM_WINDOW_TYPE_DOCK
_NET_WM_STATE            = _SKIP_PAGER, _SKIP_TASKBAR, _ABOVE, _STICKY
```

* kein Rahmen, kein Taskbar-Eintrag, kein Fenstermenü
* **immer im Vordergrund** (abschaltbar)
* **auf allen Arbeitsflächen** (STICKY)
* halbtransparente, abgerundete Glasfläche mit eigenem Cairo-Zeichner

### Warum kein HTML/JS-Elektron-Wrapper?

GTK3 über PyGObject gehört zu jedem Linux Mint, dadurch:

* **keine zusätzliche Paketinstallation** nötig
* ~64 MB RAM, **0 % CPU im Leerlauf** (kein laufender Timer)
* kein `xclip`/`xsel` nötig — die Zwischenablage geht direkt über
  `Gtk.Clipboard`, also **kein externes Tool und kein Shell-Aufruf**

---

## Projektstruktur

```
command-deck/
├── app/
│   └── command_deck.py        Widget (GTK3, ~1000 Zeilen)
├── assets/
│   ├── theme.css              Purple/Neon/Glass-Theme
│   └── command-deck.svg       Symbol für Menü und Taskleiste
├── config/
│   ├── commands.json          Vorlage der Befehlsliste
│   └── seed_favorites.json    Start-Favoriten
├── install.sh                 Installation + Backup + Selbsttest
├── uninstall.sh               Deinstallation
├── restore.sh                 Backup zurückspielen
└── README.md
```

Laufzeitdaten (bearbeitbar):

```
~/.config/terminal-clipboard/
├── commands.json              ← deine Befehle (die wichtige Datei)
├── state.json                 Position, Größe, Favoriten, Always-on-Top
├── seed_favorites.json
├── selftest.log
└── backups/<Zeitstempel>/     von install.sh angelegt
```

---

## Installation im Detail

```bash
./install.sh                  # mit Autostart
./install.sh --no-autostart   # ohne Autostart
./install.sh --force          # Befehlsliste durch die Vorlage ersetzen
```

`install.sh` legt **vor** jeder Änderung ein Backup unter
`~/.config/terminal-clipboard/backups/<Zeitstempel>/` an, prüft die
Voraussetzungen, installiert Menüeintrag und Symbol, schreibt den
Autostart-Eintrag und führt anschließend den Selbsttest inklusive
Sicherheits-Audit aus.

### Entfernen

```bash
./uninstall.sh                # Autostart + Menü + Symbol weg, Daten bleiben
./uninstall.sh --purge        # zusätzlich Befehlsliste und Zustand löschen
rm -rf command-deck # Projektordner selbst
```

`uninstall.sh` löscht ausschließlich die vier Dateien, die `install.sh` selbst
angelegt hat. Andere Autostart-Einträge, Panel-Applets, Themes und
Cinnamon-Einstellungen werden nicht angefasst.

### Zurücksetzen

```bash
./restore.sh --list           # alle Backups anzeigen
./restore.sh                  # letztes Backup einspielen
./restore.sh 20260929-103304  # bestimmtes Backup
```

Auch `restore.sh` legt vorher noch einmal eine Sicherheitskopie an.

---

## Tests

```bash
python3 app/command_deck.py --selftest        # Konfiguration + Sicherheit
python3 app/command_deck.py --audit           # nur der Ausführungs-Audit
python3 app/command_deck.py --print-commands  # geladene Liste anzeigen
python3 app/command_deck.py --copy "text"     # Zwischenablage-Roundtrip
python3 app/command_deck.py --search docker   # Start mit vorgefüllter Suche
python3 app/command_deck.py --reset-geometry  # Position/Größe zurücksetzen
```

### Was tatsächlich getestet wurde

* **Selbsttest** — 6 Prüfgruppen: AST-Sicherheits-Audit, Zwischenablage-Roundtrip,
  Befehlsliste, Struktur der Einträge, Zustandsdatei, Randbedingungen → *bestanden*
* **Interaktionstest** — 32 Prüfungen (Suche, Favoriten, Copy, Platzhalter,
  Geometrie, Always-on-Top, Neuladen) → *32/32 bestanden*
* **Echter Eingabetest (XTEST)** — 17 Prüfungen mit **echten Mausereignissen über
  den X-Server**: Klick auf `COPY`, Klick auf Befehlstext, Klick auf Stern,
  Header ziehen, Resize-Grip ziehen, 8× Klick auf verschiedene Befehle
  → *17/17 bestanden*
* **Leistung** — 64 MB RAM, 6 Threads, **0 % CPU** im Leerlauf
* **Installationszyklus** — `install.sh` → `uninstall.sh` → `restore.sh` → `install.sh`
  geprüft; andere Autostart-Einträge blieben unangetastet
* **Darstellung** — Screenshots der Oberfläche geprüft (Suche, Favoriten, Platzhalter)

Drei echte Fehler wurden dabei gefunden und behoben: `set_above_child(True)`
blockierte Klicks auf die `COPY`-Buttons, `Gdk.EventMask.BUTTON1_MASK` existiert
nicht (Absturz beim Ziehen), und `restore.sh` erwartete einen Ordnernamen,
während `install.sh` einen vollen Pfad speicherte.

---

## Sicherheit im Detail

Der Audit ist eine **AST-Analyse des Quelltextes**, kein Textmuster-Suchbefehl:

```bash
python3 app/command_deck.py --audit
# Verbotene Aufrufe: 0
# subprocess in: _on_edit, raise_existing
```

* **Verboten und nachweislich nicht vorhanden:** `os.system`, `os.popen`,
  `os.execl/v/ve/vp/vpe`, `os.fork`, `os.forkpty`, `os.spawn*`, `os.posix_spawn*`,
  `pty.spawn`, `pty.fork`, `GLib.spawn_async/sync`,
  `GLib.spawn_command_line_*`, `Gio.Subprocess`, `Gio.SubprocessLauncher`,
  `eval`, `exec`, `compile`, `__import__`, sowie jedes `shell=True`
* **`subprocess` kommt genau zweimal vor**, jeweils in klar benannten
  Funktionen, und das Audit schlägt fehl, sobald es in einer anderen auftaucht:
  * `_on_edit()` — öffnet `commands.json` in einem Texteditor (`gnome-text-editor`,
    `gedit`, `xed`, `mousepad`, `kate`), fest als Argumentliste, nie aus der
    Befehlsliste
  * `raise_existing()` — `wmctrl`, um ein bereits laufendes Deck in den
    Vordergrund zu holen
* **Einziger Datenweg für Befehlstexte:**
  `Button → Gtk.Clipboard.set_text() → .store()`
* Befehle werden **eine Zeile ohne Verkettung** erwartet; der Selbsttest meldet
  mehrzeilige Einträge oder solche mit `&&`, `||`, `|`, `;`, `&` am Ende

> Hinweis: `--copy` auf der Kommandozeile ist ein reines Debug-Werkzeug
> (Text → Zwischenablage). Der normale Weg ist immer der `COPY`-Button.

---

## Farben und Schrift

| Rolle | Farbe |
|---|---|
| Hintergrund | `#0B0612` · `#12091F` · `#1B0D2B` |
| Violet | `#6D28D9` |
| Neon-Violett | `#8B5CF6` · `#A855F7` |
| Hell-Violett | `#C084FC` |
| Text | `#EDE9F5` / `#9C8FB5` / `#5E5375` |

Schrift: **Hack** (wenn installiert), Rückfall `DejaVu Sans Mono`.
Der Glow ist sparsam: nur die Eckakzente, die Kopier-Bestätigung und die
Fokuslinien leuchten.

---

## Anpassen

| Wunsch | Weg |
|---|---|
| Theme ändern | `assets/theme.css` bearbeiten, Widget neu starten |
| Deck etwas transparenter | `opacity` in `~/.config/terminal-clipboard/state.json` (0.55–1.0) |
| Andere Schrift | in `theme.css` die `font-family`-Zeilen |
| Größenbereich | `MIN_W` / `MIN_H` in `app/command_deck.py` |
| Standardposition | `--reset-geometry`, dann `x`/`y` in `state.json` |
| Zeichen neben dem Suchfeld | ist bewusst ein Chevron `❯`; `⌕` (U+2315) ist laut Unicode ein *Telephone Recorder*, kein Lupenglas, und sah falsch aus |
