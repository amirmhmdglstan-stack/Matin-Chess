/*!
 * Fairy-Stockfish — REAL C++ engine compiled to WebAssembly + worker glue
 * for MATIN CHESS Android. Official upstream source compiled with Emscripten
 * using the maker's own Makefile_js recipe flags.
 * Upstream (GPL-3.0): https://github.com/fairy-stockfish/Fairy-Stockfish
 * Copyright (C) 2022 Fabian Fichter — GPL-3.0. See fairy-NOTICE.md.
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
    mod.ccall("fairy_wasm_init", null, [], []);
    ready = true;
    queue.forEach(function (c) { mod.ccall("fairy_wasm_cmd", null, ["string"], [c]); });
    queue = [];
    postMessage("fairy-ready");
  }
};
self.Module = mod;
self.onmessage = function (e) {
  var c = String(e.data == null ? "" : e.data);
  if (ready) mod.ccall("fairy_wasm_cmd", null, ["string"], [c]);
  else queue.push(c);
};
importScripts(self.BOT_FILES[self.BOT_CORE || self.BOT_ENTRY || "fairy-core.js"]);
})();
