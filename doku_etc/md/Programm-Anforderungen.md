# TIA Projekt Linter — Programm-Anforderungen

*Erarbeitet Juli 2026 — Basis für späteren Claude Code Prompt*

---

## GUI (Grafische Oberfläche)

### Hauptseite

- **Auswahl 1: TIA-Projektdatei** — Eingabefeld + "Durchsuchen" Button → Auswahl der `.ap__` Projektdatei die geprüft werden soll
- **Auswahl 2: Output-Ordner** — Eingabefeld + "Durchsuchen" Button → Ordner in den sowohl die Log-Datei als auch der PDF-Report gespeichert werden
- **Letzte Einstellungen merken** — zuletzt verwendeter Projektpfad und Output-Ordner beim nächsten Start vorausfüllen (gespeichert in `settings.json`)
- **Fensterposition und -größe merken** — ebenfalls in `settings.json`
- **Prüfpunkte als Checkboxen** — jeder Prüfpunkt (aus Pruefpunkte.md) kann einzeln an- oder abgewählt werden
- **Standardzustand der Checkboxen** kommt aus YAML-Konfigurationsdatei — nicht hardcodiert
- **Gruppierung der Checkboxen** nach Kategorien (Kommentare, Namenskonventionen, Programmstruktur, Hardware, Projektmetadaten, Bibliotheken) — übersichtlicher als eine lange Liste
- **"Alle auswählen" / "Alle abwählen"** Button pro Kategorie und global
- **Konfigurationsdatei-Auswahl** — Möglichkeit eine andere YAML-Config zu laden (für verschiedene Kunden/Styleguides)
- **"Prüfung starten"** Button — startet die Analyse
- **"Abbrechen"** Button — bricht eine laufende Prüfung sauber ab
- **Fortschrittsanzeige** — Progressbar + aktueller Status ("Prüfe Netzwerkbeschreibungen... 45%")
- **Log-Fenster** — Live-Ausgabe während der Prüfung (scrollbar)

### Ergebnisseite (nach Prüfung)

- **Zusammenfassung oben** — X Fehler, Y Warnungen, Z OK (farbig: rot/gelb/grün)
- **Ergebnistabelle** — filterbar nach Status (Fehler / Warnung / OK), nach Kategorie, nach Baustein
- **Vollständiger Pfad bei jedem Befund** — z.B. `PLC_1 > Programmbausteine > FB_Motor > Netzwerk 3` oder `PLC_1 > Variablentabellen > Tags_Eingaenge > I_Sensor_01`
- **Doppelklick auf Befund** — öffnet Details (vollständige Beschreibung, Empfehlung zur Behebung)
- **Report erstellen** Button — generiert PDF-Report

---

## Report (PDF)

- **Dateiname automatisch generiert** — z.B. `Lintreport_ProjektName_2026-07-15_14-30.pdf` damit mehrere Reports nicht überschrieben werden
- **Log-Datei gleiche Logik** — z.B. `Lintlog_ProjektName_2026-07-15_14-30.log`
- **Deckblatt** mit Projektname, Prüfdatum, TIA-Version, Prüfer (aus Config)
- **Zusammenfassung** — Übersicht aller Kategorien mit Fehler/Warnungs-Zähler als Tabelle
- **Detailteil** — pro Kategorie ein Abschnitt, pro Befund eine Zeile mit:
  - Vollständiger Pfad (z.B. `PLC_1 > FB_Motor > Netzwerk 3`)
  - Status (❌ Fehler / ⚠️ Warnung)
  - Beschreibung des Problems
  - Empfehlung zur Behebung
- **Farbkodierung** — Fehler rot, Warnungen gelb, OK grün
- **Fußzeile** mit Seitenzahl und Projektname
- **Format:** DIN A4, professionelles Layout (kein "generiert von Python" Aussehen)

---

## Konfiguration (YAML)

- **Prüfpunkte aktivieren/deaktivieren** — jeder Prüfpunkt hat einen Key der auf `true` oder `false` gesetzt werden kann
- **Schweregrad pro Prüfpunkt** — `fehler` oder `warnung` (überschreibt den Standard)
- **Namenskonventionen** — Regex-Muster für DBs, Tags, Bausteine
- **Schwellenwerte** — z.B. max. Zeichen pro Netzwerkbeschreibung, max. Elemente pro Netzwerk
- **Testvariablen-Präfixe** — Liste der zu prüfenden Präfixe
- **Pflichtfelder Projektmetadaten** — Liste der Felder die ausgefüllt sein müssen
- **Report-Einstellungen** — Firmenname, Logo-Pfad, Prüfer-Name für Deckblatt
- **Mehrere Config-Profile möglich** — z.B. `config_kunde_A.yaml`, `config_intern.yaml`

---

## Technisches Konzept

### Stack
- **Python** (konsistent mit Tag Exporter)
- **GUI:** Tkinter (konsistent mit Tag Exporter) — oder PySide6 für moderneres Aussehen (entscheiden)
- **PDF-Erzeugung:** `reportlab` oder `weasyprint` (HTML → PDF)
- **YAML:** `pyyaml` (bereits im Tag Exporter als Abhängigkeit)
- **TIA-Anbindung:** pythonnet + TIA Openness (identisch zu Tag Exporter)

- **Reconnect-Logik** — identisch zum Tag Exporter — TIA V19 kann die Session während der Analyse verlieren, besonders bei großen Projekten
- **Abbruch-Button** — bricht die Prüfung sauber ab ohne TIA Portal zum Absturz zu bringen
- **Einstellungen persistent** — letzter Projektpfad, Output-Ordner, Fenstergröße in `settings.json`
```
tia-linter/
├── src/tia_linter/
│   ├── main.py          # GUI-Einstiegspunkt
│   ├── gui.py           # Tkinter-Oberfläche
│   ├── connector.py     # TIA-Verbindung (aus Tag Exporter wiederverwenden)
│   ├── checks/          # Ein Modul pro Kategorie
│   │   ├── comments.py      # Prüfpunkte 1-4
│   │   ├── naming.py        # Prüfpunkte 5-9
│   │   ├── structure.py     # Prüfpunkte 10-16
│   │   ├── hardware.py      # Prüfpunkte 17-18
│   │   ├── metadata.py      # Prüfpunkte 19-22
│   │   └── libraries.py     # Prüfpunkte 23-24
│   ├── reporter.py      # PDF-Report-Erzeugung
│   ├── config.py        # YAML-Config laden/validieren
│   └── models.py        # Datenklassen: CheckResult, LintReport
├── config/
│   └── default.yaml     # Standard-Konfiguration
├── pyproject.toml
└── README.md
```

### Datenmodell (Idee)
```python
@dataclass
class CheckResult:
    check_id: str           # z.B. "comments.variables"
    status: str             # "ok" | "warning" | "error"
    path: str               # Vollständiger Pfad zum Problem
    description: str        # Was ist das Problem?
    recommendation: str     # Wie beheben?
    value: str | None       # Aktueller Wert (z.B. der problematische Name)

@dataclass
class LintReport:
    project_name: str
    tia_version: str
    check_date: datetime
    results: list[CheckResult]
    errors: int
    warnings: int
```

---

## Pfad-Format (wichtig für Usability)

Jeder Befund muss den vollständigen Pfad zeigen damit der Programmierer sofort weiß wo er suchen muss. Einheitliches Format:

```
PLC_1 > Programmbausteine > Gruppen > Antriebe > FB_Motor > Netzwerk 3
PLC_1 > Variablentabellen > Tags_Eingaenge > I_Sensor_Druck_01
PLC_1 > Datenbaustein > DB_Rezept > Member > Solltemperatur
HMI_1 > Variablentabellen > HMI_Tags > HMI_Sollwert
Projekt > Eigenschaften > Autor
```

---

## Nice-to-Have (spätere Version)

- **Vergleichsmodus** — zwei Prüfberichte vergleichen (hat sich was verbessert?)
- **Exportformate** — zusätzlich zu PDF auch Excel-Export der Befunde
- **Direktlink ins TIA Portal** — wenn möglich über Openness den Fokus auf den betroffenen Baustein setzen
- **Baseline speichern** — aktuellen Stand als "akzeptiert" markieren, beim nächsten Lauf nur neue Probleme anzeigen
- **Automatischer Lauf** — CLI-Modus ohne GUI für CI/CD-Integration (z.B. vor jedem Git-Commit)
- **Mehrere PLCs** — Report über alle PLCs im Projekt in einem Durchlauf

---

## Entschiedene Punkte

- [x] GUI-Framework: **Tkinter** (konsistent mit Tag Exporter)
- [x] Scope: **nur PLC** — HMI in späterer Version
- [x] Output-Ordner: **eine Auswahl für beides** — Log-Datei und PDF-Report landen im selben Ordner

## Offene Entscheidungen

- [x] PDF-Bibliothek: **reportlab** — direkte PDF-Erzeugung, keine externen Abhängigkeiten, stabil auf Windows
- [ ] Soll es einen CLI-Modus geben (für spätere Automatisierung)?

---

*Verknüpft mit: [[Pruefpunkte]] | [[Ideen-und-Nischen]]*
*Nächster Schritt: Claude Code Prompt aus dieser Datei + Pruefpunkte.md erstellen*
