/*!
 * Stockfish 16 — REAL C++ engine compiled to WebAssembly + worker glue
 * for MATIN CHESS Android. This is the exact upstream source
 * (github.com/official-stockfish/Stockfish tag sf_16) compiled with
 * Emscripten; the OFFICIAL network nn-5af11540bbfe.nnue (from the official
 * npm package) is embedded byte-exact in the wasm.
 *
 * Upstream (GPL-3.0): https://github.com/official-stockfish/Stockfish
 * Copyright (C) Stockfish developers — GPL-3.0
 * See ../scripts/build_sf16_wasm.sh + sf16_patch.py for the build recipe.
 */
(function () {
"use strict";
var queue = [], ready = false;
var mod = {
  print: function (t) { postMessage(String(t)); },
  printErr: function () {},
  locateFile: function (f) {
    if (/\.wasm$/.test(f) && self.BOT_WASM_URL) return self.BOT_WASM_URL;
    return f;
  },
  onRuntimeInitialized: function () {
    mod.ccall("sf16_wasm_init", null, [], []);
    ready = true;
    queue.forEach(function (c) { mod.ccall("sf16_wasm_cmd", null, ["string"], [c]); });
    queue = [];
    postMessage("sf16-ready");
  }
};
self.Module = mod;
self.onmessage = function (e) {
  var c = String(e.data == null ? "" : e.data);
  if (ready) mod.ccall("sf16_wasm_cmd", null, ["string"], [c]);
  else queue.push(c);
};
importScripts(self.BOT_FILES[self.BOT_ENTRY || "sf16-core.js"]);
})();
