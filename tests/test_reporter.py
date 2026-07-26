"""Tests für ``PdfReporter.generate``/``report_filename``/
``sanitize_filename_part`` (Review-Security-Robustheit.md, Befund 1.3/1.5).

``reporter.py`` hatte bislang keine dedizierten Tests -- diese decken
gezielt die geänderte Datei-vs-Ordner-Entscheidung in ``generate()`` ab,
nicht die volle PDF-Erzeugung im Detail (ReportLab selbst wird nicht
gemockt, ein echtes PDF wird tatsächlich geschrieben).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from tia_linter.config import AppConfig
from tia_linter.models import CheckResult, CheckStatus, LintReport
from tia_linter.reporter import PdfReporter, report_filename, sanitize_filename_part

_APP_CONFIG = {
    "tia_versionen": {
        "verfuegbar": [{"name": "V21", "version": 21, "dll_pfad": "x.dll"}],
        "standard": "V21",
    },
    "checks": {
        "namenskonventionen": {
            "testvariablen": {"enabled": True, "severity": "warning", "prefixe": ["TEST_"]},
        },
    },
}


def _report() -> LintReport:
    return LintReport(
        project_name="Testprojekt",
        project_path="/irgendwo/Testprojekt.ap21",
        tia_version="V21",
        check_date=datetime(2026, 7, 26, 12, 0),
        checker_name="Tester",
        results=[
            CheckResult(
                check_id="namenskonventionen.testvariablen",
                check_name="Testvariablen",
                category="Namenskonventionen",
                status=CheckStatus.OK,
                path="Testprojekt",
                description="Keine Verstöße.",
                recommendation="Kein Handlungsbedarf.",
            )
        ],
    )


class TestSanitizeFilenamePart:
    def test_leaves_safe_characters_untouched(self) -> None:
        assert sanitize_filename_part("Salzmaschine-01_Test") == "Salzmaschine-01_Test"

    def test_replaces_unsafe_characters(self) -> None:
        assert sanitize_filename_part('PLC:\\/Projekt "X"') == "PLC___Projekt__X_"


class TestReportFilename:
    def test_uses_sanitized_project_name_and_timestamp(self) -> None:
        name = report_filename(_report())
        assert name == "Lintreport_Testprojekt_2026-07-26_12-00.pdf"


class TestPdfReporterGenerate:
    def test_nonexistent_output_folder_is_created_and_filename_generated(self, tmp_path: Path) -> None:
        # Review-Security-Robustheit.md, Befund 1.3: vorher wurde ein noch
        # nicht existierender Ordner als Dateiname missverstanden.
        output_folder = tmp_path / "nicht_existent" / "unterordner"
        result_path = PdfReporter(AppConfig.model_validate(_APP_CONFIG)).generate(_report(), output_folder)

        assert result_path.parent == output_folder
        assert result_path.suffix == ".pdf"
        assert result_path.name == "Lintreport_Testprojekt_2026-07-26_12-00.pdf"
        assert result_path.is_file()

    def test_existing_output_folder_still_works(self, tmp_path: Path) -> None:
        result_path = PdfReporter(AppConfig.model_validate(_APP_CONFIG)).generate(_report(), tmp_path)

        assert result_path.parent == tmp_path
        assert result_path.is_file()

    def test_explicit_pdf_path_is_used_as_is(self, tmp_path: Path) -> None:
        explicit_target = tmp_path / "unterordner" / "mein_report.pdf"
        result_path = PdfReporter(AppConfig.model_validate(_APP_CONFIG)).generate(_report(), explicit_target)

        assert result_path == explicit_target
        assert result_path.is_file()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
