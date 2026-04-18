/**
 * AaronCore Shell — Electron 主窗口
 * 加载 http://localhost:8090/（FastAPI 后端）
 * 无边框 + 可缩放 + CSS 拖拽
 */
const { app, BrowserWindow, Menu, ipcMain, nativeTheme, dialog, shell: electronShell, clipboard } = require('electron');
const fs = require('fs');
const path = require('path');
const net = require('net');
const { spawn, spawnSync } = require('child_process');
const {
  resolveAaronCoreDataDir,
  resolveElectronUserDataDir,
} = require('./runtime_paths');

Menu.setApplicationMenu(null);

let win;
const WINDOW_CONTROLS_MODE = 'custom-html';
const getSystemTheme = () => (nativeTheme.shouldUseDarkColors ? 'dark' : 'light');
function resolveExistingRoot(candidate) {
  if (!candidate) return '';
  try {
    const realpathSync = fs.realpathSync.native || fs.realpathSync;
    return path.resolve(realpathSync(candidate));
  } catch (_err) {
    try {
      return path.resolve(candidate);
    } catch (__err) {
      return '';
    }
  }
}

function isAaronCoreRepoRoot(candidate) {
  if (!candidate) return false;
  const required = ['agent_final.py', 'core', 'routes', 'static', 'shell', 'brain', 'state_data'];
  try {
    return required.every((name) => fs.existsSync(path.join(candidate, name)));
  } catch (_err) {
    return false;
  }
}

function resolvePackagedOverrideRoot() {
  const explicitDevRoot = process.env.AARONCORE_DEV_ROOT || process.env.NOVACORE_DEV_ROOT;
  const resolved = resolveExistingRoot(explicitDevRoot);
  return isAaronCoreRepoRoot(resolved) ? resolved : '';
}

function resolveRootDir() {
  const explicitRoot = resolveExistingRoot(process.env.AARONCORE_ROOT || process.env.NOVACORE_ROOT);
  if (explicitRoot && isAaronCoreRepoRoot(explicitRoot)) {
    return explicitRoot;
  }
  if (app.isPackaged) {
    const overrideRoot = resolvePackagedOverrideRoot();
    if (overrideRoot) return overrideRoot;
    const packagedRoot = resolveExistingRoot(path.join(process.resourcesPath, 'aaroncore'));
    if (packagedRoot && isAaronCoreRepoRoot(packagedRoot)) {
      return packagedRoot;
    }
    const legacyPackagedRoot = resolveExistingRoot(path.join(process.resourcesPath, 'novacore'));
    if (legacyPackagedRoot && isAaronCoreRepoRoot(legacyPackagedRoot)) {
      return legacyPackagedRoot;
    }
  }
  return resolveExistingRoot(path.resolve(__dirname, '..'));
}

const ROOT_DIR = resolveRootDir();
const DATA_DIR = resolveAaronCoreDataDir({
  explicitDataDir: process.env.AARONCORE_DATA_DIR || process.env.NOVACORE_DATA_DIR,
  explicitHomeDir: process.env.AARONCORE_HOME_DIR || process.env.NOVACORE_HOME_DIR,
  homeDir: app.getPath('home'),
  isPackaged: app.isPackaged,
  portableExecutableDir: process.env.PORTABLE_EXECUTABLE_DIR,
  processExecPath: process.execPath,
  productSlug: 'aaroncore',
}) || ROOT_DIR;
const USER_DATA_DIR = resolveElectronUserDataDir({
  explicitUserDataDir: process.env.AARONCORE_USER_DATA_DIR || process.env.NOVACORE_USER_DATA_DIR,
  appDataDir: app.getPath('appData'),
  isPackaged: app.isPackaged,
  dataDir: DATA_DIR,
  rootDir: ROOT_DIR,
  portableExecutableDir: process.env.PORTABLE_EXECUTABLE_DIR,
  processExecPath: process.execPath,
  productName: 'AaronCore',
});
if (USER_DATA_DIR) {
  try {
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
  } catch (_err) {
  }
  app.setPath('userData', USER_DATA_DIR);
}
process.env.AARONCORE_ROOT = ROOT_DIR;
process.env.NOVACORE_ROOT = ROOT_DIR;
process.env.AARONCORE_DATA_DIR = DATA_DIR;
process.env.NOVACORE_DATA_DIR = DATA_DIR;
process.env.AARONCORE_USER_DATA_DIR = USER_DATA_DIR;
process.env.NOVACORE_USER_DATA_DIR = USER_DATA_DIR;
const BACKEND_ENTRY = process.env.AARONCORE_BACKEND_ENTRY || process.env.NOVACORE_BACKEND_ENTRY || path.join(ROOT_DIR, 'agent_final.py');
process.env.AARONCORE_BACKEND_ENTRY = BACKEND_ENTRY;
process.env.NOVACORE_BACKEND_ENTRY = BACKEND_ENTRY;
const WINDOW_ICON = path.join(ROOT_DIR, 'static', 'icon', 'aaroncore.ico');
const BUNDLED_RUNTIME_DIR = app.isPackaged
  ? path.join(process.resourcesPath, 'aaroncore', 'runtime')
  : path.join(__dirname, 'vendor_runtime');
const BUNDLED_PYTHON = path.join(BUNDLED_RUNTIME_DIR, 'python', 'python.exe');
const BUNDLED_PLAYWRIGHT_BROWSERS = path.join(BUNDLED_RUNTIME_DIR, 'ms-playwright');
const LOCAL_PYTHON = 'C:\\Program Files\\Python311\\python.exe';
const BACKEND_PORT = 8090;
const LOG_DIR = path.join(DATA_DIR, 'logs');
const SHELL_LOG_FILE = path.join(LOG_DIR, 'desktop_shell.log');
const BACKEND_OUT_LOG_FILE = path.join(LOG_DIR, 'desktop_backend.out.log');
const BACKEND_ERR_LOG_FILE = path.join(LOG_DIR, 'desktop_backend.err.log');
const MIN_PYTHON_MAJOR = 3;
const MIN_PYTHON_MINOR = 10;
const REQUIRED_PYTHON_MODULES = ['fastapi', 'uvicorn', 'requests', 'playwright'];

if (fs.existsSync(BUNDLED_PLAYWRIGHT_BROWSERS)) {
  process.env.PLAYWRIGHT_BROWSERS_PATH = BUNDLED_PLAYWRIGHT_BROWSERS;
}
if (fs.existsSync(BUNDLED_PYTHON)) {
  process.env.PYTHONNOUSERSITE = '1';
}

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

function buildPythonCandidates() {
  const candidates = [];
  const pushCandidate = (command, argsPrefix, label) => {
    if (!command) return;
    candidates.push({
      command,
      argsPrefix: Array.isArray(argsPrefix) ? argsPrefix : [],
      label: label || [command].concat(argsPrefix || []).join(' '),
    });
  };

  if (fs.existsSync(BUNDLED_PYTHON)) {
    pushCandidate(BUNDLED_PYTHON, [], 'bundled python');
  }
  if (process.env.AARONCORE_PYTHON) {
    pushCandidate(process.env.AARONCORE_PYTHON, [], 'AARONCORE_PYTHON');
  }
  if (process.env.NOVACORE_PYTHON) {
    pushCandidate(process.env.NOVACORE_PYTHON, [], 'NOVACORE_PYTHON');
  }
  if (process.platform === 'win32') {
    if (fs.existsSync(LOCAL_PYTHON)) {
      pushCandidate(LOCAL_PYTHON, [], LOCAL_PYTHON);
    }
    pushCandidate('py', ['-3.11'], 'py -3.11');
    pushCandidate('py', ['-3'], 'py -3');
  }
  pushCandidate('python', [], 'python');
  pushCandidate('python3', [], 'python3');

  const seen = new Set();
  return candidates.filter((candidate) => {
    const key = `${candidate.command} ${candidate.argsPrefix.join(' ')}`.trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function runCommandCapture(command, args, timeoutMs = 10000) {
  try {
    return spawnSync(command, args, {
      encoding: 'utf8',
      windowsHide: true,
      timeout: timeoutMs,
    });
  } catch (error) {
    return { error, status: -1, stdout: '', stderr: '' };
  }
}

function parsePythonVersion(versionText) {
  const match = /Python\s+(\d+)\.(\d+)(?:\.(\d+))?/i.exec(String(versionText || ''));
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3] || 0),
    text: `Python ${match[1]}.${match[2]}${match[3] ? `.${match[3]}` : ''}`,
  };
}

function isSupportedPythonVersion(version) {
  if (!version) return false;
  if (version.major > MIN_PYTHON_MAJOR) return true;
  if (version.major < MIN_PYTHON_MAJOR) return false;
  return version.minor >= MIN_PYTHON_MINOR;
}

function quoteCommandPart(value) {
  const text = String(value || '');
  if (!text) return '""';
  return /\s/.test(text) ? `"${text}"` : text;
}

function getPipInstallCommand(candidate, modules) {
  return [candidate.command]
    .concat(candidate.argsPrefix || [], ['-m', 'pip', 'install'])
    .concat(modules || [])
    .map(quoteCommandPart)
    .join(' ');
}

function readRecentLogTail(logFile, maxLines = 8) {
  try {
    if (!fs.existsSync(logFile)) return '';
    const text = fs.readFileSync(logFile, 'utf8').trim();
    if (!text) return '';
    return text.split(/\r?\n/).slice(-maxLines).join('\n');
  } catch (_error) {
    return '';
  }
}

function detectPythonRuntime() {
  const candidates = buildPythonCandidates();
  let firstTooOld = null;
  let bestMissingPackages = null;

  for (const candidate of candidates) {
    const versionCheck = runCommandCapture(candidate.command, candidate.argsPrefix.concat(['--version']));
    if (versionCheck.error || versionCheck.status !== 0) {
      continue;
    }

    const versionText = `${versionCheck.stdout || ''} ${versionCheck.stderr || ''}`.trim();
    const version = parsePythonVersion(versionText);
    if (version && !isSupportedPythonVersion(version)) {
      if (!firstTooOld) {
        firstTooOld = { status: 'python_too_old', candidate, versionText, version, candidates };
      }
      continue;
    }

    const moduleProbeScript = [
      'import importlib.util, json',
      `modules = ${JSON.stringify(REQUIRED_PYTHON_MODULES)}`,
      'missing = [name for name in modules if importlib.util.find_spec(name) is None]',
      'print(json.dumps({"missing": missing}))',
    ].join('; ');
    const moduleCheck = runCommandCapture(
      candidate.command,
      candidate.argsPrefix.concat(['-c', moduleProbeScript]),
    );
    if (moduleCheck.error || moduleCheck.status !== 0) {
      continue;
    }

    let missingModules = [];
    try {
      const payload = JSON.parse(String(moduleCheck.stdout || '').trim() || '{}');
      if (Array.isArray(payload.missing)) {
        missingModules = payload.missing.map((item) => String(item || '').trim()).filter(Boolean);
      }
    } catch (_error) {
      continue;
    }

    if (!missingModules.length) {
      return { status: 'ok', candidate, versionText, version, candidates };
    }

    if (!bestMissingPackages || missingModules.length < bestMissingPackages.missingModules.length) {
      bestMissingPackages = {
        status: 'missing_packages',
        candidate,
        versionText,
        version,
        missingModules,
        installCommand: getPipInstallCommand(candidate, missingModules),
        candidates,
      };
    }
  }

  if (bestMissingPackages) return bestMissingPackages;
  if (firstTooOld) return firstTooOld;
  return { status: 'missing_python', candidates };
}

async function showStartupProblem(problem) {
  const checkedCandidates = (problem.candidates || buildPythonCandidates())
    .map((candidate) => `- ${candidate.label}`)
    .join('\n');

  if (problem.status === 'missing_python') {
    const result = await dialog.showMessageBox({
      type: 'error',
      buttons: ['Open Python Download', 'Close'],
      defaultId: 0,
      cancelId: 1,
      noLink: true,
      title: 'AaronCore needs Python',
      message: 'AaronCore could not find a usable Python runtime on this computer.',
      detail: [
        `Install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ and reopen AaronCore.`,
        'Python 3.11 is preferred for the current desktop runtime.',
        '',
        'Checked:',
        checkedCandidates || '- python',
      ].join('\n'),
    });
    if (result.response === 0) {
      electronShell.openExternal('https://www.python.org/downloads/windows/');
    }
    return;
  }

  if (problem.status === 'python_too_old') {
    const result = await dialog.showMessageBox({
      type: 'error',
      buttons: ['Open Python Download', 'Close'],
      defaultId: 0,
      cancelId: 1,
      noLink: true,
      title: 'AaronCore needs a newer Python',
      message: 'AaronCore found Python, but the version is too old for this backend.',
      detail: [
        `Detected: ${problem.versionText || problem.candidate.label}`,
        `Required: Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+`,
        '',
        `Interpreter: ${problem.candidate.label}`,
      ].join('\n'),
    });
    if (result.response === 0) {
      electronShell.openExternal('https://www.python.org/downloads/windows/');
    }
    return;
  }

  if (problem.status === 'missing_packages') {
    const result = await dialog.showMessageBox({
      type: 'error',
      buttons: ['Copy Install Command', 'Open Logs Folder', 'Close'],
      defaultId: 0,
      cancelId: 2,
      noLink: true,
      title: 'AaronCore backend packages are missing',
      message: 'Python is installed, but AaronCore is missing required backend packages.',
      detail: [
        `Interpreter: ${problem.candidate.label}`,
        problem.versionText ? `Version: ${problem.versionText}` : '',
        `Missing packages: ${problem.missingModules.join(', ')}`,
        '',
        'Run this command in a terminal, then reopen AaronCore:',
        problem.installCommand,
      ].filter(Boolean).join('\n'),
    });
    if (result.response === 0) {
      clipboard.writeText(problem.installCommand);
    } else if (result.response === 1) {
      electronShell.openPath(LOG_DIR);
    }
    return;
  }

  if (problem.status === 'backend_failed') {
    const recentError = readRecentLogTail(BACKEND_ERR_LOG_FILE, 10);
    const result = await dialog.showMessageBox({
      type: 'error',
      buttons: ['Open Logs Folder', 'Close'],
      defaultId: 0,
      cancelId: 1,
      noLink: true,
      title: 'AaronCore backend failed to start',
      message: 'AaronCore found Python, but the backend did not start successfully.',
      detail: [
        problem.runtime && problem.runtime.candidate ? `Interpreter: ${problem.runtime.candidate.label}` : '',
        problem.runtime && problem.runtime.versionText ? `Version: ${problem.runtime.versionText}` : '',
        `Expected local URL: http://localhost:${BACKEND_PORT}/`,
        '',
        `Log folder: ${LOG_DIR}`,
        recentError ? '' : '',
        recentError ? 'Recent error output:' : '',
        recentError || '',
      ].filter(Boolean).join('\n'),
    });
    if (result.response === 0) {
      electronShell.openPath(LOG_DIR);
    }
  }
}

function emitWindowState() {
  if (!win || win.isDestroyed()) return;
  win.webContents.send('window-state', {
    maximized: win.isMaximized(),
    fullscreen: win.isFullScreen(),
  });
}

function emitSystemTheme() {
  if (!win || win.isDestroyed()) return;
  win.webContents.send('system-theme', {
    theme: getSystemTheme(),
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
    app.setAppUserModelId('com.aaroncore.desktop');
  }
  app.on('second-instance', () => {
    focusExistingWindow();
  });
}

// ── 启动 Python 后端：每次先结束旧的 AaronCore 后端，再启动当前源码版本 ──
async function ensureBackend() {
  console.log('[shell] restarting backend...');
  const runtime = detectPythonRuntime();
  if (runtime.status !== 'ok') {
    await showStartupProblem(runtime);
    return false;
  }

  stopExistingBackend();
  await waitForBackendState(false, 20, 250);

  const backendStdoutFd = openBackendLogFd(BACKEND_OUT_LOG_FILE);
  const backendStderrFd = openBackendLogFd(BACKEND_ERR_LOG_FILE);
  let spawnError = null;
  const py = spawn(
    runtime.candidate.command,
    runtime.candidate.argsPrefix.concat([BACKEND_ENTRY]),
    {
      cwd: ROOT_DIR,
      detached: true,
      windowsHide: true,
      stdio: ['ignore', backendStdoutFd, backendStderrFd],
    }
  );
  py.once('error', (error) => {
    spawnError = error;
  });
  py.unref();

  await sleep(250);
  if (spawnError) {
    console.warn('[shell] backend spawn failed:', spawnError.message);
    await showStartupProblem({ status: 'backend_failed', runtime });
    return false;
  }

  const ready = await waitForBackendState(true, 30, 500);
  if (!ready) {
    console.warn('[shell] backend did not become ready on port', BACKEND_PORT);
    console.warn('[shell] backend logs:', BACKEND_OUT_LOG_FILE, BACKEND_ERR_LOG_FILE);
    await showStartupProblem({ status: 'backend_failed', runtime });
    return false;
  }
  return true;
}

// ── 创建主窗口 ──
function createWindow() {
  const { screen } = require('electron');
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;
  const ww = 1100, wh = 900;

  nativeTheme.themeSource = 'system';
  const getWindowPalette = (theme) => ({
    backgroundColor: theme === 'dark' ? '#161618' : '#ffffff',
    overlayColor: theme === 'dark' ? '#161618' : '#ffffff',
    symbolColor: theme === 'dark' ? '#ebebf0' : '#334155',
  });
  const palette = getWindowPalette(getSystemTheme());

  win = new BrowserWindow({
    width: ww,
    height: wh,
    x: Math.round((sw - ww) / 2),
    y: Math.round((sh - wh) / 2),
    frame: false,
    transparent: false,
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
  win.webContents.on('did-finish-load', () => {
    emitWindowState();
    emitSystemTheme();
  });
  win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    console.log('[renderer]', `level=${level}`, String(message || ''), `at ${sourceId || 'unknown'}:${line || 0}`);
  });
  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    console.error('[renderer] did-fail-load', errorCode, errorDescription, validatedURL);
  });
  win.webContents.on('render-process-gone', (_event, details) => {
    console.error('[renderer] render-process-gone', JSON.stringify(details || {}));
  });
  win.webContents.on('unresponsive', () => {
    console.warn('[renderer] window unresponsive');
  });

  // 标题栏双击最大化/还原（无边框窗口需要手动处理）
  win.on('page-title-updated', (e) => e.preventDefault());
  win.on('maximize', emitWindowState);
  win.on('unmaximize', emitWindowState);
  win.on('enter-full-screen', emitWindowState);
  win.on('leave-full-screen', emitWindowState);

  // 主题切换时同步系统主题
  ipcMain.on('win-theme', (_, theme) => {
    if (!win) return;
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

nativeTheme.on('updated', () => {
  emitSystemTheme();
});

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
ipcMain.handle('win-get-system-theme', () => getSystemTheme());

// ── 启动 ──
app.whenReady().then(async () => {
  if (!gotSingleInstanceLock) {
    return;
  }
  const ready = await ensureBackend();
  if (!ready) {
    app.quit();
    return;
  }
  createWindow();
});

app.on('window-all-closed', () => {
  app.quit();
});
