# Beitragen

Danke, dass du das SCD-Deck verbessern willst. Diese Seite sagt, wie.

---

## Grundregeln

1. **Der Prüflauf muss grün sein.** `./check.sh` vor jedem Commit.
2. **Keine neue Aktion ohne sichtbaren Typ.** Jeder Knopf trägt seinen Typ als
   Text. Kein versteckter Ausführungspfad, keine „klügeren" Kürzel.
3. **Kein Paket, keine Telemetrie, kein Netzwerk** aus dem Programm heraus.
4. **Niemals in fremde Bestände schreiben** — nicht in die Geschwister, nicht
   in Wallpaper, Panel, Dock, `~/.ssh`.
5. **Deutsch oder Englisch** — Code-Kommentare und Commit-Messages auf Deutsch
   sind in diesem Projekt etabliert, Codebezeichner englisch.

---

## Setup

```bash
git clone https://github.com/Grenoullie91/SCD-Deck.git
cd SCD-Deck
./check.sh
```

Es gibt **keine** Abhängigkeiten zu installieren. Kein `pip install`, kein
`npm install`, kein Build. Python 3 und GTK3 müssen vorhanden sein — auf Linux
Mint sind sie das.

Ein Deck testweise starten, ohne es zu installieren:

```bash
python3 daily-deck/app/daily_deck.py
```

Die Konfiguration kommt aus `~/.config/<deck>/commands.json`. Zum Ausprobieren
von Änderungen an der Vorlage `config/commands.json` im Repo:

```bash
XDG_CONFIG_HOME=/tmp/scd-test python3 daily-deck/app/daily_deck.py
```

So bleiben deine echten Einstellungen unberührt.

---

## Einen Befehl hinzufügen

Der Normalfall. In `config/commands.json` des jeweiligen Decks, in der
passenden Kategorie:

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

**Bei `READ` immer `argv` setzen.** `cmd` ist nur der Anzeigetext — der Code
liest bei `READ` ausschließlich `argv`. Ohne `argv` läuft der Befehl nicht.

Pipes sind bei `READ` nicht erlaubt. Stattdessen:

```json
{
  "name": "🗂 Große Dateien in /var/log",
  "description": "Dateien ab 1 MB, nur lesend",
  "cmd": "find /var/log -type f -size +1M -ls",
  "argv": ["find", "/var/log", "-type", "f", "-size", "+1M", "-ls"],
  "requires": ["find"],
  "timeout_s": 15
}
```

`filter_re` (Python-Regex) und `filter` (Literal) filtern die **Ausgabe** in
Python — dort, wo in der Shell eine Pipe stünde. Findet der Filter nichts,
zeigt das Deck die ungefilterte Ausgabe und den Hinweis *„Keine Zeile passt
zu …"*, statt still zu bleiben.

Prüfen, ob der neue Eintrag sauber ist:

```bash
python3 system-deck/app/system_deck.py --audit
```

Fehlt ein Werkzeug, meldet `--audit` es als `[FEHLT: <werkzeug>]`. Das ist kein
Fehler im Beitrag — es ist die Information, die der Nutzer zu Gesicht
bekommt.

---

## Vor `TERM` und `ADMIN` — die Leitplanken

Bevor du einen `TERM`- oder `ADMIN`-Befehl vorschlägst, beantworte drei Fragen:

**1. Warum ist das kein `READ`?**
`READ` ist immer vorzuziehen. Nur wenn der Befehl tatsächlich ein sichtbares
Terminal braucht — also interaktiv ist oder etwas verändert — ist `TERM`
zulässig.

**2. Steht er auf der `MUTATION`-Liste?**
```bash
grep -n "MUTATION = \[" -A 12 system-deck/app/system_deck.py
```
Wenn ja: **nein.** Die Liste ist nicht verhandelbar. `MUTATION` heißt
„darf dieses Programm nie tun", unabhängig davon, was ein Admin dürfte.

**3. Trifft er einen `CRITICAL_UNITS`-Dienst?**
```bash
grep -n "CRITICAL_UNITS = {" -A 8 system-deck/app/system_deck.py
```
Wenn ja: **nein.** Der Dienst wird geschützt, Punkt.

Wird `TERM` oder `ADMIN` trotzdem begründet beigetragen, gehört die
Begründung in die Beschreibung des Eintrags — sichtbar im Tooltip, nicht nur
im Commit.

---

## Design ändern

Die drei `theme.css` teilen einen Grundblock, der **zeichengleich** sein
muss. Nach jeder Änderung:

```bash
python3 system-deck/tools/theme-check.py
```

```
  1  Farbpalette (@define-color)      13 Farben  identisch
  2  Gemeinsamer Grundblock           252 Zeilen - vollstaendig identisch
  3  Deckeigene Erweiterungen         nur Werte, die im Grundblock vorkommen
```

Was das bedeutet:

* Änderungen an Variablen, `.deck`, `.header`, `.title`, `.glyph`, `.search`,
  `.row`, `.copy`, `.footer`, `.grip`, Menü und Tooltip: **in allen drei
  `theme.css` identisch** ändern.
* Deck-eigene Klassen (`.act`, `.catbtn`, `.check`, `.output`, …) dürfen nur
  im Abschnitt **nach** der eigenen Sektionsmarke liegen:
  * System Deck: ab `AKTIONSKNÖPFEN`
  * Daily Deck: ab `DAILY DECK :: Aktionsknöpfe`
  * Command Deck: keine eigenen Abschnitte
* Nur Farb- und Größenwerte verwenden, die im Grundblock bereits vorkommen.
  Keine neue Farbe, kein neuer Eckenradius, keine neue Schrift.

Das Ergebnis muss `GEMEINSAME DESIGNFAMILIE BESTÄTIGT` lauten.

---

## Einen Fehler melden

Ein guter Fehlerbericht enthält:

1. **Welches Deck?** (`command-deck`, `daily-deck`, `system-deck`)
2. **Was du erwartet hast** und **was passiert ist**
3. **Wie es sich reproduzieren lässt** — der genaue Klickpfad oder Befehl
4. **Ausgabe von `--selftest`** des betroffenen Decks
5. **Distribution und Version** (`lsb_release -a`)

`--selftest` ist die schnellste Eingrenzung: Wenn der Test fehlschlägt, ist die
Ursache fast immer direkt benannt.

---

## Pull Request

**Titel** — eine Zeile, beschreibt die Wirkung, nicht die Dateien.

```
System Deck: journalctl-Filter um -b 1 erweitern
```

**Beschreibung** — was, warum, wie geprüft:

```markdown
## Was
`LOGS → Fehlersuche` filtert bisher nur die aktuelle Sitzung. Mit `-b 1`
sind auch Abstürze des letzten Starts sichtbar.

## Warum
Nach einem Kernel-Neustart ist die interessanteste Information in der
vorherigen Sitzung, nicht in der laufenden.

## Prüfung
- ./check.sh → alle Prüfungen grün
- python3 system-deck/app/system_deck.py --audit → READ, journalctl vorhanden
- manuell: LOGS → Fehlersuche zeigt jetzt zwei boots
```

**Änderungen an der Befehlsliste** gehören in `config/commands.json` des
Decks — nicht in `~/.config/`. Die Laufzeitkonfiguration ist Sache des Nutzers
und wird nicht mit committed.

**Keine** Änderungen an `~/.config/`, an `install.sh`-Logik ohne zugehörigen
Test, oder an der `MUTATION`-/`CRITICAL_UNITS`-Liste ohne ausführliche
Begründung.

---

## Commit-Nachrichten

Kurz, deutsch, im Imperativ. Beschreibe die **Wirkung**, nicht die Datei:

```bash
git commit -m "System Deck: Log-Suche um Journal-Filter erweitert"
git commit -m "Command Deck: leere Kategorien werden ausgeblendet"
git commit -m "docs: Sicherheitsmodell um Suchbegrenzung ergänzt"
```

Typische Präfixe, wenn es hilft: `README:`, `docs:`, `theme:`, `tools:`.

Eine Zeile, kein Punkt am Ende. Der ausführliche „Warum" gehört in die
PR-Beschreibung, nicht in die Commit-Message.

---

## Dateien, die man nicht committed

Laut `.gitignore` und aus gutem Grund:

| Datei | Warum nicht |
|---|---|
| `~/.config/<deck>/commands.json` | **gehört dem Nutzer** — die Laufzeitkonfiguration |
| `state.json` | persönliche Fensterposition und -größe |
| `instance.lock` | Laufzeitzustand |
| `*.log` | lokales Ereignislog |
| `backups/` | lokale Sicherungen, evtl. mit sensiblen Pfaden |
| `*.desktop` | vom Installer erzeugt, pro System verschieden |
| `__pycache__/` | Bytecode-Cache |

`config/commands.json` im Repo **ist** die Vorlage und gehört committed.
Sie ist die dokumentierte, kommentierte Ausgangslage — ohne persönliche
Einträge, ohne Suchbegriffe, ohne lokale Pfade.

---

## Architecture in einem Satz

Ein Deck ist ein rahmenloses GTK3-DOCK-Fenster, das `config/commands.json`
liest, Befehle in einem Thread-Pool ausführt und Ergebnisse über `GLib.idle_add`
zurückgibt. Mehr ist es nicht — und das ist gewollt, denn jedes Feature, das
hier nicht steht, wäre ein Feature, das man abschirmen müsste.

Ausführlich: **[ARCHITEKTUR.md](ARCHITEKTUR.md)**.
Sicherheitsregeln: **[SICHERHEIT.md](SICHERHEIT.md)**.

---

*◈ Teil des [SCD-Deck](../README.md)*
