"""
NovaCore Desktop - 无边框窗口（子类化 + WS_THICKFRAME 缩放 + JS 拖拽）
"""
import webview
import time
import os
import ctypes
import ctypes.wintypes
import subprocess

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

# ── 设置 ctypes 函数签名（64位关键） ──
user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
user32.CallWindowProcW.restype = ctypes.c_longlong
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong]
user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.wintypes.RECT)]
user32.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_ulonglong, ctypes.c_longlong]

# DWM 常量
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
DWMWA_BORDER_COLOR = 34

# Win32 常量
GWL_STYLE = -16
GWLP_WNDPROC = -4
WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_SYSCOMMAND = 0x0112

WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004

SC_DRAGMOVE = 0xF012
SC_SIZE = 0xF000

HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17

BORDER = 6   # 缩放感应区宽度

# SC_SIZE 方向
_RESIZE_DIR = {
    'left': 1, 'right': 2, 'top': 3,
    'topleft': 4, 'topright': 5,
    'bottom': 6, 'bottomleft': 7, 'bottomright': 8,
}

# ── 窗口子类化 ──
_hwnd = None
_original_wndproc = None

# 64 位 WNDPROC 签名
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,   # LRESULT
    ctypes.c_void_p,     # HWND
    ctypes.c_uint,       # UINT msg
    ctypes.c_ulonglong,  # WPARAM
    ctypes.c_longlong,   # LPARAM
)


def _new_wndproc(hwnd, msg, wparam, lparam):
    """子类化窗口过程：
    - WM_NCCALCSIZE: 返回 0，阻止系统画标题栏（WS_THICKFRAME 加回后不让它画）
    - WM_NCHITTEST:  边缘区域返回缩放指令（这是非客户区，WebView2 管不到）
    """
    if msg == WM_NCCALCSIZE and wparam:
        return 0

    if msg == WM_NCHITTEST:
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        left   = (x - rect.left)   < BORDER
        right  = (rect.right - x)  < BORDER
        top    = (y - rect.top)    < BORDER
        bottom = (rect.bottom - y) < BORDER

        if top and left:      return HTTOPLEFT
        if top and right:     return HTTOPRIGHT
        if bottom and left:   return HTBOTTOMLEFT
        if bottom and right:  return HTBOTTOMRIGHT
        if left:   return HTLEFT
        if right:  return HTRIGHT
        if top:    return HTTOP
        if bottom: return HTBOTTOM

        return HTCLIENT

    return user32.CallWindowProcW(_original_wndproc, hwnd, msg, wparam, lparam)


# 防 GC 回收（全局引用）
_wndproc_ref = WNDPROC(_new_wndproc)


def _subclass_window(hwnd):
    """子类化：替换窗口过程 + 加回 WS_THICKFRAME"""
    global _original_wndproc

    # 1. 替换窗口过程
    _original_wndproc = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, _wndproc_ref)
    print(f"[desktop] subclassed, original_wndproc={_original_wndproc}", flush=True)

    # 2. 加回 WS_THICKFRAME（系统缩放边框，在非客户区，WebView2 管不到）
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style = style | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)

    # 3. 通知系统刷新框架
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                        SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER)
    print(f"[desktop] WS_THICKFRAME added, hwnd={hwnd}", flush=True)


def _find_hwnd():
    global _hwnd
    if _hwnd and user32.IsWindow(_hwnd):
        return _hwnd
    for title in ["", "Nova"]:
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            _hwnd = hwnd
            return _hwnd
    return None


# ── DWM 主题 ──

def _set_titlebar_theme(dark=True):
    hwnd = _find_hwnd()
    if not hwnd:
        return
    dm = ctypes.c_int(1 if dark else 0)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dm), 4)
    if dark:
        bg, fg = ctypes.c_uint(0x00201E1E), ctypes.c_uint(0x00F0EBEB)
    else:
        bg, fg = ctypes.c_uint(0x00FCFAF8), ctypes.c_uint(0x00634B47)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(bg), 4)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TEXT_COLOR, ctypes.byref(fg), 4)
    border = ctypes.c_uint(0x00201E1E if dark else 0x00FCFAF8)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(border), 4)


# ── 暴露给前端的 API ──

def set_theme(theme):
    _set_titlebar_theme(theme == 'dark')

def minimize():
    window.minimize()

def toggle_maximize():
    hwnd = _find_hwnd()
    if hwnd:
        if user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, 9)
        else:
            user32.ShowWindow(hwnd, 3)

def close_window():
    window.destroy()

def start_drag():
    """JS 调用：顶栏 mousedown → 拖拽移动"""
    hwnd = _find_hwnd()
    if hwnd:
        user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_DRAGMOVE, 0)

def start_resize(direction):
    """JS 调用：边缘 mousedown → 缩放"""
    hwnd = _find_hwnd()
    if hwnd:
        d = _RESIZE_DIR.get(direction, 8)
        user32.PostMessageW(hwnd, WM_SYSCOMMAND, SC_SIZE + d, 0)


# ── 启动 ──

def start_backend():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", 8090)); s.close()
        print("[desktop] backend running"); return
    except ConnectionRefusedError: pass
    os.chdir(r"C:\Users\36459\NovaCore")
    subprocess.Popen([r"C:\Program Files\Python311\python.exe", "agent_final.py"])

def start_companion():
    try:
        import json
        with open(os.path.join(r"C:\Users\36459\NovaCore", "memory_db", "companion_config.json"), "r", encoding="utf-8") as f:
            if not json.load(f).get("enabled", True):
                print("[desktop] Entity disabled"); return
    except Exception: pass
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", 8091)); s.close()
        print("[desktop] companion running"); return
    except ConnectionRefusedError: pass
    d = os.path.join(r"C:\Users\36459\NovaCore", "companion")
    env = os.environ.copy(); env.pop("ELECTRON_RUN_AS_NODE", None)
    subprocess.Popen([os.path.join(d, "node_modules", "electron", "dist", "electron.exe"), "."], cwd=d, env=env)


start_backend()
time.sleep(3)

os.environ['WEBVIEW2_DEFAULT_BACKGROUND_COLOR'] = '161618'

_sw = user32.GetSystemMetrics(0)
_sh = user32.GetSystemMetrics(1)
_ww, _wh = 1100, 900

window = webview.create_window(
    'Nova', 'http://localhost:8090/',
    width=_ww, height=_wh,
    x=(_sw-_ww)//2, y=(_sh-_wh)//2,
    frameless=True, easy_drag=False,
    resizable=True, background_color='#161618',
)


def _on_loaded():
    hwnd = _find_hwnd()
    if hwnd:
        window.set_title("")
        _subclass_window(hwnd)

window.events.loaded += _on_loaded


def _on_shown():
    import threading
    def _do():
        time.sleep(2)
        window.expose(set_theme)
        window.expose(minimize)
        window.expose(toggle_maximize)
        window.expose(close_window)
        window.expose(start_drag)
        window.expose(start_resize)
        hwnd = _find_hwnd()
        if hwnd:
            window.set_title("")
            if not _original_wndproc:
                _subclass_window(hwnd)
        _set_titlebar_theme(dark=False)
        print(f"[desktop] ready, hwnd={hwnd}", flush=True)
        try:
            from core.vision import init as vi, start as vs
            from brain import vision_llm_call
            vi(llm_call=vision_llm_call); vs()
        except Exception as e:
            print(f"[desktop] vision: {e}", flush=True)
    threading.Thread(target=_do, daemon=True).start()

window.events.shown += _on_shown
start_companion()

print("NovaCore 启动中...")
_c = os.path.join(os.environ.get("APPDATA",""), "NovaCore", "EBWebView", "Default", "Cache")
if os.path.isdir(_c):
    import shutil
    try: shutil.rmtree(_c, ignore_errors=True)
    except: pass
webview.start(private_mode=False, storage_path=os.path.join(os.environ.get("APPDATA",""), "NovaCore"))
