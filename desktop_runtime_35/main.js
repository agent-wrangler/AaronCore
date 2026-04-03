const fs = require('fs');
const path = require('path');
const { app } = require('electron');

function isNovaCoreRoot(candidate) {
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
// instead of silently falling back to resources/novacore.
function resolvePackagedDevRoot() {
  const candidates = [];
  if (process.env.NOVACORE_DEV_ROOT) {
    candidates.push(process.env.NOVACORE_DEV_ROOT);
  }

  const exeDir = path.dirname(process.execPath);
  const desktopDir = path.dirname(exeDir);
  const desktopName = path.basename(desktopDir);
  if (desktopName.toLowerCase().endsWith('desktop')) {
    const repoName = desktopName.slice(0, -'Desktop'.length);
    if (repoName) {
      candidates.push(path.join(path.dirname(desktopDir), repoName));
    }
  }

  for (const candidate of candidates) {
    const resolved = path.resolve(candidate);
    if (isNovaCoreRoot(resolved)) return resolved;
  }
  return '';
}

function resolveNovaCoreRoot() {
  if (process.env.NOVACORE_ROOT) return process.env.NOVACORE_ROOT;
  if (app.isPackaged) {
    // Resolution order for packaged exe:
    // 1. explicit NOVACORE_DEV_ROOT
    // 2. sibling dev repo (NovaCoreDesktop -> NovaCore)
    // 3. packaged resources/novacore fallback
    const devRoot = resolvePackagedDevRoot();
    if (devRoot) return devRoot;
    return path.join(process.resourcesPath, 'novacore');
  }
  return path.resolve(__dirname, '..');
}

const novacoreRoot = resolveNovaCoreRoot();

process.env.NOVACORE_ROOT = novacoreRoot;
process.env.NOVACORE_SHELL_DIR = path.join(novacoreRoot, 'shell');
process.env.NOVACORE_BACKEND_ENTRY = path.join(novacoreRoot, 'agent_final.py');

require(path.join(process.env.NOVACORE_SHELL_DIR, 'main.js'));
