const fs = require('fs');
const path = require('path');
const { app } = require('electron');

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

// Packaged desktop builds still prefer the nearby development repo when it exists.
// On this machine:
// - exe dir:      C:\Users\36459\NovaCoreDesktop\win-unpacked
// - dev repo dir: C:\Users\36459\NovaCore
// This keeps the desktop app connected to the live workspace and its state_data
// instead of silently falling back to packaged resources.
function resolvePackagedDevRoot() {
  const candidates = [];
  const explicitDevRoot = process.env.AARONCORE_DEV_ROOT || process.env.NOVACORE_DEV_ROOT;
  if (explicitDevRoot) {
    candidates.push(explicitDevRoot);
  }

  const exeDir = path.dirname(process.execPath);
  const desktopDir = path.dirname(exeDir);
  const desktopParentDir = path.dirname(desktopDir);
  const desktopName = path.basename(desktopDir);
  if (desktopName.toLowerCase().endsWith('desktop')) {
    const repoName = desktopName.slice(0, -'Desktop'.length);
    if (repoName) {
      candidates.push(path.join(desktopParentDir, repoName));
    }
  }

  // Compatibility for repo/app renames such as NovaCore -> AaronCore.
  candidates.push(path.join(desktopParentDir, 'AaronCore'));
  candidates.push(path.join(desktopParentDir, 'NovaCore'));

  for (const candidate of candidates) {
    const resolved = resolveExistingRoot(candidate);
    if (isAaronCoreRepoRoot(resolved)) return resolved;
  }
  return '';
}

function resolveAaronCoreRoot() {
  const explicitRoot = resolveExistingRoot(process.env.AARONCORE_ROOT || process.env.NOVACORE_ROOT);
  if (isAaronCoreRepoRoot(explicitRoot)) return explicitRoot;
  if (app.isPackaged) {
    // Resolution order for packaged exe:
    // 1. explicit AARONCORE_DEV_ROOT (or legacy NOVACORE_DEV_ROOT)
    // 2. sibling dev repo (NovaCoreDesktop -> AaronCore / NovaCore)
    // 3. packaged resources/aaroncore fallback
    const devRoot = resolvePackagedDevRoot();
    if (devRoot) return devRoot;

    const packagedAaronCore = path.join(process.resourcesPath, 'aaroncore');
    if (isAaronCoreRepoRoot(packagedAaronCore)) return packagedAaronCore;
    return path.join(process.resourcesPath, 'novacore');
  }
  return resolveExistingRoot(path.resolve(__dirname, '..'));
}

const aaroncoreRoot = resolveAaronCoreRoot();

process.env.AARONCORE_ROOT = aaroncoreRoot;
process.env.NOVACORE_ROOT = aaroncoreRoot;

const shellDir = path.join(aaroncoreRoot, 'shell');
const backendEntry = path.join(aaroncoreRoot, 'agent_final.py');
process.env.AARONCORE_SHELL_DIR = shellDir;
process.env.NOVACORE_SHELL_DIR = shellDir;
process.env.AARONCORE_BACKEND_ENTRY = backendEntry;
process.env.NOVACORE_BACKEND_ENTRY = backendEntry;

require(path.join(shellDir, 'main.js'));
