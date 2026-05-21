"""
Dialog that asks the labeler for their name on first launch.
The name is stored in a small JSON config file next to the app
and is embedded in every exported label row.
"""
from __future__ import annotations

import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout,
)

from .. import theme

# Config file lives next to the executable / script so it persists across runs.
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "labeler_config.json",
)
_CONFIG_PATH = os.path.normpath(_CONFIG_PATH)


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(data: dict) -> None:
    try:
        with open(_CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # non-fatal


def get_or_ask_name(parent=None) -> str:
    """Return the stored labeler name, or prompt the user if not set yet."""
    config = _load_config()
    name = config.get("labeler_name", "").strip()
    if name:
        return name

    dlg = NameDialog(parent)
    dlg.exec()
    name = dlg.name().strip() or "Unknown"

    config["labeler_name"] = name
    _save_config(config)
    return name


class NameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        p = theme.P

        self.setWindowTitle("Welcome to Air Hockey Shot Labeler")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setStyleSheet(
            f"background: {p['BG']}; color: {p['TEXT']}; "
            f"font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        title = QLabel("👋  What's your name?")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {p['TEXT']}; background: transparent;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Your name will be attached to every label you export so we know who labeled what. "
            "This is stored locally and only asked once."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"font-size: 12px; color: {p['MUTED']}; background: transparent;"
        )
        layout.addWidget(subtitle)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Jane Smith")
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: {p['SURFACE2']}; color: {p['TEXT']}; "
            f"border: 1px solid {p['BORDER']}; border-radius: 6px; "
            f"padding: 8px 12px; font-size: 14px; }}"
            f"QLineEdit:focus {{ border-color: {p['ACCENT']}; }}"
        )
        layout.addWidget(self._name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Let's go →")
        ok_btn.setStyleSheet(
            f"QPushButton {{ background: {p['ACCENT']}; color: white; font-size: 13px; "
            f"font-weight: 600; padding: 8px 20px; border-radius: 6px; border: none; }}"
            f"QPushButton:hover {{ background: {p['ACCENT_H']}; }}"
        )
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignRight)

        self._name_edit.returnPressed.connect(self.accept)
        self._name_edit.setFocus()

    def name(self) -> str:
        return self._name_edit.text().strip()
