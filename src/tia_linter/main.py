"""Einstiegspunkt für den TIA Linter — die GUI ist der einzige Weg, das Tool zu starten."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from my_logger import setup_logger

from tia_linter.config import load_app_config
from tia_linter.runner import run_lint, simulate_lint_run
from tia_linter.settings import Settings

logger = logging.getLogger(__name__)

# Fällt zurück auf das im Paket mitgelieferte config/default.yaml, wenn
# settings.json noch keinen (gültigen) Config-Pfad kennt.
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


def _configure_console_encoding() -> None:
    """Erzwingt UTF-8 auf stdout/stderr, damit Umlaute in Konsolenausgaben auf
    Windows nicht anhand der lokalen Codepage verstümmelt werden."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _resolve_config_path(settings: Settings) -> Path:
    if settings.last_config_path:
        candidate = Path(settings.last_config_path)
        if candidate.is_file():
            return candidate
    return _DEFAULT_CONFIG_PATH


def main() -> int:
    _configure_console_encoding()

    settings = Settings.load()
    config_path = _resolve_config_path(settings)

    try:
        config = load_app_config(config_path)
    except Exception as exc:  # noqa: BLE001 — letzte Instanz gegen rohe Tracebacks für den Benutzer
        print(f"Fehler beim Laden der Konfiguration '{config_path}': {exc}", file=sys.stderr)
        return 1

    setup_logger(config.logging)
    logger.info("Konfiguration geladen (%s), starte GUI", config_path)

    from tia_linter.gui import TiaLinterApp

    # run_lint() ist der Produktivmodus (Standard); simulate_lint_run() bleibt
    # über die "Testmodus"-Checkbox in der GUI erreichbar (siehe gui.py) —
    # beide werden hier übergeben, die GUI entscheidet zur Laufzeit anhand
    # der Checkbox, welche Funktion für den jeweiligen Lauf verwendet wird.
    app = TiaLinterApp(config, config_path, settings, run_lint, simulate_lint_run)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
