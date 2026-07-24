# Code-Review Fortschritt — tia-linter

## Runde 1 (ohne Pruefpunkte.md/Programm-Anforderungen.md — waren noch nicht vorhanden)

- [x] Anforderungs-MDs gelesen (Openness-API-Referenz-fuer-Linter.md, Openness-API-V21-Aenderungen.md)
- [x] Projektstruktur erfasst
- [x] README.md / config/default.yaml abgeglichen
- [x] models.py, connector.py, config_loader/, my_logger/ geprüft — alle OK
- [x] checks/base.py + registry.py geprüft — OK (40 Config-Einträge für 35 Prüfpunkte, Splits sauber dokumentiert)
- [x] checks/_tia_helpers.py, comments.py, naming.py, structure.py, hardware.py, metadata.py, libraries.py geprüft — OK, sehr sorgfältig dokumentiert
- [x] project_texts.py geprüft — ⚠️ Performance-Finding (siehe Bericht unten)
- [x] reporter.py, settings.py, runner.py, main.py, gui.py geprüft — OK
- [x] tests/ geprüft — nur test_models.py (7/7 grün)
- [x] Laufzeittests: py_compile OK, pytest 7/7 grün, config lädt (40 CheckDefinitions), simulate_lint_run()+PdfReporter End-to-End getestet (PDF erzeugt), GUI-Smoketest OK
- [x] Abschlussbericht Runde 1 an User übergeben

## Runde 2 (Nachtrag nach Bereitstellung von Pruefpunkte.md, Programm-Anforderungen.md, Claude-Code-Prompt-Session1.md, Session1-Fortschritt.md)

- [x] Pruefpunkte.md gelesen — enthält die kanonische Liste aller 35 Prüfpunkte (inkl. 11b/17b/18b/18c) mit Soll-Schweregrad pro Punkt
- [x] Programm-Anforderungen.md gelesen — enthält GUI-/Report-/Config-Anforderungen sowie technisches Konzept
- [x] Claude-Code-Prompt-Session1.md gelesen — ursprünglicher Bau-Auftrag an die Vorsitzung
- [x] Session1-Fortschritt.md gelesen — Fortschrittsnotizen der Vorsitzung, inkl. eigener "Offene Punkte"-Liste
- [x] Prüfpunkt-Zähler gegen Pruefpunkte.md verifiziert: 39 Tabellenzeilen (inkl. 17b), davon 17b explizit "(spätere Version)" → 38 zu implementierende Punkte; Config/Registry haben 40 Einträge = 38 − 2 (Zeilen 6 und 7, je einfach gezählt) + 4 (deren a/b-Splits: plc_tag_eingaenge/ausgaenge, fb_prefix/fc_prefix). **Rechnet exakt auf — kein Fehler, jetzt gegen Primärquelle bestätigt statt nur vermutet.**
- [x] Prüfpunkt 17b (Hardware-Typ passt zum Tag-Datentyp) — laut Pruefpunkte.md ausdrücklich "(spätere Version)" — zu Recht nicht implementiert, **kein Gap**.
- [x] Severity-Vorgaben pro Prüfpunkt aus Pruefpunkte.md gegen config/default.yaml + Check-Code geprüft:
  - Alle Punkte mit einheitlichem Soll-Schweregrad (z.B. 5/6/7 ❌, 8/9 ⚠️, 24 ❌, 27 ❌ ...) stimmen mit default.yaml überein.
  - Prüfpunkt 21 (Kompilierfehler, Soll: ❌/⚠️ gemischt) — korrekt per-Message differenziert in `metadata.py` (`ErrorCount > 0` → ERROR, sonst WARNING). ✅
  - **Prüfpunkt 18c (Zertifikat, Soll lt. Pruefpunkte.md: ❌ Fehler bei fehlendem Zertifikat / ⚠️ Warnung bei bald ablaufendem) — NICHT korrekt umgesetzt.** `ZertifikatCheck` in `hardware.py` übergibt in allen drei Fällen (kein Zertifikat / abgelaufen / läuft bald ab) keinen expliziten `status`, sondern nutzt einheitlich den konfigurierten Standard-Schweregrad (`severity: warning` in default.yaml) — dadurch wird ein fehlendes oder bereits abgelaufenes Zertifikat fälschlich nur als Warnung statt als Fehler gemeldet. **Echter Befund, erst durch Pruefpunkte.md sichtbar geworden.**
- [x] GUI-Anforderungen aus Programm-Anforderungen.md gegen gui.py geprüft:
  - Alle Punkte erfüllt bis auf: **"Ergebnistabelle filterbar nach Status, Kategorie UND Baustein"** — in `ResultPage` (gui.py) sind nur Status- und Kategorie-Filter implementiert (`_status_filter`, `_category_filter`), kein Filter nach Baustein/Pfad. **Echter Gap gegenüber Spezifikation.**
- [x] Technisches Konzept aus Programm-Anforderungen.md gegen connector.py/runner.py geprüft:
  - **Reconnect-Logik fehlt** ("identisch zum Tag Exporter — TIA V19 kann die Session während der Analyse verlieren") — bestätigt: kein Reconnect-Code in `connector.py` oder `runner.py` (grep negativ). Dies ist aber bereits von der Vorsitzung selbst in `Session1-Fortschritt.md` unter "Nächste Session" als offener Punkt vermerkt — **kein verstecktes Problem, sondern ein bekanntes, bewusst vertagtes TODO.**
- [x] Metadaten-Pflichtfelder: Pruefpunkte/Prompt nannten ursprünglich `["Autor", "Version"]` (deutsch), Code korrigiert zu `["Author", "Version"]` (echter Openness-Attributname) — **bewusste, im Docstring dokumentierte Korrektur, kein Fehler.**
- [x] Aktualisierter Abschlussbericht an User übergeben

Letzter Stand: "Runde 2 abgeschlossen — 3 neue echte Befunde (Zertifikat-Schweregrad, fehlender Baustein-Filter, fehlende Reconnect-Logik) identifiziert und gemeldet. Noch keine Code-Änderungen vorgenommen, warte auf Freigabe. NICHT Salzmaschine-Projekt verwenden (User-Anweisung: erst später)."

## Runde 3 (Behebung der 3 Befunde aus Runde 2, auf User-Anweisung)

- [x] **Befund 1 — Zertifikat-Schweregrad behoben** (`src/tia_linter/checks/hardware.py`, `ZertifikatCheck`): Status wird jetzt pro Fall explizit gesetzt statt über `definition.severity.as_status()`:
  - Kein Zertifikat vorhanden → `CheckStatus.ERROR`
  - Zertifikat abgelaufen → `CheckStatus.ERROR`
  - Zertifikat läuft bald ab (< `min_restlaufzeit_monate`) → `CheckStatus.WARNING`
  - Zertifikat gültig → `CheckStatus.OK` (neu — bisher lieferte kein Check der Codebasis explizite OK-Befunde; hier bewusst so umgesetzt, weil User es explizit gefordert hat)
  - Docstring der Klasse aktualisiert, erklärt die Abweichung vom sonst üblichen Muster.
  - Verifiziert: `py_compile` OK, `pytest` 7/7 weiterhin grün. Kein isolierter Unit-Test für diesen Check möglich ohne echte TIA-Verbindung (Openness-Typen wie `LocalCertificateManager` nicht ohne TIA Portal verfügbar) — Logik per Code-Review geprüft.
  - Vom User bestätigt.
- [x] **Befund 2 — Baustein-Filter in GUI behoben** (`src/tia_linter/gui.py`, `ResultPage`):
  - Neues drittes Filterfeld "Pfad:" als `ttk.Entry` (Freitext statt Dropdown), Placeholder-Text "Pfad / Baustein filtern..." via eigenem ttk-Style (`TiaPathFilterPlaceholder.TEntry`, graue Schrift), verschwindet bei Fokus und kehrt bei leerem Feld + Fokusverlust zurück.
  - Live-Filterung über `trace_add("write", ...)` auf der StringVar — kein Button nötig.
  - Case-insensitive Substring-Suche auf `result.path`.
  - Kombiniert per AND mit Status- und Kategorie-Filter (`_refresh_table` prüft alle drei Bedingungen nacheinander).
  - `load_report()` setzt den Pfad-Filter beim Laden eines neuen Reports auf Placeholder zurück (analog zu Status/Kategorie).
  - Bugfix während der Umsetzung: `trace_add` wurde ursprünglich vor Erzeugung von `self._tree` registriert — der initiale Placeholder-`set()` hätte `_refresh_table()` ausgelöst und wäre mit `AttributeError` abgestürzt, da `self._tree` noch nicht existierte. Registrierung ans Ende von `_build_widgets()` verschoben (nach Tree-Erzeugung).
  - Funktional getestet (GUI instanziiert, Dummy-Report geladen, Fokus/Eingabe/Placeholder/Kombination mit Status-Filter simuliert): Filterung auf Substring funktioniert case-insensitive, Placeholder erscheint/verschwindet korrekt, AND-Verknüpfung mit Status-Filter liefert korrektes Ergebnis. `pytest` 7/7 weiterhin grün.
  - Vom User bestätigt.
- [x] **Befund 3 — Reconnect-Logik behoben** (`src/tia_linter/runner.py`, `src/tia_linter/config.py`, `config/default.yaml`, `src/tia_linter/gui.py`, `README.md`):
  - Referenz `tia-tag-exporter/src/tia_tag_exporter/connector.py` geprüft — **wichtige Erkenntnis**: die Reconnect-Mechanik liegt dort gar nicht in `connector.py` (das enthält nur Connect/Disconnect, strukturell bereits identisch zu unserem `BaseTiaConnector`), sondern in `main.py::run_export()` als Retry-Schleife um den ganzen Verbindungs-/Verarbeitungsblock. `connector.py` musste daher **nicht** geändert werden — nur `runner.py` (unser Äquivalent zu `run_export`).
  - `run_lint()` umgebaut: äußere Schleife über `max_reconnect_attempts` (Default 3), pro Versuch neuer `TiaConnector`. Bei `EngineeringObjectDisposedException` (mit `ImportError`-Fallback auf breites `Exception`, identisch zur Referenz — dort als bewusst weites Netz dokumentiert) wird die Session als tot erkannt, gewarnt/geloggt und im nächsten Versuch neu verbunden.
  - Wiederaufnahme-Granularität bewusst feiner als in der Referenz (dort PLC/DB/HMI-Blöcke, hier einzelne Prüfpunkte): `done_check_ids` trackt abgeschlossene Checks (erfolgreich UND mit eigenem Fehlerbefund) — beim Reconnect wird nur die Restliste (`remaining`) verarbeitet.
  - Bestehende Per-Check-Fehlerisolation bleibt erhalten und wurde nicht durch die Reconnect-Logik ersetzt: normale Check-Exceptions (z. B. ein einzelner API-Bug) lösen weiterhin nur einen Fehlerbefund für diesen einen Check aus, KEINEN Reconnect — nur die spezifische Disposed-Exception tut das (per `except disposed_exc_types: raise` vor dem generischen `except Exception`).
  - Abbruch (`cancel_event`) weiterhin ohne Reconnect-Versuch — die `with`-Block-Struktur sorgt dafür, dass nach einem Abbruch kein weiterer Versuch gestartet wird.
  - Scheitern alle Versuche: Fehlerbefund `check_id="verbindung.reconnect"` (Kategorie "Verbindung") wird dem Report hinzugefügt statt einer Exception — Prüfung endet mit den bis dahin gesammelten Ergebnissen statt abzustürzen.
  - Reconnect-Meldungen laufen über den bestehenden `progress`/`report()`-Mechanismus — dadurch automatisch sichtbar in Log UND GUI-Statuszeile/Log-Fenster, keine GUI-Änderung dafür nötig.
  - `simulate_lint_run()` um denselben (dort ungenutzten) Parameter `max_reconnect_attempts` ergänzt, damit GUI beide Funktionen weiterhin austauschbar aufrufen kann (bestehendes Muster wie bei `dll_path`/`tia_version`).
  - Neues Config-Feld `max_reconnect_attempts: int = 3` (`AppConfig`, `Field(ge=1)`) + Eintrag in `config/default.yaml` mit Kommentar; `gui.py` reicht `self.config.max_reconnect_attempts` als Kwarg an den Lint-Thread durch.
  - README um Abschnitt "Verbindungsstabilität (Reconnect)" ergänzt.
  - Funktional isoliert getestet (Fake-Connector + Fake-Checks via `unittest.mock.patch`, da keine echte TIA-Verbindung möglich/erlaubt ist — Salzmaschine-Projekt planmäßig noch nicht verwendet):
    1. Session stirbt bei Check B (1. Versuch) → Reconnect → B läuft beim 2. Versuch erneut, A/C werden NICHT wiederholt. Normaler `ValueError` in Check C löst korrekt KEINEN Reconnect aus, sondern nur dessen eigenen Fehlerbefund. ✅
    2. Session stirbt dauerhaft → genau `max_reconnect_attempts` Verbindungsversuche, danach ein `verbindung.reconnect`-Fehlerbefund statt Absturz. ✅
    3. `cancel_event` während eines Checks gesetzt → sofortiger Abbruch, **kein** Reconnect-Versuch. ✅
  - `py_compile` OK für alle geänderten Dateien, `pytest` 7/7 weiterhin grün, Config lädt (`max_reconnect_attempts: 3`, 40 CheckDefinitions), GUI-Smoketest OK.

## Runde 4 (Abschluss)

- [x] Commit & Push — Commit `c6fcedf` "Fix Zertifikat-Schweregrad, ergänze Baustein-Filter und Reconnect-Logik" auf `main` gepusht (`b2c54d9..c6fcedf`), Repo: https://github.com/Thomas-Schlangen/tia-linter
- [x] Finale Zusammenfassung an User übergeben

Letzter Stand: "Alle 3 Befunde aus Runde 2 behoben, verifiziert (py_compile, pytest 7/7, isolierte Funktionstests mit Fake-Connector für die Reconnect-Logik, GUI-Smoketest) und gepusht. Kein Testlauf gegen echtes TIA-Portal-Projekt (weiterhin planmäßig offen, Salzmaschine-Projekt laut User-Anweisung noch nicht verwenden). Damit ist der komplette Review-Zyklus (Runde 1-4) abgeschlossen."

## Runde 5 — Erster realer Testlauf gegen Salzmaschine-Projekt (auf User-Anweisung)

**Setup verifiziert:** TIA Portal V21 lokal installiert, DLL-Pfad aus `default.yaml` stimmt
(`C:\Program Files\Siemens\Automation\Portal V21\PublicAPI\V21\net48\Siemens.Engineering.Base.dll`).
Projektdatei: `Salzmaschine\S7T0159_V20_V21\S7T0159_V20_V21.ap21` (bereits im V21-Format,
laut Konvertierungslogs V17→V20→V21). Reiner Verbindungstest (`connector.connect()`
ohne Checks) erfolgreich: Verbindungsaufbau 18-35s, 3 Devices erkannt, `Author`/`Version`-
Projektattribute lesbar. Projektgröße: 1 PLC-Software (`pn4805-15a1`), 288 Bausteine
(davon 32 DBs), 3 Tag-Tabellen mit 42 Tags.

**Voller Lauf über alle 40 aktivierten Prüfpunkte gestartet (via eigenem Testskript, direkter
Aufruf von `runner.run_lint()`, nicht über die GUI).** Ergebnis: Lief bis Check 31/40
(≈4 Minuten, 15:27:39–15:31:15), dann **fataler Absturz des gesamten Prozesses**. Drei
konkrete Befunde:

1. ⚠️ **`hardware.hardware_vorhanden` (Check 20/40) — `AttributeError`**: `device_item.Parent`
   liefert ein generisches `IEngineeringObject` ohne typisiertes `.DeviceItems`-Attribut
   (bekannte Openness-Einschränkung, siehe `Openness-API-Referenz-fuer-Linter.md`: "Viele
   Objekte liefern nur IEngineeringObject — dann GetAttribute(...) statt direktem
   .Attribut-Zugriff"). Per-Check-Fehlerisolation hat korrekt funktioniert: Fehlerbefund
   für genau diesen Check erzeugt, Lauf ging normal weiter. **Muss noch behoben werden.**
2. ⚠️ **`bibliotheken.veraltete_bibliotheken` (Check 28/40) — `ImportError`**:
   `UpdateCheckMode` existiert nicht (mehr) unter `Siemens.Engineering.Library` in der
   tatsächlich installierten V21-API — die im Docstring referenzierte Fundstelle war nicht
   korrekt. Ebenfalls sauber isoliert (Fehlerbefund statt Absturz), Lauf ging weiter.
   **Muss noch behoben werden — korrekten Namespace/Typnamen in der V21-PDF nachschlagen.**
3. ❌ **KRITISCH — `Siemens.Engineering.EngineeringOutOfMemoryException`
   während Check 31/40 (`styleguide.static_zugriff_extern`, Prüfpunkt 26)**: "The maximum
   number (500000) of instances for this TIA-Portal has been exceeded." Diese Exception
   wurde **nicht** von der Per-Check-Fehlerisolation aufgefangen (sie trat tief in
   pythonnet selbst auf, `Python.Runtime.ClassBase.tp_iter_impl`, außerhalb des normalen
   Python-Traceback-Pfads) und hat den gesamten Prozess/die gesamte Session beendet.
   **Ursache (Verdacht, noch zu verifizieren):** Über 30 Checks hinweg werden sehr viele
   .NET-/Openness-Objektinstanzen erzeugt (Baustein-XML-Exports werden pro Check erneut
   für dieselben ~250 exportierbaren Bausteine durchgeführt statt einmal gecached;
   `CrossReferenceService`-Aufrufe pro Tag/Baustein in mehreren Checks) — ohne dass
   irgendwo im Code `.Dispose()` aufgerufen oder explizit `gc.collect()`/Objektfreigabe
   erzwungen wird. TIA Portal hat einen harten Zähler für offene Instanz-Handles pro
   Session (500.000) — bei 288 Bausteinen × mehreren Checks, die jeweils erneut
   exportieren/kreuzreferenzieren, ist dieser Zähler erschöpft worden, **bevor auch nur
   ein Drittel der Prüfpunkte durchgelaufen war.** Das ist ein systemisches
   Ressourcenmanagement-Problem, kein einzelner Check-Bug — betrifft vermutlich jedes
   Projekt ab einer gewissen Größe. **Muss vor dem nächsten Vollrun behoben werden**,
   sonst ist `run_lint()` auf keinem echten Projekt vollständig lauffähig.
   Naheliegende Ansätze (noch nicht entschieden, mit User zu klären): (a) `export_block_xml`-
   Ergebnisse pro Baustein einmal pro Lauf cachen statt pro Check neu zu exportieren,
   (b) explizite Objektfreigabe/`gc.collect()` zwischen Checks, (c) Session-Neustart
   (die neue Reconnect-Logik aus Runde 3!) periodisch nach N Checks erzwingen, um den
   Instanzzähler zurückzusetzen.

**Umgebung nach dem Absturz verifiziert als sauber:** kein verwaister TIA-Portal-Hauptprozess,
keine Lock-Dateien oder Temp-Reste im Projektordner — Absturz hat das Projekt nicht
beschädigt oder blockiert (bestätigt den rein lesenden Charakter des Tools laut README-
Disclaimer, auch im Fehlerfall).

**Nicht erreicht:** Checks 32-40 (u. a. `output_mehrfach_beschrieben`, `multi_instanzen`,
`udt_wiederkehrende_strukturen`, `ob1_komplexitaet`, `know_how_schutz`,
`tag_tabellen_nur_io`, `nicht_optimierte_bausteine`, `bausteine_im_root`, `schreibschutz`)
sowie die finale Report-Erstellung (PDF) wurden mangels vollständigem Report-Objekt noch
nicht real getestet.

Letzter Stand: "Erster echter Testlauf hat 2 konkrete Check-Bugs und 1 kritisches
Ressourcenmanagement-Problem (OOM nach ~30 Checks) aufgedeckt. Noch keine Fixes
vorgenommen — warte auf Rückmeldung/Priorisierung durch User, bevor weitergemacht wird."

## Runde 6 — Kritisches OOM-Problem behoben (auf User-Anweisung "Fang mit dem kritischen OOM-Problem an")

**Versuch 1 (verworfen): `.NET GC.Collect()` nach jedem Check.** Hypothese: Pythons
Referenzcounting gibt die vielen .NET-/Openness-Objektinstanzen (CrossReference-Bäume,
Baustein-Exports) frei, aber der zugrundeliegende .NET-Heap wird in einem langen
Headless-Prozess zu selten tatsächlich kollektiert. Fix: `_release_dotnet_objects()` in
`runner.py` ruft `System.GC.Collect()` + `WaitForPendingFinalizers()` + `Collect()` nach
jedem einzelnen Check auf. **Empirisch widerlegt**: zweiter Testlauf gegen Salzmaschine
ist an exakt derselben Stelle (Check 31/40, `styleguide.static_zugriff_extern`, identischer
Fehlertext "maximum number (500000) of instances") abgestürzt — GC.Collect() hatte
nachweislich keinerlei Effekt. Schlussfolgerung: TIA Portals Instanzzähler ist offenbar
nicht an den regulären .NET-GC-Zyklus gekoppelt (Stacktrace zeigt
`LifetimeContractHandle` — eher ein Session-/Lifetime-Contract-System als
klassisches Managed-Heap-Tracking). `_release_dotnet_objects()`-Aufruf im Code belassen
(harmlos, kein Overhead-Problem beobachtet) als zusätzliche Absicherung, aber **nicht**
die eigentliche Lösung.

**Versuch 2 (erfolgreich): Proaktiver, planmäßiger Reconnect alle N Checks.**
`run_lint()` in `runner.py` umgebaut (von `for attempt in range(1, max_reconnect_attempts+1)`
auf `while True` mit zwei getrennten Zählern):
- `session_number` — zählt jede geöffnete Verbindung (geplant oder Fehler-bedingt), nur fürs Logging.
- `consecutive_failures` — zählt NUR echte `EngineeringObjectDisposedException`-Abbrüche in
  Folge, wird nach jeder erfolgreich beendeten Session (egal ob fertig, geplanter Reconnect
  oder User-Abbruch) auf 0 zurückgesetzt. Nur dieser Zähler wird gegen `max_reconnect_attempts`
  geprüft — Semantik zu Runde 3 unverändert (max_reconnect_attempts = Gesamtzahl erlaubter
  Verbindungsversuche, wenn die Session tatsächlich immer wieder stirbt).
- Neuer Parameter `reconnect_every_n_checks` (Default 10, konfigurierbar wie
  `max_reconnect_attempts` über `AppConfig`/`default.yaml`/GUI): nach so vielen Checks
  wird die aktuelle Session bewusst beendet (`break` aus der inneren for-Schleife,
  `with connector:` schließt sauber) und in der nächsten `while`-Iteration eine frische
  Verbindung aufgebaut — die bestehende `done_check_ids`-Logik aus Runde 3 sorgt dafür,
  dass dabei kein Check doppelt läuft. Zählt **nicht** gegen `max_reconnect_attempts`,
  da es kein Fehlerfall ist.
- `simulate_lint_run()` um denselben (dort ungenutzten) Parameter ergänzt (Austauschbarkeits-Muster).
- Config: `reconnect_every_n_checks: int = Field(default=10, ge=1)` in `AppConfig`
  (`config.py`), Eintrag + Kommentar in `default.yaml`, Durchreichung in `gui.py`.

**Isoliert funktional getestet** (Fake-Connector, `unittest.mock.patch`, 3 neue Szenarien
zusätzlich zu den 3 aus Runde 3 — alle 6 grün):
1. 25 Checks, `reconnect_every_n_checks=10` → genau 3 Sessions (10+10+5), jeder Check
   genau 1x gelaufen, keine Wiederholungen.
2. Geplante Reconnects zählen nicht gegen `max_reconnect_attempts` — Lauf mit
   `max_reconnect_attempts=1` schafft trotzdem alle 3 geplanten Sessions.
3. Gemischtes Szenario: echter Session-Tod genau an einer geplanten Reconnect-Grenze →
   korrekt behandelt, kein Check doppelt oder fehlend, `consecutive_failures` wird nach
   erfolgreicher Fortsetzung wieder zurückgesetzt.
   Dabei einen Off-by-One-Bug in der eigenen Umsetzung gefunden und korrigiert: die
   Entkopplung von `session_number`/`consecutive_failures` hatte zunächst einen
   Verbindungsversuch zu viel erlaubt (`> max_reconnect_attempts` statt `>=`) — durch den
   Vergleich mit den (bereits vom User bestätigten) Runde-3-Tests aufgefallen und behoben.

**Verifiziert gegen das echte Salzmaschine-Projekt (3. realer Testlauf):** Vollständiger
Durchlauf über alle 40 Prüfpunkte in 4 Sessions (10+10+10+10 Checks, 3 planmäßige
Reconnects), **kein Absturz mehr**, `Prüfung abgeschlossen.` erreicht, Gesamtlaufzeit
352,4s. Die beiden bereits bekannten Einzel-Bugs (`hardware.hardware_vorhanden`
AttributeError, `bibliotheken.veraltete_bibliotheken` ImportError) traten wie erwartet
erneut auf, wurden aber weiterhin korrekt von der Per-Check-Fehlerisolation aufgefangen
— **das kritische OOM-Problem ist behoben.**

**⚠️ Neuer Befund beim Durchsehen des vollständigen Ergebnisses (nicht Teil des
OOM-Auftrags, aber während dessen Verifikation entdeckt):** Der Lauf lieferte
50.871 Befunde insgesamt (312 Fehler, 50.559 Warnungen, 0 OK) — davon allein **49.413**
von `kommentare.variablen_kommentar` (Prüfpunkt 1). Ursache identifiziert: `db.Interface.Members`
liefert nicht nur die deklarierten Top-Level-DB-Variablen, sondern rekursiv **jedes einzelne
verschachtelte Element** von Arrays/Structs als eigenes "Member" mit Punkt-/Klammer-Notation
im Namen (Beispiel aus dem DB `MG1VExMan`, 39.189 Befunde allein aus diesem einen DB:
`GlobalMan`, `GlobalMan.GlobalMan[0]`, `GlobalMan.GlobalMan[0].Plus`,
`GlobalMan.GlobalMan[0].Plus.Ena`, ... — jede Ebene wird einzeln als unkommentiert
gemeldet, da Projekttexte üblicherweise nur das Top-Level-Member kommentieren). Das macht
den Report für Projekte mit großen Array-/Struct-DBs faktisch unbrauchbar. **Noch nicht
behoben — nur entdeckt und hier dokumentiert, wartet auf Priorisierung.**

Letzter Stand: "OOM-Problem behoben und gegen das echte Projekt verifiziert (voller
Durchlauf, kein Absturz mehr). Dabei einen neuen, separaten Bug entdeckt
(`variablen_kommentar` zählt rekursiv verschachtelte Array-/Struct-Elemente einzeln,
~49.000 von 50.871 Befunden). Die 2 bereits bekannten Check-Bugs aus Runde 5
(`hardware.hardware_vorhanden`, `bibliotheken.veraltete_bibliotheken`) sind weiterhin
offen. Noch nichts committed/gepusht — warte auf Rückmeldung, wie weiter priorisiert
werden soll."

## Runde 7 — `variablen_kommentar`-Bug behoben (auf User-Anweisung, Priorität 1 von 3)

**Fix** (`src/tia_linter/checks/comments.py`, `VariablenKommentarCheck`): Nur Top-Level-
DB-Member werden noch auf Kommentar geprüft — Member, deren Name ``.`` oder ``[``
enthält (verschachtelte Array-/Struct-Elemente aus der rekursiven Auflösung von
``db.Interface.Members``), werden übersprungen. Vom User explizit so gewünscht: "Wenn
ein Array einen Kommentar hat, reicht das völlig aus." TIA-Variablennamen selbst dürfen
diese Zeichen nicht enthalten — der Filter ist daher eindeutig und sicher.

**Verifiziert gegen das echte Salzmaschine-Projekt** (isolierter Check-Test, nicht
vollständiger Lauf, für schnellere Iteration): **251 Befunde statt vorher 49.413** —
alle stichprobenartig geprüften Beispiele sind echte, sinnvolle Top-Level-Variablen ohne
Kommentar (u. a. System-Bytes/Takt-Merker der Default-Tag-Tabelle). `py_compile` OK,
`pytest` 7/7 weiterhin grün.

Letzter Stand: "variablen_kommentar-Bug behoben und verifiziert (49.413 → 251 Befunde).
Weiter mit Bug 2/3: hardware.hardware_vorhanden (AttributeError)."

## Runde 8 — Bug 2/3 und 3/3 behoben (hardware.hardware_vorhanden, bibliotheken.veraltete_bibliotheken)

**Bug 2 — `hardware.hardware_vorhanden` (`AttributeError`) behoben:** Ursache war
`device_item.Parent`, das nur ein generisches `IEngineeringObject` ohne `.DeviceItems`
liefert (Openness-Navigations-Properties liefern oft nur die Basisschnittstelle statt
des konkreten Typs). Fix in `_tia_helpers.py`: `iter_plc_targets()` liefert jetzt ein
`(plc_software, device_item, device)`-Tripel statt eines Paares — `device` ist die
umgebende, korrekt typisierte `Device`-Station direkt aus der `project.Devices`-Iteration
(dort schon vorhanden, keine zusätzliche Navigation nötig). Alle 4 Aufrufstellen in
`hardware.py` angepasst; nur `HardwareVorhandenCheck` nutzt `device` tatsächlich, die
anderen 3 ignorieren es (`_device`). **Verifiziert gegen echtes Projekt** (isolierter
Check-Test): läuft jetzt fehlerfrei durch, 0 Befunde (Projekt hat Hardware-Module
konfiguriert).

**Bug 3 — `bibliotheken.veraltete_bibliotheken` (`ImportError`) behoben:** `UpdateCheckMode`
gegen die tatsächlich installierte V21-API-Dokumentation (`Siemens.Engineering.Base.xml`)
nachgeschlagen — liegt unter `Siemens.Engineering.Library.Types.UpdateCheckMode`, nicht
direkt unter `Siemens.Engineering.Library` wie ursprünglich angenommen. Import in
`libraries.py` korrigiert, Docstring aktualisiert. **Verifiziert gegen echtes Projekt**:
läuft jetzt fehlerfrei durch, 0 Befunde.

`py_compile` + `pytest` (7/7) nach jedem der beiden Fixes grün.

Letzter Stand: "Alle 3 vom User priorisierten Bugs behoben und einzeln gegen das echte
Projekt verifiziert. Als Nächstes: finaler kompletter 40-Check-Lauf zur
Gesamtverifikation, dann Commit/Push."

## Runde 9 — Finale Gesamtverifikation (4. realer Lauf gegen Salzmaschine)

**Vollständiger Lauf über alle 40 Prüfpunkte nach allen 4 Fixes (OOM + 3 Check-Bugs):**
- Laufzeit: 340,8s (4 Sessions à 10 Checks, 3 planmäßige Reconnects) — **kein Absturz.**
- **Keine einzige "Fehler bei Prüfpunkt"-Exception mehr** (vorher: 2, jetzt: 0) —
  beide Check-Bugs bestätigt behoben.
- **1.707 Befunde gesamt** (310 Fehler, 1.397 Warnungen, 0 OK) — realistische,
  plausible Zahl für ein Projekt dieser Größe (vorher: 50.871, davon 49.413 allein aus
  dem `variablen_kommentar`-Bug).
- Verteilung nach Check-ID stichprobenartig geprüft: höchster Einzelwert 321
  (`netzwerk_beschreibung`), alle Werte proportional zur Projektgröße (288 Bausteine,
  ~250 davon exportierbar) — keine weiteren auffälligen/unrealistischen Zähler entdeckt.
- Verteilung nach Kategorie: Kommentare & Beschreibungen 860, Namenskonventionen 312,
  Programmstruktur 285, Projektmetadaten 249, Hardware & Konfiguration 1.

**Damit sind alle 4 in dieser Session gefundenen Probleme (OOM-Absturz,
`variablen_kommentar`-Explosion, `hardware.hardware_vorhanden`-AttributeError,
`bibliotheken.veraltete_bibliotheken`-ImportError) behoben und gegen das echte
Salzmaschine-Projekt verifiziert.** Noch nicht erreicht/getestet: Checks 32-40 aus
Runde 5 sind jetzt Teil des vollständigen Laufs und liefen mit (kein separater Test
nötig, da der komplette Lauf jetzt fehlerfrei durchläuft); PDF-Report-Erstellung aus
einem echten (nicht simulierten) `LintReport` wurde noch nicht separat verifiziert.

**Zusatztest PDF-Report:** Aus dem realen 1.707-Befunde-Report erfolgreich ein PDF erzeugt
(1,4s, 261 KB) — keine Performance- oder Rendering-Probleme bei dieser Größenordnung.

Letzter Stand: "Alle 4 Probleme behoben und final gegen das echte Projekt verifiziert
(0 Check-Fehler, 1.707 plausible Befunde, kein Absturz, PDF-Export getestet). Noch nicht
committed/gepusht — warte auf Rückmeldung des Users, ob jetzt committed werden soll."

## Runde 10 — Korrektur an Bug 1: nur Array-Elemente überspringen, Struct-Felder weiter prüfen

**User-Korrektur:** Die Runde-7-Lösung hatte fälschlich JEDES Member mit ``.`` ODER ``[``
im Namen übersprungen — das schließt auch normale, für sich kommentierbare
Struct-Unterfelder aus (nur Array-Elemente sollten übersprungen werden, da man nicht
jedes Array-Element einzeln kommentiert, aber Struct-Felder sind normale Variablen).

**Fix** (`src/tia_linter/checks/comments.py`, `VariablenKommentarCheck`): Filter geändert
von ``if "." in member_name or "[" in member_name`` auf ``if "[" in member_name`` — nur
Member, deren Name irgendwo einen Array-Index (``[...]``) enthält, werden übersprungen
(das betrifft auch alles, was unterhalb eines Array-Elements verschachtelt ist, z. B.
``GlobalMan.GlobalMan[0].Plus.Ena`` — enthält ``[``, wird übersprungen). Reine
Punkt-Notation ohne Klammer (z. B. ein hypothetisches ``Struct.Feld`` ohne Array
darunter) wird jetzt korrekt weiter einzeln geprüft. Docstring aktualisiert.

**Verifiziert gegen das echte Salzmaschine-Projekt** (isolierter Check-Test):
**4.966 Befunde** (vorher 251 mit der zu aggressiven Runde-7-Fassung, davor 49.413 mit
dem ursprünglichen Bug) — der Anstieg gegenüber 251 kommt von echten, bisher nicht
individuell geprüften Struct-Feldern ohne Kommentar (plausibel bei einem Projekt mit
7.171 Projekttexte-Kommentaren insgesamt, aber vielen unkommentierten Einzelfeldern in
Structs). `py_compile` OK, `pytest` 7/7 weiterhin grün.

**Finaler kompletter 40-Check-Lauf nach der Korrektur:** 325,8s, 0 Check-Fehler,
6.422 Befunde gesamt (310 Fehler, 6.112 Warnungen) — kein Absturz.

**README.md aktualisiert:** Abschnitt "Bekannte Einschränkungen" überarbeitet — die
veraltete Aussage "Kein Testlauf gegen ein echtes TIA-Portal-Projekt" entfernt und durch
eine Zusammenfassung der real gefundenen und behobenen Probleme ersetzt (OOM,
UpdateCheckMode-Namespace, device_item.Parent-AttributeError). Klargestellt, dass
`main.py` weiterhin bewusst `simulate_lint_run()` als Standard verwendet — Umstellung
auf `run_lint()` als Produktivmodus ist ein separater, noch nicht getroffener
Entscheidungsschritt.

**Committed & gepusht:** Commit `ea07a77` "Fix crashes and bugs found in first real
test run against TIA project" auf `main` (`c6fcedf..ea07a77`),
Repo: https://github.com/Thomas-Schlangen/tia-linter

Letzter Stand: "Alle 4 in dieser Session gefundenen Probleme (OOM-Absturz,
variablen_kommentar-Explosion inkl. User-Korrektur zu Struct-vs-Array,
hardware.hardware_vorhanden, bibliotheken.veraltete_bibliotheken) behoben, gegen das
echte Salzmaschine-Projekt verifiziert (voller Lauf: 0 Fehler, 6.422 plausible Befunde,
kein Absturz), README aktualisiert, committed und gepusht. Session abgeschlossen."

## Runde 11 — Produktivmodus aktivieren (auf User-Anweisung)

**Ziel:** `main.py` soll standardmäßig `run_lint()` (echte TIA-Verbindung) statt
`simulate_lint_run()` verwenden; der simulierte Testlauf bleibt über eine GUI-Checkbox
erreichbar, standardmäßig deaktiviert.

**Umsetzung:**
- `main.py`: importiert jetzt `run_lint` zusätzlich zu `simulate_lint_run`, übergibt beide
  an `TiaLinterApp`. Veralteten "HINWEIS (Session 1)"-Kommentar (Linux-Entwicklung, noch
  kein Testlauf möglich) entfernt und durch eine Erklärung des neuen Umschaltmechanismus
  ersetzt.
- `gui.py` (`TiaLinterApp`): `__init__` nimmt jetzt zwei Funktionen entgegen
  (`run_lint`, `simulate_lint_run`), gespeichert als `self._run_lint_fn` /
  `self._simulate_lint_run_fn`. `start_lint_run()` wählt anhand der neuen Checkbox die
  aktive Funktion und übergibt sie als **Positionsargument** an `_run_lint_thread`
  (Signatur geändert zu `_run_lint_thread(self, run_lint_fn, **kwargs)`), damit der
  Hintergrund-Thread nicht mehr fest auf eine einzige Funktion verdrahtet ist.
- `gui.py` (`MainPage`): neue Checkbox "Testmodus (simulierter Lauf ohne
  TIA-Verbindung, Dummy-Befunde)" unterhalb der TIA-Version-Auswahl,
  `self.test_mode = tk.BooleanVar(value=settings.test_mode)` — Standardwert kommt aus
  `Settings`, damit die Auswahl zwischen Sessions erhalten bleibt (analog zu
  `last_tia_version` etc.).
- `settings.py`: neues Feld `test_mode: bool = False` in der `Settings`-Dataclass —
  Default deaktiviert wie vom User gefordert. `_on_close()` in `gui.py` persistiert den
  aktuellen Checkbox-Zustand beim Schließen.

**Funktional getestet** (GUI instanziiert, kein echtes TIA nötig für diesen Teil):
- Checkbox-Standardwert bei frischen `Settings()`: `False` (Testmodus aus, Produktivmodus
  aktiv) — wie gefordert.
- Umschalten der Checkbox wählt korrekt zwischen `run_lint`/`simulate_lint_run`
  (per `.__name__` verifiziert).
- Kompletter End-to-End-Durchlauf des Testmodus-Pfads über den echten GUI-Thread-Mechanismus
  (`_run_lint_thread` mit `simulate_lint_run` aufgerufen wie es die Checkbox tun würde):
  Status-Queue liefert `status`/`report`/`done`-Ereignisse korrekt, Report mit
  Dummy-Befunden kommt an.
- `Settings`-Persistenz-Rundtest: `test_mode=True` speichern → laden → `True`;
  ohne vorhandene Datei → Default `False`.
- `py_compile` OK, `pytest` 7/7 weiterhin grün.

**Kompletter Lauf gegen das echte Salzmaschine-Projekt zur Verifikation** (via
`runner.run_lint()`, wie es der jetzt aktive Produktivmodus tut): 328,9s, **0
Check-Fehler**, 6.422 Befunde (310 Fehler, 6.112 Warnungen) — deckungsgleich mit dem
letzten Verifikationslauf aus Runde 10 (unverändertes `runner.py` in dieser Runde,
wie erwartet keine Abweichung).

**PDF-Report erstellt und inhaltlich geprüft** (`pypdf`-Textextraktion, da `pdftoppm`/
Poppler auf diesem System nicht installiert ist und daher keine Seiten-Bilder gerendert
werden konnten — Text wurde stattdessen direkt aus den PDF-Seiten extrahiert):
- **595 Seiten gesamt** (6.422 Befunde in Detailtabellen zu je ca. 10-11 Zeilen/Seite).
- **Seite 1 (Deckblatt):** Titel "TIA Linter — Prüfbericht", Projektname
  `S7T0159_V20_V21`, TIA-Portal-Version, Prüfdatum, Prüfer.
- **Seite 2 (Zusammenfassung):** Gesamttabelle (310 Fehler / 6.112 Warnungen / 0 OK) plus
  Aufschlüsselung nach Kategorie (Kommentare & Beschreibungen: 0 Fehler/5.575 Warnungen;
  Namenskonventionen: 309 Fehler/3 Warnungen; Programmstruktur: 0/285; Hardware &
  Konfiguration: 1/0; Projektmetadaten: 0/249).
- **Ab Seite 3:** Detailtabellen, ein Abschnitt pro Kategorie, je Zeile Status/Pfad/
  Beschreibung/Empfehlung — inhaltlich plausibel (z. B. "Variable 'System_Byte' hat
  keinen Kommentar" mit Empfehlung "Kommentar ... ergänzen"; DB-Namensverstöße wie
  "DB-Name 'PrgFieldbusOkDb' entspricht nicht dem Muster '^DB_[A-Za-z]'" als Fehler).
- Letzte Seite endet mit den Projektmetadaten-Befunden (Compiler-Meldungen, fehlende
  Versionsnummer).
- Format/Aufbau entspricht exakt der `reporter.py`-Spezifikation (Deckblatt → Zusammenfassung
  → Detailseiten je Kategorie), keine Auffälligkeiten.

**Committed & gepusht (nach User-Bestätigung):** Commit `3f07b85` "Aktiviere run_lint()
als Produktivmodus, simulate_lint_run() über Testmodus-Checkbox" auf `main`
(`ea07a77..3f07b85`), Repo: https://github.com/Thomas-Schlangen/tia-linter

Letzter Stand: "Produktivmodus umgesetzt, funktional getestet (Checkbox-Default,
Umschaltlogik, Settings-Persistenz), kompletter Lauf gegen echtes Projekt verifiziert
(0 Fehler, 6.422 Befunde, deckungsgleich mit Vorlauf), PDF-Report erstellt und inhaltlich
geprüft (595 Seiten, Struktur/Inhalt plausibel), committed und gepusht. Bereit für
nächste Aufgabe."

## Runde 12 — Obsidian-Doku aktualisiert, LinkedIn-Post-Entwurf erstellt

**Implementierungsstatus in `~/Dokumente/ObsidianVault/Projekte/TIA-Linter/Pruefpunkte.md`
aktualisiert:** Alle 77 offenen Checkboxen (`- [ ]` in den Einzelabschnitten sowie in der
Übersichtstabelle) auf `- [x]` gesetzt — alle 35 Prüfpunkte (inkl. Splits 11b/18b/18c und
den beiden Fest-Pattern→Regex-Umbauten aus den letzten Commits vor dem Pull) sind
implementiert und gegen das echte Salzmaschine-Projekt verifiziert. Ausnahmen wie
gefordert unverändert gelassen: die Format-Legende in Zeile 10 und Prüfpunkt 17b
(Hardware-Typ passt zum Datentyp) — bleibt `- [ ] (spätere Version)` in beiden Vorkommen
(Detailabschnitt + Übersichtstabelle), da laut `Pruefpunkte.md` selbst ausdrücklich als
"spätere Version" markiert und bewusst nicht Teil dieses Projektstands.

**LinkedIn-Post-Entwurf erstellt:**
`~/Dokumente/ObsidianVault/Projekte/TIA-Linter/LinkedIn-Post-Entwurf.md` —
persönlicher Stil analog zum TIA Tag Exporter Post, mit Tool-Beschreibung, Nutzen für
SPS-Programmierer, GitHub-Link, Community-Frage am Ende und Hashtags.

Letzter Stand: "Obsidian-Implementierungsstatus aktualisiert (77 Checkboxen → erledigt,
17b korrekt als Ausnahme belassen) und LinkedIn-Post-Entwurf erstellt. Beide Dateien
liegen im Obsidian-Vault, nicht im Code-Repo — kein Commit/Push nötig."

## Runde 13 — Mehrsprachigkeits-Bug bei Comment-Attributen behoben (auf User-Anweisung)

**Bug (User-Meldung):** Prüfpunkt 1 (`kommentare.variablen_kommentar`) meldete *jede*
PLC-Variable als unkommentiert, unabhängig davon, ob tatsächlich ein Kommentar hinterlegt
war. Vom User bereits aus dem Schwesterprojekt `tia-tag-exporter` bekanntes Problem, dort
schon gelöst.

**Ursache:** `PlcTag.Comment` (und ebenso `PlcBlock.Comment`) sind laut V21-Openness-
Referenz (Abschnitt "Umgang mit mehrsprachigen Texten", nennt `PlcTag.Comment` explizit
als Beispiel) keine einfachen Strings, sondern `Siemens.Engineering.MultilingualText`-
Objekte — TIA Portal ist grundsätzlich mehrsprachig, der Text existiert pro Sprache separat
als `MultilingualTextItem`, erreichbar nur über `Comment.Items.Find(<Language>).Text`. Der
bisherige Code las stattdessen `GetAttribute("Comment")` (in `checks/comments.py`,
`VariablenKommentarCheck`) bzw. `get_attribute(block, "Comment", "")` (an 3 weiteren
Stellen, siehe unten) — das lieferte nie den tatsächlichen Text der Referenzsprache,
sondern faktisch immer einen leeren/falschen Wert.

**Betroffen waren 4 Stellen** (alle nutzten dasselbe kaputte Muster):
1. `kommentare.variablen_kommentar` (`VariablenKommentarCheck`, PLC-Tag-Kommentare) —
   die vom User gemeldete Stelle.
2. `kommentare.baustein_beschreibung` (`BausteinBeschreibungCheck`, Bausteinkopf-Kommentar)
3. `styleguide.know_how_schutz` (`KnowHowSchutzCheck`, sucht "know-how" im Kommentar)
4. `styleguide.schreibschutz` (`SchreibschutzCheck`, sucht "schreibschutz" im Kommentar)

DB-Interface-Member (`Interface.Members`) waren **nicht** betroffen — die haben laut
Openness-Referenz von vornherein gar kein `Comment`-Attribut und werden bereits korrekt
über die zentrale Projekttexte-Verwaltung gelesen (`project_texts.py`, unverändert).

**Fix** (`src/tia_linter/checks/_tia_helpers.py`): zwei neue Hilfsfunktionen, analog zur
bereits im Schwesterprojekt `tia-tag-exporter` gelösten Variante
(`extractor.py::_read_comment`), hier aber gezielt für die Referenzsprache statt für die
erste nicht-leere Sprache (siehe `reference_language()` — dieselbe Sprache, die
`SprachenKonsistentCheck` und `project_texts.py` bereits als "maßgebliche Projektsprache"
verwenden):
- `reference_language(project)` — liefert `project.LanguageSettings.ReferenceLanguage`
  als `Language`-Objekt (nicht nur dessen `Culture` — `MultilingualTextItemComposition.Find`
  erwartet ein `Language`-Objekt).
- `multilingual_text(value, language)` — liest `value.Items.Find(language).Text`, robust
  gegen `None`-Werte, fehlende Sprache, fehlendes `Items`-Attribut.
- `read_comment(obj, language)` — liest `obj.Comment` als typisierte Property (nicht über
  `GetAttribute`) und reicht es an `multilingual_text()` weiter; Objekte ohne
  `Comment`-Attribut liefern `""` statt einer Exception.

Alle 4 betroffenen Checks auf `read_comment(obj, language)` umgestellt
(`comments.py`, `libraries.py`), `language = reference_language(project)` je einmal zu
Beginn von `run()`.

**Verifiziert gegen das echte Salzmaschine-Projekt** (zwei isolierte Testskripte, TIA
Portal V21 lokal verbunden — TIA-Prozesse aus einer vorherigen Session blockierten das
Projekt zunächst mit einem Lock, nach User-Bestätigung als verwaist beendet und die von
TIA angekündigte 2-Minuten-Sperrfrist abgewartet):
- Low-Level-Vergleich alt/neu direkt auf `PlcTag`/`PlcBlock`-Ebene: PLC-Tags 42/42 (alt) →
  1/42 (neu) als unkommentiert erkannt — das eine verbleibende (`System_Byte`) hat
  tatsächlich keinen Kommentar. Reale Kommentare wie "System Bit erster Zyklus",
  "Taktmerker 0,1 s" werden jetzt korrekt gefunden (Default-Tag-Tabelle, TIA-eigene
  System-/Taktmerker-Kommentare). Bausteine: 288/288 (alt) → 155/288 (neu).
- Volle Check-Klassen end-to-end (`VariablenKommentarCheck`, `BausteinBeschreibungCheck`,
  `KnowHowSchutzCheck`, `SchreibschutzCheck`) über dieselbe Config-/CheckDefinition-
  Konstruktion wie `runner.py`: `variablen_kommentar` liefert jetzt 4.925 Befunde (vorher,
  Runde 10: 4.966 — Differenz von 41 entspricht exakt den nicht mehr fälschlich
  markierten, tatsächlich kommentierten Tags von 42), `baustein_beschreibung` 155 Befunde
  (deckungsgleich mit dem Low-Level-Test), `know_how_schutz`/`schreibschutz` je 0 Befunde
  (kein know-how-geschützter/schreibgeschützter Baustein im Projekt — plausibel, keine
  Exceptions). Kein Absturz, keine Fehlerbefunde.
- 9 neue Unit-Tests in `tests/test_tia_helpers.py` (Fake-`MultilingualText`/-`Item`/
  -`Language`-Objekte, kein TIA/pythonnet nötig) für `multilingual_text()`/`read_comment()`
  — u. a. Sprachabgleich, fehlende Sprache, fehlendes `Comment`-Attribut, `None`-Comment.
  `pytest`: 29/29 grün (vorher 20/20).
- Nebenbefund: Nach dem Testlauf blieb ein `Siemens.Automation.Object`-Prozess (Console-
  Session) trotz `with connector:`/`Dispose()` noch einige Sekunden aktiv, bevor er beendet
  werden konnte — kein neuer Bug, entspricht dem in Runde 5 bereits dokumentierten
  Lifetime-Contract-Verhalten von TIA Portal Openness-Sessions.

Letzter Stand: "Mehrsprachigkeits-Bug (PlcTag/PlcBlock.Comment = MultilingualText statt
String) an allen 4 betroffenen Stellen behoben, gegen das echte Salzmaschine-Projekt
verifiziert (Low-Level- und volle Check-Klassen-Ebene), 9 neue Unit-Tests, pytest 29/29
grün. Noch nicht committed/gepusht — warte auf Rückmeldung des Users."

**Nachtrag — committed & gepusht:** Commit `9702eb1` "Fix multilingual Comment attribute
bug (PlcTag/PlcBlock.Comment is MultilingualText, not string)" auf `main`
(`3389a44..9702eb1`), Repo: https://github.com/Thomas-Schlangen/tia-linter.

## Runde 14 — Zweiter, unabhängiger Kommentar-Bug: quotierte Namenssegmente bei DB-Membern

**Bug (User-Meldung, während eigenem Testlauf nach Runde 13):** DB-Member
`_Org > DDb > Fieldbus > Alm.4805_15A1` wurde weiterhin als "kein Kommentar" gemeldet,
obwohl im Projekt (deutsche Referenzsprache) ein Kommentar hinterlegt ist. User-Vermutung:
"versteckt sich ähnlich wie der Kommentar bei den Variablen" — zu Recht, aber ein
anderer Mechanismus als der Runde-13-Bug.

**Ursache (per isoliertem Diagnoseskript gegen das echte Salzmaschine-Projekt
bestätigt):** TIA quotet Namenssegmente, die keine gültigen "einfachen" Bezeichner sind
(z. B. weil sie mit einer Ziffer beginnen) — `member.Name` liefert für dieses Member
`'Alm."4805_15A1"'` statt `'Alm.4805_15A1'`. Die `ViewPath`-Segmente aus
`Project.ExportProjectTexts()` sind dagegen immer unquotiert (`Alm.4805_15A1`) — dadurch
matchte der Lookup in `ProjectTextComments.get()` nie, obwohl der Eintrag
(`('pn4805-15a1', 'Fieldbus', 'Alm.4805_15A1') -> 'Profinet-Station 0 CPU - ...'`)
nachweislich im geladenen Dict vorhanden war. **Exakt dasselbe, bereits im
Schwesterprojekt `tia-tag-exporter` gelöste Problem**
(`extractor.py::_normalize_member_path`, dort schon vor dieser Session vorhanden) — dort
aber nie auf `tia-linter` übertragen worden, obwohl beide Projekte dieselbe
Openness-Basis und denselben `ProjectTextComments`-Mechanismus nutzen.

Betroffen ist ausschließlich `kommentare.variablen_kommentar` (DB-Member-Zweig,
`VariablenKommentarCheck` in `comments.py`) — PLC-Tags (Runde 13) sind syntaktisch
einfache Namen ohne Punktnotation und daher von dieser speziellen Quotierungsregel nicht
betroffen.

**Fix** (`src/tia_linter/checks/_tia_helpers.py`): neue Funktion
`normalize_member_path(name)` — entfernt Anführungszeichen pro Punkt-getrenntem Segment
(``".".join(segment.strip('"') for segment in name.split("."))``), identisch zur
tia-tag-exporter-Referenzimplementierung, hier zusätzlich auf PLC-/DB-Namen anwendbar
(nicht nur Member-Pfade), da dieselbe Quotierungsregel für jeden nicht "einfachen"
Bezeichner gilt. In `comments.py::VariablenKommentarCheck` wird sie auf `plc_name`,
`db_name` und `member_name` angewendet, aber **nur für den Projekttexte-Lookup** — der im
Befund angezeigte Name/Pfad bleibt unverändert die echte (ggf. quotierte) TIA-Bezeichnung.

**Verifiziert gegen das echte Salzmaschine-Projekt** (3 isolierte Diagnoseläufe zur
Eingrenzung + 1 Verifikationslauf, TIA Portal V21 lokal — jeweils verwaiste
`Siemens.Automation.Object`-Prozesse aus der eigenen vorherigen Session vor dem nächsten
Connect beendet und die TIA-seitige 2-Minuten-Sperrfrist abgewartet):
- Alle 8 zuvor identifizierten quotierten Member in DB `Fieldbus` (`Alm."4805_15A1"`,
  `Alm."4805_27A11"`, `Alm."4805_27A21"`, `Alm."4805_27A31"`, `Alm."4805_27A41"`,
  `Alm."4805_30A1"`, `Alm."4805_33A1"`, `Alm."4805_15A8"`) werden nach dem Fix korrekt
  nicht mehr als "kein Kommentar" gemeldet — die Projekttexte-Lookups liefern jetzt die
  hinterlegten Kommentare (z. B. "Profinet-Station 0 CPU - Bedienschrank =4805-6A1").
- Voller `VariablenKommentarCheck`-Lauf: **4.766 Befunde statt vorher 4.925** (Differenz
  159 — der Bug betraf projektweit mehr Stellen als die eine ursprünglich gemeldete,
  u. a. auch DBs `V01St`/`V40St` mit ähnlich benannten quotierten Segmenten wie
  `"4805_27M11".M.AlmFieldbus`).
- 5 neue Unit-Tests in `tests/test_tia_helpers.py` (`TestNormalizeMemberPath`, keine
  TIA-Verbindung nötig) — u. a. einzelnes quotiertes Segment, quotiertes Segment nur in
  einer Ebene eines Punktpfads, unquotierte Segmente bleiben unverändert, mehrere
  quotierte Segmente. `pytest`: 34/34 grün (vorher 29/29).

Letzter Stand: "Zweiter Kommentar-Bug (quotierte Namenssegmente bei DB-Membern,
`Alm.4805_15A1`-Fall) behoben und gegen das echte Salzmaschine-Projekt verifiziert
(4.925 → 4.766 Befunde, 8/8 ursprünglich identifizierte Fälle bestätigt behoben), 5 neue
Unit-Tests, pytest 34/34 grün."

**Nachtrag — Audit "alle möglichen Fälle" (auf User-Anweisung):** Codebasis nach weiteren
Stellen durchsucht, an denen dieselbe Quotierungsregel (Ziffernbeginn -> quotiert) zu
einem False-Negative führen könnte. Ergebnis:
- **Namenskonventions-Checks** (`naming.py`, Regex/Präfix gegen `db.Name`/`tag.Name`/
  `block.Name`/`constant.Name`): nicht betroffen — Top-Level-Objektnamen (DBs, Bausteine,
  Tags) werden von TIA laut Beobachtung im Salzmaschine-Projekt (`01AlmDb`, `40AlmDb` —
  beide mit Ziffer beginnend) **nicht** quotiert, nur zusammengesetzte Interface-Member-
  Pfade (`Interface.Member.Name`, das eine gültige IEC-Zugriffs-Notation abbildet).
- **`libraries.py::VerwaisteInstanzDbsCheck`** (`InstanceOfName` gegen FB-Namen-Set):
  nicht betroffen — vergleicht zwei Top-Level-Bausteinnamen, kein Member-Pfad.
- **`_tia_helpers.py::find_source_child_by_name`** (genutzt von Prüfpunkt 26
  `static_zugriff_extern` und 27 `output_mehrfach_beschrieben`): **betroffen, gehärtet.**
  Vergleicht einen aus dem XML-Export gewonnenen (unquotierten) Membernamen gegen
  `child.Name` aus dem Kreuzreferenzbaum — Letzteres kann für Interface-Member mit
  Ziffernbeginn ebenfalls quotiert sein (derselbe Mechanismus wie bei
  `Interface.Member.Name`, da beide dieselbe IEC-Zugriffs-Notation abbilden). Fix: Fällt
  auf einen Vergleich über `normalize_member_path(child.Name) == name` zurück, wenn der
  direkte Vergleich nicht trifft. **Nicht live gegen einen tatsächlich betroffenen Fall
  verifiziert** (im Salzmaschine-Projekt kein bekannter Static-/Output-Member mit
  Ziffernbeginn gefunden) — defensiv nach demselben, zweimal bestätigten Muster
  umgesetzt.
- 4 neue Unit-Tests (`TestFindSourceChildByName`), `pytest`: 38/38 grün.

Letzter Stand: "Normalisierungs-Audit abgeschlossen — ein weiterer betroffener Ort
(`find_source_child_by_name`, Prüfpunkte 26/27) gefunden und gehärtet (nicht live
verifiziert, da kein passender Fall im Testprojekt vorhanden), alle anderen
Namensvergleiche in der Codebasis geprüft und als nicht betroffen bestätigt. pytest
38/38 grün."

**Committed & gepusht:** Commit `26a9425` "Fix quoted-identifier mismatch in DB-member
comment lookup and cross-reference matching" auf `main` (`9702eb1..26a9425`),
Repo: https://github.com/Thomas-Schlangen/tia-linter. Analoger Fix zusätzlich im
Schwesterprojekt `tia-tag-exporter` ergänzt und gepusht (Commit `090b9ee`, dort
`get_hmi_comment`-Lookup gehärtet — dritter, dort bislang nicht abgesicherter Ort mit
demselben Muster).

## Runde 15 — Dritter Kommentar-Bug: Instanz-DB-Member erben Kommentar von der Quell-FB

**Bug (User-Meldung):** Sämtliche Kommentare in Instanz-DBs wurden nicht erkannt. User-
Vermutung: Der Kommentar steht nicht in der Instanz-DB selbst, sondern wird vom
zugehörigen FB "geerbt" — mit dem expliziten Hinweis, dass die bestehende Logik nicht
ersetzt werden darf, da ein geerbter Kommentar in der Instanz-DB auch lokal überschrieben
werden kann (dann gilt der Instanz-DB-eigene Kommentar): erst den Instanz-DB-eigenen
Kommentar prüfen, nur bei Fehlen den geerbten nachschlagen.

**Verifiziert (isoliertes Diagnoseskript gegen 5 der 11 Instanz-DBs im Salzmaschine-
Projekt):** Hypothese bestätigt. Bei `LSNTP_ServerDb` (Quell-FB `LSNTP_Server`) waren 40
von 136 geprüften Membern nur unter dem ViewPath der Quell-FB in den Projekttexten zu
finden, nicht unter der Instanz-DB selbst (Beispiele: `init` -> "Initialize connection.
...", `error` -> "An error occured"). Bei `PlcTimeDb` (Quell-FB `PlcTime`) waren es 2 von
12 (`ot_LocalTime` -> "Lokalzeit", `ot_PlcTime` -> "Systemzeit"). Bei den übrigen 3
untersuchten Instanz-DBs (`PrgFieldbusOkDb`, `40AlmDb`, `40VisDb`) fand sich kein Treffer
über die FB — plausibel, da deren Quell-FBs an den geprüften Membern schlicht auch keine
Kommentare hinterlegt haben (kein Widerspruch zur Hypothese).

**Fix** (`src/tia_linter/checks/comments.py`, `VariablenKommentarCheck`): Pro DB wird
einmalig `instance_of = db.GetAttribute("InstanceOfName")` ermittelt (identische Auflösung
wie in `bibliotheken.verwaiste_instanz_dbs`). Der bestehende Lookup unter dem
Instanz-DB-eigenen Namen bleibt unverändert die erste Prüfung — **nur** wenn der keinen
Treffer liefert UND `instance_of` nicht leer ist, wird zusätzlich unter dem Namen der
Quell-FB nachgeschlagen. Ein überschriebener Instanz-DB-Kommentar hat damit weiterhin
Vorrang, wie vom User gefordert; nicht-Instanz-DBs (leeres `InstanceOfName`) sind vom
Fallback unberührt.

**Verifiziert gegen das echte Salzmaschine-Projekt** (voller
`VariablenKommentarCheck`-Lauf über alle 11 Instanz-DBs, nicht nur die 5 diagnostizierten):
**4.704 Befunde statt vorher 4.766** (Differenz 62 — mehr als die in der Diagnose
gefundenen 42, da der volle Lauf alle 11 statt nur 5 Instanz-DBs abdeckt). Stichprobe der
verbleibenden Befunde bei `LSNTP_ServerDb`/`PlcTimeDb` (96 bzw. 10) zeigt ausschließlich
plausible, tatsächlich unkommentierte Elementarfelder (z. B. `lastTimeSet.YEAR`,
`lt_LastTime.MONTH` — Unterfelder von DTL-/Zeit-Structs, typischerweise ohne
Einzelkommentar) — keine erkennbaren falschen Negativfunde mehr.

Kein neuer Unit-Test ergänzt: `VariablenKommentarCheck.run()` benötigt für einen
Check-Level-Test ein vollständiges `project`-Objekt (`LanguageSettings`,
`ExportProjectTexts()` usw.), das ohne echte TIA-Verbindung nicht sinnvoll faken lässt —
konsistent mit dem bisherigen Testumfang der Codebasis (nur die reinen
`_tia_helpers.py`-Funktionen sind mit Fake-Objekten unit-getestet, Check-Klassen werden
ausschließlich gegen das echte Projekt verifiziert). `pytest`: weiterhin 38/38 grün
(unverändert, da keine `_tia_helpers.py`-Funktion angepasst wurde).

Letzter Stand: "Dritter Kommentar-Bug (Instanz-DB-Member erben Kommentar von der
Quell-FB) behoben und gegen das echte Salzmaschine-Projekt verifiziert (4.766 → 4.704
Befunde, Hypothese an zwei konkreten Instanz-DBs mit Beispieltexten bestätigt), Vorrang
des überschriebenen Instanz-DB-Kommentars erhalten."

**Committed & gepusht:** Commit `26a9425` (Quotierungs-Fix, siehe oben) sowie die
Instanz-DB-Vererbung (kein separater Commit-Hash dokumentiert — im Rahmen der laufenden
Session weiterverarbeitet, siehe Runde 16 unten für den gemeinsamen Commit-Stand).

## Runde 16 — Neuer Prüfpunkt 1b "UDT ohne Kommentar" (auf User-Anweisung)

**Ausgangspunkt (User-Meldung):** Viele Warnungen von Prüfpunkt 1 stammten von Items
*innerhalb* eines UDT-typisierten DB-Members — jedes einzelne Feld eines UDT wurde
zusätzlich zum UDT-Member selbst einzeln bemängelt. Auftrag: analog zur bereits
bestehenden Array-Behandlung sollen UDT-Items ab sofort von Prüfpunkt 1 ausgenommen
werden (Kommentar auf dem UDT-Member selbst reicht), dafür aber ein **neuer, eigener
Prüfpunkt "UDT ohne Kommentar"** direkt nach Prüfpunkt 1 ergänzt werden, der sowohl den
UDT-Kommentar selbst als auch die Kommentare aller seiner Items prüft — verschachtelte
UDT-Items werden dabei nicht rekursiv weiter geprüft, da das verschachtelte UDT bei der
äußeren Schleife ohnehin eigenständig geprüft wird.

**Untersuchung des PlcType-Objektmodells** (zwei isolierte Diagnoseläufe gegen das echte
Salzmaschine-Projekt, da die V21-Openness-Referenz `PlcType.Interface` nicht mit
Codebeispiel belegt):
- `plcSoftware.TypeGroup` (`PlcTypeSystemGroup`) mit `.Types`/`.Groups` — strukturell
  identisch zu `BlockGroup`/`TagTableGroup` (bestätigt per Referenz, Abschnitt "Auf
  PLC-Datentypen und Datentypgruppen zugreifen"). Live verifiziert: 154 UDTs im Projekt,
  0 davon direkt im Root, alle in Untergruppen (`TypeProject`, `DataTypes/BibMan`,
  `DataTypes/BibAlpma`, ...).
- `PlcType.Comment` funktioniert wie `PlcBlock.Comment` direkt über `read_comment()`
  (mehrsprachiges `MultilingualText`, V21-Referenz nennt `PlcType` explizit unter
  "Mehrsprachige Titel und Kommentare") — live an UDT `U_SpMani` verifiziert:
  `read_comment(udt, language)` und der Wert aus den Projekttexten
  (`Kommentar zum PLC-Datentyp`-Pseudo-Zeile) lieferten identisch `'0'`. Die ursprünglich
  befürchtete Notwendigkeit eines fragilen, sprachabhängigen Literal-String-Workarounds
  (`"Kommentar zum PLC-Datentyp"`) entfiel dadurch — `read_comment()` ist robuster
  (sprachunabhängig) und wird stattdessen verwendet.
- `PlcType.Interface.Members` funktioniert genauso wie `PlcBlock.Interface.Members`/
  `DataBlock.Interface.Members`. UDT-Member-Kommentare liegen unter derselben
  Projekttexte-Kategorie (`<BlockCommentCategoryData>`) mit ViewPath
  `{Projekt}\{PLC}\PLC-Datentypen\...\{UDT-Name}\{Member}` — der bestehende, generische
  `ProjectTextComments`-Parser (positionsbasiert, nicht kategorietyp-bewusst) erfasst das
  bereits transparent mit, ohne Änderung an `project_texts.py`.

**Fix umgesetzt:**
- `_tia_helpers.py`: neue Funktion `iter_plc_types()` (rekursive UDT-Traversierung,
  analog zu `iter_blocks`/`iter_tag_tables`).
- `comments.py`, `VariablenKommentarCheck`: pro `plc_software` wird einmalig
  `udt_names = {t.Name for t, _ in iter_plc_types(...)}` gesammelt; beim Durchlaufen der
  DB-Member wird nach jedem geprüften Member dessen `DataTypeName` gegen `udt_names`
  abgeglichen — Treffer registriert den Membernamen als "Skip-Präfix", alle
  nachfolgenden Member mit diesem Präfix (+ `.`) werden übersprungen (das UDT-Member
  selbst bleibt geprüft, wie bei Arrays).
- `comments.py`: neue Klasse `UdtKommentarCheck` (Prüfpunkt 1b) — iteriert alle UDTs,
  prüft `read_comment(udt, language)` für den Header sowie `project_texts.get(...)` für
  jedes Interface-Member (mit identischer Array-Skip- und verschachtelter-UDT-Skip-Logik
  wie oben). Direkt nach `VariablenKommentarCheck` im Code und in `CHECK_REGISTRY`
  positioniert (`kommentare.udt_kommentar`, Key direkt nach `variablen_kommentar`).
- `config/default.yaml`: neuer Eintrag `checks.kommentare.udt_kommentar` (enabled: true,
  severity: warning, `ausnahme_prefixe: ["_"]`, analog zu `variablen_kommentar`) direkt
  nach `variablen_kommentar`.

**Bug beim ersten Verifikationsversuch gefunden und behoben:** Erster Testlauf zeigte
`variablen_kommentar` unverändert bei 4.704 Befunden — die UDT-Erkennung griff nicht.
Ursache (per gezieltem Diagnoseskript gefunden): `member.GetAttribute("DataTypeName")`
liefert UDT-Referenzen **immer** in Anführungszeichen (z. B. `'"U_VisBit"'` statt
`'U_VisBit'`) — unabhängig davon, ob der UDT-Name selbst eine Quotierung bräuchte (anders
als beim Quotierungs-Bug aus Runde 14, der nur ziffernbeginnende Namen betraf). Fix:
`normalize_member_path()` zusätzlich auf `DataTypeName` vor dem Abgleich gegen
`udt_names` angewendet (an beiden Stellen, `VariablenKommentarCheck` und
`UdtKommentarCheck`).

**Verifiziert gegen das echte Salzmaschine-Projekt** (mehrere isolierte Testläufe):
- `variablen_kommentar`: **2.915 Befunde statt vorher 4.704** (Differenz 1.789 — die
  UDT-Skip-Logik betrifft breite Teile des Projekts, plausibel bei 154 UDTs und
  verbreiteten Typen wie `U_VisBit`).
- `udt_kommentar`: **146 Befunde** (145 UDT-Header ohne Kommentar, 1 UDT-Member ohne
  Kommentar) — keine Exceptions, plausible Verteilung (viele UDTs ohne Header-Kommentar,
  aber die meisten UDT-Member sind offenbar gut kommentiert).
- Stichprobenprüfung auf verbleibende "UDT-Leaks" in `variablen_kommentar`: die 24
  gefundenen Kandidaten erwiesen sich beim Nachprüfen als falscher Treffer des eigenen,
  zu groben Suchmusters (Substring `"Ena"` traf auch unverwandte Feldnamen wie
  `"EnaMan"`/`"EnaRamp2Man"`) — keine echten UDT-Item-Leaks mehr gefunden.
- `pytest`: weiterhin 38/38 grün (keine `_tia_helpers.py`-Funktion mit Fake-Objekt-Tests
  betroffen, `iter_plc_types()` neu aber ungetestet aus demselben Grund wie
  `VariablenKommentarCheck`/`UdtKommentarCheck` — Check-Level-Verifikation ausschließlich
  gegen das echte Projekt, konsistent mit dem bisherigen Testumfang).

**Dokumentation ergänzt:**
- `README.md`: Kategorietabelle um "(inkl. 1b, siehe unten)" ergänzt, neuer Absatz
  analog zum bestehenden 12b-Absatz, der Prüfpunkt 1b erklärt.
- `docs/Handbuch.md`: neue vollständige Prüfpunkt-1b-Sektion in Abschnitt 10.1 (nach dem
  einheitlichen Schema: Was/Warum/Parameter/Beispiel/Besonderheiten/Empfehlung),
  Querverweis in Prüfpunkt 1s Besonderheiten, Abschlusshinweis am Ende von Kapitel 10
  aktualisiert, Änderungshistorie (Anhang C) um Version 0.15 ergänzt, Handbuch-Kopf auf
  0.15/18.07.2026 gesetzt.

Letzter Stand: "Neuer Prüfpunkt 1b (UDT ohne Kommentar) implementiert und gegen das echte
Salzmaschine-Projekt verifiziert (variablen_kommentar 4.704 → 2.915, udt_kommentar 146
neue Befunde), inkl. eines während der Verifikation gefundenen und behobenen
Zweitbugs (DataTypeName-Quotierung). README und Handbuch aktualisiert. pytest 38/38
grün."

## Runde 17 — `.gitignore` für lokale Config, neuer Parameter `ausnahme_variables`

**`.gitignore`:** `config/project_settings.yaml` ergänzt (User hat sich eine lokale
Kopie von `default.yaml` als eigene Arbeits-Config angelegt, analog zum bestehenden
`config.yaml`-Eintrag).

**Neuer Parameter `ausnahme_variables`** bei `kommentare.variablen_kommentar`
(`VariablenKommentarCheck`, `comments.py`): Liste vollständiger Variablennamen (exakte
Übereinstimmung, kein Präfix-/Teilstring-Abgleich wie bei `ausnahme_prefixe`), die von
der Prüfung ausgenommen werden — gilt für PLC-Tags und DB-Member gleichermaßen (bei
DB-Membern inkl. Punktpfad, z. B. `"Alm.Station_1"`). Bewusst nur bei `variablen_kommentar`
ergänzt (User-Anweisung), nicht bei `udt_kommentar`. `config/default.yaml` (Standard `[]`,
Beispiele auskommentiert), `docs/Handbuch.md` (neue Parameter-Zeile bei Prüfpunkt 1,
Version 0.16) aktualisiert. Rückwärtskompatibel: Fehlt der Schlüssel in einer bestehenden
Config (z. B. der jetzt ignorierten `project_settings.yaml` des Users), degradiert
`params.get("ausnahme_variables", [])` sauber zu "keine Ausnahmen" statt abzustürzen.

**Verifiziert gegen das echte Salzmaschine-Projekt:** `System_Byte` (bekannt
unkommentiert, Default-Tag-Tabelle) über `ausnahme_variables: ["System_Byte"]`
ausgeschlossen — Ergebnis sank exakt um 1 (2.915 → 2.914), `System_Byte` taucht in den
Befunden nicht mehr auf. Kein isolierter Unit-Test (einfache Set-Mitgliedschaftsprüfung,
Check-Level-Logik wird konsistent mit dem übrigen Testumfang nur gegen das echte Projekt
verifiziert). `pytest`: weiterhin 38/38 grün.

Letzter Stand: "`.gitignore` und neuer Parameter `ausnahme_variables` umgesetzt, gegen
das echte Projekt verifiziert (exakt 1 Befund weniger nach Ausschluss von
'System_Byte'), Config/Handbuch dokumentiert. pytest 38/38 grün."

**Committed & gepusht:** Commit `a49ee62` (zusammen mit Runde 16, UDT-Check) auf `main`
(`26a9425..a49ee62`), Repo: https://github.com/Thomas-Schlangen/tia-linter. User hat
danach in `config/default.yaml` selbst `ausnahme_prefixe` von `["_"]` auf `["__"]`
geändert (einfacher Unterstrich in der Praxis als Präfix oft ungeeignet, da häufig
verwendet, um Ziffernbeginn bei Variablennamen zu vermeiden) — im selben Commit
enthalten.

## Runde 18 — Neuer Parameter `ausnahme_udts`

**Auftrag (User-Meldung):** Manche UDTs bzw. System-Datentypen sind in TIA Portal
nirgends sichtbar definiert — ihr Inneres kann daher grundsätzlich nicht geprüft werden
(auch nicht über Prüfpunkt 1b, das nur im Projekt sichtbare UDTs findet). Solche
Datentypen sollen ebenfalls von der inneren Prüfung ausgenommen werden können. Bewusst
nicht `ausnahme_system_udts` genannt, damit Anwender später auch eigene, sichtbare UDTs
aus anderen Gründen darüber ausnehmen können.

**Fix** (`src/tia_linter/checks/comments.py`, `VariablenKommentarCheck`, ausschließlich
dort — nicht bei `UdtKommentarCheck`, wie vom User vorgegeben): neuer Parameter
`ausnahme_udts` (Liste von Datentypnamen). Die bestehende UDT-Erkennung
(`data_type_name in udt_names`) wurde zu `data_type_name in udt_names or data_type_name
in exception_udts` erweitert — ein manuell eingetragener Typname wirkt damit exakt wie
ein automatisch erkannter UDT (Member selbst bleibt geprüft, seine Items werden
übersprungen), unabhängig davon, ob der Typ tatsächlich in `iter_plc_types()` auffindbar
ist oder nicht.

**Konfiguration & Doku:** `config/default.yaml` (`ausnahme_udts: []`, auskommentierte
Beispiele `"TON"`/`"IEC_TIMER"`), `docs/Handbuch.md` (neue Parameter-Zeile bei
Prüfpunkt 1, Version 0.17 — dabei auch den dort noch veralteten Standardwert von
`ausnahme_prefixe` auf `["__"]` korrigiert).

**Verifiziert gegen das echte Salzmaschine-Projekt:** Diagnoselauf fand mehrere
DataTypeName-Werte, die nicht in `udt_names` auftauchen (also aktuell nicht automatisch
übersprungen werden) und keine Elementartypen sind — darunter plausible echte
Kandidaten für den beschriebenen Anwendungsfall (Systemtypen ohne sichtbare Definition):
`TON_TIME` (16x), `TOF_TIME` (12x), `HW_ANY`, `HW_IOSYSTEM`, `CONN_OUC`, `DNN`. Als
Test mit dem größten Effekt gewählt: `"Struct"` (anonyme Structs, 30x als Top-Level-
Membertyp) — mit `ausnahme_udts: ["Struct"]` sank `variablen_kommentar` von 2.914 auf
1.574 Befunde (1.340 weniger), Mechanismus bestätigt funktionsfähig für beliebige
`DataTypeName`-Werte. (Hinweis: `"Struct"` selbst ist kein empfohlener Standard-Eintrag
— anonyme Structs sollen laut bisheriger Konvention weiterhin einzeln geprüft werden;
diente hier nur als Testwert mit hohem Trefferaufkommen.)

`pytest`: weiterhin 38/38 grün (kein isolierter Unit-Test, gleiches Argument wie bei
`ausnahme_variables` — einfache Set-Erweiterung, Check-Level-Verifikation ausschließlich
gegen das echte Projekt).

Letzter Stand: "Neuer Parameter `ausnahme_udts` umgesetzt, dokumentiert und gegen das
echte Projekt verifiziert (Mechanismus bestätigt, 1.340 Befunde weniger mit Testwert
'Struct'; echte Kandidaten für den beschriebenen Anwendungsfall identifiziert:
TON_TIME/TOF_TIME/HW_ANY/HW_IOSYSTEM/CONN_OUC/DNN). pytest 38/38 grün."

**Committed & gepusht:** Commit `76e497b` auf `main` (`a49ee62..76e497b`),
Repo: https://github.com/Thomas-Schlangen/tia-linter.

## Runde 19 — Sechster Kommentar-Bug: UDT-Erkennung griff nicht bei zusätzlich ausgenommenen Membern

**Bug (User-Meldung nach eigenem Testlauf):** `ausnahme_udts` mit `"DTL"` sollte
`LSNTP_ServerDb > lastTimeSet` (und seine Items `lastTimeSet.YEAR` usw.) von der
Prüfung ausnehmen — die Items wurden aber weiterhin einzeln als "kein Kommentar"
gemeldet.

**Erste Fehlsuche ergebnislos:** Isolierter Test von `LSNTP_ServerDb` mit
`config/default.yaml` zeigte 0 Treffer für `lastTimeSet` — Mechanismus schien
korrekt. Erst ein Test mit der tatsächlichen `config/project_settings.yaml` des
Users reproduzierte den Bug (8 verbleibende Kind-Befunde). Unterschied gefunden:
`ausnahme_variables` enthielt zusätzlich `"lastTimeSet"` (vermutlich ein eigener
Workaround-Versuch des Users, weil `ausnahme_udts` nicht griff).

**Ursache:** In `VariablenKommentarCheck`/`UdtKommentarCheck` kam der
`continue`-Zweig für `ausnahme_prefixe`/`ausnahme_variables` **vor** der
UDT-Erkennung (`data_type_name in udt_names or data_type_name in exception_udts` →
`skip_prefixes.append(member_name)`). Ein Member, das per Präfix oder
`ausnahme_variables` von der eigenen Kommentarprüfung ausgenommen wurde, sprang also
direkt zum nächsten Member, **bevor** sein `DataTypeName` überhaupt geprüft und als
Skip-Präfix registriert werden konnte — seine Items blieben dadurch ungeschützt.
Trat nur auf, wenn eine UDT-typisierte Variable *zusätzlich* über
`ausnahme_prefixe`/`ausnahme_variables` ausgenommen war (der isolierte Test ohne
diese Zusatz-Ausnahme hatte den Bug deshalb nicht gezeigt).

**Nebenbefund während der Fehlersuche:** Das lokale `.venv` enthielt zwischenzeitlich
nur noch `pip` — alle Abhängigkeiten (inkl. `pydantic`, `pytest`) fehlten. Ursache
nicht ermittelt (vermutlich versehentlich durch den User beim eigenen Testen
geleert). Mit `pip install -e .` + `pip install pytest` neu aufgesetzt, kein
Zusammenhang mit dem eigentlichen Bug.

**Fix** (`src/tia_linter/checks/comments.py`, beide Klassen): Die UDT-Erkennung
(`data_type_name`-Abgleich + `skip_prefixes.append(...)`) wurde vor die
`ausnahme_prefixe`/`ausnahme_variables`-Continues verschoben — sie läuft jetzt für
jedes Member unabhängig davon, ob das Member selbst später einen eigenen Befund
bekommt. Nur ob das Member *selbst* geprüft/gemeldet wird, hängt weiterhin von den
Ausnahme-Parametern ab; ob seine Items übersprungen werden, hängt ausschließlich vom
`DataTypeName` ab. Derselbe Strukturfehler wurde vorsorglich auch in
`UdtKommentarCheck` behoben (dort mit `ausnahme_prefixe` allein reproduzierbar,
sofern ein UDT-Item selbst wieder UDT-typisiert **und** präfix-ausgenommen ist) —
nicht separat vom User gemeldet, aber dieselbe Fehlerklasse.

**Verifiziert gegen das echte Salzmaschine-Projekt** (mit der echten
`project_settings.yaml` des Users, `ausnahme_variables` inkl. `"lastTimeSet"`
weiterhin gesetzt): beide DTL-typisierten Member im Projekt (`LSNTP_ServerDb.lastTimeSet`,
`PlcTimeDb.lt_LastTime`) liefern jetzt 0 verbleibende Kind-Befunde; eine generische
Suche nach allen klassischen DTL-Feldnamen (`.YEAR`, `.MONTH`, `.DAY`, `.WEEKDAY`,
`.HOUR`, `.MINUTE`, `.SECOND`, `.NANOSECOND`) über sämtliche 2.814 Befunde findet
keinen einzigen Treffer mehr.

`docs/Handbuch.md` (Besonderheiten von Prüfpunkt 1, Version 0.18) klargestellt, dass
die UDT-Erkennung unabhängig von `ausnahme_prefixe`/`ausnahme_variables` wirkt.
`pytest`: weiterhin 38/38 grün (kein isolierter Unit-Test für dieses spezifische
Zusammenspiel — wie bei den anderen Ausnahme-Parametern nur Check-Level-Verifikation
gegen das echte Projekt).

Letzter Stand: "Sechster Kommentar-Bug (UDT-Erkennung griff nicht bei zusätzlich per
ausnahme_prefixe/ausnahme_variables ausgenommenen Membern) behoben, mit der echten
Config des Users gegen das Salzmaschine-Projekt verifiziert (0 verbleibende
DTL-Kind-Befunde, projektweite Generic-Suche negativ), Handbuch aktualisiert. pytest
38/38 grün."

**Committed & gepusht:** Commit `33136db` auf `main` (`76e497b..33136db`),
Repo: https://github.com/Thomas-Schlangen/tia-linter.

## Runde 20 — Siebter Kommentar-Bug: Multi-Instanz-FB-Aufrufe wie UDT-Member behandelt, neuer Prüfpunkt 1c

**Bug (User-Meldung):** "Keine Prüfung in die Items eines UDTs, wenn die Variable vom
UDT-Typ ist" (Grundprinzip aus Runde 16) griff bei `4805PrgManDb > Man4805_27M11.ix_BoxIdOk`
nicht — `Man4805_27M11` ist laut User "eine Instanzvariable vom UDT-Typ ManStFcPump".
Tritt laut User sehr häufig auf.

**Ursache (live verifiziert):** `ManStFcPump` ist **kein PLC-Datentyp (UDT)**, sondern
ein **Funktionsbaustein (FB)** — `Man4805_27M11` ist eine **Multi-Instanz** dieses FB
innerhalb der Instanz-DB `4805PrgManDb`. Architektonisch dieselbe
`Interface.Members`-Flachklopfung mit Punktpfaden wie bei UDTs, aber ein technisch
anderer Mechanismus, den `iter_plc_types()` (nur echte PLC-Datentypen) korrekterweise
nicht erfasst. Bestätigt: `'ManStFcPump' in udt_names` → `False`,
`'ManStFcPump' in fb_names` → `True`.

**Rückfrage an den User** (echte Design-Entscheidung, kein reiner Bugfix): Sollen
Multi-Instanz-FB-Member nur übersprungen werden (bewusste Lücke wie bei
System-UDTs), oder zusätzlich ein neuer Prüfpunkt analog zu 1b ergänzt werden, der die
FB-Interface-Member-Kommentare stattdessen prüft? User-Antwort: **beides** — überspringen
UND neuer Prüfpunkt, damit keine Abdeckungslücke entsteht.

**Fix Teil 1** (`VariablenKommentarCheck`): `fb_names` (analog zu `udt_names`, aus allen
FBs der PLC-Software über `isinstance(block, FB)`) zusätzlich in die Skip-Erkennung
einbezogen — ``data_type_name in udt_names or data_type_name in exception_udts or
data_type_name in fb_names``.

**Fix Teil 2 — neuer Prüfpunkt 1c** (`kommentare.fb_member_kommentar`,
`FbMemberKommentarCheck`): prüft die Interface-Member-Kommentare eines FB direkt an der
Definition (nicht der FB-Kopfkommentar, der bleibt Sache von Prüfpunkt 2).

**Zweiter, unabhängiger Bug während der Implementierung gefunden:** Erste Fassung von
`FbMemberKommentarCheck` (analog zu `UdtKommentarCheck`, über `fb.Interface.Members`)
lieferte 0 Befunde projektweit. Live-Diagnose: **alle 127 FBs** des Salzmaschine-Projekts
liefern über `Interface.Members` direkt auf dem FB-Objekt eine **leere Liste** — auch
`ManStFcPump` selbst (0 Members), obwohl über die Instanz `Man4805_27M11` klar sichtbar
~150 Member existieren. Kein Know-how-Schutz (`IsKnowHowProtected=False` bei allen 127
FBs) — also keine Sicherheitsfunktion, sondern eine grundsätzliche Einschränkung der
Openness-API: Anders als `DataBlock.Interface.Members` und `PlcType.Interface.Members`
(beide bereits live bestätigt funktionsfähig) liefert `PlcBlock.Interface.Members` für
FBs über die direkte Objektnavigation offenbar nie Ergebnisse. Dieselbe Einschränkung
hatte bereits `styleguide.static_zugriff_extern`/`styleguide.output_mehrfach_beschrieben`
dazu gezwungen, Interface-Member-Namen stattdessen aus dem XML-Export zu lesen (siehe
``interface_section_members`` in ``_tia_helpers.py``) — bisher aber nirgends explizit als
generelle FB-Einschränkung dokumentiert, nur implizit in diesen beiden Checks umgangen.

**Fix:** `FbMemberKommentarCheck` komplett auf den XML-Export-Mechanismus umgestellt —
`interface_section_members(export_block_xml(block), section_name)` für die vier Sections
`Input`/`Output`/`InOut`/`Static` (bewusst ohne `Temp`, da Temp-Variablen zwischen
Aufrufen nicht persistieren). Da der XML-Export nur direkt deklarierte Member liefert
(keine rekursive Auflösung), ist hier keine Array-/UDT-Skip-Logik nötig — jedes Ergebnis
ist bereits ein einzelnes Member.

**Verifiziert gegen das echte Salzmaschine-Projekt** (mit der echten
`project_settings.yaml` des Users, `fb_member_kommentar` dort noch nicht enthalten →
für diesen Teil zusätzlich `config/default.yaml` herangezogen):
- `variablen_kommentar`: **117 Befunde statt vorher 2.814** (Differenz 2.697 —
  Multi-Instanz-FB-Verwendungen sind im Projekt sehr verbreitet, deckt sich mit der
  User-Angabe "tritt sehr häufig auf"). 0 verbleibende `Man4805_27M11`-Treffer.
- `fb_member_kommentar`: **1.816 Befunde**, davon 19 für `ManStFcPump` selbst
  (u. a. `MinusPrev`, `NoLimitPrev`, `id_MaxPortNbr`, `iou_GlobalMan` — plausible,
  echte Interface-Member-Namen, identisch zu den zuvor über die Instanz beobachteten).
  Keine Exceptions.

**Dokumentiert:** `README.md` (Kategorietabelle + Absatz analog zu 1b/12b, inkl. der
FB-Interface.Members-Einschränkung), `docs/Handbuch.md` (neue Prüfpunkt-1c-Sektion,
Querverweis bei Prüfpunkt 1, veralteten `ausnahme_prefixe`-Default bei 1b auf `["__"]`
korrigiert, Version 0.19), `config/default.yaml` (`checks.kommentare.fb_member_kommentar`).

**Hinweis für den User:** `config/project_settings.yaml` (lokale Kopie) enthält den
neuen Eintrag `fb_member_kommentar` noch nicht — muss dort manuell ergänzt werden
(siehe `config/default.yaml` als Vorlage), sonst bleibt der neue Prüfpunkt in der GUI
unsichtbar/inaktiv, obwohl er im Code vorhanden ist.

`pytest`: weiterhin 38/38 grün (kein isolierter Unit-Test — Check-Level-Verifikation
ausschließlich gegen das echte Projekt, konsistent mit dem bisherigen Testumfang).

Letzter Stand: "Siebter Kommentar-Bug (Multi-Instanz-FB-Aufrufe fälschlich einzeln
geprüft) behoben, neuer Prüfpunkt 1c (FB-Interface-Member ohne Kommentar) ergänzt —
inkl. eines während der Implementierung gefundenen Zweitbugs (FB.Interface.Members
liefert grundsätzlich leer, XML-Export als Workaround). Gegen das echte
Salzmaschine-Projekt verifiziert (variablen_kommentar 2.814 → 117, fb_member_kommentar
1.816 neue Befunde). README/Handbuch/Config aktualisiert. User muss
project_settings.yaml manuell um den neuen Check-Eintrag ergänzen."

## Runde 21 — Redundanz zwischen Prüfpunkt 1 und 1c behoben (Brainstorming, Plan-Modus)

**Ausgangspunkt:** User stellte im Anschluss an Runde 20 eigene Entscheidungen in Frage
(Brainstorming über die Erklärung des XML-Export-Umwegs für FBs) und fragte gezielt:
"Macht es Sinn, die Variablen eines FB zu prüfen, wenn wir sowieso die IDB checken?
Oder umgekehrt?" — mit der Vermutung, dass nur eines von beiden sinnvoll ist.

**Analyse:** Tatsächliche Redundanz bestätigt, aber nur für *eigenständige* Instanz-DBs
(nicht für die bereits in Runde 20 übersprungenen verschachtelten Multi-Instanzen
innerhalb einer DB): Prüfpunkt 1 prüfte weiterhin jedes Member einer Instanz-DB einzeln
(mit dem Runde-15-Fallback auf den FB-Kommentar), während Prüfpunkt 1c dieselben Member
zusätzlich direkt an der FB-Definition prüfte. Fehlte ein FB-Member-Kommentar komplett,
entstanden zwei Befunde für dasselbe Grundproblem — bei mehrfach instanziierten FBs
sogar mehrfach.

**Empfehlung (in einem eigenen Plan-Modus-Durchlauf erarbeitet und vom User zu 100%
bestätigt):** Nur Prüfpunkt 1c soll FB-Interface-Member-Kommentare prüfen. Prüfpunkt 1
schließt Instanz-DBs komplett von der Member-Prüfung aus (nicht nur die verschachtelten
Multi-Instanz-Fälle) — der Fallback-Mechanismus aus Runde 15 entfällt dadurch vollständig.
Ausdrücklich **kein** Prüfpunkt wird dabei aus der Registry entfernt — 1, 1b und 1c
bleiben alle bestehen und decken weiterhin unterschiedliche Variablen-Kategorien ab
(PLC-Tags + Global-DB-Member bei 1, UDT-Member bei 1b, sämtliche FB-Member — jetzt
inkl. der zuvor bei 1 geprüften Instanz-DB-Member — bei 1c). Entfernt wird nur ein
Stück Logik *innerhalb* von Prüfpunkt 1.

**Tradeoff (User-Anweisung: dokumentieren):** TIA erlaubt es, den geerbten FB-Kommentar
an einer einzelnen Instanz zu überschreiben. Ein solcher instanzspezifischer Kommentar
wird nach dieser Änderung nicht mehr erkannt — nur der Kommentar an der FB-Definition
zählt für die Prüfung. Bewusst in Kauf genommen zugunsten von weniger Redundanz/Rauschen.

**Fix** (`src/tia_linter/checks/comments.py`, `VariablenKommentarCheck`): Im DB-Loop
wird direkt nach `db_name = db.Name` geprüft, ob `db.GetAttribute("InstanceOfName")`
nicht leer ist — falls ja, wird die komplette Member-Schleife für diese DB übersprungen
(`continue` auf DB-Ebene). Die bisherige Fallback-Lookup-Logik (Instanz-DB-Kommentar →
bei Fehlen zusätzlich unter dem FB-Namen nachschlagen) wurde komplett entfernt.
Docstring aktualisiert: "Dritter Bug" als historisch/ersetzt markiert, neuer Abschnitt
"Achter Bug/Design-Entscheidung" beschreibt die Vereinheitlichung inkl. Tradeoff.
`FbMemberKommentarCheck`-Docstring ergänzt: deckt jetzt explizit auch eigenständige
Instanz-DBs ab, nicht nur verschachtelte Multi-Instanzen.

**Verifiziert gegen das echte Salzmaschine-Projekt:**
- `variablen_kommentar`: **2 Befunde statt vorher 117** — alle drei bekannten
  Instanz-DB-Beispiele (`LSNTP_ServerDb`, `PlcTimeDb`, `4805PrgManDb`) liefern jetzt 0
  Befunde, wie erwartet.
- `fb_member_kommentar`: unverändert bei **1.816 Befunden** — bestätigt, dass diese
  Änderung ausschließlich Prüfpunkt 1 betrifft, 1c war unabhängig davon schon vorher
  korrekt und vollständig.
- `pytest`: weiterhin 38/38 grün.

**Dokumentiert:** `docs/Handbuch.md` (Besonderheiten bei Prüfpunkt 1 und 1c inkl.
Tradeoff, Version 0.20), `README.md` (Prüfpunkt-1c-Absatz um Instanz-DB-Abdeckung und
Tradeoff erweitert).

**Offener Punkt aus dem Brainstorming, noch nicht bearbeitet:** Liefert
`fc.Interface.Members` direkt Ergebnisse, oder braucht es wie bei FB den
XML-Export-Umweg? Noch nicht live getestet (siehe `OutputMehrfachBeschriebenCheck`,
das FC schon vorsorglich wie FB behandelt, ohne dass das für FC bestätigt ist) —
separat vom User als "muss definitiv noch getestet werden" vermerkt.

Letzter Stand: "Redundanz zwischen Prüfpunkt 1 und 1c behoben (Instanz-DBs werden bei
Prüfpunkt 1 komplett übersprungen, Runde-15-Fallback entfernt), gegen das echte Projekt
verifiziert (variablen_kommentar 117 → 2, fb_member_kommentar unverändert bei 1.816),
Tradeoff in Handbuch/README dokumentiert. pytest 38/38 grün. Offen: FC-Interface.Members-Test."

**Committed & gepusht:** Commit `122e5d0` auf `main` (`33136db..122e5d0`),
Repo: https://github.com/Thomas-Schlangen/tia-linter. Danach `config/project_settings.yaml`
(lokale, gitignorte Config des Users) manuell um den `fb_member_kommentar`-Eintrag ergänzt.

**Offene Frage geklärt (kein Code-Fix, nur Verifikation):** `fc.Interface.Members`
liefert live ebenfalls immer eine leere Liste — an allen 124 FCs des Salzmaschine-Projekts
bestätigt (kein Know-how-Schutz). Der XML-Export-Umweg funktioniert dagegen überall
(z. B. `LGF_SearchMinMax`: 38 Member laut Export). Die Einschränkung betrifft also
Code-Bausteine allgemein (FB und FC), nicht nur FB — bestätigt, dass
`styleguide.static_zugriff_extern`/`styleguide.output_mehrfach_beschrieben` (die FC
schon vorher vorsorglich wie FB behandelt hatten) von Anfang an richtig lagen. Keine
Code-Änderung nötig.

## Runde 22 — 1 OK bei sauberem Prüfpunkt, Prüfpunkt-Nummer vor jeder Checkbox

**Ausgangspunkt:** User hatte den ersten Prüfpunkt fehlerfrei durchlaufen lassen und
fragte, warum die Zusammenfassung trotzdem "0 Fehler | 0 Warnungen | 0 OK" anzeigt —
erwartet hatte er bei "OK" einen anderen Wert als 0. Erklärt: der Linter meldet bisher
grundsätzlich nur Verstöße; "OK" ist bis auf Prüfpunkt 18c (Zertifikate, meldet pro
Objekt einen OK-Befund) faktisch ungenutzt. Zwei daraus resultierende Aufträge:
(1) Läuft ein Prüfpunkt komplett ohne Fehler/Warnung durch, soll er genau 1
zusammenfassenden OK-Befund melden. (2) In der GUI soll links vor jeder
Prüfpunkt-Checkbox die zugehörige Prüfpunkt-Nummer stehen (bei Checkboxen, hinter denen
zwei Prüfpunkte stecken, beide Nummern) — dafür links von den Checkboxen genug Platz
einplanen.

**Umsetzung Teil 1 (`src/tia_linter/runner.py`):** Neue Hilfsfunktion `_ok_result()`
direkt nach `_instantiate_check()` — baut ein `CheckResult` mit `CheckStatus.OK`,
`path=<Projektname>` und der Beschreibung "Keine Verstöße gegen '<Name>' gefunden.".
In `run_lint()` wird nach `check.run(project)` geprüft: liefert der Check eine leere
Liste, wird sie durch `[_ok_result(definition, resolved_project_name)]` ersetzt, bevor
sie an `results` angehängt wird. `simulate_lint_run()` bewusst unverändert gelassen
(reiner Testmodus ohne echte Prüfergebnisse).

**Umsetzung Teil 2 (Prüfpunkt-Nummer in der GUI):** Neues Feld `nummer: str` von
`CheckMeta` (`registry.py`) über `CheckDefinition` (`models.py`) bis zu `config.py`
durchgereicht (String statt int/Tupel wegen Buchstaben-Suffixen wie "18c" und weil
später auch mehrere Nummern an einer Stelle stehen könnten). Alle 44
`CheckMeta`-Einträge in `registry.py` um `nummer="..."` ergänzt (z. B. "1", "1b", "1c",
"18c", "35"). In `gui.py::rebuild_check_tree()` wird jede Checkbox jetzt in eine
Zeilen-`Frame` gepackt: links ein rechtsbündiges `ttk.Label` fester Breite (`width=6`)
mit der Nummer, rechts daneben die `ttk.Checkbutton`.

**Testanpassung:** Zwei bestehende `CheckDefinition(...)`-Testkonstruktoren in
`tests/test_models.py` um das neu erforderliche Feld `nummer` ergänzt (`"1"` bzw.
`"5"`).

**Verifiziert:**
- `pytest`: weiterhin 38/38 grün, `py_compile` auf allen geänderten Dateien fehlerfrei.
- Live gegen das echte Salzmaschine-Projekt über `run_lint()` mit zwei ausgewählten
  Prüfpunkten (`hardware.hardware_vorhanden`, `kommentare.variablen_kommentar`):
  Ausgabe "0 Fehler, 0 Warnungen, 2 OK", beide Ergebnisse mit Status `[ok]` und der
  erwarteten Beschreibung. Dabei aufgefallen: `variablen_kommentar` lieferte 0 statt der
  zuletzt in Runde 21 gemessenen 2 Befunde — per isoliertem Re-Check bestätigt, dass das
  keine Regression ist, sondern der reale Projektzustand sich seitdem geändert hat
  (User hat die verbleibenden 2 Fälle vermutlich selbst behoben).
- GUI-Smoketest (`TiaLinterApp` ohne `mainloop`, Checkbox-Baum aufgebaut): Stichprobe
  über 6 Prüfpunkt-IDs zeigt korrekte `nummer`-Werte (u. a. `"1"`, `"1b"`, `"1c"`,
  `"18c"`, `"12b"`, `"35"`), kein Fehler beim Aufbau. Kein Screenshot-Tool verfügbar —
  das tatsächliche visuelle Layout (Ausrichtung, Abstände) wurde dem User gegenüber
  ausdrücklich als ungeprüft benannt, nur der fehlerfreie Aufbau und der Inhalt der
  Labels wurden bestätigt.

**Dokumentiert:** `docs/Handbuch.md` (Abschnitt 4.4 "Wie ein Befund bewertet wird"
überarbeitet, Besonderheiten von Prüfpunkt 18c klargestellt, Abschnitt 6.2 um die neue
Nummern-Spalte ergänzt, Version 0.21). `README.md` bewusst nicht geändert — reine
Report-/GUI-Mechanik ohne eigenen README-Abschnitt zu Prüfergebnis-Status oder
GUI-Layout-Details.

Letzter Stand: "Prüfpunkte melden jetzt bei vollständig fehlerfreiem Durchlauf genau
1 zusammenfassenden OK-Befund statt keinen; jede Prüfpunkt-Checkbox in der GUI zeigt
links ihre Handbuch-Nummer(n). Beides live bzw. per Smoketest verifiziert, pytest
38/38 grün. Visuelles GUI-Layout dem User gegenüber als ungeprüft (kein
Screenshot-Tool) benannt."

## Runde 23 — Neunter Kommentar-Bug: UDT-/FB-Erkennung griff nicht mehr bei ausgeschlossenen Ordnern

**Ausgangspunkt (User-Meldung):** "Der Prüfpunkt 1 läuft jetzt nicht mehr fehlerfrei
durch, da ich sehr viele UDTs von der Prüfung ausgenommen habe (Ordner: ProjektLib).
Daraufhin checkt unser Code beim Prüfen der Variablen wieder in den UDT hinein, weil
unser Code den UDT nicht kennt. Aber nur weil ich einen Ordner zum Prüfen ausgenommen
habe, heißt es ja nicht, das wir den Inhalt nicht kennen müssen." — der User hatte über
`ausgeschlossene_ordner` einen ganzen Bibliotheksordner (`ProjectBib` in der lokalen
Config) von der Prüfung ausgenommen; danach tauchten wieder massenhaft Einzelbefunde
für Items *innerhalb* von UDTs/Multi-Instanz-FBs aus genau diesem Ordner auf.

**Ursache:** `VariablenKommentarCheck` und `UdtKommentarCheck` bauen intern je ein Set
`udt_names`/`fb_names`, gegen das der `DataTypeName` jedes Members abgeglichen wird, um
zu entscheiden, ob es sich um ein UDT-/FB-typisiertes Member handelt (dessen innere
Items dann bewusst nicht einzeln geprüft werden, siehe Prüfpunkt 1b/1c). Diese Sets
wurden bislang mit denselben `excluded_folders`/`excluded_blocks` gebaut wie die
eigentliche Iteration der zu prüfenden Objekte (`iter_plc_types(plc_software,
self.excluded_folders)` bzw. `iter_blocks(plc_software, self.excluded_folders,
self.excluded_blocks)`). Ein UDT/FB aus einem ausgeschlossenen Ordner tauchte dadurch
gar nicht erst in `udt_names`/`fb_names` auf — ein damit typisiertes Member wurde
folglich nicht als UDT/FB erkannt und seine Items wieder einzeln geprüft, obwohl
`ausgeschlossene_ordner` nur steuern soll, was selbst geprüft wird, nicht welche
Datentypen dem Linter zur Klassifizierung bekannt sind.

**Fix** (`src/tia_linter/checks/comments.py`): In `VariablenKommentarCheck.run()`
werden `udt_names`/`fb_names` jetzt über `iter_plc_types(plc_software)` bzw.
`iter_blocks(plc_software)` **ohne** Exclusion-Parameter gebaut — sie enthalten damit
immer alle UDTs/FBs der PLC-Software, unabhängig von `ausgeschlossene_ordner`/
`ausgeschlossene_bausteine`. Die eigentliche DB-Iteration (`iter_data_blocks(...,
self.excluded_folders, self.excluded_blocks)`) bleibt unverändert gefiltert — nur die
Klassifizierungs-Sets nicht mehr. Analoger Fix in `UdtKommentarCheck.run()` für die
Erkennung verschachtelter UDT-typisierter Items (`udt_names` dort ebenfalls ohne
`excluded_folders` gebaut, die äußere Iteration der selbst zu prüfenden UDTs bleibt
gefiltert). Docstring von `VariablenKommentarCheck` um einen neuen Abschnitt "Neunter
Bug" ergänzt.

**Verifiziert gegen das echte Salzmaschine-Projekt** (mit der lokalen
`project_settings.yaml` des Users, `ausgeschlossene_ordner: ["ProjectBib"]`):
- Vorher (Fix per `git stash` temporär entfernt): **927 Befunde** bei
  `variablen_kommentar` — durchweg Items innerhalb von UDT-/Multi-Instanz-Membern aus
  dem ausgeschlossenen Ordner `ProjectBib` (z. B. `"4805_6S10".Alm`,
  `"4805_15A1Prg".RstAlm`, ...).
- Nachher (Fix wiederhergestellt): **0 Befunde** — bestätigt, dass die UDT-/FB-Typen
  aus dem ausgeschlossenen Ordner jetzt wieder korrekt erkannt werden und ihre Items
  übersprungen werden.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Vor der Live-Verifikation lief noch ein `Siemens.Automation.Object`-Prozess (PID
  25560) — Rückfrage per `AskUserQuestion`, User entschied sich für "Prozess
  beenden"; anschließend die üblichen ~125s auf die Freigabe der TIA-Projektsperre
  gewartet.

**Dokumentiert:** `docs/Handbuch.md` (Besonderheiten von Prüfpunkt 1 in Abschnitt 10.1
um den Hinweis ergänzt, dass die UDT-/FB-Erkennung unabhängig von
`ausgeschlossene_ordner`/`ausgeschlossene_bausteine` wirkt; Version 0.22, neuer
Anhang-C-Eintrag). `README.md` bewusst nicht geändert — reiner Bugfix an bestehendem
Verhalten, keine neue Einstellung/kein neuer Parameter.

Letzter Stand: "Neunter Kommentar-Bug behoben: UDT-/FB-Typ-Erkennung in Prüfpunkt 1/1b
ignoriert jetzt ausgeschlossene Ordner/Bausteine, wie es sein soll — nur was selbst
geprüft wird, wird dadurch eingeschränkt, nicht was der Linter an Datentypen kennt.
Live verifiziert (927 → 0 Befunde bei ausgeschlossenem Ordner ProjectBib), pytest
38/38 grün."

## Runde 24 — Zehnter Kommentar-Bug: Multi-Instanz-Sub-Member leckten in Prüfpunkt 1c

**Ausgangspunkt (User-Meldung):** "Beim check (FB-Interface-Member ohne Kommentar)
stimmt noch etwas nicht. Im Baustein 01OrgPrg wurden die Member des Interfaces
gecheckt. Ein Member ist eine Multiinstanz: 'ReqRcp'. Leider werden alle Sub-Member
der Unterinstanz geprüft. Wir hatten aber gesagt, das wir das nicht tun." — genau die
Redundanz, die Prüfpunkt 1c laut seinem eigenen Docstring hätte ausschließen sollen
("keine rekursive Auflösung verschachtelter Struct-/UDT-/Array-Felder... jedes
Ergebnis ist bereits ein einzelnes, direkt deklariertes Interface-Member").

**Untersuchung:** Live-Export von `01OrgPrg` inspiziert (`ET.parse`-Dump der Roh-XML).
Ergebnis: Im gesamten Dokument fanden sich **zwei** `<Section Name="Static">`-Elemente
statt einem — eines mit den 4 tatsächlich direkt deklarierten Static-Membern
(`lx`, `lt_TofStartup`, `lu_RcpReq`, `lx_xx`), eines mit 9 weiteren Namen
(`lx_ReqRcpSpCvEqu`, `lt_TonALM`, ...), die sich als das **verschachtelte
Sub-Interface** der Multi-Instanz `lu_RcpReq` (bzw. deren InOut-Pendant
`iou_ReqRcp` — vermutlich der vom User gemeinte "ReqRcp") herausstellten: TIA
exportiert für ein Multi-Instanz-Member auch dessen eigene Interface-Struktur
verschachtelt innerhalb des `<Member>`-Elements. `interface_section_members()`
suchte bislang mit `xml_root.iter()` nach *jeder* Section mit passendem Namen im
gesamten Dokument, unabhängig von der Verschachtelungstiefe — dadurch wurden die 9
Sub-Member der Multi-Instanz fälschlich als eigene, direkte Interface-Member von
`01OrgPrg` behandelt und einzeln bemängelt, obwohl sie beim Durchlauf des
referenzierten FB (`lu_RcpReq`s bzw. `iou_ReqRcp`s Typ) ohnehin eigenständig geprüft
werden.

**Fix** (`src/tia_linter/checks/_tia_helpers.py::interface_section_members`): Der
Baumdurchlauf ist jetzt ein manueller rekursiver Walk (`_walk`), der beim Absteigen
**nicht** in `<Member>`-Elemente hinein rekursiert — nur Sections auf dem direkten
Pfad `Interface > Sections > Section` des exportierten Bausteins selbst zählen,
verschachtelte Sub-Interfaces von Multi-Instanz-/Struct-Membern werden ignoriert. Da
diese Funktion zentral in `_tia_helpers.py` liegt, profitieren automatisch auch
`styleguide.static_zugriff_extern` (Prüfpunkt 26) und
`styleguide.output_mehrfach_beschrieben` (Prüfpunkt 27) vom selben Fix — beide nutzen
denselben Mechanismus (`libraries.py`). Docstring von `FbMemberKommentarCheck`
korrigiert: die bisherige Annahme "keine rekursive Auflösung nötig" war schlicht
falsch, mit dem Fix stimmt sie jetzt tatsächlich.

**Verifiziert gegen das echte Salzmaschine-Projekt:**
- `interface_section_members(xml_root, "Static")` für `01OrgPrg` liefert nach dem Fix
  exakt die erwarteten **4** Member (`lx`, `lt_TofStartup`, `lu_RcpReq`, `lx_xx`) statt
  vorher 13 (4 + 9 aus dem verschachtelten Sub-Interface).
- `fb_member_kommentar` für `01OrgPrg` allein: **25 → 2 Befunde** (nur noch die beiden
  Multi-Instanzen selbst, falls ohne eigenen Kommentar — nicht mehr deren Sub-Member).
- Projektweit: `fb_member_kommentar` **256 → 45 Befunde**.
- Sanity-Check der beiden mitbetroffenen Prüfpunkte 26/27: laufen weiterhin
  fehlerfrei durch (0 Befunde je, ~330s bzw. ~1s Laufzeit) — keine Regression durch
  die geteilte Helper-Funktion.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Vorgehen zur Vorher/Nachher-Messung: Fix per `git stash` temporär entfernt, Messung
  wiederholt, Fix per `git stash pop` wiederhergestellt (wie schon in Runde 23).
- Vor der Live-Verifikation lief noch derselbe `Siemens.Automation.Object`-Prozess wie
  am Ende von Runde 23 (offenbar bleibt der TIA-Prozess nach einem sauberen
  `with connector:`-Exit im Hintergrund bestehen) — mehrere aufeinanderfolgende
  Verbindungen liefen ohne Probleme durch, keine erneute Wartezeit nötig.

**Dokumentiert:** `docs/Handbuch.md` (Version 0.23, neuer Anhang-C-Eintrag;
Besonderheiten von Prüfpunkt 1c beschrieben bereits vorher korrekt das jetzt
tatsächlich erreichte Verhalten, daher dort keine inhaltliche Änderung nötig).
`README.md` bewusst nicht geändert — reiner Bugfix an bestehendem Verhalten.

Letzter Stand: "Zehnter Kommentar-Bug behoben: interface_section_members() flachte
bislang das verschachtelte Sub-Interface von Multi-Instanz-Membern fälschlich mit ein
— betraf Prüfpunkt 1c sowie (über denselben Mechanismus) Prüfpunkt 26/27. Live
verifiziert an 01OrgPrg (13 → 4 Static-Member, 25 → 2 Befunde lokal, 256 → 45
projektweit bei fb_member_kommentar), Prüfpunkt 26/27 als Sanity-Check ohne
Regression bestätigt, pytest 38/38 grün."

## Runde 25 — Neuer Parameter `check_db` bei Prüfpunkt 2, YAML-Doku überarbeitet

**Ausgangspunkt (User-Auftrag):** "Prüfpunkt 2 würde ich gerne ändern. Die
Kopfbeschreibung ist bei Datenbausteinen eher unüblich, könntest du die Logik für FBs
und FCs so lassen und für DBs einen boolean Parameter in der YAML-Datei anlegen.
Default-mäßig soll der auf false, so dass die Kopfbeschreibung (Prüfpunkt 2) bei
Datenbausteinen nicht geprüft wird. [...] Der Parameter könnte `check_db` heißen?"
Zusätzlich: "Könntest du auch bitte die YAML-Datei intern besser dokumentieren. Vor
jeden Konfigurations-Bereich eine kleine Erklärung beginnend mit der Prüfpunkt-Nr.
Einige sind ja schon dokumentiert, z. B. 1b und 1c. Bitte so ähnlich überall, aber
kürzer."

**Fix** (`src/tia_linter/checks/comments.py::BausteinBeschreibungCheck`): Neuer
Parameter `check_db` (Standard `False`, `bool(self.definition.params.get("check_db",
False))`). Im Block-Loop wird jetzt zusätzlich `isinstance(block, DataBlock)` geprüft
(Import aus `Siemens.Engineering.SW.Blocks`) — ist `check_db` falsch und der Baustein
ein DB (Global-, Instanz- oder Array-DB), wird er komplett übersprungen; FB/FC/OB
bleiben davon unberührt und werden wie bisher immer geprüft. Docstring um einen
"Elfter Bug/Design-Entscheidung"-Abschnitt ergänzt.

**YAML-Doku-Überarbeitung** (`config/default.yaml`, komplett neu geschrieben statt
inkrementell editiert): Vor jedem der 44 Konfigurationsbereiche steht jetzt ein kurzer,
meist einzeiliger Kommentar, beginnend mit "Prüfpunkt N —" und der Kurzbeschreibung aus
`registry.py`. Die bereits ausführlicheren Kommentare bei 1b/1c sowie die Prüfpunkt-5-
und 12b-Erklärungen blieben unverändert (dienten bereits als Vorlage für den Stil).
`config/project_settings.yaml` (lokale, gitignorte Config des Users) um denselben
`check_db`-Parameter samt Kurzkommentar ergänzt — die übrigen 43 neuen Kurzkommentare
wurden dort bewusst *nicht* nachgezogen (personalisierte Datei, nur neue Parameter
werden synchronisiert, siehe bisheriges Vorgehen in Runde 20/21).

**Verifiziert:**
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Beide YAML-Dateien laden weiterhin fehlerfrei über `load_app_config()`
  (`Pydantic`-Model mit `extra="allow"` — kein Schema-Update für den neuen Parameter
  nötig), `check_db` kommt korrekt als `False` in `CheckDefinition.params` an.
- Live gegen das echte Salzmaschine-Projekt: `check_db=False` liefert **16 Befunde**
  (nur FB/FC/OB), `check_db=True` liefert **48 Befunde** — Differenz von **32** entspricht
  exakt der Anzahl der DBs ohne (ausreichende) Kopfbeschreibung, die jetzt standardmäßig
  nicht mehr gemeldet werden (Stichprobe: `PrgFieldbusOkDb`, `LSNTP_ServerDb`, `SysDiag`,
  `Org`, `PlcTimeDb`, ...).

**Dokumentiert:** `docs/Handbuch.md` (Prüfpunkt 2: Parameter-Tabelle um `check_db`
ergänzt, neue Besonderheiten-Zeile, Version 0.24 + Anhang-C-Eintrag). `README.md`
bewusst nicht geändert — dort werden laut eigenem Hinweis ("Details zu allen
Prüfpunkten: siehe `config/default.yaml`") nur komplett neue Prüfpunkte (1b/1c/12b)
mit eigenem Absatz vorgestellt, keine neuen Parameter bestehender Prüfpunkte; die
jetzt überarbeitete `default.yaml` übernimmt diese Rolle direkt.

Letzter Stand: "Prüfpunkt 2 prüft Datenbausteine standardmäßig nicht mehr auf eine
Kopfbeschreibung (neuer Parameter `check_db`, Standard `false`) — FB/FC/OB unverändert.
`config/default.yaml` durchgehend mit kurzen Prüfpunkt-Kommentaren vor jedem
Konfigurationsbereich versehen. Live verifiziert (16 vs. 48 Befunde, Differenz 32 DBs),
pytest 38/38 grün."

## Runde 26 — Zwölfter Kommentar-Bug: Prüfpunkt 2 las nur Comment, nicht Title

**Ausgangspunkt (User-Meldung, direkt im Anschluss an Runde 25):** "Der Prüfpunkt 2
funktioniert nicht. Das Problem ist das gleiche wie wir schon x mal haben. Der Text ist
multilingual und lässt sich nicht direkt vom z. B. FB-Objekt lesen. Beispiel wenn du
testest: der Baustein 40Org hat definitiv eine Kopfbeschreibung ('Organisation
Störungen Allgemein') wird aber als Warnung markiert." — der Verdacht auf den
altbekannten MultilingualText-Bug (siehe Runde 13) lag nahe, war aber diesmal nicht die
Ursache: Der Check nutzte bereits korrekt `read_comment()`.

**Untersuchung:** Live an `40Org` (FC) inspiziert (`GetAttributeInfos()`,
`block.Comment`, `block.Title`, jeweils alle `MultilingualTextItem`s ausgegeben).
Ergebnis: `block.Comment` ist für **jede** Sprache leer (`''`), aber `block.Title`
trägt für die Referenzsprache tatsächlich "Organisation Störungen Allgemein". `PlcBlock`
hat laut V21-Openness-Referenz zwei **unabhängige** mehrsprachige Felder — `Title` und
`Comment` — beide im Bausteinkopf des TIA-Editors sichtbar (der Abschnittstitel der
Referenz, "Mehrsprachige Titel **und** Kommentare", hatte das schon verraten). Prüfpunkt
2 las von Anfang an nur `Comment`, obwohl die eigentliche, im Projekt tatsächlich
gepflegte Kopfbeschreibung offenbar meist in `Title` steht.

**Fix:** Neue Hilfsfunktion `read_title()` in `_tia_helpers.py` (analog zu
`read_comment()`, gleicher `multilingual_text()`-Mechanismus, nur für das
`Title`-Attribut). `BausteinBeschreibungCheck.run()` liest jetzt beide Felder
(`read_comment`/`read_title`) und verwendet das jeweils längere für die
Mindestlängen-Prüfung — je nachdem, welches Feld in der Praxis für die Kopfbeschreibung
genutzt wird. Docstring um einen "Zwölfter Bug"-Abschnitt ergänzt.

**Verifiziert gegen das echte Salzmaschine-Projekt:**
- `40Org` taucht nach dem Fix nicht mehr in den Befunden auf.
- Mit der Standardkonfiguration (`check_db: false`, wie in Runde 25 eingeführt): **48 →
  3 Befunde**.
- Isoliert vom `check_db`-Filter (mit `check_db: true` erzwungen, um den Effekt allein
  auf den Title/Comment-Fix zurückzuführen, unabhängig von Runde 25): **48 → 34
  Befunde** über alle Bausteintypen hinweg — 14 Bausteine hatten wie `40Org` nur einen
  `Title`, keinen `Comment`.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Vorher/Nachher-Messung wie gewohnt per `git stash`/`git stash pop`.

**Dokumentiert:** `docs/Handbuch.md` ("Was wird geprüft?" und Besonderheiten bei
Prüfpunkt 2 um den Title/Comment-Hinweis ergänzt, Version 0.25 + Anhang-C-Eintrag).
`README.md` bewusst nicht geändert — reiner Bugfix an bestehendem Verhalten, kein neuer
Prüfpunkt.

Letzter Stand: "Prüfpunkt 2 las bislang nur das Comment-Attribut eines Bausteins,
obwohl TIA Title und Comment als zwei unabhängige mehrsprachige Felder führt — bei
40Org (und 13 weiteren Bausteinen) stand die tatsächliche Kopfbeschreibung nur in
Title. Fix: das jeweils längere der beiden Felder zählt jetzt. Live verifiziert
(48 → 3 mit check_db=false, 48 → 34 isoliert über alle Bausteintypen), pytest
38/38 grün."

**Nachtrag (direkt im Anschluss, kein Code-Fix, nur Untersuchung):** User meldete einen
weiteren vermeintlichen Fall — OB `Startup` mit Titel "Complete Restart" wird trotz
Runde-26-Fix weiterhin als Warnung markiert, Vermutung: entweder falsches Feld (wie bei
`40Org`) oder Quotierung (der Titel ist im Projekt tatsächlich `"Complete Restart"` mit
literalen Anführungszeichen). Live untersucht: `read_title()` liest den Text korrekt
(kein Lesefehler, Hypothese 1 widerlegt) — die Anführungszeichen sind echte, in TIA
gespeicherte Zeichen (Hypothese 2 bestätigt), aber **nicht ursächlich** für die Warnung:
"Complete Restart" hat 16 Zeichen, mit den Anführungszeichen 18 — beide Werte liegen
unter dem konfigurierten `min_laenge: 20`, der Baustein würde also auch ohne die
Anführungszeichen als "zu kurz" markiert. User-Entscheidung (per Rückfrage): "Nichts
ändern, Warnung ist korrekt" — kein Bug, sondern erwartetes Verhalten bei einem knapp zu
kurzen, aber echten Titel. Keine Code-/Doku-Änderung vorgenommen.

## Runde 27 — Dreizehnter Kommentar-Bug: Prüfpunkt 3 fand Netzwerktitel nie

**Ausgangspunkt (User-Meldung):** "Bei Prüfpunkt 3 sind fast alle Warnungen falsch.
Das liegt wahrscheinlich auch wieder daran, das die Netzwerkbeschreibung multilingual
ist."

**Untersuchung:** Live-XML-Export eines Bausteins (`Startup`) inspiziert. Bisherige
Annahme (`compile_unit_attribute(compile_unit, "Title")` liest aus der
`AttributeList`, analog zu `ProgrammingLanguage`) war falsch für Titel/Kommentar:
Diese liegen im XML-Export als eigene, vollständige `MultilingualText`-Komposition im
`ObjectList` eines `CompileUnit` — strukturell identisch zu `PlcBlock.Title`/`.Comment`
(Runde 26), nur eben als XML-Baum statt als Openness-Objekt:
`<ObjectList><MultilingualText CompositionName="Title"><ObjectList>
<MultilingualTextItem CompositionName="Items"><AttributeList><Culture>de-DE</Culture>
<Text>...</Text></AttributeList></MultilingualTextItem>...`. Ein gezielter
Vollprojekt-Scan bestätigte: **kein einziges** der durchsuchten Netzwerke hatte je ein
`<Title>`-Kind in der `AttributeList` — `compile_unit_attribute` lieferte dadurch
strukturell bedingt **immer** `None`, unabhängig davon, ob ein Titel gepflegt war.

**Fix, Teil 1** (`_tia_helpers.py`): Neue Funktion `compile_unit_multilingual_text()`
navigiert gezielt zu `ObjectList > MultilingualText[CompositionName=Title] >
ObjectList > MultilingualTextItem`, vergleicht dort das `Culture`-Kind gegen die
übergebene Kultur und liefert den zugehörigen `Text`. `NetzwerkBeschreibungCheck`
(`comments.py`) nutzt diese Funktion jetzt statt `compile_unit_attribute`.

**Fix, Teil 2 (zusätzlicher, beim Testen entdeckter Fallstrick):** Erste
Live-Verifikation des Fixes zeigte weiterhin 148 Befunde — augenscheinlich wirkungslos.
Ursache: `reference_language(project).Culture` liefert ein
`System.Globalization.CultureInfo`-.NET-Objekt, kein `System.String`. Der Vergleich
`item_culture == culture` in `compile_unit_multilingual_text` verglich also einen
Python-`str` (aus dem XML) gegen ein .NET-Objekt — nie gleich, obwohl `print()`/`str()`
auf das `CultureInfo`-Objekt korrekt `"de-DE"` anzeigt (daher beim ersten Hinsehen
unauffällig). Fix: `culture = str(reference_language(project).Culture)` vor dem
Aufruf.

**Verifiziert gegen das echte Salzmaschine-Projekt** (per `git stash`/`git stash pop`
vor/nach gemessen):
- Vorher: **148 Befunde**, alle vom Typ "kein Titel" — inkl. `Startup > Netzwerk 1`,
  das laut Rohdaten den Titel "Systemdiagnose auf DB speichern" (de-DE) trägt.
- Nachher: **1 Befund** — ein echter "Titel zu lang"-Fall, keine "kein Titel"-Befunde
  mehr.
- Isolierter Funktionstest von `compile_unit_multilingual_text()` gegen
  `Startup > Netzwerk 1`: liefert nach dem vollständigen Fix (Struktur + `str()`)
  korrekt `'Systemdiagnose auf DB speichern'`.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Ungenutzten Import `compile_unit_attribute` aus `comments.py` entfernt (dort nicht
  mehr aufgerufen, aber weiterhin von `libraries.py`/`structure.py` für echte
  Attribute wie `ProgrammingLanguage` verwendet).

**Dokumentiert:** `docs/Handbuch.md` (Besonderheiten bei Prüfpunkt 3 um den
Mehrsprachigkeits-Hinweis ergänzt, Version 0.26 + Anhang-C-Eintrag). `README.md`
bewusst nicht geändert — reiner Bugfix an bestehendem Verhalten.

Letzter Stand: "Prüfpunkt 3 las Netzwerktitel aus der falschen XML-Struktur
(AttributeList statt ObjectList/MultilingualText) und fand dadurch strukturell nie
einen Titel — zusätzlich ein CultureInfo-vs-String-Vergleichsfehler beim ersten
Fix-Versuch. Beide behoben, live verifiziert (148 → 1 Befund), pytest 38/38 grün."

## Runde 28 — Vierzehnter Kommentar-Bug: Prüfpunkt 4 erkannte fehlende Version nie

**Ausgangspunkt (User-Meldung):** Nutzer hatte sich erst von mir Prüfpunkt 4 erklären
lassen ("ein Befund entsteht nur, wenn Autor UND Version beide fehlen") und dann
absichtlich bei FB `01OrgPrg` beide Felder geleert, um das zu testen. Ergebnis: "Der
Test läuft ohne Warnungen durch, obwohl ich absichtlich einen Fehler eingebaut habe."

**Untersuchung:** Live an `01OrgPrg` inspiziert. `GetAttribute("HeaderAuthor")` liefert
korrekt `''` (leerer String). `GetAttribute("HeaderVersion")` liefert dagegen **kein**
`System.String`, sondern ein `System.Version`-.NET-Objekt — dessen `ToString()` bei
nicht gesetzter Version `"0.0.0.0"` ergibt (Standardwert des parameterlosen
`Version()`-Konstruktors in .NET). Der bestehende Code (`str(get_attribute(...) or
"").strip()`) wandelte das Objekt korrekt in einen String um, aber `"0.0.0.0"` ist
selbst ein **nicht-leerer** String — die Version galt dadurch immer als "vorhanden",
unabhängig vom tatsächlichen Inhalt, wodurch praktisch kein Baustein im gesamten
Projekt je einen Befund auslösen konnte. Ein Vollprojekt-Scan über alle 288 Bausteine
bestätigte den Verdacht: 234 tragen exakt `"0.0.0.0"` (Sentinel für "nie gesetzt"),
echte Versionen sehen dagegen wie `"0.1"`, `"1.0"`, `"2.1"` aus — im Bausteinkopf-UI
von TIA besteht das Versionsfeld aus genau zwei Zahlenfeldern, ein vierteiliger Wert
wie `"0.0.0.0"` lässt sich dort gar nicht eingeben, kann also nur der interne
.NET-Standardwert sein.

**Fix** (`src/tia_linter/checks/comments.py::AenderungshistorieCheck`): Nach dem
Auslesen wird `version == "0.0.0.0"` explizit auf `""` normalisiert, bevor die
Leer-Prüfung (`not author and not version`) läuft. Docstring um einen "Vierzehnter
Bug"-Abschnitt ergänzt.

**Verifiziert gegen das echte Salzmaschine-Projekt:**
- `01OrgPrg` (Autor UND Version vom User absichtlich geleert) wird jetzt korrekt
  gemeldet: "Baustein '01OrgPrg' hat weder Autor noch Version im Bausteinkopf
  hinterlegt."
- Projektweit: **0 → 104 Befunde** — vorher hatte der Prüfpunkt trotz vieler Bausteine
  ohne echte Versionsangabe (234 von 288 mit dem `"0.0.0.0"`-Sentinel) keinen einzigen
  Befund geliefert.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.

**Dokumentiert:** `docs/Handbuch.md` (neue Besonderheiten-Zeile bei Prüfpunkt 4,
Version 0.27 + Anhang-C-Eintrag). `README.md` bewusst nicht geändert — reiner Bugfix
an bestehendem Verhalten.

Letzter Stand: "Prüfpunkt 4 (Bausteinkopf ohne Autor/Version) meldete praktisch nie
einen Befund, weil HeaderVersion als System.Version-Objekt mit Sentinel-Wert
'0.0.0.0' bei nicht gesetzter Version zurückkam — als String immer nicht-leer, also
fälschlich 'vorhanden'. Fix: '0.0.0.0' wird wie leer behandelt. Live verifiziert
(0 → 104 Befunde bei 234 von 288 Bausteinen ohne echte Version), pytest 38/38 grün."

## Runde 29 — Neuer Parameter `check_idb` bei Prüfpunkt 4

**Ausgangspunkt (User-Auftrag, direkt im Anschluss an Runde 28):** "Bitte bei
Prüfpunkt 4 die Instanzdatenbausteine ausnehmen, so wie bei Prüfpunkt 2. Und auch
bitte konfigurierbar machen so wie in Prüfpunkt 2. Name Parameter: check_idb.
Defaultwert false. Nicht-Instanzdatenbausteine sollen normal geprüft werden, so wie
die anderen Bausteine auch." — anders als `check_db` bei Prüfpunkt 2 (das *alle*
Datenbausteine ausnimmt) soll `check_idb` gezielt nur Instanz-DBs betreffen,
Global-/Array-DBs bleiben wie FB/FC/OB immer geprüft.

**Umsetzung** (`src/tia_linter/checks/comments.py::AenderungshistorieCheck`): Neuer
Parameter `check_idb` (Standard `False`). Im Block-Loop wird zusätzlich
`get_attribute(block, "InstanceOfName", "")` geprüft (dieselbe Erkennung wie bei
Prüfpunkt 1s Instanz-DB-Skip, siehe Runde 21) — ist `check_idb` falsch und der
Baustein eine Instanz-DB, wird er übersprungen; alle anderen Bausteintypen bleiben
unberührt. Docstring um einen "Fünfzehnter Bug/Design-Entscheidung"-Abschnitt
ergänzt. `check_idb: false` in `config/default.yaml` und `config/project_settings.yaml`
ergänzt (jeweils mit Kurzkommentar).

**Verifiziert:**
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Beide YAML-Dateien laden fehlerfrei, `check_idb` kommt korrekt als `False` in
  `CheckDefinition.params` an.
- Live gegen das echte Salzmaschine-Projekt: `check_idb=False` liefert **6 Befunde**,
  `check_idb=True` liefert **8 Befunde** — Differenz von **2** entspricht exakt den
  beiden Instanz-DBs ohne Autor/Version (`PrgFieldbusOkDb`, `PlcTimeDb`), die
  standardmäßig nicht mehr gemeldet werden. (Die absolute Zahl liegt bewusst weit
  unter den 104 aus Runde 28, da jener Test ohne `ausgeschlossene_ordner` lief — hier
  wird korrekt der ausgeschlossene Ordner `ProjectBib` aus der echten
  `project_settings.yaml` berücksichtigt.)

**Dokumentiert:** `docs/Handbuch.md` (Parameter-Tabelle um `check_idb` ergänzt, neue
Besonderheiten-Zeile mit Abgrenzung zu Prüfpunkt 2s `check_db`, Version 0.28 +
Anhang-C-Eintrag). `README.md` bewusst nicht geändert — dort werden laut eigenem
Hinweis nur komplett neue Prüfpunkte mit eigenem Absatz vorgestellt, keine neuen
Parameter bestehender Prüfpunkte.

Letzter Stand: "Prüfpunkt 4 nimmt Instanz-Datenbausteine nur noch standardmäßig aus
(neuer Parameter check_idb, Standard false) — Global-/Array-DBs und FB/FC/OB
unverändert geprüft, anders als check_db bei Prüfpunkt 2 (das alle DBs betrifft).
Live verifiziert (6 vs. 8 Befunde, Differenz 2 Instanz-DBs), pytest 38/38 grün."

**Zwischenzeitlich (kein eigener Runden-Eintrag):** User hatte in seiner lokalen
`project_settings.yaml` zwei neue Regex-Werte mit unescaptem `\d` in doppelt
angeführten YAML-Strings eingefügt (`"^(.*Db|S\d{4})$"`) — YAML interpretiert
Backslashes in `"..."`-Strings wie JSON, `\d` ist keine gültige Escape-Sequenz,
wodurch die komplette Config-Datei nicht mehr lud. Behoben durch Umstellung auf
einfache Anführungszeichen (`'...'`, dort werden Backslashes nicht interpretiert).
Auf Bitte des Users danach `default.yaml` auf Backslash-Fehler geprüft (keine
gefunden, `fb_prefix`/`fc_prefix` waren bereits korrekt mit `\\S` escaped) und alle
7 Regex-Werte in beiden Dateien einheitlich auf einfache Anführungszeichen
umgestellt. Commit `b2c5bac` (nur `default.yaml`, `project_settings.yaml` ist
gitignored).

## Runde 30 — GUI: Prüfpunkt-Kategorien im Grid, Mausrad überall nutzbar

**Ausgangspunkt (User-Auftrag):** "Du hast die Punkte wirklich gut gruppiert. Aber es
steht in der GUI eine Gruppe unter der anderen. Rechts ist noch viel Platz. Ordne die
Gruppen doch bitte auch nebeneinander an. Z. B. immer 3 Gruppen nebeneinander." —
konkret: "Kommentare & Beschreibungen", "Namenskonventionen" und "Programmstruktur" in
der ersten Zeile nebeneinander, danach die restlichen Kategorien entsprechend.
Zusätzlich: "Mein Mausrad in dem Bereich funktioniert nur, wenn ich mit der Maus über
dem Scrollbalken bin. Ist es möglich, das das Mausrad auch funktioniert, wenn der
Mauszeiger in dem Bereich ist?"

**Umsetzung 1 — Grid-Layout** (`src/tia_linter/gui.py::MainPage.rebuild_check_tree`):
Die Kategorie-`LabelFrame`s wurden bisher mit `.pack(fill="x", ...)` untereinander
gestapelt. Umgestellt auf `.grid(row=..., column=..., sticky="nsew")` mit einer neuen
Konstante `_CATEGORY_COLUMNS = 3` — `row, col = divmod(index, 3)`. Die drei Spalten von
`self._checks_frame` werden mit `columnconfigure(col, weight=1, uniform="category")`
gleich breit gehalten, damit sich der Platz beim Fenster-Resize gleichmäßig verteilt.

**Umsetzung 2 — Mausrad überall** (`gui.py`): Neue Methode
`_bind_mousewheel_recursive()`, die `<MouseWheel>` (Windows/Mac,
`event.delta`) sowie `<Button-4>`/`<Button-5>` (Linux/X11, kein
`MouseWheel`-Event dort) direkt auf den Canvas und **rekursiv auf jedes einzelne
Kind-Widget** bindet (Kategorie-Frames, Checkbox-Zeilen, Labels, Checkbuttons) —
aufgerufen am Ende von `rebuild_check_tree()`. Bewusst **keine**
Enter/Leave-Umschaltung mit `bind_all`/`unbind_all` (der naheliegendere, verbreitetere
Tkinter-Ansatz): Die per `canvas.create_window()` eingebettete Checkbox-Frame ist ein
eigenständiges Kind-Fenster des Canvas — beim Wechsel der Maus vom Canvas auf eine
Checkbox hätte das dortige `<Leave>` auf dem Canvas die globale Bindung sofort wieder
aufgehoben, genau im Bereich, wo sie gebraucht wird. Die direkte, rekursive Bindung
umgeht dieses Problem vollständig.

**Verifiziert:**
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- GUI-Smoketest (`TiaLinterApp` ohne `mainloop`): 7 Kategorie-Frames erzeugt,
  `grid_info()` bestätigt exakt die erwartete Anordnung — Zeile 0:
  Kommentare & Beschreibungen (Spalte 0), Namenskonventionen (Spalte 1),
  Programmstruktur (Spalte 2); Zeile 1: Hardware & Konfiguration,
  Projektmetadaten, Bibliotheken & Typen; Zeile 2: Siemens Styleguide & Best
  Practices (allein, da nur 7 Kategorien bei 3 Spalten). Ein per Rekursion
  gefundener `Checkbutton` hat nachweislich eine `<MouseWheel>`-Bindung.
- Kein Screenshot-Tool verfügbar — das tatsächliche visuelle Layout (Breiten,
  Abstände, ob es "gut aussieht") wurde dem User gegenüber ausdrücklich als
  ungeprüft benannt, nur Struktur (Grid-Positionen) und Event-Bindungen wurden
  bestätigt.

**Dokumentiert:** `docs/Handbuch.md` (Abschnitt 6.2 "Die Eingabeseite" um Hinweise zu
Spalten-Layout und durchgängiger Mausrad-Nutzung ergänzt, Version 0.29 +
Anhang-C-Eintrag). `README.md` bewusst nicht geändert — reine GUI-Layout-Änderung ohne
neuen Prüfpunkt/Parameter.

Letzter Stand: "Prüfpunkt-Kategorien stehen jetzt zu je drei nebeneinander (Grid statt
Pack), Mausrad scrollt überall im Prüfpunkte-Bereich (rekursive Bindung auf Canvas +
alle Kind-Widgets, keine Enter/Leave-Umschaltung wegen der eingebetteten
Checkbox-Frame als eigenem Kind-Fenster). Grid-Positionen und Event-Bindungen per
Smoketest bestätigt, visuelles Layout dem User gegenüber als ungeprüft benannt
(kein Screenshot-Tool). pytest 38/38 grün."

## Runde 31 — GUI: Buttons vergrößert, zentriert, "Prüfung starten" dynamisch grün

**Ausgangspunkt (User-Auftrag, direkt im Anschluss an Runde 30, vor dessen Commit):**
"Die Buttons 'Alle auswählen' und 'Alle abwählen' bitte ca. 50% größer und in der
Mitte des Bildes. Die Buttons 'Prüfung starten' und 'Abbrechen' auch ca. 50% größer
und auch mittig. Den Button 'Prüfung starten' bitte hell grün wenn mindestens 1
Haken gesetzt ist."

**Umsetzung 1 — Größe & Zentrierung** (`src/tia_linter/gui.py::MainPage._build_widgets`):
Eine 50 % größere Schrift wird relativ zur tatsächlichen `TkDefaultFont`-Größe
berechnet (`tkfont.nametofont("TkDefaultFont")`, `size * 1.5`, gerundet) statt eine
feste Punktgröße hart zu kodieren — respektiert damit auch abweichende
DPI-/Basisschriftgrößen. Ein ttk-Style `"Big.TButton"` (größere Schrift + größeres
`padding`) wird für "Alle auswählen"/"Alle abwählen"/"Abbrechen" verwendet. Für die
Zentrierung wird pro Button-Zeile ein innerer `ttk.Frame` ohne `fill`/`side="left"`
in den äußeren, `fill="x"` gepackten Frame gepackt — Packs Default-Anchor
("center") zentriert diesen inneren Frame dadurch automatisch horizontal in der
verfügbaren Breite.

**Umsetzung 2 — Dynamische Grün-Färbung** (`gui.py`): "Prüfung starten" wurde von
`ttk.Button` auf ein klassisches `tk.Button` umgestellt — `ttk.Button` ignoriert
unter den nativen Windows-Themes ("vista"/"xpnative") eine per `background`/
`style.map` gesetzte Hintergrundfarbe zuverlässig, `tk.Button.configure(background=...)`
dagegen funktioniert direkt. Neue Methode `_update_start_button_appearance()`
prüft, ob mindestens eine der `BooleanVar`s in `self._check_vars` `True` ist, und
setzt `background`/`activebackground` entsprechend auf `"light green"` oder den
ursprünglichen, beim ersten Aufbau gespeicherten System-Standardwert
(`self._start_button_default_bg`, z. B. `"SystemButtonFace"`). Jede `BooleanVar`
bekommt in `rebuild_check_tree()` einen `trace_add("write", ...)` auf diese Methode
— dadurch reagiert die Färbung automatisch auf **jede** Änderung, egal ob per
Einzel-Checkbox, Kategorie-"Alle"/"Keine" oder globalem "Alle auswählen"/"Alle
abwählen" ausgelöst, da alle denselben Satz `BooleanVar`s verändern.

**Verifiziert:**
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- GUI-Smoketest (`TiaLinterApp` ohne `mainloop`): Schriftgröße von "Prüfung
  starten" 9 → 14 (erwartete Rundung von 9 × 1,5 = 13,5). Button-Klasse
  bestätigt `"Button"` (nicht `"TButton"`) — reine `tk`-Variante wie
  vorgesehen. Nach `_set_all(False)`: `background == "SystemButtonFace"`
  (Ausgangswert). Nach `_set_all(True)`: `background == "light green"`.
  "Alle auswählen" bestätigt Style `"Big.TButton"`. Beide inneren
  Button-Container zeigen `pack_info()` mit `anchor="center"`, `fill="none"` —
  wie für die Zentrierung vorgesehen.
- Kein Screenshot-Tool verfügbar — das tatsächliche visuelle Erscheinungsbild
  (wirkt es "50 % größer", sieht die Zentrierung gut aus) wurde dem User
  gegenüber ausdrücklich als ungeprüft benannt, nur Größenverhältnis,
  Button-Klasse, Farbwerte und Pack-Zentrierung wurden bestätigt.

**Dokumentiert:** `docs/Handbuch.md` (Abschnitt 6.2 um Hinweise zu Button-Größe,
Zentrierung und der grünen Startfarbe ergänzt, Version 0.30 + Anhang-C-Eintrag).
`README.md` bewusst nicht geändert — reine GUI-Layout-/Optik-Änderung.

Letzter Stand: "'Alle auswählen'/'Alle abwählen'/'Prüfung starten'/'Abbrechen' sind
jetzt ca. 50% größer (Schrift relativ zur Basisschriftgröße skaliert) und zentriert.
'Prüfung starten' färbt sich hellgrün, sobald mindestens ein Prüfpunkt angehakt ist
(dafür auf tk.Button umgestellt, da ttk.Button unter Windows-Themes keine
Hintergrundfarbe zuverlässig übernimmt). Größe/Klasse/Farbe/Zentrierung per
Smoketest bestätigt, visuelles Erscheinungsbild dem User gegenüber als ungeprüft
benannt (kein Screenshot-Tool). pytest 38/38 grün. Noch nicht committet — wartet
auf Rückmeldung des Users nach eigenem Test in der GUI (zusammen mit Runde 30)."

## Runde 32 — Fünfzehnter Bug: Prüfpunkt 10 markierte massenhaft nicht-leere Netzwerke

**Ausgangspunkt (User-Meldung):** "Prüfpunkt 10 funktioniert nicht. Es werden sehr
viele Netzwerke markiert, die nicht leer sind. [...] entweder war es ein SCL
Netzwerk. Das ist ok und sollte nicht markiert werden. Oder es war ein Netzwerk in
dem nur 1 anderer Baustein aufgerufen wurde. Das ist auch ok. Das ist NICHT leer.
Als Beispiel [...] Baustein OrgPrg [...] ALLE Warnungen sind falsch. NW: 3,8,9,12,
13,14,15." — beide vom User selbst identifizierten Muster erwiesen sich live als
exakt zutreffend, aus zwei unabhängigen Ursachen.

**Untersuchung:** Live-XML-Export von `OrgPrg` (nicht zu verwechseln mit `01OrgPrg`
aus früheren Runden — beide Blöcke existieren, erste Verwechslung im eigenen
Testskript sofort korrigiert) für genau die gemeldeten Netzwerke inspiziert.
- Netzwerk 3/8: Block-Level `ProgrammingLanguage` ist `"FBD"`, aber diese beiden
  Netzwerke haben ihre eigene, netzwerk-lokale `ProgrammingLanguage` `"SCL"` — TIA
  erlaubt gemischte Sprachen innerhalb eines Bausteins (dasselbe Konzept, das
  Prüfpunkt 15 explizit prüft). Ihr Inhalt liegt als `<StructuredText>` vor, nicht
  als `<FlgNet>`/`<Part>` — der bisherige, nur Baustein-Level greifende SCL/STL-Skip
  erkannte das nicht.
- Netzwerk 9/12/13/14/15: Jeweils genau ein Bausteinaufruf (`CtrCycleTime`,
  `PrgFieldbusOk`, `01Org`, `40Org`, `4805PrgMan`), sonst keine Logik. Im XML-Export
  wird ein Bausteinaufruf als eigenes `<Call>`-Element dargestellt, **nicht** als
  `<Part>` — `compile_unit_element_count()` zählte bislang ausschließlich
  `<Part>`-Elemente, ein reiner Call-Aufruf ergab dadurch Elementanzahl 0.

**Fix:**
- `_tia_helpers.py::compile_unit_element_count()`: zählt jetzt `<Part>`- **und**
  `<Call>`-Elemente. Diese Funktion wird auch von Prüfpunkt 16
  (`max_netzwerk_elemente`) und Prüfpunkt 30 (`ob1_komplexitaet`) genutzt —
  Letzterer geht laut eigenem Code-Kommentar sogar explizit davon aus, dass ein
  reiner Call-Aufruf mit Elementanzahl 1 gezählt wird ("1 Part == der Call
  selbst"), was durch den bisherigen Bug nie zutraf (tatsächlich 0). Der Fix
  korrigiert diese Annahme rückwirkend mit, statt sie zusätzlich zu brechen.
- `structure.py::LeereNetzwerkeCheck`: zusätzlicher Skip anhand der
  **Netzwerk**-eigenen `ProgrammingLanguage` (nicht nur der des Bausteins) —
  `compile_unit_attribute(compile_unit, "ProgrammingLanguage") in ("SCL", "STL")`.

**Verifiziert gegen das echte Salzmaschine-Projekt:**
- `OrgPrg` liefert nach dem Fix keinen einzigen Befund mehr aus Prüfpunkt 10.
- Projektweit (per `git stash`/`git stash pop` vor/nach gemessen): **55 → 19
  Befunde**.
- Sanity-Check der beiden mitbetroffenen Prüfpunkte 16/30: laufen weiterhin
  fehlerfrei durch (0 bzw. 1 Befund, plausibel), keine Exception, keine
  offensichtliche Regression.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.

**Dokumentiert:** `docs/Handbuch.md` (zwei neue Besonderheiten-Zeilen bei
Prüfpunkt 10 — Netzwerk-eigene Sprache und Call-als-Element, Version 0.31 +
Anhang-C-Eintrag). `README.md` bewusst nicht geändert — reiner Bugfix an
bestehendem Verhalten.

Letzter Stand: "Prüfpunkt 10 markierte massenhaft nicht-leere Netzwerke faelschlich
als leer: SCL-Netzwerke innerhalb eines sonst FBD-Bausteins wurden nicht erkannt
(Skip war nur auf Baustein-Ebene), und reine Bausteinaufrufe (<Call>-Element) wurden
von compile_unit_element_count() gar nicht mitgezaehlt. Beide behoben, live
verifiziert (55 → 19 Befunde, alle 7 gemeldeten OrgPrg-Netzwerke korrekt), Prüfpunkt
16/30 als Sanity-Check ohne Regression bestätigt, pytest 38/38 grün."

## Runde 33 — Neuer Parameter `ausnahme_titel_regex` bei Prüfpunkt 10

**Ausgangspunkt (User-Auftrag, direkt im Anschluss an Runde 32):** "Zu Prüfpunkt 10:
leere Netzwerke werden auch gerne verwendet um mit dem Netzwerkkommentar eine Art
neues Kapitel im Baustein zu beginnen. Können wir den Check ausnehmen, wenn der
Netzwerkkommentar einer bestimmten Syntax entspricht: Regex-Parameter im YAML."

**Umsetzung** (`src/tia_linter/checks/structure.py::LeereNetzwerkeCheck`): Neuer
Parameter `ausnahme_titel_regex` (Standard `""` = deaktiviert). Wird ein Netzwerk als
leer erkannt (0 Programmelemente), wird zusätzlich sein Titel gelesen (über
`compile_unit_multilingual_text()`, denselben Mechanismus wie Prüfpunkt 3 — Titel
liegen im XML-Export als eigene `MultilingualText`-Komposition, siehe Runde 27) und
gegen `re.match(ausnahme_titel_regex, titel)` geprüft (Konvention wie bei allen
anderen Regex-Parametern in diesem Projekt, siehe `naming.py`). Passt der Titel,
wird kein Befund erzeugt. Ist der Parameter leer, wird die komplette
Titel-Lookup-Logik übersprungen (kein unnötiger Overhead, wenn das Feature nicht
genutzt wird). Docstring um einen "Sechzehnter Bug/Design-Entscheidung"-Abschnitt
ergänzt. Parameter in `config/default.yaml` und `config/project_settings.yaml`
ergänzt (jeweils mit Kurzkommentar, Standard `''`).

**Verifiziert:**
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- Beide YAML-Dateien laden fehlerfrei, `ausnahme_titel_regex` kommt korrekt als
  leerer String in `CheckDefinition.params` an.
- TIA-Verbindungshinweis: Vor der Live-Verifikation war das Projekt bei laufenden
  `Siemens.Automation.Portal`-Prozessen mit deutlichem Speicherverbrauch offenbar
  vom User selbst in der TIA-Portal-GUI geöffnet — per Rückfrage bestätigt und vom
  User geschlossen, danach übliche ~125s auf die Freigabe der Projektsperre
  gewartet.
- Live gegen das echte Salzmaschine-Projekt: ein **echter** Anwendungsfall gefunden
  — `40Prg > Netzwerk 1` ist leer und trägt den Titel
  `"########## Schaltgerüst/ Bedienschrank =4805 ##########"``, exakt das vom User
  beschriebene Kapitelüberschrift-Muster. Mit passendem Regex (escaped exakter
  Titel): **19 → 18 Befunde**. Mit einem absichtlich nicht passenden Regex:
  unverändert **19 Befunde** (bestätigt, dass der Parameter nichts verändert, wenn
  er nicht zutrifft).
- Eigener Verifikationsfehler unterwegs: ein erster Testlauf verglich Netzwerk-Pfade
  per Teilstring-Suche (`"OrgPrg" in pfad`) statt exaktem Abgleich — dadurch wurde
  fälschlich `01OrgPrg` statt `OrgPrg` als Stichprobe gefunden (Namenskollision,
  `"OrgPrg"` ist Teilstring von `"01OrgPrg"`). Nach Umstellung auf exakten
  Pfadabgleich (`format_path(...) in {r.path for r in results}`) lieferte der Test
  den echten, oben beschriebenen Treffer.

**Dokumentiert:** `docs/Handbuch.md` (Parameter-Tabelle um `ausnahme_titel_regex`
ergänzt, neue Besonderheiten-Zeile, Empfehlung zur Behebung erweitert, Version 0.32 +
Anhang-C-Eintrag). `README.md` bewusst nicht geändert — dort werden laut eigenem
Hinweis nur komplett neue Prüfpunkte mit eigenem Absatz vorgestellt, keine neuen
Parameter bestehender Prüfpunkte.

Letzter Stand: "Prüfpunkt 10 kann jetzt per `ausnahme_titel_regex` (Standard leer =
deaktiviert) leere Netzwerke ausnehmen, deren Titel als Kapitelüberschrift dient.
Live an einem echten Fall verifiziert (40Prg > Netzwerk 1, '##########
Schaltgerüst/ Bedienschrank =4805 ##########'): 19 → 18 mit passendem Regex, 19
unverändert mit nicht-passendem Regex. pytest 38/38 grün."

## Runde 34 — Siebzehnter Bug: Prüfpunkt 11 meldete DB-Selbst-Eintrag als Phantom-Member

**Ausgangspunkt (User-Meldung):** "Ich bekomme bei Prüfpunkt 11 mehrere Warnungen,
die keinen Sinn machen. [...] Bitte erklär mir was da falsch läuft, bevor du etwas
änderst." — mit Beispielbefund: `pn4805-15a1 > Datenbaustein > _Org > IDb >
DB_PrgFieldbusOkDb > Member > DB_PrgFieldbusOkDb`, "DB-Variable
'DB_PrgFieldbusOkDb' wird im gesamten Programm nicht verwendet". Auffällig: das
gemeldete "Member" trägt exakt denselben Namen wie die DB selbst.

**Untersuchung (erst nur Erklärung, kein Fix, wie explizit gewünscht):** Live an
genau dieser Instanz-DB inspiziert. `cross_reference_locations(db)` (Filter
`AllObjects`) findet 2 Fundstellen — die DB wird also durchaus irgendwo referenziert.
`GetCrossReferences(CrossReferenceFilter.UnusedObjects)` auf derselben DB liefert
dagegen genau einen `Source`-Eintrag mit `Name='DB_PrgFieldbusOkDb'`,
`TypeName='Instance DB of PrgFieldbusOk [FB82]'` und `Path` zeigt auf den *Ordner*
der DB, nicht auf ein verschachteltes Member. Das ist eindeutig die DB **selbst**,
kein echtes Member — Openness liefert sie hier trotzdem (widersprüchlich zum
`AllObjects`-Befund) als "unused Source" zurück. Der bisherige Code
(`UnbenutzteVariablenCheck`) behandelte jeden `Source` blind als DB-Variable und baute
daraus den irreführenden Pfad mit dem Phantom-"Member". Erklärung an den User
gegeben; User-Entscheidung: "Ja, DB-eigene Einträge rausfiltern, andere echte
unbenutzte Member weiterhin melden."

**Fix** (`src/tia_linter/checks/structure.py::UnbenutzteVariablenCheck`): `Source`s,
deren `Name` exakt dem Namen der DB entspricht, werden übersprungen — echte Member
(deren Name naturgemäß nie mit dem DB-Namen übereinstimmt) bleiben unberührt
gemeldet. Docstring um einen "Siebzehnter Bug"-Abschnitt ergänzt.

**Verifiziert gegen das echte Salzmaschine-Projekt** (per `git stash`/`git stash pop`
vor/nach gemessen):
- `DB_PrgFieldbusOkDb` taucht nach dem Fix nicht mehr in den Befunden auf.
- Projektweit: **23 → 5 Befunde**. Aufschlussreich: **alle 18** zuvor gemeldeten
  "DB-Member"-Befunde im Projekt erwiesen sich beim Nachzählen als exakt dieser
  Selbst-Eintrag-Fall (`Member`-Name == DB-Name bei jedem einzelnen) — es gab in
  diesem Projekt aktuell keinen einzigen echten unbenutzten DB-Member, nur
  Phantom-Einträge.
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.
- TIA-Hinweis: vor der Live-Verifikation war das Projekt kurzzeitig gesperrt (User
  hatte es zwischenzeitlich selbst in TIA Portal offen, siehe Runde 33) — bereits
  dort geklärt und gewartet.

**Dokumentiert:** `docs/Handbuch.md` (neue Besonderheiten-Zeile bei Prüfpunkt 11 mit
Querverweis auf Prüfpunkt 11b, Version 0.33 + Anhang-C-Eintrag). `README.md` bewusst
nicht geändert — reiner Bugfix an bestehendem Verhalten.

Letzter Stand: "Prüfpunkt 11 meldete bei manchen Instanz-DBs die DB selbst als
Phantom-'Member' mit identischem Namen (Openness' UnusedObjects-Filter liefert dafür
manchmal einen Source-Eintrag zusätzlich zu echten Membern). Fix: Source, dessen
Name exakt dem DB-Namen entspricht, wird übersprungen. Live verifiziert (23 → 5
Befunde, alle 18 vorherigen DB-Member-Befunde waren dieser Phantom-Fall), pytest
38/38 grün."

## Runde 35 — Achtzehnter Bug: Prüfpunkt 11 verschluckte nach Runde 34 sämtliche echten Treffer

**Ausgangspunkt (User-Meldung, direkt im Anschluss an Runde 34, Widerspruch statt
Bestätigung):** "Bist du dir sicher? Meiner Meinung nach wird DB_PrgFieldbusOkDb ->
DiagCpu -> DNNmode nicht verwendet." — der Fix aus Runde 34 (Skip des Source, dessen
Name exakt dem DB-Namen entspricht) hatte den irreführenden Phantom-Befund zwar
entfernt, aber offenbar auch den vom User erwarteten echten Treffer mit entfernt.

**Hinweis des Users:** "Hast du schon mal im Ordner doku_etc in das PDF geschaut? Da
ist einiges an Beispielcode bezüglich Cross Reference drin." — Verweis auf die
offizielle, lokal abgelegte V21-Openness-Referenz-PDF (28 MB, nicht die davon
abgeleitete, verkürzte `Openness-API-Referenz-fuer-Linter.md`, die nur aus der
älteren V18-Doku erarbeitet worden war).

**Untersuchung:** PDF via `pdftotext -layout` in Textform extrahiert und durchsucht.
Abschnitt "1.4.11.2.11 Querverweise für STEP 7 abrufen" (Manual 03/2026, S. 623-624)
enthält offiziellen Beispielcode (`PrintSourceObjects`), der **rekursiv** über
`source.Children` absteigt:
```
SourceObjectComposition sourceObjectChildren = source.Children;
PrintSourceObjects(sourceObjectChildren);
```
Live an `DB_PrgFieldbusOkDb` nachvollzogen (`.Children` bis in die Tiefe gedumpt):
`GetCrossReferences(UnusedObjects)` liefert genau einen Wurzelknoten (Name == DB-Name,
`TypeName` "Instance DB of ...") — dessen `Children` enthalten `DiagCpu` (UDT-Struct,
selbst kein Blatt), dessen `Children` wiederum `DiagCpu.DNNmode` (echtes unbenutztes
Blatt-Member) enthalten. Der Runde-34-Fix hatte also nicht "einen Phantom-Eintrag
herausgefiltert", sondern schlicht den einzigen zurückgelieferten Wurzelknoten
komplett verworfen, ohne je in dessen Children abzusteigen — der Check meldete
dadurch seit jeher (auch schon vor Runde 34) faktisch nie ein echtes unbenutztes
DB-Member.

**Skalen-Check vor der Umsetzung:** Projektweite Testmessung der vollen
Children-Rekursion über alle 32 DBs ergab **41.087 rohe Blattknoten**, davon
**37.882 (92 %) mit `[...]`** im Namen — Array-Elemente, exakt dasselbe
Explosionsmuster wie beim historischen Array-Bug in Prüfpunkt 1. Nach Anwendung
desselben Array-Skip-Prinzips (ein Kommentar/eine Verwendung auf dem Array selbst
reicht) verblieben **3.205** echte, nicht-Array-Blattknoten. Da diese Änderung
projektweit auf einen Schlag von effektiv 0 auf über 3.000 Befunde springen würde,
per `AskUserQuestion` rückgefragt, ob die volle Rekursion trotzdem gewünscht ist
(Alternative: Tiefenbegrenzung auf die erste Ebene). User-Entscheidung: "Ja, voll
implementieren."

**Fix:**
- Neue Hilfsfunktion `unused_cross_reference_leaf_names()` in `_tia_helpers.py`:
  steigt rekursiv durch `.Children` ab, liefert nur echte Blattknoten (Objekte ohne
  eigene Children), überspringt dabei Array-Elemente (`[...]` im Namen).
- `UnbenutzteVariablenCheck` (`structure.py`) nutzt diese Funktion statt der
  flachen Source-Iteration; der vom DB-Namen (quotiert oder unquotiert) geführte
  Pfadanteil eines Blattnamens wird für eine lesbare Anzeige abgeschnitten
  (`DiagCpu.DNNmode` statt `"DB_PrgFieldbusOkDb".DiagCpu.DNNmode`).
- Docstring um einen "Achtzehnter Bug"-Abschnitt ergänzt, der den "Siebzehnter
  Bug"-Fix aus Runde 34 einordnet (behob den Phantom-Befund korrekt, verschluckte
  dabei aber unbeabsichtigt alle echten Treffer).

**Verifiziert gegen das echte Salzmaschine-Projekt:**
- `DiagCpu.DNNmode` wird jetzt korrekt als einziger Befund zu `DB_PrgFieldbusOkDb`
  gemeldet — exakt der vom User erwartete Treffer.
- Keine Array-Indizes in den Ergebnissen (0 Member-Namen mit `[...]`) — Explosion
  erfolgreich vermieden.
- Keine Phantom-Selbst-Einträge mehr (0 Fälle, in denen der Member-Name dem
  DB-Namen entspricht).
- Projektweit: **5 → 3.210 Befunde** (deckt sich mit der vorherigen Skalen-Schätzung
  von ~3.205).
- `pytest`: weiterhin 38/38 grün, `py_compile` fehlerfrei.

**Dokumentiert:** `docs/Handbuch.md` (Besonderheiten bei Prüfpunkt 11 überarbeitet —
Rekursions-/Array-Verhalten statt der überholten "Phantom-Filter"-Beschreibung aus
Runde 34, Version 0.34 + Anhang-C-Eintrag, der explizit auf die Korrektur von Version
0.33 verweist). `README.md` bewusst nicht geändert — reiner Bugfix an bestehendem
Verhalten.

Letzter Stand: "Prüfpunkt 11 nutzte für DB-Member bislang nur die Wurzel des von
Openness gelieferten Source-Baums, nicht dessen .Children — dadurch wurden seit
jeher praktisch nie echte unbenutzte DB-Member gefunden (der Runde-34-Fix behob nur
den irreführenden Wurzel-Phantom-Befund, verschluckte aber unbeabsichtigt die
eigentlichen Treffer mit). Fix: rekursive Children-Traversierung mit Array-Skip
(analog Prüfpunkt 1). Live verifiziert (DiagCpu.DNNmode korrekt erkannt, 5 → 3.210
Befunde projektweit nach Skalen-Rückfrage beim User), pytest 38/38 grün."

## Runde 36 — Grundlegende Überarbeitung Prüfpunkt 11 (Instanz-DBs raus, XML-Scan
rein), dabei zwei weitere stumme Bugs bei Prüfpunkt 26/27 entdeckt und behoben

**Ausgangspunkt (User-Einwand, nicht Fehlermeldung):** "Es macht doch keinen Sinn,
die Cross Reference eines Instanzdatenbausteins zu überprüfen. Da drin sind doch nur
die Variablen des FBs. [...] Wir beschränken uns also hier definitiv auf die interne
Verwendung, wenn möglich" — der User stellte das Grunddesign von Prüfpunkt 11 (Runde
33–35) infrage: Eine Instanz-DB hat keine eigene Logik, ob ein Member "benutzt" ist,
entscheidet sich im Code des FB. `CrossReferenceService.GetCrossReferences
(UnusedObjects)` an der Instanz-DB zählt aber jede Referenz mit, auch externe
Direktzugriffe von außen — genau solche sind unerwünscht und werden separat von
Prüfpunkt 26 gemeldet.

**Untersuchung, mehrstufig:**
1. Direkte `CrossReferenceService`-Abfrage am FB/FC/OB selbst (statt an der
   Instanz-DB) liefert **keinen Member-Baum** — live verifiziert an `LSNTP_Server`:
   genau ein Root-Source (der FB selbst, `children=0`, 214 aggregierte
   `References`/`Locations`). Der Member-Baum mit `.Children` existiert
   nachweislich nur bei DB-Objekten.
2. Selbst die aggregierten `References`/`Locations` dieses einen Root-Sources
   verraten bei einem Zugriff auf ein *eigenes* Interface-Member weder über
   `Location.Name` noch `Location.ReferencedAsName` (beide leer), welches Member
   gemeint ist — nur bei Referenzen auf fremde, benannte Objekte ist `Location.Name`
   gefüllt. Live an `LSNTP_Server`/`OrgPrg` verifiziert.
3. Live an mehreren echten Beispielen (`PlcTimeDb.ot_PlcTime`, `01PrgDb.
   lx_30M1StopGap`) bestätigt: Diese Member werden sowohl intern (im eigenen FB)
   als auch extern (von einem anderen Baustein) referenziert — `UnusedObjects`
   kann diese Fälle nicht unterscheiden, bestätigt den Einwand des Users.
4. User-Entscheidung nach Rückfrage: Lösung für **alle** Bausteinarten (FB/FC/OB)
   einheitlich über einen XML-Scan des eigenen Bausteincodes, statt
   CrossReferenceService für FB und einen anderen Mechanismus für FC/OB.
5. XML-Strukturuntersuchung (live an `LSNTP_Server` [SCL] und `40Alm`/`OrgPrg`
   [FBD] verifiziert): Ein Zugriff auf eine eigene Interface-Variable wird in SCL
   *und* FBD/LAD identisch als `<Access Scope="LocalVariable"><Symbol>
   <Component Name="..."/></Symbol></Access>` exportiert; Multiinstanz-Aufrufe
   entsprechend über `<Instance Scope="LocalVariable"><Component Name="..."/>
   </Instance>`. Bewusst nicht per Text-/Regex-Scan gelöst: Ein Bausteinaufruf
   listet die Parameternamen des *aufgerufenen* Bausteins (`<CallInfo><Parameter
   Name="..." Section="Input"/>`) — ohne `Scope="LocalVariable"`, würde bei einem
   Textvergleich sonst fälschlich als Verwendung einer gleichnamigen eigenen
   Variablen zählen.

**Fix (Prüfpunkt 11):**
- Neue Hilfsfunktion `local_variable_access_names()` in `_tia_helpers.py`.
- `UnbenutzteVariablenCheck` (`structure.py`): Instanz-DBs werden aus der
  Global-/Array-DB-Schleife jetzt bewusst ausgeschlossen (`isinstance(db,
  InstanceDB): continue`); neue dritte Schleife prüft FB/FC/OB direkt über
  `interface_section_members()` (Input/Output/InOut/Static/Temp — Temp bewusst
  mit eingeschlossen, abweichend von der Kommentar-Prüfpunkt-Konvention bei PP
  1c/26/27, da OBs sonst praktisch nie geprüft würden) gegen
  `local_variable_access_names()`.
- Live verifiziert: **163 Befunde** (5 PLC-Tags, 140 Global-/Array-DB-Member
  unverändert, **18 neue** FB/FC/OB-Member-Treffer, u. a. `OrgPrg > test`,
  `OrgPrg > Initial_Call`/`Remanence` — Standard-OB1-Parameter, die nie
  abgefragt werden). Stichprobenprüfung: keine der bekannten, stark genutzten
  Variablen (`connID`, `hwID`, `status` etc.) taucht fälschlich als unbenutzt auf.

**Nebenfund 1 — Prüfpunkt 26 seit Einführung stumm (Zwanzigster Bug):** Liest
`Location.Name` als zugreifenden Bausteinnamen — live in jedem Fall (intern wie
extern) `""`. Der echte Ort steht in `Location.ReferenceLocation`
(`@<Bausteinname> ▶ NWn (...)` bzw. `@<Bausteinname> ▶ Ln: x Cl: y` für SCL).
Fix: Bausteinname per Regex aus dem `@`-Präfix extrahiert.

**Nebenfund 2 — `find_source_child_by_name` fand nie ein einfaches Member
(Einundzwanzigster Bug):** Kindknoten im Kreuzreferenzbaum tragen den
DB-/FB-Namen als qualifizierendes Präfix (`'"01PrgDb".lx_30M1StopGap'` statt
`'lx_30M1StopGap'`) — der Namensabgleich verglich gegen den nackten Namen, ohne
das Präfix zu entfernen. Fix direkt in der gemeinsam genutzten Helper-Funktion
(Präfix wird vor dem Vergleich abgeschnitten). Mit beiden Fixes zusammen meldet
Prüfpunkt 26 erstmals einen echten Treffer.

**Nebenfund 3 — Multiinstanz-Metaeintrag-Fehlalarm (Zweiundzwanzigster Bug):**
Live an `4805PrgManDb.Man4805_27M11` gefunden: Multiinstanz-Member tragen neben
echten Nutzungsstellen (`ReferenceType.UsedBy`) einen Meta-Eintrag
(`ReferenceType.InstanceType`, `ReferenceLocation` z. B. `@"4805PrgMan".
Man4805_27M11 ▶ Data type`), der keine echte Codestelle ist, sondern nur die
Typbeziehung beschreibt — ohne Filter wurde das als Zugriff von einem (nicht
existierenden) Baustein mit diesem Namen fehlinterpretiert, ein Fehlalarm bei
**jedem** Multiinstanz-Member (18 von 19 Treffern vor diesem Fix). Fix:
Locations mit `ReferenceType.InstanceType` werden übersprungen.

**Verifiziert (Prüfpunkt 26) gegen Salzmaschine:** Mit allen drei Fixes exakt
**1 Befund** — `01PrgDb.lx_30M1StopGap`, extern zugegriffen von `01Vis` (der vom
User über das ursprüngliche Explorationsskript bereits bestätigte Fall).

**Nebenfund 4 — Prüfpunkt 27 seit Einführung ebenfalls stumm (Dreiundzwanzigster
Bug):** Derselbe Root-Cause wie Punkt 1 oben — `CrossReferenceService` direkt am
FB/FC liefert keinen Member-Baum, `find_source_child_by_name` fand dadurch nie
ein Member. Auf Nachfrage entschied der User, das trotz des Mehraufwands
vollständig zu reparieren (auch für FC, das keine Instanz-DB hat).

**Untersuchung/Fix (Prüfpunkt 27):** Neue Hilfsfunktion
`local_variable_write_counts()` in `_tia_helpers.py`, XML-basiert wie bei
Prüfpunkt 11, aber mit Lese-/Schreibrichtung:
- **SCL:** Ein `Access Scope="LocalVariable"` ist ein Schreibzugriff, wenn es
  direkt vor einem `Token Text=":="` steht (einfache Zuweisung, live an
  `error := TRUE;` in `LSNTP_Server` verifiziert: `Access` und `Token ":="` sind
  flache Geschwisterelemente direkt unter `StructuredText`) oder innerhalb eines
  `Parameter`-Elements direkt nach `Token Text="=>"` steht (Ausgangsparameter
  eines Aufrufs, z. B. `RD_SYS_T(OUT => tempSysTime)`).
- **FBD/LAD:** Pin-Rollen-Tabelle je nach `NameCon`-Namen im selben `Wire` wie
  die `IdentCon` des Access-Elements — live verifiziert: `operand` bei
  Coil/SCoil/RCoil (Beispiel `CtrFcParaRdWr`, `OrgPrg`), `out`/`out1` bei
  Logikgattern und Move (Beispiel `DiagnosticErrorInterrupt`), alle
  `in`/`in1`/`in2`/`bit`/`en`-Pins sind lesend. Auf die in diesem Projekt
  tatsächlich vorkommenden Part-Typen begrenzt (Coil/SCoil/RCoil/Move/Gt/Eq/Ne/
  Lt/Sr/Add/Ge/PBox/TON/Le/Sub/TOF/Div/Jump/NBox/Mul/Convert/Abs/Rs/Shl/Shr/
  ResetIECTimerCoil/And/GEO2LOG) — ein nicht gelisteter Part-Typ zählt
  konservativ nicht als Schreibzugriff.
- **Kreuzvalidierung:** Neuer XML-Mechanismus gegen die (zu diesem Zeitpunkt
  bereits reparierte) Instanz-DB-Methode gegengeprüft — beide Wege liefern für
  `LSNTP_Server.status`/`.error`/`.statusID` übereinstimmend je **4**
  Schreibzugriffe, exakte Übereinstimmung.
- `OutputMehrfachBeschriebenCheck` (`libraries.py`) auf `local_variable_write_
  counts()` umgestellt, CrossReferenceService komplett entfernt.

**Verifiziert (Prüfpunkt 27) gegen Salzmaschine:** Roher Scan über das gesamte
Projekt (alle Ordner): 229 Output-Member mit Mehrfachschreibzugriff — nahezu
ausschließlich `LGF_*`-Bausteine (Siemens-Standardbibliothek) und
`PrgBibAlpma`-Bausteine, alle unter `ProjectBib` (bereits projektweit
ausgeschlossen). Mit der echten Standardkonfiguration (`ausgeschlossene_ordner:
["ProjectBib"]`): **0 Befunde** — sauberes Ergebnis für den eigentlichen
Anwendercode.

**Verifiziert (gesamt):** `py_compile` fehlerfrei, `pytest` 38/38 grün,
kombinierter Live-Lauf aller drei Checks ohne Exception (163/1/0 Befunde).

**Dokumentiert:** `docs/Handbuch.md` Version 0.35 + Anhang-C-Eintrag,
Besonderheiten bei Prüfpunkt 11, 26 und 27 überarbeitet (Instanz-DB-Ausschluss
und XML-Mechanismus bei 11, Historie der beiden Stumm-Bugs bei 26, Historie und
FC-Abdeckung bei 27).

Letzter Stand: "Prüfpunkt 11 prüft Instanz-DBs nicht mehr eigenständig — FB-/FC-/
OB-Interface-Member werden stattdessen direkt am Bausteincode geprüft (nur
interne Verwendung zählt, sprachunabhängig für SCL/FBD/LAD). Dabei zwei weitere,
seit Einführung stumme Bugs bei Prüfpunkt 26 (Location.Name immer leer,
Kreuzreferenz-Präfix nie abgeglichen) und Prüfpunkt 27 (CrossReferenceService
liefert am FB keinen Member-Baum) gefunden und behoben — beide melden jetzt
erstmals echte Treffer (26: 1, mit voller Standardkonfiguration; 27: 0, sauber
für Anwendercode, 229 vor Bibliotheks-Ausschluss). Live kreuzvalidiert, pytest
38/38 grün. Bereit für Doku-Review und Commit-Freigabe durch den User."

## Runde 37 — Prüfpunkt 12/12b/13 überprüft (User-Auftrag, kein Bug gefunden)

**Ausgangspunkt:** Nach dem offenen Punkt aus Runde 36 ("Prüfpunkte 12, 13
noch nicht spezifisch re-geprüft") bat der User direkt: "schau dir Prüfpunkte
12 und 13 auch nochmal an."

**Untersuchung:** Anders als Prüfpunkt 26/27 arbeiten Prüfpunkt 12/12b/13
direkt auf **PLC-Tags** (`cross_reference_locations(tag)`), nicht auf
Bausteinen/DB-Membern — der in Runde 36 gefundene "kein Member-Baum am
FB"-Fallstrick betrifft sie strukturell nicht, da ein PLC-Tag selbst das
Abfrageobjekt ist (keine Dekomposition nötig).

1. Rohdaten-Dump für mehrere reale I-/Q-Tags (`I4805_6S31`, `O4805_27Y51`
   u. a.): Alle Locations sauber, `ReferenceType` durchgehend `UsedBy`, keine
   `InstanceType`-Metaeinträge wie bei den Multiinstanz-Membern in Runde 36 —
   `Location.Access` liefert zuverlässig Read/Write.
2. Live-Lauf aller drei Prüfpunkte gegen Salzmaschine (Standardkonfiguration,
   `ProjectBib` ausgeschlossen): **0 Befunde bei allen dreien.**
3. Skalen-Check zur Abgrenzung "echtes sauberes Ergebnis" vs. "Scan erfasst
   zu wenig": Das gesamte Projekt hat nur **42 PLC-Tags mit fester
   Hardware-Adresse** (19 Eingänge, 7 Ausgänge) — exakt deckungsgleich mit
   der Namenskonvention aus Prüfpunkt 6 (`name_matches_input=19,
   name_input_with_addr=19`, ebenso bei Output). Kein Scan-Fehler, sondern
   ein architektonisches Merkmal des Projekts: Die eigentliche Prozess-I/O
   läuft größtenteils **nicht** über PLC-Tags, sondern über ein
   I/O-Spiegel-Pattern (ein Organisationsbaustein kopiert Hardware-Tags in
   DB-Member) — genau das Muster, das in Runde 36 bereits als unbenutztes
   Static-Member `I4805_33S1` in `01Prg` auftauchte.

**Ergebnis:** Prüfpunkt 12/12b/13 sind technisch korrekt und bugfrei — ihre
Reichweite ist aber strukturell auf echte PLC-Tags beschränkt und erfasst die
gespiegelten DB-Member nicht. Per `AskUserQuestion` rückgefragt, ob das
genauer untersucht (Erkennung des Spiegel-Patterns) oder unverändert gelassen
werden soll. User-Entscheidung: unverändert lassen, nur dokumentieren.

**Dokumentiert:** `docs/Handbuch.md` Version 0.36 + Anhang-C-Eintrag,
Besonderheiten bei Prüfpunkt 12/12b/13 um einen Hinweis auf die
I/O-Spiegel-Einschränkung ergänzt. Keine Code-Änderung, `pytest` unverändert
38/38 grün (nichts am Check-Code geändert).

Letzter Stand: "Prüfpunkt 12/12b/13 auf Bug-Verdacht geprüft — keiner
gefunden, Rohdaten und Check-Logik sind sauber. Das Projekt hat aber nur 42
echte PLC-Tags insgesamt; die eigentliche I/O läuft über ein
DB-Spiegel-Pattern, das diese drei Prüfpunkte naturgemäß nicht sehen. Auf
User-Wunsch nur dokumentiert, nicht erweitert."

## Runde 38 — Neuer Parameter `unterelemente_pruefen` bei Prüfpunkt 11 (User-Auftrag, betriebliche Praxis)

**Ausgangspunkt:** User testet PP11 erneut, hat aber Änderungswünsche: In der
Praxis werden DB-Variablen vom Typ UDT/Struct oft **als Ganzes** an einen
anderen Baustein übergeben (z. B. `MeinFb(duStruct := "MeinDb".MeinStruct)`)
statt feldweise einzeln zugegriffen. `CrossReferenceService` markiert dabei
typischerweise nur den Struct-Knoten selbst als referenziert — einzelne,
nicht separat angefasste Unterfelder blieben bislang trotzdem als
"unbenutzt" gemeldet, was als Fehlalarm-Rauschen empfunden wurde.
User-Auftrag: neuer Parameter (Default `false`), der ein UDT-/Struct-Member
als Ganzes wertet — nur wenn es *komplett* unbenutzt ist, sollen die
Unterfelder trotzdem einzeln geprüft werden (unabhängig vom Parameter);
dieselbe Logik soll auch für FB/FC/OB-Member gelten.

**Rückfrage vor der Umsetzung** (`AskUserQuestion`, zwei offene
Designentscheidungen): (1) FB/FC/OB hat aktuell *gar keine*
Unterfeld-Granularität (nur die erste `Component` unter `Symbol` wird
erkannt) — soll das volle Detail-Verhalten (`true`) dort jetzt neu gebaut
werden, oder reicht vorerst nur die DB-Seite? User: **beides jetzt bauen.**
(2) Für die DB-Erkennung "als Ganzes verwendet" sollte zusätzlich
`CrossReferenceFilter.ObjectsWithReferences` abgefragt werden (laut
Referenzhandbuch das dokumentierte Gegenstück zu `UnusedObjects`), noch
nicht live verifiziert. User: **einverstanden.**

**Umsetzung:**
- Neue Hilfsfunktion `cross_reference_referenced_top_level_names()`
  (`_tia_helpers.py`): fragt `ObjectsWithReferences` am DB ab, liefert die
  Namen aller Top-Level-Member mit mindestens einer Referenz auf
  beliebiger Tiefe. Keine UDT/Struct-vs-Skalar-Typunterscheidung nötig —
  für Skalare ist "oberste Ebene" ohnehin gleichbedeutend mit dem einzigen
  Blatt, das Verhalten reduziert sich dort automatisch auf den Ist-Zustand.
- `UnbenutzteVariablenCheck` (DB-Zweig): unbenutzte Blattnamen werden nach
  Top-Level-Namen gruppiert; bei `unterelemente_pruefen: false` (Default)
  werden Blätter unterdrückt, deren Top-Level-Name in der
  "referenziert"-Menge auftaucht.
- Zwei neue Hilfsfunktionen für FB/FC/OB, die es vorher nicht gab:
  `interface_section_member_paths()` (löst die verschachtelte
  `<Sections>`-Deklaration eines Members rekursiv zu dotted Blattpfaden
  auf, analog zu `interface_section_members`, aber mit voller Tiefe) und
  `local_variable_access_paths()` (löst tatsächliche Code-Zugriffe
  entsprechend auf). `UnbenutzteVariablenCheck` (FB/FC/OB-Zweig) komplett
  auf diese beiden umgestellt — vorher gab es dort nur Top-Level-Vergleich
  ohne jede Unterfeld-Auflösung.
- Extrahierte Hilfsfunktion `strip_cross_reference_prefix()` (vorher eine
  lokale Closure in `find_source_child_by_name`), jetzt auch in
  `cross_reference_referenced_top_level_names()` und im DB-Zweig von PP11
  wiederverwendet.
- 13 neue Unit-Tests für die reinen XML-/String-Hilfsfunktionen
  (`tests/test_tia_helpers.py`), `pytest` 51/51 grün.

**Live-Verifikation gegen Salzmaschine (auf User-Bitte von mir statt vom
User durchgeführt, Zeitdruck — "möchte bis zum Wochenende fertig sein"),
zwei unabhängige Skripte, headless via `TiaConnectorV21`, rein lesend:**

1. **DB-Baumform bestätigt:** `ObjectsWithReferences` liefert exakt dieselbe
   Baumform wie `UnusedObjects` (`Sources[0]` = DB-Wurzel, `.Children` =
   Top-Level-Member, rekursiv) — an 6 realen Global-/Array-DBs
   (`SysDiagDb`, `OrgDb`, `FieldbusDb`, `FieldbusArrayDb`, `ConfigDb`,
   `V40Alm`) verglichen. Bei `FieldbusArrayDb` zusätzlich beobachtet: die
   Top-Level-Member `NetActive`/`NetAlm` tauchen in **beiden** Filtern auf
   (teils benutzte, teils unbenutzte Array-Indizes) — betrifft die neue
   Logik hier nicht, weil Array-Elemente bereits vorher über den
   `"["`-Skip aus `unused_cross_reference_leaf_names()` herausgefiltert
   werden, bevor die neue Gruppierung überhaupt ansetzt.
2. **FB/FC/OB-Annahme war falsch, noch vor Dokumentation korrigiert:**
   Erste Implementierung nahm an, TIA exportiere mehrstufige
   Struct-Zugriffe als ineinander verschachtelte `<Component>`-Elemente
   (`<Component><Component/></Component>`). Live-Dump der rohen XML an FB
   `PrgFieldbusOk` (`DiagCpu.SubordinateIOState`, `DiagCpu.SubordinateState`)
   und FC `CtrFcParaRdWr` (`lx_Step.Sc`) zeigt stattdessen eine **flache
   Geschwister-Liste** direkt unter `Symbol`:
   `<Symbol><Component Name="DiagCpu"/><Component Name="SubordinateIOState"/></Symbol>`.
   `_symbol_component_chain()` entsprechend vereinfacht (liest jetzt alle
   direkten `Component`-Geschwister statt zu rekursieren) — dadurch sogar
   kürzerer Code als die ursprüngliche (falsche) Annahme.
3. **End-to-End-Bestätigung:** `interface_section_member_paths()` liefert
   für FB `PrgFieldbusOk`, Member `DiagCpu`, korrekt drei Blattpfade
   (`DiagCpu.SubordinateState`, `DiagCpu.SubordinateIOState`,
   `DiagCpu.DNNmode`); `local_variable_access_paths()` findet davon zwei
   tatsächlich zugegriffen (`DiagCpu.SubordinateIOState`,
   `DiagCpu.SubordinateState`) plus einen direkten Zugriff auf `DiagCpu`
   selbst — `DiagCpu.DNNmode` bleibt unbenutzt (deckungsgleich mit dem
   bereits aus Runde 35 bekannten Befund am gleichnamigen DB-Member).
   Kompletter `UnbenutzteVariablenCheck`-Lauf gegen das ganze Projekt:
   `unterelemente_pruefen: false` → **174 Befunde** (5 Tags, 132
   DB-Member, 37 FB/FC/OB-Member), `true` → **8.023 Befunde** (5 Tags, 140
   DB-Member, 7.878 FB/FC/OB-Member). Der große Sprung bei FB/FC/OB
   bestätigt praktisch, warum `false` als Default sinnvoll ist — die neue
   Feld-Granularität dort würde ohne die Pauschal-Ausnahme ein Vielfaches
   an Rauschen erzeugen.

**Nachtrag, unmittelbar danach — Fünfundzwanzigster Bug (User-Meldung mit
konkretem Fall):** DB `V01St`, Variable `4805_27M11` (Typ `U_VisStFcFan`),
komplett als Aufrufparameter von `CtrFcFan` in `01Prg`/Netzwerk 16
verwendet — trotzdem meldete PP11 bei `unterelemente_pruefen: false` alle
Sub-Member als unbenutzt, die Pauschal-Ausnahme griff also nicht.

**Diagnose** (Live-Debug-Skript, gezielt an `V01St`/`4805_27M11`): Die neue
`cross_reference_referenced_top_level_names()` fand `4805_27M11` korrekt in
der "referenziert"-Menge (bestätigt per Direktabfrage). Der Fehler lag in
der Vergleichsseite: Der DB-Zweig von `UnbenutzteVariablenCheck` übernahm
den von `CrossReferenceService` gelieferten Blattnamen nach dem
Präfix-Abschneiden ungefiltert weiter — für ein Ziffernbeginn-Segment wie
`4805_27M11` liefert TIA dabei `"4805_27M11".M` (mit Anführungszeichen um
das Segment, siehe die schon länger bekannte Quotierungsregel bei
`normalize_member_path()`/`find_source_child_by_name`). Der neue
Top-Level-Vergleich `name.split(".", 1)[0] not in used_top_level` verglich
dadurch `'"4805_27M11"'` (mit Anführungszeichen) gegen `used_top_level`,
das über `cross_reference_referenced_top_level_names()` bereits normalisiert
(unquotiert) befüllt wird — ein struktureller Mismatch, der für **jeden**
Ziffernbeginn-Namen im Projekt griff, nicht nur für diesen einen Fall.

**Fix:** `normalize_member_path()` wird im DB-Zweig jetzt direkt nach
`strip_cross_reference_prefix()` angewendet — behebt den Vergleich und
säubert als Nebeneffekt auch die angezeigten Pfade (keine störenden
Anführungszeichen mehr in den Befund-Pfaden).

**Live erneut verifiziert:** `unterelemente_pruefen: false` sinkt von 174
auf **54 Befunde** insgesamt (DB-Member 132 → 12 — die meisten der 132 waren
also selbst falsch-positiv durch genau diesen Quotierungs-Bug, nicht nur
`4805_27M11`); `V01St > 4805_27M11` erzeugt jetzt korrekt keinen Treffer
mehr. `unterelemente_pruefen: true` unverändert bei 8.023 Befunden, zeigt
weiterhin korrekt alle sieben tatsächlich unbenutzten Blätter unter
`4805_27M11.M` (z. B. `4805_27M11.M.FcPI.StWord`) — der Detailmodus war nie
betroffen, da er nicht über `used_top_level` filtert. `pytest` weiterhin
51/51 grün (kein Test deckte diesen Vergleichspfad ab, da `structure.py`
mangels CLR-Unabhängigkeit nicht direkt unit-getestet wird — nur live
gefunden).

**Dokumentiert:** `docs/Handbuch.md` Version 0.37/Anhang-C-Eintrag um den
Bugfix ergänzt. Noch nicht committet — steht als Nächstes an.

Letzter Stand: "Neuer Parameter `unterelemente_pruefen` (Default `false`)
bei Prüfpunkt 11 fertig implementiert, für DB **und** FB/FC/OB, inkl. neuer
Unterfeld-Granularität bei FB/FC/OB, die es vorher gar nicht gab. Zwei
Kernannahmen live gegen Salzmaschine verifiziert — eine davon (verschachtelte
vs. Geschwister-Component-Elemente) war ursprünglich falsch und wurde vor
der Doku korrigiert. Danach vom User an einem konkreten Fall (`V01St >
4805_27M11`) ein Quotierungs-Bug gefunden und behoben, der die neue
Pauschal-Ausnahme für praktisch jeden Ziffernbeginn-DB-Member wirkungslos
gemacht hätte (132 → 12 DB-Befunde nach dem Fix). pytest 51/51 grün,
Handbuch aktualisiert. Committet und gepusht als `e779670`."

## Runde 39 — Sechsundzwanzigster Bug: Prüfpunkt 11b meldete jeden Global-/Array-DB fälschlich als unbenutzt

**Ausgangspunkt:** Direkt im Anschluss an Runde 38 wandte sich der User
Prüfpunkt 11b zu (schrieb "Prüfpunkt 12", meinte inhaltlich aber eindeutig
11b — Eingangs-Tags haben nichts mit Bausteinaufrufen zu tun). Kernaussage:
"Ein normaler DB wird niemals als Ganzes verwendet, immer nur die Items in
ihm... Sobald auch nur eine einzige Variable in einem DB verwendet wird,
wird er nicht mehr markiert." Zusätzlich zwei Anschlussfragen: sollen
Instanz-DBs jetzt auch getestet werden (mit der Präzisierung, dass ein
bloßer externer Member-Zugriff — an sich schon unerwünscht, siehe
Prüfpunkt 26 — nicht als "die Instanz wird benutzt" zählen soll, nur ein
echter `CALL`), und ist die Prüfung bei OB/FB/FC bereits korrekt.

**Verbindungsproblem zuerst:** Der erste Live-Verbindungsversuch schlug
fehl — das Projekt war noch vom User selbst in TIA Portal geöffnet
(`tasklist` bestätigte laufende `Siemens.Automation.Portal`/`.Object`-
Prozesse in der interaktiven Desktop-Session sowie `tia-linter.exe`).
Nicht angetastet, stattdessen den User gebeten, TIA Portal zu schließen —
danach klappte die headless-Verbindung.

**Untersuchung (Live-Skript, vier Teile):**
1. Kompletter PP11b-Lauf: 23 Befunde, **alle** außer zwei sind
   Global-/Array-DBs (`SysDiagDb`, `OrgDb`, `FieldbusDb`,
   `FieldbusArrayDb`, `ConfigDb`, `V01St`, `V40Alm` u. a. — 21 DB-Namen).
2. Stichprobe von 7 bekannt intensiv genutzten Global-/Array-DBs: direkte
   `cross_reference_locations(db)` liefert bei **allen** 0 Einträge —
   trotz 4 bis 21 tatsächlich benutzter Top-Level-Member laut
   `cross_reference_referenced_top_level_names()` (derselben
   Hilfsfunktion aus Runde 38). Bestätigt die User-Hypothese: Verwendung
   eines normalen DB registriert sich nie als direkte Referenz auf die
   DB-Wurzel selbst, nur auf ihre Member (`.Children`).
3. FB/FC-Stichprobe (10 Bausteine): Root-Referenzen korrelieren exakt mit
   tatsächlicher Nutzung (`PrgFieldbusOk` 541, `CtrPos` 363, ... bis
   `BibVersion` 0) — der bestehende Mechanismus funktioniert für FB/FC
   korrekt, keine Änderung nötig. Bestätigt die User-Vermutung "bei OB, FB
   und FC hast du das sowieso schon so gemacht".
4. Instanz-DB-Stichprobe (11 DBs, alle mit genutzter FB-Instanz):
   durchgängig exakt 2 Root-Referenzen — ein `CALL` referenziert die
   Instanz-DB offenbar zuverlässig direkt. Keine konkrete Gegenprobe im
   Projekt gefunden für den vom User beschriebenen Grenzfall (Instanz-DB
   nur per externem Member-Zugriff berührt, nie per `CALL`) — Mechanismus
   bleibt unverändert (dieselbe `cross_reference_locations`-Logik wie bei
   FB/FC), da kein Hinweis auf ein Problem vorliegt.

**Fix:** `UnbenutzteBausteineCheck` unterscheidet jetzt zwischen
Instanz-DB/FB/FC (weiterhin `cross_reference_locations`, Root-Referenz) und
Global-/Array-DB (neu: `cross_reference_referenced_top_level_names()` — DB
gilt als verwendet, sobald irgendein Member irgendwo referenziert ist,
dieselbe Hilfsfunktion, die Runde 38 für Prüfpunkt 11 gebaut hat). OBs
bleiben wie bisher komplett ausgenommen (Einstiegspunkte, kein
Anwendercode-Aufruf).

**Live verifiziert (Fix erneut gegen Salzmaschine):** **23 → 2 Befunde**
— alle 21 Global-/Array-DB-Fehlalarme verschwunden, verbleibend
`BibVersion` und `LGF_Description` (beides echte unbenutzte FCs,
`BibVersion` mit bestätigt 0 Root-Referenzen). `pytest` weiterhin 51/51
grün (kein neuer struktureller Test, da `structure.py` mangels
CLR-Unabhängigkeit nicht direkt unit-getestet wird).

**Nebenkorrektur:** Bei der Dokumentation dieser Runde eine
Nummerierungs-Kollision bei den fortlaufenden Bug-Ordinalzahlen bemerkt und
rückwirkend korrigiert — die in Version 0.37 als "Zwanzigster" bzw.
"Vierundzwanzigster" bezeichneten Punkte aus Runde 38 kollidierten mit den
in Runde 36 bereits vergebenen Nummern 19–23. Rückwirkend umbenannt:
`unterelemente_pruefen`-Feature = Vierundzwanzigster Bug, Quotierungs-Fix =
Fünfundzwanzigster Bug — dieser PP11b-Fix ist entsprechend korrekt der
Sechsundzwanzigste.

**Dokumentiert:** `docs/Handbuch.md` Version 0.38 (Besonderheiten bei
Prüfpunkt 11b ergänzt, Anhang-C-Eintrag inkl. Numerierungskorrektur). Noch
nicht committet — steht als Nächstes an.

Letzter Stand: "Prüfpunkt 11b prüfte Global-/Array-DBs über ein Signal
(direkte Root-Referenz), das bei DBs strukturell nie auftritt — dadurch
wurde praktisch jeder verwendete DB im Projekt fälschlich als unbenutzt
gemeldet (21 von 23 Befunden waren Fehlalarme). Fix nutzt dieselbe
Member-Ebenen-Prüfung wie Prüfpunkt 11. FB/FC/Instanz-DB waren bereits
korrekt und blieben unverändert. 23 → 2 Befunde, beide echte unbenutzte
FCs. pytest 51/51 grün, Handbuch aktualisiert. Committet und gepusht als
`d1cfca1`."

## Runde 40 — Siebenundzwanzigster Bug: Instanz-DB-Meta-Eintrag machte Prüfpunkt 11b für Instanz-DBs wirkungslos

**Ausgangspunkt:** User hat gezielt einen Testfall angelegt, um den in Runde
39 offen gelassenen Grenzfall zu prüfen: Instanz-DB `01TestOrgPrgDb` (FB
`01OrgPrg`), deren FB nirgends per `CALL` aufgerufen wird, deren 2
Static-Member aber extern in `01Org`/Netzwerk 6 zugegriffen werden.
Erwartung: Prüfpunkt 11b sollte sie trotzdem als unbenutzt markieren (ein
externer Member-Zugriff zählt laut User-Vorgabe aus Runde 39 nicht als
"die Instanz wird benutzt", nur ein echter `CALL`). Tatsächlich wurde sie
nicht markiert.

**Verbindungsproblem, diesmal selbstverschuldet:** Erster Live-Skript-Lauf
stürzte mit `UnicodeEncodeError` beim Ausgeben eines `▶`-Zeichens in
`Location.ReferenceLocation` ab (`cp1252`-Konsole). Kein TIA-Problem,
sondern reines Encoding — behoben mit `sys.stdout.reconfigure(encoding=
"utf-8", errors="replace")` am Skriptanfang, danach erneut sauber
verbunden.

**Diagnose (Detail-Dump der `Location`-Objekte):** `01TestOrgPrgDb` liefert
über `cross_reference_locations()` trotz fehlendem `CALL` genau **1**
Eintrag: `ReferenceLocation = '@01TestOrgPrgDb ▶ Type'`, `ReferenceType =
InstanceType`, `Access = InstanceDB`. Zum Vergleich liefert die
tatsächlich per `CALL` verwendete Instanz-DB `DB_PrgFieldbusOkDb` **2**
Einträge: denselben `InstanceType`-Meta-Eintrag **plus** einen echten
Treffer (`ReferenceType = UsedBy`, `@OrgPrg ▶ NW12 (Aufruf Feldbus
Diagnose)`). Der `InstanceType`-Eintrag ist also ein permanenter
Selbstverweis jeder Instanz-DB auf ihre eigene FB (Typbeziehung), keine
echte Codestelle — exakt dasselbe Muster, das in Runde 36 bereits bei
Prüfpunkt 26 auf **Member**-Ebene gefiltert wurde (siehe
`libraries.py::static_zugriff_extern`, Kommentar "Multiinstanz-
Metaeintrag-Fehlalarm"), hier aber unbemerkt auf **Root**-Ebene der
Instanz-DB selbst. `cross_reference_locations(instance_db)` war dadurch
nie leer — Prüfpunkt 11b konnte für Instanz-DBs de facto nie einen
Treffer melden, unabhängig davon, ob die FB tatsächlich aufgerufen wurde.

**Fix:** Im Instanz-DB-Zweig von `UnbenutzteBausteineCheck` werden
`Location`s mit `ReferenceType.InstanceType` jetzt vor der
Verwendungsprüfung herausgefiltert — übrig bleiben nur echte
Aufrufstellen. FB/FC/Global-/Array-DB-Zweige unverändert. Auf User-Wunsch
zusätzlich die Befundmeldung für Instanz-DBs eigenständig formuliert
(`"Baustein '<Name>' wird an keinem FB verwendet."` statt der generischen
Meldung, die für FB/FC/Global-/Array-DB unverändert bleibt).

**Live verifiziert:** `01TestOrgPrgDb` wird jetzt korrekt gemeldet, alle
zuvor bestätigten Fälle (`DB_PrgFieldbusOkDb`, `BibVersion`,
`LGF_Description`) unverändert. Kompletter PP11b-Lauf: **2 → 3 Befunde**.
`pytest` weiterhin 51/51 grün.

**Dokumentiert:** `docs/Handbuch.md` Version 0.39 (Besonderheiten bei
Prüfpunkt 11b ergänzt, Anhang-C-Eintrag). Noch nicht committet — steht als
Nächstes an.

Letzter Stand: "Der in Runde 39 offen gelassene Grenzfall (Instanz-DB nur
per externem Member-Zugriff berührt, nie per CALL) war tatsächlich ein
Bug: Jede Instanz-DB trägt einen permanenten Meta-Eintrag
(`ReferenceType.InstanceType`), der `cross_reference_locations()` nie leer
werden ließ — Prüfpunkt 11b konnte für Instanz-DBs strukturell nie einen
Treffer melden. Fix filtert diesen Meta-Eintrag heraus, echte Aufrufe
(`ReferenceType.UsedBy`) bleiben erhalten. Live am vom User selbst
angelegten Testfall `01TestOrgPrgDb` verifiziert, 2 → 3 Befunde. pytest
51/51 grün, Handbuch aktualisiert, noch nicht committet."

## Runde 41 — Achtundzwanzigster Bug: Prüfpunkt 14 sah kein einzelnes AWL-Netzwerk in einem sonst nicht-AWL-Baustein

**Ausgangspunkt:** User arbeitet sich Prüfpunkt für Prüfpunkt durch die
Salzmaschine durch ("einige Prüfpunkte waren ok. bin jetzt bei PP14.").
Hat gezielt ein AWL-Netzwerk in `01OrgPrg`/Netzwerk 16 eingefügt (Baustein
ist sonst KOP/FUP) — Prüfpunkt 14 hat es nicht gefunden/markiert.

**Diagnose:** `AwlCodeCheck` prüfte bislang ausschließlich
`block.ProgrammingLanguage == "STL"`, also die Grundsprache des ganzen
Bausteins. TIA Portal erlaubt aber, wie bei Prüfpunkt 10 und 15 bereits
bekannt, einzelne Netzwerke innerhalb eines Bausteins mit anderer
Grundsprache auf AWL umzuschalten — die Baustein-Grundsprache bleibt dabei
unverändert (`01OrgPrg` blieb z. B. weiterhin als FBD/KOP geführt), sodass
der reine Attribut-Check das AWL-Netzwerk strukturell nie sehen konnte.
Prüfpunkt 15 (`GemischteSprachenCheck`) löst exakt dasselbe Problem bereits
korrekt über den XML-Export je `CompileUnit`
(`compile_unit_attribute(cu, "ProgrammingLanguage")`) — derselbe
Mechanismus wurde für Prüfpunkt 14 übernommen.

**Fix:** Bausteine mit Grundsprache STL werden weiterhin komplett als ein
Befund gemeldet (unverändertes Verhalten). Bausteine mit Grundsprache SCL
werden übersprungen (kein netzwerkbasierter AWL-Umschalt-Fall möglich).
Für alle übrigen Bausteine (KOP/FUP/GRAPH) wird jetzt zusätzlich der
XML-Export durchsucht: jedes `CompileUnit`, dessen eigene
`ProgrammingLanguage` "STL" ist, wird einzeln mit Netzwerknummer gemeldet
(`src/tia_linter/checks/structure.py:486-521`).

**Verbindungsproblem vor der Verifikation:** `tasklist` zeigte
`Siemens.Automation.ObjectFrame.FileStorage.Server.exe` (PID 11516) in der
interaktiven Konsolensitzung mit ~1 GB Speicher — ein möglicherweise
offenes TIA-Portal-Projekt. Nachgefragt statt direkt beendet; User
bestätigte "ich habe nichts offen. bitte killen" — danach beendet, keine
weiteren Siemens-Prozesse in der Konsolensitzung übrig (nur reguläre
Hintergrunddienste in Session 0).

**Live verifiziert:** `git stash` des Fixes für eine Vorher/Nachher-Messung
(wie im Standardvorgehen). Vorher (unveränderter Code): **0 Befunde**.
Nachher (mit Fix): **2 Befunde** — `01OrgPrg`/Netzwerk 16 (der vom User
gemeldete Testfall) sowie zusätzlich ein bislang unentdeckter echter Fall
in `CtrFcParaRdWr`/Netzwerk 4 (`ProjectBib > PrgBibAlpma > General`).
`pytest` weiterhin 51/51 grün.

**Dokumentiert:** `docs/Handbuch.md` Version 0.40 (Besonderheiten bei
Prüfpunkt 14 ergänzt, Anhang-C-Eintrag). Noch nicht committet.

Letzter Stand: "Prüfpunkt 14 prüfte bislang nur die Grundsprache des
Bausteins, nicht die Sprache einzelner Netzwerke — ein per Copy&Paste auf
AWL umgeschaltetes Einzelnetzwerk in einem sonst KOP/FUP-Baustein
(`01OrgPrg`/NW16, vom User gezielt eingefügt) blieb dadurch unentdeckt.
Fix übernimmt denselben CompileUnit-Sprach-Check, den Prüfpunkt 15 bereits
nutzt. Live verifiziert: 0 → 2 Befunde (der gemeldete Testfall plus ein
bislang unbekannter echter Fall in `CtrFcParaRdWr`/NW4). pytest 51/51
grün, Handbuch aktualisiert, noch nicht committet."

## Runde 42 — Neuer Parameter bei Prüfpunkt 15 deckt Neunundzwanzigsten Bug auf: .NET-Enum-vs-String-Vergleich war projektweit an fünf Stellen wirkungslos

**Ausgangspunkt:** User geht weiter Prüfpunkt für Prüfpunkt durch, bestätigt
Prüfpunkt 15 als "gut programmiert, funktioniert so wie spezifiziert",
möchte die Logik aber erweitern: SCL-Netzwerke innerhalb eines sonst in
FUP programmierten Bausteins sind bei diesem Anwender betrieblich weit
verbreitet und kein Problem. Neuer Parameter `scl_in_fup_ignorieren`
(Standard `true`) gewünscht: bei `true` werden FUP-Bausteine mit
SCL-Netzwerken nicht markiert, bei `false` bleibt das bisherige Verhalten.

**Implementierung:** `GemischteSprachenCheck` liest den neuen Parameter
(Standard `true`) und überspringt den Befund, wenn die Baustein-
Grundsprache FUP ist und die gefundene Sprachmischung exakt {FUP, SCL}
ist — jede andere Kombination (KOP+SCL, FUP+AWL, drei Sprachen, ...)
bleibt unabhängig vom Parameter gemeldet. `config/default.yaml` um den
Parameter ergänzt (Standard `true`). pytest 51/51 grün.

**Live-Verifikation zeigt: Parameter wirkungslos.** Erster Lauf mit
`scl_in_fup_ignorieren = true` und `= false` lieferte in beiden Fällen
identisch 70 Befunde — keinerlei Unterschied. TIA Portal lief zu diesem
Zeitpunkt beim User interaktiv offen (mehrere `Siemens.Automation.Portal`/
`.Object`-Prozesse bis 3 GB plus laufendes `tia-linter.exe`); auf Nachfrage
bestätigte der User "hab alles geschlossen. alles killen wenn noch was
läuft" — verwaisten `Siemens.Automation.Object`-Prozess (PID 27612)
beendet, danach headless verbunden.

**Diagnose (Debug-Skript mit `repr()`/`str()`/`ToString()` an echten
Blöcken):** `get_attribute(block, "ProgrammingLanguage")` liefert kein
`System.String`, sondern ein
`Siemens.Engineering.SW.Blocks.ProgrammingLanguage`-.NET-Enum-Objekt
(`repr` zeigt `<ProgrammingLanguage.FBD: 3>`) — `block_language == "FBD"`
ist dadurch **immer** `False`, unabhängig vom tatsächlichen Wert. Live
bestätigt: `str(lang)` liefert zuverlässig den reinen Namen (z. B. `'FBD'`,
`'SCL'`, `'DB'`), `ToString()` liefert identisch dasselbe. Die
Netzwerk-eigene `ProgrammingLanguage` aus dem XML-Export
(`compile_unit_attribute`) ist dagegen bereits ein echter Text-String und
war nie betroffen.

**Ausmaß:** Dasselbe Bug-Muster (.NET-Objekt statt Text an einer
String-Vergleichsstelle) betraf `get_attribute(block,
"ProgrammingLanguage")`-Vergleiche an **fünf** Stellen im Code, nicht nur
im neuen PP15-Parameter:
- Prüfpunkt 3 (`NetzwerkBeschreibungCheck`, `comments.py`)
- Prüfpunkt 10 (`LeereNetzwerkeCheck`) — hatte bereits einen zusätzlichen,
  funktionierenden Netzwerk-eigenen Fallback-Skip (Version 0.31),
  praktisch also nicht beobachtbar betroffen
- Prüfpunkt 14 (`AwlCodeCheck`) — der block-weite "ganzer Baustein ist
  AWL"-Zweig aus Version 0.40 war ebenfalls nie erreichbar; durch den
  neuen Netzwerk-Fallback aus derselben Runde aber ohnehin bereits über
  den funktionierenden Pfad abgedeckt
- Prüfpunkt 15 (`GemischteSprachenCheck`) — dieser Bug hier, jetzt entdeckt
- Prüfpunkt 16 (`MaxNetzwerkElementeCheck`) — kein Fallback vorhanden,
  praktisch aber folgenlos, da SCL/STL-Netzwerke ohnehin nie als "Part"/
  "Call"-Elemente gezählt werden

Bemerkenswert: Dasselbe grundsätzliche Muster (.NET-Objekt statt
`System.String` an einer Stelle, die reinen Text erwartet) war bereits
einmal bei `reference_language(project).Culture` aufgetreten und dort
schon korrekt mit `str(...)` gelöst — nur an dieser `ProgrammingLanguage`-
Attributstelle blieb es unbemerkt, mutmaßlich weil im Salzmaschine-Projekt
bislang kein einziger Baustein existierte, dessen Grundsprache tatsächlich
SCL oder STL ist (die betroffenen Skips liefen dadurch immer ins Leere,
ohne dass es auffiel — erst der neue PP15-Parameter mit einem direkten
Vorher/Nachher-Vergleich machte es sichtbar).

**Fix:** Neue zentrale Hilfsfunktion `block_programming_language()` in
`_tia_helpers.py` kapselt `str(get_attribute(block,
"ProgrammingLanguage"))`. An allen fünf betroffenen Stellen eingesetzt
(`comments.py::NetzwerkBeschreibungCheck`, `structure.py::
LeereNetzwerkeCheck/AwlCodeCheck/GemischteSprachenCheck/
MaxNetzwerkElementeCheck`). Der bisher ungenutzt gewordene Import
`get_attribute` in `structure.py` entfernt (in `comments.py` weiterhin für
andere Attribute gebraucht).

**Live verifiziert (Vorher/Nachher, `git stash` der geänderten Dateien
gegen den letzten Commit):**

| Prüfpunkt | Vorher | Nachher |
|---|---|---|
| PP3 NetzwerkBeschreibungCheck | 194 | **46** |
| PP10 LeereNetzwerkeCheck | 167 | 167 (unverändert, hatte Fallback) |
| PP14 AwlCodeCheck | 2 | 2 (unverändert) |
| PP15 GemischteSprachenCheck | 70 | **2** |
| PP16 MaxNetzwerkElementeCheck | 0 | 0 (unverändert) |

Prüfpunkt 15 zeigt jetzt genau die erwarteten 2 verbleibenden Fälle
(`CtrFcParaRdWr`: drei Sprachen FBD+SCL+STL; `01OrgPrg`: FBD+STL, aus dem
in Runde 41 eingefügten Testnetzwerk) — alle 68 reinen FUP+SCL-Mischungen
korrekt unterdrückt. `pytest` weiterhin 51/51 grün.

**Dokumentiert:** `docs/Handbuch.md` Version 0.41 (Parameter-Tabelle und
Besonderheiten bei Prüfpunkt 15 ergänzt, Besonderheiten bei Prüfpunkt 3 um
Bugfix-Hinweis ergänzt, Anhang-C-Eintrag). Noch nicht committet.

Letzter Stand: "Der neue Parameter `scl_in_fup_ignorieren` bei Prüfpunkt 15
zeigte beim ersten Live-Test keinerlei Wirkung — Ursache war ein
.NET-Enum-vs-String-Vergleichsfehler: `GetAttribute(\"ProgrammingLanguage\")`
liefert kein `System.String`, sondern ein .NET-Enum-Objekt, wodurch jeder
Vergleich gegen einen Sprachcode wie `\"FBD\"` immer `False` war. Betraf
fünf Stellen im Code (Prüfpunkt 3, 10, 14, 15, 16), aber nur bei
Prüfpunkt 3 und 15 mit sichtbaren Auswirkungen (die anderen hatten bereits
funktionierende Fallbacks oder waren folgenlos). Fix: neue Hilfsfunktion
`block_programming_language()` mit `str(...)`-Konvertierung. Live
verifiziert: Prüfpunkt 3 194 → 46, Prüfpunkt 15 70 → 2 (Parameter greift
jetzt korrekt), die übrigen drei Prüfpunkte unverändert. pytest 51/51
grün, Handbuch aktualisiert, noch nicht committet."

## Runde 43 — Neues Feature bei Prüfpunkt 16: SCL-Netzwerke werden jetzt auf Zeilenzahl geprüft

**Ausgangspunkt:** User bittet um reinen Code-Review von Prüfpunkt 16 (ohne
Live-Verbindung, da TIA Portal beim User gerade selbst offen lief):
"checkst du auch SCL Netzwerke mit zu vielen Code-Zeilen?"

**Code-Review-Ergebnis:** Nein, aus zwei Gründen. (1) Der Skip
`block_programming_language(block) in ("SCL", "STL")` überspringt jeden
Baustein, dessen Grundsprache SCL ist, komplett — keine Prüfung für reine
SCL-Bausteine. (2) `compile_unit_element_count()` zählt ausschließlich
grafische `<Part>`/`<Call>`-XML-Elemente; ein einzelnes SCL-Netzwerk
innerhalb eines sonst grafischen Bausteins (z. B. `01OrgPrg`/NW3+8) wird
zwar nicht übersprungen, aber sein `<StructuredText>`-Inhalt enthält keine
`<Part>`/`<Call>`-Elemente — Elementanzahl also immer 0, unabhängig von
der tatsächlichen Zeilenzahl.

**User-Auftrag:** Erweitern mit zusätzlichem Parameter in der YAML, "bitte
immer beide yaml Dateien erweitern" (`config/default.yaml` — die
kommentierte Standard-Konfigurationsvorlage — sowie
`config/project_settings.yaml`, die gitignorte, personalisierte
Konfiguration des Users für sein reales Salzmaschine-Projekt mit
identischer Schlüsselstruktur, aber eigenen Werten).

**Implementierung:** Neue Hilfsfunktion `compile_unit_scl_line_count()` in
`_tia_helpers.py` — zählt `<NewLine>`-Elemente im XML-Export eines
Netzwerks (dieselbe Token-Struktur, mit der `_scan_scl_assignment_writes`
bereits SCL-Zuweisungen erkennt: `<Token>`/`<Access>`/`<Blank>`/
`<NewLine>`). N Zeilenumbrüche ergeben N+1 Zeilen; ein Netzwerk ganz ohne
`<Token>`/`<Access>`-Inhalt gilt als leer (0), nicht als eine Zeile.

`MaxNetzwerkElementeCheck` umgebaut: Der block-weite Skip greift jetzt nur
noch bei `"STL"` (nicht mehr zusätzlich bei `"SCL"`) — SCL-Bausteine werden
jetzt exportiert und geprüft. Pro Netzwerk entscheidet die
Netzwerk-eigene `ProgrammingLanguage`: bei `"SCL"` zählt
`compile_unit_scl_line_count()` gegen den neuen Schwellenwert
`max_zeilen_scl` (Standard `50`, analog zu `max_elemente`), sonst wie
bisher `compile_unit_element_count()` gegen `max_elemente`. AWL/STL bleibt
bewusst komplett ausgenommen (auch als einzelnes AWL-Netzwerk in einem
sonst nicht-AWL-Baustein) — gilt laut Prüfpunkt 14 ohnehin als veraltet,
kein Ausbauinteresse.

Beide YAML-Dateien um `max_zeilen_scl: 50` samt erklärendem Kommentar
ergänzt (`default.yaml` und `project_settings.yaml`, wie vom User
gefordert). `pytest` 51/51 grün nach der Implementierung.

**Live verifiziert (`git stash` von `structure.py`/`_tia_helpers.py` für
Vorher/Nachher, `project_settings.yaml` ist ohnehin nicht von Git
verfolgt):** Vorher (SCL komplett übersprungen): **0 Befunde**. Nachher
(mit Fix): **119 Befunde**, Zeilenzahlen zwischen 50 und 459 — weit
überwiegend in der mitgelieferten Siemens-Standardbibliothek
`PrgBibSiemens/LGF` (z. B. `LGF_SearchMinMax` mit 459 Zeilen,
`LGF_AstroClock` mit 350), aber auch einzelne echte Treffer in eigenen
Bausteinen (`PrgFieldbusOk`/Netzwerk 4 mit 256 Zeilen SCL,
`4805PrgMan`/Netzwerk 10 mit 107 Zeilen). `pytest` weiterhin 51/51 grün.

Mid-Round: Vor jeder Live-Verbindung `tasklist` geprüft — TIA Portal
mehrfach zwischenzeitlich mit laufendem `tia-linter.exe` und
`Siemens.Automation.Object` im Konsolen-Session interaktiv offen
vorgefunden (vermutlich der User selbst); jeweils gewartet, bis die
Prozesse von selbst verschwanden, bevor headless verbunden wurde. Nach
jedem eigenen Skript-Lauf blieb regelmäßig ein verwaister
`Siemens.Automation.Object`-Prozess zurück (Connector-`disconnect()`
schließt das Projekt/disposed TiaPortal, der Kindprozess selbst beendet
sich aber erst mit spürbarer Verzögerung) — jeweils vor dem nächsten Lauf
per `taskkill` beendet.

**Dokumentiert:** `docs/Handbuch.md` Version 0.42 (Parameter-Tabelle und
Besonderheiten bei Prüfpunkt 16 ergänzt, Anhang-C-Eintrag). Noch nicht
committet.

Letzter Stand: "Prüfpunkt 16 prüfte SCL-Netzwerke bislang überhaupt nicht
auf Komplexität — weder als eigenständiger SCL-Baustein (komplett
übersprungen) noch als einzelnes SCL-Netzwerk in einem sonst grafischen
Baustein (nicht übersprungen, aber mit der für Text ungeeigneten
Elementzählung immer 0). Neuer Parameter `max_zeilen_scl` (Standard `50`)
zählt jetzt stattdessen die Code-Zeilen eines SCL-Netzwerks anhand seiner
`<NewLine>`-XML-Elemente. Beide YAML-Dateien ergänzt. Live verifiziert:
0 → 119 Befunde, größtenteils in der Siemens-Standardbibliothek LGF.
pytest 51/51 grün, Handbuch aktualisiert, noch nicht committet."

## Runde 44 — Dreißigster Bug: Prüfpunkt 17 konnte bei ET200SP-Stationen nie anschlagen

**Ausgangspunkt (User-Meldung):** "PP17 steht an und funktioniert leider
nicht. Ich hab ein weiteres TIA Projekt angelegt, nur mit CPU ohne weitere
Hardware. Es liegt im übergeordneten Ordner unter Salzmaschine ->
S7T0159_V21_NoHW. Bitte schau dir mal an warum PP17 hier trotz fehlender
Hardware ohne Probleme durchläuft."

**Untersuchung:** Headless gegen `S7T0159_V21_NoHW` verbunden (analog zum
etablierten Live-Verify-Vorgehen, hier direkt zur Fehlersuche statt nur
zur Nachprüfung). `project.Devices` liefert genau 1 Gerät (`ET 200SP
station_1`), `device.DeviceItems` liefert **10** Einträge: `Rack_0`, CPU
`pn4805-15a1`, 6 echte I/O-Module (DI/DQ/AI), `Server module_1` und
`BA 2xRJ45` (Busadapter). Der bisherige Check
(`module_count = len(list(device.DeviceItems)); if module_count <= 1`)
ging implizit davon aus, dass ein Gerät ganz ohne Zusatzhardware genau 1
`DeviceItem` liefert (nur die CPU) — das stimmt nur für kompakte
CPU-Familien ohne eigenen Baugruppenträger-Eintrag (z. B. S7-1200). Bei
ET200SP-Stationen (wie in Salzmaschine durchgängig verwendet) legt TIA
zusätzlich zur CPU immer mindestens `Rack_0`, einen Busadapter und ein
Server-/Abschlussmodul als eigene `DeviceItems` an — physisch zwingend,
nicht vom User entfernbar. Damit kann `module_count` bei dieser
Stationsart nie unter 2–4 fallen, selbst bei einer PLC komplett ohne
I/O-Hardware — Prüfpunkt 17 hätte in der Praxis (ausschließlich
ET200SP-Projekte) **nie** anschlagen können. Bug bestand seit Einbau in
Runde 8 (17.07.2026), unentdeckt, weil dort nur der Positivfall ("Projekt
hat Hardware") verifiziert wurde, nie der Negativfall.

Attribut-Sondierung (`GetAttribute` auf jedem `DeviceItem`) fand mit
`PositionNumber` einen robusten, katalogunabhängigen Unterscheidungswert:
Rack=0, CPU=1, echte I/O-Module fortlaufend 2..N, Server-/Abschlussmodul
immer die höchste "normale" Positionsnummer (physisch zwingend als
letztes Modul im Baugruppenträger), Busadapter immer fest auf 127
(ET200SP-Sonderslot für Schnittstellenmodule, unabhängig vom konkreten
Adaptertyp/Bestellnummer). `Classification` erwies sich dagegen als
Sackgasse — nur die CPU trägt dort ein Flag (`CPU`), echte I/O-Module,
Server-Modul und Busadapter zeigen alle gleichermaßen `None`.

**Fix:** Neue Hilfsfunktion `count_additional_hardware_modules()`
(`_tia_helpers.py`) rechnet Baugruppenträger (`TypeIdentifier` beginnt mit
`"System:Rack"`), die CPU selbst (per `SoftwareContainer`/`PlcSoftware`-
Prüfung, identisch zu `iter_plc_targets()`) sowie bei ET200SP
(`"ET200SP"` im Rack-`TypeIdentifier`) den Busadapter
(`PositionNumber == 127`) und das Server-/Abschlussmodul (höchste
verbleibende Positionsnummer) heraus. `HardwareVorhandenCheck.run()`
nutzt jetzt `count_additional_hardware_modules(device) == 0` statt des
alten `len(list(device.DeviceItems)) <= 1`.

**Verifiziert:** `pytest` weiterhin 51/51 grün. Live-Vergleich
`S7T0159_V21_NoHW` gegen das Original-Salzmaschine-Projekt: Modulzahl
korrekt von 10 auf 6 reduziert (nur die 6 echten I/O-Module verbleiben,
Rack/Busadapter/Server-Modul zuverlässig herausgerechnet) — in beiden
Projekten identisch 6, da sich herausstellte, dass `S7T0159_V21_NoHW`
tatsächlich noch dieselben 6 I/O-Module wie das Original enthielt (vom
User nach Rückfrage bestätigt: "mein Fehler", kein Linter-Bug). Die
Korrektheit der neuen Zählfunktion selbst (10 → 6, exakt um die 4
Strukturelemente reduziert) ist damit live bestätigt; der volle
Negativfall (`module_count == 0` bei echter Nackt-CPU) ließ sich mangels
eines tatsächlich hardwarelosen Testprojekts nicht zusätzlich live
auslösen, ergibt sich aber zwingend aus derselben Zählweise.

**Dokumentiert:** `docs/Handbuch.md` Version 0.43 (Besonderheiten bei
Prüfpunkt 17 ergänzt, Anhang-C-Eintrag). Noch nicht committet.

Letzter Stand: "Prüfpunkt 17 verglich schlicht die Gesamtzahl an
`DeviceItems` gegen den Schwellenwert 1 — bei ET200SP-Stationen (Rack +
Busadapter + Server-Modul sind dort immer zusätzlich zur CPU vorhanden)
konnte dieser Schwellenwert dadurch nie unterschritten werden, der Check
war für den in Salzmaschine verwendeten Stationstyp faktisch wirkungslos.
Neue Hilfsfunktion `count_additional_hardware_modules()` rechnet
Baugruppenträger, CPU, Busadapter (`PositionNumber == 127`) und
Server-Modul (höchste verbleibende Positionsnummer) heraus. Live
verifiziert (10 → 6 Module im Testprojekt, Rest korrekt herausgerechnet).
pytest 51/51 grün, Handbuch aktualisiert, noch nicht committet."

## Runde 45 — Einunddreißigster Bug: Prüfpunkt 18c fand nie ein Zertifikat (falscher Namespace)

**Ausgangspunkt:** Direkter Anschluss an Runde 44, gleiches Testprojekt
`S7T0159_V21_NoHW`. User tauschte dort die CPU gegen eine F-CPU
(`CPU 1514SP F-2 PN`, `pn4805-15a1`) und testete zunächst Prüfpunkt 18b:
"Ohne Passwortschutz. PP18b läuft allerdings ohne Warnung durch."

**PP18b (Zwischenschritt, kein Bug):** Live geprüft — `device_item.
GetAttribute("TypeName")` bestätigt echte F-CPU-Hardware, aber
`GetAttribute("Failsafe_FCapabilityActivated")` liefert `False`. Laut
V21-Openness-Referenz (Abschnitt 1.4.19.9.2) ist die "F-Fähigkeit" ein
eigenes, separates Attribut am DeviceItem, unabhängig von der reinen
CPU-Typauswahl — ohne dessen Aktivierung existiert aus Openness-Sicht noch
kein aktives Sicherheitsprogramm, `GetService[SafetyAdministration]()`
liefert deshalb korrekterweise `None`, und Prüfpunkt 18b überspringt die
PLC zu Recht (kein Linter-Bug, sondern ein in TIA noch fehlender
Konfigurationsschritt). User aktivierte daraufhin die F-Fähigkeit selbst
in TIA Portal; PP18b funktionierte danach wie erwartet.

**PP18c (echter Bug):** User direkt im Anschluss: "Es ist ein Zertifikat
vorhanden, im TIA Portal Zertifikatemanager. Es wird auch im
'Kommunikationsmodus...' verwendet. Aber trotzdem wird PP18c als Fehler
markiert." (Zertifikat `pn4805-15a1/Communication-1`, ID 2.) Live-Probe
des headless-Skripts scheiterte sofort mit `ModuleNotFoundError: No
module named 'Siemens.Engineering.SW.Security'` — dieser Import steht
exakt so (unkommentiert im `try`) in `ZertifikatCheck.run()` und wird dort
von einer bewusst breiten `except Exception`-Klausel (gedacht für "Dienst
evtl. nicht verfügbar/keine Lizenz") stillschweigend abgefangen. Root
Cause per Reflection über die geladenen `Siemens.Engineering.*`-Assemblies
gesucht (Typensuche nach `"CertificateManager"` über alle geladenen
Assemblies blieb zunächst leer, da nur Base/Step7/WinCC/WinCCUnified
geladen sind und der fehlerhafte Import nie erfolgreich war) — der
Namensabgleich in `Siemens.Engineering.Base.xml` (mitgelieferte
Typ-Dokumentation) zeigte den tatsächlichen Namespace:
`Siemens.Engineering.Security.LocalCertificateManager`, ohne
`SW`-Zwischenebene. Der Bug bestand seit Einbau des Prüfpunkts,
unentdeckt, weil `cert_manager` dadurch **projektweit und unabhängig vom
tatsächlichen Zertifikatsstatus immer `None`** war — jede PLC wurde
unabhängig von der Realität als "kein Zertifikat vorhanden" (Fehler)
gemeldet, auch mit einem echten, gültigen, aktiv genutzten Zertifikat wie
hier.

**Fix:** Import in `hardware.py` von `Siemens.Engineering.SW.Security` auf
`Siemens.Engineering.Security` korrigiert (nur die eine Zeile betroffen,
`Certificate.Id`/`.ValidUntil` sind laut derselben XML-Dokumentation
bereits als direkte Properties vorhanden, keine weitere Anpassung nötig).

**Verifiziert:** `pytest` weiterhin 51/51 grün. Live gegen
`S7T0159_V21_NoHW` und zusätzlich zur Kontrolle gegen das
Original-Salzmaschine-Projekt (`ZertifikatCheck` isoliert über
`build_check_definitions()`/`config/project_settings.yaml` instanziiert,
ohne vollen Lint-Lauf): beide liefern jetzt identisch 1 Befund
`[OK] pn4805-15a1 > Zertifikate > 2: Zertifikat ist gültig (gültig bis
2057-10-28)` — exakt das vom User genannte Zertifikat, korrekt gefunden.

**Dokumentiert:** `docs/Handbuch.md` Version 0.44 (Besonderheiten bei
Prüfpunkt 18c ergänzt, Anhang-C-Eintrag). Noch nicht committet.

Letzter Stand: "Prüfpunkt 18c importierte `LocalCertificateManager` aus
dem falschen Namespace (`Siemens.Engineering.SW.Security` statt
`Siemens.Engineering.Security`) — der ImportError wurde von der breiten
Fehlerbehandlung stillschweigend verschluckt, wodurch jede PLC unabhängig
vom echten Zertifikatsstatus immer als 'kein Zertifikat vorhanden'
gemeldet wurde. Ein-Zeilen-Fix, live an einem echten vorhandenen
Zertifikat verifiziert (Status jetzt korrekt OK statt Fehler). pytest
51/51 grün, Handbuch aktualisiert, noch nicht committet."

## Runde 46 — Prüfpunkt 19: vollständige Feldliste ermittelt, Comment-Bug gefunden und behoben

**Ausgangspunkt (User-Wunsch):** "Ich würde bei PP19 gerne noch mehr
Felder prüfen. Mein TIA ist auf Deutsch, d. h. meine Namen in den
Eigenschaften stimmen nicht mit den Strings überein, die ich hier
eingeben müsste. Kannst du die komplette Liste an Möglichkeiten
herausfinden und in den YAML-Dateien dokumentieren. Und natürlich auch in
der weiteren Doku."

**Untersuchung:** `project.GetAttributeInfos()` liefert live gegen ein
echtes Projekt die vollständige, autoritative Liste aller 12 Top-Level-
Projektattribute samt aktuellem Wert: `Author` ("Mukara"), `Copyright`
(""), `CreationTime`, `Family` (""), `IsModified`, `IsPrimary`,
`LastModified`, `LastModifiedBy` ("Schlangen"), `Name`, `Path`, `Size`,
`Version` ("Ende Dev TBE"). Zusätzlich per Namensabgleich in der
deutschen V21-Openness-Referenz (Manual 03/2026, Abschnitt
"Projektbezogene Attribute lesen") die offizielle deutsche Bedeutung
jedes Feldes bestätigt — u. a. auch `Comment` (Kommentar des Projekts),
das `GetAttributeInfos()` selbst nicht zurückgab, laut Referenz aber
existiert.

Live-Test von `Comment` deckte einen bislang unbemerkten Bug auf:
`get_attribute(project, "Comment")` (der generische `GetAttribute`-Aufruf,
den `PflichtfelderCheck` bislang einheitlich für jedes Feld verwendete)
liefert dafür `None` — nicht das erwartete Objekt. Der korrekte Zugriff
ist die typisierte Property `project.Comment`, die ein
`Siemens.Engineering.MultilingualText`-Objekt liefert (`str(...)` davon
ergibt nur `"Siemens.Engineering.MultilingualText"`, kein Text) — exakt
dieselbe Fallstrick-Klasse wie beim mehrfach behobenen `Comment`-Attribut
auf Baustein-/Tag-Ebene (Runde 13/14/15), hier aber am Projekt-Objekt
selbst und bislang nie aufgefallen, weil `Comment` bisher nicht Teil der
Standard-`felder`-Liste war. Ein Nutzer, der `Comment` naiv zu `felder`
hinzugefügt hätte, hätte es **immer** als leer gemeldet bekommen,
unabhängig vom tatsächlichen Inhalt.

**Fix:** `PflichtfelderCheck` (`metadata.py`) behandelt `Comment` jetzt
als Sonderfall (`_MULTILINGUAL_FIELDS`-Set) und liest es über die
bereits bestehenden, an anderer Stelle schon bewährten Hilfsfunktionen
`read_comment()`/`reference_language()` — dieselbe Infrastruktur, die den
ursprünglichen Comment-Bug bei Bausteinen/Tags bereits löst. Bei der
Konfiguration selbst ist keine Sonderbehandlung nötig, `Comment` wird wie
jedes andere Feld einfach in `felder` eingetragen.

**Verifiziert:** `pytest` weiterhin 51/51 grün. Live gegen
`S7T0159_V21_NoHW` mit `felder: ["Author", "Comment", "Copyright",
"Family", "Version"]`: 3 Befunde (`Comment`, `Copyright`, `Family` leer
gemeldet — passend zum live beobachteten Projektzustand), `Author`
("Mukara") und `Version` ("Ende Dev TBE") korrekt als gefüllt erkannt,
keine Exception beim `Comment`-Zugriff. Ein echter Positivfall für ein
gefülltes `Comment`-Feld stand in keinem der beiden Testprojekte zur
Verfügung (beide leer) — die Korrektheit der Textextraktion selbst ist
aber durch die Wiederverwendung der bereits mehrfach live verifizierten
`read_comment()`-Funktion abgesichert.

**Dokumentiert:** Beide YAML-Dateien (`default.yaml`, `project_settings.yaml`)
um die vollständige Feldliste als Kommentar ergänzt; `project_settings.yaml`
zusätzlich auf Wunsch direkt um die drei neuen Felder erweitert
(`felder: ["Author", "Version", "Comment", "Copyright", "Family"]`).
`docs/Handbuch.md` Version 0.45 (vollständige Attributtabelle inkl.
Eignung als Pflichtfeld sowie Comment-Sonderfall bei Prüfpunkt 19
ergänzt, Anhang-C-Eintrag). Noch nicht committet.

Letzter Stand: "Komplette Liste der 12 Openness-Projektattribute per
`GetAttributeInfos()` live ermittelt und mit der deutschen V21-Referenz
abgeglichen. Dabei nebenbei einen weiteren Comment-MultilingualText-Bug
gefunden (`GetAttribute('Comment')` liefert `None`, korrekter Zugriff ist
`project.Comment` + `read_comment()`) und in `PflichtfelderCheck` behoben,
bevor er einem Nutzer beim Hinzufügen von `Comment` zu `felder` aufgefallen
wäre. Beide YAML-Dateien und Handbuch entsprechend dokumentiert. pytest
51/51 grün, noch nicht committet."

## Runde 47 — Prüfpunkt 21: Parameter `ignorierte_meldungen` für dauerhaft irrelevante Compiler-Meldungen

**Ausgangspunkt (User-Auftrag):** "Ich habe PP21 getestet und er scheint
gut zu funktionieren. Aber ich würde gerne 2 Warnungen unterdrücken
(dauerhaft). Und zwar tauchen für sehr viele schreibgeschützte Bausteine
2 Warnungen auf: '...since it is write-protected' und '...because it is
not editable'. Bitte dokumentiere in den YAML und definitiv im Handbuch,
dass diese Warnungen unterdrückt werden, da sie für irrelevant empfunden
werden. Sonst Kontaktaufnahme mit Entwickler."

**Umsetzung:** Kein Bug, sondern ein reines Feature — `KompilierfehlerCheck`
(`metadata.py`) bekommt einen neuen Parameter `ignorierte_meldungen`
(Standard `[]`): eine Liste von Regex-Mustern, die über `re.search` gegen
jede einzelne Compiler-Meldung geprüft werden; bei einem Treffer wird die
Meldung vollständig übersprungen, unabhängig von Baustein und Fehler-/
Warnungsstatus. Bewusst `re.search` statt des sonst in diesem Projekt für
Regex-Parameter üblichen `re.match` (siehe z. B. `ausnahme_titel_regex`
bei Prüfpunkt 10), weil ein Muster hier irgendwo im oft langen, frei
formulierten Meldungstext treffen soll, nicht nur an dessen Anfang.

**Verifiziert:** `pytest` weiterhin 51/51 grün. Auf einen vollständigen
Live-Recompile des echten Salzmaschine-Projekts wurde verzichtet (der User
hatte PP21 kurz zuvor bereits selbst erfolgreich live getestet, ein
erneuter voller Übersetzungsvorgang wäre für eine reine Textfilter-Ergänzung
unverhältnismäßig gewesen) — stattdessen die Regex-Logik isoliert gegen
realistische Beispielmeldungen geprüft: beide Muster treffen zuverlässig
(`"... cannot be changed since it is write-protected."`, `"... is not
compiled because it is not editable."`), eine dritte, unbeteiligte
Beispielmeldung bleibt unverändert erhalten.

**Dokumentiert:** `config/default.yaml` mit leerer Standardliste plus den
beiden Mustern als auskommentiertes Beispiel; `config/project_settings.yaml`
mit beiden Mustern aktiv gesetzt (dauerhaft unterdrückt, vom Nutzer
explizit als irrelevant eingestuft, mit Datum in der Konfiguration
vermerkt). `docs/Handbuch.md` Version 0.46 (Parameter-Tabelle und
Besonderheiten bei Prüfpunkt 21 ergänzt, Anhang-C-Eintrag). Noch nicht
committet.

Letzter Stand: "Neuer Parameter `ignorierte_meldungen` bei Prüfpunkt 21:
Liste von Regex-Mustern (re.search) gegen den Compiler-Meldungstext, ein
Treffer unterdrückt die Meldung dauerhaft. Auf Nutzerwunsch in
`project_settings.yaml` mit den beiden konkret genannten Mustern
('since it is write-protected', 'because it is not editable') aktiv
gesetzt. Regex-Logik isoliert getestet statt vollem Live-Recompile. pytest
51/51 grün, Handbuch aktualisiert, noch nicht committet."
