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
    """Feste Metadaten eines Prüfpunkts (Name, Kategorie, Beschreibung,
    Empfehlung, Nummer) — über alle Config-Profile hinweg identisch. Die
    konfigurierbaren Werte (enabled/severity/Parameter) kommen dagegen aus der
    YAML-Config (siehe ``config.py::CheckEntryConfig``) und werden in
    ``build_check_definitions`` mit diesen Metadaten zu einer vollständigen
    ``CheckDefinition`` zusammengeführt."""

    name: str
    category: str
    description: str
    recommendation: str
    # Prüfpunkt-Nummer(n) aus Pruefpunkte.md, z. B. "5" oder "17b" — als
    # String statt int/tuple, da manche Nummern Buchstaben-Suffixe tragen
    # (11b, 12b, 18b, 18c) und ein Eintrag im Prinzip auch mehrere Nummern
    # abdecken könnte (bisher kein Fall, aber die GUI zeigt in dem Fall
    # einfach beide, z. B. "6/7"). Wird in der GUI links neben jeder
    # Prüfpunkt-Checkbox angezeigt (siehe gui.py, rebuild_check_tree).
    nummer: str


CHECK_REGISTRY: dict[str, CheckMeta] = {
    # --- Kommentare & Beschreibungen (Prüfpunkte 1-4) ---------------------
    "kommentare.variablen_kommentar": CheckMeta(
        name="Variablen ohne Kommentar",
        category=KOMMENTARE,
        description="Prüfpunkt 1a: PLC-Tags und DB-Variablen ohne Kommentar.",
        recommendation="Kommentar mit Beschreibung der Funktion/Bedeutung der Variable ergänzen.",
        nummer="1a",
    ),
    "kommentare.udt_kommentar": CheckMeta(
        name="UDT ohne Kommentar",
        category=KOMMENTARE,
        description=(
            "Prüfpunkt 1b: PLC-Datentyp (UDT) selbst oder eines seiner Items ohne Kommentar. "
            "Ergänzt Prüfpunkt 1a, dessen DB-Variablen-Prüfung Items innerhalb eines "
            "UDT-typisierten Members bewusst nicht mehr einzeln erfasst."
        ),
        recommendation="Kommentar auf dem PLC-Datentyp bzw. dem betroffenen Item ergänzen.",
        nummer="1b",
    ),
    "kommentare.fb_member_kommentar": CheckMeta(
        name="FB-Interface-Member ohne Kommentar",
        category=KOMMENTARE,
        description=(
            "Prüfpunkt 1c: Interface-Member eines Funktionsbausteins (FB) ohne Kommentar "
            "(nur die Member selbst, nicht der FB-Kopfkommentar — siehe Prüfpunkt 2). "
            "Ergänzt Prüfpunkt 1a, dessen DB-Variablen-Prüfung Items innerhalb einer "
            "Multi-Instanz-FB-Variable bewusst nicht mehr einzeln erfasst."
        ),
        recommendation="Kommentar auf dem betroffenen FB-Interface-Member ergänzen.",
        nummer="1c",
    ),
    "kommentare.baustein_beschreibung": CheckMeta(
        name="Bausteine ohne Kopfbeschreibung",
        category=KOMMENTARE,
        description=(
            "Prüfpunkt 2: FBs/FCs/DBs ohne (aussagekräftige) Kopfbeschreibung "
            "— Mindestlänge konfigurierbar."
        ),
        recommendation="Kopfbeschreibung mit Zweck und Funktionsweise des Bausteins ergänzen.",
        nummer="2",
    ),
    "kommentare.netzwerk_beschreibung": CheckMeta(
        name="Netzwerk ohne Beschreibung",
        category=KOMMENTARE,
        description="Prüfpunkt 3: Netzwerke ohne Titel/Kurzbeschreibung oder mit zu langer Beschreibung.",
        recommendation="Kurzen, prägnanten Netzwerktitel ergänzen (Länge siehe Konfiguration).",
        nummer="3",
    ),
    "kommentare.aenderungshistorie": CheckMeta(
        name="Bausteinköpfe ohne Änderungshistorie",
        category=KOMMENTARE,
        description="Prüfpunkt 4: Bausteinkopf ohne Versionsinfo/Änderungshistorie (Autor, Version, Datum).",
        recommendation="Änderungshistorie im Bausteinkopf gemäß Siemens Standardisierungsleitfaden pflegen.",
        nummer="4",
    ),
    # --- Namenskonventionen (Prüfpunkte 5-9) -------------------------------
    "namenskonventionen.db_format_global": CheckMeta(
        name="DB-Namensformat (Global-/Array-DB)",
        category=NAMENSKONVENTIONEN,
        description=(
            "Prüfpunkt 5: Name eines Global- oder Array-Datenbausteins entspricht "
            "nicht dem konfigurierten Regex-Muster."
        ),
        recommendation="Global-/Array-Datenbaustein gemäß Namenskonvention umbenennen.",
        nummer="5",
    ),
    "namenskonventionen.db_format_instance": CheckMeta(
        name="DB-Namensformat (Instanz-DB)",
        category=NAMENSKONVENTIONEN,
        description=(
            "Prüfpunkt 5: Name eines Instanz-Datenbausteins entspricht nicht dem "
            "konfigurierten Regex-Muster."
        ),
        recommendation="Instanz-Datenbaustein gemäß Namenskonvention umbenennen.",
        nummer="5",
    ),
    "namenskonventionen.plc_tag_eingaenge": CheckMeta(
        name="PLC-Tag Namenskonvention (Eingänge)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 6: Eingangs-Tag entspricht nicht dem konfigurierten Muster.",
        recommendation="Tag gemäß Namenskonvention für Eingänge umbenennen (siehe Konfiguration).",
        nummer="6",
    ),
    "namenskonventionen.plc_tag_ausgaenge": CheckMeta(
        name="PLC-Tag Namenskonvention (Ausgänge)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 6: Ausgangs-Tag entspricht nicht dem konfigurierten Muster.",
        recommendation="Tag gemäß Namenskonvention für Ausgänge umbenennen (siehe Konfiguration).",
        nummer="6",
    ),
    "namenskonventionen.fb_prefix": CheckMeta(
        name="Bausteinname Konvention (FB)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 7: Funktionsbaustein entspricht nicht dem konfigurierten Regex.",
        recommendation="Funktionsbaustein gemäß Namenskonvention umbenennen (siehe Konfiguration).",
        nummer="7",
    ),
    "namenskonventionen.fc_prefix": CheckMeta(
        name="Bausteinname Konvention (FC)",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 7: Funktion entspricht nicht dem konfigurierten Regex.",
        recommendation="Funktion gemäß Namenskonvention umbenennen (siehe Konfiguration).",
        nummer="7",
    ),
    "namenskonventionen.konstanten_format": CheckMeta(
        name="Konstanten-Namensformat",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 8: Konstante entspricht nicht dem konfigurierten Regex (Standard: nur Großbuchstaben).",
        recommendation="Konstantenname gemäß Namenskonvention anpassen (siehe Konfiguration).",
        nummer="8",
    ),
    "namenskonventionen.testvariablen": CheckMeta(
        name="Testvariablen vorhanden",
        category=NAMENSKONVENTIONEN,
        description="Prüfpunkt 9: Variable mit Test-/Debug-Präfix (aus Config) im Projekt gefunden.",
        recommendation="Prüfen ob Testvariable noch benötigt wird — sonst entfernen.",
        nummer="9",
    ),
    # --- Programmstruktur (Prüfpunkte 10-16) -------------------------------
    "programmstruktur.leere_netzwerke": CheckMeta(
        name="Leere Netzwerke",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 10: Netzwerk ohne Inhalt (keine Kontakte, keine Bausteinaufrufe).",
        recommendation="Leeres Netzwerk mit Logik befüllen oder entfernen.",
        nummer="10",
    ),
    "programmstruktur.unbenutzte_variablen": CheckMeta(
        name="Unbenutzte Variablen (Dead Code)",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 11a: PLC-Tag/DB-Variable wird im gesamten Programm nirgends referenziert.",
        recommendation="Unbenutzte Variable entfernen oder Verwendung ergänzen.",
        nummer="11a",
    ),
    "programmstruktur.unbenutzte_bausteine": CheckMeta(
        name="Unbenutzte Bausteine",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 11b: FB/FC/DB wird von keiner Stelle im Projekt aufgerufen/referenziert.",
        recommendation="Unbenutzten Baustein entfernen oder Aufruf ergänzen.",
        nummer="11b",
    ),
    "programmstruktur.eingaenge_gelesen": CheckMeta(
        name="Eingänge min. 1x gelesen",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 12a: Eingangs-Tag wird im Programm nie gelesen.",
        recommendation="Prüfen ob der Eingang tatsächlich benötigt wird, sonst Beschaltung/Tag entfernen.",
        nummer="12a",
    ),
    "programmstruktur.eingaenge_nicht_beschrieben": CheckMeta(
        name="Eingänge dürfen nicht beschrieben werden",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 12b: Eingangs-Tag wird im Programm beschrieben (statt nur gelesen).",
        recommendation=(
            "Schreibzugriff auf den Eingang entfernen — Eingänge sind nur lesend zu verwenden. "
            "Falls ein veränderbarer Wert benötigt wird, eine separate Merker-/Hilfsvariable verwenden."
        ),
        nummer="12b",
    ),
    "programmstruktur.ausgaenge_mehrfach_schreiben": CheckMeta(
        name="Ausgänge max. 1x geschrieben",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 13: Ausgangs-Tag wird an mehreren Stellen im Programm beschrieben.",
        recommendation="Schreibzugriffe auf den Ausgang auf eine einzige Stelle konsolidieren.",
        nummer="13",
    ),
    "programmstruktur.awl_code": CheckMeta(
        name="AWL-Code vorhanden",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 14: Baustein bzw. Netzwerk ist in AWL/STL programmiert.",
        recommendation="Baustein nach KOP/FUP/SCL migrieren (AWL gilt als veraltet).",
        nummer="14",
    ),
    "programmstruktur.gemischte_sprachen": CheckMeta(
        name="Gemischte Programmiersprachen",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 15: Innerhalb eines Bausteins werden mehrere Sprachen gemischt (z. B. KOP und SCL).",
        recommendation="Baustein auf eine einheitliche Programmiersprache vereinheitlichen.",
        nummer="15",
    ),
    "programmstruktur.max_netzwerk_elemente": CheckMeta(
        name="Zu komplexe Netzwerke",
        category=PROGRAMMSTRUKTUR,
        description="Prüfpunkt 16: Netzwerk mit mehr Elementen als der konfigurierte Schwellenwert.",
        recommendation="Netzwerk aufteilen oder in einen eigenen Baustein auslagern.",
        nummer="16",
    ),
    # --- Hardware & Konfiguration (Prüfpunkte 17-18c) ----------------------
    "hardware.hardware_vorhanden": CheckMeta(
        name="Hardware vorhanden und aktiviert",
        category=HARDWARE,
        description="Prüfpunkt 17: Für einen I/O-Tag ist kein passendes, aktives Hardware-Modul vorhanden.",
        recommendation="Hardware-Konfiguration prüfen — Modul projektieren/aktivieren oder Tag entfernen.",
        nummer="17",
    ),
    "hardware.cpu_firmware_dokumentiert": CheckMeta(
        name="CPU-Typ und Firmware-Version dokumentiert",
        category=HARDWARE,
        description="Prüfpunkt 18a: CPU-Typ oder Firmware-Version sind in den Projekteigenschaften nicht vermerkt.",
        recommendation="CPU-Typ und Firmware-Version in den Projekteigenschaften dokumentieren.",
        nummer="18a",
    ),
    "hardware.safety_passwort": CheckMeta(
        name="Passwortschutz bei Sicherheits-SPS",
        category=HARDWARE,
        description="Prüfpunkt 18b: F-CPU ohne gesetztes Safety-Offline-Passwort.",
        recommendation="F-Passwort für die Sicherheits-CPU vergeben (SafetyAdministration).",
        nummer="18b",
    ),
    "hardware.zertifikat": CheckMeta(
        name="Kommunikationszertifikat",
        category=HARDWARE,
        description="Prüfpunkt 18c: Kein Kommunikationszertifikat vorhanden oder Restlaufzeit unter Schwellenwert.",
        recommendation="Zertifikat einspielen bzw. rechtzeitig vor Ablauf erneuern.",
        nummer="18c",
    ),
    # --- Projektmetadaten (Prüfpunkte 19-21) -------------------------------
    "projektmetadaten.pflichtfelder": CheckMeta(
        name="Kundeninformation in Projekteigenschaften",
        category=PROJEKTMETADATEN,
        description=(
            "Prüfpunkt 19: Konfiguriertes Pflichtfeld in den Top-Level-Projekteigenschaften ist leer. "
            "Wichtig: 'felder' in der Config muss die echten (englischen) Openness-Attributnamen "
            "enthalten, z. B. 'Author', nicht die deutsche GUI-Bezeichnung 'Autor'."
        ),
        recommendation="Pflichtfeld in den Projekteigenschaften ausfüllen.",
        nummer="19",
    ),
    "projektmetadaten.max_sprachen": CheckMeta(
        name="Anzahl Sprachen",
        category=PROJEKTMETADATEN,
        description="Prüfpunkt 20: Mehr aktive Sprachen im Projekt als konfiguriertes Maximum (oft vergessene Testsprachen).",
        recommendation="Nicht mehr benötigte Sprachen aus den Projekteigenschaften entfernen.",
        nummer="20",
    ),
    "projektmetadaten.kompilierfehler": CheckMeta(
        name="Kompilierfehler und Warnungen",
        category=PROJEKTMETADATEN,
        description="Prüfpunkt 21: Beim Übersetzen der PLC-Software sind Fehler oder Warnungen aufgetreten.",
        recommendation="Compiler-Meldung beheben und Baustein neu übersetzen.",
        nummer="21",
    ),
    # --- Bibliotheken & Typen (Prüfpunkte 22-23) ---------------------------
    "bibliotheken.veraltete_bibliotheken": CheckMeta(
        name="Bibliotheksbausteine auf aktuellem Stand",
        category=BIBLIOTHEKEN,
        description="Prüfpunkt 22: Verwendeter Bibliothekstyp entspricht nicht der aktuellen Bibliotheksversion.",
        recommendation="Bibliothekstyp in der Projektbibliothek aktualisieren und Instanzen neu generieren.",
        nummer="22",
    ),
    "bibliotheken.verwaiste_instanz_dbs": CheckMeta(
        name="Instanz-DBs ohne zugehörigen FB",
        category=BIBLIOTHEKEN,
        description="Prüfpunkt 23: Instanz-Datenbaustein, dessen Quell-FB nicht mehr im Projekt existiert.",
        recommendation="Verwaisten Instanz-DB entfernen oder zugehörigen FB wiederherstellen.",
        nummer="23",
    ),
    # --- Siemens Styleguide & Best Practices (Prüfpunkte 24-33) ------------
    "styleguide.sprachen_konsistent": CheckMeta(
        name="Sprachen konsistent",
        category=STYLEGUIDE,
        description="Prüfpunkt 24: Kommentare/Netzwerktitel weichen von der in Config erwarteten Sprache ab.",
        recommendation="Kommentare und Netzwerktitel einheitlich in der Projektsprache verfassen.",
        nummer="24",
    ),
    "styleguide.static_zugriff_extern": CheckMeta(
        name="Direkter Zugriff auf Static-Tags von außen",
        category=STYLEGUIDE,
        description="Prüfpunkt 25: Static-Tag eines FB wird von außerhalb des FB direkt gelesen/beschrieben.",
        recommendation="Zugriff über Ein-/Ausgangsparameter des FB kapseln statt direkt auf den Instanz-DB zuzugreifen.",
        nummer="25",
    ),
    "styleguide.output_mehrfach_beschrieben": CheckMeta(
        name="InOut und Output-Tag nur einmal beschrieben",
        category=STYLEGUIDE,
        description="Prüfpunkt 26: VAR_OUTPUT-/VAR_IN_OUT-Parameter wird innerhalb eines Bausteins an mehreren Stellen beschrieben.",
        recommendation="Schreibzugriffe auf den Output-Parameter auf eine Stelle im Baustein konsolidieren.",
        nummer="26",
    ),
    "styleguide.udt_wiederkehrende_strukturen": CheckMeta(
        name="UDT für wiederkehrende Strukturen",
        category=STYLEGUIDE,
        description="Prüfpunkt 27: Identische STRUCT-Definition kommt in mehreren DBs vor, ohne als UDT ausgelagert zu sein.",
        recommendation="Wiederkehrende Struktur als PLC-Datentyp (UDT) anlegen und referenzieren.",
        nummer="27",
    ),
    "styleguide.ob1_komplexitaet": CheckMeta(
        name="OB1 (Main) Komplexität",
        category=STYLEGUIDE,
        description="Prüfpunkt 28: OB1 enthält mehr Netzwerke mit eigener Logik als der konfigurierte Schwellenwert.",
        recommendation="Logik aus OB1 in eigene Bausteine auslagern — OB1 sollte primär Bausteine aufrufen.",
        nummer="28",
    ),
    "styleguide.know_how_schutz": CheckMeta(
        name="Know-How-Schutz dokumentiert",
        category=STYLEGUIDE,
        description="Prüfpunkt 29: Know-how-geschützter Baustein ist nicht als solcher dokumentiert.",
        recommendation="Know-how-Schutz im Bausteinkopf bzw. in der Projektdokumentation vermerken.",
        nummer="29",
    ),
    "styleguide.tag_tabellen_nur_io": CheckMeta(
        name="Tag-Tabellen nur I/O-Tags",
        category=STYLEGUIDE,
        description="Prüfpunkt 30: Tag-Tabelle enthält Tags außerhalb des I-/Q-Adressbereichs.",
        recommendation="Nicht-I/O-Tags (Merker etc.) in eine eigene Tag-Tabelle verschieben.",
        nummer="30",
    ),
    "styleguide.nicht_optimierte_bausteine": CheckMeta(
        name="Nicht-optimierte Bausteine",
        category=STYLEGUIDE,
        description="Prüfpunkt 31: Baustein ist mit Standard- statt optimiertem Bausteinzugriff projektiert.",
        recommendation="Bausteinzugriff auf 'Optimiert' umstellen, sofern kein technischer Grund dagegenspricht.",
        nummer="31",
    ),
    "styleguide.bausteine_im_root": CheckMeta(
        name="Bausteine im Root ohne Ordnerstruktur",
        category=STYLEGUIDE,
        description="Prüfpunkt 32: Mehr Bausteine im Wurzelordner als der konfigurierte Schwellenwert.",
        recommendation="Bausteine in thematische Unterordner/Gruppen einsortieren.",
        nummer="32",
    ),
    "styleguide.schreibschutz": CheckMeta(
        name="Schreibschutz von Bausteinen",
        category=STYLEGUIDE,
        description="Prüfpunkt 33 (neu in V21): Baustein hat Schreibschutz, der nicht dokumentiert ist.",
        recommendation="Schreibschutz im Bausteinkopf bzw. in der Projektdokumentation vermerken.",
        nummer="33",
    ),
}
