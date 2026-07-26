"""Prüfpunkte 17-18c: Hardware & Konfiguration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from tia_linter.checks._tia_helpers import (
    count_additional_hardware_modules,
    format_path,
    get_attribute,
    iter_plc_targets,
)
from tia_linter.checks.base import BaseCheck
from tia_linter.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class HardwareVorhandenCheck(BaseCheck):
    """Prüfpunkt 17: Hardware-Module für I/O-Tags vorhanden und aktiv.

    Vereinfachung: Eine belastbare Zuordnung "PLC-Tag-Adresse -> konkretes
    Hardware-Modul" erfordert Adressbereichs-Abgleich, dessen genaue
    Openness-Attribute (Baugruppen-Adresslänge je E/A-Bereich) in der
    allgemeinen Referenzdokumentation nicht eindeutig belegt sind. Als
    überprüfbarer Näherungswert wird stattdessen geprüft, ob die PLC
    überhaupt zusätzliche Hardware-Module (über die CPU hinaus) besitzt —
    eine PLC ganz ohne konfigurierte E/A-Module bei vorhandenen I/O-Tags im
    Programm ist in jedem Fall auffällig. ``device.DeviceItems`` enthält
    daneben immer strukturelle, von TIA selbst angelegte Elemente
    (Baugruppenträger, bei ET200SP zusätzlich Busadapter und
    Server-/Abschlussmodul) — ``count_additional_hardware_modules()``
    rechnet diese heraus, siehe dort für Details.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software, _device_item, device in iter_plc_targets(project):
            module_count = count_additional_hardware_modules(device)
            if module_count == 0:
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Hardwarekonfiguration"),
                        description=(
                            f"PLC '{plc_software.Name}' hat keine zusätzlichen Hardware-Module "
                            "konfiguriert (nur die CPU selbst)."
                        ),
                    )
                )
        return results


class CpuFirmwareDokumentiertCheck(BaseCheck):
    """Prüfpunkt 18a: CPU-Typ und Firmware-Version in den Projekteigenschaften."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software, device_item, _device in iter_plc_targets(project):
            order_number = str(get_attribute(device_item, "OrderNumber", "") or "").strip()
            firmware = str(get_attribute(device_item, "FirmwareVersion", "") or "").strip()
            missing = [
                label
                for label, value in (("CPU-Typ/Bestellnummer", order_number), ("Firmware-Version", firmware))
                if not value
            ]
            if missing:
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Hardwarekonfiguration"),
                        description=f"Nicht dokumentiert: {', '.join(missing)}.",
                    )
                )
        return results


class SafetyPasswortCheck(BaseCheck):
    """Prüfpunkt 18b: F-CPU ohne gesetztes Safety-Offline-Passwort.

    Review-General.md, Befund 2: Ist ``SafetyAdministration`` für eine PLC
    nicht verfügbar (keine F-CPU oder Safety-Feature nicht lizenziert), lief
    diese Schleife bislang stillschweigend weiter — eine PLC, die aus diesem
    Grund gar nicht geprüft werden konnte, war von einer PLC ohne Verstoß
    nicht zu unterscheiden. Meldet jetzt stattdessen einen expliziten
    ``CheckStatus.SKIPPED``-Befund je betroffener PLC."""

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        for plc_software, device_item, _device in iter_plc_targets(project):
            try:
                from Siemens.Engineering.Safety import SafetyAdministration

                safety_admin = device_item.GetService[SafetyAdministration]()
            except Exception:  # noqa: BLE001 — Service evtl. nicht verfügbar (keine F-CPU/keine Lizenz)
                logger.debug(
                    "SafetyAdministration nicht verfügbar für '%s' (keine F-CPU/keine Lizenz).",
                    plc_software.Name,
                    exc_info=True,
                )
                safety_admin = None

            if safety_admin is None:
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Sicherheitsprogramm"),
                        description=(
                            f"Sicherheitsfunktion (SafetyAdministration) für '{plc_software.Name}' "
                            "nicht verfügbar (keine F-CPU oder keine Lizenz) — Prüfpunkt übersprungen."
                        ),
                        status=CheckStatus.SKIPPED,
                    )
                )
                continue

            if not bool(getattr(safety_admin, "IsSafetyOfflineProgramPasswordSet", False)):
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Sicherheitsprogramm"),
                        description=f"F-CPU '{plc_software.Name}' hat kein Safety-Offline-Passwort gesetzt.",
                    )
                )
        return results


class ZertifikatCheck(BaseCheck):
    """Prüfpunkt 18c: Kommunikationszertifikat vorhanden und gültig.

    Der Status wird abweichend vom sonst üblichen Muster (konfigurierter
    Standard-Schweregrad aus ``definition.severity``) für jeden Fall explizit
    gesetzt (siehe Pruefpunkte.md, Prüfpunkt 18c):
    kein Zertifikat vorhanden -> ERROR, abgelaufen -> ERROR, läuft innerhalb
    der konfigurierten Restlaufzeit ab -> WARNING, sonst -> OK.

    Review-Security-Robustheit.md, Befund 3.2: Ist ``LocalCertificateManager``
    für ein ``DeviceItem`` nicht verfügbar, wurde bislang trotzdem
    weitergelaufen — ``getattr(None, "LocalCertificateStore", None)`` ergab
    ``[]``, was denselben Zweig wie "kein Zertifikat vorhanden" traf und
    fälschlich ``CheckStatus.ERROR`` meldete, obwohl der Dienst schlicht
    nicht geprüft werden konnte. Analog zu ``SafetyPasswortCheck`` (drei
    Klassen weiter oben in dieser Datei) wird ein fehlender Dienst jetzt
    nicht mehr als Befund gewertet.

    Review-General.md, Befund 2: Der Fix zu 3.2 hat den fehlenden Dienst
    zunächst komplett stillschweigend übersprungen (leere Ergebnisliste) —
    ``runner._ok_result`` machte daraus dann ein grünes "keine Verstöße
    gefunden", obwohl der Zertifikatsdienst gar nicht geprüft werden konnte.
    Meldet jetzt stattdessen einen expliziten ``CheckStatus.SKIPPED``-Befund
    je betroffener PLC.
    """

    def run(self, project: Any) -> list[CheckResult]:
        results: list[CheckResult] = []
        min_months = int(self.definition.params.get("min_restlaufzeit_monate", 6))

        for plc_software, device_item, _device in iter_plc_targets(project):
            try:
                from Siemens.Engineering.Security import LocalCertificateManager

                cert_manager = device_item.GetService[LocalCertificateManager]()
            except Exception:  # noqa: BLE001 — Service evtl. nicht verfügbar
                logger.debug(
                    "LocalCertificateManager nicht verfügbar für '%s'.",
                    plc_software.Name,
                    exc_info=True,
                )
                cert_manager = None

            if cert_manager is None:
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Zertifikate"),
                        description=(
                            f"Zertifikatsdienst (LocalCertificateManager) für '{plc_software.Name}' "
                            "nicht verfügbar/lizenziert — Prüfpunkt übersprungen."
                        ),
                        status=CheckStatus.SKIPPED,
                    )
                )
                continue

            certificates = list(getattr(getattr(cert_manager, "LocalCertificateStore", None), "Certificates", []) or [])
            if not certificates:
                results.append(
                    self._make_result(
                        path=format_path(plc_software.Name, "Zertifikate"),
                        description=f"Kein Kommunikationszertifikat für '{plc_software.Name}' vorhanden.",
                        status=CheckStatus.ERROR,
                    )
                )
                continue

            threshold = datetime.now() + timedelta(days=30 * min_months)
            for cert in certificates:
                valid_until = getattr(cert, "ValidUntil", None)
                if valid_until is None:
                    continue
                cert_path = format_path(plc_software.Name, "Zertifikate", str(getattr(cert, "Id", "?")))
                valid_until_dt = datetime(valid_until.Year, valid_until.Month, valid_until.Day)
                if valid_until_dt < datetime.now():
                    results.append(
                        self._make_result(
                            path=cert_path,
                            description="Zertifikat ist abgelaufen.",
                            status=CheckStatus.ERROR,
                            value=valid_until_dt.isoformat(),
                        )
                    )
                elif valid_until_dt < threshold:
                    results.append(
                        self._make_result(
                            path=cert_path,
                            description=(
                                f"Zertifikat läuft bald ab (gültig bis {valid_until_dt.date()}, "
                                f"Schwellenwert {min_months} Monate)."
                            ),
                            status=CheckStatus.WARNING,
                            value=valid_until_dt.isoformat(),
                        )
                    )
                else:
                    results.append(
                        self._make_result(
                            path=cert_path,
                            description=f"Zertifikat ist gültig (gültig bis {valid_until_dt.date()}).",
                            status=CheckStatus.OK,
                            value=valid_until_dt.isoformat(),
                        )
                    )
        return results


CHECK_CLASSES = {
    "hardware.hardware_vorhanden": HardwareVorhandenCheck,
    "hardware.cpu_firmware_dokumentiert": CpuFirmwareDokumentiertCheck,
    "hardware.safety_passwort": SafetyPasswortCheck,
    "hardware.zertifikat": ZertifikatCheck,
}
