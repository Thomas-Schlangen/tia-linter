"""Tests für die Prüfpunkt-Parameter-Validierung in ``AppConfig``
(Review-Security-Robustheit.md, Befund 2.1/2.2).

Prüft ``AppConfig`` direkt über ``model_validate`` statt über
``load_app_config``/eine echte YAML-Datei — der Validator sitzt auf dem
Pydantic-Modell selbst, eine Datei auf der Festplatte fügt hier nur
Overhead hinzu, ohne zusätzliches Verhalten zu prüfen.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from tia_linter.config import AppConfig

_BASE_CONFIG = {
    "tia_versionen": {
        "verfuegbar": [{"name": "V21", "version": 21, "dll_pfad": "x.dll"}],
        "standard": "V21",
    },
    "checks": {
        "namenskonventionen": {
            "testvariablen": {"enabled": True, "severity": "warning", "prefixe": ["TEST_", "DBG_"]},
            "fb_prefix": {"enabled": True, "severity": "warning", "regex": "^FB_[A-Z][a-zA-Z0-9]*$"},
        },
    },
}


def _config(**overrides: object) -> dict:
    data = copy.deepcopy(_BASE_CONFIG)
    for check_key, params in overrides.items():
        data["checks"]["namenskonventionen"][check_key].update(params)
    return data


class TestListParamValidation:
    def test_valid_list_passes(self) -> None:
        AppConfig.model_validate(_config(testvariablen={"prefixe": ["TEST_"]}))

    def test_string_instead_of_list_is_rejected(self) -> None:
        # Klassischer YAML-Tippfehler: "prefixe: TEST" statt "prefixe: [TEST]" --
        # tuple("TEST") würde zur Laufzeit stillschweigend ('T','E','S','T')
        # ergeben (siehe Review-Security-Robustheit.md, Befund 2.1).
        with pytest.raises(ValidationError, match="testvariablen.prefixe.*erwartet eine Liste"):
            AppConfig.model_validate(_config(testvariablen={"prefixe": "TEST"}))

    def test_missing_list_param_is_not_an_error(self) -> None:
        # Fehlt der Schlüssel komplett, greift der Check-seitige Default --
        # das ist kein Validierungsfehler, nur ein nicht gesetzter Parameter.
        AppConfig.model_validate(_config(testvariablen={}))


class TestRegexParamValidation:
    def test_valid_regex_passes(self) -> None:
        AppConfig.model_validate(_config(fb_prefix={"regex": "^FB_"}))

    def test_invalid_regex_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="ungültiger regulärer Ausdruck"):
            AppConfig.model_validate(_config(fb_prefix={"regex": "^[A-Z"}))

    def test_empty_regex_string_is_allowed(self) -> None:
        # Leerer String bedeutet je Prüfpunkt "deaktiviert" (siehe z. B.
        # structure.py::LeeresNetzwerkCheck), kein Validierungsfehler.
        AppConfig.model_validate(_config(fb_prefix={"regex": ""}))

    def test_non_string_regex_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="erwartet einen String"):
            AppConfig.model_validate(_config(fb_prefix={"regex": 123}))


class TestMultipleViolationsCollected:
    def test_all_violations_reported_in_one_error(self) -> None:
        data = _config(testvariablen={"prefixe": "TEST"}, fb_prefix={"regex": "^[A-Z"})
        with pytest.raises(ValidationError) as exc_info:
            AppConfig.model_validate(data)
        message = str(exc_info.value)
        assert "testvariablen.prefixe" in message
        assert "fb_prefix.regex" in message


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
