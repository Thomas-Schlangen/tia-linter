"""Tests für ``naming.py`` (Review-General.md, Befund 2 + Befund 8 der
Umsetzung — ``naming.py`` hatte zuvor keine eigene Testdatei).

``TestTestvariablenCheckSkipsWithoutPrefixes`` deckt den SKIPPED-Pfad ab: ein
nicht konfiguriertes ``prefixe`` lieferte bislang eine leere Ergebnisliste,
aus der ``runner._ok_result`` ein grünes "keine Verstöße gefunden" gemacht
hätte, obwohl mangels Präfix gar keine Variable geprüft werden konnte.

``TestDbFormatGlobalCheckSmoke`` ist der Smoke-Test aus Maßnahme 4
(Befund 8): ein sauberer, dem Muster entsprechender Global-DB-Name liefert
keinen Befund, ein abweichender liefert genau einen mit dem erwarteten Pfad.
"""

from __future__ import annotations

import pytest

# Modulimport statt "from tia_linter.checks.naming import TestvariablenCheck":
# Ein direkter Import brächte den Klassennamen in dieses Testmodul-Namespace,
# wo pytest ihn wegen des "Test"-Präfixes fälschlich als Testklasse
# einzusammeln versucht (PytestCollectionWarning, harmlos aber unnötig).
from tests.conftest import FakePlcSoftware
from tia_linter.checks import naming
from tia_linter.models import CheckDefinition, CheckSeverity, CheckStatus

_DEFINITION = CheckDefinition(
    check_id="namenskonventionen.testvariablen",
    name="Testvariablen vorhanden",
    category="Namenskonventionen",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="9",
    params={},
)

_DB_FORMAT_DEFINITION = CheckDefinition(
    check_id="namenskonventionen.db_format_global",
    name="DB-Namensformat (Global-/Array-DB)",
    category="Namenskonventionen",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="5",
    params={"regex": "^DB_"},
)


class TestTestvariablenCheckSkipsWithoutPrefixes:
    def test_missing_prefixe_yields_skipped_result(self) -> None:
        check = naming.TestvariablenCheck(_DEFINITION)

        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].status == CheckStatus.SKIPPED


class TestDbFormatGlobalCheckSmoke:
    def test_matching_db_name_is_not_reported(
        self, monkeypatch: pytest.MonkeyPatch, fake_sw_blocks_classes: object
    ) -> None:
        db = fake_sw_blocks_classes.DataBlock()
        db.Name = "DB_Rezept"
        monkeypatch.setattr(naming, "iter_plc_software", lambda project: [FakePlcSoftware("PLC_1")])
        monkeypatch.setattr(naming, "iter_data_blocks", lambda plc, ef, eb: [(db, [])])

        check = naming.DbFormatGlobalCheck(_DB_FORMAT_DEFINITION)
        results = check.run(project=object())

        assert results == []

    def test_non_matching_db_name_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, fake_sw_blocks_classes: object
    ) -> None:
        db = fake_sw_blocks_classes.DataBlock()
        db.Name = "Rezept"
        monkeypatch.setattr(naming, "iter_plc_software", lambda project: [FakePlcSoftware("PLC_1")])
        monkeypatch.setattr(naming, "iter_data_blocks", lambda plc, ef, eb: [(db, [])])

        check = naming.DbFormatGlobalCheck(_DB_FORMAT_DEFINITION)
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].path == "PLC_1 > Datenbaustein > Rezept"
        assert results[0].value == "Rezept"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
