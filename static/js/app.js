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

function _syncWindowBackdrop(theme){
 var bg=theme==='light'?'#ffffff':'#262521';
 var useTransparentShell=!!(window.novaShell&&window.novaShell.transparentShell===true);
 document.documentElement.classList.remove('theme-light','theme-dark');
 document.documentElement.classList.add(theme==='light'?'theme-light':'theme-dark');
 document.documentElement.style.backgroundColor=useTransparentShell?'transparent':bg;
 if(document.body) document.body.style.backgroundColor=useTransparentShell?'transparent':bg;
 var shell=document.getElementById('windowShell');
 if(shell) shell.style.backgroundColor=bg;
}

function toggleTheme(){
 var body=document.body;
 if(body.classList.contains('dark')){
  body.classList.remove('dark');
  body.classList.add('light');
  localStorage.setItem('nova_theme','light');
  _syncWindowBackdrop('light');
  _syncTitleBar('light');
  _syncThemeIcon();
 }else{
  body.classList.remove('light');
  body.classList.add('dark');
  localStorage.setItem('nova_theme','dark');
  _syncWindowBackdrop('dark');
  _syncTitleBar('dark');
  _syncThemeIcon();
 }
 var currentTab=window._currentTab||1;
 if(currentTab!==1){
  setTimeout(function(){
   if(typeof show==='function' && window._currentTab===currentTab){
    show(currentTab);
   }
  },0);
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
 return;
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

function _setModelLabel(label){
 ['modelName','topModelName'].forEach(function(id){
  var el=document.getElementById(id);
  if(el) el.textContent=label;
 });
}

window.onload=function(){
 window._currentTab=1; // 默认聊天 tab
 initSidebarResize();
 hideWelcome();
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
_syncWindowBackdrop(savedTheme==='light'?'light':'dark');
_syncThemeIcon();
 // pywebview API 可能延迟就绪，等一下再同步标题栏颜色
 setTimeout(function(){
  _syncTitleBar(savedTheme==='light'?'light':'dark');
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
  if(typeof hasCompatibleChatHistorySnapshot==='function' && !hasCompatibleChatHistorySnapshot()){
   if(typeof clearChatHistorySnapshot==='function'){
    clearChatHistorySnapshot();
   }
   return false;
  }
  var snapshot='';
  try{
   snapshot=localStorage.getItem('nova_chat_history')||'';
  }catch(e){
   snapshot='';
  }
  if(!snapshot.trim()) return false;
  chat.innerHTML=snapshot;
  chatHistory=snapshot;
  _schedulePinChatToBottom();
  return true;
 }

 function _looksLikeChatSnapshot(html){
  var text=String(html||'').trim();
  if(!text) return false;
  if(/class="skill-store"|class="stats-page"|id="memScroll"|class="runtime-graph-page"|class="settings-page"/.test(text)) return false;
  return /class="msg\b|class="welcome\b|thinking-msg|process-msg|reply-part-msg/.test(text);
 }

 function _reloadChatFromServer(keepScroll){
  var chat=document.getElementById('chat');
  if(!chat) return;
  fetch('/history?limit=15&offset=0').then(function(r){return r.json()}).then(function(d){
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
    if(typeof window._rebindStepToggles==='function'){
     window._rebindStepToggles(chat);
    }
    if(!(keepScroll&&_restoreChatScroll())){
     _schedulePinChatToBottom();
    }
    return;
   }
   chat.innerHTML='';
   chatHistory='';
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

  var html='';
  items.forEach(function(item){
   var role=item.role||'user';
   var text=item.content||'';
   var process=item.process||null;
   var plan=(process&&process.plan)||null;
   var processSteps=(process&&process.steps)||[];
   var time=item.time||'';
   if(role!=='user'&&processSteps.length){
    processSteps.forEach(function(step){
     html+=_renderProcessMessage(step);
    });
   }
   if(!text.trim()) return;
   var cls=role==='user'?'user':'assistant';
   var name=role==='user'?t('chat.you'):'Nova';
   var avBg=role==='user'?'linear-gradient(135deg,#10b981,#059669)':'linear-gradient(135deg,#667eea,#764ba2)';
   var avTxt=role==='user'?t('chat.you'):'N';
   html+='<div class="msg '+cls+'">';
   html+='<div class="avatar" style="background:'+avBg+'">'+avTxt+'</div>';
   if(role==='user'){
    html+='<div class="msg-content">';
   }else if(plan&&plan.items&&plan.items.length){
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
   var bubbleHtml=role==='user' ? formatBubbleText(text) : renderAssistantBubbleHtml(text, item.content_html);
   html+='<div class="bubble">'+bubbleHtml+'</div>';
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
  var awayFromBottom=_chatAwayFromBottom(chat);
  if(awayFromBottom>150){
   _scrollBtn.style.display='flex';
   requestAnimationFrame(function(){ _scrollBtn.classList.add('visible'); });
  }else{
   _scrollBtn.classList.remove('visible');
   setTimeout(function(){ if(!_scrollBtn.classList.contains('visible')) _scrollBtn.style.display='none'; },200);
  }
 }

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

fetch('/history?limit=15&offset=0').then(function(r){return r.json()}).then(function(d){
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

function show(n){
 var chat = document.getElementById('chat');
 window._currentTab=n;
 try{
  _closeSkillModal(true);
 }catch(e){
  console.warn('[Nova] close skill modal failed', e);
 }
 for(var i=1;i<=6;i++){
  var menu=document.getElementById('m'+i);
  if(menu) menu.classList.remove('active');
 }
 var activeMenu=document.getElementById('m'+n);
 if(activeMenu) activeMenu.classList.add('active');
 var isLight = document.body.classList.contains('light');

 if(n==1){
  if(typeof window._beginChatViewRestore==='function'){
   window._beginChatViewRestore(900);
  }
  setInputVisible(true);
  if(!chatHistory || chatHistory.trim()===''){
   if(typeof hasCompatibleChatHistorySnapshot==='function' && !hasCompatibleChatHistorySnapshot()){
    if(typeof clearChatHistorySnapshot==='function'){
     clearChatHistorySnapshot();
    }
   }
   try{
    chatHistory=localStorage.getItem('nova_chat_history')||'';
   }catch(e){
    chatHistory='';
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
   console.warn('[Nova] close skill modal failed on skills tab', e);
  }
  chat.innerHTML='<div class="skill-store"><div class="skill-store-head"><div class="skill-store-hero"><div class="page-title">'+t('skills.title')+'</div><div class="skill-store-subtitle">'+t('skills.subtitle')+'</div></div><div class="skill-store-toolbar" id="skillsToolbar"></div></div><div class="skill-tabs" id="skillsViewTabs"></div><div id="skillsList">'+t('loading')+'</div></div>';
  try{
   _renderSkillsToolbar();
  }catch(e){
   console.warn('[Nova] render skills toolbar failed', e);
  }
  try{
   _loadSkillsList();
  }catch(e){
   console.warn('[Nova] load skills list failed', e);
  }
 }

 if(n==3){
  setInputVisible(false);
  chat.innerHTML='<div class="stats-page"><div style="text-align:right;margin-bottom:8px;"><button class="stats-refresh-btn" onclick="loadStatsData()" title="'+t('common.refresh')+'"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6"/><path d="M1 20v-6h6"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg></button></div><div id="statsBox">'+t('loading')+'</div></div>';
  try{
   loadStatsData();
  }catch(e){
   console.warn('[Nova] load stats failed', e);
  }
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
var _skillsViewScope='default';
var _skillsViewCounts={default:0,advanced:0};

function _skillsViewScopeQuery(){
 return _skillsViewScope==='advanced'?'default,advanced':'default';
}

function _renderSkillsToolbar(){
 var tabs=document.getElementById('skillsViewTabs');
 var note=document.getElementById('skillsViewNote');
 if(tabs){
  var items=[{scope:'default', label:t('skills.view.default')}];
  if((_skillsViewCounts.advanced||0)>0){
   items.push({scope:'advanced', label:t('skills.view.advanced')});
  }else if(_skillsViewScope==='advanced'){
   _skillsViewScope='default';
  }
  tabs.style.display=items.length>1?'flex':'none';
  tabs.innerHTML='';
  items.forEach(function(item){
   var active=item.scope===_skillsViewScope?' active':'';
   tabs.innerHTML+='<button class="skill-tab'+active+'" onclick="_setSkillsView(\''+item.scope+'\')">'+escapeHtml(item.label)+'</button>';
  });
 }
 if(note){
  note.textContent=_skillsViewScope==='advanced'
   ?t('skills.view.advanced.desc')
   :t('skills.view.default.desc');
 }
}

function _loadSkillsCatalogSummary(){
 fetch('/skills/catalog/summary').then(function(r){return r.json();}).then(function(d){
  var by=(d&&d.summary&&d.summary.by_user_view_scope)||{};
  var advancedCount=Number(by.advanced||0);
  var changed=_skillsViewScope==='advanced'&&advancedCount<=0;
  _skillsViewCounts={
   default:Number(by.default||0),
   advanced:advancedCount
  };
  if(changed){
   _skillsViewScope='default';
   if(window._currentTab===2){
    _loadSkillsList();
    return;
   }
  }
  _renderSkillsToolbar();
 }).catch(function(){
  _skillsViewCounts={default:0,advanced:0};
  if(_skillsViewScope==='advanced'){
   _skillsViewScope='default';
  }
  _renderSkillsToolbar();
 });
}

function _setSkillsView(scope){
 var next=scope==='advanced'?'advanced':'default';
 if(_skillsViewScope===next){
  _renderSkillsToolbar();
  return;
 }
 _skillsViewScope=next;
 _renderSkillsToolbar();
 _loadSkillsList();
}

function _loadSkillsList(){
 var list=document.getElementById('skillsList');
 if(!list) return;
 _renderSkillsToolbar();
 list.innerHTML=t('loading');
 fetch('/skills/views/user?scope='+encodeURIComponent(_skillsViewScopeQuery())).then(function(r){return r.json();}).then(function(d){
  _cachedSkillsData=d;
  if(!d||!d.skills){list.innerHTML='';return;}
  var filtered=d.skills.filter(function(s){return (s.source||'native')==='native';});
  _renderNativeSkills(filtered);
 }).catch(function(){
  list.innerHTML='<div style="color:#ef4444;">'+t('skills.load.fail')+'</div>';
 });
}

function _renderNativeSkills(skills){
 if(!Array.isArray(skills) || !skills.length){
  var emptyList=document.getElementById('skillsList');
  if(emptyList) emptyList.innerHTML='<div style="color:#94a3b8;padding:20px;">'+t('skills.empty')+'</div>';
  return;
 }
 var catOrder=[t('skills.cat.info'),t('skills.cat.content'),t('skills.cat.dev')];
 var groups={};
  catOrder.forEach(function(c){groups[c]=[];});
 skills.forEach(function(s){
  var cat=s.category||t('skills.cat.dev');
  if(!groups[cat])groups[cat]=[];
  groups[cat].push(s);
 });
 var html='';
 var renderedCount=0;
 function _appendSkillCard(skill){
  try{
   html+=_buildSkillCard(skill);
  }catch(_err){
   html+=_buildSkillFallbackCard(skill);
  }
  renderedCount++;
 }
 catOrder.forEach(function(catName){
  var items=groups[catName];
  if(!items||items.length===0)return;
  var ci=_catIcons[catName]||'';
  html+='<div class="skill-category">';
  html+='<div class="skill-category-header">'+ci+'<span class="skill-category-name">'+catName+'</span></div>';
  html+='<div class="skill-grid">';
  items.forEach(function(s){_appendSkillCard(s);});
  html+='</div></div>';
 });
 Object.keys(groups).forEach(function(cat){
  if(catOrder.indexOf(cat)===-1&&groups[cat].length>0){
   html+='<div class="skill-category"><div class="skill-category-header"><span class="skill-category-name">'+cat+'</span></div><div class="skill-grid">';
   groups[cat].forEach(function(s){_appendSkillCard(s);});
   html+='</div></div>';
  }
 });
 if(!renderedCount&&skills.length){
  html='<div class="skill-grid skill-grid-flat">';
  skills.forEach(function(s){_appendSkillCard(s);});
  html+='</div>';
 }
 if(!html) html='<div style="color:#94a3b8;padding:20px;">'+t('skills.empty')+'</div>';
 var list=document.getElementById('skillsList');
 if(list) list.innerHTML='<div class="skill-store-summary">'+tf('skills.visible.count', skills.length)+'</div>'+html;
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

function _buildSkillFallbackCard(s){
 var name=escapeHtml(s&&s.name||s&&s.id||'Skill');
 var desc=escapeHtml(s&&s.description||t('skills.no.desc'));
 return '<div class="skill-card"><div class="skill-card-name">'+name+'</div><div class="skill-card-desc">'+desc+'</div></div>';
}

function _escHtml(s){
 if(!s) return '';
 return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

// ===== Codex-style skills surface override =====
var _skillIcons={
 weather:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 3v2"/><path d="M12 19v2"/><path d="M4.93 4.93l1.41 1.41"/><path d="M17.66 17.66l1.41 1.41"/><path d="M3 12h2"/><path d="M19 12h2"/><path d="M4.93 19.07l1.41-1.41"/><path d="M17.66 6.34l1.41-1.41"/><circle cx="12" cy="12" r="4"/></svg>',
 stock:'<svg viewBox="0 0 24 24" width="22" height="22"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>',
 news:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 5h13a3 3 0 013 3v11H7a3 3 0 01-3-3z"/><path d="M7 5v13a3 3 0 01-3-3V8a3 3 0 013-3z"/><line x1="9" y1="10" x2="17" y2="10"/><line x1="9" y1="14" x2="15" y2="14"/></svg>',
 article:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M14 3H6a2 2 0 00-2 2v14a2 2 0 002 2h12a2 2 0 002-2V9z"/><polyline points="14 3 14 9 20 9"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="14" y2="17"/></svg>',
 story:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>',
 draw:'<svg viewBox="0 0 24 24" width="22" height="22"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>',
 creator:'<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 5v14"/><path d="M5 12h14"/><path d="M4 4h16v16H4z" opacity="0.35"/></svg>',
 generic:'<svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><circle cx="12" cy="16" r="1"/></svg>'
};
var _skillPinnedStorageKey='nova_skill_defaults_v2';
var _skillPinnedFallback=['weather'];
var _skillsCatalogCache=[];
var _skillsCatalogById={};
var _skillsSearchQuery='';
var _skillModalState=null;
var _skillToggleBusy={};
var _skillDetailCache={};
var _skillMeta={
 weather:{
  theme:'info',
  maturity:'core',
  summary:'查询城市当前天气和短期预报，适合出行前快速确认。',
  scenes:['今天和未来几天的天气概况','出门、通勤、周末安排前的快速判断'],
  boundary:'缺少城市时先确认；可以给出是否适合出门的结论，但不要把天气回复写成完整行程规划。',
  samplePrompt:'帮我看下上海今天和接下来三天的天气，顺便告诉我要不要带伞',
  promptPreview:'在用户需要当前天气或短期预报时使用。先确认城市；默认给今天和接下来几天，不先铺小时级数据。先讲温度、降雨、风和体感；如果用户在安排出行，最后补一句是否适合出门。',
  docLead:'在用户只是想先知道今天要不要带伞、周末能不能出门，或者某个城市接下来几天大概什么天气时，用这个 skill。它的目标是先把结论说清楚，再按需要展开，而不是把原始天气数据整页铺开。',
  docHighlights:['今天与未来几天的天气概况','出行、通勤、周末计划前的快速判断','需要一句明确结论再补数据的场景'],
  docQuickStart:['上海今天会下雨吗？顺手告诉我接下来三天大概怎么样','这周末杭州适合出门吗','北京今晚降温厉害吗，需要穿厚一点吗'].join('\n'),
  docNotes:['城市不明确时先追问，不硬猜。','默认先讲温度、降雨、风力和体感。','小时级细节只在用户明确需要时展开。','不要把天气回复写成旅游攻略或生活方式文章。']
 },
 news:{
  theme:'info',
  maturity:'beta',
  summary:'快速汇总最新动态，适合先建立今天发生了什么的全局感。',
  scenes:['今天最值得关注的几条动态','某个话题或行业的快速盘点'],
  boundary:'这是快速情报视图，不替代完整调研；不要把未证实信息写成定论。',
  samplePrompt:'帮我看下今天科技圈最值得关注的几条新闻，按重要性排一下',
  promptPreview:'在用户需要快速建立“今天发生了什么”的全局感时使用。先收窄话题或范围，再给 3 到 5 条最新重点；能给时间线索就给时间线索，变化快的话题要提醒用户继续核实。',
  docLead:'这个 skill 用来先建立一个清楚的新闻面，而不是一上来就写长篇研究。先给最新几条，再由用户决定要不要继续深挖其中一条。',
  docHighlights:['今天最值得关注的几条动态','某个行业、公司或话题的快速盘点','需要带时间线索和来源感的摘要'],
  docQuickStart:['今天 AI 圈最值得关注的几条新闻是什么','帮我看下最近和苹果有关的重点动态','用 5 条以内快速总结一下今天的国际新闻'].join('\n'),
  docNotes:['先给 3 到 5 条重点，不一上来写长评。','时效性强的话题尽量带时间线索。','敏感或不稳定消息要提醒继续核实。','只有当用户要继续时，再展开其中一条。']
 },
 stock:{
  theme:'info',
  maturity:'beta',
  summary:'查看股票最新价格、涨跌幅和交易时段，用于行情速查。',
  scenes:['单只股票的行情速查','需要一句数字结论再补充背景'],
  boundary:'给行情和必要背景，不做收益承诺，也不把速查结果写成投资建议。',
  samplePrompt:'帮我看下英伟达现在的股价、涨跌幅和今天的交易情况',
  promptPreview:'在用户需要快速看行情时使用。先确认股票代码或公司；先给最新价格、涨跌幅和交易时段，再补一句背景。这是行情速查，不是投资建议。',
  docLead:'这是一个行情速查 skill。重点不是替用户做决策，而是把最新数字、涨跌和交易阶段先说清楚，再补上一句最必要的背景信息。',
  docHighlights:['单只股票当前价格与涨跌幅','盘前、盘中、盘后的交易阶段判断','需要先看数字再决定要不要继续分析'],
  docQuickStart:['英伟达现在多少钱，今天涨了还是跌了','帮我看下特斯拉现在的股价和交易时段','AAPL 最新价格、涨跌幅、今天整体表现'].join('\n'),
  docNotes:['代码或公司名不明确时先澄清，不要猜错标的。','先给价格、涨跌幅和交易时段，再补一句背景。','行情结果要写成速查口吻，不写成投资建议。','用户想继续分析时，再往下展开。']
 },
 article:{
  theme:'content',
  maturity:'beta',
  summary:'按指定受众和语气把素材整理成可继续修改的成稿。',
  scenes:['把零散素材整理成完整草稿','按平台、受众和语气改写'],
  boundary:'它负责把素材写顺，不负责凭空补全事实，也不替代真实采访或查证。',
  samplePrompt:'帮我把这几条素材整理成一篇面向公众号读者的短文章，语气自然一点',
  promptPreview:'在用户已经有素材、观点或方向时使用。先锁定角度、受众和语气，再把零散信息整理成一篇能继续改的成稿；不要把原始要点直接堆成段落。',
  docLead:'这个 skill 的工作不是“多写一点”，而是先把主线、角度和结构找出来，再把素材组织成一篇可以继续修改的成稿。它适合从零散材料走到首版草稿。',
  docHighlights:['把素材、提纲或碎片笔记整理成成稿','按目标平台、受众和语气重写','给出一版可继续润色的首稿'],
  docQuickStart:['把这几条采访笔记整理成一篇 800 字公众号稿','按更口语一点的语气，把这段内容改成小红书风格','我给你一些要点，你先帮我起一版正式文章'].join('\n'),
  docNotes:['先定角度、受众和语气，再动笔。','原始素材要先整理，不直接硬拼成段落。','事实不稳的地方要留复核空间。','用户指明平台或语气时，要明显向那个口味靠。']
 },
 story:{
  theme:'content',
  maturity:'beta',
  summary:'根据题材、人物和情绪写完整片段或短篇开头。',
  scenes:['短篇开头与单场景片段','需要一个能继续扩写的故事骨架'],
  boundary:'这是虚构创作 skill；不要把真实问答误写成小说，也不要把事实内容包装成虚构。',
  samplePrompt:'写一个带一点悬疑感的短篇开头，主角是个总在凌晨接到陌生电话的人',
  promptPreview:'在用户需要一个顺的故事片段时使用。先定题材、人物和情绪，再写完整片段；就算篇幅短，也要有起势、转折和落点，而不是只堆设定。',
  docLead:'这个 skill 更像一个会先把叙事跑顺的写作者，而不是设定生成器。它的目标是先写出一个能读下去的片段，再看是否继续扩写。',
  docHighlights:['短篇开头、单场景片段、故事钩子','先给设定，再落成真正的叙事','需要一个能继续扩写的故事骨架'],
  docQuickStart:['写一个赛博朋克悬疑故事的开头，主角是失业调查员','帮我写一段温柔一点的校园重逢片段','给我一个黑色幽默风格的短故事开场'].join('\n'),
  docNotes:['用户没给方向时，先补一个明确的题材或情绪走向。','就算是短篇，也要有起势、转折和落点。','设定要服务故事推进，不要只堆概念。','如果用户只要脑洞，可以先给设定和开头。']
 },
 draw:{
  theme:'content',
  maturity:'beta',
  summary:'为插画、海报和概念图生成清晰可迭代的图像提示。',
  scenes:['海报、插画、概念图方向锁定','需要一段可继续迭代的生图提示'],
  boundary:'适合锁方向和生图提示，不替代严谨排版、品牌规范或后期精修。',
  samplePrompt:'帮我写一段海报级的生图提示：赛博朋克雨夜街头，电影感，竖版',
  promptPreview:'在用户需要为插画、海报或概念图快速锁定画面方向时使用。先确认主体、风格、用途和画幅，再生成可以继续迭代的图像提示；它更适合创意方向，不替代完整设计流程。',
  docLead:'这个 skill 用来把画面方向先锁清楚，再产出一段可以继续生成、继续细化的图像提示。它擅长海报、插画和概念图，不负责最后的品牌规范和精修交付。',
  docHighlights:['海报视觉：电影海报、活动海报、封面主视觉','插画方向：角色、场景、故事氛围图','概念图：产品概念、世界观氛围、风格探索','参考延展：在已有参考图上继续明确方向'],
  docQuickStart:['主体：一只在雨夜街头奔跑的银色机械狐','风格：电影感赛博朋克插画，冷蓝霓虹','用途：竖版海报主视觉，适合做封面','补充：高对比、湿润路面反光、画面中心构图'].join('\n'),
  docNotes:['先把主体、风格、用途和画幅说清楚。','有参考图时，先说明是延展、改造还是重做。','它给出的是可继续生成的提示，不是最终设计交付。','如果用户需要品牌规范、排版和成品修图，要明确那是后续流程。']
 }
};

function _defaultPinnedSkillIds(){
 var raw=null;
 try{ raw=localStorage.getItem(_skillPinnedStorageKey); }catch(_err){}
 if(!raw) return _skillPinnedFallback.slice();
 try{
  var parsed=JSON.parse(raw);
  if(Array.isArray(parsed)){
   var ids=[];
   parsed.forEach(function(id){
    id=String(id||'').trim();
    if(id && ids.indexOf(id)===-1) ids.push(id);
   });
   return ids.length?ids:_skillPinnedFallback.slice();
  }
 }catch(_err){}
 return _skillPinnedFallback.slice();
}

function _savePinnedSkillIds(ids){
 var unique=[];
 (ids||[]).forEach(function(id){
  id=String(id||'').trim();
  if(id && unique.indexOf(id)===-1) unique.push(id);
 });
 try{ localStorage.setItem(_skillPinnedStorageKey, JSON.stringify(unique)); }catch(_err){}
}

function _getSkillIcon(skill){
 if(skill&&skill.icon_url){
  return '<img class="skill-icon-img" src="'+escapeHtml(skill.icon_url)+'" alt="">';
 }
 if(skill&&skill.pseudo) return _skillIcons.creator;
 return _skillIcons[String(skill&&skill.id||'').trim()]||_skillIcons.generic;
}

function _getSkillMeta(skill){
 var base=_skillMeta[String(skill&&skill.id||'').trim()]||{};
 return {
  theme: base.theme||((skill&&skill.category)===t('skills.cat.content')?'content':'info'),
  maturity: base.maturity||'beta',
  summary: base.summary||'',
  scenes: base.scenes||[],
  boundary: base.boundary||t('skills.boundary.default'),
  samplePrompt: base.samplePrompt||t('skills.sample.default'),
  promptPreview: base.promptPreview||'',
  docLead: base.docLead||'',
  docHighlights: base.docHighlights||[],
  docQuickStart: base.docQuickStart||'',
  docNotes: base.docNotes||[],
  guideLead: base.guideLead||'',
  guideRules: base.guideRules||[],
  delivery: base.delivery||[]
  };
}

function _buildCreatorSkillCard(){
 return {
  id:'__skill_creator__',
  pseudo:true,
  name:t('skills.creator.name'),
  description:t('skills.creator.desc'),
  category:t('skills.cat.build'),
  tags:[t('skills.tag.user'),t('skills.tag.assistant')],
  theme:'builder',
  maturity:'core'
 };
}

function _openSkillCreatorEntry(){
 _showCreateSkillModal();
}

function _decorateSkill(skill){
 var item={};
 Object.keys(skill||{}).forEach(function(key){ item[key]=skill[key]; });
 var meta=_getSkillMeta(item);
 item.theme=meta.theme;
 item.maturity=meta.maturity;
 item.scenes=meta.scenes;
 item.description=item.description||meta.summary||'';
 item.boundary=meta.boundary;
 item.samplePrompt=meta.samplePrompt;
  item.tags=[item.category||'', meta.maturity==='core'?t('skills.badge.core'):t('skills.badge.beta')].filter(Boolean);
 return item;
}

function _renderSkillsToolbar(){
 var tabs=document.getElementById('skillsViewTabs');
 var note=document.getElementById('skillsViewNote');
 var toolbar=document.getElementById('skillsToolbar');
 if(toolbar){
  toolbar.innerHTML=
   '<button class="skill-toolbar-btn" onclick="_refreshSkillsCatalog()">'+
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15.5-6.36L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15.5 6.36L3 16"/></svg>'+
    '<span>'+escapeHtml(t('common.refresh'))+'</span>'+
   '</button>'+
   '<label class="skill-search-shell">'+
    '<span class="skill-search-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="20" y1="20" x2="16.65" y2="16.65"/></svg></span>'+
    '<input class="skill-search-input" type="text" value="'+escapeHtml(_skillsSearchQuery)+'" placeholder="'+escapeHtml(t('skills.search.placeholder'))+'" oninput="_onSkillSearch(this.value)">'+
   '</label>'+
   '<button class="skill-primary-btn" onclick="_openSkillCreatorEntry()">'+
    '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>'+
    '<span>'+escapeHtml(t('skills.new'))+'</span>'+
   '</button>';
 }
 if(tabs){
  tabs.style.display='none';
  tabs.innerHTML='';
 }
 if(note){
  note.textContent='';
  note.style.display='none';
 }
}

function _refreshSkillsCatalog(){
 _loadSkillsList();
}

function _onSkillSearch(value){
 _skillsSearchQuery=String(value||'').trim();
 _renderNativeSkills(_skillsCatalogCache);
}

function _loadSkillsList(){
 var list=document.getElementById('skillsList');
 if(!list) return;
 _renderSkillsToolbar();
 list.innerHTML=t('loading');
 fetch('/skills/views/user?scope=default').then(function(r){return r.json();}).then(function(d){
  _cachedSkillsData=d;
  if(!d||!d.skills){list.innerHTML='';return;}
  _skillsCatalogById={};
  _skillDetailCache={};
  _skillsCatalogCache=d.skills.filter(function(s){
   return (s.source||'native')==='native';
  }).map(function(s){
   var item=_decorateSkill(s);
   _skillsCatalogById[item.id]=item;
   return item;
  });
  _renderNativeSkills(_skillsCatalogCache);
 }).catch(function(){
  list.innerHTML='<div style="color:#ef4444;">'+t('skills.load.fail')+'</div>';
 });
}

function _skillMatchesQuery(skill, query){
 if(!query) return true;
 var haystack=[
  skill.name||'',
  skill.description||'',
  skill.category||'',
  (skill.tags||[]).join(' '),
  ((skill.keywords||[])||[]).join(' ')
 ].join(' ').toLowerCase();
 return haystack.indexOf(query.toLowerCase())!==-1;
}

function _buildSkillSection(title, desc, cards, sectionName){
 var html='<section class="skill-section">';
 html+='<div class="skill-section-head">';
 html+='<div><div class="skill-section-title">'+escapeHtml(title)+'</div>'+(desc?'<div class="skill-section-desc">'+escapeHtml(desc)+'</div>':'')+'</div>';
 html+='</div>';
 if(!cards.length){
  html+='<div class="skill-section-empty">'+escapeHtml(sectionName==='installed'?t('skills.empty.installed'):t('skills.empty.search'))+'</div>';
 }else{
  html+='<div class="skill-grid skill-grid-shelf">';
  cards.forEach(function(skill){ html+=_buildSkillCard(skill, sectionName); });
  html+='</div>';
 }
 html+='</section>';
 return html;
}

function _renderNativeSkills(skills){
 var list=document.getElementById('skillsList');
 if(!list) return;
 if(!Array.isArray(skills) || !skills.length){
  list.innerHTML='<div class="skill-section-empty">'+escapeHtml(t('skills.empty'))+'</div>';
  return;
 }
 var visible=skills.filter(function(skill){ return _skillMatchesQuery(skill, _skillsSearchQuery); });
 if(!visible.length){
  list.innerHTML='<div class="skill-section-empty">'+escapeHtml(t('skills.empty.search'))+'</div>';
  return;
 }
 var installed=visible.slice();
 var html=_buildSkillSection(t('skills.section.installed'), '', installed, 'installed');
 list.innerHTML=html;
}

function _skillBadgeHtml(label, cls){
 return '<span class="skill-pill '+cls+'">'+escapeHtml(label)+'</span>';
}

function _buildSkillCard(skill, sectionName){
 var icon=_getSkillIcon(skill);
 var enabled=skill.enabled!==false;
 var busy=!!_skillToggleBusy[skill.id];
 var actionHtml='<div class="skill-manage-wrap"><div class="skill-manage-label">'+escapeHtml(t('skills.action.manage'))+'</div><button class="skill-icon-btn skill-manage-btn" onclick="return _onSkillCardAction(event,\''+skill.id+'\',\'detail\')" title="'+escapeHtml(t('skills.action.manage'))+'"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6z"></path></svg></button></div>';
 actionHtml+='<button class="skill-switch '+(enabled?'is-on':'')+(busy?' is-busy':'')+'" onclick="return _onSkillCardAction(event,\''+skill.id+'\',\'toggle\')" title="'+escapeHtml(enabled?t('skills.action.disable'):t('skills.action.enable'))+'"'+(busy?' disabled':'')+'><span class="skill-switch-track"><span class="skill-switch-thumb"></span></span></button>';
 var html='<article class="skill-shelf-card theme-'+escapeHtml(skill.theme||'info')+(enabled?'':' is-disabled')+'" onclick="_openSkillModalById(\''+skill.id+'\')">';
 html+='<div class="skill-shelf-icon">'+icon+'</div>';
 html+='<div class="skill-shelf-main">';
 html+='<div class="skill-shelf-title-row"><div class="skill-shelf-title">'+escapeHtml(skill.name||skill.id||'Skill')+'</div></div>';
 html+='<div class="skill-shelf-desc">'+escapeHtml(skill.description||t('skills.no.desc'))+'</div>';
 html+='</div>';
 html+='<div class="skill-shelf-side">'+actionHtml+'</div>';
 html+='</article>';
 return html;
}

function _onSkillCardAction(evt, skillId, action){
 if(evt){
  evt.preventDefault();
  evt.stopPropagation();
 }
 if(action==='create'){
  _showCreateSkillModal();
  return false;
 }
 if(action==='detail'){
  _openSkillModalById(skillId);
  return false;
 }
 if(action==='toggle'){
  _toggleSkillEnabled(skillId);
  return false;
 }
 return false;
}

function _toggleSkillEnabled(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill || _skillToggleBusy[skillId]) return;
 _skillToggleBusy[skillId]=true;
 _renderNativeSkills(_skillsCatalogCache);
 fetch('/skills/'+encodeURIComponent(skillId)+'/toggle', {method:'POST'}).then(function(r){return r.json();}).then(function(d){
  if(d && d.ok){
   var enabled=d.enabled!==false;
   if(_skillsCatalogById[skillId]) _skillsCatalogById[skillId].enabled=enabled;
   _skillsCatalogCache=_skillsCatalogCache.map(function(item){
    if(item.id===skillId){
     item.enabled=enabled;
    }
    return item;
   });
  }
 }).catch(function(){}).finally(function(){
  delete _skillToggleBusy[skillId];
  _renderNativeSkills(_skillsCatalogCache);
  if(_skillModalState && _skillModalState.id===skillId) _openSkillModalById(skillId);
 });
}

function _copyText(text){
 text=String(text||'');
 if(!text) return;
 if(navigator.clipboard && navigator.clipboard.writeText){
  navigator.clipboard.writeText(text).catch(function(){});
  return;
 }
 try{
  var input=document.createElement('textarea');
  input.value=text;
  input.setAttribute('readonly','readonly');
  input.style.position='fixed';
  input.style.opacity='0';
  document.body.appendChild(input);
  input.select();
  document.execCommand('copy');
  if(input.parentNode) input.parentNode.removeChild(input);
 }catch(_err){}
}

function _copySkillPrompt(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill) return false;
 _copyText(_buildSkillPromptPreview(skill));
 return false;
}

function _openSkillFolder(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill) return false;
 fetch('/skills/'+encodeURIComponent(skillId)+'/open-folder', {method:'POST'}).catch(function(){});
 return false;
}

function _buildSkillPromptPreview(skill){
 return String((skill&&skill.default_prompt)||'').trim();
}

function _renderSkillModal(content){
 _closeSkillModal(true);
 var host=document.createElement('div');
 host.id='skillModalHost';
 host.innerHTML='<div class="skill-modal-backdrop" onclick="_closeSkillModal()"><div class="skill-modal" onclick="event.stopPropagation()">'+content+'</div></div>';
 document.body.appendChild(host);
 document.body.classList.add('skill-modal-open');
}

function _closeSkillModal(silent){
 var host=document.getElementById('skillModalHost');
 if(host && host.parentNode) host.parentNode.removeChild(host);
 document.body.classList.remove('skill-modal-open');
 if(!silent) _skillModalState=null;
}

function _buildSkillDetailSections(skill){
 return '<div class="skill-modal-doc">'+String((skill&&skill.body_html)||'')+'</div>';
}

function _renderInstalledSkillModal(skill){
 if(!skill) return;
 var enabled=skill.enabled!==false;
 var disableLabel=enabled?t('skills.action.disable'):t('skills.action.enable');
 var promptPreview=_buildSkillPromptPreview(skill);
 var content='';
 content+='<button class="skill-modal-close" onclick="_closeSkillModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>';
 content+='<div class="skill-modal-header"><div class="skill-modal-icon theme-'+escapeHtml(skill.theme||'info')+'">'+_getSkillIcon(skill)+'</div><div class="skill-modal-head-main"><div class="skill-modal-title">'+escapeHtml(skill.name||skill.id)+'</div><div class="skill-modal-subtitle">'+escapeHtml(skill.description||t('skills.no.desc'))+'</div></div><div class="skill-modal-head-actions"><button class="skill-modal-link" onclick="return _openSkillFolder(\''+skill.id+'\')">'+escapeHtml(t('skills.action.openFolder'))+' <span>&#8599;</span></button></div></div>';
 if(promptPreview){
  content+='<div class="skill-modal-prompt-panel"><div class="skill-modal-prompt-head"><div class="skill-modal-section-title">'+escapeHtml(t('skills.detail.example'))+'</div><button class="skill-modal-copy" onclick="return _copySkillPrompt(\''+skill.id+'\')" title="'+escapeHtml(t('skills.action.copyPrompt'))+'"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="10" height="10" rx="2"></rect><path d="M5 15V7a2 2 0 0 1 2-2h8"></path></svg></button></div><div class="skill-modal-prompt-text">'+escapeHtml(promptPreview)+'</div></div>';
 }
 content+='<div class="skill-modal-scroll"><div class="skill-modal-body">'+_buildSkillDetailSections(skill)+'</div></div>';
 content+='<div class="skill-modal-actions"><div class="skill-modal-actions-left"><button class="skill-modal-btn ghost" onclick="_toggleSkillEnabled(\''+skill.id+'\')">'+escapeHtml(disableLabel)+'</button></div><div class="skill-modal-actions-right"><button class="skill-modal-btn primary" onclick="_trySkill(\''+skill.id+'\')">'+escapeHtml(t('skills.action.try'))+'</button></div></div>';
 _renderSkillModal(content);
}

function _openSkillModalById(skillId){
 if(skillId==='__skill_creator__'){
  _showCreateSkillModal();
  return;
 }
 var skill=_skillsCatalogById[skillId];
 if(!skill) return;
 _skillModalState={id:skillId};
 if(_skillDetailCache[skillId]){
  var merged=Object.assign({}, skill, _skillDetailCache[skillId]);
  _skillsCatalogById[skillId]=merged;
  _renderInstalledSkillModal(merged);
  return;
 }
 _renderSkillModal(
  '<button class="skill-modal-close" onclick="_closeSkillModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>'+
  '<div class="skill-modal-header"><div class="skill-modal-icon theme-'+escapeHtml(skill.theme||'info')+'">'+_getSkillIcon(skill)+'</div><div class="skill-modal-head-main"><div class="skill-modal-title">'+escapeHtml(skill.name||skill.id)+'</div><div class="skill-modal-subtitle">'+escapeHtml(skill.description||t('skills.no.desc'))+'</div></div></div>'+
  '<div class="skill-modal-scroll"><div class="skill-modal-loading">'+escapeHtml(t('loading'))+'</div></div>'
 );
 fetch('/skills/'+encodeURIComponent(skillId)+'/detail').then(function(r){return r.json();}).then(function(d){
  if(!d || !d.ready || !d.skill) return;
  _skillDetailCache[skillId]=d.skill;
  var merged=Object.assign({}, _skillsCatalogById[skillId]||{}, d.skill);
  _skillsCatalogById[skillId]=merged;
  if(_skillModalState && _skillModalState.id===skillId){
   _renderInstalledSkillModal(merged);
  }
 }).catch(function(){});
}

function _showCreateSkillModal(){
 _skillModalState={id:'__skill_creator__'};
 var content='';
 content+='<button class="skill-modal-close" onclick="_closeSkillModal()"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>';
 content+='<div class="skill-modal-header"><div class="skill-modal-icon theme-builder">'+_skillIcons.creator+'</div><div class="skill-modal-head-main"><div class="skill-modal-title-row"><div class="skill-modal-title">'+escapeHtml(t('skills.creator.name'))+'</div></div><div class="skill-modal-subtitle">'+escapeHtml(t('skills.creator.summary'))+'</div></div></div>';
 content+='<div class="skill-modal-scroll"><div class="skill-modal-body">';
 content+='<div class="skill-modal-section"><div class="skill-modal-section-title">'+escapeHtml(t('skills.creator.user.title'))+'</div><div class="skill-modal-paragraph">'+escapeHtml(t('skills.creator.user.desc'))+'</div></div>';
 content+='<div class="skill-modal-section"><div class="skill-modal-section-title">'+escapeHtml(t('skills.creator.assistant.title'))+'</div><div class="skill-modal-paragraph">'+escapeHtml(t('skills.creator.assistant.desc'))+'</div></div>';
 content+='<div class="skill-modal-section"><div class="skill-modal-section-title">'+escapeHtml(t('skills.modal.boundary.title'))+'</div><div class="skill-modal-paragraph">'+escapeHtml(t('skills.modal.createBoundary'))+'</div></div>';
 content+='</div></div>';
 content+='<div class="skill-modal-actions"><div class="skill-modal-actions-left"><button class="skill-modal-btn ghost" onclick="_startCreateSkillFlow(\'user\')">'+escapeHtml(t('skills.action.userCreate'))+'</button></div><div class="skill-modal-actions-right"><button class="skill-modal-btn primary" onclick="_startCreateSkillFlow(\'assistant\')">'+escapeHtml(t('skills.action.assistantCreate'))+'</button></div></div>';
 _renderSkillModal(content);
}

function _startCreateSkillFlow(mode){
 _closeSkillModal(true);
 if(mode==='user'){
  show(6);
  return;
 }
 show(1);
 setTimeout(function(){ quickSend(t('skills.creator.assistant.prompt')); },0);
}

function _trySkill(skillId){
 var skill=_skillsCatalogById[skillId];
 if(!skill) return;
 _closeSkillModal(true);
 show(1);
 var prompt=String(skill.default_prompt||'').trim();
 if(!prompt) prompt=String(skill.description||'').trim();
 if(!prompt) prompt='请用'+String(skill.name||skill.id||'这个技能')+'来处理这个任务。';
 setTimeout(function(){ quickSend(prompt); },0);
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
    html+='<div class="model-dropdown-item'+active+'" data-model-id="'+escapeHtml(mid)+'">'+displayName+vision+'</div>';
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
    html+='<div class="model-dropdown-item'+active+'" data-model-id="'+escapeHtml(mid)+'">'+displayName+vision+'</div>';
   });
  }
 }else{
  // fallback: 无 catalog 时扁平列表
  Object.keys(models).forEach(function(mid){
   var m=models[mid];
   var displayName=m.model||mid;
   var active=mid===current?' active':'';
   var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
   html+='<div class="model-dropdown-item'+active+'" data-model-id="'+escapeHtml(mid)+'">'+displayName+vision+'</div>';
  });
 }
 dd.innerHTML=html;
 dd.onclick=function(evt){
  evt.stopPropagation();
  var target=evt.target;
  if(!target||!target.closest) return;
  var item=target.closest('.model-dropdown-item[data-model-id]');
  if(!item) return;
  var modelId=String(item.getAttribute('data-model-id')||'').trim();
  if(!modelId) return;
  console.log('[models][sidebar] click', modelId);
  _sidebarSwitchModel(modelId);
 };
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
function _resetModelSwitchButtons(){
 var items=document.querySelectorAll('[onclick*="switchModel"],[onclick*="_sidebarSwitchModel"],[data-model-action="switch"]');
 items.forEach(function(it){
  it.style.pointerEvents='';
  it.style.opacity='';
  it.style.outline='';
  it.style.outlineOffset='';
 });
 return items;
}
function _restoreModelSwitchState(previousModel, previousLabel, previousSettingsModel){
 window._novaCurrentModel=previousModel||'';
 _setModelLabel(previousLabel||t('unknown'));
 if(typeof _settingsCurrentModel!=='undefined'){
  _settingsCurrentModel=previousSettingsModel||'';
 }
 _resetModelSwitchButtons();
 if(typeof updateImageBtnState==='function') updateImageBtnState();
}
function _alertModelSwitchFailure(detail){
 var text=String(detail||'').trim()||'切换失败，请检查模型配置或网络连接';
 try{
  alert(text);
 }catch(_err){}
}
function _sidebarSwitchModel(mid){
 // 即时关闭 dropdown
 var dd=document.getElementById('modelDropdown');
 if(dd) dd.style.display='none';
 var previousModel=window._novaCurrentModel||'';
  if(mid===previousModel) return;
  console.log('[models][sidebar] switch start', mid, 'current=', previousModel||'');
 var previousSettingsModel=(typeof _settingsCurrentModel!=='undefined')?_settingsCurrentModel:'';
 var previousCfg=(window._novaModels||{})[previousModel];
 var previousLabel=(previousCfg&&previousCfg.model)?previousCfg.model:(previousModel||t('unknown'));
 // 即时更新侧边栏显示
 window._novaCurrentModel=mid;
 var _m=(window._novaModels||{})[mid];
 _setModelLabel((_m&&_m.model)?_m.model:mid);
 // 如果在设置页，即时高亮
 var items=_resetModelSwitchButtons();
 items.forEach(function(it){it.style.pointerEvents='none';it.style.opacity='0.5';});
 var clicked=null;
 items.forEach(function(it){
  var targetMid=String(it.getAttribute('data-model-id')||'').trim();
  var onclick=String(it.getAttribute('onclick')||'');
  if(targetMid===mid||onclick.indexOf(mid)!==-1){clicked=it;}
 });
 if(clicked){clicked.style.opacity='1';clicked.style.outline='2px solid #60a5fa';clicked.style.outlineOffset='-2px';}
 fetch('/model/'+encodeURIComponent(mid),{method:'POST'}).then(r=>r.json()).then(function(d){
  if(d.ok){
   console.log('[models][sidebar] switch ok', mid);
   _resetModelSwitchButtons();
   if(typeof updateImageBtnState==='function') updateImageBtnState();
   if(typeof _settingsCurrentModel!=='undefined'){
    _settingsCurrentModel=mid;
    setTimeout(function(){if(typeof loadSettingsModels==='function') loadSettingsModels();},300);
   }
  }else{
   console.warn('[models][sidebar] switch fail', mid, d&&d.error);
   // 回滚
   _restoreModelSwitchState(previousModel, previousLabel, previousSettingsModel);
   _alertModelSwitchFailure(d&&d.error);
  }
 }).catch(function(){
  console.warn('[models][sidebar] switch error', mid);
  _restoreModelSwitchState(previousModel, previousLabel, previousSettingsModel);
  _alertModelSwitchFailure('');
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
