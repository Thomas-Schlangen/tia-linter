"""Smoke-Test für ``MaxSprachenCheck`` (Review-General.md, Befund 8 —
metadata.py hatte bislang keine eigene Testdatei).

Prüfpunkt 20: nicht mehr aktive Sprachen als konfiguriertes Maximum liefert
keinen Befund, mehr als das Maximum liefert genau einen. ``FakeLanguage``
bildet ``GetAttribute("Name")`` nach (siehe ``_tia_helpers.get_attribute``) —
kein Monkeypatch von ``get_attribute`` nötig, da das reale Attributzugriffs-
muster hier ausreicht.
"""

from __future__ import annotations

import pytest

from tia_linter.checks.metadata import MaxSprachenCheck
from tia_linter.models import CheckDefinition, CheckSeverity

_DEFINITION = CheckDefinition(
    check_id="projektmetadaten.max_sprachen",
    name="Anzahl Sprachen",
    category="Projektmetadaten",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="20",
    params={"max": 2},
)


class FakeLanguage:
    def __init__(self, name: str) -> None:
        self._name = name

    def GetAttribute(self, attribute_name: str) -> str | None:
        return self._name if attribute_name == "Name" else None


class FakeLanguageSettings:
    def __init__(self, active_languages: list[FakeLanguage]) -> None:
        self.ActiveLanguages = active_languages


class FakeProject:
    def __init__(self, active_languages: list[FakeLanguage]) -> None:
        self.LanguageSettings = FakeLanguageSettings(active_languages)


class TestMaxSprachenCheckSmoke:
    def test_language_count_within_limit_is_not_reported(self) -> None:
        project = FakeProject([FakeLanguage("Deutsch"), FakeLanguage("Englisch")])

        check = MaxSprachenCheck(_DEFINITION)
        results = check.run(project=project)

        assert results == []

    def test_language_count_above_limit_is_reported(self) -> None:
        project = FakeProject([FakeLanguage("Deutsch"), FakeLanguage("Englisch"), FakeLanguage("Französisch")])

        check = MaxSprachenCheck(_DEFINITION)
        results = check.run(project=project)

        assert len(results) == 1
        assert results[0].path == "Projekt > Eigenschaften > Sprachen"
        assert results[0].value == "3"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
