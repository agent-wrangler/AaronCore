# 天气查询技能 - 动态城市
import requests
import re
from pathlib import Path
import json

# 常用城市映射
CITIES = {
    "常州": ("Changzhou", 31.81, 119.97),
    "北京": ("Beijing", 39.90, 116.40),
    "上海": ("Shanghai", 31.23, 121.47),
    "苏州": ("Suzhou", 31.30, 120.58),
    "南京": ("Nanjing", 32.06, 118.79),
    "杭州": ("Hangzhou", 30.24, 120.15),
    "广州": ("Guangzhou", 23.13, 113.27),
    "深圳": ("Shenzhen", 22.55, 114.06),
    "大理": ("Dali", 25.04, 100.29),
    "纽约": ("New York", 40.71, -74.01),
    "东京": ("Tokyo", 35.68, 139.69),
    "伦敦": ("London", 51.51, -0.13),
    "巴黎": ("Paris", 48.86, 2.35),
    "首尔": ("Seoul", 37.57, 126.98),
}

DEFAULT_CITY = "常州"
HISTORY_PATH = Path(__file__).resolve().parents[2] / 'memory_db' / 'msg_history.json'


def _load_recent_messages(limit: int = 12):
    try:
        if HISTORY_PATH.exists():
            data = json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
            return data[-limit:]
    except Exception:
        pass
    return []


def _infer_city_from_history() -> str:
    recent = _load_recent_messages(12)
    for item in reversed(recent):
        content = str(item.get('content', ''))
        for city in CITIES.keys():
            if city in content:
                return city
    return DEFAULT_CITY


def get_weather(city_cn, coords):
    try:
        lat, lon = coords
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json().get('current', {})
        temp = data.get('temperature_2m', '?')
        code = data.get('weather_code', 0)
        desc = {0:'晴',1:'晴',2:'多云',3:'阴',45:'雾',61:'小雨',71:'小雪',80:'阵雨',95:'雷暴'}.get(code, str(code))
        return f"📍 {city_cn}现在 {temp}°C，{desc}"
    except Exception:
        return None


def _extract_city(query: str) -> str:
    text = (query or '').strip()

    # 先直接命中城市名
    for city in CITIES.keys():
        if city in text:
            return city

    # 清理常见无意义词，避免剩下一堆语气词
    cleaned = re.sub(r'[？?，。呀啊呢嘛吧啦哦哇呗]', '', text)
    cleaned = cleaned.replace('今天天气怎么样', '').replace('天气怎么样', '').replace('天气如何', '')
    cleaned = cleaned.replace('天气', '').replace('气温', '').replace('温度', '').replace('查询', '')
    cleaned = cleaned.strip()

    for city in CITIES.keys():
        if cleaned == city:
            return city

    # 像“明天呢 / 后天呢 / 未来几天呢”这种短追问，从最近对话继承城市
    if any(word in text for word in ['明天', '后天', '未来', '下周', '今天', '这周']) or len(cleaned) <= 4:
        return _infer_city_from_history()

    return DEFAULT_CITY


def _extract_day_offset(query: str) -> int:
    text = (query or '').strip()
    if '后天' in text:
        return 2
    if '明天' in text:
        return 1
    return 0


def get_forecast(city_cn, coords, day_offset: int = 0):
    try:
        lat, lon = coords
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=7"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        daily = resp.json().get('daily', {})
        dates = daily.get('time', [])
        maxs = daily.get('temperature_2m_max', [])
        mins = daily.get('temperature_2m_min', [])
        codes = daily.get('weather_code', [])
        if not dates:
            return None
        idx = min(max(day_offset, 0), len(dates) - 1)
        label = '今天' if idx == 0 else '明天' if idx == 1 else '后天' if idx == 2 else dates[idx]
        code = codes[idx] if idx < len(codes) else 0
        desc = {0:'晴',1:'晴',2:'多云',3:'阴',45:'雾',61:'小雨',71:'小雪',80:'阵雨',95:'雷暴'}.get(code, str(code))
        return f"📍 {city_cn}{label}：{mins[idx]}~{maxs[idx]}°C，{desc}"
    except Exception:
        return None


def execute(query):
    city = _extract_city(query)
    _, lat, lon = CITIES[city]
    day_offset = _extract_day_offset(query)
    if day_offset > 0:
        result = get_forecast(city, (lat, lon), day_offset)
    else:
        result = get_weather(city, (lat, lon))
    if result:
        return result
    return f"我这次没查到{city}的天气，你再让我试一次嘛。"


if __name__ == "__main__":
    print(execute("纽约天气"))
    print(execute("东京天气"))
    print(execute("苏州天气"))
    print(execute("今天天气怎么样呀"))
