from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSizePolicy,
)

import cv2
import numpy as np

from .. import theme


class _FrameCanvas(QLabel):
    """QLabel that lets the user drag a crop rectangle."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._base = pixmap
        self._start: QPoint | None = None
        self._end: QPoint | None = None
        self._rect: QRect | None = None
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def rect_in_image(self) -> QRect | None:
        """Return the crop rect in original image coordinates, or None."""
        if not self._rect or self._rect.width() < 4 or self._rect.height() < 4:
            return None
        # Map from widget coords → image coords
        pix = self._base
        ww, wh = self.width(), self.height()
        iw, ih = pix.width(), pix.height()
        # Letterbox offsets
        scale = min(ww / iw, wh / ih)
        ox = (ww - iw * scale) / 2
        oy = (wh - ih * scale) / 2

        r = self._rect.normalized()
        x = int((r.x() - ox) / scale)
        y = int((r.y() - oy) / scale)
        w = int(r.width() / scale)
        h = int(r.height() / scale)
        x = max(0, min(x, iw - 1))
        y = max(0, min(y, ih - 1))
        w = min(w, iw - x)
        h = min(h, ih - y)
        if w < 4 or h < 4:
            return None
        return QRect(x, y, w, h)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._rect = QRect(self._start, self._end)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._start:
            self._end = event.pos()
            self._rect = QRect(self._start, self._end)
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._start:
            self._end = event.pos()
            self._rect = QRect(self._start, self._end).normalized()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._rect:
            return
        painter = QPainter(self)
        r = self._rect.normalized()
        # Dim outside
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        # Clear inside selection
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(r, QColor(0, 0, 0, 255))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        # Border
        pen = QPen(QColor("#3b82f6"), 2)
        painter.setPen(pen)
        painter.drawRect(r)
        # Size hint
        img_rect = self.rect_in_image()
        if img_rect:
            painter.setPen(QColor("white"))
            painter.drawText(r.bottomLeft() + QPoint(4, -4),
                             f"{img_rect.width()}×{img_rect.height()}")
        painter.end()


class CropDialog(QDialog):
    """Shows the first frame of a video and lets the user drag a crop rectangle."""

    def __init__(self, frame: np.ndarray, parent=None):
        super().__init__(parent)
        p = theme.P
        self.setWindowTitle("Select Table Region")
        self.setMinimumSize(800, 560)
        self.setStyleSheet(f"background: {p['BG']}; color: {p['TEXT']};")

        self._crop: QRect | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel("Drag to select the table region. Press Confirm when done.")
        hint.setStyleSheet(f"color: {p['MUTED']}; font-size: 12px;")
        layout.addWidget(hint)

        pix = self._frame_to_pixmap(frame)
        self._canvas = _FrameCanvas(pix, self)
        layout.addWidget(self._canvas, 1)

        btn_row = QHBoxLayout()
        skip_btn = QPushButton("Skip (use full frame)")
        skip_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {p['MUTED']}; "
            f"font-size: 12px; padding: 7px 14px; border-radius: 6px; "
            f"border: 1px solid {p['BORDER']}; }} "
            f"QPushButton:hover {{ color: {p['TEXT']}; }}"
        )
        skip_btn.clicked.connect(self.reject)

        confirm_btn = QPushButton("Confirm Selection")
        confirm_btn.setStyleSheet(
            f"QPushButton {{ background: {p['ACCENT']}; color: white; "
            f"font-size: 12px; font-weight: 600; padding: 7px 14px; "
            f"border-radius: 6px; border: none; }} "
            f"QPushButton:hover {{ background: {p['ACCENT_H']}; }}"
        )
        confirm_btn.clicked.connect(self._confirm)

        btn_row.addStretch()
        btn_row.addWidget(skip_btn)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

    def _confirm(self) -> None:
        r = self._canvas.rect_in_image()
        if r:
            self._crop = r
            self.accept()
        else:
            self.reject()

    def crop_xywh(self) -> tuple[int, int, int, int] | None:
        """Returns (x, y, w, h) in original frame pixels, or None if skipped."""
        if self._crop:
            return (self._crop.x(), self._crop.y(),
                    self._crop.width(), self._crop.height())
        return None

    @staticmethod
    def _frame_to_pixmap(frame: np.ndarray) -> QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img)
