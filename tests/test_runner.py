"""Tests für reine, TIA-unabhängige Logik in runner.py.

``runner.py`` orchestriert echte TIA-Portal-Verbindungen und lässt sich
größtenteils nur gegen ein echtes Projekt sinnvoll testen (siehe
review_fortschritt.md) — ``_check_weight`` (Reconnect-Gewichtung,
Review-Performance.md, Maßnahme 5) ist aber eine reine Dict-Lookup-Funktion
ohne TIA-Abhängigkeit und lässt sich isoliert prüfen.
"""

from __future__ import annotations

from tia_linter.runner import _check_weight


class TestCheckWeight:
    def test_returns_configured_weight_for_known_check_id(self) -> None:
        weights = {"programmstruktur.unbenutzte_variablen": 5, "default": 1}
        assert _check_weight("programmstruktur.unbenutzte_variablen", weights) == 5

    def test_falls_back_to_default_key_for_unknown_check_id(self) -> None:
        weights = {"programmstruktur.unbenutzte_variablen": 5, "default": 2}
        assert _check_weight("kommentare.baustein_beschreibung", weights) == 2

    def test_falls_back_to_one_when_no_default_key_present(self) -> None:
        assert _check_weight("irgendein_check", {"programmstruktur.unbenutzte_variablen": 5}) == 1

    def test_falls_back_to_one_for_empty_weights(self) -> None:
        assert _check_weight("beliebiger_check", {}) == 1


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
