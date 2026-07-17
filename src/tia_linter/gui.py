"""Tkinter-Oberfläche für den TIA Linter — Eingabeseite und Ergebnisseite."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from my_logger import setup_logger

from tia_linter.config import AppConfig, build_check_definitions, load_app_config
from tia_linter.models import CheckDefinition, CheckStatus, LintReport
from tia_linter.reporter import PdfReporter
from tia_linter.settings import Settings

logger = logging.getLogger(__name__)

RunLintFn = Callable[..., LintReport]

_ALL_CATEGORIES = "(Alle Kategorien)"
_ALL_STATUSES = "(Alle Status)"
_PATH_FILTER_PLACEHOLDER = "Pfad / Baustein filtern..."

_STATUS_LABEL = {CheckStatus.ERROR: "Fehler", CheckStatus.WARNING: "Warnung", CheckStatus.OK: "OK"}
_STATUS_TAG_COLOR = {
    CheckStatus.ERROR: "#CC0000",
    CheckStatus.WARNING: "#B36B00",
    CheckStatus.OK: "#2E8B32",
}


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M")


class TiaLinterApp(tk.Tk):
    """Hauptfenster: schaltet zwischen Eingabeseite (``MainPage``) und
    Ergebnisseite (``ResultPage``) um und koordiniert den Prüflauf im
    Hintergrund-Thread."""

    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        settings: Settings,
        run_lint: RunLintFn,
    ) -> None:
        super().__init__()
        self.title("TIA Linter")

        self.config: AppConfig = config
        self.config_path = config_path
        self.settings = settings
        self.definitions: list[CheckDefinition] = build_check_definitions(config)

        self._run_lint = run_lint
        self._report: LintReport | None = None
        self._lint_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._status_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

        try:
            self.geometry(settings.window_geometry)
        except tk.TclError:
            logger.warning("Ungültige Fenstergeometrie in settings.json, verwende Standard.")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.main_page = MainPage(container, self)
        self.result_page = ResultPage(container, self)
        self._show_main_page()

        self.after(100, self._poll_status_queue)

    # -- Seitenwechsel --------------------------------------------------

    def _show_main_page(self) -> None:
        self.result_page.pack_forget()
        self.main_page.pack(fill="both", expand=True)

    def _show_result_page(self, report: LintReport) -> None:
        self._report = report
        self.result_page.load_report(report)
        self.main_page.pack_forget()
        self.result_page.pack(fill="both", expand=True)

    def start_new_run(self) -> None:
        self._show_main_page()

    # -- Konfiguration ----------------------------------------------------

    def reload_config(self, config_path: Path) -> None:
        """Lädt eine andere YAML-Konfigurationsdatei und baut die
        Prüfpunkt-Checkboxen neu auf."""
        try:
            config = load_app_config(config_path)
        except Exception as exc:  # noqa: BLE001 — letzte Instanz gegen rohe Tracebacks in der GUI
            messagebox.showerror("TIA Linter", f"Konfigurationsdatei konnte nicht geladen werden:\n{exc}")
            return
        self.config = config
        self.config_path = config_path
        self.definitions = build_check_definitions(config)
        self.main_page.rebuild_check_tree()

    # -- Prüfung starten/abbrechen ----------------------------------------

    def start_lint_run(self) -> None:
        if self._lint_thread is not None and self._lint_thread.is_alive():
            return

        project_path_str = self.main_page.project_path.get().strip()
        output_folder = self.main_page.output_folder.get().strip()
        if not project_path_str:
            messagebox.showerror("TIA Linter", "Bitte zuerst eine TIA-Projektdatei auswählen.")
            return
        if not output_folder:
            messagebox.showerror("TIA Linter", "Bitte zuerst einen Output-Ordner auswählen.")
            return

        enabled_definitions = self.main_page.collect_enabled_definitions()
        if not enabled_definitions:
            messagebox.showerror("TIA Linter", "Bitte mindestens einen Prüfpunkt auswählen.")
            return

        version_name = self.main_page.tia_version.get()
        version_entry = self.config.tia_versionen.find(version_name)
        dll_path = version_entry.dll_pfad if version_entry else ""
        version_number = version_entry.version if version_entry else 0

        if self.config.logging.file:
            project_name = Path(project_path_str).stem
            log_name = f"Lintlog_{project_name}_{_timestamp()}.log"
            log_config = self.config.logging.model_copy(update={"file": str(Path(output_folder) / log_name)})
            setup_logger(log_config)

        self.main_page.clear_log()
        self._cancel_event = threading.Event()
        self.main_page.set_running(True)

        self._lint_thread = threading.Thread(
            target=self._run_lint_thread,
            kwargs={
                "dll_path": dll_path,
                "tia_version": version_number,
                "project_path": project_path_str,
                "project_name": Path(project_path_str).stem,
                "tia_version_name": version_name,
                "checker_name": self.config.report.pruefer,
                "definitions": enabled_definitions,
                "cancel_event": self._cancel_event,
                "max_reconnect_attempts": self.config.max_reconnect_attempts,
                "reconnect_every_n_checks": self.config.reconnect_every_n_checks,
            },
            daemon=True,
        )
        self._lint_thread.start()

    def cancel_lint_run(self) -> None:
        self._cancel_event.set()
        self._status_queue.put(("status", "Abbruch angefordert ..."))

    def _run_lint_thread(self, **kwargs) -> None:
        try:
            report = self._run_lint(progress=lambda message: self._status_queue.put(("status", message)), **kwargs)
            self._status_queue.put(("report", report))
        except Exception as exc:  # noqa: BLE001 — letzte Instanz gegen rohe Tracebacks in der GUI
            logger.exception("Unerwarteter Fehler bei der Prüfung")
            self._status_queue.put(("status", f"FEHLER: {exc}"))
        finally:
            self._status_queue.put(("done", None))

    def _poll_status_queue(self) -> None:
        try:
            while True:
                kind, payload = self._status_queue.get_nowait()
                if kind == "status":
                    self.main_page.append_log(str(payload))
                elif kind == "report":
                    self._show_result_page(payload)  # type: ignore[arg-type]
                elif kind == "done":
                    self.main_page.set_running(False)
        except queue.Empty:
            pass
        self.after(100, self._poll_status_queue)

    # -- PDF-Report ---------------------------------------------------------

    def generate_pdf_report(self) -> None:
        if self._report is None:
            return
        output_folder = self.main_page.output_folder.get().strip() or "."
        try:
            output_path = PdfReporter(self.config.report).generate(self._report, output_folder)
        except OSError as exc:
            messagebox.showerror("TIA Linter", f"PDF-Report konnte nicht erstellt werden:\n{exc}")
            return
        messagebox.showinfo("TIA Linter", f"PDF-Report erstellt:\n{output_path}")

    # -- Fenster schließen ----------------------------------------------

    def _on_close(self) -> None:
        self.settings.window_geometry = self.geometry()
        self.settings.last_project_path = self.main_page.project_path.get().strip()
        self.settings.last_output_folder = self.main_page.output_folder.get().strip()
        self.settings.last_config_path = str(self.config_path)
        self.settings.last_tia_version = self.main_page.tia_version.get()
        self.settings.save()
        self.destroy()


class MainPage(ttk.Frame):
    """Eingabeseite: Projektdatei, Output-Ordner, Config, TIA-Version,
    Prüfpunkt-Checkboxen, Start/Abbrechen, Fortschritt und Log."""

    def __init__(self, parent: tk.Widget, app: TiaLinterApp) -> None:
        super().__init__(parent)
        self.app = app
        settings = app.settings

        self.project_path = tk.StringVar(value=settings.last_project_path)
        self.output_folder = tk.StringVar(value=settings.last_output_folder)
        self.config_path_var = tk.StringVar(value=settings.last_config_path or str(app.config_path))

        version_names = [v.name for v in app.config.tia_versionen.verfuegbar]
        default_version = (
            settings.last_tia_version
            if settings.last_tia_version in version_names
            else app.config.tia_versionen.standard
        )
        self.tia_version = tk.StringVar(value=default_version)

        self._check_vars: dict[str, tk.BooleanVar] = {}

        self._build_widgets(version_names, default_version)
        self.rebuild_check_tree()

    def _build_widgets(self, version_names: list[str], default_version: str) -> None:
        pad = {"padx": 8, "pady": 4}

        form = ttk.Frame(self)
        form.pack(fill="x", **pad)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="TIA-Projektdatei:").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.project_path).grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(form, text="Durchsuchen ...", command=self._choose_project).grid(row=0, column=2)

        ttk.Label(form, text="Output-Ordner:").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.output_folder).grid(row=1, column=1, sticky="we", padx=4)
        ttk.Button(form, text="Durchsuchen ...", command=self._choose_output_folder).grid(row=1, column=2)

        ttk.Label(form, text="Konfigurationsdatei:").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.config_path_var).grid(row=2, column=1, sticky="we", padx=4)
        ttk.Button(form, text="Durchsuchen ...", command=self._choose_config).grid(row=2, column=2)

        ttk.Label(form, text="TIA Portal Version:").grid(row=3, column=0, sticky="w")
        version_menu = tk.OptionMenu(form, self.tia_version, *version_names)
        version_menu.grid(row=3, column=1, sticky="w")
        # OptionMenu setzt beim Erzeugen die Variable auf den ersten Eintrag —
        # die Vorauswahl aus settings.json danach explizit wiederherstellen.
        self.tia_version.set(default_version)

        checks_outer = ttk.LabelFrame(self, text="Prüfpunkte")
        checks_outer.pack(fill="both", expand=True, **pad)

        global_buttons = ttk.Frame(checks_outer)
        global_buttons.pack(fill="x", padx=4, pady=(4, 0))
        ttk.Button(global_buttons, text="Alle auswählen", command=lambda: self._set_all(True)).pack(side="left")
        ttk.Button(
            global_buttons, text="Alle abwählen", command=lambda: self._set_all(False)
        ).pack(side="left", padx=(6, 0))

        canvas = tk.Canvas(checks_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(checks_outer, orient="vertical", command=canvas.yview)
        self._checks_frame = ttk.Frame(canvas)
        self._checks_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._checks_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scrollbar.pack(side="right", fill="y")

        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)
        self._start_button = ttk.Button(action_frame, text="Prüfung starten", command=self.app.start_lint_run)
        self._start_button.pack(side="left")
        self._cancel_button = ttk.Button(
            action_frame, text="Abbrechen", command=self.app.cancel_lint_run, state="disabled"
        )
        self._cancel_button.pack(side="left", padx=(6, 0))

        self._progress = ttk.Progressbar(self, mode="indeterminate")
        self._progress.pack(fill="x", **pad)

        self._status_var = tk.StringVar(value="Bereit.")
        ttk.Label(self, textvariable=self._status_var).pack(fill="x", padx=8)

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self._log_text = tk.Text(log_frame, height=8, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def rebuild_check_tree(self) -> None:
        """Baut die Checkbox-Gruppen aus ``app.definitions`` neu auf — z. B.
        nach dem Laden einer anderen Konfigurationsdatei."""
        for child in self._checks_frame.winfo_children():
            child.destroy()
        self._check_vars.clear()

        by_category: dict[str, list[CheckDefinition]] = {}
        for definition in self.app.definitions:
            by_category.setdefault(definition.category, []).append(definition)

        for category, definitions in by_category.items():
            cat_frame = ttk.LabelFrame(self._checks_frame, text=category)
            cat_frame.pack(fill="x", padx=4, pady=4, anchor="w")

            header = ttk.Frame(cat_frame)
            header.pack(fill="x")
            ttk.Button(
                header, text="Alle", width=6, command=lambda c=category: self._set_category(c, True)
            ).pack(side="left")
            ttk.Button(
                header, text="Keine", width=6, command=lambda c=category: self._set_category(c, False)
            ).pack(side="left", padx=(4, 0))

            for definition in definitions:
                var = tk.BooleanVar(value=definition.enabled)
                self._check_vars[definition.check_id] = var
                ttk.Checkbutton(cat_frame, text=definition.name, variable=var).pack(anchor="w", padx=16)

    def collect_enabled_definitions(self) -> list[CheckDefinition]:
        result = []
        for definition in self.app.definitions:
            var = self._check_vars.get(definition.check_id)
            if var is not None and var.get():
                result.append(definition)
        return result

    def _set_all(self, value: bool) -> None:
        for var in self._check_vars.values():
            var.set(value)

    def _set_category(self, category: str, value: bool) -> None:
        for definition in self.app.definitions:
            if definition.category == category:
                var = self._check_vars.get(definition.check_id)
                if var is not None:
                    var.set(value)

    def _choose_project(self) -> None:
        path = filedialog.askopenfilename(
            title="TIA-Projektdatei wählen",
            filetypes=[("TIA-Portal-Projekt", "*.ap*"), ("Alle Dateien", "*.*")],
        )
        if path:
            self.project_path.set(path)

    def _choose_output_folder(self) -> None:
        path = filedialog.askdirectory(title="Output-Ordner wählen", initialdir=self.output_folder.get() or ".")
        if path:
            self.output_folder.set(path)

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Konfigurationsdatei wählen",
            filetypes=[("YAML-Config", "*.yaml *.yml"), ("Alle Dateien", "*.*")],
        )
        if path:
            self.config_path_var.set(path)
            self.app.reload_config(Path(path))

    def set_running(self, running: bool) -> None:
        self._start_button.configure(state="disabled" if running else "normal")
        self._cancel_button.configure(state="normal" if running else "disabled")
        if running:
            self._progress.start(12)
        else:
            self._progress.stop()

    def clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def append_log(self, message: str) -> None:
        self._status_var.set(message)
        self._log_text.configure(state="normal")
        self._log_text.insert("end", message + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")


class ResultPage(ttk.Frame):
    """Ergebnisseite: Zusammenfassung, filterbare Befundtabelle,
    Detail-Dialog per Doppelklick, PDF-Report erstellen."""

    def __init__(self, parent: tk.Widget, app: TiaLinterApp) -> None:
        super().__init__(parent)
        self.app = app
        self._report: LintReport | None = None

        self._status_filter = tk.StringVar(value=_ALL_STATUSES)
        self._category_filter = tk.StringVar(value=_ALL_CATEGORIES)
        self._path_filter = tk.StringVar()
        self._path_filter_is_placeholder = False

        self._build_widgets()

    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}

        summary = ttk.Frame(self)
        summary.pack(fill="x", **pad)
        self._summary_var = tk.StringVar()
        ttk.Label(summary, textvariable=self._summary_var, font=("TkDefaultFont", 13, "bold")).pack(side="left")

        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill="x", **pad)
        ttk.Label(filter_frame, text="Status:").pack(side="left")
        self._status_combo = ttk.Combobox(filter_frame, textvariable=self._status_filter, state="readonly", width=15)
        self._status_combo.pack(side="left", padx=(4, 12))
        self._status_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        ttk.Label(filter_frame, text="Kategorie:").pack(side="left")
        self._category_combo = ttk.Combobox(
            filter_frame, textvariable=self._category_filter, state="readonly", width=36
        )
        self._category_combo.pack(side="left", padx=(4, 12))
        self._category_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_table())

        ttk.Label(filter_frame, text="Pfad:").pack(side="left")
        style = ttk.Style()
        style.configure("TiaPathFilterPlaceholder.TEntry", foreground="#888888")
        style.configure("TiaPathFilter.TEntry", foreground="")
        self._path_entry = ttk.Entry(filter_frame, textvariable=self._path_filter, width=28)
        self._path_entry.pack(side="left", padx=(4, 0))
        self._path_entry.bind("<FocusIn>", self._on_path_filter_focus_in)
        self._path_entry.bind("<FocusOut>", self._on_path_filter_focus_out)

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, **pad)
        columns = ("status", "check", "path", "description")
        self._tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in (
            ("status", "Status", 80),
            ("check", "Prüfpunkt", 220),
            ("path", "Pfad", 340),
            ("description", "Beschreibung", 340),
        ):
            self._tree.heading(col, text=label)
            self._tree.column(col, width=width, anchor="w")
        tree_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=tree_scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self._tree.bind("<Double-1>", self._show_detail)

        for status, color in _STATUS_TAG_COLOR.items():
            self._tree.tag_configure(status.value, foreground=color)

        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **pad)
        ttk.Button(action_frame, text="PDF-Report erstellen", command=self.app.generate_pdf_report).pack(side="left")
        ttk.Button(action_frame, text="Neue Prüfung", command=self.app.start_new_run).pack(side="left", padx=(6, 0))

        # Trace erst registrieren, nachdem self._tree existiert — _refresh_table()
        # greift darauf zu und wird bei jedem Tastendruck im Pfad-Filter ausgelöst.
        self._path_filter.trace_add("write", lambda *_args: self._refresh_table())
        self._show_path_filter_placeholder()

    def load_report(self, report: LintReport) -> None:
        self._report = report
        self._summary_var.set(
            f"{report.errors} Fehler   |   {report.warnings} Warnungen   |   {report.ok_count} OK"
        )

        categories = sorted({r.category for r in report.results})
        self._category_combo["values"] = [_ALL_CATEGORIES, *categories]
        self._status_combo["values"] = [_ALL_STATUSES, *(_STATUS_LABEL[s] for s in CheckStatus)]
        self._status_filter.set(_ALL_STATUSES)
        self._category_filter.set(_ALL_CATEGORIES)
        self._show_path_filter_placeholder()

        self._refresh_table()

    # -- Pfad-Filter (Freitext mit Placeholder) --------------------------

    def _show_path_filter_placeholder(self) -> None:
        self._path_filter_is_placeholder = True
        self._path_filter.set(_PATH_FILTER_PLACEHOLDER)
        self._path_entry.configure(style="TiaPathFilterPlaceholder.TEntry")

    def _on_path_filter_focus_in(self, _event: tk.Event) -> None:
        if self._path_filter_is_placeholder:
            self._path_filter_is_placeholder = False
            self._path_filter.set("")
            self._path_entry.configure(style="TiaPathFilter.TEntry")

    def _on_path_filter_focus_out(self, _event: tk.Event) -> None:
        if not self._path_filter.get():
            self._show_path_filter_placeholder()

    def _refresh_table(self) -> None:
        self._tree.delete(*self._tree.get_children())
        if self._report is None:
            return
        status_filter = self._status_filter.get()
        category_filter = self._category_filter.get()
        path_filter = "" if self._path_filter_is_placeholder else self._path_filter.get().strip().lower()

        for index, result in enumerate(self._report.results):
            if status_filter != _ALL_STATUSES and _STATUS_LABEL[result.status] != status_filter:
                continue
            if category_filter != _ALL_CATEGORIES and result.category != category_filter:
                continue
            if path_filter and path_filter not in result.path.lower():
                continue
            self._tree.insert(
                "",
                "end",
                iid=str(index),
                values=(_STATUS_LABEL[result.status], result.check_name, result.path, result.description),
                tags=(result.status.value,),
            )

    def _show_detail(self, _event: tk.Event) -> None:
        selection = self._tree.selection()
        if not selection or self._report is None:
            return
        result = self._report.results[int(selection[0])]

        dialog = tk.Toplevel(self)
        dialog.title(result.check_name)
        dialog.geometry("520x320")
        pad = {"padx": 12, "pady": 6}

        ttk.Label(dialog, text=result.check_name, font=("TkDefaultFont", 11, "bold")).pack(anchor="w", **pad)
        ttk.Label(dialog, text=f"Status: {_STATUS_LABEL[result.status]}").pack(anchor="w", padx=12)
        ttk.Label(dialog, text=f"Pfad: {result.path}", wraplength=480, justify="left").pack(anchor="w", **pad)

        ttk.Label(dialog, text="Beschreibung:", font=("TkDefaultFont", 9, "bold")).pack(anchor="w", padx=12)
        ttk.Label(dialog, text=result.description, wraplength=480, justify="left").pack(anchor="w", **pad)

        ttk.Label(dialog, text="Empfehlung zur Behebung:", font=("TkDefaultFont", 9, "bold")).pack(
            anchor="w", padx=12
        )
        ttk.Label(dialog, text=result.recommendation, wraplength=480, justify="left").pack(anchor="w", **pad)

        ttk.Button(dialog, text="Schließen", command=dialog.destroy).pack(pady=(8, 12))
