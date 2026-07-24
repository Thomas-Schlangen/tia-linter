"""Prüfpunkte 19-21: Projektmetadaten."""

from __future__ import annotations

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
    User-Auftrag): Liste von **literalen Teiltexten** (kein Regex!), auf die
    der Meldungstext case-insensitiv geprüft wird — ein Treffer unterdrückt
    die Meldung vollständig, unabhängig von Baustein oder Fehler-/
    Warnungsstatus. Bewusst kein Regex (anders als sonst in diesem Projekt
    bei ähnlichen Ausnahme-Parametern üblich, siehe z. B.
    ``ausnahme_titel_regex`` bei Prüfpunkt 10): Zweiunddreißigster Bug,
    live gefunden — reale Compiler-Meldungen enthalten sehr häufig
    Klammern/Anführungszeichen (z. B. "(Project > Properties >
    Protection)"), die als Regex-Metazeichen (Gruppierung) interpretiert
    würden statt als literale Zeichen und den Abgleich dadurch stillschweigend
    zum Scheitern bringen — sogar ein Muster gegen sich selbst als Text
    liefert dann keinen Treffer. Da der praktische Anwendungsfall ("genau
    diese eine bekannte Meldung dauerhaft unterdrücken") ohnehin nie
    Wildcards braucht, ist reiner Teiltext-Abgleich hier robuster als Regex.
    Gedacht für Compiler-Meldungen, die der Nutzer bewusst als irrelevant
    einstuft (z. B. "since it is write-protected"/"because it is not
    editable" bei schreibgeschützten Bausteinen aus zugekauften
    Bibliotheken) — bei Unsicherheit gilt weiterhin: lieber den Entwickler
    kontaktieren, statt eine Meldung hier pauschal zu unterdrücken.
    """

    def run(self, project: Any) -> list[CheckResult]:
        from Siemens.Engineering.Compiler import ICompilable

        results: list[CheckResult] = []
        ignored_substrings = [
            text.casefold() for text in self.definition.params.get("ignorierte_meldungen", [])
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
                folded_description = description.casefold()
                if any(text in folded_description for text in ignored_substrings):
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


CHECK_CLASSES = {
    "projektmetadaten.pflichtfelder": PflichtfelderCheck,
    "projektmetadaten.max_sprachen": MaxSprachenCheck,
    "projektmetadaten.kompilierfehler": KompilierfehlerCheck,
}
