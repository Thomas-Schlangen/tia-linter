"""Prüfpunkte 23-35: Bibliotheken & Typen sowie Siemens Styleguide & Best Practices.

Einige Checks in diesem Modul (26-29, 35) beruhen auf Attributen/Diensten,
die in der allgemeinen Openness-Referenzdokumentation nicht abschließend
belegt sind (siehe jeweilige Klassen-Docstrings) — Struktur und Zugriffspfad
sind plausibel gewählt, aber vor produktivem Einsatz gegen ein echtes
TIA-Portal-V21-Projekt zu verifizieren (siehe README, "Bekannte Einschränkungen").
"""

from __future__ import annotations

from typing import Any

from tia_linter.checks._tia_helpers import (
    compile_unit_attribute,
    compile_unit_element_count,
    cross_reference_locations,
    export_block_xml,
    format_path,
    get_attribute,
    iter_blocks,
    iter_compile_units,
    iter_data_blocks,
    iter_plc_software,
    iter_tag_tables,
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
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.Library import UpdateCheckMode

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
            fb_names = {block.Name for block, _ in iter_blocks(plc_software) if isinstance(block, FB)}

            for db, group_path in iter_data_blocks(plc_software):
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

    Nicht abschließend belegt: ob ``Interface.Member``-Objekte selbst einen
    ``CrossReferenceService`` bereitstellen (die Referenzdokumentation belegt
    das nur für Bausteine). ``cross_reference_locations`` fängt eine
    fehlende Service-Verfügbarkeit ab und liefert dann schlicht keine
    Befunde für diesen Member.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import InstanceDB

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for db, group_path in iter_data_blocks(plc_software):
                if not isinstance(db, InstanceDB):
                    continue
                owner_fb = str(get_attribute(db, "InstanceOfName", "") or "")
                interface = getattr(db, "Interface", None)
                for member in getattr(interface, "Members", []) or []:
                    if str(get_attribute(member, "Modifier", "")).lower() != "static":
                        continue
                    for location in cross_reference_locations(member):
                        source_block_name = str(getattr(getattr(location, "Parent", None), "Name", "") or "")
                        if source_block_name and source_block_name != owner_fb and source_block_name != db.Name:
                            results.append(
                                self._make_result(
                                    path=format_path(
                                        plc_software.Name, "Datenbaustein", *group_path, db.Name, "Member", member.Name
                                    ),
                                    description=(
                                        f"Static-Tag '{member.Name}' wird von außerhalb "
                                        f"('{source_block_name}') direkt zugegriffen."
                                    ),
                                    value=source_block_name,
                                )
                            )
                            break
        return results


class OutputMehrfachBeschriebenCheck(BaseCheck):
    """Prüfpunkt 27: VAR_OUTPUT-Parameter wird an mehreren Stellen im Baustein beschrieben."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access
        from Siemens.Engineering.SW.Blocks import FB, FC

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software):
                if not isinstance(block, (FB, FC)):
                    continue
                interface = getattr(block, "Interface", None)
                for member in getattr(interface, "Members", []) or []:
                    if str(get_attribute(member, "Modifier", "")).lower() != "output":
                        continue
                    locations = cross_reference_locations(member)
                    write_count = sum(1 for loc in locations if getattr(loc, "Access", None) == Access.Write)
                    if write_count > 1:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, member.Name
                                ),
                                description=f"Output-Parameter '{member.Name}' wird an {write_count} Stellen beschrieben.",
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
            for db, group_path in iter_data_blocks(plc_software):
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
            for db, group_path in iter_data_blocks(plc_software):
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
            for block, group_path in iter_blocks(plc_software):
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
    """Prüfpunkt 31: Know-how-geschützte Bausteine ohne entsprechenden Vermerk."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software):
                if not bool(get_attribute(block, "IsKnowHowProtected", False)):
                    continue
                comment = str(get_attribute(block, "Comment", "") or "").lower()
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
            for tag_table in iter_tag_tables(plc_software):
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
    """Prüfpunkt 33: Bausteine mit Standard- statt optimiertem Bausteinzugriff."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software):
                is_optimized = get_attribute(block, "IsOptimizedBlockAccess")
                if is_optimized is False:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=f"Baustein '{block.Name}' ist nicht optimiert (Standardzugriff).",
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

    Attributname ``IsWriteProtected`` ist eine plausible Annahme (V21 führt
    laut Openness-API-V21-Aenderungen.md "Verwalten des Schreibschutzes von
    Bausteinen" neu ein) — nicht gegen ein echtes V21-Projekt verifiziert.
    ``get_attribute`` liefert defensiv ``None``/``False``, falls das Attribut
    nicht existiert, statt abzustürzen.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software):
                if not bool(get_attribute(block, "IsWriteProtected", False)):
                    continue
                comment = str(get_attribute(block, "Comment", "") or "").lower()
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
