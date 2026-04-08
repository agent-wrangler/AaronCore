// Primary tab switching and page-level view rendering
// Source: app.js lines 938-1094

function show(n){
 var chat = document.getElementById('chat');
 window._currentTab=n;
 try{
  _closeSkillModal(true);
 }catch(e){
  console.warn('[AaronCore] close skill modal failed', e);
 }
 for(var i=1;i<=6;i++){
  var menu=document.getElementById('m'+i);
  if(menu) menu.classList.remove('active');
 }
 var activeMenu=document.getElementById('m'+n);
 if(activeMenu) activeMenu.classList.add('active');
  if(typeof window._setRunPanelTabState==='function'){
   window._setRunPanelTabState(n===1);
  }
  var isLight = document.body.classList.contains('light');

 if(n==1){
  if(typeof window._beginChatViewRestore==='function'){
   window._beginChatViewRestore(900);
  }
  setInputVisible(true);
  if(!chatHistory || chatHistory.trim()===''){
   if(typeof getStoredChatHistorySnapshot==='function'){
    chatHistory=(getStoredChatHistorySnapshot({
     preferSession:true,
     recentTurns:CHAT_HISTORY_BOOT_TURNS
    })||{}).html||'';
   }else{
    try{
     chatHistory=localStorage.getItem('aaroncore_chat_history')||localStorage.getItem('nova_chat_history')||'';
    }catch(e){
     chatHistory='';
    }
   }
  }
  if(typeof window._looksLikeChatSnapshot==='function' && window._looksLikeChatSnapshot(chatHistory)){
   chat.innerHTML=chatHistory;
   var currentTurnCount=(typeof window._countRenderedHistoryTurns==='function')
    ?window._countRenderedHistoryTurns(chat)
    :chat.querySelectorAll('.msg.user, .msg.assistant:not(.process-msg):not(.reply-part-msg):not(.thinking-msg):not(.thinking-trace-msg)').length;
   if(currentTurnCount<window._historyOffset){
    window._historyOffset=currentTurnCount;
    window._historyHasMore=true;
   }
   if(typeof window._rebindStepToggles==='function'){
    window._rebindStepToggles(chat);
   }
   if(!(typeof window._restoreChatScroll==='function' && window._restoreChatScroll())){
    if(typeof window._schedulePinChatToBottom==='function'){
     window._schedulePinChatToBottom();
    }
   }
   if(typeof window._flushPendingModelSwitchNote==='function'){
    setTimeout(function(){
     if(window._currentTab===1) window._flushPendingModelSwitchNote();
    },0);
   }
  } else {
   if(typeof window._reloadChatFromServer==='function'){
    window._reloadChatFromServer(true);
   }
  }
 }

 if(n==2){
  setInputVisible(false);
  _skillsSearchQuery='';
  try{
   _closeSkillModal(true);
  }catch(e){
   console.warn('[AaronCore] close skill modal failed on skills tab', e);
  }
  chat.innerHTML='<div class="skill-store"><div class="skill-store-head"><div class="skill-store-hero"><div class="page-title">'+t('skills.title')+'</div><div class="skill-store-subtitle">'+t('skills.subtitle')+'</div></div><div class="skill-store-toolbar" id="skillsToolbar"></div></div><div class="skill-tabs" id="skillsViewTabs"></div><div id="skillsList">'+t('loading')+'</div></div>';
  try{
   _renderSkillsToolbar();
  }catch(e){
   console.warn('[AaronCore] render skills toolbar failed', e);
  }
  try{
   _loadSkillsList();
  }catch(e){
   console.warn('[AaronCore] load skills list failed', e);
  }
 }

 if(n==3){
  setInputVisible(false);
  chat.innerHTML='<div class="stats-page"><div id="statsBox">'+t('loading')+'</div></div>';
  try{
   loadStatsData();
  }catch(e){
   console.warn('[AaronCore] load stats failed', e);
  }
 }

 if(n==4){
  setInputVisible(false);
  var _savedMemFilter=currentMemoryFilter||'all';
  chat.innerHTML='<div id="memScroll"><div id="memoryOverview" style="display:grid;grid-template-columns:'+memoryOverviewColumns()+';gap:12px;margin-bottom:18px;"></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;" id="memoryChips"><button class="mem-chip" onclick="setMemoryFilter(\'all\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-primary);cursor:pointer;">'+t('mem.filter.all')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L2\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L2')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L3\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L3')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L4\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L4')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L5\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L5')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L6\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L6')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L7\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L7')+'</button><button class="mem-chip" onclick="setMemoryFilter(\'L8\',this)" style="padding:8px 14px;border-radius:999px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-chip);cursor:pointer;">'+t('mem.filter.L8')+'</button></div><div style="margin-bottom:18px;"><input id="memorySearch" type="text" placeholder="'+t('mem.search')+'" style="width:100%;padding:12px 16px;border-radius:12px;border:1px solid var(--border-input);background:var(--bg-input);color:var(--text-primary);outline:none;" onkeyup="filterMemBySearch(this.value)"></div><div id="memoryTimeline" style="display:flex;flex-direction:column;gap:10px;">'+t('loading')+'</div></div>';
  fetch('/memory').then(r=>r.json()).then(function(d){
   var softBg='var(--surface-panel)';
   var textColor='var(--text-primary)';
   var labelColor='var(--text-label)';
   var borderColor='var(--border-panel)';
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
   var overviewCardBg='var(--bg-growth)';
   var overviewCardBorder='var(--border-tag-pill)';
   var overview='';
   overview+='<div style="background:'+overviewCardBg+';border:1px solid '+overviewCardBorder+';padding:18px;border-radius:18px;display:flex;flex-direction:column;gap:12px;">';
   overview+='<div style="display:flex;align-items:center;gap:6px;"><span style="font-size:11px;color:'+labelColor+';letter-spacing:0.2px;">'+t('mem.growth.level')+'</span><span class="mem-help-trigger" style="position:relative;display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;border:1px solid '+labelColor+';color:'+labelColor+';font-size:10px;font-weight:600;cursor:help;" onmouseenter="this.querySelector(\'.mem-help-tip\').style.display=\'block\'" onmouseleave="this.querySelector(\'.mem-help-tip\').style.display=\'none\'">?<div class="mem-help-tip" style="display:none;position:absolute;left:22px;top:-8px;width:260px;padding:12px;border-radius:10px;background:'+overviewCardBg+';border:1px solid '+overviewCardBorder+';font-size:11px;color:var(--text-secondary);line-height:1.7;z-index:99;box-shadow:var(--shadow-card);font-weight:400;cursor:default;" onmouseenter="this.style.display=\'block\'" onmouseleave="this.style.display=\'none\'">'+t('mem.desc')+'</div></span></div><div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;"><div style="min-width:0;"><div style="display:inline-flex;align-items:baseline;gap:8px;white-space:nowrap;font-size:24px;font-weight:700;color:'+textColor+';margin-bottom:2px;">Lv.'+level+' <span style="font-size:15px;font-weight:600;color:var(--text-secondary);white-space:nowrap;">'+stage+'</span></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;"><span style="padding:6px 10px;border-radius:999px;background:rgba(255,255,255,0.46);border:1px solid var(--border-tag-pill);font-size:11px;color:var(--text-secondary);">'+t('mem.growth.totalExp')+' '+formatGrowthNumber(totalExp)+'</span><span style="padding:6px 10px;border-radius:999px;background:rgba(255,255,255,0.46);border:1px solid var(--border-tag-pill);font-size:11px;color:var(--text-secondary);">'+t('mem.growth.currentLevel')+' '+formatGrowthNumber(growth.currentExp)+'/'+formatGrowthNumber(growth.nextNeed)+'</span></div></div><div style="padding:7px 12px;border-radius:999px;background:rgba(255,255,255,0.52);border:1px solid var(--border-badge);font-size:11px;font-weight:600;color:var(--text-badge);white-space:nowrap;">'+t('mem.growth.needMore')+' '+formatGrowthNumber(growth.remainingExp)+' EXP</div></div><div style="margin-top:2px;height:10px;background:var(--bar-track);border-radius:999px;overflow:hidden;"><div style="height:100%;width:'+progress+'%;background:var(--bar-fill);border-radius:999px;"></div></div></div>';
   overview+='<div style="background:'+overviewCardBg+';border:1px solid '+overviewCardBorder+';padding:14px 14px 13px;border-radius:16px;min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;letter-spacing:0.2px;">'+t('mem.card.L1.title')+'</div><div style="font-size:20px;font-weight:700;color:'+textColor+';line-height:1.05;">'+counts.L1+'</div><div style="font-size:11px;color:var(--text-secondary);margin-top:8px;line-height:1.6;">'+t('mem.card.L1.desc')+'</div></div>';
   overview+='<div style="background:'+overviewCardBg+';border:1px solid '+overviewCardBorder+';padding:14px 14px 13px;border-radius:16px;min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;letter-spacing:0.2px;">'+t('mem.card.L3.title')+'</div><div style="font-size:20px;font-weight:700;color:'+textColor+';line-height:1.05;">'+counts.L3+'</div><div style="font-size:11px;color:var(--text-secondary);margin-top:8px;line-height:1.6;">'+t('mem.card.L3.desc')+'</div></div>';
   overview+='<div style="background:'+overviewCardBg+';border:1px solid '+overviewCardBorder+';padding:14px 14px 13px;border-radius:16px;min-width:0;"><div style="font-size:11px;color:'+labelColor+';margin-bottom:8px;letter-spacing:0.2px;">'+t('mem.card.days.title')+'</div><div style="font-size:20px;font-weight:700;color:'+textColor+';line-height:1.05;">'+days+'</div><div style="font-size:11px;color:var(--text-secondary);margin-top:8px;line-height:1.6;">'+t('mem.card.days.desc')+'</div></div>';
   document.getElementById('memoryOverview').innerHTML=overview;

   // 瀛樺叏閲忎簨浠讹紝浜ょ粰鍒嗛〉妯″潡澶勭悊
   window._memAllEvents=events; // 鍚庣宸叉寜鏃堕棿闄嶅簭鎺掑ソ
   _memCurrentPage=1;
   // 鎭㈠涔嬪墠鐨勭瓫閫夌姸鎬?
   var targetFilter=_savedMemFilter||'all';
   var chips=document.querySelectorAll('.mem-chip');
   var matched=null;
   chips.forEach(function(c){
    var oc=c.getAttribute('onclick')||'';
    if(oc.indexOf("'"+targetFilter+"'")!==-1) matched=c;
   });
   if(matched) setMemoryFilter(targetFilter, matched);
   else { currentMemoryFilter='all'; _memFilteredItems=window._memAllEvents; _memRenderPage(); }
   // fetch 瀹屾垚鍚庢仮澶嶆粴鍔ㄤ綅缃?
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
  loadLabPage(isLight);
  return;
 }
}


