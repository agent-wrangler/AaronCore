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
- The current backend still expects a local Python runtime on the target machine.
- Continue editing the main app in the repo root (`shell`, `routes`, `core`, `static`, etc.); this wrapper only handles launching and packaging.
- In-app update checks are wired for packaged Windows `nsis` builds published through GitHub Releases.
- `win-unpacked` and `portable` builds remain useful for local development/distribution, but they do not act as the formal auto-update channel.
- Before publishing a new installer, bump the version in `desktop_runtime_35/package.json`; Electron auto-update compares packaged app versions.
- `.github/workflows/release-desktop.yml` provides a minimal GitHub Actions path for publishing the Windows installer to Releases.
