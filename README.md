# Airhockey Strategic Statistics

A complete pipeline for downloading air hockey tournament footage, annotating shot types using a PyQt6 labeling tool, and preparing a dataset for ML training.
And a Model to classify the shots.

---

## Table of Contents

1. [Overview](#overview)
2. [Shot Type Taxonomy](#shot-type-taxonomy)
3. [Prerequisites](#prerequisites)
4. [Step 1 — Download Footage](#step-1--download-footage)
5. [Step 2 — Extract & Segment Clips](#step-2--extract--segment-clips)
6. [Step 3 — Labeling Tool Setup](#step-3--labeling-tool-setup)
7. [Step 4 — Labeling Workflow](#step-4--labeling-workflow)
8. [Step 5 — Validate & Export Dataset](#step-5--validate--export-dataset)
9. [Output Format](#output-format)
10. [Folder Structure](#folder-structure)

---

## Overview

This pipeline turns raw tournament footage (YouTube streams, local MP4s) into a labeled dataset of air hockey shot clips suitable for training a video classification model.

**Rough effort estimate:**
| Stage | Time |
|---|---|
| Downloading footage | 30–60 min |
| Preprocessing / segmenting | 1–2 hrs |
| Labeling (per annotator) | 3–5 hrs for ~1,500 clips |
| Dataset validation | 30 min |

---

## Shot Type Taxonomy

Annotators must agree on these definitions before labeling. Consistency matters more than perfection.

| # | Label Key | Shot Type | Description |
|---|---|---|---|
| 1 | `1` | **Straight** | Puck travels directly forward with no lateral angle |
| 2 | `2` | **Angle** | Puck is shot diagonally toward the goal without bouncing off a wall |
| 3 | `3` | **Bank** | Puck deflects off one or more side rails before reaching the goal |
| 4 | `4` | **cut_straight** | Short, sharp redirected shot using wrist flick; changes direction abruptly |
| 5 | `5` | **Drift / Push** | Slow, controlled slide; no snap — used to bait or set up |
| 6 | `6` | **Combo / Other** | Multi-step shot or any shot that doesn't clearly fit the above |

> **Tip:** When in doubt between two classes, use `6` (Combo/Other). A clean dataset beats a large ambiguous one.

---

## Prerequisites

### System Requirements
- Python 3.10+
- FFmpeg installed and on PATH
- PyQt6
- yt-dlp

### Install dependencies

```bash
pip install yt-dlp pyqt6 opencv-python pandas
```

### Verify FFmpeg

```bash
ffmpeg -version
```

If not installed:
- **Ubuntu/Debian:** `sudo apt install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

---

## Step 1 — Download Footage

Use `yt-dlp` to download tournament streams or match VODs from YouTube.

### Single video

```bash
yt-dlp \
  -f "bestvideo[height<=1080][fps>=60]+bestaudio/bestvideo[height<=1080]+bestaudio" \
  --merge-output-format mp4 \
  --write-info-json \
  -o "raw_footage/%(title)s_%(id)s.%(ext)s" \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Batch download (multiple URLs)

Create a file `urls.txt` with one URL per line:

```
https://www.youtube.com/watch?v=ABC123
https://www.youtube.com/watch?v=DEF456
```

Then run:

```bash
yt-dlp \
  -f "bestvideo[height<=1080][fps>=60]+bestaudio/bestvideo[height<=1080]+bestaudio" \
  --merge-output-format mp4 \
  --write-info-json \
  -o "raw_footage/%(title)s_%(id)s.%(ext)s" \
  -a urls.txt
```

### Target specs
- **Resolution:** 1080p (720p acceptable; 4K is overkill)
- **Frame rate:** 60fps strongly preferred — puck motion is too fast for 30fps clips to be useful
- **Format:** MP4

### Extract a specific time range (optional)

If you only need a portion of a long stream:

```bash
ffmpeg -ss 00:10:30 -to 01:45:00 -i "raw_footage/input.mp4" -c copy "raw_footage/trimmed.mp4"
```

---

## Step 2 — Extract & Segment Clips

Before labeling, break long videos into shorter, manageable segments. This is optional but makes the labeling tool faster and reduces the chance of annotators getting fatigued on one file.

### Segment a video into 5-minute chunks

```bash
ffmpeg -i "raw_footage/input.mp4" \
  -c copy -map 0 \
  -segment_time 300 \
  -f segment \
  -reset_timestamps 1 \
  "segments/clip_%03d.mp4"
```

All segments land in `segments/` and are ready to load into the labeling tool.

---

## Step 3 — Labeling Tool Setup

The labeling tool is a repurposed PyQt6 DVR player. It adds shot-type hotkeys, a timestamp logger, and JSON/CSV export on top of the existing video playback controls.

### Install the tool

Clone or copy the `labeler/` folder into this project directory (see [Folder Structure](#folder-structure)).

```bash
pip install pyqt6 pandas
```

### Launch

```bash
python labeler/main.py
```

### Recommended additions to the existing DVR player

Below are the specific modifications needed to convert the DVR player into a labeling tool. Apply these to your existing `main.py` / player class:

#### 1. Add shot label state and output buffer

```python
# At the top of your player class __init__
self.labels = []  # list of dicts: {file, timestamp_ms, shot_type}
self.current_file = ""

SHOT_TYPES = {
    Qt.Key.Key_1: "straight",
    Qt.Key.Key_2: "angle",
    Qt.Key.Key_3: "bank",
    Qt.Key.Key_4: "cut",
    Qt.Key.Key_5: "drift_push",
    Qt.Key.Key_6: "combo_other",
}
```

#### 2. Override keyPressEvent to capture labels

```python
def keyPressEvent(self, event):
    key = event.key()

    if key in SHOT_TYPES:
        timestamp_ms = self.media_player.position()  # QMediaPlayer .position()
        label = SHOT_TYPES[key]
        entry = {
            "file": self.current_file,
            "timestamp_ms": timestamp_ms,
            "shot_type": label,
        }
        self.labels.append(entry)
        self.status_bar.showMessage(f"Labeled: {label} @ {timestamp_ms}ms", 2000)

    # Pass other keys to existing handler
    else:
        super().keyPressEvent(event)
```

#### 3. Add export button to toolbar

```python
export_btn = QPushButton("Export Labels")
export_btn.clicked.connect(self.export_labels)
self.toolbar.addWidget(export_btn)
```

#### 4. Export method

```python
import json, csv, os
from datetime import datetime

def export_labels(self):
    if not self.labels:
        QMessageBox.warning(self, "Nothing to export", "No labels recorded yet.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = "labeled"
    os.makedirs(out_dir, exist_ok=True)

    # JSON
    json_path = f"{out_dir}/labels_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump(self.labels, f, indent=2)

    # CSV
    csv_path = f"{out_dir}/labels_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "timestamp_ms", "shot_type"])
        writer.writeheader()
        writer.writerows(self.labels)

    QMessageBox.information(self, "Exported", f"Saved to:\n{json_path}\n{csv_path}")
```

#### 5. Track current file on open

In your existing file-open handler, add:

```python
self.current_file = os.path.basename(file_path)
```

---

## Step 4 — Labeling Workflow

Share this section with every annotator.

### Setup (one-time)

1. Install dependencies: `pip install pyqt6 pandas`
2. Launch the tool: `python labeler/main.py`
3. Open a video file: **File → Open** or drag-and-drop an MP4

### Hotkeys

| Key | Shot Type |
|---|---|
| `1` | Straight |
| `2` | Angle |
| `3` | Bank |
| `4` | Cut |
| `5` | Drift / Push |
| `6` | Combo / Other |
| `Space` | Play / Pause |
| `←` / `→` | Step back / forward 5 seconds |
| `J` / `L` | Slow down / speed up playback |

### Labeling rules

- **Label at the moment of contact** — when the mallet strikes the puck, not when it arrives
- **Pause first if needed** — it's better to pause and label accurately than to label on the fly and get the wrong frame
- **Use `6` liberally** — ambiguous shots labeled as `6` are more useful than ambiguous shots mislabeled as a specific type
- **One label per shot** — do not double-label a single strike
- **Export often** — hit "Export Labels" every 20–30 minutes. Labels are only in memory until exported

### Saving your work

Labels are exported per session to the `labeled/` folder as both `.json` and `.csv`. Submit the entire `labeled/` folder when done.

---

## Step 5 — Validate & Export Dataset

After collecting labels from all annotators, run the validation script to check class balance and flag anomalies.

```bash
python scripts/validate_labels.py --input labeled/ --output dataset_summary.csv
```

This script (to be added in `scripts/`) should:
- Merge all annotator CSVs
- Report label counts per class
- Flag shots with timestamps < 500ms apart (likely double-labels)
- Flag files that appear in only one annotator's output (missed coverage)

### Minimum targets before training

| Shot Type | Minimum clips |
|---|---|
| Straight | 200 |
| Angle | 200 |
| Bank | 200 |
| Cut | 200 |
| Drift / Push | 200 |
| Combo / Other | 100 |
| **Total** | **1,100+** |

---

## Output Format

Each exported label file follows this schema:

**JSON**
```json
[
  {
    "file": "clip_001.mp4",
    "timestamp_ms": 14320,
    "shot_type": "bank"
  },
  {
    "file": "clip_001.mp4",
    "timestamp_ms": 27810,
    "shot_type": "straight"
  }
]
```

**CSV**
```
file,timestamp_ms,shot_type
clip_001.mp4,14320,bank
clip_001.mp4,27810,straight
```

Timestamps mark the moment of mallet contact. During preprocessing for training, extract a ±N frame window around each timestamp to form the clip.

---

## Folder Structure

```
air-hockey-shot-labeling/
│
├── raw_footage/          # Downloaded MP4s (not committed to git)
├── segments/             # 5-minute clips split from raw footage
├── labeled/              # Exported label JSON/CSV files from annotators
├── dataset/              # Final processed clips ready for training (generated)
│
├── labeler/
│   ├── main.py           # PyQt6 labeling tool (repurposed DVR player)
│   └── requirements.txt
│
├── scripts/
│   ├── validate_labels.py
│   └── extract_clips.py  # Cuts labeled timestamps into clip files
│
├── urls.txt              # YouTube URLs to download
└── README.md
```

---

## Notes

- **Do not commit raw footage to git** — add `raw_footage/` and `segments/` to `.gitignore`
- **Coordinate annotators** — assign specific video files per person to avoid duplicate labeling
- **Camera setup reminder** — top-down mount, 1080p 60fps, fixed white balance, no auto-exposure
- **yt-dlp may need updating** — YouTube changes frequently. If downloads fail: `pip install -U yt-dlp`
