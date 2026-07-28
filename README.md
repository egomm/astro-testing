# Solar System Orbit Viewer - Tauri + REBOUND (local Python sidecar)
_This "project" is entirely vibe coded for testing purposes._

## Architecture

```
Tauri (native window, small installer, Rust shell)
   └─ spawns a bundled Python executable as a sidecar process
        (Flask server + REBOUND, bound to 127.0.0.1 only)
   └─ webview loads dist/index.html (Three.js frontend)
   └─ JS fetches planet positions from the local Python server
```

Unlike the earlier astronomy-engine version, planet positions here come
from **real gravitational N-body integration** (REBOUND), not an analytic
ephemeris curve. Initial conditions (position + velocity per planet at
J2000) are derived from standard osculating orbital elements via normal
two-body orbital mechanics, then REBOUND integrates the Sun + 8 planets
forward/backward under mutual gravity - so planet-planet perturbations are
physically simulated rather than looked up.

I could not test-run this exact pipeline in my own sandbox (no network
access there to `pip install rebound`, which needs to compile a C
extension, or to run PyInstaller). The code is structurally correct, but
budget for a round or two of CI debugging the first time you run it -
that's been true of every step of this project so far, not unique to this
version.

## What changed from the pure-JS version

- **New**: `sidecar/server.py` - the Flask + REBOUND backend.
- **New**: `src-tauri/binaries/` - where CI drops the frozen Python
  executable before `tauri build` runs (empty in this zip; CI populates it).
- **Changed**: `src-tauri/src/main.rs` - now spawns the sidecar on startup
  via `tauri-plugin-shell`, and writes its stdout/stderr (plus its own
  startup/shutdown events and any Rust panics) to a log file, since release
  builds have no attached console to print to. Log file location:
  `<OS temp dir>/orbit-viewer-logs/orbit-viewer.log` (overwritten fresh each
  launch). Also kills the sidecar when the window closes.
- **Changed**: `src-tauri/Cargo.toml` - added `tauri-plugin-shell`.
- **Changed**: `src-tauri/tauri.conf.json` - added `bundle.externalBin`
  (registers the sidecar) and `connect-src http://127.0.0.1:51733` in the
  CSP (without this, the webview would silently block the fetch calls).
- **Changed**: `dist/index.html` - now fetches from the local server
  instead of computing positions in JS. Orbit-path guide lines and current
  planet positions are both server-sourced. Includes a startup screen that
  polls `/health` until the sidecar is ready (frozen Python + Flask can
  take a second or two to spin up, especially the first launch after
  install).
- **Changed**: `.github/workflows/build.yml` - now sets up Python, installs
  `sidecar/requirements.txt`, freezes the server with PyInstaller, and
  copies the result into `src-tauri/binaries/orbit-server-<target-triple>`
  (the exact naming Tauri's sidecar mechanism requires) before building.

## Manual build (any OS)

The steps below are in addition to whatever Rust/Node/Tauri prerequisites
you already have set up from the earlier version of this project (Rust,
Node 18+, plus the OS-specific Tauri v2 system packages - webkit2gtk-4.1 +
friends on Linux, Xcode CLT on macOS, VS Build Tools + WebView2 on Windows).

1. Install Python 3.10+ and pip.
2. From the project root:
   ```
   pip install -r sidecar/requirements.txt
   ```
3. Locate the compiled `librebound` extension (it installs as a top-level
   file next to the `rebound` package, not inside it) and pass it to
   PyInstaller explicitly, since `--collect-all rebound` alone misses it -
   see "Known risk areas" below for why:
   ```
   # macOS/Linux
   LIBREBOUND=$(python -c "import glob, os, rebound; d = os.path.dirname(rebound.__file__); print(glob.glob(os.path.join(d, '..', 'librebound*'))[0])")
   pyinstaller --onefile --name orbit-server --collect-all rebound \
     --add-binary "${LIBREBOUND}:." --distpath sidecar/dist sidecar/server.py

   # Windows (PowerShell)
   $LIBREBOUND = python -c "import glob, os, rebound; d = os.path.dirname(rebound.__file__); print(glob.glob(os.path.join(d, '..', 'librebound*'))[0])"
   pyinstaller --onefile --name orbit-server --collect-all rebound `
     --add-binary "$LIBREBOUND;." --distpath sidecar/dist sidecar/server.py
   ```
4. Copy the frozen binary into `src-tauri/binaries/` with the exact name
   Tauri expects for your platform (find your triple with `rustc -Vv` -
   look for `host:`):
   ```
   # Windows example
   mkdir src-tauri\binaries
   copy sidecar\dist\orbit-server.exe src-tauri\binaries\orbit-server-x86_64-pc-windows-msvc.exe

   # macOS Apple Silicon example
   mkdir -p src-tauri/binaries
   cp sidecar/dist/orbit-server src-tauri/binaries/orbit-server-aarch64-apple-darwin
   chmod +x src-tauri/binaries/orbit-server-aarch64-apple-darwin

   # Linux example
   mkdir -p src-tauri/binaries
   cp sidecar/dist/orbit-server src-tauri/binaries/orbit-server-x86_64-unknown-linux-gnu
   chmod +x src-tauri/binaries/orbit-server-x86_64-unknown-linux-gnu
   ```
4. `npm install && npm run tauri build` as before.

## GitHub Actions (recommended path)

Same as before - push a tag (`git tag v0.2.0 && git push origin v0.2.0`) or
use "Run workflow" in the Actions tab. The workflow now handles the Python
freeze + sidecar placement automatically for all three OSes before running
the Tauri build, and attaches everything to a draft Release as before.

## Known risk areas / things to sanity-check first

- **REBOUND's compiled library under PyInstaller.** This bit on the first
  real build, twice. REBOUND loads its `librebound` shared library via
  `ctypes` at import time (`os.path.dirname(__file__) + "/../librebound" +
  suffix`) rather than as a normal Python extension module, so
  PyInstaller's static import analysis misses it entirely - `--collect-all
  rebound` alone doesn't fix this, because that library also isn't inside
  the `rebound` package folder in the first place. `setup.py` installs it
  as a separate top-level extension module (`librebound.<tag>.so` / `.pyd`
  / `.dylib`) that sits next to the `rebound/` folder in site-packages, and
  `--collect-all rebound` only walks files inside the package folder
  itself, so it never picks up that sibling file. Fixed by locating the
  compiled file explicitly and passing it to PyInstaller with
  `--add-binary` so it lands at the bundle root, where REBOUND's
  `../librebound<suffix>` lookup finds it the same way it would in a normal
  install - see the workflow and manual build steps above.
- **Antivirus false positives.** PyInstaller one-file executables
  frequently get flagged by Windows Defender and others. If the Windows
  build gets quarantined/deleted post-download, that's why - not a bug in
  this code. Switching PyInstaller to `--onedir` mode instead of
  `--onefile` is the usual fix if this becomes a real blocker.
- **Startup latency.** Expect ~1-3 extra seconds versus the pure-JS
  version while the frozen Python interpreter boots and Flask starts
  listening - this is what the startup overlay in the frontend is for.
- **Bundle size.** This version will be tens of MB larger than the
  astronomy-engine version, since it now ships an entire Python runtime
  plus REBOUND's compiled library, not just a webview pointed at a small
  HTML file.
- **Performance on far-future/past dates.** Each `/positions` request
  currently re-integrates from J2000 from scratch (simple and safe for
  concurrent requests, but means requesting a date millennia away takes
  proportionally longer). Fine for the intended date range of this viewer;
  a long-lived `Simulation` object that steps incrementally would be the
  next optimization if you want smooth scrubbing across huge time spans.
