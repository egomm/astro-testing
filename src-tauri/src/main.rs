#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;
use std::sync::Mutex;

// Holds the running Python sidecar's child handle so we can kill it when
// the app exits. Without this, closing the window would leave an orphaned
// python/pyinstaller process running in the background.
struct SidecarState(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState(Mutex::new(None)))
        .setup(|app| {
            // Spawn the bundled REBOUND/Flask backend. `sidecar()` looks
            // for a binary named `orbit-server-<target-triple>[.exe]`
            // under src-tauri/binaries/, per the `externalBin` entry in
            // tauri.conf.json.
            let shell = app.shell();
            let (mut rx, child) = shell
                .sidecar("orbit-server")
                .expect("failed to create sidecar command - was it bundled under src-tauri/binaries?")
                .spawn()
                .expect("failed to spawn orbit-server sidecar");

            let state = app.state::<SidecarState>();
            *state.0.lock().unwrap() = Some(child);

            // Forward the sidecar's stdout/stderr into this app's own
            // console during development, so Python-side errors (e.g. a
            // REBOUND import failure) are visible instead of silent.
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            print!("[orbit-server] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Stderr(line) => {
                            eprint!("[orbit-server] {}", String::from_utf8_lossy(&line));
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // When the main window closes, kill the sidecar so it doesn't
            // keep running (and keep holding its port) in the background.
            if let tauri::WindowEvent::CloseRequested { .. } = event {
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
