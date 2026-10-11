# -*- coding: utf-8 -*-
"""MATIN CHESS — the tkinter application.

Look & feel of the original single-file MATIN CHESS desktop edition,
upgraded with the Android-edition feature set: the multi-bot battle
system, bot-vs-bot spectate, a real promotion picker, an update banner,
and the Veltrix board design (gui/board_widget.py of the Veltrix project)
rendered exactly as requested.
"""
import json
import math
import os
import pathlib
import random
import threading
import time
import webbrowser

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser

from .constants import (APP_VERSION, APP_REPO, CREATORS_FA, CREATORS_EN, FILES, VALUE,
                        UNICODE, FILLED, BOARD_STYLES, DEFAULT_BOARD_STYLE,
                        PIECE_COLORS, PIECE_LINE_LIGHT, PIECE_LINE_DARK, THEMES,
                        HL_LAST_LIGHT, HL_LAST_DARK, HL_CHECK, HL_SELECTED,
                        HL_TARGET_EMPTY, HL_TARGET_CAPTURE, fa_num)
from .core import ChessGame, PROMO_FLAGS
from .engine import ChessAI, BOTS, BOT_BY_ID
from .audio import AudioEngine
from .systems import (AppLogger, StatsDB, SaveVault, PGNExporter, ColorTools,
                      ReplayEngine, TournamentEngine, PerformanceMeter,
                      ChessAnalytics, DeviceInfo)
from .content import TRAINING_LEVELS, ACADEMY_LESSONS, ACADEMY_TEXTS


# ------------------------------------------------------------- font resolution
# Windows uses Segoe UI / Segoe UI Symbol natively.  On Linux/macOS we probe
# the installed font families once and fall back to the best available
# (Vazirmatn for Persian, Noto Emoji / DejaVu Sans for symbols), so the game
# renders correctly everywhere — including the recorded gameplay video.
UI_FONT = "Segoe UI"
SYMBOL_FONT = "Segoe UI Symbol"
MONO_FONT = "Consolas"


def resolve_fonts(root):
    global UI_FONT, SYMBOL_FONT, MONO_FONT
    try:
        import tkinter.font as tkfont
        fams = set(tkfont.families(root))
        for cand in (UI_FONT, "Vazirmatn", "Noto Sans Arabic", "Tahoma"):
            if cand in fams:
                UI_FONT = cand
                break
        for cand in (SYMBOL_FONT, "Noto Emoji", "Noto Sans Symbols 2", "DejaVu Sans"):
            if cand in fams:
                SYMBOL_FONT = cand
                break
        for cand in (MONO_FONT, "DejaVu Sans Mono", "Liberation Mono"):
            if cand in fams:
                MONO_FONT = cand
                break
    except Exception:
        pass


class Trophy:
    def __init__(self, root, parent):
        self.root = root
        self.parent = parent
        self.frame = tk.Frame(parent, bg="#120e08", bd=3, relief="ridge")
        self.frame.pack(fill="x", padx=20, pady=12)
        self.label = tk.Label(self.frame, text="🏆  MATIN CHESS", bg="#120e08",
                              fg="#ffd76a", font=(UI_FONT, 18, "bold"))
        self.label.pack(pady=(10, 2))
        self.sub = tk.Label(self.frame, text="Win a match to claim the cup!",
                            bg="#120e08", fg="#fff3cf", font=(UI_FONT, 9))
        self.sub.pack(pady=(0, 10))
        self.particles = []

    def celebrate(self, text="🏆 قهرمان!"):
        self.label.configure(text=text)
        self.sub.configure(text="✨ MATIN CHESS • CHAMPION ✨")
        for i in range(18):
            self.root.after(i * 45, self._flash)

    def _flash(self):
        self.label.configure(fg=random.choice(["#fff2a8", "#ffd76a", "#ffffff", "#e9b949"]))


class MatinChessX:
    # ================================================================ setup
    def __init__(self, root, demo=False):
        self.root = root
        self.demo_mode = demo
        self.root.title("MATIN CHESS")
        self.root.geometry("1280x820")
        self.root.minsize(1000, 700)
        self.root.configure(bg="#090b18")
        resolve_fonts(root)
        self.audio = AudioEngine()
        self.logger = AppLogger()
        self.db = StatsDB()
        self.tournament = TournamentEngine()
        self.replay = ReplayEngine()
        self.performance = PerformanceMeter()
        self.game_started_at = time.time()
        self.db_game_id = None
        self.g = ChessGame()
        self.theme = "Galaxy"
        self.language = "فارسی"
        self.board_style = DEFAULT_BOARD_STYLE
        self.custom_light, self.custom_dark = BOARD_STYLES[DEFAULT_BOARD_STYLE]
        self.custom_board_colors = False
        self.piece_style = "Classic"
        self.unlocked = 1
        # bot battle system state
        self.bot_id = "matin"
        self.bot_variant = None          # None | "flash" | "light" | "high"
        self.level = 1
        self.player = "w"
        self.two_player = False
        self.spectate = False
        self.spec_w = None               # (bot_id, level, variant)
        self.spec_b = None
        self.spec_delay = 700
        self.spec_engine_w = None
        self.spec_engine_b = None
        self.spec_job = None
        self.game_mode = "هوش مصنوعی"
        self.game_finished = False
        self.ai_thinking = False
        self.hint = None
        self.selected = None
        self.flipped = False
        self.anim_speed = 820
        self.ai_min_delay = 2000
        self.ai_animation_speed = 2200
        self._ai_move_animation = False
        self.hover_square = None
        self.animating = False
        self.animation_job = None
        self.sound = True
        self.music = True
        self.hints = True
        self.last_time = time.time()
        self.stats = {"games": 0, "wins": 0, "losses": 0, "draws": 0, "moves": 0,
                      "captures": 0, "checkmates": 0, "academy_done": 0,
                      "best_streak": 0, "current_streak": 0}
        self.move_analysis = []
        self.training_mode = False
        self.training_index = 0
        self.training_game = None
        self.training_target = None
        self.clock = {"w": 600, "b": 600}
        self.time_mode = "∞"
        self.clock_job = None
        self.autosave_job = None
        self.session_file = pathlib.Path.home() / ".matin_chess_session.mcgx"
        self.settings_file = pathlib.Path.home() / ".matin_chess_galaxy_x.json"
        self._update_checked = False
        self._update_info = None         # (latest_tag, url) or None
        self.load_settings()
        self.language = "فارسی"
        self.ai = ChessAI(self.bot_id)
        self.build_menu()
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.exit_fullscreen())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-s>", lambda e: self.quick_save())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-h>", lambda e: self.hint_move())
        self.root.bind("<Control-n>", lambda e: self.bots_screen())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_file())
        self.root.after(1200, self.autosave_tick)
        self.check_for_updates_async()
        if self.demo_mode:
            self.root.after(400, self._demo_tour)

    def colors(self):
        return THEMES[self.theme]

    def clear(self):
        for w in self.root.winfo_children():
            w.destroy()

    def button(self, parent, text, cmd, big=False):
        bg = self.colors()[1]
        fg = self.colors()[2]
        ac = self.colors()[3]
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                      activebackground=ac, activeforeground="#ffffff",
                      relief="flat", bd=0, font=(UI_FONT, 15 if big else 11, "bold"),
                      padx=24, pady=13, cursor="hand2")

        def _enter(e):
            b.configure(bg=ac, relief="raised", bd=2, highlightthickness=1,
                        highlightbackground="#f6df9a")

        def _leave(e):
            b.configure(bg=bg, relief="flat", bd=0, highlightthickness=0)
        b.bind("<Enter>", _enter)
        b.bind("<Leave>", _leave)
        return b

    def themeize_buttons(self, root=None):
        root = root or self.root
        accent = self.colors()[3]

        def walk(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Button):
                    normal = child.cget("bg")
                    try:
                        child.configure(activebackground=accent, activeforeground="#ffffff")
                        child.bind("<Enter>", lambda e, b=child, n=normal: b.configure(bg=accent, relief="raised", bd=1))
                        child.bind("<Leave>", lambda e, b=child, n=normal: b.configure(bg=n, relief="flat", bd=0))
                    except Exception:
                        pass
                walk(child)
        walk(root)

    # ================================================================ menu
    def build_menu(self):
        self.spectate = False
        self.clear()
        self.root.configure(bg="#0b0f14")
        shell = tk.Frame(self.root, bg="#0b0f14")
        shell.pack(fill="both", expand=True)
        side = tk.Frame(shell, bg="#111820", width=245)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="M", bg="#1c2732", fg="#f2c66d",
                 font=(UI_FONT, 26, "bold"), width=3, height=1).pack(pady=(28, 8))
        tk.Label(side, text="MATIN\nCHESS", bg="#111820", fg="#f4f6f8",
                 font=(UI_FONT, 18, "bold"), justify="center").pack(pady=(0, 30))
        tk.Label(side, text="مرکز بازی", bg="#111820", fg="#748190",
                 font=(UI_FONT, 8, "bold")).pack(pady=(0, 8))
        items = [
            ("♟", "بازی با هوش مصنوعی", self.bots_screen),
            ("♟♟", "بازی دونفره", self.two_player_setup),
            ("🤖", "مشاهده بازی هوش مصنوعی", self.spectate_setup),
            ("🎓", "آکادمی آموزش", self.academy_menu),
            ("🎯", "تمرین یک‌حرکتی", self.training_menu),
            ("◈", "ظاهر و تم", self.themes),
            ("▣", "آمار", self.statistics),
            ("↥", "ذخیره / بارگذاری", self.save_load),
            ("⚙", "تنظیمات", self.settings),
            ("?", "راهنما", self.help),
            ("ⓘ", "درباره", self.about),
        ]
        for icon, label, cmd in items:
            b = tk.Button(side, text=f"  {icon}   {label}", command=cmd, anchor="w",
                          bg="#111820", fg="#cbd4dd", activebackground="#202d39",
                          activeforeground="#f2c66d", relief="flat", bd=0,
                          font=(UI_FONT, 11, "bold"), padx=18, pady=12, cursor="hand2")
            b.pack(fill="x", padx=12, pady=2)
        tk.Frame(side, bg="#26333e", height=1).pack(fill="x", padx=20, pady=22)
        tk.Label(side, text="سازندگان", bg="#111820", fg="#667482",
                 font=(UI_FONT, 8, "bold")).pack()
        tk.Label(side, text="متین کتویی زاده\nامیرمحمد گلستان", bg="#111820", fg="#f2c66d",
                 font=(UI_FONT, 11, "bold"), justify="center").pack(pady=5)
        tk.Button(side, text="×   خروج", command=self.close, bg="#111820", fg="#9ba7b2",
                  activebackground="#2a2020", activeforeground="#ff7777", relief="flat",
                  bd=0, font=(UI_FONT, 10, "bold"), cursor="hand2").pack(side="bottom", pady=22)

        content = tk.Frame(shell, bg="#0b0f14")
        content.pack(side="left", fill="both", expand=True, padx=30, pady=26)
        top = tk.Frame(content, bg="#0b0f14")
        top.pack(fill="x")
        tk.Label(top, text="بازی خوب؛ فکر بهتر!", bg="#0b0f14", fg="#f4f6f8",
                 font=(UI_FONT, 28, "bold")).pack(side="left")
        tk.Label(top, text=f"  میز شطرنج / {APP_VERSION}", bg="#0b0f14", fg="#697786",
                 font=(MONO_FONT, 9, "bold")).pack(side="right", pady=12)
        tk.Frame(content, bg="#29333d", height=1).pack(fill="x", pady=(18, 22))

        # update banner (Android-edition feature)
        if self._update_info:
            latest, url = self._update_info
            banner = tk.Button(content, text=f"🎉 نسخهٔ جدید {latest} منتشر شد — برای دانلود کلیک کنید",
                               command=lambda u=url: webbrowser.open(u), bg="#2a2113", fg="#ffd76a",
                               activebackground="#3a2e18", activeforeground="#ffe9a8",
                               relief="flat", bd=0, font=(UI_FONT, 11, "bold"),
                               padx=18, pady=9, cursor="hand2", anchor="w")
            banner.pack(fill="x", pady=(0, 14))

        hero = tk.Frame(content, bg="#18212a", highlightbackground="#2a3742", highlightthickness=1)
        hero.pack(fill="x")
        left = tk.Frame(hero, bg="#18212a")
        left.pack(side="left", fill="both", expand=True, padx=28, pady=26)
        tk.Label(left, text="آمادهٔ طرح صفحه شطرنجی؟", bg="#18212a", fg="#f2c66d",
                 font=(UI_FONT, 10, "bold")).pack(anchor="w")
        tk.Label(left, text="حرکت بعدی شما\nاز اینجا شروع می‌شود.", bg="#18212a",
                 fg="#ffffff", font=(UI_FONT, 30, "bold"), justify="left").pack(anchor="w", pady=(8, 12))
        tk.Label(left, text="۷ ربات نبرد • ۲۰ سطح متین • قوانین کامل • صفحهٔ سینمایی",
                 bg="#18212a", fg="#9aa8b5", font=(UI_FONT, 10)).pack(anchor="w")
        self.button(hero, "شروع شطرنج  ←", self.bots_screen, big=True).pack(side="right", padx=30, pady=45)

        tk.Label(content, text="دسترسی سریع", bg="#0b0f14", fg="#73818e",
                 font=(UI_FONT, 9, "bold")).pack(anchor="w", pady=(25, 10))
        cards = tk.Frame(content, bg="#0b0f14")
        cards.pack(fill="x")
        data = [("♜", "۷", "ربات نبرد", "هر ربات نردبان خودش", self.bots_screen),
                ("🤖", "ربات✕ربات", "مشاهده مسابقه", "دو ربات به هم", self.spectate_setup),
                ("♟♟", "۲ نفر", "بازی دونفره", "روی یک رایانه", self.two_player_setup),
                ("🎓", "۱۰ درس", "آکادمی", "آموزش مرحله‌ای", self.academy_menu)]
        for icon, val, title, sub, cmd in data:
            card = tk.Frame(cards, bg="#141c24", highlightbackground="#27343f",
                            highlightthickness=1, width=220, height=115)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12))
            card.pack_propagate(False)
            card.bind("<Button-1>", lambda e, c=cmd: c())
            tk.Label(card, text=icon, bg="#141c24", fg="#f2c66d",
                     font=(SYMBOL_FONT, 20)).pack(anchor="w", padx=18, pady=(12, 0))
            tk.Label(card, text=f"{val}  {title}", bg="#141c24", fg="#f4f6f8",
                     font=(UI_FONT, 14, "bold")).pack(anchor="w", padx=18)
            tk.Label(card, text=sub, bg="#141c24", fg="#71808d",
                     font=(UI_FONT, 8)).pack(anchor="w", padx=18)
        footer = tk.Frame(content, bg="#0b0f14")
        footer.pack(side="bottom", fill="x", pady=8)
        tk.Label(footer, text="MATIN CHESS • نسخهٔ میز شطرنج", bg="#0b0f14", fg="#46535f",
                 font=(MONO_FONT, 8, "bold")).pack(side="left")
        tk.Label(footer, text=f"تم / {self.theme.upper()} • {APP_VERSION}", bg="#0b0f14",
                 fg="#687682", font=(MONO_FONT, 8)).pack(side="right")

    def page_header(self, title, subtitle=None):
        bg, panel, fg, accent, _ = self.colors()
        top = tk.Frame(self.root, bg=bg)
        top.pack(fill="x", padx=28, pady=(18, 10))
        back = tk.Button(top, text="←  منوی اصلی", command=self.build_menu, bg="#ffffff",
                         fg="#17212a", activebackground="#f2c66d",
                         activeforeground="#101820", relief="flat", bd=0,
                         font=(UI_FONT, 10, "bold"), padx=18, pady=9, cursor="hand2")
        back.pack(side="left")
        tk.Label(top, text=title, bg=bg, fg=fg, font=(UI_FONT, 25, "bold")).pack(side="right")
        if subtitle:
            tk.Label(self.root, text=subtitle, bg=bg, fg=accent,
                     font=(UI_FONT, 10, "bold")).pack(anchor="e", padx=30)
        tk.Frame(self.root, bg="#29333d", height=1).pack(fill="x", padx=28, pady=(8, 12))
        return top

    # ========================================================= bots screens
    def bots_screen(self):
        self.clear()
        bg, panel, fg, accent, _ = self.colors()
        self.page_header("ربات‌های شطرنج",
                         "۷ ربات نبرد • هر ربات نردبان قدرت مخصوص خودش را دارد")
        area = tk.Frame(self.root, bg=bg)
        area.pack(fill="both", expand=True, padx=40, pady=10)
        for i, b in enumerate(BOTS):
            card = tk.Frame(area, bg="#141c24", highlightbackground=b.c2, highlightthickness=2)
            card.grid(row=i // 4, column=i % 4, padx=10, pady=10, sticky="nsew")
            tk.Label(card, text=b.icon, bg="#141c24", fg=b.c1,
                     font=(SYMBOL_FONT, 26)).pack(pady=(14, 0))
            tk.Label(card, text=b.latin, bg="#141c24", fg=b.c1,
                     font=(MONO_FONT, 11, "bold")).pack()
            tk.Label(card, text=b.fa, bg="#141c24", fg="#f4f6f8",
                     font=(UI_FONT, 13, "bold")).pack()
            tk.Label(card, text=b.tag, bg="#141c24", fg="#8f9eab",
                     font=(UI_FONT, 8), wraplength=190, justify="center").pack(pady=(4, 6), padx=8)
            lvls = f"{fa_num(b.levels)} سطح" + (" + ۳ مدل" if b.variants else "")
            tk.Label(card, text=lvls, bg="#1a232c", fg=b.c1,
                     font=(UI_FONT, 9, "bold")).pack(pady=(0, 6), ipadx=8, ipady=2)
            self.button(card, "انتخاب", lambda bb=b: self.bot_levels(bb)).pack(pady=(0, 12), ipadx=14)
        for c in range(4):
            area.grid_columnconfigure(c, weight=1, uniform="bots")
        for r in range(2):
            area.grid_rowconfigure(r, weight=1, uniform="botsr")
        self.themeize_buttons()

    def bot_levels(self, bot):
        self.clear()
        bg, panel, fg, accent, _ = self.colors()
        lvls_fa = f"{fa_num(bot.levels)} سطح • سطح ۱ آسان برای تازه‌کارها • سطح {fa_num(bot.levels)} = قدرت کامل"
        self.page_header(f"{bot.icon} {bot.fa} — {bot.latin}", lvls_fa)
        area = tk.Frame(self.root, bg=bg)
        area.pack(fill="both", expand=True, padx=40, pady=8)
        cols = 5
        for i in range(1, bot.levels + 1):
            row, col = (i - 1) // cols, (i - 1) % cols
            locked = bot.id == "matin" and i > self.unlocked
            label = ("🔒 " if locked else "♟ ") + f"سطح {fa_num(i)}"
            b = self.button(area, label, lambda n=i, bb=bot: self.setup_game(n, bb))
            if locked:
                b.configure(state="disabled")
            b.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        for c in range(cols):
            area.grid_columnconfigure(c, weight=1)
        if bot.variants:
            tk.Label(self.root, text="مدل‌های رسمی ولتریکس — دقیقاً مطابق پروژهٔ اصلی",
                     bg=bg, fg=accent, font=(UI_FONT, 11, "bold")).pack(pady=(10, 2))
            vrow = tk.Frame(self.root, bg=bg)
            vrow.pack(fill="x", padx=60, pady=(2, 10))
            for key, fa, latin, depth, t, sigma, desc in bot.variants:
                vcard = tk.Frame(vrow, bg="#141c24", highlightbackground=bot.c2, highlightthickness=2)
                vcard.pack(side="left", fill="both", expand=True, padx=8)
                tk.Label(vcard, text=fa, bg="#141c24", fg="#f4f6f8",
                         font=(UI_FONT, 14, "bold")).pack(pady=(10, 0))
                tk.Label(vcard, text=latin, bg="#141c24", fg=bot.c1,
                         font=(MONO_FONT, 10, "bold")).pack()
                tk.Label(vcard, text=desc, bg="#141c24", fg="#8f9eab",
                         font=(UI_FONT, 8), wraplength=200, justify="center").pack(pady=4, padx=8)
                self.button(vcard, "بازی", lambda k=key, bb=bot: self.setup_game(None, bb, variant=k)).pack(pady=(0, 10), ipadx=10)
        self.themeize_buttons()

    # ============================================================= spectate
    def spectate_setup(self):
        win = tk.Toplevel(self.root)
        win.title("مشاهده بازی هوش مصنوعی")
        win.geometry("560x620")
        win.configure(bg=self.colors()[0])
        win.grab_set()
        tk.Label(win, text="🤖  مشاهده بازی هوش مصنوعی", bg=self.colors()[0], fg=self.colors()[3],
                 font=(UI_FONT, 20, "bold")).pack(pady=(22, 4))
        tk.Label(win, text="ربات در مقابل ربات — دو موتور را انتخاب کن و تماشا کن",
                 bg=self.colors()[0], fg=self.colors()[2], font=(UI_FONT, 10)).pack(pady=(0, 16))
        names = [f"{b.icon}  {b.fa} — {b.latin}" for b in BOTS]
        ids = [b.id for b in BOTS]
        maxlv = {b.id: b.levels for b in BOTS}

        def side_block(parent, title, default_id, default_lv):
            box = tk.Frame(parent, bg=self.colors()[1], highlightbackground="#2d3a46", highlightthickness=1)
            box.pack(fill="x", padx=24, pady=8)
            tk.Label(box, text=title, bg=self.colors()[1], fg=self.colors()[3],
                     font=(UI_FONT, 12, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
            nb = tk.StringVar(value=names[ids.index(default_id)])
            ttk.Combobox(box, textvariable=nb, values=names, state="readonly", width=30).pack(padx=14, pady=4)
            lv = tk.IntVar(value=default_lv)
            spin = ttk.Spinbox(box, from_=1, to=maxlv[default_id], textvariable=lv, width=8)
            spin.pack(padx=14, pady=(2, 10))

            def refresh(*_):
                bid = ids[names.index(nb.get())]
                spin.configure(to=maxlv[bid])
                lv.set(min(lv.get(), maxlv[bid]))
            nb.trace_add("write", refresh)
            return nb, lv

        wbot, wlv = side_block(win, "♔ ربات سفید", "matin", 8)
        bbot, blv = side_block(win, "♚ ربات سیاه", "stockfish", 6)
        tk.Label(win, text="سرعت نمایش حرکت‌ها", bg=self.colors()[0], fg=self.colors()[2],
                 font=(UI_FONT, 10, "bold")).pack(pady=(14, 2))
        speedv = tk.StringVar(value="عادی")
        for x, d in (("سریع", 350), ("عادی", 700), ("آرام و سینمایی", 1300)):
            tk.Radiobutton(win, text=x, variable=speedv, value=x, bg=self.colors()[0],
                           fg=self.colors()[2], selectcolor=self.colors()[1],
                           activebackground=self.colors()[0], activeforeground=self.colors()[3],
                           font=(UI_FONT, 10), command=lambda dd=d: setattr(self, "spec_delay", dd)).pack(anchor="w", padx=200)
        self.spec_delay = 700

        def go():
            wid, bid = ids[names.index(wbot.get())], ids[names.index(bbot.get())]
            self.start_spectate((wid, int(wlv.get()), None), (bid, int(blv.get()), None))
            win.destroy()
        self.button(win, "شروع تماشا  →", go, big=True).pack(pady=20)
        self.button(win, "انصراف", win.destroy).pack()
        self.themeize_buttons(win)

    def start_spectate(self, spec_w, spec_b):
        self.training_mode = False
        self.training_game = None
        self.training_target = None
        self.spectate = True
        self.spec_w, self.spec_b = spec_w, spec_b
        self.spec_engine_w = ChessAI(spec_w[0])
        self.spec_engine_b = ChessAI(spec_b[0])
        self.game_mode = "مشاهده ربات‌ها"
        self.time_mode = "∞"
        self.clock = {"w": None, "b": None}
        self.g = ChessGame()
        self.selected = None
        self.hint = None
        self.ai_thinking = False
        self.game_finished = False
        self.move_analysis = []
        self.game_started_at = time.time()
        self.anim_speed = 520
        self.ai_animation_speed = 700
        self.ai_min_delay = self.spec_delay
        self.build_game()
        self.audio.play("start")
        self.audio.start_music()
        self.root.after(900, self._spectate_step)

    def _spectate_step(self):
        if not self.spectate or self.game_finished:
            return
        if self.animating or self.ai_thinking:
            self.spec_job = self.root.after(150, self._spectate_step)
            return
        state = self.g.game_state()
        if state not in ("play", "check"):
            self._spectate_finish(state)
            return
        engine = self.spec_engine_w if self.g.turn == "w" else self.spec_engine_b
        spec = self.spec_w if self.g.turn == "w" else self.spec_b
        self.ai_thinking = True
        self.status.configure(text=f"🧠 {BOT_BY_ID[spec[0]].fa} در حال فکر کردن...")

        def work():
            cap = 0.55 if self.demo_mode else None
            m = engine.best(self.g, spec[1], variant=spec[2], time_limit=cap)
            self.root.after(0, lambda: self._spectate_move(m))
        threading.Thread(target=work, daemon=True).start()

    def _spectate_move(self, m):
        self.ai_thinking = False
        if m is None:
            self._spectate_finish(self.g.game_state())
            return
        self._ai_move_animation = True
        self.make_move(m)

    def _spectate_finish(self, state):
        self.game_finished = True
        self.ai_thinking = False
        wname = BOT_BY_ID[self.spec_w[0]].fa
        bname = BOT_BY_ID[self.spec_b[0]].fa
        wl = f"سطح {fa_num(self.spec_w[1])}" + (f" / {dict((v[0], v[1]) for v in BOT_BY_ID[self.spec_w[0]].variants).get(self.spec_w[2], '')}" if self.spec_w[2] else "")
        bl = f"سطح {fa_num(self.spec_b[1])}" + (f" / {dict((v[0], v[1]) for v in BOT_BY_ID[self.spec_b[0]].variants).get(self.spec_b[2], '')}" if self.spec_b[2] else "")
        if state == "checkmate":
            winner = "b" if self.g.turn == "w" else "w"
            txt = (f"🏆 {wname} ({wl}) با کیش‌ومات برنده شد!" if winner == "w"
                   else f"🏆 {bname} ({bl}) با کیش‌ومات برنده شد!")
        elif state in ("stalemate", "drawMaterial"):
            txt = "مساوی شد — پات!" if state == "stalemate" else "مساوی — مهرهٔ کافی برای مات نبود."
        else:
            txt = "مساوی شد."
        self.audio.play("finish")
        self.audio.victory()
        win = tk.Toplevel(self.root)
        win.title("پایان مسابقهٔ ربات‌ها")
        win.geometry("560x400")
        win.configure(bg="#101820")
        win.grab_set()
        tk.Label(win, text="🤖🤖", font=(SYMBOL_FONT, 52), bg="#101820",
                 fg="#f2c66d").pack(pady=(22, 4))
        tk.Label(win, text="پایان مسابقهٔ ربات‌ها", font=(UI_FONT, 22, "bold"),
                 bg="#101820", fg="#ffffff").pack()
        tk.Label(win, text=txt, font=(UI_FONT, 13, "bold"), bg="#101820",
                 fg="#f2c66d", wraplength=460).pack(pady=14)
        tk.Label(win, text=f"♔ {wname} ({wl})   در برابر   ♚ {bname} ({bl})",
                 font=(UI_FONT, 11), bg="#101820", fg="#aab6c0").pack()
        self.button(win, "تماشای دوباره", lambda: (win.destroy(), self.start_spectate(self.spec_w, self.spec_b))).pack(pady=16)
        self.button(win, "منوی اصلی", lambda: (win.destroy(), self.build_menu())).pack()
        self.themeize_buttons(win)

    def stop_spectate(self):
        self.spectate = False
        if self.spec_job:
            try:
                self.root.after_cancel(self.spec_job)
            except Exception:
                pass
        self.build_menu()

    # ========================================================= game setup
    def academy_menu(self):
        self.clear()
        bg, panel, fg, accent, _ = self.colors()
        self.page_header("🎓 آکادمی MATIN CHESS", "۱۰ درس کوتاه و مرحله‌ای؛ همهٔ درس‌ها در یک صفحه جا می‌شوند.")
        area = tk.Frame(self.root, bg=bg)
        area.pack(fill="both", expand=True, padx=28, pady=4)
        for i, (num, title, desc) in enumerate(ACADEMY_LESSONS):
            card = tk.Frame(area, bg="#141c24", highlightbackground="#344554", highlightthickness=1)
            card.grid(row=i // 5, column=i % 5, padx=4, pady=4, sticky="nsew")
            tk.Label(card, text=num, bg="#141c24", fg=accent, font=(UI_FONT, 15, "bold")).pack(pady=(10, 0))
            tk.Label(card, text=title, bg="#141c24", fg="#ffffff", font=(UI_FONT, 10, "bold")).pack()
            tk.Label(card, text=desc, bg="#141c24", fg="#8f9eab", font=(UI_FONT, 8),
                     wraplength=150, justify="center").pack(pady=2, padx=6)
            self.button(card, "درس", lambda n=num, t=title, d=desc: self.academy_lesson(n, t, d)).pack(pady=(2, 10), ipadx=10)
        for c in range(5):
            area.grid_columnconfigure(c, weight=1)
        for r in range(2):
            area.grid_rowconfigure(r, weight=1)

    def academy_lesson(self, num, title, desc):
        win = tk.Toplevel(self.root)
        win.title(f"آکادمی MATIN CHESS — درس {num}")
        win.geometry("650x520")
        win.configure(bg="#101820")
        win.grab_set()
        tk.Label(win, text=f"درس {num}  •  {title}", bg="#101820", fg="#f2c66d",
                 font=(UI_FONT, 23, "bold")).pack(pady=(28, 8))
        text = ACADEMY_TEXTS.get(title, desc)   # BUGFIX: keys now match titles
        box = tk.Frame(win, bg="#17212a", highlightbackground="#33424e", highlightthickness=1)
        box.pack(fill="both", expand=True, padx=28, pady=20)
        tk.Label(box, text=text, bg="#17212a", fg="#eef2f5", font=(UI_FONT, 13),
                 wraplength=540, justify="right", anchor="e").pack(fill="both", expand=True, padx=28, pady=28)
        self.button(win, "متوجه شدم ✓", win.destroy, big=True).pack(pady=(0, 22))

    def two_player_setup(self):
        win = tk.Toplevel(self.root)
        win.title("بازی دونفره")
        win.geometry("460x500")
        win.configure(bg=self.colors()[0])
        win.grab_set()
        tk.Label(win, text="♟  بازی دونفره", bg=self.colors()[0], fg=self.colors()[3],
                 font=(UI_FONT, 25, "bold")).pack(pady=(28, 8))
        tk.Label(win, text="دو نفر روی یک کامپیوتر، بدون هوش مصنوعی", bg=self.colors()[0],
                 fg=self.colors()[2], font=(UI_FONT, 10)).pack(pady=(0, 20))
        timev = tk.StringVar(value="∞")
        tk.Label(win, text="زمان هر بازیکن", bg=self.colors()[0], fg=self.colors()[2],
                 font=(UI_FONT, 11, "bold")).pack(pady=8)
        for x in ("∞", "10 دقیقه", "5 دقیقه", "3 دقیقه"):
            tk.Radiobutton(win, text=x, variable=timev, value=x, bg=self.colors()[0],
                           fg=self.colors()[2], selectcolor=self.colors()[1],
                           activebackground=self.colors()[0], activeforeground=self.colors()[3],
                           font=(UI_FONT, 10)).pack(anchor="w", padx=135)
        self.button(win, "شروع بازی دونفره  →",
                    lambda: (win.destroy(), self.start_game(1, "سفید", timev.get(), two_player=True)),
                    big=True).pack(pady=28)
        self.button(win, "انصراف", win.destroy).pack()

    def training_menu(self):
        self.clear()
        bg, panel, fg, accent, _ = self.colors()
        top = tk.Frame(self.root, bg=bg)
        top.pack(fill="x", pady=18)
        tk.Label(top, text="🎯 تمرین‌های مات", bg=bg, fg=fg, font=(UI_FONT, 25, "bold")).pack()
        tk.Label(top, text="۱۰ تمرین مات در یک حرکت • هر کارت یک موقعیت جداگانه است", bg=bg,
                 fg=accent, font=(UI_FONT, 10, "bold")).pack(pady=4)
        area = tk.Frame(self.root, bg=bg)
        area.pack(fill="both", expand=True, padx=32, pady=10)
        for i, pz in enumerate(TRAINING_LEVELS, 1):
            card = tk.Frame(area, bg="#141c24", highlightbackground="#2c3b49", highlightthickness=1)
            card.grid(row=(i - 1) // 5, column=(i - 1) % 5, padx=6, pady=6, sticky="nsew")
            tk.Label(card, text=f"#{fa_num(i)}", bg="#141c24", fg=accent,
                     font=(UI_FONT, 12, "bold")).pack(pady=(8, 1))
            tk.Label(card, text=pz["name"], bg="#141c24", fg="#ffffff",
                     font=(UI_FONT, 10, "bold")).pack()
            tk.Label(card, text="مات در ۱", bg="#141c24", fg="#8f9eab",
                     font=(UI_FONT, 8, "bold")).pack(pady=1)
            self.button(card, "شروع", lambda n=i - 1: self.start_training(n)).pack(pady=(3, 8))
        for c in range(5):
            area.grid_columnconfigure(c, weight=1, uniform="training")
        for r in range(2):
            area.grid_rowconfigure(r, weight=1, uniform="training")
        self.button(self.root, "← بازگشت", self.build_menu).pack(pady=10)

    def start_training(self, index):
        if not (0 <= index < len(TRAINING_LEVELS)):
            return
        pz = TRAINING_LEVELS[index]
        self.training_mode = True
        self.two_player = False
        self.spectate = False
        self.game_mode = "تمرین"
        self.training_index = index
        self.training_game = ChessGame()
        self.training_game.board = [list(r) for r in pz["board"]]
        self.training_game.turn = pz["side"]
        self.training_game.castle = {k: False for k in "KQkq"}
        self.training_game.ep = None
        self.training_game.history = []
        self.training_game.moves = []
        self.training_game.captured = []
        self.training_game.last = None
        self.g = self.training_game
        self.player = pz["side"]
        self.selected = None
        self.hint = None
        self.training_target = pz["move"]
        self.ai_thinking = False
        self.game_finished = False
        self.time_mode = "∞"
        self.clock = {"w": None, "b": None}
        self.anim_speed = 520
        self.ai_animation_speed = 620
        self.build_game()
        self.status.configure(text=f"🎯 {pz['goal']}  •  حرکت درست را پیدا کن")
        self.audio.play("start")

    def next_training(self):
        n = self.training_index + 1
        if n >= len(TRAINING_LEVELS):
            messagebox.showinfo("تمرین‌ها", "🏆 همهٔ تمرین‌های یک‌حرکتی را کامل کردی!\nتو حالا آمادهٔ تمرین‌های سخت‌تر هستی.")
            self.training_mode = False
            self.training_game = None
            self.training_target = None
            self.build_menu()
            return
        self.start_training(n)

    def setup_game(self, level, bot, variant=None):
        win = tk.Toplevel(self.root)
        win.title("تنظیم مسابقه")
        win.geometry("430x540")
        win.configure(bg=self.colors()[0])
        win.grab_set()
        vlabel = variant and dict((v[0], v[1]) for v in bot.variants).get(variant, "")
        title = f"{bot.icon} {bot.fa} — {vlabel or (level and f'سطح {fa_num(level)}')}"
        tk.Label(win, text=title, bg=self.colors()[0], fg=self.colors()[3],
                 font=(UI_FONT, 20, "bold")).pack(pady=22)
        side = tk.StringVar(value="سفید")
        timev = tk.StringVar(value="∞")
        ttk.Label(win, text="نوع مسابقه").pack(pady=(4, 6))
        mode = tk.StringVar(value="هوش مصنوعی")
        ttk.Radiobutton(win, text="مقابل هوش مصنوعی", variable=mode, value="هوش مصنوعی").pack()
        ttk.Radiobutton(win, text="دو نفره روی یک رایانه", variable=mode, value="دونفره").pack()
        ttk.Label(win, text="مهره شما").pack(pady=8)
        for x in ("سفید", "سیاه"):
            ttk.Radiobutton(win, text=x, variable=side, value=x).pack()
        ttk.Label(win, text="زمان").pack(pady=(18, 5))
        for x in ("∞", "10 دقیقه", "5 دقیقه", "3 دقیقه"):
            ttk.Radiobutton(win, text=x, variable=timev, value=x).pack()
        self.button(win, "شروع مسابقه",
                    lambda: (win.destroy(), self.start_game(level or bot.levels, side.get(), timev.get(),
                                                            two_player=(mode.get() == "دونفره"),
                                                            bot_id=bot.id, variant=variant))).pack(pady=26)

    def start_game(self, level, side, time_mode, two_player=False, bot_id=None, variant=None):
        self.training_mode = False
        self.training_game = None
        self.training_target = None
        self.spectate = False
        self.bot_id = bot_id or self.bot_id
        self.bot_variant = variant
        self.ai = ChessAI(self.bot_id)
        self.level = int(level or 1)
        self.player = "w" if side == "سفید" else "b"
        self.two_player = bool(two_player)
        self.game_mode = "دونفره" if self.two_player else "هوش مصنوعی"
        self.time_mode = time_mode
        self.game_finished = False
        base_by_time = {"∞": 700, "10 دقیقه": 640, "5 دقیقه": 590, "3 دقیقه": 540}
        self.anim_speed = max(460, min(820, base_by_time.get(time_mode, 640) + int(self.level * 4)))
        self.ai_animation_speed = max(1200, min(1550, self.anim_speed + 650))
        if self.two_player:
            self.ai_animation_speed = self.anim_speed
        mins = {"∞": None, "10 دقیقه": 10, "5 دقیقه": 5, "3 دقیقه": 3}[time_mode]
        self.clock = {"w": mins * 60 if mins else None, "b": mins * 60 if mins else None}
        self.g = ChessGame()
        self.selected = None
        self.hint = None
        self.ai_thinking = False
        self.move_analysis = []
        self.stats["games"] += 1
        self.game_started_at = time.time()
        self.db_game_id = self.db.add_game(self.level, self.player, "active", 0, 0, 0,
                                           ChessAnalytics.position_hash(self.g))
        self.logger.info(f"Game started bot={self.bot_id} level={self.level} side={self.player}")
        self.save_settings()
        self.build_game()
        self.audio.play("start")
        self.audio.start_music()
        if (not self.two_player) and self.player == "b":
            self.root.after(self.ai_min_delay, self.ai_move)
        self.tick_clock()

    # ========================================================== game view
    def build_game(self):
        self.clear()
        self.root.configure(bg="#0b0f14")
        shell = tk.Frame(self.root, bg="#0b0f14")
        shell.pack(fill="both", expand=True, padx=18, pady=16)
        head = tk.Frame(shell, bg="#0b0f14")
        head.pack(fill="x", pady=(0, 12))
        tk.Button(head, text="←  منوی اصلی", command=self.build_menu, bg="#ffffff", fg="#17212a",
                  activebackground="#f2c66d", activeforeground="#101820", relief="flat", bd=0,
                  font=(UI_FONT, 10, "bold"), padx=16, pady=8, cursor="hand2").pack(side="left", padx=(0, 18))
        tk.Label(head, text="MATIN CHESS", bg="#0b0f14", fg="#f4f6f8",
                 font=(UI_FONT, 20, "bold")).pack(side="left")
        if self.training_mode:
            tk.Label(head, text=f"  🎯 تمرین {fa_num(self.training_index + 1)}/{fa_num(len(TRAINING_LEVELS))}",
                     bg="#0b0f14", fg="#f2c66d", font=(UI_FONT, 11, "bold")).pack(side="left", padx=12)
        meta = f"  /  {self.game_mode}"
        if self.spectate:
            meta += f"  /  ♔ {BOT_BY_ID[self.spec_w[0]].fa} در برابر ♚ {BOT_BY_ID[self.spec_b[0]].fa}"
        elif not self.two_player:
            meta += f"  /  {BOT_BY_ID[self.bot_id].fa} • {self._bot_level_label()}"
        meta += f"  /  {self.time_mode}"
        tk.Label(head, text=meta, bg="#0b0f14", fg="#74818d",
                 font=(MONO_FONT, 9, "bold")).pack(side="left", pady=8)
        self.clock_label = tk.Label(head, text="", bg="#0b0f14", fg="#f2c66d",
                                    font=(MONO_FONT, 16, "bold"))
        self.clock_label.pack(side="right")
        self.capture_hud = tk.Label(head, text="", bg="#0b0f14", fg="#d9e0e6",
                                    font=(SYMBOL_FONT, 11, "bold"), anchor="e", justify="right")
        self.capture_hud.pack(side="right", padx=(20, 18))
        tk.Frame(shell, bg="#27323c", height=1).pack(fill="x", pady=(0, 14))

        body = tk.Frame(shell, bg="#0b0f14")
        body.pack(fill="both", expand=True)
        rail = tk.Frame(body, bg="#111820", width=190)
        rail.pack(side="left", fill="y", padx=(0, 14))
        rail.pack_propagate(False)
        tk.Label(rail, text="مسابقه", bg="#111820", fg="#73818d",
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=18, pady=(20, 8))
        self.info = tk.Label(rail, text="", bg="#111820", fg="#e6ebef",
                             font=(UI_FONT, 11, "bold"), justify="left", anchor="w")
        self.info.pack(fill="x", padx=18, pady=5)
        tk.Frame(rail, bg="#27343f", height=1).pack(fill="x", padx=18, pady=14)
        self.status = tk.Label(rail, text="", bg="#111820", fg="#a5b1bc",
                               font=(UI_FONT, 9), wraplength=150, justify="left", anchor="nw")
        self.status.pack(fill="x", padx=18, pady=4)
        tk.Label(rail, text="مهره‌های گرفته‌شده", bg="#111820", fg="#73818d",
                 font=(UI_FONT, 8, "bold")).pack(anchor="w", padx=18, pady=(25, 5))
        self.captured_label = tk.Label(rail, text="—", bg="#111820", fg="#d5dce2",
                                       font=(SYMBOL_FONT, 13), wraplength=150, justify="left")
        self.captured_label.pack(anchor="w", padx=18)
        if self.spectate:
            railbtns = [("⏹  توقف تماشا", self.stop_spectate), ("⌂  میز بازی", self.build_menu)]
        else:
            railbtns = [("↶  واگردانی", self.undo), ("✦  راهنمای حرکت", self.hint_move),
                        ("▤  تحلیل", self.analysis_popup), ("⚙  تنظیمات", self.settings),
                        ("⌂  میز بازی", self.build_menu)]
        for txt, cmd in railbtns:
            tk.Button(rail, text=txt, command=cmd, anchor="w", bg="#111820", fg="#b9c3cc",
                      activebackground="#202c37", activeforeground="#f2c66d", relief="flat", bd=0,
                      font=(UI_FONT, 9, "bold"), padx=18, pady=9, cursor="hand2").pack(fill="x", pady=1)

        board_panel = tk.Frame(body, bg="#111820", highlightbackground="#27343f", highlightthickness=1)
        board_panel.pack(side="left", fill="both", expand=True)
        board_top = tk.Frame(board_panel, bg="#111820")
        board_top.pack(fill="x", padx=16, pady=10)
        board_name = "صفحهٔ شطرنج ولتریکس" if True else ""
        tk.Label(board_top, text=board_name, bg="#111820", fg="#71808d",
                 font=(MONO_FONT, 8, "bold")).pack(side="left")
        tk.Label(board_top, text="● زنده", bg="#111820", fg="#8fcf9b",
                 font=(MONO_FONT, 8, "bold")).pack(side="right")
        self.canvas = tk.Canvas(board_panel, width=680, height=680, bg="#0d1217", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        legend = tk.Label(board_panel, text="🟢 حرکت آزاد   🔴 گرفتن مهره   🟡 آخرین حرکت / کیش",
                          bg="#111820", fg="#aeb9c3", font=(UI_FONT, 9, "bold"))
        legend.pack(pady=(0, 8))
        self.canvas.bind("<Button-1>", self.click_board)
        self.canvas.bind("<Motion>", self.hover_board)
        self.canvas.bind("<Leave>", self.clear_hover)
        self.canvas.bind("<Configure>", lambda e: self.draw_board())

        actions = tk.Frame(shell, bg="#0b0f14")
        actions.pack(fill="x", pady=(12, 0))
        if self.spectate:
            acts = [("تماشای دوباره", lambda: self.start_spectate(self.spec_w, self.spec_b)),
                    ("منو", self.build_menu)]
        else:
            acts = [("ذخیره", self.save_file), ("خروجی حرکات", self.export_pgn),
                    ("قهرمانی", self.championship_popup), ("منو", self.build_menu)]
        for txt, cmd in acts:
            tk.Button(actions, text=txt, command=cmd, bg="#151e26", fg="#9eabb5",
                      activebackground="#222f3a", activeforeground="#f2c66d", relief="flat", bd=0,
                      font=(MONO_FONT, 8, "bold"), padx=18, pady=8, cursor="hand2").pack(side="right", padx=(7, 0))
        self.draw_board()
        self.update_hud()
        self.themeize_buttons()

    def _bot_level_label(self):
        if self.bot_variant:
            return f"مدل {dict((v[0], v[1]) for v in BOT_BY_ID[self.bot_id].variants).get(self.bot_variant, '')}"
        return f"سطح {fa_num(self.level)}/{fa_num(BOT_BY_ID[self.bot_id].levels)}"

    # =================================================== board (VELTRIX design)
    def _board_geometry(self):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        cell = min(w, h, 680) / 8
        ox = (w - cell * 8) / 2
        oy = (h - cell * 8) / 2
        return ox, oy, cell

    def square_at(self, x, y):
        w = max(1, self.canvas.winfo_width())
        h = max(1, self.canvas.winfo_height())
        cell = min(w, h, 680) / 8
        ox = (w - cell * 8) / 2
        oy = (h - cell * 8) / 2
        c = int((x - ox) // cell)
        r = int((y - oy) // cell)
        if not (0 <= r < 8 and 0 <= c < 8):
            return None
        if self.flipped:
            r, c = 7 - r, 7 - c
        return r, c

    def _board_colors(self):
        if self.custom_board_colors:
            return self.custom_light, self.custom_dark
        return BOARD_STYLES.get(self.board_style, BOARD_STYLES[DEFAULT_BOARD_STYLE])

    def _piece_body_line(self, piece):
        body_idx = 0 if piece.isupper() else 1
        body = PIECE_COLORS.get(self.piece_style, PIECE_COLORS["Classic"])[body_idx]
        line = PIECE_LINE_LIGHT if piece.isupper() else PIECE_LINE_DARK
        return body, line

    def draw_piece_art(self, canvas, cx, cy, size, piece, tag="piece"):
        """Veltrix two-tone piece: solid filled glyph + 8 offset outline stamps."""
        fs = max(12, int(size * 0.72))
        body, line = self._piece_body_line(piece)
        d = max(1, int(size * 0.022))
        font = (SYMBOL_FONT, fs)
        glyph = FILLED[piece]
        for dx in (-d, 0, d):
            for dy in (-d, 0, d):
                if dx == 0 and dy == 0:
                    continue
                canvas.create_text(cx + dx, cy + dy, text=glyph, font=font, fill=line, tags=tag)
        canvas.create_text(cx, cy, text=glyph, font=font, fill=body, tags=tag)

    def _veltrix_hl(self, sq, color, ox, oy, cell):
        """Veltrix highlight: 45% blend of the highlight colour with the base."""
        r, c = sq
        light, dark = self._board_colors()
        base = light if (r + c) % 2 == 0 else dark
        blend = ColorTools.mix(base, color, 0.45)
        x0, y0 = self._sq_xy(r, c, ox, oy, cell)
        self.canvas.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=blend,
                                     outline=blend, tags="hl")

    def _sq_xy(self, r, c, ox, oy, cell):
        if self.flipped:
            r, c = 7 - r, 7 - c
        return ox + c * cell, oy + r * cell

    def draw_board(self):
        """Veltrix board design, rendered exactly like gui/board_widget.py."""
        if not hasattr(self, "canvas"):
            return
        c = self.canvas
        c.delete("all")
        w = max(1, c.winfo_width())
        h = max(1, c.winfo_height())
        cell = min(w, h, 680) / 8
        ox, oy = (w - cell * 8) / 2, (h - cell * 8) / 2
        light, dark = self._board_colors()

        legal_targets = {}
        if self.selected is not None:
            active_side = self.g.turn if (self.two_player or self.spectate) else self.player
            if self.training_mode:
                active_side = self.player
            legal_targets = {(m[2], m[3]): m for m in self.g.legal(active_side) if m[0:2] == self.selected}

        # ---- squares (flat, exactly Veltrix)
        for r in range(8):
            for cc in range(8):
                x0, y0 = self._sq_xy(r, cc, ox, oy, cell)
                col = light if (r + cc) % 2 == 0 else dark
                c.create_rectangle(x0, y0, x0 + cell, y0 + cell, fill=col, outline=col, tags="sq")

        # ---- highlights (below pieces), Veltrix colours
        if self.g.last:
            for sq in ((self.g.last[0], self.g.last[1]), (self.g.last[2], self.g.last[3])):
                hl = HL_LAST_LIGHT if (sq[0] + sq[1]) % 2 == 1 else HL_LAST_DARK
                self._veltrix_hl(sq, hl, ox, oy, cell)
        # king square in check -> red blend
        if self.g.game_state() == "check":
            ks = self.g.find_king(self.g.turn)
            if ks:
                self._veltrix_hl(ks, HL_CHECK, ox, oy, cell)
        if self.selected is not None:
            self._veltrix_hl(self.selected, HL_SELECTED, ox, oy, cell)

        # ---- target hints: dot on empty, ring on capture
        for (r, cc), m in legal_targets.items():
            x0, y0 = self._sq_xy(r, cc, ox, oy, cell)
            cx_, cy_ = x0 + cell / 2, y0 + cell / 2
            occupied = self.g.board[r][cc] != "." or m[4] == "ep"
            if occupied:
                c.create_oval(cx_ - cell * 0.46, cy_ - cell * 0.46, cx_ + cell * 0.46, cy_ + cell * 0.46,
                              outline=HL_TARGET_CAPTURE, width=3, tags="hint")
            else:
                c.create_oval(cx_ - cell * 0.16, cy_ - cell * 0.16, cx_ + cell * 0.16, cy_ + cell * 0.16,
                              fill=HL_TARGET_EMPTY, outline="", stipple="gray50", tags="hint")

        # ---- hover ring (app feel, subtle)
        if self.hover_square and not self.animating:
            x0, y0 = self._sq_xy(self.hover_square[0], self.hover_square[1], ox, oy, cell)
            c.create_rectangle(x0 + 3, y0 + 3, x0 + cell - 3, y0 + cell - 3,
                               outline="#fff1a8", width=2, tags="hover")

        # ---- hint marker (gold dot)
        if self.hint:
            x0, y0 = self._sq_xy(self.hint[2], self.hint[3], ox, oy, cell)
            cx_, cy_ = x0 + cell / 2, y0 + cell / 2
            c.create_oval(cx_ - cell * 0.13, cy_ - cell * 0.13, cx_ + cell * 0.13, cy_ + cell * 0.13,
                          fill="#d9a441", outline="#fff0a0", width=2, tags="hintmark")

        # ---- pieces (two-tone Veltrix rendering)
        for r in range(8):
            for cc in range(8):
                p = self.g.board[r][cc]
                if p == ".":
                    continue
                x0, y0 = self._sq_xy(r, cc, ox, oy, cell)
                self.draw_piece_art(c, x0 + cell / 2, y0 + cell / 2 + cell * 0.03, cell, p, "piece")

        # ---- coordinates: rank left, file bottom, contrasting colour
        small = max(8, int(cell // 6))
        for i in range(8):
            # rank label at the left of row i
            file_i = i if not self.flipped else 7 - i
            rank_i = 7 - i if not self.flipped else i
            r, cl = (rank_i, 0) if not self.flipped else (rank_i, 7)
            baseL = light if (r + cl) % 2 == 0 else dark
            label_col = dark if baseL == light else light
            c.create_text(3, i * cell + small + 2, text=str(rank_i + 1),
                          font=("TkDefaultFont", small), fill=label_col, tags="coord", anchor="w")
            # file label at the bottom of column i
            sq_r = 7 if not self.flipped else 0
            baseB = light if (sq_r + file_i) % 2 == 0 else dark
            label_col2 = dark if baseB == light else light
            c.create_text(i * cell + cell - 4, 8 * cell - small - 2, text=FILES[file_i],
                          font=("TkDefaultFont", small), fill=label_col2, tags="coord", anchor="e")

    def hover_board(self, event):
        if not hasattr(self, "canvas") or self.animating:
            return
        sq = self.square_at(event.x, event.y)
        if sq != self.hover_square:
            self.hover_square = sq
            self.draw_board()

    def clear_hover(self, event=None):
        if getattr(self, "hover_square", None) is not None:
            self.hover_square = None
            self.draw_board()

    # ========================================================== animation
    def _screen_center(self, sq):
        r, c = sq
        if self.flipped:
            r, c = 7 - r, 7 - c
        ox, oy, cell = self._board_geometry()
        return ox + c * cell + cell / 2, oy + r * cell + cell / 2

    def _draw_animation_board(self, start, end):
        """Draw the final position but cover the animating squares."""
        self.draw_board()
        if not hasattr(self, "canvas"):
            return
        ox, oy, cell = self._board_geometry()
        light, dark = self._board_colors()
        for sq in (start, end):
            r, c = sq
            col = light if (r + c) % 2 == 0 else dark
            x, y = self._screen_center(sq)
            self.canvas.create_rectangle(x - cell / 2, y - cell / 2, x + cell / 2, y + cell / 2,
                                         fill=col, outline=col, tags="animcover")

    def animate_move(self, start, end, capture=False, callback=None, extra_moves=None):
        """Cinematic Matin animation with Veltrix piece rendering."""
        if not hasattr(self, "canvas") or not getattr(self, "g", None):
            if callback:
                callback()
            return
        self.animating = True
        try:
            moving_piece = self.g.board[end[0]][end[1]]
            self._draw_animation_board(start, end)
            if extra_moves:
                for a, b in extra_moves:
                    self._draw_animation_board(a, b)
            sx, sy = self._screen_center(start)
            ex, ey = self._screen_center(end)
            ox, oy, cell = self._board_geometry()
            self.draw_piece_art(self.canvas, sx, sy, cell * 0.92, moving_piece, "anim")
            ai_anim = getattr(self, "_ai_move_animation", False)
            if self.spectate:
                duration = max(240, min(620, int(self.ai_animation_speed * (0.30 if self.demo_mode else 0.42))))
            else:
                duration = max(700, int(self.ai_animation_speed if ai_anim else self.anim_speed))
            steps = max(42, int(duration / 22))
            delay = max(10, int(duration / steps))

            def ease(t):
                return t * t * (3 - 2 * t)

            def frame(i):
                if not self.animating:
                    return
                t = min(1.0, i / steps)
                e = ease(t)
                lift = math.sin(math.pi * t) * min(18, cell * .11)
                x = sx + (ex - sx) * e
                y = sy + (ey - sy) * e - lift
                self.canvas.delete("anim")
                self.draw_piece_art(self.canvas, x, y, cell * 0.92, moving_piece, "anim")
                if i < steps:
                    self.animation_job = self.root.after(delay, lambda: frame(i + 1))
                    return
                for rad in (12, 22, 34, 46):
                    self.canvas.create_oval(ex - rad, ey - rad, ex + rad, ey + rad,
                                            outline="#ffe49a", width=2, tags="animpulse")
                if capture:
                    self.canvas.create_oval(ex - 34, ey - 34, ex + 34, ey + 34, fill="#c98a3d",
                                            stipple="gray50", outline="#ffe49a", width=2, tags="captureflash")
                self.root.after(120, lambda: (self.canvas.delete("animpulse"), self.canvas.delete("captureflash")))
                self.canvas.delete("anim")
                self._ai_move_animation = False
                if extra_moves:
                    self.root.after(20, lambda: self._animate_rook(extra_moves[0][0], extra_moves[0][1], callback, capture))
                else:
                    self.root.after(45, lambda: self._finish_animation(callback))
            frame(0)
        except Exception:
            self.animating = False
            self.draw_board()
            if callback:
                callback()

    def _animate_rook(self, start, end, callback=None, capture=False):
        if not hasattr(self, "canvas"):
            self._finish_animation(callback)
            return
        self.draw_board()
        ox, oy, cell = self._board_geometry()
        sx, sy = self._screen_center(start)
        ex, ey = self._screen_center(end)
        piece = self.g.board[end[0]][end[1]]
        steps = max(12, int(self.anim_speed / 24))
        delay = max(10, int(self.anim_speed * .72 / steps))

        def f(i):
            t = min(1, i / steps)
            e = t * t * (3 - 2 * t)
            x = sx + (ex - sx) * e
            y = sy + (ey - sy) * e
            self.canvas.delete("rookanim")
            self.draw_piece_art(self.canvas, x, y, cell * 0.92, piece, "rookanim")
            if i < steps:
                self.root.after(delay, lambda: f(i + 1))
            else:
                self.canvas.delete("rookanim")
                self.root.after(50, lambda: self._finish_animation(callback))
        f(0)

    def _finish_animation(self, callback=None):
        self.animating = False
        self.animation_job = None
        self.draw_board()
        self.update_hud()
        if callback:
            callback()

    # ============================================================== clicks
    def click_board(self, event):
        if self.ai_thinking or self.animating or self.game_finished:
            return
        if self.spectate:
            return
        if self.training_mode:
            sq = self.square_at(event.x, event.y)
            if sq:
                self.click_training(sq)
            return
        if (not self.two_player) and self.g.turn != self.player:
            return
        sq = self.square_at(event.x, event.y)
        if not sq:
            return
        r, c = sq
        p = self.g.board[r][c]
        if self.selected is None:
            if p != "." and self.g.color(p) == (self.g.turn if self.two_player else self.player):
                self.selected = sq
                self.audio.play("select")
                self.draw_board()
            return
        moves = [m for m in self.g.legal(self.g.turn if self.two_player else self.player)
                 if m[0:2] == self.selected and m[2:4] == sq]
        if moves:
            promo_moves = [m for m in moves if m[4] in PROMO_FLAGS]
            if promo_moves and not self.spectate:
                self._promotion_picker(promo_moves)
                return
            self.make_move(moves[0])
        elif p != "." and self.g.color(p) == (self.g.turn if self.two_player else self.player):
            self.selected = sq
            self.draw_board()
        else:
            self.audio.play("error")
            self.selected = None
            self.draw_board()

    def _promotion_picker(self, promo_moves):
        """Android-edition feature: choose the promotion piece."""
        win = tk.Toplevel(self.root)
        win.title("تبدیل پیاده")
        win.geometry("420x230")
        win.configure(bg="#101820")
        win.grab_set()
        tk.Label(win, text="تبدیل پیاده", bg="#101820", fg="#f2c66d",
                 font=(UI_FONT, 22, "bold")).pack(pady=(22, 4))
        tk.Label(win, text="مهرهٔ جدید خود را انتخاب کن", bg="#101820", fg="#aab6c0",
                 font=(UI_FONT, 10)).pack(pady=(0, 10))
        row = tk.Frame(win, bg="#101820")
        row.pack(pady=8)
        by_flag = {m[4]: m for m in promo_moves}
        white = self.g.turn == "w"
        for flag, glyph, name in (("pQ", "♕" if white else "♛", "وزیر"),
                                  ("pR", "♖" if white else "♜", "رخ"),
                                  ("pB", "♗" if white else "♝", "فیل"),
                                  ("pN", "♘" if white else "♞", "اسب")):
            m = by_flag.get(flag)
            if m is None:
                continue
            card = tk.Frame(row, bg="#17212a", highlightbackground="#33424e", highlightthickness=1)
            card.pack(side="left", padx=6)
            tk.Label(card, text=glyph, bg="#17212a", fg="#f2c66d",
                     font=(SYMBOL_FONT, 34)).pack(pady=(8, 0))
            tk.Label(card, text=name, bg="#17212a", fg="#eef2f5",
                     font=(UI_FONT, 10, "bold")).pack(pady=(0, 4))
            tk.Button(card, text="انتخاب", command=lambda mm=m: (win.destroy(), self.make_move(mm)),
                      bg="#26333e", fg="#f2c66d", activebackground="#33424e", relief="flat",
                      font=(UI_FONT, 9, "bold"), padx=10, pady=4, cursor="hand2").pack(pady=(0, 8), ipadx=8)

    # =========================================================== training
    def click_training(self, sq):
        """BUGFIX (original): this handler was never bound — training clicks
        fell through to the normal game flow, the target move was never
        checked and the AI even answered inside puzzles.  It is now bound
        whenever training mode is active, and ANY mating move is accepted."""
        legal = self.g.legal(self.player)
        if self.selected is None:
            if self.g.board[sq[0]][sq[1]] != "." and self.g.color(self.g.board[sq[0]][sq[1]]) == self.player:
                self.selected = sq
                self.audio.play("select")
                self.draw_board()
            return
        if sq == self.selected:
            self.selected = None
            self.draw_board()
            return
        candidates = [m for m in legal if m[0:2] == self.selected and m[2:4] == sq]
        if not candidates:
            self.audio.play("error")
            self.status.configure(text="❌ این حرکت قانونی نیست؛ یک حرکت دیگر امتحان کن.")
            return
        m = candidates[0]
        # any move that delivers checkmate solves the puzzle
        snap = self.g.snap()
        self.g._apply_raw(m, record=False)
        is_mate = self.g.game_state() == "checkmate"
        self.g.restore(snap)
        if is_mate:
            self.g.apply(m)
            self.selected = None
            self.draw_board()
            pz = TRAINING_LEVELS[self.training_index]
            self.status.configure(text="✅ " + pz["success"])
            self.audio.play_capture() if self.g.captured else self.audio.play_move()
            self.root.after(700, lambda: self.training_success(m))
        else:
            self.audio.play("error")
            self.selected = None
            self.draw_board()
            self.status.configure(text="❌ هنوز نه! حرکت درست این تمرین چیز دیگری است.")

    def training_success(self, m):
        if not self.training_mode:
            return
        win = tk.Toplevel(self.root)
        win.title("تمرین موفق")
        win.geometry("430x300")
        win.configure(bg="#101820")
        win.grab_set()
        tk.Label(win, text="🎯 عالی بود!", bg="#101820", fg="#f2c66d",
                 font=(UI_FONT, 26, "bold")).pack(pady=28)
        tk.Label(win, text=TRAINING_LEVELS[self.training_index]["success"], bg="#101820",
                 fg="#ffffff", font=(UI_FONT, 12, "bold"), wraplength=360).pack(pady=8)
        self.button(win, "تمرین بعدی →", lambda: (win.destroy(), self.next_training()), big=True).pack(pady=20)
        self.button(win, "بازگشت به تمرین‌ها", lambda: (win.destroy(), self.training_menu())).pack()
        self.themeize_buttons(win)

    # ============================================================= moves
    def make_move(self, m):
        if self.animating:
            return
        cap = self.g.board[m[2]][m[3]] != "." or m[4] == "ep"
        start = (m[0], m[1])
        end = (m[2], m[3])
        moving_before = self.g.board[m[0]][m[1]]
        special = m[4]
        mover = self.g.turn
        before_eval = self.ai.evaluate(self.g)
        t0 = time.perf_counter()
        self.g.apply(m)
        self.performance.add(time.perf_counter() - t0)
        self.stats["moves"] += 1
        after_eval = self.ai.evaluate(self.g)
        delta = (after_eval - before_eval) if mover == "w" else (before_eval - after_eval)
        state_after = self.g.game_state()
        if state_after == "checkmate":
            grade = "عالی"
        elif delta >= 140:
            grade = "عالی"
        elif delta >= 35:
            grade = "خوب"
        elif delta >= -35:
            grade = "معمولی"
        elif delta >= -140:
            grade = "مشکوک"
        else:
            grade = "بد"
        self.move_analysis.append({"ply": len(self.g.moves), "move": self.g.moves[-1],
                                   "side": mover, "delta": delta, "grade": grade})
        if self.db_game_id and not self.spectate:
            self.db.add_event(self.db_game_id, "move", self.g.moves[-1])
        if cap:
            self.stats["captures"] += 1
        self.selected = None
        self.hint = None

        # ---- SOUNDS (spec): every move -> move-self, every capture -> capture
        if cap:
            self.audio.play_capture()
        else:
            self.audio.play_move()
        if special in ("castleK", "castleQ"):
            self.audio.play("castle")
        if moving_before.upper() == "P" and self.g.board[end[0]][end[1]].upper() in ("Q", "R", "B", "N") and special in PROMO_FLAGS:
            self.audio.play("promote")
        if self.g.check(self.g.turn) and state_after != "checkmate":
            self.audio.play("check")

        extra = None
        if special == "castleK":
            row = start[0]
            extra = [((row, 7), (row, 5))]
        elif special == "castleQ":
            row = start[0]
            extra = [((row, 0), (row, 3))]

        def after_animation():
            state = self.g.game_state()
            if state == "checkmate":
                # BUGFIX (original): the winner was inverted — after checkmate
                # g.turn is the side that is mated, so the winner is the other.
                self.finish("b" if self.g.turn == "w" else "w")
            elif state in ("stalemate", "draw50", "draw3", "drawMaterial"):
                self.finish("draw")
            elif self.spectate:
                self.spec_job = self.root.after(self.spec_delay, self._spectate_step)
            elif (not self.two_player) and self.g.turn != self.player:
                self.root.after(self.ai_min_delay, self.ai_move)

        self.animate_move(start, end, cap, after_animation, extra_moves=extra)

    def ai_move(self):
        if (self.ai_thinking or self.game_finished or self.training_mode
                or self.spectate or self.g.game_state() not in ("play", "check")):
            return
        self.ai_thinking = True
        self.status.configure(text="🧠 هوش مصنوعی در حال فکر کردن...")

        def work():
            m = self.ai.best(self.g, self.level, variant=self.bot_variant)
            self.root.after(0, lambda: self.finish_ai(m))
        threading.Thread(target=work, daemon=True).start()

    def finish_ai(self, m):
        self.ai_thinking = False
        if m and not self.game_finished:
            self._ai_move_animation = True
            self.make_move(m)

    def hint_move(self):
        if self.spectate or self.training_mode or self.game_finished:
            return
        if self.g.turn != self.player or self.ai_thinking:
            return
        m = self.ai.best(self.g, self.level, max(.12, self.ai.settings(self.level)[1] * .45),
                         variant=self.bot_variant)
        self.hint = m
        self.audio.play("hint")
        self.draw_board()
        self.status.configure(text="💡 حرکت پیشنهادی با نقطه طلایی مشخص شده است.")

    def undo(self):
        if self.ai_thinking or self.spectate or self.game_finished:
            return
        self.g.undo()
        self.audio.play("undo")
        if (not self.two_player) and self.g.turn != self.player and self.g.history:
            self.g.undo()
        self.selected = None
        self.hint = None
        self.draw_board()
        self.update_hud()

    def score(self):
        s = {"w": 0, "b": 0}
        for p in self.g.captured:
            s["b" if p.isupper() else "w"] += VALUE[p.upper()] // 100
        return s

    # ================================================================ HUD
    def update_hud(self):
        if not hasattr(self, "info"):
            return
        s = self.score()
        pieces = " ".join(UNICODE[p] for p in self.g.captured[-16:]) or "—"
        if self.spectate:
            wname, bname = BOT_BY_ID[self.spec_w[0]], BOT_BY_ID[self.spec_b[0]]
            who_line = (f"♔ {wname.fa} ({fa_num(self.spec_w[1])})\n"
                        f"♚ {bname.fa} ({fa_num(self.spec_b[1])})\n")
            nodes = (self.spec_engine_w.nodes if self.g.turn == "w" else self.spec_engine_b.nodes)
            depth = (self.spec_engine_w.depth_reached if self.g.turn == "w" else self.spec_engine_b.depth_reached)
        elif self.two_player:
            who_line = f"حالت: {self.game_mode}\n"
            nodes = depth = 0
        else:
            who_line = f"شما: {'سفید' if self.player == 'w' else 'سیاه'}\nربات: {BOT_BY_ID[self.bot_id].fa}\n"
            nodes, depth = self.ai.nodes, self.ai.depth_reached
        level_line = self._bot_level_label() if not self.two_player else "—"
        self.info.configure(text=f"{level_line}\n" + who_line +
                            f"نوبت: {'سفید' if self.g.turn == 'w' else 'سیاه'}\n"
                            f"حرکت‌ها: {fa_num(len(self.g.moves))}   گره‌های AI: {fa_num(nodes)}\n"
                            f"عمق جست‌وجو: {fa_num(depth)}")
        self.captured_label.configure(text=f"گرفته‌شده: {pieces}\n"
                                     f"امتیاز سفید: {fa_num(s['w'])}   |   سیاه: {fa_num(s['b'])}")
        if hasattr(self, "capture_hud"):
            white_lost = " ".join(UNICODE[p] for p in self.g.captured if p.isupper()) or "—"
            black_lost = " ".join(UNICODE[p] for p in self.g.captured if p.islower()) or "—"
            self.capture_hud.configure(text=f"♔ سفید  {white_lost}  •  -{fa_num(s['w'])}     |     سیاه  {black_lost}  •  -{fa_num(s['b'])} ♚")
        st = self.g.game_state()
        msg = {"play": "نوبت بازی.", "check": "⚠ کیش!", "checkmate": "♛ کیش‌ومات!",
               "stalemate": "مساوی! پات.", "draw50": "مساوی با قانون ۵۰ حرکت",
               "draw3": "مساوی با تکرار سه‌باره",
               "drawMaterial": "مساوی — مهرهٔ کافی برای مات وجود ندارد"}.get(st, "")
        if self.training_mode:
            msg = f"🎯 تمرین {fa_num(self.training_index + 1)}: {TRAINING_LEVELS[self.training_index]['goal']}"
        if self.game_finished:
            msg = "پایان بازی — برای بازی جدید به منو برو."
        self.status.configure(text=msg)

    def tick_clock(self):
        if not hasattr(self, "clock_label") or not self.clock_label.winfo_exists():
            return
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        if self.time_mode != "∞" and self.clock[self.g.turn] is not None:
            self.clock[self.g.turn] = max(0, self.clock[self.g.turn] - dt)
            if self.clock[self.g.turn] <= 0:
                self.finish("timeout")
                return

            def fmt(x):
                x = int(max(0, x))
                return f"{x // 60:02d}:{x % 60:02d}"
            self.clock_label.configure(text=f"⏱ سفید {fmt(self.clock['w'])}   |   سیاه {fmt(self.clock['b'])}")
        else:
            self.clock_label.configure(text="⏱ زمان: نامحدود")
        self.clock_job = self.root.after(250, self.tick_clock)

    # ============================================================== finish
    def achievement_popup(self, text):
        win = tk.Toplevel(self.root)
        win.title("دستاورد جدید")
        win.geometry("500x290")
        win.configure(bg="#111820")
        win.grab_set()
        tk.Label(win, text="🏆", bg="#111820", fg="#f2c66d", font=(SYMBOL_FONT, 58)).pack(pady=(18, 0))
        tk.Label(win, text="دستاورد جدید!", bg="#111820", fg="#ffffff",
                 font=(UI_FONT, 22, "bold")).pack(pady=2)
        tk.Label(win, text=text, bg="#111820", fg="#f2c66d",
                 font=(UI_FONT, 14, "bold"), wraplength=420).pack(pady=12)
        tk.Label(win, text=f"بازی‌ها: {fa_num(self.stats.get('games', 0))}   •   مات‌ها: {fa_num(self.stats.get('checkmates', 0))}",
                 bg="#111820", fg="#9ba8b5", font=(UI_FONT, 10)).pack()
        self.button(win, "عالی! ✓", win.destroy, big=True).pack(pady=18)
        self.audio.play("win")

    def finish(self, winner):
        self.ai_thinking = False
        self.game_finished = True       # finished games can never be resumed
        if self.spectate:
            return
        milestone = None
        was_checkmate = (winner not in ("draw", "timeout")) and self.g.game_state() == "checkmate"
        if winner == "draw":
            self.stats["draws"] += 1
            msg = "مساوی شد."
        elif winner == "timeout":
            loser = self.g.turn
            win_side = "b" if loser == "w" else "w"
            if self.two_player:
                self.stats["wins"] += 1
            elif win_side == self.player:
                self.stats["wins"] += 1
            else:
                self.stats["losses"] += 1
            msg = "⏰ زمان تمام شد!"
        else:
            if self.two_player:
                self.stats["wins"] += 1
                msg = f"🏆 {'سفید' if winner == 'w' else 'سیاه'} برنده شد!"
            elif winner != self.player:
                self.stats["losses"] += 1
            else:
                self.stats["wins"] += 1
                self.unlocked = max(self.unlocked, min(20, self.level + 1))
            # BUGFIX (original): said "بازیکن" (the player) when the AI won
            if not self.two_player:
                msg = "🏆 شما بردید!" if winner == self.player else "🤖 هوش مصنوعی برنده شد!"
        if was_checkmate and not self.two_player and winner == self.player:
            self.stats["checkmates"] = self.stats.get("checkmates", 0) + 1
        if winner == self.player and winner not in ("draw", "timeout"):
            self.stats["current_streak"] = self.stats.get("current_streak", 0) + 1
            self.stats["best_streak"] = max(self.stats.get("best_streak", 0), self.stats["current_streak"])
            self.tournament.record_win()
        elif winner not in ("draw",):
            if not self.two_player:
                self.stats["current_streak"] = 0
                self.tournament.record_loss()
        gcount = self.stats.get("games", 0)
        cm = self.stats.get("checkmates", 0)
        milestones = {1: "🎉 اولین بازیتو تموم کردی!", 10: "🔥 دهمین بازیت مبارک!",
                      25: "🏅 بیست‌وپنجمین بازیت مبارک!", 50: "🚀 پنجاهمین بازیت مبارک!",
                      100: "👑 صدمین بازیت مبارک!", 250: "💎 ۲۵۰ بازی! تو دیگه حرفه‌ای شدی!",
                      500: "🌟 ۵۰۰ بازی MATIN CHESS!"}
        cm_milestones = {1: "🎯 اولین ماتت مبارک!", 2: "🔥 دومین ماتت مبارک!",
                         5: "🏆 پنجمین ماتت مبارک!", 10: "👑 دهمین ماتت مبارک!",
                         25: "💎 ۲۵ مات!", 50: "🌟 ۵۰ مات!"}
        milestone = cm_milestones.get(cm) or milestones.get(gcount)
        self.save_settings()
        self.audio.play("finish" if winner != "timeout" else "timeout")
        self.audio.victory()
        if milestone:
            self.root.after(180, lambda msg=milestone: self.achievement_popup(msg))
        self.root.after(450, self.endgame_analysis_popup)
        if winner == self.player:
            self.audio.play("promote")
            win = tk.Toplevel(self.root)
            win.title("🏆 قهرمان")
            win.geometry("560x430")
            win.configure(bg="#120e08")
            win.grab_set()
            tk.Label(win, text="🏆", font=(SYMBOL_FONT, 88), bg="#120e08", fg="#ffd76a").pack(pady=12)
            tk.Label(win, text="جام قهرمانی", font=(UI_FONT, 28, "bold"), bg="#120e08", fg="#ffd76a").pack()
            tk.Label(win, text="جام قهرمانی برای شما!", font=(UI_FONT, 18, "bold"),
                     bg="#120e08", fg="#fff3cf").pack(pady=8)
            tk.Label(win, text=f"سازندگان: {CREATORS_FA}", font=(UI_FONT, 11),
                     bg="#120e08", fg="#d9c68a").pack(pady=8)
            self.root.after(80, lambda: Trophy(self.root, win).celebrate("🏆 جام قهرمانی"))
            self.button(win, "ادامه", lambda: (win.destroy(), self.build_menu())).pack(pady=22)
        else:
            messagebox.showinfo("پایان بازی", msg)
            self.build_menu()

    def toggle_fullscreen(self):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    def exit_fullscreen(self):
        self.root.attributes("-fullscreen", False)

    # ============================================================== popups
    def championship_popup(self):
        win = tk.Toplevel(self.root)
        win.title("🏆 قهرمانی MATIN CHESS")
        win.geometry("600x500")
        win.configure(bg="#100d08")
        tk.Label(win, text="🏆", font=(SYMBOL_FONT, 88), bg="#100d08", fg="#ffd76a").pack(pady=5)
        tk.Label(win, text="MATIN CHESS CHAMPIONSHIP", font=(UI_FONT, 22, "bold"),
                 bg="#100d08", fg="#ffd76a").pack()
        tk.Label(win, text=f"Rank: {self.tournament.rank()}", font=(UI_FONT, 15, "bold"),
                 bg="#100d08", fg="#fff4d6").pack(pady=12)
        tk.Label(win, text=f"Points: {self.tournament.points}   •   Win Streak: {self.tournament.streak}",
                 font=(UI_FONT, 12), bg="#100d08", fg="#d9c68a").pack()
        tk.Label(win, text="Trophies: " + (", ".join(map(str, self.tournament.trophies)) if self.tournament.trophies else "—"),
                 bg="#100d08", fg="#fff4d6", font=(UI_FONT, 12)).pack(pady=15)
        tk.Label(win, text=f"سازندگان: {CREATORS_FA}", bg="#100d08", fg="#d9c68a",
                 font=(UI_FONT, 11)).pack(pady=8)
        self.button(win, "بستن", win.destroy).pack(pady=18)

    def endgame_analysis_popup(self):
        if not self.g.moves and not self.move_analysis:
            return
        counts = {k: 0 for k in ("عالی", "خوب", "معمولی", "مشکوک", "بد")}
        for x in self.move_analysis:
            counts[x["grade"]] = counts.get(x["grade"], 0) + 1
        lines = []
        for x in self.move_analysis[-24:]:
            lines.append(f"{x['ply']:>2}. {'سفید' if x['side'] == 'w' else 'سیاه'}  {x['move']}  →  {x['grade']}  ({x['delta']:+.0f})")
        summary = (f"عالی: {counts['عالی']}   خوب: {counts['خوب']}   معمولی: {counts['معمولی']}\n"
                   f"مشکوک: {counts['مشکوک']}   بد: {counts['بد']}\n\n" + "\n".join(lines))
        win = tk.Toplevel(self.root)
        win.title("تحلیل پایان بازی")
        win.geometry("700x620")
        win.configure(bg="#101820")
        tk.Label(win, text="📊 تحلیل پایان بازی", bg="#101820", fg="#f2c66d",
                 font=(UI_FONT, 25, "bold")).pack(pady=(22, 8))
        tk.Label(win, text="حرکت‌ها بر اساس تغییر ارزیابی موتور دسته‌بندی شده‌اند.",
                 bg="#101820", fg="#aab6c0", font=(UI_FONT, 10)).pack(pady=(0, 10))
        box = tk.Text(win, bg="#17212a", fg="#eef2f5", insertbackground="#ffffff",
                      font=(MONO_FONT, 11), relief="flat", bd=0)
        box.pack(fill="both", expand=True, padx=24, pady=12)
        box.insert("1.0", summary)
        box.configure(state="disabled")
        self.button(win, "بستن", win.destroy, big=True).pack(pady=16)

    def analysis_popup(self):
        a = ChessAnalytics.material(self.g)
        m = ChessAnalytics.mobility(self.g)
        dbs = self.db.summary()
        text = (f"POSITION تحلیل\n\nارزش مهره‌های سفید: {a['white']}\nارزش مهره‌های سیاه: {a['black']}\n"
                f"Difference: {a['difference']}\n\nحرکت‌های قانونی سفید: {m['white']}\nحرکت‌های قانونی سیاه: {m['black']}\n"
                f"گره‌های هوش مصنوعی: {self.ai.nodes}   •   جست‌وجوی تاکتیکی: {self.ai.qnodes}\n"
                f"زمان آخرین فکر: {self.ai.last_time:.3f}s\nمیانگین زمان پردازش حرکت: {self.performance.average():.5f}s\n"
                f"Device: {DeviceInfo.text()}\nبازی‌های ثبت‌شده: {dbs.get('games', 0)}\n"
                f"W/L/D: {dbs.get('wins', 0)}/{dbs.get('losses', 0)}/{dbs.get('draws', 0)}\n"
                f"شناسه وضعیت: {ChessAnalytics.position_hash(self.g)}\n\nدسته‌بندی حرکات: "
                + " | ".join(f"{k}: {sum(1 for x in self.move_analysis if x['grade'] == k)}"
                            for k in ("عالی", "خوب", "معمولی", "مشکوک", "بد")))
        messagebox.showinfo("📊 Galaxy Analysis", text)

    def statistics(self):
        total = self.stats["games"]
        rate = (self.stats["wins"] / total * 100) if total else 0
        msg = (f"بازی‌ها: {fa_num(total)}\nبرد: {fa_num(self.stats['wins'])}\n"
               f"باخت: {fa_num(self.stats['losses'])}\nمساوی: {fa_num(self.stats['draws'])}\n"
               f"نرخ برد: {rate:.1f}%\nحرکت‌ها: {fa_num(self.stats['moves'])}\n"
               f"گرفتن مهره: {fa_num(self.stats['captures'])}\n"
               f"رتبهٔ تورنمنت: {self.tournament.rank()}")
        messagebox.showinfo("📊 آمار", msg)

    def help(self):
        messagebox.showinfo("راهنما",
            "• برای حرکت روی مهره و سپس خانه مقصد کلیک کن.\n"
            "• در تبدیل پیاده، مهرهٔ جدید را از پنجره انتخاب کن.\n"
            "• «بازی با هوش مصنوعی» ۷ ربات با نردبان سطح دارد؛ متین ۲۰ سطح، ولتریکس ۸ سطح + ۳ مدل.\n"
            "• «مشاهده بازی هوش مصنوعی» دو ربات را به هم می‌اندازد و تماشا می‌کنی.\n"
            "• Hint بهترین حرکت فعلی را با نقطه طلایی نشان می‌دهد.\n"
            "• Undo یک یا چند حرکت را برمی‌گرداند.\n"
            "• Save/Load بازی را در JSON/MCGX نگه می‌دارد.\n"
            "• F11 تمام‌صفحه است؛ Ctrl+Z واگردانی، Ctrl+H راهنما، Ctrl+S ذخیرهٔ سریع.\n"
            "• در مراحل زمانی، ساعت واقعی فعال است.\n"
            "• صدای حرکت و گرفتن مهره واقعی است (move-self / capture).")

    def about(self):
        messagebox.showinfo("درباره",
            "MATIN CHESS\n"
            f"نسخهٔ {APP_VERSION} — نسخهٔ دسکتاپ ارتقایافته\n\n"
            "هوش مصنوعی چندرباتی • مشاهدهٔ ربات در برابر ربات • تبدیل پیادهٔ واقعی\n"
            "قوانین کامل شطرنج • زمان‌سنج • صدا • آمار • ذخیره/بارگذاری\n"
            "طراحی صفحهٔ شطرنج از پروژهٔ Veltrix\n\n"
            f"سازندگان: {CREATORS_FA}\n{CREATORS_EN}")

    # ========================================================= save / load
    def quick_save(self):
        if self.game_finished or self.spectate:      # finished games never resume
            return
        try:
            SaveVault.write(str(self.session_file), self.serial())
            if hasattr(self, "status") and self.status.winfo_exists():
                self.status.configure(text="💾 بازی در فضای امن ذخیره شد.")
        except Exception as e:
            self.logger.error(f"quick save: {e}")

    def autosave_tick(self):
        try:
            if hasattr(self, "g") and self.g.moves and not self.game_finished and not self.spectate:
                SaveVault.write(str(self.session_file), self.serial())
        except Exception as e:
            self.logger.error(f"autosave: {e}")
        try:
            self.autosave_job = self.root.after(8000, self.autosave_tick)
        except Exception:
            self.autosave_job = None

    def serial(self):
        return {"game": self.g.snap(), "level": self.level, "player": self.player,
                "bot_id": self.bot_id, "bot_variant": self.bot_variant,
                "time_mode": self.time_mode, "clock": self.clock, "theme": self.theme,
                "language": self.language, "board_style": self.board_style,
                "custom_light": self.custom_light, "custom_dark": self.custom_dark,
                "custom_board_colors": self.custom_board_colors, "piece_style": self.piece_style,
                "stats": self.stats, "unlocked": self.unlocked, "anim_speed": self.anim_speed}

    def _apply_loaded(self, d):
        self.level = int(d.get("level", 1) or 1)
        self.player = d.get("player", "w")
        self.bot_id = d.get("bot_id", "matin")
        self.bot_variant = d.get("bot_variant")
        if self.bot_id not in BOT_BY_ID:
            self.bot_id = "matin"
        self.ai = ChessAI(self.bot_id)
        self.time_mode = d.get("time_mode", "∞")
        self.clock = d.get("clock", {"w": None, "b": None})
        self.theme = d.get("theme", "Galaxy") if d.get("theme", "Galaxy") in THEMES else "Galaxy"
        self.language = d.get("language", "فارسی")
        bs = d.get("board_style", DEFAULT_BOARD_STYLE)
        self.board_style = bs if bs in BOARD_STYLES else DEFAULT_BOARD_STYLE
        self.custom_light = d.get("custom_light", self.custom_light)
        self.custom_dark = d.get("custom_dark", self.custom_dark)
        self.custom_board_colors = bool(d.get("custom_board_colors", False))
        ps = d.get("piece_style", "Classic")
        self.piece_style = ps if ps in PIECE_COLORS else "Classic"
        self.stats = d.get("stats", self.stats)
        self.unlocked = d.get("unlocked", 1)
        self.anim_speed = d.get("anim_speed", 520)
        self.two_player = False
        self.spectate = False
        self.game_mode = "هوش مصنوعی"
        self.game_finished = False
        self.g = ChessGame()
        self.g.restore(d["game"])
        self.build_game()
        self.tick_clock()
        if (not self.two_player) and self.g.turn != self.player:
            self.root.after(self.ai_min_delay, self.ai_move)

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("Matin Chess Save", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.serial(), f, ensure_ascii=False, indent=2)
            messagebox.showinfo("ذخیره", "بازی ذخیره شد.")
        except Exception as e:
            messagebox.showerror("خطا", str(e))

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Matin Chess Save", "*.json")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self._apply_loaded(d)
        except Exception as e:
            messagebox.showerror("بارگذاری ناموفق", str(e))

    def save_compressed(self):
        path = filedialog.asksaveasfilename(defaultextension=".mcgx",
                                            filetypes=[("Matin Galaxy Save", "*.mcgx")])
        if not path:
            return
        try:
            SaveVault.write(path, self.serial())
            messagebox.showinfo("ذخیره", "سیو فشرده MCGX ذخیره شد.")
        except Exception as e:
            messagebox.showerror("خطا", str(e))

    def load_compressed(self):
        path = filedialog.askopenfilename(filetypes=[("Matin Galaxy Save", "*.mcgx")])
        if not path:
            return
        try:
            d = SaveVault.read(path)
            self._apply_loaded(d)
        except Exception as e:
            messagebox.showerror("خطای بارگذاری", str(e))

    def save_load(self):
        self.clear()
        bg, panel, fg, accent, _ = self.colors()
        tk.Label(self.root, text="ذخیره و بارگذاری", bg=bg, fg=accent,
                 font=(UI_FONT, 27, "bold")).pack(pady=55)
        self.button(self.root, "💾 ذخیره بازی JSON", self.save_file, big=True).pack(pady=8)
        self.button(self.root, "🗜 ذخیره فشرده MCGX", self.save_compressed, big=True).pack(pady=8)
        self.button(self.root, "📂 بارگذاری JSON", self.load_file, big=True).pack(pady=8)
        self.button(self.root, "🗜 بارگذاری MCGX", self.load_compressed, big=True).pack(pady=8)
        self.button(self.root, "← بازگشت", self.build_menu).pack(pady=35)
        self.themeize_buttons()

    def export_pgn(self):
        path = filedialog.asksaveasfilename(defaultextension=".pgn",
                                            filetypes=[("Chess PGN", "*.pgn"), ("Text", "*.txt")])
        if not path:
            return
        PGNExporter.export(self.g, path, {"Event": "Matin Chess Galaxy X",
                                          "Level": self.level, "Bot": BOT_BY_ID[self.bot_id].latin,
                                          "Creator": CREATORS_EN,
                                          "Date": __import__("datetime").date.today().isoformat()})
        messagebox.showinfo("Export", "لیست حرکت‌ها ذخیره شد.")

    # ==================================================== settings / themes
    def settings(self):
        win = tk.Toplevel(self.root)
        win.title("تنظیمات MATIN CHESS • Ultimate")
        win.geometry("540x620")
        win.configure(bg=self.colors()[0])
        tk.Label(win, text="⚙ تنظیمات", bg=self.colors()[0], fg=self.colors()[3],
                 font=(UI_FONT, 25, "bold")).pack(pady=22)
        sound = tk.BooleanVar(value=self.sound)
        music = tk.BooleanVar(value=self.music)
        hints = tk.BooleanVar(value=self.hints)
        anim = tk.StringVar(value=str(self.anim_speed))
        ttk.Checkbutton(win, text="🔊 صدای حرکت و گرفتن (move-self / capture)", variable=sound).pack(pady=8)
        ttk.Checkbutton(win, text="🎵 موسیقی پس‌زمینه", variable=music).pack(pady=8)
        ttk.Checkbutton(win, text="💡 راهنمای حرکت", variable=hints).pack(pady=8)
        tk.Label(win, text="🎬 سرعت انیمیشن", bg=self.colors()[0], fg=self.colors()[2]).pack(pady=(18, 4))
        ttk.Combobox(win, textvariable=anim, values=["260", "380", "520", "700", "900"], state="readonly").pack()

        tk.Label(win, text="طرح صفحهٔ شطرنج (طراحی ولتریکس)", bg=self.colors()[0],
                 fg=self.colors()[2]).pack(pady=(20, 4))
        bs = tk.StringVar(value=self.board_style)
        ttk.Combobox(win, textvariable=bs, values=list(BOARD_STYLES), state="readonly").pack()

        tk.Label(win, text="رنگ دستی خانه‌های صفحه", bg=self.colors()[0], fg=self.colors()[3],
                 font=(UI_FONT, 10, "bold")).pack(pady=(14, 4))
        color_row = tk.Frame(win, bg=self.colors()[0])
        color_row.pack()
        lightv = tk.StringVar(value=self.custom_light)
        darkv = tk.StringVar(value=self.custom_dark)
        preview = tk.Canvas(win, width=240, height=60, bg="#111820", highlightthickness=0)
        preview.pack(pady=8)

        def refresh_preview(*_):
            preview.delete("all")
            colors = [lightv.get(), darkv.get(), darkv.get(), lightv.get()]
            for i, col in enumerate(colors):
                x = (i % 4) * 60
                preview.create_rectangle(x, 0, x + 60, 60, fill=col, outline="")

        def pick(v, btn):
            chosen = colorchooser.askcolor(color=v.get(), title="انتخاب رنگ خانه")
            if chosen and chosen[1]:
                v.set(chosen[1])
                btn.configure(bg=chosen[1])
                refresh_preview()
                self.custom_board_colors = True

        def style_changed(*_):
            if bs.get() in BOARD_STYLES:
                a, b = BOARD_STYLES[bs.get()]
                lightv.set(a)
                darkv.set(b)
                self.custom_board_colors = False
                for child, val in zip(color_row.winfo_children(), (a, b)):
                    child.configure(bg=val)
                refresh_preview()
        bs.trace_add("write", style_changed)

        for label, v in (("روشن", lightv), ("تیره", darkv)):
            btn = tk.Button(color_row, text=label, command=lambda vv=v: None, bg=v.get(),
                            fg="#111", relief="raised", bd=1, width=9, cursor="hand2")
            btn.configure(command=lambda vv=v, bb=btn: pick(vv, bb))
            btn.pack(side="left", padx=3)
        refresh_preview()

        tk.Label(win, text="سبک مهره‌ها", bg=self.colors()[0], fg=self.colors()[2]).pack(pady=(18, 4))
        ps = tk.StringVar(value=self.piece_style)
        ttk.Combobox(win, textvariable=ps, values=list(PIECE_COLORS), state="readonly").pack()
        tk.Label(win, text="تم رابط", bg=self.colors()[0], fg=self.colors()[2]).pack(pady=(18, 4))
        th = tk.StringVar(value=self.theme)
        ttk.Combobox(win, textvariable=th, values=list(THEMES), state="readonly").pack()

        def apply():
            self.sound = sound.get()
            self.music = music.get()
            self.hints = hints.get()
            try:
                self.anim_speed = int(anim.get())
            except Exception:
                self.anim_speed = 760
            self.board_style = bs.get()
            self.custom_light = lightv.get()
            self.custom_dark = darkv.get()
            self.piece_style = ps.get()
            self.theme = th.get()
            self.audio.enabled = self.sound
            self.audio.music_enabled = self.music
            if self.music:
                self.audio.start_music()
            else:
                self.audio.stop_music()
            self.save_settings()
            win.destroy()
            if hasattr(self, "canvas"):
                self.draw_board()
                self.update_hud()
            else:
                self.build_menu()
        self.button(win, "✓ اعمال تنظیمات", apply, big=True).pack(pady=18)
        self.button(win, "🧪 آزمون سلامت بازی", self.internal_self_check).pack(pady=6)

    def themes(self):
        win = tk.Toplevel(self.root)
        win.title("ظاهر و تم • MATIN CHESS")
        win.geometry("860x760")
        bg, panel, fg, accent, _ = self.colors()
        win.configure(bg=bg)
        tk.Label(win, text="🎨 ظاهر و تم", bg=bg, fg=accent,
                 font=(UI_FONT, 26, "bold")).pack(pady=(20, 3))
        tk.Label(win, text="اول طرح صفحهٔ شطرنج (ولتریکس) را انتخاب کن؛ همان لحظه اعمال می‌شود.",
                 bg=bg, fg=fg, font=(UI_FONT, 10)).pack()
        outer = tk.Frame(win, bg=bg)
        outer.pack(fill="both", expand=True, padx=22, pady=5)
        board_box = tk.LabelFrame(outer, text="  طرح آمادهٔ صفحه (ولتریکس)  ", bg=bg, fg=accent,
                                  font=(UI_FONT, 11, "bold"), bd=1, relief="groove")
        board_box.pack(fill="both", expand=True)
        grid = tk.Frame(board_box, bg=bg)
        grid.pack(fill="both", expand=True, padx=10, pady=8)
        for i, (name, vals) in enumerate(BOARD_STYLES.items()):
            card = tk.Frame(grid, bg=panel,
                            highlightbackground=(accent if name == self.board_style else "#2d3a46"),
                            highlightthickness=2)
            card.grid(row=i // 4, column=i % 4, padx=6, pady=6, sticky="nsew")
            mini = tk.Canvas(card, width=150, height=80, bg=vals[0], highlightthickness=0, cursor="hand2")
            mini.pack(pady=(7, 4))
            for rr in range(4):
                for cc in range(4):
                    mini.create_rectangle(cc * 20, rr * 20, cc * 20 + 20, rr * 20 + 20,
                                          fill=vals[0] if (rr + cc) % 2 == 0 else vals[1], outline="")
            tk.Label(card, text=name, bg=panel, fg=fg, font=(UI_FONT, 9, "bold")).pack()
            b = self.button(card, "انتخاب", lambda n=name: self.apply_board_style(n))
            b.configure(font=(UI_FONT, 8, "bold"), padx=9, pady=5)
            b.pack(pady=(3, 7))
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1)
        for r in range(2):
            grid.grid_rowconfigure(r, weight=1)
        manual = tk.Frame(win, bg=bg)
        manual.pack(fill="x", padx=25, pady=7)
        self.button(manual, "🖌 رنگ دستی خانه‌ها", self.settings).pack(side="left")
        self.button(manual, "← بستن", win.destroy).pack(side="right")
        tk.Label(win, text="تم رابط بازی", bg=bg, fg=accent,
                 font=(UI_FONT, 11, "bold")).pack(pady=(5, 4))
        row = tk.Frame(win, bg=bg)
        row.pack(pady=(0, 12))
        for n in THEMES:
            self.button(row, n, lambda x=n: self.apply_theme(x)).pack(side="left", padx=2)
        self.themeize_buttons(win)

    def apply_board_style(self, name):
        if name not in BOARD_STYLES:
            return
        a, b = BOARD_STYLES[name]
        self.board_style = name
        self.custom_light, self.custom_dark = a, b
        self.custom_board_colors = False
        self.save_settings()
        if hasattr(self, "canvas"):
            self.draw_board()
        self.audio.play("button")

    def apply_theme(self, name):
        self.theme = name
        self.save_settings()
        self.build_menu()

    # ==================================================== persistent settings
    def load_settings(self):
        try:
            if self.settings_file.exists():
                with open(self.settings_file, encoding="utf-8") as f:
                    d = json.load(f)
                for k in ("theme", "language", "board_style", "custom_light", "custom_dark",
                          "custom_board_colors", "piece_style", "unlocked", "sound", "music",
                          "hints", "anim_speed", "bot_id", "level"):
                    if k in d:
                        setattr(self, k, d[k])
                if self.board_style not in BOARD_STYLES:
                    self.board_style = DEFAULT_BOARD_STYLE
                if self.bot_id not in BOT_BY_ID:
                    self.bot_id = "matin"
                self.audio.enabled = self.sound
                self.audio.music_enabled = self.music
        except Exception:
            pass

    def save_settings(self):
        try:
            d = {k: getattr(self, k) for k in ("theme", "language", "board_style", "custom_light",
                                               "custom_dark", "custom_board_colors", "piece_style",
                                               "unlocked", "sound", "music", "hints", "anim_speed",
                                               "bot_id", "level")}
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def internal_self_check(self):
        checks = []
        try:
            g = ChessGame()
            checks.append((len(g.legal("w")) == 20, "۲۰ حرکت قانونی در شروع"))
            checks.append((g.game_state() in ("play", "check"), "وضعیت شروع"))
            checks.append((all(len(g.legal(s)) > 0 for s in ("w",)), "موتور حرکت‌های قانونی"))
            checks.append((ChessAI("matin").best(g, 3, .25) is not None, "حرکت قانونی هوش مصنوعی"))
            checks.append((len(BOTS) == 7, "۷ ربات نبرد"))
            checks.append((BOT_BY_ID["matin"].levels == 20, "متین بات = ۲۰ سطح"))
            checks.append((BOT_BY_ID["veltrix"].levels == 8 and len(BOT_BY_ID["veltrix"].variants) == 3,
                           "ولتریکس = ۸ سطح + ۳ مدل"))
            checks.append((self.audio.real_sound_available("move") and self.audio.real_sound_available("capture"),
                           "صداهای واقعی حرکت/گرفتن"))
            checks.append((len(BOARD_STYLES) == 8, "۸ طرح صفحهٔ ولتریکس"))
            checks.append((len(PIECE_COLORS) >= 4, "سبک‌های مهره"))
            ok = sum(1 for x, _ in checks if x)
            messagebox.showinfo("آزمون سلامت بازی",
                                f"نتیجه: {ok}/{len(checks)}\n\n" +
                                "\n".join(("✓ " if x else "✗ ") + n for x, n in checks))
        except Exception as e:
            messagebox.showerror("آزمون سلامت بازی", f"خطا در آزمون:\n{e}")

    # ========================================================= update check
    def check_for_updates_async(self):
        if self._update_checked:
            return
        self._update_checked = True

        def work():
            try:
                import urllib.request
                url = f"https://api.github.com/repos/{APP_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"User-Agent": "MatinChess-Desktop"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                latest = (data.get("tag_name") or "").lstrip("v")
                if latest and latest != APP_VERSION:

                    def _tuple(v):
                        parts = []
                        for x in v.split("."):
                            parts.append(int(x) if x.isdigit() else 0)
                        while len(parts) < 3:
                            parts.append(0)
                        return tuple(parts[:3])
                    if _tuple(latest) > _tuple(APP_VERSION):
                        link = data.get("html_url") or f"https://github.com/{APP_REPO}/releases/latest"
                        self._update_info = (latest, link)
                        try:
                            self.root.after(0, lambda: self._refresh_update_banner())
                        except Exception:
                            pass
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _refresh_update_banner(self):
        # only rebuild the menu if we are currently showing it
        try:
            if not self.root.winfo_exists():
                return
            kids = self.root.winfo_children()
            if kids and isinstance(kids[0], tk.Frame):
                # crude but safe: rebuild menu only when no game canvas exists
                if not hasattr(self, "canvas") or not self.canvas.winfo_exists():
                    self.build_menu()
        except Exception:
            pass

    # ================================================================ demo
    def _demo_tour(self):
        """Scripted tour for the gameplay video (``--demo``)."""
        try:
            self.root.after(2600, self._demo_bots)
        except Exception:
            pass

    def _demo_bots(self):
        self.bots_screen()
        self.root.after(2400, self._demo_levels)

    def _demo_levels(self):
        self.bot_levels(BOT_BY_ID["veltrix"])
        self.root.after(2200, self._demo_spectate)

    def _demo_spectate(self):
        self.spec_delay = 150
        self.start_spectate(("veltrix", 8, "high"), ("garbochess", 1, None))
        self.root.after(1000, lambda: self._demo_watch_end(0))
    def _demo_watch_end(self, elapsed=0):
        if not self.root.winfo_exists():
            return
        if self.game_finished or elapsed > 240:
            self.root.after(5000, self._demo_quit)
            return
        self.root.after(1000, lambda: self._demo_watch_end(elapsed + 1))

    def _demo_quit(self):
        try:
            self.close()
        except Exception:
            try:
                self.root.destroy()
            except Exception:
                pass
        # the recorder waits for process exit; make it deterministic
        import os as _os
        try:
            _os._exit(0)
        except Exception:
            pass

    # ================================================================ close
    def close(self):
        try:
            self.quick_save()
        except Exception:
            pass
        for job in ("autosave_job", "clock_job", "spec_job", "animation_job"):
            try:
                if getattr(self, job, None):
                    self.root.after_cancel(getattr(self, job))
            except Exception:
                pass
        self.audio.cleanup()
        try:
            self.db.close()
        except Exception:
            pass
        try:
            self.logger.info("Application closed")
        except Exception:
            pass
        self.save_settings()
        try:
            self.root.destroy()
        except Exception:
            pass
