#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

// Log file location: <OS temp dir>/orbit-viewer-logs/orbit-viewer.log
// (e.g. Windows: C:\Users\<you>\AppData\Local\Temp\orbit-viewer-logs\orbit-viewer.log
//  macOS/Linux: /tmp/orbit-viewer-logs/orbit-viewer.log or $TMPDIR equivalent)
// Used instead of println!/eprintln! because release builds on Windows have
// `windows_subsystem = "windows"` set, which means there is no console
// attached at all - anything printed to stdout/stderr is simply lost when
// running the built .exe directly (as opposed to `cargo run`/`tauri dev`).
fn log_dir() -> PathBuf {
    std::env::temp_dir().join("orbit-viewer-logs")
}
fn log_path() -> PathBuf {
    log_dir().join("orbit-viewer.log")
}
fn write_log(line: &str) {
    let _ = std::fs::create_dir_all(log_dir());
    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(log_path()) {
        let _ = writeln!(f, "{}", line);
    }
}

// Holds the running Python sidecar's child handle so we can kill it when
// the app exits. Without this, closing the window would leave an orphaned
// python/pyinstaller process running in the background.
struct SidecarState(Mutex<Option<CommandChild>>);

fn main() {
    // Capture panics (e.g. "failed to spawn sidecar") into the log file
    // too - in a release build there's no console to see them otherwise,
    // so a panic would just look like the app silently doing nothing.
    std::panic::set_hook(Box::new(|info| {
        write_log(&format!("PANIC: {}", info));
    }));

    // Fresh log each run, and note where to find it.
    let _ = std::fs::remove_file(log_path());
    write_log(&format!(
        "=== orbit-viewer starting. Log file: {} ===",
        log_path().display()
    ));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            write_log("setup(): spawning orbit-server sidecar...");

            let shell = app.shell();
            let (mut rx, child) = shell
                .sidecar("orbit-server")
                .expect("failed to create sidecar command - was it bundled under src-tauri/binaries?")
                .spawn()
                .expect("failed to spawn orbit-server sidecar");

            write_log("orbit-server sidecar spawned.");

            let state = app.state::<SidecarState>();
            *state.0.lock().unwrap() = Some(child);

            // Forward the sidecar's stdout/stderr into the same log file -
            // this is where Python-side errors (a REBOUND import failure,
            // a Flask traceback, etc.) will show up.
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            write_log(&format!(
                                "[orbit-server] {}",
                                String::from_utf8_lossy(&line).trim_end()
                            ));
                        }
                        CommandEvent::Stderr(line) => {
                            write_log(&format!(
                                "[orbit-server:ERR] {}",
                                String::from_utf8_lossy(&line).trim_end()
                            ));
                        }
                        other => {
                            write_log(&format!("[orbit-server] event: {:?}", other));
                        }
                    }
                }
                write_log("[orbit-server] output stream closed (process exited).");
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // When the main window closes, kill the sidecar so it doesn't
            // keep running (and keep holding its port) in the background.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                write_log("window CloseRequested - killing sidecar.");
                let state = window.app_handle().state::<SidecarState>();
                let mut guard = state.0.lock().unwrap();
                if let Some(child) = guard.take() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running orbit viewer");
}
