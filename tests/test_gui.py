"""Tests für ``TiaLinterApp._validate_inputs`` (Review-Security-Robustheit.md,
Befund 1.1/1.2).

``gui.py`` hatte bislang keine dedizierten Tests (nur eine manuelle
Live-Instanziierung als Smoketest, siehe review_fortschritt.md Runde 16) --
``_validate_inputs`` ist aber reine Pfad-/Berechtigungslogik plus
``messagebox``-Aufrufe und lässt sich mit einem echten (aber ausgeblendeten)
``Tk``-Root und gemockten ``messagebox``-Funktionen automatisiert prüfen, ohne
dass echte Dialoge aufpoppen oder auf Benutzereingaben warten.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tia_linter import gui as gui_module
from tia_linter.config import AppConfig
from tia_linter.gui import TiaLinterApp
from tia_linter.settings import Settings

pytest.importorskip("tkinter")

_BASE_CONFIG = {
    "tia_versionen": {
        "verfuegbar": [{"name": "V21", "version": 21, "dll_pfad": "x.dll"}],
        "standard": "V21",
    },
    "checks": {
        "namenskonventionen": {
            "testvariablen": {"enabled": False, "severity": "warning", "prefixe": ["TEST_"]},
        },
    },
}


def _noop_run_lint(**_kwargs: object) -> None:
    return None


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TiaLinterApp:
    """Liefert eine echte, aber sofort ausgeblendete ``TiaLinterApp`` --
    ``withdraw()`` verhindert, dass beim Testlauf ein sichtbares Fenster
    aufpoppt. Wird nach jedem Test wieder zerstört."""
    try:
        config = AppConfig.model_validate(_BASE_CONFIG)
        instance = TiaLinterApp(config, tmp_path / "config.yaml", Settings(), _noop_run_lint, _noop_run_lint)
    except Exception as exc:  # noqa: BLE001 — kein Display/Tk in dieser Umgebung verfügbar
        pytest.skip(f"Tk-GUI konnte nicht erzeugt werden: {exc}")
    instance.withdraw()
    yield instance
    instance.destroy()


def _set_inputs(app: TiaLinterApp, project_path: str, output_folder: str) -> None:
    app.main_page.project_path.set(project_path)
    app.main_page.output_folder.set(output_folder)


class TestValidateInputsProjectPath:
    def test_empty_project_path_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        _set_inputs(app, "", str(tmp_path))

        assert app._validate_inputs() is False
        showerror.assert_called_once()

    def test_nonexistent_project_file_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        _set_inputs(app, str(tmp_path / "nicht_vorhanden.ap21"), str(tmp_path))

        assert app._validate_inputs() is False
        showerror.assert_called_once()
        assert "nicht gefunden" in showerror.call_args[0][1]

    def test_wrong_extension_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_file = tmp_path / "projekt.txt"
        project_file.write_text("dummy")
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        _set_inputs(app, str(project_file), str(tmp_path))

        assert app._validate_inputs() is False
        showerror.assert_called_once()
        assert "TIA-Portal-Projektdatei" in showerror.call_args[0][1]

    def test_valid_ap_extension_is_accepted(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_file = tmp_path / "projekt.ap21"
        project_file.write_text("dummy")
        monkeypatch.setattr(gui_module.messagebox, "showerror", MagicMock())
        monkeypatch.setattr(app.main_page, "collect_enabled_definitions", lambda: ["dummy"])
        _set_inputs(app, str(project_file), str(tmp_path))

        assert app._validate_inputs() is True


class TestValidateInputsOutputFolder:
    def _valid_project(self, tmp_path: Path) -> Path:
        project_file = tmp_path / "projekt.ap21"
        project_file.write_text("dummy")
        return project_file

    def test_empty_output_folder_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        _set_inputs(app, str(self._valid_project(tmp_path)), "")

        assert app._validate_inputs() is False
        showerror.assert_called_once()

    def test_missing_output_folder_offers_creation_and_creates_on_yes(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing_folder = tmp_path / "neuer_ordner"
        monkeypatch.setattr(gui_module.messagebox, "askyesno", MagicMock(return_value=True))
        monkeypatch.setattr(app.main_page, "collect_enabled_definitions", lambda: ["dummy"])
        _set_inputs(app, str(self._valid_project(tmp_path)), str(missing_folder))

        assert app._validate_inputs() is True
        assert missing_folder.is_dir()

    def test_missing_output_folder_not_created_on_no(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing_folder = tmp_path / "neuer_ordner"
        monkeypatch.setattr(gui_module.messagebox, "askyesno", MagicMock(return_value=False))
        _set_inputs(app, str(self._valid_project(tmp_path)), str(missing_folder))

        assert app._validate_inputs() is False
        assert not missing_folder.exists()

    def test_output_path_that_is_a_file_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_as_file = tmp_path / "ich_bin_eine_datei"
        output_as_file.write_text("dummy")
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        _set_inputs(app, str(self._valid_project(tmp_path)), str(output_as_file))

        assert app._validate_inputs() is False
        showerror.assert_called_once()
        assert "kein Ordner" in showerror.call_args[0][1]

    def test_non_writable_output_folder_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        monkeypatch.setattr(gui_module.os, "access", lambda *_args, **_kwargs: False)
        _set_inputs(app, str(self._valid_project(tmp_path)), str(tmp_path))

        assert app._validate_inputs() is False
        showerror.assert_called_once()
        assert "Schreibrecht" in showerror.call_args[0][1]


class TestValidateInputsCheckSelection:
    def test_no_enabled_checks_is_rejected(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_file = tmp_path / "projekt.ap21"
        project_file.write_text("dummy")
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        monkeypatch.setattr(app.main_page, "collect_enabled_definitions", lambda: [])
        _set_inputs(app, str(project_file), str(tmp_path))

        assert app._validate_inputs() is False
        showerror.assert_called_once()
        assert "Prüfpunkt" in showerror.call_args[0][1]


class TestSetupRunLoggerFailureShowsDialog:
    def test_logger_setup_error_is_caught_and_shown(
        self, app: TiaLinterApp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from my_logger import LoggerSetupError

        project_file = tmp_path / "projekt.ap21"
        project_file.write_text("dummy")
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        monkeypatch.setattr(app.main_page, "collect_enabled_definitions", lambda: ["dummy"])
        monkeypatch.setattr(
            app,
            "_setup_run_logger",
            MagicMock(side_effect=LoggerSetupError("Logdatei konnte nicht geöffnet werden")),
        )
        _set_inputs(app, str(project_file), str(tmp_path))

        app.start_lint_run()

        showerror.assert_called_once()
        assert "Log-Datei" in showerror.call_args[0][1]
        assert app._lint_thread is None


class TestGeneratePdfReportCatchesAllExceptions:
    """Review-Security-Robustheit.md, Befund 1.4: ``generate_pdf_report``
    fing bislang nur ``OSError`` — ReportLab-eigene Fehler (z. B.
    ``LayoutError`` bei einer zu breiten Tabellenzelle) liefen als roher
    Traceback im Tk-Callback statt als Meldung."""

    def test_non_oserror_from_pdf_generation_is_caught_and_shown(
        self, app: TiaLinterApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tia_linter.models import CheckStatus, LintReport
        from datetime import datetime

        app._report = LintReport(
            project_name="Test",
            project_path="x.ap21",
            tia_version="V21",
            check_date=datetime(2026, 7, 26),
            checker_name="Tester",
            results=[],
        )
        showerror = MagicMock()
        monkeypatch.setattr(gui_module.messagebox, "showerror", showerror)
        monkeypatch.setattr(
            gui_module.PdfReporter,
            "generate",
            MagicMock(side_effect=ValueError("ReportLab-Layoutfehler (simuliert)")),
        )

        app.generate_pdf_report()

        showerror.assert_called_once()
        assert "PDF-Report" in showerror.call_args[0][1]


class TestCollectEnabledDefinitionsReflectsCheckboxState:
    """Review-General.md, Befund 1: ein in der Config auf ``enabled: false``
    stehender Prüfpunkt musste trotz angehaktem Kästchen als ``enabled=False``
    zurückkommen — ``run_lint``/``simulate_lint_run`` filtern selbst noch
    einmal danach und führten ihn dadurch nie aus."""

    def test_checked_definition_disabled_in_config_is_returned_as_enabled(
        self, app: TiaLinterApp
    ) -> None:
        check_id = next(iter(app.definitions)).check_id
        assert app.definitions[0].enabled is False

        app.main_page._check_vars[check_id].set(True)
        result = app.main_page.collect_enabled_definitions()

        assert len(result) == 1
        assert result[0].check_id == check_id
        assert result[0].enabled is True

    def test_unchecked_definition_is_not_returned(self, app: TiaLinterApp) -> None:
        check_id = next(iter(app.definitions)).check_id
        app.main_page._check_vars[check_id].set(False)

        assert app.main_page.collect_enabled_definitions() == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
