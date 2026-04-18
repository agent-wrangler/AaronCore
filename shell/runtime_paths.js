const fs = require('fs');
const path = require('path');

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

function resolvePackagedAppDir(processExecPath = process.execPath) {
  return resolveExistingRoot(path.dirname(processExecPath));
}

function resolvePackagedDataDir(processExecPath = process.execPath) {
  const appDir = resolvePackagedAppDir(processExecPath);
  if (!appDir) return '';
  const appDirName = path.basename(appDir).toLowerCase();
  if (appDirName === 'app') {
    return path.join(path.dirname(appDir), 'Data');
  }
  return path.join(appDir, 'Data');
}

function isPortableOrUnpackedBuild(options = {}) {
  const portableExecutableDir = String(options.portableExecutableDir || '').trim();
  const processExecPath = String(options.processExecPath || process.execPath || '').trim().toLowerCase();
  return Boolean(portableExecutableDir) || processExecPath.includes('win-unpacked');
}

function resolveAaronCoreHomeDir(options = {}) {
  const explicitHomeDir = options.explicitHomeDir || '';
  const homeDir = options.homeDir || '';
  const productSlug = options.productSlug || 'aaroncore';

  const explicit = resolveExistingRoot(explicitHomeDir);
  if (explicit) return explicit;

  const resolvedHomeDir = resolveExistingRoot(homeDir);
  if (resolvedHomeDir) {
    return path.join(resolvedHomeDir, `.${productSlug}`);
  }

  return `.${productSlug}`;
}

function resolveAaronCoreDataDir(options = {}) {
  const explicitDataDir = options.explicitDataDir || '';
  const isPackaged = Boolean(options.isPackaged);
  const processExecPath = options.processExecPath || process.execPath;

  const explicit = resolveExistingRoot(explicitDataDir);
  if (explicit) return explicit;
  if (!isPackaged) return '';

  if (isPortableOrUnpackedBuild(options)) {
    return resolvePackagedDataDir(processExecPath);
  }

  return resolveAaronCoreHomeDir(options);
}

function resolveElectronUserDataDir(options = {}) {
  const explicitUserDataDir = options.explicitUserDataDir || '';
  const appDataDir = options.appDataDir || '';
  const isPackaged = Boolean(options.isPackaged);
  const dataDir = options.dataDir || '';
  const rootDir = options.rootDir || '';
  const processExecPath = options.processExecPath || process.execPath;
  const productName = options.productName || 'AaronCore';

  const explicit = resolveExistingRoot(explicitUserDataDir);
  if (explicit) return explicit;

  const resolvedDataDir = resolveExistingRoot(dataDir);
  const resolvedRootDir = resolveExistingRoot(rootDir);
  const repoBackedStateDir = Boolean(
    resolvedDataDir
      && ((resolvedRootDir && resolvedDataDir === resolvedRootDir) || isAaronCoreRepoRoot(resolvedDataDir))
  );

  if (!isPackaged || repoBackedStateDir) {
    const resolvedAppDataDir = resolveExistingRoot(appDataDir);
    if (resolvedAppDataDir) {
      return path.join(resolvedAppDataDir, `${productName}-dev-shell`);
    }
    if (resolvedDataDir) {
      return path.join(resolvedDataDir, '.electron-user-data');
    }
    if (resolvedRootDir) {
      return path.join(resolvedRootDir, '.electron-user-data');
    }
    return `${productName}-dev-shell`;
  }

  const resolvedAppDataDir = resolveExistingRoot(appDataDir);
  if (isPortableOrUnpackedBuild(options)) {
    if (resolvedDataDir) {
      return path.join(resolvedDataDir, 'userData');
    }
    const packagedDataDir = resolvePackagedDataDir(processExecPath);
    if (packagedDataDir) {
      return path.join(packagedDataDir, 'userData');
    }
  }

  if (resolvedAppDataDir) {
    return path.join(resolvedAppDataDir, productName);
  }

  return productName;
}

module.exports = {
  isPortableOrUnpackedBuild,
  resolveAaronCoreDataDir,
  resolveAaronCoreHomeDir,
  isAaronCoreRepoRoot,
  resolveElectronUserDataDir,
  resolveExistingRoot,
  resolvePackagedAppDir,
  resolvePackagedDataDir,
};
