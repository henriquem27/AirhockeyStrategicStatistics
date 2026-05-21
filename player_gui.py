#!/usr/bin/env python3
import os
import sys

os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")

from PyQt6.QtWidgets import QApplication

from canguru import theme
from canguru.log import setup_logging, install_excepthook
from canguru.widgets import MainWindow


def main() -> None:
    setup_logging()
    install_excepthook()

    app = QApplication(sys.argv)
    app.setApplicationName("AH Labeler")
    app.setApplicationDisplayName("Air Hockey Shot Labeler")
    app.setStyle("Fusion")

    theme.apply("dark")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
