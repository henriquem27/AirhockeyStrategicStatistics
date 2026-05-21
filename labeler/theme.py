PALETTES = {
    "dark": {
        "BG":       "#0d0d0d",
        "SURFACE":  "#141414",
        "SURFACE2": "#1a1a1a",
        "BORDER":   "#272727",
        "ACCENT":   "#3b82f6",
        "ACCENT_H": "#2563eb",
        "MUTED":    "#6b7280",
        "TEXT":     "#f1f5f9",
        "TEXT2":    "#94a3b8",
        "DANGER":   "#dc2626",
        "DANGER_H": "#b91c1c",
    },
    "light": {
        "BG":       "#f1f5f9",
        "SURFACE":  "#ffffff",
        "SURFACE2": "#f8fafc",
        "BORDER":   "#e2e8f0",
        "ACCENT":   "#3b82f6",
        "ACCENT_H": "#2563eb",
        "MUTED":    "#64748b",
        "TEXT":     "#0f172a",
        "TEXT2":    "#475569",
        "DANGER":   "#dc2626",
        "DANGER_H": "#b91c1c",
    },
}

# Active palette — updated at startup and on theme switch
P: dict = dict(PALETTES["dark"])


def apply(mode: str) -> None:
    P.clear()
    P.update(PALETTES.get(mode, PALETTES["dark"]))
