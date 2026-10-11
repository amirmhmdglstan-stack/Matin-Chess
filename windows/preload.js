/* MATIN CHESS — preload bridge (context isolation kept ON)
 * Exposes a tiny, safe API to the Android web app:
 *   window.MatinDesktop = { platform, close(), minimize(), maximize() }
 */
'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('MatinDesktop', {
  platform: process.platform,
  close: () => ipcRenderer.invoke('win-close'),
  minimize: () => ipcRenderer.invoke('win-min'),
  maximize: () => ipcRenderer.invoke('win-max'),
});
