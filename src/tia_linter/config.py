"""YAML-Konfiguration laden, validieren und in CheckDefinition-Objekte übersetzen."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from config_loader import load_config
from my_logger import LoggingConfig

from tia_linter.checks.registry import CHECK_REGISTRY
from tia_linter.models import CheckDefinition, CheckSeverity


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
            "default": 1,
        }
    )
    ausgeschlossene_ordner: list[str] = Field(default_factory=list)
    ausgeschlossene_bausteine: list[str] = Field(default_factory=list)


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
