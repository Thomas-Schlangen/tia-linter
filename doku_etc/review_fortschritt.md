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
