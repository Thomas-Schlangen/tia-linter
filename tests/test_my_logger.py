"""Tests für ``my_logger.setup_logger`` (Review-Security-Robustheit.md,
Befund 4.5): ein fehlgeschlagener Aufruf (z. B. Logdatei nicht anlegbar)
darf den zuvor konfigurierten Root-Logger nicht ohne jeden Handler
zurücklassen."""

from __future__ import annotations

import logging

import pytest

from my_logger import LoggingConfig, setup_logger
from my_logger.exceptions import LoggerSetupError


@pytest.fixture(autouse=True)
def _reset_root_logger() -> None:
    """Räumt den Root-Logger vor und nach jedem Test auf — ``setup_logger``
    konfiguriert den globalen ``logging.getLogger()``, Tests dürfen sich
    daher nicht gegenseitig beeinflussen."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)
    for handler in original_handlers:
        root.addHandler(handler)
    root.setLevel(original_level)


class TestSetupLoggerHappyPath:
    def test_configures_console_and_file_handlers(self, tmp_path) -> None:
        config = LoggingConfig(console=True, file=str(tmp_path / "test.log"))
        root = setup_logger(config)

        assert any(isinstance(h, logging.StreamHandler) for h in root.handlers)
        assert any(isinstance(h, logging.FileHandler) for h in root.handlers)


class TestSetupLoggerFailurePreservesPreviousState:
    def test_failed_file_handler_leaves_previous_handlers_intact(self, tmp_path) -> None:
        good_log = tmp_path / "good.log"
        root = setup_logger(LoggingConfig(console=True, file=str(good_log)))
        previous_handlers = list(root.handlers)
        assert len(previous_handlers) == 2  # Konsole + Datei

        # Elternordner der neuen Logdatei ist tatsächlich eine Datei, kein
        # Ordner -- log_path.parent.mkdir(parents=True) muss daran scheitern.
        blocked_path = tmp_path / "ich_bin_eine_datei"
        blocked_path.write_text("kein Ordner")
        bad_config = LoggingConfig(console=True, file=str(blocked_path / "sub" / "new.log"))

        with pytest.raises(LoggerSetupError):
            setup_logger(bad_config)

        # Vor Befund 4.5 wären die alten Handler an dieser Stelle bereits
        # entfernt gewesen -- der Logger stand komplett ohne Output da.
        assert root.handlers == previous_handlers

    def test_failure_on_first_ever_call_raises_without_leaving_null_handler(
        self, tmp_path
    ) -> None:
        blocked_path = tmp_path / "ich_bin_eine_datei"
        blocked_path.write_text("kein Ordner")
        bad_config = LoggingConfig(console=False, file=str(blocked_path / "sub" / "new.log"))

        with pytest.raises(LoggerSetupError):
            setup_logger(bad_config)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
