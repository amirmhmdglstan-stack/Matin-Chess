# MATIN CHESS — Windows Desktop Edition (v3.0.0)

The **exact Android app** (same look, same Persian texts, same engines, same
sounds) running on Windows as a real desktop application — built with
**Electron**, packaged by **electron-builder**.

```
windows/
├── main.js        Electron main process (private matin:// protocol, window)
├── preload.js     Safe bridge: window.MatinDesktop.close/minimize/maximize
├── app/           ← the Android web app itself
│   ├── index.html   (same source as www/, adapted: real piece sounds,
│   │                 3-second menu-music gap, Windows exit bridge)
│   └── audio/       theme.mp3 (menu music) + move-self.mp3 + capture.mp3
├── build/         icon.ico / icon.png
└── package.json   electron-builder config (portable .exe + NSIS setup)
```

## Run from source

```bash
cd windows
npm install
npm start
```

Requires Node.js 18+ (Electron is the only dev dependency).

## Build the Windows EXE yourself

```bash
npm run dist
```

Produces in `windows/dist/`:

| File | What it is |
|---|---|
| `MATIN-CHESS-v3.0.0-windows-portable.exe` | single-file portable — no install, just run |
| `MATIN-CHESS-v3.0.0-windows-setup.exe` | classic installer (start-menu + desktop shortcuts) |

## How it matches the Android app

- **Look & texts** — the renderer is the Android `www/index.html` itself:
  same dark dashboard + gold theme, same buttons, same Persian wording.
- **Background music** — `theme.mp3` loops **only on the main menu** with a
  **3-second gap**, never inside a game (exactly like Android, gap widened
  on request).
- **Real piece sounds** — every move by anyone (you, the bot, or two bots in
  spectate mode) plays `move-self.mp3`; every capture plays `capture.mp3`.
- **Real engines, nothing preinstalled** — besides the built-in MATIN BOT,
  every engine (Veltrix, Stockfish 6→19, Berserk 12/13/14, Lozza,
  Garbochess, Fairy-Stockfish) is downloaded **inside the app** from its
  official source and stored in the app's own IndexedDB storage, exactly
  like the Android downloader.
- **Board design** — identical Veltrix board rendering with 8 color themes.

## Bot storage

Downloaded engine files live in Chromium IndexedDB under
`%APPDATA%\MATIN CHESS\` — one download stays installed forever, fully
offline afterwards.

## GitHub Actions

`.github/workflows/build-windows.yml` builds both EXE files on every `v*`
tag and publishes them to a GitHub Release automatically.
