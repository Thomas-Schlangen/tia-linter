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
import re
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from tia_linter.checks import comments, hardware, libraries, metadata, naming, structure
from tia_linter.checks._tia_helpers import (
    iter_plc_software,
    release_dotnet_objects,
    reset_export_cache,
    reset_xref_cache,
    set_export_cache_max_size,
    set_xref_cache_max_size,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.connector import create_connector
from tia_linter.models import CheckDefinition, CheckResult, CheckStatus, LintReport
from tia_linter.project_texts import ProjectTextComments

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

# Prüfpunkt 21 kompiliert das Projekt (einziger Check im gesamten Programm,
# der den Übersetzungsstand im TIA-Portal-Speicher verändert) — läuft daher
# fest als allerletzter Check eines Laufs, siehe ``run_lint``-Docstring und
# Review-General.md, Befund 3. Nicht konfigurierbar.
_KOMPILIERFEHLER_CHECK_ID = "metadata.kompilierfehler"


def _reset_run_caches(xml_cache_max_size: int, xref_cache_max_size: int) -> None:
    """Leert alle lauf-gebundenen Export-Caches (Block-XML + Projekttexte +
    CrossReference + Prüfpunkt-12a/12b-Zwischenspeicher) und setzt die
    LRU-Maxgrößen des XML- und CrossReference-Caches aus der Config.

    Muss einmalig zu Beginn jedes ``run_lint``-Aufrufs erfolgen, damit ein
    Cache nicht zwischen zwei unabhängigen Läufen in derselben GUI-Session
    "leakt". **Nicht** bei jedem Reconnect aufrufen (siehe
    ``Review-Performance.md``, Maßnahme 2/4): Anders als ursprünglich
    angenommen halten alle drei Caches ausschließlich Python-seitige Daten
    ohne .NET-Objektreferenzen — ``_export_cache`` einen geparsten
    ``ElementTree``, ``ProjectTextComments`` reine Strings, ``_xref_cache``
    extrahierte ``Access``/``ReferenceType``-Strings — die nach einem
    Reconnect weiterhin gültig sind. Ein zwischenzeitlich fehlgeschlagener
    Export/Import wird ohnehin **nie** gecacht (siehe ``export_block_xml``
    bzw. ``ProjectTextComments.load``), der ursprünglich genannte Grund für
    das Leeren bei jedem Reconnect ("erneuter Versuch nach Fehlschlag")
    trifft also nicht zu. Ein Reconnect mitten im Lauf leerte den XML-Cache
    dadurch bislang unnötig — bei einer Check-Reihenfolge, die XML-nutzende
    Prüfpunkte über mehrere Reconnect-Fenster verteilt, wurde derselbe
    Baustein dadurch mehrfach statt einmal pro Lauf exportiert. Siehe
    ``XML-Optimierung-Analysebericht.md``.
    """
    set_export_cache_max_size(xml_cache_max_size)
    reset_export_cache()
    set_xref_cache_max_size(xref_cache_max_size)
    reset_xref_cache()
    ProjectTextComments.reset_cache()
    structure.reset_pending_write_counts()


def _instantiate_check(
    definition: CheckDefinition,
    excluded_folders: frozenset[str],
    excluded_blocks: frozenset[str],
    gc_interval: int,
    enabled_check_ids: frozenset[str],
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
    return check_class(definition, excluded_folders, excluded_blocks, gc_interval, enabled_check_ids)


def _ok_result(definition: CheckDefinition, project_name: str) -> CheckResult:
    """Synthetischer OK-Befund für einen Prüfpunkt, der ohne einen einzigen
    Fehler/Warnung durchgelaufen ist.

    Checks melden nach dem etablierten Muster ausschließlich Verstöße — eine
    leere Ergebnisliste bedeutet "keine Verstöße gefunden", nicht "nichts
    geprüft". Ohne diesen expliziten OK-Eintrag stünde ein vollständig
    sauberer Prüfpunkt im Report/GUI-Summary nirgends, weder als Fehler/
    Warnung noch als OK — der `ok_count` in ``models.LintReport`` wäre dann
    unabhängig vom tatsächlichen Prüfergebnis praktisch immer 0.

    Betrifft nur Checks, die selbst nie eigene OK-Befunde liefern. Ein Check,
    der inhaltlich gar nichts prüfen konnte (fehlender Openness-Dienst,
    fehlende Konfiguration), liefert seit Review-General.md, Befund 2, dafür
    selbst einen expliziten ``CheckStatus.SKIPPED``-Befund statt einer leeren
    Liste — dieser Fallback hier greift dort also ebenfalls nicht (die
    zurückgelieferte Liste ist nicht leer)."""
    return CheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        status=CheckStatus.OK,
        path=project_name,
        description=f"Keine Verstöße gegen '{definition.name}' gefunden.",
        recommendation="Kein Handlungsbedarf.",
    )


def _disposed_exception_types() -> tuple[type, ...]:
    """Ermittelt die Exception-Typen, die eine komplett gestorbene
    Openness-Session anzeigen (siehe ``run_lint``-Docstring). Erfordert eine
    bereits geladene Openness-DLL — wird daher erst nach dem ersten
    erfolgreichen ``connector.connect()`` aufgerufen; ohne verfügbaren Typ
    (z. B. auf Systemen ohne TIA Portal) degradiert die Erkennung auf die
    generische ``Exception``, statt den Reconnect-Mechanismus ganz
    auszuschalten."""
    try:
        from Siemens.Engineering import EngineeringObjectDisposedException

        return (EngineeringObjectDisposedException,)
    except ImportError:
        return (Exception,)


# Exception-Typen, die typischerweise auf einen fehlerhaften
# Konfigurationsparameter zurückgehen (ungültige Regex, falscher Typ eines
# params-Werts) statt auf ein API-/Openness-Zugriffsproblem — siehe
# ``_check_failure_recommendation``/Review-Security-Robustheit.md, Befund
# 4.4. ``config.py``s eigener Validator (Maßnahme 3) fängt die meisten
# solcher Fälle bereits beim Config-Laden ab; diese Liste deckt Checks ab,
# deren Parameter nicht über die dort bekannten Schlüsselnamen laufen (z. B.
# numerische Parameter wie ``max_zeichen``, die bei einem YAML-String statt
# einer Zahl erst bei ``int(...)`` zur Check-Laufzeit auffallen).
_CONFIG_PARAM_ERROR_TYPES: tuple[type[Exception], ...] = (re.error, TypeError, ValueError)


def _check_failure_recommendation(exc: Exception) -> str:
    """Liefert den Empfehlungstext für einen fehlgeschlagenen Prüfpunkt,
    differenziert nach Exception-Typ (Review-Security-Robustheit.md, Befund
    4.4) — der bisherige, einheitliche Text ("Log-Datei prüfen — vermutlich
    ein API-Zugriffsproblem") war bei einem Konfigurationsfehler (z. B.
    einer ungültigen Regex oder einem Parameter im falschen Typ) schlicht
    falsch: Weder ist es ein API-Problem, noch hilft die Logdatei — der
    Anwender müsste stattdessen die YAML-Konfiguration dieses Prüfpunkts
    prüfen."""
    if isinstance(exc, _CONFIG_PARAM_ERROR_TYPES):
        return "Parameter dieses Prüfpunkts in der Konfigurationsdatei prüfen."
    return "Log-Datei prüfen — vermutlich ein API-Zugriffsproblem."


def _check_weight(check_id: str, check_weights: dict[str, int]) -> int:
    """Liefert das konfigurierte Reconnect-Gewicht eines Prüfpunkts (Maßnahme
    5, ``Review-Performance.md``, Befund 5.3): CrossReference-intensive
    Checks (11a/11b/12a/12b/13, siehe ``structure.py``) erzeugen pro
    verarbeitetem Tag/Baustein deutlich mehr .NET-Handles als ein
    durchschnittlicher Check — ein einheitliches "1 Check = 1 Einheit" beim
    Reconnect-Schwellenwert (``reconnect_every_n_checks``) lässt den
    Reconnect-Zeitpunkt dadurch zufällig danach richten, *wo* im Lauf gerade
    besonders teure Checks liegen, statt danach, wie viel tatsächlich
    verarbeitet wurde. Der konfigurierte Wert für den jeweiligen
    ``check_id`` gewinnt; ohne passenden Eintrag greift der Schlüssel
    ``"default"`` in ``check_weights`` (Standard 1), fehlt auch der, wird 1
    angenommen."""
    return check_weights.get(check_id, check_weights.get("default", 1))


def _run_session(
    project: Any,
    remaining: list[CheckDefinition],
    total_check_count: int,
    excluded_folders: frozenset[str],
    excluded_blocks: frozenset[str],
    resolved_project_name: str,
    reconnect_every_n_checks: int,
    gc_interval: int,
    check_weights: dict[str, int],
    enabled_check_ids: frozenset[str],
    cancel_event: threading.Event | None,
    disposed_exc_types: tuple[type, ...],
    report: ProgressFn,
    results: list[CheckResult],
    done_check_ids: set[str],
) -> bool:
    """Führt so viele der noch offenen Prüfpunkte (``remaining``) wie möglich
    innerhalb der aktuellen TIA-Portal-Session aus. Liefert ``True``, wenn der
    Nutzer die Prüfung während dieser Session abgebrochen hat.

    ``total_check_count`` ist die Gesamtzahl aller aktivierten Prüfpunkte des
    gesamten Laufs (nicht nur dieser Session) — der Fortschritt in der
    Statuszeile (Review-General.md, Befund 10c) zählt damit gegen das
    tatsächliche Gesamtziel (``len(done_check_ids) + 1``/``total_check_count``)
    statt gegen ``remaining`` (die Größe von ``remaining`` schrumpft nach
    jedem geplanten Reconnect, wodurch die Anzeige sonst z. B. von "10/42"
    unvermittelt auf "1/32" zurückspringt, obwohl der Lauf tatsächlich
    fortschreitet statt neu zu beginnen).

    ``results``/``done_check_ids`` werden direkt mutiert statt als eigener
    Rückgabewert kopiert — dadurch bleiben bereits abgeschlossene Checks
    dieser Session auch dann erhalten, wenn ein späterer Check die Session
    per disposed-Exception beendet: Diese Exception propagiert unverändert
    nach außen (siehe ``run_lint``-Docstring für die anschließende
    Reconnect-Logik), ohne dass die Ergebnisse der zuvor bereits
    abgeschlossenen Checks verloren gehen.

    Endet außerdem, wenn alle übergebenen Checks fertig sind (dann ohne
    Abbruch) oder wenn der geplante Reconnect-Schwellenwert
    (``reconnect_every_n_checks``) erreicht wird (ebenfalls ohne Abbruch —
    nur ein Session-Wechsel, siehe ``run_lint``-Docstring).

    ``checks_this_session`` zählt nicht mehr Checks 1:1, sondern gewichtet
    (siehe ``_check_weight``/``Review-Performance.md``, Maßnahme 5) — ein als
    besonders CrossReference-intensiv konfigurierter Prüfpunkt zählt mehrfach,
    wodurch der Reconnect-Schwellenwert bei einer Häufung solcher Checks
    (z. B. Prüfpunkte 11a-13, die alle direkt hintereinander in der Registry
    stehen) früher erreicht wird als bei einer reinen Check-Zählung.
    """
    checks_this_session = 0
    for index, definition in enumerate(remaining, start=1):
        if cancel_event is not None and cancel_event.is_set():
            report("Prüfung abgebrochen.")
            return True

        report(f"Prüfe {definition.name} ... {len(done_check_ids) + 1}/{total_check_count}")
        check = _instantiate_check(definition, excluded_folders, excluded_blocks, gc_interval, enabled_check_ids)
        if check is None:
            done_check_ids.add(definition.check_id)
        else:
            try:
                check_results = check.run(project)
                if not check_results:
                    check_results = [_ok_result(definition, resolved_project_name)]
                results.extend(check_results)
                done_check_ids.add(definition.check_id)
            except disposed_exc_types:
                # Session komplett gestorben — nicht als Fehler dieses einen
                # Checks werten, sondern an den äußeren Reconnect-Handler in
                # run_lint weiterreichen.
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
                        recommendation=_check_failure_recommendation(exc),
                    )
                )
                done_check_ids.add(definition.check_id)
            finally:
                release_dotnet_objects()

        checks_this_session += _check_weight(definition.check_id, check_weights)
        if checks_this_session >= reconnect_every_n_checks and index < len(remaining):
            return False  # geplanter Reconnect, siehe run_lint-Docstring — kein Abbruch, nur Session-Wechsel

    report("Prüfung abgeschlossen.")
    return False


def _run_connection_loop(
    dll_path: str,
    tia_version: int,
    project_path: str,
    tia_version_name: str,
    connect_message: str,
    definitions_to_run: list[CheckDefinition],
    total_check_count: int,
    excluded_folders_set: frozenset[str],
    excluded_blocks_set: frozenset[str],
    reconnect_every_n_checks: int,
    gc_interval: int,
    xml_cache_max_size: int,
    xref_cache_max_size: int,
    check_weights: dict[str, int],
    enabled_check_ids: frozenset[str],
    cancel_event: threading.Event | None,
    max_reconnect_attempts: int,
    check_plc_software: bool,
    report: ProgressFn,
    results: list[CheckResult],
    done_check_ids: set[str],
    resolved_project_name: str,
    disposed_exc_types: tuple[type, ...],
    session_number: int,
) -> tuple[str, tuple[type, ...], int, bool]:
    """Verbindet sich mit TIA Portal und arbeitet ``definitions_to_run`` ab —
    mit derselben Reconnect-/Wiederaufnahme-Logik wie zuvor direkt in
    ``run_lint`` (siehe dessen Docstring). Extrahiert, damit ``run_lint``
    (Review-General.md, Befund 3) diese Schleife zweimal aufrufen kann: einmal
    für alle Prüfpunkte außer Prüfpunkt 21, einmal — erst nachdem die erste
    vollständig und ohne Abbruch durchgelaufen ist — für Prüfpunkt 21 allein.

    ``session_number`` wird über beide Aufrufe hinweg fortgezählt (nicht pro
    Aufruf neu bei 0 gestartet) — dadurch bleibt ``check_plc_software``
    (übersetzt das bisherige ``if session_number == 1:``) exakt auf den
    allerersten Verbindungsaufbau des gesamten Laufs beschränkt, auch wenn er
    über zwei Aufrufe dieser Funktion verteilt ist: Der zweite Aufruf (für
    Prüfpunkt 21) übergibt dafür bewusst ``check_plc_software=False`` — ein
    Projekt ohne PLC-Software hätte den ersten Aufruf bereits beendet, ein
    erneuter Check wäre daher nur redundant.

    ``connect_message`` ersetzt die Meldung des allerersten
    Verbindungsaufbaus *dieses Aufrufs* (nicht jedes späteren, geplanten oder
    ausfallbedingten Reconnects innerhalb desselben Aufrufs — dafür gelten
    unverändert die bisherigen Meldungen), damit der Prüfpunkt-21-Aufruf sich
    im Log klar von der ursprünglichen Verbindung unterscheidet.

    Liefert ``(resolved_project_name, disposed_exc_types, session_number,
    cancelled)`` — alle vier müssen unverändert an einen eventuellen zweiten
    Aufruf weitergereicht werden.
    """
    consecutive_failures = 0
    cancelled = False
    first_session_of_call = True
    still_need_plc_check = check_plc_software

    while True:
        remaining = [d for d in definitions_to_run if d.check_id not in done_check_ids]
        if not remaining or cancelled:
            break

        session_number += 1
        try:
            connector = create_connector(tia_version, dll_path)
            if first_session_of_call:
                report(connect_message)
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
            first_session_of_call = False

            with connector:
                project = connector.connect(project_path)
                resolved_project_name = getattr(project, "Name", resolved_project_name)
                report(f"Projekt geöffnet: {resolved_project_name}")
                if still_need_plc_check:
                    _reset_run_caches(xml_cache_max_size, xref_cache_max_size)
                    still_need_plc_check = False
                    if not any(True for _ in iter_plc_software(project)):
                        report("Kein PLC-Programm im Projekt gefunden — Prüfung wird beendet.")
                        results.append(
                            CheckResult(
                                check_id="verbindung.keine_plc",
                                check_name="TIA-Portal-Verbindung",
                                category="Verbindung",
                                status=CheckStatus.ERROR,
                                path="Projekt",
                                description="Kein PLC-Programm im Projekt gefunden.",
                                recommendation="Prüfen, ob das richtige TIA-Projekt ausgewählt wurde.",
                            )
                        )
                        break

                if not disposed_exc_types:
                    disposed_exc_types = _disposed_exception_types()

                cancelled = _run_session(
                    project=project,
                    remaining=remaining,
                    total_check_count=total_check_count,
                    excluded_folders=excluded_folders_set,
                    excluded_blocks=excluded_blocks_set,
                    resolved_project_name=resolved_project_name,
                    reconnect_every_n_checks=reconnect_every_n_checks,
                    gc_interval=gc_interval,
                    check_weights=check_weights,
                    enabled_check_ids=enabled_check_ids,
                    cancel_event=cancel_event,
                    disposed_exc_types=disposed_exc_types,
                    report=report,
                    results=results,
                    done_check_ids=done_check_ids,
                )

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
        except Exception as exc:  # noqa: BLE001 — Review-Security-Robustheit.md, Befund 4.2/4.3
            # Fängt zwei Fälle ab, die bisher komplett an dieser Schleife
            # vorbei propagierten: (a) der allererste Verbindungsversuch
            # (disposed_exc_types ist dort noch das leere Tupel () — ein
            # except () fängt nichts, siehe 4.3), und (b) jede Exception in
            # einer späteren Session, die kein disposed_exc_types-Typ ist
            # (z. B. eine andere TIA-/.NET-Exception). Ohne diesen Handler
            # verlässt die Exception run_lint komplett, wodurch sämtliche
            # bereits gesammelten results verloren gehen — der Anwender sieht
            # nur noch "FEHLER: ..." im GUI-Log, aber nie die Ergebnisseite,
            # egal wie weit die Prüfung schon gekommen war. Stattdessen: wie
            # beim Erschöpfen der Reconnect-Versuche einen Fehlbefund anlegen
            # und den Lauf mit den bisherigen Ergebnissen sauber beenden.
            logger.exception("Unerwarteter Fehler bei der TIA-Portal-Verbindung.")
            results.append(
                CheckResult(
                    check_id="verbindung.reconnect",
                    check_name="TIA-Portal-Verbindung",
                    category="Verbindung",
                    status=CheckStatus.ERROR,
                    path=resolved_project_name,
                    description=f"TIA-Portal-Verbindung unerwartet fehlgeschlagen: {exc}",
                    recommendation="Log-Datei prüfen, TIA Portal manuell neu starten und Prüfung wiederholen.",
                )
            )
            break

    return resolved_project_name, disposed_exc_types, session_number, cancelled


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
    gc_interval: int = 200,
    xml_cache_max_size: int = 500,
    xref_cache_max_size: int = 1000,
    check_weights: dict[str, int] | None = None,
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

    Ein zusätzlicher, allgemeiner ``except Exception`` um dieselbe Session-
    Schleife fängt zwei Fälle ab, die vor diesem Sicherheitsnetz komplett an
    ``run_lint`` vorbei propagiert wären (Review-Security-Robustheit.md,
    Befund 4.2/4.3): den allerersten Verbindungsversuch (``disposed_exc_types``
    ist dort noch das leere Tupel, ein ``except ()`` fängt nichts) sowie jede
    Exception in einer späteren Session, die kein
    ``EngineeringObjectDisposedException`` ist. In beiden Fällen wird — wie
    beim Erschöpfen der Reconnect-Versuche — ein Fehlbefund für die
    Verbindung angelegt und der Lauf mit den bis dahin gesammelten
    Ergebnissen sauber beendet, statt sie komplett zu verlieren.

    Zusätzlich wird die Verbindung **proaktiv** alle ``reconnect_every_n_checks``
    Prüfpunkte neu aufgebaut (unabhängig davon, ob die Session tatsächlich
    stirbt). Grund: der erste Testlauf gegen ein echtes Projekt (288
    Bausteine) ist bei Check 31/40 mit
    ``EngineeringOutOfMemoryException: The maximum number (500000) of
    instances ... has been exceeded`` abgestürzt — TIA Portal Openness zählt
    offene Instanz-Handles (u. a. aus ``CrossReferenceService``-Ergebnissen
    und Baustein-Exports) pro Session und lässt sich durch erzwungene
    .NET-Garbage-Collection (``release_dotnet_objects``) *nicht* davon
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

    Direkt nach dem ersten erfolgreichen Verbindungsaufbau wird geprüft, ob
    das Projekt überhaupt eine PLC-Software enthält (``iter_plc_software``).
    Ohne diese Prüfung liefert **jeder** Check (der ausschließlich über
    ``iter_plc_software`` an seine Objekte gelangt) eine leere Ergebnisliste
    zurück — und die etablierte Konvention "leere Liste = keine Verstöße"
    (siehe ``_ok_result``) würde daraus 42 synthetische OK-Befunde machen (die
    Anzahl der Check-Definitionen in ``CHECK_REGISTRY``, nicht die Anzahl der
    Prüfpunkt-*Nummern* aus ``Pruefpunkte.md`` — einige Nummern wie 5/6/7
    decken zwei separat konfigurierbare Check-Einträge ab, siehe
    ``registry.py``).
    Ein HMI-only-Projekt, ein versehentlich falsch gewähltes Projekt, oder
    eine ``ausgeschlossene_ordner``-Konfiguration, die zufällig die gesamte
    PLC-Struktur trifft, sähe dadurch nicht wie "nichts geprüft", sondern
    wie ein vollständig sauberes Projekt aus — der für ein Prüfwerkzeug
    teuerste Fehlermodus (siehe ``Review-Security-Robustheit.md``, Befund
    3.3). Fehlt jede PLC-Software, wird stattdessen ein einzelner
    Fehlbefund (``verbindung.keine_plc``) erzeugt und der Lauf sofort
    beendet, ohne einen einzigen Check zu instanziieren.

    Prüfpunkt 21 (``metadata.kompilierfehler``, siehe
    ``_KOMPILIERFEHLER_CHECK_ID``) läuft — fest vorgegeben, nicht über die
    Config einstellbar — immer als **letzter** Check des gesamten Laufs
    (Review-General.md, Befund 3): Er ist der einzige Check im ganzen
    Programm, der den Übersetzungsstand des Projekts im TIA-Portal-Speicher
    tatsächlich verändert (``ICompilable.Compile()``, siehe
    ``metadata.py::KompilierfehlerCheck``) — alle anderen Checks lesen nur.
    Liefe er zwischen anderen Checks, könnte der lauf-gebundene XML-Cache
    (``_tia_helpers.export_block_xml``) danach einen anderen Übersetzungsstand
    zeigen als vor dem Compile, und nachfolgende Checks würden auf einem
    inkonsistenten Zwischenstand aufsetzen. Umsetzung: ``definitions`` wird
    in ``main_definitions`` (alles außer Prüfpunkt 21) und ``pp21_definition``
    aufgeteilt; ``_run_connection_loop`` läuft zunächst für
    ``main_definitions``, und — nur wenn diese vollständig und ohne Abbruch
    durchgelaufen sind (siehe unten) — ein zweites Mal für ``pp21_definition``
    allein. ``session_number`` wird dabei über beide Aufrufe hinweg
    fortgezählt, damit die PLC-Software-Prüfung/der Cache-Reset weiterhin nur
    beim allerersten Verbindungsaufbau des gesamten Laufs passiert (siehe
    ``_run_connection_loop``-Docstring). Das Projekt wird dabei nicht
    gespeichert — der Compile-Vorgang betrifft nur die offene, headless
    geöffnete Session.

    Der zweite Aufruf für Prüfpunkt 21 unterbleibt, wenn der erste Aufruf
    nicht vollständig erfolgreich war: bei einem Abbruch durch den Nutzer
    (``cancelled``), bei fehlender PLC-Software oder bei endgültig
    gescheiterter Verbindung (``verbindung.keine_plc``/``verbindung.reconnect``)
    bleiben in ``main_definitions`` offene Prüfpunkte übrig — in allen diesen
    Fällen ergäbe ein weiterer Verbindungsversuch nur für Prüfpunkt 21 keinen
    Sinn.
    """

    def report(message: str) -> None:
        logger.info(message)
        if progress is not None:
            progress(message)

    enabled = [d for d in definitions if d.enabled]
    enabled_check_ids = frozenset(d.check_id for d in enabled)
    main_definitions = [d for d in enabled if d.check_id != _KOMPILIERFEHLER_CHECK_ID]
    pp21_definition = next((d for d in enabled if d.check_id == _KOMPILIERFEHLER_CHECK_ID), None)

    check_weights = check_weights or {}
    excluded_folders_set = frozenset(excluded_folders)
    excluded_blocks_set = frozenset(excluded_blocks)
    results: list[CheckResult] = []
    done_check_ids: set[str] = set()
    resolved_project_name = project_name
    disposed_exc_types: tuple[type, ...] = ()
    session_number = 0

    # Ist außer Prüfpunkt 21 kein einziger Check aktiviert, bleibt
    # main_definitions leer — der erste Aufruf von _run_connection_loop
    # bricht dann sofort ohne jeden Verbindungsversuch ab (leere
    # "remaining"-Liste), die PLC-Software-Prüfung/der Cache-Reset (siehe
    # dortiger Docstring, "check_plc_software") müssen in diesem Sonderfall
    # also beim Prüfpunkt-21-Aufruf nachgeholt werden statt hier.
    main_check_plc_software = bool(main_definitions)

    resolved_project_name, disposed_exc_types, session_number, cancelled = _run_connection_loop(
        dll_path=dll_path,
        tia_version=tia_version,
        project_path=project_path,
        tia_version_name=tia_version_name,
        connect_message=f"Verbinde mit TIA Portal ({tia_version_name}) ...",
        definitions_to_run=main_definitions,
        total_check_count=len(enabled),
        excluded_folders_set=excluded_folders_set,
        excluded_blocks_set=excluded_blocks_set,
        reconnect_every_n_checks=reconnect_every_n_checks,
        gc_interval=gc_interval,
        xml_cache_max_size=xml_cache_max_size,
        xref_cache_max_size=xref_cache_max_size,
        check_weights=check_weights,
        enabled_check_ids=enabled_check_ids,
        cancel_event=cancel_event,
        max_reconnect_attempts=max_reconnect_attempts,
        check_plc_software=main_check_plc_software,
        report=report,
        results=results,
        done_check_ids=done_check_ids,
        resolved_project_name=resolved_project_name,
        disposed_exc_types=disposed_exc_types,
        session_number=session_number,
    )

    main_completed = not cancelled and all(d.check_id in done_check_ids for d in main_definitions)
    if pp21_definition is not None and main_completed:
        resolved_project_name, disposed_exc_types, session_number, cancelled = _run_connection_loop(
            dll_path=dll_path,
            tia_version=tia_version,
            project_path=project_path,
            tia_version_name=tia_version_name,
            connect_message="Verbinde für den abschließenden Prüfpunkt 21 (Kompilierfehler) ...",
            definitions_to_run=[pp21_definition],
            total_check_count=len(enabled),
            excluded_folders_set=excluded_folders_set,
            excluded_blocks_set=excluded_blocks_set,
            reconnect_every_n_checks=reconnect_every_n_checks,
            gc_interval=gc_interval,
            xml_cache_max_size=xml_cache_max_size,
            xref_cache_max_size=xref_cache_max_size,
            check_weights=check_weights,
            enabled_check_ids=enabled_check_ids,
            cancel_event=cancel_event,
            max_reconnect_attempts=max_reconnect_attempts,
            # Läuft main_check_plc_software bereits mit mindestens einem
            # anderen Check die PLC-Software-Prüfung durch, ist sie hier
            # überflüssig. Ist Prüfpunkt 21 dagegen der einzige aktivierte
            # Check überhaupt (main_definitions leer, main_check_plc_software
            # False), holt dieser Aufruf sie nach — siehe Kommentar oben.
            check_plc_software=not main_check_plc_software,
            report=report,
            results=results,
            done_check_ids=done_check_ids,
            resolved_project_name=resolved_project_name,
            disposed_exc_types=disposed_exc_types,
            session_number=session_number,
        )

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
    gc_interval: int = 200,
    xml_cache_max_size: int = 500,
    xref_cache_max_size: int = 1000,
    check_weights: dict[str, int] | None = None,
    excluded_folders: Iterable[str] = (),
    excluded_blocks: Iterable[str] = (),
) -> LintReport:
    """Simuliert einen Prüflauf: 5-10 zufällige Dummy-Befunde aus den
    aktivierten Prüfpunkten, mit realistischen Statuswerten und Pfaden.

    Nimmt dieselben Parameter wie ``run_lint`` entgegen (inkl. ``dll_path``/
    ``tia_version``/``max_reconnect_attempts``/``reconnect_every_n_checks``/
    ``gc_interval``/``xml_cache_max_size``/``xref_cache_max_size``/
    ``check_weights``/``excluded_folders``/``excluded_blocks``, hier
    ungenutzt), damit die GUI beide Funktionen ohne Anpassung gegeneinander
    austauschen kann. ``cancel_event`` erlaubt sauberes Abbrechen zwischen
    zwei Dummy-Checks.
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
