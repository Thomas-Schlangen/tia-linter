"""Prüfpunkte 10-16: Programmstruktur.

Prüfpunkte 11-13 nutzen den ``CrossReferenceService``. Gegen die TIA Portal
V21 Openness-Referenz (Manual 03/2026, Abschnitt "Unter STEP 7 auf Cross
Reference Service zugreifen") verifiziert: der Dienst ist nur auf einzelnen
STEP-7-Objekten verfügbar (OB, FB, FC, DB, Instanz-DB, Globaler DB, Array-DB,
PLC-Variable, PLC-Systemkonstante, PLC-Anwenderdatentyp) — **nicht** auf der
PLC-Software als Ganzes. Entsprechend wird hier pro Tag bzw. pro Baustein
abgefragt, nicht projektweit in einem Aufruf.
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


class LeereNetzwerkeCheck(BaseCheck):
    """Prüfpunkt 10: Netzwerke ohne Inhalt (keine Programmelemente).

    User-Meldung, live an FC ``OrgPrg`` verifiziert: TIA erlaubt gemischte
    Programmiersprachen innerhalb eines Bausteins (siehe Prüfpunkt 15,
    ``GemischteSprachenCheck``) — ein einzelnes Netzwerk kann z. B. SCL sein,
    obwohl der Baustein insgesamt als FBD geführt wird (``OrgPrg``: Netzwerk
    3/8). Der Skip anhand der **Baustein**-``ProgrammingLanguage`` greift in
    diesem Fall nicht; ein SCL-Netzwerk exportiert seinen Inhalt als
    ``<StructuredText>`` statt ``<FlgNet>``/``<Part>``, wurde also von
    ``compile_unit_element_count`` fälschlich als leer (0 Elemente) gezählt.
    Fix: zusätzlicher Skip anhand der **Netzwerk**-eigenen
    ``ProgrammingLanguage``.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if get_attribute(block, "ProgrammingLanguage") in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    if compile_unit_attribute(compile_unit, "ProgrammingLanguage") in ("SCL", "STL"):
                        continue
                    if compile_unit_element_count(compile_unit) == 0:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, f"Netzwerk {index}"
                                ),
                                description="Netzwerk ist leer (keine Programmelemente).",
                            )
                        )
        return results


class UnbenutzteVariablenCheck(BaseCheck):
    """Prüfpunkt 11: PLC-Tags ohne jegliche Referenz im Programm, sowie
    unbenutzte DB-Variablen.

    PLC-Tags: ``cross_reference_locations`` direkt am Tag (bestätigt
    unterstützter Objekttyp) — leer bedeutet unbenutzt. DB-Variablen: da
    Interface-Member selbst keinen ``CrossReferenceService`` bereitstellen,
    wird ``CrossReferenceFilter.UnusedObjects`` am jeweiligen DB abgefragt
    (DB ist bestätigt unterstützt) — die zurückgegebenen ``Sources`` sind
    dann die unbenutzten Mitglieder dieses DBs.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if not cross_reference_locations(tag):
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Variable '{tag.Name}' wird im gesamten Programm nicht verwendet.",
                                value=tag.Name,
                            )
                        )

            for db, group_path in iter_data_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                try:
                    service = db.GetService[CrossReferenceService]()
                except Exception:  # noqa: BLE001
                    service = None
                if service is None:
                    continue
                unused_result = service.GetCrossReferences(CrossReferenceFilter.UnusedObjects)
                for source in getattr(unused_result, "Sources", []) or []:
                    name = getattr(source, "Name", None)
                    if not name:
                        continue
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Datenbaustein", *group_path, db.Name, "Member", name),
                            description=f"DB-Variable '{name}' wird im gesamten Programm nicht verwendet.",
                            value=name,
                        )
                    )
        return results


class UnbenutzteBausteineCheck(BaseCheck):
    """Prüfpunkt 11b: FBs/FCs/DBs, die von keiner Stelle aufgerufen/referenziert werden.

    ``cross_reference_locations`` direkt am Baustein (OB/FB/FC/DB sind
    bestätigt unterstützte Objekttypen) — leer bedeutet unbenutzt. OBs werden
    ausgenommen, da sie als Einstiegspunkte vom Betriebssystem und nicht von
    anderem Anwendercode aufgerufen werden.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import OB

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if isinstance(block, OB):
                    continue
                if not cross_reference_locations(block):
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=f"Baustein '{block.Name}' wird von keiner Stelle im Projekt referenziert.",
                            value=block.Name,
                        )
                    )
        return results


class EingaengeGelesenCheck(BaseCheck):
    """Prüfpunkt 12: Eingangs-Tags, die im Programm nie gelesen werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != "I":
                        continue
                    locations = cross_reference_locations(tag)
                    has_read = any(getattr(loc, "Access", None) == Access.Read for loc in locations)
                    if not has_read:
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Eingang '{tag.Name}' wird im Programm nie gelesen.",
                                value=tag.Name,
                            )
                        )
        return results


class EingaengeNichtBeschriebenCheck(BaseCheck):
    """Prüfpunkt 12b: Eingangs-Tags dürfen im Programm nicht beschrieben werden.

    Ergänzung zu Prüfpunkt 12 (liest nur, ob ein Eingang gelesen wird) — war
    in der ursprünglichen Prüfpunkte-Liste kein eigener Punkt, ist aber eine
    der grundlegendsten SPS-Programmierregeln: Eingänge werden jeden Zyklus
    vom Prozessabbild aus der Hardware überschrieben, ein Schreibzugriff aus
    dem Anwenderprogramm wird beim nächsten Zyklus also ohnehin wieder
    verworfen — er täuscht daher bestenfalls einen Wert vor, der real nie
    ankommt, und deutet meist auf eine Verwechslung mit einem Merker hin.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != "I":
                        continue
                    locations = cross_reference_locations(tag)
                    write_count = sum(1 for loc in locations if getattr(loc, "Access", None) == Access.Write)
                    if write_count > 0:
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=(
                                    f"Eingang '{tag.Name}' wird im Programm an {write_count} Stelle(n) "
                                    "beschrieben — Eingänge dürfen nicht beschrieben werden."
                                ),
                                value=str(write_count),
                            )
                        )
        return results


class AusgaengeMehrfachSchreibenCheck(BaseCheck):
    """Prüfpunkt 13: Ausgangs-Tags, die an mehreren Stellen beschrieben werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software, self.excluded_folders):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != "Q":
                        continue
                    locations = cross_reference_locations(tag)
                    write_count = sum(1 for loc in locations if getattr(loc, "Access", None) == Access.Write)
                    if write_count > 1:
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Ausgang '{tag.Name}' wird an {write_count} Stellen beschrieben.",
                                value=str(write_count),
                            )
                        )
        return results


class AwlCodeCheck(BaseCheck):
    """Prüfpunkt 14: Bausteine, die noch in AWL/STL programmiert sind."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if get_attribute(block, "ProgrammingLanguage") == "STL":
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=f"Baustein '{block.Name}' ist in AWL (STL) programmiert.",
                        )
                    )
        return results


class GemischteSprachenCheck(BaseCheck):
    """Prüfpunkt 15: Innerhalb eines Bausteins werden mehrere Sprachen gemischt."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if get_attribute(block, "ProgrammingLanguage") in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                languages = {
                    compile_unit_attribute(cu, "ProgrammingLanguage")
                    for cu in iter_compile_units(xml_root)
                }
                languages.discard(None)
                if len(languages) > 1:
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, block.Name),
                            description=f"Baustein '{block.Name}' mischt mehrere Sprachen: {', '.join(sorted(languages))}.",
                            value=", ".join(sorted(languages)),
                        )
                    )
        return results


class MaxNetzwerkElementeCheck(BaseCheck):
    """Prüfpunkt 16: Netzwerke mit mehr Elementen als der Schwellenwert."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        max_elements = int(self.definition.params.get("max_elemente", 50))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software, self.excluded_folders, self.excluded_blocks):
                if get_attribute(block, "ProgrammingLanguage") in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
                    count = compile_unit_element_count(compile_unit)
                    if count > max_elements:
                        results.append(
                            self._make_result(
                                path=format_path(
                                    plc_software.Name, "Programmbausteine", *group_path, block.Name, f"Netzwerk {index}"
                                ),
                                description=f"Netzwerk hat {count} Elemente (Schwellenwert: {max_elements}).",
                                value=str(count),
                            )
                        )
        return results


CHECK_CLASSES = {
    "programmstruktur.leere_netzwerke": LeereNetzwerkeCheck,
    "programmstruktur.unbenutzte_variablen": UnbenutzteVariablenCheck,
    "programmstruktur.unbenutzte_bausteine": UnbenutzteBausteineCheck,
    "programmstruktur.eingaenge_gelesen": EingaengeGelesenCheck,
    "programmstruktur.eingaenge_nicht_beschrieben": EingaengeNichtBeschriebenCheck,
    "programmstruktur.ausgaenge_mehrfach_schreiben": AusgaengeMehrfachSchreibenCheck,
    "programmstruktur.awl_code": AwlCodeCheck,
    "programmstruktur.gemischte_sprachen": GemischteSprachenCheck,
    "programmstruktur.max_netzwerk_elemente": MaxNetzwerkElementeCheck,
}
