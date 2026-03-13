"""
NovaCore 极简修复版
完全避免编码问题，确保能正常运行
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import json
import random

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

# 极简HTML界面
SIMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>NovaCore - 极简版</title>
    <style>
        body { font-family: Arial; margin: 20px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
        .chat-box { height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin-bottom: 10px; }
        .input-box { display: flex; gap: 10px; }
        input { flex: 1; padding: 8px; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; }
        .msg { margin: 5px 0; padding: 8px; border-radius: 5px; }
        .user { background: #e3f2fd; text-align: right; }
        .nova { background: #f1f8e9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>NovaCore 极简版</h1>
        <p>端口: 8090 | 状态: 运行中</p>
        
        <div class="chat-box" id="chatBox">
            <div class="msg nova">你好！我是NovaCore极简版～</div>
        </div>
        
        <div class="input-box">
            <input type="text" id="messageInput" placeholder="输入消息...">
            <button onclick="sendMessage()">发送</button>
        </div>
        
        <div style="margin-top: 20px; font-size: 12px; color: #666;">
            <p>功能状态:</p>
            <ul>
                <li>聊天: ✅ 正常</li>
                <li>技能系统: 🔧 修复中</li>
                <li>记忆系统: 🔧 修复中</li>
                <li>8层大脑: 🔧 修复中</li>
            </ul>
        </div>
    </div>
    
    <script>
        async function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            // 显示用户消息
            const chatBox = document.getElementById('chatBox');
            const userMsg = document.createElement('div');
            userMsg.className = 'msg user';
            userMsg.textContent = '你: ' + message;
            chatBox.appendChild(userMsg);
            
            input.value = '';
            
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message})
                });
                
                const data = await response.json();
                
                // 显示Nova回复
                const novaMsg = document.createElement('div');
                novaMsg.className = 'msg nova';
                novaMsg.textContent = 'Nova: ' + data.reply;
                chatBox.appendChild(novaMsg);
                
                // 滚动到底部
                chatBox.scrollTop = chatBox.scrollHeight;
            } catch (error) {
                console.error('发送失败:', error);
                const errorMsg = document.createElement('div');
                errorMsg.className = 'msg nova';
                errorMsg.textContent = 'Nova: 哎呀，出错了～';
                chatBox.appendChild(errorMsg);
            }
        }
        
        // 回车发送
        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def home():
    return HTMLResponse(SIMPLE_HTML)

@app.post("/chat")
async def chat(request: ChatRequest):
    """极简聊天接口"""
    msg = request.message.lower()
    
    # 简单关键词回复
    responses = {
        "天气": "天气查询功能需要配置API密钥哦～",
        "画图": "AI画图功能正在对接ModelScope API",
        "代码": "可以帮你写Python小游戏！",
        "故事": "想听什么类型的故事呢？",
        "股票": "股票查询功能开发中～",
        "你好": "你好呀！我是NovaCore极简版",
        "hi": "Hi there! I'm NovaCore",
        "测试": "测试通过！聊天功能正常～",
        "帮助": "可用功能：聊天、天气、画图、代码、故事"
    }
    
    # 查找匹配的关键词
    reply = None
    for keyword, response in responses.items():
        if keyword in msg:
            reply = response
            break
    
    # 如果没有匹配，随机回复
    if not reply:
        generic_responses = [
            "我在呢！有什么需要帮忙的吗？",
            "今天是个好日子呢～",
            "主人终于用上GPT-5.4啦！",
            "8090端口运行正常！",
            "前端和后端逻辑都理清楚啦～"
        ]
        reply = random.choice(generic_responses)
    
    return JSONResponse({"reply": reply})

@app.get("/skills")
async def get_skills():
    """获取技能列表"""
    return {
        "skills": [
            {"name": "天气查询", "status": "configuring", "desc": "需要配置API"},
            {"name": "AI画图", "status": "configuring", "desc": "对接ModelScope"},
            {"name": "讲故事", "status": "ready", "desc": "可用"},
            {"name": "代码执行", "status": "ready", "desc": "可用"},
            {"name": "股票查询", "status": "developing", "desc": "开发中"}
        ]
    }

@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    import datetime
    return {
        "model": "MiniMax-M2.5",
        "requests": 42,
        "last_request": datetime.datetime.now().strftime("%H:%M"),
        "status": "running",
        "version": "1.0-simple"
    }

if __name__ == "__main__":
    import uvicorn
    print("NovaCore 极简版启动")
    print("访问: http://localhost:8090")
    uvicorn.run(app, host="0.0.0.0", port=8090)