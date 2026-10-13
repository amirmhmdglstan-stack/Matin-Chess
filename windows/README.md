# MATIN CHESS — Windows Desktop Edition (Tauri)

The real Windows app — the **exact same web app as the Android build** (`app/` ==
`www/`), served inside the system **WebView2** by a tiny native **Tauri 2** shell.

## Why Tauri (v3.1.0+)

| | Electron (v3.0.0) | Tauri (v3.1.0) |
|---|---|---|
| Portable EXE | ~73 MB | **~5 MB** |
| Setup EXE | ~73 MB | **~3-4 MB** |
| Zipped setup | — | **~3 MB** |
| Chromium bundled | yes (~70 MB) | no (uses WebView2, preinstalled on Win10/11) |

Same content, same look, same engines, same texts — just a much smaller exe
(user request: *reduce the size, not the content*).

## Layout

```
windows/
  app/            the Android web app, unchanged (HTML + audio)
  src-tauri/      the native shell (Rust)
    src/main.rs     window commands + CORS-free streaming downloader
    tauri.conf.json window/bundle config (NSIS, currentUser)
    icons/          app icons (exe resource + installer)
  package.json    only devDependency: @tauri-apps/cli
```

## Build

```
npm install
npx tauri build
```

Outputs:

- `src-tauri/target/release/matin-chess.exe` — standalone portable EXE
- `src-tauri/target/release/bundle/nsis/*-setup.exe` — NSIS installer
  (LZMA solid compression, desktop shortcut, start menu, WebView2 bootstrap)

CI renames them to `MATIN-CHESS-vX.Y.Z-windows-{portable,setup}.exe` and zips
the setup with 7-Zip max compression (`.github/workflows/build-windows.yml`).

## Native commands (invoke from the web app)

- `win_close` / `win_min` / `win_max` — the exit button bridge
  (`window.MatinDesktop` is defined by the inline script when `window.__TAURI__` exists)
- `download_stream {url}` — last-resort engine download when both web mirrors
  fail (no CORS, streams `dl-chunk`/`dl-done`/`dl-error` events for the progress bar)
- `mc_export_pick {defaultName}` / `mc_export_begin {path}` /
  `mc_export_chunk {b64data}` / `mc_export_end` — v3.2.0 engine-package export:
  native save dialog (rfd) + chunked base64 writer for `.mceng` files, used by
  the Bot Hub's "📤 Export installed engines" button

Bot engines themselves are **not bundled** — they are downloaded in-app from the
creators' official sources and stored in IndexedDB, exactly like the Android app.

v3.2.0 adds **file transfer**: export all installed engines into a single
`.mceng` package and import it on another computer (Bot Hub -> 📥/📤 buttons),
fully offline.

v3.3.0 — **max level of every engine = truly unlimited thinking**:
`go depth 30` with no movetime in untimed games (soft stop after 10 min returns
the best move found so far, so the game never locks), self-managed clock in
timed games (`go wtime/btime`), 256MB hash, Matin-bot depth 12 / 90s. Also:
**17 full app themes** (15 dark + 2 light: Daylight, Paper) that restyle
background, panels and buttons together, live think-time/depth indicators, and
several bug fixes (background spectate loop, stale veltrix clock, file-dialog
cancel, session memory release on exit).
