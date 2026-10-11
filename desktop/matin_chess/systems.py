# -*- coding: utf-8 -*-
"""MATIN CHESS — supporting systems (stats DB, save vault, PGN export,
replay, tournament ranks, analytics, device info)."""
import csv
import datetime
import hashlib
import json
import logging
import os
import platform
import sqlite3
import statistics
import subprocess
import sys
import zlib
from collections import Counter, deque

from .constants import VALUE, UNICODE


class AppLogger:
    def __init__(self):
        try:
            self.log = logging.getLogger("matin_chess")
            self.log.setLevel(logging.INFO)
            if not self.log.handlers:
                h = logging.StreamHandler()
                h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
                self.log.addHandler(h)
        except Exception:
            self.log = None

    def info(self, msg):
        try:
            if self.log:
                self.log.info(msg)
        except Exception:
            pass

    def error(self, msg):
        try:
            if self.log:
                self.log.error(msg)
        except Exception:
            pass


class StatsDB:
    def __init__(self):
        self.path = os.path.join(os.path.expanduser("~"), ".matin_chess_stats.db")
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "level INT,side TEXT,result TEXT,moves INT,captures INT,"
                        "duration REAL,state_hash TEXT,created TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "game_id INT,kind TEXT,value TEXT,created TEXT)")
        self.db.commit()

    def add_game(self, level, side, result, moves, captures, duration, state_hash):
        cur = self.db.execute("INSERT INTO games(level,side,result,moves,captures,duration,state_hash,created)"
                              " VALUES(?,?,?,?,?,?,?,?)",
                              (level, side, result, moves, captures, duration, state_hash,
                               datetime.datetime.now().isoformat()))
        self.db.commit()
        return cur.lastrowid

    def add_event(self, game_id, kind, value):
        self.db.execute("INSERT INTO events(game_id,kind,value,created) VALUES(?,?,?,?)",
                        (game_id, kind, str(value), datetime.datetime.now().isoformat()))
        self.db.commit()

    def summary(self):
        try:
            row = self.db.execute("SELECT COUNT(*),SUM(result='win'),SUM(result='loss'),SUM(result='draw')"
                                  " FROM games").fetchone()
            return {"games": row[0] or 0, "wins": row[1] or 0, "losses": row[2] or 0, "draws": row[3] or 0}
        except Exception:
            return {"games": 0, "wins": 0, "losses": 0, "draws": 0}

    def close(self):
        try:
            self.db.close()
        except Exception:
            pass


class SaveVault:
    @staticmethod
    def encode(payload):
        return zlib.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), 9)

    @staticmethod
    def decode(text):
        return json.loads(zlib.decompress(text).decode("utf-8"))

    @staticmethod
    def write(path, payload):
        with open(path, "wb") as f:
            f.write(SaveVault.encode(payload))

    @staticmethod
    def read(path):
        with open(path, "rb") as f:
            return SaveVault.decode(f.read())


class PGNExporter:
    @staticmethod
    def export(game, path, metadata=None):
        md = metadata or {}
        lines = []
        for k, v in md.items():
            lines.append(f'[{k} "{v}"]')
        if lines:
            lines.append("")
        body, row = [], []
        for i, mv in enumerate(game.moves):
            if i % 2 == 0:
                row.append(f"{i//2 + 1}.")
            row.append(mv)
            if len(row) >= 7:
                body.append(" ".join(row))
                row = []
        if row:
            body.append(" ".join(row))
        lines.append(" ".join(body) if body else "*")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


class ColorTools:
    @staticmethod
    def hex_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def rgb_hex(rgb):
        return "#%02x%02x%02x" % tuple(max(0, min(255, int(x))) for x in rgb)

    @staticmethod
    def mix(a, b, t=.5):
        try:
            ra, rb = ColorTools.hex_rgb(a), ColorTools.hex_rgb(b)
            return ColorTools.rgb_hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))
        except Exception:
            return a

    @staticmethod
    def shade(h, amount):
        try:
            r, g, b = ColorTools.hex_rgb(h)
            return ColorTools.rgb_hex((r + amount, g + amount, b + amount))
        except Exception:
            return h


class ReplayEngine:
    def __init__(self, moves=None):
        self.moves = list(moves or [])
        self.index = len(self.moves)

    def first(self):
        self.index = 0
        return self.current()

    def previous(self):
        self.index = max(0, self.index - 1)
        return self.current()

    def next(self):
        self.index = min(len(self.moves), self.index + 1)
        return self.current()

    def last(self):
        self.index = len(self.moves)
        return self.current()

    def current(self):
        return self.moves[self.index - 1] if 0 < self.index <= len(self.moves) else None


class TournamentEngine:
    RANKS = ["تازه‌کار", "سرباز", "شوالیه", "استاد", "قهرمان کهکشان"]

    def __init__(self):
        self.points = 0
        self.streak = 0
        self.trophies = []

    def record_win(self):
        self.points += 3
        self.streak += 1
        if self.streak in (2, 4, 7):
            self.trophies.append(self.streak)

    def record_loss(self):
        self.streak = 0

    def rank(self):
        # BUGFIX (original): the index expression was malformed and always
        # returned False; now it actually indexes the rank table.
        try:
            idx = min(len(self.RANKS) - 1, self.points // 6)
            return self.RANKS[idx]
        except Exception:
            return self.RANKS[0]


class PerformanceMeter:
    def __init__(self):
        self.samples = deque(maxlen=100)

    def add(self, seconds):
        self.samples.append(float(seconds))

    def average(self):
        return statistics.mean(self.samples) if self.samples else 0


class ChessAnalytics:
    @staticmethod
    def material(game):
        w = b = 0
        for r in range(8):
            for c in range(8):
                p = game.board[r][c]
                if p != "." and p.upper() != "K":
                    v = VALUE[p.upper()]
                    if p.isupper():
                        w += v
                    else:
                        b += v
        return {"white": w, "black": b, "difference": w - b}

    @staticmethod
    def mobility(game):
        return {"white": len(game.legal("w")), "black": len(game.legal("b"))}

    @staticmethod
    def position_hash(game):
        return hashlib.sha256(game.key().encode()).hexdigest()[:16]


class DeviceInfo:
    @staticmethod
    def text():
        try:
            return f"{platform.system()} {platform.release()} • Python {sys.version.split()[0]} • {os.cpu_count()} CPU"
        except Exception:
            return "Unknown device"


def captured_glyphs(captured):
    return " ".join(UNICODE[p] for p in captured)
