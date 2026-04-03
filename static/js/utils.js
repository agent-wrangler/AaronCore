var chatHistory='';
var CHAT_HISTORY_MAX=200;
var CHAT_HISTORY_RENDER_VERSION='chat-render-v20260412b';
var CHAT_HISTORY_RENDER_VERSION_KEY='nova_chat_history_render_version';
var voiceEnabled=false;
function T(){var d=new Date();return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0');}

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

function hasCompatibleChatHistorySnapshot(){
 try{
  return localStorage.getItem(CHAT_HISTORY_RENDER_VERSION_KEY)===CHAT_HISTORY_RENDER_VERSION;
 }catch(e){
  return false;
 }
}

function clearChatHistorySnapshot(){
 chatHistory='';
 try{
  localStorage.removeItem('nova_chat_history');
  localStorage.removeItem(CHAT_HISTORY_RENDER_VERSION_KEY);
 }catch(e){}
}

function persistChatHistorySnapshot(){
 trimChatHistory();
 try{
  localStorage.setItem('nova_chat_history',chatHistory);
  localStorage.setItem(CHAT_HISTORY_RENDER_VERSION_KEY,CHAT_HISTORY_RENDER_VERSION);
 }catch(e){}
}

function renderAssistantBubbleHtml(text, renderedHtml){
  var html=String(renderedHtml||'').trim();
  if(html){
    if(typeof normalizeRenderedAssistantHtml === 'function'){
      html=normalizeRenderedAssistantHtml(html);
    }
    if(html) return html;
  }
  return formatBubbleText(text);
}

function normalizeRenderedAssistantHtml(html){
  var text=String(html||'');
  if(!text) return '';
  return text.replace(/<hr\b[^>]*\/?>/gi, '<p>---</p>');
}

function formatMarkdownInline(text){
  var s=escapeHtml(text);
  s=s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  s=s.replace(/`([^`]+)`/g,'<code>$1</code>');
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
 var awarenessBar=document.getElementById('awarenessBar');
 if(awarenessBar) awarenessBar.style.display=visible?'':'none';
}

// memoryGrowthProfile / formatGrowthNumber → 已移至 memory.js
