import os
import threading
import time

import cv2
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..log import logger

_MAX_READ_ERRORS = 8

os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "hwaccel;none")


class VideoWidget(QWidget):
    playback_ended = pyqtSignal()

    _frame_ready_sig = pyqtSignal(object)
    _error_sig = pyqtSignal(str)
    _info_sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cap: cv2.VideoCapture | None = None
        self._paused = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending_seek_frame: float | None = None
        self._fps = 25.0
        self._total_frames = 0
        self._read_errors = 0
        self._error_state = False
        self._current_filepath: str | None = None
        self._crop: tuple[int, int, int, int] | None = None  # (x, y, w, h) in frame pixels

        self._frame_ready_sig.connect(self._on_frame_ready)
        self._error_sig.connect(self._on_show_error)
        self._info_sig.connect(self._on_info)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background: #0d0d0d;")
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setMinimumSize(320, 240)

        self.info_label = QLabel()
        self.info_label.setStyleSheet(
            "color: white; background: rgba(0,0,0,180); "
            "padding: 2px 6px; font-size: 11px; font-family: 'Courier New', Courier, monospace;"
        )
        self.info_label.setMaximumHeight(20)

        layout.addWidget(self.video_label, 1)
        layout.addWidget(self.info_label)
        self.setStyleSheet("border: 1px solid #333;")

    # ── Public API ─────────────────────────────────────────────────────────

    def set_crop(self, xywh: tuple[int, int, int, int] | None) -> None:
        self._crop = xywh

    def get_first_frame(self) -> "np.ndarray | None":
        """Return the first frame of the currently open file, or None."""
        with self._lock:
            if not self.cap:
                return None
            pos = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            return frame if ret else None

    def play(self, filepath: str) -> None:
        self.stop()
        self._current_filepath = filepath
        self._error_state = False
        self._paused = False
        self._read_errors = 0

        self.cap = cv2.VideoCapture(filepath, cv2.CAP_FFMPEG)
        if not self.cap.isOpened():
            logger.error("Cannot open: %s", filepath)
            self._show_error("File not found")
            return

        self._fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self._total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.info_label.setText(f"{filepath.split('/')[-1]}  [{self._fps:.1f} fps]")
        self._start_thread()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        if self._error_state:
            return
        self._paused = False
        self._start_thread()

    def toggle_pause(self) -> bool:
        """Toggle play/pause. Returns True if now playing."""
        if self._paused:
            self.resume()
            return True
        else:
            self.pause()
            return False

    def stop(self) -> None:
        self._paused = False
        self._read_errors = 0
        self._error_state = False
        self._pending_seek_frame = None
        self._stop_thread()
        with self._lock:
            if self.cap:
                self.cap.release()
                self.cap = None
        self.info_label.setText("")
        self.video_label.setPixmap(QPixmap())
        self.video_label.setStyleSheet("background: #0d0d0d;")

    def set_speed(self, speed: float) -> None:
        self._speed = speed

    def seek_by(self, seconds: float) -> None:
        if not self.cap:
            return
        current = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        target = max(0.0, current + seconds * self._fps)
        self._pending_seek_frame = target

    def seek_to_ms(self, ms: int) -> None:
        if not self.cap:
            return
        self._pending_seek_frame = ms / 1000.0 * self._fps

    def position_ms(self) -> int:
        if not self.cap:
            return 0
        frame = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        return int(frame / self._fps * 1000) if self._fps > 0 else 0

    def duration_ms(self) -> int:
        if self._fps > 0 and self._total_frames > 0:
            return int(self._total_frames / self._fps * 1000)
        return 0

    def is_open(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    # ── Internal ───────────────────────────────────────────────────────────

    def _show_error(self, message: str) -> None:
        self._error_state = True
        self.info_label.setText(f"⚠ {message}")
        self.info_label.setStyleSheet(
            "color: #ef4444; background: rgba(0,0,0,180); "
            "padding: 2px 6px; font-size: 11px;"
        )

    def _on_frame_ready(self, frame: np.ndarray) -> None:
        if self._crop:
            x, y, w, h = self._crop
            fh, fw = frame.shape[:2]
            x2 = min(x + w, fw)
            y2 = min(y + h, fh)
            if x2 > x and y2 > y:
                frame = frame[y:y2, x:x2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fh, fw, ch = rgb.shape
        img = QImage(rgb.tobytes(), fw, fh, ch * fw, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.video_label.setPixmap(pix)

    def _on_show_error(self, message: str) -> None:
        self._show_error(message)

    def _on_info(self, text: str) -> None:
        self.info_label.setText(text)

    def _start_thread(self) -> None:
        if not self._running:
            self._running = True
            self._speed = getattr(self, "_speed", 1.0)
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _stop_thread(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _loop(self) -> None:
        while self._running:
            pending = self._pending_seek_frame
            if pending is not None:
                self._pending_seek_frame = None
                with self._lock:
                    if self.cap:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(pending))
                        ret, frame = self.cap.read()
                        if ret:
                            self._frame_ready_sig.emit(frame)
                time.sleep(0.03)
                continue

            if self._paused or self._error_state:
                time.sleep(0.03)
                continue

            with self._lock:
                if not self.cap or not self._running:
                    time.sleep(0.03)
                    continue

                speed = getattr(self, "_speed", 1.0)
                frames_to_skip = max(1, int(speed * self._fps * 0.030))
                last_frame = None

                for i in range(frames_to_skip):
                    if i < frames_to_skip - 1:
                        ret = self.cap.grab()
                    else:
                        ret, frame = self.cap.read()
                        if ret:
                            last_frame = frame

                    if not ret:
                        self._read_errors += 1
                        if self._read_errors >= _MAX_READ_ERRORS:
                            self._running = False
                            self.playback_ended.emit()
                            return
                        break
                    else:
                        self._read_errors = 0

            if last_frame is not None:
                self._frame_ready_sig.emit(last_frame)

            time.sleep(0.03)
