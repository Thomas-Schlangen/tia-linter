# Claude Code Prompt — TIA Linter Grundgerüst

*Erstellt Juli 2026 — Für Session 1: Grundgerüst ohne TIA-Interaktion*

---

## Prompt

```
Wir bauen ein neues Python-Projekt namens "tia-linter" — ein Tool das TIA Portal Projekte
auf Qualität und Konventionen prüft und einen PDF-Report erstellt.

## Kontext & Referenzprojekte

Du hast Zugriff auf folgende bestehende Projekte — bitte frag nach wenn du sie nicht
findest:
- Tag Exporter: D:\Daten\Projekte\OpennessDev\tia-tag-exporter
  → Wiederverwendbar: connector.py (TIA-Verbindung), gui.py (Tkinter-Muster),
    logging-Setup, config-Loading, pyproject.toml Struktur
- Openness API Referenz (V18 PDF):
  ~/Dokumente/ObsidianVault/Projekte/TiaOpenness/TIAPortalOpenness_Referenz_V18_de.pdf
- Openness API Referenz (V21 PDF):
  ~/Dokumente/ObsidianVault/Projekte/TiaOpenness/TIAPortalOpenness_Referenz_V21_de.pdf
- Openness API Notizen:
  ~/Dokumente/ObsidianVault/Projekte/TiaOpenness/Openness-API-Referenz-fuer-Linter.md
  ~/Dokumente/ObsidianVault/Projekte/TiaOpenness/Openness-API-V21-Aenderungen.md

## Ziel dieser Session

Das vollständige Grundgerüst inklusive TIA-relevantem Code — aber **kein aktiver Testlauf gegen TIA Portal** in dieser Session, da wir auf Linux entwickeln und TIA Portal nur unter Windows läuft.

**Was in dieser Session gemacht wird:**
- Vollständiger TIA-Verbindungscode (connector.py) — direkt aus tia-tag-exporter übernehmen und anpassen, von dem wir wissen dass er funktioniert
- Alle check-Module mit echter Implementierungsstruktur (nicht nur leere Stubs)
- GUI, Config, Logging, Reporter — alles vollständig
- Simulierter Testlauf mit Dummy-Daten zum Testen der GUI und des PDF-Reports ohne TIA

**Was NICHT in dieser Session gemacht wird:**
- Kein aktiver Verbindungsaufbau zu TIA Portal
- Kein Test gegen ein echtes TIA-Projekt
- Das erfolgt in einer späteren Session auf Windows mit laufendem TIA Portal

## GitHub Repository

1. Neues GitHub Repo anlegen: `tia-linter` unter Thomas-Schlangen
2. Lizenz: GPL v3 (identisch zu tia-tag-exporter)
3. .gitignore für Python
4. README.md mit Projektbeschreibung (ähnlich Stil wie tia-tag-exporter)
5. Ersten Commit und Push

## Projektstruktur

```
tia-linter/
├── src/tia_linter/
│   ├── __init__.py
│   ├── main.py              # Einstiegspunkt
│   ├── gui.py               # Tkinter GUI
│   ├── connector.py         # TIA-Verbindung (nur Stub in dieser Session)
│   ├── config.py            # YAML-Config laden/validieren (aus Tag Exporter)
│   ├── settings.py          # GUI-Einstellungen persistent (settings.json)
│   ├── models.py            # Datenklassen: CheckResult, LintReport, CheckDefinition
│   ├── reporter.py          # PDF-Report (reportlab) — Grundgerüst
│   ├── runner.py            # Prüf-Orchestrierung (ohne TIA in dieser Session)
│   └── checks/
│       ├── __init__.py
│       ├── base.py          # Abstrakte Basisklasse für alle Checks
│       ├── comments.py      # Stub — Prüfpunkte 1-4
│       ├── naming.py        # Stub — Prüfpunkte 5-9
│       ├── structure.py     # Stub — Prüfpunkte 10-16
│       ├── hardware.py      # Stub — Prüfpunkte 17-18
│       ├── metadata.py      # Stub — Prüfpunkte 19-22
│       └── libraries.py     # Stub — Prüfpunkte 23-35
├── config/
│   └── default.yaml         # Standard-Konfiguration (alle Prüfpunkte)
├── tests/
│   └── test_models.py       # Erste Tests für Datenklassen
├── pyproject.toml
├── .gitignore
├── LICENSE                  # GPL v3
└── README.md
```

## TIA Portal Version

Das Programm ist aktuell **nur für TIA Portal V21** implementiert. Die Architektur soll aber
von Anfang an so aufgebaut sein, dass spätere Versionen (V22, V23 ...) einfach ergänzt
werden können.

**GUI — Versionsauswahl:**
- Dropdown-Liste in der Hauptseite (neben der TIA-Projektdatei-Auswahl)
- Aktuell nur ein Eintrag: `TIA Portal V21`
- Beschriftung: "TIA Portal Version"
- Letzte Auswahl in `settings.json` merken
- Spätere Versionen werden durch Hinzufügen eines Eintrags in der Config ergänzt

**Config (default.yaml) — Versionen:**
```yaml
tia_versionen:
  verfuegbar:
    - name: "TIA Portal V21"
      version: 21
      dll_pfad: "C:\\Program Files\\Siemens\\Automation\\Portal V21\\PublicAPI\\V21\\net48\\Siemens.Engineering.Base.dll"
  standard: "TIA Portal V21"
```

**connector.py — Versionslogik:**
- Nimmt die gewählte Version als Parameter
- Lädt die passende DLL basierend auf der Config
- Abstrakte Basisklasse `BaseTiaConnector` — pro Version eine konkrete Implementierung
- Aktuell: `TiaConnectorV21(BaseTiaConnector)`
- Spätere Versionen: einfach `TiaConnectorV22(BaseTiaConnector)` ergänzen


- Python 3.11+
- GUI: Tkinter (identisch zu Tag Exporter)
- PDF: reportlab
- Config: pyyaml (aus Tag Exporter übernehmen)
- Logging: aus Tag Exporter übernehmen
- Settings: eigene settings.json Lösung

## GUI — Anforderungen

Die GUI hat zwei Bereiche:

### Hauptseite (Eingabe)

**Auswahl 1 — TIA-Projektdatei:**
- Eingabefeld + "Durchsuchen" Button
- Filtert auf *.ap__ Dateien
- Letzten Pfad aus settings.json vorausfüllen

**Auswahl 2 — Output-Ordner:**
- Eingabefeld + "Durchsuchen" Button
- Letzten Pfad aus settings.json vorausfüllen

**Konfigurationsdatei:**
- Eingabefeld + "Durchsuchen" Button → andere YAML laden möglich
- Standard: config/default.yaml

**Prüfpunkte-Bereich:**
- Checkboxen gruppiert nach Kategorien:
  - Kommentare & Beschreibungen (Prüfpunkte 1-4)
  - Namenskonventionen (5-9)
  - Programmstruktur (10-16)
  - Hardware & Konfiguration (17-18c)
  - Projektmetadaten (19-22)
  - Bibliotheken & Typen (23-24)
  - Siemens Styleguide (25-35)
- "Alle auswählen" / "Alle abwählen" pro Kategorie und global
- Standardzustand kommt aus YAML-Config (nicht hardcodiert)

**Buttons:**
- "Prüfung starten" — startet Analyse (in dieser Session: simulierter Ablauf)
- "Abbrechen" — bricht laufende Prüfung ab

**Fortschritt:**
- Progressbar
- Status-Label ("Verbinde mit TIA Portal...", "Prüfe Kommentare... 3/47")
- Scrollbares Log-Fenster (Live-Ausgabe)

### Ergebnisseite (nach Prüfung)

- Zusammenfassung: X Fehler (rot), Y Warnungen (gelb), Z OK (grün)
- Tabelle mit allen Befunden:
  - Spalten: Status | Prüfpunkt | Pfad | Beschreibung
  - Filterbar nach Status und Kategorie
  - Doppelklick → Detail-Dialog mit Empfehlung zur Behebung
- Button "PDF-Report erstellen"
- Button "Neue Prüfung"

**Fenster-Einstellungen:**
- Position und Größe in settings.json merken
- Beim nächsten Start wiederherstellen

## Datenmodell (models.py)

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class CheckStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"

class CheckSeverity(Enum):
    WARNING = "warning"
    ERROR = "error"

@dataclass
class CheckDefinition:
    """Definition eines Prüfpunkts — kommt aus YAML-Config"""
    check_id: str           # z.B. "comments.variables"
    name: str               # Anzeigename
    category: str           # Kategorie für Gruppierung
    enabled: bool           # Aktiviert in dieser Prüfung
    severity: CheckSeverity # Standard-Schweregrad
    description: str        # Was wird geprüft
    recommendation: str     # Wie beheben

@dataclass
class CheckResult:
    """Ergebnis eines einzelnen Prüfpunkt-Befunds"""
    check_id: str
    check_name: str
    category: str
    status: CheckStatus
    path: str               # z.B. "PLC_1 > FB_Motor > Netzwerk 3"
    description: str        # Was ist das Problem
    recommendation: str     # Wie beheben
    value: str | None = None  # Aktueller problematischer Wert

@dataclass
class LintReport:
    """Gesamtergebnis einer Prüfung"""
    project_name: str
    project_path: str
    tia_version: str
    check_date: datetime
    checker_name: str       # Aus Config
    results: list[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.WARNING)

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.OK)
```

## Pfad-Format (WICHTIG — einheitlich überall)

```
PLC_1 > Programmbausteine > FB_Motor > Netzwerk 3
PLC_1 > Variablentabellen > Tags_Eingaenge > I_Sensor_01
PLC_1 > Datenbaustein > DB_Rezept > Member > Solltemperatur
Projekt > Eigenschaften > Autor
```

## YAML-Konfiguration (config/default.yaml)

Die Config definiert ALLE 35 Prüfpunkte mit:
- `enabled: true/false` — Standardzustand der Checkbox
- `severity: warning/error` — Schweregrad
- Alle konfigurierbaren Parameter (Regex, Schwellenwerte, Listen)

Beispielstruktur:
```yaml
report:
  pruefer: ""
  firma: ""
  logo_pfad: ""

checks:
  kommentare:
    variablen_kommentar:
      enabled: true
      severity: warning
      ausnahme_prefixe: ["_"]

    baustein_beschreibung:
      enabled: true
      severity: warning
      min_laenge: 20

    netzwerk_beschreibung:
      enabled: true
      severity: warning
      max_zeichen: 80

  namenskonventionen:
    db_format:
      enabled: true
      severity: error
      regex: "^DB_[A-Za-z]"

    plc_tag_eingaenge:
      enabled: true
      severity: error
      regex: "^I_"

    plc_tag_ausgaenge:
      enabled: true
      severity: error
      regex: "^Q_"

    fb_prefix:
      enabled: true
      severity: error
      prefix: "FB_"

    fc_prefix:
      enabled: true
      severity: error
      prefix: "FC_"

    testvariablen:
      enabled: true
      severity: warning
      prefixe: ["TEST_", "DEBUG_", "_TEMP"]

  programmstruktur:
    leere_netzwerke:
      enabled: true
      severity: warning

    awl_code:
      enabled: true
      severity: warning

    max_netzwerk_elemente:
      enabled: true
      severity: warning
      max_elemente: 50

    ausgaenge_mehrfach_schreiben:
      enabled: true
      severity: error

  hardware:
    hardware_vorhanden:
      enabled: true
      severity: error

    safety_passwort:
      enabled: true
      severity: error

    zertifikat:
      enabled: true
      severity: warning
      min_restlaufzeit_monate: 6

  projektmetadaten:
    pflichtfelder:
      enabled: true
      severity: warning
      felder: ["Autor", "Version"]

    max_sprachen:
      enabled: true
      severity: warning
      max: 2

    projektversion:
      enabled: true
      severity: warning

  bibliotheken:
    veraltete_bibliotheken:
      enabled: true
      severity: warning

    verwaiste_instanz_dbs:
      enabled: true
      severity: error

  styleguide:
    nicht_optimierte_bausteine:
      enabled: true
      severity: warning

    ob1_komplexitaet:
      enabled: true
      severity: warning
      max_netzwerke_mit_logik: 5

    know_how_schutz:
      enabled: true
      severity: warning

    schreibschutz:
      enabled: true
      severity: warning

    tag_tabellen_nur_io:
      enabled: true
      severity: warning

    bausteine_im_root:
      enabled: true
      severity: warning
      max_bausteine_root: 20
```

## connector.py — vollständig aus Tag Exporter übernehmen

Den vollständigen `connector.py` aus `tia-tag-exporter` kopieren und für den Linter anpassen.
Der Code ist bereits getestet und funktioniert — nicht neu erfinden.

Anpassungen gegenüber Tag Exporter:
- Abstrakte Basisklasse `BaseTiaConnector` einführen
- `TiaConnectorV21(BaseTiaConnector)` als konkrete Implementierung für V21
- DLL-Pfad aus Config laden (nicht hardcodiert) basierend auf gewählter Version
- Reconnect-Logik identisch übernehmen (TIA V19 Session-Instabilität bekannt)
- Gleiche Exception-Typen und Logging-Konventionen wie im Tag Exporter

## checks/base.py — Abstrakte Basisklasse

```python
from abc import ABC, abstractmethod
from tia_linter.models import CheckResult, CheckDefinition

class BaseCheck(ABC):
    def __init__(self, definition: CheckDefinition):
        self.definition = definition

    @abstractmethod
    def run(self, project) -> list[CheckResult]:
        """Führt den Prüfpunkt aus. project = TIA Openness Project-Objekt"""
        ...

    def _make_result(self, status, path, description, value=None) -> CheckResult:
        return CheckResult(
            check_id=self.definition.check_id,
            check_name=self.definition.name,
            category=self.definition.category,
            status=status,
            path=path,
            description=description,
            recommendation=self.definition.recommendation,
            value=value,
        )
```

## checks/*.py — vollständige Implementierung

Alle Check-Klassen vollständig implementieren — nicht nur Stubs. Der TIA-Code
kann geschrieben werden, auch wenn er auf Linux nicht gegen TIA getestet werden kann.

Jede Check-Datei enthält die vollständige Logik für ihre Prüfpunkte:

```python
class VariablenKommentarCheck(BaseCheck):
    def run(self, project) -> list[CheckResult]:
        results = []
        plc_software = ...  # aus project holen
        for tag_table in _iter_tag_tables(plc_software):
            for tag in tag_table.Tags:
                comment = tag.GetAttribute("Comment")
                if not comment or not comment.strip():
                    results.append(self._make_result(
                        status=CheckStatus.WARNING,
                        path=f"{plc_software.Name} > Variablentabellen > {tag_table.Name} > {tag.Name}",
                        description=f'Variable "{tag.Name}" hat keinen Kommentar.',
                        value=tag.Name
                    ))
        return results
```

Bei Unsicherheit über exakte API-Aufrufe: Openness-Referenz-PDFs und
`Openness-API-Referenz-fuer-Linter.md` im Obsidian Vault konsultieren.
Im Zweifelsfall lieber nachschauen als raten — falsche API-Aufrufe
führen später zu schwer findbaren Fehlern.

## reporter.py — Grundgerüst mit reportlab

- Klasse `PdfReporter` mit Methode `generate(report: LintReport, output_path: Path)`
- Deckblatt: Projektname, Prüfdatum, Prüfer, Firma
- Zusammenfassungsseite: Tabelle mit Kategorien + Fehler/Warnungs-Zähler
- Detailseiten: Pro Kategorie ein Abschnitt, pro Befund eine Zeile
- Farbkodierung: Fehler rot (#FF4444), Warnungen orange (#FFA500), OK grün (#44AA44)
- Fußzeile: Seitenzahl + Projektname
- Format: DIN A4
- Dateiname: `Lintreport_{projektname}_{datum}_{uhrzeit}.pdf`

## settings.py — GUI-Einstellungen persistent

```python
# Speichert/lädt in settings.json:
{
    "last_project_path": "",
    "last_output_folder": "",
    "last_config_path": "",
    "window_geometry": "1200x800+100+100"
}
```

## Logging

Identisch zu Tag Exporter übernehmen:
- Logging in Datei UND in das GUI Log-Fenster
- Dateiname: `Lintlog_{projektname}_{datum}_{uhrzeit}.log`
- Level: INFO für normalen Betrieb, DEBUG optional

## pyproject.toml

Identisch zu Tag Exporter als Vorlage — anpassen:
- name: `tia-linter`
- description: "TIA Portal Projekt Qualitätsprüfer"
- dependencies: tkinter (stdlib), pyyaml, reportlab, pydantic
- entry_point: `tia-linter = tia_linter.main:main`

## Simulierter Testlauf

Die GUI soll in dieser Session mit einem simulierten Prüflauf getestet werden können:
- Beim Klick auf "Prüfung starten" ohne echtes TIA-Projekt
- Simuliert 5-10 Dummy-CheckResults (mix aus Fehlern, Warnungen, OKs)
- Zeigt die komplette GUI inklusive Ergebnisseite
- PDF-Report wird mit Dummy-Daten generiert und gespeichert
- Damit kann die komplette GUI und der Report-Generator getestet werden

## Arbeitsweise

1. Zuerst GitHub Repo anlegen und pushen
2. Dann Projektstruktur anlegen
3. models.py und base.py zuerst (Fundament)
4. config.py und default.yaml (YAML aus Tag Exporter wiederverwenden)
5. settings.py
6. reporter.py (Grundgerüst mit Dummy-Daten testbar)
7. GUI (gui.py + main.py) — mit simuliertem Testlauf
8. Alle check-Stubs anlegen
9. Tests für models.py
10. Finaler Commit und Push

## Fortschritts-Tracking (WICHTIG)

Nach jedem abgeschlossenen Schritt aus der Arbeitsweise oben:
- Schreibe eine kurze Zusammenfassung was erledigt wurde in die Datei
  `~/Dokumente/ObsidianVault/Projekte/TIA-Linter/Session1-Fortschritt.md`
- Format:
```markdown
## Fortschritt Session 1

- [x] Schritt 1: GitHub Repo angelegt — https://github.com/Thomas-Schlangen/tia-linter
- [x] Schritt 2: Projektstruktur angelegt
- [x] Schritt 3: models.py und base.py fertig
- [ ] Schritt 4: config.py und default.yaml — IN ARBEIT
- [ ] Schritt 5: settings.py
...

### Letzter Stand
Zuletzt abgeschlossen: Schritt 3 (models.py, base.py)
Nächster Schritt: Schritt 4 — config.py aus Tag Exporter übernehmen,
dann default.yaml mit allen 35 Prüfpunkten erstellen.

### Offene Punkte / Probleme
- (hier eintragen wenn etwas unklar ist oder nicht funktioniert hat)
```

Wenn die Token nicht reichen und die Session neu gestartet werden muss:
- Lies zuerst `Session1-Fortschritt.md` um den aktuellen Stand zu kennen
- Lies dann den ursprünglichen Prompt aus `Claude-Code-Prompt-Session1.md`
- Mache dann genau dort weiter wo aufgehört wurde
- Kein Schritt der bereits erledigt und committed ist muss wiederholt werden

Bitte frag nach wenn du Zugriff auf den Tag Exporter oder andere Dateien brauchst.
Arbeite Schritt für Schritt und bestätige nach jedem größeren Schritt.
```
