"""Verbindung zur TIA Portal Openness API über pythonnet.

Aus ``tia-tag-exporter`` übernommen (dort bereits gegen ein echtes V21-Projekt
getestet, siehe dessen README) und für den Linter um eine abstrakte
``BaseTiaConnector``-Basisklasse mit einer konkreten Implementierung pro
TIA-Portal-Version erweitert. Aktuell nur ``TiaConnectorV21`` — spätere
Versionen (V22, V23, ...) werden durch Ergänzen einer weiteren
``TiaConnectorVNN``-Klasse und eines Eintrags in ``_CONNECTORS``
unterstützt, ohne bestehenden Code zu ändern.
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from types import TracebackType
from typing import Any

logger = logging.getLogger(__name__)


class TiaConnectionError(RuntimeError):
    """Wird ausgelöst, wenn die Verbindung zu TIA Portal fehlschlägt."""


# Ab TIA Portal V21 ist die Openness API nicht mehr eine einzelne
# "Siemens.Engineering.dll", sondern in mehrere Assemblies im selben
# net48-Ordner aufgeteilt (siehe Openness-API-V21-Aenderungen.md). "Base"
# enthält TiaPortal/TiaPortalMode und muss zuerst geladen werden, die
# übrigen liefern PLC- (Step7) bzw. HMI-Zugriff.
_V21_ASSEMBLIES = (
    "Siemens.Engineering.Base",
    "Siemens.Engineering.Step7",
    "Siemens.Engineering.WinCC",
    "Siemens.Engineering.WinCCUnified",
)


class BaseTiaConnector(ABC):
    """Gemeinsame Verbindungslogik (DLLs laden, Projekt öffnen/schließen) für
    alle TIA-Portal-Versionen. Konkrete Unterklassen legen nur fest, welche
    Assemblies zusätzlich zur Basis-DLL geladen werden müssen."""

    def __init__(self, dll_path: str | Path) -> None:
        self.dll_path = Path(dll_path)
        self._tia_portal = None
        self._project = None
        self._clr_loaded = False

    @property
    @abstractmethod
    def _assembly_names(self) -> tuple[str, ...]:
        """Namen der im selben Ordner wie ``dll_path`` liegenden Assemblies,
        die zusätzlich geladen werden müssen (``dll_path`` selbst wird
        implizit über ``clr.AddReference`` beim Import von ``Siemens.Engineering``
        aufgelöst, sobald der Ordner in ``sys.path`` steht)."""
        ...

    def _load_dll(self) -> None:
        if self._clr_loaded:
            return

        if not self.dll_path.is_file():
            raise TiaConnectionError(f"Openness-Assembly wurde unter '{self.dll_path}' nicht gefunden.")

        import clr  # pythonnet

        assembly_dir = self.dll_path.parent
        # Review-General.md, Befund 10f: ``_clr_loaded`` ist instanzgebunden,
        # ``run_lint`` erzeugt aber pro TIA-Portal-Session einen neuen
        # Connector (siehe ``create_connector``) — ohne diese Prüfung würde
        # derselbe Pfad bei jedem (geplanten oder ausfallbedingten) Reconnect
        # erneut angehängt.
        if str(assembly_dir) not in sys.path:
            sys.path.append(str(assembly_dir))

        for assembly_name in self._assembly_names:
            assembly_path = assembly_dir / f"{assembly_name}.dll"
            if not assembly_path.is_file():
                logger.warning(
                    "Optionale Openness-Assembly nicht gefunden, wird übersprungen: %s", assembly_path
                )
                continue
            clr.AddReference(assembly_name)
            logger.debug("Assembly geladen: %s", assembly_path)

        self._clr_loaded = True

    def connect(self, project_path: str | Path) -> Any:
        """Öffnet ein TIA-Portal-Projekt (headless) und gibt das Projekt-Objekt
        zurück (``Siemens.Engineering.Project`` — .NET-Typ, daher ``Any``)."""
        project_path = Path(project_path)
        if not project_path.is_file():
            raise TiaConnectionError(f"Projektdatei nicht gefunden: {project_path}")

        self._load_dll()

        from Siemens.Engineering import TiaPortal, TiaPortalMode  # noqa: E402
        from System.IO import FileInfo  # noqa: E402

        logger.info("Öffne TIA Portal (Headless) für Projekt: %s", project_path)
        self._tia_portal = TiaPortal(TiaPortalMode.WithoutUserInterface)

        try:
            self._project = self._tia_portal.Projects.Open(FileInfo(str(project_path)))
        except Exception as exc:  # noqa: BLE001 — Openness wirft .NET-Exceptions
            self.disconnect()
            raise TiaConnectionError(f"Projekt konnte nicht geöffnet werden: {exc}") from exc

        logger.info("Projekt erfolgreich geöffnet: %s", self._project.Name)
        return self._project

    def disconnect(self) -> None:
        """Schließt das Projekt und beendet die TIA-Portal-Instanz."""
        if self._project is not None:
            try:
                self._project.Close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fehler beim Schließen des Projekts: %s", exc)
            self._project = None

        if self._tia_portal is not None:
            try:
                self._tia_portal.Dispose()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fehler beim Beenden von TIA Portal: %s", exc)
            self._tia_portal = None

    def __enter__(self) -> "BaseTiaConnector":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.disconnect()

    @property
    def project(self) -> Any:
        """Das aktuell geöffnete Projekt-Objekt (``Siemens.Engineering.Project``
        — .NET-Typ, daher ``Any``), oder ``None`` außerhalb einer Verbindung."""
        return self._project


class TiaConnectorV21(BaseTiaConnector):
    """Connector für TIA Portal V21 (Split-DLL-Layout unter
    ``PublicAPI\\V21\\net48``, ``dll_path`` zeigt auf
    ``Siemens.Engineering.Base.dll``)."""

    @property
    def _assembly_names(self) -> tuple[str, ...]:
        return _V21_ASSEMBLIES


_CONNECTORS: dict[int, type[BaseTiaConnector]] = {
    21: TiaConnectorV21,
}


def create_connector(version: int, dll_path: str | Path) -> BaseTiaConnector:
    """Factory: liefert den passenden Connector für die gewählte TIA-Version
    (``version`` aus ``tia_versionen.verfuegbar[].version`` in der Config).

    Neue Versionen werden unterstützt, indem eine weitere
    ``TiaConnectorVNN``-Klasse ergänzt und hier in ``_CONNECTORS`` eingetragen
    wird — Config und GUI benötigen dafür keine Anpassung.
    """
    connector_class = _CONNECTORS.get(version)
    if connector_class is None:
        raise TiaConnectionError(f"Keine Connector-Implementierung für TIA Portal V{version} vorhanden.")
    return connector_class(dll_path)
