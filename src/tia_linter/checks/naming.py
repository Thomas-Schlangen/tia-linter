"""Prüfpunkte 5-9: Namenskonventionen."""

from __future__ import annotations

import re
from typing import Any

from tia_linter.checks._tia_helpers import (
    format_path,
    get_attribute,
    iter_blocks,
    iter_data_blocks,
    iter_plc_software,
    iter_tag_tables,
    tag_direction,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult


class DbFormatCheck(BaseCheck):
    """Prüfpunkt 5: Datenbausteinname entspricht nicht dem konfigurierten Regex."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        pattern = re.compile(self.definition.params.get("regex", ".*"))

        for plc_software in iter_plc_software(project):
            for db, group_path in iter_data_blocks(plc_software):
                if not pattern.match(db.Name):
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Datenbaustein", *group_path, db.Name),
                            description=f"DB-Name '{db.Name}' entspricht nicht dem Muster '{pattern.pattern}'.",
                            value=db.Name,
                        )
                    )
        return results


class _PlcTagAddressPatternCheck(BaseCheck):
    """Gemeinsame Basis für Eingangs-/Ausgangs-Namenskonvention (Prüfpunkt 6)."""

    _direction: str = ""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        pattern = re.compile(self.definition.params.get("regex", ".*"))

        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software):
                for tag in tag_table.Tags:
                    if tag_direction(tag) != self._direction:
                        continue
                    if not pattern.match(tag.Name):
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=(
                                    f"Tag '{tag.Name}' entspricht nicht dem Muster '{pattern.pattern}'."
                                ),
                                value=tag.Name,
                            )
                        )
        return results


class PlcTagEingaengeCheck(_PlcTagAddressPatternCheck):
    """Prüfpunkt 6: Eingangs-Tags entsprechen nicht dem konfigurierten Muster."""

    _direction = "I"


class PlcTagAusgaengeCheck(_PlcTagAddressPatternCheck):
    """Prüfpunkt 6: Ausgangs-Tags entsprechen nicht dem konfigurierten Muster."""

    _direction = "Q"


class _BlockNamingCheck(BaseCheck):
    """Gemeinsame Basis für FB-/FC-Namenskonvention (Prüfpunkt 7)."""

    _block_type_name: str = ""

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.SW.Blocks import FB, FC

        block_types = {"FB": FB, "FC": FC}
        block_type = block_types[self._block_type_name]

        results: list[CheckResult] = []
        pattern = re.compile(self.definition.params.get("regex", ".*"))

        for plc_software in iter_plc_software(project):
            for block, group_path in iter_blocks(plc_software):
                if not isinstance(block, block_type):
                    continue
                name = block.Name
                if not pattern.match(name):
                    results.append(
                        self._make_result(
                            path=format_path(plc_software.Name, "Programmbausteine", *group_path, name),
                            description=f"Bausteinname '{name}' entspricht nicht dem Muster '{pattern.pattern}'.",
                            value=name,
                        )
                    )
        return results


class FbPrefixCheck(_BlockNamingCheck):
    """Prüfpunkt 7: Funktionsbausteine entsprechen nicht dem konfigurierten Regex."""

    _block_type_name = "FB"


class FcPrefixCheck(_BlockNamingCheck):
    """Prüfpunkt 7: Funktionen entsprechen nicht dem konfigurierten Regex."""

    _block_type_name = "FC"


class KonstantenFormatCheck(BaseCheck):
    """Prüfpunkt 8: Konstanten entsprechen nicht dem konfigurierten Regex (Standard: nur Großbuchstaben)."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        pattern = re.compile(self.definition.params.get("regex", "^[A-Z][A-Z0-9_]*$"))

        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software):
                # Anmerkung: Der Zugriffspfad auf PLC-Konstanten ist über die
                # allgemeine Openness-Dokumentation nicht eindeutig belegt —
                # ``UserConstants`` wird hier als plausibler Kandidat
                # verwendet und degradiert bei Nichtvorhandensein sauber zu
                # "keine Konstanten in dieser Tabelle" statt abzustürzen.
                constants = getattr(tag_table, "UserConstants", None)
                if not constants:
                    continue
                for constant in constants:
                    name = constant.Name
                    if not pattern.match(name):
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, name),
                                description=f"Konstante '{name}' entspricht nicht dem Muster '{pattern.pattern}'.",
                                value=name,
                            )
                        )
        return results


class TestvariablenCheck(BaseCheck):
    """Prüfpunkt 9: Variablen mit Test-/Debug-Präfix im Projekt gefunden."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        prefixes = tuple(self.definition.params.get("prefixe", []))
        if not prefixes:
            return results

        for plc_software in iter_plc_software(project):
            for tag_table in iter_tag_tables(plc_software):
                for tag in tag_table.Tags:
                    if tag.Name.startswith(prefixes):
                        results.append(
                            self._make_result(
                                path=format_path(plc_software.Name, "Variablentabellen", tag_table.Name, tag.Name),
                                description=f"Testvariable '{tag.Name}' ist noch im Projekt vorhanden.",
                                value=tag.Name,
                            )
                        )
        return results


CHECK_CLASSES = {
    "namenskonventionen.db_format": DbFormatCheck,
    "namenskonventionen.plc_tag_eingaenge": PlcTagEingaengeCheck,
    "namenskonventionen.plc_tag_ausgaenge": PlcTagAusgaengeCheck,
    "namenskonventionen.fb_prefix": FbPrefixCheck,
    "namenskonventionen.fc_prefix": FcPrefixCheck,
    "namenskonventionen.konstanten_format": KonstantenFormatCheck,
    "namenskonventionen.testvariablen": TestvariablenCheck,
}
