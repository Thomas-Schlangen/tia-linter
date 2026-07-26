"""Tests für reine, TIA-unabhängige Logik in runner.py.

``runner.py`` orchestriert echte TIA-Portal-Verbindungen und lässt sich
größtenteils nur gegen ein echtes Projekt sinnvoll testen (siehe
review_fortschritt.md) — ``_check_weight`` (Reconnect-Gewichtung,
Review-Performance.md, Maßnahme 5) ist aber eine reine Dict-Lookup-Funktion
ohne TIA-Abhängigkeit und lässt sich isoliert prüfen.
"""

from __future__ import annotations

import pytest

import re

from tia_linter import runner
from tia_linter.models import CheckDefinition, CheckSeverity, CheckStatus
from tia_linter.runner import _check_failure_recommendation, _check_weight


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


class TestCheckFailureRecommendation:
    """Review-Security-Robustheit.md, Befund 4.4: der Empfehlungstext muss
    bei einem Konfigurationsfehler auf die Config verweisen, nicht auf die
    Logdatei/ein API-Problem."""

    @pytest.mark.parametrize("exc", [re.error("kaputt"), TypeError("falscher Typ"), ValueError("ungültiger Wert")])
    def test_config_like_exceptions_point_to_configuration(self, exc: Exception) -> None:
        assert _check_failure_recommendation(exc) == "Parameter dieses Prüfpunkts in der Konfigurationsdatei prüfen."

    def test_other_exceptions_point_to_log_file(self) -> None:
        assert _check_failure_recommendation(RuntimeError("API kaputt")) == (
            "Log-Datei prüfen — vermutlich ein API-Zugriffsproblem."
        )


class FakeConnector:
    """Simuliert ``BaseTiaConnector`` ohne echte TIA-Verbindung — liefert bei
    ``connect()`` ein festes Fake-Projekt zurück, ``__enter__``/``__exit__``
    sind No-Ops."""

    def __init__(self, project: object) -> None:
        self._project = project

    def __enter__(self) -> "FakeConnector":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def connect(self, project_path: str) -> object:
        return self._project


_DUMMY_DEFINITION = CheckDefinition(
    check_id="namenskonventionen.testvariablen",
    name="Testvariablen",
    category="Namenskonventionen",
    enabled=True,
    severity=CheckSeverity.WARNING,
    description="",
    recommendation="",
    nummer="9",
)


class TestRunLintEmptyPlcSoftware:
    """Review-Security-Robustheit.md, Befund 3.3: Ein Projekt ohne PLC-Software
    (HMI-only, falsches Projekt gewählt, ``ausgeschlossene_ordner`` trifft
    zufällig die gesamte Struktur) darf nicht als "39 × keine Verstöße"
    durchlaufen — dafür müsste jeder Check über ``iter_plc_software`` iterieren
    und leer bleiben, was nach der bisherigen Konvention (``_ok_result``) wie
    ein vollständig sauberes Projekt aussähe. Stattdessen muss ``run_lint``
    sofort mit genau einem Fehlbefund abbrechen, ohne einen einzigen Check zu
    instanziieren."""

    def test_no_plc_software_yields_single_error_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_project = object()
        monkeypatch.setattr(runner, "create_connector", lambda tia_version, dll_path: FakeConnector(fake_project))
        monkeypatch.setattr(runner, "iter_plc_software", lambda project: iter(()))

        report = runner.run_lint(
            dll_path="dummy.dll",
            tia_version=21,
            project_path="dummy.ap21",
            project_name="Dummy",
            tia_version_name="V21",
            checker_name="Tester",
            definitions=[_DUMMY_DEFINITION],
        )

        assert len(report.results) == 1
        result = report.results[0]
        assert result.check_id == "verbindung.keine_plc"
        assert result.status == CheckStatus.ERROR

    def test_no_plc_software_does_not_instantiate_any_check(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_project = object()
        monkeypatch.setattr(runner, "create_connector", lambda tia_version, dll_path: FakeConnector(fake_project))
        monkeypatch.setattr(runner, "iter_plc_software", lambda project: iter(()))
        instantiate_calls: list[str] = []
        monkeypatch.setattr(
            runner,
            "_instantiate_check",
            lambda definition, *args: instantiate_calls.append(definition.check_id),
        )

        runner.run_lint(
            dll_path="dummy.dll",
            tia_version=21,
            project_path="dummy.ap21",
            project_name="Dummy",
            tia_version_name="V21",
            checker_name="Tester",
            definitions=[_DUMMY_DEFINITION],
        )

        assert instantiate_calls == []


class FakeFailingConnector:
    """Wie ``FakeConnector``, aber ``connect()`` wirft eine Exception —
    simuliert einen fehlgeschlagenen Verbindungsaufbau (Befund 4.2/4.3)."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def __enter__(self) -> "FakeFailingConnector":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def connect(self, project_path: str) -> object:
        raise self._exc


class TestRunLintUnexpectedConnectionError:
    """Review-Security-Robustheit.md, Befund 4.2/4.3: Vor diesem Fix propagierte
    eine Exception beim allerersten Verbindungsversuch (``disposed_exc_types``
    ist dort noch das leere Tupel, ``except ()`` fängt nichts) oder eine
    spätere Exception eines anderen Typs als ``disposed_exc_types`` komplett
    an ``run_lint`` vorbei — verloren gingen dabei sowohl der Report selbst
    als auch alle bereits gesammelten Ergebnisse."""

    def test_first_connect_failure_returns_report_with_error_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            runner, "create_connector", lambda tia_version, dll_path: FakeFailingConnector(RuntimeError("kaputt"))
        )

        report = runner.run_lint(
            dll_path="dummy.dll",
            tia_version=21,
            project_path="dummy.ap21",
            project_name="Dummy",
            tia_version_name="V21",
            checker_name="Tester",
            definitions=[_DUMMY_DEFINITION],
        )

        assert len(report.results) == 1
        result = report.results[0]
        assert result.check_id == "verbindung.reconnect"
        assert result.status == CheckStatus.ERROR
        assert "kaputt" in result.description

    def test_create_connector_failure_returns_report_with_error_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # create_connector() selbst stand vor diesem Fix AUSSERHALB des
        # try-Blocks -- eine TiaConnectionError von dort (z. B. unbekannte
        # TIA-Version, siehe connector.py::create_connector) propagierte
        # dadurch komplett an run_lint vorbei, unabhängig vom neuen
        # except-Exception-Handler.
        from tia_linter.connector import TiaConnectionError

        def _raise_connection_error(tia_version: int, dll_path: str) -> None:
            raise TiaConnectionError(f"Keine Connector-Implementierung für TIA Portal V{tia_version} vorhanden.")

        monkeypatch.setattr(runner, "create_connector", _raise_connection_error)

        report = runner.run_lint(
            dll_path="dummy.dll",
            tia_version=99,
            project_path="dummy.ap21",
            project_name="Dummy",
            tia_version_name="V99",
            checker_name="Tester",
            definitions=[_DUMMY_DEFINITION],
        )

        assert len(report.results) == 1
        result = report.results[0]
        assert result.check_id == "verbindung.reconnect"
        assert result.status == CheckStatus.ERROR
        assert "V99" in result.description

    def test_results_from_earlier_session_preserved_on_later_unexpected_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_project = object()
        first_result = CheckStatus.OK  # nur als Marker, siehe unten
        connectors = iter([FakeConnector(fake_project), FakeFailingConnector(RuntimeError("Session 2 kaputt"))])
        monkeypatch.setattr(runner, "create_connector", lambda tia_version, dll_path: next(connectors))
        monkeypatch.setattr(runner, "iter_plc_software", lambda project: iter([object()]))
        # Simuliert einen echten, spezifischen disposed-Exception-Typ (wie
        # EngineeringObjectDisposedException) -- ohne das würde die generische
        # Fallback-Erkennung (kein TIA Portal in dieser Testumgebung
        # installiert) jede Exception als "disposed" behandeln und über den
        # bereits bestehenden Reconnect-Pfad laufen statt über den neuen.
        monkeypatch.setattr(runner, "_disposed_exception_types", lambda: (ValueError,))

        class FakeCheck:
            def run(self, project: object) -> list:
                from tia_linter.models import CheckResult

                return [
                    CheckResult(
                        check_id="namenskonventionen.testvariablen",
                        check_name="Testvariablen",
                        category="Namenskonventionen",
                        status=first_result,
                        path="Dummy",
                        description="ok",
                        recommendation="",
                    )
                ]

        monkeypatch.setattr(runner, "_instantiate_check", lambda *args: FakeCheck())

        definition_1 = _DUMMY_DEFINITION
        definition_2 = CheckDefinition(
            check_id="namenskonventionen.fb_prefix",
            name="FB-Präfix",
            category="Namenskonventionen",
            enabled=True,
            severity=CheckSeverity.WARNING,
            description="",
            recommendation="",
            nummer="7",
        )

        report = runner.run_lint(
            dll_path="dummy.dll",
            tia_version=21,
            project_path="dummy.ap21",
            project_name="Dummy",
            tia_version_name="V21",
            checker_name="Tester",
            definitions=[definition_1, definition_2],
            reconnect_every_n_checks=1,  # erzwingt Reconnect nach dem ersten Check
        )

        # Der Fehlbefund aus Session 2 UND das Ergebnis von Check 1 aus
        # Session 1 müssen beide im Report stehen -- nichts geht verloren.
        check_ids = [r.check_id for r in report.results]
        assert "namenskonventionen.testvariablen" in check_ids
        assert "verbindung.reconnect" in check_ids
        error_result = next(r for r in report.results if r.check_id == "verbindung.reconnect")
        assert "Session 2 kaputt" in error_result.description


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
