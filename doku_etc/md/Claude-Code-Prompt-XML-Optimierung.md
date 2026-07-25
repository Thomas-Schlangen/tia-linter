# Claude Code Prompt — XML Export Optimierung

*Erstellt Juli 2026 — Gezielter Performance-Review: XML-Export-Deduplizierung*

---

## Prompt

```
Wir optimieren den TIA Linter für maximale Performance beim XML-Export.

## Kontext

Das Projekt liegt unter:
- Code: GitHub repo tia-linter (clonen falls nicht lokal vorhanden)
- Referenz V21 API: ~/Dokumente/ObsidianVault/Projekte/TiaOpenness/TIAPortalOpenness_Referenz_V21_de.pdf
- API-Notizen: ~/Dokumente/ObsidianVault/Projekte/TiaOpenness/Openness-API-Referenz-fuer-Linter.md

## Hypothese

In TIA Portal Openness ist Export() (XML-Export von Bausteinen, Tag-Tabellen,
DBs etc.) eine teure Operation — sie schreibt temporäre XML-Dateien auf die
Festplatte und liest sie wieder ein. Die Vermutung: verschiedene Prüfpunkte
in checks/*.py rufen Export() auf denselben Objekten mehrfach auf, obwohl
ein einziger Export für mehrere Prüfpunkte ausreichen würde.

## Aufgabe — Analyse zuerst, KEINE Änderungen

### Schritt 1 — Bestandsaufnahme aller XML-Exporte

Durchsuche den gesamten Code unter src/tia_linter/checks/ nach allen
Stellen wo Export() aufgerufen wird oder XML-Daten aus TIA gelesen werden.

Erstelle eine vollständige Liste:
- Welche Datei / Funktion / Prüfpunkt ruft Export() auf?
- Auf welchem Objekt wird exportiert? (Block, TagTable, DB, HmiTagTable etc.)
- Was wird aus dem XML gelesen? (Kommentare, Netzwerktitel, Member-Namen etc.)
- Wie oft wird dasselbe Objekt exportiert (über alle Prüfpunkte zusammen)?

### Schritt 2 — Duplikate identifizieren

Erstelle eine Tabelle:

| Objekt-Typ | Export-Inhalt | Prüfpunkte die es brauchen | Aktuell wie oft exportiert |
|---|---|---|---|
| Block (FB/FC) | XML komplett | 3, 4, 10, 14, 15, 16, 25 | X mal |
| TagTable | XML komplett | 1, 6, 9, 12, 13 | X mal |
| ... | ... | ... | ... |

### Schritt 3 — Optimierungspotenzial bewerten

Berechne wie viele Export()-Aufrufe eingespart werden könnten wenn
gemeinsam genutzte XML-Daten gecacht werden.

### Schritt 4 — Lösungsvorschlag

Entwirf ein Caching-Konzept das folgende Punkte berücksichtigt:

**Kritische Einschränkung — Prüfpunkt-Abhängigkeit:**
Wenn Prüfpunkt A deaktiviert ist, darf Prüfpunkt B sich NICHT auf
einen XML-Export verlassen der nur durch Prüfpunkt A gemacht worden
wäre. Das Caching muss unabhängig von der Prüfpunkt-Auswahl funktionieren.

**Mögliche Lösungsansätze:**
- Option A: Zentraler XML-Cache in runner.py — alle benötigten Exporte
  werden zu Beginn der Prüfung einmalig gemacht, unabhängig davon
  welche Prüfpunkte aktiv sind
- Option B: Lazy Cache — Export wird beim ersten Zugriff gemacht
  und dann gecacht, jeder weitere Zugriff liest aus dem Cache
- Option C: Deduplizierung in _tia_helpers.py — gemeinsame Hilfsfunktionen
  die den Cache verwalten

Bewerte jeden Ansatz nach:
- Einsparung (wie viele Exporte weniger?)
- Risiko (könnte etwas kaputtgehen?)
- Implementierungsaufwand

## Fortschritts-Tracking

Schreibe deinen Fortschritt nach jedem Schritt in:
~/Dokumente/ObsidianVault/Projekte/TIA-Linter/XML-Optimierung-Fortschritt.md

Format:
- [x] Schritt 1: Bestandsaufnahme abgeschlossen
- [x] Schritt 2: Duplikate identifiziert
- [ ] Schritt 3: Potenzial bewertet — IN ARBEIT
- [ ] Schritt 4: Lösungsvorschlag erstellt

## Ausgabe

Erstelle einen vollständigen Analysebericht BEVOR du irgendetwas änderst.
Warte auf meine Freigabe bevor du mit der Implementierung beginnst.

Der Bericht soll enthalten:
- Vollständige Export-Bestandsaufnahme
- Duplikate-Tabelle
- Konkrete Einsparungsschätzung (z.B. "von 47 auf 12 Exporte reduzierbar")
- Empfohlener Lösungsansatz mit Begründung
- Risiken und wie man sie mitigiert
```
