"""Persistente GUI-Einstellungen (settings.json) — zuletzt verwendete Pfade,
TIA-Version und Fenstergeometrie."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS_PATH = Path("settings.json")
DEFAULT_WINDOW_GEOMETRY = "1200x800+100+100"


@dataclass
class Settings:
    last_project_path: str = ""
    last_output_folder: str = ""
    last_config_path: str = ""
    last_tia_version: str = ""
    window_geometry: str = DEFAULT_WINDOW_GEOMETRY
    test_mode: bool = False

    @classmethod
    def load(cls, path: str | Path = DEFAULT_SETTINGS_PATH) -> "Settings":
        """Lädt die Einstellungen aus ``path``. Liefert Standardwerte, wenn die
        Datei fehlt oder beschädigt ist — Settings sind nie kritisch fürs
        Starten der Anwendung."""
        path = Path(path)
        if not path.is_file():
            return cls()

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("settings.json konnte nicht gelesen werden, verwende Standardwerte: %s", exc)
            return cls()

        known_fields = {field for field in cls.__dataclass_fields__}
        filtered = {key: value for key, value in raw.items() if key in known_fields}
        return cls(**filtered)

    def save(self, path: str | Path = DEFAULT_SETTINGS_PATH) -> None:
        """Speichert die Einstellungen nach ``path``. Fehler beim Schreiben
        werden geloggt, aber nicht weitergeworfen — ein Speicherfehler bei den
        Einstellungen soll die Anwendung nicht zum Absturz bringen."""
        path = Path(path)
        try:
            path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            logger.warning("settings.json konnte nicht gespeichert werden: %s", exc)
