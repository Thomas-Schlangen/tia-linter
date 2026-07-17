"""PDF-Lintreport (DIN A4) mit reportlab."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from tia_linter.config import ReportConfig
from tia_linter.models import CheckResult, CheckStatus, LintReport

logger = logging.getLogger(__name__)

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

    def __init__(self, report_config: ReportConfig | None = None) -> None:
        self._report_config = report_config or ReportConfig()
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
        story.extend(self._build_summary_page(report))
        story.append(PageBreak())
        story.extend(self._build_detail_pages(report))

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
