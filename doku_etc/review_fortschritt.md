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
