import cv2
import numpy as np
from PyQt6.QtCore import Qt, QRect, QRectF, QPoint
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QSizePolicy, QWidget,
)

from .. import theme


class _FrameCanvas(QWidget):
    """Widget that shows a frame and lets the user drag a crop rectangle."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._orig = pixmap          # full-resolution source pixmap
        self._start: QPoint | None = None
        self._rect: QRect | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMinimumSize(400, 300)

    # ── Coordinate helpers ─────────────────────────────────────────────────

    def _layout(self) -> tuple[int, int, float]:
        """Return (offset_x, offset_y, scale) for the current widget size."""
        ww, wh = self.width(), self.height()
        iw, ih = self._orig.width(), self._orig.height()
        if iw == 0 or ih == 0:
            return 0, 0, 1.0
        scale = min(ww / iw, wh / ih)
        ox = int((ww - iw * scale) / 2)
        oy = int((wh - ih * scale) / 2)
        return ox, oy, scale

    def rect_in_image(self) -> QRect | None:
        """Return the crop rect in original image pixel coordinates, or None."""
        if not self._rect or abs(self._rect.width()) < 4 or abs(self._rect.height()) < 4:
            return None
        ox, oy, scale = self._layout()
        iw, ih = self._orig.width(), self._orig.height()
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

    # ── Mouse events ───────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._rect = QRect(self._start, self._start)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._start:
            self._rect = QRect(self._start, event.pos())
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._start:
            self._rect = QRect(self._start, event.pos()).normalized()
            self._start = None
            self.update()

    # ── Paint ──────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        ox, oy, scale = self._layout()
        iw, ih = self._orig.width(), self._orig.height()
        sw, sh = int(iw * scale), int(ih * scale)
        scaled = self._orig.scaled(
            sw, sh,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0d0d0d"))
        p.drawPixmap(ox, oy, scaled)

        if self._rect and abs(self._rect.width()) >= 4 and abs(self._rect.height()) >= 4:
            r = self._rect.normalized()
            # Dim everything
            p.fillRect(self.rect(), QColor(0, 0, 0, 130))
            # Restore image inside selection (undimmed)
            src = QRectF(r.x() - ox, r.y() - oy, r.width(), r.height())
            p.drawPixmap(QRectF(r), scaled, src)
            # Blue border
            p.setPen(QPen(QColor("#3b82f6"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
            # Dimension label
            ir = self.rect_in_image()
            if ir:
                p.setPen(QColor("white"))
                p.drawText(r.bottomLeft() + QPoint(4, -4),
                           f"{ir.width()} × {ir.height()}")
        p.end()


class CropDialog(QDialog):
    """Shows the first frame of a video and lets the user drag a crop rectangle."""

    def __init__(self, frame: np.ndarray, parent=None):
        super().__init__(parent)
        p = theme.P
        self.setWindowTitle("Select Table Region")
        self.setMinimumSize(860, 600)
        self.setStyleSheet(f"background: {p['BG']}; color: {p['TEXT']};")

        self._crop: QRect | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel("Drag to select the table region, then click Confirm.")
        hint.setStyleSheet(f"color: {p['MUTED']}; font-size: 12px;")
        layout.addWidget(hint)

        self._canvas = _FrameCanvas(self._to_pixmap(frame), self)
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
            # Nothing drawn — treat as skip
            self.reject()

    def crop_xywh(self) -> tuple[int, int, int, int] | None:
        """Returns (x, y, w, h) in original frame pixels, or None if skipped."""
        if self._crop:
            return (self._crop.x(), self._crop.y(),
                    self._crop.width(), self._crop.height())
        return None

    @staticmethod
    def _to_pixmap(frame: np.ndarray) -> QPixmap:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img)
