"""
theme.py — El Hombre Taco color palette and font constants.
Flat, modern aesthetic: clean whites, soft grays, accent orange.
"""

C = {
    # Backgrounds
    "bg":         "#F7F8FA",   # page background — near-white
    "panel":      "#FFFFFF",   # card / panel white
    "card":       "#FFFFFF",
    "card2":      "#F0F4FF",   # accent card (conversion rate, etc.)
    "sidebar":    "#1E1E2E",   # dark sidebar / header

    # Borders & dividers
    "border":     "#E2E6ED",
    "border_dk":  "#CBD2DC",

    # Brand accent
    "accent":     "#E8521A",   # El Hombre orange
    "accent_lt":  "#FF7043",
    "accent_dk":  "#BF3B0E",

    # Text
    "text":       "#1A1D23",   # primary text
    "muted":      "#6B7280",   # secondary / label text
    "dim":        "#9CA3AF",   # placeholder / hint

    # Semantic
    "success":    "#16A34A",
    "warn":       "#D97706",
    "error":      "#DC2626",
    "info":       "#2563EB",

    # Specific UI
    "input_bg":   "#FFFFFF",
    "input_border":"#D1D5DB",
    "btn_txt":    "#FFFFFF",
    "gold":       "#D97706",
    "gold_lt":    "#F59E0B",

    # Legacy aliases kept so old references don't break
    "cream":      "#1A1D23",
    "log_bg":     "#F7F8FA",
    "bubble_in":  "#F3F4F6",
    "bubble_ai":  "#EFF6FF",
    "bubble_me":  "#FFF7ED",
}

FONT_FAMILY = "Inter" if True else "Helvetica"   # Falls back gracefully
FONT = {
    "h1":    ("Helvetica", 22, "bold"),
    "h2":    ("Helvetica", 16, "bold"),
    "h3":    ("Helvetica", 13, "bold"),
    "body":  ("Helvetica", 10),
    "small": ("Helvetica",  9),
    "tiny":  ("Helvetica",  8),
    "label": ("Helvetica",  8, "bold"),
    "mono":  ("Courier",   10),
}
