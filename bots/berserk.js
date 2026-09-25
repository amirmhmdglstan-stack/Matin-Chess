/*!
 * Berserk 14 — REAL C engine compiled to WebAssembly + worker glue
 * for MATIN CHESS Android. This is the exact upstream release 14
 * (github.com/jhonnold/Berserk) compiled with Emscripten; the OFFICIAL
 * release network berserk-9b84c340af7e.nn is embedded in the wasm.
 *
 * Upstream (GPL-3.0): https://github.com/jhonnold/Berserk
 * Copyright (C) 2024 Jay Honnold — GPL-3.0
 * See berserk-NOTICE.md for the build recipe and local build-config patches.
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
importScripts(self.BOT_FILES[self.BOT_ENTRY||"berserk-core.js"]);
})();
