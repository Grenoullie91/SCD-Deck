# Changelog

Alle nennenswerten Änderungen am SCD-Deck-System.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/).

---

## [1.0.0] — 2026-09-29

Erste gemeinsame Veröffentlichung der drei Decks in **einem** Repository.

### Hinzugefügt

* **`command-deck/`** — Command Deck, 8 Kategorien, 93 Befehle.
  Kopiert Befehle, führt sie nie aus. `--audit` beweist per AST-Analyse, dass
  kein Ausführungspfad existiert.
* **`daily-deck/`** — Daily Deck, 6 Kategorien, 36 Befehle plus dynamische
  SSH-Einträge aus `~/.ssh/config`. `START` / `TERMINAL` / `COPY`.
* **`system-deck/`** — System Deck, 17 Kategorien, 121 Befehle
  (93 `READ` · 18 `TERM` · 7 `COPY` · 3 `ADMIN`) plus Quick System Check
  mit neun live ermittelten Werten.
* **`check.sh`** — ein Prüflauf für alle drei Decks (Selbsttests, Audits,
  Theme-Abgleich).
* **`docs/ARCHITEKTUR.md`** — Fenster, Threading, Datenfluss, Theme-Familie.
* **`docs/SICHERHEIT.md`** — das Sicherheitsmodell mit Nachprüfwegen.
* **`docs/BEITRAGEN.md`** — Beitragsregeln und Prüfwege.
* **`LICENSE`** — MIT.
* **`.gitignore`** — trennt Repo von Laufzeit-Zustand.

### Geändert

* Die Schwestern-Erkennung in allen Installations-, Restore-, Uninstall- und
  Backup-Skripten sucht den Nachbarordner **im Repository** zuerst und fällt
  auf die bisherigen Pfade `~/TerminalCommandWidget` und `~/DailyDeck` zurück.
  Vorher funktionierte der Theme-Abgleich nur im Einzelverzeichnis-Setup.
* `system-deck/tools/theme-check.py` sucht die Geschwister über dieselbe
  Kette statt über fest verdrahtete `$HOME`-Pfade.
* `daily-deck/backup.sh --full` legt das Command Deck unter dem Namen
  `command-deck` ab (vorher: `TerminalCommandWidget`).
  `daily-deck/restore.sh` liest **beide** Namen, ältere Backups bleiben
  wiederherstellbar.
* Alle Pfade in den drei `README.md` sind jetzt relativ zum Repository-Root.
* **Anonymisierung für das öffentliche Repository.** Es bleibt nur
  funktionaler Code, der über Platzhalter individuell angepasst wird:
  * Server-IP, Benutzername, Projekt-Host und SSH-Alias sind durch `<IP>`,
    `<USER>`, `<HOST>` und `<SSH-ALIAS>` ersetzt.
  * `command-deck/config/commands.json` ist eine **generische Vorlage**:
    projektbezogene Befehle sind durch allgemeine Formen mit Platzhaltern
    ersetzt. Die Kategorie der Skriptsprache trägt einen neutralen Namen.
  * Die Auswertung der Shell-Historie im Command-Deck-README (Zeilenzahl,
    Aufrufhäufigkeiten, abgeleitetes Arbeitsprofil) ist durch eine
    Beschreibung der Vorlage und ihrer Platzhalter ersetzt.
  * Die Systeminventur im Daily-Deck-README (exakte Distribution, Desktop-
    und Terminal-Version, installierte Programme, Installationsstatus) ist
    durch eine Beschreibung der Laufzeiterkennung ersetzt.
  * Zwei `READ`-Einträge des System Decks, die ein festes Home-Verzeichnis im
    `argv` hatten, nutzen jetzt den `{home}`-Platzhalter.
  * Start-Favoriten und Seed-Konfiguration enthalten keine projektbezogenen
    Pfade mehr.
  * Der Programmcode, die Themes, die Symbole und alle Shell-Skripte waren
    bereits frei von personenbezogenen Inhalten — dort wurde nichts geändert.

### Sicherheit

* Unverändert am Code der drei Decks. Diese Version reorganisiert nur —
  jede Datei der Decks wurde byteweise übernommen, mit Ausnahme der oben
  genannten Schwestern-Pfadauflösung in den Shell-Skripten und
  `theme-check.py`.

### Bekannte Einschränkungen

* Fehlende Systemwerkzeuge (`nvidia-smi`, `pavucontrol`, `nvme`, `iostat`,
  `powertop`, `gnome-system-report`) melden ihre Einträge als
  `NICHT VERFÜGBAR`. Kein Deck installiert je ein Paket.
* Das System Deck ist auf X11/Cinnamon ausgelegt (`_NET_WM_TYPE_DOCK`).
  Unter Wayland verhalten sich DOCK-Fenfen je nach Compositor anders.

---

*◈ SCD-DECK — Command Deck = Developer Control · Daily Deck = Everyday Control · System Deck = System Control*
