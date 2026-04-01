# Electron Shell Source

`shell/` contains the actual Electron shell source used by NovaCore desktop.

Responsibilities:

- create the BrowserWindow
- restart and monitor the Python backend on port `8090`
- load `http://localhost:8090/`
- manage preload and desktop window behavior

This directory is launched by `/desktop_runtime_35/main.js`.
