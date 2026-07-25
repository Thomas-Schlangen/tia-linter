"""Tkinter-Oberfläche für den TIA Linter — Eingabeseite und Ergebnisseite."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Any, Callable

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
    Hintergrund-Thread.

    Nimmt sowohl ``run_lint`` (Produktivmodus, Standard) als auch
    ``simulate_lint_run`` (Testmodus, Dummy-Befunde ohne TIA-Verbindung)
    entgegen — welche der beiden Funktionen für einen konkreten Lauf
    verwendet wird, entscheidet die "Testmodus"-Checkbox auf der
    ``MainPage`` zum Zeitpunkt von ``start_lint_run()``.
    """

    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        settings: Settings,
        run_lint: RunLintFn,
        simulate_lint_run: RunLintFn,
    ) -> None:
        super().__init__()
        self.title("TIA Linter")

        self.config: AppConfig = config
        self.config_path = config_path
        self.settings = settings
        self.definitions: list[CheckDefinition] = build_check_definitions(config)

        self._run_lint_fn = run_lint
        self._simulate_lint_run_fn = simulate_lint_run
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
        """Validiert die Eingaben und startet den Lint-Lauf (echt oder
        simuliert, siehe Testmodus-Checkbox) in einem Hintergrund-Thread."""
        if self._lint_thread is not None and self._lint_thread.is_alive():
            return
        if not self._validate_inputs():
            return

        project_path_str = self.main_page.project_path.get().strip()
        output_folder = self.main_page.output_folder.get().strip()
        enabled_definitions = self.main_page.collect_enabled_definitions()

        version_name = self.main_page.tia_version.get()
        version_entry = self.config.tia_versionen.find(version_name)
        dll_path = version_entry.dll_pfad if version_entry else ""
        version_number = version_entry.version if version_entry else 0

        self._setup_run_logger(output_folder, project_path_str)

        self.main_page.clear_log()
        self._cancel_event = threading.Event()
        self.main_page.set_running(True)

        active_run_lint = self._simulate_lint_run_fn if self.main_page.test_mode.get() else self._run_lint_fn

        self._lint_thread = threading.Thread(
            target=self._run_lint_thread,
            args=(active_run_lint,),
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
                "excluded_folders": self.config.ausgeschlossene_ordner,
                "excluded_blocks": self.config.ausgeschlossene_bausteine,
            },
            daemon=True,
        )
        self._lint_thread.start()

    def _validate_inputs(self) -> bool:
        """Prüft die Eingaben der Eingabeseite vor Start eines Lint-Laufs
        (Projektdatei, Output-Ordner, mindestens ein aktivierter Prüfpunkt)
        und zeigt bei einem Mangel eine Fehlermeldung an. Liefert ``True``,
        wenn der Lauf gestartet werden darf."""
        if not self.main_page.project_path.get().strip():
            messagebox.showerror("TIA Linter", "Bitte zuerst eine TIA-Projektdatei auswählen.")
            return False
        if not self.main_page.output_folder.get().strip():
            messagebox.showerror("TIA Linter", "Bitte zuerst einen Output-Ordner auswählen.")
            return False
        if not self.main_page.collect_enabled_definitions():
            messagebox.showerror("TIA Linter", "Bitte mindestens einen Prüfpunkt auswählen.")
            return False
        return True

    def _setup_run_logger(self, output_folder: str, project_path_str: str) -> None:
        """Richtet die Log-Datei für diesen Lauf ein, sofern in der Config
        eine Dateiausgabe konfiguriert ist (``config.logging.file``)."""
        if not self.config.logging.file:
            return
        project_name = Path(project_path_str).stem
        log_name = f"Lintlog_{project_name}_{_timestamp()}.log"
        log_config = self.config.logging.model_copy(update={"file": str(Path(output_folder) / log_name)})
        setup_logger(log_config)

    def cancel_lint_run(self) -> None:
        self._cancel_event.set()
        self._status_queue.put(("status", "Abbruch angefordert ..."))

    def _run_lint_thread(self, run_lint_fn: RunLintFn, **kwargs: Any) -> None:
        try:
            report = run_lint_fn(progress=lambda message: self._status_queue.put(("status", message)), **kwargs)
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
        """Erzeugt den PDF-Report für den zuletzt geladenen Lint-Lauf im
        gewählten Output-Ordner (kein-op, solange noch kein Report vorliegt)."""
        if self._report is None:
            return
        output_folder = self.main_page.output_folder.get().strip() or "."
        try:
            output_path = PdfReporter(self.config).generate(self._report, output_folder)
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
        self.settings.test_mode = self.main_page.test_mode.get()
        self.settings.save()
        self.destroy()


class MainPage(ttk.Frame):
    """Eingabeseite: Projektdatei, Output-Ordner, Config, TIA-Version,
    Prüfpunkt-Checkboxen, Start/Abbrechen, Fortschritt und Log."""

    _PAD = {"padx": 8, "pady": 4}

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
        self.test_mode = tk.BooleanVar(value=settings.test_mode)

        self._check_vars: dict[str, tk.BooleanVar] = {}

        self._build_widgets(version_names, default_version)
        self.rebuild_check_tree()

    def _build_widgets(self, version_names: list[str], default_version: str) -> None:
        self._build_form(version_names, default_version)
        big_font = self._setup_big_button_style()
        self._build_check_area()
        self._build_buttons(big_font)
        self._build_log_area()

    def _build_form(self, version_names: list[str], default_version: str) -> None:
        """Baut das obere Formular: Projektdatei, Output-Ordner,
        Konfigurationsdatei, TIA-Version und Testmodus-Checkbox."""
        form = ttk.Frame(self)
        form.pack(fill="x", **self._PAD)
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

        ttk.Checkbutton(
            form,
            text="Testmodus (simulierter Lauf ohne TIA-Verbindung, Dummy-Befunde)",
            variable=self.test_mode,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _setup_big_button_style(self) -> tkfont.Font:
        """Konfiguriert den ttk-Style ``"Big.TButton"`` (~50% größere Schrift,
        skaliert relativ zur tatsächlichen Basisschriftgröße statt eine feste
        Punktgröße hart zu kodieren) für die hervorgehobenen Buttons unten.
        Liefert dieselbe Font zusätzlich zurück, da der Start-Button
        (``_build_buttons``) als reines ``tk.Button`` keinen ttk-Style
        annehmen kann und die Font explizit gesetzt bekommen muss."""
        default_font = tkfont.nametofont("TkDefaultFont")
        big_font = default_font.copy()
        big_font.configure(size=round(default_font.cget("size") * 1.5))
        style = ttk.Style()
        style.configure("Big.TButton", font=big_font, padding=(12, 8))
        return big_font

    def _build_check_area(self) -> None:
        """Baut den scrollbaren Prüfpunkt-Bereich samt "Alle (ab)wählen"-Buttons."""
        checks_outer = ttk.LabelFrame(self, text="Prüfpunkte")
        checks_outer.pack(fill="both", expand=True, **self._PAD)

        global_buttons = ttk.Frame(checks_outer)
        global_buttons.pack(fill="x", padx=4, pady=(4, 0))
        # Innerer Frame ohne fill/side="left" -> wird per Pack-Default
        # (anchor="center") innerhalb der vollen Breite von global_buttons
        # horizontal zentriert, statt links auszurichten.
        global_buttons_inner = ttk.Frame(global_buttons)
        global_buttons_inner.pack()
        ttk.Button(
            global_buttons_inner, text="Alle auswählen", style="Big.TButton", command=lambda: self._set_all(True)
        ).pack(side="left")
        ttk.Button(
            global_buttons_inner,
            text="Alle abwählen",
            style="Big.TButton",
            command=lambda: self._set_all(False),
        ).pack(side="left", padx=(8, 0))

        canvas = tk.Canvas(checks_outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(checks_outer, orient="vertical", command=canvas.yview)
        self._checks_frame = ttk.Frame(canvas)
        self._checks_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._checks_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        scrollbar.pack(side="right", fill="y")
        self._checks_canvas = canvas

    def _build_buttons(self, big_font: tkfont.Font) -> None:
        """Baut Start-/Abbrechen-Buttons, Fortschrittsbalken und Statuszeile."""
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **self._PAD)
        action_frame_inner = ttk.Frame(action_frame)
        action_frame_inner.pack()
        # Reines tk.Button statt ttk.Button: ttk-Buttons ignorieren unter den
        # nativen Windows-Themes ("vista"/"xpnative") eine über
        # background/style.map gesetzte Hintergrundfarbe — nur ein klassisches
        # tk.Button setzt sie zuverlässig um. Farbe wechselt dynamisch je
        # nachdem, ob mindestens ein Prüfpunkt angehakt ist, siehe
        # _update_start_button_appearance().
        self._start_button = tk.Button(
            action_frame_inner,
            text="Prüfung starten",
            font=big_font,
            padx=12,
            pady=8,
            command=self.app.start_lint_run,
        )
        self._start_button.pack(side="left")
        self._start_button_default_bg = self._start_button.cget("background")
        self._cancel_button = ttk.Button(
            action_frame_inner,
            text="Abbrechen",
            style="Big.TButton",
            command=self.app.cancel_lint_run,
            state="disabled",
        )
        self._cancel_button.pack(side="left", padx=(8, 0))

        self._progress = ttk.Progressbar(self, mode="indeterminate")
        self._progress.pack(fill="x", **self._PAD)

        self._status_var = tk.StringVar(value="Bereit.")
        ttk.Label(self, textvariable=self._status_var).pack(fill="x", padx=8)

    def _build_log_area(self) -> None:
        """Baut den Log-Bereich (scrollbares, nicht editierbares Textfeld)."""
        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **self._PAD)
        self._log_text = tk.Text(log_frame, height=6, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_scroll.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    # Anzahl Kategorie-Spalten nebeneinander in der Prüfpunkte-Übersicht —
    # nutzt die verfügbare horizontale Breite besser aus, statt alle 7
    # Kategorien stur untereinander zu stapeln.
    _CATEGORY_COLUMNS = 4

    def rebuild_check_tree(self) -> None:
        """Baut die Checkbox-Gruppen aus ``app.definitions`` neu auf — z. B.
        nach dem Laden einer anderen Konfigurationsdatei."""
        for child in self._checks_frame.winfo_children():
            child.destroy()
        self._check_vars.clear()

        by_category: dict[str, list[CheckDefinition]] = {}
        for definition in self.app.definitions:
            by_category.setdefault(definition.category, []).append(definition)

        for col in range(self._CATEGORY_COLUMNS):
            self._checks_frame.columnconfigure(col, weight=1, uniform="category")

        for index, (category, definitions) in enumerate(by_category.items()):
            row_index, col_index = divmod(index, self._CATEGORY_COLUMNS)
            cat_frame = ttk.LabelFrame(self._checks_frame, text=category)
            cat_frame.grid(row=row_index, column=col_index, padx=4, pady=4, sticky="nsew")

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
                var.trace_add("write", lambda *_args: self._update_start_button_appearance())

                row = ttk.Frame(cat_frame)
                row.pack(fill="x", anchor="w", padx=16)
                # Feste Breite links von jeder Checkbox für die Prüfpunkt-
                # Nummer(n) (z. B. "18c") — rechtsbündig, damit die Namen der
                # Checkboxen selbst untereinander bündig stehen.
                ttk.Label(row, text=definition.nummer, width=6, anchor="e").pack(side="left")
                ttk.Checkbutton(row, text=definition.name, variable=var).pack(side="left", padx=(4, 0))

        self._bind_mousewheel_recursive(self._checks_frame)
        self._update_start_button_appearance()

    def _update_start_button_appearance(self) -> None:
        """Färbt den "Prüfung starten"-Button hellgrün, sobald mindestens ein
        Prüfpunkt angehakt ist — reagiert auf jede Änderung eines
        Kontrollkästchens, egal ob einzeln, per Kategorie- oder per
        globalem Auswählen/Abwählen-Button ausgelöst (alle wirken auf
        dieselben ``BooleanVar``s, an die dieser Trace hängt)."""
        any_checked = any(var.get() for var in self._check_vars.values())
        color = "light green" if any_checked else self._start_button_default_bg
        self._start_button.configure(background=color, activebackground=color)

    def _bind_mousewheel_recursive(self, widget: tk.Widget) -> None:
        """Bindet das Mausrad direkt an ``widget`` und alle seine Kinder, damit
        der Prüfpunkte-Bereich überall scrollt, nicht nur über der Scrollbar
        selbst (Windows/Mac: ``<MouseWheel>`` mit ``event.delta``; Linux:
        ``<Button-4>``/``<Button-5>``, da X11 kein ``MouseWheel``-Event kennt).
        Direkte Bindung statt ``bind_all`` mit Enter/Leave-Umschaltung, weil
        die eingebettete Checkbox-Frame ein eigenes Kind-Widget des Canvas ist
        — ein Wechsel der Maus vom Canvas auf eine Checkbox würde dort sonst
        ein <Leave> auf dem Canvas auslösen und die Bindung wieder aufheben."""
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = int(-1 * (event.delta / 120))
        self._checks_canvas.yview_scroll(delta, "units")

    def collect_enabled_definitions(self) -> list[CheckDefinition]:
        """Liefert alle Prüfpunkte, deren Checkbox im Baum aktuell angehakt ist."""
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
        """Schaltet Start-/Abbrechen-Button und Fortschrittsbalken auf den
        Lauf-Zustand um (aktiver Lint-Lauf ja/nein)."""
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
        """Übernimmt einen neuen Lint-Report in die Ergebnisseite (Übersicht,
        Filter, Tabelle) — aufgerufen beim Wechsel von der Eingabe- zur
        Ergebnisseite."""
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
