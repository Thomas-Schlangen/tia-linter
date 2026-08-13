# Prompt für Claude Code (Linux) — Handbuch.pdf exakt wie unter Windows erzeugen

Diesen Block 1:1 in Claude Code auf dem Linux-Rechner einfügen (im Repo-Root von tia-linter/code):

---

Erzeuge `docs/Handbuch.pdf` aus `docs/Handbuch.md` exakt nach folgendem Verfahren, das unter Windows bereits erfolgreich 92 saubere Seiten ergeben hat (Pandoc + headless Chromium-Browser, NICHT die VS-Code-"Markdown PDF"-Erweiterung aus Anhang B, NICHT Pandocs LaTeX-Standardpfad, da dieser die Seitenumbruch-Marker ignoriert):

1. Prüfe zuerst, was verfügbar ist: `pandoc --version` sowie eines von `google-chrome --version` / `google-chrome-stable --version` / `chromium --version` / `chromium-browser --version`. Melde kurz, was gefunden wurde, bevor du weitermachst.

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

3. Wandle das Markdown in ein eigenständiges HTML mit eingebetteten Bildern um (Bilder liegen in `docs/images/`, im Markdown relativ referenziert):

```bash
pandoc docs/Handbuch.md -f markdown -t html5 --standalone \
  --embed-resources --css docs/print.css \
  -o /tmp/handbuch.html
```

   `--embed-resources` erfordert ein neueres Pandoc (>=3.0); falls die Version älter ist, stattdessen `--self-contained` verwenden (macht dasselbe).

4. Erzeuge das PDF per headless Chromium/Chrome aus dem HTML (wichtig: Chromium-Engine, nicht Pandocs LaTeX, da nur sie die Marker `<div style="page-break-after: always;">` vor jeder Kapitelüberschrift korrekt respektiert):

```bash
google-chrome --headless=new --disable-gpu \
  --print-to-pdf=docs/Handbuch.pdf \
  --no-pdf-header-footer --no-margins \
  file:///tmp/handbuch.html
```

   (`chromium` bzw. `chromium-browser` statt `google-chrome`, je nachdem was in Schritt 1 gefunden wurde.)

   Bekannte Stolperfalle vom Windows-Lauf: `--print-to-pdf-no-header` (aus älterer Chromium-Doku) unterdrückt Header/Footer NICHT zuverlässig unter `--headless=new` — es muss `--no-pdf-header-footer` sein.

5. Verifiziere das Ergebnis: PDF sollte ca. 90+ Seiten haben, keine Browser-Header/Footer (Datum, URL, Seitenzahl am Rand), alle 22 Bilder aus `docs/images/` eingebettet sichtbar, und jedes Kapitel beginnt auf einer neuen Seite (Seitenumbruch-Marker wirken). Bei Abweichungen: Pandoc-/Chrome-Version prüfen und ggf. Flags anpassen, nicht einfach den LaTeX-Pfad nehmen.

---

Kontext (nicht Teil des Prompts, nur zur Info): Diese Anleitung entspricht 1:1 dem Verfahren, das gestern (2026-08-12) unter Windows mit `msedge.exe` funktioniert hat — nur der Browser-Binary-Name und die Font-Fallbacks sind Linux-spezifisch angepasst.
