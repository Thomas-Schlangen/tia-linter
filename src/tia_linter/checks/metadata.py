"""Prüfpunkte 19-22: Projektmetadaten."""

from __future__ import annotations

from typing import Any

from tia_linter.checks._tia_helpers import format_path, get_attribute, iter_plc_software
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult, CheckStatus


class PflichtfelderCheck(BaseCheck):
    """Prüfpunkt 19: Pflichtfelder in den Top-Level-Projekteigenschaften."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for field in self.definition.params.get("felder", []):
            value = str(get_attribute(project, field, "") or "").strip()
            if not value:
                results.append(
                    self._make_result(
                        path=format_path("Projekt", "Eigenschaften", field),
                        description=f"Pflichtfeld '{field}' ist nicht ausgefüllt.",
                    )
                )
        return results


class MaxSprachenCheck(BaseCheck):
    """Prüfpunkt 20: Mehr aktive Sprachen als konfiguriertes Maximum."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        max_languages = int(self.definition.params.get("max", 2))
        active_languages = list(project.LanguageSettings.ActiveLanguages)
        if len(active_languages) > max_languages:
            names = ", ".join(str(get_attribute(lang, "Name", lang)) for lang in active_languages)
            results.append(
                self._make_result(
                    path=format_path("Projekt", "Eigenschaften", "Sprachen"),
                    description=(
                        f"{len(active_languages)} aktive Sprachen konfiguriert "
                        f"(Schwellenwert: {max_languages}): {names}."
                    ),
                    value=str(len(active_languages)),
                )
            )
        return results


class KompilierfehlerCheck(BaseCheck):
    """Prüfpunkt 21: Kompilierfehler und -warnungen je PLC-Software."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software in iter_plc_software(project):
            try:
                compile_result = plc_software.Compile()
            except Exception as exc:  # noqa: BLE001 — .NET-Exception beim Übersetzen
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name),
                        description=f"Übersetzen fehlgeschlagen: {exc}",
                        status=CheckStatus.ERROR,
                    )
                )
                continue

            for message in getattr(compile_result, "Messages", []) or []:
                description = str(getattr(message, "Description", message))
                severity = str(getattr(message, "Severity", "")).lower()
                status = CheckStatus.ERROR if "error" in severity else CheckStatus.WARNING
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Compiler-Meldung"),
                        description=description,
                        status=status,
                    )
                )
        return results


class ProjektversionCheck(BaseCheck):
    """Prüfpunkt 22: Projekt hat keine Versionsnummer hinterlegt."""

    def run(self, project: Any) -> list[CheckResult]:
        version = str(get_attribute(project, "Version", "") or "").strip()
        if not version:
            return [
                self._make_result(
                    path=format_path("Projekt", "Eigenschaften", "Version"),
                    description="Projekt hat keine Versionsnummer hinterlegt.",
                )
            ]
        return []


CHECK_CLASSES = {
    "projektmetadaten.pflichtfelder": PflichtfelderCheck,
    "projektmetadaten.max_sprachen": MaxSprachenCheck,
    "projektmetadaten.kompilierfehler": KompilierfehlerCheck,
    "projektmetadaten.projektversion": ProjektversionCheck,
}
