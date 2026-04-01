"""诊断：枚举窗口层级，逐个尝试设置红色边框"""
import ctypes
import ctypes.wintypes

dwmapi = ctypes.windll.dwmapi
user32 = ctypes.windll.user32

dwmapi.DwmSetWindowAttribute.argtypes = [
    ctypes.wintypes.HWND, ctypes.wintypes.DWORD,
    ctypes.c_void_p, ctypes.wintypes.DWORD,
]
dwmapi.DwmSetWindowAttribute.restype = ctypes.HRESULT

DWMWA_BORDER_COLOR = 34
GA_ROOT = 2

# 找窗口
hwnd = user32.FindWindowW(None, "") or user32.FindWindowW(None, "Nova")
if not hwnd:
    print("找不到窗口")
    exit()

# 找到最顶层的根窗口
root = user32.GetAncestor(hwnd, GA_ROOT)
print(f"FindWindow hwnd = {hwnd}")
print(f"Root hwnd       = {root}")

# 获取窗口类名
buf = ctypes.create_unicode_buffer(256)

targets = set()
targets.add(hwnd)
targets.add(root)
# 也试试父窗口
parent = user32.GetParent(hwnd)
if parent:
    targets.add(parent)

for h in sorted(targets):
    user32.GetClassNameW(h, buf, 256)
    cls = buf.value
    red = ctypes.c_uint(0x000000FF)
    hr = dwmapi.DwmSetWindowAttribute(h, DWMWA_BORDER_COLOR, ctypes.byref(red), 4)
    print(f"  hwnd={h}, class='{cls}', border_color -> 0x{hr & 0xFFFFFFFF:08X} ({'OK' if hr == 0 else 'FAIL'})")

print("\n如果某个窗口设置成功，边框应该变红。看看哪个生效了？")
