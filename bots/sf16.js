/*!
 * Stockfish 16 — REAL C++ engine compiled to WebAssembly + worker glue for
 * MATIN CHESS Android. Official upstream source (tag sf_16) compiled with
 * Emscripten; the OFFICIAL nn-5af11540bbfe.nnue (official npm package) is
 * embedded byte-exact. Upstream (GPL-3.0):
 * https://github.com/official-stockfish/Stockfish — see sf16 build script.
 */
(function () {
"use strict";
/* books/veltrix.bin — the original Veltrix Polyglot opening book, embedded */
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
importScripts(self.BOT_FILES[self.BOT_CORE || self.BOT_ENTRY || "sf16-core.js"]);
})();
