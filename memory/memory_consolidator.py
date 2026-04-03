# Memory Consolidator - 记忆整合器
# 负责：L3→L4 记忆整合，主题总结

import json
from datetime import datetime
from storage.paths import PRIMARY_STATE_DIR

L3_FILE = PRIMARY_STATE_DIR / "long_term.json"
L4_FILE = PRIMARY_STATE_DIR / "topic_summary.json"


def load_l3():
    """加载L3原始记忆"""
    if L3_FILE.exists():
        return json.loads(L3_FILE.read_text(encoding="utf-8"))
    return []


def load_l4():
    """加载L4主题总结"""
    if L4_FILE.exists():
        return json.loads(L4_FILE.read_text(encoding="utf-8"))
    return {}


def save_l4(l4):
    """保存L4主题总结"""
    L4_FILE.parent.mkdir(parents=True, exist_ok=True)
    L4_FILE.write_text(json.dumps(l4, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_topic(text: str) -> str:
    """从文本提取主题关键词"""
    keywords = {
        "天气": "weather",
        "画图": "image",
        "编程": "code",
        "新闻": "news",
        "翻译": "translate",
        "股票": "stock",
        "记忆": "memory",
        "学习": "learning",
    }
    for kw, topic in keywords.items():
        if kw in text:
            return topic
    return "other"


def consolidate():
    """整合L3生成L4主题总结"""
    l3_memories = load_l3()
    l4_topics = load_l4()
    
    # 按主题分组
    topic_groups = {}
    for mem in l3_memories:
        content = mem.get('content', '')
        topic = extract_topic(content)
        
        if topic not in topic_groups:
            topic_groups[topic] = []
        topic_groups[topic].append(content)
    
    # 生成主题总结
    for topic, contents in topic_groups.items():
        count = len(contents)
        
        if count >= 3:  # 至少3条才生成总结
            summary = f"用户{count}次使用{topic}相关功能"
            
            l4_topics[topic] = {
                "summary": summary,
                "count": count,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
    save_l4(l4_topics)
    return l4_topics


def add_memory(content: str):
    """添加记忆并自动整合"""
    # 1. 写入L3
    l3 = load_l3()
    l3.append({
        "content": content,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    L3_FILE.parent.mkdir(parents=True, exist_ok=True)
    L3_FILE.write_text(json.dumps(l3, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 2. 自动整合L4（每5条整合一次）
    if len(l3) % 5 == 0:
        consolidate()
    
    return {"saved": True, "l3_count": len(l3)}
