/**
 * NovaCore Shell — Electron 主窗口
 * 加载 http://localhost:8090/（FastAPI 后端）
 * 无边框 + 可缩放 + CSS 拖拽
 */
const { app, BrowserWindow, Menu, ipcMain, nativeTheme } = require('electron');
const path = require('path');
const { execSync, spawn } = require('child_process');

Menu.setApplicationMenu(null);

let win;
const WINDOW_CONTROLS_MODE = 'custom-html';

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

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    focusExistingWindow();
  });
}

// ── 启动 Python 后端（如果还没在跑） ──
function ensureBackend() {
  const net = require('net');
  return new Promise((resolve) => {
    const sock = new net.Socket();
    sock.setTimeout(1000);
    sock.on('connect', () => { sock.destroy(); resolve(true); });
    sock.on('error',   () => { sock.destroy(); resolve(false); });
    sock.on('timeout', () => { sock.destroy(); resolve(false); });
    sock.connect(8090, '127.0.0.1');
  }).then((running) => {
    if (running) {
      console.log('[shell] backend already running');
      return;
    }
    console.log('[shell] starting backend...');
    const py = spawn(
      'C:\\Program Files\\Python311\\python.exe',
      ['agent_final.py'],
      { cwd: 'C:\\Users\\36459\\NovaCore', detached: true, stdio: 'ignore' }
    );
    py.unref();
    // 等后端就绪
    return new Promise((resolve) => {
      let tries = 0;
      const check = setInterval(() => {
        const s = new net.Socket();
        s.setTimeout(500);
        s.on('connect', () => { s.destroy(); clearInterval(check); resolve(); });
        s.on('error',   () => { s.destroy(); });
        s.on('timeout', () => { s.destroy(); });
        s.connect(8090, '127.0.0.1');
        if (++tries > 30) { clearInterval(check); resolve(); } // 15s 超时
      }, 500);
    });
  });
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
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  win.loadURL('http://localhost:8090/');
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
