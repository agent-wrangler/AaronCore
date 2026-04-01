const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('novaShell', {
  windowControlsMode: 'custom-html',
  transparentShell: false,
  minimize:       () => ipcRenderer.send('win-minimize'),
  maximize:       () => ipcRenderer.send('win-maximize'),
  close:          () => ipcRenderer.send('win-close'),
  setTheme: (theme) => ipcRenderer.send('win-theme', theme),
  dragBy:   (dx, dy) => ipcRenderer.send('win-drag-by', dx, dy),
  onWindowState: (callback) => {
    if (typeof callback !== 'function') return;
    ipcRenderer.on('window-state', (_event, state) => callback(state || {}));
  },
});
