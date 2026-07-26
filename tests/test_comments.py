"""Smoke-Test für ``VariablenKommentarCheck`` (Review-General.md, Befund 8 —
comments.py hatte bislang keine eigene Testdatei).

Deckt gezielt den PLC-Tag-Pfad ab (``_check_tags``): ein sauberes Tag mit
Kommentar liefert keinen Befund, ein Tag ohne Kommentar liefert genau einen
Befund mit dem erwarteten Pfad. Der DB-Member-Pfad (``_check_db_members``,
UDT-/FB-Erkennung, Projekttexte) ist deutlich komplexer und bereits über
seine ausführliche Docstring-Historie dokumentiert — für einen ersten
Smoke-Test reicht der Tag-Pfad als repräsentativer Ausschnitt.

Alle Iterator-Hilfsfunktionen (``iter_plc_software``/``iter_tag_tables``/
``iter_data_blocks``/``iter_blocks``/``iter_plc_types``) sowie
``read_comment``/``reference_language`` werden direkt gemockt (analog zu
test_structure_checks.py) — ``_all_fb_names``/``_all_udt_names`` (aufgerufen
von ``_check_db_members``, das bei jedem Lauf mit ausgeführt wird) brauchen
zusätzlich ein importierbares Fake-Modul für
``Siemens.Engineering.SW.Blocks`` (``fake_sw_blocks_classes``-Fixture aus
conftest.py), da ihr lokaler Import sonst unabhängig vom eigentlichen
Testfall mit ``ModuleNotFoundError`` scheitert.
"""

from __future__ import annotations

import pytest

from tests.conftest import FakePlcSoftware, FakeTag, FakeTagTable
from tia_linter.checks import comments
from tia_linter.checks.comments import VariablenKommentarCheck
from tia_linter.models import CheckDefinition, CheckSeverity

_DEFINITION = CheckDefinition(
    check_id="kommentare.variablen_kommentar",
    name="Variablen ohne Kommentar",
    category="Kommentare & Beschreibungen",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="1a",
    params={},
)


@pytest.fixture(autouse=True)
def _stub_helpers(monkeypatch: pytest.MonkeyPatch, fake_sw_blocks_classes: object) -> None:
    monkeypatch.setattr(comments, "iter_plc_software", lambda project: [FakePlcSoftware("PLC_1")])
    monkeypatch.setattr(comments, "iter_data_blocks", lambda plc, ef, eb: [])
    monkeypatch.setattr(comments, "iter_blocks", lambda plc, *args, **kwargs: [])
    monkeypatch.setattr(comments, "iter_plc_types", lambda plc, *args, **kwargs: [])
    monkeypatch.setattr(comments, "reference_language", lambda project: "de-DE")
    monkeypatch.setattr(comments, "read_comment", lambda obj, language: getattr(obj, "comment", ""))


class TestVariablenKommentarCheckSmoke:
    def test_tag_without_comment_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tag = FakeTag("Merker_1", comment="")
        table = FakeTagTable("Tabelle_1", [tag])
        monkeypatch.setattr(comments, "iter_tag_tables", lambda plc, excluded: [table])

        check = VariablenKommentarCheck(_DEFINITION)
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].path == "PLC_1 > Variablentabellen > Tabelle_1 > Merker_1"
        assert results[0].value == "Merker_1"

    def test_tag_with_comment_is_not_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tag = FakeTag("Merker_1", comment="Motor läuft")
        table = FakeTagTable("Tabelle_1", [tag])
        monkeypatch.setattr(comments, "iter_tag_tables", lambda plc, excluded: [table])

        check = VariablenKommentarCheck(_DEFINITION)
        results = check.run(project=object())

        assert results == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
