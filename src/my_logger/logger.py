import logging
import sys
from pathlib import Path

from .exceptions import LoggerSetupError
from .schema import LoggingConfig

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(module)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(config: LoggingConfig) -> logging.Logger:
    """Configure the root logger and return it.

    Configures the root logger so all module-level loggers (logging.getLogger(__name__))
    automatically inherit the handlers and format.

    Builds every new handler *before* touching the existing ones (Review-
    Security-Robustheit.md, Befund 4.5): opening the log file is the one
    step that can fail (``LoggerSetupError``, e.g. a read-only output
    folder) — if the old handlers had already been removed at that point,
    a failed call left the root logger completely without output targets
    (only the ``NullHandler`` fallback below, which never triggers here
    since it only applies to a *successful* call with no configured
    targets). Now a failed call raises without touching the logger at all,
    so the previous configuration keeps working.
    """
    root = logging.getLogger()
    level = getattr(logging, config.level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    new_handlers: list[logging.Handler] = []

    if config.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        new_handlers.append(console_handler)

    if config.file:
        log_path = Path(config.file)
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LoggerSetupError(
                f"Cannot create log directory '{log_path.parent}': {exc}"
            ) from exc
        try:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
        except OSError as exc:
            raise LoggerSetupError(
                f"Cannot open log file '{log_path}': {exc}"
            ) from exc
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        new_handlers.append(file_handler)

    if not new_handlers:
        new_handlers.append(logging.NullHandler())
        import warnings
        warnings.warn(
            "Logger configured with no output targets (console=False, file=None).",
            stacklevel=2,
        )

    # Erst jetzt, nachdem alle neuen Handler erfolgreich erstellt wurden
    # (insbesondere die Logdatei erfolgreich geöffnet ist), die alten
    # entfernen — siehe Docstring oben.
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)

    root.setLevel(level)
    for handler in new_handlers:
        root.addHandler(handler)

    return root
