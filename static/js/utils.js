var chatHistory='';
var CHAT_HISTORY_MAX=200;
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
 var raw=String(text||'');
 var lines=raw.split('\n');
 var html=[];
 var inCode=false, codeLines=[];
 var inList=false, listType='';

 function flushCode(){
  if(!inCode) return;
  html.push('<pre class="bubble-code"><code>'+escapeHtml(codeLines.join('\n'))+'</code></pre>');
  codeLines=[];
  inCode=false;
 }

 function flushList(){
  if(!inList) return;
  html.push(listType==='ol'?'</ol>':'</ul>');
  inList=false;
  listType='';
 }

 function fmtInline(s){
  s=escapeHtml(s);
  s=s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  s=s.replace(/`([^`]+)`/g,'<code class="bubble-inline-code">$1</code>');
  return s;
 }

 for(var i=0;i<lines.length;i++){
  var line=lines[i];
  var trimmed=line.trim();

  if(trimmed.startsWith('```')){
   if(inCode){ flushCode(); }
   else{ flushList(); inCode=true; codeLines=[]; }
   continue;
  }
  if(inCode){ codeLines.push(line); continue; }

  if(!trimmed){ flushList(); html.push('<div class="bubble-spacer"></div>'); continue; }

  var hm=trimmed.match(/^(#{1,3})\s+(.+)$/);
  if(hm){ flushList(); html.push('<div class="bubble-h'+hm[1].length+'">'+fmtInline(hm[2])+'</div>'); continue; }

  if(trimmed.startsWith('> ')){ flushList(); html.push('<blockquote class="bubble-quote">'+fmtInline(trimmed.slice(2))+'</blockquote>'); continue; }

  var ulm=trimmed.match(/^[-*]\s+(.+)$/);
  if(ulm){
   if(!inList||listType!=='ul'){ flushList(); html.push('<ul class="bubble-ul">'); inList=true; listType='ul'; }
   html.push('<li>'+fmtInline(ulm[1])+'</li>');
   continue;
  }

  var olm=trimmed.match(/^\d+[.)]\s+(.+)$/);
  if(olm){
   if(!inList||listType!=='ol'){ flushList(); html.push('<ol class="bubble-ol">'); inList=true; listType='ol'; }
   html.push('<li>'+fmtInline(olm[1])+'</li>');
   continue;
  }

  flushList();
  html.push('<div class="bubble-p">'+fmtInline(trimmed)+'</div>');
 }

 flushCode();
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

