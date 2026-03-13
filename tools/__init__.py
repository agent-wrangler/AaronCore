# Tools - 工具系统
import os
import subprocess
import requests

def get_weather(params: dict) -> str:
    """天气查询"""
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=31.81&longitude=119.97&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=Asia/Shanghai"
        data = requests.get(url, timeout=15).json()
        daily = data.get('daily', {})
        temps = daily.get('temperature_2m_max', [])[:3]
        rain = daily.get('precipitation_probability_max', [])[:3]
        
        result = "常州天气预报：\n"
        days = ["今天", "明天", "后天"]
        for i in range(len(temps)):
            result += f"{days[i]}: {temps[i]}°C, 降雨{rain[i]}%\n"
        return result
    except Exception as e:
        return None  # 让LLM处理

def open_website(params: dict) -> str:
    """打开网站"""
    target = params.get("target", "")
    
    # 网站映射
    sites = {
        "百度": "https://www.baidu.com",
        "淘宝": "https://www.taobao.com",
        "京东": "https://www.jd.com",
        "抖音": "https://www.douyin.com",
        "b站": "https://www.bilibili.com",
        "知乎": "https://www.zhihu.com",
        "微博": "https://weibo.com",
    }
    
    url = sites.get(target, f"https://www.baidu.com/s?wd={target}")
    
    try:
        os.startfile(url)
        return f"好哒～帮你打开{tool}啦～"
    except:
        return None

def search_web(params: dict) -> str:
    """网页搜索"""
    target = params.get("target", "")
    if not target:
        return None
    
    url = f"https://www.baidu.com/s?wd={target}"
    try:
        os.startfile(url)
        return f"好～帮你搜「{target}」啦～"
    except:
        return None

def generate_image(params: dict) -> str:
    """AI画图 - 暂不可用"""
    return None

def open_website(params: dict) -> str:
    """打开网站"""
    target = params.get("target", "")
    
    # 网站映射
    sites = {
        "百度": "https://www.baidu.com",
        "淘宝": "https://www.taobao.com",
        "京东": "https://www.jd.com",
        "抖音": "https://www.douyin.com",
        "b站": "https://www.bilibili.com",
        "bilibili": "https://www.bilibili.com",
        "知乎": "https://www.zhihu.com",
        "微博": "https://weibo.com",
        "谷歌": "https://www.google.com",
        "youtube": "https://www.youtube.com",
    }
    
    url = sites.get(target, None)
    
    # 如果没匹配到，尝试搜索
    if not url:
        url = f"https://www.baidu.com/s?wd={target}"
    
    try:
        os.startfile(url)
        return f"好哒～帮你打开{target}啦～"
    except:
        return f"打开失败啦..."

def search_web(params: dict) -> str:
    """网页搜索"""
    target = params.get("target", "")
    if not target:
        return "要搜什么呢？"
    
    url = f"https://www.baidu.com/s?wd={target}"
    try:
        os.startfile(url)
        return f"好～帮你搜「{target}」啦～"
    except:
        return "搜索失败啦..."

def generate_image(params: dict) -> str:
    """AI画图 - 返回提示让Nova自己回复"""
    return None  # 暂时不支持，返回None让LLM处理
