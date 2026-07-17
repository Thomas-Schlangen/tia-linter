# Mitwirken am TIA Linter

Danke für dein Interesse, zum TIA Linter beizutragen! Diese Datei
beschreibt kurz den Ablauf.

## Bevor du startest

- Für größere Änderungen (neue Prüfpunkte, Architekturänderungen) am
  besten vorher ein Issue eröffnen und kurz abstimmen, bevor du viel
  Arbeit investierst.
- Für kleinere Fixes (Tippfehler, Bugfixes) kannst du direkt einen Pull
  Request öffnen.

## Contributor License Agreement (CLA)

Dieses Projekt steht unter der
[GNU General Public License v3.0](LICENSE). Damit der Projektinhaber das
Projekt langfristig flexibel weiterentwickeln kann (z. B. bei einer
künftigen Umlizenzierung), gilt zusätzlich das
[Contributor License Agreement (.github/CLA.md)](.github/CLA.md).

**Ein automatisierter CLA-Check (CLA Assistant) läuft für dieses
Repository.** Bei deinem ersten Pull Request postet der Bot einen
Kommentar mit einem Link zum CLA — erst nach deiner Zustimmung (Kommentar
*„I have read the CLA Document and I hereby sign the CLA"*) wird der PR
mergebar. Bitte lies das CLA vorher durch — im Kern regelt es, dass du dem
Projekt ein zusätzliches, weitreichendes Nutzungsrecht an deinem Beitrag
einräumst, während du selbst Urheber deines Beitrags bleibst und ihn auch
weiterhin frei anderweitig verwenden darfst.

## Ablauf für einen Beitrag

1. Repository forken und einen aussagekräftig benannten Branch anlegen.
2. Änderungen vornehmen.
3. Sicherstellen, dass die bestehende Testsuite durchläuft:
   ```bash
   pytest tests/
   ```
4. Bei Änderungen an den Check-Modulen (`src/tia_linter/checks/`) nach
   Möglichkeit passende Tests ergänzen — siehe `tests/test_tia_helpers.py`
   als Beispiel für Tests, die ohne TIA Portal/Windows laufen.
5. Pull Request öffnen und kurz beschreiben, was und warum geändert
   wurde.

## Hinweise zum Code

- Deutsche Bezeichner/Kommentare im Code sind in diesem Projekt üblich —
  bitte beibehalten.
- TIA-Portal-spezifische Importe (`Siemens.Engineering.*`) gehören lokal
  in die jeweilige Funktion, nicht auf Modulebene — dadurch bleiben
  Dateien wie `_tia_helpers.py` unter Linux ohne TIA Portal testbar.
- Bei neuen Prüfpunkten: Eintrag in `checks/registry.py` (Metadaten) +
  Check-Klasse im passenden `checks/*.py`-Modul + Eintrag in
  `config/default.yaml`.

## Lizenz

Mit deinem Beitrag erklärst du dich einverstanden, dass er unter der
[GNU General Public License v3.0](LICENSE) veröffentlicht wird (siehe
auch [.github/CLA.md](.github/CLA.md)).
