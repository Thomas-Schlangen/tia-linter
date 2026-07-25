# TIA Projekt Linter — Prüfpunkte

*Erarbeitet Juli 2026 — Kombination aus eigenen Ideen + Forum-Recherche + Best-Practice-Quellen*

Alle Prüfpunkte sollen konfigurierbar sein (YAML-Konfigurationsdatei). Jeder Punkt liefert einen von drei Status:
- ✅ OK
- ⚠️ Warnung (im Report dokumentiert, kein Abbruch)
- ❌ Fehler (im Report als Problem markiert)

**Implementierungsstatus:** `- [ ] Stub` → `- [x] Implementiert`

---

## Kategorie: Kommentare & Beschreibungen

### 1a. Variablen ohne Kommentar
**Was:** Prüfen ob alle PLC-Tag-Variablen einen Kommentar haben.
**Auch:** DB-Variablen (Interface.Members) prüfen — Kommentar kommt aus Projekttexten (bekannt aus Tag Exporter).
**Konfigurierbar:** Ausnahmen per Namenspattern (z.B. interne Hilfsvariablen mit Prefix `_`)
**Status bei Verstoß:** ⚠️ Warnung oder ❌ Fehler (konfigurierbar)
**Implementiert:** - [x]

### 1b. UDT ohne Kommentar
**Was:** Prüfen ob PLC-Datentypen (UDTs) einen Kommentar haben — sowohl der UDT selbst als auch seine einzelnen Items (Interface-Member).
**Hintergrund:** War in der ursprünglichen Liste der 33 Prüfpunkte kein eigener Punkt — ergänzt Prüfpunkt 1a um eine Lücke, die durch dessen eigene UDT-Sonderbehandlung entstanden ist: Prüfpunkt 1a prüft Items *innerhalb* eines UDT-typisierten DB-Members bewusst nicht mehr einzeln (ein Kommentar auf dem UDT-Member selbst genügt dort), dieser Prüfpunkt schließt die Lücke, indem er sowohl den Kommentar des UDT selbst als auch die Kommentare aller seiner Items direkt an der UDT-Definition prüft.
**Konfigurierbar:** Ausnahmen per Namenspattern (Standard-Präfix `__`).
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 1c. FB-Interface-Member ohne Kommentar
**Was:** Prüfen ob die Interface-Member (Input/Output/InOut/Static) eines Funktionsbausteins (FB) einen Kommentar haben.
**Hintergrund:** War in der ursprünglichen Liste der 33 Prüfpunkte kein eigener Punkt — analog zu Prüfpunkt 1b, aber für Funktionsbausteine statt UDTs: Prüfpunkt 1a prüft Instanz-DB-Member bewusst nicht mehr einzeln, dieser Prüfpunkt ist die alleinige Quelle für Kommentar-Befunde zu FB-Interface-Membern, geprüft einmalig an der FB-Definition (nicht pro Instanz). Der Kopfkommentar des FB als Ganzes ist Sache von Prüfpunkt 2 und wird hier nicht erneut geprüft.
**Konfigurierbar:** Ausnahmen per Namenspattern (Standard-Präfix `__`).
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 2. Bausteine ohne Kopfbeschreibung
**Was:** Prüfen ob alle FBs, FCs, DBs im Baustein-Kopf eine Beschreibung haben.
**Inhalt prüfen:** Nicht nur ob vorhanden, sondern ob Mindestlänge (z.B. > 20 Zeichen) — leere oder nichtssagende Texte wie "." oder "FB" zählen nicht.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 3. Netzwerk ohne Beschreibung
**Was:** Prüfen ob jedes Netzwerk einen Titel / Kurzbeschreibung hat.
**Zusatzcheck:** Beschreibung zu lang → als Warnung (max. Zeichenanzahl konfigurierbar, z.B. 80 Zeichen).
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 4. Bausteinköpfe ohne Änderungshistorie
**Was:** Prüfen ob der Baustein-Kopf eine Versionsinfo oder Änderungshistorie enthält.
**Hintergrund:** Best Practice laut Siemens Standardisierungsleitfaden — Bausteinköpfe sollen Autor, Version, Datum und Änderungshistorie enthalten.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

---

## Kategorie: Namenskonventionen

### 5. DB-Namensformat (dynamische Formatvorgabe)
**Was:** Prüfen ob alle DBs einer definierten Namenskonvention entsprechen.
**Konfigurierbar:** Format per Regex oder Muster, z.B. muss mit `DB_` beginnen, darf nicht mit Zahl beginnen.
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 6. PLC-Tag Namenskonvention (dynamische Formatvorgabe)
**Was:** Prüfen ob alle PLC-Tags einem definierten Muster entsprechen.
**Konfigurierbar:** Regex-Muster oder Präfix-Liste (z.B. Eingänge `I_`, Ausgänge `Q_`, Merker `M_`)
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 7. Bausteinname Konvention
**Was:** Prüfen ob FBs, FCs, OBs einem Namensschema entsprechen (FB_, FC_, keine Leerzeichen).
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 8. Konstanten in GROSSBUCHSTABEN
**Was:** Prüfen ob Konstanten in UPPERCASE_WITH_UNDERSCORES geschrieben sind.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 9. Testvariablen prüfen
**Was:** Variablen mit bestimmten Namen (z.B. `TEST_`, `DEBUG_`, `TEMP_`) dürfen vorhanden sein, aber nicht mehr im Programm verwendet werden.
**Konfigurierbar:** Liste der zu prüfenden Präfixe.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

---

## Kategorie: Programmstruktur

### 10. Leere Netzwerke
**Was:** Netzwerke ohne Inhalt (keine Kontakte, keine Bausteinaufrufe) finden.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 11a. Unbenutzte Variablen (Dead Code)
**Was:** PLC-Tags und DB-Variablen finden die im gesamten Programm nie verwendet werden.
**Technisch komplex:** Erfordert Kreuzreferenz-Analyse über alle Bausteine.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 11b. Unbenutzte Bausteine (FB, FC, DB)
**Was:** Prüfen ob alle im Projekt vorhandenen FBs, FCs und DBs auch mindestens einmal aufgerufen bzw. verwendet werden.
**Technisch komplex:** Erfordert Kreuzreferenz-Analyse über alle Aufrufhierarchien.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 12a. Eingänge min. 1x gelesen
**Was:** Prüfen ob jeder Eingangs-PLC-Tag mindestens einmal im Programm gelesen wird.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 12b. Eingänge dürfen nicht beschrieben werden
**Was:** Prüfen ob ein Eingangs-PLC-Tag irgendwo im Programm beschrieben (geschrieben) statt nur gelesen wird.
**Hintergrund:** War in der ursprünglichen Liste der 33 Prüfpunkte kein eigener Punkt — eine der grundlegendsten SPS-Programmierregeln: Eingänge werden jeden Zyklus vom Prozessabbild aus der Hardware überschrieben, ein Schreibzugriff aus dem Anwenderprogramm wird beim nächsten Zyklus also ohnehin wieder verworfen und deutet meist auf eine Verwechslung mit einem Merker hin.
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 13. Ausgänge max. 1x geschrieben
**Was:** Prüfen ob Ausgangs-PLC-Tags nicht von mehreren Stellen im Programm beschrieben werden.
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 14. AWL-Code vorhanden
**Was:** Prüfen ob noch Netzwerke in AWL (Statement List / STL) programmiert sind.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 15. Gemischte Programmiersprachen im selben Baustein
**Was:** Prüfen ob innerhalb eines Bausteins mehrere Sprachen gemischt werden (z.B. KOP und SCL).
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 16. Zu komplexe Netzwerke
**Was:** Netzwerke mit mehr als X Elementen (konfigurierbar) als Warnung markieren.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

---

## Kategorie: Hardware & Konfiguration

### 17. Hardware vorhanden und aktiviert für jeden I/O-Tag
**Was:** Prüfen ob für jeden PLC-Eingangs- und Ausgangs-Tag auch ein entsprechendes Hardware-Modul vorhanden und aktiv ist.
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 17b. Hardware-Typ passt zum Tag-Datentyp (spätere Version)
**Was:** Prüfen ob der Datentyp des Tags zum Typ des Hardware-Moduls passt (z.B. Analog ↔ Digital).
**Aufwand:** Sehr Hoch
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [ ] *(spätere Version)*

### 18a. CPU-Typ und Firmware-Version dokumentiert
**Was:** Prüfen ob in den Projekteigenschaften CPU-Typ und Firmware-Version vermerkt sind.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 18b. Passwortschutz bei Sicherheits-SPS
**Was:** Prüfen ob für eine Safety-CPU (z.B. S7-1500F) ein F-Passwort vergeben wurde.
**Technisch:** `SafetyAdministration.IsSafetyOfflineProgramPasswordSet`
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 18c. Kommunikationszertifikat prüfen
**Was:** Prüfen ob ein Kommunikationszertifikat vorhanden ist und bis wann es gültig ist.
**Details:** Gültigkeitsdatum immer im Report — Warnung wenn Restlaufzeit < Schwellenwert aus Config.
**Technisch:** `LocalCertificateManager` + `ValidUntil`
**Status bei Verstoß:** ❌ Fehler (kein Zertifikat) / ⚠️ Warnung (läuft bald ab)
**Implementiert:** - [x]

---

## Kategorie: Projektmetadaten

### 19. Kundeninformation in Top-Level-Eigenschaften
**Was:** Prüfen ob Pflichtfelder (Kundenname, Projektnummer etc.) in den Projekteigenschaften ausgefüllt sind.
**Konfigurierbar:** Liste der Pflichtfelder.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 20. Anzahl Sprachen prüfen
**Was:** Mehr als 2 Sprachen → Warnung (oft vergessene Testsprachen).
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 21. Kompilierfehler und Warnungen
**Was:** Alle Kompilierfehler und Compiler-Warnungen in den Report aufnehmen.
**Technisch:** Über Openness API nach Übersetzung abrufbar.
**Status bei Verstoß:** ❌ Fehler / ⚠️ Warnung
**Implementiert:** - [x]

---

## Kategorie: Bibliotheken & Typen

### 22. Bibliotheksbausteine auf aktuellem Stand
**Was:** Prüfen ob verwendete Bibliothekstypen mit der aktuellen Version übereinstimmen.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 23. Instanz-DBs ohne zugehörigen FB
**Was:** Prüfen ob Instanz-DBs vorhanden sind, deren Quell-FB nicht mehr im Projekt existiert.
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

---

## Kategorie: Siemens Styleguide & Best Practices

*Basierend auf Siemens Programming Styleguide (Pub. ID: 81318674) und weiteren Quellen*

### 24. Sprachen konsistent — keine Mischung
**Was:** Prüfen ob Kommentare und Netzwerktitel konsequent in einer Sprache geschrieben sind.
**Konfigurierbar:** Erwartete Sprache (`de` oder `en`) in Config.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 25. Direkter Zugriff auf Static-Tags von außen
**Was:** Prüfen ob Static-Tags eines FB von außen direkt gelesen oder beschrieben werden.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 26. Output-Tag pro Zyklus nur einmal beschrieben
**Was:** Prüfen ob ein Output-Tag an mehreren Stellen beschrieben wird.
**Status bei Verstoß:** ❌ Fehler
**Implementiert:** - [x]

### 27. UDT für wiederkehrende Strukturen
**Was:** Prüfen ob identische STRUCT-Definitionen in mehreren DBs auftauchen statt als UDT.
**Aufwand:** Hoch
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 28. OB1 (Main) Komplexität
**Was:** Prüfen ob OB1 direkt Logik enthält statt nur Bausteinaufrufe.
**Konfigurierbar:** Max. Netzwerke mit Logik (z.B. > 5 = Warnung)
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 29. Know-How-Schutz dokumentiert
**Was:** Prüfen ob know-how-geschützte Bausteine dokumentiert sind.
**Technisch:** `GetAttribute("IsKnowHowProtected")`
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 30. Tag-Tabellen nur I/O-Tags
**Was:** Prüfen ob Tag-Tabellen ausschließlich I/O-Tags (I- und Q-Bereich) enthalten.
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 31. Nicht-optimierte Bausteine
**Was:** Prüfen ob Bausteine als "nicht optimiert" projektiert sind.
**Technisch:** `GetAttribute("IsOptimizedBlockAccess")`
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 32. Bausteine im Root ohne Ordnerstruktur
**Was:** Prüfen ob alle Bausteine ungeordnet im Root liegen.
**Konfigurierbar:** Schwellenwert (z.B. > 20 Blöcke im Root = Warnung)
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

### 33. Schreibschutz von Bausteinen (neu in V21)
**Was:** Prüfen ob Bausteine einen Schreibschutz haben und ob dieser dokumentiert ist.
**Technisch:** V21 Bausteinattribut — siehe Openness-API-V21-Aenderungen.md
**Status bei Verstoß:** ⚠️ Warnung
**Implementiert:** - [x]

---

## Übersicht Implementierungsstatus

| Nr | Prüfpunkt | Via Openness | Schwierigkeit | Implementiert |
|---|---|---|---|---|
| 1a | Kommentare Variablen | ✅ Ja | Gering | - [x] |
| 1b | UDT ohne Kommentar | ✅ Ja | Gering | - [x] |
| 1c | FB-Interface-Member ohne Kommentar | ✅ Ja | Gering | - [x] |
| 2 | Kommentare Bausteine | ✅ Ja | Gering | - [x] |
| 3 | Netzwerkbeschreibungen | ✅ Ja | Gering | - [x] |
| 4 | Änderungshistorie | ✅ Ja | Gering | - [x] |
| 5 | DB-Namensformat | ✅ Ja | Gering | - [x] |
| 6 | PLC-Tag Konvention | ✅ Ja | Gering | - [x] |
| 7 | Bausteinname Konvention | ✅ Ja | Gering | - [x] |
| 8 | Konstanten UPPERCASE | ✅ Ja | Gering | - [x] |
| 9 | Testvariablen | ✅ Ja | Gering | - [x] |
| 10 | Leere Netzwerke | ✅ Ja | Gering | - [x] |
| 11a | Unbenutzte Variablen | ⚠️ Kreuzreferenz | Hoch | - [x] |
| 11b | Unbenutzte Bausteine | ⚠️ Kreuzreferenz | Hoch | - [x] |
| 12a | Eingänge min. 1x gelesen | ⚠️ Kreuzreferenz | Hoch | - [x] |
| 12b | Eingänge dürfen nicht beschrieben werden | ⚠️ Kreuzreferenz | Hoch | - [x] |
| 13 | Ausgänge max. 1x geschrieben | ⚠️ Kreuzreferenz | Hoch | - [x] |
| 14 | AWL-Code | ✅ Ja | Mittel | - [x] |
| 15 | Gemischte Sprachen | ✅ Ja | Mittel | - [x] |
| 16 | Zu komplexe Netzwerke | ✅ Ja | Mittel | - [x] |
| 17 | Hardware vorhanden | ✅ Ja | Mittel | - [x] |
| 17b | Hardware-Typ passt | ⚠️ Komplex | Sehr Hoch | - [ ] |
| 18a | CPU/Firmware dokumentiert | ✅ Ja | Gering | - [x] |
| 18b | Safety-Passwort | ✅ Ja | Gering | - [x] |
| 18c | Zertifikat | ✅ Ja | Mittel | - [x] |
| 19 | Kundeninformation | ✅ Ja | Gering | - [x] |
| 20 | Anzahl Sprachen | ✅ Ja | Gering | - [x] |
| 21 | Kompilierfehler | ✅ Ja | Mittel | - [x] |
| 22 | Bibliotheken aktuell | ✅ Ja | Mittel | - [x] |
| 23 | Verwaiste Instanz-DBs | ✅ Ja | Mittel | - [x] |
| 24 | Sprachen konsistent | ✅ Ja | Mittel | - [x] |
| 25 | Static-Tag Zugriff | ✅ Ja | Hoch | - [x] |
| 26 | Output-Tag 1x beschrieben | ✅ Ja | Hoch | - [x] |
| 27 | UDT für Strukturen | ⚠️ Komplex | Hoch | - [x] |
| 28 | OB1 Komplexität | ✅ Ja | Mittel | - [x] |
| 29 | Know-How-Schutz | ✅ Ja | Gering | - [x] |
| 30 | Tag-Tabellen I/O | ✅ Ja | Gering | - [x] |
| 31 | Nicht-optimierte Blöcke | ✅ Ja | Gering | - [x] |
| 32 | Bausteine im Root | ✅ Ja | Gering | - [x] |
| 33 | Schreibschutz (V21) | ✅ Ja | Gering | - [x] |

---

*Verknüpft mit: [[Ideen-und-Nischen]] → TIA Projekt Linter / Qualitätsprüfer*
