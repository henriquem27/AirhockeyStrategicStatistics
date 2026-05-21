Air Hockey Shot Labeler — Instructions
========================================

Thank you for helping label air hockey footage!
Your labels will be used to build a dataset for strategic analysis.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 1 — Download footage
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Footage is available on Google Drive:
  https://drive.google.com/drive/u/0/folders/15tfC14FXiRyIMUdfQIcIH4rkRFuVvWiO

Download one or more .mp4 files to your computer.
Prefer videos that haven't been labeled yet (no matching .csv in the labels folder).


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 2 — Launch the app
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • macOS:  Double-click AHLabeler.app
  • Windows: Double-click AHLabeler.exe inside the AHLabeler folder

On first launch, you will be asked to enter your name.
This is stored locally and attached to every label you create.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 3 — Load a video
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Click "Open Video File" and select the downloaded .mp4.
2. A crop dialog will open automatically — drag to select the table area.
   If the full frame already shows only the table, click "OK" without cropping.
3. The video will start playing.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 4 — Label shots
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Playback controls:
  Space / P   — Play / Pause
  ← / →       — Seek ±5 seconds
  J / L       — Slow down / Speed up
  K           — Stop

When you see a shot being taken, pause or slow down the video.
Press the hotkey (or click the button) for the shot type at the moment of impact:

  1  —  Cut Straight
  2  —  Cross Straight
  3  —  Right-wall under (RWU) bank
  4  —  Left-wall under (LWU) bank
  5  —  Right-wall over (RWO) bank
  6  —  Left-wall over (LWO) bank
  7  —  Forehands

After pressing a shot key, the status bar will prompt:
  "Scored?  Y = yes   N = no"
Press Y if the shot resulted in a goal, or N if it did not.
(If you skip Y/N, the label is saved with scored = unknown.)

Tips:
  • Double-click any label in the list to jump back to that moment.
  • "Delete Last" removes the most recent label if you made a mistake.
  • Label the attacking player's shot (the puck leaving their mallet).


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STEP 5 — Export and upload your labels
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. When done with a video, click "Export Labels".
2. Two files will be saved in a "labeled/" folder next to the app:
     labels_YYYYMMDD_HHMMSS.csv
     labels_YYYYMMDD_HHMMSS.json
3. Upload those files to the same Google Drive folder:
     https://drive.google.com/drive/u/0/folders/15tfC14FXiRyIMUdfQIcIH4rkRFuVvWiO


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Questions?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Contact the project owner via GitHub:
  https://github.com/henriquem27/AirhockeyStrategicStatistics

Thank you for contributing!
