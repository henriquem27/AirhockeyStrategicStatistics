#!/bin/bash
set -e

echo "================================================"
echo "  Security Camera Player — Setup"
echo "================================================"

# ── 1. Homebrew ──────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "[1/4] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "[1/4] Homebrew already installed. ✓"
fi

# ── 2. System dependencies ───────────────────────────
echo "[2/4] Installing ffmpeg and sdl2..."
brew install ffmpeg sdl2

# ── 3. Python dependencies ───────────────────────────
echo "[3/4] Installing Python packages..."
pip3 install PyQt6 opencv-python

# ── 4. Compile C player (optional, lightweight) ──────
echo "[4/4] Compiling C player..."
if pkg-config --exists libavcodec libavformat libavutil libswscale sdl2 2>/dev/null; then
    gcc player.c -o player \
        $(pkg-config --cflags --libs libavcodec libavformat libavutil libswscale sdl2)
    echo "      C player compiled: ./player ✓"
else
    echo "      Skipping C player (pkg-config not found — ffmpeg may need a shell restart)"
fi

echo ""
echo "================================================"
echo "  Setup complete!"
echo "  Run:  python3 player_gui.py"
echo "================================================"
