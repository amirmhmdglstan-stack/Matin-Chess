#!/usr/bin/env node
/* MATIN CHESS — Windows Desktop Edition (Electron main process)
 * ------------------------------------------------------------------
 * Serves the exact Android web app (app/) through a private secure
 * "matin://" protocol, so IndexedDB bot storage, WASM engines,
 * Web Workers and https downloads all behave exactly like the
 * Android build — same look, same texts, same engines.
 */
'use strict';

const { app, protocol, BrowserWindow, shell, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const APP_ROOT = path.join(__dirname, 'app');
const SCHEME = 'matin';
const INDEX = 'matin://app/index.html';

/* --- private scheme: standard+secure so storage/fetch work properly --- */
protocol.registerSchemesAsPrivileged([
  {
    scheme: SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: true,
    },
  },
]);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.ogg': 'audio/ogg',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

let win = null;

/* --- file responder for matin:// --- */
function serveFile(request) {
  return new Promise((resolve) => {
    let p;
    try {
      const u = new URL(request.url);
      p = decodeURIComponent(u.pathname);
    } catch (e) {
      return resolve(new Response(null, { status: 400 }));
    }
    if (!p || p === '/' || p.endsWith('/')) p += 'index.html';
    const file = path.normalize(path.join(APP_ROOT, p));
    if (!file.startsWith(APP_ROOT)) return resolve(new Response(null, { status: 403 }));
    fs.readFile(file, (err, data) => {
      if (err || !data) return resolve(new Response('Not found', { status: 404 }));
      const ext = path.extname(file).toLowerCase();
      resolve(new Response(data, { headers: { 'Content-Type': MIME[ext] || 'application/octet-stream' } }));
    });
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#0b0f14',
    title: 'MATIN CHESS',
    icon: path.join(__dirname, 'build', 'icon.png'),
    autoHideMenuBar: true,          /* modern: no File/Edit menu bar */
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      spellcheck: false,
      devTools: true,
    },
  });

  win.once('ready-to-show', () => win.show());

  /* keep external links in the default browser, never navigate away */
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (e, url) => {
    if (!url.startsWith(SCHEME + '://')) e.preventDefault();
  });

  /* renderer crash guard */
  win.webContents.on('render-process-gone', () => {
    if (win && !win.isDestroyed()) win.reload();
  });

  win.loadURL(INDEX);
}

/* --- window control IPC (used by the in-app exit button) --- */
ipcMain.handle('win-close', () => { if (win && !win.isDestroyed()) win.close(); });
ipcMain.handle('win-min', () => { if (win && !win.isDestroyed()) win.minimize(); });
ipcMain.handle('win-max', () => { if (win && !win.isDestroyed()) win.isMaximized() ? win.unmaximize() : win.maximize(); });

/* --- single instance: protects the IndexedDB bot storage --- */
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  /* headless/CI capture mode and software-only machines */
  const isCaptureRun = process.argv.some(a => a === '--capture' || a.startsWith('--capture='));
  if (isCaptureRun || process.env.MATIN_NO_GPU) {
    app.disableHardwareAcceleration();
    app.commandLine.appendSwitch('no-sandbox');   /* container/CI only */
  }
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(() => {
    protocol.handle(SCHEME, (request) => serveFile(request));
    createWindow();

    /* screenshot mode for CI/local smoke tests:
       electron . --capture=/path/out.png [ --wait=3000 ]            */
    const argv = process.argv;
    let out = null;
    const capIdx = argv.findIndex(a => a === '--capture' || a.startsWith('--capture='));
    if (capIdx !== -1) {
      out = argv[capIdx].startsWith('--capture=') ? argv[capIdx].slice('--capture='.length) : argv[capIdx + 1];
    }
    if (out && win) {
      let wait = 4500;
      const wIdx = argv.findIndex(a => a === '--wait' || a.startsWith('--wait='));
      if (wIdx !== -1) {
        wait = argv[wIdx].startsWith('--wait=') ? parseInt(argv[wIdx].slice('--wait='.length), 10) : parseInt(argv[wIdx + 1], 10);
        if (!isFinite(wait)) wait = 4500;
      }
      wait = Math.max(500, wait);
      win.webContents.once('did-finish-load', () => {
        setTimeout(async () => {
          try {
            const img = await win.webContents.capturePage();
            fs.writeFileSync(out, img.toPNG());
            console.log('CAPTURE_OK ' + out);
          } catch (e) {
            console.error('CAPTURE_FAIL ' + e.message);
          }
          app.quit();
        }, wait);
      });
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
}
