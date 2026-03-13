"""
NovaCore Agent Engine v1
"""
import sys
import requests
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import random

engine_dir = Path(__file__).parent
core_dir = engine_dir / "core"

try:
    sys.path.insert(0, str(core_dir))
    from router import route as neuro_route
    from executor import execute as neuro_execute
    NOVA_CORE_READY = True
except:
    NOVA_CORE_READY = False

sys.path.insert(0, str(engine_dir))
from brain import think
# from brain import think, auto_learn
from memory import get_context, add_to_history
import json
from pathlib import Path
from datetime import datetime, timedelta

# 对话历史文件
history_file = Path(__file__).parent / "memory" / "msg_history.json"

def load_msg_history():
    """加载历史并自动清理7天前的"""
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
            # 清理7天前的
            now = datetime.now()
            cutoff = now - timedelta(days=7)
            cleaned = []
            for h in history:
                try:
                    t = datetime.fromisoformat(h.get('time', '2020-01-01'))
                    if t > cutoff:
                        cleaned.append(h)
                except:
                    cleaned.append(h)
            # 保存清理后的
            if len(cleaned) != len(history):
                history_file.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
            return cleaned
        except:
            return []
    return []

def save_msg_history(history):
    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    # 同时保存到8888的L1
    try:
        if len(history) >= 2:
            last_user = history[-2].get('content', '') if history[-2].get('role') == 'user' else ''
            last_nova = history[-1].get('content', '') if history[-1].get('role') == 'nova' else ''
            if last_user:
                requests.post('http://127.0.0.1:8888/save', json={'user_input': last_user[:500], 'ai_response': last_nova[:500]}, timeout=3)
    except:
        pass  # 8888可能没开

msg_history = []

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
async def home():
    html = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Nova</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;user-select:text}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:#1a1a2a}
::-webkit-scrollbar-thumb{background:#3a3a5a;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#4a4a6a}
/* 亮色主题 */
body.light{background:#f5f5f5;color:#1a1a1a}
body.light .sidebar{background:#fff;box-shadow:2px 0 10px rgba(0,0,0,0.1)}
body.light .menu{color:#333}
body.light .menu:hover{background:#eee}
body.light .menu.active{background:#e0e7ff;color:#4f46e5}
body.light .chat{background:#fff}
body.light .bubble{background:#e5e7eb;color:#1a1a1a}
body.light .msg.user .bubble{background:#4f46e5;color:#fff}
body.light .input{background:#fff;border-top:1px solid #e5e7eb}
body.light .input textarea{background:#f9fafb;color:#1a1a1a;border:1px solid #d1d5db}
body.light::-webkit-scrollbar-track{background:#f1f1f1}
body.light::-webkit-scrollbar-thumb{background:#ccc}
body.light .input textarea::placeholder{color:#9ca3af}
/* 滚动条样式 */
body.light textarea{scrollbar-width:thin;scrollbar-color:#d1d5db #f3f4f6}
body.light textarea::-webkit-scrollbar{width:6px;height:6px}
body.light textarea::-webkit-scrollbar-track{background:#f3f4f6;border-radius:3px}
body.light textarea::-webkit-scrollbar-thumb{background:#d1d5db;border-radius:3px}
body.light textarea::-webkit-scrollbar-thumb:hover{background:#9ca3af}
body{font-family:ui-rounded,system-ui,-apple-system,"SF Pro Rounded","Segoe UI",sans-serif;line-height:1.4;background:#0a0a0f;color:#fff;height:100vh;overflow:hidden}
.thinking{display:inline-flex;gap:4px;margin-left:8px;vertical-align:middle}
.thinking span{width:4px;height:4px;background:#888;border-radius:50%;animation:dot 1.4s infinite}
.thinking span:nth-child(2){animation-delay:0.2s}
.thinking span:nth-child(3){animation-delay:0.4s}
@keyframes dot{0%,80%,100%{opacity:0.3;transform:scale(0.8)}40%{opacity:1;transform:scale(1)}}
.app{display:flex;flex-direction:column;height:100%}
.app-content{display:flex;flex:1;overflow:hidden}
.sidebar{width:200px;background:#12121a;padding:20px}
.menu{padding:12px;margin:8px 0;border-radius:10px;cursor:pointer;user-select:none}
.menu:hover{background:#2a2a3a}
.menu.active{background:#3a3a5a}
.main{flex:1;display:flex;flex-direction:column}
.chat{flex:1;overflow:auto;padding:20px;padding-bottom:100px}
.msg{margin:6px 0}
.msg .meta{font-size:12px;color:#888;margin-bottom:4px}
.bubble{display:inline-block;padding:12px 18px;border-radius:14px;background:#222;max-width:80%;line-height:1.4}
.msg.user{text-align:right}
.msg.user .bubble{background:#2a3a5a}
.input{padding:20px;border-top:1px solid #222;background:#0f0f1a;position:fixed;bottom:0;left:0;right:0;z-index:100}
.input .input-box{flex:1;display:flex;align-items:center;background:#1a1a2a;border:1px solid #333;border-radius:24px;padding:8px 12px;gap:10px;max-width:800px;margin:0 auto;width:100%}
body.light .input{background:#f9fafb;border-top:1px solid #e5e7eb}
body.light .input .input-box{background:#fff;border:1px solid #d1d5db}
.input textarea{flex:1;padding:6px 0;border:none;background:transparent;color:#fff;font-size:15px;resize:none;height:20px;min-height:20px;max-height:100px;outline:none;line-height:1.4;overflow:hidden}
body.light .input textarea{color:#1a1a1a}
.input textarea:focus{outline:none}
.input button{padding:0;width:36px;height:36px;border:none;background:#10a37f;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;transition:all 0.2s;margin-bottom:2px}
.input button:hover{background:#1a8a6e}
.input button:disabled{background:#555;cursor:not-allowed}
.input button.stop{background:#ef4444}
.header{display:flex;justify-content:space-between;align-items:center;padding:15px 20px;border-bottom:1px solid #222}
.page-title{font-weight:600;color:#e2e8f0;margin-bottom:15px;font-size:18px}
body.light .page-title{color:#1a1a1a}
.header-left{display:flex;align-items:center;gap:10px}
.header-title{font-size:16px;font-weight:600;color:#fff}
.status-dot{width:8px;height:8px;border-radius:50%;background:#22c55e}
.header-right{display:flex;align-items:center;gap:12px}
.theme-toggle{background:transparent;border:1px solid #333;padding:6px 12px;border-radius:8px;cursor:pointer;color:#fff;font-size:14px;transition:all 0.2s}
.theme-toggle:hover{background:#222;border-color:#444}
body.light .header{background:#fff;border-bottom:1px solid #e5e7eb}
body.light .header-title{color:#1a1a1a}
body.light .theme-toggle{background:#f3f4f6;border-color:#d1d5db;color:#1a1a1a}
body.light .theme-toggle:hover{background:#e5e7eb}
</style>
</head>
<body>
<div class="app">
<div class="header">
<div class="header-left"><span class="status-dot"></span><span class="header-title">✨ NovaCore</span></div>
<div class="header-right"><button class="theme-toggle" id="headerThemeBtn" onclick="toggleTheme()">🌙</button></div>
</div>
<div class="app-content">
<div class="sidebar">
<div class="menu active" id="m1">💬 聊天</div>
<div class="menu" id="m2">⚡ 技能</div>
<div class="menu" id="m3">📊 消耗</div>
<div class="menu" id="m4">🧠 记忆</div>
</div>
<div class="main">
<div class="chat" id="chat"></div>
<div class="input">
<div class="input-box">
<textarea id="inp" placeholder="给Nova发消息..." onkeyup="var h=Math.max(20,Math.min(this.scrollHeight,150));this.style.height=h+'px'" onkeypress="if(event.key==='Enter' && !event.shiftKey){event.preventDefault();send();}"></textarea>
<button id="sendBtn" onclick="send()">
<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
</button>
</div>
</div>
</div>
</div>
</div>
<script>
function toggleCat(el){
  var next = el.nextElementSibling;
  var arrow = el.querySelector('span:last-child');
  if(next.style.display === 'none'){next.style.display='block';arrow.innerHTML='-';}else{next.style.display='none';arrow.innerHTML='+';}
}
function filterMem(el,type){document.querySelectorAll('.mem-nav').forEach(function(n){n.classList.remove('active');n.style.background=document.body.classList.contains('light')?'#fff':'#252535';n.style.color=document.body.classList.contains('light')?'#6b7280':'#888';});el.classList.add('active');el.style.background=document.body.classList.contains('light')?'#e5e7eb':'#333';el.style.color=document.body.classList.contains('light')?'#1a1a1a':'#fff';}
function filterMemBySearch(q){q=q.toLowerCase();document.querySelectorAll('.mem-item').forEach(function(item){var txt=item.innerText.toLowerCase();item.style.display=txt.includes(q)?'block':'none';});}
var chat=document.getElementById('chat');
var chatHistory='<div class="msg"><div class="meta">✨ NovaCore</div><div class="bubble">你好！我是NovaCore～ ✨</div></div>';
fetch('/nova_name').then(r=>r.json()).then(function(d){
 var name=d.name||'NovaCore';
 chatHistory='<div class="msg"><div class="meta">✨ '+name+'</div><div class="bubble">你好！我是'+name+'～ ✨</div></div>';
 if(chat.innerHTML.indexOf('NovaCore')>-1){chat.innerHTML=chatHistory;}
 window.novaName=name;
});
document.getElementById('m1').onclick=function(){show(1)};
document.getElementById('m2').onclick=function(){show(2)};
document.getElementById('m3').onclick=function(){show(3)};
document.getElementById('m4').onclick=function(){show(4)};
document.getElementById('themeBtn').onclick=toggleTheme;
function toggleTheme(){
 var isLight = document.body.classList.contains('light');
 setTheme(isLight);
 localStorage.setItem('novaTheme', isLight?'dark':'light');
 // 更新header按钮文字
 var btn = document.getElementById('headerThemeBtn');
 if(btn) btn.innerHTML = isLight ? '🌙' : '☀️';
}
// 读取主题
var savedTheme = localStorage.getItem('novaTheme');
if(savedTheme === 'light'){
 document.body.classList.add('light');
 document.body.classList.remove('dark');
 document.getElementById('headerThemeBtn').innerHTML = '☀️';
}
function setTheme(isLight){
 if(isLight){
  document.body.classList.remove('light');
  document.body.classList.add('dark');
 }else{
  document.body.classList.add('light');
  document.body.classList.remove('dark');
 }
 var skillsList = document.getElementById('skillsList');
 if(skillsList){ fetch('/skills').then(r=>r.json()).then(function(d){
   var isLight = document.body.classList.contains('light');
   var textColor = isLight ? '#1a1a1a' : '#e2e8f0';
   var bgColor = isLight ? '#f3f4f6' : 'rgba(42,58,90,0.5)';
   var cardBg = isLight ? '#fff' : 'rgba(30,30,40,0.8)';
   var subColor = isLight ? '#666' : '#888';
   var html='<div style="display:flex;flex-direction:column;gap:8px;">';
   if(d.skills){d.skills.forEach(function(s){
     var statusBg=s.status==='ready'?'#22c55e':'#ef4444';
     var status='<span style="color:#fff;background:'+statusBg+';padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500;">'+(s.status==='ready'?'在线':'离线')+'</span>';
     html+='<div style="background:'+cardBg+';padding:12px;border-radius:8px;margin-top:8px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;"><span style="font-weight:500;color:'+textColor+';">'+(s.name||'-')+'</span>'+status+'</div><div style="font-size:12px;color:'+subColor+';">'+(s.description||'-')+'</div></div>';
   });}
   html+='</div>';document.getElementById('skillsList').innerHTML=html;});}
 var statsBox = document.getElementById('statsBox');
 if(statsBox){ fetch('/stats').then(r=>r.json()).then(function(d){
   var isLight = document.body.classList.contains('light');
   var titleColor = isLight ? '#1a1a1a' : '#e2e8f0';
   var numColor = isLight ? '#1a1a1a' : '#fff';
   var labelColor = isLight ? '#666' : '#888';
   var html='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px;">';
   html+='<div style="background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">输入</div><div style="font-size:20px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.input_tokens.toLocaleString():'-')+'</div></div>';
   html+='<div style="background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">输出</div><div style="font-size:20px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.output_tokens.toLocaleString():'-')+'</div></div>';
   html+='<div style="background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">缓存命中</div><div style="font-size:20px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.cache_hit+'%':'-')+'</div></div></div>';
   html+='<div style="display:flex;gap:12px;margin-bottom:20px;">';
   html+='<div style="flex:1;background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">当前模型</div><div style="font-size:18px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.model:'-')+'</div></div>';
   html+='<div style="flex:1;background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">API请求</div><div style="font-size:14px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.total_requests:'-')+'</div></div></div>';
   html+='<div style="display:flex;gap:12px;">';
   html+='<div style="flex:1;background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">总Token</div><div style="font-size:20px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.total_tokens.toLocaleString():'-')+'</div></div>';
   html+='<div style="flex:1;background:'+(isLight?'#f3f4f6':'rgba(30,30,40,0.8)')+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">最后使用</div><div style="font-size:14px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.last_used:'-')+'</div></div>';
   document.getElementById('statsBox').innerHTML=html;});}
 var memoryTimeline = document.getElementById('memoryTimeline');
 if(memoryTimeline){ location.reload(); }
}
function T(){var d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}
function show(n){
 for(var i=1;i<=4;i++)document.getElementById('m'+i).classList.remove('active');
 document.getElementById('m'+n).classList.add('active');
 if(n==1){chat.innerHTML=chatHistory;chat.scrollTop=chat.scrollHeight;}
 if(n==2){
  chat.innerHTML='<div style="padding:20px;"><h2 class="page-title">⚡ 技能矩阵</h2><div id="skillsList" style="margin-top:15px;">加载中...</div></div>';
  fetch('/skills').then(r=>r.json()).then(function(d){
   var isLight=document.body.classList.contains('light');
   var titleColor=isLight?'#1a1a1a':'#e2e8f0';
   chat.querySelector('h2').style.color=titleColor;
   var cardBg=isLight?'#f9fafb':'rgba(30,30,40,0.8)';
   var textColor=isLight?'#1a1a1a':'#e2e8f0';
   var subColor=isLight?'#6b7280':'#94a3b8';
   var headerBg=isLight?'#f3f4f6':'#1e293b';
   // 四大技能分类
   var categories = {
     '信息查询': [],
     '内容创作': [],
     '生活娱乐': [],
     '个人助手': []
   };
   if(d.skills){
    d.skills.forEach(function(s){
     var name = s.name || '';
     var cat = '个人助手';
     if(name.includes('天气') || name.includes('气温') || name.includes('温度') || name.includes('股票') || name.includes('股价') || name.includes('大盘') || name.includes('查询')) cat = '信息查询';
     else if(name.includes('画图') || name.includes('海报') || name.includes('图片') || name.includes('生成图片') || name.includes('AI画')) cat = '内容创作';
     else if(name.includes('故事') || name.includes('讲故事') || name.includes('创作') || name.includes('写作') || name.includes('文案')) cat = '内容创作';
     else if(name.includes('视频') || name.includes('短视频')) cat = '生活娱乐';
     if(!categories[cat]) categories[cat] = [];
     categories[cat].push(s);
    });
   }
   var html='<div style="display:flex;flex-direction:column;gap:6px;">';
   Object.keys(categories).forEach(function(catName){
     var skills = categories[catName];
     if(skills && skills.length > 0){
       html+='<div style="background:'+cardBg+';border-radius:10px;overflow:hidden;margin-bottom:4px;">';
       html+='<div class="catHeader" onclick="toggleCat(this)" style="padding:12px 14px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;background:'+headerBg+';">';
       html+='<span style="font-weight:600;color:'+textColor+';">'+catName+' ('+skills.length+' 个)</span>';
       html+='<span style="color:'+subColor+';font-weight:bold;">+</span></div>';
       html+='<div class="catSkills" style="display:none;padding:8px 12px;">';
       skills.forEach(function(s){
         var statusBg=s.status==='ready'?'#22c55e':'#ef4444';
         var status='<span style="color:#fff;background:'+statusBg+';padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500;margin-left:8px;">'+(s.status==='ready'?'在线':'离线')+'</span>';
         html+='<div style="padding:8px 0;border-bottom:1px solid '+(isLight?'#e5e7eb':'#334155')+';"><span style="font-weight:500;color:'+textColor+';">'+s.name+'</span>'+status+'<div style="font-size:12px;color:'+subColor+';margin-top:4px;">'+(s.description||'暂无描述')+'</div></div>';
       });
       html+='</div></div>';
     }
   });
   html+='</div>';
   document.getElementById('skillsList').innerHTML=html;
  });
 }
 if(n==3){
  chat.innerHTML='<div style="padding:20px;"><h2 class="page-title">📊 消耗统计</h2><div id="statsBox" style="margin-top:15px;">加载中...</div></div>';
  fetch('/stats').then(r=>r.json()).then(function(d){
   var isLight=document.body.classList.contains('light');
   var titleColor=isLight?'#1a1a1a':'#e2e8f0';
   var numColor=isLight?'#1a1a1a':'#fff';
   var labelColor=isLight?'#6b7280':'#94a3b8';
   chat.querySelector('h2').style.color=titleColor;
   var cardBg=isLight?'#f9fafb':'rgba(30,30,40,0.8)';
   var html='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;">';
   html+='<div style="background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">输入</div><div style="font-size:22px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.input_tokens.toLocaleString():'-')+'</div></div>';
   html+='<div style="background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">输出</div><div style="font-size:22px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.output_tokens.toLocaleString():'-')+'</div></div>';
   html+='<div style="background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">缓存命中</div><div style="font-size:22px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.cache_hit+'%':'-')+'</div></div></div>';
   html+='<div style="display:flex;gap:12px;margin-bottom:16px;">';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">当前模型</div><div style="font-size:16px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.model:'-')+'</div></div>';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">API请求</div><div style="font-size:16px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.total_requests:'-')+'</div></div></div>';
   html+='<div style="display:flex;gap:12px;">';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">总Token</div><div style="font-size:20px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.total_tokens.toLocaleString():'-')+'</div></div>';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;">';
   html+='<div style="font-size:12px;color:'+labelColor+';">最后使用</div><div style="font-size:14px;font-weight:600;color:'+numColor+';">'+(d.stats?d.stats.last_used:'-')+'</div></div>';
   document.getElementById('statsBox').innerHTML=html;
  });
 }
 if(n==4){chat.innerHTML='<div style="display:flex;height:100%;"><div style="width:160px;background:'+(isLight?'#f3f4f6':'#1a1a2a')+';padding:20px 10px;border-right:1px solid '+(isLight?'#e5e7eb':'#333')+';"><div style="font-size:12px;color:'+(isLight?'#6b7280':'#888')+';margin-bottom:12px;padding-left:8px;">我的</div><div class="mem-nav active" onclick="filterMem(this,\'all\')" style="padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:4px;background:'+(isLight?'#fff':'#252535')+';color:'+(isLight?'#1a1a1a':'#fff')+';">对话</div><div class="mem-nav" onclick="filterMem(this,\'timeline\')" style="padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:4px;color:'+(isLight?'#6b7280':'#888')+';">NovaCore Timeline</div><div class="mem-nav" onclick="filterMem(this,\'all\')" style="padding:10px 12px;border-radius:8px;cursor:pointer;color:'+(isLight?'#6b7280':'#888')+';">全部</div></div><div style="flex:1;padding:20px;overflow:auto;"><div style="margin-bottom:20px;"><input type="text" placeholder="搜索记忆..." style="width:100%;padding:10px 16px;border-radius:10px;border:1px solid '+(isLight?'#d1d5db':'#333')+';background:'+(isLight?'#fff':'#1a1a2a')+';color:'+(isLight?'#1a1a1a':'#fff')+';outline:none;" onkeyup="filterMemBySearch(this.value)"></div><div id="memoryTimeline" style="display:flex;flex-direction:column;gap:8px;">加载中...</div></div></div>';inputArea.style.display='none';fetch('/memory').then(r=>r.json()).then(function(d){var isLight=document.body.classList.contains('light');var cardBg=isLight?'#fff':'rgba(34,34,34,0.5)';var textColor=isLight?'#1a1a1a':'#e2e8f0';var labelColor=isLight?'#6b7280':'#94a3b8';var events=d.events||[];var grouped={};events.forEach(function(e){var date=e.time?e.time.split('T')[0]:'未知';if(!grouped[date])grouped[date]=[];grouped[date].push(e);});var dates=Object.keys(grouped).sort().reverse();var html='';dates.forEach(function(date){var label='未知';var today=new Date().toISOString().split('T')[0];var yesterday=new Date(Date.now()-86400000).toISOString().split('T')[0];if(date===today)label='今天';else if(date===yesterday)label='昨天';else label=date;html+='<div style="font-size:12px;color:'+labelColor+';margin:16px 0 8px 0;font-weight:600;">'+label+'</div>';grouped[date].forEach(function(e){var tagBg='#475569';var tagColor='#e2e8f0';if(e.layer==='L5'){tagBg='#3d2f0a';tagColor='#fcd34d';}else if(e.layer==='L6'){tagBg='#14532d';tagColor='#86efac';}else if(e.layer==='L8'){tagBg='#1f4a3d';tagColor='#6ee7b7';}var time=e.time?e.time.replace('T',' ').substring(11,16):'';html+='<div class="mem-item" style="padding:12px 14px;background:'+cardBg+';border-radius:12px;margin-bottom:8px;"><div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><span style="font-size:10px;padding:2px 8px;background:'+tagBg+';color:'+tagColor+';border-radius:6px;font-weight:600;">'+e.layer+'</span><span style="font-size:11px;color:'+labelColor+';">'+time+'</span></div><div style="font-size:13px;color:'+textColor+';line-height:1.4;">'+(e.content||'')+'</div></div>';});});document.getElementById('memoryTimeline').innerHTML=html;});}
 if(n==6){
  chat.innerHTML='<div style="padding:20px;"><h2 style="font-weight:600;color:#e2e8f0;margin-bottom:15px;font-size:18px;">📜 对话历史</h2><div id="historyList" style="margin-top:15px;">加载中...</div></div>';
  fetch('/history').then(r=>r.json()).then(function(d){
   var isLight=document.body.classList.contains('light');
   var titleColor=isLight?'#1a1a1a':'#e2e8f0';
   chat.querySelector('h2').style.color=titleColor;
   var cardBg=isLight?'#f9fafb':'rgba(30,30,40,0.8)';
   var textColor=isLight?'#1a1a1a':'#e2e8f0';
   var subColor=isLight?'#6b7280':'#94a3b8';
   var userBubble=isLight?'#4f46e5':'#3b5bdb';
   var novaBubble=isLight?'#e5e7eb':'#2a3a5a';
   var novaText=isLight?'#1a1a1a':'#e2e8f0';
   var html='<div style="display:flex;flex-direction:column;gap:12px;">';
   d.history.slice(0,20).forEach(function(h){
     var time=h.time||'';
     var content=h.content||'';
     var role=h.role||'';
     if(role==='user'){
       html+='<div style="text-align:right;"><div style="display:inline-block;max-width:80%;background:'+userBubble+';color:#fff;padding:10px 14px;border-radius:14px 14px 4px 14px;text-align:left;font-size:14px;">'+content.replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</div><div style="font-size:11px;color:'+subColor+';margin-top:4px;">'+time+'</div></div>';
     }else{
       html+='<div style="text-align:left;"><div style="display:inline-block;max-width:80%;background:'+novaBubble+';color:'+novaText+';padding:10px 14px;border-radius:14px 14px 14px 4px;text-align:left;font-size:14px;">'+content.replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</div><div style="font-size:11px;color:'+subColor+';margin-top:4px;">'+time+'</div></div>';
     }
   });
   html+='</div>';
   document.getElementById('historyList').innerHTML=html;
  });
 }
 if(n==5){location.reload();}
}
let abortCtrl=null;
let isThinking=false;
async function send(){
 var inp=document.getElementById('inp');
 var btn=document.getElementById('sendBtn');
 var msg=inp.value;
 if(isThinking){
  if(abortCtrl){abortCtrl.abort();abortCtrl=null;isThinking=false;btn.innerHTML='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';btn.classList.remove('stop');inp.placeholder='给Nova发消息...';}
  return;
 }
 if(!msg.trim())return;
 isThinking=true;
 btn.innerHTML='<svg width="18" height="18" viewBox="0 0 24 24" fill="white"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>';
 btn.classList.add('stop');
 inp.placeholder='·';
 var id='msg_'+Date.now();
 var thinkingHTML='<div class="msg user"><div class="meta">😊 我 '+T()+'</div><div class="bubble">'+msg.replace(String.fromCharCode(10),"<br>")+'</div></div><div class="msg" id="r_'+id+'"><div class="meta">✨ Nova</div><div class="bubble">思考中<span class="thinking"><span></span><span></span><span></span></span></div></div>';
 chat.innerHTML+=thinkingHTML;
 chatHistory+=thinkingHTML;
 inp.value='';
 inp.scrollTop=0;
 chat.scrollTop=chat.scrollHeight;
 try{
  abortCtrl=new AbortController();
  var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},signal:abortCtrl.signal,body:JSON.stringify({message:msg})});
  var d=await r.json();
  console.log('返回:',d);
  document.getElementById('r_'+id).innerHTML='<div class="meta">✨ Nova '+T()+'</div><div class="bubble">'+(d.reply||'...').replace(/\\n/g,'<br>')+'</div>';
  chatHistory=chatHistory.replace('id="r_'+id+'"><div class="meta">✨ Nova</div><div class="bubble">思考中<span class="thinking"><span></span><span></span><span></span></span></div></div>','id="r_'+id+'"><div class="meta">✨ Nova '+T()+'</div><div class="bubble">'+(d.reply||'...').replace(/\\n/g,'<br>')+'</div>');
 }catch(e){
  if(e.name==='AbortError'){
   document.getElementById('r_'+id).innerHTML='<div class="meta">✨ Nova '+T()+'</div><div class="bubble">已停止～</div>';
  }else{
   document.getElementById('r_'+id).innerHTML='<div class="meta">✨ Nova '+T()+'</div><div class="bubble">出错: '+e+'</div>';
  }
 }
 abortCtrl=null;
 isThinking=false;
 btn.innerHTML='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>';
 btn.classList.remove('stop');
 inp.placeholder='给Nova发消息...';
 inp.focus();
}
</script></body></html>'''
    return html

@app.post("/chat")
async def chat(request: ChatRequest):
    msg = request.message
    add_to_history("user", msg)
    response = "你好！我是NovaCore～"
    
    # ===== L7: 经验沉淀 - 负面反馈检测（要在加历史之前！）=====
    # 每次请求时加载历史
    msg_history = load_msg_history()
    
    negative_keywords = ['不对', '不是', '错了', '不好用', '不喜欢', '重来', '假', '骗人']
    is_negative = any(w in msg for w in negative_keywords)
    
    # 找上一轮问题（排除当前这条）
    last_q = ""
    for h in reversed(msg_history):
        if h.get('role') == 'user' and h.get('content') != msg:
            last_q = h.get('content', '')
            break
    
    
    
    if is_negative and last_q:
        # 用户反馈不好 → 触发L8学习
        try:
            from core.l8_learn import auto_learn
            learn_result = auto_learn(last_q)
            if learn_result.get('success'):
                response = f"""人家记住啦！刚才说的不对，我现在重新学了一下：

{learn_result.get('answer', learn_result.get('message', ''))[:200]}

这次对了吗？对不起嘛，下次不会了～ 💕"""
                msg_history.append({"role": "user", "content": msg, "time": datetime.now().isoformat()})
                save_msg_history(msg_history)
                add_to_history("nova", response)
                msg_history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
                save_msg_history(msg_history)
                return {"reply": response}
        except Exception as e:
            print(f"L7触发L8失败: {e}")
    
    # 加用户消息到历史（不管是否触发L7）
    msg_history.append({"role": "user", "content": msg, "time": datetime.now().isoformat()})
    save_msg_history(msg_history)
    
    if NOVA_CORE_READY:
        try:
            from core.router import route as nova_route
            from core.executor import execute as nova_execute
            from core.skills import get_all_skills
            from brain import think

            route_result = nova_route(msg)

            if route_result.get('mode') == 'skill':
                skill_name = route_result.get('skill')
                execute_result = nova_execute(route_result, msg)

                from memory import evolve
                evolve(msg, skill_name)

                if execute_result.get('success'):
                    skill_response = execute_result.get('response', '')
                    result2 = think(f"用户问：{msg}\n\n技能结果：{skill_response}\n\n请用Nova甜美风格回复用户，一句话就好", "")
                    if isinstance(result2, dict):
                        response = result2.get("reply", "")
                    else:
                        response = result2
                else:
                    response = execute_result.get('error', '技能执行失败')
            else:
                skills_data = get_all_skills()
                skill_list = ", ".join([f"{v.get('name',k)}(关键词:{','.join(v.get('keywords',[]))})" for k,v in skills_data.items()])

                result2 = think(f"""用户问：{msg}

可用技能：{skill_list}

请直接自然回复用户。如果问题适合普通聊天，就不要假装调用技能。""", "")

                if isinstance(result2, dict):
                    response = result2.get("reply", "")
                else:
                    response = result2
        except Exception as e:
            print(e)
            response = "抱歉，出错了"
    
    add_to_history("nova", response)
    msg_history.append({"role": "nova", "content": response, "time": datetime.now().isoformat()})
    save_msg_history(msg_history)
    
    # 更新统计
    try:
        requests.post('http://localhost:8090/stats', json={'tokens': len(msg) + len(response)}, timeout=1)
    except:
        pass
    
    return {"reply": response}

@app.get("/stats")
async def get_stats():
    import os
    
    # 简单统计
    stats_file = os.path.join(os.path.dirname(__file__), 'memory', 'stats.json')
    stats = {"total_tokens": 0, "total_requests": 0, "model": "MiniMax-M2.5", "last_used": ""}
    
    if os.path.exists(stats_file):
        import json
        try:
            stats = json.load(open(stats_file, 'r', encoding='utf-8'))
        except:
            pass
    
    return stats

@app.post("/stats")
async def update_stats(request: dict):
    import os, json
    
    stats_file = os.path.join(os.path.dirname(__file__), 'memory', 'stats.json')
    stats = {"total_tokens": 0, "total_requests": 0, "model": "MiniMax-M2.5", "last_used": ""}
    
    if os.path.exists(stats_file):
        try:
            stats = json.load(open(stats_file, 'r', encoding='utf-8'))
        except:
            pass
    
    # 更新
    if 'tokens' in request:
        stats['total_tokens'] = stats.get('total_tokens', 0) + request['tokens']
    stats['total_requests'] = stats.get('total_requests', 0) + 1
    stats['last_used'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    os.makedirs(os.path.dirname(stats_file), exist_ok=True)
    json.dump(stats, open(stats_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    
    return {"ok": True}

@app.get("/nova_name")
async def get_nova_name():
    import os, json
    config_path = os.path.join(os.path.dirname(__file__), 'brain', 'persona.json')
    if os.path.exists(config_path):
        try:
            persona = json.load(open(config_path, 'r', encoding='utf-8'))
            return {"name": persona.get('nova_name', 'NovaCore')}
        except:
            pass
    return {"name": "NovaCore"}

@app.get("/skills")
async def get_skills():
    if NOVA_CORE_READY:
        try:
            from core.skills import get_all_skills
            skills_data = get_all_skills()
            skills = []
            for name, info in skills_data.items():
                skills.append({
                    "name": info.get("name", name),
                    "keywords": info.get("keywords", []),
                    "description": info.get("description", ""),
                    "priority": info.get("priority", 10),
                    "status": info.get("status", "ready")
                })
            skills.sort(key=lambda x: x.get("priority", 10))
            return {"skills": skills}
        except Exception as e:
            return {"skills": [], "error": str(e)}
    return {"skills": []}

@app.get("/memory")
async def get_memory():
    """获取记忆时间线"""
    db_path = Path(__file__).parent / "memory_db"
    events = []
    
    # L5技能
    l5_file = db_path / "knowledge.json"
    if l5_file.exists():
        try:
            l5_skills = json.loads(l5_file.read_text(encoding="utf-8"))
            for s in l5_skills[:5]:
                events.append({
                    'time': s.get('learned_at', '2026-03-10')[:16],
                    'layer': 'L5',
                    'event_type': 'skill',
                    'title': '技能矩阵',
                    'content': f'解锁新技能：<strong>{s.get("name", "skill")}</strong>技能'
                })
        except:
            pass
    
    # L6执行
    l6_file = db_path / "evolution.json"
    if l6_file.exists():
        try:
            l6_data = json.loads(l6_file.read_text(encoding="utf-8"))
            skills_used = l6_data.get('skills_used', {})
            for skill_name, data in skills_used.items():
                events.append({
                    'time': data.get('last_used', '2026-03-10')[:16],
                    'layer': 'L6',
                    'event_type': 'evolution',
                    'title': '技能执行',
                    'content': f'执行了<strong>{skill_name}</strong>技能（累计使用 {data.get("count", 0)} 次）'
                })
        except:
            pass
    
    # L8知识
    l8_file = db_path / "knowledge_base.json"
    if l8_file.exists():
        try:
            l8_data = json.loads(l8_file.read_text(encoding="utf-8"))
            for kw in l8_data[:10]:
                scene = kw.get('二级场景', '')
                if '自动学习' in scene:
                    events.append({
                        'time': kw.get('最近使用时间', '2026-03-10')[:16],
                        'layer': 'L8',
                        'event_type': 'knowledge',
                        'title': '能力进化',
                        'content': f'习得经验<strong>{scene.replace("自动学习-", "")}</strong>（将转化为技能/执行依据）'
                    })
        except:
            pass
    
    events.sort(key=lambda x: x.get('time', ''), reverse=True)
    return {"events": events[:50], "stats": {"conversation_count": 0}}

@app.get("/history")
async def get_history():
    """获取对话历史"""
    history_file = Path(__file__).parent / "memory" / "msg_history.json"
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
            # 格式化时间
            for h in history:
                if 'time' in h:
                    try:
                        t = datetime.fromisoformat(h['time'])
                        h['time'] = t.strftime("%m-%d %H:%M")
                    except:
                        pass
            return {"history": history[-40:]}  # 最近40条
        except:
            pass
    return {"history": []}

if __name__ == "__main__":
    import uvicorn
    print("NovaCore: http://localhost:8090")
    uvicorn.run(app, host="0.0.0.0", port=8090)
