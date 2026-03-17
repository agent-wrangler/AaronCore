const { app, BrowserWindow, Menu, ipcMain } = require('electron');

Menu.setApplicationMenu(null);

let win;

function createWindow() {
  const { screen } = require('electron');
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize;

  win = new BrowserWindow({
    width: 600,
    height: 700,
    x: sw - 650,
    y: sh - 750,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    roundedCorners: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: require('path').join(__dirname, 'preload.js'),
    },
  });

  win.setMenu(null);
  win.loadURL('http://localhost:8090/companion');
  win.setIgnoreMouseEvents(false);
  win.on('closed', () => { win = null; });
}

// 窗口拖拽：渲染进程发来鼠标偏移量
ipcMain.on('window-move', (event, dx, dy) => {
  if (!win) return;
  const [x, y] = win.getPosition();
  win.setPosition(x + dx, y + dy);
});

app.commandLine.appendSwitch('disable-gpu-compositing');

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { app.quit(); });
