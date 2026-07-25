"""Liest DB-Variablen-Kommentare aus der zentralen TIA-Portal-Projekttexte-Verwaltung.

Übernommen und angepasst aus ``tia-tag-exporter`` (HMI-Teil entfernt — der
Linter prüft in dieser Version nur PLC-Software, siehe
Programm-Anforderungen.md, "Entschiedene Punkte").

``Siemens.Engineering.SW.Blocks.Interface.Member`` (DB-Variablen) hat über
Openness kein ``Comment``-Attribut — live erschöpfend verifiziert über alle
Member-Typen eines realen Projekts (siehe Tag-Exporter, docs/setup-notes.md).
Die Kommentare existieren aber sehr wohl im Projekt: TIA Portal verwaltet sie
zentral unter "Sprachen & Ressourcen > Projekttexte", exportierbar über
``Project.ExportProjectTexts()``. Dieses Modul exportiert die Projekttexte
einmalig in eine temporäre Excel-Datei und baut daraus eine
Nachschlage-Tabelle für DB-Variablen-Kommentare (Kategorie
``<BlockCommentCategoryData>``, ``ViewPath`` wie
``{Projekt}\\{PLC}\\Programmbausteine\\...\\{DB-Name}\\{Membername}``).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BLOCK_COMMENT_CATEGORY = "<BlockCommentCategoryData>"


class ProjectTextComments:
    """Nachschlage-Tabelle für DB-Variablen-Kommentare aus den Projekttexten."""

    _cache: "ProjectTextComments | None" = None

    def __init__(self) -> None:
        self._comments: dict[tuple[str, str, str], str] = {}

    @classmethod
    def reset_cache(cls) -> None:
        """Leert den lauf-gebundenen Cache von ``load()``.

        Siehe ``XML-Optimierung-Analysebericht.md`` (Option B/C) sowie
        ``_tia_helpers.reset_export_cache`` für dasselbe Muster beim
        Block-XML-Export: ``load()`` wird von drei Prüfpunkten (1a, 1b, 1c)
        pro PLC-Software unabhängig aufgerufen, exportiert dabei aber stets
        die komplette, projektweite Projekttexte-Tabelle neu. Muss von
        ``runner.py`` zu Beginn jedes Lint-Laufs sowie nach jedem
        TIA-Portal-Reconnect aufgerufen werden — aus denselben Gründen wie
        bei ``reset_export_cache`` (kein Leak zwischen zwei Läufen, erneuter
        Versuch nach einem zwischenzeitlich fehlgeschlagenen Export, da nach
        einem Reconnect ein neues ``project``-.NET-Objekt vorliegt).
        """
        cls._cache = None

    @classmethod
    def load(cls, project: Any) -> "ProjectTextComments":
        """Exportiert die Projekttexte einmalig pro Lauf und baut die
        Nachschlage-Tabelle auf (siehe ``reset_cache``).

        Schlägt der Export oder das Einlesen fehl, wird eine leere Instanz
        zurückgegeben — DB-Variablen-Kommentare gelten dann als nicht
        vorhanden, statt die gesamte Prüfung abzubrechen. Eine fehlgeschlagene
        Instanz wird bewusst nicht gecacht, damit der nächste Aufruf erneut
        versucht zu exportieren.
        """
        if cls._cache is not None:
            return cls._cache

        instance = cls()
        try:
            instance._load_from_project(project)
            cls._cache = instance
        except Exception as exc:  # noqa: BLE001 — .NET-/openpyxl-Fehler, Prüfung soll trotzdem weiterlaufen
            logger.warning(
                "Projekttexte konnten nicht gelesen werden, DB-Variablen-Kommentare gelten als fehlend: %s",
                exc,
            )
        return instance

    def _load_from_project(self, project: Any) -> None:
        import openpyxl
        from System.IO import FileInfo

        language = project.LanguageSettings.ReferenceLanguage.Culture

        with tempfile.TemporaryDirectory() as tmp_dir:
            export_path = Path(tmp_dir) / "project_texts.xlsx"
            project.ExportProjectTexts(FileInfo(str(export_path)), language, language)

            workbook = openpyxl.load_workbook(export_path, read_only=True, data_only=True)
            try:
                sheet = workbook["User Texts"]
                rows = sheet.iter_rows(values_only=True)
                header = next(rows)
                category_idx = header.index("Category")
                view_path_idx = header.index("ViewPath")
                lang_col_indices = [
                    i for i, name in enumerate(header) if isinstance(name, str) and str(language.Name) in name
                ]

                for row in rows:
                    if row[category_idx] != _BLOCK_COMMENT_CATEGORY:
                        continue
                    view_path = row[view_path_idx]
                    if not view_path:
                        continue
                    text = next((row[i] for i in lang_col_indices if row[i]), None)
                    if not text:
                        continue

                    segments = view_path.split("\\")
                    if len(segments) < 3:
                        continue
                    plc_name = segments[1]
                    db_name = segments[-2]
                    member_path = segments[-1]
                    self._comments[(plc_name, db_name, member_path)] = text
            finally:
                workbook.close()

        logger.info("%d DB-Variablen-Kommentare aus Projekttexten geladen", len(self._comments))

    def get(self, plc_name: str, db_name: str, member_path: str) -> str | None:
        """Liefert den Kommentar für ``plc_name``/``db_name``/``member_path``
        (Punktnotation bei verschachtelten Membern), oder ``None`` falls keiner
        hinterlegt ist."""
        return self._comments.get((plc_name, db_name, member_path))
