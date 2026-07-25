"""Abstrakte Basisklasse für alle Prüfpunkt-Checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from tia_linter.models import CheckDefinition, CheckResult, CheckStatus


class BaseCheck(ABC):
    """Ein Check kapselt die Prüflogik für genau einen Prüfpunkt.

    ``definition`` liefert die Konfiguration (enabled, severity, Parameter)
    aus der YAML-Config; ``run`` erhält das geöffnete TIA-Openness-Projekt
    und liefert eine Liste von Befunden (leer, wenn alles in Ordnung ist).

    ``excluded_folders``/``excluded_blocks`` kommen aus den globalen
    Config-Schlüsseln ``ausgeschlossene_ordner``/``ausgeschlossene_bausteine``
    (nicht aus ``definition.params`` — gelten projektweit für alle Checks,
    nicht nur für einen einzelnen Prüfpunkt). Checks, die Bausteine/DBs/
    Variablentabellen rekursiv durchlaufen, reichen diese Sets an die
    entsprechenden ``iter_*``-Hilfsfunktionen aus ``_tia_helpers.py`` weiter.

    ``gc_interval`` kommt aus dem globalen Config-Schlüssel ``gc_interval``
    (Standard 200) — Checks mit projektweiten CrossReference-Schleifen
    (Prüfpunkte 11a/11b/12a/12b/13, siehe ``structure.py``) rufen alle
    ``gc_interval`` verarbeitete Objekte zusätzlich
    ``_tia_helpers.release_dotnet_objects()`` auf, um bei sehr großen
    Projekten das .NET-Handle-Limit nicht innerhalb eines einzelnen Checks zu
    reißen (siehe ``Review-Performance.md``, Maßnahme 1).

    ``enabled_check_ids`` enthält die ``check_id``s aller für diesen Lauf
    aktivierten Prüfpunkte (nicht nur die eigene) — ermöglicht Checks, die
    dieselben, teuren Rohdaten wie ein anderer Prüfpunkt benötigen, zu
    erkennen, ob sich ein gemeinsamer Durchlauf lohnt (aktuell genutzt von
    Prüfpunkt 12a/12b, siehe ``structure.py::EingaengeGelesenCheck``/
    ``Review-Performance.md``, Maßnahme 3). Checks, die das nicht brauchen,
    ignorieren dieses Attribut einfach.
    """

    def __init__(
        self,
        definition: CheckDefinition,
        excluded_folders: frozenset[str] = frozenset(),
        excluded_blocks: frozenset[str] = frozenset(),
        gc_interval: int = 200,
        enabled_check_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.definition = definition
        self.excluded_folders = excluded_folders
        self.excluded_blocks = excluded_blocks
        self.gc_interval = gc_interval
        self.enabled_check_ids = enabled_check_ids

    @abstractmethod
    def run(self, project: Any) -> list[CheckResult]:
        """Führt den Prüfpunkt aus. ``project`` = TIA Openness Project-Objekt."""
        ...

    def _make_result(
        self,
        path: str,
        description: str,
        status: CheckStatus | None = None,
        value: str | None = None,
    ) -> CheckResult:
        """Baut ein CheckResult für einen Verstoß gegen diesen Prüfpunkt.

        ``status`` ist optional — ohne Angabe wird der in der Config
        hinterlegte Standard-Schweregrad (``definition.severity``) verwendet.
        """
        return CheckResult(
            check_id=self.definition.check_id,
            check_name=self.definition.name,
            category=self.definition.category,
            status=status or self.definition.severity.as_status(),
            path=path,
            description=description,
            recommendation=self.definition.recommendation,
            value=value,
        )
