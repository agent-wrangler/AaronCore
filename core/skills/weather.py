import json
import re
from pathlib import Path

import requests


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
    "邢台": ("Xingtai", 37.07, 114.50),
}

DEFAULT_CITY = "常州"
HISTORY_PATH = Path(__file__).resolve().parents[2] / "memory_db" / "msg_history.json"
PERSONA_PATH = Path(__file__).resolve().parents[2] / "memory_db" / "persona.json"

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
    "天气吗",
    "温度吗",
    "气温吗",
)

FOLLOW_UP_WEATHER_TEXTS = {
    "",
    "今天",
    "明天",
    "后天",
    "这周",
    "未来几天",
    "还冷吗",
    "会下雨吗",
    "会下雪吗",
}


def _load_user_default_city() -> str:
    try:
        if PERSONA_PATH.exists():
            data = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
            city = str((data.get("user_profile") or {}).get("city") or "").strip()
            if city in CITIES:
                return city
    except Exception:
        pass
    return ""


def _save_user_default_city(city: str):
    try:
        data = {}
        if PERSONA_PATH.exists():
            data = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
        if not isinstance(data.get("user_profile"), dict):
            data["user_profile"] = {}
        data["user_profile"]["city"] = city
        PERSONA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_recent_messages(limit: int = 12):
    try:
        if HISTORY_PATH.exists():
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
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

    for city in CITIES:
        if city in content:
            return city

    return None


def _clean_weather_query(text: str) -> str:
    cleaned = re.sub(r"[，。？！、\s]", "", str(text or ""))
    replacements = (
        "今天天气怎么样",
        "天气怎么样",
        "天气如何",
        "什么天气",
        "天气",
        "气温",
        "温度",
        "查询",
        "查一个",
        "查查",
        "看一个",
        "看看",
        "现在",
        "目前",
        "多少",
        "度",
        "会不会",
        "有没有",
    )
    for item in replacements:
        cleaned = cleaned.replace(item, "")
    return cleaned.strip()


def _infer_city_from_history() -> str:
    recent = _load_recent_messages(12)
    for item in reversed(recent):
        content = str(item.get("content", ""))
        resolved = _resolve_city(content)
        if resolved:
            return resolved
    return ""


def _extract_city(query: str) -> str:
    text = (query or "").strip()
    resolved = _resolve_city(text)
    if resolved:
        return resolved

    cleaned = _clean_weather_query(text)
    resolved = _resolve_city(cleaned)
    if resolved:
        return resolved

    if cleaned in FOLLOW_UP_WEATHER_TEXTS or (not cleaned and any(word in text for word in FOLLOW_UP_WEATHER_HINTS)):
        return _infer_city_from_history()

    return ""


def _extract_day_offset(query: str) -> int:
    text = (query or "").strip()
    if "后天" in text:
        return 2
    if "明天" in text:
        return 1
    return 0


def _weather_desc(code):
    return {
        0: "晴",
        1: "晴",
        2: "多云",
        3: "阴",
        45: "雾",
        61: "小雨",
        71: "小雪",
        80: "阵雨",
        95: "雷暴",
    }.get(code, str(code))


def _resolve_city_coords(city_name: str):
    city = str(city_name or "").strip()
    if not city:
        return None
    if city in CITIES:
        _, lat, lon = CITIES[city]
        return city, (lat, lon)
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh", "format": "json"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = (resp.json() or {}).get("results") or []
        if not results:
            return None
        first = results[0]
        lat = first.get("latitude")
        lon = first.get("longitude")
        if lat is None or lon is None:
            return None
        resolved_name = str(first.get("name") or city).strip() or city
        return resolved_name, (float(lat), float(lon))
    except Exception:
        return None


def _fetch_current(coords):
    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weather_code&timezone=auto"
    )
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    return resp.json().get("current", {})


def _fetch_daily_forecast(coords, days: int = 7):
    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days={days}"
    )
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return None
    daily = resp.json().get("daily", {})
    if not daily or not daily.get("time"):
        return None
    return daily


def _forecast_label(idx: int, dates: list[str]) -> str:
    if idx == 0:
        return "今天"
    if idx == 1:
        return "明天"
    if idx == 2:
        return "后天"
    return dates[idx] if 0 <= idx < len(dates) else f"D+{idx}"


def get_weather(city_cn, coords):
    try:
        current = _fetch_current(coords)
        if not current:
            return None
        temp = current.get("temperature_2m", "?")
        code = current.get("weather_code", 0)
        return f"📍 {city_cn}现在 {temp}°C，{_weather_desc(code)}"
    except Exception:
        return None


def get_forecast(city_cn, coords, day_offset: int = 0):
    try:
        daily = _fetch_daily_forecast(coords, 7)
        if not daily:
            return None
        dates = daily.get("time", [])
        maxs = daily.get("temperature_2m_max", [])
        mins = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        if not dates:
            return None
        idx = min(max(day_offset, 0), len(dates) - 1)
        label = _forecast_label(idx, dates)
        low = mins[idx] if idx < len(mins) else "?"
        high = maxs[idx] if idx < len(maxs) else "?"
        code = codes[idx] if idx < len(codes) else 0
        return f"📍 {city_cn}{label}：{low}~{high}°C，{_weather_desc(code)}"
    except Exception:
        return None


def get_forecast_window(city_cn, coords, focus_offset: int = 0, span: int = 7):
    try:
        daily = _fetch_daily_forecast(coords, max(7, focus_offset + span + 1))
        if not daily:
            return None
        dates = daily.get("time", [])
        maxs = daily.get("temperature_2m_max", [])
        mins = daily.get("temperature_2m_min", [])
        codes = daily.get("weather_code", [])
        if not dates:
            return None

        start = min(max(focus_offset, 0), len(dates) - 1)
        end = min(len(dates), start + max(span, 1))
        lines = []
        for idx in range(start, end):
            label = _forecast_label(idx, dates)
            low = mins[idx] if idx < len(mins) else "?"
            high = maxs[idx] if idx < len(maxs) else "?"
            code = codes[idx] if idx < len(codes) else 0
            prefix = "📍 " if idx == start else "   "
            lines.append(f"{prefix}{label}：{low}~{high}°C，{_weather_desc(code)}")
        return f"{city_cn}{_forecast_label(start, dates)}天气：\n" + "\n".join(lines)
    except Exception:
        return None


def execute(query, context=None):
    city = _extract_city(query)
    if not city and isinstance(context, dict) and context.get("city"):
        city = str(context["city"]).strip()
    if not city and isinstance(context, dict) and context.get("user_city"):
        city = str(context["user_city"]).strip()
    if not city:
        city = _load_user_default_city()
    if not city:
        return "你想看哪个城市呀？比如上海、北京、乌鲁木齐这样，告诉我一次后面就记住啦。"

    resolved = _resolve_city_coords(city)
    if not resolved:
        return f"我暂时没法确认「{city}」对应的城市位置，你可以再说得完整一点，比如加上省市名。"

    city, coords = resolved
    _save_user_default_city(city)

    text = str(query or "")
    day_offset = _extract_day_offset(text)
    wants_window = day_offset > 0 or any(token in text for token in ("今天", "明天", "后天", "这周", "未来", "几天"))

    if wants_window:
        result = get_forecast_window(city, coords, day_offset, span=7)
    else:
        current = get_weather(city, coords)
        trend = get_forecast_window(city, coords, 0, span=7)
        result = "\n".join([part for part in (current, trend) if part])

    if result:
        return result
    return f"我这次没查到{city}的天气，你再让我试一次嘛。"


if __name__ == "__main__":
    print(execute("纽约天气"))
    print(execute("东京天气"))
    print(execute("苏州天气"))
    print(execute("今天天气怎么样呀"))
