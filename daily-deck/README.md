# ◈ DAILY DECK

**Persönliches Alltags-Cockpit für Linux Mint / Cinnamon**

Ein kleines, kompaktes Desktop-Widget, das die alltäglichen Terminal-Aktionen
bündelt: Programme starten, Verzeichnisse öffnen, SSH-Server verbinden,
Systeminfos ansehen.

> **Wichtig:** Das Daily Deck ist **kein** Entwickler-Command-Deck.
> Es führt keine Git-/Docker-Befehle aus und kopiert keine Code-Snippets.
> Es öffnet, navigiert, verbindet, zeigt an.

### Ort im Repository

Dieses Deck liegt in `SCD-Deck/daily-deck/`. Alle Pfade in dieser Datei sind
**relativ zum Repository-Root** gemeint (Ausnahme: `~/.config/daily-deck`, das ist
der Laufzeit-Zustand auf deinem Rechner). Das Deck ist **ortsunabhängig** — es
läuft aus jedem Verzeichnis.

```bash
git clone https://github.com/Grenoullie91/SCD-Deck.git
cd SCD-Deck/daily-deck
./install.sh
```

---

## Inhalt

1. [Systemvoraussetzungen](#1-systemvoraussetzungen)
2. [Installation](#2-installation)
3. [Start / Stopp](#3-start--stopp)
4. [Bedienung](#4-bedienung)
5. [Kategorien und Befehle](#5-kategorien-und-befehle)
6. [Aktionstypen: START / TERMINAL / COPY](#6-aktionstypen-start--terminal--copy)
7. [Konfigurationsdatei](#7-konfigurationsdatei)
8. [Eigene Befehle hinzufügen](#8-eigene-befehle-hinzufügen)
9. [SSH-Hosts](#9-ssh-hosts)
10. [Automatisch erkannte Programme](#10-automatisch-erkannte-programme)
11. [CS Matrix – Entscheidung](#11-cs-matrix--entscheidung)
12. [ncmpcpp / MPD](#12-ncmpcpp--mpd)
13. [Sicherheitsregeln](#13-sicherheitsregeln)
14. [Backup / Restore](#14-backup--restore)
15. [Deinstallation](#15-deinstallation)
16. [Wartung & Prüfwerkzeuge](#16-wartung--prüfwerkzeuge)
17. [Bekannte Einschränkungen](#17-bekannte-einschränkungen)
18. [Verzeichnisstruktur](#18-verzeichnisstruktur)

---

## 1. Systemvoraussetzungen

Das Deck läuft auf **Linux Mint mit Cinnamon**. Nichts davon ist verdrahtet —
alles wird zur Laufzeit ermittelt:

| Punkt | Wie | Fallback |
|---|---|---|
| Distribution | Linux Mint / Cinnamon | — |
| Shell | `/bin/bash` | — |
| Standard-Terminal | `org.cinnamon.desktop.default-applications.terminal`, dann `org.gnome.desktop.*`, dann `$TERMINAL` | `gnome-terminal`, `x-terminal-emulator`, `xterm` |
| XDG-Ordner | `xdg-user-dir` — **deutsche und englische** Namen | englische Namen |
| SSH-Hosts | `~/.ssh/config` lesen | keine |
| Fensteranheben | `wmctrl`, sonst `xdotool` | nur Start |
| Pakete | **es wird nichts installiert** | — |

Die Funktion heißt `detect_terminal()` in `app/daily_deck.py`. Wer
`x-terminal-emulator` oder `kitty` benutzt, bekommt dieses — nicht
`gnome-terminal`. Wallpaper, Theme, Auflösung und Panel werden nicht angefasst.

---

## 2. Installation

```bash
cd daily-deck
./install.sh                 # mit Autostart
./install.sh --no-autostart  # ohne Autostart
./install.sh --force         # Befehlsliste neu erzeugen (überschreibt die eigene)
./install.sh --help
```

`install.sh` erledigt:

* Backup des eigenen Zustands nach `~/.config/daily-deck/backups/<Zeitstempel>/`
* Anlegen von `~/.config/daily-deck/{commands.json,state.json}`
* Symbol nach `~/.local/share/icons/hicolor/scalable/apps/daily-deck.svg`
* Menüeintrag „Daily Deck“ in `~/.local/share/applications/`
* Autostart `~/.config/autostart/daily-deck.desktop`
* Selbsttest + Bestandsschutz-Kontrolle des Command Decks

### Vollständige Rückmeldung des Installers

```
1  Backup            → ~/.config/daily-deck/backups/YYYYmmdd-HHMMSS
2  Voraussetzungen   → python3 + GTK3 vorhanden, Standard-Terminal erkannt
3  Konfiguration     → commands.json / state.json
4  Symbol            → ~/.local/share/icons/hicolor/scalable/apps/daily-deck.svg
5  Menüeintrag       → ~/.local/share/applications/daily-deck.desktop
6  Autostart         → ~/.config/autostart/daily-deck.desktop
7  Prüfung           → Selbsttest
8  Bestandsschutz    → Command Deck unberührt, Wallpaper unberührt
```

---

## 3. Start / Stopp

| Aktion | Befehl |
|---|---|
| Starten | `python3 daily-deck/app/daily_deck.py` |
| Aus dem Menü | „Daily Deck“ im Anwendungsmenü |
| Beenden | `Strg+Q` im Widget, oder `✕` blendet nur aus |
| Instanz anheben | `python3 daily-deck/app/daily_deck.py --raise` |
| Version | `python3 daily-deck/app/daily_deck.py --version` |

Eine Sperrdatei (`~/.config/daily-deck/instance.lock`) verhindert mehrere
Instanzen. Ein zweiter Start hebt die bestehende einfach an.

---

## 4. Bedienung

Optik und Bedienlogik sind **identisch zum Command Deck**: gleiche
Glasfläche, gleiche Kopfzeile, gleiche Suchzeile mit Hinweistext und
Löschknopf, gleiche Kategoriebalken mit Zähler, gleiche Zeilen mit Stern
und Aktionsknopf, gleiche Fußzeile mit Status, `▲ PIN` und Größengriff.
Unterschied ist nur die Art der Aktion (siehe Abschnitt 6).

| Element | Funktion |
|---|---|
| Kopfzeile | **Verschieben** – am Fenster ziehen · Rechtsklick = Menü |
| `PIN` (Kopfzeile) / `▲ PIN` (Fußzeile) | zeigt den Always-on-Top-Status |
| Suchzeile `❯` | Freitextfilter über Name, Beschreibung und Kategorie |
| `✕` rechts in der Suchzeile | Filter leeren |
| `☆` / `★` je Zeile | Favorit umschalten (Erscheint oben in `★ Favorites`) |
| Klick auf die Zeile | führt die Aktion aus |
| Knopf `START` / `TERMINAL` / `COPY` | **zeigt die Art der Aktion** und löst sie aus |
| `◢` (Fußzeile rechts) | Fenstergröße ändern |
| Tooltip einer Zeile | Beschreibung, Typ, Ziel, Verfügbarkeit |

**Tastatur**

| Taste | Funktion |
|---|---|
| `Strg+F` | Suchfeld fokussieren (Auswahl markieren) |
| `Enter` / `↓` in der Suche | ersten Treffer ausführen |
| `Esc` | Filter leeren |
| `Strg+H` | Deck verbergen |
| `Strg+T` | Always-on-Top umschalten |
| `F5` | Aktionen neu laden |
| `Strg+Q` / `Strg+W` | Programm beenden |

**Menü (Rechtsklick auf die Kopfzeile)**

Immer im Vordergrund · Aktionen neu laden (F5) · Aktionen bearbeiten …
· Deck verbergen (Strg+H) · Position / Größe zurücksetzen · Beenden

**Gespeichert wird** in `~/.config/daily-deck/state.json`:
Position, Größe, Always-on-Top, Transparenz, Favoriten.

---

## 5. Kategorien und Befehle

Aktuell **37 Einträge** in 6 Kategorien.

### 🚀 START — Programme starten

| Eintrag | Typ | Aktion |
|---|---|---|
| 🖥 Terminal öffnen | TERMINAL | gnome-terminal im Home-Verzeichnis |
| 🖥 Terminal · sauber | TERMINAL | Terminal im Home, Bild geleert |
| 📂 Nemo | START | `nemo ~` |
| 🟣 CS Matrix | TERMINAL | `cmatrix` |
| 🎵 Musik · Rhythmbox | START | `rhythmbox` |
| ✉ Thunderbird | START | `thunderbird` |

### 📁 NAVIGATION — Verzeichnisse

Alle öffnen ein **neues Terminal direkt im gewählten Verzeichnis**.

| Eintrag | Verzeichnis |
|---|---|
| ⬆ Home | `~` |
| 📥 Downloads | `~/Downloads` |
| 📄 Dokumente | `~/Dokumente` |
| 🎵 Musik-Ordner | `~/Musik` |
| 🖼 Bilder | `~/Bilder` |
| 🎬 Videos | `~/Videos` |
| 🗂 Schreibtisch | `~/Schreibtisch` |
| 📦 Projekte | `~/Projekte` |
| 📦 Projekte (Schreibtisch) | `~/Schreibtisch/Projekte` |
| 🗂 Nemo Downloads | START `nemo ~/Downloads` |

> Die Pfade stammen aus `xdg-user-dir` – es wurde nichts erfunden.

### 🌐 SERVER — SSH

| Eintrag | Typ | Aktion |
|---|---|---|
| ⏏ SSH verlassen | COPY | kopiert `exit` |
| 🌐 SSH-Verbindung prüfen | COPY | kopiert `ssh -v` (Alias anhängen) |
| 📜 SSH-Aliase anzeigen | COPY | kopiert `grep -E '^Host ' ~/.ssh/config` |
| 🌐 <SSH-ALIAS> | TERMINAL | `ssh <SSH-ALIAS>` (automatisch erkannt) |

Die Spalte mit den Erläuterungen steht als **Tooltip** über dem Eintrag,
nicht als zweite Zeile – dadurch bleibt das Deck so kompakt wie das
Command Deck.

### ⌨ TERMINAL — In der bestehenden Shell

Diese Befehle sind **nur innerhalb einer laufenden Shell sinnvoll**
(`cd ..` in einer neuen Shell bringt nichts). Sie werden deshalb
ausschließlich **kopiert**, nie ausgeführt.

| Eintrag | kopiert |
|---|---|
| ⬆ cd .. | `cd ..` |
| ⬆ cd ~ | `cd ~` |
| 📍 pwd | `pwd` |
| 📋 ls -la | `ls -la` |
| 👁 versteckte Dateien | `ls -lad .*` |
| 🧹 clear | `clear` |
| 🗂 cd &lt;Verzeichnis&gt; | `cd ` (Platzhalter zum Ergänzen) |

### ⚙ SYSTEM

| Eintrag | Typ | Aktion |
|---|---|---|
| 💻 Systeminfo | TERMINAL | `neofetch` |
| 💽 Speicherplatz | COPY | `df -h` |
| 🧠 Arbeitsspeicher | COPY | `free -h` |
| ⚙ Top-Prozesse | COPY | `ps aux --sort=-%mem \| head -n 15` |
| ⏱ Laufzeit | COPY | `uptime` |
| 📶 Netzwerkstatus | COPY | `nmcli device status` |
| 🌍 IP-Adressen | COPY | `ip -brief address` |

### 🎵 MEDIEN

| Eintrag | Typ | Aktion |
|---|---|---|
| 🎵 Musik / ncmpcpp | TERMINAL | `ncmpcpp` – **derzeit nicht installiert**, Eintrag ist ausgegraut |
| 🎼 MPD starten | TERMINAL | `systemctl --user start mpd` – **mpd nicht installiert** |
| 🔊 MPD-Status | COPY | `systemctl --user status mpd` |

Sobald `ncmpcpp` und `mpd` installiert sind, werden die Einträge automatisch
aktiv – ohne die Konfiguration anzufassen (siehe Abschnitt 12).

---

## 6. Aktionstypen: START / TERMINAL / COPY

Jeder Knopf trägt seine Art **sichtbar** als Aufschrift. Es gibt keinen
versteckten Ausführungspfad.

| Typ | Bedeutung | Technik |
|---|---|---|
| `START` | startet eine Desktop-Anwendung | `subprocess.Popen(argv)` – Argumentliste, **keine** Shell |
| `TERMINAL` | öffnet das System-Terminal in einem Arbeitsverzeichnis, führt dort optional einen Befehl aus | `gnome-terminal --working-directory=…` bzw. `gnome-terminal -- bash -lc '…'` |
| `COPY` | kopiert Text in die Zwischenablage, **führt nichts aus** | `Gtk.Clipboard.set_text()` / `.store()` |

Ein `COPY`-Eintrag kann konstruktionsbedingt keinen Prozess starten.

---

## 7. Konfigurationsdatei

```
~/.config/daily-deck/commands.json   ← Aktionen (bearbeitbar)
~/.config/daily-deck/state.json      ← Position, Größe, Transparenz, Favoriten
~/.config/daily-deck/backups/        ← Sicherungen
~/.config/daily-deck/instance.lock   ← verhindert Doppelstart
```

Die Befehle sind **nicht im Programmcode verdrahtet**.
Nach dem Bearbeiten: `F5` im Deck oder `⚙ → Neu laden`.

### Aufbau eines Eintrags

```jsonc
{
  "name": "🖥 Terminal öffnen",   // Anzeigename mit Icon
  "description": "Standard-Terminal im Home-Verzeichnis",
  "type": "TERMINAL",            // START | TERMINAL | COPY  (Pflicht)
  "argv": ["nemo", "~"],          // nur bei START
  "command": "cmatrix",           // TERMINAL: Befehl im Terminal
                                  // COPY: Text zum Kopieren
  "workdir": "~/Downloads",       // TERMINAL: Arbeitsverzeichnis
  "copy_text": "ls -la",          // optional: eigener Text für COPY
  "requires": ["ncmpcpp"],        // Programme, die installiert sein müssen
  "enabled": true                 // false blendet den Eintrag aus
}
```

Kategorien:

```jsonc
"categories": {
  "START": {
    "icon": "🚀",
    "order": 10,                  // Reihenfolge
    "entries": [ … ]
  }
}
```

`requires` ist praktisch: fehlt das Programm, wird der Eintrag **ausgegraut**
und zeigt im Tooltip `FEHLT: <Programm>` – statt einen Fehler zu produzieren.

---

## 8. Eigene Befehle hinzufügen

1. `~/.config/daily-deck/commands.json` im Editor öffnen
   (im Deck: `⚙ → Befehle bearbeiten`)
2. In der passenden Kategorie einen neuen Block nach dem Muster oben einfügen
3. **JSON-Validität beachten** – Komma nach dem letzten Element, Anführungszeichen
4. Im Deck `F5` drücken
5. Prüfen: `python3 daily-deck/tools/audit.py` zeigt Typ, Ziel und Verfügbarkeit

Beispiel – Terminal in einem neuen Ordner:

```jsonc
{
  "name": "📁 Mails",
  "description": "Terminal in ~/Mails",
  "type": "TERMINAL",
  "workdir": "~/Mails"
}
```

Beispiel – nur kopierbarer Befehl:

```jsonc
{
  "name": "🔎 große Dateien",
  "description": "kopiert: du -sh * | sort -rh | head",
  "type": "COPY",
  "command": "du -sh * | sort -rh | head",
  "copy_text": "du -sh * | sort -rh | head"
}
```

---

## 9. SSH-Hosts

`~/.ssh/config` wird **ausschließlich gelesen** und **niemals geschrieben**.
Neue `Host`-Einträge erscheinen automatisch im Deck – ohne Pflege in
`commands.json`. Keine Passwörter, keine Keys, keine Zugangsdaten im Deck.

Beispiel (aus `~/.ssh/config` gelesen — hier anonymisiert):

| Alias | Ziel | Benutzer |
|---|---|---|
| `<SSH-ALIAS>` | `<IP>` | `<USER>` |

Das Deck liest nur die `Host`-Zeilen. Es kennt und speichert keine IPs, keine
Benutzernamen und keine Schlüssel aus dieser Datei — die Tabelle oben zeigt nur,
was der jeweilige Nutzer selbst in seiner `~/.ssh/config` stehen hat.

Klick auf `🌐 <SSH-ALIAS>` öffnet:

```bash
gnome-terminal -- bash -lc 'cd ~ && ssh <SSH-ALIAS>; …'
```

→ Es wird genau der vorhandene Alias verwendet, inklusive `IdentityFile` und
`IdentitiesOnly` aus deiner `~/.ssh/config`.

**„SSH verlassen“** kopiert `exit`. Im SSH-Fenster `Strg+Shift+V`, dann Enter.
Bewusst **kein** `kill`/`pkill` – das wäre abhängig vom Terminal-Typ fehler- oder
zerstörerisch. Details unter [Abschnitt 17](#17-bekannte-einschränkungen).

---

## 10. Automatisch erkannte Programme

Jeder Eintrag prüft beim Laden, ob sein Programm vorhanden ist
(`shutil.which`). Fehlt es, wird die Zeile ausgegraut, der Knopf heißt
`NICHT VERFÜGBAR`, und der Tooltip nennt das fehlende Werkzeug. **Es wird
nichts nachinstalliert.**

| Befehl | Wird verwendet für | Fehlend? |
|---|---|---|
| *(Standard-Terminal)* | alle `TERMINAL`-Einträge | Einträge ausgegraut |
| `nemo` | Dateimanager | `START` läuft nicht |
| `cmatrix` | **CS Matrix** | ausgegraut |
| `neofetch` | Systeminfo | ausgegraut |
| `rhythmbox` | Musikplayer | `START` läuft nicht |
| `thunderbird` | E-Mail | `START` läuft nicht |
| `nmcli` | Netzwerkstatus | ausgegraut |
| `wmctrl` | Instanz anheben | nur Start |
| `ncmpcpp` | Musik-Frontend | siehe Abschnitt 12 |
| `mpd` | Musik-Dienst | siehe Abschnitt 12 |

Wer ein anderes Programm nutzt, trägt es in `commands.json` ein — der
Dateimanager, der Musikplayer und der E-Mail-Client sind frei wählbar.

---

## 11. CS Matrix – Entscheidung

Es gibt mehrere Matrix-Programme. `cmatrix` ist der Klassiker und der
üblichste Kandidat auf Mint; es ist ein reines Terminalprogramm und passt von
allen am besten in ein schmales Deck-Fenster. Deshalb steht es als Vorgabe in
der Konfiguration — wer ein anderes bevorzugt, ersetzt einfach den Befehl:

```bash
sudo apt install cmatrix        # Vorgabe
sudo apt install hollywood      # Alternative
sudo apt install cava           # Alternative
```

Eintrag:

```json
{ "name": "🟣 CS Matrix", "type": "TERMINAL", "command": "cmatrix" }
```

Ein Terminal öffnet sich in `~` und startet `cmatrix`. Nach `q` (der
Quittierungstaste von cmatrix) erscheint der Abschlusshinweis des Decks.

---

## 12. ncmpcpp / MPD

**Sind sie nicht installiert**, sind die drei Einträge vorhanden, aber
`requires`-markiert und dadurch ausgegraut. Zum Nachinstallieren:

```bash
sudo apt install ncmpcpp mpd
```

Es wurde **nichts ungefragt installiert** — das Deck installiert nie ein Paket. Die Einträge sind vorhanden, aber
`requires`-markiert und dadurch ausgegraut, bis die Pakete nachinstalliert
werden. Danach sind sie sofort funktionsfähig – die Konfiguration muss nicht
geändert werden.

**Danach** in der Konfiguration des Decks die Einträge optional anpassen:

* `ncmpcpp` braucht eine MPD-Verbindung; Standard ist `~/.config/ncmpcpp/config`
  mit Zeile `mpd_host = 127.0.0.1`
* MPD als Benutzerdienst: `systemctl --user enable --now mpd`
* **Wichtig:** es wurden **keine** Musikdateien verschoben, umbenannt oder
  gelöscht, und **keine** vorhandene MPD-/ncmpcpp-Konfiguration verändert.

Rhythmbox ist installiert und als `🎵 Musik · Rhythmbox` bereits verfügbar –
das Deck ist also auch ohne ncmpcpp sofort nutzbar.

---

## 13. Sicherheitsregeln

* **Blockliste.** Befehle mit destruktivem Muster werden beim Laden abgewiesen
  und sind **nicht ausführbar**: `rm -rf`, `mkfs`, `fdisk`, `dd`, `shred`,
  `sudo`, `su`, `passwd`, `useradd`, `chown`, `chmod 777`, `shutdown`,
  `reboot`, `poweroff`, `kill -9`, `killall`, `history -c`, `curl … | sh`,
  `nc -e` …
* **Kein Root.** Es gibt keinen einzigen Aufruf mit erhöhten Rechten.
* **Keine Passwörter, keine SSH-Keys.** Weder gespeichert noch angezeigt noch kopiert.
* **Keine Shell für `START`.** `argv`-Listen, kein `shell=True`.
* **Kein verstecktes Ausführen.** Der Typ steht als Text auf dem Knopf.
* **Kein Zugriff** auf Wallpaper, Hintergrundbild, Auflösung, Cinnamon-Theme
  oder irgendeine andere Desktop-Einstellung.
* **Keine Schreibzugriffe** auf `~/.ssh`, `~/.config/mpd`, `~/.config/terminal-clipboard`.
* **Kein Neustart/Herunterfahren** im Deck.

Prüfen:

```bash
python3 daily-deck/app/daily_deck.py --selftest
```

---

## 14. Backup / Restore

### Automatisch

`install.sh` legt vor jeder Änderung ein Backup unter
`~/.config/daily-deck/backups/<Zeitstempel>/` an und protokolliert darin
`manifest.txt`, ob Command Deck, SSH-Config, MPD und Wallpaper vorhanden waren.

### Manuell

```bash
cd daily-deck
./backup.sh              # Daily Deck + Bestandsaufnahme (empfohlen)
./backup.sh --full       # zusätzlich Command Deck, ~/.ssh/config, ~/.config/mpd
./restore.sh --list      # alle Backups auflisten
./restore.sh <STAMP>     # ein Backup zurückspielen
./restore.sh <STAMP> --external   # auch Command Deck / SSH / MPD zurückspielen
```

* `restore.sh` sichert vor dem Zurückspielen erneut den aktuellen Stand
  (`pre-restore-<Zeitstempel>/`).
* Ohne `--external` werden **ausschließlich Daily-Deck-Dateien** angefasst.
* `--full` speichert `~/.ssh/config` mit – der Ordner wird auf `700` gesetzt.

### Geschützte Bestände (werden nie verändert)

| Pfad | Datei des Command Decks |
|---|---|
| `../command-deck/` | Projektordner des Command Decks |
| `~/.config/terminal-clipboard/` | dessen Befehlsliste + Status |
| `~/.config/autostart/command-deck.desktop` | dessen Autostart |
| `../command-deck/assets/theme.css` | dessen Theme (Daily Deck hat eine **Kopie**) |
| `~/.local/share/applications/command-deck.desktop` | dessen Menüeintrag |
| `~/.local/share/icons/…/command-deck.svg` | dessen Symbol |

---

## 15. Deinstallation

```bash
cd daily-deck
./uninstall.sh                # Programm, Autostart, Menü, Symbol entfernen
./uninstall.sh --purge        # zusätzlich ~/.config/daily-deck inkl. Backups
./uninstall.sh --keep-config  # Quellcode und Konfiguration behalten
```

Die Deinstallation

* entfernt **ausschließlich** Daily-Deck-Dateien
* deinstalliert **keine** Programme
* verändert `~/.ssh`, `~/.config/mpd` **nicht**
* verändert das bestehende Command Deck **nicht**
* verändert das Wallpaper **nicht**
* beendet nur den eigenen Prozess (über die eigene Lock-Datei, nicht per `pkill`)

Ein erneutes `./install.sh` stellt alles wieder her.

---

## 16. Wartung & Prüfwerkzeuge

| Befehl | Zweck |
|---|---|
| `python3 app/daily_deck.py --selftest` | Konfiguration, Terminal-Erkennung, Blockliste, Trennung zum Command Deck |
| `python3 app/daily_deck.py --print-config` | alle Einträge mit Typ und Verfügbarkeit |
| `python3 tools/audit.py` | zeigt zusätzlich das **exakte Terminal-Argv** je Eintrag |
| `python3 tools/uitest.py` | UI-Rauchtest ohne Nebenwirkungen (löst nur COPY aus) |
| `python3 tools/run.py --list` | alle Einträge auflisten |
| `python3 tools/run.py --show "Downloads"` | zeigt, was ein Klick tun würde |
| `python3 tools/run.py "Home"` | führt die Aktion wirklich aus |

`assets/theme.css` ist eine **Kopie** des Command-Deck-Themes (Original
bleibt unberührt); die einzige Erweiterung ist der Abschnitt
`DAILY DECK :: Aktionsknöpfe` mit den drei Knopf-Ausprägungen `START`,
`TERMINAL` und `COPY`. Symbol: `assets/daily-deck.svg` (gleiches Raster,
gleiche Randfarbe, gleicher Eckakzent wie das Command-Deck-Symbol).
Vorlage: `config/commands.json`.

---

## 17. Bekannte Einschränkungen

1. **„SSH verlassen“ kopiert `exit`.**
   Ein Tastendruck in ein fremdes Terminal erfordert eine Tastatur-Automation,
   für die kein Programm installiert ist (`xdotool` ist nicht vorhanden).
   Der Weg über die Zwischenablage ist zuverlässig und zerstörungsfrei.
   *Optional*, falls du das trotzdem willst:
   `sudo apt install xdotool` – dann könnte das Deck `exit` in das aktive
   Terminal tippen. Wird **nicht** automatisch gemacht.

2. **ncmpcpp / MPD fehlen** (Abschnitt 12). Einträge sind vorbereitet und werden
   automatisch aktiv, sobald die Pakete installiert sind.

3. **GTK3 malt in `listbox` einen undurchsichtigen Theme-Hintergrund**, der sich
   per CSS nicht abschalten lässt. Deshalb besteht die Liste – wie beim
   Command Deck – aus einem `Gtk.Box` mit `EventBox`-Zeilen statt aus einem
   `Gtk.ListBox`. Optik und Bedienung sind dadurch identisch.

4. **Der Hinweistext in der Suchzeile** ist ein eigenes Label im Overlay,
   weil GTK 3.24 den CSS-Selektor `::placeholder` nicht kennt – identisch
   zur Lösung im Command Deck.

5. **Arbeitsverzeichnis** eines `TERMINAL`-Eintrags wird mit
   `--working-directory` gesetzt (nur gnome-terminal). Bei Terminals, die das
   nicht können, wird auf `bash -lc "cd … && …"` zurückgefallen.

6. **Kein Mehrfachstart** – die Lock-Datei erlaubt nur eine Instanz.

7. **Transparenz** braucht einen Compositing-Fenster-Manager. Cinnamon/X11
   liefert das; unter Wayland wird der Hintergrund einfach deckend gezeichnet.

8. `ncmpcpp` wird in `~/Musik` gestartet, weil MPD üblicherweise relative
   Pfade nutzt. Beim Nachinstallieren ggf. anpassen.

---

## 18. Verzeichnisstruktur

```
daily-deck/
├── app/
│   └── daily_deck.py          Programm (Python 3 / GTK3)
├── assets/
│   ├── theme.css              Dark Purple / Neon Violet / Glass / Cyber
│   └── daily-deck.svg         Symbol
├── config/
│   └── commands.json          Vorlage für die Befehlsliste
├── tools/
│   ├── audit.py               Konfigurations-Audit
│   ├── uitest.py              UI-Rauchtest
│   └── run.py                 Eintrag per Namen ausführen
├── install.sh
├── uninstall.sh
├── backup.sh
├── restore.sh
└── README.md

~/.config/daily-deck/          Laufzeitdaten (nur vom Daily Deck benutzt)
~/.config/autostart/daily-deck.desktop
~/.local/share/applications/daily-deck.desktop
~/.local/share/icons/hicolor/scalable/apps/daily-deck.svg
```

Außerhalb dieses Bereichs wurde **nichts** angelegt.

---

◈ Daily Deck 1.0.0 – Dark Purple / Neon Violet / Glass / Cyber
