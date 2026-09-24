# Fairy-Stockfish — WASM build for MATIN CHESS (Android)

## Upstream project
- Engine: **Fairy-Stockfish** by Fabian Fichter — https://github.com/fairy-stockfish/Fairy-Stockfish
- License: **GPL-3.0** (Stockfish derivative; see repository LICENSE + COPYING.txt)
- Version built: master snapshot 240926 ("Fairy-Stockfish 240926 LB")

## What this build is
The unmodified upstream C++ sources compiled to WebAssembly with Emscripten
3.1.64 using the **maker's own `src/Makefile_js` flags**:
`-O3 -DNNUE_EMBEDDING_OFF -DNO_THREADS -DLARGEBOARDS -DPRECOMPUTED_MAGICS -DALLVARS`
plus `-fexceptions` (the engine throws/catches internally) and memory growth.
No strength-affecting changes. Build-config patches only:

1. `src/thread.cpp` — synchronous single-thread search driver
   (`Thread::start_searching` runs the (virtual) `search()` inline;
   ctor/dtor do not spawn/join `std::thread`).
2. `src/uci.cpp` — `UCI::loop` split into `UCI::WasmInit()` / `UCI::WasmCmd(const char*)`
   for function-call UCI driving from a Web Worker.
3. `src/tt.cpp` — `TranspositionTable::clear()` zeroes the table inline
   (upstream spawns one clear thread per pool thread).
4. `src/main_wasm.cpp` — exported `fairy_wasm_init` / `fairy_wasm_cmd` drivers
   mirroring upstream `main()`.

## Build recipe
See `scripts/build_fairy_wasm.sh` in the MATIN CHESS repository.
Node test: uciok, bestmove on startpos/kiwipete/endgame, repeated searches —
all pass, movetime respected.
