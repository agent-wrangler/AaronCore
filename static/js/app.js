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
  chat.innerHTML='<div class="skill-store"><div class="skill-store-title"><svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 3l1.8 4.6L18.5 9 14 10.7 12 15l-2-4.3L5.5 9l4.7-1.4z" stroke="currentColor" fill="none"/><path d="M18 15l.9 2.1L21 18l-2.1.9L18 21l-.9-2.1L15 18l2.1-.9z" stroke="currentColor" fill="none"/></svg>\u6280\u80fd\u4e2d\u5fc3</div><div id="skillsList">\u52a0\u8f7d\u4e2d...</div></div>';
  fetch('/skills').then(r=>r.json()).then(function(d){
   // SVG 图标映射（线条风格，带 inline 尺寸防止 CSS 未加载时撑满）
   var icons={
    '\u5929\u6c14':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M6.34 17.66l-1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/><circle cx="12" cy="12" r="4"/></svg>',
    '\u80a1\u7968':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
    '\u65b0\u95fb':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z"/><line x1="6" y1="8" x2="18" y2="8"/><line x1="6" y1="12" x2="14" y2="12"/><line x1="6" y1="16" x2="10" y2="16"/></svg>',
    '\u6587\u7ae0':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
    '\u6545\u4e8b':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>',
    '\u753b\u56fe':'<svg viewBox="0 0 24 24" width="22" height="22"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
    '\u4ee3\u7801':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    '\u7f16\u7a0b':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>'
   };
   // 分类图标
   var catIcons={
    '\u4fe1\u606f\u67e5\u8be2':'<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    '\u5185\u5bb9\u521b\u4f5c':'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
    '\u5f00\u53d1\u5de5\u5177':'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>'
   };
   // 按 category 分组
   var catOrder=['\u4fe1\u606f\u67e5\u8be2','\u5185\u5bb9\u521b\u4f5c','\u5f00\u53d1\u5de5\u5177'];
   var groups={};
   catOrder.forEach(function(c){groups[c]=[];});
   if(d.skills){
    d.skills.forEach(function(s){
     var cat=s.category||'\u5f00\u53d1\u5de5\u5177';
     if(!groups[cat])groups[cat]=[];
     groups[cat].push(s);
    });
   }
   var html='';
   catOrder.forEach(function(catName){
    var skills=groups[catName];
    if(!skills||skills.length===0)return;
    var ci=catIcons[catName]||'';
    html+='<div class="skill-category">';
    html+='<div class="skill-category-header">'+ci+'<span class="skill-category-name">'+catName+'</span><span class="skill-category-count">'+skills.length+'</span></div>';
    html+='<div class="skill-grid">';
    skills.forEach(function(s){
     var name=s.name||'';
     var iconKey=Object.keys(icons).find(function(k){return name.indexOf(k)!==-1;});
     var icon=iconKey?icons[iconKey]:'<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
     var isOnline=s.status==='ready';
     html+='<div class="skill-card">';
     html+='<div class="skill-card-icon">'+icon+'</div>';
     html+='<div class="skill-card-name">'+name+'</div>';
     html+='<div class="skill-card-desc">'+(s.description||'\u6682\u65e0\u63cf\u8ff0')+'</div>';
     html+='<div class="skill-card-status"><span class="dot'+(isOnline?'':' offline')+'"></span>'+(isOnline?'\u5728\u7ebf':'\u79bb\u7ebf')+'</div>';
     html+='</div>';
    });
    html+='</div></div>';
   });
   // 未分类的也展示
   Object.keys(groups).forEach(function(cat){
    if(catOrder.indexOf(cat)===-1&&groups[cat].length>0){
     html+='<div class="skill-category"><div class="skill-category-header"><span class="skill-category-name">'+cat+'</span><span class="skill-category-count">'+groups[cat].length+'</span></div><div class="skill-grid">';
     groups[cat].forEach(function(s){
      html+='<div class="skill-card"><div class="skill-card-icon"><svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10"/></svg></div><div class="skill-card-name">'+(s.name||'')+'</div><div class="skill-card-desc">'+(s.description||'')+'</div><div class="skill-card-status"><span class="dot'+(s.status==='ready'?'':' offline')+'"></span>'+(s.status==='ready'?'\u5728\u7ebf':'\u79bb\u7ebf')+'</div></div>';
     });
     html+='</div></div>';
    }
   });
   document.getElementById('skillsList').innerHTML=html;
  }).catch(function(){
   document.getElementById('skillsList').innerHTML='<div style="color:#ef4444;">\u6280\u80fd\u6570\u636e\u52a0\u8f7d\u5931\u8d25</div>';
  });
 }

 if(n==3){
  setInputVisible(false);
  chat.innerHTML='<div class="stats-page"><h2 class="page-title" style="margin-bottom:15px;"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:6px;"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>\u6570\u636e\u770b\u677f</h2><div id="statsBox">\u52a0\u8f7d\u4e2d...</div></div>';
  fetch('/stats').then(function(r){return r.json()}).then(function(d){
   var s=d.stats||d||{};
   var bs=s.by_scene||{};
   var totalReq=s.total_requests||0;
   var avgToken=totalReq>0?Math.round((s.total_tokens||0)/totalReq):0;
   var svgToken='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
   var svgCall='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M7.76 16.24a6 6 0 0 1 0-8.49"/><path d="M4.93 19.07a10 10 0 0 1 0-14.14"/></svg>';
   var svgScene='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>';
   var svgCache='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="M12 18v4"/><path d="M4.93 4.93l2.83 2.83"/><path d="M16.24 16.24l2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="M4.93 19.07l2.83-2.83"/><path d="M16.24 7.76l2.83-2.83"/></svg>';
   // Token \u6d88\u8017
   var h='<div class="stats-section"><div class="stats-section-title">'+svgToken+' Token \u6d88\u8017</div><div class="stats-grid">';
   h+='<div class="stats-card"><div class="stats-label">\u8f93\u5165</div><div class="stats-number">'+((s.input_tokens||0).toLocaleString())+'</div></div>';
   h+='<div class="stats-card"><div class="stats-label">\u8f93\u51fa</div><div class="stats-number">'+((s.output_tokens||0).toLocaleString())+'</div></div>';
   h+='<div class="stats-card"><div class="stats-label">\u603b Token</div><div class="stats-number">'+((s.total_tokens||0).toLocaleString())+'</div></div>';
   h+='</div></div>';
   // \u8c03\u7528\u7edf\u8ba1
   h+='<div class="stats-section"><div class="stats-section-title">'+svgCall+' \u8c03\u7528\u7edf\u8ba1</div><div class="stats-grid">';
   h+='<div class="stats-card"><div class="stats-label">\u603b\u8bf7\u6c42</div><div class="stats-number">'+(totalReq.toLocaleString())+'</div></div>';
   h+='<div class="stats-card"><div class="stats-label">\u5e73\u5747\u6d88\u8017</div><div class="stats-number">'+(avgToken.toLocaleString())+' <span style="font-size:12px;font-weight:400;opacity:0.6;">/\u6b21</span></div></div>';
   h+='<div class="stats-card"><div class="stats-label">\u5f53\u524d\u6a21\u578b</div><div class="stats-number model-name">'+(s.model||'-')+'</div></div>';
   h+='</div></div>';
   // \u7f13\u5b58\u7edf\u8ba1
   var cacheWrite=s.cache_write_tokens||0;
   var cacheRead=s.cache_read_tokens||0;
   var cacheTotal=cacheWrite+cacheRead;
   var cacheRate=(s.input_tokens||0)>0?Math.round(cacheRead/(s.input_tokens||1)*100):0;
   h+='<div class="stats-section"><div class="stats-section-title">'+svgCache+' \u7f13\u5b58\u7edf\u8ba1</div><div class="stats-grid">';
   h+='<div class="stats-card"><div class="stats-label">\u7f13\u5b58\u5199\u5165</div><div class="stats-number">'+(cacheWrite.toLocaleString())+'</div></div>';
   h+='<div class="stats-card"><div class="stats-label">\u7f13\u5b58\u8bfb\u53d6</div><div class="stats-number">'+(cacheRead.toLocaleString())+'</div></div>';
   h+='<div class="stats-card"><div class="stats-label">\u547d\u4e2d\u7387</div><div class="stats-number stats-highlight">'+(cacheRate)+'%</div></div>';
   h+='</div></div>';
   // 本地记忆总览
   var mem=s.memory||{};
   var l2s=mem.l2_searches||0,l2h=mem.l2_hits||0;
   var l8s=mem.l8_searches||0,l8h=mem.l8_hits||0;
   var tq=mem.total_queries||0;
   var fla=mem.full_layer_available||0;
   var l2rate=l2s>0?Math.round(l2h/l2s*100):0;
   var l8rate=l8s>0?Math.round(l8h/l8s*100):0;
   // 综合有效率 = (全量层贡献 + 检索层贡献) / (总请求×2) × 100%
   var fullLayerPct=tq>0?Math.round(fla/(tq*4)*100):0;
   var searchHits=(l2h+l8h);var searchTotal=(l2s+l8s);
   var searchPct=searchTotal>0?Math.round(searchHits/searchTotal*100):0;
   var compositeRate=tq>0?Math.min(100,Math.round((fullLayerPct+searchPct)/2)):0;
   var svgMem='<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>';
   h+='<div class="stats-section"><div class="stats-section-title">'+svgMem+' \u672c\u5730\u8bb0\u5fc6\u603b\u89c8</div>';
   h+='<div style="text-align:center;padding:12px 0 8px;"><div style="font-size:32px;font-weight:700;" class="stats-highlight">'+compositeRate+'%</div>';
   h+='<div style="font-size:12px;opacity:0.6;margin-top:2px;">\u7efc\u5408\u6709\u6548\u7387</div></div>';
   h+='<div style="display:flex;justify-content:center;gap:24px;font-size:12px;opacity:0.7;padding-bottom:10px;">';
   h+='<span>\u5168\u91cf\u5c42\u8d21\u732e '+fullLayerPct+'%</span><span>\u68c0\u7d22\u5c42\u8d21\u732e '+searchPct+'%</span></div>';
   h+='<div class="stats-grid">';
   h+='<div class="stats-card"><div class="stats-label">L2 \u547d\u4e2d\u7387</div><div class="stats-number stats-highlight">'+l2rate+'%</div><div style="font-size:11px;opacity:0.5;margin-top:2px;">'+l2s+'\u6b21/'+l2h+'\u547d\u4e2d</div></div>';
   h+='<div class="stats-card"><div class="stats-label">L8 \u547d\u4e2d\u7387</div><div class="stats-number stats-highlight">'+l8rate+'%</div><div style="font-size:11px;opacity:0.5;margin-top:2px;">'+l8s+'\u6b21/'+l8h+'\u547d\u4e2d</div></div>';
   h+='<div class="stats-card"><div class="stats-label">L1 \u5bf9\u8bdd</div><div class="stats-number">'+(mem.l1_count||0)+'\u6761</div></div>';
   h+='<div class="stats-card"><div class="stats-label">L3 \u7ecf\u5386</div><div class="stats-number">'+(mem.l3_count||0)+'\u6761</div></div>';
   h+='<div class="stats-card"><div class="stats-label">L4 \u4eba\u683c</div><div class="stats-number">'+(mem.l4_available?'\u2705':'\u274c')+'</div></div>';
   h+='<div class="stats-card"><div class="stats-label">L5 \u6280\u80fd</div><div class="stats-number">'+(mem.l5_count||0)+'\u4e2a</div></div>';
   h+='</div></div>';
   // \u573a\u666f\u5206\u5e03
   var scenes=[{k:'chat',n:'\u804a\u5929'},{k:'route',n:'\u8def\u7531'},{k:'skill',n:'\u6280\u80fd'},{k:'learn',n:'\u5b66\u4e60'}];
   var totalSceneTokens=0;
   scenes.forEach(function(sc){totalSceneTokens+=(bs[sc.k]||{}).tokens||0;});
   h+='<div class="stats-section"><div class="stats-section-title">'+svgScene+' \u573a\u666f\u5206\u5e03</div>';
   if(totalSceneTokens>0){
   h+='<div class="stats-bars">';
   scenes.forEach(function(sc){
    var t=(bs[sc.k]||{}).tokens||0;
    var r=(bs[sc.k]||{}).requests||0;
    var pct=totalSceneTokens>0?Math.round(t/totalSceneTokens*100):0;
    h+='<div class="stats-bar-row"><div class="stats-bar-label">'+sc.n+'</div>';
    h+='<div class="stats-bar-track"><div class="stats-bar-fill '+sc.k+'" style="width:'+pct+'%"></div></div>';
    h+='<div class="stats-bar-pct">'+pct+'% <span style="opacity:0.5;font-size:11px;">'+r+'\u6b21</span></div></div>';
   });
   h+='</div>';
   }else{
   h+='<div style="text-align:center;padding:16px;color:#64748b;font-size:13px;">\u804a\u51e0\u53e5\u5c31\u6709\u6570\u636e\u4e86</div>';
   }
   h+='</div>';
   // \u5e95\u90e8
   h+='<div class="stats-footer"><div class="stats-footer-info">\u6700\u540e\u4f7f\u7528\uff1a'+(s.last_used||'-')+'</div>';
   h+='<button class="stats-reset-btn" onclick="if(confirm(\'\u786e\u8ba4\u91cd\u7f6e\u6240\u6709\u7edf\u8ba1\u6570\u636e\uff1f\')){fetch(\'/stats\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({reset:true})}).then(function(){show(3)})}">\u21bb \u91cd\u7f6e\u7edf\u8ba1</button></div>';
   document.getElementById('statsBox').innerHTML=h;
  }).catch(function(){
   document.getElementById('statsBox').innerHTML='<div style="color:#ef4444;">\u7edf\u8ba1\u6570\u636e\u52a0\u8f7d\u5931\u8d25</div>';
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
