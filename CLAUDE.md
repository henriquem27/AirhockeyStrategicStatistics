# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Log (Obsidian Vault)

Daily notes and open tasks for this project live at `~/Vault/Canguru Player/`.

**At the start of every session:**
1. Read `index.md` for current status and open tasks.
2. Read the most recent `YYYY-MM-DD.md` for where things were left off.
3. Run `git log --oneline -5` and `git status` and briefly report the state.

**During the session — log proactively, without being asked:**
- After every meaningful action (fix, decision, finding, blocker), append a short bullet to today's `YYYY-MM-DD.md` under `## Log`. Create the file if it doesn't exist using the format in `~/Vault/claude.md`.
- After every branch switch, append it under `## Git` in today's daily log. (Commits are captured automatically by a hook — no need to log those manually.)
- After any task is completed or a new one is identified, update `## Open Tasks` in `index.md` immediately.
- Do not wait to be asked. Log as you go.

## What This App Is

Multi-camera H.264 player for DVR backup footage. Plays all cameras side by side in sync, with speed control, clip trimming, and mosaic export. Built for Canguru.

## Running Locally

```bash
# First time
bash setup.sh

# Every time after
python3 player_gui.py
```

Requires Homebrew, `ffmpeg`, `sdl2`, and the Python packages in `requirements.txt`. The optional C player is compiled by `setup.sh`.

## Stack

- **GUI:** Python (`player_gui.py`)
- **Core player:** C (`player.c`), compiled to `build/`
- **Video decoding:** FFmpeg
- **Display:** SDL2
- **Packaging:** PyInstaller (`CanguruPlayer.spec`)

## Build / Dist

```bash
make          # compile C player
pyinstaller CanguruPlayer.spec   # build distributable
```

License generation: `generate_license.py` / `private.pem`.
