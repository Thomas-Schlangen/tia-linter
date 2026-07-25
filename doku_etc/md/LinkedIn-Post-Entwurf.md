# LinkedIn-Post-Entwurf — TIA Linter

*Entwurf, Stil angelehnt an den ersten Post zum TIA Tag Exporter. Bitte vor Veröffentlichung
gegenlesen und bei Bedarf anpassen (Screenshot vom PDF-Report würde sich anbieten).*

---

Jeder SPS-Programmierer kennt das: Man öffnet ein fremdes TIA-Portal-Projekt und
weiß nach fünf Minuten – hier hat sich niemand an eine Namenskonvention gehalten.

DB_Motor_01, MotorDB1, motor_db_001 – alles im selben Projekt. Kommentare mal auf
Deutsch, mal auf Englisch, meistens gar keine. Bausteine ohne Kopfbeschreibung,
Netzwerke ohne Titel, und irgendwo eine Instanz-DB, deren FB längst gelöscht wurde.

Genau dafür habe ich den **TIA Linter** gebaut: ein Tool, das ein komplettes
TIA-Portal-Projekt automatisch gegen 35 konfigurierbare Prüfpunkte prüft – über die
offizielle Siemens Openness API – und daraus einen strukturierten PDF-Prüfbericht
erstellt. Kommentare & Beschreibungen, Namenskonventionen, Programmstruktur,
Hardware-Konfiguration, Projektmetadaten, Bibliotheken und Siemens-Styleguide-Regeln
(nach Pub. ID 81318674) – alles in einem Report, mit Status OK / Warnung / Fehler
pro Fund.

Warum ist das für SPS-Programmierer relevant?

- Neue Kollegen finden sich in dokumentierten, konsistenten Projekten in Minuten
  statt Stunden zurecht.
- Vor der Übergabe an den Kunden zeigt der Report schwarz auf weiß, wo noch
  Doku fehlt – bevor der Kunde es findet.
- Wiederkehrende Stilfragen ("müssen wir das jetzt so oder so nennen?") lassen
  sich einmal in einer Config festlegen, statt sie bei jedem Review neu zu
  diskutieren.

Ich habe das Tool inzwischen gegen ein reales, gewachsenes Projekt mit über 280
Bausteinen laufen lassen – inklusive ein paar Überraschungen, die man beim reinen
Schreibtisch-Test nie gesehen hätte (z. B. dass TIA Portal pro Session nur eine
begrenzte Anzahl offener API-Instanzen erlaubt, was bei einem vollständigen Lauf
über alle Prüfpunkte tatsächlich zu einem Absturz geführt hat, bis ich das
Verbindungsmanagement entsprechend angepasst habe).

Der Code ist quelloffen auf GitHub:
👉 https://github.com/Thomas-Schlangen/tia-linter

**Frage an euch:** Welche Stilregel nervt euch in fremden TIA-Projekten am
meisten – fehlende Kommentare, wilde Namenskonventionen oder etwas ganz anderes,
das ich noch gar nicht auf dem Schirm habe?

#TIAPortal #SPSProgrammierung #Siemens #Automatisierung #Openness #SoftwareQualität #SPS #Industrie40
