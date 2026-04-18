# AaronCore Desktop Runtime

This directory is the dedicated Electron desktop wrapper for AaronCore.

Development:

```powershell
cd desktop_runtime_35
npm install
npm run start
```

Packaging:

```powershell
cd desktop_runtime_35
npm install
npm run dist:portable
```

Official Windows installer release:

```powershell
cd desktop_runtime_35
npm install
npm run dist:nsis
```

Notes:

- The packaged app bundles the current AaronCore backend/source tree as `resources/aaroncore`.
- Local packaged builds now bundle a full Python runtime plus Playwright browser assets from `desktop_runtime_35/vendor_runtime`.
- The runtime prep step also merges the current user's Python site-packages into the bundled Python so packaged builds do not rely on `%APPDATA%\Python\Python311\site-packages` at runtime.
- The bundled build path does not require the target machine to preinstall Python or Playwright separately.
- Browser automation in bundled builds can start the bundled Chromium runtime first, then fall back to local Chrome, Edge, or Brave.
- `npm run prepare:runtime` syncs `C:\Program Files\Python311` and `%LOCALAPPDATA%\ms-playwright` into `desktop_runtime_35/vendor_runtime`.
- `npm run dist:nsis` and `npm run dist:portable` now build the bundled "fat" package; `npm run dist:nsis:thin` keeps the old lightweight package path for CI or fallback.
- Continue editing the main app in the repo root (`shell`, `routes`, `core`, `static`, etc.); this wrapper only handles launching and packaging.
- Packaged builds include the backend runtime support directories (`decision`, `protocols`, `storage`, `tasks`, etc.) required for packaged-only startup.
- Packaged builds now include the `workers` directory used by browser / QQ automation subprocesses.
- In-app update checks are wired for packaged Windows `nsis` builds published through GitHub Releases.
- `win-unpacked` and `portable` builds remain useful for local development/distribution, but they do not act as the formal auto-update channel.
- Installed `nsis` builds keep three layers separate:
  - program files in the chosen install folder under `AaronCore\App`
  - AaronCore business data under `%USERPROFILE%\.aaroncore`
  - Electron / Chromium shell profile under `%APPDATA%\AaronCore`
- Local `win-unpacked` and `portable` builds keep disposable state next to the executable under `Data/` so they do not trample the installed app's long-lived home.
- Packaged builds replace `brain/llm_config.local.json` with the checked-in safe template so the file exists without carrying local secrets.
- Before publishing a new installer, bump the version in `desktop_runtime_35/package.json`; Electron auto-update compares packaged app versions.
- `.github/workflows/release-desktop.yml` provides a minimal GitHub Actions path for publishing the Windows installer to Releases.
