/*!
 * Berserk — REAL C engine compiled to WebAssembly + worker glue for MATIN
 * CHESS Android. Official upstream sources compiled with Emscripten; each
 * version embeds its OFFICIAL release network byte-exact.
 * Upstream (GPL-3.0): https://github.com/jhonnold/Berserk
 * Copyright (C) Jay Honnold — GPL-3.0. See berserk-NOTICE.md.
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
    mod.ccall("berserk_wasm_init", null, [], []);
    ready = true;
    queue.forEach(function (c) { mod.ccall("berserk_wasm_cmd", null, ["string"], [c]); });
    queue = [];
    postMessage("berserk-ready");
  }
};
self.Module = mod;
self.onmessage = function (e) {
  var c = String(e.data == null ? "" : e.data);
  if (ready) mod.ccall("berserk_wasm_cmd", null, ["string"], [c]);
  else queue.push(c);
};
importScripts(self.BOT_FILES[self.BOT_CORE || self.BOT_ENTRY || "berserk-14-core.js"]);
})();
