# 编程游戏技能
import subprocess
import os
from datetime import datetime
import requests
import json
import sys

def execute(user_request):
    """生成Python游戏并运行"""
    # 加载LLM配置
    config_path = os.path.join(os.path.dirname(__file__), '..', 'brain', 'llm_config.json')
    if os.path.exists(config_path):
        llm_config = json.load(open(config_path, 'r', encoding='utf-8'))
    else:
        llm_config = {"api_key": "", "model": "abab6.5s-chat", "base_url": "https://api.minimax.chat/v1"}
    
    # 用LLM生成游戏代码
    prompt = f"""用户想要：{user_request}

请生成一个完整的Python游戏程序。
要求：
1. 必须用tkinter做图形界面
2. 游戏要能直接运行，打开就能玩
3. 窗口大小约400x300
4. 包含游戏主循环
5. 直接输出代码，不要解释

只输出代码，不要其他内容。"""
    
    try:
        resp = requests.post(
            f"{llm_config['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {llm_config['api_key']}", "Content-Type": "application/json"},
            json={"model": llm_config['model'], "messages": [{"role": "user", "content": prompt}], "temperature": 0.7},
            timeout=30
        )
        code = resp.json()["choices"][0]["message"]["content"]
        
        # 清理代码
        if "```" in code:
            lines = code.split("\n")
            code = "\n".join([l for l in lines if not l.strip().startswith("```")])
        
        # 保存到临时文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"nova_game_{timestamp}.py"
        temp_path = os.path.join(os.environ.get('TEMP', '/tmp'), filename)
        
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(code)
        
        # 运行游戏
        if os.name == 'nt':
            subprocess.Popen([sys.executable, temp_path], detached=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen([sys.executable, temp_path])
        
        return "游戏启动啦！玩得开心哦～🎮"
    except Exception as e:
        return f"启动失败：{str(e)[:50]}"
