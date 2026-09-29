# Sicherheitsmodell

Die verbindlichen Zusagen des SCD-Deck-Systems. Jede Aussage auf dieser Seite
ist im Code nachprüfbar — die Prüfwege stehen jeweils dabei.

> **Kurzfassung in einem Satz:** Die Decks kopieren, öffnen und lesen.
> Sie führen Befehle nie selbst aus, sie kennen kein Passwortfeld,
> und sie schreiben nie in fremde Bestände.

---

## 1. Die Grundregel

Ein klassisches Terminal-Widget nimmt eine Befehlszeile, macht eine Shell
daraus und führt sie aus. Das ist bequem und genau das Problem: **eine
absichtliche Zeile und ein Tippfehler sehen gleich aus.**

SCD-Deck trennt das. Jeder Knopf trägt seinen Typ als **Text**, und jeder Typ
hat genau eine Bedeutung:

| Typ | Was passiert | Was nicht passiert |
|---|---|---|
| **READ** | Argumentliste an `subprocess`, ohne Shell, mit Zeitlimit | kein `sudo`, kein Schreiben, kein Netzwerk |
| **COPY** | `Gtk.Clipboard.set_text()` | **nichts wird ausgeführt** — konstruktionsbedingt |
| **START** | `Popen(argv)` für ein Programm | keine Shell, kein Befehl |
| **TERM** | sichtbares Terminal öffnet sich | das Deck führt nichts selbst aus |
| **ADMIN** | Bestätigungsdialog, dann wie `TERM` | das Deck führt nie `sudo` aus |

Es gibt **keinen versteckten Ausführungspfad**. Was auf dem Knopf steht, ist
was passiert.

---

## 2. Warum `READ` keine Shell bekommt

Der entscheidende Code:

```python
argv = [self._subst(str(a), token, value) for a in item["argv"]]
argv[0] = os.path.expanduser(argv[0])
...
proc = subprocess.run(
    argv,                       # <- Argumentliste, nicht ein String
    shell=False,                 # <- ausdrücklich
    stdin=subprocess.DEVNULL,    # <- die Eingabe wartet auf niemanden
    capture_output=True,
    text=True,
    timeout=item.get("timeout_s", 10),
    start_new_session=True,      # <- eigene Prozessgruppe
)
```

Daraus folgt mechanisch:

* `cmd: "du -sh /var/log | head"` kann **nicht** als `READ` laufen. Pipes gibt
  es dort nicht. Wer filtern will, nutzt `filter` / `filter_re` — das ist ein
  Python-Ausdruck im Prozess, nicht in einer Shell.
* Ein Eintrag kann sich nicht in einen anderen hineinschleichen. `argv` ist
  eine Liste, keine zu interpretierende Zeichenkette.

### `argv[0]` ist eingeschränkt

```python
FORBIDDEN_ARGV0 = {
    "sh", "bash", "zsh", "ksh", "dash", "csh", "tcsh", "fish", "busybox",
    "env", "xargs", "nohup", "setsid", "eval", "exec", "su", "sudo", "doas",
    "pkexec", "gdb", "strace", "perl", "python", "python3", "ruby", "php",
    "nc", "ncat", "socat", "telnet", "awk",
}
SAFE_ARGV0_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")
FIND_DANGER = {"-exec", "-execdir", "-delete", "-ok", "-okdir"}
```

Shellen, Rechte-Eskalation, Interpreter und Netzwerkwerkzeuge sind als
`argv[0]` verboten. `find` darf nur lesen — `-exec`, `-execdir`, `-delete`,
`-ok`, `-okdir` werden abgewiesen.

---

## 3. Die zwei Sperrlisten des System Decks

### `BLOCKED` — destruktiv

Gilt für alles, was das Deck anfasst **oder** in ein Terminal legt.

```
rm -rf            mkfs             fdisk            parted
dd                shred            :(){ :|:& };:    sudo
su -              passwd           useradd          userdel
usermod           chown            chmod 777        shutdown
reboot            poweroff          halt             init 0
kill -9           killall          mv /…            > /dev/sd…
curl …| sh        wget …| sh       nc -e            history -c
apt purge         apt install      apt upgrade      ufw allow
iptables -F       truncate         wipefs           mkswap
```

### `MUTATION` — verändernd

**Diese Liste lässt sich durch kein Flag aufheben.** Auch `sudo: true` nicht.

```
rm  dd  shred  mkfs  wipefs  mkswap  truncate  fdisk  parted
apt install|purge|remove|autoremove|upgrade|dist-upgrade|clean
ufw allow|deny|delete|reset|enable|disable|reload|insert
iptables -A|-I|-F|-X|…
journalctl --vacuum      logrotate      systemctl mask|unmask|enable|disable|preset
userdel  groupdel  killall  kill -9
shutdown  reboot  poweroff  halt
git push|reset|clean|checkout        docker rm|rmi|system prune
```

Der Unterschied: `BLOCKED` ist die Sicht des Nutzers — was darf ich anklicken?
`MUTATION` ist die Sicht des Systems — was darf dieses Programm **jemals**
anfassen? `apt clean` steht in beiden Listen: anklicken wäre sinnlos, der
gesperrte Status erklärt warum.

Prüfen:

```bash
python3 system-deck/app/system_deck.py --selftest
```

---

## 4. Geschützte Systemdienste

Auch wenn ein `ADMIN`-Eintrag es erlauben würde, diese Dienste fasst das Deck
**nie** an:

```python
CRITICAL_UNITS = {
    "ssh", "sshd", "networking", "networkmanager", "network-manager",
    "display-manager", "cups", "cups-browsed", "cron", "crond",
    "dbus", "polkit", "accounts-daemon", "upower", "packagekit",
    "modemmanager", "bluetooth", "avahi-daemon", "apparmor",
    "systemd-logind", "systemd-journald", "systemd-udevd",
    "systemd-resolved", "getty@", "user@", "snapd", "fail2ban",
}
```

Der Dienstname wird aus dem Befehl extrahiert und **vor** dem Dialog geprüft.
Ein `ADMIN`-Befehl, der auf `NetworkManager` zielt, landet in einem
gesperrten Zustand — der Knopf ist rot, es passiert nichts.

Warum diese Liste: `NetworkManager` oder `display-manager` anhalten heißt
Schwarzer Bildschirm ohne Rückweg. `polkit`, `dbus` und `accounts-daemon`
sind die Grundlage jeder Rechteabfrage — wer die anfasst, sperrt sich selbst
aus. `systemd-logind` ist die Session selbst.

---

## 5. Das `sudo`-Versprechen

> **Das Deck führt nie `sudo` aus. Es gibt kein Passwortfeld.**

`sudo: true` existiert, aber:

1. Nur bei `TYPE=TERM` erlaubt.
2. Der Befehl landet in einem **sichtbaren Terminalfenster**.
3. Dort wird er normal bestätigt — das Deck hat den String nur vorbelegt.
4. Das Deck speichert kein Passwort, hat kein Feld dafür, kennt keinen Keyring.

Der Effekt ist, dass die gefährlichste Aktion des Systems **vor dem Nutzer
passiert**, nicht im Deck. Wer `sudo systemctl restart ssh` klickt, sieht ein
Terminal, in dem er tippen muss.

`ADMIN` verhält sich genauso, nur mit einem zusätzlichen Dialog davor, der den
Befehl **wörtlich** zeigt:

```
  Diese Aktion verändert das System.

    sudo systemctl restart cups

  Terminal: gnome-terminal
  Es wird kein Passwort gespeichert und kein Passwortfeld angezeigt.
                                    [ Abbrechen ]  [ Im Terminal ausführen ]
```

---

## 6. Suchbegriffe werden geprüft

Einträge mit `prompt` fragen nach einem Suchbegriff — Prozessname, Dienstname,
Port, Journal-Begriff, Sensor. Dieser Begriff landet in einer
Argumentliste. Deshalb:

```python
if len(value) > 64 or not re.match(r"^[A-Za-z0-9_.@:+-]+$", value):
    → ablehnen
```

Höchstens 64 Zeichen aus `[A-Za-z0-9_.@:+-]`. Der Begriff ersetzt **genau ein**
Argument. Keine Shell, kein Verkettungszeichen, kein Unterbefehl — man kann
mit dem Suchfeld keinen Befehl einschleusen, weil der Platz für genau ein
Wort ohne Leerzeichen ist.

---

## 7. Das Command Deck: maschineller Beweis

Das Command Deck macht ein Versprechen, das man nicht glauben muss — es
**beweist** es. `--audit` parst die eigene Quelldatei mit `ast` und sucht nach
 jedem denkbaren Ausführungsweg:

```
  OK  0 verbotene Aufrufe (system/popen/exec*/fork/pty/eval/exec/shell=True)
  OK  subprocess nur in: _on_edit, raise_existing
```

Geprüft wird unter anderem:

* Aufrufe von `os.system`, `os.popen`, `subprocess.call/run/Popen/check_output`,
  `eval`, `exec`, `os.fork`, `pty.*`
* jeder Aufruf mit `shell=True`
* jede Verwendung von `__import__` oder `importlib` zur Laufzeit
* ob die gefundenen `subprocess`-Stellen überhaupt Befehle ausführen können
  (die zwei genannten Orte schreiben nur `state.json` bzw. beenden eine
  Instanz)

```bash
python3 command-deck/app/command_deck.py --audit
```

Der Selbsttest prüft zusätzlich, dass **kein** Konfigurationseintrag eine
Verkettung enthält (`;`, `&&`, `||`, `|` am Zeilenende) und dass alle
93 Befehle eindeutig sind.

---

## 8. Bestandsschutz: die anderen Decks

Die drei Decks teilen sich keinen Code. Ihre Installationsskripte lesen die
Bestände der Geschwister — **ausschließlich lesend**:

```bash
COMMAND_DECK_DIR="$REPO_DIR/command-deck"
[ -d "$COMMAND_DECK_DIR" ] || COMMAND_DECK_DIR="$HOME/TerminalCommandWidget"
```

Jedes `install.sh` protokolliert vor der ersten Änderung, was vorhanden ist:

```
~/.config/system-deck/backups/<Zeitstempel>/manifest.txt
  command_deck_project_exists=yes
  command_deck_state_exists=yes
  daily_deck_project_exists=yes
  cairo_dock_exists=yes
  wallpaper=unveraendert
  panel=unveraendert
```

Und `uninstall.sh` bestätigt zum Schluss, dass alles noch da ist.

Unberührt bleiben in **allen** Decken: Command Deck, Daily Deck, Wallpaper,
Cinnamon-Schemata, Cairo-Dock, Panel, `~/.ssh`, MPD-/ncmpcpp-Konfiguration.

---

## 9. Keine Passwörter, keine Telemetrie, kein Netzwerk

| | |
|---|---|
| Passwortfeld | **nicht vorhanden** — in keinem der drei Programme |
| Keyring | nicht angesprochen |
| `~/.ssh` | Daily Deck **liest** `config` für die Host-Liste, schreibt nie |
| Telemetrie | keine |
| Analytics | keine |
| Netzwerkzugriff aus dem Programm | keiner — es wird nichts kontaktiert |
| Abhängigkeiten | nur Python-Standardbibliothek + `python3-gi` / GTK3 |

Der Quick System Check liest `/proc`, `/sys` und `statvfs`. `ping` wird
ausschließlich als `READ`-Befehl **auf Anfrage** ausgeführt, nie im Hintergrund,
nie automatisch.

### Das interne Log

Falls überhaupt, gibt es ein **begrenztes** Ereignislog:

```
~/.config/system-deck/system-deck.log
```

256 KB, eine Rotation, nur Ereignisnamen wie `READ Systemübersicht`.
**Keine** Befehlsausgaben, keine Passwörter, keine Keys, keine Tokens.
Steuerung über `SYSTEM_DECK_DEBUG`.

---

## 10. Änderungen, die nichts kosten dürfen

Befehle, die das System verändern, sind im Deck **COPY**, nicht `ADMIN` oder
`TERM` — auch wenn man sie als Administrator ausführen dürfte:

```
apt update                              -> COPY
apt upgrade                             -> COPY
apt clean                               -> COPY
journalctl --vacuum-time=7d            -> COPY
ufw allow <port>                        -> gesperrt
```

Der Grund ist nicht Misstrauen, sondern Einheitlichkeit: **ein Klick im Deck
darf nie den Zustand des Systems ändern.** Wer etwas ändern will, kopiert es
und tippt es ins Terminal. Das ist ein Schritt mehr — genau das ist der Sinn.

---

## 11. Selbst prüfen

```bash
# Gesamter Prüflauf über alle drei Decks
./check.sh

# Nur Sicherheits- und Konfigurationsregeln
python3 command-deck/app/command_deck.py --selftest
python3 daily-deck/app/daily_deck.py --selftest
python3 system-deck/app/system_deck.py --selftest

# Maschineller Beweis für das Command Deck
python3 command-deck/app/command_deck.py --audit

# Verfügbarkeit und Typ jedes einzelnen Befehls
python3 system-deck/app/system_deck.py --audit
python3 daily-deck/tools/audit.py
```

---

## 12. Zusammenfassung der Zusagen

1. **Lesen ist der Standard.** 93 der 121 System-Deck-Einträge sind `READ` —
   ohne Root, ohne Shell, ohne Schreibzugriff.
2. **Keine Shell beim Ausführen.** `subprocess` mit Argumentliste,
   `stdin` geschlossen, eigene Prozessgruppe, 10 s Limit, Ausgabe gekürzt.
3. **Zwei Sperrlisten.** `BLOCKED` für den Nutzer, `MUTATION` für das System —
   und `MUTATION` ist durch kein Flag aufhebbar.
4. **Kritische Dienste geschützt.** 27 Units, nie per `ADMIN` veränderbar.
5. **`sudo` nur sichtbar.** Nur bei `TERM`, mit Bestätigungsdialog, ohne
   Passwortfeld.
6. **Suchbegriffe geprüft.** 64 Zeichen aus einem zeichenarmen Alphabet,
   genau ein Argument.
7. **Veränderungen nur als `COPY`.** `apt`, `journalctl --vacuum`, `ufw` —
   zum bewussten Einfügen, nie als Klickaktion.
8. **Keine Firewall-Regeländerungen.** UFW liefert nur Status und Regelliste.
9. **Kein Bestandsschutz fehlt.** Geschwister, Wallpaper, Panel, Dock, `~/.ssh`
   werden nur gelesen.
10. **Lokal.** Keine Telemetrie, keine Cloud, keine Netzwerkzugriffe aus dem
    Programm.
11. **Begrenztes Log.** 256 KB, nur Ereignisnamen, keine Inhalte.
12. **Nachprüfbar.** Jede Zusage hat einen Befehl, der sie belegt.

---

*◈ Teil des [SCD-Deck](../README.md) — Command Deck · Daily Deck · System Deck*
