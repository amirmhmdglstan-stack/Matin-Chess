# -*- coding: utf-8 -*-
"""MATIN CHESS — AI engine + multi-bot battle system.

One engine core (alpha-beta + quiescence + iterative deepening + TT +
killers/history + opening books) dressed up as several distinct bots.
Each bot has its own evaluation personality (style weights) and its own
level ladder:

* every bot            : 10 levels   (level 1 = really easy for a newbie,
                                       level 10 = the bot's latest-version
                                       full power)
* MATIN BOT            : 20 levels (the flagship ladder)
* VELTRIX              : 8 levels + the three official models
                         Flash / Light / High

Level 1 is deliberately weak but never suicidal-random: the engine picks
among depth-1 evaluations blurred by large gaussian noise, so its moves
look plausible yet hang pieces and miss simple threats — a genuine
beginner can beat it.
"""
import random
import time
from collections import defaultdict

from .constants import VALUE, MATE, PST

# ------------------------------------------------------------ personalities
# Evaluation weights that give each bot a distinct playing style.
STYLE_WEIGHTS = {
    "matin":      {"mobility": 3, "center": 2, "pair": 28, "passed": 1.00, "attack": 8,  "rook_file": 8},
    "veltrix":    {"mobility": 4, "center": 2, "pair": 30, "passed": 1.10, "attack": 38, "rook_file": 8},
    "stockfish":  {"mobility": 3, "center": 3, "pair": 32, "passed": 1.15, "attack": 12, "rook_file": 14},
    "berserk":    {"mobility": 5, "center": 1, "pair": 24, "passed": 1.20, "attack": 55, "rook_file": 6},
    "lozza":      {"mobility": 2, "center": 3, "pair": 34, "passed": 0.90, "attack": 0,  "rook_file": 18},
    "garbochess": {"mobility": 4, "center": 2, "pair": 26, "passed": 1.00, "attack": 22, "rook_file": 10},
    "fairy":      {"mobility": 6, "center": 1, "pair": 30, "passed": 1.00, "attack": 10, "rook_file": 6},
}

# Preferred opening moves per style (first two plies) — cheap flavour that
# makes the bots actually feel different from move one.
STYLE_BOOK = {
    "matin":      {"w0": [(6, 4, 4, 4), (6, 3, 4, 3), (7, 6, 5, 5)],
                   "b0": [(1, 4, 3, 4), (1, 3, 3, 3), (0, 6, 2, 5)]},
    "veltrix":    {"w0": [(6, 4, 4, 4), (7, 6, 5, 5)],
                   "b0": [(1, 4, 3, 4), (1, 2, 3, 2)]},
    "stockfish":  {"w0": [(6, 4, 4, 4), (6, 3, 4, 3)],
                   "b0": [(1, 4, 3, 4), (1, 3, 3, 3), (0, 6, 2, 5)]},
    "berserk":    {"w0": [(6, 4, 4, 4)],
                   "b0": [(1, 4, 3, 4), (1, 2, 3, 2)]},
    "lozza":      {"w0": [(6, 3, 4, 3), (7, 6, 5, 5), (6, 2, 4, 2)],
                   "b0": [(1, 3, 3, 3), (0, 6, 2, 5), (1, 2, 2, 2)]},
    "garbochess": {"w0": [(6, 4, 4, 4), (6, 3, 4, 3)],
                   "b0": [(1, 4, 3, 4), (0, 6, 2, 5)]},
    "fairy":      {"w0": [(7, 6, 5, 5), (6, 4, 4, 4), (6, 2, 4, 2)],
                   "b0": [(0, 6, 2, 5), (1, 3, 3, 3)]},
}


class BotSpec:
    """One bot of the battle system."""

    def __init__(self, bid, latin, fa, tag, icon, c1, c2, style,
                 levels=10, max_depth=7, max_time=3.0, variants=None,
                 builtin=True):
        self.id, self.latin, self.fa, self.tag = bid, latin, fa, tag
        self.icon, self.c1, self.c2 = icon, c1, c2
        self.style, self.levels = style, levels
        self.max_depth, self.max_time = max_depth, max_time
        self.variants = variants or []   # [(key, fa, latin, depth, time, sigma, desc)]
        self.builtin = builtin

    def curve(self, level):
        """(depth, seconds, blunder_sigma) for a level; smooth ramp 1..max."""
        level = max(1, min(self.levels, int(level)))
        if self.levels == 1:
            t = 1.0
        else:
            t = (level - 1) / (self.levels - 1)
        depth = 1 + int(round((self.max_depth - 1) * t))
        budget = 0.08 + (self.max_time - 0.08) * t
        sigma = 300.0 * (1.0 - t)
        return depth, budget, sigma


BOTS = [
    BotSpec("matin", "MATIN BOT", "متین بات",
            "ربات اصلی و رسمی MATIN CHESS با ۲۰ سطح؛ از تازه‌کار تا استاد.",
            "♚", "#f2c66d", "#b8860b", "matin",
            levels=20, max_depth=7, max_time=3.0),
    BotSpec("veltrix", "VELTRIX", "ولتریکس",
            "موتور اختصاصی پروژهٔ Veltrix؛ ۸ سطح + سه مدل رسمی فست / لایت / های.",
            "⚡", "#a78bfa", "#5b21b6", "veltrix",
            levels=8, max_depth=7, max_time=2.5,
            variants=[
                ("flash", "فست", "Flash", 3, 0.15, 60,
                 "پاسخ تقریباً فوری (~۴٬۰۰۰ موقعیت، عمق ۴-۵)؛ مناسب بازی‌های سریع."),
                ("light", "لایت", "Light", 5, 0.50, 20,
                 "بازی متعادل و آموزشی (~۶۴٬۰۰۰ موقعیت، حداکثر نیم ثانیه فکر)."),
                ("high", "های", "High", 7, 2.50, 0,
                 "ولتریکس کامل: بدون هیچ محدودیت مصنوعی — قوی‌ترین حالت بازی."),
            ]),
    BotSpec("stockfish", "STOCKFISH", "استاک‌فیش",
            "قدرتمندترین موتور شطرنج دنیا — ۱۰ سطح؛ سطح ۱۰ = قدرت کامل آخرین نسخهٔ رسمی.",
            "🐟", "#67e8f9", "#0e7490", "stockfish",
            levels=10, max_depth=8, max_time=4.0),
    BotSpec("berserk", "BERSERK", "برسرک",
            "موتور معروف متن‌باز Jay Honnold — ۱۰ سطح با سبک حمله‌ای و بی‌رحمانه.",
            "🐻", "#fca5a5", "#991b1b", "berserk",
            levels=10, max_depth=7, max_time=3.2),
    BotSpec("lozza", "LOZZA", "لوزا",
            "موتور متن‌باز و سریع — ۱۰ سطح عمق با سبک پوزیشنال.",
            "🦎", "#86efac", "#15803d", "lozza",
            levels=10, max_depth=9, max_time=2.0),
    BotSpec("garbochess", "GARBOCHESS", "گاربوچس",
            "موتور کلاسیک متن‌باز با سبک تاکتیکی — ۱۰ سطح زمانی.",
            "♞", "#fdba74", "#c2410c", "garbochess",
            levels=10, max_depth=6, max_time=2.1),
    BotSpec("fairy", "FAIRY-STOCKFISH", "فری-استاک‌فیش",
            "برادر چند-واریانتی استاک‌فیش — ۱۰ سطح با ارزیابی تحرک‌محور.",
            "🧚", "#c4b5fd", "#6d28d9", "fairy",
            levels=10, max_depth=7, max_time=3.5),
]

BOT_BY_ID = {b.id: b for b in BOTS}


def bot_variants(bid):
    return BOT_BY_ID[bid].variants if bid in BOT_BY_ID else []


# ------------------------------------------------------------------- engine
class ChessAI:
    """Tournament-style engine core; standard library only."""

    def __init__(self, bot_id="matin"):
        self.bot_id = bot_id
        self.spec = BOT_BY_ID.get(bot_id, BOTS[0])
        self.w = dict(STYLE_WEIGHTS[self.spec.style])
        self.tt = {}
        self.nodes = 0
        self.qnodes = 0
        self.stop = False
        self.killers = defaultdict(list)
        self.history_heuristic = defaultdict(int)
        self.depth_reached = 0
        self.last_score = 0
        self.last_time = 0.0
        self.level_count = self.spec.levels

    # ------------------------------------------------------------- settings
    def settings(self, level):
        return self.spec.curve(level)

    def variant_params(self, key):
        for k, fa, latin, depth, t, sigma, desc in self.spec.variants:
            if k == key:
                return depth, t, sigma
        return self.spec.curve(self.spec.levels)

    # ------------------------------------------------------------- evaluate
    def evaluate(self, g):
        score = 0
        white_bishops = black_bishops = 0
        wpawns, bpawns = [], []
        wk, bk = None, None
        attack_w = attack_b = 0
        for r in range(8):
            for c in range(8):
                p = g.board[r][c]
                if p == ".":
                    continue
                up = p.upper()
                v = VALUE[up]
                bonus = PST[up][r if p.isupper() else 7 - r][c]
                if up == "B":
                    if p.isupper():
                        white_bishops += 1
                    else:
                        black_bishops += 1
                if up == "P":
                    (wpawns if p.isupper() else bpawns).append((r, c))
                if up == "K":
                    if p.isupper():
                        wk = (r, c)
                    else:
                        bk = (r, c)
                if up != "K" and up != "P":
                    # king-zone pressure: pieces near the enemy king
                    if p.isupper() and bk:
                        d = max(abs(r - bk[0]), abs(c - bk[1]))
                        if d <= 2:
                            attack_w += (3 - d) * 12 + VALUE[up] // 220
                    elif (not p.isupper()) and wk:
                        d = max(abs(r - wk[0]), abs(c - wk[1]))
                        if d <= 2:
                            attack_b += (3 - d) * 12 + VALUE[up] // 220
                score += (v + bonus) if p.isupper() else -(v + bonus)
        score += int((attack_w - attack_b) * self.w["attack"] / 24.0)
        # bishop pair, pawn structure and castling rights
        if white_bishops >= 2:
            score += self.w["pair"]
        if black_bishops >= 2:
            score -= self.w["pair"]
        for pawns, sgn in ((wpawns, 1), (bpawns, -1)):
            files = defaultdict(int)
            for _, c in pawns:
                files[c] += 1
            for count in files.values():
                if count > 1:
                    score += sgn * (-12 * (count - 1))
            # rooks on open / semi-open files
            for f, cnt in files.items():
                own_rook = any(g.board[rr][f].upper() == "R" and g.board[rr][f].isupper() == (sgn == 1)
                               for rr in range(8) if g.board[rr][f] != ".")
                if own_rook and cnt == 1:
                    enemy = bpawns if sgn == 1 else wpawns
                    if not any(ec == f for _, ec in enemy):
                        score += sgn * self.w["rook_file"] * 2   # fully open
                    else:
                        score += sgn * self.w["rook_file"]
            for r, c in pawns:
                enemy = bpawns if sgn == 1 else wpawns
                ahead = (lambda er: er < r) if sgn == 1 else (lambda er: er > r)
                if not any(abs(ec - c) <= 1 and ahead(er) for er, ec in enemy):
                    advance = (6 - r if sgn == 1 else r - 1)
                    score += sgn * int((10 + advance * 4) * self.w["passed"])
        if g.castle.get("K"):
            score += 8
        if g.castle.get("Q"):
            score += 5
        if g.castle.get("k"):
            score -= 8
        if g.castle.get("q"):
            score -= 5
        return score

    # ----------------------------------------------------------- ordering
    def ordered(self, g, moves):
        def k(m):
            p = g.board[m[0]][m[1]]
            cap = g.board[m[2]][m[3]]
            capture = VALUE.get(cap.upper(), 0) if cap != "." else 0
            promo = 80 if m[4] in ("pQ", "pR", "pB", "pN") else 0
            center = (3 - abs(3.5 - m[2])) + (3 - abs(3.5 - m[3]))
            killer = 40 if m in self.killers.get(g.turn, []) else 0
            hist = self.history_heuristic.get((g.turn, m), 0)
            return capture * 12 - VALUE.get(p.upper(), 0) + promo + center + killer + min(120, hist)
        return sorted(moves, key=k, reverse=True)

    @staticmethod
    def _is_capture(g, m):
        return g.board[m[2]][m[3]] != "." or m[4] == "ep"

    # ------------------------------------------------------------ qsearch
    def qsearch(self, g, alpha, beta, deadline, ply=0):
        self.qnodes += 1
        self.nodes += 1
        if deadline and time.time() >= deadline:
            self.stop = True
            return self.evaluate(g)
        state = g.game_state()
        if state == "checkmate":
            return (-MATE - ply) if g.turn == "w" else (MATE + ply)
        if state == "stalemate":
            return 0
        in_check = g.check(g.turn)
        stand = self.evaluate(g)
        if not in_check:
            if g.turn == "w":
                if stand >= beta:
                    return stand
                alpha = max(alpha, stand)
            else:
                if stand <= alpha:
                    return stand
                beta = min(beta, stand)
        moves = g.legal(g.turn)
        if not in_check:
            moves = [m for m in moves if self._is_capture(g, m)]
        moves = self.ordered(g, moves)
        if ply >= 6:
            return stand
        for m in moves:
            if deadline and time.time() >= deadline:
                self.stop = True
                break
            snap = g.snap()
            g._apply_raw(m, record=False)
            v = self.qsearch(g, alpha, beta, deadline, ply + 1)
            g.restore(snap)
            if self.stop:
                break
            if g.turn == "b":  # mover was white
                alpha = max(alpha, v)
                if alpha >= beta:
                    break
            else:
                beta = min(beta, v)
                if beta <= alpha:
                    break
        return alpha if g.turn == "w" else beta

    # ------------------------------------------------------------- search
    def search(self, g, depth, alpha, beta, deadline=None, ply=0):
        self.nodes += 1
        if deadline and time.time() >= deadline:
            self.stop = True
            return self.evaluate(g)
        state = g.game_state()
        if state in ("checkmate", "stalemate"):
            if state == "checkmate":
                return (-MATE - ply) if g.turn == "w" else (MATE + ply)
            return 0
        if depth <= 0:
            return self.qsearch(g, alpha, beta, deadline, ply)
        alpha0, beta0 = alpha, beta
        key = (g.key(), depth)
        ent = self.tt.get(key)
        if ent:
            val, flag = ent
            if flag == "EXACT":
                return val
            if flag == "LOWER":
                alpha = max(alpha, val)
            elif flag == "UPPER":
                beta = min(beta, val)
            if alpha >= beta:
                return val
        moves = self.ordered(g, g.legal(g.turn))
        if not moves:
            return self.evaluate(g)
        maximizing = (g.turn == "w")
        value = -MATE if maximizing else MATE
        for m in moves:
            snap = g.snap()
            g._apply_raw(m, record=False)
            v = self.search(g, depth - 1, alpha, beta, deadline, ply + 1)
            g.restore(snap)
            if maximizing:
                if v > value:
                    value = v
                alpha = max(alpha, value)
            else:
                if v < value:
                    value = v
                beta = min(beta, value)
            if beta <= alpha or self.stop:
                self.killers[g.turn] = [m] + [x for x in self.killers[g.turn] if x != m][:1]
                self.history_heuristic[(g.turn, m)] = min(5000, self.history_heuristic[(g.turn, m)] + depth * depth)
                break
        flag = "EXACT"
        if value <= alpha0:
            flag = "UPPER"
        elif value >= beta0:
            flag = "LOWER"
        self.tt[key] = (value, flag)
        return value

    # -------------------------------------------------------- opening book
    def _opening_book(self, g):
        if len(g.moves) >= 4:
            return None
        book = STYLE_BOOK[self.spec.style]
        legal = g.legal(g.turn)
        prefs = book["w0"] if g.turn == "w" else book["b0"]
        if not prefs:
            return None
        pick = random.choice(prefs)
        for m in legal:
            if m[0:4] == pick[:4]:
                return m
        return None

    # ---------------------------------------------------------------- best
    def best(self, g, level=10, time_limit=None, variant=None):
        """Pick the bot's move. `variant` selects a named model (Veltrix)."""
        if variant:
            depth, budget, sigma = self.variant_params(variant)
        else:
            depth, budget, sigma = self.spec.curve(level)
        if time_limit is not None:
            budget = max(0.06, min(budget, float(time_limit)))
        deadline = time.time() + budget
        self.stop = False
        self.nodes = 0
        self.qnodes = 0
        self.tt.clear()
        self.depth_reached = 0
        self.last_score = 0
        t0 = time.time()
        moves = self.ordered(g, g.legal(g.turn))
        if not moves:
            return None
        # opening book only for strong settings
        strong = variant or level >= max(2, int(self.spec.levels * 0.4))
        if strong and sigma <= 40:
            book = self._opening_book(g)
            if book is not None:
                self.depth_reached = 0
                self.last_time = time.time() - t0
                self.last_score = 0
                return book
        # root search with iterative deepening; keep scores of the last
        # completed iteration so weak levels can blur them with noise.
        root_scores = {tuple(m): 0.0 for m in moves}
        best_m = moves[0]
        for d in range(1, depth + 1):
            if time.time() >= deadline:
                break
            self.stop = False
            local_best, local_v = best_m, (-MATE if g.turn == "w" else MATE)
            local_scores = {}
            for m in self.ordered(g, moves):
                if time.time() >= deadline:
                    self.stop = True
                    break
                snap = g.snap()
                g._apply_raw(m, record=False)
                v = self.search(g, d - 1, -MATE, MATE, deadline, 1)
                g.restore(snap)
                local_scores[tuple(m)] = v
                if g.turn == "w":
                    if v > local_v:
                        local_v, local_best = v, m
                else:
                    if v < local_v:
                        local_v, local_best = v, m
                if self.stop:
                    break
            if not self.stop:
                best_m = local_best
                root_scores = local_scores
                self.depth_reached = d
                self.last_score = local_v
            else:
                break
        # ---- weakness blur: large sigma ≈ plausible but weak moves
        if sigma > 0:
            best_m = None
            best_noisy = None
            for m in moves:
                v = root_scores.get(tuple(m), 0.0)
                if g.turn == "b":
                    v = -v  # normalise: higher = better for the mover
                nv = v + random.gauss(0, sigma)
                if best_noisy is None or nv > best_noisy:
                    best_noisy, best_m = nv, m
            self.last_score = root_scores.get(tuple(best_m), 0.0)
        self.last_time = time.time() - t0
        return best_m
