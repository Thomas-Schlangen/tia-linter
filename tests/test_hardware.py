"""Tests für ``ZertifikatCheck`` (Review-Security-Robustheit.md, Befund 3.2).

``Siemens.Engineering.Security`` ist in dieser Testumgebung nicht
installierbar — der lokale Import innerhalb von ``ZertifikatCheck.run()``
schlägt daher immer mit ``ModuleNotFoundError`` fehl, was ``cert_manager``
zuverlässig auf ``None`` setzt. Das reicht bereits aus, um den "Service nicht
verfügbar"-Pfad ohne echtes TIA Portal zu prüfen.
"""

from __future__ import annotations

import pytest

from tia_linter.checks import hardware
from tia_linter.checks.hardware import ZertifikatCheck
from tia_linter.models import CheckDefinition, CheckSeverity

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


class FakePlcSoftware:
    Name = "PLC_1"


class TestZertifikatCheckSkipsUnavailableService:
    def test_missing_certificate_manager_yields_no_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Vor Befund 3.2 wäre das hier fälschlich ein CheckStatus.ERROR
        # ("Kein Kommunikationszertifikat vorhanden") gewesen, obwohl der
        # Dienst schlicht nicht geprüft werden konnte.
        monkeypatch.setattr(
            hardware, "iter_plc_targets", lambda project: iter([(FakePlcSoftware(), object(), object())])
        )

        check = ZertifikatCheck(_DEFINITION)
        results = check.run(project=object())

        assert results == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
