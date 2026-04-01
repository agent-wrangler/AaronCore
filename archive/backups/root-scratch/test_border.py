"""诊断 DWMWA_BORDER_COLOR 是否生效"""
import ctypes
import ctypes.wintypes

dwmapi = ctypes.windll.dwmapi
user32 = ctypes.windll.user32

# 设置正确的函数签名
dwmapi.DwmSetWindowAttribute.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
]
dwmapi.DwmSetWindowAttribute.restype = ctypes.HRESULT

DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35

# 找 Nova 窗口
hwnd = user32.FindWindowW(None, "") or user32.FindWindowW(None, "Nova")
print(f"hwnd = {hwnd}")

if hwnd:
    # 测试设置边框色为红色（明显可见）
    red_bgr = ctypes.c_uint(0x000000FF)  # 红色 BGR
    hr = dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, ctypes.byref(red_bgr), 4)
    print(f"BORDER_COLOR result: 0x{hr & 0xFFFFFFFF:08X} ({'OK' if hr == 0 else 'FAILED'})")

    # 对比：设置标题栏为红色
    red_bgr2 = ctypes.c_uint(0x000000FF)
    hr2 = dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(red_bgr2), 4)
    print(f"CAPTION_COLOR result: 0x{hr2 & 0xFFFFFFFF:08X} ({'OK' if hr2 == 0 else 'FAILED'})")
else:
    print("找不到 Nova 窗口，请先启动 desktop.py")
