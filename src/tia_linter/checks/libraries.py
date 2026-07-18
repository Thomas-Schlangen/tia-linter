"""Prüfpunkte 23-35: Bibliotheken & Typen sowie Siemens Styleguide & Best Practices.

Gegen die TIA Portal V21 Openness-Referenz (Manual 03/2026, lokal unter
~/Dokumente/ObsidianVault/Projekte/TiaOpenness/) geprüft. Checks 26/27 (Static-
/Output-Zugriff auf einzelne Interface-Member) bleiben teilweise heuristisch,
da die Referenz zwar bestätigt, dass Member als namenlose Kind-Objekte im
Kreuzreferenzbaum ihres Bausteins/DBs auftauchen (siehe
``_tia_helpers.find_source_child_by_name``), aber kein Codebeispiel zeigt,
welche ``Location``-Eigenschaft den Namen des zugreifenden Bausteins trägt —
siehe jeweiligen Klassen-Docstring.
"""

from __future__ import annotations

from typing import Any

from tia_linter.checks._tia_helpers import (
    compile_unit_attribute,
    compile_unit_element_count,
    cross_reference_root_source,
    export_block_xml,
    find_source_child_by_name,
    format_path,
    get_attribute,
    interface_section_members,
    iter_blocks,
    iter_compile_units,
    iter_data_blocks,
    iter_plc_software,
    iter_tag_tables,
    read_comment,
    reference_language,
    tag_direction,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult

# Häufige Siemens-System-/IEC-Bausteine, die typischerweise als Multi-Instanz
# statt als eigener Instanz-DB aufgerufen werden sollten (Heuristik für
# Prüfpunkt 28 — keine erschöpfende Liste).
_MULTI_INSTANCE_CANDIDATES = (
    "TON", "TOF", "TP", "TONR",
    "CTU", "CTD", "CTUD",
    "IEC_Timer", "IEC_Counter",
    "S_ODT", "S_OFFDT", "S_PULSE",
)


class VeralteteBibliothekenCheck(BaseCheck):
    """Prüfpunkt 23: Bibliothekstyp-Instanzen mit veralteter Version.

    Nutzt ``ILibrary.UpdateCheck(project, UpdateCheckMode.ReportOutOfDateOnly)``
    (Openness-Referenz, Abschnitt "Ermitteln veralteter Typinstanzen") — mit
    diesem Modus enthält das Ergebnis ausschließlich veraltete Instanzen,
    jede Blattmeldung ist somit ein Befund. Deckt nur die Projektbibliothek
    ab (``project.ProjectLibrary``); globale Bibliotheken sind in dieser
    Session nicht konfigurierbar.

    ``UpdateCheckMode`` liegt (gegen die tatsächlich installierte V21-API
    verifiziert, ``Siemens.Engineering.Base.xml``) unter
    ``Siemens.Engineering.Library.Types``, nicht direkt unter
    ``Siemens.Engineering.Library`` — der erste Testlauf gegen ein echtes
    Projekt ist an dieser falschen Fundstelle mit einem ``ImportError``
    gescheitert.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.Library.Types import UpdateCheckMode

        library = getattr(project, "ProjectLibrary", None)
        if library is None:
            return []

        try:
            update_result = library.UpdateCheck(project, UpdateCheckMode.ReportOutOfDateOnly)
        except Exception:  # noqa: BLE001 — Bibliothek evtl. leer/nicht lizenziert
            return []

        def _leaf_messages(messages: Any) -> list[Any]:
            leaves = []
            for message in messages or []:
                sub_messages = list(getattr(message, "Messages", []) or [])
                if sub_messages:
                    leaves.extend(_leaf_messages(sub_messages))
                else:
                    leaves.append(message)
            return leaves

        results: list[CheckResult] = []
        for message in _leaf_messages(getattr(update_result, "Messages", [])):
            description = str(getattr(message, "Description", "Veraltete Bibliotheksinstanz."))
            results.append(
                self._make_result(
                    path=format_path("Projektbibliothek"),
                    description=description,
                )
            )
        return results


class VerwaisteInstanzDbsCheck(BaseCheck):
    """Prüfpunkt 24: Instanz-DBs, deren Quell-FB nicht mehr im Projekt existiert."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import FB, InstanceDB

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            fb_names = {block.Name for block, _ in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks) if isinstance(block, FB)}

            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(db, InstanceDB):
                    continue
                instance_of = str(get_attribute(db, "InstanceOfName", "") or "")
                if instance_of and instance_of not in fb_names:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Datenbaustein", *group_path, db.Name),
                            description=(
                                f"Instanz-DB '{db.Name}' referenziert FB '{instance_of}', "
                                "der nicht mehr im Projekt existiert."
                            ),
                            value=instance_of,
                        )
                    )
        return results


class SprachenKonsistentCheck(BaseCheck):
    """Prüfpunkt 25: Projektsprache weicht von der erwarteten Sprache ab.

    Vereinfachung: prüft die projektweite Referenzsprache statt jeden
    einzelnen Kommentar/Netzwerktitel auf die tatsächlich verwendete Sprache
    zu analysieren (dafür wäre Spracherkennung pro Text nötig).
    """

    def run(self, project: Any) -> list[CheckResult]:
        expected = str(self.definition.params.get("erwartete_sprache", "de")).lower()
        try:
            culture = project.LanguageSettings.ReferenceLanguage.Culture
            actual = str(getattr(culture, "Name", culture)).lower()
        except Exception:  # noqa: BLE001
            return []

        if not actual.startswith(expected):
            return [
                self._make_result(
                    path=format_path("Projekt", "Eigenschaften", "Sprache"),
                    description=f"Referenzsprache des Projekts ('{actual}') weicht von '{expected}' ab.",
                    value=actual,
                )
            ]
        return []


class StaticZugriffExternCheck(BaseCheck):
    """Prüfpunkt 26: Static-Tags eines FB werden von außerhalb direkt gelesen/beschrieben.

    Ablauf: Die Namen der "Static"-Interface-Mitglieder kommen aus dem
    XML-Export der FB-Definition (Interface-Sections sind dort laut V21-
    Referenz bestätigt vorhanden, siehe ``interface_section_members``). Der
    Kreuzreferenzbaum der zugehörigen Instanz-DB (``CrossReferenceService``
    ist für Instanz-DBs laut V21-Referenz bestätigt unterstützt) wird dann
    nach einem Kind-Objekt mit passendem Namen durchsucht
    (``find_source_child_by_name`` — Member erscheinen dort laut Referenz als
    Kind-Objekte ohne ``UnderlyingObject``, aber mit Namens-Textinfo).
    Welche ``Location``-Eigenschaft den Namen des zugreifenden Bausteins
    trägt, zeigt kein Codebeispiel in der Referenz — hier wird
    ``Location.Name`` verwendet (plausibelste der dokumentierten
    Location-Eigenschaften), nicht gegen ein echtes Projekt verifiziert.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import FB, InstanceDB

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            fb_by_name = {block.Name: block for block, _ in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks) if isinstance(block, FB)}

            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(db, InstanceDB):
                    continue
                owner_name = str(get_attribute(db, "InstanceOfName", "") or "")
                owner_fb = fb_by_name.get(owner_name)
                if owner_fb is None:
                    continue

                static_members = interface_section_members(export_block_xml(owner_fb), "Static")
                if not static_members:
                    continue

                root_source = cross_reference_root_source(db)
                if root_source is None:
                    continue

                for member_name in static_members:
                    member_source = find_source_child_by_name(root_source, member_name)
                    if member_source is None:
                        continue
                    for reference in getattr(member_source, "References", []) or []:
                        for location in getattr(reference, "Locations", []) or []:
                            accessor = str(getattr(location, "Name", "") or "")
                            if accessor and accessor not in (owner_name, db.Name):
                                results.append(
                                    self._make_result(
                                        path=format_path(
                                            plc_software.Name, "Datenbaustein", *group_path, db.Name, "Member", member_name
                                        ),
                                        description=(
                                            f"Static-Tag '{member_name}' wird von außerhalb "
                                            f"('{accessor}') direkt zugegriffen."
                                        ),
                                        value=accessor,
                                    )
                                )
        return results


class OutputMehrfachBeschriebenCheck(BaseCheck):
    """Prüfpunkt 27: VAR_OUTPUT-Parameter wird an mehreren Stellen beschrieben.

    Wie Prüfpunkt 26: Output-Mitgliedernamen kommen aus dem XML-Export
    (Interface-Section "Output"), die Kreuzreferenz wird direkt am FB/FC
    abgefragt (bestätigt unterstützter Objekttyp) und pro gefundenem
    Output-Mitglied werden ``Access``-Schreibzugriffe gezählt.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access
        from Siemens.Engineering.SW.Blocks import FB, FC

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(block, (FB, FC)):
                    continue

                output_members = interface_section_members(export_block_xml(block), "Output")
                if not output_members:
                    continue

                root_source = cross_reference_root_source(block)
                if root_source is None:
                    continue

                for member_name in output_members:
                    member_source = find_source_child_by_name(root_source, member_name)
                    if member_source is None:
                        continue
                    write_count = sum(
                        1
                        for reference in getattr(member_source, "References", []) or []
                        for location in getattr(reference, "Locations", []) or []
                        if getattr(location, "Access", None) == Access.Write
                    )
                    if write_count > 1:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, member_name
                                ),
                                description=f"Output-Parameter '{member_name}' wird an {write_count} Stellen beschrieben.",
                                value=str(write_count),
                            )
                        )
        return results


class MultiInstanzenCheck(BaseCheck):
    """Prüfpunkt 28: Timer/Zähler als Einzel-Instanz-DB statt Multi-Instanz.

    Heuristik anhand einer Liste bekannter Siemens-/IEC-System-Bausteine
    (``_MULTI_INSTANCE_CANDIDATES``) — erkennt keine kundeneigenen
    FBs, die ebenfalls besser als Multi-Instanz aufgerufen würden.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import InstanceDB

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(db, InstanceDB):
                    continue
                instance_of = str(get_attribute(db, "InstanceOfName", "") or "")
                if instance_of in _MULTI_INSTANCE_CANDIDATES:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Datenbaustein", *group_path, db.Name),
                            description=(
                                f"Instanz-DB '{db.Name}' für '{instance_of}' — "
                                "als Multi-Instanz statt Einzel-Instanz-DB anlegen."
                            ),
                            value=instance_of,
                        )
                    )
        return results


class UdtWiederkehrendeStrukturenCheck(BaseCheck):
    """Prüfpunkt 29: Identische Member-Struktur kommt in mehreren DBs vor, ohne UDT zu sein."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            signatures: dict[tuple, list[tuple[Any, list[str]]]] = {}
            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                interface = getattr(db, "Interface", None)
                members = getattr(interface, "Members", None)
                if not members:
                    continue
                signature = tuple(
                    sorted((m.Name, str(get_attribute(m, "DataTypeName", "") or "")) for m in members)
                )
                if len(signature) < 2:
                    continue  # zu trivial, um als "wiederkehrende Struktur" zu zählen
                signatures.setdefault(signature, []).append((db, group_path))

            for signature, occurrences in signatures.items():
                if len(occurrences) < 2:
                    continue
                names = ", ".join(db.Name for db, _ in occurrences)
                for db, group_path in occurrences:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Datenbaustein", *group_path, db.Name),
                            description=(
                                f"Struktur von '{db.Name}' ist identisch zu {len(occurrences) - 1} "
                                f"weiteren DBs ({names}) — als UDT auslagern."
                            ),
                        )
                    )
        return results


class Ob1KomplexitaetCheck(BaseCheck):
    """Prüfpunkt 30: OB1 (Main) enthält mehr Netzwerke mit eigener Logik als der Schwellenwert."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import OB

        results: list[CheckResult] = []
        max_networks = int(self.definition.params.get("max_netzwerke_mit_logik", 5))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not isinstance(block, OB) or int(get_attribute(block, "Number", -1) or -1) != 1:
                    continue

                xml_root = export_block_xml(block)
                # Ein Netzwerk, das nur einen einzigen Bausteinaufruf enthält
                # (1 Part == der Call selbst), zählt nicht als "eigene Logik".
                logic_networks = sum(
                    1 for cu in iter_compile_units(xml_root) if compile_unit_element_count(cu) > 1
                )
                if logic_networks > max_networks:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=(
                                f"OB1 enthält {logic_networks} Netzwerke mit eigener Logik "
                                f"(Schwellenwert: {max_networks}) — Logik in eigene Bausteine auslagern."
                            ),
                            value=str(logic_networks),
                        )
                    )
        return results


class KnowHowSchutzCheck(BaseCheck):
    """Prüfpunkt 31: Know-how-geschützte Bausteine ohne entsprechenden Vermerk.

    ``PlcBlock.Comment`` ist mehrsprachig (``MultilingualText``, siehe
    ``comments.py::VariablenKommentarCheck``) — Lesen über ``read_comment``
    statt ``GetAttribute``.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        language = reference_language(project)
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not bool(get_attribute(block, "IsKnowHowProtected", False)):
                    continue
                comment = read_comment(block, language).lower()
                if "know-how" not in comment and "knowhow" not in comment:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=(
                                f"Baustein '{block.Name}' ist know-how-geschützt, "
                                "aber nicht als solcher dokumentiert."
                            ),
                        )
                    )
        return results


class TagTabellenNurIoCheck(BaseCheck):
    """Prüfpunkt 32: Tag-Tabelle mischt I/O-Tags mit Nicht-I/O-Tags."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                tags = list(tag_table.Tags)
                if not tags:
                    continue
                directions = {tag_direction(tag) for tag in tags}
                has_io = "I" in directions or "Q" in directions
                has_non_io = None in directions
                if has_io and has_non_io:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name),
                            description=(
                                f"Tag-Tabelle '{tag_table.Name}' enthält sowohl I/O-Tags als auch "
                                "andere Tags — in getrennte Tabellen aufteilen."
                            ),
                        )
                    )
        return results


class NichtOptimierteBausteineCheck(BaseCheck):
    """Prüfpunkt 33: Bausteine mit Standard- statt optimiertem Bausteinzugriff.

    Attribut ``MemoryLayout`` (enum, Werte ``Standard``/``Optimized``) ist in
    der V21-Openness-Referenz als allgemeines Bausteinattribut bestätigt
    (Manual 03/2026, "Standardwert: Standard bei klassischen PLCs und
    Optimized bei S7-1200/1500-PLCs") — ersetzt die ursprünglich angenommene,
    nicht belegte Eigenschaft ``IsOptimizedBlockAccess``.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                memory_layout = str(get_attribute(block, "MemoryLayout", "") or "")
                if memory_layout == "Standard":
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=f"Baustein '{block.Name}' ist nicht optimiert (MemoryLayout = Standard).",
                        )
                    )
        return results


class BausteineImRootCheck(BaseCheck):
    """Prüfpunkt 34: Zu viele Bausteine direkt im Wurzelordner ohne Gruppierung."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        max_root = int(self.definition.params.get("max_bausteine_root", 20))

        for plc_software in iter_plc_software(project):
            root_count = len(list(plc_software.BlockGroup.Blocks))
            if root_count > max_root:
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Programmbausteine"),
                        description=(
                            f"{root_count} Bausteine liegen direkt im Root-Ordner "
                            f"(Schwellenwert: {max_root}) — in Unterordner gruppieren."
                        ),
                        value=str(root_count),
                    )
                )
        return results


class SchreibschutzCheck(BaseCheck):
    """Prüfpunkt 35 (neu in V21): Schreibschutz von Bausteinen ohne Dokumentation.

    Attribut ``IsWriteProtected`` (Bool) ist als allgemeines Bausteinattribut
    in der V21-Openness-Referenz bestätigt (Manual 03/2026, Tabelle der
    allgemeinen Bausteinattribute). Getrennt davon führt V21 zusätzlich den
    Dienst ``PlcBlockWriteProtectionProvider`` ein (Passwort-Workflow zum
    Setzen/Aufheben des Schutzes, Abschnitt "Schreibschutz für Bausteine
    einrichten") — dieser bietet aber keine dokumentierte Eigenschaft zum
    reinen Auslesen des aktuellen Schutzstatus, daher wird hier weiterhin
    das lesbare ``IsWriteProtected``-Attribut verwendet.

    ``PlcBlock.Comment`` ist mehrsprachig (``MultilingualText``, siehe
    ``comments.py::VariablenKommentarCheck``) — Lesen über ``read_comment``
    statt ``GetAttribute``.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        language = reference_language(project)
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if not bool(get_attribute(block, "IsWriteProtected", False)):
                    continue
                comment = read_comment(block, language).lower()
                if "schreibschutz" not in comment and "write-protect" not in comment:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=(
                                f"Baustein '{block.Name}' ist schreibgeschützt, "
                                "aber nicht entsprechend dokumentiert."
                            ),
                        )
                    )
        return results


CHECK_CLASSES = {
    "bibliotheken.veraltete_bibliotheken": VeralteteBibliothekenCheck,
    "bibliotheken.verwaiste_instanz_dbs": VerwaisteInstanzDbsCheck,
    "styleguide.sprachen_konsistent": SprachenKonsistentCheck,
    "styleguide.static_zugriff_extern": StaticZugriffExternCheck,
    "styleguide.output_mehrfach_beschrieben": OutputMehrfachBeschriebenCheck,
    "styleguide.multi_instanzen": MultiInstanzenCheck,
    "styleguide.udt_wiederkehrende_strukturen": UdtWiederkehrendeStrukturenCheck,
    "styleguide.ob1_komplexitaet": Ob1KomplexitaetCheck,
    "styleguide.know_how_schutz": KnowHowSchutzCheck,
    "styleguide.tag_tabellen_nur_io": TagTabellenNurIoCheck,
    "styleguide.nicht_optimierte_bausteine": NichtOptimierteBausteineCheck,
    "styleguide.bausteine_im_root": BausteineImRootCheck,
    "styleguide.schreibschutz": SchreibschutzCheck,
}
