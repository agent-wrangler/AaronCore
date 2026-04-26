// Window boot flow, chat restore, and initial runtime wiring
// Source: app.js lines 158-936

window.onload=function(){
 window._currentTab=1; // 默认聊天 tab
 initSidebarResize();
 hideWelcome();
 (function(){
  var scrollingTimers=new WeakMap();
  function markScrolling(el){
   if(!el || !el.classList) return;
   el.classList.add('is-scrolling');
   var oldTimer=scrollingTimers.get(el);
   if(oldTimer) clearTimeout(oldTimer);
   var nextTimer=setTimeout(function(){
    el.classList.remove('is-scrolling');
    scrollingTimers.delete(el);
   },720);
   scrollingTimers.set(el,nextTimer);
  }
  function resolveScrollableTarget(target){
   var el=target && target.nodeType===1 ? target : null;
   if(!el) return null;
   if(el.matches && el.matches('.chat, .run-panel-stream, .input textarea, .task-plan-list, .settings-page-host')) return el;
   if(el.closest){
    return el.closest('.chat, .run-panel-stream, .input textarea, .task-plan-list, .settings-page-host');
   }
   return null;
  }
  document.addEventListener('scroll',function(e){
   var target=e.target===document ? (document.scrollingElement||document.documentElement) : e.target;
   markScrolling(resolveScrollableTarget(target) || target);
  },true);
  document.addEventListener('wheel',function(e){
   var target=resolveScrollableTarget(e.target);
   if(target) markScrolling(target);
  },{capture:true,passive:true});
 })();
 // 输入框右键菜单（浏览器环境下提供一致的编辑菜单）
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
var savedTheme=_applyTheme(
 localStorage.getItem('nova_theme') || localStorage.getItem('novaTheme') || 'light',
 {deferTitlebar:true}
);
 // 主题初始化后再同步一次页面外壳颜色
 setTimeout(function(){
  _syncTitleBar(savedTheme);
 },800);

 // 从后端加载聊天历史
 window._historyOffset=0;
 window._historyHasMore=false;
 window._historyLoading=false;
 var _chatViewRestoring=false;
 var _chatViewRestoreTimer=0;
 var _chatScrollSnapshot=null;

 function _countRenderedHistoryTurns(container){
  var host=container||document.getElementById('chat');
  if(!host) return 0;
  return host.querySelectorAll('.msg.user, .msg.assistant:not(.process-msg):not(.reply-part-msg):not(.thinking-msg):not(.thinking-trace-msg)').length;
 }

 function _snapshotChatScroll(){
  var chat=document.getElementById('chat');
  if(!chat) return;
  var maxTop=Math.max(chat.scrollHeight-chat.clientHeight,0);
  var top=Math.max(0,Math.min(chat.scrollTop,maxTop));
  var fromBottom=Math.max(0,maxTop-top);
  _chatScrollSnapshot={
   hasValue:true,
   top:top,
   fromBottom:fromBottom,
   atBottom:fromBottom<=24
  };
 }

 function _restoreChatScroll(){
  var chat=document.getElementById('chat');
  if(!chat||!_chatScrollSnapshot||!_chatScrollSnapshot.hasValue) return false;
  var apply=function(){
   var maxTop=Math.max(chat.scrollHeight-chat.clientHeight,0);
   var targetTop=_chatScrollSnapshot.atBottom ? maxTop : Math.max(0,maxTop-_chatScrollSnapshot.fromBottom);
   chat.style.scrollBehavior='auto';
   chat.scrollTop=targetTop;
  };
  apply();
  requestAnimationFrame(function(){
   apply();
   requestAnimationFrame(function(){
    apply();
    chat.style.scrollBehavior='';
   });
  });
  setTimeout(function(){
   apply();
   chat.style.scrollBehavior='';
  },48);
  return true;
 }

var _chatBottomLockRaf=0;
var _chatBottomLockUntil=0;
var _chatBottomLockStopTimer=0;
var _chatBottomResizeObserver=null;
var _chatAutoStickToBottom=true;

 function _chatAwayFromBottom(chat){
  var host=chat||document.getElementById('chat');
  if(!host) return 0;
  return Math.max(host.scrollHeight-host.scrollTop-host.clientHeight, 0);
 }

 function _isChatNearBottom(threshold){
  return _chatAwayFromBottom() <= Math.max(0, Number(threshold)||150);
 }

 function _pinChatToBottom(){
  var chat=document.getElementById('chat');
  if(!chat) return;
  var settle=function(){
   chat.style.scrollBehavior='auto';
   chat.scrollTop=chat.scrollHeight;
  };
  settle();
  requestAnimationFrame(function(){
   settle();
   requestAnimationFrame(function(){
    settle();
    chat.style.scrollBehavior='';
   });
  });
  setTimeout(function(){
   settle();
   chat.style.scrollBehavior='';
  }, 48);
 }

 function _setChatAutoStick(enabled){
  _chatAutoStickToBottom = enabled!==false;
 }

 function _maybePinChatToBottom(options){
  var chat=document.getElementById('chat');
  if(!chat) return false;
  options=options||{};
  var force=!!options.force;
  var lockMs=Math.max(0, Number(options.lock_ms)||0);
  var threshold=Math.max(0, Number(options.threshold)||150);
  if(!force && !_chatAutoStickToBottom && _chatAwayFromBottom(chat)>threshold && Date.now()>=_chatBottomLockUntil){
   return false;
  }
  _chatAutoStickToBottom=true;
  _pinChatToBottom();
  if(force || lockMs>0){
   _lockChatToBottom(lockMs||900);
  }
  return true;
 }

 function _beginChatViewRestore(durationMs){
  _chatViewRestoring=true;
  if(_chatViewRestoreTimer){
   clearTimeout(_chatViewRestoreTimer);
  }
  _chatViewRestoreTimer=setTimeout(function(){
   _chatViewRestoring=false;
   _chatViewRestoreTimer=0;
  }, durationMs||900);
 }

 function _stopChatBottomLock(){
  if(_chatBottomLockRaf){
   cancelAnimationFrame(_chatBottomLockRaf);
   _chatBottomLockRaf=0;
  }
  if(_chatBottomLockStopTimer){
   clearTimeout(_chatBottomLockStopTimer);
   _chatBottomLockStopTimer=0;
  }
  if(_chatBottomResizeObserver){
   try{ _chatBottomResizeObserver.disconnect(); }catch(e){}
   _chatBottomResizeObserver=null;
  }
  _chatBottomLockUntil=0;
 }

 function _lockChatToBottom(durationMs){
  _stopChatBottomLock();
  _chatBottomLockUntil=Date.now()+(durationMs||900);
  if(typeof ResizeObserver==='function'){
   var chat=document.getElementById('chat');
   var inputArea=document.querySelector('.input');
   _chatBottomResizeObserver=new ResizeObserver(function(){
    if(window._currentTab!==1) return;
    _pinChatToBottom();
   });
   if(chat) _chatBottomResizeObserver.observe(chat);
   if(inputArea) _chatBottomResizeObserver.observe(inputArea);
   _chatBottomLockStopTimer=setTimeout(function(){
    if(_chatBottomResizeObserver){
     try{ _chatBottomResizeObserver.disconnect(); }catch(e){}
     _chatBottomResizeObserver=null;
    }
    _chatBottomLockStopTimer=0;
   }, durationMs||900);
  }
  var tick=function(){
   var chat=document.getElementById('chat');
   if(!chat || window._currentTab!==1){
    _stopChatBottomLock();
    return;
   }
   chat.style.scrollBehavior='auto';
   chat.scrollTop=chat.scrollHeight;
   if(Date.now()>=_chatBottomLockUntil){
    chat.style.scrollBehavior='';
    _chatBottomLockRaf=0;
    return;
   }
   _chatBottomLockRaf=requestAnimationFrame(tick);
  };
  tick();
 }

 function _schedulePinChatToBottom(){
  _maybePinChatToBottom({force:true, lock_ms:900});
 }

 function _restoreTimelineSnapshot(){
  var chat=document.getElementById('chat');
  if(!chat) return false;
  var snapshot='';
  if(typeof getStoredChatHistorySnapshot==='function'){
   snapshot=(getStoredChatHistorySnapshot({
    preferSession:true,
    recentTurns:CHAT_HISTORY_BOOT_TURNS
   })||{}).html||'';
  }else{
   try{
    snapshot=localStorage.getItem('nova_chat_history')||'';
   }catch(e){
    snapshot='';
   }
  }
  if(!snapshot.trim()) return false;
  chat.innerHTML=snapshot;
  chatHistory=snapshot;
  if(typeof window._rebindChatImagePreviews==='function'){
   window._rebindChatImagePreviews(chat);
  }
  _schedulePinChatToBottom();
  return true;
 }

 function _looksLikeChatSnapshot(html){
  var text=String(html||'').trim();
  if(!text) return false;
  if(/class="skill-store"|class="stats-page"|id="memScroll"|class="runtime-graph-page"|class="settings-page"/.test(text)) return false;
  return /class="msg\b|class="welcome\b|thinking-msg|process-msg|reply-part-msg/.test(text);
 }

 function _restoreChatFromSnapshot(chat, keepScroll){
  var host=chat||document.getElementById('chat');
  if(!host) return false;
  var snapshot='';
  var currentHtml=String(host.innerHTML||'');
  if(_looksLikeChatSnapshot(currentHtml)){
   snapshot=currentHtml;
  }else if(_looksLikeChatSnapshot(chatHistory)){
   snapshot=chatHistory;
  }else{
   var stored='';
   if(typeof getStoredChatHistorySnapshot==='function'){
    stored=(getStoredChatHistorySnapshot({
     preferSession:true,
     recentTurns:CHAT_HISTORY_BOOT_TURNS
    })||{}).html||'';
   }else{
    try{
     stored=localStorage.getItem('aaroncore_chat_history')
      || localStorage.getItem('nova_chat_history')
      || '';
    }catch(e){
     stored='';
    }
   }
   if(_looksLikeChatSnapshot(stored)) snapshot=stored;
  }
  if(!snapshot.trim()) return false;
  host.innerHTML=snapshot;
  chatHistory=snapshot;
  if(typeof window._rebindChatImagePreviews==='function'){
   window._rebindChatImagePreviews(host);
  }
  if(typeof window._rebindStepToggles==='function'){
   window._rebindStepToggles(host);
  }
  if(!(keepScroll&&_restoreChatScroll())){
   _schedulePinChatToBottom();
  }
  return true;
 }

 function _reloadChatFromServer(keepScroll){
  var chat=document.getElementById('chat');
  if(!chat) return;
  fetch('/history?limit='+CHAT_HISTORY_BOOT_TURNS+'&offset=0').then(function(r){return r.json()}).then(function(d){
   if(window._currentTab!==1&&window._currentTab!==undefined) return;
   var items=d.history||[];
   window._historyHasMore=d.has_more||false;
   window._historyOffset=items.length;
   if(typeof window._clearSessionTaskPlan==='function'){
    window._clearSessionTaskPlan();
   }
   if(items.length){
   chat.innerHTML=window._renderHistoryItems(items);
   chatHistory=chat.innerHTML;
   if(typeof persistChatHistorySnapshot==='function'){
     persistChatHistorySnapshot();
   }
   if(typeof window._rebindChatImagePreviews==='function'){
    window._rebindChatImagePreviews(chat);
   }
   if(typeof window._rebindStepToggles==='function'){
     window._rebindStepToggles(chat);
   }
    if(!(keepScroll&&_restoreChatScroll())){
     _schedulePinChatToBottom();
    }
    if(typeof window._flushPendingModelSwitchNote==='function'){
     setTimeout(function(){
      if(window._currentTab===1) window._flushPendingModelSwitchNote();
     },0);
    }
    return;
   }
   if(!_restoreChatFromSnapshot(chat, keepScroll)){
    chat.innerHTML='';
    chatHistory='';
    if(typeof persistChatHistorySnapshot==='function'){
     persistChatHistorySnapshot();
    }
   }
   if(typeof window._flushPendingModelSwitchNote==='function'){
    setTimeout(function(){
     if(window._currentTab===1) window._flushPendingModelSwitchNote();
    },0);
   }
  }).catch(function(e){
   console.warn('[Nova] reload chat from server failed', e);
  });
 }

 window._countRenderedHistoryTurns=_countRenderedHistoryTurns;
 window._snapshotChatScroll=_snapshotChatScroll;
 window._restoreChatScroll=_restoreChatScroll;
 window._beginChatViewRestore=_beginChatViewRestore;
window._stopChatBottomLock=_stopChatBottomLock;
window._schedulePinChatToBottom=_schedulePinChatToBottom;
window._maybePinChatToBottom=_maybePinChatToBottom;
window._setChatAutoStick=_setChatAutoStick;
window._isChatNearBottom=_isChatNearBottom;
window._looksLikeChatSnapshot=_looksLikeChatSnapshot;
window._reloadChatFromServer=_reloadChatFromServer;

 var _restoredTimelineSnapshot=_restoreTimelineSnapshot();

window._renderHistoryItems=function(items){
 var shouldRenderTaskPlanInChat=typeof window._isTaskPlanBoardEnabled==='function'
  ? window._isTaskPlanBoardEnabled()
  : true;
 function _processMarkerText(label, status){
   var text=String(label||'');
   if(status==='error') return '!';
   if(/思考|thinking/i.test(text)) return '·';
   if(/计划|plan/i.test(text)) return '⌁';
    return '·';
   }

  function _looksLikeMemoryLoadLabel(label){
    return /^(?:记忆加载(?:完成)?|memory_load|load_memory)$/i.test(String(label||'').trim());
   }

  function _formatProcessDisplayLabel(label){
    var text=String(label||'').trim();
    if(!text) return text;
    return /^[a-z]/.test(text) ? (text.charAt(0).toUpperCase()+text.slice(1)) : text;
   }

  function _escapeRegExp(text){
    return String(text||'').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
   }

  function _stripProcessDetailPrefix(detail, label){
    var text=String(detail||'').trim();
    var head=String(label||'').trim();
    if(!text || !head) return text;
    var pattern=new RegExp('^'+_escapeRegExp(head)+'(?:\\s*[·•:：-]\\s*)?', 'i');
    return text.replace(pattern, '').trim();
   }

  function _cleanProcessDetail(detail, rawLabel, displayLabel, status){
    var text=String(detail||'').replace(/\s+/g,' ').trim();
    if(!text) return '';
    text=_stripProcessDetailPrefix(text, displayLabel);
    text=_stripProcessDetailPrefix(text, rawLabel);
    text=text.replace(/(?:\s*[·•]\s*)?(?:执行中|输出中|处理中)\s*(\d+s)\s*$/i, ' $1').trim();
    text=text.replace(/\s*[·•:：-]+\s*$/g,'').trim();
    if(!text) return '';
    var lower=text.toLowerCase();
    var rawLower=String(rawLabel||'').trim().toLowerCase();
    var displayLower=String(displayLabel||'').trim().toLowerCase();
    if((rawLower && lower===rawLower) || (displayLower && lower===displayLower)) return '';
    return text;
   }

  function _splitProcessWaitSuffix(detail){
    var text=String(detail||'').trim();
    if(!text) return {text:'', wait:''};
    var match=text.match(/^(.*?)(?:\s*[\u00b7\u2022]\s*)?(\d+s)\s*$/i);
    if(!match) return {text:text, wait:''};
    return {
      text:String(match[1]||'').replace(/\s*[\u00b7\u2022:：-]+\s*$/g,'').trim(),
      wait:String(match[2]||'').trim()
    };
   }

  function _stepMetaText(value){
    return String(value||'').replace(/\s+/g,' ').trim();
   }

  function _stepMetaContains(base, sample){
    var left=_stepMetaText(base).toLowerCase();
    var right=_stepMetaText(sample).toLowerCase();
    if(!left || !right) return false;
    return left.indexOf(right)!==-1 || right.indexOf(left)!==-1;
   }

  function _appendUniqueStepMeta(parts, text, prefix){
    var value=_stepMetaText(text);
    if(!value) return;
    if(prefix && value.indexOf(prefix)!==0) value=prefix+value;
    for(var i=0;i<parts.length;i++){
      if(_stepMetaContains(parts[i], value)) return;
    }
    parts.push(value);
   }

  function _joinStepMeta(parts){
    return parts.join(' ').trim();
   }

  function _buildThinkingProcessDetail(step, fallbackSummary, fallbackFull){
    var summaryParts=[];
    var fullParts=[];
    var lead=_stepMetaText((step&&step.decision_note)||'') || _stepMetaText((step&&step.handoff_note)||'') || _stepMetaText(fallbackSummary) || _stepMetaText(fallbackFull);
    var goal=_stepMetaText(step&&step.goal);
    var expected=_stepMetaText(step&&step.expected_output);
    var nextNeed=_stepMetaText(step&&step.next_user_need);
    _appendUniqueStepMeta(summaryParts, lead, '');
    _appendUniqueStepMeta(fullParts, lead, '');
    if(goal){
      _appendUniqueStepMeta(summaryParts, goal, '先确认：');
      _appendUniqueStepMeta(fullParts, goal, '先确认：');
    }
    if(expected){
      _appendUniqueStepMeta(fullParts, expected, '预期产出：');
    }
    if(nextNeed){
      _appendUniqueStepMeta(fullParts, nextNeed, '下一步可能会关心：');
    }
    return {
      summary:_joinStepMeta(summaryParts) || _stepMetaText(fallbackSummary) || _stepMetaText(fallbackFull),
      full:_joinStepMeta(fullParts) || _stepMetaText(fallbackFull) || _stepMetaText(fallbackSummary)
    };
   }

  function _buildToolProcessDetail(step, fallbackSummary, fallbackFull, state){
    var summaryParts=[];
    var fullParts=[];
    var lead=_stepMetaText(fallbackSummary) || _stepMetaText(fallbackFull) || _stepMetaText(step&&step.goal) || _stepMetaText(step&&step.handoff_note) || _stepMetaText(step&&step.expected_output);
    var goal=_stepMetaText(step&&step.goal);
    var expected=_stepMetaText(step&&step.expected_output);
    _appendUniqueStepMeta(summaryParts, lead, '');
    _appendUniqueStepMeta(fullParts, lead, '');
    if(String(state||'')==='running' && goal){
      _appendUniqueStepMeta(fullParts, goal, '目标：');
    }
    if(String(state||'')==='running' && expected){
      _appendUniqueStepMeta(fullParts, expected, '预期：');
    }
    return {
      summary:_joinStepMeta(summaryParts) || _stepMetaText(fallbackSummary) || _stepMetaText(fallbackFull),
      full:_joinStepMeta(fullParts) || _stepMetaText(fallbackFull) || _stepMetaText(fallbackSummary)
    };
   }

  function _buildStructuredProcessDetail(step, phase, state, fallbackSummary, fallbackFull){
    if(phase==='thinking') return _buildThinkingProcessDetail(step, fallbackSummary, fallbackFull);
    if(phase==='tool') return _buildToolProcessDetail(step, fallbackSummary, fallbackFull, state);
    return {
      summary:_stepMetaText(fallbackSummary),
      full:_stepMetaText(fallbackFull) || _stepMetaText(fallbackSummary)
    };
   }

  function _renderProcessDetailMarkup(detail){
    return escapeHtml(String(detail||'').trim());
   }

  function _processLabelAlias(rawLabel){
    var text=String(rawLabel||'').trim();
    if(!text) return null;
    var aliases={
      '记忆加载':'memory_load',
      '记忆加载完成':'memory_load',
      '人格切换':'persona_switch',
      '切换模型':'model_switch',
      '整理结果':'organize_results',
      '组织回复':'compose_reply',
      '回忆对话':'recall_memory',
      '等待':'waiting'
    };
    return aliases[text]||null;
   }

  function _toolLabelFallback(rawLabel){
    var text=String(rawLabel||'').trim();
    if(!text) return '';
    if(text==='联网搜索' || text==='搜索完成' || text==='搜索失败') return 'web_search';
    if(text==='检索记忆' || text==='检索失败' || text==='记忆就绪') return 'recall_memory';
    if(text==='调用技能' || text==='技能完成' || text==='技能失败') return 'tool';
    return '';
   }

  function _extractToolKey(detail){
    var text=String(detail||'').trim();
    if(!text) return '';
    var parts=text.split(/\s*[\u00b7\u2022]\s*/);
    var head=String(parts[0]||'').trim();
    if(!head && parts.length>1) head=String(parts[1]||'').trim();
    return head.toLowerCase();
   }

  function _extractToolDetail(detail){
    var text=String(detail||'').trim();
    if(!text) return '';
    var parts=text.split(/\s*[\u00b7\u2022]\s*/);
    if(parts.length<=1) return text;
    return String(parts.slice(1).join(' · ')).trim();
   }

  function _simplifyToolDetail(detail, toolKey, status){
    var text=String(detail||'').trim();
    var key=String(toolKey||'').trim();
    var state=String(status||'').trim();
    if(!text) return '';
    if(key){
      text=text.replace(new RegExp('^正在执行\\s+'+_escapeRegExp(key)+'(?:\\.\\.\\.)?$', 'i'), '').trim();
      text=text.replace(new RegExp('^'+_escapeRegExp(key)+'\\s*$', 'i'), '').trim();
    }
    if(state==='running'){
      text=text.replace(/^正在执行(?:中)?(?:\\.\\.\\.)?$/i, '').trim();
    }
    return text;
   }

  function _displayProcessLabel(step){
    var rawLabel=String((step&&step.label)||'').trim();
    if(/思考|thinking/i.test(rawLabel)) return 'Thinking';
    if(_looksLikeMemoryLoadLabel(rawLabel)) return 'Memory_load';
    var toolFallback=_toolLabelFallback(rawLabel);
    if(toolFallback){
      var explicitTool=String((step&&step.tool_name)||'').trim();
      if(explicitTool) return _formatProcessDisplayLabel(explicitTool);
      var detail=String((step&&((step.full_detail&&String(step.full_detail).trim())||step.detail))||'').trim();
      return _formatProcessDisplayLabel(_extractToolKey(detail)||toolFallback||'tool');
    }
    var alias=_processLabelAlias(rawLabel);
    if(alias) return _formatProcessDisplayLabel(alias);
    return _formatProcessDisplayLabel(rawLabel);
   }

  function _renderProcessMarker(step, state){
    if(state==='running'){
      return '<span class="process-marker is-running" aria-hidden="true"><span></span><span></span><span></span></span>';
    }
    return '<span class="process-marker">'+escapeHtml(_processMarkerText(step&&step.label, state))+'</span>';
   }

  function _renderProcessMessage(step){
    var displayLabel=_displayProcessLabel(step);
    var label=escapeHtml(displayLabel);
    var rawStatus=String((step&&step.status)||'done');
    var state=(rawStatus==='error'?'error':(rawStatus==='running'?'running':'done'));
    var rawLabel=String((step&&step.label)||'').trim();
    var detailRaw=String((step&&((step.full_detail&&String(step.full_detail).trim())||step.detail))||'');
    var toolFallback=_toolLabelFallback(rawLabel);
    var phase=String((step&&step.phase)||'').trim();
    if(!phase){
      if(/思考|thinking/i.test(rawLabel)) phase='thinking';
      else if(toolFallback) phase='tool';
      else if(/等待|waiting/i.test(rawLabel)) phase='waiting';
      else phase='info';
    }
    if(toolFallback){
      var toolKey=String((step&&step.tool_name)||'').trim() || _extractToolKey(detailRaw)||toolFallback;
      detailRaw=_extractToolDetail(detailRaw)||detailRaw;
      detailRaw=_simplifyToolDetail(detailRaw, toolKey, state);
    }
    var structuredDetail=_buildStructuredProcessDetail(step, phase, state, detailRaw, detailRaw);
    detailRaw=String((structuredDetail&&structuredDetail.full)||detailRaw||'');
    detailRaw=_cleanProcessDetail(detailRaw, rawLabel, displayLabel, state);
    var detailMarkup=_renderProcessDetailMarkup(detailRaw);
    var marker=_renderProcessMarker(step, state);
    var html='<div class="msg assistant process-msg'+(state==='running'?' is-running':'')+(state==='error'?' is-error':'')+'">';
    html+='<div class="avatar" style="background:linear-gradient(135deg,#667eea,#764ba2)">N</div>';
    html+='<div class="msg-content process-content">';
    html+='<div class="process-line '+state+'">';
    html+=marker;
    html+='<span class="process-label">'+(label||escapeHtml(t('chat.process')))+'</span>';
   html+='<span class="process-detail">'+detailMarkup+'</span>';
   html+='</div>';
   html+='</div>';
   html+='</div>';
   return html;
  }

  function _planCssStatus(status){
   status=String(status||'pending');
   if(status==='done') return 'done';
   if(status==='running') return 'running';
   if(status==='waiting_user') return 'waiting-user';
   if(status==='blocked' || status==='error' || status==='failed') return 'error';
   return '';
  }

  function _renderPlanStrip(plan){
   var items=(plan&&plan.items)||[];
   if(!items.length) return '';
   var html='<div class="plan-strip">';
   html+='<div class="plan-goal">'+escapeHtml(String((plan&&plan.goal)||''))+'</div>';
   var summary=String((plan&&plan.summary)||'').trim();
   if(summary){
    html+='<div class="plan-summary">'+escapeHtml(summary)+'</div>';
   }
   html+='<div class="plan-items">';
   items.forEach(function(item){
    var status=_planCssStatus(item&&item.status);
    var cls='plan-item'+(status?' '+status:'');
    html+='<div class="'+cls+'">'+escapeHtml(String((item&&item.title)||''))+'</div>';
   });
   html+='</div>';
   html+='</div>';
   return html;
  }

  function _normalizeHistoryAttachments(raw){
   if(!Array.isArray(raw)) return [];
   var list=[];
   raw.forEach(function(item){
    if(!item||typeof item!=='object') return;
    var kind=String(item.type||'image').trim().toLowerCase()||'image';
    var url=String(item.url||'').trim();
    if(kind!=='image'||!url) return;
    list.push({
     url:url,
     alt:String(item.alt||item.name||'image').trim()||'image'
    });
   });
   return list;
  }

  function _renderHistoryAttachmentsHtml(raw){
   var attachments=_normalizeHistoryAttachments(raw);
   if(!attachments.length) return '';
   var cls='bubble-attachments'+(attachments.length>1?' is-multi':'');
   var html='<div class="'+cls+'">';
   attachments.forEach(function(item,idx){
    var url=escapeHtml(item.url);
    var alt=escapeHtml(item.alt||('image '+String(idx+1)));
    html+='<img class="bubble-image" src="'+url+'" alt="'+alt+'" data-chat-preview-src="'+url+'" loading="lazy">';
   });
   html+='</div>';
   return html;
  }

  var html='';
  items.forEach(function(item){
   var role=item.role||'user';
   var text=item.content||'';
   var attachmentsHtml=_renderHistoryAttachmentsHtml(item.attachments||[]);
   var process=item.process||null;
   var plan=(process&&process.plan)||null;
   var processSteps=(process&&process.steps)||[];
   var time=item.time||'';
   if(role!=='user'&&processSteps.length){
    processSteps.forEach(function(step){
     html+=_renderProcessMessage(step);
    });
   }
   if(!text.trim()&&!attachmentsHtml) return;
   var cls=role==='user'?'user':'assistant';
   var name=role==='user'?t('chat.you'):'Nova';
   var avBg=role==='user'?'linear-gradient(135deg,#10b981,#059669)':'linear-gradient(135deg,#667eea,#764ba2)';
   var avTxt=role==='user'?t('chat.you'):'N';
   html+='<div class="msg '+cls+'">';
   html+='<div class="avatar" style="background:'+avBg+'">'+avTxt+'</div>';
   if(role==='user'){
    html+='<div class="msg-content">';
  }else if(shouldRenderTaskPlanInChat && plan&&plan.items&&plan.items.length){
   html+='<div class="msg-content-wrap">';
   if(plan&&plan.items&&plan.items.length){
    html+=_renderPlanStrip(plan);
   }
   html+='<div class="msg-content">';
   }else{
    html+='<div class="msg-content">';
   }
   html+='<div class="msg-meta">';
   html+='<span class="msg-name">'+name+'</span><span class="msg-time">'+time+'</span>';
   html+='</div>';
   var bubbleMode=role==='user' ? '' : (
    typeof getAssistantBubbleMode==='function'
     ? getAssistantBubbleMode(text, item.content_html)
     : 'markdown'
   );
   var bubbleHtml=role==='user'
    ? formatBubbleText(text)
    : (typeof renderAssistantReplyHtml==='function'
      ? renderAssistantReplyHtml(text, item.content_html, bubbleMode)
      : renderAssistantBubbleHtml(text, item.content_html));
   html+='<div class="bubble'+(role==='user' ? '' : ' assistant-reply-'+bubbleMode)+'">'+attachmentsHtml+bubbleHtml+'</div>';
   html+='</div>';
   if(role!=='user'&&(plan&&plan.items&&plan.items.length)){
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
   if(typeof persistChatHistorySnapshot==='function'){
    persistChatHistorySnapshot();
   }
   if(typeof window._rebindChatImagePreviews==='function'){
    window._rebindChatImagePreviews(chat);
   }
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
  if(_chatViewRestoring) return;
  if(!_scrollBtn) return;
  if(window._currentTab!==1&&window._currentTab!==undefined){
   _scrollBtn.classList.remove('visible');
   _scrollBtn.style.display='none';
   return;
  }
  var awayFromBottom=_chatAwayFromBottom(chat);
  if(awayFromBottom>150){
   _scrollBtn.style.display='flex';
   requestAnimationFrame(function(){ _scrollBtn.classList.add('visible'); });
  }else{
   _scrollBtn.classList.remove('visible');
   setTimeout(function(){ if(!_scrollBtn.classList.contains('visible')) _scrollBtn.style.display='none'; },200);
  }
 }

 window._setScrollToBottomButtonTabState=function(isChatTab){
  if(!_scrollBtn) return;
  if(!isChatTab){
   _scrollBtn.classList.remove('visible');
   _scrollBtn.style.display='none';
   return;
  }
  _updateScrollBtn();
 };

 window.scrollToBottom=function(){
  _setChatAutoStick(true);
  _schedulePinChatToBottom();
 };

 chat.addEventListener('scroll',function(){
  if(window._currentTab!==1&&window._currentTab!==undefined) return;
  if(_chatViewRestoring) return;
  _snapshotChatScroll();
  _chatAutoStickToBottom=_isChatNearBottom(150);
  _updateScrollBtn();
  if(chat.scrollTop<80&&window._historyHasMore&&!window._historyLoading){
   window._loadMoreHistory();
  }
 });

fetch('/history?limit='+CHAT_HISTORY_BOOT_TURNS+'&offset=0').then(function(r){return r.json()}).then(function(d){
  var items=d.history||[];
  window._historyHasMore=d.has_more||false;
  var chat=document.getElementById('chat');
  var renderedTurns=_countRenderedHistoryTurns(chat);
  window._historyOffset=Math.max(items.length, renderedTurns);
  if(items.length===0){
   if(_restoredTimelineSnapshot){
    _rebindStepToggles(chat);
   }
   return;
  }
  if(typeof window._clearSessionTaskPlan==='function'){
   window._clearSessionTaskPlan();
  }
  if(!_restoredTimelineSnapshot || !renderedTurns){
   chat.innerHTML=window._renderHistoryItems(items);
   chatHistory=chat.innerHTML;
   if(typeof persistChatHistorySnapshot==='function'){
     persistChatHistorySnapshot();
   }
   if(typeof window._rebindChatImagePreviews==='function'){
    window._rebindChatImagePreviews(chat);
   }
   _schedulePinChatToBottom();
  }
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
    var sp=btn.querySelector('span'); if(sp) sp.textContent=t('chat.steps.hide');
   }else{
    tracker.classList.add('collapsed');
    var steps=tracker.querySelectorAll('.step-item');
    var sp=btn.querySelector('span'); if(sp) sp.textContent=tf('chat.steps.done',steps.length);
   }
  };
 });
};

// 读取模型列表
function _setModelLabel(label){
 ['modelName','topModelName'].forEach(function(id){
  var el=document.getElementById(id);
  if(el) el.textContent=label;
 });
}

 fetch('/models').then(r=>r.json()).then(function(d){
  var models=d.models||{};
  var cur=d.current||'';
  var displayName=(models[cur]&&models[cur].model)?models[cur].model:(cur||t('unknown'));
  _setModelLabel(displayName);
  window._novaModels=models;
  window._novaCurrentModel=cur;
  updateImageBtnState();
  // 加载 catalog 供 dropdown 分组用
  fetch('/models/catalog').then(function(r){return r.json();}).then(function(c){
   window._novaCatalog=c.catalog||{};
  }).catch(function(){});
 }).catch(function(){
  _setModelLabel(t('unknown'));
 });
};
