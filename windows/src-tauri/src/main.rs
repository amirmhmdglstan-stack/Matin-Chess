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
 * Runs on the command thread pool (blocking is fine). Streams the file
 * to the webview via events so the UI keeps its live progress bar:
 *   dl-chunk {b64, seq, total} -> dl-done -> (or dl-error {msg})
 * Follows redirects; no CORS, no mixed-content, no browser limits. */
#[tauri::command]
fn download_stream(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(Duration::from_secs(30))
        .build();
    let resp = agent
        .get(&url)
        .call()
        .map_err(|e| {
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
        let n = reader
            .read(&mut buf)
            .map_err(|e| {
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
            download_stream
        ])
        .run(tauri::generate_context!())
        .expect("error while running MATIN CHESS");
}
