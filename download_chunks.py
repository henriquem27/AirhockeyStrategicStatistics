#!/usr/bin/env python3
"""Download YouTube videos in 15-minute chunks using yt-dlp + ffmpeg."""

import subprocess
import os

URLS = [
    "https://www.youtube.com/watch?v=rHeYzSRLIQs",
    "https://www.youtube.com/watch?v=FPc3fbdLikk",
    "https://www.youtube.com/watch?v=kFv7ra5wEGE",
    "https://www.youtube.com/watch?v=ipLPsjxYVz8",
    "https://www.youtube.com/watch?v=KvG2Z85qgz0",
    "https://www.youtube.com/watch?v=BheI3rd35Wk",
    "https://www.youtube.com/watch?v=KbNFONjFjDQ",
    "https://www.youtube.com/watch?v=nJushDztsAg",
    "https://www.youtube.com/watch?v=9C_c1i0Im-w",
]

CHUNK_SECONDS = 15 * 60
OUTPUT_DIR = "./downloads"


def fmt(seconds):
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def get_info(url):
    r = subprocess.run(
        ["yt-dlp", "--print", "%(id)s\t%(duration)s\t%(title)s", "--no-playlist", url],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not r.stdout.strip():
        print(f"  Error: {r.stderr.strip()}")
        return None
    parts = r.stdout.strip().split("\t", 2)
    return parts[0], int(float(parts[1])), parts[2] if len(parts) > 2 else parts[0]


def download_chunk(url, start, end, out_template, n):
    print(f"  chunk {n:02d}: {fmt(start)} → {fmt(end)}")
    subprocess.run([
        "yt-dlp",
        "--download-sections", f"*{fmt(start)}-{fmt(end)}",
        "--output", out_template,
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        url,
    ])


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for url in URLS:
        print(f"\n{url}")
        info = get_info(url)
        if not info:
            print("  skipped")
            continue

        vid, duration, title = info
        print(f"  {title}  ({fmt(duration)})")

        start, n = 0, 1
        while start < duration:
            end = min(start + CHUNK_SECONDS, duration)
            out = os.path.join(OUTPUT_DIR, f"{vid}_chunk{n:02d}.%(ext)s")
            download_chunk(url, start, end, out, n)
            start, n = end, n + 1

        print(f"  done — {n - 1} chunk(s)")


if __name__ == "__main__":
    main()
