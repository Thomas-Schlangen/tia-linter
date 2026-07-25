"""Datenklassen für Prüfpunkte, Befunde und den Gesamtbericht."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class CheckStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class CheckSeverity(Enum):
    WARNING = "warning"
    ERROR = "error"

    def as_status(self) -> CheckStatus:
        """Wandelt den konfigurierten Standard-Schweregrad eines Befunds in
        den entsprechenden CheckStatus um (bei Verstoß gegen den Prüfpunkt)."""
        return CheckStatus.ERROR if self is CheckSeverity.ERROR else CheckStatus.WARNING


@dataclass
class CheckDefinition:
    """Definition eines Prüfpunkts — kommt aus der YAML-Config."""

    check_id: str
    name: str
    category: str
    enabled: bool
    severity: CheckSeverity
    description: str
    recommendation: str
    nummer: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Ergebnis eines einzelnen Prüfpunkt-Befunds."""

    check_id: str
    check_name: str
    category: str
    status: CheckStatus
    path: str
    description: str
    recommendation: str
    value: str | None = None


@dataclass
class LintReport:
    """Gesamtergebnis einer Prüfung."""

    project_name: str
    project_path: str
    tia_version: str
    check_date: datetime
    checker_name: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.ERROR)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.WARNING)

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.OK)

    def results_by_category(self) -> dict[str, list[CheckResult]]:
        """Gruppiert die Befunde nach Kategorie, in Erstauftritts-Reihenfolge."""
        grouped: dict[str, list[CheckResult]] = {}
        for result in self.results:
            grouped.setdefault(result.category, []).append(result)
        return grouped
