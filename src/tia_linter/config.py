"""YAML-Konfiguration laden, validieren und in CheckDefinition-Objekte übersetzen."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from config_loader import load_config
from my_logger import LoggingConfig

from tia_linter.checks.registry import CHECK_REGISTRY
from tia_linter.models import CheckDefinition, CheckSeverity

# Prüfpunkt-Parameter, deren erwarteter Typ projektweit einheitlich ist,
# unabhängig vom jeweiligen Prüfpunkt (siehe Review-Security-Robustheit.md,
# Befund 2.1) — alle Aufrufstellen siehe checks/comments.py, naming.py,
# structure.py, metadata.py, libraries.py.
_LIST_PARAM_KEYS = frozenset(
    {
        "ausnahme_prefixe",
        "ausnahme_variables",
        "ausnahme_udts",
        "dokumentations_hinweise",
        "ignorierte_meldungen",
        "prefixe",
        "felder",
    }
)
_REGEX_PARAM_KEYS = frozenset({"regex", "ausnahme_titel_regex"})


class ReportConfig(BaseModel):
    """Angaben für das Deckblatt des PDF-Reports."""

    pruefer: str = ""
    firma: str = ""
    logo_pfad: str = ""


class TiaVersionEntry(BaseModel):
    """Ein wählbarer TIA-Portal-Versionseintrag samt DLL-Pfad."""

    name: str
    version: int
    dll_pfad: str


class TiaVersionenConfig(BaseModel):
    """Liste der in der GUI wählbaren TIA-Portal-Versionen samt der als
    Standard vorausgewählten (``standard`` referenziert einen ``name`` aus
    ``verfuegbar``)."""

    verfuegbar: list[TiaVersionEntry]
    standard: str

    def default_entry(self) -> TiaVersionEntry:
        for entry in self.verfuegbar:
            if entry.name == self.standard:
                return entry
        return self.verfuegbar[0]

    def find(self, name: str) -> TiaVersionEntry | None:
        return next((entry for entry in self.verfuegbar if entry.name == name), None)


class CheckEntryConfig(BaseModel):
    """Konfiguration eines einzelnen Prüfpunkts aus der YAML-Datei.

    ``enabled``/``severity`` sind fest, alle weiteren Schlüssel (Regex,
    Schwellenwerte, Listen, ...) sind je Prüfpunkt unterschiedlich und werden
    unverändert als ``params`` an den Check weitergereicht.
    """

    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    severity: CheckSeverity = CheckSeverity.WARNING


class AppConfig(BaseModel):
    """Wurzelschema der YAML-Konfiguration (siehe ``config/*.yaml``) — validiert
    über ``load_app_config`` und in ``CheckDefinition``-Objekte übersetzt über
    ``build_check_definitions``."""

    tia_versionen: TiaVersionenConfig
    report: ReportConfig = ReportConfig()
    checks: dict[str, dict[str, CheckEntryConfig]]
    logging: LoggingConfig = LoggingConfig()
    max_reconnect_attempts: int = Field(default=3, ge=1)
    reconnect_every_n_checks: int = Field(default=10, ge=1)
    gc_interval: int = Field(default=200, ge=1)
    xml_cache_max_size: int = Field(default=500, ge=1)
    xref_cache_max_size: int = Field(default=1000, ge=1)
    check_weights: dict[str, int] = Field(
        default_factory=lambda: {
            "programmstruktur.unbenutzte_variablen": 5,
            "programmstruktur.unbenutzte_bausteine": 5,
            "programmstruktur.eingaenge_gelesen": 3,
            "programmstruktur.eingaenge_nicht_beschrieben": 3,
            "programmstruktur.ausgaenge_mehrfach_schreiben": 3,
            "metadata.kompilierfehler": 10,
            "default": 1,
        }
    )
    ausgeschlossene_ordner: list[str] = Field(default_factory=list)
    ausgeschlossene_bausteine: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_check_params(self) -> "AppConfig":
        """Validiert die frei-formen Prüfpunkt-Parameter (``CheckEntryConfig``
        erlaubt via ``extra="allow"`` beliebige zusätzliche YAML-Schlüssel,
        siehe dortiger Docstring) gegen den projektweit einheitlichen Typ der
        bekannten Parameternamen (siehe ``_LIST_PARAM_KEYS``/
        ``_REGEX_PARAM_KEYS``).

        Ohne diese Prüfung kippt ein Tippfehler wie ``prefixe: TEST`` (statt
        ``prefixe: [TEST]``) ein Prüfergebnis lautlos: ``tuple("TEST")``
        ergibt ``('T', 'E', 'S', 'T')``, und Prüfpunkt 9 meldet danach jede
        Variable, die mit T, E oder S beginnt, als Testvariable — ohne
        Exception, ohne Logeintrag (Review-Security-Robustheit.md, Befund
        2.1, empirisch verifiziert). Ein ungültiger regulärer Ausdruck
        (Befund 2.2) fiele sonst erst zur Check-Laufzeit auf, nachdem TIA
        Portal bereits gestartet und ggf. lange geprüft wurde — hier wird er
        beim Config-Laden erkannt, also in Millisekunden und vor jedem
        TIA-Verbindungsaufbau.

        Sammelt alle Verstöße über alle Prüfpunkte hinweg in einer einzigen
        Fehlermeldung, statt beim ersten Treffer abzubrechen — bei mehreren
        Tippfehlern in derselben Config muss der Anwender sie sonst einzeln
        nacheinander entdecken."""
        errors: list[str] = []
        for category_key, entries in self.checks.items():
            for check_key, entry in entries.items():
                check_ref = f"{category_key}.{check_key}"
                params = entry.model_dump(exclude={"enabled", "severity"})
                for key in sorted(_LIST_PARAM_KEYS & params.keys()):
                    if not isinstance(params[key], list):
                        errors.append(
                            f"{check_ref}.{key}: erwartet eine Liste, "
                            f"erhalten {type(params[key]).__name__} ({params[key]!r})"
                        )
                for key in sorted(_REGEX_PARAM_KEYS & params.keys()):
                    value = params[key]
                    if not isinstance(value, str):
                        errors.append(
                            f"{check_ref}.{key}: erwartet einen String (regulärer Ausdruck), "
                            f"erhalten {type(value).__name__} ({value!r})"
                        )
                        continue
                    if not value:
                        continue  # leerer String bedeutet je Prüfpunkt "deaktiviert", kein Fehler
                    try:
                        re.compile(value)
                    except re.error as exc:
                        errors.append(f"{check_ref}.{key}: ungültiger regulärer Ausdruck '{value}': {exc}")
        if errors:
            raise ValueError("Ungültige Prüfpunkt-Parameter in der Konfiguration:\n- " + "\n- ".join(errors))
        return self


def load_app_config(path: str | Path) -> AppConfig:
    """Lädt und validiert die YAML-Konfigurationsdatei unter ``path``."""
    return load_config(path, AppConfig)


def build_check_definitions(config: AppConfig) -> list[CheckDefinition]:
    """Verknüpft die konfigurierbaren Werte (enabled/severity/Parameter) aus
    ``config.checks`` mit den festen Metadaten (Name, Kategorie, Beschreibung,
    Empfehlung) aus ``CHECK_REGISTRY`` und liefert eine flache Liste aller
    CheckDefinitions in Registry-Reihenfolge.

    Unbekannte Config-Keys (z. B. Tippfehler) werden ignoriert; Prüfpunkte aus
    der Registry, die in der Config fehlen, werden übersprungen.
    """
    definitions: list[CheckDefinition] = []
    for check_id, meta in CHECK_REGISTRY.items():
        category_key, check_key = check_id.split(".", 1)
        entry = config.checks.get(category_key, {}).get(check_key)
        if entry is None:
            continue
        params = entry.model_dump(exclude={"enabled", "severity"})
        definitions.append(
            CheckDefinition(
                check_id=check_id,
                name=meta.name,
                category=meta.category,
                enabled=entry.enabled,
                severity=entry.severity,
                description=meta.description,
                recommendation=meta.recommendation,
                nummer=meta.nummer,
                params=params,
            )
        )
    return definitions
