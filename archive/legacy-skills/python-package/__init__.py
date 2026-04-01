# Skills - L5 技能路由
import sys
from pathlib import Path

# 动态导入tools
tools_dir = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(tools_dir))
import tools

SKILLS = {
    "天气": {
        "keywords": ["天气", "温度", "下雨", "晴天", "冷", "热"],
        "intent": ["天气"],
        "handler": tools.get_weather
    },
    "开网站": {
        "keywords": ["打开", "开", "访问", "去"],
        "intent": ["网站", "打开"],
        "handler": tools.open_website
    },
    "搜索": {
        "keywords": ["搜索", "查一下", "找", "问问"],
        "intent": ["搜索"],
        "handler": tools.search_web
    },
    "AI画图": {
        "keywords": ["画", "生成图片", "做图", "海报", "AI画", "生成"],
        "intent": ["画图", "AI画图", "生成图片"],
        "handler": tools.generate_image
    }
}

def route(intent_data: dict) -> tuple:
    """L5: 技能路由 - 判断用什么技能"""
    intent = intent_data.get("intent", "")
    action = intent_data.get("action", "")
    target = intent_data.get("target", "")
    
    # 不需要工具
    if not intent_data.get("need_tool", False):
        return None, None
    
    # 先精确匹配intent
    for skill_name, skill_info in SKILLS.items():
        if any(i in intent for i in skill_info.get("intent", [])):
            return skill_info["handler"], {"target": target, "action": action}
    
    # 再模糊匹配keywords
    combined = action + " " + target
    for skill_name, skill_info in SKILLS.items():
        for kw in skill_info["keywords"]:
            if kw in combined:
                return skill_info["handler"], {"target": target, "action": action}
    
    return None, None

def execute_skill(handler, params: dict):
    """L6: 执行技能"""
    if handler and callable(handler):
        return handler(params)
    return None
