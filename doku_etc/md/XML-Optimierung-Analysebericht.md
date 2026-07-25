# XML-Export-Optimierung — Analysebericht

*Reine Analyse, keine Code-Änderungen. Stand: Code-Repo `code/` nach Pull auf `099653b`.*

## Korrektur der Ausgangshypothese

Im gesamten Code gibt es **genau eine** Stelle, die `.Export()` aufruft:

```
src/tia_linter/checks/_tia_helpers.py:402
    block.Export(FileInfo(str(export_path)), ExportOptions.WithDefaults)
```

gekapselt in der Hilfsfunktion `export_block_xml(block)`. Es gibt **keine** Exporte von TagTable, DB oder HmiTagTable als XML — die in der Hypothese genannten Objekttypen werden im Code nicht so behandelt. TagTable/DB-Daten werden ausschließlich über direkte Openness-Objektzugriffe (`CrossReferenceService`, `.Interface.Members`) gelesen, nicht über XML-Export.

Zusätzlich gibt es einen **zweiten, unabhängigen Export-Typ**, der in der Hypothese nicht erwähnt war, aber dieselbe Kategorie von Problem hat:

```
src/tia_linter/project_texts.py:63
    project.ExportProjectTexts(FileInfo(str(export_path)), language, language)
```

— ein projektweiter Excel-Export aller Projekttexte (DB-Variablen-Kommentare), gekapselt in `ProjectTextComments.load(project)`.

## Schritt 1 — Bestandsaufnahme aller Exporte

### A) Block-XML-Export (`export_block_xml`)

| # | Datei:Zeile | Check-Klasse | Prüfpunkt | Objekt | Was wird gelesen |
|---|---|---|---|---|---|
| 1 | comments.py:450 | `FbMemberKommentarCheck` | 1c | jeder FB | Interface-Member-Namen (Input/Output/InOut/Static) |
| 2 | comments.py:573 | `NetzwerkBeschreibungCheck` | 3 | jeder Block (außer SCL/STL) | Netzwerk-Titel pro CompileUnit |
| 3 | structure.py:80 | `LeereNetzwerkeCheck` | 10 | jeder Block (außer SCL/STL) | Elementanzahl + Sprache pro CompileUnit |
| 4 | structure.py:282 | `UnbenutzteVariablenCheck` | 11a | jeder FB/FC/OB | Interface-Member-Pfade + lokale Zugriffspfade |
| 5 | structure.py:515 | `AwlCodeCheck` | 14 | jeder Block (außer SCL, STL-Skip separat) | Sprache pro CompileUnit *(Docstring: „dieselbe Abfrage wie PP15, hier wiederverwendet“)* |
| 6 | structure.py:552 | `GemischteSprachenCheck` | 15 | jeder Block (außer SCL/STL) | Sprache pro CompileUnit |
| 7 | structure.py:605 | `MaxNetzwerkElementeCheck` | 16 | jeder Block (außer STL) | Elementanzahl/SCL-Zeilenzahl pro CompileUnit |
| 8 | libraries.py:223 | `StaticZugriffExternCheck` | 25 | Owner-FB **jeder Instanz-DB** | Static-Interface-Member-Namen |
| 9 | libraries.py:302 | `OutputMehrfachBeschriebenCheck` | 26 | jeder FB/FC | Output/InOut-Member + Schreibzugriffszähler |
| 10 | libraries.py:376 | `Ob1KomplexitaetCheck` | 28 | nur OB1 | Elementanzahl pro CompileUnit |

Alle 10 Stellen sind in **default.yaml standardmäßig aktiviert**. Jede Stelle exportiert unabhängig — es gibt keinen gemeinsamen Cache, keine Memoization, kein `functools.lru_cache`.

### B) Projekttexte-Export (`ProjectTextComments.load`)

| # | Datei:Zeile | Check-Klasse | Prüfpunkt |
|---|---|---|---|
| 1 | comments.py:186 | `VariablenKommentarCheck` | 1a |
| 2 | comments.py:307 | `UdtKommentarCheck` | 1b |
| 3 | comments.py:443 | `FbMemberKommentarCheck` | 1c |

Alle drei Aufrufe liegen zusätzlich **innerhalb der `for plc_software in iter_plc_software(project)`-Schleife** und exportieren dabei stets die **komplette** Projekttexte-Tabelle (`project.ExportProjectTexts`, projektweit, nicht PLC-spezifisch) — bei mehreren PLC-Geräten im Projekt wird derselbe Export also zusätzlich pro PLC wiederholt.

## Schritt 2 — Duplikate

| Objekt-Typ | Export-Inhalt | Prüfpunkte, die es brauchen | Wie oft exportiert (pro Objekt, Default-Config) |
|---|---|---|---|
| FB (grafisch, kein SCL/STL) | Block-XML | 1c, 3, 10, 11a, 14, 15, 16, 26 | **8×**, zusätzlich **+1× pro Instanz-DB** über PP25 |
| FC (grafisch) | Block-XML | 3, 10, 11a, 14, 15, 16, 26 | **7×** |
| OB, nicht OB1 (grafisch) | Block-XML | 3, 10, 11a, 14, 15, 16 | **6×** |
| OB1 (grafisch) | Block-XML | 3, 10, 11a, 14, 15, 16, 28 | **7×** |
| FB/FC/OB (SCL) | Block-XML | 11a, 16, 26 (+1c falls FB) | 3–4× |
| Global-/Array-DB | — | keiner (über CrossReferenceService, nicht XML) | 0× |
| Instanz-DB | — | keiner direkt (nur Owner-FB via PP25) | 0× (aber löst je 1 Export des Owner-FB aus) |
| Projekttexte (Excel, projektweit) | Kommentar-Lookup-Tabelle | 1a, 1b, 1c | **3× pro PLC-Software-Instanz** |

Bemerkenswert: Der Docstring von `AwlCodeCheck` (Prüfpunkt 14) benennt die Duplikation zu Prüfpunkt 15 explizit selbst („dieselbe Abfrage wird hier wiederverwendet“) — dem Entwickler war das Muster bereits bewusst, ohne dass es zu einer gemeinsamen Datenquelle geführt hätte.

Zusätzliche, in der Hypothese nicht erwähnte Duplikationsquelle: `StaticZugriffExternCheck` (PP25) iteriert über **Instanz-DBs**, nicht über FBs, und exportiert dabei den zugehörigen Owner-FB pro Instanz-DB neu — hat ein FB mehrere Instanz-DBs, wird er innerhalb dieses einen Checks bereits mehrfach exportiert, unabhängig von den anderen 9 Stellen.

## Schritt 3 — Optimierungspotenzial

**Wichtiger Kontextfund (`runner.py`, `_release_dotnet_objects`):** Das Projekt hatte bereits einen echten Absturz gegen ein reales 288-Bausteine-Projekt — `EngineeringOutOfMemoryException: The maximum number (500000) of instances ... has been exceeded`, ausgelöst unter anderem durch offene .NET-Handles aus `CrossReferenceService`-Ergebnissen **und Baustein-Exports**. Die aktuelle Gegenmaßnahme ist ein erzwungener `GC.Collect()` nach jedem Check plus ein präventiver Session-Reconnect alle 10 Checks. Das bedeutet: **jeder unnötige Export ist nicht nur Zeit, sondern trägt aktiv zu genau dem Ressourcenlimit bei, das bereits einmal zum Absturz geführt hat.**

**Hochrechnung (Block-XML):**

Belegte Fakten aus den Doku-Kommentaren des Repos: Referenzprojekt „Salzmaschine" hat 288 Bausteine gesamt, davon 127 FBs. Die genaue FC/OB/DB-Aufteilung ist in den Docs nicht vermerkt; für die folgende Rechnung wird sie geschätzt (klar als Schätzung markiert) — restliche ~161 Bausteine geschätzt als ~100 FC, ~10 OB, ~51 Global-/Array-/Instanz-DBs (DBs tragen 0 zur Export-Zahl bei):

- 127 FB × 8 = 1.016
- 100 FC × 7 = 700
- 10 OB × 6 (+1 für OB1) = 61
- **Summe: ≈ 1.777 `Export()`-Aufrufe** für nur 237 tatsächlich exportierbare Bausteine

Nach Deduplizierung (ein Export pro Baustein pro Lauf, unabhängig von der Anzahl interessierter Prüfpunkte): **237 Exporte** — der theoretische Minimalwert.

**Ergebnis: ≈ 1.777 → 237, Faktor ≈ 7,5, d. h. rund 87 % weniger `Export()`-Aufrufe.** Selbst bei konservativeren Annahmen zur FC/OB-Aufteilung bleibt der Faktor im Bereich 6–8×, da er primär von der Anzahl der aktiven Checks pro Blocktyp abhängt (Code-Fakt), nicht von der genauen Blockzahl (Schätzung).

**Projekttexte-Export:** Reduktion von 3×N (N = Anzahl PLC-Software-Instanzen im Projekt) auf 1× pro Lauf — bei den meisten Projekten (1 PLC) von 3 auf 1, Faktor 3×. Kleiner absoluter Betrag, aber der Export ist projektweit (potenziell viele Zeilen Excel + `openpyxl`-Parsing) und daher pro Aufruf vergleichsweise teuer.

## Schritt 4 — Lösungsvorschlag

**Kritische Einschränkung geprüft:** Alle 10 Callsites sind unabhängige `BaseCheck.run(project)`-Aufrufe, die von `runner.py` sequenziell und nur für **aktivierte** Prüfpunkte ausgeführt werden (`enabled = [d for d in definitions if d.enabled]`). Kein Check verlässt sich auf einen Seiteneffekt eines anderen — jeder ruft `export_block_xml(block)` bei Bedarf selbst auf. Ein Cache darf diese Unabhängigkeit nicht brechen.

**Lese-Sicherheit geprüft:** Kein Check verändert Bausteine (`grep` über alle `checks/*.py` nach `.Compile(`/`SetAttribute(`/`.Delete(` etc. ergibt nur `metadata.py` → `compile_service.Compile()` für Prüfpunkt 21, was aber nur eine Neuübersetzung anstößt, nicht den Quellcode/die Netzwerke verändert). Block-XML-Inhalt ist über die gesamte Laufzeit eines Lint-Laufs stabil — Caching pro Lauf ist inhaltlich sicher.

**Reconnect-Falle geprüft:** `run_lint` disposed die komplette Openness-Session alle `reconnect_every_n_checks` (Standard 10) Checks und holt sich danach *neue* .NET-Objekte für Projekt/Blocks. Ein Cache, der auf Objekt-**Identität** (`id(block)` / das `block`-Objekt selbst als Dict-Key) basiert, würde nach jedem Reconnect ungültig — und schlimmer: alte, disposed .NET-Handles referenzieren. Der Cache-Key muss stattdessen ein **stabiler String** sein (z. B. `plc_software.Name + "/" + "/".join(group_path) + "/" + block.Name`, exakt die Bestandteile, die `format_path()` ohnehin schon für die Ergebnis-Pfade verwendet) — der geparste `ElementTree`-Inhalt selbst ist reines Python und bleibt über einen Reconnect hinweg gültig.

### Bewertung der drei Optionen

| Option | Einsparung | Risiko | Aufwand |
|---|---|---|---|
| **A — Zentraler Vorab-Export in `runner.py`** | Theoretisches Maximum, aber nur wenn vorab bekannt ist, welche Bausteine welcher Check braucht | **Hoch:** bündelt alle ~237 Exporte in einer kurzen Phase am Anfang, *bevor* der bestehende periodische GC/Reconnect-Mechanismus eingreifen kann — läuft dem Grund zuwider, warum dieser Mechanismus überhaupt existiert (siehe OOM-Absturz oben). Zusätzlich muss die Vorab-Liste bei jedem neuen Check, der künftig XML braucht, händisch synchron gehalten werden — sonst stiller Cache-Miss. | Hoch (Filterlogik pro Blocktyp muss zentral dupliziert werden) |
| **B — Lazy Cache (Export beim ersten Zugriff, danach aus Cache)** | Identisch zu A (jedes Objekt genau 1× exportiert), aber über den ganzen Lauf verteilt | **Niedrig:** Export-Zeitpunkte bleiben so verteilt wie bisher, der bestehende Reconnect-Mechanismus bleibt voll wirksam. Erfüllt die Prüfpunkt-Unabhängigkeit automatisch — welcher Check den Export zuerst braucht, ist beliebig, keiner muss vorher gelaufen sein. | Niedrig |
| **C — Cache-Verwaltung in `_tia_helpers.py`** | Kein eigener Einspareffekt — das ist die *Implementierungsstelle*, nicht die *Strategie* | Kein zusätzliches Risiko; im Gegenteil, hier existiert `export_block_xml` schon als einzige Export-Stelle | Sehr niedrig |

**Empfehlung: B, implementiert als C** — d. h. `export_block_xml(block)` selbst um einen lauf-gebundenen (nicht global persistenten) Cache erweitern, keine neue Vorab-Phase in `runner.py`. Die Signatur/Aufrufstellen in allen 10 Checks bleiben unverändert; nur `_tia_helpers.py` ändert sich. Konkret:

- Cache lebt als Instanzattribut/Closure, das pro `run_lint()`-Aufruf neu erzeugt wird (nicht als Modul-globale Variable — sonst „leakt" der Cache zwischen zwei unabhängigen Lint-Läufen, z. B. in der GUI bei zwei Klicks auf „Prüfung starten").
- Key: `(plc_software.Name, group_path-Tupel, block.Name)`, nicht das `block`-Objekt selbst (Reconnect-Sicherheit, siehe oben).
- Gleiches Muster für `ProjectTextComments.load()` — dort sogar einfacher, da der Cache-Key konstant ist (projektweit, nicht pro Block): ein einziges `_cache: ProjectTextComments | None`-Attribut reicht, das beim ersten `.load()`-Aufruf pro Lauf gefüllt wird.
- Fehlerfall unverändert beibehalten: schlägt ein einzelner Export fehl (aktuell: `return None` + `logger.warning`), darf das **nicht** dauerhaft gecacht werden als „dieser Block kann nie exportiert werden" — sinnvoll wäre, `None`-Ergebnisse *nicht* zu cachen, sondern bei jedem erneuten Zugriff erneut zu versuchen (kostet im Fehlerfall etwas Redundanz, ist aber sicherer als einen temporären Fehler dauerhaft einzufrieren).

### Verbleibende Risiken

1. **Speicherverbrauch:** 237 geparste `ElementTree`-Bäume gleichzeitig im Speicher statt einer nach dem anderen. Bei sehr großen Bausteinen (z. B. das erwähnte 256-Zeilen-SCL-Netzwerk) ist das pro Baum klein; in Summe über ein 288-Bausteine-Projekt voraussichtlich unkritisch, aber nicht verifiziert — sollte im Rahmen der Implementierung kurz beobachtet werden (RAM vor/nach).
2. **PP25-Sonderfall:** Instanz-DBs mit mehreren Instanzen desselben FB profitieren zusätzlich, weil der Owner-FB-Export jetzt auch *innerhalb* von `StaticZugriffExternCheck` selbst gecacht wird — sollte beim Testen explizit mitverifiziert werden (z. B. an einem FB mit ≥2 Instanz-DBs).
3. **Testabdeckung:** `tests/test_tia_helpers.py` müsste um einen Test ergänzt werden, der belegt, dass zwei Aufrufe von `export_block_xml()` mit demselben Baustein nur einen `block.Export()`-Aufruf auslösen (Mock-Zählung) — aktuell nicht vorhanden.

---

**Nächster Schritt liegt bei dir:** Freigabe zur Implementierung von Option B/C (Lazy Cache in `_tia_helpers.py` + `project_texts.py`), oder Rückfragen zu den obigen Schätzungen/Annahmen.
