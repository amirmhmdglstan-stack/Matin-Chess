# -*- coding: utf-8 -*-
"""MATIN CHESS — shared constants.

Board visual design (squares, highlights, piece rendering, coordinates) is
taken verbatim from the Veltrix-Chess-bot project (gui/board_widget.py,
gui/theme.py) as requested; everything else keeps the original MATIN CHESS
desktop look and feel.
"""

APP_NAME = "MATIN CHESS"
APP_VERSION = "2.0.0"
APP_REPO = "amirmhmdglstan-stack/Matin-Chess"
CREATORS_FA = "متین کتویی زاده • امیرمحمد گلستان"
CREATORS_EN = "Matin Katooei-zadeh & AmirMohammad Golestan"

FILES = "abcdefgh"

UNICODE = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}
# Veltrix board design: BOTH colours use the *filled* glyph shapes; the body
# fill + offset outline stamps give the colour.
FILLED = {k: UNICODE[k.lower()] for k in UNICODE}

VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}
MATE = 999999

# ------------------------------------------------------------------ UI themes
THEMES = {
    "Galaxy":       ("#090b18", "#141a32", "#f2f5ff", "#8ea2ff", "#1b2240"),
    "Emerald":      ("#07120f", "#0d211a", "#ecfff6", "#65d6a0", "#163a2b"),
    "Royal":        ("#110b16", "#21122b", "#fff4ff", "#d7a6e6", "#3c2050"),
    "Ocean":        ("#07131a", "#0d2733", "#effbff", "#6bd5ee", "#174759"),
    "Crimson":      ("#16080b", "#321017", "#fff1f2", "#ff7180", "#541923"),
    "Sapphire":     ("#071020", "#102447", "#eef5ff", "#64a9ff", "#1b3970"),
    "Obsidian Gold": ("#0b0a08", "#211b10", "#fff7df", "#d7ad52", "#463817"),
    "Cyber":        ("#050b0d", "#092125", "#eaffff", "#35e5d0", "#12474a"),
    "Ice":          ("#0a1118", "#183040", "#f5fcff", "#9be7ff", "#29526a"),
    "Sunset":       ("#170c0a", "#30201b", "#fff8ef", "#ffb36b", "#583827"),
}

# ------------------------------------------------- board themes (VELTRIX design)
# Copied from Veltrix-Chess-bot gui/theme.py — the board is rendered exactly
# like the Veltrix GUI: flat squares, blended highlights, two-tone pieces,
# contrasting coordinate labels.
BOARD_STYLES = {
    "Classic":   ("#f0d9b5", "#b58863"),
    "Blue Grey": ("#dee3e6", "#8ca2ad"),
    "Forest":    ("#ffffdd", "#86a666"),
    "Sand":      ("#ffe8c8", "#d7a05b"),
    "Slate":     ("#c8cdd2", "#6f7d8c"),
    "Rosewood":  ("#f6e3d4", "#a86950"),
    "Mono":      ("#e8e8e8", "#7d7d7d"),
    "Night":     ("#999999", "#334455"),
}
DEFAULT_BOARD_STYLE = "Classic"

# Veltrix highlight colours (blended 45% with the base square colour)
HL_LAST_LIGHT, HL_LAST_DARK = "#c9e37f", "#acc64f"
HL_CHECK = "#ff6961"
HL_SELECTED = "#7fb6e3"
HL_TARGET_EMPTY = "#3a6f3a"     # stippled dot on empty squares
HL_TARGET_CAPTURE = "#d9534f"   # ring around capturable pieces

# Piece body/line colours per style. "Classic" is byte-for-byte the Veltrix
# two-tone scheme; the other styles only retint the body while the rendering
# method (solid filled glyph + 8 offset outline stamps) stays pure Veltrix.
PIECE_COLORS = {
    "Classic": ("#fdfdfd", "#1e1e1e"),
    "Ivory":   ("#fff4d6", "#2b1d0d"),
    "Silver":  ("#f2f5f8", "#17202a"),
    "Gold":    ("#ffe49a", "#241708"),
}
PIECE_LINE_LIGHT, PIECE_LINE_DARK = "#202020", "#f0f0f0"

LANGS = {
    "فارسی": {"start": "شروع بازی", "settings": "تنظیمات", "themes": "تم‌ها",
               "save": "ذخیره / بارگذاری", "stats": "آمار بازی", "help": "راهنما",
               "about": "درباره", "exit": "خروج", "choose": "انتخاب مرحله",
               "back": "بازگشت", "hint": "Hint", "undo": "Undo", "menu": "منو",
               "creator": CREATORS_FA,
               "victory": "🏆 پیروزی! جام قهرمانی برای شماست!"},
}

PIECE_SOUNDS = {
    "select": (880, 45), "check": (1040, 120), "castle": (760, 80),
    "promote": (1200, 140), "error": (180, 100), "win": (523, 90),
    "button": (840, 35), "start": (392, 55), "finish": (1047, 180),
    "timeout": (240, 180), "hint": (980, 55), "undo": (300, 75),
}

# piece-square tables (unchanged from the original engine)
PST = {
    "P": [[0, 0, 0, 0, 0, 0, 0, 0], [5, 8, 8, -2, -2, 8, 8, 5],
          [2, 3, 4, 6, 6, 4, 3, 2], [1, 2, 3, 12, 12, 3, 2, 1],
          [0, 0, 0, 10, 10, 0, 0, 0], [1, -2, -3, 0, 0, -3, -2, 1],
          [2, 3, 3, -8, -8, 3, 3, 2], [0, 0, 0, 0, 0, 0, 0, 0]],
    "N": [[-5, -4, -3, -3, -3, -3, -4, -5], [-4, -2, 0, 0, 0, 0, -2, -4],
          [-3, 0, 3, 5, 5, 3, 0, -3], [-3, 1, 5, 6, 6, 5, 1, -3],
          [-3, 0, 5, 6, 6, 5, 0, -3], [-3, 1, 3, 5, 5, 3, 1, -3],
          [-4, -2, 0, 1, 1, 0, -2, -4], [-5, -4, -3, -3, -3, -3, -4, -5]],
    "B": [[-3, -2, -2, -2, -2, -2, -2, -3], [-2, 2, 0, 0, 0, 0, 2, -2],
          [-2, 0, 3, 4, 4, 3, 0, -2], [-2, 1, 4, 5, 5, 4, 1, -2],
          [-2, 0, 4, 5, 5, 4, 0, -2], [-2, 1, 3, 4, 4, 3, 1, -2],
          [-2, 2, 0, 0, 0, 0, 2, -2], [-3, -2, -2, -2, -2, -2, -2, -3]],
    "R": [[0, 0, 0, 3, 3, 0, 0, 0], [0, 0, 0, 2, 2, 0, 0, 0],
          [0, 0, 0, 2, 2, 0, 0, 0], [3, 3, 3, 5, 5, 3, 3, 3],
          [2, 2, 2, 4, 4, 2, 2, 2], [0, 0, 0, 2, 2, 0, 0, 0],
          [0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 1, 1, 0, 0, 0]],
    "Q": [[-4, -2, -2, -1, -1, -2, -2, -4], [-2, 0, 1, 0, 0, 0, 0, -2],
          [-2, 1, 1, 1, 1, 1, 1, -2], [-1, 0, 1, 1, 1, 1, 0, -1],
          [-1, 0, 1, 1, 1, 1, 0, -1], [-2, 0, 1, 1, 1, 1, 0, -2],
          [-2, 0, 0, 0, 0, 0, 0, -2], [-4, -2, -2, -1, -1, -2, -2, -4]],
    "K": [[6, 8, 8, -10, -10, 8, 8, 6], [6, 8, 8, -10, -10, 8, 8, 6],
          [6, 8, 8, -10, -10, 8, 8, 6], [6, 8, 8, -10, -10, 8, 8, 6],
          [4, 6, 6, -8, -8, 6, 6, 4], [2, 4, 4, -6, -6, 4, 4, 2],
          [2, 2, 2, -4, -4, 2, 2, 2], [2, 2, -2, 0, 0, -2, 2, 2]],
}

# Endgame king table: in simple endings the king must RUN TO THE CENTER and
# help push pawns / hunt the enemy king — otherwise mates take forever.
KING_END = [[-30, -20, -10, -10, -10, -10, -20, -30],
            [-20, -10, 0, 0, 0, 0, -10, -20],
            [-10, 0, 12, 16, 16, 12, 0, -10],
            [-10, 0, 16, 24, 24, 16, 0, -10],
            [-10, 0, 16, 24, 24, 16, 0, -10],
            [-10, 0, 12, 16, 16, 12, 0, -10],
            [-20, -10, 0, 0, 0, 0, -10, -20],
            [-30, -20, -10, -10, -10, -10, -20, -30]]


def fa_num(n):
    """Persian digits for the UI, like the Android edition."""
    try:
        s = str(n)
        return s.translate(str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫"))
    except Exception:
        return str(n)
