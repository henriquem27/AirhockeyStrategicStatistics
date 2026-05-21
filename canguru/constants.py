import sys
import os

from PyQt6.QtCore import Qt

VERSION = "1.0"

SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16, 32]

SHOT_TYPES = {
    Qt.Key.Key_1: ("straight",    "1  Straight"),
    Qt.Key.Key_2: ("angle",       "2  Angle"),
    Qt.Key.Key_3: ("bank",        "3  Bank"),
    Qt.Key.Key_4: ("cut",         "4  Cut"),
    Qt.Key.Key_5: ("drift_push",  "5  Drift / Push"),
    Qt.Key.Key_6: ("combo_other", "6  Combo / Other"),
}


def _find_ffmpeg() -> str:
    if getattr(sys, "frozen", False):
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        return os.path.join(sys._MEIPASS, name)
    return "ffmpeg"


FFMPEG = _find_ffmpeg()
