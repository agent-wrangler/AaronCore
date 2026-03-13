"""
NovaCore Desktop - 桌面客户端
统一启动 agent_final.py 作为 8090 主入口
"""
import webview
import time
import os
import ctypes
import subprocess


def start_backend():
    os.chdir(r"C:\Users\36459\NovaCore")
    subprocess.Popen([r"C:\Program Files\Python311\python.exe", "agent_final.py"])


user32 = ctypes.windll.user32
screen_width = user32.GetSystemMetrics(0)
screen_height = user32.GetSystemMetrics(1)

window_width = 1100
window_height = 800
x = (screen_width - window_width) // 2
y = (screen_height - window_height) // 2

start_backend()
time.sleep(3)

webview.create_window(
    'NovaCore',
    'http://localhost:8090/',
    width=window_width,
    height=window_height,
    x=x,
    y=y,
    resizable=True
)

print("NovaCore 启动中...")
webview.start()
