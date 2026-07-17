# TIA Linter

Prüft TIA-Portal-Projekte auf Qualität und Konventionen (Kommentare,
Namenskonventionen, Programmstruktur, Hardware-Konfiguration, Projektmetadaten,
Bibliotheken, Siemens-Styleguide) über die **TIA Portal Openness API** und
erstellt einen PDF-Report der Befunde.

## Status

**Aktuell in Entwicklung.** Diese Version enthält das vollständige Grundgerüst
inklusive TIA-relevantem Code (Connector, alle Check-Module), wurde aber noch
**nicht gegen ein echtes TIA-Portal-Projekt getestet** — die Entwicklung
erfolgt auf Linux, TIA Portal läuft nur unter Windows. Getestet wurde die GUI
und der PDF-Report mit simulierten Dummy-Befunden.

## Voraussetzungen

- **TIA Portal V21** (weitere Versionen sind vorgesehen, siehe unten)
- **Python 3.11+**
- **Windows** (die Openness API ist eine Windows-.NET-Assembly)

## Disclaimer / Haftungsausschluss

**English**

This software is provided "as is", without warranty of any kind, express or implied. The author makes no representations or warranties regarding the accuracy, completeness, or suitability of this software for any particular purpose.

This tool is designed exclusively for reading and analyzing TIA Portal projects. It does not modify, write to, or interfere with any PLC configuration, program code, or machine control system.

The author assumes no liability for any direct, indirect, incidental, or consequential damages arising from the use or inability to use this software, including but not limited to:

- Data loss or data corruption
- Unplanned machine downtime or production loss
- Damage to equipment or infrastructure
- Personal injury or property damage

Use in safety-relevant systems (functional safety, SIL, Performance Level) is explicitly not recommended without independent verification by a qualified engineer.

By using this software, you agree that you use it entirely at your own risk.

**Deutsch**

Diese Software wird ohne jegliche ausdrückliche oder implizite Gewährleistung bereitgestellt. Der Autor übernimmt keine Garantie für die Korrektheit, Vollständigkeit oder Eignung der Software für einen bestimmten Zweck.

Dieses Tool dient ausschließlich dem Lesen und Analysieren von TIA-Portal-Projekten. Es nimmt keine Änderungen an SPS-Konfigurationen, Programmcode oder Maschinensteuerungen vor.

Der Autor übernimmt keine Haftung für direkte, indirekte oder Folgeschäden, die aus der Nutzung oder Nichtnutzbarkeit dieser Software entstehen, einschließlich, aber nicht beschränkt auf:

- Datenverlust oder Datenbeschädigung
- Ungeplante Maschinenstillstände oder Produktionsausfälle
- Schäden an Anlagen oder Infrastruktur
- Personen- oder Sachschäden

Die Verwendung in sicherheitsrelevanten Systemen (funktionale Sicherheit, SIL, Performance Level) wird ohne unabhängige Prüfung durch einen qualifizierten Ingenieur ausdrücklich nicht empfohlen.

Mit der Nutzung dieser Software erklärst du dich damit einverstanden, dass du sie auf eigenes Risiko verwendest.

## Installation

```bash
pip install -e .
```

## Konfiguration

1. `config/default.yaml` nach eigenem Bedarf kopieren (z. B. `config_kunde_a.yaml`).
2. TIA-Version und DLL-Pfad prüfen/anpassen:

```yaml
tia_versionen:
  verfuegbar:
    - name: "TIA Portal V21"
      version: 21
      dll_pfad: "C:\\Program Files\\Siemens\\Automation\\Portal V21\\PublicAPI\\V21\\net48\\Siemens.Engineering.Base.dll"
  standard: "TIA Portal V21"
```

3. Prüfpunkte, Schweregrade und Schwellenwerte nach Bedarf anpassen — siehe
   Kommentare in `config/default.yaml`.

Die Config wird über [`config_loader`](src/config_loader) gegen ein
Pydantic-v2-Schema validiert (`src/tia_linter/config.py`).

## Verwendung

```bash
tia-linter
```

Startet ein GUI-Fenster (Tkinter):

1. TIA-Projektdatei auswählen (`.ap*`).
2. Output-Ordner auswählen (Log-Datei und PDF-Report landen hier).
3. Konfigurationsdatei auswählen (Standard: `config/default.yaml`).
4. Gewünschte Prüfpunkte ankreuzen (gruppiert nach Kategorie).
5. "Prüfung starten" klicken — Fortschritt und Log laufen live mit.
6. Auf der Ergebnisseite die Befunde filtern, Details ansehen und den
   PDF-Report erstellen.

**Hinweis:** TIA Portal muss zur Prüfung nicht geöffnet sein — der Zugriff
erfolgt headless über `TiaPortalMode.WithoutUserInterface`.

## Geprüfte Kategorien

| Kategorie | Prüfpunkte |
|---|---|
| Kommentare & Beschreibungen | 1–4 |
| Namenskonventionen | 5–9 |
| Programmstruktur | 10–16 |
| Hardware & Konfiguration | 17–18c |
| Projektmetadaten | 19–22 |
| Bibliotheken & Typen | 23–24 |
| Siemens Styleguide | 25–35 |

Details zu allen 35 Prüfpunkten: siehe `config/default.yaml`
(`description`/`recommendation` je Prüfpunkt).

## Pfad-Format im Report

Jeder Befund zeigt den vollständigen Pfad zum betroffenen Objekt, einheitlich
formatiert:

```
PLC_1 > Programmbausteine > FB_Motor > Netzwerk 3
PLC_1 > Variablentabellen > Tags_Eingaenge > I_Sensor_01
PLC_1 > Datenbaustein > DB_Rezept > Member > Solltemperatur
Projekt > Eigenschaften > Autor
```

## TIA-Portal-Versionen

Aktuell nur für **TIA Portal V21** implementiert. Die Architektur ist so
aufgebaut, dass weitere Versionen (V22, V23, …) durch Ergänzen einer weiteren
`BaseTiaConnector`-Implementierung (z. B. `TiaConnectorV22`) und eines
weiteren Eintrags in `tia_versionen.verfuegbar` in der Config unterstützt
werden können — ohne Änderungen an GUI oder Check-Logik.

## Verbindungsstabilität (Reconnect)

TIA Portal V19 hat sich im Schwesterprojekt `tia-tag-exporter` wiederholt
nicht-deterministisch als instabil erwiesen — die Openness-Session kann
mitten in der Prüfung unerwartet sterben. `run_lint()` fängt das ab und
verbindet automatisch neu (bis zu `max_reconnect_attempts`, Standard `3`,
konfigurierbar in `config/default.yaml`). Bereits abgeschlossene Prüfpunkte
werden dabei nicht wiederholt — die Prüfung setzt genau bei den noch
fehlenden Punkten fort. Schlägt auch der letzte Versuch fehl, landet ein
Fehlerbefund zur Verbindung selbst im Report, statt die gesamte Prüfung
abzubrechen. Reconnects sind live im Log und in der GUI-Fortschrittsanzeige
sichtbar.

## Logging

Alle Läufe werden über [`my_logger`](src/my_logger) (stdlib `logging`)
protokolliert:
- Konsole und GUI-Log-Fenster: Live-Ausgabe
- Datei: `Lintlog_{projektname}_{datum}_{uhrzeit}.log` im gewählten
  Output-Ordner

## Projektstruktur

```
tia-linter/
├── src/
│   ├── tia_linter/
│   │   ├── main.py          # Einstiegspunkt
│   │   ├── gui.py            # Tkinter GUI
│   │   ├── connector.py       # TIA-Verbindung (Openness, pythonnet)
│   │   ├── config.py         # YAML-Config laden/validieren
│   │   ├── settings.py       # GUI-Einstellungen persistent (settings.json)
│   │   ├── models.py         # Datenklassen: CheckResult, LintReport, CheckDefinition
│   │   ├── reporter.py       # PDF-Report (reportlab)
│   │   ├── runner.py         # Prüf-Orchestrierung
│   │   └── checks/
│   │       ├── base.py       # Abstrakte Basisklasse für alle Checks
│   │       ├── comments.py   # Prüfpunkte 1-4
│   │       ├── naming.py     # Prüfpunkte 5-9
│   │       ├── structure.py  # Prüfpunkte 10-16
│   │       ├── hardware.py   # Prüfpunkte 17-18c
│   │       ├── metadata.py   # Prüfpunkte 19-22
│   │       └── libraries.py  # Prüfpunkte 23-35
│   ├── config_loader/        # Wiederverwendbare YAML/JSON-Config-Bibliothek
│   └── my_logger/            # Wiederverwendbare Logging-Bibliothek
├── config/
│   └── default.yaml          # Standard-Konfiguration (alle 35 Prüfpunkte)
├── tests/
├── pyproject.toml
└── LICENSE
```

## Bekannte Einschränkungen

- **`run_lint()` wurde erfolgreich gegen ein echtes TIA-Portal-V21-Projekt
  getestet** (288 Bausteine, 32 DBs) — vollständiger Lauf über alle 40
  Check-Einträge, kein Absturz, plausible Befundzahlen. Dabei gefunden und
  behoben: ein `EngineeringOutOfMemoryException`-Absturz nach ~30 Checks
  (TIA Portal begrenzt offene Openness-Objektinstanzen pro Session auf
  500.000 — behoben durch planmäßigen Reconnect alle `reconnect_every_n_checks`
  Prüfpunkte, siehe Abschnitt "Verbindungsstabilität"), ein falscher
  Namespace für `UpdateCheckMode` (Prüfpunkt 23) sowie ein `AttributeError`
  bei Prüfpunkt 17 (`device_item.Parent` lieferte nur ein generisches
  `IEngineeringObject` ohne `.DeviceItems`). `main.py` verwendet weiterhin
  standardmäßig `runner.simulate_lint_run()` (Dummy-Befunde) statt
  `run_lint()` — die Umstellung des Produktiv-Einstiegspunkts ist ein
  bewusster separater Schritt.
- **API-Zugriffe wurden gegen die TIA Portal V21 Openness-Referenz (Manual
  03/2026, lokal unter `~/Dokumente/ObsidianVault/Projekte/TiaOpenness/`)
  geprüft und mehrfach korrigiert** (u. a. `MemoryLayout` statt der
  ursprünglich angenommenen `IsOptimizedBlockAccess`, `ICompilable`-Dienst
  statt einer direkten `Compile()`-Methode, `CrossReferenceService` nur auf
  einzelnen STEP-7-Objekten statt auf der PLC-Software als Ganzes). Details
  und Fundstellen in den jeweiligen Klassen-Docstrings.
- **Netzwerk-Inhalte (Titel, Kommentar, Elementanzahl, Sprache pro Netzwerk)**
  werden über den XML-Export eines Bausteins gelesen (`Block.Export()` +
  Parsen des SIMATIC-ML-Dokuments, siehe `checks/_tia_helpers.py`) — die
  Openness-Referenz bestätigt den Export-Aufruf selbst und die
  Interface-Section-Struktur (`<Sections><Section Name="Static">`), aber
  nicht die exakten Netzwerk-Elementnamen (angenommen: `SW.Blocks.CompileUnit`
  mit `ProgrammingLanguage`/`Title`/`Comment`). Betrifft: Prüfpunkte 3, 10,
  15, 16, 30.
- **Prüfpunkte 26/27 (Static-/Output-Zugriff auf einzelne Interface-Member)**
  bleiben heuristisch: Die Referenz bestätigt, dass Member als namenlose
  Kind-Objekte im Kreuzreferenzbaum ihres Bausteins/DBs auftauchen, zeigt
  aber kein Codebeispiel dafür, welche `Location`-Eigenschaft den Namen des
  zugreifenden Bausteins trägt (`Location.Name` wird angenommen).
- Hardware-Adressabgleich (Prüfpunkt 17) ist vereinfacht auf "PLC ganz ohne
  Zusatzmodule" statt exaktem Adressbereichs-Abgleich pro I/O-Tag.

## License

This project is licensed under the GNU General Public License v3.0 — see the [LICENSE](LICENSE) file for details.
