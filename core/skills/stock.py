# 股票查询技能
import re
from datetime import datetime

import requests


QUOTE_API = "https://qt.gtimg.cn/q="
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.qq.com/",
}

SYMBOL_ALIASES = {
    "苹果": "usAAPL",
    "apple": "usAAPL",
    "aapl": "usAAPL",
    "英伟达": "usNVDA",
    "nvidia": "usNVDA",
    "nvda": "usNVDA",
    "特斯拉": "usTSLA",
    "tesla": "usTSLA",
    "tsla": "usTSLA",
    "微软": "usMSFT",
    "microsoft": "usMSFT",
    "msft": "usMSFT",
    "亚马逊": "usAMZN",
    "amazon": "usAMZN",
    "amzn": "usAMZN",
    "meta": "usMETA",
    "facebook": "usMETA",
    "脸书": "usMETA",
    "谷歌": "usGOOGL",
    "google": "usGOOGL",
    "alphabet": "usGOOGL",
    "googl": "usGOOGL",
    "goog": "usGOOG",
    "amd": "usAMD",
    "英特尔": "usINTC",
    "intel": "usINTC",
    "intc": "usINTC",
    "奈飞": "usNFLX",
    "netflix": "usNFLX",
    "nflx": "usNFLX",
    "贵州茅台": "sh600519",
    "五粮液": "sz000858",
    "宁德时代": "sz300750",
    "比亚迪": "sz002594",
    "上证指数": "sh000001",
    "上证": "sh000001",
    "沪指": "sh000001",
    "深证成指": "sz399001",
    "深成指": "sz399001",
    "创业板指": "sz399006",
    "创业板": "sz399006",
    "纳斯达克": "usIXIC",
    "纳指": "usIXIC",
    "道琼斯": "usDJI",
    "道指": "usDJI",
    "标普500": "usINX",
    "标普": "usINX",
}

INDEX_SYMBOLS = {"sh000001", "sz399001", "sz399006", "usDJI", "usIXIC", "usINX"}
CN_OVERVIEW = [("上证指数", "sh000001"), ("深证成指", "sz399001"), ("创业板指", "sz399006")]
US_OVERVIEW = [("道琼斯", "usDJI"), ("纳斯达克", "usIXIC"), ("标普500", "usINX")]
STOCK_CONTEXT_WORDS = (
    "股票",
    "股价",
    "行情",
    "报价",
    "大盘",
    "指数",
    "美股",
    "a股",
    "港股",
    "涨跌",
    "多少",
    "怎么样",
    "现在",
    "查",
    "看下",
)
TICKER_STOP_WORDS = {"USD", "CNY", "ETF", "NOW", "HOW", "WHY", "WHAT", "THE", "AND"}


def _dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _normalize_timestamp(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""

    if re.fullmatch(r"\d{14}", text):
        try:
            return datetime.strptime(text, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return text
    return text


def _safe_float(value, default=0.0):
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return default


def _format_number(value: float, digits: int = 2) -> str:
    if abs(value) >= 1000:
        return f"{value:,.{digits}f}"
    return f"{value:.{digits}f}"


def _format_signed(value: float, digits: int = 2) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{digits}f}"


def _is_overview_query(text: str) -> str | None:
    raw = str(text or "").strip()
    lower = raw.lower()

    if any(word in raw for word in ["大盘", "三大指数", "沪深", "股市怎么样", "今天行情", "行情怎么样"]):
        return "cn"
    if "a股" in lower and any(word in raw for word in ["怎么样", "行情", "指数", "大盘"]):
        return "cn"
    if "美股" in lower and any(word in raw for word in ["怎么样", "行情", "指数", "大盘"]):
        return "us"
    return None


def _extract_alias_symbols(text: str) -> list[str]:
    normalized = str(text or "").lower()
    matches = []
    for alias, symbol in sorted(SYMBOL_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in normalized:
            matches.append(symbol)
    return _dedupe_keep_order(matches)


def _extract_prefixed_cn_codes(text: str) -> list[str]:
    normalized = str(text or "").lower()
    return _dedupe_keep_order(re.findall(r"\b(?:sh|sz)\d{6}\b", normalized))


def _extract_plain_cn_codes(text: str) -> list[str]:
    out = []
    for code in re.findall(r"(?<!\d)(\d{6})(?!\d)", str(text or "")):
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
        out.append(prefix + code)
    return _dedupe_keep_order(out)


def _extract_us_tickers(text: str) -> list[str]:
    raw = str(text or "").strip()
    normalized = raw.lower()
    has_context = any(word in normalized for word in STOCK_CONTEXT_WORDS)
    tokens = re.findall(r"(?<![A-Za-z])([A-Za-z]{2,5})(?![A-Za-z])", raw)
    out = []
    stripped_upper = raw.strip().upper()

    for token in tokens:
        upper = token.upper()
        if upper in TICKER_STOP_WORDS:
            continue
        if has_context or stripped_upper == upper:
            out.append("us" + upper)
    return _dedupe_keep_order(out)


def _extract_symbols(query: str) -> tuple[str | None, list[str]]:
    overview_mode = _is_overview_query(query)
    if overview_mode == "cn":
        return "cn", [item[1] for item in CN_OVERVIEW]
    if overview_mode == "us":
        return "us", [item[1] for item in US_OVERVIEW]

    symbols = []
    symbols.extend(_extract_alias_symbols(query))
    symbols.extend(_extract_prefixed_cn_codes(query))
    symbols.extend(_extract_plain_cn_codes(query))
    symbols.extend(_extract_us_tickers(query))
    symbols = _dedupe_keep_order(symbols)

    if not symbols and any(word in str(query or "") for word in ("大盘", "行情")):
        return "cn", [item[1] for item in CN_OVERVIEW]

    return None, symbols[:3]


def _parse_quote(symbol: str, parts: list[str]) -> dict | None:
    if len(parts) < 35 or not parts[1]:
        return None

    name = re.sub(r"\s+", "", parts[1]).strip()
    raw_code = str(parts[2] or symbol).strip()
    code = raw_code.lstrip(".").split(".")[0].upper() if symbol.startswith("us") else raw_code
    current = _safe_float(parts[3])
    prev_close = _safe_float(parts[4])
    open_price = _safe_float(parts[5])
    change = _safe_float(parts[31] if len(parts) > 31 else 0)
    change_percent = _safe_float(parts[32] if len(parts) > 32 else 0)
    high = _safe_float(parts[33] if len(parts) > 33 else 0)
    low = _safe_float(parts[34] if len(parts) > 34 else 0)
    updated_at = _normalize_timestamp(parts[30] if len(parts) > 30 else "")
    is_index = symbol in INDEX_SYMBOLS or "指数" in name or symbol in {"usDJI", "usIXIC", "usINX"}

    if not current:
        return None

    return {
        "symbol": symbol,
        "code": code,
        "name": name,
        "current": current,
        "prev_close": prev_close,
        "open": open_price,
        "high": high,
        "low": low,
        "change": change,
        "change_percent": change_percent,
        "updated_at": updated_at,
        "is_index": is_index,
        "unit": "点" if is_index else ("USD" if symbol.startswith("us") else "元"),
    }


def _fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    if not symbols:
        return {}

    resp = requests.get(QUOTE_API + ",".join(symbols), timeout=10, headers=REQUEST_HEADERS)
    resp.raise_for_status()
    resp.encoding = "gbk"

    quotes = {}
    for chunk in resp.text.split(";"):
        line = chunk.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        symbol = key.replace("v_", "").strip()
        body = value.strip().strip('"')
        if not body:
            continue
        parsed = _parse_quote(symbol, body.split("~"))
        if parsed:
            quotes[symbol] = parsed
    return quotes


def _format_single_quote(quote: dict) -> str:
    current = _format_number(quote["current"])
    change = _format_signed(quote["change"])
    change_pct = _format_signed(quote["change_percent"])
    open_price = _format_number(quote["open"])
    high = _format_number(quote["high"])
    low = _format_number(quote["low"])
    label = f"{quote['name']}（{quote['code']}）" if quote["code"] else quote["name"]
    current_with_unit = f"{current}{quote['unit']}" if quote["unit"] == "点" else f"{current} {quote['unit']}"

    return (
        f"{label} 现在 {current_with_unit}，较昨收 {change}（{change_pct}%）。\n"
        f"今开 {open_price}，最高 {high}，最低 {low}。\n"
        f"更新时间：{quote['updated_at'] or '刚刚'}"
    )


def _format_multi_quotes(quotes: list[dict], headline: str) -> str:
    lines = [headline]
    times = []

    for quote in quotes:
        current = _format_number(quote["current"])
        change = _format_signed(quote["change"])
        change_pct = _format_signed(quote["change_percent"])
        label = f"{quote['name']}（{quote['code']}）" if quote["code"] else quote["name"]
        current_with_unit = f"{current}{quote['unit']}" if quote["unit"] == "点" else f"{current} {quote['unit']}"
        lines.append(f"- {label}：{current_with_unit}，{change}（{change_pct}%）")
        if quote["updated_at"]:
            times.append(quote["updated_at"])

    if times:
        lines.append(f"更新时间：{max(times)}")
    return "\n".join(lines)


def execute(query):
    overview_mode, symbols = _extract_symbols(query)
    if not symbols:
        return (
            "我现在能查美股代码和常见指数啦，比如 NVDA / AAPL，或者纳指、标普、道指、沪指、深成指、创业板。"
            "你也可以直接发 6 位股票代码给我。"
        )

    try:
        quotes_map = _fetch_quotes(symbols)
    except Exception:
        return "我这次没把行情抓回来，可能是数据源刚刚抽了一下，你再让我查一次嘛。"

    quotes = [quotes_map[symbol] for symbol in symbols if symbol in quotes_map]
    if not quotes:
        return "这次我没识别到有效的股票/指数结果，你给我代码或者更明确一点的名字，我再帮你查。"

    if overview_mode == "cn":
        return _format_multi_quotes(quotes, "A股这边我先给你看一眼三大指数：")
    if overview_mode == "us":
        return _format_multi_quotes(quotes, "美股这边我先给你看一眼三大指数：")
    if len(quotes) == 1:
        return _format_single_quote(quotes[0])
    return _format_multi_quotes(quotes, "我先给你查到这几只：")


if __name__ == "__main__":
    print(execute("今天大盘怎么样"))
    print(execute("NVDA股价多少"))
    print(execute("贵州茅台"))
