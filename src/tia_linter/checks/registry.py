"""Feste Metadaten (Name, Kategorie, Beschreibung, Empfehlung) zu jedem
Prüfpunkt — referenziert per ``check_id`` (``"<yaml-kategorie>.<yaml-key>"``).

Die konfigurierbaren Werte (enabled/severity/Parameter) kommen dagegen aus der
YAML-Config (siehe ``config.py``); dieses Registry hier bleibt über alle
Config-Profile hinweg identisch. Prüfpunkt-Nummern beziehen sich auf
``Pruefpunkte.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

KOMMENTARE = "Kommentare & Beschreibungen"
NAMENSKONVENTIONEN = "Namenskonventionen"
PROGRAMMSTRUKTUR = "Programmstruktur"
HARDWARE = "Hardware & Konfiguration"
PROJEKTMETADATEN = "Projektmetadaten"
BIBLIOTHEKEN = "Bibliotheken & Typen"
STYLEGUIDE = "Siemens Styleguide & Best Practices"


@dataclass(frozen=True)
class CheckMeta:
    name: str
    category: str
    description: str
    recommendation: str


CHECK_REGISTRY: dict[str, CheckMeta] = {
    # --- Kommentare & Beschreibungen (Prüfpunkte 1-4) ---------------------
    "kommentare.variablen_kommentar": CheckMeta(
        name="Variablen ohne Kommentar",
        category=KOMMENTARE,
        description="Prüfpunkt 1: PLC-Tags und DB-Variablen ohne Kommentar.",
        recommendation="Kommentar mit Beschreibung der Funktion/Bedeutung der Variable ergänzen.",
    ),
    "kommentare.baustein_beschreibung": CheckMeta(
        name="Bausteine ohne Kopfbeschreibung",
        category=KOMMENTARE,
        description=(
            "Prüfpunkt 2: FBs/FCs/DBs ohne (aussagekräftige) Kopfbeschreibung "
            "— Mindestlänge konfigurierbar."
        ),
        recommendation="Kopfbeschreibung mit Zweck und Funktionsweise des Bausteins ergänzen.",
    ),
    "kommentare.netzwerk_beschreibung": CheckMeta(
        name="Netzwerk ohne Beschreibung",
        category=KOMMENTARE,
        description="Prüfpunkt 3: Netzwerke ohne Titel/Kurzbeschreibung oder mit zu langer Beschreibung.",
        recommendation="Kurzen, prägnanten Netzwerktitel ergänzen (Länge siehe Konfiguration).",
    ),
    "kommentare.aenderungshistorie": CheckMeta(
        name="Bausteinköpfe ohne Änderungshistorie",
        category=KOMMENTARE,
        description="Prüfpunkt 4: Bausteinkopf ohne Versionsinfo/Änderungshistorie (Autor, Version, Datum).",
        recommendation="Änderungshistorie im Bausteinkopf gemäß Siemens Standardisierungsleitfaden pflegen.",
    ),
    # --- Namenskonventionen (Prüfpunkte 5-9) -------------------------------
    "namenskonventionen.db_format": CheckMeta(
        name="DB-Namensformat",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 5: Datenbausteinname entspricht nicht dem konfigurierten Regex-Muster.",
        recommendation="Datenbaustein gemäß Namenskonvention umbenennen.",
    ),
    "namenskonventionen.plc_tag_eingaenge": CheckMeta(
        name="PLC-Tag Namenskonvention (Eingänge)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 6: Eingangs-Tag entspricht nicht dem konfigurierten Muster.",
        recommendation="Tag gemäß Namenskonvention für Eingänge umbenennen (siehe Konfiguration).",
    ),
    "namenskonventionen.plc_tag_ausgaenge": CheckMeta(
        name="PLC-Tag Namenskonvention (Ausgänge)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 6: Ausgangs-Tag entspricht nicht dem konfigurierten Muster.",
        recommendation="Tag gemäß Namenskonvention für Ausgänge umbenennen (siehe Konfiguration).",
    ),
    "namenskonventionen.fb_prefix": CheckMeta(
        name="Bausteinname Konvention (FB)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 7: Funktionsbaustein entspricht nicht dem konfigurierten Regex.",
        recommendation="Funktionsbaustein gemäß Namenskonvention umbenennen (siehe Konfiguration).",
    ),
    "namenskonventionen.fc_prefix": CheckMeta(
        name="Bausteinname Konvention (FC)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 7: Funktion entspricht nicht dem konfigurierten Regex.",
        recommendation="Funktion gemäß Namenskonvention umbenennen (siehe Konfiguration).",
    ),
    "namenskonventionen.konstanten_format": CheckMeta(
        name="Konstanten-Namensformat",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 8: Konstante entspricht nicht dem konfigurierten Regex (Standard: nur Großbuchstaben).",
        recommendation="Konstantenname gemäß Namenskonvention anpassen (siehe Konfiguration).",
    ),
    "namenskonventionen.testvariablen": CheckMeta(
        name="Testvariablen vorhanden",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 9: Variable mit Test-/Debug-Präfix (aus Config) im Projekt gefunden.",
        recommendation="Prüfen ob Testvariable noch benötigt wird — sonst entfernen.",
    ),
    # --- Programmstruktur (Prüfpunkte 10-16) -------------------------------
    "programmstruktur.leere_netzwerke": CheckMeta(
        name="Leere Netzwerke",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 10: Netzwerk ohne Inhalt (keine Kontakte, keine Bausteinaufrufe).",
        recommendation="Leeres Netzwerk mit Logik befüllen oder entfernen.",
    ),
    "programmstruktur.unbenutzte_variablen": CheckMeta(
        name="Unbenutzte Variablen (Dead Code)",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 11: PLC-Tag/DB-Variable wird im gesamten Programm nirgends referenziert.",
        recommendation="Unbenutzte Variable entfernen oder Verwendung ergänzen.",
    ),
    "programmstruktur.unbenutzte_bausteine": CheckMeta(
        name="Unbenutzte Bausteine",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 11b: FB/FC/DB wird von keiner Stelle im Projekt aufgerufen/referenziert.",
        recommendation="Unbenutzten Baustein entfernen oder Aufruf ergänzen.",
    ),
    "programmstruktur.eingaenge_gelesen": CheckMeta(
        name="Eingänge min. 1x gelesen",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 12: Eingangs-Tag wird im Programm nie gelesen.",
        recommendation="Prüfen ob der Eingang tatsächlich benötigt wird, sonst Beschaltung/Tag entfernen.",
    ),
    "programmstruktur.ausgaenge_mehrfach_schreiben": CheckMeta(
        name="Ausgänge max. 1x geschrieben",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 13: Ausgangs-Tag wird an mehreren Stellen im Programm beschrieben.",
        recommendation="Schreibzugriffe auf den Ausgang auf eine einzige Stelle konsolidieren.",
    ),
    "programmstruktur.awl_code": CheckMeta(
        name="AWL-Code vorhanden",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 14: Baustein bzw. Netzwerk ist in AWL/STL programmiert.",
        recommendation="Baustein nach KOP/FUP/SCL migrieren (AWL gilt als veraltet).",
    ),
    "programmstruktur.gemischte_sprachen": CheckMeta(
        name="Gemischte Programmiersprachen",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 15: Innerhalb eines Bausteins werden mehrere Sprachen gemischt (z. B. KOP und SCL).",
        recommendation="Baustein auf eine einheitliche Programmiersprache vereinheitlichen.",
    ),
    "programmstruktur.max_netzwerk_elemente": CheckMeta(
        name="Zu komplexe Netzwerke",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 16: Netzwerk mit mehr Elementen als der konfigurierte Schwellenwert.",
        recommendation="Netzwerk aufteilen oder in einen eigenen Baustein auslagern.",
    ),
    # --- Hardware & Konfiguration (Prüfpunkte 17-18c) ----------------------
    "hardware.hardware_vorhanden": CheckMeta(
        name="Hardware vorhanden und aktiviert",
        category=HARDWARE,
        description="Prüfpunkt 17: Für einen I/O-Tag ist kein passendes, aktives Hardware-Modul vorhanden.",
        recommendation="Hardware-Konfiguration prüfen — Modul projektieren/aktivieren oder Tag entfernen.",
    ),
    "hardware.cpu_firmware_dokumentiert": CheckMeta(
        name="CPU-Typ und Firmware-Version dokumentiert",
        category=HARDWARE,
        description="Prüfpunkt 18: CPU-Typ oder Firmware-Version sind in den Projekteigenschaften nicht vermerkt.",
        recommendation="CPU-Typ und Firmware-Version in den Projekteigenschaften dokumentieren.",
    ),
    "hardware.safety_passwort": CheckMeta(
        name="Passwortschutz bei Sicherheits-SPS",
        category=HARDWARE,
        description="Prüfpunkt 18b: F-CPU ohne gesetztes Safety-Offline-Passwort.",
        recommendation="F-Passwort für die Sicherheits-CPU vergeben (SafetyAdministration).",
    ),
    "hardware.zertifikat": CheckMeta(
        name="Kommunikationszertifikat",
        category=HARDWARE,
        description="Prüfpunkt 18c: Kein Kommunikationszertifikat vorhanden oder Restlaufzeit unter Schwellenwert.",
        recommendation="Zertifikat einspielen bzw. rechtzeitig vor Ablauf erneuern.",
    ),
    # --- Projektmetadaten (Prüfpunkte 19-22) -------------------------------
    "projektmetadaten.pflichtfelder": CheckMeta(
        name="Kundeninformation in Projekteigenschaften",
        category=PROJEKTMETADATEN,
        description=(
            "Prüfpunkt 19: Konfiguriertes Pflichtfeld in den Top-Level-Projekteigenschaften ist leer. "
            "Wichtig: 'felder' in der Config muss die echten (englischen) Openness-Attributnamen "
            "enthalten, z. B. 'Author', nicht die deutsche GUI-Bezeichnung 'Autor'."
        ),
        recommendation="Pflichtfeld in den Projekteigenschaften ausfüllen.",
    ),
    "projektmetadaten.max_sprachen": CheckMeta(
        name="Anzahl Sprachen",
        category=PROJEKTMETADATEN,
        description="Prüfpunkt 20: Mehr aktive Sprachen im Projekt als konfiguriertes Maximum (oft vergessene Testsprachen).",
        recommendation="Nicht mehr benötigte Sprachen aus den Projekteigenschaften entfernen.",
    ),
    "projektmetadaten.kompilierfehler": CheckMeta(
        name="Kompilierfehler und Warnungen",
        category=PROJEKTMETADATEN,
        description="Prüfpunkt 21: Beim Übersetzen der PLC-Software sind Fehler oder Warnungen aufgetreten.",
        recommendation="Compiler-Meldung beheben und Baustein neu übersetzen.",
    ),
    "projektmetadaten.projektversion": CheckMeta(
        name="Projektversion vorhanden",
        category=PROJEKTMETADATEN,
        description="Prüfpunkt 22: Projekt hat keine Versionsnummer hinterlegt.",
        recommendation="Versionsnummer (z. B. 1.2.3) in den Projekteigenschaften vergeben.",
    ),
    # --- Bibliotheken & Typen (Prüfpunkte 23-24) ---------------------------
    "bibliotheken.veraltete_bibliotheken": CheckMeta(
        name="Bibliotheksbausteine auf aktuellem Stand",
        category=BIBLIOTHEKEN,
        description="Prüfpunkt 23: Verwendeter Bibliothekstyp entspricht nicht der aktuellen Bibliotheksversion.",
        recommendation="Bibliothekstyp in der Projektbibliothek aktualisieren und Instanzen neu generieren.",
    ),
    "bibliotheken.verwaiste_instanz_dbs": CheckMeta(
        name="Instanz-DBs ohne zugehörigen FB",
        category=BIBLIOTHEKEN,
        description="Prüfpunkt 24: Instanz-Datenbaustein, dessen Quell-FB nicht mehr im Projekt existiert.",
        recommendation="Verwaisten Instanz-DB entfernen oder zugehörigen FB wiederherstellen.",
    ),
    # --- Siemens Styleguide & Best Practices (Prüfpunkte 25-35) ------------
    "styleguide.sprachen_konsistent": CheckMeta(
        name="Sprachen konsistent",
        category=STYLEGUIDE,
        description="Prüfpunkt 25: Kommentare/Netzwerktitel weichen von der in Config erwarteten Sprache ab.",
        recommendation="Kommentare und Netzwerktitel einheitlich in der Projektsprache verfassen.",
    ),
    "styleguide.static_zugriff_extern": CheckMeta(
        name="Direkter Zugriff auf Static-Tags von außen",
        category=STYLEGUIDE,
        description="Prüfpunkt 26: Static-Tag eines FB wird von außerhalb des FB direkt gelesen/beschrieben.",
        recommendation="Zugriff über Ein-/Ausgangsparameter des FB kapseln statt direkt auf den Instanz-DB zuzugreifen.",
    ),
    "styleguide.output_mehrfach_beschrieben": CheckMeta(
        name="Output-Tag pro Zyklus nur einmal beschrieben",
        category=STYLEGUIDE,
        description="Prüfpunkt 27: VAR_OUTPUT-Parameter wird innerhalb eines Bausteins an mehreren Stellen beschrieben.",
        recommendation="Schreibzugriffe auf den Output-Parameter auf eine Stelle im Baustein konsolidieren.",
    ),
    "styleguide.multi_instanzen": CheckMeta(
        name="Multi-Instanzen statt Einzel-Instanzen",
        category=STYLEGUIDE,
        description="Prüfpunkt 28: Timer/Zähler/FB-Aufruf verwendet einen Einzel-Instanz-DB statt einer Multi-Instanz.",
        recommendation="Aufruf auf Multi-Instanz umstellen (spart Bausteine und DBs).",
    ),
    "styleguide.udt_wiederkehrende_strukturen": CheckMeta(
        name="UDT für wiederkehrende Strukturen",
        category=STYLEGUIDE,
        description="Prüfpunkt 29: Identische STRUCT-Definition kommt in mehreren DBs vor, ohne als UDT ausgelagert zu sein.",
        recommendation="Wiederkehrende Struktur als PLC-Datentyp (UDT) anlegen und referenzieren.",
    ),
    "styleguide.ob1_komplexitaet": CheckMeta(
        name="OB1 (Main) Komplexität",
        category=STYLEGUIDE,
        description="Prüfpunkt 30: OB1 enthält mehr Netzwerke mit eigener Logik als der konfigurierte Schwellenwert.",
        recommendation="Logik aus OB1 in eigene Bausteine auslagern — OB1 sollte primär Bausteine aufrufen.",
    ),
    "styleguide.know_how_schutz": CheckMeta(
        name="Know-How-Schutz dokumentiert",
        category=STYLEGUIDE,
        description="Prüfpunkt 31: Know-how-geschützter Baustein ist nicht als solcher dokumentiert.",
        recommendation="Know-how-Schutz im Bausteinkopf bzw. in der Projektdokumentation vermerken.",
    ),
    "styleguide.tag_tabellen_nur_io": CheckMeta(
        name="Tag-Tabellen nur I/O-Tags",
        category=STYLEGUIDE,
        description="Prüfpunkt 32: Tag-Tabelle enthält Tags außerhalb des I-/Q-Adressbereichs.",
        recommendation="Nicht-I/O-Tags (Merker etc.) in eine eigene Tag-Tabelle verschieben.",
    ),
    "styleguide.nicht_optimierte_bausteine": CheckMeta(
        name="Nicht-optimierte Bausteine",
        category=STYLEGUIDE,
        description="Prüfpunkt 33: Baustein ist mit Standard- statt optimiertem Bausteinzugriff projektiert.",
        recommendation="Bausteinzugriff auf 'Optimiert' umstellen, sofern kein technischer Grund dagegenspricht.",
    ),
    "styleguide.bausteine_im_root": CheckMeta(
        name="Bausteine im Root ohne Ordnerstruktur",
        category=STYLEGUIDE,
        description="Prüfpunkt 34: Mehr Bausteine im Wurzelordner als der konfigurierte Schwellenwert.",
        recommendation="Bausteine in thematische Unterordner/Gruppen einsortieren.",
    ),
    "styleguide.schreibschutz": CheckMeta(
        name="Schreibschutz von Bausteinen",
        category=STYLEGUIDE,
        description="Prüfpunkt 35 (neu in V21): Baustein hat Schreibschutz, der nicht dokumentiert ist.",
        recommendation="Schreibschutz im Bausteinkopf bzw. in der Projektdokumentation vermerken.",
    ),
}
