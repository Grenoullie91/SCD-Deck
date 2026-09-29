# Architektur

Wie die drei Decks zusammenhängen und warum sie so gebaut sind, wie sie gebaut sind.

---

## 1. Die Grundentscheidung: ein Fenster, kein Dienst

Keines der drei Programme ist ein Systemdienst, kein Hintergrund-Daemon, kein
Autostart-Addon mit Socket. Jedes ist ein **GTK3-Fenster** mit der Eigenschaft
`_NET_WM_TYPE_DOCK`:

```python
self.set_type_hint(Gdk.WindowTypeHint.DOCK)
self.set_skip_taskbar_hint(True)
self.set_skip_pager_hint(True)
```

Das bedeutet:

* Das Deck taucht **nicht** in der Fensterleiste auf.
* `Alt+Tab` überspringt es.
* Es stirbt mit der Sitzung — kein Aufräumen, kein Zombie-Prozess, keine
  Leiste, die nach dem Abmelden noch im Hintergrund läuft.
* Ein zweiter Start erkennt die laufende Instanz über `instance.lock` und
  hebt sie nur an (`--raise`).

Position, Größe, Transparenz und `always_on_top` liegen in
`state.json` im jeweiligen `~/.config/<deck>/` und werden beim Beenden
geschrieben, beim Starten gelesen.

---

## 2. Warum drei Deck-Ordner und nicht ein Deck

Ein Deck mit 250 Befehlen in 17 Kategorien ist unbenutzbar. Man sucht
Dinge, die **zu einem Zeitpunkt wichtig sind**, und diese Dinge fallen in
drei klar getrennte Bereiche:

| | Command Deck | Daily Deck | System Deck |
|---|---|---|---|
| Frage | *„Wie war der Befehl nochmal?"* | *„Wo ist das Programm?"* | *„Ist mein System ok?"* |
| Nutzer | Entwickler | jeder | Administrator |
| Aktion | Kopieren | Öffnen/Verbinden | Lesen |
| Risiko | keines | gering | keines |

Die Trennung ist inhaltlich, nicht kosmetisch. Sie hat zwei praktische Folgen:

1. **Ein Fehler in einem Deck betrifft die anderen nicht.** Die drei Apps teilen
   sich keinen Code — sie teilen sich ein *Design*.
2. **Die Sicherheitsregeln bleiben einfach.** Das System Deck hat die größte
   Blockliste, das Command Deck die strengste Zusage
   (führt nie etwas aus). Beides ist jeweils in genau einer Datei prüfbar.

---

## 3. Datenfluss

```
config/commands.json          (im Repo, Vorlage)
        │
        │  install.sh --force  /  erste Installation
        ▼
~/.config/<deck>/commands.json   (Laufzeit, vom Nutzer bearbeitbar)
        │
        │  Store.load()  beim Start,  F5 lädt neu
        ▼
      Items                 (Flache Liste: name, description, type, cmd, argv, …)
        │
        ├─ READ  ──► subprocess.run(argv, shell=False, stdin=DEVNULL, timeout=10s)
        │                    └─► gekürzt auf 500 Zeilen / 90 KB ──► Ausgabefenster
        │
        ├─ COPY  ──► Gtk.Clipboard.set_text(...)        (nichts wird ausgeführt)
        │
        ├─ START ──► subprocess.Popen(argv, shell=False)   (nur Daily Deck)
        │
        ├─ TERM  ──► subprocess.Popen([<terminal>, …])    (sichtbares Fenster)
        │
        └─ ADMIN ──► Bestätigungsdialog ──► wie TERM
```

Der wichtigste Punkt in dieser Grafik: **`READ` nimmt `argv`, niemals `cmd`.**
`cmd` ist Anzeigetext. `argv` ist eine Argumentliste. Es gibt keinen Pfad,
auf dem ein `READ` eine Shell bekommt.

---

## 4. Threading

GTK ist nicht threadsicher. Jedes Deck löst das gleich:

```
UI-Thread          Runner-Pool (2 Arbeiter)
──────────         ─────────────────────
submit(token, fn) ──► Queue
                                  fn()              # subprocess, sensoren, systemctl
                                  ↓
GLib.idle_add(...) ◄──────── result
                            └─ prüft sid: ältere Ergebnisse
                              werden verworfen
```

Drei Konsequenzen, die überall gleich umgesetzt sind:

* **Der UI-Thread blockiert nie.** `systemctl --failed` darf fünf Sekunden
  brauchen — das Fenster bleibt bedienbar.
* **Ergebnisse können veralten.** Jeder Auftrag bekommt eine `sid`. Kommt ein
  Ergebnis mit `sid <= gesehen` an, wird es verworfen. Sonst überschreibt
  eine langsame alte Abfrage eine schnelle neue.
* **Buttons werden gesperrt, nicht die Oberfläche.** Während ein Befehl läuft,
  wird genau dieser Knopf inaktiv — der Rest des Decks bleibt nutzbar.

---

## 5. Das gemeinsame Theme

Jedes Deck hat eine **eigene Kopie** von `assets/theme.css`. Das ist Absicht:

> Ein Deck, das die/theme-Datei eines anderen Decks zur Laufzeit liest,
> bricht, sobald dieses andere Deck gelöscht, aktualisiert oder aus einem
> anderen Repo geklont wird.

Stattdessen hält `system-deck/tools/theme-check.py` die drei Kopien in Sync und
beweist maschinell, dass der gemeinsame Grundblock identisch ist:

```
  1  Farbpalette (@define-color)      13 Farben  identisch
  2  Gemeinsamer Grundblock           252 Zeilen - vollstaendig identisch
  3  Deckeigene Erweiterungen         nur Werte, die im Grundblock vorkommen
```

Erlaubt ist ausschließlich der Abschnitt **nach** der eigenen Sektion-Marke
(bei System Deck `AKTIONSKNÖPFEN`, bei Daily Deck `DAILY DECK :: Aktionsknöpfe`).
Alles davor — Variablen, `.deck`, `.header`, `.title`, `.glyph`, `.search`,
`.row`, `.copy`, `.footer`, `.grip`, Menü, Tooltip — muss zeichengleich sein.

### Farbpalette

| Rolle | Wert | Verwendung |
|---|---|---|
| `bg` | `#1A0B2E` | Fensterhintergrund |
| `surface` | `#241442` | Zeilen, Kopfzeile |
| `accent` | `#7C3AED` | Rahmen, Fokus, Hauptakzent |
| `accent-bright` | `#A855F7` | Hover, aktive Kategorie |
| `text` | `#E9D5FF` | Primärtext |
| `text-dim` | `#9B7BB8` | Sekundärtext |
| `ok` | `#4ADE80` | grün |
| `warn` | `#FBBF24` | gelb |
| `err` | `#F87171` | rot |
| `info` | `#C084FC` | violett |

Die vier Statusfarben liegen **bewusst außerhalb** der Purple-Familie. Ein
lila Warnsymbol ist keins. `OK` muss in drei Metern Entfernung sofort als
„alles gut" lesbar sein, nicht als „irgendwas mit dem Theme".

---

## 6. Fensteranatomie

Identisch in allen drei Decks:

```
┌──────────────────────────────────────┐
│ ◈ DECKNAME                    ● PIN │   header   (ziehbar)
├──────────────────────────────────────┤
│ [Kopfzeile der aktuellen Sektion]    │   section
│ [Suchfeld ❯                    ✕]   │   search
│ [Kategorie][Kategorie][Kategorie]    │   cats
├──────────────────────────────────────┤
│ Zeile      Beschreibung   [A][B]     │   row
│ Zeile      Beschreibung   [A][B]     │
├──────────────────────────────────────┤
│ AUSGABE · TYP · TITEL          ⧉ ✕   │   output  (klappt auf)
│ …                                    │
├──────────────────────────────────────┤
│ 121 Befehle · 17 Kategorien  ▲ PIN ▪  │   footer
└──────────────────────────────────────┘
                                   ▪    ← grip (ziehbar, ändert Größe)
```

Der **Grip** unten rechts ist ein eigenes Zeichen-Fenster mit
`set_has_frame(False)`, das beim Ziehen die Größe des Hauptfensters mitführt.
Das ist der einzige Weg, wie ein rahmenloses Fenster sinnvoll skalierbar bleibt.

---

## 7. Erkennung statt Festverdrahtung

Alles, was sich zur Laufzeit ermitteln lässt, wird ermittelt:

| Ermittelt | Wie | Fallback |
|---|---|---|
| Standard-Terminal | `gsettings get org.cinnamon.desktop.default-applications.terminal exec` | `gnome-terminal` |
| SSH-Hosts | `~/.ssh/config` lesen, `Host`-Aliasse sammeln | keine |
| XDG-Ordner | deutsche Benennung über `user-dirs.dirs` | englische Namen |
| Fehlende Werkzeuge | `shutil.which()` beim Laden | `NICHT VERFÜGBAR` |
| Bildschirmposition | `Gdk.Monitor.get_workarea()` des primären Monitors | unten rechts, 14 px Rand |
| Audio-Standard | `pactl get-default-sink` | — |

`detect_terminal()` ist das deutlichste Beispiel: das Daily Deck verdrahtet
**kein** Terminal. Wer `x-terminal-emulator` benutzt, bekommt dieses.

---

## 8. Abwärtskompatibilität der Skripte

Alle Installations-, Restore-, Uninstall- und Backup-Skripte bestimmen ihren
eigenen Ort:

```bash
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

```python
HERE  = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
```

Daraus folgt: **das Repo kann überall liegen.** Ein Checkout nach `/opt/scd`,
`~/Dokumente/SCD-Deck` oder in einen Docker-Build funktioniert ohne Anpassung.

### Schwestern-Erkennung

Die Skripte referenzieren die Geschwister über eine kleine Fallback-Kette:

```bash
REPO_DIR="$(dirname "$PROJECT_DIR")"
COMMAND_DECK_DIR="$REPO_DIR/command-deck"
[ -d "$COMMAND_DECK_DIR" ] || COMMAND_DECK_DIR="$HOME/TerminalCommandWidget"
```

Im **Monorepo** wird also der Nachbarordner geprüft (für
`theme-check.py`, Bestandsaufnahmen), im **Legacy-Setup** der alte Pfad.
Diese Referenzen sind **ausschließlich lesend** — kein Skript schreibt je in
ein Schwester-Deck.

---

## 9. Fehlerbehandlung

* **Ein fehlendes Werkzeug ist kein Fehler.** Der Eintrag wird ausgegraut, der
  Knopf heißt `NICHT VERFÜGBAR`, der Tooltip nennt das Paket. Der Code läuft
  normal weiter — ohne das Werkzeug.
* **Ein Zeitlimit ist Pflicht.** Jeder `READ` hat 10 s (oder `timeout_s` aus
  der Konfiguration). Danach wird die Prozessgruppe beendet, nicht nur der
  Prozess.
* **Ein Fehler wird angezeigt, nicht geschluckt.** `stderr` landet im
  Ausgabefenster, zusammen mit dem Rückgabewert.
* **Ungültige JSON-Konfiguration startet das Deck nicht.** Die alte Datei
  bleibt liegen, die Meldung nennt den Parsefehler mit Zeilennummer.

---

*◈ Teil des [SCD-Deck](../README.md) — Command Deck · Daily Deck · System Deck*
