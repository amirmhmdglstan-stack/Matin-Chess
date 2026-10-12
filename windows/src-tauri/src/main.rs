/* MATIN CHESS — Windows Desktop Edition (Tauri shell)
 * ------------------------------------------------------------------
 * Serves the exact Android web app (app/) inside the system WebView2,
 * so IndexedDB bot storage, WASM engines, Web Workers and https
 * downloads all behave exactly like the Android build — same look,
 * same texts, same engines — in a tiny native exe (~5 MB instead of
 * ~73 MB Electron).
 */
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::Read;
use std::io::Write;
use std::sync::Mutex;
use std::time::Duration;
use base64::Engine;
use tauri::{Emitter, Manager};

fn b64(data: &[u8]) -> String {
    base64::engine::general_purpose::STANDARD.encode(data)
}

/* --- window control (same bridge the web app's exit button uses) --- */
#[tauri::command]
fn win_close(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.close();
    }
}

#[tauri::command]
fn win_min(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.minimize();
    }
}

#[tauri::command]
fn win_max(app: tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let is_max = w.is_maximized().unwrap_or(false);
        if is_max {
            let _ = w.unmaximize();
        } else {
            let _ = w.maximize();
        }
    }
}

/* --- CORS-free engine downloader (last-resort path for bot files) ---
 * Streams the file to the webview via events so the UI keeps its live
 * progress bar:  dl-chunk {b64, seq, total} -> dl-done -> (or dl-error {msg})
 * Follows redirects; no CORS, no mixed-content, no browser limits.
 * Runs on the blocking thread pool — the UI/main thread never freezes. */
fn download_blocking(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(30))
        .build();
    let resp = agent.get(&url).call().map_err(|e| {
        let _ = app.emit("dl-error", serde_json::json!({ "msg": e.to_string() }));
        e.to_string()
    })?;
    let total: u64 = resp
        .header("content-length")
        .and_then(|v| v.parse().ok())
        .unwrap_or(0);
    let mut reader = resp.into_reader();
    let mut seq: u64 = 0;
    loop {
        let mut buf = vec![0u8; 262144];
        let n = reader.read(&mut buf).map_err(|e| {
            let _ = app.emit("dl-error", serde_json::json!({ "msg": e.to_string() }));
            e.to_string()
        })?;
        if n == 0 {
            break;
        }
        buf.truncate(n);
        let _ = app.emit(
            "dl-chunk",
            serde_json::json!({ "b64": b64(&buf), "seq": seq, "total": total }),
        );
        seq += 1;
    }
    let _ = app.emit("dl-done", ());
    Ok(())
}

#[tauri::command]
async fn download_stream(app: tauri::AppHandle, url: String) -> Result<(), String> {
    // async command => runs on the runtime; blocking work is moved to the
    // blocking pool so neither the main thread nor the UI ever stalls
    match tauri::async_runtime::spawn_blocking(move || download_blocking(app, url)).await {
        Ok(res) => res,
        Err(e) => Err(format!("download task failed: {e}")),
    }
}

/* --- engine package export (.mceng): file transfer between computers ---
 * Native save dialog (rfd) + chunked base64 writes, so even a ~95MB
 * Stockfish 19 package streams to disk smoothly without freezing the UI.
 * JS side: mceSavePackage() in app/index.html. */
static EXPORT_FILE: Mutex<Option<std::fs::File>> = Mutex::new(None);

#[tauri::command]
async fn mc_export_pick(default_name: String) -> Result<Option<String>, String> {
    tauri::async_runtime::spawn_blocking(move || -> Result<Option<String>, String> {
        let picked = rfd::FileDialog::new()
            .set_title("Save MATIN CHESS engine package")
            .set_file_name(&default_name)
            .add_filter("MATIN engine package", &["mceng"])
            .save_file();
        Ok(picked.map(|p| p.to_string_lossy().into_owned()))
    })
    .await
    .map_err(|e| format!("pick failed: {e}"))?
}

#[tauri::command]
async fn mc_export_begin(path: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let f = std::fs::File::create(&path).map_err(|e| e.to_string())?;
        let mut guard = EXPORT_FILE.lock().map_err(|e| e.to_string())?;
        *guard = Some(f);
        Ok(())
    })
    .await
    .map_err(|e| format!("begin failed: {e}"))?
}

#[tauri::command]
async fn mc_export_chunk(b64data: String) -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let bytes = base64::engine::general_purpose::STANDARD
            .decode(b64data.as_bytes())
            .map_err(|e| e.to_string())?;
        let mut guard = EXPORT_FILE.lock().map_err(|e| e.to_string())?;
        let f = guard.as_mut().ok_or("no-export-open")?;
        f.write_all(&bytes).map_err(|e| e.to_string())
    })
    .await
    .map_err(|e| format!("chunk failed: {e}"))?
}

#[tauri::command]
async fn mc_export_end() -> Result<(), String> {
    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let mut guard = EXPORT_FILE.lock().map_err(|e| e.to_string())?;
        *guard = None; // File dropped -> flushed & closed
        Ok(())
    })
    .await
    .map_err(|e| format!("end failed: {e}"))?
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            // protect the IndexedDB bot storage: focus the existing window
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.show();
                let _ = w.set_focus();
            }
        }))
        .invoke_handler(tauri::generate_handler![
            win_close,
            win_min,
            win_max,
            download_stream,
            mc_export_pick,
            mc_export_begin,
            mc_export_chunk,
            mc_export_end
        ])
        .run(tauri::generate_context!())
        .expect("error while running MATIN CHESS");
}
