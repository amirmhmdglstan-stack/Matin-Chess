# Veltrix — Real Engine Build (WebAssembly)

The `veltrix.js` / `veltrix-core.js` / `veltrix.wasm` trio in this folder is the
**real, unmodified C++ engine** of the Veltrix project, compiled to WebAssembly
— not a re-implementation. It is the same engine the upstream GUI plays
against: bitboards, PVS + quiescence search with modern pruning, tapered
hand-crafted evaluation and the original Polyglot opening book
(`books/veltrix.bin`, embedded in `veltrix.js`).

* Upstream project: <https://github.com/amirmhmdglstan-stack/Veltrix-Chess-bot>
  (branch `arena/01a0b58e-veltrix-chess-bot`)
* License: **GPL-3.0-or-later** — Copyright (C) 2026 Veltrix Project
* Difficulty ladder: `gui/models.py` of the upstream project (High / Light /
  Flash named models + Level 1..8 node budgets). The app sends the exact
  `go nodes N` / `go movetime M` budgets defined there, so every level behaves
  exactly as strong as upstream.

## Local patches (build-config only; chess behaviour unchanged)

1. `uci.h` / `uci.cpp` — `loop()` refactored into `wasm_init()` +
   `process_line()` so the worker can drive the engine by function call
   instead of stdin. The stdin loop remains for native builds.
2. `search.h` — default `Hash` is 32 MB under `VELTRIX_WASM` (native stays 128 MB).
3. `search.cpp` — under `VELTRIX_WASM` the Lazy-SMP driver runs synchronously
   on the calling thread with `Threads=1` (WebViews have no pthreads). Search
   algorithm and node accounting are untouched (`perft 4 = 197,281` exact).
4. `main_wasm.cpp` (new) — exports `veltrix_wasm_init` / `veltrix_wasm_cmd`.

## Build

```sh
em++ -std=c++17 -O3 -DNDEBUG -DVELTRIX_WASM -Isrc \
  -fno-exceptions -fno-rtti -s ALLOW_MEMORY_GROWTH=1 \
  -s INITIAL_MEMORY=33554432 -s STACK_SIZE=8388608 \
  -s ENVIRONMENT=worker,node \
  -s EXPORTED_FUNCTIONS='["_veltrix_wasm_init","_veltrix_wasm_cmd","_malloc","_free","_stackSave","_stackRestore"]' \
  -s EXPORTED_RUNTIME_METHODS='["ccall","cwrap","UTF8ToString","stringToUTF8","FS"]' \
  -s FORCE_FILESYSTEM=1 -s INVOKE_RUN=0 \
  $(ls src/*.cpp | grep -v "src/main.cpp") -o veltrix-core.js
```

(with Emscripten 3.1.64; script kept at the project build box as
`scripts/build_veltrix_wasm.sh`.)
