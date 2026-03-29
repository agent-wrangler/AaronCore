const path = require('path');
const { app } = require('electron');

function resolveNovaCoreRoot() {
  if (process.env.NOVACORE_ROOT) return process.env.NOVACORE_ROOT;
  if (app.isPackaged) return path.join(process.resourcesPath, 'novacore');
  return path.resolve(__dirname, '..');
}

const novacoreRoot = resolveNovaCoreRoot();

process.env.NOVACORE_ROOT = novacoreRoot;
process.env.NOVACORE_SHELL_DIR = path.join(novacoreRoot, 'shell');
process.env.NOVACORE_BACKEND_ENTRY = path.join(novacoreRoot, 'agent_final.py');

require(path.join(process.env.NOVACORE_SHELL_DIR, 'main.js'));
