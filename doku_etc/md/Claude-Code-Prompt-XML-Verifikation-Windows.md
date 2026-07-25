# Claude Code Prompt — XML Cache Verifikation (Windows / TIA)

*Erstellt Juli 2026 — Verifikation des Lazy Cache gegen echtes TIA-Projekt*

---

## Prompt

```
Lies zuerst:
D:\Daten\Projekte\OpennessDev\tia-linter\doku_etc\XML-Optimierung-Fortschritt.md
D:\Daten\Projekte\OpennessDev\tia-linter\doku_etc\XML-Optimierung-Analysebericht.md

Der Lazy Cache für XML-Exporte wurde auf Linux implementiert und committed.
Jetzt echter Verifikationstest gegen das Salzmaschine-Projekt.

## Vorbereitung

1. git pull — neuesten Stand holen
2. venv aktivieren: .venv\Scripts\Activate.ps1
3. pip install -e . falls nötig

## Aufgabe 1 — Debug-Logging einbauen

In _tia_helpers.py temporäres Debug-Logging einbauen das Cache-Hits
und Cache-Misses sichtbar macht:
- Cache-Miss (echter Export): logger.debug("EXPORT: %s", cache_key)
- Cache-Hit (aus Cache): logger.debug("CACHE-HIT: %s", cache_key)

Gleiches für project_texts.py:
- Cache-Miss: logger.debug("EXPORT: ProjectTexts")
- Cache-Hit: logger.debug("CACHE-HIT: ProjectTexts")

Log-Level auf DEBUG stellen damit diese Zeilen sichtbar sind.

## Aufgabe 2 — Lauf gegen Salzmaschine

Kompletten Lint-Lauf gegen das Salzmaschine-Projekt starten:
D:\Daten\Projekte\OpennessDev\tia-linter\Salzmaschine\[Projektdatei]

Alle Prüfpunkte aktiviert (default.yaml).

## Aufgabe 3 — Auswertung

Aus dem Log auswerten:
- Wie viele EXPORT-Einträge (Cache-Misses)?
- Wie viele CACHE-HIT-Einträge?
- Stimmt die Anzahl der Exporte mit der Anzahl der Bausteine überein?
- Gibt es unerwartete mehrfache Exporte desselben Bausteins?
- Wird der Cache nach dem Reconnect korrekt geleert?
  (Im Log sichtbar: Reconnect-Meldung gefolgt von erneuten EXPORT-Einträgen
  für Bausteine die vorher schon gecacht waren)

RAM-Verbrauch beobachten:
- RAM vor dem Lauf (Task-Manager oder psutil)
- RAM nach dem Lauf
- Kurz kommentieren ob der Cache den Speicher nennenswert erhöht

Laufzeit messen und mit dem letzten bekannten Wert vergleichen
(aus review_fortschritt.md falls vorhanden).

## Aufgabe 4 — Aufräumen und Abschluss

1. Debug-Logging wieder entfernen (Log-Level zurück auf INFO)
2. XML-Optimierung-Fortschritt.md aktualisieren mit:
   - Anzahl Exporte vor/nach Optimierung
   - Gemessene Laufzeit
   - RAM-Beobachtung
   - Ob Cache-Reset nach Reconnect korrekt funktioniert
3. Commit und Push
   Commit-Message: "perf: XML export cache verified against real TIA project"

## Fortschritts-Tracking

Nach jedem Schritt in XML-Optimierung-Fortschritt.md aktualisieren:
- [x] Schritt 1: Debug-Logging eingebaut
- [x] Schritt 2: Lauf gegen Salzmaschine abgeschlossen
- [x] Schritt 3: Auswertung dokumentiert
- [x] Schritt 4: Aufgeräumt und committed

Warte nach Aufgabe 2 auf meine Bestätigung bevor du aufräumst —
ich möchte die Zahlen zuerst sehen.
```
