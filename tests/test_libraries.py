"""Tests für ``VeralteteBibliothekenCheck``/``SprachenKonsistentCheck``
(Review-General.md, Befund 2).

``libraries.py`` hatte bislang keine eigene Testdatei — diese Tests decken
gezielt die neuen SKIPPED-Pfade ab: fehlt die Projektbibliothek bzw. ist die
Referenzsprache nicht lesbar, lieferten beide Checks bislang eine leere
Ergebnisliste, aus der ``runner._ok_result`` ein grünes "keine Verstöße
gefunden" gemacht hätte, obwohl gar nichts geprüft werden konnte.
"""

from __future__ import annotations

import sys
import types

import pytest

from tia_linter.checks.libraries import SprachenKonsistentCheck, VeralteteBibliothekenCheck
from tia_linter.models import CheckDefinition, CheckSeverity, CheckStatus

_BIBLIOTHEKEN_DEFINITION = CheckDefinition(
    check_id="bibliotheken.veraltete_bibliotheken",
    name="Bibliotheksbausteine auf aktuellem Stand",
    category="Bibliotheken & Typen",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="22",
)

_SPRACHEN_DEFINITION = CheckDefinition(
    check_id="styleguide.sprachen_konsistent",
    name="Sprachen konsistent",
    category="Siemens Styleguide & Best Practices",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="24",
)


@pytest.fixture
def fake_library_types_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installiert ein importierbares Fake-Modul für
    ``Siemens.Engineering.Library.Types`` (lokaler Import in
    ``VeralteteBibliothekenCheck.run()``), analog zu
    ``_install_fake_dotnet_modules`` in test_structure_checks.py/
    test_tia_helpers.py."""
    library_types = types.ModuleType("Siemens.Engineering.Library.Types")
    library_types.UpdateCheckMode = types.SimpleNamespace(ReportOutOfDateOnly="ReportOutOfDateOnly")
    library = types.ModuleType("Siemens.Engineering.Library")
    library.Types = library_types
    engineering = types.ModuleType("Siemens.Engineering")
    engineering.Library = library
    siemens = types.ModuleType("Siemens")
    siemens.Engineering = engineering

    monkeypatch.setitem(sys.modules, "Siemens", siemens)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering", engineering)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.Library", library)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.Library.Types", library_types)


class TestVeralteteBibliothekenCheckSkipsWithoutLibrary:
    def test_missing_project_library_yields_skipped_result(self, fake_library_types_module: None) -> None:
        check = VeralteteBibliothekenCheck(_BIBLIOTHEKEN_DEFINITION)

        results = check.run(project=object())  # kein ProjectLibrary-Attribut

        assert len(results) == 1
        assert results[0].status == CheckStatus.SKIPPED

    def test_failing_update_check_yields_skipped_result(self, fake_library_types_module: None) -> None:
        class FailingLibrary:
            def UpdateCheck(self, project: object, mode: object) -> None:
                raise RuntimeError("UpdateCheck fehlgeschlagen (simuliert)")

        class FakeProject:
            ProjectLibrary = FailingLibrary()

        check = VeralteteBibliothekenCheck(_BIBLIOTHEKEN_DEFINITION)

        results = check.run(project=FakeProject())

        assert len(results) == 1
        assert results[0].status == CheckStatus.SKIPPED


class TestSprachenKonsistentCheckSkipsWhenLanguageUnreadable:
    def test_unreadable_reference_language_yields_skipped_result(self) -> None:
        class FakeProject:
            @property
            def LanguageSettings(self) -> None:
                raise RuntimeError("Referenzsprache nicht lesbar (simuliert)")

        check = SprachenKonsistentCheck(_SPRACHEN_DEFINITION)

        results = check.run(project=FakeProject())

        assert len(results) == 1
        assert results[0].status == CheckStatus.SKIPPED


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
