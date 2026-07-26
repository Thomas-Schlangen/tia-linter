"""Tests für die Prüfpunkt-12a/12b-Zusammenlegung (Maßnahme 3) und die
CrossReference-Cache-Anbindung (Maßnahme 4) in checks/structure.py, siehe
Review-Performance.md.

Prüft nicht die volle CrossReferenceService-Kette (dafür fehlt eine echte
TIA-Verbindung, siehe test_tia_helpers.py), sondern die Logik, die diese
Session tatsächlich geändert hat: Wird bei beiden aktivierten Checks nur
noch eine ``cached_cross_reference_locations``-Abfrage pro Tag gemacht,
landen die richtigen Rohdaten im Zwischenspeicher, und fällt der zweite
Check korrekt auf einen eigenständigen Durchlauf zurück, wenn kein
Zwischenspeicher da ist? Dafür werden ``iter_plc_software``/
``iter_tag_tables``/``tag_direction``/``cached_cross_reference_locations``
direkt im ``structure``-Modul durch einfache Fakes ersetzt -- die echte
LRU-/Filter-Logik von ``cached_cross_reference_locations`` selbst wird in
test_tia_helpers.py geprüft.
"""

from __future__ import annotations

import sys
import types

import pytest

from tia_linter.checks import structure
from tia_linter.checks.structure import (
    EingaengeGelesenCheck,
    EingaengeNichtBeschriebenCheck,
    LeereNetzwerkeCheck,
    UnbenutzteVariablenCheck,
)
from tia_linter.models import CheckDefinition, CheckSeverity


class FakeCrossReferenceFilter:
    """Ersetzt ``Siemens.Engineering.CrossReference.CrossReferenceFilter`` —
    die Checks übergeben nur ``.AllObjects`` unverändert an die (hier
    gefakte) ``cached_cross_reference_locations``, der konkrete Wert spielt
    für die Tests keine Rolle."""

    AllObjects = "AllObjects"


class FakeTag:
    def __init__(self, name: str) -> None:
        self.Name = name


class FakeTagTable:
    def __init__(self, name: str, tags: list[FakeTag]) -> None:
        self.Name = name
        self.Tags = tags


class FakePlcSoftware:
    def __init__(self, name: str) -> None:
        self.Name = name


def _definition(check_id: str, name: str) -> CheckDefinition:
    return CheckDefinition(
        check_id=check_id,
        name=name,
        category="Programmstruktur",
        enabled=True,
        severity=CheckSeverity.ERROR,
        description="",
        recommendation="",
        nummer="12",
    )


_CHECK_ID_A = "programmstruktur.eingaenge_gelesen"
_CHECK_ID_B = "programmstruktur.eingaenge_nicht_beschrieben"


@pytest.fixture(autouse=True)
def _reset_stash() -> None:
    structure.reset_pending_write_counts()
    yield
    structure.reset_pending_write_counts()


def _patch_common(
    monkeypatch: pytest.MonkeyPatch,
    tags: list[FakeTag],
    locations_by_tag: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """Installiert die Fakes und liefert eine Liste, in der jeder
    ``cached_cross_reference_locations``-Aufruf (Tag-Name) protokolliert
    wird — damit Tests zählen können, wie oft tatsächlich abgefragt wurde.

    ``locations_by_tag`` liefert je Tag eine Liste von
    ``(access, reference_type)``-Tupeln, exakt das Format, das die echte
    ``cached_cross_reference_locations`` zurückgibt (siehe _tia_helpers.py)."""
    plc = FakePlcSoftware("PLC_1")
    tag_table = FakeTagTable("Tags_Eingaenge", tags)

    call_log: list[str] = []

    def fake_cached_cross_reference_locations(obj: FakeTag, cross_reference_filter: object, plc_name: str) -> list[tuple[str, str]]:
        call_log.append(obj.Name)
        return locations_by_tag.get(obj.Name, [])

    monkeypatch.setattr(structure, "iter_plc_software", lambda project: [plc])
    monkeypatch.setattr(structure, "iter_tag_tables", lambda plc_software, excluded_folders: [tag_table])
    monkeypatch.setattr(structure, "tag_direction", lambda tag: "I")
    monkeypatch.setattr(structure, "cached_cross_reference_locations", fake_cached_cross_reference_locations)

    # ``from Siemens.Engineering.CrossReference import CrossReferenceFilter``
    # (lokaler Import in _run_standalone/_run_combined/run) braucht ein
    # importierbares Fake-Modul, analog zu _install_fake_dotnet_modules in
    # test_tia_helpers.py -- über monkeypatch.setitem, damit sys.modules nach
    # dem Test wieder sauber zurückgesetzt wird.
    cross_reference = types.ModuleType("Siemens.Engineering.CrossReference")
    cross_reference.CrossReferenceFilter = FakeCrossReferenceFilter
    engineering = types.ModuleType("Siemens.Engineering")
    engineering.CrossReference = cross_reference
    siemens = types.ModuleType("Siemens")
    siemens.Engineering = engineering

    monkeypatch.setitem(sys.modules, "Siemens", siemens)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering", engineering)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.CrossReference", cross_reference)

    return call_log


class TestOnlyOneCheckEnabled:
    def test_eingaenge_gelesen_alone_runs_standalone_and_flags_missing_read(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tags = [FakeTag("Sensor1"), FakeTag("Sensor2")]
        locations = {
            "Sensor1": [("Read", "UsedBy")],
            "Sensor2": [("Write", "UsedBy")],  # nie gelesen -> Befund erwartet
        }
        call_log = _patch_common(monkeypatch, tags, locations)

        check = EingaengeGelesenCheck(_definition(_CHECK_ID_A, "12a"), enabled_check_ids=frozenset({_CHECK_ID_A}))
        results = check.run(project=object())

        assert [r.value for r in results] == ["Sensor2"]
        assert call_log == ["Sensor1", "Sensor2"]  # eine Abfrage pro Tag, kein Merge
        assert structure._pending_write_counts == {}  # kein Zwischenspeicher befüllt

    def test_eingaenge_nicht_beschrieben_alone_runs_standalone_and_flags_write(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tags = [FakeTag("Sensor1"), FakeTag("Sensor2")]
        locations = {
            "Sensor1": [("Read", "UsedBy")],
            "Sensor2": [("Write", "UsedBy"), ("Write", "UsedBy")],
        }
        call_log = _patch_common(monkeypatch, tags, locations)

        check = EingaengeNichtBeschriebenCheck(_definition(_CHECK_ID_B, "12b"), enabled_check_ids=frozenset({_CHECK_ID_B}))
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].value == "2"
        assert "Sensor2" in results[0].description
        assert call_log == ["Sensor1", "Sensor2"]


class TestBothChecksEnabled:
    def test_eingaenge_gelesen_populates_stash_with_single_query_per_tag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tags = [FakeTag("Sensor1"), FakeTag("Sensor2")]
        locations = {
            "Sensor1": [("Read", "UsedBy")],
            "Sensor2": [("Write", "UsedBy"), ("Write", "UsedBy")],  # nie gelesen UND mehrfach beschrieben
        }
        call_log = _patch_common(monkeypatch, tags, locations)
        both_enabled = frozenset({_CHECK_ID_A, _CHECK_ID_B})

        check_a = EingaengeGelesenCheck(_definition(_CHECK_ID_A, "12a"), enabled_check_ids=both_enabled)
        results_a = check_a.run(project=object())

        # Genau eine Abfrage pro Tag -- keine Verdopplung durch den Merge.
        assert call_log == ["Sensor1", "Sensor2"]
        assert [r.value for r in results_a] == ["Sensor2"]

        stashed = structure._pending_write_counts[_CHECK_ID_B]
        assert len(stashed) == 1
        path, tag_name, write_count = stashed[0]
        assert tag_name == "Sensor2"
        assert write_count == 2

    def test_eingaenge_nicht_beschrieben_consumes_stash_without_requerying(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tags = [FakeTag("Sensor1"), FakeTag("Sensor2")]
        locations = {
            "Sensor1": [("Read", "UsedBy")],
            "Sensor2": [("Write", "UsedBy"), ("Write", "UsedBy")],
        }
        call_log = _patch_common(monkeypatch, tags, locations)
        both_enabled = frozenset({_CHECK_ID_A, _CHECK_ID_B})

        check_a = EingaengeGelesenCheck(_definition(_CHECK_ID_A, "12a"), enabled_check_ids=both_enabled)
        check_a.run(project=object())
        call_log.clear()  # nur die Aufrufe von 12b zählen ab hier

        check_b = EingaengeNichtBeschriebenCheck(_definition(_CHECK_ID_B, "12b"), enabled_check_ids=both_enabled)
        results_b = check_b.run(project=object())

        assert call_log == []  # keine erneute CrossReference-Abfrage
        assert len(results_b) == 1
        assert results_b[0].value == "2"
        assert "Sensor2" in results_b[0].description
        assert structure._pending_write_counts == {}  # Zwischenspeicher wieder leer (konsumiert)

    def test_eingaenge_nicht_beschrieben_falls_back_when_stash_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 12b läuft "zuerst" (Stash leer) -- muss trotz enabled_check_ids,
        # die 12a als aktiv ausweisen, korrekt eigenständig abfragen.
        tags = [FakeTag("Sensor1")]
        locations = {"Sensor1": [("Write", "UsedBy")]}
        call_log = _patch_common(monkeypatch, tags, locations)
        both_enabled = frozenset({_CHECK_ID_A, _CHECK_ID_B})

        check_b = EingaengeNichtBeschriebenCheck(_definition(_CHECK_ID_B, "12b"), enabled_check_ids=both_enabled)
        results_b = check_b.run(project=object())

        assert call_log == ["Sensor1"]
        assert len(results_b) == 1
        assert results_b[0].value == "1"


class FakeBlock:
    def __init__(self, name: str) -> None:
        self.Name = name


class TestLeereNetzwerkeCheckSmoke:
    """Smoke-Test für Prüfpunkt 10 (Review-General.md, Befund 8/Maßnahme 4):
    ein Netzwerk ohne Programmelemente liefert genau einen Befund, ein
    Netzwerk mit Inhalt keinen. ``ausnahme_titel_regex`` bleibt hier
    deaktiviert (Standard ``""``), daher wird ``reference_language`` nicht
    ausgewertet."""

    _DEFINITION = CheckDefinition(
        check_id="programmstruktur.leere_netzwerke",
        name="Leere Netzwerke",
        category="Programmstruktur",
        enabled=True,
        severity=CheckSeverity.WARNING,
        description="",
        recommendation="",
        nummer="10",
        params={},
    )

    def _stub_common(self, monkeypatch: pytest.MonkeyPatch, block: FakeBlock, element_count: int) -> None:
        monkeypatch.setattr(structure, "iter_plc_software", lambda project: [FakePlcSoftware("PLC_1")])
        monkeypatch.setattr(structure, "iter_blocks", lambda plc, ef, eb: [(block, [])])
        monkeypatch.setattr(structure, "block_programming_language", lambda block: "FBD")
        monkeypatch.setattr(structure, "export_block_xml", lambda block, plc: object())
        monkeypatch.setattr(structure, "iter_compile_units", lambda xml_root: [object()])
        monkeypatch.setattr(structure, "compile_unit_attribute", lambda cu, name: None)
        monkeypatch.setattr(structure, "compile_unit_element_count", lambda cu: element_count)

    def test_empty_network_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        block = FakeBlock("FB_Motor")
        self._stub_common(monkeypatch, block, element_count=0)

        check = LeereNetzwerkeCheck(self._DEFINITION)
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].path == "PLC_1 > Programmbausteine > FB_Motor > Netzwerk 1"

    def test_non_empty_network_is_not_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        block = FakeBlock("FB_Motor")
        self._stub_common(monkeypatch, block, element_count=3)

        check = LeereNetzwerkeCheck(self._DEFINITION)
        results = check.run(project=object())

        assert results == []


class TestUnbenutzteVariablenCheckDbMembersViaRootSource:
    """Regressionstest für Review-General.md, Befund 10g: ``_check_db_members``
    fragt den CrossReferenceService seit diesem Fix über
    ``cross_reference_root_source()`` ab statt ``GetService[...]`` selbst
    nachzubilden — stellt sicher, dass der Umbau das gefundene Ergebnis nicht
    verändert hat (weiterhin verifiziert am "Siebzehnter/Achtzehnter
    Bug"-Fall: Root-Source trägt den DB-Namen, das eigentliche unbenutzte
    Member steckt als Kind darunter)."""

    def test_unused_db_member_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, fake_sw_blocks_classes: object
    ) -> None:
        from tests.test_tia_helpers import (
            FakeCrossReferenceService,
            FakeXrefSourceObject,
            _FakeGenericMethod,
            _install_fake_cross_reference_module,
        )

        _install_fake_cross_reference_module(monkeypatch)

        leaf = FakeXrefSourceObject([])
        leaf.Name = "DiagCpu.DNNmode"
        root = FakeXrefSourceObject([])
        root.Name = "DB_X"
        root.Children = [leaf]
        service = FakeCrossReferenceService([root])

        class FakeDb(fake_sw_blocks_classes.DataBlock):
            Name = "DB_X"
            Interface = None
            GetService = _FakeGenericMethod(service)

        db = FakeDb()
        monkeypatch.setattr(structure, "iter_data_blocks", lambda plc, ef, eb: [(db, [])])

        definition = CheckDefinition(
            check_id="programmstruktur.unbenutzte_variablen",
            name="Unbenutzte Variablen",
            category="Programmstruktur",
            enabled=True,
            severity=CheckSeverity.WARNING,
            description="",
            recommendation="",
            nummer="11a",
            params={},
        )
        check = UnbenutzteVariablenCheck(definition)

        results = check._check_db_members(FakePlcSoftware("PLC_1"), check_sub_items=True)

        assert len(results) == 1
        assert results[0].path == "PLC_1 > Datenbaustein > DB_X > Member > DiagCpu.DNNmode"
        assert service.call_count == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
