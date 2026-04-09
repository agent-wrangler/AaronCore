var chatHistory='';
var CHAT_HISTORY_MAX=200;
var CHAT_HISTORY_BOOT_TURNS=15;
var CHAT_HISTORY_SNAPSHOT_KEY='aaroncore_chat_history';
var CHAT_HISTORY_SESSION_SNAPSHOT_KEY='aaroncore_chat_history_session';
var _LEGACY_CHAT_HISTORY_SNAPSHOT_KEY='nova_chat_history';
var _LEGACY_CHAT_HISTORY_SESSION_SNAPSHOT_KEY='nova_chat_history_session';
var CHAT_HISTORY_RENDER_VERSION='chat-render-v20260409f';
var CHAT_HISTORY_RENDER_VERSION_KEY='aaroncore_chat_history_render_version';
var CHAT_HISTORY_SESSION_RENDER_VERSION_KEY='aaroncore_chat_history_session_render_version';
var _LEGACY_CHAT_HISTORY_RENDER_VERSION_KEY='nova_chat_history_render_version';
var _LEGACY_CHAT_HISTORY_SESSION_RENDER_VERSION_KEY='nova_chat_history_session_render_version';
var voiceEnabled=false;
function T(){var d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}

function _chatHistoryStorage(scope){
 return scope==='session' ? window.sessionStorage : window.localStorage;
}

function _chatHistorySnapshotKey(scope){
 return scope==='session' ? CHAT_HISTORY_SESSION_SNAPSHOT_KEY : CHAT_HISTORY_SNAPSHOT_KEY;
}

function _chatHistoryVersionKey(scope){
 return scope==='session' ? CHAT_HISTORY_SESSION_RENDER_VERSION_KEY : CHAT_HISTORY_RENDER_VERSION_KEY;
}

function _legacyChatHistorySnapshotKey(scope){
 return scope==='session' ? _LEGACY_CHAT_HISTORY_SESSION_SNAPSHOT_KEY : _LEGACY_CHAT_HISTORY_SNAPSHOT_KEY;
}

function _legacyChatHistoryVersionKey(scope){
 return scope==='session' ? _LEGACY_CHAT_HISTORY_SESSION_RENDER_VERSION_KEY : _LEGACY_CHAT_HISTORY_RENDER_VERSION_KEY;
}

function _readChatHistorySnapshot(scope){
 try{
  var storage=_chatHistoryStorage(scope);
  return storage.getItem(_chatHistorySnapshotKey(scope))
   || storage.getItem(_legacyChatHistorySnapshotKey(scope))
   || '';
 }catch(e){
  return '';
 }
}

function _writeChatHistorySnapshot(scope, html){
 try{
  var storage=_chatHistoryStorage(scope);
  storage.setItem(_chatHistorySnapshotKey(scope), html);
  storage.setItem(_chatHistoryVersionKey(scope), CHAT_HISTORY_RENDER_VERSION);
 }catch(e){}
}

function _removeChatHistorySnapshot(scope){
 try{
  var storage=_chatHistoryStorage(scope);
  storage.removeItem(_chatHistorySnapshotKey(scope));
  storage.removeItem(_chatHistoryVersionKey(scope));
 }catch(e){}
}

function _isHistoryTurnNode(node){
 if(!node || !node.classList || !node.classList.contains('msg')) return false;
 if(node.classList.contains('user')) return true;
 if(!node.classList.contains('assistant')) return false;
 return !node.classList.contains('process-msg')
  && !node.classList.contains('reply-part-msg')
  && !node.classList.contains('thinking-msg')
  && !node.classList.contains('thinking-trace-msg');
}

function trimChatHistoryHtml(sourceHtml, maxMessages){
 var html=String(sourceHtml||'');
 if(!html.trim()) return '';
 var limit=Math.max(1, Number(maxMessages)||CHAT_HISTORY_MAX);
 var tmp=document.createElement('div');
 tmp.innerHTML=html;
 var msgs=tmp.querySelectorAll('.msg');
 if(msgs.length<=limit) return tmp.innerHTML;
 var remove=msgs.length-limit;
 for(var i=0;i<remove;i++){
  if(msgs[i] && msgs[i].parentNode) msgs[i].parentNode.removeChild(msgs[i]);
 }
 return tmp.innerHTML;
}

function buildRecentChatHistorySnapshot(sourceHtml, maxTurns){
 var html=trimChatHistoryHtml(sourceHtml, CHAT_HISTORY_MAX);
 if(!html.trim()) return '';
 var limit=Math.max(1, Number(maxTurns)||CHAT_HISTORY_BOOT_TURNS);
 var tmp=document.createElement('div');
 tmp.innerHTML=html;
 var children=Array.prototype.slice.call(tmp.children||[]);
 var turnIndexes=[];
 for(var i=0;i<children.length;i++){
  if(_isHistoryTurnNode(children[i])) turnIndexes.push(i);
 }
 if(turnIndexes.length<=limit) return tmp.innerHTML;
 var keepFromTurnPos=turnIndexes.length-limit;
 var previousTurnIndex=keepFromTurnPos>0 ? turnIndexes[keepFromTurnPos-1] : -1;
 var startIndex=Math.max(0, previousTurnIndex+1);
 for(var j=0;j<startIndex;j++){
  if(children[j] && children[j].parentNode===tmp) tmp.removeChild(children[j]);
 }
 return tmp.innerHTML;
}

function trimChatHistory(){
 var tmp=document.createElement('div');
 tmp.innerHTML=chatHistory;
 var msgs=tmp.querySelectorAll('.msg');
 if(msgs.length>CHAT_HISTORY_MAX){
  var remove=msgs.length-CHAT_HISTORY_MAX;
  for(var i=0;i<remove;i++) msgs[i].parentNode.removeChild(msgs[i]);
  chatHistory=tmp.innerHTML;
  // 同步 offset，确保加载更多历史时不会跳过消息
  if(window._historyOffset!==undefined){
   window._historyOffset=CHAT_HISTORY_MAX;
   window._historyHasMore=true;
  }
 }
}

function hasCompatibleChatHistorySnapshot(scope){
 var target=scope==='session' ? 'session' : 'persistent';
 try{
  var storage=_chatHistoryStorage(target);
  return storage.getItem(_chatHistoryVersionKey(target))===CHAT_HISTORY_RENDER_VERSION
   || storage.getItem(_legacyChatHistoryVersionKey(target))===CHAT_HISTORY_RENDER_VERSION;
 }catch(e){
  return false;
 }
}

function getStoredChatHistorySnapshot(options){
 options=options||{};
 var preferSession=options.preferSession!==false;
 var recentTurns=Math.max(1, Number(options.recentTurns)||CHAT_HISTORY_BOOT_TURNS);
 var scopes=preferSession ? ['session','persistent'] : ['persistent','session'];
 for(var i=0;i<scopes.length;i++){
  var scope=scopes[i];
  if(!hasCompatibleChatHistorySnapshot(scope)){
   _removeChatHistorySnapshot(scope);
   continue;
  }
  var snapshot=_readChatHistorySnapshot(scope);
  if(!snapshot.trim()) continue;
  if(scope==='persistent'){
   snapshot=buildRecentChatHistorySnapshot(snapshot, recentTurns);
  }
  if(snapshot.trim()){
   return {html:snapshot, scope:scope};
  }
 }
 return {html:'', scope:''};
}

function clearChatHistorySnapshot(scope){
 chatHistory='';
 if(scope==='session' || scope==='persistent'){
  _removeChatHistorySnapshot(scope);
  return;
 }
 _removeChatHistorySnapshot('persistent');
 _removeChatHistorySnapshot('session');
}

function persistChatHistorySnapshot(){
 trimChatHistory();
 var fullSnapshot=String(chatHistory||'');
 var recentSnapshot=buildRecentChatHistorySnapshot(fullSnapshot, CHAT_HISTORY_BOOT_TURNS);
 _writeChatHistorySnapshot('session', fullSnapshot);
 _writeChatHistorySnapshot('persistent', recentSnapshot);
}

function assistantReplyLooksStructured(text, renderedHtml){
  var html=String(renderedHtml||'').trim();
  if(html){
    if(typeof normalizeRenderedAssistantHtml === 'function'){
      html=normalizeRenderedAssistantHtml(html);
    }
    if (/<(h[1-6]|pre|code|blockquote|table|hr)\b/i.test(html)) return true;
  }
  var raw=String(text||'').replace(/\r/g,'').trim();
  if(!raw) return false;
  if(/```/.test(raw)) return true;
  if(/^\s{0,3}(?:#{1,6}\s+|>\s+)/m.test(raw)) return true;
  if(/^\s*\|.+\|\s*$/m.test(raw)) return true;
  if(/^\s*[-*_]{3,}\s*$/m.test(raw)) return true;
  return false;
}

function getAssistantBubbleMode(text, renderedHtml){
  return assistantReplyLooksStructured(text, renderedHtml) ? 'markdown' : 'plain';
}

function applyAssistantBubbleRenderMode(bubble, text, renderedHtml, forcedMode){
  if(!bubble || !bubble.classList) return 'plain';
  bubble.classList.remove('assistant-reply-markdown','assistant-reply-plain');
  var mode=String(forcedMode||'').trim() || getAssistantBubbleMode(text, renderedHtml);
  bubble.classList.add(mode==='markdown' ? 'assistant-reply-markdown' : 'assistant-reply-plain');
  return mode;
}

function renderAssistantReplyHtml(text, renderedHtml, forcedMode){
  var mode=String(forcedMode||'').trim() || getAssistantBubbleMode(text, renderedHtml);
  if(mode==='markdown'){
    var html=String(renderedHtml||'').trim();
    if(html){
      if(typeof normalizeRenderedAssistantHtml === 'function'){
        html=normalizeRenderedAssistantHtml(html);
      }
      if(html) return html;
    }
    if(typeof formatBubbleText==='function'){
      return formatBubbleText(text);
    }
  }
  return renderAssistantPlainTextHtml(text);
}

function renderAssistantBubbleHtml(text, renderedHtml){
  return renderAssistantReplyHtml(text, renderedHtml);
}

function normalizeRenderedAssistantHtml(html){
  var text=String(html||'');
  if(!text) return '';
  return text.replace(/<hr\b[^>]*\/?>/gi, '<p>---</p>');
}

function renderAssistantPlainTextHtml(text){
  var raw=String(text||'').replace(/\r/g,'').trim();
  if(!raw) return '<div class="bubble-spacer"></div>';
  return '<div class="assistant-plain-text">'
    +escapeHtml(raw)
      .replace(/\n{3,}/g,'\n\n')
      .replace(/\n\n/g,'<br><br>')
      .replace(/\n/g,'<br>')
    +'</div>';
}

function formatMarkdownInline(text){
  var s=escapeHtml(text);
  s=s.replace(/\*\*(.+?)\*\*/g,'$1');
  s=s.replace(/__(.+?)__/g,'$1');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
  return s;
}

function stripMarkdownForStreamingText(text){
  var s=String(text||'').replace(/\r/g,'');
  if(!s) return '';
  s=s.replace(/^#{1,6}\s+/gm,'');
  s=s.replace(/^\s*>\s?/gm,'');
  s=s.replace(/^\s*[-*+]\s+/gm,'• ');
  s=s.replace(/^\s*\d+[.)]\s+/gm,'');
  s=s.replace(/```[\w-]*\n?/g,'');
  s=s.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'$1');
  s=s.replace(/\*\*/g,'');
  s=s.replace(/__/g,'');
  s=s.replace(/~~/g,'');
  s=s.replace(/`/g,'');
  return s;
}

function updateSendButton(){
 var inp=document.getElementById('inp');
 var btn=document.getElementById('sendBtn');
 var hasText=inp.value.trim().length>0;
 var hasImage=typeof _pendingImages!=='undefined'&&_pendingImages.length>0;
 var hasContent=hasText||hasImage;

 btn.disabled=!hasContent;
 if(hasContent){
  btn.classList.add('visible');
 }else if(!btn.classList.contains('stop-mode')){
  btn.classList.remove('visible');
 }
}

function formatBubbleText(text){
  var raw=String(text||'').replace(/\r/g,'');
  var lines=raw.split('\n');
  var html=[];
  var inCode=false, codeLines=[];
  var inList=false, listType='';
  var paragraphLines=[];

  function flushCode(){
    if(!inCode) return;
    html.push('<pre><code>'+escapeHtml(codeLines.join('\n'))+'</code></pre>');
    codeLines=[];
    inCode=false;
  }

  function flushList(){
    if(!inList) return;
    html.push(listType==='ol' ? '</ol>' : '</ul>');
    inList=false;
    listType='';
  }

  function flushParagraph(){
    if(!paragraphLines.length) return;
    html.push('<p>'+paragraphLines.map(formatMarkdownInline).join('<br>')+'</p>');
    paragraphLines=[];
  }

  function listTypeForLine(trimmed){
    if(/^[-*]\s+(.+)$/.test(trimmed)) return 'ul';
    if(/^\d+[.)]\s+(.+)$/.test(trimmed)) return 'ol';
    return '';
  }

  for(var i=0;i<lines.length;i++){
    var line=lines[i];
    var trimmed=line.trim();

    if(trimmed.startsWith('```')){
      if(inCode){
        flushCode();
      }else{
        flushParagraph();
        flushList();
        inCode=true;
        codeLines=[];
      }
      continue;
    }

    if(inCode){
      codeLines.push(line);
      continue;
    }

    // Empty lines end the current paragraph, but a single blank line between list items
    // should keep the same visual list instead of splitting into many one-item lists.
    if(!trimmed){
      var nextListType='';
      for(var ni=i+1;ni<lines.length;ni++){
        var nextTrimmed=lines[ni].trim();
        if(!nextTrimmed) continue;
        nextListType=listTypeForLine(nextTrimmed);
        break;
      }
      flushParagraph();
      if(inList && nextListType===listType) continue;
      flushList();
      continue;
    }

    var hm=trimmed.match(/^(#{1,3})\s+(.+)$/);
    if(hm){
      flushParagraph();
      flushList();
      html.push('<h'+hm[1].length+'>'+formatMarkdownInline(hm[2])+'</h'+hm[1].length+'>');
      continue;
    }

    if(trimmed.startsWith('> ')){
      flushParagraph();
      flushList();
      html.push('<blockquote>'+formatMarkdownInline(trimmed.slice(2))+'</blockquote>');
      continue;
    }

    var ulm=trimmed.match(/^[-*]\s+(.+)$/);
    if(ulm){
      flushParagraph();
      if(!inList || listType!=='ul'){
        flushList();
        html.push('<ul>');
        inList=true;
        listType='ul';
      }
      html.push('<li>'+formatMarkdownInline(ulm[1])+'</li>');
      continue;
    }

    var olm=trimmed.match(/^\d+[.)]\s+(.+)$/);
    if(olm){
      flushParagraph();
      if(!inList || listType!=='ol'){
        flushList();
        html.push('<ol>');
        inList=true;
        listType='ol';
      }
      html.push('<li>'+formatMarkdownInline(olm[1])+'</li>');
      continue;
    }

    flushList();
    paragraphLines.push(trimmed);
  }

  flushCode();
  flushParagraph();
  flushList();
  return html.join('');
}

function escapeHtml(text){
 return String(text||'')
  .replace(/&/g,'&amp;')
  .replace(/</g,'&lt;')
  .replace(/>/g,'&gt;')
  .replace(/"/g,'&quot;')
  .replace(/'/g,'&#39;');
}

function cleanInlineText(text, limit){
 var cleaned=String(text||'').replace(/\s+/g,' ').trim();
 if(!cleaned) return '';
 if(limit && cleaned.length>limit) return cleaned.slice(0, Math.max(limit-1, 1))+'\u2026';
 return cleaned;
}

function setInputVisible(visible){
 var inputArea=document.querySelector('.input');
 if(inputArea) inputArea.style.display=visible?'block':'none';
}

// memoryGrowthProfile / formatGrowthNumber → 已移至 memory.js
