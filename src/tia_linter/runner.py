"""Orchestriert die Ausführung aller aktivierten Prüfpunkte.

``simulate_lint_run`` erzeugt einen LintReport mit Dummy-Befunden ohne
TIA-Verbindung — für Entwicklung/Test der GUI und des PDF-Reports auf
Systemen ohne TIA Portal. Die reale Prüfung gegen ein TIA-Projekt
(``run_lint``, mit ``TiaConnector`` und den ``checks/*.py``-Modulen) wird in
einem späteren Schritt ergänzt, sobald sie unter Windows getestet werden kann.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable, Iterable
from datetime import datetime

from tia_linter.models import CheckDefinition, CheckResult, CheckStatus, LintReport

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str], None]

_DUMMY_PATH_TEMPLATES = [
    "PLC_1 > Variablentabellen > Tags_Eingaenge > {name}",
    "PLC_1 > Programmbausteine > {name}",
    "PLC_1 > Programmbausteine > {name} > Netzwerk {n}",
    "PLC_1 > Datenbaustein > {name} > Member > Wert",
    "Projekt > Eigenschaften > {name}",
]

_STATUS_WEIGHTS = {CheckStatus.ERROR: 0.25, CheckStatus.WARNING: 0.45, CheckStatus.OK: 0.30}


def simulate_lint_run(
    dll_path: str,
    project_path: str,
    project_name: str,
    tia_version_name: str,
    checker_name: str,
    definitions: Iterable[CheckDefinition],
    progress: ProgressFn | None = None,
    cancel_event: threading.Event | None = None,
) -> LintReport:
    """Simuliert einen Prüflauf: 5-10 zufällige Dummy-Befunde aus den
    aktivierten Prüfpunkten, mit realistischen Statuswerten und Pfaden.

    Nimmt dieselben Parameter wie das spätere ``run_lint`` entgegen (inkl.
    ``dll_path``, hier ungenutzt), damit die GUI beide Funktionen ohne
    Anpassung gegeneinander austauschen kann. ``cancel_event`` erlaubt
    sauberes Abbrechen zwischen zwei Dummy-Checks.
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
