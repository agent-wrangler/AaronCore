// ── textarea 自动撑高 ──
(function(){
 var inp=document.getElementById('inp');
 if(!inp)return;
 function autoResize(){
  inp.style.height='auto';
  inp.style.height=Math.min(inp.scrollHeight,280)+'px';
 }
 inp.addEventListener('input',autoResize);
})();

function addMessage(sender,text,type){
 var chat=document.getElementById('chat');
 var msgDiv=document.createElement('div');
 msgDiv.className='msg '+(type==='user'?'user':'assistant');
 
 // 创建头像（确保正确显示）
 var avatar=document.createElement('div');
 avatar.className='avatar';
 if(type==='user'){
  avatar.textContent='你';
  avatar.title='用户';
  avatar.style.background='linear-gradient(135deg, #10b981 0%, #059669 100%)';
 }else{
  avatar.textContent='N';
  avatar.title='Nova AI';
  avatar.style.background='linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
 }
 
 // 创建消息内容区域
 var msgContent=document.createElement('div');
 msgContent.className='msg-content';
 
 // 创建气泡
 var bubble=document.createElement('div');
 bubble.className='bubble';
 bubble.innerHTML=formatBubbleText(text);
 
 // 创建元信息（昵称+时间）
 var msgMeta=document.createElement('div');
 msgMeta.className='msg-meta';
 var nameSpan=document.createElement('span');
 nameSpan.className='msg-name';
 nameSpan.textContent=type==='user'?'你':'Nova';
 var timeSpan=document.createElement('span');
 timeSpan.className='msg-time';
 timeSpan.textContent=T();
 var copyBtn=document.createElement('button');
 copyBtn.className='msg-copy';
 copyBtn.textContent='\u590d\u5236';
 copyBtn.onclick=function(){navigator.clipboard.writeText(text).then(function(){copyBtn.textContent='\u2713';setTimeout(function(){copyBtn.textContent='\u590d\u5236';},1200);});};
 if(type==='user'){
  msgMeta.appendChild(copyBtn);
  msgMeta.appendChild(nameSpan);
  msgMeta.appendChild(timeSpan);
 } else {
  msgMeta.appendChild(nameSpan);
  msgMeta.appendChild(timeSpan);
  msgMeta.appendChild(copyBtn);
 }
 
  // 组装消息
  msgContent.appendChild(bubble);
  msgContent.appendChild(msgMeta);
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(msgContent);
  
  chat.appendChild(msgDiv);
 chat.scrollTop=chat.scrollHeight;
 
 // 保存到历史
 if(type==='user'||type==='assistant'){
  chatHistory+=msgDiv.outerHTML;
  trimChatHistory();
  localStorage.setItem('nova_chat_history',chatHistory);
 }
}

var _thinkingLabels=null; // removed: no more fake rotating labels

function buildPendingAssistantMessage(){
 var msgDiv=document.createElement('div');
 msgDiv.className='msg assistant thinking-msg';

 var avatar=document.createElement('div');
 avatar.className='avatar';
 avatar.textContent='N';
 avatar.title='Nova AI';
 avatar.style.background='linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

 var panel=document.createElement('div');
 panel.className='thinking-panel';

 var stack=document.createElement('div');
 stack.className='thinking-stack';

 var status=document.createElement('div');
 status.className='thinking-status';
 status.innerHTML='<div class="thinking"><span></span><span></span><span></span></div><span class="thinking-status-text">\u601d\u8003\u4e2d</span>';

 var meta=document.createElement('div');
 meta.className='msg-meta';
 var nameSpan=document.createElement('span');
 nameSpan.className='msg-name';
 nameSpan.textContent='Nova';
 var timeSpan=document.createElement('span');
 timeSpan.className='msg-time';
 timeSpan.textContent=T();
 meta.appendChild(nameSpan);
 meta.appendChild(timeSpan);

 panel.appendChild(stack);
 panel.appendChild(status);
 panel.appendChild(meta);
 msgDiv.appendChild(avatar);
 msgDiv.appendChild(panel);

 return {
  root: msgDiv,
  panel: panel,
  stack: stack,
  status: status,
  meta: meta,
  labelTimer: null,
  persisted: false
 };
}

function finalizePendingAssistantMessage(pendingState, replyText){
 if(!pendingState || !pendingState.root) return;
 if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
 // Convert to simple message bubble
 var root=pendingState.root;
 var avatar=root.querySelector('.avatar');
 var panel=root.querySelector('.thinking-panel');
 if(panel) root.removeChild(panel);
 root.className='msg assistant';
 var msgContent=document.createElement('div');
 msgContent.className='msg-content';
 var bubble=document.createElement('div');
 bubble.className='bubble';
 bubble.innerHTML=formatBubbleText(replyText);
 var meta=document.createElement('div');
 meta.className='msg-meta';
 var nameSpan=document.createElement('span');
 nameSpan.className='msg-name';
 nameSpan.textContent='Nova';
 var timeSpan=document.createElement('span');
 timeSpan.className='msg-time';
 timeSpan.textContent=T();
 meta.appendChild(nameSpan);
 meta.appendChild(timeSpan);
 msgContent.appendChild(bubble);
 msgContent.appendChild(meta);
 root.appendChild(msgContent);
 if(!pendingState.persisted){
  chatHistory+=root.outerHTML;
  trimChatHistory();
  localStorage.setItem('nova_chat_history',chatHistory);
  pendingState.persisted=true;
 }
}

function showRepairBar(repair){
 if(!repair || !repair.show) return;
 var bar=document.getElementById('repairBar');
 var headline=document.getElementById('repairHeadline');
 var detail=document.getElementById('repairDetail');
 var progress=document.getElementById('repairProgress');
 if(!bar||!headline||!detail||!progress) return;

 if(bar._repairTimer){ clearInterval(bar._repairTimer); bar._repairTimer=null; }
 headline.textContent=repair.headline||'\u5df2\u8bb0\u5f55\u53cd\u9988';
 detail.textContent=repair.detail||'';
 progress.style.width=(repair.progress||20)+'%';
 bar.style.display='';

 if(repair.watch && repair.poll_ms && repair.max_polls){
  var polls=0;
  var maxPolls=repair.max_polls||10;
  var interval=repair.poll_ms||1600;
  bar._repairTimer=setInterval(function(){
   polls++;
   var pct=Math.min(22+Math.round((polls/maxPolls)*68), 90);
   progress.style.width=pct+'%';
   if(polls>=maxPolls){
    clearInterval(bar._repairTimer); bar._repairTimer=null;
    progress.style.width='100%';
    detail.textContent='\u540e\u53f0\u5b66\u4e60\u4efb\u52a1\u5df2\u5b8c\u6210\u3002';
    setTimeout(function(){ hideRepairBar(); }, 3000);
   }
  }, interval);
 }else{
  setTimeout(function(){ hideRepairBar(); }, 6000);
 }
}

function hideRepairBar(){
 var bar=document.getElementById('repairBar');
 if(!bar) return;
 if(bar._repairTimer){ clearInterval(bar._repairTimer); bar._repairTimer=null; }
 bar.style.display='none';
}

// cleanInlineText is in utils.js

function createProcessBubble(card){
 var bubble=document.createElement('div');
 bubble.className='thinking-bubble done';

 var body=document.createElement('div');
 body.className='thinking-bubble-body';

 var label=document.createElement('div');
 label.className='thinking-bubble-label';
 label.textContent=card.label||'过程';

 var detail=document.createElement('div');
 detail.className='thinking-bubble-text';
 detail.textContent=card.detail||'';

 body.appendChild(label);
 body.appendChild(detail);
 bubble.appendChild(body);
 return bubble;
}

async function send(){
 AwarenessManager.stopPolling();
 if(typeof hideWelcome==='function') hideWelcome();
 var inp=document.getElementById('inp');
 var text=inp.value.trim();
 if(text==='')return;

 addMessage('\u4f60',text,'user');
 inp.value='';
 inp.style.height='auto';
 updateSendButton();

 var btn=document.getElementById('sendBtn');
 btn.disabled=true;
 btn.classList.add('sending');
 setTimeout(function(){btn.classList.remove('sending');},500);
 var pendingState=buildPendingAssistantMessage();
 var chat=document.getElementById('chat');
 chat.appendChild(pendingState.root);
 chat.scrollTop=chat.scrollHeight;

 var replyText='';
 var repairData=null;
 var hasTrace=false;

 function addTraceCard(card){
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  hasTrace=true;
  var statusText=pendingState.status.querySelector('.thinking-status-text');
  if(statusText){
   statusText.textContent=card.detail||card.label||'';
   statusText.style.animation='none';
   statusText.offsetHeight;
   statusText.style.animation='statusFade 0.5s ease';
  }
  chat.scrollTop=chat.scrollHeight;
 }

 function showFinalReply(text){
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  if(pendingState.status && pendingState.status.parentNode){
   pendingState.status.parentNode.removeChild(pendingState.status);
  }
  var panel=pendingState.panel;
  if(panel) panel.parentNode.removeChild(panel);
  pendingState.root.className='msg assistant';
  var msgContent=document.createElement('div');
  msgContent.className='msg-content';
  var bubble=document.createElement('div');
  bubble.className='bubble';
  var meta=document.createElement('div');
  meta.className='msg-meta';
  var nameSpan=document.createElement('span');
  nameSpan.className='msg-name';
  nameSpan.textContent='Nova';
  var timeSpan=document.createElement('span');
  timeSpan.className='msg-time';
  timeSpan.textContent=T();
  meta.appendChild(nameSpan);
  meta.appendChild(timeSpan);
  var cpBtn=document.createElement('button');
  cpBtn.className='msg-copy';
  cpBtn.textContent='\u590d\u5236';
  cpBtn.onclick=function(){navigator.clipboard.writeText(text).then(function(){cpBtn.textContent='\u2713';setTimeout(function(){cpBtn.textContent='\u590d\u5236';},1200);});};
  meta.appendChild(cpBtn);
  msgContent.appendChild(bubble);
  msgContent.appendChild(meta);
  pendingState.root.appendChild(msgContent);

  // ── 打字机效果 ──
  var chars=Array.from(text);
  var idx=0;
  var speed=30; // 每字 30ms
  var cursor=document.createElement('span');
  cursor.className='typing-cursor';
  bubble.appendChild(cursor);

  function typeNext(){
   if(idx>=chars.length){
    // 打完了：移除光标，格式化 markdown
    if(cursor.parentNode) cursor.parentNode.removeChild(cursor);
    bubble.innerHTML=formatBubbleText(text);
    chat.scrollTop=chat.scrollHeight;
    if(!pendingState.persisted){
     chatHistory+=pendingState.root.outerHTML;
     trimChatHistory();
     localStorage.setItem('nova_chat_history',chatHistory);
     pendingState.persisted=true;
    }
    return;
   }
   var ch=chars[idx];
   bubble.insertBefore(document.createTextNode(ch), cursor);
   idx++;
   chat.scrollTop=chat.scrollHeight;
   // 标点符号稍微停顿
   var delay=speed;
   if('，。！？、；：…'.indexOf(ch)>=0) delay=speed*3;
   else if(',.!?;:'.indexOf(ch)>=0) delay=speed*2;
   else if(ch==='\n') delay=speed*2;
   setTimeout(typeNext, delay);
  }
  typeNext();
 }

 try{
  var resp=await fetch('/chat',{
   method:'POST',
   headers:{'Content-Type':'application/json; charset=utf-8','Accept':'text/event-stream'},
   body:JSON.stringify({message:String(text)})
  });

  var reader=resp.body.getReader();
  var decoder=new TextDecoder();
  var buffer='';

  while(true){
   var result=await reader.read();
   if(result.done) break;
   buffer+=decoder.decode(result.value, {stream:true});

   var lines=buffer.split('\n');
   buffer=lines.pop();

   var currentEvent='';
   var currentData='';
   for(var i=0;i<lines.length;i++){
    var line=lines[i].trim();
    if(line.startsWith('event:')){
     currentEvent=line.slice(6).trim();
    }else if(line.startsWith('data:')){
     currentData=line.slice(5).trim();
    }else if(line===''){
     if(currentEvent && currentData){
      try{
       var parsed=JSON.parse(currentData);
       if(currentEvent==='trace'){
        addTraceCard(parsed);
       }else if(currentEvent==='reply'){
        replyText=parsed.reply||'\u6211\u521a\u521a\u6ca1\u63a5\u597d\uff0c\u4f60\u518d\u53d1\u6211\u4e00\u6b21\u561b\u3002';
       }else if(currentEvent==='repair'){
        repairData=parsed;
       }else if(currentEvent==='awareness'){
        AwarenessManager.handleEvent(parsed);
       }
      }catch(e){}
     }
     currentEvent='';
     currentData='';
    }
   }
  }

  if(replyText){
   showFinalReply(replyText);
  }else{
   finalizePendingAssistantMessage(pendingState, '\u6211\u521a\u521a\u6ca1\u63a5\u597d\uff0c\u4f60\u518d\u53d1\u6211\u4e00\u6b21\u561b\u3002');
  }
  if(repairData && repairData.show){ showRepairBar(repairData); }
  AwarenessManager.startPolling();
 }catch(e){
  finalizePendingAssistantMessage(pendingState, '\u540e\u7aef\u8fde\u63a5\u5931\u8d25\u5566\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u8bd5\u3002');
 }
 chat.scrollTop=chat.scrollHeight;
 setTimeout(updateSendButton,100);
}
