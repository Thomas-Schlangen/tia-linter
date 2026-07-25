"""PDF-Lintreport (DIN A4) mit reportlab."""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path
from typing import Callable

import yaml
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from tia_linter.checks.registry import CHECK_REGISTRY
from tia_linter.config import AppConfig
from tia_linter.models import CheckResult, CheckStatus, LintReport

logger = logging.getLogger(__name__)

# Präfix des synthetischen Fehlerbefunds aus ``runner.py::run_lint``, wenn ein
# Check selbst (technisch) fehlschlägt (z. B. API-Zugriffsproblem) — im
# Unterschied zu einem regulären Fehlerbefund, der einen echten Verstoß gegen
# den Prüfpunkt meldet. Dient in der Übersichtstabelle zur Unterscheidung von
# "durchgeführt, aber nicht erfolgreich" gegenüber "durchgeführt, Verstoß(e)
# gefunden".
_CHECK_FAILED_PREFIX = "Prüfpunkt konnte nicht ausgeführt werden"

# Schriftgröße des ``TiaCode``-Stils (Anhang A) — muss mit der dortigen
# ParagraphStyle-Definition übereinstimmen (siehe ``PdfReporter.__init__``).
_CODE_FONT_SIZE = 7.5
_CODE_CONTENT_WIDTH_PT = A4[0] - 2 * 18 * mm
# Zeichen, die bei ``_CODE_FONT_SIZE`` sicher in die Seitenbreite passen —
# ``Courier`` ist ein Festbreitenschrift, ein einzelnes Zeichen liefert daher
# die Breite jedes Zeichens. Ein PyYAML-``width``-Ziel (siehe
# ``_YAML_DUMP_WIDTH``) verhindert lange Zeilen meist schon beim Dump, ist
# aber nur ein Soft-Limit (PyYAML bricht nur an Leerzeichen um) — einzelne
# unteilbare Tokens wie Windows-Pfade oder Regex-Muster können es dennoch
# überschreiten. ``_hard_wrap`` (siehe unten) bricht solche Zeilen zusätzlich
# hart um, damit ``Preformatted`` (das selbst nicht umbricht) nichts über den
# Seitenrand hinaus zeichnet.
_CODE_MAX_CHARS = int(_CODE_CONTENT_WIDTH_PT / stringWidth("0", "Courier", _CODE_FONT_SIZE)) - 2
_YAML_DUMP_WIDTH = _CODE_MAX_CHARS


def _hard_wrap(text: str, max_chars: int) -> str:
    """Letzte Sicherheitsnetz-Zeilenumbruch-Instanz für Anhang A: PyYAMLs
    ``width`` bricht nur an Leerzeichen um, längere unteilbare Tokens (Pfade,
    Regex) bleiben dadurch ggf. trotzdem zu lang für die Seitenbreite. Jede
    noch zu lange Zeile wird hier zusätzlich hart umgebrochen, mit
    Fortsetzungszeilen um 2 Zeichen weiter eingerückt als die Originalzeile."""
    out_lines: list[str] = []
    for line in text.split("\n"):
        if len(line) <= max_chars:
            out_lines.append(line)
            continue
        indent = len(line) - len(line.lstrip(" "))
        out_lines.extend(
            textwrap.wrap(
                line,
                width=max_chars,
                initial_indent="",
                subsequent_indent=" " * (indent + 2),
                break_long_words=True,
                break_on_hyphens=False,
            )
        )
    return "\n".join(out_lines)

COLOR_ERROR = colors.HexColor("#FF4444")
COLOR_WARNING = colors.HexColor("#FFA500")
COLOR_OK = colors.HexColor("#44AA44")
COLOR_HEADER_BG = colors.HexColor("#2F3B52")

_STATUS_LABEL = {
    CheckStatus.ERROR: "Fehler",
    CheckStatus.WARNING: "Warnung",
    CheckStatus.OK: "OK",
}
_STATUS_COLOR = {
    CheckStatus.ERROR: COLOR_ERROR,
    CheckStatus.WARNING: COLOR_WARNING,
    CheckStatus.OK: COLOR_OK,
}


def report_filename(report: LintReport) -> str:
    """Erzeugt den Dateinamen ``Lintreport_{projekt}_{datum}_{uhrzeit}.pdf``."""
    timestamp = report.check_date.strftime("%Y-%m-%d_%H-%M")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in report.project_name)
    return f"Lintreport_{safe_name}_{timestamp}.pdf"


class PdfReporter:
    """Erzeugt den PDF-Lintreport aus einem ``LintReport``."""

    def __init__(self, app_config: AppConfig) -> None:
        self._app_config = app_config
        self._report_config = app_config.report
        self._styles = getSampleStyleSheet()
        self._styles.add(
            ParagraphStyle(
                name="TiaTitle",
                parent=self._styles["Title"],
                fontSize=26,
                spaceAfter=6 * mm,
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="TiaCoverLine",
                parent=self._styles["Normal"],
                fontSize=12,
                leading=18,
                alignment=TA_CENTER,
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="TiaCategoryHeading",
                parent=self._styles["Heading2"],
                spaceBefore=8 * mm,
                spaceAfter=3 * mm,
                textColor=COLOR_HEADER_BG,
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="TiaCell",
                parent=self._styles["Normal"],
                fontSize=8.5,
                leading=11,
            )
        )
        self._styles.add(
            ParagraphStyle(
                name="TiaCode",
                parent=self._styles["Normal"],
                fontName="Courier",
                fontSize=7.5,
                leading=9,
            )
        )

    def generate(self, report: LintReport, output_path: str | Path) -> Path:
        """Schreibt den vollständigen PDF-Report. ``output_path`` kann eine
        Datei oder ein Ordner sein — bei einem Ordner wird der Dateiname
        automatisch generiert (siehe ``report_filename``)."""
        output_path = Path(output_path)
        if output_path.is_dir():
            output_path = output_path / report_filename(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            title=f"Lintreport {report.project_name}",
        )

        story: list = []
        story.extend(self._build_cover_page(report))
        story.append(PageBreak())
        story.extend(self._build_overview_page(report))
        story.append(PageBreak())
        story.extend(self._build_summary_page(report))
        story.append(PageBreak())
        story.extend(self._build_detail_pages(report))
        story.append(PageBreak())
        story.extend(self._build_appendix_a())

        footer = self._make_footer(report.project_name)
        doc.build(story, onFirstPage=footer, onLaterPages=footer)

        logger.info("PDF-Report geschrieben: %s", output_path)
        return output_path

    # -- Deckblatt -----------------------------------------------------

    def _build_cover_page(self, report: LintReport) -> list:
        cfg = self._report_config
        lines = [
            Spacer(1, 50 * mm),
            Paragraph("TIA Linter — Prüfbericht", self._styles["TiaTitle"]),
            Spacer(1, 10 * mm),
            Paragraph(report.project_name, self._styles["TiaCoverLine"]),
            Paragraph(f"TIA-Portal-Version: {report.tia_version}", self._styles["TiaCoverLine"]),
            Paragraph(
                f"Prüfdatum: {report.check_date.strftime('%d.%m.%Y %H:%M')}",
                self._styles["TiaCoverLine"],
            ),
        ]
        pruefer = cfg.pruefer or report.checker_name
        if pruefer:
            lines.append(Paragraph(f"Prüfer: {pruefer}", self._styles["TiaCoverLine"]))
        if cfg.firma:
            lines.append(Paragraph(f"Firma: {cfg.firma}", self._styles["TiaCoverLine"]))
        return lines

    # -- Prüfpunkte-Übersicht --------------------------------------------

    def _build_overview_page(self, report: LintReport) -> list:
        """Tabelle mit allen im Linter bekannten Prüfpunkten (nicht nur den
        durchgeführten) — zeigt auf einen Blick, welche Prüfpunkte überhaupt
        gelaufen sind, ob sie technisch erfolgreich durchgelaufen sind (im
        Unterschied zu einem inhaltlichen Verstoß, den ein Prüfpunkt meldet),
        sowie die Anzahl Fehler/Warnungen je Prüfpunkt."""
        story: list = [Paragraph("Prüfpunkte-Übersicht", self._styles["Heading1"]), Spacer(1, 4 * mm)]

        by_check_id: dict[str, list[CheckResult]] = {}
        for result in report.results:
            by_check_id.setdefault(result.check_id, []).append(result)

        header = ["Nr", "Prüfpunkt", "Kategorie", "Durchgeführt", "Erfolgreich", "Fehler", "Warn."]
        rows: list[list] = [header]
        row_kinds: list[str] = ["header"]  # "ok" | "not_run" | "failed", parallel zu rows[1:]

        durchgefuehrt_count = 0
        erfolgreich_count = 0
        fehler_total = 0
        warnungen_total = 0

        for check_id, meta in CHECK_REGISTRY.items():
            results = by_check_id.get(check_id, [])
            durchgefuehrt = bool(results)
            fehlgeschlagen = any(
                r.status == CheckStatus.ERROR and r.description.startswith(_CHECK_FAILED_PREFIX) for r in results
            )
            erfolgreich = durchgefuehrt and not fehlgeschlagen
            fehler = sum(1 for r in results if r.status == CheckStatus.ERROR)
            warnungen = sum(1 for r in results if r.status == CheckStatus.WARNING)

            if durchgefuehrt:
                durchgefuehrt_count += 1
                fehler_total += fehler
                warnungen_total += warnungen
            if erfolgreich:
                erfolgreich_count += 1

            rows.append(
                [
                    meta.nummer,
                    Paragraph(meta.name, self._styles["TiaCell"]),
                    Paragraph(meta.category, self._styles["TiaCell"]),
                    "Ja" if durchgefuehrt else "Nein",
                    ("Ja" if erfolgreich else "Nein") if durchgefuehrt else "-",
                    str(fehler) if durchgefuehrt else "-",
                    str(warnungen) if durchgefuehrt else "-",
                ]
            )
            row_kinds.append("failed" if (durchgefuehrt and not erfolgreich) else ("ok" if durchgefuehrt else "not_run"))

        rows.append(
            [
                "",
                "Gesamt",
                "",
                f"{durchgefuehrt_count}/{len(CHECK_REGISTRY)}",
                str(erfolgreich_count),
                str(fehler_total),
                str(warnungen_total),
            ]
        )
        row_kinds.append("total")

        table = Table(
            rows,
            colWidths=[12 * mm, 55 * mm, 40 * mm, 22 * mm, 22 * mm, 11.5 * mm, 11.5 * mm],
            repeatRows=1,
        )
        style = self._table_style_with_header()
        for row_index, kind in enumerate(row_kinds):
            if kind == "not_run":
                style.add("TEXTCOLOR", (0, row_index), (-1, row_index), colors.HexColor("#999999"))
            elif kind == "failed":
                style.add("TEXTCOLOR", (3, row_index), (4, row_index), COLOR_ERROR)
                style.add("FONTNAME", (3, row_index), (4, row_index), "Helvetica-Bold")
            elif kind == "total":
                style.add("FONTNAME", (0, row_index), (-1, row_index), "Helvetica-Bold")
                style.add("LINEABOVE", (0, row_index), (-1, row_index), 0.75, colors.HexColor("#666666"))
        table.setStyle(style)
        story.append(table)
        return story

    # -- Zusammenfassung -------------------------------------------------

    def _build_summary_page(self, report: LintReport) -> list:
        story: list = [Paragraph("Zusammenfassung", self._styles["Heading1"]), Spacer(1, 4 * mm)]

        totals_table = Table(
            [["Fehler", "Warnungen", "OK"], [str(report.errors), str(report.warnings), str(report.ok_count)]],
            colWidths=[52 * mm] * 3,
        )
        totals_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 1), colors.Color(1, 0.27, 0.27, alpha=0.15)),
                    ("BACKGROUND", (1, 0), (1, 1), colors.Color(1, 0.65, 0, alpha=0.15)),
                    ("BACKGROUND", (2, 0), (2, 1), colors.Color(0.27, 0.67, 0.27, alpha=0.15)),
                    ("TEXTCOLOR", (0, 1), (0, 1), COLOR_ERROR),
                    ("TEXTCOLOR", (1, 1), (1, 1), COLOR_WARNING),
                    ("TEXTCOLOR", (2, 1), (2, 1), COLOR_OK),
                    ("FONTSIZE", (0, 1), (-1, 1), 20),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ]
            )
        )
        story.append(totals_table)
        story.append(Spacer(1, 10 * mm))

        story.append(Paragraph("Nach Kategorie", self._styles["Heading2"]))
        story.append(Spacer(1, 2 * mm))

        header = ["Kategorie", "Fehler", "Warnungen", "OK"]
        rows = [header]
        for category, results in report.results_by_category().items():
            errors = sum(1 for r in results if r.status == CheckStatus.ERROR)
            warnings = sum(1 for r in results if r.status == CheckStatus.WARNING)
            ok = sum(1 for r in results if r.status == CheckStatus.OK)
            rows.append([category, str(errors), str(warnings), str(ok)])

        category_table = Table(rows, colWidths=[90 * mm, 28 * mm, 28 * mm, 28 * mm], repeatRows=1)
        category_table.setStyle(self._table_style_with_header())
        story.append(category_table)
        return story

    # -- Detailseiten ----------------------------------------------------

    def _build_detail_pages(self, report: LintReport) -> list:
        story: list = [Paragraph("Details", self._styles["Heading1"])]

        grouped = report.results_by_category()
        if not grouped:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Keine Befunde — alle geprüften Punkte sind in Ordnung.", self._styles["Normal"]))
            return story

        for category, results in grouped.items():
            story.append(Paragraph(category, self._styles["TiaCategoryHeading"]))
            story.append(self._build_category_table(results))

        return story

    def _build_category_table(self, results: list[CheckResult]) -> Table:
        header = ["Status", "Pfad", "Beschreibung", "Empfehlung"]
        rows: list[list] = [header]
        status_column: list[CheckStatus] = []
        for result in results:
            rows.append(
                [
                    _STATUS_LABEL[result.status],
                    Paragraph(result.path, self._styles["TiaCell"]),
                    Paragraph(result.description, self._styles["TiaCell"]),
                    Paragraph(result.recommendation, self._styles["TiaCell"]),
                ]
            )
            status_column.append(result.status)

        table = Table(rows, colWidths=[20 * mm, 45 * mm, 55 * mm, 54 * mm], repeatRows=1)
        style = self._table_style_with_header()
        for row_index, status in enumerate(status_column, start=1):
            style.add("TEXTCOLOR", (0, row_index), (0, row_index), _STATUS_COLOR[status])
            style.add("FONTNAME", (0, row_index), (0, row_index), "Helvetica-Bold")
        table.setStyle(style)
        return table

    # -- Anhang A: verwendete Konfiguration --------------------------------

    def _build_appendix_a(self) -> list:
        story: list = [
            Paragraph("Anhang A — Verwendete Konfiguration", self._styles["Heading1"]),
            Spacer(1, 4 * mm),
            Paragraph(
                "Vollständiger Parameterinhalt der YAML-Konfigurationsdatei, mit der diese "
                "Prüfung durchgeführt wurde (ohne die erläuternden Kommentare der Originaldatei, "
                "bis auf einen Verweis auf die jeweilige Prüfpunkt-Nummer).",
                self._styles["Normal"],
            ),
            Spacer(1, 4 * mm),
            Preformatted(_hard_wrap(self._render_config_yaml(), _CODE_MAX_CHARS), self._styles["TiaCode"]),
        ]
        return story

    def _render_config_yaml(self) -> str:
        """Rendert die aktuelle ``AppConfig`` als YAML-Text — reine Parameter,
        ohne die Erklärkommentare der Originaldatei. Einzige Ausnahme: über
        jedem einzelnen Prüfpunkt-Eintrag im ``checks:``-Abschnitt steht ein
        Kommentar mit dessen Prüfpunkt-Nummer (aus ``CHECK_REGISTRY``), zur
        leichteren Zuordnung zu Kapitel 10 des Handbuchs bzw. den Detailseiten
        dieses Reports.

        Reines Block-Style (statt kompakterem Flow-Style) mit an die
        ``TiaCode``-Schrift/Seitenbreite angepasstem ``width`` — Flow-Style
        erzeugte bei langen Einträgen (z. B. ``ausnahme_udts``, Regex-Listen)
        einzelne Zeilen, die im ``Preformatted``-Block breiter als die
        Seitenbreite wurden und dadurch über den Rand hinausliefen, statt
        umzubrechen (``Preformatted`` bricht selbst nicht um)."""
        config = self._app_config
        top_level = config.model_dump(mode="json", exclude={"checks"})
        top_level_order = [
            "report",
            "tia_versionen",
            "max_reconnect_attempts",
            "reconnect_every_n_checks",
            "ausgeschlossene_ordner",
            "ausgeschlossene_bausteine",
        ]
        ordered_top = {key: top_level[key] for key in top_level_order if key in top_level}

        checks_dict: dict[str, dict[str, dict]] = {}
        for check_id, meta in CHECK_REGISTRY.items():
            category_key, check_key = check_id.split(".", 1)
            entry = config.checks.get(category_key, {}).get(check_key)
            if entry is None:
                continue
            checks_dict.setdefault(category_key, {})[check_key] = entry.model_dump(mode="json")

        return "\n".join(
            [
                self._dump_yaml(ordered_top),
                "",
                self._insert_check_number_comments(self._dump_yaml({"checks": checks_dict})),
                "",
                self._dump_yaml({"logging": top_level["logging"]}),
            ]
        )

    @staticmethod
    def _dump_yaml(data: object) -> str:
        return yaml.safe_dump(
            data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=_YAML_DUMP_WIDTH
        ).rstrip("\n")

    @staticmethod
    def _insert_check_number_comments(checks_yaml: str) -> str:
        """Fügt über jeder Prüfpunkt-Konfigurationszeile (Einrücktiefe 4 —
        direkt unter einer Kategorie auf Einrücktiefe 2, direkt unter
        ``checks:`` auf Einrücktiefe 0) einen ``# Prüfpunkt <nummer>``-
        Kommentar ein."""
        output: list[str] = []
        current_category: str | None = None
        for line in checks_yaml.split("\n"):
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            if indent == 2 and stripped.endswith(":"):
                current_category = stripped[:-1]
            elif indent == 4 and stripped.endswith(":") and current_category is not None:
                meta = CHECK_REGISTRY.get(f"{current_category}.{stripped[:-1]}")
                if meta is not None:
                    output.append(f"    # Prüfpunkt {meta.nummer}")
            output.append(line)
        return "\n".join(output)

    # -- Gemeinsame Bausteine ---------------------------------------------

    def _table_style_with_header(self) -> TableStyle:
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )

    def _make_footer(self, project_name: str) -> Callable:
        def footer(canvas, doc) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#666666"))
            canvas.drawString(18 * mm, 12 * mm, project_name)
            canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Seite {doc.page}")
            canvas.restoreState()

        return footer
