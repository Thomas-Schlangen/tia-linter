"""Tests für die Datenklassen in tia_linter.models."""

from __future__ import annotations

from datetime import datetime

import pytest

from tia_linter.models import (
    CheckDefinition,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    LintReport,
)


def make_result(category: str, status: CheckStatus, check_id: str = "kategorie.check") -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_name="Testprüfpunkt",
        category=category,
        status=status,
        path="PLC_1 > Test",
        description="Testbeschreibung",
        recommendation="Testempfehlung",
    )


class TestCheckSeverity:
    def test_error_severity_maps_to_error_status(self) -> None:
        assert CheckSeverity.ERROR.as_status() is CheckStatus.ERROR

    def test_warning_severity_maps_to_warning_status(self) -> None:
        assert CheckSeverity.WARNING.as_status() is CheckStatus.WARNING


class TestCheckDefinition:
    def test_defaults_to_empty_params(self) -> None:
        definition = CheckDefinition(
            check_id="kommentare.variablen_kommentar",
            name="Variablen ohne Kommentar",
            category="Kommentare & Beschreibungen",
            enabled=True,
            severity=CheckSeverity.WARNING,
            description="...",
            recommendation="...",
            nummer="1a",
        )
        assert definition.params == {}

    def test_accepts_explicit_params(self) -> None:
        definition = CheckDefinition(
            check_id="namenskonventionen.db_format",
            name="DB-Namensformat",
            category="Namenskonventionen",
            enabled=True,
            severity=CheckSeverity.ERROR,
            description="...",
            recommendation="...",
            nummer="5",
            params={"regex": "^DB_"},
        )
        assert definition.params == {"regex": "^DB_"}


class TestLintReport:
    def test_counts_results_by_status(self) -> None:
        report = LintReport(
            project_name="Testprojekt",
            project_path="/tmp/Testprojekt.ap21",
            tia_version="TIA Portal V21",
            check_date=datetime(2026, 1, 1),
            checker_name="Max Mustermann",
            results=[
                make_result("Kommentare", CheckStatus.ERROR),
                make_result("Kommentare", CheckStatus.WARNING),
                make_result("Kommentare", CheckStatus.WARNING),
                make_result("Hardware", CheckStatus.OK),
            ],
        )
        assert report.errors == 1
        assert report.warnings == 2
        assert report.ok_count == 1

    def test_empty_results_have_zero_counts(self) -> None:
        report = LintReport(
            project_name="Testprojekt",
            project_path="/tmp/Testprojekt.ap21",
            tia_version="TIA Portal V21",
            check_date=datetime(2026, 1, 1),
            checker_name="Max Mustermann",
        )
        assert report.errors == 0
        assert report.warnings == 0
        assert report.ok_count == 0
        assert report.results_by_category() == {}

    def test_results_by_category_groups_and_preserves_order(self) -> None:
        report = LintReport(
            project_name="Testprojekt",
            project_path="/tmp/Testprojekt.ap21",
            tia_version="TIA Portal V21",
            check_date=datetime(2026, 1, 1),
            checker_name="Max Mustermann",
            results=[
                make_result("Kommentare", CheckStatus.ERROR),
                make_result("Hardware", CheckStatus.OK),
                make_result("Kommentare", CheckStatus.WARNING),
            ],
        )
        grouped = report.results_by_category()
        assert list(grouped.keys()) == ["Kommentare", "Hardware"]
        assert len(grouped["Kommentare"]) == 2
        assert len(grouped["Hardware"]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
