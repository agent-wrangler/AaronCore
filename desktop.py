"""
AaronCore Desktop - 无边框窗口（子类化 + WS_THICKFRAME 缩放 + JS 拖拽）
"""
import webview
import time
import os
import json
import base64
import atexit
import ctypes
import ctypes.wintypes
import subprocess
import threading
from pathlib import Path
try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None

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
_theme_watch_started = False
_last_system_theme = ""
_voice_bridge_lock = threading.RLock()
_voice_capabilities_cache = None
_voice_listen_process = None
_voice_speak_process = None
_voice_listen_cancelled_ids = set()
_voice_speak_cancelled_ids = set()
_voice_state = {"listening": False, "speaking": False}
_PS_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

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
    for title in ["", "AaronCore", "Aaron", "Nova"]:
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

def get_system_theme():
    if winreg is None:
        return "light"
    personalize_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, personalize_path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "dark" if int(value) == 0 else "light"
    except Exception:
        return "light"

def _dispatch_window_event(name: str, detail: dict | None = None):
    try:
        payload = json.dumps(detail or {}, ensure_ascii=True)
        event_name = json.dumps(str(name or ""), ensure_ascii=True)
        window.evaluate_js(
            "window.dispatchEvent(new CustomEvent("
            + event_name
            + ", { detail: "
            + payload
            + " }));"
        )
    except Exception:
        pass

def _emit_system_theme(theme: str):
    _dispatch_window_event("aaroncore-system-theme", {"theme": str(theme or "light")})

def _start_theme_watch():
    global _theme_watch_started, _last_system_theme
    if _theme_watch_started:
        return
    _theme_watch_started = True

    def _watch():
        global _last_system_theme
        while True:
            try:
                theme = get_system_theme()
                if theme != _last_system_theme:
                    _last_system_theme = theme
                    _emit_system_theme(theme)
                time.sleep(1.2)
            except Exception:
                time.sleep(2.0)

    threading.Thread(target=_watch, daemon=True).start()


def _powershell_path() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return candidate if os.path.isfile(candidate) else "powershell"


def _spawn_powershell(script: str) -> subprocess.Popen:
    wrapped = (
        "$ErrorActionPreference='Stop'\n"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n"
        "$OutputEncoding = [System.Text.Encoding]::UTF8\n"
        + str(script or "")
    )
    encoded = base64.b64encode(wrapped.encode("utf-16le")).decode("ascii")
    return subprocess.Popen(
        [
            _powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
        creationflags=_PS_CREATE_NO_WINDOW,
    )


def _parse_powershell_json(stdout_text: str, stderr_text: str, *, default_code: str) -> dict:
    stdout_lines = [line.strip() for line in str(stdout_text or "").splitlines() if line.strip()]
    for candidate in reversed(stdout_lines):
        try:
            payload = json.loads(candidate)
            if isinstance(payload, dict):
                return payload
        except Exception:
            continue
    message = str(stderr_text or stdout_text or "").strip() or "PowerShell command failed."
    return {"ok": False, "code": default_code, "message": message}


def _normalize_lang_list(values) -> list[str]:
    items = values if isinstance(values, list) else ([values] if values else [])
    normalized = []
    seen = set()
    for value in items:
        lang = str(value or "").strip()
        key = lang.lower()
        if not lang or key in seen:
            continue
        seen.add(key)
        normalized.append(lang)
    return normalized


def _select_native_lang(requested_lang: str | None, available_langs: list[str]) -> str:
    langs = _normalize_lang_list(available_langs)
    requested = str(requested_lang or "").strip()
    if not langs:
        return ""
    if not requested:
        return langs[0]
    lowered = requested.lower()
    for lang in langs:
        if lang.lower() == lowered:
            return lang
    prefix = lowered.split("-", 1)[0]
    if prefix:
        for lang in langs:
            lang_lower = lang.lower()
            if lang_lower == prefix or lang_lower.startswith(prefix + "-"):
                return lang
    return ""


def _build_voice_capabilities_script() -> str:
    return r"""
Add-Type -AssemblyName System.Speech
$sttLangs = @()
$ttsLangs = @()
try {
  $sttLangs = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | ForEach-Object { $_.Culture.Name } | Select-Object -Unique)
} catch {}
try {
  $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $ttsLangs = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Culture.Name } | Select-Object -Unique)
  $synth.Dispose()
} catch {}
([PSCustomObject]@{
  ok = $true
  stt_available = @($sttLangs).Count -gt 0
  tts_available = @($ttsLangs).Count -gt 0
  stt_langs = @($sttLangs)
  tts_langs = @($ttsLangs)
} | ConvertTo-Json -Compress)
""".strip()


def _build_voice_listen_script(lang: str) -> str:
    requested = json.dumps(str(lang or "").strip(), ensure_ascii=True)
    return f"""
Add-Type -AssemblyName System.Speech
$targetLang = {requested}
$recognizerInfo = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | Where-Object {{ $_.Culture.Name -ieq $targetLang }} | Select-Object -First 1
if (-not $recognizerInfo) {{
  throw "Recognizer unavailable for $targetLang"
}}
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($recognizerInfo.Culture)
$engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
$engine.InitialSilenceTimeout = [TimeSpan]::FromSeconds(5)
$engine.BabbleTimeout = [TimeSpan]::FromSeconds(3)
$engine.EndSilenceTimeout = [TimeSpan]::FromMilliseconds(900)
$engine.EndSilenceTimeoutAmbiguous = [TimeSpan]::FromMilliseconds(1200)
$engine.SetInputToDefaultAudioDevice()
$result = $engine.Recognize([TimeSpan]::FromSeconds(12))
$engine.Dispose()
if ($result -and -not [string]::IsNullOrWhiteSpace($result.Text)) {{
  ([PSCustomObject]@{{
    ok = $true
    lang = $targetLang
    text = $result.Text
    confidence = [Math]::Round($result.Confidence, 4)
  }} | ConvertTo-Json -Compress)
}} else {{
  ([PSCustomObject]@{{
    ok = $false
    code = "no-speech"
    lang = $targetLang
    message = "No speech recognized."
  }} | ConvertTo-Json -Compress)
}}
""".strip()


def _build_voice_speak_script(text: str, lang: str) -> str:
    requested_text = json.dumps(str(text or ""), ensure_ascii=True)
    requested_lang = json.dumps(str(lang or "").strip(), ensure_ascii=True)
    return f"""
Add-Type -AssemblyName System.Speech
$targetText = {requested_text}
$targetLang = {requested_lang}
if ([string]::IsNullOrWhiteSpace($targetText)) {{
  ([PSCustomObject]@{{ ok = $true; skipped = $true; lang = $targetLang }} | ConvertTo-Json -Compress)
  return
}}
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $null
if (-not [string]::IsNullOrWhiteSpace($targetLang)) {{
  $voice = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -ieq $targetLang }} | Select-Object -First 1
  if (-not $voice) {{
    $prefix = if ($targetLang.Length -ge 2) {{ $targetLang.Substring(0, 2) }} else {{ $targetLang }}
    if (-not [string]::IsNullOrWhiteSpace($prefix)) {{
      $voice = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like ($prefix + "*") }} | Select-Object -First 1
    }}
  }}
}}
if ($voice) {{
  $synth.SelectVoice($voice.VoiceInfo.Name)
}}
$synth.Speak($targetText)
$synth.Dispose()
([PSCustomObject]@{{
  ok = $true
  lang = if ($voice) {{ $voice.VoiceInfo.Culture.Name }} else {{ $targetLang }}
}} | ConvertTo-Json -Compress)
""".strip()


def _get_voice_capabilities(*, force: bool = False) -> dict:
    global _voice_capabilities_cache
    with _voice_bridge_lock:
        if _voice_capabilities_cache is not None and not force:
            return dict(_voice_capabilities_cache)
    try:
        proc = _spawn_powershell(_build_voice_capabilities_script())
        stdout_text, stderr_text = proc.communicate(timeout=12)
        payload = _parse_powershell_json(stdout_text, stderr_text, default_code="voice_capabilities_failed")
    except Exception as exc:
        payload = {"ok": False, "code": "voice_capabilities_failed", "message": str(exc)}
    caps = {
        "native_host": True,
        "stt_available": bool(payload.get("stt_available")),
        "tts_available": bool(payload.get("tts_available")),
        "stt_langs": _normalize_lang_list(payload.get("stt_langs")),
        "tts_langs": _normalize_lang_list(payload.get("tts_langs")),
    }
    if not payload.get("ok", True):
        caps["error"] = str(payload.get("message") or payload.get("code") or "")
    with _voice_bridge_lock:
        _voice_capabilities_cache = dict(caps)
    return dict(caps)


def _emit_native_voice_state():
    caps = _get_voice_capabilities()
    with _voice_bridge_lock:
        detail = {
            "native_host": True,
            "listening": bool(_voice_state.get("listening")),
            "speaking": bool(_voice_state.get("speaking")),
            "stt_available": bool(caps.get("stt_available")),
            "tts_available": bool(caps.get("tts_available")),
            "stt_langs": list(caps.get("stt_langs") or []),
            "tts_langs": list(caps.get("tts_langs") or []),
        }
    _dispatch_window_event("aaroncore-native-voice-state", detail)


def voice_bridge_status():
    caps = _get_voice_capabilities()
    with _voice_bridge_lock:
        return {
            "ok": True,
            "native_host": True,
            "listening": bool(_voice_state.get("listening")),
            "speaking": bool(_voice_state.get("speaking")),
            "stt_available": bool(caps.get("stt_available")),
            "tts_available": bool(caps.get("tts_available")),
            "stt_langs": list(caps.get("stt_langs") or []),
            "tts_langs": list(caps.get("tts_langs") or []),
            "error": str(caps.get("error") or ""),
        }


def voice_listen_stop():
    global _voice_listen_process
    proc = None
    should_emit = False
    with _voice_bridge_lock:
        proc = _voice_listen_process
        if proc is not None:
            _voice_listen_cancelled_ids.add(id(proc))
            _voice_listen_process = None
        if _voice_state.get("listening"):
            _voice_state["listening"] = False
            should_emit = True
    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass
        should_emit = True
    if should_emit:
        _emit_native_voice_state()
    return {"ok": True, "stopped": bool(proc)}


def voice_speak_stop():
    global _voice_speak_process
    proc = None
    should_emit = False
    with _voice_bridge_lock:
        proc = _voice_speak_process
        if proc is not None:
            _voice_speak_cancelled_ids.add(id(proc))
            _voice_speak_process = None
        if _voice_state.get("speaking"):
            _voice_state["speaking"] = False
            should_emit = True
    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass
        should_emit = True
    if should_emit:
        _emit_native_voice_state()
    return {"ok": True, "stopped": bool(proc)}


def voice_listen_start(lang=None):
    global _voice_listen_process
    caps = _get_voice_capabilities()
    requested_lang = str(lang or "").strip()
    selected_lang = _select_native_lang(requested_lang, caps.get("stt_langs") or [])
    if not caps.get("stt_available"):
        return {
            "ok": False,
            "reason": "stt_unavailable",
            "available_langs": list(caps.get("stt_langs") or []),
        }
    if not selected_lang:
        return {
            "ok": False,
            "reason": "language_unavailable",
            "available_langs": list(caps.get("stt_langs") or []),
        }
    voice_listen_stop()
    try:
        proc = _spawn_powershell(_build_voice_listen_script(selected_lang))
    except Exception as exc:
        _dispatch_window_event(
            "aaroncore-native-voice-error",
            {"phase": "listen", "code": "start_failed", "lang": selected_lang, "message": str(exc)},
        )
        return {"ok": False, "reason": "start_failed", "message": str(exc)}

    with _voice_bridge_lock:
        _voice_listen_process = proc
        _voice_state["listening"] = True
    _emit_native_voice_state()

    def _worker(process: subprocess.Popen, target_lang: str):
        global _voice_listen_process
        stdout_text, stderr_text = process.communicate()
        payload = _parse_powershell_json(stdout_text, stderr_text, default_code="listen_failed")
        should_emit = False
        with _voice_bridge_lock:
            cancelled = id(process) in _voice_listen_cancelled_ids
            _voice_listen_cancelled_ids.discard(id(process))
            if _voice_listen_process is process:
                _voice_listen_process = None
                _voice_state["listening"] = False
                should_emit = True
        if should_emit:
            _emit_native_voice_state()
        if cancelled:
            return
        if payload.get("ok") and str(payload.get("text") or "").strip():
            _dispatch_window_event(
                "aaroncore-native-voice-result",
                {
                    "text": str(payload.get("text") or "").strip(),
                    "lang": str(payload.get("lang") or target_lang),
                    "confidence": float(payload.get("confidence") or 0.0),
                },
            )
            return
        _dispatch_window_event(
            "aaroncore-native-voice-error",
            {
                "phase": "listen",
                "code": str(payload.get("code") or "listen_failed"),
                "lang": str(payload.get("lang") or target_lang),
                "message": str(payload.get("message") or "Native speech recognition failed."),
            },
        )

    threading.Thread(target=_worker, args=(proc, selected_lang), daemon=True).start()
    return {"ok": True, "started": True, "lang": selected_lang}


def voice_speak(text, lang=None):
    global _voice_speak_process
    caps = _get_voice_capabilities()
    utterance = str(text or "").strip()
    requested_lang = str(lang or "").strip()
    selected_lang = _select_native_lang(requested_lang, caps.get("tts_langs") or [])
    if not utterance:
        return {"ok": False, "reason": "empty"}
    if not caps.get("tts_available"):
        return {
            "ok": False,
            "reason": "tts_unavailable",
            "available_langs": list(caps.get("tts_langs") or []),
        }
    if requested_lang and not selected_lang:
        return {
            "ok": False,
            "reason": "language_unavailable",
            "available_langs": list(caps.get("tts_langs") or []),
        }
    if not selected_lang:
        selected_lang = requested_lang or _select_native_lang("", caps.get("tts_langs") or [])
    voice_speak_stop()
    try:
        proc = _spawn_powershell(_build_voice_speak_script(utterance, selected_lang))
    except Exception as exc:
        _dispatch_window_event(
            "aaroncore-native-voice-error",
            {"phase": "speak", "code": "start_failed", "lang": selected_lang, "message": str(exc)},
        )
        return {"ok": False, "reason": "start_failed", "message": str(exc)}

    with _voice_bridge_lock:
        _voice_speak_process = proc
        _voice_state["speaking"] = True
    _emit_native_voice_state()

    def _worker(process: subprocess.Popen, target_lang: str):
        global _voice_speak_process
        stdout_text, stderr_text = process.communicate()
        payload = _parse_powershell_json(stdout_text, stderr_text, default_code="speak_failed")
        should_emit = False
        with _voice_bridge_lock:
            cancelled = id(process) in _voice_speak_cancelled_ids
            _voice_speak_cancelled_ids.discard(id(process))
            if _voice_speak_process is process:
                _voice_speak_process = None
                _voice_state["speaking"] = False
                should_emit = True
        if should_emit:
            _emit_native_voice_state()
        if cancelled:
            return
        if payload.get("ok"):
            return
        _dispatch_window_event(
            "aaroncore-native-voice-error",
            {
                "phase": "speak",
                "code": str(payload.get("code") or "speak_failed"),
                "lang": str(payload.get("lang") or target_lang),
                "message": str(payload.get("message") or "Native speech synthesis failed."),
            },
        )

    threading.Thread(target=_worker, args=(proc, selected_lang), daemon=True).start()
    return {"ok": True, "started": True, "lang": selected_lang}


def _cleanup_native_voice_processes():
    voice_listen_stop()
    voice_speak_stop()


atexit.register(_cleanup_native_voice_processes)

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
    repo_root = Path(__file__).resolve().parent
    os.chdir(str(repo_root))
    subprocess.Popen([r"C:\Program Files\Python311\python.exe", "agent_final.py"])

start_backend()
time.sleep(3)

os.environ['WEBVIEW2_DEFAULT_BACKGROUND_COLOR'] = '161618'

_sw = user32.GetSystemMetrics(0)
_sh = user32.GetSystemMetrics(1)
_ww, _wh = 1100, 900

window = webview.create_window(
    'AaronCore', 'http://localhost:8090/',
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
        window.expose(get_system_theme)
        window.expose(minimize)
        window.expose(toggle_maximize)
        window.expose(close_window)
        window.expose(start_drag)
        window.expose(start_resize)
        window.expose(voice_bridge_status)
        window.expose(voice_listen_start)
        window.expose(voice_listen_stop)
        window.expose(voice_speak)
        window.expose(voice_speak_stop)
        hwnd = _find_hwnd()
        if hwnd:
            window.set_title("")
            if not _original_wndproc:
                _subclass_window(hwnd)
        current_theme = get_system_theme()
        _set_titlebar_theme(dark=(current_theme == "dark"))
        _emit_system_theme(current_theme)
        _start_theme_watch()
        print(f"[desktop] ready, hwnd={hwnd}", flush=True)
        try:
            from core.vision import can_autostart_background_capture as _can_autostart_background_capture

            _vision_enabled, _vision_reason = _can_autostart_background_capture()
            if _vision_enabled:
                from core.vision import init as vi, start as vs
                from brain import vision_llm_call
                vi(llm_call=vision_llm_call)
                vs()
            else:
                print(f"[desktop] vision skipped: {_vision_reason}", flush=True)
        except Exception as e:
            print(f"[desktop] vision: {e}", flush=True)
    threading.Thread(target=_do, daemon=True).start()

window.events.shown += _on_shown

print("AaronCore starting...")
def _resolve_webview_storage():
    appdata_dir = os.environ.get("APPDATA", "")
    if not appdata_dir:
        return "AaronCore"

    aaron_dir = os.path.join(appdata_dir, "AaronCore")
    legacy_profile_dir = os.path.join(appdata_dir, "NovaCore")

    # Keep using the pre-rename webview profile so theme/localStorage/session
    # state survive the legacy NovaCore -> AaronCore rename.
    if os.path.isdir(legacy_profile_dir) and not os.path.isdir(aaron_dir):
        print(f"[desktop] reusing legacy webview storage: {legacy_profile_dir}", flush=True)
        return legacy_profile_dir
    return aaron_dir

_webview_storage = _resolve_webview_storage()
_c = os.path.join(_webview_storage, "EBWebView", "Default", "Cache")
if os.path.isdir(_c):
    import shutil
    try: shutil.rmtree(_c, ignore_errors=True)
    except: pass
webview.start(private_mode=False, storage_path=_webview_storage)
