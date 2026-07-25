# Claude Code Prompt — Standard Code Review

*Erstellt Juli 2026 — Vollständiger Code Review nach XML-Cache-Optimierung*

---

## Prompt

```
Lies zuerst:
~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/review_fortschritt.md
~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/md/XML-Optimierung-Fortschritt.md

Führe einen vollständigen Standard Code Review des tia-linter Projekts durch.
Der XML-Cache wurde bereits implementiert und gegen ein echtes TIA-Projekt
verifiziert — das ist der aktuelle Stand.

## Fokus-Punkte (besonders gründlich prüfen)

### 1. Test-Abdeckung
- Welche Module haben keine oder kaum Tests?
- Besonders: runner.py, reporter.py, gui.py, connector.py, checks/*.py
- Was wären die wichtigsten fehlenden Tests?
- Konkrete Vorschläge was als nächstes getestet werden sollte

### 2. Vollständigkeit der 35 Prüfpunkte
Prüfe ob alle 35 Prüfpunkte (inkl. 11b, 17b, 18b, 18c) korrekt
implementiert sind. Referenz:
~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/md/Pruefpunkte.md
(falls nicht vorhanden, frag nach)

- Welche Prüfpunkte sind vollständig implementiert?
- Welche sind nur als Stub vorhanden?
- Stimmen die Schweregrade (ERROR/WARNING) mit der Spezifikation überein?

### 3. Konsistenz nach XML-Cache-Refactoring
- Sind alle 10 Aufrufstellen von export_block_xml korrekt auf die
  neue Signatur export_block_xml(block, plc_software) umgestellt?
- Gibt es noch alte direkte Export()-Aufrufe die nicht gecacht werden?
- Ist der Cache-Reset nach Reconnect in runner.py korrekt eingebunden?

### 4. Standard Code Review
- Code-Qualität: Type Hints, Docstrings, Kommentare
- Namenskonventionen konsistent?
- Fehlerbehandlung vollständig?
- Keine hardcodierten Pfade oder Magic Numbers?
- Logging konsistent und sinnvoll?
- Gibt es doppelten Code der refactored werden sollte?
- Ist die Architektur noch sauber nach allen Änderungen?

### 5. PDF-Report
- Sind alle 35 Prüfpunkte im Report sauber dargestellt?
- Sind Fehler und Warnungen klar unterscheidbar?
- Ist das Pfad-Format einheitlich? (PLC_1 > FB_Motor > Netzwerk 3)
- Deckblatt, Zusammenfassung, Detailteil vollständig?

### 6. GUI
- Sind alle 35 Prüfpunkte als Checkboxen vorhanden?
- Gruppierung nach Kategorien korrekt?
- TIA-Version Dropdown vorhanden (V21)?
- Testmodus-Checkbox vorhanden?
- Letzte Einstellungen werden in settings.json gespeichert?

## Fortschritts-Tracking

Schreibe nach jedem geprüften Bereich den Status in:
~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/review_fortschritt.md

Format:
- [x] Test-Abdeckung geprüft
- [x] 35 Prüfpunkte verifiziert
- [ ] Konsistenz XML-Cache — IN ARBEIT
...

Falls die Session abbricht — beim Neustart diese Datei lesen
und genau dort weitermachen.

## Ausgabe

Strukturierter Bericht mit:
- ✅ Was ist vollständig und korrekt
- ⚠️ Was ist vorhanden aber verbesserungswürdig
- ❌ Was fehlt oder ist falsch
- 📋 Priorisierte Liste der empfohlenen nächsten Schritte

Fang NICHT an Code zu ändern — erst Bericht erstellen
und auf meine Freigabe warten.
```
