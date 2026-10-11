#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MATIN CHESS — desktop edition launcher.

Usage:
    python main.py               # normal launch
    python main.py --demo        # scripted bot-vs-bot tour (for video capture)
    python main.py --selftest    # headless integrity check, exit code 0/1
"""
import sys


def selftest():
    """Headless integrity check — no window is opened."""
    from matin_chess.core import ChessGame, PROMO_FLAGS
    from matin_chess.engine import ChessAI, BOTS, BOT_BY_ID
    from matin_chess.constants import BOARD_STYLES, PIECE_COLORS, THEMES
    from matin_chess.content import TRAINING_LEVELS, ACADEMY_LESSONS, ACADEMY_TEXTS
    checks = []

    g = ChessGame()
    checks.append(("20 legal moves at start", len(g.legal("w")) == 20))

    def perft(game, d):
        if d == 0:
            return 1
        n = 0
        for m in game.legal(game.turn):
            s = game.snap()
            game._apply_raw(m, record=False)
            n += perft(game, d - 1)
            game.restore(s)
        return n
    checks.append(("perft(2) == 400", perft(ChessGame(), 2) == 400))
    checks.append(("perft(3) == 8902", perft(ChessGame(), 3) == 8902))

    # castling / en passant / promotion
    g2 = ChessGame()
    for m in [(6, 4, 4, 4, None), (1, 7, 2, 7, None), (7, 6, 5, 5, None),
              (0, 6, 2, 5, None), (7, 5, 6, 6, None), (0, 5, 2, 4, None)]:
        g2.apply(m)
    checks.append(("castling generated", any(m[4] == "castleK" for m in g2.legal("w"))))
    g2.apply((7, 4, 7, 6, "castleK"))
    checks.append(("castling applied", g2.board[7][5] == "R" and g2.board[7][6] == "K"))

    g3 = ChessGame()
    for m in [(6, 4, 4, 4, None), (1, 0, 2, 0, None), (4, 4, 3, 4, None), (1, 3, 3, 3, None)]:
        g3.apply(m)
    ep = [m for m in g3.legal("w") if m[4] == "ep"]
    checks.append(("en passant generated", bool(ep)))
    if ep:
        g3.apply(ep[0])
    checks.append(("en passant applied", g3.captured and g3.captured[-1] == "p"))

    g4 = ChessGame()
    g4.board = [["."] * 8 for _ in range(8)]
    g4.board[1][0] = "P"
    g4.board[0][1] = "k"
    g4.board[7][7] = "K"
    g4.turn = "w"
    g4.castle = {k: False for k in "KQkq"}
    promos = [m for m in g4.legal("w") if m[4] in PROMO_FLAGS]
    checks.append(("4 promotion choices", len(promos) == 4))

    # bots registry
    checks.append(("7 bots", len(BOTS) == 7))
    checks.append(("matin 20 levels", BOT_BY_ID["matin"].levels == 20))
    checks.append(("veltrix 8 levels + 3 models",
                   BOT_BY_ID["veltrix"].levels == 8 and len(BOT_BY_ID["veltrix"].variants) == 3))
    ten_level_bots = [b for b in BOTS if b.id not in ("matin", "veltrix")]
    checks.append(("all other bots have 10 levels", all(b.levels == 10 for b in ten_level_bots)))
    for b in BOTS:
        d1, t1, s1 = b.curve(1)
        dN, tN, sN = b.curve(b.levels)
        checks.append((f"{b.latin}: level1 weak (sigma>200), level max strong (sigma=0)",
                       s1 > 200 and sN == 0 and dN > d1 and tN > t1))

    # engine sanity: every level returns a legal move
    g5 = ChessGame()
    ai = ChessAI("matin")
    ok = True
    for lv in (1, 10, 20):
        g5 = ChessGame()
        m = ai.best(g5, lv, time_limit=0.4)
        if m not in g5.legal("w"):
            ok = False
    checks.append(("engine legal moves at levels 1/10/20", ok))

    # audio assets extract headlessly
    from matin_chess.audio import AudioEngine
    a = AudioEngine()
    checks.append(("real move sound extracted", a.real_sound_available("move")))
    checks.append(("real capture sound extracted", a.real_sound_available("capture")))
    a.cleanup()

    # content integrity
    checks.append(("8 board themes (Veltrix)", len(BOARD_STYLES) == 8))
    checks.append(("10 themes", len(THEMES) == 10))
    checks.append(("4 piece styles", len(PIECE_COLORS) == 4))
    checks.append(("10 training puzzles", len(TRAINING_LEVELS) == 10))
    checks.append(("10 academy lessons", len(ACADEMY_LESSONS) == 10))
    missing = [t for _, t, _ in ACADEMY_LESSONS if t not in ACADEMY_TEXTS]
    checks.append(("academy lesson texts all reachable (bugfix)", not missing))

    failed = [name for name, okk in checks if not okk]
    for name, okk in checks:
        print(("PASS " if okk else "FAIL ") + str(name))
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("FAILED:", failed)
    return 0 if not failed else 1


def main():
    demo = "--demo" in sys.argv
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    import tkinter as tk
    from tkinter import ttk
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    root = tk.Tk()
    from matin_chess.app import MatinChessX
    app = MatinChessX(root, demo=demo)
    root.mainloop()


if __name__ == "__main__":
    main()
