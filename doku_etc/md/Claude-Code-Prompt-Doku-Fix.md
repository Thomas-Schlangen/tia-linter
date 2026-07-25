# Claude Code Prompt — Doku-Fix (Prüfpunkte + Terminologie)

*Erstellt Juli 2026 — Runde 14: Dokumentation nachziehen*

---

## Prompt

```
Lies zuerst:
~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/review_fortschritt.md

Runde 13 des Reviews hat 2 Doku-Lücken identifiziert die jetzt geschlossen
werden. Kein Code wird geändert — nur Dokumentation.

## Aufgabe 1 — Pruefpunkte.md um 1b/1c/12b ergänzen

Datei: ~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/md/Pruefpunkte.md

Alle drei Prüfpunkte sind bereits vollständig im Code implementiert
und gegen das Salzmaschine-Projekt verifiziert — die Referenzliste
wurde nur nie nachgezogen.

Bitte:
1. Schau dir im Code (checks/*.py) nach was 1b, 1c und 12b konkret prüfen
2. Formuliere für jeden einen vollständigen Eintrag analog zu den
   bestehenden Einträgen — mit:
   - Was wird geprüft
   - Hintergrund / Warum wertvoll
   - Status bei Verstoß (ERROR/WARNING)
   - Implementiert: - [x]
3. Füge sie an der richtigen Stelle in Pruefpunkte.md ein
   (1b/1c direkt nach Prüfpunkt 1, 12b direkt nach Prüfpunkt 12)
4. Aktualisiere die Übersichtstabelle am Ende der Datei entsprechend

## Aufgabe 2 — Terminologie vereinheitlichen

Die Anzahl der Prüfpunkte wird in verschiedenen Dateien unterschiedlich
angegeben (33, 34, 35). Bitte vereinheitlichen:

Dateien die geprüft und korrigiert werden müssen:
- README.md
- docs/ (falls vorhanden)
- Kommentare im Code die eine konkrete Zahl nennen
- config/default.yaml (falls Kommentare mit Zahl vorhanden)

Korrekte Zahl: Die tatsächliche Anzahl implementierter Prüfpunkte
laut Pruefpunkte.md nach Aufgabe 1 — bitte selbst zählen und
dann konsequent überall dieselbe Zahl verwenden.

## Fortschritts-Tracking

~/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/doku_etc/review_fortschritt.md

Als neue Sektion "Runde 14" anhängen:
- [x] Aufgabe 1: Pruefpunkte.md um 1b/1c/12b ergänzt
- [x] Aufgabe 2: Terminologie vereinheitlicht — korrekte Zahl: XX

## Abschluss

Commit und Push mit Message:
"docs: add missing check entries 1b/1c/12b, unify check count terminology"
```
