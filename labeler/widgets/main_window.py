import csv
import json
import os
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSlider, QSplitter, QTextEdit,
    QVBoxLayout, QWidget, QComboBox,
)

from .. import theme
from ..constants import SPEEDS, SHOT_TYPES
from ..log import logger
from .crop_dialog import CropDialog
from .video_widget import VideoWidget


def _btn(label="", bg=None, bg_h=None, fg=None, bold=False):
    p = theme.P
    bg   = bg   or p["SURFACE2"]
    bg_h = bg_h or p["BORDER"]
    fg   = fg   or p["TEXT"]
    w = "600" if bold else "400"
    return (
        f"QPushButton {{ background: {bg}; color: {fg}; font-size: 12px; font-weight: {w}; "
        f"padding: 7px 12px; border-radius: 6px; border: 1px solid {p['BORDER']}; }} "
        f"QPushButton:hover {{ background: {bg_h}; border-color: {p['ACCENT']}; }}"
    )

def _btn_primary():
    p = theme.P
    return (
        f"QPushButton {{ background: {p['ACCENT']}; color: white; font-size: 12px; font-weight: 600; "
        f"padding: 7px 14px; border-radius: 6px; border: none; }} "
        f"QPushButton:hover {{ background: {p['ACCENT_H']}; }}"
    )

def _btn_danger():
    p = theme.P
    return (
        f"QPushButton {{ background: transparent; color: {p['DANGER']}; font-size: 12px; "
        f"padding: 7px 12px; border-radius: 6px; border: 1px solid {p['BORDER']}; }} "
        f"QPushButton:hover {{ background: {p['DANGER']}; color: white; border-color: {p['DANGER']}; }}"
    )

def _btn_shot(label_text: str, key: str) -> str:
    p = theme.P
    return (
        f"QPushButton {{ background: {p['SURFACE2']}; color: {p['TEXT']}; "
        f"font-size: 13px; font-weight: 500; text-align: left; "
        f"padding: 8px 12px; border-radius: 6px; border: 1px solid {p['BORDER']}; }} "
        f"QPushButton:hover {{ background: {p['BORDER']}; border-color: {p['ACCENT']}; }} "
        f"QPushButton:pressed {{ background: {p['ACCENT']}; color: white; }}"
    )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.labels: list[dict] = []
        self._current_file: str = ""
        self._crop_rect: tuple[int, int, int, int] | None = None
        self._slider_dragging = False

        self.setWindowTitle("Air Hockey Shot Labeler")
        self.setMinimumSize(1100, 660)
        self.setStyleSheet(
            f"background: {theme.P['BG']}; color: {theme.P['TEXT']}; "
            f"font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;"
        )

        self._setup_ui()
        self._timeline_timer = QTimer(self)
        self._timeline_timer.setInterval(200)
        self._timeline_timer.timeout.connect(self._update_timeline)

        QApplication.instance().installEventFilter(self)

    # ── UI setup ───────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        p = theme.P

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {p['BORDER']}; width: 1px; }}")

        # ── Left: video + transport ────────────────────────────────────────
        left = QWidget()
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(0)

        self.video_widget = VideoWidget(left)
        self.video_widget.playback_ended.connect(self._on_playback_ended)
        left_vbox.addWidget(self.video_widget, 1)

        # Transport bar
        transport = QWidget()
        transport.setFixedHeight(56)
        transport.setStyleSheet(
            f"background: {p['SURFACE']}; border-top: 1px solid {p['BORDER']};"
        )
        tb = QHBoxLayout(transport)
        tb.setContentsMargins(12, 0, 12, 0)
        tb.setSpacing(4)

        def _tbtn(icon, tooltip, slot, accent=False):
            btn = QPushButton(icon)
            btn.setFixedSize(42, 42)
            btn.setToolTip(tooltip)
            style_base = (
                f"QPushButton {{ background: {p['ACCENT'] if accent else 'transparent'}; "
                f"color: {'white' if accent else p['TEXT']}; font-size: 16px; "
                f"border: none; border-radius: 8px; }}"
            )
            style_hover = (
                f"QPushButton:hover {{ background: {p['ACCENT_H'] if accent else p['BORDER']}; }}"
            )
            btn.setStyleSheet(style_base + style_hover)
            btn.clicked.connect(slot)
            return btn

        tb.addWidget(_tbtn("■", "Stop (K)", self._stop))
        tb.addWidget(_tbtn("◀◀", "Back 5s (←)", lambda: self._seek(-5)))
        self._play_btn = _tbtn("▶", "Play / Pause (Space)", self._toggle_pause, accent=True)
        tb.addWidget(self._play_btn)
        tb.addWidget(_tbtn("▶▶", "Forward 5s (→)", lambda: self._seek(5)))

        tb.addSpacing(8)

        self._tl_current = QLabel("0:00")
        self._tl_current.setStyleSheet(
            f"color: {p['TEXT']}; font-size: 12px; font-family: Menlo, Monaco, monospace; "
            f"min-width: 48px; background: transparent;"
        )
        tb.addWidget(self._tl_current)

        self._tl_slider = QSlider(Qt.Orientation.Horizontal)
        self._tl_slider.setRange(0, 1000)
        self._tl_slider.setValue(0)
        self._tl_slider.sliderPressed.connect(self._on_slider_pressed)
        self._tl_slider.sliderMoved.connect(self._on_slider_moved)
        self._tl_slider.sliderReleased.connect(self._on_slider_released)
        self._tl_slider.setStyleSheet(
            f"QSlider::groove:horizontal {{ height: 4px; background: {p['BORDER']}; border-radius: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {p['ACCENT']}; border-radius: 2px; }}"
            f"QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -5px 0; "
            f"background: {p['TEXT']}; border-radius: 7px; }}"
        )
        tb.addWidget(self._tl_slider, 1)

        self._tl_end = QLabel("0:00")
        self._tl_end.setStyleSheet(
            f"color: {p['MUTED']}; font-size: 12px; font-family: Menlo, Monaco, monospace; "
            f"min-width: 48px; background: transparent;"
        )
        self._tl_end.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        tb.addWidget(self._tl_end)

        tb.addSpacing(8)

        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet(f"color: {p['MUTED']}; font-size: 11px; background: transparent;")
        tb.addWidget(speed_lbl)

        self.speed_combo = QComboBox()
        for s in SPEEDS:
            self.speed_combo.addItem(f"{int(s)}x" if s >= 1 else f"{s}x")
        self.speed_combo.setCurrentIndex(SPEEDS.index(1))
        self.speed_combo.setFixedWidth(64)
        self.speed_combo.setStyleSheet(
            f"QComboBox {{ background: {p['SURFACE2']}; color: {p['TEXT']}; "
            f"border: 1px solid {p['BORDER']}; border-radius: 5px; padding: 4px 8px; font-size: 12px; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox QAbstractItemView {{ background: {p['SURFACE2']}; color: {p['TEXT']}; "
            f"border: 1px solid {p['BORDER']}; selection-background-color: {p['ACCENT']}; }}"
        )
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        tb.addWidget(self.speed_combo)

        left_vbox.addWidget(transport)
        splitter.addWidget(left)

        # ── Right: sidebar ─────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        sidebar.setStyleSheet(
            f"background: {p['SURFACE']}; border-left: 1px solid {p['BORDER']};"
        )
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(12, 12, 12, 12)
        sb.setSpacing(8)

        open_btn = QPushButton("Open Video File")
        open_btn.setStyleSheet(_btn_primary())
        open_btn.clicked.connect(self._open_file)
        sb.addWidget(open_btn)

        self._file_lbl = QLabel("No file loaded")
        self._file_lbl.setStyleSheet(
            f"color: {p['MUTED']}; font-size: 10px; background: transparent;"
        )
        self._file_lbl.setWordWrap(True)
        sb.addWidget(self._file_lbl)

        self._crop_btn = QPushButton("Set Table Region")
        self._crop_btn.setStyleSheet(_btn())
        self._crop_btn.setEnabled(False)
        self._crop_btn.setToolTip("Select the table area to crop during labeling")
        self._crop_btn.clicked.connect(self._open_crop_dialog)
        sb.addWidget(self._crop_btn)

        self._crop_lbl = QLabel("")
        self._crop_lbl.setStyleSheet(
            f"color: {p['MUTED']}; font-size: 10px; background: transparent;"
        )
        sb.addWidget(self._crop_lbl)

        sep1 = QWidget()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {p['BORDER']};")
        sb.addWidget(sep1)

        # Shot type buttons
        shot_label = QLabel("Shot Type  (hotkeys 1–6)")
        shot_label.setStyleSheet(f"color: {p['MUTED']}; font-size: 11px; background: transparent;")
        sb.addWidget(shot_label)

        self._shot_btns: dict = {}
        for key, (slug, display) in SHOT_TYPES.items():
            btn = QPushButton(display)
            btn.setStyleSheet(_btn_shot(display, str(key)))
            btn.clicked.connect(lambda checked, s=slug: self._label_shot(s))
            sb.addWidget(btn)
            self._shot_btns[slug] = btn

        sep2 = QWidget()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {p['BORDER']};")
        sb.addWidget(sep2)

        self._label_count_lbl = QLabel("Labels (0):")
        self._label_count_lbl.setStyleSheet(
            f"color: {p['MUTED']}; font-size: 11px; background: transparent;"
        )
        sb.addWidget(self._label_count_lbl)

        self._label_list = QListWidget()
        self._label_list.setStyleSheet(
            f"QListWidget {{ background: {p['SURFACE2']}; border: 1px solid {p['BORDER']}; "
            f"border-radius: 6px; font-family: Menlo, Monaco, monospace; font-size: 11px; "
            f"color: {p['TEXT']}; outline: none; }}"
            f"QListWidget::item {{ padding: 5px 8px; border-bottom: 1px solid {p['BORDER']}; }}"
            f"QListWidget::item:selected {{ background: {p['ACCENT']}; color: white; }}"
            f"QListWidget::item:hover {{ background: {p['BORDER']}; }}"
        )
        self._label_list.itemDoubleClicked.connect(self._on_label_double_clicked)
        sb.addWidget(self._label_list, 1)

        del_btn = QPushButton("Delete Last")
        del_btn.setStyleSheet(_btn_danger())
        del_btn.clicked.connect(self._delete_last)
        sb.addWidget(del_btn)

        export_btn = QPushButton("Export Labels")
        export_btn.setStyleSheet(_btn_primary())
        export_btn.clicked.connect(self._export_labels)
        sb.addWidget(export_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color: {p['ACCENT']}; font-size: 11px; background: transparent;"
        )
        self._status_lbl.setWordWrap(True)
        sb.addWidget(self._status_lbl)

        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    # ── File loading ───────────────────────────────────────────────────────

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Video", os.path.expanduser("~"),
            "Video files (*.mp4 *.MP4 *.mov *.MOV *.avi *.AVI *.mkv *.MKV)"
        )
        if not path:
            return
        self._current_file = os.path.basename(path)
        self._file_lbl.setText(self._current_file)
        self.labels.clear()
        self._crop_rect = None
        self.video_widget.set_crop(None)
        self._crop_lbl.setText("")
        self._refresh_label_list()

        # Open file and pause on first frame so crop dialog can grab it
        self.video_widget.play(path)
        self.video_widget.pause()

        dur = self.video_widget.duration_ms()
        self._tl_end.setText(self._fmt_ms(dur))
        self._tl_slider.setValue(0)
        self._play_btn.setText("▶")
        self._crop_btn.setEnabled(True)
        self._timeline_timer.start()

        # Auto-open crop dialog after a short delay (give VideoWidget time to read frame)
        QTimer.singleShot(300, self._open_crop_dialog)

    def _open_crop_dialog(self) -> None:
        frame = self.video_widget.get_first_frame()
        if frame is None:
            return
        dlg = CropDialog(frame, self)
        if dlg.exec() == CropDialog.DialogCode.Accepted:
            xywh = dlg.crop_xywh()
            self._crop_rect = xywh
            self.video_widget.set_crop(xywh)
            if xywh:
                x, y, w, h = xywh
                self._crop_lbl.setText(f"Crop: {w}×{h} at ({x},{y})")
            else:
                self._crop_lbl.setText("")
        else:
            self._crop_rect = None
            self.video_widget.set_crop(None)
            self._crop_lbl.setText("Full frame")
        # Resume playback after crop is set
        self.video_widget.resume()
        self._play_btn.setText("⏸")

    # ── Labeling ───────────────────────────────────────────────────────────

    def _label_shot(self, shot_type: str) -> None:
        if not self._current_file:
            self._flash_status("Open a video file first.")
            return
        ms = self.video_widget.position_ms()
        entry = {"file": self._current_file, "timestamp_ms": ms, "shot_type": shot_type}
        self.labels.append(entry)
        self._refresh_label_list()
        self._flash_status(f"Labeled: {shot_type} @ {ms}ms")
        logger.debug("Label added: %s @ %d ms", shot_type, ms)

    def _refresh_label_list(self) -> None:
        self._label_list.clear()
        for entry in reversed(self.labels):
            ms = entry["timestamp_ms"]
            text = f"{self._fmt_ms(ms)}  {entry['shot_type']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, ms)
            self._label_list.addItem(item)
        n = len(self.labels)
        self._label_count_lbl.setText(f"Labels ({n}):")

    def _on_label_double_clicked(self, item: QListWidgetItem) -> None:
        ms = item.data(Qt.ItemDataRole.UserRole)
        if ms is not None:
            self.video_widget.seek_to_ms(ms)

    def _delete_last(self) -> None:
        if not self.labels:
            return
        removed = self.labels.pop()
        self._refresh_label_list()
        self._flash_status(f"Removed: {removed['shot_type']} @ {removed['timestamp_ms']}ms")

    # ── Export ─────────────────────────────────────────────────────────────

    def _export_labels(self) -> None:
        if not self.labels:
            QMessageBox.warning(self, "Nothing to export", "No labels recorded yet.")
            return

        out_dir = os.path.join(os.getcwd(), "labeled")
        os.makedirs(out_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export = {
            "crop_xywh": list(self._crop_rect) if self._crop_rect else None,
            "labels": self.labels,
        }
        json_path = os.path.join(out_dir, f"labels_{stamp}.json")
        with open(json_path, "w") as f:
            json.dump(export, f, indent=2)

        csv_path = os.path.join(out_dir, f"labels_{stamp}.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "timestamp_ms", "shot_type"])
            writer.writeheader()
            writer.writerows(self.labels)

        QMessageBox.information(
            self, "Exported",
            f"Saved {len(self.labels)} labels to:\n{json_path}\n{csv_path}"
        )
        logger.info("Exported %d labels to %s", len(self.labels), out_dir)

    # ── Playback controls ──────────────────────────────────────────────────

    def _toggle_pause(self) -> None:
        if not self.video_widget.is_open():
            return
        playing = self.video_widget.toggle_pause()
        self._play_btn.setText("⏸" if playing else "▶")

    def _stop(self) -> None:
        self.video_widget.stop()
        self._timeline_timer.stop()
        self._play_btn.setText("▶")
        self._tl_current.setText("0:00")
        self._tl_slider.setValue(0)

    def _seek(self, seconds: float) -> None:
        self.video_widget.seek_by(seconds)

    def _on_playback_ended(self) -> None:
        self._play_btn.setText("▶")
        self._timeline_timer.stop()

    def _on_speed_changed(self, index: int) -> None:
        self.video_widget.set_speed(SPEEDS[index])

    def _speed_up(self) -> None:
        idx = self.speed_combo.currentIndex()
        if idx < len(SPEEDS) - 1:
            self.speed_combo.setCurrentIndex(idx + 1)

    def _speed_down(self) -> None:
        idx = self.speed_combo.currentIndex()
        if idx > 0:
            self.speed_combo.setCurrentIndex(idx - 1)

    # ── Timeline ───────────────────────────────────────────────────────────

    def _update_timeline(self) -> None:
        if self._slider_dragging or not self.video_widget.is_open():
            return
        pos = self.video_widget.position_ms()
        dur = self.video_widget.duration_ms()
        self._tl_current.setText(self._fmt_ms(pos))
        if dur > 0:
            self._tl_slider.setValue(int(pos / dur * 1000))

    def _on_slider_pressed(self) -> None:
        self._slider_dragging = True

    def _on_slider_moved(self, value: int) -> None:
        dur = self.video_widget.duration_ms()
        if dur > 0:
            ms = int(value / 1000 * dur)
            self._tl_current.setText(self._fmt_ms(ms))

    def _on_slider_released(self) -> None:
        self._slider_dragging = False
        dur = self.video_widget.duration_ms()
        if dur > 0:
            ms = int(self._tl_slider.value() / 1000 * dur)
            self.video_widget.seek_to_ms(ms)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        s = ms // 1000
        m = s // 60
        s = s % 60
        return f"{m}:{s:02d}"

    def _flash_status(self, msg: str) -> None:
        self._status_lbl.setText(msg)
        QTimer.singleShot(2500, lambda: self._status_lbl.setText(""))

    # ── Keyboard ───────────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        if event.type() != QEvent.Type.KeyPress:
            return False
        focused = QApplication.focusWidget()
        if isinstance(focused, (QLineEdit, QTextEdit)):
            return False

        key = event.key()

        if key in SHOT_TYPES:
            slug, _ = SHOT_TYPES[key]
            self._label_shot(slug)
            return True
        elif key in (Qt.Key.Key_Space, Qt.Key.Key_P):
            self._toggle_pause()
        elif key == Qt.Key.Key_K:
            self._stop()
        elif key == Qt.Key.Key_Left:
            self._seek(-5)
        elif key == Qt.Key.Key_Right:
            self._seek(5)
        elif key == Qt.Key.Key_J:
            self._speed_down()
        elif key == Qt.Key.Key_L:
            self._speed_up()
        else:
            return False
        return True

    def closeEvent(self, event) -> None:
        self.video_widget.stop()
        super().closeEvent(event)
