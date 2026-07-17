"""Orchestriert die Ausführung aller aktivierten Prüfpunkte.

``simulate_lint_run`` erzeugt einen LintReport mit Dummy-Befunden ohne
TIA-Verbindung — für Entwicklung/Test der GUI und des PDF-Reports auf
Systemen ohne TIA Portal. ``run_lint`` führt die echte Prüfung gegen ein
TIA-Projekt aus (``TiaConnector`` + ``checks/*.py``) — vollständig
implementiert, aber noch nicht gegen ein echtes TIA-Portal-Projekt getestet
(siehe README, "Bekannte Einschränkungen"). ``main.py`` verwendet in dieser
Session weiterhin ``simulate_lint_run``.

``run_lint`` enthält außerdem eine Reconnect-Logik, übernommen aus
``tia-tag-exporter`` (dort in ``main.py::run_export``, nicht in dessen
``connector.py`` — Letzteres enthält wie bei uns nur Connect/Disconnect ohne
Retry-Wissen). Hintergrund: TIA Portal V19 hat sich im Tag Exporter
wiederholt nicht-deterministisch als instabil erwiesen — die
Openness-Session kann mitten in der Verarbeitung sterben
(``EngineeringObjectDisposedException``, alle Objekte dieser Session sind
dann disposed; ein Retry auf derselben Session hilft nicht mehr). Anders als
im Tag Exporter (der ganze PLC/DB/HMI-Extraktionsblöcke retried) ist die
Wiederaufnahme-Granularität hier der einzelne Prüfpunkt: bereits
abgeschlossene Checks (erfolgreich oder mit eigenem Fehlerbefund) werden bei
einem Reconnect nicht wiederholt.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime

from tia_linter.checks import comments, hardware, libraries, metadata, naming, structure
from tia_linter.checks.base import BaseCheck
from tia_linter.connector import create_connector
from tia_linter.models import CheckDefinition, CheckResult, CheckStatus, LintReport

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str], None]

# check_id-Präfix (Kategorie-Key aus der YAML-Config) -> Modul mit den
# konkreten Check-Klassen dieser Kategorie (siehe jeweiliges CHECK_CLASSES).
_CHECK_MODULES = {
    "kommentare": comments,
    "namenskonventionen": naming,
    "programmstruktur": structure,
    "hardware": hardware,
    "projektmetadaten": metadata,
    "bibliotheken": libraries,
    "styleguide": libraries,
}

_DUMMY_PATH_TEMPLATES = [
    "PLC_1 > Variablentabellen > Tags_Eingaenge > {name}",
    "PLC_1 > Programmbausteine > {name}",
    "PLC_1 > Programmbausteine > {name} > Netzwerk {n}",
    "PLC_1 > Datenbaustein > {name} > Member > Wert",
    "Projekt > Eigenschaften > {name}",
]

_STATUS_WEIGHTS = {CheckStatus.ERROR: 0.25, CheckStatus.WARNING: 0.45, CheckStatus.OK: 0.30}


def _instantiate_check(definition: CheckDefinition) -> BaseCheck | None:
    category_key = definition.check_id.split(".", 1)[0]
    module = _CHECK_MODULES.get(category_key)
    if module is None:
        logger.warning("Keine Check-Module für Kategorie '%s' gefunden.", category_key)
        return None
    check_class = module.CHECK_CLASSES.get(definition.check_id)
    if check_class is None:
        logger.warning("Keine Check-Klasse für '%s' gefunden — wird übersprungen.", definition.check_id)
        return None
    return check_class(definition)


def run_lint(
    dll_path: str,
    tia_version: int,
    project_path: str,
    project_name: str,
    tia_version_name: str,
    checker_name: str,
    definitions: Iterable[CheckDefinition],
    progress: ProgressFn | None = None,
    cancel_event: threading.Event | None = None,
    max_reconnect_attempts: int = 3,
) -> LintReport:
    """Führt alle aktivierten Prüfpunkte gegen das echte TIA-Projekt unter
    ``project_path`` aus (headless, über ``TiaConnector``).

    Ein einzelner fehlschlagender Check bricht die Prüfung nicht ab — er wird
    als Fehlerbefund für genau diesen Prüfpunkt aufgenommen, die übrigen
    Checks laufen weiter (analog zum Tag Exporter: robust gegen einzelne
    API-Zugriffsprobleme).

    Stirbt die Openness-Session dagegen komplett
    (``EngineeringObjectDisposedException``), wird bis zu
    ``max_reconnect_attempts``-mal neu verbunden und die Prüfung bei den noch
    nicht abgeschlossenen Prüfpunkten fortgesetzt — bereits gelaufene Checks
    (erfolgreich oder mit eigenem Fehlerbefund) werden dabei nicht wiederholt.
    Schlägt auch der letzte Versuch fehl, wird ein Fehlerbefund für die
    Verbindung selbst aufgenommen und die Prüfung mit den bis dahin
    gesammelten Ergebnissen beendet. Noch nicht gegen ein echtes
    TIA-Projekt getestet.
    """

    def report(message: str) -> None:
        logger.info(message)
        if progress is not None:
            progress(message)

    enabled = [d for d in definitions if d.enabled]
    results: list[CheckResult] = []
    done_check_ids: set[str] = set()
    resolved_project_name = project_name
    disposed_exc_types: tuple[type, ...] = ()

    for attempt in range(1, max_reconnect_attempts + 1):
        remaining = [d for d in enabled if d.check_id not in done_check_ids]

        connector = create_connector(tia_version, dll_path)
        try:
            if attempt == 1:
                report(f"Verbinde mit TIA Portal ({tia_version_name}) ...")
            else:
                report(
                    f"TIA-Portal-Session unerwartet beendet — verbinde neu "
                    f"(Versuch {attempt}/{max_reconnect_attempts}) ..."
                )

            with connector:
                project = connector.connect(project_path)
                resolved_project_name = getattr(project, "Name", project_name)
                report(f"Projekt geöffnet: {resolved_project_name}")

                if not disposed_exc_types:
                    try:
                        from Siemens.Engineering import EngineeringObjectDisposedException

                        disposed_exc_types = (EngineeringObjectDisposedException,)
                    except ImportError:
                        disposed_exc_types = (Exception,)

                for index, definition in enumerate(remaining, start=1):
                    if cancel_event is not None and cancel_event.is_set():
                        report("Prüfung abgebrochen.")
                        break

                    report(f"Prüfe {definition.name} ... {index}/{len(remaining)}")
                    check = _instantiate_check(definition)
                    if check is None:
                        done_check_ids.add(definition.check_id)
                        continue
                    try:
                        results.extend(check.run(project))
                        done_check_ids.add(definition.check_id)
                    except disposed_exc_types:
                        # Session komplett gestorben — nicht als Fehler dieses
                        # einen Checks werten, sondern an den äußeren
                        # Reconnect-Handler weiterreichen (siehe unten).
                        raise
                    except Exception as exc:  # noqa: BLE001 — ein Check darf die gesamte Prüfung nicht abbrechen
                        logger.exception("Fehler bei Prüfpunkt %s", definition.check_id)
                        results.append(
                            CheckResult(
                                check_id=definition.check_id,
                                check_name=definition.name,
                                category=definition.category,
                                status=CheckStatus.ERROR,
                                path=resolved_project_name,
                                description=f"Prüfpunkt konnte nicht ausgeführt werden: {exc}",
                                recommendation="Log-Datei prüfen — vermutlich ein API-Zugriffsproblem.",
                            )
                        )
                        done_check_ids.add(definition.check_id)
                else:
                    report("Prüfung abgeschlossen.")
            break  # with-Block ohne Session-Abbruch durchlaufen (regulär fertig oder abgebrochen) -> keine weiteren Versuche
        except disposed_exc_types as exc:
            if attempt == max_reconnect_attempts:
                logger.error(
                    "TIA-Portal-Verbindung nach %d Versuchen weiterhin instabil: %s",
                    max_reconnect_attempts,
                    exc,
                )
                results.append(
                    CheckResult(
                        check_id="verbindung.reconnect",
                        check_name="TIA-Portal-Verbindung",
                        category="Verbindung",
                        status=CheckStatus.ERROR,
                        path=resolved_project_name,
                        description=(
                            f"TIA-Portal-Verbindung nach {max_reconnect_attempts} Versuchen "
                            f"weiterhin instabil: {exc}"
                        ),
                        recommendation="Log-Datei prüfen, TIA Portal manuell neu starten und Prüfung wiederholen.",
                    )
                )
                break
            logger.warning("TIA-Portal-Session unerwartet beendet (Versuch %d): %s", attempt, exc)

    return LintReport(
        project_name=resolved_project_name,
        project_path=str(project_path),
        tia_version=tia_version_name,
        check_date=datetime.now(),
        checker_name=checker_name,
        results=results,
    )


def simulate_lint_run(
    dll_path: str,
    tia_version: int,
    project_path: str,
    project_name: str,
    tia_version_name: str,
    checker_name: str,
    definitions: Iterable[CheckDefinition],
    progress: ProgressFn | None = None,
    cancel_event: threading.Event | None = None,
    max_reconnect_attempts: int = 3,
) -> LintReport:
    """Simuliert einen Prüflauf: 5-10 zufällige Dummy-Befunde aus den
    aktivierten Prüfpunkten, mit realistischen Statuswerten und Pfaden.

    Nimmt dieselben Parameter wie ``run_lint`` entgegen (inkl. ``dll_path``/
    ``tia_version``/``max_reconnect_attempts``, hier ungenutzt), damit die
    GUI beide Funktionen ohne Anpassung gegeneinander austauschen kann.
    ``cancel_event`` erlaubt sauberes Abbrechen zwischen zwei Dummy-Checks.
    """

    def report(message: str) -> None:
        logger.info(message)
        if progress is not None:
            progress(message)

    enabled = [d for d in definitions if d.enabled]
    if not enabled:
        report("Keine Prüfpunkte aktiviert — nichts zu prüfen.")
        return LintReport(
            project_name=project_name,
            project_path=project_path,
            tia_version=tia_version_name,
            check_date=datetime.now(),
            checker_name=checker_name,
            results=[],
        )

    report("Verbinde mit TIA Portal (simuliert) ...")
    time.sleep(0.3)

    sample_size = min(len(enabled), random.randint(5, 10))
    sampled = random.sample(enabled, sample_size)

    results: list[CheckResult] = []
    for index, definition in enumerate(sampled, start=1):
        if cancel_event is not None and cancel_event.is_set():
            report("Prüfung abgebrochen.")
            break

        report(f"Prüfe {definition.name} ... {index}/{len(sampled)}")
        time.sleep(0.15)

        status = random.choices(
            list(_STATUS_WEIGHTS.keys()), weights=list(_STATUS_WEIGHTS.values())
        )[0]
        dummy_name = f"Dummy_{definition.check_id.split('.')[-1]}"
        template = random.choice(_DUMMY_PATH_TEMPLATES)
        path = template.format(name=dummy_name, n=random.randint(1, 20))
        description = (
            "Kein Verstoß gefunden (simuliert)."
            if status == CheckStatus.OK
            else f"Simulierter Verstoß gegen Prüfpunkt '{definition.name}'."
        )
        results.append(
            CheckResult(
                check_id=definition.check_id,
                check_name=definition.name,
                category=definition.category,
                status=status,
                path=path,
                description=description,
                recommendation=definition.recommendation,
                value=dummy_name if status != CheckStatus.OK else None,
            )
        )
    else:
        report("Simulierte Prüfung abgeschlossen.")

    return LintReport(
        project_name=project_name,
        project_path=project_path,
        tia_version=tia_version_name,
        check_date=datetime.now(),
        checker_name=checker_name,
        results=results,
    )
