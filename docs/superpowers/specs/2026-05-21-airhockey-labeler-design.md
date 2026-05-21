# Air Hockey Shot Labeler — Design Spec

**Date:** 2026-05-21  
**Status:** Approved

---

## Goal

Repurpose the existing Canguru DVR player (PyQt6 + OpenCV) into a single-video shot-labeling tool for the Air Hockey Strategic Statistics project. Remove all H264/DVR/license-specific code and replace the sidebar with a labeling panel.

---

## What Changes

### Files deleted
- `canguru/license.py`
- `canguru/api_client.py`
- `canguru/scanner.py`
- `canguru/sync.py`
- `canguru/trim_worker.py`
- `canguru/metadata.py`
- `canguru/wfs_direct.py`
- `canguru/annotator.py`
- `canguru/exporter.py`
- `canguru/count_worker.py`
- `canguru/config.py`
- `canguru/widgets/license_dialog.py`
- `canguru/widgets/settings_dialog.py`
- `canguru/widgets/shortcuts_dialog.py`
- `canguru/widgets/trim_dialog.py`
- `canguru/widgets/capture_dialog.py`
- `generate_license.py`
- `private.pem`
- `player.c`
- `CanguruPlayer.spec`
- `Makefile`
- `hooks/`

### Files kept and modified

| File | Change |
|---|---|
| `player_gui.py` | Remove license check, config, setproctitle; straight to QApplication → MainWindow |
| `canguru/theme.py` | No change |
| `canguru/log.py` | No change |
| `canguru/constants.py` | Remove H264 pattern, DVR shortcuts, ocorrencias; add `SHOT_TYPES` dict |
| `canguru/widgets/__init__.py` | Update import to new MainWindow |
| `canguru/widgets/video_widget.py` | Strip H264 conversion, gap detection, chunks, MasterClock; keep core OpenCV frame loop + rendering; add `position_ms()` |
| `canguru/widgets/main_window.py` | Full rewrite: labeling layout |

---

## New `constants.py` additions

```python
from PyQt6.QtCore import Qt

SHOT_TYPES = {
    Qt.Key.Key_1: ("straight",   "Straight"),
    Qt.Key.Key_2: ("angle",      "Angle"),
    Qt.Key.Key_3: ("bank",       "Bank"),
    Qt.Key.Key_4: ("cut",        "Cut"),
    Qt.Key.Key_5: ("drift_push", "Drift / Push"),
    Qt.Key.Key_6: ("combo_other","Combo / Other"),
}
```

---

## VideoWidget simplification

Remove (~200 lines deleted):
- `_start_conversion()`, `_estimate_h264_fps()` — H264→MP4 background conversion
- `_advance_chunk()`, `set_chunks()` — multi-chunk DVR playback
- `set_master_clock()`, `set_slot_end_dt()` — sync clock
- `gap_detected` signal, gap/SSD logic in `_loop()`
- `_ended_early`, `_mp4_ready`, `_convert_*`, `_is_indexed`, `_needs_conversion_path`

Keep:
- `play(filepath)`, `pause()`, `resume()`, `stop()`
- `seek_by(seconds)`, `_manual_seek()`
- `_loop()` — simplified (no clock sync, no chunk advancing, no gap detection)
- `_on_frame_ready()`, frame rendering to QLabel

Add:
- `position_ms() -> int` — `int(cap.get(CAP_PROP_POS_FRAMES) / effective_fps * 1000)`
- `duration_ms() -> int` — `int(total_frames / effective_fps * 1000)`

`play()` signature simplifies to `play(filepath: str)` — no `file_start_dt`, `file_end_dt`.

Signal kept: `playback_ended`  
Signal removed: `gap_detected`, `conversion_ready`

---

## New MainWindow layout

```
┌──────────────────────────────────┬──────────────────┐
│                                  │  [Open File]     │
│                                  │                  │
│                                  │  [1] Straight    │
│         VIDEO (full height)      │  [2] Angle       │
│                                  │  [3] Bank        │
│                                  │  [4] Cut         │
│                                  │  [5] Drift/Push  │
│                                  │  [6] Combo/Other │
│                                  │                  │
│                                  │  Labels (0):     │
│                                  │  ┌────────────┐  │
│                                  │  │00:14 bank  │  │
│                                  │  │00:27 str…  │  │
│                                  │  └────────────┘  │
│                                  │  [Delete Last]   │
│                                  │  [Export Labels] │
├──────────────────────────────────┴──────────────────┤
│  [■] [◀◀] [▶] [▶▶]  00:14 ─────●──── 01:45  1x   │
└─────────────────────────────────────────────────────┘
```

### Sidebar contents (top→bottom)
1. **Open File** button — `QFileDialog.getOpenFileName` filtered to `*.mp4 *.MP4`
2. **Current file label** — shows filename
3. **Shot type panel** — 6 labeled buttons (clickable + keyboard), highlight on press
4. **Label count heading** — "Labels (n):"
5. **Label list** — `QListWidget`, items formatted as `MM:SS.mmm  shot_type`, most recent at top; double-click to seek to that timestamp
6. **Delete Last** button — removes last label entry
7. **Export Labels** button — writes JSON + CSV to `labeled/` under cwd

### Transport bar (bottom, reused from DVR player)
- Stop ■, Back ◀◀ (−5 s), Play/Pause ▶, Forward ▶▶ (+5 s)
- Time label `MM:SS` | Seek slider (0–1000) | Duration label
- Speed combo (0.25× → 32×)

---

## Hotkeys

| Key | Action |
|---|---|
| `1` | Label: Straight |
| `2` | Label: Angle |
| `3` | Label: Bank |
| `4` | Label: Cut |
| `5` | Label: Drift / Push |
| `6` | Label: Combo / Other |
| `Space` / `P` | Play / Pause |
| `K` | Stop |
| `←` | Seek −5 s |
| `→` | Seek +5 s |
| `J` | Speed down |
| `L` | Speed up |

---

## Label schema

```json
[
  {"file": "clip_001.mp4", "timestamp_ms": 14320, "shot_type": "bank"},
  {"file": "clip_001.mp4", "timestamp_ms": 27810, "shot_type": "straight"}
]
```

Exported to:
- `labeled/labels_YYYYMMDD_HHMMSS.json`
- `labeled/labels_YYYYMMDD_HHMMSS.csv` (columns: `file,timestamp_ms,shot_type`)

---

## Label entry flow

1. User presses `1`–`6` (or clicks a shot button) while video is playing or paused
2. `position_ms()` is read from `VideoWidget`
3. Entry appended to `self.labels` list
4. Status bar shows `"Labeled: bank @ 14320ms"` for 2 s
5. Label list updates (new item at top)

---

## Entry point (`player_gui.py`)

```python
app = QApplication(sys.argv)
app.setApplicationName("AH Labeler")
app.setStyle("Fusion")
theme.apply("dark")
win = MainWindow()
win.show()
sys.exit(app.exec())
```

No license check, no config file, no setproctitle dependency.

---

## Requirements

```
pyqt6
opencv-python
pandas        # for CSV export (or use stdlib csv)
```

`yt-dlp` and `ffmpeg` are not required by the labeler itself (they're used upstream for footage download/segmentation per the README).
