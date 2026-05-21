from PyQt6.QtCore import Qt

VERSION = "1.2"

SPEEDS = [0.25, 0.5, 1, 2, 4, 8, 16, 32]

SHOT_TYPES = {
    Qt.Key.Key_1: ("cut_straight", "1  Cut Straight"),
    Qt.Key.Key_2: ("cross_straight", "2  Cross Straight"),
    Qt.Key.Key_3: ("rw_under",     "3  Right-wall under (RWU) bank"),
    Qt.Key.Key_4: ("lw_under",     "4  Left-wall under (LWU) bank"),
    Qt.Key.Key_5: ("rw_over",      "5  Right-wall over (RWO) bank"),
    Qt.Key.Key_6: ("lw_over",      "6  Left-wall over (LWO) bank"),
    Qt.Key.Key_7: ("forehands",    "7  Forehands"),
}
