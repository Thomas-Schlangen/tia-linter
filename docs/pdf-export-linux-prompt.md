# Prompt für Claude Code (Linux) — Handbuch.pdf exakt wie unter Windows erzeugen

Diesen Block 1:1 in Claude Code auf dem Linux-Rechner einfügen (im Repo-Root von tia-linter/code):

---

Erzeuge `docs/Handbuch.pdf` aus `docs/Handbuch.md` exakt nach folgendem Verfahren, das unter Windows bereits erfolgreich 92 saubere Seiten ergeben hat (Pandoc + headless Chromium-Browser, NICHT die VS-Code-"Markdown PDF"-Erweiterung aus Anhang B, NICHT Pandocs LaTeX-Standardpfad, da dieser die Seitenumbruch-Marker ignoriert):

**Wichtig, immer zu beachten:** Das PDF wird grundsätzlich OHNE Anhang C ("Änderungshistorie dieses Handbuchs") erzeugt — dieser Abschnitt ist nur für die Entwicklung gedacht, nicht für die ausgelieferte Anleitung. Siehe Schritt 3.

1. Prüfe zuerst, was verfügbar ist: `pandoc --version` sowie eines von `google-chrome --version` / `google-chrome-stable --version` / `chromium --version` / `chromium-browser --version`. Melde kurz, was gefunden wurde, bevor du weitermachst.

   Bekannte Stolperfalle vom Linux-Testlauf (2026-08-13): `google-chrome`/`google-chrome-stable` sind auf diesem Rechner nicht installiert, dafür `chromium` (als Snap-Paket). Die Mount-Namespace-Warnungen (`update.go: cannot change mount namespace...`), die der Snap-Wrapper bei jedem Aufruf auf stderr ausgibt, sind harmlos und können ignoriert werden.

2. Lege exakt diese CSS-Datei als `docs/print.css` an (unverändert vom Windows-Lauf übernehmen; einzige potenzielle Anpassung: `Calibri`/`Segoe UI` sind auf Linux i. d. R. nicht installiert — falls verfügbar, `Carlito` voranstellen, das ist Calibri-metrikkompatibel; sonst Fallback auf `Arial`/`sans-serif` wie unten belassen, das reicht auch):

```css
@page {
  size: A4;
  margin: 20mm 18mm;
}

body {
  font-family: "Calibri", "Segoe UI", Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.45;
  color: #1a1a1a;
  max-width: 100%;
}

h1 { font-size: 22pt; margin-top: 0; }
h2 { font-size: 16pt; border-bottom: 2px solid #23578a; padding-bottom: 4px; margin-top: 28px; }
h3 { font-size: 13pt; color: #23578a; margin-top: 22px; }
h4 { font-size: 12pt; color: #23578a; margin-top: 18px; }

a { color: #23578a; text-decoration: none; }

code, pre {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 9.5pt;
  background: #f2f4f7;
  border-radius: 4px;
}
pre {
  padding: 8px 12px;
  overflow-x: auto;
  border: 1px solid #dfe3e8;
}
code { padding: 1px 4px; }
pre code { padding: 0; background: none; border: none; }

table {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
  font-size: 10pt;
}
th, td {
  border: 1px solid #c7ccd1;
  padding: 5px 8px;
  text-align: left;
  vertical-align: top;
}
th { background: #eaf0f6; }

blockquote {
  border-left: 4px solid #23578a;
  margin: 10px 0;
  padding: 4px 14px;
  background: #f6f8fa;
  color: #333;
}

img {
  max-width: 100%;
  display: block;
  margin: 12px auto;
  border: 1px solid #d7dce1;
}

hr { border: none; border-top: 1px solid #c7ccd1; margin: 20px 0; }

ul, ol { padding-left: 22px; }
```

3. Entferne zuerst Anhang C aus einer temporären Kopie des Markdowns — das PDF wird IMMER ohne diesen Abschnitt erzeugt, unabhängig vom aktuellen Bearbeitungsstand. Anhang C ist der letzte Abschnitt der Datei; ermittle die Grenze dynamisch (Zeilennummern verschieben sich mit jedem neuen Changelog-Eintrag), statt sie hart zu kodieren:

```bash
ANHANG_C_LINE=$(grep -n '^## Anhang C:' docs/Handbuch.md | head -1 | cut -d: -f1)
DIV_LINE=$(head -n $((ANHANG_C_LINE-1)) docs/Handbuch.md \
  | grep -n '<div style="page-break-after: always;"></div>' | tail -1 | cut -d: -f1)
head -n $((DIV_LINE-1)) docs/Handbuch.md > docs/_handbuch_ohne_anhang_c.md
```

   (Schneidet auch den Seitenumbruch-Marker unmittelbar vor Anhang C mit ab, sonst bliebe am Ende eine unnötige leere Seite.)

4. Wandle das (bereinigte) Markdown in ein eigenständiges HTML mit eingebetteten Bildern um (Bilder liegen in `docs/images/`, im Markdown relativ dazu referenziert):

```bash
pandoc docs/_handbuch_ohne_anhang_c.md -f markdown -t html5 --standalone \
  --resource-path=docs \
  --embed-resources --css docs/print.css \
  -o docs/_handbuch_tmp.html
```

   `--embed-resources` erfordert ein neueres Pandoc (>=3.0); falls die Version älter ist, stattdessen `--self-contained` verwenden (macht dasselbe).

   Bekannte Stolperfalle vom Linux-Testlauf (2026-08-13): Ohne `--resource-path=docs` sucht Pandoc die Bilder relativ zum aktuellen Arbeitsverzeichnis (`code/`), nicht relativ zur Markdown-Datei (`code/docs/`) — die Bilder werden dann NICHT gefunden (stille `[WARNING] Could not fetch resource images/...`-Meldungen, HTML bleibt ohne Bilder, aber ohne Fehlerabbruch). Unbedingt die Warnungen der Pandoc-Ausgabe kontrollieren.

   Zweite Stolperfalle: Die HTML-Zwischendatei absichtlich NICHT nach `/tmp` schreiben (siehe Schritt 5).

5. Erzeuge das PDF per headless Chromium/Chrome aus dem HTML (wichtig: Chromium-Engine, nicht Pandocs LaTeX, da nur sie die Marker `<div style="page-break-after: always;">` vor jeder Kapitelüberschrift korrekt respektiert):

```bash
chromium --headless=new --disable-gpu \
  --print-to-pdf=docs/Handbuch.pdf \
  --no-pdf-header-footer --no-margins \
  file:///home/thomasa/Dokumente/ObsidianVault/Projekte/TIA-Linter/code/docs/_handbuch_tmp.html
```

   (`google-chrome` bzw. `chromium-browser` statt `chromium`, je nachdem was in Schritt 1 gefunden wurde.)

   Bekannte Stolperfalle vom Windows-Lauf: `--print-to-pdf-no-header` (aus älterer Chromium-Doku) unterdrückt Header/Footer NICHT zuverlässig unter `--headless=new` — es muss `--no-pdf-header-footer` sein.

   Bekannte Stolperfalle vom Linux-Testlauf (2026-08-13): Wenn Chromium als Snap-Paket installiert ist (Snap-Confinement), kann es nicht auf `/tmp` zugreifen — die HTML-Zwischendatei per `file://`-URL aus `/tmp` liefert dann eine leere, 1-seitige PDF (kein Fehler, nur eine leere Seite in Letter-Format statt A4!). Deshalb die HTML-Zwischendatei in Schritt 4 bewusst ins Projekt-/Home-Verzeichnis schreiben, nicht nach `/tmp`. Falls `google-chrome`/`chromium-browser` (kein Snap) verwendet wird, tritt das Problem vermutlich nicht auf und `/tmp` funktioniert.

6. Verifiziere das Ergebnis: PDF sollte ca. 70+ Seiten haben (ohne Anhang C — mit Anhang C wären es die vollen 90+ Seiten wie beim ursprünglichen Windows-Lauf mit 92 Seiten), keine Browser-Header/Footer (Datum, URL, Seitenzahl am Rand), A4-Seitenformat, alle 22 Bilder aus `docs/images/` eingebettet sichtbar (`pdfimages -list docs/Handbuch.pdf` bzw. `pdfinfo docs/Handbuch.pdf`), und jedes Kapitel beginnt auf einer neuen Seite (Seitenumbruch-Marker wirken). Bei Abweichungen: Pandoc-/Chrome-Version prüfen und ggf. Flags anpassen, nicht einfach den LaTeX-Pfad nehmen.

7. Räume die temporären Dateien auf: `rm -f docs/_handbuch_ohne_anhang_c.md docs/_handbuch_tmp.html`. Nur `docs/Handbuch.pdf` ist das gewünschte Ergebnis und soll im Repo verbleiben.

---

Kontext (nicht Teil des Prompts, nur zur Info): Diese Anleitung entspricht 1:1 dem Verfahren, das gestern (2026-08-12) unter Windows mit `msedge.exe` funktioniert hat — nur der Browser-Binary-Name und die Font-Fallbacks sind Linux-spezifisch angepasst.

Update (2026-08-13): Erfolgreich unter Linux getestet (Pandoc 3.7.0.2, Chromium 151 als Snap-Paket, kein Carlito installiert → Arial/sans-serif-Fallback verwendet). Erster Testlauf noch inklusive Anhang C: 94 Seiten A4, 22 Bilder eingebettet, keine Header/Footer. Nach Einbau des Anhang-C-Ausschlusses (neue Vorgabe vom selben Tag) finaler Lauf: 73 Seiten A4, weiterhin alle 22 Bilder, sauberer Seitenabschluss ohne leere Restseite. Die beiden Stolperfallen (`--resource-path=docs` bei Pandoc, HTML-Zwischendatei nicht in `/tmp` wegen Snap-Confinement von Chromium) sowie der feste Ausschluss von Anhang C sind oben bereits eingearbeitet.
