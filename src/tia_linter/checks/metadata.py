"""Prüfpunkte 19-22: Projektmetadaten."""

from __future__ import annotations

import re
from typing import Any

from tia_linter.checks._tia_helpers import (
    format_path,
    get_attribute,
    iter_plc_software,
    read_comment,
    reference_language,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult, CheckStatus

# Attribut, das als Siemens.Engineering.MultilingualText geliefert wird statt
# als System.String (siehe Openness-Referenz, Abschnitt "Projektbezogene
# Attribute lesen") — GetAttribute("Comment") liefert dafür sogar direkt
# None statt des Objekts, ein generischer str(get_attribute(...))-Zugriff
# hätte das Feld also immer als leer gemeldet, unabhängig vom tatsächlichen
# Inhalt (dieselbe Klasse von Bug wie beim mehrfach behobenen
# Comment-Attribut auf PlcBlock/PlcTag).
_MULTILINGUAL_FIELDS = {"Comment"}


class PflichtfelderCheck(BaseCheck):
    """Prüfpunkt 19: Pflichtfelder in den Top-Level-Projekteigenschaften."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for field in self.definition.params.get("felder", []):
            if field in _MULTILINGUAL_FIELDS:
                value = read_comment(project, reference_language(project))
            else:
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
    """Prüfpunkt 21: Kompilierfehler und -warnungen je PLC-Software.

    Übersetzt wird über den ``ICompilable``-Dienst, nicht über eine direkte
    ``Compile()``-Methode auf der PLC-Software — bestätigt durch die V21-
    Openness-Referenz (Manual 03/2026, Namespace ``Siemens.Engineering.Compiler``):
    ``plcSoftware.GetService<ICompilable>().Compile()``. Voraussetzung laut
    Referenz: alle Geräte müssen vor dem Start der Übersetzung offline sein.

    ``CompilerResultMessage`` hat laut Referenz **kein** ``Severity``-Feld,
    sondern rekursiv verschachtelte ``Messages`` mit je eigenem
    ``ErrorCount``/``WarningCount`` (analog zu ``UpdateCheckResultMessage`` in
    ``libraries.py``) — Blattmeldungen mit ``ErrorCount > 0`` werden als
    Fehler eingestuft, alle übrigen als Warnung.

    Neuer Parameter ``ignorierte_meldungen`` (Standard ``[]`` = deaktiviert,
    User-Auftrag): Liste von Regex-Mustern, auf die der Meldungstext geprüft
    wird (``re.search``, nicht ``re.match`` wie sonst bei Regex-Parametern
    in diesem Projekt üblich — hier soll ein Muster irgendwo im oft langen,
    freien Meldungstext treffen dürfen, nicht nur am Anfang). Ein Treffer
    unterdrückt die Meldung vollständig, unabhängig von Baustein oder
    Fehler-/Warnungsstatus. Gedacht für Compiler-Meldungen, die der Nutzer
    bewusst als irrelevant einstuft (z. B. "since it is write-protected"/
    "because it is not editable" bei schreibgeschützten Bausteinen aus
    zugekauften Bibliotheken) — bei Unsicherheit gilt weiterhin: lieber den
    Entwickler kontaktieren, statt eine Meldung hier pauschal zu
    unterdrücken.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.Compiler import ICompilable

        results: list[CheckResult] = []
        ignored_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.definition.params.get("ignorierte_meldungen", [])
        ]

        for plc_software in iter_plc_software(project):
            try:
                compile_service = plc_software.GetService[ICompilable]()
                compile_result = compile_service.Compile()
            except Exception as exc:  # noqa: BLE001 — .NET-Exception beim Übersetzen
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name),
                        description=f"Übersetzen fehlgeschlagen: {exc}",
                        status=CheckStatus.ERROR,
                    )
                )
                continue

            for message in _leaf_compiler_messages(getattr(compile_result, "Messages", [])):
                description = str(getattr(message, "Description", "Compiler-Meldung"))
                if any(pattern.search(description) for pattern in ignored_patterns):
                    continue
                error_count = int(getattr(message, "ErrorCount", 0) or 0)
                status = CheckStatus.ERROR if error_count > 0 else CheckStatus.WARNING
                path_hint = str(getattr(message, "Path", "") or "")
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Compiler-Meldung", path_hint),
                        description=description,
                        status=status,
                    )
                )
        return results


def _leaf_compiler_messages(messages: Any) -> list[Any]:
    leaves = []
    for message in messages or []:
        children = list(getattr(message, "Messages", []) or [])
        if children:
            leaves.extend(_leaf_compiler_messages(children))
        else:
            leaves.append(message)
    return leaves


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
