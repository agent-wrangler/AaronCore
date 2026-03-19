"""
NovaCore Desktop - 桌面客户端
"""
import webview
import time
import os
import ctypes
import ctypes.wintypes
import subprocess

dwmapi = ctypes.windll.dwmapi
user32 = ctypes.windll.user32
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_USE_IMMERSIVE_DARK_MODE = 20

# 缓存窗口句柄
_hwnd = None


def _find_hwnd():
    """通过窗口标题找到 pywebview 窗口句柄"""
    global _hwnd
    if _hwnd:
        return _hwnd
    hwnd = user32.FindWindowW(None, "Nova")
    if hwnd:
        _hwnd = hwnd
    return _hwnd


def _set_titlebar_theme(dark=True):
    """设置系统标题栏颜色（DWMWA_CAPTION_COLOR + TEXT_COLOR）"""
    hwnd = _find_hwnd()
    if not hwnd:
        print(f"[desktop] _set_titlebar_theme: hwnd not found", flush=True)
        return
    # 先设置深色/浅色模式，否则系统主题会覆盖自定义颜色
    dark_mode = ctypes.c_int(1 if dark else 0)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_mode), 4)
    if dark:
        bg = ctypes.c_uint(0x00201E1E)   # #1e1e20 BGR
        fg = ctypes.c_uint(0x00F0EBEB)   # #ebebf0 BGR
    else:
        bg = ctypes.c_uint(0x00FCFAF8)   # #f8fafc BGR
        fg = ctypes.c_uint(0x00634B47)   # #474b63 BGR
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(bg), 4)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(fg), 4)
    print(f"[desktop] titlebar set to {'dark' if dark else 'light'}, hwnd={hwnd}", flush=True)


def set_theme(theme):
    """前端调用：切换标题栏主题"""
    _set_titlebar_theme(theme == 'dark')


def start_backend():
    """启动后端服务，如果已在运行则跳过"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("127.0.0.1", 8090))
        sock.close()
        print("[desktop] 后端已在运行，跳过启动")
        return
    except ConnectionRefusedError:
        pass
    os.chdir(r"C:\Users\36459\NovaCore")
    subprocess.Popen([r"C:\Program Files\Python311\python.exe", "agent_final.py"])


def start_companion():
    """启动伴侣窗口，如果已在运行则跳过"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(("127.0.0.1", 8091))
        sock.close()
        print("[desktop] 伴侣窗口已在运行，跳过启动")
        return
    except ConnectionRefusedError:
        pass
    companion_dir = os.path.join(r"C:\Users\36459\NovaCore", "companion")
    electron_exe = os.path.join(companion_dir, "node_modules", "electron", "dist", "electron.exe")
    env = os.environ.copy()
    env.pop("ELECTRON_RUN_AS_NODE", None)
    subprocess.Popen([electron_exe, "."], cwd=companion_dir, env=env)


start_backend()
time.sleep(3)

# WebView2 初始化前设默认背景色（环境变量方式，最可靠）
os.environ['WEBVIEW2_DEFAULT_BACKGROUND_COLOR'] = 'EFF6FF'

window = webview.create_window(
    'Nova',
    'http://localhost:8090/',
    width=1100,
    height=800,
    resizable=True,
    background_color='#eff6ff',
)


def _on_shown():
    import threading
    def _do():
        time.sleep(2)
        window.expose(set_theme)
        hwnd = _find_hwnd()
        print(f"[desktop] hwnd={hwnd}", flush=True)
        # hwnd 已缓存，清掉标题栏文字和图标
        if hwnd:
            window.set_title("")
        _set_titlebar_theme(dark=False)
        print("[desktop] ready, titlebar set to light", flush=True)
    threading.Thread(target=_do, daemon=True).start()


window.events.shown += _on_shown

start_companion()

print("NovaCore 启动中...")
webview.start(private_mode=False, storage_path=os.path.join(os.environ.get("APPDATA", ""), "NovaCore"))
