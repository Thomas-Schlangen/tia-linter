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


def _release_dotnet_objects() -> None:
    """Erzwingt eine .NET-Garbage-Collection nach jedem Check.

    Beim ersten Testlauf gegen ein echtes Projekt (288 Bausteine) ist
    ``run_lint`` bei Check 31/40 mit
    ``Siemens.Engineering.EngineeringOutOfMemoryException: The maximum
    number (500000) of instances for this TIA-Portal has been exceeded``
    abgestürzt — außerhalb der Per-Check-Fehlerisolation, da die Exception
    tief in pythonnet selbst auftrat. Ursache: TIA Portal Openness zählt
    intern offene Instanz-Handles (RCW-gewrappte Engineering-Objekte, z. B.
    aus ``CrossReferenceService``-Ergebnisbäumen oder Baustein-Exports) pro
    Session und wirft ab diesem harten Limit die Exception — Pythons eigenes
    Referenzcounting reicht nicht, die zugrunde liegenden .NET-Objekte werden
    erst bei einem tatsächlichen .NET-GC-Lauf freigegeben, den ein langer
    Headless-Prozess von sich aus zu selten auslöst, um mit der Anzahl der
    pro Check erzeugten Objekte Schritt zu halten. Deshalb wird nach jedem
    einzelnen Check eine .NET-GC erzwungen, um den Instanzzähler regelmäßig
    zurückzusetzen statt ihn über den ganzen Lauf anwachsen zu lassen.
    """
    try:
        from System import GC

        GC.Collect()
        GC.WaitForPendingFinalizers()
        GC.Collect()
    except Exception:  # noqa: BLE001 — reine Aufräum-Maßnahme, darf den Lauf nicht gefährden
        logger.debug("GC.Collect() fehlgeschlagen (evtl. kein .NET-Kontext) — ignoriert.", exc_info=True)


def _instantiate_check(
    definition: CheckDefinition, excluded_folders: frozenset[str], excluded_blocks: frozenset[str]
) -> BaseCheck | None:
    category_key = definition.check_id.split(".", 1)[0]
    module = _CHECK_MODULES.get(category_key)
    if module is None:
        logger.warning("Keine Check-Module für Kategorie '%s' gefunden.", category_key)
        return None
    check_class = module.CHECK_CLASSES.get(definition.check_id)
    if check_class is None:
        logger.warning("Keine Check-Klasse für '%s' gefunden — wird übersprungen.", definition.check_id)
        return None
    return check_class(definition, excluded_folders, excluded_blocks)


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
    reconnect_every_n_checks: int = 10,
    excluded_folders: Iterable[str] = (),
    excluded_blocks: Iterable[str] = (),
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
    gesammelten Ergebnissen beendet.

    Zusätzlich wird die Verbindung **proaktiv** alle ``reconnect_every_n_checks``
    Prüfpunkte neu aufgebaut (unabhängig davon, ob die Session tatsächlich
    stirbt). Grund: der erste Testlauf gegen ein echtes Projekt (288
    Bausteine) ist bei Check 31/40 mit
    ``EngineeringOutOfMemoryException: The maximum number (500000) of
    instances ... has been exceeded`` abgestürzt — TIA Portal Openness zählt
    offene Instanz-Handles (u. a. aus ``CrossReferenceService``-Ergebnissen
    und Baustein-Exports) pro Session und lässt sich durch erzwungene
    .NET-Garbage-Collection (``_release_dotnet_objects``) *nicht* davon
    abbringen, den Zähler hochzuzählen — ein zweiter Testlauf mit GC nach
    jedem Check ist an exakt derselben Stelle abgestürzt. Ein periodischer
    Reconnect umgeht das Problem zuverlässig, weil er den Zähler der ganzen
    Session (nicht nur einzelner Objekte) zurücksetzt; die bestehende
    Wiederaufnahme-Logik (``done_check_ids``) sorgt dafür, dass dabei kein
    Check doppelt läuft. Ein planmäßiger Reconnect zählt nicht gegen
    ``max_reconnect_attempts`` — nur eine tatsächlich gestorbene Session tut
    das.

    ``excluded_folders``/``excluded_blocks`` kommen aus den globalen
    Config-Schlüsseln ``ausgeschlossene_ordner``/``ausgeschlossene_bausteine``
    und werden unverändert an jeden instanziierten Check weitergereicht
    (siehe ``BaseCheck``) — Bausteine/DBs/Variablentabellen in einem
    passenden Ordner (samt aller Unterordner) bzw. Bausteine mit passendem
    Namen (unabhängig vom Ordner) werden dadurch von allen Checks
    übersprungen, die Bausteinstrukturen durchlaufen.
    """

    def report(message: str) -> None:
        logger.info(message)
        if progress is not None:
            progress(message)

    enabled = [d for d in definitions if d.enabled]
    excluded_folders_set = frozenset(excluded_folders)
    excluded_blocks_set = frozenset(excluded_blocks)
    results: list[CheckResult] = []
    done_check_ids: set[str] = set()
    resolved_project_name = project_name
    disposed_exc_types: tuple[type, ...] = ()
    consecutive_failures = 0
    session_number = 0
    cancelled = False

    while True:
        remaining = [d for d in enabled if d.check_id not in done_check_ids]
        if not remaining or cancelled:
            break

        session_number += 1
        connector = create_connector(tia_version, dll_path)
        try:
            if session_number == 1:
                report(f"Verbinde mit TIA Portal ({tia_version_name}) ...")
            elif consecutive_failures > 0:
                report(
                    f"TIA-Portal-Session unerwartet beendet — verbinde neu "
                    f"(Versuch {consecutive_failures + 1}/{max_reconnect_attempts}) ..."
                )
            else:
                report(
                    f"Verbinde nach {reconnect_every_n_checks} Prüfpunkten vorsorglich neu, "
                    "um die TIA-Portal-Session zu entlasten ..."
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

                checks_this_session = 0
                for index, definition in enumerate(remaining, start=1):
                    if cancel_event is not None and cancel_event.is_set():
                        report("Prüfung abgebrochen.")
                        cancelled = True
                        break

                    report(f"Prüfe {definition.name} ... {index}/{len(remaining)}")
                    check = _instantiate_check(definition, excluded_folders_set, excluded_blocks_set)
                    if check is None:
                        done_check_ids.add(definition.check_id)
                    else:
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
                        finally:
                            _release_dotnet_objects()

                    checks_this_session += 1
                    if checks_this_session >= reconnect_every_n_checks and index < len(remaining):
                        break  # geplanter Reconnect, siehe Docstring — kein "Abbruch", nur Session-Wechsel
                else:
                    report("Prüfung abgeschlossen.")

            consecutive_failures = 0  # Session ohne Absturz beendet (fertig, geplanter Reconnect oder Abbruch)
        except disposed_exc_types as exc:
            consecutive_failures += 1
            if consecutive_failures >= max_reconnect_attempts:
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
            logger.warning("TIA-Portal-Session unerwartet beendet (Versuch %d): %s", consecutive_failures, exc)

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
    reconnect_every_n_checks: int = 10,
    excluded_folders: Iterable[str] = (),
    excluded_blocks: Iterable[str] = (),
) -> LintReport:
    """Simuliert einen Prüflauf: 5-10 zufällige Dummy-Befunde aus den
    aktivierten Prüfpunkten, mit realistischen Statuswerten und Pfaden.

    Nimmt dieselben Parameter wie ``run_lint`` entgegen (inkl. ``dll_path``/
    ``tia_version``/``max_reconnect_attempts``/``reconnect_every_n_checks``/
    ``excluded_folders``/``excluded_blocks``, hier ungenutzt), damit die GUI
    beide Funktionen ohne Anpassung gegeneinander austauschen kann.
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
