# Berserk 14 — WASM build for MATIN CHESS (Android)

## Upstream project
- Engine: **Berserk 14** by Jay Honnold — https://github.com/jhonnold/Berserk
- License: **GPL-3.0** (see Berserk repository LICENSE)
- Official release network: `berserk-9b84c340af7e.nn` (25,201,924 bytes)
  from https://github.com/jhonnold/Berserk/releases/tag/14 — embedded byte-exact.

## What this build is
The unmodified upstream C sources of tag **14** compiled to WebAssembly
(Emscripten 3.1.64) so the real engine runs locally inside the app.
No strength-affecting changes. Build-config patches only:

1. `src/uci.c` — `UCILoop()` split into `UciWasmInit()` / `UciWasmCmd(const char*)`
   so the WebView can drive UCI by function call instead of stdin blocking.
2. `src/thread.c` — synchronous single-thread driver (WebView has no
   SharedArrayBuffer): `ThreadWake` runs `Search`/`MainSearch` inline,
   `ThreadCreate` allocates without pthreads.
3. `src/nn/evaluate.c` — `INCBIN(Embed, EVALFILE)` replaced by an external
   `EmbedData[]` array (generated from the official release net) because the
   assembler `INCBIN` path is not available on the wasm target.

## Build recipe
See `scripts/build_berserk2_wasm.sh` in the MATIN CHESS repository.
Node test: perft/search verified; movetime respected; kiwipete (capture-heavy)
regression position passes (this was the v1.5.0 crash — root cause was the
net never reaching memory; embedding at compile time fixes it).
