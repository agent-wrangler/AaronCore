const fs = require('fs');
const path = require('path');
const { app, dialog } = require('electron');
const {
  resolveAaronCoreDataDir,
  resolveElectronUserDataDir,
  resolvePackagedDataDir,
} = require(
  app.isPackaged
    ? path.join(process.resourcesPath, 'aaroncore', 'shell', 'runtime_paths.js')
    : path.join(__dirname, '..', 'shell', 'runtime_paths.js')
);

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

function resolveAaronCoreRoot() {
  const explicitRoot = resolveExistingRoot(process.env.AARONCORE_ROOT || process.env.NOVACORE_ROOT);
  if (isAaronCoreRepoRoot(explicitRoot)) return explicitRoot;
  if (app.isPackaged) {
    const overrideRoot = resolvePackagedOverrideRoot();
    if (overrideRoot) return overrideRoot;
    const packagedAaronCore = path.join(process.resourcesPath, 'aaroncore');
    if (isAaronCoreRepoRoot(packagedAaronCore)) return packagedAaronCore;
    const legacyPackagedRoot = path.join(process.resourcesPath, 'novacore');
    if (isAaronCoreRepoRoot(legacyPackagedRoot)) return legacyPackagedRoot;
    return packagedAaronCore;
  }
  return resolveExistingRoot(path.resolve(__dirname, '..'));
}

function ensureDir(target) {
  if (!target) return;
  fs.mkdirSync(target, { recursive: true });
}

function copyFileIfMissing(source, target) {
  if (!source || !target) return;
  if (!fs.existsSync(source) || fs.existsSync(target)) return;
  ensureDir(path.dirname(target));
  fs.copyFileSync(source, target);
}

function copyDirIfMissing(source, target) {
  if (!source || !target) return;
  if (!fs.existsSync(source) || fs.existsSync(target)) return;
  ensureDir(path.dirname(target));
  fs.cpSync(source, target, { recursive: true, force: false, errorOnExist: false });
}

function migratePackagedData(dataDir) {
  if (!app.isPackaged || !dataDir) return;
  const packagedRoot = path.join(process.resourcesPath, 'aaroncore');
  const legacyPackagedDataDir = resolvePackagedDataDir(process.execPath);

  if (legacyPackagedDataDir && resolveExistingRoot(legacyPackagedDataDir) !== resolveExistingRoot(dataDir)) {
    copyFileIfMissing(
      path.join(legacyPackagedDataDir, 'brain', 'llm_config.json'),
      path.join(dataDir, 'brain', 'llm_config.json'),
    );
    copyFileIfMissing(
      path.join(legacyPackagedDataDir, 'brain', 'llm_config.local.json'),
      path.join(dataDir, 'brain', 'llm_config.local.json'),
    );
    copyDirIfMissing(
      path.join(legacyPackagedDataDir, 'state_data'),
      path.join(dataDir, 'state_data'),
    );
    copyDirIfMissing(
      path.join(legacyPackagedDataDir, 'logs'),
      path.join(dataDir, 'logs'),
    );
  }

  if (!isAaronCoreRepoRoot(packagedRoot)) return;

  copyFileIfMissing(
    path.join(packagedRoot, 'brain', 'llm_config.json'),
    path.join(dataDir, 'brain', 'llm_config.json'),
  );
  copyFileIfMissing(
    path.join(packagedRoot, 'brain', 'llm_config.local.json'),
    path.join(dataDir, 'brain', 'llm_config.local.json'),
  );
  copyDirIfMissing(
    path.join(packagedRoot, 'state_data'),
    path.join(dataDir, 'state_data'),
  );
  copyDirIfMissing(
    path.join(packagedRoot, 'logs'),
    path.join(dataDir, 'logs'),
  );
}

const aaroncoreRoot = resolveAaronCoreRoot();
const aaroncoreDataDir = resolveAaronCoreDataDir({
  explicitDataDir: process.env.AARONCORE_DATA_DIR || process.env.NOVACORE_DATA_DIR,
  explicitHomeDir: process.env.AARONCORE_HOME_DIR || process.env.NOVACORE_HOME_DIR,
  homeDir: app.getPath('home'),
  isPackaged: app.isPackaged,
  portableExecutableDir: process.env.PORTABLE_EXECUTABLE_DIR,
  processExecPath: process.execPath,
  productSlug: 'aaroncore',
});
const aaroncoreUserDataDir = resolveElectronUserDataDir({
  explicitUserDataDir: process.env.AARONCORE_USER_DATA_DIR || process.env.NOVACORE_USER_DATA_DIR,
  appDataDir: app.getPath('appData'),
  isPackaged: app.isPackaged,
  dataDir: aaroncoreDataDir,
  rootDir: aaroncoreRoot,
  portableExecutableDir: process.env.PORTABLE_EXECUTABLE_DIR,
  processExecPath: process.execPath,
  productName: 'AaronCore',
});
if (aaroncoreUserDataDir) {
  ensureDir(aaroncoreUserDataDir);
  app.setPath('userData', aaroncoreUserDataDir);
  process.env.AARONCORE_USER_DATA_DIR = aaroncoreUserDataDir;
  process.env.NOVACORE_USER_DATA_DIR = aaroncoreUserDataDir;
}
if (aaroncoreDataDir) {
  process.env.AARONCORE_DATA_DIR = aaroncoreDataDir;
  process.env.NOVACORE_DATA_DIR = aaroncoreDataDir;
  ensureDir(aaroncoreDataDir);
  migratePackagedData(aaroncoreDataDir);
}

function shouldEnableAutoUpdate() {
  if (!app.isPackaged) return false;
  if (process.platform !== 'win32') return false;
  if (process.env.AARONCORE_DISABLE_AUTO_UPDATE === '1') return false;
  // electron-builder portable builds are not a good target for in-app updates.
  if (process.env.PORTABLE_EXECUTABLE_DIR) return false;
  // Local unpacked builds are still part of the development/distribution path.
  if (String(process.execPath || '').toLowerCase().includes('win-unpacked')) return false;
  return true;
}

function setupAutoUpdate() {
  if (!shouldEnableAutoUpdate()) return;

  let autoUpdater;
  try {
    ({ autoUpdater } = require('electron-updater'));
  } catch (error) {
    console.warn('[updater] electron-updater unavailable:', error && (error.stack || error.message) || error);
    return;
  }

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('error', (error) => {
    console.warn('[updater] update check failed:', error && (error.stack || error.message) || error);
  });

  autoUpdater.on('update-available', (info) => {
    console.log('[updater] update available:', info && info.version ? info.version : 'unknown');
  });

  autoUpdater.on('update-not-available', () => {
    console.log('[updater] no update available');
  });

  autoUpdater.on('update-downloaded', async (info) => {
    const currentVersion = app.getVersion();
    const nextVersion = info && info.version ? String(info.version) : '';
    const detailLines = [
      `Current version: ${currentVersion}`,
      nextVersion ? `New version: ${nextVersion}` : '',
      'The update has been downloaded and is ready to install.',
    ].filter(Boolean);

    try {
      const result = await dialog.showMessageBox({
        type: 'info',
        buttons: ['Restart and Update', 'Later'],
        defaultId: 0,
        cancelId: 1,
        noLink: true,
        title: 'AaronCore Update Ready',
        message: 'A new AaronCore version has finished downloading.',
        detail: detailLines.join('\n'),
      });

      if (result.response === 0) {
        setImmediate(() => autoUpdater.quitAndInstall(false, true));
      }
    } catch (error) {
      console.warn('[updater] failed to show update dialog:', error && (error.stack || error.message) || error);
    }
  });

  app.whenReady().then(() => {
    setTimeout(() => {
      autoUpdater.checkForUpdates().catch((error) => {
        console.warn('[updater] checkForUpdates threw:', error && (error.stack || error.message) || error);
      });
    }, 15000);
  });
}

process.env.AARONCORE_ROOT = aaroncoreRoot;
process.env.NOVACORE_ROOT = aaroncoreRoot;

const shellDir = path.join(aaroncoreRoot, 'shell');
const backendEntry = path.join(aaroncoreRoot, 'agent_final.py');
process.env.AARONCORE_SHELL_DIR = shellDir;
process.env.NOVACORE_SHELL_DIR = shellDir;
process.env.AARONCORE_BACKEND_ENTRY = backendEntry;
process.env.NOVACORE_BACKEND_ENTRY = backendEntry;

setupAutoUpdate();

require(path.join(shellDir, 'main.js'));
