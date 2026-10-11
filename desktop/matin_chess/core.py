# -*- coding: utf-8 -*-
"""MATIN CHESS — chess rules core.

Full rules: castling, en passant, promotion (with real piece choice),
50-move rule, threefold repetition, stalemate/checkmate detection.
"""
import hashlib

from .constants import FILES

# move = (r, c, rr, cc, flag)
#   flag: None | "ep" | "castleK" | "castleQ" | "pQ" | "pR" | "pB" | "pN"
# A promotion move carries the chosen piece in its flag; a pawn move to the
# last rank WITHOUT a promo flag still auto-promotes to a queen, so old
# save files and simple engine calls keep working.
PROMO_FLAGS = ("pQ", "pR", "pB", "pN")


class ChessGame:
    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [list("rnbqkbnr"),
                      list("pppppppp"),
                      ["."] * 8, ["."] * 8, ["."] * 8, ["."] * 8,
                      list("PPPPPPPP"),
                      list("RNBQKBNR")]
        self.turn = "w"
        self.castle = {"K": True, "Q": True, "k": True, "q": True}
        self.ep = None
        self.history = []
        self.moves = []
        self.captured = []
        self.last = None
        self.halfmove = 0
        self.fullmove = 1

    def snap(self):
        return {"board": [list(r) for r in self.board], "turn": self.turn,
                "castle": dict(self.castle), "ep": self.ep,
                "moves": list(self.moves), "captured": list(self.captured),
                "last": self.last, "halfmove": self.halfmove,
                "fullmove": self.fullmove}

    def restore(self, s):
        self.board = [list(r) for r in s["board"]]
        self.turn = s["turn"]
        self.castle = dict(s["castle"])
        self.ep = s["ep"]
        self.moves = list(s.get("moves", []))
        self.captured = list(s.get("captured", []))
        self.last = s.get("last")
        self.halfmove = s.get("halfmove", 0)
        self.fullmove = s.get("fullmove", 1)
        self.history = s.get("history", self.history)

    def color(self, p):
        return "w" if p.isupper() else "b"

    @staticmethod
    def inside(r, c):
        return 0 <= r < 8 and 0 <= c < 8

    def find_king(self, side):
        k = "K" if side == "w" else "k"
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == k:
                    return r, c
        return None

    def attacked(self, r, c, by):
        """Is square (r,c) attacked by side `by`?"""
        # pawns
        d = 1 if by == "w" else -1
        for dc in (-1, 1):
            rr, cc = r + d, c + dc
            if self.inside(rr, cc) and self.board[rr][cc] == ("P" if by == "w" else "p"):
                return True
        # knights
        for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
            rr, cc = r + dr, c + dc
            if self.inside(rr, cc) and self.board[rr][cc] == ("N" if by == "w" else "n"):
                return True
        # king
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    rr, cc = r + dr, c + dc
                    if self.inside(rr, cc) and self.board[rr][cc] == ("K" if by == "w" else "k"):
                        return True
        # sliders
        for dirs, kind in ((((1, 1), (1, -1), (-1, 1), (-1, -1)), "bq"),
                           (((1, 0), (-1, 0), (0, 1), (0, -1)), "rq")):
            want = kind if by == "b" else kind.upper()
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                while self.inside(rr, cc):
                    q = self.board[rr][cc]
                    if q != ".":
                        if q in want:
                            return True
                        break
                    rr += dr
                    cc += dc
        return False

    def check(self, side):
        k = self.find_king(side)
        return self.attacked(k[0], k[1], "b" if side == "w" else "w") if k else False

    def pseudo(self, side):
        out = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p == "." or self.color(p) != side:
                    continue
                P = p.upper()
                if P == "P":
                    d = -1 if side == "w" else 1
                    start = 6 if side == "w" else 1
                    last = 0 if side == "w" else 7
                    if self.inside(r + d, c) and self.board[r + d][c] == ".":
                        if r + d == last:
                            for f in PROMO_FLAGS:
                                out.append((r, c, r + d, c, f))
                        else:
                            out.append((r, c, r + d, c, None))
                            if r == start and self.board[r + 2 * d][c] == ".":
                                out.append((r, c, r + 2 * d, c, None))
                    for dc in (-1, 1):
                        rr, cc = r + d, c + dc
                        if self.inside(rr, cc):
                            q = self.board[rr][cc]
                            if q != "." and self.color(q) != side:
                                if rr == last:
                                    for f in PROMO_FLAGS:
                                        out.append((r, c, rr, cc, f))
                                else:
                                    out.append((r, c, rr, cc, None))
                            if self.ep == (rr, cc):
                                out.append((r, c, rr, cc, "ep"))
                elif P == "N":
                    for dr, dc in ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)):
                        rr, cc = r + dr, c + dc
                        if self.inside(rr, cc) and (self.board[rr][cc] == "." or self.color(self.board[rr][cc]) != side):
                            out.append((r, c, rr, cc, None))
                elif P in ("B", "R", "Q"):
                    dirs = []
                    if P in ("B", "Q"):
                        dirs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
                    if P in ("R", "Q"):
                        dirs += [(1, 0), (-1, 0), (0, 1), (0, -1)]
                    for dr, dc in dirs:
                        rr, cc = r + dr, c + dc
                        while self.inside(rr, cc):
                            if self.board[rr][cc] == ".":
                                out.append((r, c, rr, cc, None))
                            else:
                                if self.color(self.board[rr][cc]) != side:
                                    out.append((r, c, rr, cc, None))
                                break
                            rr += dr
                            cc += dc
                else:
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            if dr or dc:
                                rr, cc = r + dr, c + dc
                                if self.inside(rr, cc) and (self.board[rr][cc] == "." or self.color(self.board[rr][cc]) != side):
                                    out.append((r, c, rr, cc, None))
                    # castling
                    if side == "w" and r == 7 and c == 4 and not self.check("w"):
                        if self.castle["K"] and self.board[7][7] == "R" and self.board[7][5] == "." and self.board[7][6] == "." and not self.attacked(7, 5, "b") and not self.attacked(7, 6, "b"):
                            out.append((7, 4, 7, 6, "castleK"))
                        if self.castle["Q"] and self.board[7][0] == "R" and self.board[7][3] == "." and self.board[7][2] == "." and self.board[7][1] == "." and not self.attacked(7, 3, "b") and not self.attacked(7, 2, "b"):
                            out.append((7, 4, 7, 2, "castleQ"))
                    if side == "b" and r == 0 and c == 4 and not self.check("b"):
                        if self.castle["k"] and self.board[0][7] == "r" and self.board[0][5] == "." and self.board[0][6] == "." and not self.attacked(0, 5, "w") and not self.attacked(0, 6, "w"):
                            out.append((0, 4, 0, 6, "castleK"))
                        if self.castle["q"] and self.board[0][0] == "r" and self.board[0][3] == "." and self.board[0][2] == "." and self.board[0][1] == "." and not self.attacked(0, 3, "w") and not self.attacked(0, 2, "w"):
                            out.append((0, 4, 0, 2, "castleQ"))
        return out

    def legal(self, side=None):
        side = side or self.turn
        out = []
        enemy = "k" if side == "w" else "K"
        for m in self.pseudo(side):
            # A king is never captured in chess; checkmate ends the game.
            target = self.board[m[2]][m[3]]
            if target == enemy:
                continue
            s = self.snap()
            self._apply_raw(m, record=False)
            if not self.check(side):
                out.append(m)
            self.restore(s)
        return out

    def _apply_raw(self, m, record=True):
        r, c, rr, cc, flag = m
        p = self.board[r][c]
        captured = self.board[rr][cc]
        if flag == "ep":
            cr = rr + 1 if p == "P" else rr - 1
            captured = self.board[cr][cc]
            self.board[cr][cc] = "."
        self.board[rr][cc] = p
        self.board[r][c] = "."
        if flag == "castleK":
            row = 7 if p == "K" else 0
            self.board[row][5] = self.board[row][7]
            self.board[row][7] = "."
        elif flag == "castleQ":
            row = 7 if p == "K" else 0
            self.board[row][3] = self.board[row][0]
            self.board[row][0] = "."
        # promotion (explicit choice, or auto-queen for legacy flag=None)
        if flag in PROMO_FLAGS:
            self.board[rr][cc] = flag[1] if p.isupper() else flag[1].lower()
        elif p == "P" and rr == 0:
            self.board[rr][cc] = "Q"
        elif p == "p" and rr == 7:
            self.board[rr][cc] = "q"
        # castling rights
        if p.upper() == "K":
            if p == "K":
                self.castle["K"] = self.castle["Q"] = False
            else:
                self.castle["k"] = self.castle["q"] = False
        if p == "R":
            if (r, c) == (7, 0):
                self.castle["Q"] = False
            if (r, c) == (7, 7):
                self.castle["K"] = False
        if p == "r":
            if (r, c) == (0, 0):
                self.castle["q"] = False
            if (r, c) == (0, 7):
                self.castle["k"] = False
        if captured == "R":
            if (rr, cc) == (7, 0):
                self.castle["Q"] = False
            if (rr, cc) == (7, 7):
                self.castle["K"] = False
        if captured == "r":
            if (rr, cc) == (0, 0):
                self.castle["q"] = False
            if (rr, cc) == (0, 7):
                self.castle["k"] = False
        self.ep = None
        if p.upper() == "P" and abs(rr - r) == 2:
            self.ep = ((r + rr) // 2, c)
        self.turn = "b" if self.turn == "w" else "w"
        if captured != ".":
            self.captured.append(captured)
        self.last = m
        if record:
            self.moves.append(self.move_text(m, p, captured))
            self.halfmove = 0 if (p.upper() == "P" or captured != ".") else self.halfmove + 1
            if self.turn == "w":
                self.fullmove += 1

    def apply(self, m):
        self.history.append(self.snap())
        self._apply_raw(m, record=True)

    def undo(self):
        if self.history:
            self.restore(self.history.pop())

    def move_text(self, m, p, captured):
        r, c, rr, cc, flag = m
        s = f"{FILES[c]}{8-r}-{FILES[cc]}{8-rr}" + ("x" if captured != "." else "")
        if flag in PROMO_FLAGS:
            s += "=" + flag[1]
        return s

    def game_state(self):
        lm = self.legal(self.turn)
        if not lm:
            return "checkmate" if self.check(self.turn) else "stalemate"
        # FIDE-style automatic draw conditions supported by this local engine.
        if self.halfmove >= 100:
            return "draw50"
        current = self.key()
        repeats = 1
        for snap in self.history:
            try:
                raw = ("".join("".join(r) for r in snap["board"]) + snap["turn"]
                       + str(snap["castle"]) + str(snap["ep"]))
                if hashlib.sha256(raw.encode()).hexdigest() == current:
                    repeats += 1
            except Exception:
                pass
        if repeats >= 3:
            return "draw3"
        return "check" if self.check(self.turn) else "play"

    def key(self):
        raw = "".join("".join(r) for r in self.board) + self.turn + str(self.castle) + str(self.ep)
        return hashlib.sha256(raw.encode()).hexdigest()
