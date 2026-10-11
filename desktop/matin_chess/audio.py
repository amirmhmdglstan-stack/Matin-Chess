# -*- coding: utf-8 -*-
"""MATIN CHESS — audio engine.

* Every quiet piece move (player, AI, two-player or spectate) plays the
  real ``move-self`` sound; every capture plays the real ``capture``
  sound.  Both ship inside this file as zlib+base64 WAV blobs extracted
  from the uploaded mp3 files, so the game (and the built .exe) needs no
  external assets and works fully offline.
* Cross-platform playback: Windows ``winsound``, Linux ``aplay`` /
  ``paplay`` / ``ffplay``, macOS ``afplay``.  If nothing is available the
  app silently no-ops — sound never breaks the game.
* The remaining UI events use small synthesized tones (the original
  MATIN CHESS charm) and the background music is generated in code.
"""
import base64
import math
import os
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave
import zlib

try:
    import winsound
except Exception:  # non-Windows
    winsound = None

from .constants import PIECE_SOUNDS

_SR = 22050

# ----------------------------------------------------------- embedded sounds
_MOVE_SELF_B64 = "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"
_CAPTURE_B64 = "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"

# ----------------------------------------------------------------- player
_PLAYER = None


def _detect_player():
    global _PLAYER
    if _PLAYER is not None:
        return _PLAYER
    if winsound is not None:
        _PLAYER = "winsound"
        return _PLAYER
    for exe, kind in (("aplay", "wav"), ("paplay", "wav"),
                      ("ffplay", "any"), ("afplay", "any")):
        if shutil.which(exe):
            _PLAYER = exe
            return _PLAYER
    _PLAYER = ""
    return _PLAYER


def _play_file(path):
    """Asynchronously play a WAV file on whatever the OS offers."""
    if not path or not os.path.exists(path):
        return
    player = _detect_player()
    try:
        if player == "winsound":
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        elif player == "aplay":
            subprocess.Popen([player, "-q", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif player in ("paplay", "afplay"):
            subprocess.Popen([player, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif player == "ffplay":
            subprocess.Popen([player, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _synth_tone(freq, ms, path):
    """Write a short enveloped tone to a WAV file (original charm)."""
    n = int(_SR * ms / 1000)
    frames = bytearray()
    for i in range(n):
        t = i / _SR
        env = min(1.0, i / (_SR * 0.01), (n - i) / (_SR * 0.03) or 1)
        sample = int(7000 * env * math.sin(2 * math.pi * freq * t))
        frames += struct.pack("<h", sample)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes(bytes(frames))


def _synth_melody(path):
    """The tiny original background melody, standard library only."""
    notes = [(523, .18), (659, .18), (784, .18), (659, .18),
             (587, .18), (698, .18), (880, .25), (698, .18),
             (523, .18), (659, .18), (784, .18), (1047, .35)]
    frames = bytearray()
    for freq, dur in notes:
        n = int(_SR * dur)
        for i in range(n):
            t = i / _SR
            env = min(1, i / (_SR * .02), (n - i) / (_SR * .05))
            frames += struct.pack("<h", int(8500 * env * math.sin(2 * math.pi * freq * t)))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes(bytes(frames))


class AudioEngine:
    """Thread-safe-ish game audio: real move/capture sounds + tones + music."""

    def __init__(self):
        self.enabled = True
        self.music_enabled = True
        self.music_thread = None
        self.stop_event = threading.Event()
        self.sound_q = queue.Queue()
        self._dir = None
        self._files = {}          # kind -> wav path
        self._music_path = None
        self._extract()

    # ------------------------------------------------------------ assets
    def _extract(self):
        try:
            self._dir = tempfile.mkdtemp(prefix="matin_chess_audio_")
            blobs = {"move": _MOVE_SELF_B64, "capture": _CAPTURE_B64}
            for kind, b64 in blobs.items():
                raw = zlib.decompress(base64.b64decode(b64))
                p = os.path.join(self._dir, f"{kind}.wav")
                with open(p, "wb") as f:
                    f.write(raw)
                self._files[kind] = p
            # synthesized event tones
            for kind, (freq, ms) in PIECE_SOUNDS.items():
                p = os.path.join(self._dir, f"t_{kind}.wav")
                try:
                    _synth_tone(freq, ms, p)
                    self._files[kind] = p
                except Exception:
                    pass
        except Exception:
            self._files = {}

    def real_sound_available(self, kind):
        return kind in self._files

    # ------------------------------------------------------------- events
    def play_move(self):
        """The real 'move-self' sound — every non-capturing move."""
        if self.enabled:
            _play_file(self._files.get("move"))

    def play_capture(self):
        """The real 'capture' sound — every capture."""
        if self.enabled:
            _play_file(self._files.get("capture"))

    def play(self, kind):
        if not self.enabled:
            return
        path = self._files.get(kind)
        if path:
            _play_file(path)
            return
        # fallback beep (Windows only, like the original)
        f, ms = PIECE_SOUNDS.get(kind, (700, 60))
        if winsound:
            try:
                winsound.Beep(int(f), int(ms))
            except Exception:
                pass

    def move(self, capture=False, check=False):
        """Compatibility shim used by older call sites."""
        if capture:
            self.play_capture()
        else:
            self.play_move()

    def victory(self):
        def seq():
            for f in (523, 659, 784, 1047, 1319):
                self.play("win")
                time.sleep(.09)
        threading.Thread(target=seq, daemon=True).start()

    # -------------------------------------------------------------- music
    def start_music(self):
        if not self.music_enabled:
            return
        if self.music_thread and self.music_thread.is_alive():
            return
        if not self._music_path:
            try:
                self._music_path = os.path.join(self._dir, "music.wav")
                _synth_melody(self._music_path)
            except Exception:
                return
        self.stop_event.clear()

        def loop():
            while not self.stop_event.is_set():
                if winsound is not None:
                    try:
                        winsound.PlaySound(self._music_path, winsound.SND_FILENAME)
                    except Exception:
                        break
                else:
                    before = time.time()
                    _play_file(self._music_path)
                    # melody is ~2.6 s; keep the loop gentle
                    while time.time() - before < 3.0 and not self.stop_event.is_set():
                        time.sleep(0.15)
                    if self.stop_event.is_set():
                        break
                for _ in range(20):
                    if self.stop_event.is_set():
                        return
                    time.sleep(0.1)

        self.music_thread = threading.Thread(target=loop, daemon=True)
        self.music_thread.start()

    def stop_music(self):
        self.stop_event.set()
        if winsound:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass

    # ------------------------------------------------------------ cleanup
    def cleanup(self):
        self.stop_music()
        try:
            if self._dir and os.path.isdir(self._dir):
                shutil.rmtree(self._dir, ignore_errors=True)
        except Exception:
            pass
