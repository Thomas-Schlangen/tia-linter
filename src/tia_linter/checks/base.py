"""Abstrakte Basisklasse für alle Prüfpunkt-Checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tia_linter.models import CheckDefinition, CheckResult, CheckStatus


class BaseCheck(ABC):
    """Ein Check kapselt die Prüflogik für genau einen Prüfpunkt.

    ``definition`` liefert die Konfiguration (enabled, severity, Parameter)
    aus der YAML-Config; ``run`` erhält das geöffnete TIA-Openness-Projekt
    und liefert eine Liste von Befunden (leer, wenn alles in Ordnung ist).
    """

    def __init__(self, definition: CheckDefinition) -> None:
        self.definition = definition

    @abstractmethod
    def run(self, project: Any) -> list[CheckResult]:
        """Führt den Prüfpunkt aus. ``project`` = TIA Openness Project-Objekt."""
        ...

    def _make_result(
        self,
        path: str,
        description: str,
        status: CheckStatus | None = None,
        value: str | None = None,
    ) -> CheckResult:
        """Baut ein CheckResult für einen Verstoß gegen diesen Prüfpunkt.

        ``status`` ist optional — ohne Angabe wird der in der Config
        hinterlegte Standard-Schweregrad (``definition.severity``) verwendet.
        """
        return CheckResult(
            check_id=self.definition.check_id,
            check_name=self.definition.name,
            category=self.definition.category,
            status=status or self.definition.severity.as_status(),
            path=path,
            description=description,
            recommendation=self.definition.recommendation,
            value=value,
        )
