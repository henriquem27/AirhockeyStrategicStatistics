"""
Centralised logging for Canguru Player.

Call setup_logging() once at startup (player_gui.py does this).
Every other module should simply use:

    from .log import logger        # inside the canguru package
    from canguru.log import logger # from player_gui.py

Log file location (in preference order):
  1. Folder that contains the executable / player_gui.py
  2. %TEMP% / /tmp  (fallback if the exe folder is read-only)

Log filename: CanguruPlayer.log  (rotates at 5 MB, keeps 2 backups)
"""

import logging
import os
import sys
import tempfile
import traceback
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("canguru")

_LOG_FILENAME = "CanguruPlayer.log"
_MAX_BYTES    = 5 * 1024 * 1024   # 5 MB
_BACKUP_COUNT = 2


def _log_dir() -> str:
    """Return the best writable directory for the log file."""
    if getattr(sys, "frozen", False):
        candidate = os.path.dirname(sys.executable)
    else:
        candidate = os.path.dirname(os.path.abspath(__file__ + "/.."))

    # Verify the directory is writable
    try:
        test = os.path.join(candidate, ".write_test")
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return candidate
    except OSError:
        return tempfile.gettempdir()


def log_path() -> str:
    return os.path.join(_log_dir(), _LOG_FILENAME)


def setup_logging(level: int = logging.DEBUG) -> None:
    """
    Configure file + console handlers. Safe to call multiple times
    (subsequent calls are no-ops if handlers are already attached).
    """
    if logger.handlers:
        return  # already configured

    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Rotating file handler ─────────────────────────────────────────────
    try:
        fh = RotatingFileHandler(
            log_path(),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError as exc:
        # Last resort: stderr only
        print(f"[canguru.log] Could not open log file: {exc}", file=sys.stderr)

    # ── Console handler (stderr) — useful during development ─────────────
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    logger.info("=" * 60)
    logger.info("Canguru Player starting — log file: %s", log_path())
    logger.info("Python %s | platform: %s", sys.version.split()[0], sys.platform)


def install_excepthook() -> None:
    """
    Replace sys.excepthook so unhandled exceptions are written to the log
    file instead of (or in addition to) disappearing silently in frozen apps.
    """
    def _hook(exc_type, exc_value, exc_tb):
        logger.critical(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        )
        # Call the original hook (prints to stderr in dev mode)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook
