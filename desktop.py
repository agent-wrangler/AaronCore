"""
NovaCore Desktop - 桌面客户端
无边框自定义标题栏
"""
import webview
import time
import os
import ctypes
import ctypes.wintypes
import subprocess

user32 = ctypes.windll.user32


class WindowApi:
    def __init__(self, win):
        self._win = win

    def _hwnd(self):
        """获取 pywebview 主窗口句柄"""
        result = []
        def cb(hwnd, _):
            cls = ctypes.create_unicode_buffer(64)
            title = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 64)
            user32.GetWindowTextW(hwnd, title, 256)
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 800 and h > 600 and 'Nova Companion' not in title.value and 'Visual Studio' not in title.value and 'Claude' not in title.value:
                result.append(hwnd)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        return result[0] if result else None

    def minimize(self):
        self._win.minimize()

    def toggle_maximize(self):
        self._win.toggle_fullscreen()

    def start_drag(self):
        """触发 Windows 原生窗口拖拽"""
        hwnd = self._hwnd()
        if not hwnd:
            return
        WM_NCLBUTTONDOWN = 0x00A1
        HTCAPTION = 2
        user32.ReleaseCapture()
        user32.PostMessageW(hwnd, WM_NCLBUTTONDOWN, HTCAPTION, 0)

    def move_window(self, dx, dy):
        pass

    def close(self):
        import sys
        self._win.destroy()
        sys.exit(0)

    def set_theme(self, theme):
        pass


def start_backend():
    os.chdir(r"C:\Users\36459\NovaCore")
    subprocess.Popen([r"C:\Program Files\Python311\python.exe", "agent_final.py"])


def start_companion():
    companion_dir = os.path.join(r"C:\Users\36459\NovaCore", "companion")
    electron_exe = os.path.join(companion_dir, "node_modules", "electron", "dist", "electron.exe")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    subprocess.Popen([electron_exe, "."], cwd=companion_dir, env=env)


screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)
window_width = 1100
window_height = 800
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2

start_backend()
time.sleep(3)

api = WindowApi(None)
window = webview.create_window(
    '',
    'http://localhost:8090/',
    width=window_width,
    height=window_height,
    x=x,
    y=y,
    resizable=True,
    frameless=True,
    easy_drag=False,
    js_api=api,
)
api._win = window

start_companion()

print("NovaCore \u542f\u52a8\u4e2d...")
webview.start()
