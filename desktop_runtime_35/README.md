# AaronCore Desktop Runtime

This directory is the dedicated Electron desktop wrapper for AaronCore.

Development:

```powershell
cd C:\Users\36459\NovaCore\desktop_runtime_35
npm install
npm run start
```

Packaging:

```powershell
cd C:\Users\36459\NovaCore\desktop_runtime_35
npm install
npm run dist:portable
```

Notes:

- The packaged app bundles the current AaronCore backend/source tree as `resources/novacore`.
- The current backend still expects a local Python runtime on the target machine.
- Continue editing the main app in the repo root (`shell`, `routes`, `core`, `static`, etc.); this wrapper only handles launching and packaging.
