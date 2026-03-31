/**
 * NovaCore Shell — Electron 主窗口
 * 加载 http://localhost:8090/（FastAPI 后端）
 * 无边框 + 可缩放 + CSS 拖拽
 */
const { app, BrowserWindow, Menu, ipcMain, nativeTheme } = require('electron');
const fs = require('fs');
const path = require('path');
const net = require('net');
const { spawn, spawnSync } = require('child_process');

Menu.setApplicationMenu(null);

let win;
const WINDOW_CONTROLS_MODE = 'custom-html';
const ROOT_DIR = process.env.NOVACORE_ROOT || path.resolve(__dirname, '..');
const BACKEND_ENTRY = process.env.NOVACORE_BACKEND_ENTRY || path.join(ROOT_DIR, 'agent_final.py');
const WINDOW_ICON = path.join(ROOT_DIR, 'static', 'icon', 'nova.ico');
const LOCAL_PYTHON = 'C:\\Program Files\\Python311\\python.exe';
const BACKEND_PORT = 8090;
const LOG_DIR = path.join(ROOT_DIR, 'logs');
const SHELL_LOG_FILE = path.join(LOG_DIR, 'desktop_shell.log');
const BACKEND_OUT_LOG_FILE = path.join(LOG_DIR, 'desktop_backend.out.log');
const BACKEND_ERR_LOG_FILE = path.join(LOG_DIR, 'desktop_backend.err.log');

function ensureLogDir() {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
  } catch (_err) {
  }
}

function appendShellLog(level, args) {
  ensureLogDir();
  try {
    const rendered = args
      .map((item) => {
        if (item instanceof Error) return item.stack || item.message;
        if (typeof item === 'string') return item;
        try {
          return JSON.stringify(item);
        } catch (_err) {
          return String(item);
        }
      })
      .join(' ');
    fs.appendFileSync(
      SHELL_LOG_FILE,
      `[${new Date().toISOString()}] [${level}] ${rendered}\n`,
      'utf8',
    );
  } catch (_err) {
  }
}

const _consoleLog = console.log.bind(console);
const _consoleWarn = console.warn.bind(console);
const _consoleError = console.error.bind(console);
console.log = (...args) => {
  appendShellLog('INFO', args);
  _consoleLog(...args);
};
console.warn = (...args) => {
  appendShellLog('WARN', args);
  _consoleWarn(...args);
};
console.error = (...args) => {
  appendShellLog('ERROR', args);
  _consoleError(...args);
};

function openBackendLogFd(logFile) {
  ensureLogDir();
  return fs.openSync(logFile, 'a');
}

function resolvePythonCommand() {
  if (process.env.NOVACORE_PYTHON) return process.env.NOVACORE_PYTHON;
  if (process.platform === 'win32' && fs.existsSync(LOCAL_PYTHON)) return LOCAL_PYTHON;
  return 'python';
}

function emitWindowState() {
  if (!win || win.isDestroyed()) return;
  win.webContents.send('window-state', {
    maximized: win.isMaximized(),
    fullscreen: win.isFullScreen(),
  });
}

function focusExistingWindow() {
  if (!win) return;
  if (win.isMinimized()) {
    win.restore();
  }
  if (!win.isVisible()) {
    win.show();
  }
  win.focus();
}

function escapePowerShell(value) {
  return String(value || "").replace(/'/g, "''");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isBackendListening() {
  return new Promise((resolve) => {
    const sock = new net.Socket();
    sock.setTimeout(1000);
    sock.on('connect', () => { sock.destroy(); resolve(true); });
    sock.on('error', () => { sock.destroy(); resolve(false); });
    sock.on('timeout', () => { sock.destroy(); resolve(false); });
    sock.connect(BACKEND_PORT, '127.0.0.1');
  });
}

async function waitForBackendState(shouldBeUp, maxAttempts = 30, delayMs = 500) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const listening = await isBackendListening();
    if (listening === shouldBeUp) return true;
    await sleep(delayMs);
  }
  return false;
}

function stopExistingBackend() {
  if (process.platform !== 'win32') return [];

  const backendPath = BACKEND_ENTRY.replace(/\//g, '\\');
  const rootPath = ROOT_DIR.replace(/\//g, '\\');
  const script = `
$backend = '${escapePowerShell(backendPath)}'
$root = '${escapePowerShell(rootPath)}'
$killed = @()
Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and
  $_.CommandLine -and (
    $_.CommandLine.Replace('/', '\\').Contains($backend) -or
    ($_.CommandLine.Replace('/', '\\').Contains('agent_final.py') -and $_.CommandLine.Replace('/', '\\').Contains($root))
  )
} | ForEach-Object {
  try {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    $killed += [string]$_.ProcessId
  } catch {
  }
}
$killed -join ','
`.trim();

  const result = spawnSync('powershell.exe', ['-NoProfile', '-Command', script], {
    encoding: 'utf8',
    windowsHide: true,
  });

  if (result.error) {
    console.warn('[shell] failed to stop old backend:', result.error.message);
    return [];
  }
  if (result.status !== 0 && result.stderr) {
    console.warn('[shell] backend stop stderr:', result.stderr.trim());
  }

  const killed = String(result.stdout || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  if (killed.length) {
    console.log('[shell] stopped old backend pids:', killed.join(', '));
  }
  return killed;
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  if (process.platform === 'win32') {
    app.setAppUserModelId('com.novacore.desktop');
  }
  app.on('second-instance', () => {
    focusExistingWindow();
  });
}

// ── 启动 Python 后端：每次先结束旧的 NovaCore 后端，再启动当前源码版本 ──
async function ensureBackend() {
  console.log('[shell] restarting backend...');
  stopExistingBackend();
  await waitForBackendState(false, 20, 250);

  const pythonCommand = resolvePythonCommand();
  const backendStdoutFd = openBackendLogFd(BACKEND_OUT_LOG_FILE);
  const backendStderrFd = openBackendLogFd(BACKEND_ERR_LOG_FILE);
  const py = spawn(
    pythonCommand,
    [BACKEND_ENTRY],
    {
      cwd: ROOT_DIR,
      detached: true,
      windowsHide: true,
      stdio: ['ignore', backendStdoutFd, backendStderrFd],
    }
  );
  py.unref();

  const ready = await waitForBackendState(true, 30, 500);
  if (!ready) {
    console.warn('[shell] backend did not become ready on port', BACKEND_PORT);
    console.warn('[shell] backend logs:', BACKEND_OUT_LOG_FILE, BACKEND_ERR_LOG_FILE);
  }
}

// ── 创建主窗口 ──
function createWindow() {
  const { screen } = require('electron');
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
  const ww = 1100, wh = 900;

  nativeTheme.themeSource = 'light';
  const getWindowPalette = (theme) => ({
    backgroundColor: theme === 'dark' ? '#00161618' : '#00ffffff',
    overlayColor: theme === 'dark' ? '#161618' : '#ffffff',
    symbolColor: theme === 'dark' ? '#ebebf0' : '#334155',
  });
  const palette = getWindowPalette('light');

  win = new BrowserWindow({
    width: ww,
    height: wh,
    x: Math.round((sw - ww) / 2),
    y: Math.round((sh - wh) / 2),
    frame: false,
    transparent: true,
    roundedCorners: true,
    thickFrame: true,
    ...(WINDOW_CONTROLS_MODE === 'native-overlay' ? {
      titleBarOverlay: {
        color: palette.overlayColor,
        symbolColor: palette.symbolColor,
        height: 60,
      },
    } : {}),
    hasShadow: true,
    resizable: true,
    minWidth: 800,
    minHeight: 600,
    backgroundColor: palette.backgroundColor,
    icon: fs.existsSync(WINDOW_ICON) ? WINDOW_ICON : undefined,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.loadURL(`http://localhost:${BACKEND_PORT}/`);
  win.webContents.on('did-finish-load', emitWindowState);

  // 标题栏双击最大化/还原（无边框窗口需要手动处理）
  win.on('page-title-updated', (e) => e.preventDefault());
  win.on('maximize', emitWindowState);
  win.on('unmaximize', emitWindowState);
  win.on('enter-full-screen', emitWindowState);
  win.on('leave-full-screen', emitWindowState);

  // 主题切换时同步系统主题
  ipcMain.on('win-theme', (_, theme) => {
    if (!win) return;
    nativeTheme.themeSource = theme === 'dark' ? 'dark' : 'light';
    const nextPalette = getWindowPalette(theme);
    if (typeof win.setBackgroundColor === 'function') {
      win.setBackgroundColor(nextPalette.backgroundColor);
    }
    if (WINDOW_CONTROLS_MODE === 'native-overlay' && typeof win.setTitleBarOverlay === 'function') {
      win.setTitleBarOverlay({
        color: nextPalette.overlayColor,
        symbolColor: nextPalette.symbolColor,
        height: 60,
      });
    }
  });

  win.on('closed', () => { win = null; });
}

// ── IPC：窗口控制 ──
ipcMain.on('win-minimize', () => { if (win) win.minimize(); });
ipcMain.on('win-maximize', () => {
  if (!win) return;
  win.isMaximized() ? win.unmaximize() : win.maximize();
});
ipcMain.on('win-close', () => { if (win) win.close(); });
ipcMain.on('win-drag-by', (_, dx, dy) => {
  if (!win || win.isMaximized()) return;
  const [x, y] = win.getPosition();
  win.setPosition(x + dx, y + dy);
});

// ── 启动 ──
app.whenReady().then(async () => {
  if (!gotSingleInstanceLock) {
    return;
  }
  await ensureBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  app.quit();
});
