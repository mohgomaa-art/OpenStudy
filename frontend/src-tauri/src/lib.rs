// Force rebuild to re-link regenerated high-quality icon.ico resources
use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Manager, PhysicalPosition, WebviewWindow,
};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

struct AppState {
    companion_pos: Mutex<Option<(i32, i32)>>,
}

struct BackendProcess {
    child: Mutex<Option<std::process::Child>>,
}

impl Drop for BackendProcess {
    fn drop(&mut self) {
        let mut lock = self.child.lock().unwrap();
        if let Some(mut child) = lock.take() {
            let _ = child.kill();
        }
    }
}

fn find_backend_path() -> Option<std::path::PathBuf> {
    let mut dir = std::env::current_dir().ok()?;
    loop {
        let main_py = dir.join("main.py");
        if main_py.exists() {
            return Some(main_py);
        }
        if let Some(parent) = dir.parent() {
            dir = parent.to_path_buf();
        } else {
            break;
        }
    }
    None
}

fn kill_port_8000() {
    #[cfg(target_os = "windows")]
    {
        // Use PowerShell to kill any process listening on port 8000 silently
        let mut cmd = std::process::Command::new("powershell");
        cmd.args(&[
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle", "Hidden",
            "-Command",
            "Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }",
        ]);
        cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
        let _ = cmd.status();
    }
}


fn spawn_backend(app: &tauri::AppHandle) -> Option<std::process::Child> {
    kill_port_8000();

    // 1. Bundled production executable — release builds only.
    // In debug/dev, skip it: the exe may be a stale PyInstaller build that
    // calls uvicorn with a string import ("main:app") which fails because
    // the working directory isn't the project root. Dev always uses python.
    #[cfg(not(debug_assertions))]
    if let Ok(resource_dir) = app.path().resource_dir() {
        let exe_path = resource_dir.join("OpenStudyBackend.exe");
        if exe_path.exists() {
            let mut cmd = std::process::Command::new(&exe_path);
            cmd.current_dir(&resource_dir);
            #[cfg(target_os = "windows")]
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW
            if let Ok(child) = cmd.spawn() {
                return Some(child);
            }
        }
    }

    // 2. Fallback to development mode (pythonw or python)
    if let Some(main_py) = find_backend_path() {
        if let Some(root_dir) = main_py.parent() {
            // Try pythonw first
            let mut cmd = std::process::Command::new("pythonw");
            cmd.arg(&main_py)
               .current_dir(root_dir);
            #[cfg(target_os = "windows")]
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

            if let Ok(child) = cmd.spawn() {
                return Some(child);
            }

            // Fallback to python
            let mut cmd = std::process::Command::new("python");
            cmd.arg(&main_py)
               .current_dir(root_dir);
            #[cfg(target_os = "windows")]
            cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW

            if let Ok(child) = cmd.spawn() {
                return Some(child);
            }
        }
    }

    None
}

// ── Tauri commands ────────────────────────────────────────────────────────────

#[tauri::command]
fn set_click_through(window: WebviewWindow, enabled: bool) -> Result<(), String> {
    window
        .set_ignore_cursor_events(enabled)
        .map_err(|e| e.to_string())
}

#[tauri::command]
fn start_dragging(window: WebviewWindow) -> Result<(), String> {
    window.start_dragging().map_err(|e| e.to_string())
}

#[tauri::command]
fn save_position(app: AppHandle, x: i32, y: i32) {
    let state = app.state::<AppState>();
    let mut pos = state.companion_pos.lock().unwrap();
    *pos = Some((x, y));
    // Persist to disk via Tauri path API
    if let Ok(data_dir) = app.path().app_data_dir() {
        let file = data_dir.join("companion-position.json");
        let json = format!("{{\"x\":{},\"y\":{}}}", x, y);
        let _ = std::fs::create_dir_all(&data_dir);
        let _ = std::fs::write(file, json);
    }
}



#[tauri::command]
async fn open_visualizer(app: AppHandle, file_path: String) -> Result<(), String> {
    let filename = std::path::Path::new(&file_path)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or(&file_path)
        .to_string();
    let url_str = format!("http://localhost:8000/api/visual/view/{}", filename);
    let url = tauri::Url::parse(&url_str).map_err(|e| e.to_string())?;

    // Close old window non-blockingly, then spawn new one.
    if let Some(win) = app.get_webview_window("visualizer") {
        let _ = win.close();
    }

    let app2 = app.clone();
    let filename_clone = filename.clone();
    tauri::async_runtime::spawn(async move {
        // Short async yield — lets the OS process the close before creating anew.
        tokio::time::sleep(std::time::Duration::from_millis(150)).await;
        let url2 = tauri::Url::parse(&format!(
            "http://localhost:8000/api/visual/view/{}",
            filename_clone
        ))
        .unwrap();
        let _ = tauri::WebviewWindowBuilder::new(
            &app2,
            "visualizer",
            tauri::WebviewUrl::External(url2),
        )
        .title(format!("Visual — {}", filename_clone))
        .inner_size(1100.0, 860.0)
        .min_inner_size(600.0, 400.0)
        .decorations(true)
        .transparent(false)
        .always_on_top(false)
        .skip_taskbar(false)
        .resizable(true)
        .center()
        .build();
    });

    Ok(())
}

#[tauri::command]
fn open_dashboard(app: AppHandle) -> Result<(), String> {
    // Open an in-app dashboard window (or show existing one).
    if let Some(win) = app.get_webview_window("dashboard") {
        let _ = win.show();
        let _ = win.set_focus();
        return Ok(());
    }
    let _ = tauri::WebviewWindowBuilder::new(
        &app,
        "dashboard",
        tauri::WebviewUrl::App("index.html".into()),
    )
    .title("OpenStudy — Dashboard")
    .inner_size(1200.0, 800.0)
    .min_inner_size(800.0, 500.0)
    .decorations(true)
    .resizable(true)
    .center()
    .build()
    .map_err(|e| e.to_string())?;
    Ok(())
}


#[tauri::command]
fn close_visualizer(app: AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("visualizer") {
        win.close().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn minimize_window(window: WebviewWindow) -> Result<(), String> {
    window.minimize().map_err(|e| e.to_string())
}

#[tauri::command]
fn maximize_window(window: WebviewWindow) -> Result<(), String> {
    if window.is_maximized().unwrap_or(false) {
        window.unmaximize().map_err(|e| e.to_string())
    } else {
        window.maximize().map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn toggle_fullscreen(window: WebviewWindow) -> Result<(), String> {
    let is_full = window.is_fullscreen().unwrap_or(false);
    window.set_fullscreen(!is_full).map_err(|e| e.to_string())
}

#[tauri::command]
fn close_window(window: WebviewWindow) -> Result<(), String> {
    window.close().map_err(|e| e.to_string())
}

#[tauri::command]
fn hide_companion(app: AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("main") {
        win.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn reset_position(app: AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("main") {
        let monitor = win.primary_monitor().map_err(|e| e.to_string())?;
        let (x, y) = if let Some(m) = monitor {
            let size = m.size();
            ((size.width as i32) - 700 - 20, 20)
        } else {
            (1520, 20)
        };
        win.set_position(PhysicalPosition::new(x, y))
            .map_err(|e| e.to_string())?;
        save_position(app, x, y);
    }
    Ok(())
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    if let Some(backend) = app.try_state::<BackendProcess>() {
        let mut lock = backend.child.lock().unwrap();
        if let Some(mut child) = lock.take() {
            let _ = child.kill();
        }
    }
    app.exit(0);
}

// ── Boot ──────────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState {
            companion_pos: Mutex::new(None),
        })
        .setup(|app| {
            // Spawn the python backend silently
            let child = spawn_backend(app.handle());
            app.manage(BackendProcess {
                child: Mutex::new(child),
            });

            // Restore saved position or center on screen
            if let Some(win) = app.get_webview_window("main") {
                // Try to restore saved position
                let mut restored = false;
                if let Ok(data_dir) = app.path().app_data_dir() {
                    let file = data_dir.join("companion-position.json");
                    if let Ok(json) = std::fs::read_to_string(&file) {
                        if let Ok(v) = serde_json::from_str::<serde_json::Value>(&json) {
                            let x = v["x"].as_i64().unwrap_or(0) as i32;
                            let y = v["y"].as_i64().unwrap_or(0) as i32;
                            // Validate position is on a real monitor (not off-screen)
                            if let Ok(Some(monitor)) = win.primary_monitor() {
                                let sw = monitor.size().width as i32;
                                let sh = monitor.size().height as i32;
                                if x >= -100 && x < sw && y >= -100 && y < sh {
                                    let _ = win.set_position(PhysicalPosition::new(x, y));
                                    let state = app.state::<AppState>();
                                    *state.companion_pos.lock().unwrap() = Some((x, y));
                                    restored = true;
                                }
                            }
                        }
                    }
                }
                // Center on screen if no valid saved position
                if !restored {
                    if let Ok(Some(monitor)) = win.primary_monitor() {
                        let sw = monitor.size().width as i32;
                        let sh = monitor.size().height as i32;
                        let win_w = 700i32;
                        let win_h = 700i32;
                        let x = (sw - win_w) / 2;
                        let y = (sh - win_h) / 2;
                        let _ = win.set_position(PhysicalPosition::new(x, y));
                    }
                }
                // Show window only once backend is ready — avoids ERR_CONNECTION_REFUSED spam
                let win_for_ready = win.clone();
                std::thread::spawn(move || {
                    for _ in 0..60 {
                        std::thread::sleep(std::time::Duration::from_millis(250));
                        if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
                            let _ = win_for_ready.show();
                            let _ = win_for_ready.set_focus();
                            return;
                        }
                    }
                    // Fallback: show after 15 s even if backend never came up
                    let _ = win_for_ready.show();
                    let _ = win_for_ready.set_focus();
                });
            }

            // Save position when companion moves
            if let Some(win) = app.get_webview_window("main") {
                let app_handle = app.handle().clone();
                win.on_window_event(move |event| {
                    if let tauri::WindowEvent::Moved(pos) = event {
                        let ah = app_handle.clone();
                        let x = pos.x;
                        let y = pos.y;
                        std::thread::spawn(move || {
                            save_position(ah, x, y);
                        });
                    }
                });
            }


            // System tray
            let show_item = MenuItem::with_id(app, "show_app", "Show App", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("OpenStudy")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show_app" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "quit" => {
                        if let Some(backend) = app.try_state::<BackendProcess>() {
                            let mut lock = backend.child.lock().unwrap();
                            if let Some(mut child) = lock.take() {
                                let _ = child.kill();
                            }
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            set_click_through,
            start_dragging,
            save_position,
            open_visualizer,
            open_dashboard,
            close_visualizer,
            minimize_window,
            maximize_window,
            toggle_fullscreen,
            close_window,
            hide_companion,
            reset_position,
            quit_app,
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(backend) = app_handle.try_state::<BackendProcess>() {
                    let mut lock = backend.child.lock().unwrap();
                    if let Some(mut child) = lock.take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
