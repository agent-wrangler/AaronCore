var _SVG_SUN='<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
var _SVG_MOON='<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
function _syncThemeIcon(){
 var btn=document.getElementById('themeBtn');
 if(!btn) return;
 btn.innerHTML=document.body.classList.contains('light')?_SVG_SUN:_SVG_MOON;
}
function _syncTitleBar(theme){
 if(window.novaShell) window.novaShell.setTheme(theme);
 else if(window.pywebview&&window.pywebview.api&&window.pywebview.api.set_theme)
  window.pywebview.api.set_theme(theme);
}

function toggleTheme(){
 var body=document.body;
 if(body.classList.contains('dark')){
  body.classList.remove('dark');
  body.classList.add('light');
  localStorage.setItem('nova_theme','light');
  _syncTitleBar('light');
  _syncThemeIcon();
 }else{
  body.classList.remove('light');
  body.classList.add('dark');
  localStorage.setItem('nova_theme','dark');
  _syncTitleBar('dark');
  _syncThemeIcon();
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

// 快捷发送（欢迎页按钮）
function quickSend(text){
 var inp=document.getElementById('inp');
 inp.value=text;
 send();
}

// 隐藏欢迎页
function loadWelcomeNews(){
 var el=document.getElementById('welcomeNewsList');
 if(!el) return;
 fetch('/skills/news/headlines').then(function(r){return r.json();}).then(function(d){
  var items=d.headlines||d.items||[];
  if(!items.length){el.innerHTML='<div style="color:#6b7280;font-size:13px;">'+t('welcome.news.empty')+'</div>';return;}
  el.innerHTML=items.slice(0,6).map(function(item){
   var title=typeof item==='string'?item:(item.title||item.text||'');
   return '<div class="welcome-news-item" onclick="quickSend(\'帮我介绍一下：'+title.replace(/'/g,'')+'\')">'+title+'</div>';
  }).join('');
 }).catch(function(){
  el.innerHTML='<div style="color:#6b7280;font-size:13px;">'+t('welcome.news.offline')+'</div>';
 });
}
function hideWelcome(){
 var w=document.getElementById('welcomePage');
 if(w) w.style.display='none';
}

window.onload=function(){
 window._currentTab=1; // 默认聊天 tab
 initSidebarResize();
 loadWelcomeNews();
 // 输入框右键菜单（pywebview 不提供原生右键）
 (function(){
  var menu=document.createElement('div');
  menu.id='ctx-menu';
  menu.style.cssText='position:fixed;z-index:9999;background:#2a2a2e;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:4px 0;display:none;box-shadow:0 4px 16px rgba(0,0,0,0.4);min-width:100px;';
  var items=[{label:t('ctx.cut'),act:'cut'},{label:t('ctx.copy'),act:'copy'},{label:t('ctx.paste'),act:'paste'},{label:t('ctx.selectAll'),act:'selectAll'}];
  items.forEach(function(it){
   var d=document.createElement('div');
   d.textContent=it.label;
   d.style.cssText='padding:6px 16px;font-size:13px;color:#e0e0e0;cursor:pointer;';
   d.onmouseenter=function(){d.style.background='rgba(255,255,255,0.08)';};
   d.onmouseleave=function(){d.style.background='none';};
   d.onclick=function(){document.execCommand(it.act);menu.style.display='none';};
   menu.appendChild(d);
  });
  document.body.appendChild(menu);
  document.getElementById('inp').addEventListener('contextmenu',function(e){
   e.preventDefault();
   menu.style.display='block';
   var mh=menu.offsetHeight;
   var x=e.clientX,y=e.clientY;
   if(y+mh>window.innerHeight) y=y-mh;
   if(x+menu.offsetWidth>window.innerWidth) x=window.innerWidth-menu.offsetWidth-5;
   menu.style.left=x+'px';
   menu.style.top=y+'px';
  });
  document.addEventListener('click',function(){menu.style.display='none';});
 })();

 // 加载保存的主题，默认白天
 var savedTheme=localStorage.getItem('nova_theme')||'light';
 if(savedTheme==='light'){
  document.body.classList.remove('dark');
  document.body.classList.add('light');
 }
 _syncThemeIcon();
 // pywebview API 可能延迟就绪，等一下再同步标题栏颜色
 setTimeout(function(){
  _syncTitleBar(savedTheme==='light'?'light':'dark');
 },800);

 // 从后端加载聊天历史
 window._historyOffset=0;
 window._historyHasMore=false;
 window._historyLoading=false;

 window._renderHistoryItems=function(items){
  function _renderProcessTimeline(process){
   var steps=(process&&process.steps)||[];
   if(!steps.length) return '';
   var html='<div class="step-tracker">';
   steps.forEach(function(step){
    var label=escapeHtml(String((step&&step.label)||''));
    var rawStatus=String((step&&step.status)||'done');
    var status=escapeHtml(rawStatus==='error'?'error':'done');
    var detailRaw=String((step&&((step.full_detail&&String(step.full_detail).trim())||step.detail))||'');
    var detail=escapeHtml(detailRaw);
    html+='<div class="step-item '+status+' expanded">';
    html+='<div class="step-icon '+status+'"></div>';
    html+='<span class="step-label">'+label+'</span>';
    html+='<span class="step-detail">'+detail+'</span>';
    html+='</div>';
   });
   html+='</div>';
   return html;
  }

  var html='';
  items.forEach(function(item){
   var role=item.role||'user';
   var text=item.content||'';
   var process=item.process||null;
   var time=item.time||'';
   if(!text.trim()) return;
   var cls=role==='user'?'user':'assistant';
   var name=role==='user'?t('chat.you'):'Nova';
   var avBg=role==='user'?'linear-gradient(135deg,#10b981,#059669)':'linear-gradient(135deg,#667eea,#764ba2)';
   var avTxt=role==='user'?t('chat.you'):'N';
   html+='<div class="msg '+cls+'">';
   html+='<div class="avatar" style="background:'+avBg+'">'+avTxt+'</div>';
   if(role==='user'){
    html+='<div class="msg-content">';
   }else if(process&&process.steps&&process.steps.length){
    html+='<div class="msg-content-wrap">';
    html+=_renderProcessTimeline(process);
    html+='<div class="msg-content">';
   }else{
    html+='<div class="msg-content">';
   }
   html+='<div class="msg-meta">';
   html+='<span class="msg-name">'+name+'</span><span class="msg-time">'+time+'</span>';
   html+='</div>';
   html+='<div class="bubble">'+formatBubbleText(text)+'</div>';
   html+='</div>';
   if(role!=='user'&&process&&process.steps&&process.steps.length){
    html+='</div>';
   }
   html+='</div>';
  });
  return html;
 };

 window._loadMoreHistory=function(){
  if(window._historyLoading||!window._historyHasMore) return;
  if(window._currentTab!==1&&window._currentTab!==undefined) return;
  window._historyLoading=true;
  var chat=document.getElementById('chat');
  var prevHeight=chat.scrollHeight;
  fetch('/history?limit=20&offset='+window._historyOffset).then(function(r){return r.json()}).then(function(d){
   if(window._currentTab!==1&&window._currentTab!==undefined){window._historyLoading=false;return;}
   var items=d.history||[];
   window._historyHasMore=d.has_more||false;
   window._historyOffset+=items.length;
   if(items.length===0){window._historyLoading=false;return;}
   var html=window._renderHistoryItems(items);
   // 加载历史：禁用 smooth 防止跳动，精确保持视线位置
   chat.style.scrollBehavior='auto';
   chat.insertAdjacentHTML('afterbegin',html);
   chatHistory=chat.innerHTML;
   chat.scrollTop=chat.scrollHeight-prevHeight;
   requestAnimationFrame(function(){ chat.style.scrollBehavior=''; });
   window._historyLoading=false;
   _rebindStepToggles(chat);
  }).catch(function(){window._historyLoading=false;});
 };

 // 始终绑定 scroll 监听器（不依赖初始加载成功）
 var chat=document.getElementById('chat');
 var _scrollBtn=document.getElementById('scrollToBottomBtn');

 function _updateScrollBtn(){
  if(!_scrollBtn) return;
  var awayFromBottom=chat.scrollHeight-chat.scrollTop-chat.clientHeight;
  if(awayFromBottom>150){
   _scrollBtn.style.display='flex';
   requestAnimationFrame(function(){ _scrollBtn.classList.add('visible'); });
  }else{
   _scrollBtn.classList.remove('visible');
   setTimeout(function(){ if(!_scrollBtn.classList.contains('visible')) _scrollBtn.style.display='none'; },200);
  }
 }

 window.scrollToBottom=function(){
  chat.scrollTo({top:chat.scrollHeight,behavior:'smooth'});
 };

 chat.addEventListener('scroll',function(){
  if(window._currentTab!==1&&window._currentTab!==undefined) return;
  _updateScrollBtn();
  if(chat.scrollTop<80&&window._historyHasMore&&!window._historyLoading){
   window._loadMoreHistory();
  }
 });

fetch('/history?limit=15&offset=0').then(function(r){return r.json()}).then(function(d){
  var items=d.history||[];
  window._historyHasMore=d.has_more||false;
  window._historyOffset=items.length;
  if(items.length===0) return;
  if(typeof window._clearSessionTaskPlan==='function'){
   window._clearSessionTaskPlan();
  }
  var chat=document.getElementById('chat');
  chat.innerHTML=window._renderHistoryItems(items);
  chatHistory=chat.innerHTML;
  chat.style.scrollBehavior='auto';
  chat.scrollTop=chat.scrollHeight;
  requestAnimationFrame(function(){ chat.style.scrollBehavior=''; });
  console.log('[Nova] 从后端恢复聊天历史，消息数:', items.length, '更多:', window._historyHasMore);
  // 重新绑定步骤折叠按钮事件
  _rebindStepToggles(chat);
  // 边界修复：如果内容不够高（无法滚动），且还有更多历史，自动继续加载
  if(window._historyHasMore){
   var _autoFill=function(){
    if(!window._historyHasMore||window._historyLoading) return;
    if(chat.scrollHeight<=chat.clientHeight+100){
     window._loadMoreHistory();
     setTimeout(_autoFill, 300);
    }
   };
   setTimeout(_autoFill, 200);
  }
 }).catch(function(e){ console.warn('[Nova] 加载历史失败',e); });
 
 // 初始化输入框监听
 var inp=document.getElementById('inp');
 inp.addEventListener('input',updateSendButton);
 updateSendButton();
 setInputVisible(true);
 AwarenessManager.init();

 window._rebindStepToggles=function(container){
 var toggles=(container||document).querySelectorAll('.step-tracker-toggle');
 toggles.forEach(function(btn){
  var tracker=btn.closest('.step-tracker');
  if(!tracker) return;
  btn.onclick=function(e){
   e.preventDefault(); e.stopPropagation();
   if(tracker.classList.contains('collapsed')){
    tracker.classList.remove('collapsed');
    var sp=btn.querySelector('span'); if(sp) sp.textContent='收起步骤';
   }else{
    tracker.classList.add('collapsed');
    var steps=tracker.querySelectorAll('.step-item');
    var sp=btn.querySelector('span'); if(sp) sp.textContent=steps.length+' 步完成';
   }
  };
 });
};

// 读取模型列表
 fetch('/models').then(r=>r.json()).then(function(d){
  var el=document.getElementById('modelName');
  var models=d.models||{};
  var cur=d.current||'';
  var displayName=(models[cur]&&models[cur].model)?models[cur].model:(cur||t('unknown'));
  if(el) el.textContent=displayName;
  window._novaModels=models;
  window._novaCurrentModel=cur;
  updateImageBtnState();
  // 加载 catalog 供 dropdown 分组用
  fetch('/models/catalog').then(function(r){return r.json();}).then(function(c){
   window._novaCatalog=c.catalog||{};
  }).catch(function(){});
 }).catch(function(){
  var el=document.getElementById('modelName');
  if(el) el.textContent=t('unknown');
 });
};

function show(n){
 window._currentTab=n;
 for(var i=1;i<=7;i++){
  var menu=document.getElementById('m'+i);
  if(menu) menu.classList.remove('active');
 }
 document.getElementById('m'+n).classList.add('active');
 var chat = document.getElementById('chat');
 var isLight = document.body.classList.contains('light');

 if(n==1){
  setInputVisible(true);
  if(chatHistory && chatHistory.trim()!==''){
   chat.innerHTML=chatHistory;
   var currentMsgCount=chat.querySelectorAll('.msg').length;
   if(currentMsgCount<window._historyOffset){
    window._historyOffset=currentMsgCount;
    window._historyHasMore=true;
   }
   chat.style.scrollBehavior='auto';
   chat.scrollTop=chat.scrollHeight;
   requestAnimationFrame(function(){ chat.style.scrollBehavior=''; });
  } else {
   chat.innerHTML='';
  }
 }

 if(n==2){
  setInputVisible(false);
  chat.innerHTML='<div class="skill-store"><div id="skillsList">'+t('loading')+'</div></div>';
  _loadSkillsList();
 }

 if(n==3){
  setInputVisible(false);
  chat.innerHTML='<div class="stats-page"><div style="text-align:right;margin-bottom:8px;"><button class="stats-refresh-btn" onclick="loadStatsData()" title="刷新数据"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button></div><div id="statsBox">'+t('loading')+'</div></div>';
  loadStatsData();
 }

 if(n==4){
  setInputVisible(false);
  var _savedMemFilter=currentMemoryFilter||'all';
  chat.innerHTML='<div id="memScroll"><div id="memoryOverview" style="display:grid;grid-template-columns:'+memoryOverviewColumns()+';gap:12px;margin-bottom:18px;"></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;" id="memoryChips"><button class="mem-chip" onclick="setMemoryFilter(\'all\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-primary);cursor:pointer;">'+t('mem.filter.all')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L2\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L2')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L3\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L3')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L4\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L4')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L5\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L5')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L6\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L6')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L7\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L7')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L8\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L8')+'</button></div><div style="margin-bottom:18px;"><input id="memorySearch" type="text" placeholder="'+t('mem.search')+'" style="width:100%;padding:12px 16px;border-radius:12px;border:1px solid var(--border-input);background:var(--bg-input);color:var(--text-primary);outline:none;" onkeyup="filterMemBySearch(this.value)"></div><div id="memoryTimeline" style="display:flex;flex-direction:column;gap:10px;">'+t('loading')+'</div></div>';
  fetch('/memory').then(r=>r.json()).then(function(d){
   var softBg='var(--bg-soft)';
   var textColor='var(--text-primary)';
   var labelColor='var(--text-label)';
   var borderColor='var(--border-card)';
   var events=d.events||[];
   var counts=d.counts||{L1:0,L2:0,L3:0,L4:0,L5:0,L6:0,L7:0,L8:0};
   if(!d.counts){
    events.forEach(function(e){ if(counts[e.layer]!==undefined) counts[e.layer]++; });
   }
   console.log('[MEMORY DEBUG] d.counts:', d.counts, 'final counts:', JSON.stringify(counts));
   var days=Math.max(1, Math.floor((Date.now() - new Date('2026-02-26').getTime())/86400000)+1);
   var growth=memoryGrowthProfile(counts);
   console.log('[MEMORY DEBUG] growth:', JSON.stringify(growth));
   var totalExp=growth.totalExp;
   var level=growth.level;
   var progress=growth.progressPercent;
   var stage=t('mem.growth.stage.awake');
   if(level>=2) stage=t('mem.growth.stage.grow');
   if(level>=10) stage=t('mem.growth.stage.resonate');
   if(level>=30) stage=t('mem.growth.stage.evolve');
   if(level>=60) stage=t('mem.growth.stage.selfconsist');
   if(level>=120) stage=t('mem.growth.stage.expand');
   if(level>=300) stage=t('mem.growth.stage.stars');
   if(level>=1000) stage=t('mem.growth.stage.infinite');
   var overview='';
   overview+='<div style="background:var(--bg-growth);border:1px solid '+borderColor+';padding:18px;border-radius:18px;box-shadow:var(--shadow-card);display:flex;flex-direction:column;gap:12px;">';
   overview+='<div style="display:flex;align-items:center;gap:6px;"><span style="font-size:12px;color:'+labelColor+';">'+t('mem.growth.level')+'</span><span class="mem-help-trigger" style="position:relative;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;border:1px solid '+labelColor+';color:'+labelColor+';font-size:10px;font-weight:700;cursor:help;" onmouseenter="this.querySelector(\'.mem-help-tip\').style.display=\'block\'" onmouseleave="this.querySelector(\'.mem-help-tip\').style.display=\'none\'">?<div class="mem-help-tip" style="display:none;position:absolute;left:22px;top:-8px;width:260px;padding:12px;border-radius:10px;background:var(--bg-card);border:1px solid '+borderColor+';font-size:11px;color:'+labelColor+';line-height:1.7;z-index:99;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-weight:400;cursor:default;" onmouseenter="this.style.display=\'block\'" onmouseleave="this.style.display=\'none\'">'+t('mem.desc')+'</div></span></div><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;"><div style="min-width:0;"><div style="display:inline-flex;align-items:baseline;gap:8px;white-space:nowrap;font-size:28px;font-weight:800;color:'+textColor+';margin-bottom:2px;">Lv.'+level+' <span style="font-size:16px;font-weight:700;opacity:0.9;white-space:nowrap;">'+stage+'</span></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;"><span style="padding:6px 10px;border-radius:999px;background:var(--bg-tag-pill);border:1px solid var(--border-tag-pill);font-size:12px;color:'+labelColor+';">'+t('mem.growth.totalExp')+' '+formatGrowthNumber(totalExp)+'</span><span style="padding:6px 10px;border-radius:999px;background:var(--bg-tag-pill);border:1px solid var(--border-tag-pill);font-size:12px;color:'+labelColor+';">'+t('mem.growth.currentLevel')+' '+formatGrowthNumber(growth.currentExp)+'/'+formatGrowthNumber(growth.nextNeed)+'</span></div></div><div style="padding:7px 12px;border-radius:999px;background:var(--bg-badge);border:1px solid var(--border-badge);font-size:12px;font-weight:700;color:var(--text-badge);white-space:nowrap;">'+t('mem.growth.needMore')+' '+formatGrowthNumber(growth.remainingExp)+' EXP</div></div><div style="margin-top:2px;height:10px;background:var(--bar-track);border-radius:999px;overflow:hidden;"><div style="height:100%;width:'+progress+'%;background:var(--bar-fill);border-radius:999px;"></div></div></div>';
   overview+='<div style="background:'+softBg+';border:1px solid '+borderColor+';padding:14px 14px 13px;border-radius:16px;backdrop-filter:blur(8px);min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;">'+t('mem.card.L1.title')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';line-height:1.05;">'+counts.L1+'</div><div style="font-size:11px;color:'+labelColor+';margin-top:8px;line-height:1.55;">'+t('mem.card.L1.desc')+'</div></div>';
   overview+='<div style="background:'+softBg+';border:1px solid '+borderColor+';padding:14px 14px 13px;border-radius:16px;backdrop-filter:blur(8px);min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;">'+t('mem.card.L3.title')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';line-height:1.05;">'+counts.L3+'</div><div style="font-size:11px;color:'+labelColor+';margin-top:8px;line-height:1.55;">'+t('mem.card.L3.desc')+'</div></div>';
   overview+='<div style="background:'+softBg+';border:1px solid '+borderColor+';padding:14px 14px 13px;border-radius:16px;backdrop-filter:blur(8px);min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;">'+t('mem.card.days.title')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';line-height:1.05;">'+days+'</div><div style="font-size:11px;color:'+labelColor+';margin-top:8px;line-height:1.55;">'+t('mem.card.days.desc')+'</div></div>';
   document.getElementById('memoryOverview').innerHTML=overview;

   // 存全量事件，交给分页模块处理
   window._memAllEvents=events; // 后端已按时间降序排好
   _memCurrentPage=1;
   // 恢复之前的筛选状态
   var targetFilter=_savedMemFilter||'all';
   var chips=document.querySelectorAll('.mem-chip');
   var matched=null;
   chips.forEach(function(c){
    var oc=c.getAttribute('onclick')||'';
    if(oc.indexOf("'"+targetFilter+"'")!==-1) matched=c;
   });
   if(matched) setMemoryFilter(targetFilter, matched);
   else { currentMemoryFilter='all'; _memFilteredItems=window._memAllEvents; _memRenderPage(); }
   // fetch 完成后恢复滚动位置
   var ms=document.getElementById('memScroll');
   if(ms && window._memScrollTop) ms.scrollTop=window._memScrollTop;
  }).catch(function(){
   document.getElementById('memoryTimeline').innerHTML='<div style="color:#ef4444;">'+t('mem.load.fail')+'</div>';
  });
 }

 if(n==5){
  loadSettingsPage(isLight);
  return;
 }

 if(n==6){
  loadEntityPage(isLight);
  return;
 }
 if(n==7){
  loadLabPage(isLight);
  return;
 }
}

// ── 技能商店 ──
var _skillIcons={
 '\u5929\u6c14':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 2v2"/><path d="M12 20v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="M6.34 17.66l-1.41 1.41"/><path d="M19.07 4.93l-1.41 1.41"/><circle cx="12" cy="12" r="4"/></svg>',
 '\u80a1\u7968':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
 '\u65b0\u95fb':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2z"/><line x1="6" y1="8" x2="18" y2="8"/><line x1="6" y1="12" x2="14" y2="12"/><line x1="6" y1="16" x2="10" y2="16"/></svg>',
 '\u6587\u7ae0':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
 '\u6545\u4e8b':'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>',
 '\u753b\u56fe':'<svg viewBox="0 0 24 24" width="22" height="22"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
 '\u4ee3\u7801':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
 '\u7f16\u7a0b':'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>'
};
var _catIcons={
 '\u4fe1\u606f\u67e5\u8be2':'<svg viewBox="0 0 24 24" width="18" height="18"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
 '\u5185\u5bb9\u521b\u4f5c':'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="M2 2l7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>',
 '\u5f00\u53d1\u5de5\u5177':'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>'
};
var _cachedSkillsData=null;

function _loadSkillsList(){
 fetch('/skills').then(function(r){return r.json();}).then(function(d){
  _cachedSkillsData=d;
  if(!d||!d.skills){document.getElementById('skillsList').innerHTML='';return;}
  var filtered=d.skills.filter(function(s){return (s.source||'native')==='native';});
  _renderNativeSkills(filtered);
 }).catch(function(){
  document.getElementById('skillsList').innerHTML='<div style="color:#ef4444;">'+t('skills.load.fail')+'</div>';
 });
}

function _renderNativeSkills(skills){
 var catOrder=[t('skills.cat.info'),t('skills.cat.content'),t('skills.cat.dev')];
 var groups={};
 catOrder.forEach(function(c){groups[c]=[];});
 skills.forEach(function(s){
  var cat=s.category||'\u5f00\u53d1\u5de5\u5177';
  if(!groups[cat])groups[cat]=[];
  groups[cat].push(s);
 });
 var html='';
 catOrder.forEach(function(catName){
  var items=groups[catName];
  if(!items||items.length===0)return;
  var ci=_catIcons[catName]||'';
  html+='<div class="skill-category">';
  html+='<div class="skill-category-header">'+ci+'<span class="skill-category-name">'+catName+'</span></div>';
  html+='<div class="skill-grid">';
  items.forEach(function(s){html+=_buildSkillCard(s);});
  html+='</div></div>';
 });
 Object.keys(groups).forEach(function(cat){
  if(catOrder.indexOf(cat)===-1&&groups[cat].length>0){
   html+='<div class="skill-category"><div class="skill-category-header"><span class="skill-category-name">'+cat+'</span></div><div class="skill-grid">';
   groups[cat].forEach(function(s){html+=_buildSkillCard(s);});
   html+='</div></div>';
  }
 });
 if(!html) html='<div style="color:#94a3b8;padding:20px;">'+t('skills.empty')+'</div>';
 document.getElementById('skillsList').innerHTML=html;
}

function _buildSkillCard(s){
 var name=s.name||'';
 var id=s.id||'';
 var iconKey=Object.keys(_skillIcons).find(function(k){return name.indexOf(k)!==-1;});
 var icon=iconKey?_skillIcons[iconKey]:'<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
 var enabled=s.enabled!==false;
 var disabledCls=enabled?'':' disabled';
 var dotCls=enabled?'':'offline';
 var statusText=enabled?t('skills.status.ready'):t('skills.status.off');
 var html='<div class="skill-card'+disabledCls+'" id="skill-'+id+'">';
 html+='<div class="skill-card-icon">'+icon+'</div>';
 html+='<div class="skill-card-name">'+escapeHtml(name)+'</div>';
 html+='<div class="skill-card-desc">'+(s.description||t('skills.no.desc'))+'</div>';
 html+='<div class="skill-card-status"><span class="dot '+dotCls+'"></span>'+statusText+'</div>';
 html+='</div>';
 return html;
}

function _escHtml(s){
 if(!s) return '';
 return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ── 模型选择器 ──
function toggleModelDropdown(e){
 e.stopPropagation();
 var dd=document.getElementById('modelDropdown');
 if(!dd)return;
 if(dd.style.display!=='none'){dd.style.display='none';return;}
 var models=window._novaModels||{};
 var current=window._novaCurrentModel||'';
 var catalog=window._novaCatalog||null;
 var html='';
 if(catalog&&Object.keys(catalog).length>0){
  // 按厂商分组
  var grouped={};
  var uncategorized=[];
  Object.keys(models).forEach(function(mid){
   var m=models[mid];
   var midL=mid.toLowerCase();
   var mNameL=String((m||{}).model||'').toLowerCase();
   var mUrlL=String((m||{}).base_url||'').toLowerCase();
   var pkey=null;
   // 第一轮：按模型 ID / 模型名 / 别名匹配（优先级高）
   for(var pk in catalog){
    if(midL.indexOf(pk)!==-1||mNameL.indexOf(pk)!==-1){pkey=pk;break;}
    var aliases=catalog[pk].aliases||[];
    for(var i=0;i<aliases.length;i++){if(midL.indexOf(aliases[i])!==-1||mNameL.indexOf(aliases[i])!==-1){pkey=pk;break;}}
    if(pkey)break;
   }
   // 第二轮：按 base_url 匹配（兜底）
   if(!pkey){
    for(var pk2 in catalog){
     if(catalog[pk2].url_hint&&mUrlL.indexOf(catalog[pk2].url_hint)!==-1){pkey=pk2;break;}
    }
   }
   if(pkey){
    if(!grouped[pkey])grouped[pkey]=[];
    grouped[pkey].push(mid);
   }else{
    uncategorized.push(mid);
   }
  });
  var first=true;
  for(var pk in catalog){
   var items=grouped[pk];
   if(!items||items.length===0) continue;
   if(!first) html+='<div style="height:1px;background:rgba(128,128,128,0.15);margin:4px 0;"></div>';
   first=false;
   var label=pk.charAt(0).toUpperCase()+pk.slice(1);
   html+='<div style="padding:6px 12px 2px;font-size:10px;color:#64748b;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;user-select:none;pointer-events:none;">'+label+'</div>';
   items.forEach(function(mid){
    var m=models[mid];
    var displayName=m.model||mid;
    var active=mid===current?' active':'';
    var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
    html+='<div class="model-dropdown-item'+active+'" onclick="switchModel(\''+mid+'\')">'+displayName+vision+'</div>';
   });
  }
  if(uncategorized.length>0){
   if(!first) html+='<div style="height:1px;background:rgba(128,128,128,0.15);margin:4px 0;"></div>';
   html+='<div style="padding:6px 12px 2px;font-size:10px;color:#64748b;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;user-select:none;pointer-events:none;">Other</div>';
   uncategorized.forEach(function(mid){
    var m=models[mid];
    var displayName=m.model||mid;
    var active=mid===current?' active':'';
    var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
    html+='<div class="model-dropdown-item'+active+'" onclick="switchModel(\''+mid+'\')">'+displayName+vision+'</div>';
   });
  }
 }else{
  // fallback: 无 catalog 时扁平列表
  Object.keys(models).forEach(function(mid){
   var m=models[mid];
   var displayName=m.model||mid;
   var active=mid===current?' active':'';
   var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
   html+='<div class="model-dropdown-item'+active+'" onclick="switchModel(\''+mid+'\')">'+displayName+vision+'</div>';
  });
 }
 dd.innerHTML=html;
 dd.style.display='block';
 // 点击其他地方关闭
 setTimeout(function(){
  document.addEventListener('click',_closeModelDropdown,{once:true});
 },0);
}
function _closeModelDropdown(){
 var dd=document.getElementById('modelDropdown');
 if(dd) dd.style.display='none';
}
function switchModel(mid){
 // 即时关闭 dropdown
 var dd=document.getElementById('modelDropdown');
 if(dd) dd.style.display='none';
 if(mid===window._novaCurrentModel) return;
 // 即时更新侧边栏显示
 window._novaCurrentModel=mid;
 var el=document.getElementById('modelName');
 var _m=(window._novaModels||{})[mid];
 if(el) el.textContent=(_m&&_m.model)?_m.model:mid;
 // 如果在设置页，即时高亮
 var items=document.querySelectorAll('[onclick*="switchModel"]');
 items.forEach(function(it){it.style.pointerEvents='none';it.style.opacity='0.5';});
 var clicked=null;
 items.forEach(function(it){if(it.getAttribute('onclick')&&it.getAttribute('onclick').indexOf(mid)!==-1){clicked=it;}});
 if(clicked){clicked.style.opacity='1';clicked.style.outline='2px solid #60a5fa';clicked.style.outlineOffset='-2px';}
 fetch('/model/'+encodeURIComponent(mid),{method:'POST'}).then(r=>r.json()).then(function(d){
  if(d.ok){
   if(typeof updateImageBtnState==='function') updateImageBtnState();
   if(typeof _settingsCurrentModel!=='undefined'){
    _settingsCurrentModel=mid;
    setTimeout(function(){if(typeof loadSettingsModels==='function') loadSettingsModels();},300);
   }
  }else{
   // 回滚
   items.forEach(function(it){it.style.pointerEvents='';it.style.opacity='';it.style.outline='';});
  }
 }).catch(function(){
  items.forEach(function(it){it.style.pointerEvents='';it.style.opacity='';it.style.outline='';});
 });
}
function updateImageBtnState(){
 var btn=document.getElementById('imageUploadBtn');
 if(!btn)return;
 var models=window._novaModels||{};
 var current=window._novaCurrentModel||'';
 // 只要有任何一个模型支持 vision 就启用（会自动 fallback）
 var anyVision=Object.keys(models).some(function(k){return models[k].vision;});
 btn.disabled=!anyVision;
 btn.title=anyVision?t('model.upload.title'):t('model.no.vision');
}

function loadStatsData(){
  var box=document.getElementById('statsBox');
  if(!box) return;
  var btn=document.querySelector('.stats-refresh-btn');
  if(btn) btn.classList.add('spinning');
  fetch('/stats').then(function(r){return r.json()}).then(function(d){
    var s=d.stats||d||{};
    box.innerHTML=renderStats(s);
    if(btn) btn.classList.remove('spinning');
  }).catch(function(){
    box.innerHTML='<div style="color:#ef4444;">'+t('dash.load.fail')+'</div>';
    if(btn) btn.classList.remove('spinning');
  });
}
