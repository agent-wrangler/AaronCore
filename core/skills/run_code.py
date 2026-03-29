# 编程游戏技能
import subprocess
import os
from datetime import datetime
from pathlib import Path
import requests
import json
import sys

CONNECT_TIMEOUT = 15      # 连接超时（秒）— 连不上就快速失败
READ_TIMEOUT    = 120     # 读取超时（秒）— 生成代码可能较慢，给够时间


def execute(user_request):
    """生成Python游戏并运行"""
    # 加载LLM配置
    config_path = Path(__file__).resolve().parents[2] / "brain" / "llm_config.json"
    if config_path.exists():
        _raw = json.load(open(config_path, 'r', encoding='utf-8'))
        if "models" in _raw:
            _default = _raw.get("default", "")
            _models = _raw["models"]
            llm_config = _models.get(_default) or next(iter(_models.values()))
        else:
            llm_config = _raw
    else:
        llm_config = {"api_key": "", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"}
    
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
        from brain import llm_call
        result = llm_call(llm_config, [{"role": "user", "content": prompt}],
                          temperature=0.7, max_tokens=2000, timeout=(CONNECT_TIMEOUT + READ_TIMEOUT))
        code = result.get("content", "")
        
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
            subprocess.Popen(
                [sys.executable, temp_path],
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        else:
            subprocess.Popen([sys.executable, temp_path])
        
        return "游戏启动啦！玩得开心哦～🎮"
    except Exception as e:
        return f"启动失败：{str(e)[:50]}"
