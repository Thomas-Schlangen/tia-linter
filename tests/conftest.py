"""Gemeinsame, minimale Test-Attrappen für Openness-Objekte
(Review-General.md, Befund 8/Maßnahme 4 der Umsetzung).

Bislang duplizierte jede Testdatei ihre eigenen ``FakePlcSoftware``/
``FakeTag``/``FakeTagTable``-Klassen (siehe test_structure_checks.py,
test_hardware.py) — die drei einfachsten, über mehrere Check-Module hinweg
identisch geformten Attrappen stehen jetzt hier zentral.

Bewusst **nicht** die vollständige Openness-Objektstruktur (``Devices``/
``DeviceItems``/``GetService[...]``) nachgebaut — die Checks werden
stattdessen auf Ebene ihrer importierten ``_tia_helpers``-Funktionen
(``iter_plc_software``, ``iter_tag_tables``, ...) gemockt, analog zum
bereits etablierten Muster in test_structure_checks.py/test_libraries.py.

``fake_sw_blocks_classes`` installiert ein importierbares Fake-Modul für
``Siemens.Engineering.SW.Blocks`` mit echten Python-Klassen für
FB/FC/OB/DataBlock/InstanceDB — ``isinstance()``-Prüfungen in den Checks
(z. B. ``isinstance(block, FB)``) funktionieren damit genau wie mit der
echten Openness-DLL, ohne dass TIA Portal installiert sein muss.
"""

from __future__ import annotations

import sys
import types

import pytest


class FakePlcSoftware:
    def __init__(self, name: str = "PLC_1") -> None:
        self.Name = name


class FakeTag:
    def __init__(self, name: str, comment: str = "") -> None:
        self.Name = name
        # Kein echtes MultilingualText-Objekt (siehe _tia_helpers.read_comment) --
        # Tests, die dieses Attribut auswerten wollen, monkeypatchen
        # ``read_comment`` direkt auf ``getattr(obj, "comment", "")``.
        self.comment = comment


class FakeTagTable:
    def __init__(self, name: str, tags: list[FakeTag] | None = None) -> None:
        self.Name = name
        self.Tags = tags or []


@pytest.fixture
def fake_sw_blocks_classes(monkeypatch: pytest.MonkeyPatch) -> types.SimpleNamespace:
    """Installiert ``Siemens.Engineering.SW.Blocks`` mit echten Fake-Klassen
    ``DataBlock``/``InstanceDB``/``FB``/``FC``/``OB`` (``InstanceDB`` leitet
    von ``DataBlock`` ab, wie in der echten Openness-API) und liefert sie als
    Namespace zurück, damit Tests eigene Fake-Instanzen ableiten können
    (z. B. ``class FakeGlobalDb(classes.DataBlock): ...``)."""

    class DataBlock:
        pass

    class InstanceDB(DataBlock):
        pass

    class FB:
        pass

    class FC:
        pass

    class OB:
        pass

    blocks_module = types.ModuleType("Siemens.Engineering.SW.Blocks")
    blocks_module.DataBlock = DataBlock
    blocks_module.InstanceDB = InstanceDB
    blocks_module.FB = FB
    blocks_module.FC = FC
    blocks_module.OB = OB

    sw_module = types.ModuleType("Siemens.Engineering.SW")
    sw_module.Blocks = blocks_module
    engineering_module = types.ModuleType("Siemens.Engineering")
    engineering_module.SW = sw_module
    siemens_module = types.ModuleType("Siemens")
    siemens_module.Engineering = engineering_module

    monkeypatch.setitem(sys.modules, "Siemens", siemens_module)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering", engineering_module)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.SW", sw_module)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.SW.Blocks", blocks_module)

    return types.SimpleNamespace(DataBlock=DataBlock, InstanceDB=InstanceDB, FB=FB, FC=FC, OB=OB)


@pytest.fixture
def fake_safety_administration_class(monkeypatch: pytest.MonkeyPatch) -> type:
    """Installiert ``Siemens.Engineering.Safety`` mit einer echten Fake-Klasse
    ``SafetyAdministration``, damit ``SafetyPasswortCheck`` (hardware.py) den
    "Dienst verfügbar"-Pfad testen kann (der "Dienst nicht verfügbar"-Pfad
    kommt bereits ohne dieses Fixture zustande, siehe
    ``TestSafetyPasswortCheckSkipsUnavailableService`` in test_hardware.py)."""

    class SafetyAdministration:
        pass

    safety_module = types.ModuleType("Siemens.Engineering.Safety")
    safety_module.SafetyAdministration = SafetyAdministration
    engineering_module = types.ModuleType("Siemens.Engineering")
    engineering_module.Safety = safety_module
    siemens_module = types.ModuleType("Siemens")
    siemens_module.Engineering = engineering_module

    monkeypatch.setitem(sys.modules, "Siemens", siemens_module)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering", engineering_module)
    monkeypatch.setitem(sys.modules, "Siemens.Engineering.Safety", safety_module)

    return SafetyAdministration
