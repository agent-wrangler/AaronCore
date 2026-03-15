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
    "乌鲁木齐": ("Urumqi", 43.82, 87.62),
}

DEFAULT_CITY = "常州"
HISTORY_PATH = Path(__file__).resolve().parents[2] / 'memory_db' / 'msg_history.json'
PERSONA_PATH = Path(__file__).resolve().parents[2] / 'memory_db' / 'persona.json'
CITY_ALIASES = {
    "新疆维吾尔自治区": "乌鲁木齐",
    "新疆": "乌鲁木齐",
    "乌市": "乌鲁木齐",
}
FOLLOW_UP_WEATHER_HINTS = (
    "多少度",
    "几度",
    "冷不冷",
    "热不热",
    "下雨",
    "下雪",
    "有雨",
    "有雪",
    "会不会",
    "还冷吗",
    "天气呢",
    "温度呢",
    "气温呢",
)
FOLLOW_UP_WEATHER_TEXTS = {
    "",
    "明天",
    "后天",
    "今天",
    "这周",
    "未来几天",
    "还冷吗",
    "会下雨吗",
    "会下雪吗",
}


def _load_user_default_city() -> str:
    """从 persona.json 的 user_profile.city 读取用户默认城市"""
    try:
        if PERSONA_PATH.exists():
            data = json.loads(PERSONA_PATH.read_text(encoding='utf-8'))
            city = str((data.get('user_profile') or {}).get('city') or '').strip()
            if city and city in CITIES:
                return city
    except Exception:
        pass
    return ""


def _save_user_default_city(city: str):
    """把用户查过的城市存入 persona.json 的 user_profile.city"""
    try:
        data = {}
        if PERSONA_PATH.exists():
            data = json.loads(PERSONA_PATH.read_text(encoding='utf-8'))
        if not isinstance(data.get('user_profile'), dict):
            data['user_profile'] = {}
        data['user_profile']['city'] = city
        PERSONA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _load_recent_messages(limit: int = 12):
    try:
        if HISTORY_PATH.exists():
            data = json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
            return data[-limit:]
    except Exception:
        pass
    return []


def _resolve_city(text: str) -> str | None:
    content = str(text or "").strip()
    if not content:
        return None

    for alias, city in CITY_ALIASES.items():
        if alias in content:
            return city

    for city in CITIES.keys():
        if city in content:
            return city

    return None


def _clean_weather_query(text: str) -> str:
    cleaned = re.sub(r'[？?，。呀啊呢嘛吧啦哦哇呗～~、\s]', '', str(text or ''))
    replacements = (
        '今天天气怎么样',
        '天气怎么样',
        '天气如何',
        '什么天气',
        '天气',
        '气温',
        '温度',
        '查询',
        '查一下',
        '查查',
        '看一下',
        '看看',
        '现在',
        '目前',
        '多少',
        '度',
        '会不会',
        '有没有',
    )
    for item in replacements:
        cleaned = cleaned.replace(item, '')
    return cleaned.strip()


def _infer_city_from_history() -> str:
    recent = _load_recent_messages(12)
    for item in reversed(recent):
        content = str(item.get('content', ''))
        resolved = _resolve_city(content)
        if resolved:
            return resolved
    return ""


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
    resolved = _resolve_city(text)
    if resolved:
        return resolved

    cleaned = _clean_weather_query(text)
    resolved = _resolve_city(cleaned)
    if resolved:
        return resolved

    # 只有没有新地点信息的天气追问，才从最近对话继承城市
    if cleaned in FOLLOW_UP_WEATHER_TEXTS or (not cleaned and any(word in text for word in FOLLOW_UP_WEATHER_HINTS)):
        return _infer_city_from_history()

    return ""


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
    if not city:
        city = _load_user_default_city()
    if not city:
        return "你想看哪个城市呀？比如上海、北京、乌鲁木齐这样，告诉我一次后面就记住啦。"

    # 记住用户查过的城市作为默认
    _save_user_default_city(city)

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
