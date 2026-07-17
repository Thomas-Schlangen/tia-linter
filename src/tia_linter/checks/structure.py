"""Prüfpunkte 10-16: Programmstruktur.

Prüfpunkte 11-13 (Kreuzreferenz-basiert) nutzen den ``CrossReferenceService``
(siehe Openness-API-Referenz-fuer-Linter.md) — die exakte Objekt-Scope
(Baustein/PLC-Software/Projekt), auf der der Service abgerufen werden muss,
ist in der allgemeinen Referenzdokumentation nicht abschließend belegt; hier
wird er auf PLC-Software- bzw. Tag-Ebene verwendet (plausibelste Variante,
nicht gegen ein echtes Projekt verifiziert).
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
    iter_plc_software,
    iter_tag_tables,
    tag_direction,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult


class LeereNetzwerkeCheck(BaseCheck):
    """Prüfpunkt 10: Netzwerke ohne Inhalt (keine Programmelemente)."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software):
                if get_attribute(block, "ProgrammingLanguage") in ("SCL", "STL"):
                    continue
                xml_root = export_block_xml(block)
                for index, compile_unit in enumerate(iter_compile_units(xml_root), start=1):
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
    """Prüfpunkt 11: PLC-Tags/DB-Variablen ohne jegliche Referenz im Programm."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            service = plc_software.GetService[CrossReferenceService]()
            if service is None:
                continue
            cross_ref = service.GetCrossReferences(CrossReferenceFilter.UnusedObjects)
            for source in getattr(cross_ref, "Sources", []) or []:
                type_name = str(getattr(source, "TypeName", "") or "")
                if "Tag" not in type_name and "Member" not in type_name:
                    continue
                name = getattr(source, "Name", "?")
                path = getattr(source, "Path", "") or name
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, path),
                        description=f"Variable '{name}' wird im gesamten Programm nicht verwendet.",
                        value=name,
                    )
                )
        return results


class UnbenutzteBausteineCheck(BaseCheck):
    """Prüfpunkt 11b: FBs/FCs/DBs, die von keiner Stelle aufgerufen/referenziert werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import CrossReferenceFilter, CrossReferenceService

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            service = plc_software.GetService[CrossReferenceService]()
            if service is None:
                continue
            cross_ref = service.GetCrossReferences(CrossReferenceFilter.UnusedObjects)
            for source in getattr(cross_ref, "Sources", []) or []:
                type_name = str(getattr(source, "TypeName", "") or "")
                if not any(keyword in type_name for keyword in ("Block", "FunctionBlock", "Function", "DataBlock")):
                    continue
                name = getattr(source, "Name", "?")
                path = getattr(source, "Path", "") or name
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Programmbausteine", path),
                        description=f"Baustein '{name}' wird von keiner Stelle im Projekt referenziert.",
                        value=name,
                    )
                )
        return results


class EingaengeGelesenCheck(BaseCheck):
    """Prüfpunkt 12: Eingangs-Tags, die im Programm nie gelesen werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software):
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


class AusgaengeMehrfachSchreibenCheck(BaseCheck):
    """Prüfpunkt 13: Ausgangs-Tags, die an mehreren Stellen beschrieben werden."""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.CrossReference import Access

        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software):
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
            for block, group_path in iter_blocks(plc_software):
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
            for block, group_path in iter_blocks(plc_software):
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
            for block, group_path in iter_blocks(plc_software):
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
    "programmstruktur.ausgaenge_mehrfach_schreiben": AusgaengeMehrfachSchreibenCheck,
    "programmstruktur.awl_code": AwlCodeCheck,
    "programmstruktur.gemischte_sprachen": GemischteSprachenCheck,
    "programmstruktur.max_netzwerk_elemente": MaxNetzwerkElementeCheck,
}
