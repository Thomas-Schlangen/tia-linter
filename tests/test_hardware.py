"""Tests für ``ZertifikatCheck`` (Review-Security-Robustheit.md, Befund 3.2;
Review-General.md, Befund 2).

``Siemens.Engineering.Security`` ist in dieser Testumgebung nicht
installierbar — der lokale Import innerhalb von ``ZertifikatCheck.run()``
schlägt daher immer mit ``ModuleNotFoundError`` fehl, was ``cert_manager``
zuverlässig auf ``None`` setzt. Das reicht bereits aus, um den "Service nicht
verfügbar"-Pfad ohne echtes TIA Portal zu prüfen.
"""

from __future__ import annotations

import pytest

from tia_linter.checks import hardware
from tia_linter.checks.hardware import SafetyPasswortCheck, ZertifikatCheck
from tia_linter.models import CheckDefinition, CheckSeverity, CheckStatus

_DEFINITION = CheckDefinition(
    check_id="hardware.zertifikat",
    name="Kommunikationszertifikat",
    category="Hardware",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="18c",
)

_SAFETY_DEFINITION = CheckDefinition(
    check_id="hardware.safety_passwort",
    name="Passwortschutz bei Sicherheits-SPS",
    category="Hardware",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="18b",
)


class FakePlcSoftware:
    Name = "PLC_1"


class TestZertifikatCheckSkipsUnavailableService:
    def test_missing_certificate_manager_yields_skipped_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Vor Befund 3.2 (Security-Runde) wäre das hier fälschlich ein
        # CheckStatus.ERROR ("Kein Kommunikationszertifikat vorhanden")
        # gewesen. Vor Befund 2 (General-Runde) wäre die Ergebnisliste leer
        # geblieben, was runner._ok_result zu einem grünen "keine Verstöße
        # gefunden" gemacht hätte — obwohl der Dienst schlicht nicht geprüft
        # werden konnte.
        monkeypatch.setattr(
            hardware, "iter_plc_targets", lambda project: iter([(FakePlcSoftware(), object(), object())])
        )

        check = ZertifikatCheck(_DEFINITION)
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].status == CheckStatus.SKIPPED


class TestSafetyPasswortCheckSkipsUnavailableService:
    """Review-General.md, Befund 2: analog zu ``ZertifikatCheck`` — eine PLC
    ohne verfügbare ``SafetyAdministration`` (keine F-CPU/keine Lizenz)
    meldete bislang gar nichts, wodurch ``runner._ok_result`` daraus ein
    grünes "keine Verstöße gefunden" gemacht hätte."""

    def test_missing_safety_administration_yields_skipped_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            hardware, "iter_plc_targets", lambda project: iter([(FakePlcSoftware(), object(), object())])
        )

        check = SafetyPasswortCheck(_SAFETY_DEFINITION)
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].status == CheckStatus.SKIPPED


class _FakeGetService:
    """Fake für ``device_item.GetService[ServiceType]()`` — pythonnets
    Indexer-Syntax für generische Methoden."""

    def __init__(self, instance: object) -> None:
        self._instance = instance

    def __getitem__(self, service_type: type) -> object:
        return lambda: self._instance


class _FakeDeviceItem:
    def __init__(self, service_instance: object) -> None:
        self.GetService = _FakeGetService(service_instance)


class TestSafetyPasswortCheckSmoke:
    """Smoke-Test für Prüfpunkt 18b (Review-General.md, Befund 8/Maßnahme 4):
    eine F-CPU mit gesetztem Safety-Passwort liefert keinen Befund, eine ohne
    genau einen. Ergänzt ``TestSafetyPasswortCheckSkipsUnavailableService``
    (Dienst nicht verfügbar) um den "Dienst verfügbar"-Pfad."""

    def test_password_set_is_not_reported(
        self, monkeypatch: pytest.MonkeyPatch, fake_safety_administration_class: type
    ) -> None:
        safety_admin = fake_safety_administration_class()
        safety_admin.IsSafetyOfflineProgramPasswordSet = True
        device_item = _FakeDeviceItem(safety_admin)
        monkeypatch.setattr(
            hardware, "iter_plc_targets", lambda project: iter([(FakePlcSoftware(), device_item, object())])
        )

        check = SafetyPasswortCheck(_SAFETY_DEFINITION)
        results = check.run(project=object())

        assert results == []

    def test_missing_password_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, fake_safety_administration_class: type
    ) -> None:
        safety_admin = fake_safety_administration_class()
        safety_admin.IsSafetyOfflineProgramPasswordSet = False
        device_item = _FakeDeviceItem(safety_admin)
        monkeypatch.setattr(
            hardware, "iter_plc_targets", lambda project: iter([(FakePlcSoftware(), device_item, object())])
        )

        check = SafetyPasswortCheck(_SAFETY_DEFINITION)
        results = check.run(project=object())

        assert len(results) == 1
        assert results[0].path == "PLC_1 > Sicherheitsprogramm"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
