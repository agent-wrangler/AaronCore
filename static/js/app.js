function toggleTheme(){
 var body=document.body;
 var currentMenu=document.querySelector('.menu.active');
 var currentId=currentMenu?currentMenu.id:'';
 if(body.classList.contains('dark')){
  body.classList.remove('dark');
  body.classList.add('light');
  localStorage.setItem('nova_theme','light');
 }else{
  body.classList.remove('light');
  body.classList.add('dark');
  localStorage.setItem('nova_theme','dark');
 }
 var menuMap={m1:1,m2:2,m3:3,m4:4,m5:5,m6:6};
 if(currentId && menuMap[currentId]){
  show(menuMap[currentId]);
 }
}

/* ===== 侧边栏拉伸功能 ===== */
function initSidebarResize(){
 var sidebar=document.querySelector('.sidebar');
 var isResizing=false;
 var startX,startWidth;
 
 function startResize(e){
  isResizing=true;
  startX=e.clientX||e.touches[0].clientX;
  startWidth=parseInt(getComputedStyle(sidebar).width,10);
  document.addEventListener('mousemove',resize);
  document.addEventListener('mouseup',stopResize);
  document.addEventListener('touchmove',resize);
  document.addEventListener('touchend',stopResize);
  sidebar.style.transition='none';
  document.body.style.userSelect='none';
 }
 
 function resize(e){
  if(!isResizing)return;
  var clientX=e.clientX||(e.touches&&e.touches[0].clientX);
  if(!clientX)return;
  
  var diff=clientX-startX;
  var newWidth=Math.max(200,Math.min(400,startWidth+diff));
  sidebar.style.width=newWidth+'px';
 }
 
 function stopResize(){
  if(!isResizing)return;
  isResizing=false;
  sidebar.style.transition='width 0.2s';
  document.body.style.userSelect='';
  document.removeEventListener('mousemove',resize);
  document.removeEventListener('mouseup',stopResize);
  document.removeEventListener('touchmove',resize);
  document.removeEventListener('touchend',stopResize);
  
  // 保存宽度到本地存储
  localStorage.setItem('nova_sidebar_width',sidebar.style.width);
 }
 
 // 添加事件监听
 sidebar.addEventListener('mousedown',function(e){
  if(e.offsetX>sidebar.offsetWidth-8){
   startResize(e);
  }
 });
 
 sidebar.addEventListener('touchstart',function(e){
  var touchX=e.touches[0].clientX;
  var rect=sidebar.getBoundingClientRect();
  if(touchX>rect.right-20){
   startResize(e);
  }
 });
 
 // 加载保存的宽度
 var savedWidth=localStorage.getItem('nova_sidebar_width');
 if(savedWidth){
  sidebar.style.width=savedWidth;
 }
}

// setInputVisible is in utils.js

window.onload=function(){
 // 初始化侧边栏拉伸
 initSidebarResize();
 
 // 加载保存的主题
 var savedTheme=localStorage.getItem('nova_theme');
 if(savedTheme==='light'){
  document.body.classList.remove('dark');
  document.body.classList.add('light');
 }
 
 // 加载聊天历史
 var saved=localStorage.getItem('nova_chat_history');
 if(saved){
  // 修复历史数据中残留的 opacity:0
  var tmp=document.createElement('div');
  tmp.innerHTML=saved;
  tmp.querySelectorAll('.bubble').forEach(function(b){
   if(b.style.opacity==='0') b.style.removeProperty('opacity');
   b.style.removeProperty('transition');
  });
  tmp.querySelectorAll('.thinking-bubble').forEach(function(b){
   b.style.removeProperty('opacity');
   b.style.removeProperty('transform');
   b.style.removeProperty('transition');
  });
  var cleaned=tmp.innerHTML;
  chatHistory=cleaned;
  document.getElementById('chat').innerHTML=cleaned;
  document.getElementById('chat').scrollTop=document.getElementById('chat').scrollHeight;
  // 回写修复后的数据
  if(cleaned!==saved) localStorage.setItem('nova_chat_history',cleaned);
  console.log('[Nova] 恢复聊天历史，消息数:', tmp.querySelectorAll('.msg').length);
 }
 
 // 初始化输入框监听
 var inp=document.getElementById('inp');
 inp.addEventListener('input',updateSendButton);
 updateSendButton();
 setInputVisible(true);
 AwarenessManager.init();

 // 读取模型名
 fetch('/stats').then(r=>r.json()).then(function(d){
  var stats=d.stats||d||{};
  var el=document.getElementById('modelName');
  if(el) el.textContent=stats.model||'未知';
 }).catch(function(){
  var el=document.getElementById('modelName');
  if(el) el.textContent='未知';
 });
 
 // 添加欢迎消息（如果无历史记录）
 if(!saved||saved.trim()===''){
  setTimeout(function(){
   addMessage('Nova','你好，我是 Nova。现在聊天、技能、消耗、记忆这些页面都已经接回来了。','assistant');
  },300);
 }
};

function show(n){
 for(var i=1;i<=6;i++){
  var menu=document.getElementById('m'+i);
  if(menu) menu.classList.remove('active');
 }
 document.getElementById('m'+n).classList.add('active');
 var chat = document.getElementById('chat');
 var isLight = document.body.classList.contains('light');

 if(n==1){
  setInputVisible(true);
  chat.innerHTML=chatHistory;
  chat.scrollTop=chat.scrollHeight;
 }

 if(n==2){
  setInputVisible(false);
  chat.innerHTML='<div style="padding:20px;"><h2 class="page-title" style="margin-bottom:15px;">⚡ 技能矩阵</h2><div id="skillsList">加载中...</div></div>';
  fetch('/skills').then(r=>r.json()).then(function(d){
   var cardBg=isLight?'#f9fafb':'rgba(30,30,40,0.8)';
   var textColor=isLight?'#1a1a1a':'#e2e8f0';
   var subColor=isLight?'#6b7280':'#94a3b8';
   var headerBg=isLight?'#f3f4f6':'#1e293b';
   var borderColor=isLight?'#e5e7eb':'#334155';
   var categories={ '信息查询':[], '内容创作':[], '生活娱乐':[], '个人助手':[] };
   if(d.skills){
    d.skills.forEach(function(s){
     var name=s.name||'';
     var cat='个人助手';
     if(name.includes('天气')||name.includes('气温')||name.includes('温度')||name.includes('股票')||name.includes('查询')) cat='信息查询';
     else if(name.includes('画')||name.includes('图片')||name.includes('海报')||name.includes('图')) cat='内容创作';
     else if(name.includes('故事')||name.includes('写作')||name.includes('文案')) cat='内容创作';
     else if(name.includes('视频')||name.includes('娱乐')) cat='生活娱乐';
     categories[cat].push(s);
    });
   }
   var html='<div style="display:flex;flex-direction:column;gap:6px;">';
   Object.keys(categories).forEach(function(catName){
    var skills=categories[catName];
    if(skills && skills.length>0){
     html+='<div style="background:'+cardBg+';border-radius:10px;overflow:hidden;margin-bottom:4px;">';
     html+='<div class="catHeader" onclick="toggleCat(this)" style="padding:12px 14px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;background:'+headerBg+';">';
     html+='<span style="font-weight:600;color:'+textColor+';">'+catName+' ('+skills.length+' 个)</span>';
     html+='<span style="color:'+subColor+';font-weight:bold;">+</span></div>';
     html+='<div class="catSkills" style="display:none;padding:8px 12px;">';
     skills.forEach(function(s){
      var statusBg=s.status==='ready'?'#22c55e':'#ef4444';
      var status='<span style="color:#fff;background:'+statusBg+';padding:2px 8px;border-radius:12px;font-size:11px;font-weight:500;margin-left:8px;">'+(s.status==='ready'?'在线':'离线')+'</span>';
      html+='<div style="padding:8px 0;border-bottom:1px solid '+borderColor+';"><span style="font-weight:500;color:'+textColor+';">'+(s.name||'未命名技能')+'</span>'+status+'<div style="font-size:12px;color:'+subColor+';margin-top:4px;">'+(s.description||'暂无描述')+'</div></div>';
     });
     html+='</div></div>';
    }
   });
   html+='</div>';
   document.getElementById('skillsList').innerHTML=html;
  }).catch(function(){
   document.getElementById('skillsList').innerHTML='<div style="color:#ef4444;">技能数据加载失败</div>';
  });
 }

 if(n==3){
  setInputVisible(false);
  chat.innerHTML='<div style="padding:20px;"><h2 class="page-title" style="margin-bottom:15px;">📊 数据看板</h2><div id="statsBox">加载中...</div></div>';
  fetch('/stats').then(r=>r.json()).then(function(d){
   var stats=d.stats||d||{};
   var cardBg=isLight?'#ffffff':'rgba(30,41,59,0.78)';
   var numColor=isLight?'#0f172a':'#f8fafc';
   var labelColor=isLight?'#64748b':'#94a3b8';
   var html='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;">';
   html+='<div style="background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">输入</div><div style="font-size:22px;font-weight:600;color:'+numColor+';">'+((stats.input_tokens||0).toLocaleString())+'</div></div>';
   html+='<div style="background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">输出</div><div style="font-size:22px;font-weight:600;color:'+numColor+';">'+((stats.output_tokens||0).toLocaleString())+'</div></div>';
   html+='<div style="background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">总请求</div><div style="font-size:22px;font-weight:600;color:'+numColor+';">'+((stats.total_requests||0).toLocaleString())+'</div></div></div>';
   html+='<div style="display:flex;gap:12px;margin-bottom:16px;">';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">当前模型</div><div style="font-size:16px;font-weight:600;color:'+numColor+';">'+(stats.model||'-')+'</div></div>';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">最后使用</div><div style="font-size:14px;font-weight:600;color:'+numColor+';">'+(stats.last_used||'-')+'</div></div></div>';
   html+='<div style="display:flex;gap:12px;">';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">总 Token</div><div style="font-size:20px;font-weight:600;color:'+numColor+';">'+((stats.total_tokens||0).toLocaleString())+'</div></div>';
   html+='<div style="flex:1;background:'+cardBg+';padding:16px;border-radius:12px;text-align:center;"><div style="font-size:12px;color:'+labelColor+';">缓存命中</div><div style="font-size:14px;font-weight:600;color:'+numColor+';">'+((stats.cache_hit||0)+'%')+'</div></div></div>';
   document.getElementById('statsBox').innerHTML=html;
  }).catch(function(){
   document.getElementById('statsBox').innerHTML='<div style="color:#ef4444;">统计数据加载失败</div>';
  });
 }

 if(n==4){
  setInputVisible(false);
  currentMemoryFilter='all';
  chat.innerHTML='<div style="padding:20px;overflow:auto;height:100%;"><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:18px;"><div><div style="font-size:26px;font-weight:700;color:'+(isLight?'#1a1a1a':'#e2e8f0')+';margin-bottom:6px;">记忆引擎</div><div style="font-size:13px;color:'+(isLight?'#6b7280':'#94a3b8')+';line-height:1.7;max-width:720px;">这里会沉淀 NovaCore 从 L1 到 L8 的变化轨迹。记忆粒子、记忆结晶、成长经验、相伴时间，都会在这里慢慢长出来。</div></div><div style="font-size:12px;color:'+(isLight?'#6b7280':'#94a3b8')+';padding-top:6px;">Memory Engine</div></div><div id="memoryOverview" style="display:grid;grid-template-columns:'+memoryOverviewColumns()+';gap:12px;margin-bottom:18px;"></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;" id="memoryChips"><button class="mem-chip" onclick="setMemoryFilter(\'all\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#1a1a1a':'#fff')+';cursor:pointer;">全部</button><button class="mem-chip" onclick="setMemoryFilter(\'L3\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#6b7280':'#94a3b8')+';cursor:pointer;">记忆结晶</button><button class="mem-chip" onclick="setMemoryFilter(\'L4\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#6b7280':'#94a3b8')+';cursor:pointer;">人格图谱</button><button class="mem-chip" onclick="setMemoryFilter(\'L5\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#6b7280':'#94a3b8')+';cursor:pointer;">技能矩阵</button><button class="mem-chip" onclick="setMemoryFilter(\'L6\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#6b7280':'#94a3b8')+';cursor:pointer;">技能执行</button><button class="mem-chip" onclick="setMemoryFilter(\'L7\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#6b7280':'#94a3b8')+';cursor:pointer;">反馈学习</button><button class="mem-chip" onclick="setMemoryFilter(\'L8\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid '+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';background:'+(isLight?'#fff':'rgba(255,255,255,0.04)')+';color:'+(isLight?'#6b7280':'#94a3b8')+';cursor:pointer;">成长经验</button></div><div style="margin-bottom:18px;"><input id="memorySearch" type="text" placeholder="搜索记忆事件..." style="width:100%;padding:12px 16px;border-radius:12px;border:1px solid '+(isLight?'#d1d5db':'#333')+';background:'+(isLight?'#fff':'#1a1a2a')+';color:'+(isLight?'#1a1a1a':'#fff')+';outline:none;" onkeyup="filterMemBySearch(this.value)"></div><div id="memoryTimeline" style="display:flex;flex-direction:column;gap:10px;">加载中...</div></div>';
  fetch('/memory').then(r=>r.json()).then(function(d){
   var cardBg=isLight?'#ffffff':'rgba(30,41,59,0.72)';
   var softBg=isLight?'#f8fafc':'rgba(255,255,255,0.03)';
   var textColor=isLight?'#0f172a':'#e2e8f0';
   var labelColor=isLight?'#64748b':'#94a3b8';
   var borderColor=isLight?'rgba(148,163,184,0.28)':'rgba(255,255,255,0.05)';
   var events=d.events||[];
   var counts=d.counts||{L1:0,L3:0,L4:0,L5:0,L6:0,L7:0,L8:0};
   if(!d.counts){
    events.forEach(function(e){ if(counts[e.layer]!==undefined) counts[e.layer]++; });
   }
   var days=Math.max(1, Math.floor((Date.now() - new Date('2026-02-26').getTime())/86400000)+1);
   var growth=memoryGrowthProfile(counts);
   var totalExp=growth.totalExp;
   var level=growth.level;
   var progress=growth.progressPercent;
   var stage='初醒';
   if(level>=2) stage='生长';
   if(level>=10) stage='共振';
   if(level>=30) stage='进化';
   if(level>=60) stage='自洽';
   if(level>=120) stage='拓展';
   if(level>=300) stage='繁星';
   if(level>=1000) stage='无界';
   var overview='';
   overview+='<div style="background:linear-gradient(135deg,'+(isLight?'#eef2ff,#f5f3ff':'rgba(102,126,234,0.18),rgba(118,75,162,0.22)')+');border:1px solid '+borderColor+';padding:18px;border-radius:18px;box-shadow:'+(isLight?'0 8px 24px rgba(79,70,229,0.08)':'0 10px 28px rgba(0,0,0,0.18)')+';display:flex;flex-direction:column;gap:12px;">';
   overview+='<div style="font-size:12px;color:'+labelColor+';">成长等级</div><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;"><div style="min-width:0;"><div style="display:inline-flex;align-items:baseline;gap:8px;white-space:nowrap;font-size:28px;font-weight:800;color:'+textColor+';margin-bottom:2px;">Lv.'+level+' <span style="font-size:16px;font-weight:700;opacity:0.9;white-space:nowrap;">'+stage+'</span></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;"><span style="padding:6px 10px;border-radius:999px;background:'+(isLight?'rgba(255,255,255,0.78)':'rgba(15,23,42,0.28)')+';border:1px solid '+(isLight?'rgba(99,102,241,0.12)':'rgba(255,255,255,0.08)')+';font-size:12px;color:'+labelColor+';">总经验 '+formatGrowthNumber(totalExp)+'</span><span style="padding:6px 10px;border-radius:999px;background:'+(isLight?'rgba(255,255,255,0.78)':'rgba(15,23,42,0.28)')+';border:1px solid '+(isLight?'rgba(99,102,241,0.12)':'rgba(255,255,255,0.08)')+';font-size:12px;color:'+labelColor+';">本级 '+formatGrowthNumber(growth.currentExp)+'/'+formatGrowthNumber(growth.nextNeed)+'</span></div></div><div style="padding:7px 12px;border-radius:999px;background:'+(isLight?'rgba(79,70,229,0.1)':'rgba(129,140,248,0.16)')+';border:1px solid '+(isLight?'rgba(79,70,229,0.14)':'rgba(129,140,248,0.2)')+';font-size:12px;font-weight:700;color:'+(isLight?'#4338ca':'#c7d2fe')+';white-space:nowrap;">升级还差 '+formatGrowthNumber(growth.remainingExp)+' EXP</div></div><div style="margin-top:2px;height:10px;background:'+(isLight?'#e5e7eb':'rgba(255,255,255,0.08)')+';border-radius:999px;overflow:hidden;"><div style="height:100%;width:'+progress+'%;background:linear-gradient(90deg,#667eea,#764ba2);border-radius:999px;"></div></div></div>';
   overview+='<div style="background:'+softBg+';border:1px solid '+borderColor+';padding:14px 14px 13px;border-radius:16px;backdrop-filter:blur(8px);min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;">记忆粒子（L1）</div><div style="font-size:22px;font-weight:800;color:'+textColor+';line-height:1.05;">'+counts.L1+'</div><div style="font-size:11px;color:'+labelColor+';margin-top:8px;line-height:1.55;">最细小的输入与感知片段</div></div>';
   overview+='<div style="background:'+softBg+';border:1px solid '+borderColor+';padding:14px 14px 13px;border-radius:16px;backdrop-filter:blur(8px);min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;">记忆结晶（L3）</div><div style="font-size:22px;font-weight:800;color:'+textColor+';line-height:1.05;">'+counts.L3+'</div><div style="font-size:11px;color:'+labelColor+';margin-top:8px;line-height:1.55;">已经沉淀成结构的长期片段</div></div>';
   overview+='<div style="background:'+softBg+';border:1px solid '+borderColor+';padding:14px 14px 13px;border-radius:16px;backdrop-filter:blur(8px);min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;">相伴天数</div><div style="font-size:22px;font-weight:800;color:'+textColor+';line-height:1.05;">'+days+'</div><div style="font-size:11px;color:'+labelColor+';margin-top:8px;line-height:1.55;">一起把系统慢慢养起来的时间</div></div>';
   document.getElementById('memoryOverview').innerHTML=overview;

   var grouped={};
   events.forEach(function(e){
    var date=e.time?String(e.time).split('T')[0].split(' ')[0]:'未知';
    if(!grouped[date]) grouped[date]=[];
    grouped[date].push(e);
   });
   var dates=Object.keys(grouped).sort().reverse();
   var html='';
    dates.forEach(function(date){
     var label=date;
     var now=new Date();
     var today=now.getFullYear()+'-'+String(now.getMonth()+1).padStart(2,'0')+'-'+String(now.getDate()).padStart(2,'0');
     var yd=new Date(now.getFullYear(),now.getMonth(),now.getDate()-1);
     var yesterday=yd.getFullYear()+'-'+String(yd.getMonth()+1).padStart(2,'0')+'-'+String(yd.getDate()).padStart(2,'0');
     if(date===today) label='今天'; else if(date===yesterday) label='昨天';
     html+='<div class="mem-date-group">';
     html+='<div class="mem-date-label" style="font-size:12px;color:'+labelColor+';margin:18px 0 8px 0;font-weight:700;letter-spacing:0.3px;">'+label+'</div>';
     grouped[date].forEach(function(e){
      var view=memoryEventCopy(e);
      var layer=e.layer||'MEM';
     var tagBg='#475569'; var tagColor='#e2e8f0';
     if(layer==='L1'){tagBg='#0f766e';tagColor='#ccfbf1';}
     else if(layer==='L3'){tagBg='#1d4ed8';tagColor='#dbeafe';}
     else if(layer==='L4'){tagBg='#6d28d9';tagColor='#ede9fe';}
     else if(layer==='L5'){tagBg='#3d2f0a';tagColor='#fcd34d';}
     else if(layer==='L6'){tagBg='#14532d';tagColor='#86efac';}
     else if(layer==='L7'){tagBg='#7c2d12';tagColor='#fdba74';}
     else if(layer==='L8'){tagBg='#1f4a3d';tagColor='#6ee7b7';}
     var time=e.time?String(e.time).replace('T',' ').substring(11,16):'';
     html+='<div class="mem-item" data-layer="'+layer+'" style="padding:16px 18px;background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;margin-bottom:10px;box-shadow:'+(isLight?'0 6px 20px rgba(15,23,42,0.06)':'0 8px 24px rgba(0,0,0,0.14)')+';position:relative;overflow:hidden;">';
     html+='<div style="position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg, transparent, rgba(102,126,234,0.55), transparent);"></div>';
     html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;"><div style="display:flex;align-items:center;gap:8px;min-width:0;"><span style="font-size:10px;padding:3px 8px;background:'+tagBg+';color:'+tagColor+';border-radius:999px;font-weight:700;flex-shrink:0;">'+layer+'</span><span style="font-size:14px;font-weight:700;color:'+textColor+';letter-spacing:0.2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+view.title.replace(/^'+layer+'\s?/,'')+'</span></div><span style="font-size:11px;color:'+labelColor+';flex-shrink:0;">'+time+'</span></div>';
      html+='<div style="font-size:13px;color:'+textColor+';line-height:1.82;opacity:0.96;">'+view.content+'</div>';
      html+='</div>';
     });
     html+='</div>';
    });
   document.getElementById('memoryTimeline').innerHTML=html||'<div style="color:'+labelColor+';">还没有记忆事件</div>';
   var allNode=document.querySelector('.mem-chip');
   if(allNode) setMemoryFilter('all', allNode);
  }).catch(function(){
   document.getElementById('memoryTimeline').innerHTML='<div style="color:#ef4444;">记忆数据加载失败</div>';
  });
 }

 if(n==5){
  loadSettingsPage(isLight);
  return;
 }

 if(n==6){
  loadDocsPage(isLight);
  return;
 }
}
</script>
