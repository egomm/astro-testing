# Solar System Orbit Viewer — Tauri build

**Now on Tauri v2** (v1 was migrated: `Cargo.toml`/`package.json` bumped to
v2, `tauri.conf.json` converted to the v2 schema, and a `src-tauri/capabilities/default.json`
permissions file was added since v2 requires explicit capabilities instead
of v1's allowlist). If you'd already set up a repo from the earlier v1 zip,
just overwrite these files with the ones in this zip:
`src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`,
`package.json`, `.github/workflows/build.yml`.

I could NOT produce the .exe directly, because this sandbox has no Rust
toolchain and no network access (both required to install Rust/Tauri deps
and cross-compile a Windows binary). What's here is a complete, ready-to-go
Tauri project — building it into an .exe on your own Windows machine takes
about 2 minutes once prerequisites are installed.

## What you're getting
- `dist/index.html` — the full app (3D solar system, Three.js, real
  Keplerian orbital elements, time controls, drag-to-orbit camera). This is
  the exact same file as `orbit-viewer-demo.html` I sent separately, which
  you can already open directly in a browser to test the concept with zero
  setup.
- `src-tauri/` — minimal Rust/Tauri wrapper that just loads that HTML in a
  native window. No custom Rust logic needed for this feasibility version.

## Build steps (Windows)

1. Install prerequisites (one-time):
   - Rust: https://rustup.rs
   - Node.js (18+): https://nodejs.org
   - Microsoft C++ Build Tools + WebView2 (Tauri installer checks/prompts
     for these automatically): https://tauri.app/v1/guides/getting-started/prerequisites

2. From this project folder:
   ```
   npm install
   npm run tauri build
   ```

3. The installer/exe appears under:
   ```
   src-tauri/target/release/bundle/nsis/Solar System Orbit Viewer_0.1.0_x64-setup.exe
   src-tauri/target/release/bundle/msi/Solar System Orbit Viewer_0.1.0_x64_en-US.msi
   ```
   There's also a plain standalone exe (no installer) at:
   ```
   src-tauri/target/release/orbit-viewer.exe
   ```

## Building all three platforms via GitHub Actions (no local toolchain needed)

This project includes `.github/workflows/build.yml`, which builds Windows,
macOS (universal), and Linux binaries in parallel on GitHub's servers and
attaches them to a draft GitHub Release.

1. Push this project to a new GitHub repo (see steps in chat).
2. Tag a commit and push the tag, e.g.:
   ```
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. Go to the repo's **Actions** tab and watch the `build` workflow run
   (~10-15 min for all three platforms).
4. When it finishes, go to **Releases** — there's a draft release with:
   - `...x64-setup.exe` / `...x64_en-US.msi` (Windows)
   - `...universal.dmg` (macOS, Intel + Apple Silicon)
   - `...amd64.deb` / `...AppImage` (Linux)
5. Edit the draft release and click **Publish** when you're ready to share it.

You can also trigger the workflow manually (no tag needed) from the Actions
tab via "Run workflow" — useful for testing before you're ready to tag a
release.


## Build steps (macOS)

1. Install prerequisites (one-time):
   - Xcode Command Line Tools: `xcode-select --install`
   - Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
   - Node.js (18+): https://nodejs.org or `brew install node`
2. From this project folder: `npm install && npm run tauri build`
3. Output:
   ```
   src-tauri/target/release/bundle/macos/Solar System Orbit Viewer.app
   src-tauri/target/release/bundle/dmg/Solar System Orbit Viewer_0.1.0_aarch64.dmg
   ```
   Builds for whichever chip you're on. For a universal (Intel + Apple
   Silicon) build: `npm run tauri build -- --target universal-apple-darwin`
   (after `rustup target add aarch64-apple-darwin x86_64-apple-darwin`).

## Build steps (Linux)

1. Install prerequisites (one-time, Debian/Ubuntu example — this project
   pins Tauri v2, which needs the **4.1** webkit stack, not 4.0):
   ```
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   sudo apt-get update
   sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential curl wget file \
     libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev
   ```
   Plus Node.js (18+) via your package manager or https://nodejs.org.
2. From this project folder: `npm install && npm run tauri build`
3. Output:
   ```
   src-tauri/target/release/orbit-viewer                    (standalone binary)
   src-tauri/target/release/bundle/deb/...deb
   src-tauri/target/release/bundle/appimage/...AppImage
   ```

## Notes on the simulation itself
- Planet positions come from **astronomy-engine** (github.com/cosinekitty/astronomy),
  a real, actively-maintained ephemeris library — not hand-rolled two-body
  Kepler math. It's loaded client-side from jsDelivr's CDN copy of the npm
  package, so an internet connection is needed the first time the app opens
  (there's an on-screen message if that load fails).
- Distances are scaled with sqrt(a) so all 8 planets fit on screen at once;
  planet *sizes* are exaggerated (not to scale) so they're visible — same
  trick the reference screenshot's app uses. Eccentricity/inclination shown
  in the click-for-details panel are static reference values for display
  only; they aren't used to compute positions.
- If you'd rather bundle the ephemeris instead of loading it from a CDN
  (e.g. for a fully offline build), vendor `astronomy.browser.min.js` from
  the astronomy-engine GitHub repo into `dist/` and swap the `<script src>`
  tag in `dist/index.html` for a local path.

## Feasibility verdict
This is very feasible. The whole thing is ~400 lines of vanilla JS/Three.js
running in Tauri's webview — no heavy dependencies, no native 3D code
needed, small binary (~5-10MB), fast to iterate on. The main cost driver
for a "real" version would be polish (better textures/lighting, moons,
asteroid belt, more accurate ephemeris) rather than architecture risk.
