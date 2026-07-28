# Solar System Orbit Viewer (Tauri)

_Disclaimer: This is fully vibe coded and is meant for testing._

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
