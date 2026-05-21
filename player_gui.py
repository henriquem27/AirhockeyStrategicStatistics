#!/usr/bin/env python3
import os
import sys

os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")

from PyQt6.QtWidgets import QApplication

from labeler import theme
from labeler.log import setup_logging, install_excepthook
from labeler.widgets import MainWindow
from labeler.widgets.name_dialog import get_or_ask_name


def main() -> None:
    setup_logging()
    install_excepthook()

    app = QApplication(sys.argv)
    app.setApplicationName("AH Labeler")
    app.setApplicationDisplayName("Air Hockey Shot Labeler")
    app.setStyle("Fusion")

    theme.apply("dark")

    # Ask for labeler name on first run (no-op if already stored)
    labeler_name = get_or_ask_name()

    win = MainWindow(labeler_name=labeler_name)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
