// ── textarea 自动撑高 ──
var _pendingImages = []; // base64 图片暂存（支持多张）
var MAX_IMAGES = 4;
var _abortController = null; // 用于中断 SSE 请求

var _sendSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 18V6.5" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/><path d="M7 11.2L12 6.5L17 11.2" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/></svg>';
var _stopSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>';
var _taskProgressWorkingSvg = '<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="8" cy="8" r="5.25" stroke="currentColor" stroke-opacity="0.35" stroke-width="1.5"/><circle cx="8" cy="8" r="2.4" fill="currentColor"/></svg>';
var _taskProgressDoneSvg = '<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><circle cx="8" cy="8" r="5.25" stroke="currentColor" stroke-width="1.5"/><path d="M5.1 8.1L7.1 10.1L11 6.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function _processMarkerText(label, status){
 var text=String(label||'');
 if(status==='error') return '!';
 if(/思考|thinking/i.test(text)) return '∴';
 if(/计划|plan/i.test(text)) return '⌁';
 return status==='running' ? '›' : '·';
}

(function(){
 var inp=document.getElementById('inp');
 if(!inp)return;
 function autoResize(){
  var maxH=Math.floor(window.innerHeight*0.4);
  // 先临时设 auto 让浏览器算出真实 scrollHeight，但用 overflow:hidden 防止闪烁
  var prevOverflow=inp.style.overflow;
  inp.style.overflow='hidden';
  inp.style.height='auto';
  var sh=inp.scrollHeight;
  inp.style.height=Math.min(sh,maxH)+'px';
  inp.style.overflow=prevOverflow||'';
 }
 inp.addEventListener('input',function(){ autoResize(); updateSendButton(); });

 // 动态 Placeholder 轮换
 var _placeholders=['与 Nova 对话...','向 Nova 提问...','粘贴代码进行分析...','聊聊你的想法...','描述你需要的帮助...'];
 var _phIdx=0;
 setInterval(function(){
  if(inp===document.activeElement||inp.value.trim()) return;
  _phIdx=(_phIdx+1)%_placeholders.length;
  inp.setAttribute('placeholder',_placeholders[_phIdx]);
 },8000);

 // 粘贴图片拦截
 inp.addEventListener('paste',function(e){
  var items=e.clipboardData&&e.clipboardData.items;
  if(!items)return;
  for(var i=0;i<items.length;i++){
   if(items[i].type.indexOf('image')!==-1){
    e.preventDefault();
    var file=items[i].getAsFile();
    if(file) readImageFile(file);
    return;
   }
  }
 });
})();

function readImageFile(file){
 if(!file||file.size>10*1024*1024)return;
 if(_pendingImages.length>=MAX_IMAGES) return;
 var reader=new FileReader();
 reader.onload=function(e){
  _pendingImages.push(e.target.result);
  renderImagePreviews();
  updateSendButton();
 };
 reader.readAsDataURL(file);
}

function handleImageFile(input){
 if(input.files){
  for(var i=0;i<input.files.length&&_pendingImages.length<MAX_IMAGES;i++){
   readImageFile(input.files[i]);
  }
 }
 input.value='';
}

function renderImagePreviews(){
 var bar=document.getElementById('imagePreviewBar');
 if(!bar)return;
 bar.innerHTML='';
 if(_pendingImages.length===0){ bar.style.display='none'; return; }
 bar.style.display='flex';
 _pendingImages.forEach(function(dataUrl,idx){
  var item=document.createElement('div');
  item.className='image-preview-item';
  var img=document.createElement('img');
  img.src=dataUrl; img.alt='preview';
  var btn=document.createElement('button');
  btn.className='image-preview-remove';
  btn.title=t('chat.remove.image');
  btn.innerHTML='&times;';
  btn.onclick=function(){ removeImageAt(idx); };
  item.appendChild(img);
  item.appendChild(btn);
  bar.appendChild(item);
 });
}

function removeImageAt(idx){
 _pendingImages.splice(idx,1);
 renderImagePreviews();
 updateSendButton();
}

function removeImagePreview(){
 _pendingImages=[];
 renderImagePreviews();
 updateSendButton();
}

function _enterStopMode(){
 var btn=document.getElementById('sendBtn');
 btn.disabled=false;
 btn.classList.add('stop-mode');
 btn.innerHTML=_stopSvg;
}

function _exitStopMode(){
 var btn=document.getElementById('sendBtn');
 btn.classList.remove('stop-mode');
 btn.innerHTML=_sendSvg;
 updateSendButton();
}

function _stopGeneration(){
 if(_abortController){
  _abortController.abort();
  _abortController=null;
 }
}

function addMessage(sender,text,type,imageUrl){
 var chat=document.getElementById('chat');
 var msgDiv=document.createElement('div');
 msgDiv.className='msg '+(type==='user'?'user':'assistant');
 
 // 创建头像（确保正确显示）
 var avatar=document.createElement('div');
 avatar.className='avatar';
 if(type==='user'){
  avatar.textContent=t('chat.you');
  avatar.title=t('chat.you');
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
 if(imageUrl){
  var img=document.createElement('img');
  img.className='bubble-image';
  img.src=imageUrl;
  img.alt='图片';
  bubble.appendChild(img);
 }
 if(text){
  var textNode=document.createElement('div');
  textNode.className='bubble-body';
  // 用户消息不做 markdown 渲染，直接显示纯文本
  if(type==='user'){
   textNode.textContent=text;
  }else{
   textNode.innerHTML=formatBubbleText(text);
  }
  bubble.appendChild(textNode);
 }
 
 // 创建元信息（昵称+时间）
 var msgMeta=document.createElement('div');
 msgMeta.className='msg-meta';
 var nameSpan=document.createElement('span');
 nameSpan.className='msg-name';
 nameSpan.textContent=type==='user'?t('chat.you'):'Nova';
 var timeSpan=document.createElement('span');
 timeSpan.className='msg-time';
 timeSpan.textContent=T();
 var copyBtn=document.createElement('button');
 copyBtn.className='msg-copy';
 copyBtn.textContent=t('chat.copy');
 copyBtn.onclick=function(){navigator.clipboard.writeText(text).then(function(){copyBtn.textContent=t('chat.copied');setTimeout(function(){copyBtn.textContent=t('chat.copy');},1200);});};
 if(type==='user'){
  msgMeta.appendChild(copyBtn);
  msgMeta.appendChild(nameSpan);
  msgMeta.appendChild(timeSpan);
 } else {
  msgMeta.appendChild(nameSpan);
  msgMeta.appendChild(timeSpan);
  msgMeta.appendChild(copyBtn);
 }
 
  // 组装消息：meta（昵称+时间）在上，bubble 在下
  msgContent.appendChild(msgMeta);
  msgContent.appendChild(bubble);
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

function _snapshotChatHistory(){
 var chat=document.getElementById('chat');
 if(!chat) return;
 chatHistory=chat.innerHTML;
 trimChatHistory();
 localStorage.setItem('nova_chat_history',chatHistory);
}

function _createNovaAvatar(){
 var avatar=document.createElement('div');
 avatar.className='avatar';
 avatar.textContent='N';
 avatar.title='Nova AI';
 avatar.style.background='linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
 return avatar;
}

var _thinkingLabels=null; // removed: no more fake rotating labels

function buildPendingAssistantMessage(){
 var msgDiv=document.createElement('div');
 msgDiv.className='msg assistant thinking-msg';

 var avatar=_createNovaAvatar();

 var wrap=document.createElement('div');
 wrap.className='msg-content-wrap';

 var planStrip=document.createElement('div');
 planStrip.className='plan-strip';
 planStrip.style.display='none';

 var tracker=document.createElement('div');
 tracker.className='step-tracker';
 tracker.classList.add('collapsed');
 tracker.style.display='none';

 var status=document.createElement('button');
 status.type='button';
 status.className='step-tracker-status running';
 status.setAttribute('aria-expanded','false');
 status.innerHTML=''
  +'<span class="step-tracker-status-main">'
  +'<span class="step-tracker-spinner running" aria-hidden="true"></span>'
  +'<span class="step-tracker-title">Thinking</span>'
  +'</span>'
  +'<span class="step-tracker-summary"></span>'
  +'<span class="step-tracker-toggle-text"></span>';
 status.style.display='';

 var contentArea=document.createElement('div');
 contentArea.className='msg-content';
 contentArea.style.display='none';

 wrap.appendChild(status);
 wrap.appendChild(planStrip);
 wrap.appendChild(tracker);
 wrap.appendChild(contentArea);
 msgDiv.appendChild(avatar);
 msgDiv.appendChild(wrap);

 return {
  root: msgDiv,
  wrap: wrap,
  planStrip: planStrip,
  tracker: tracker,
  status: status,
  statusSpinner: status.querySelector('.step-tracker-spinner'),
  statusSummary: status.querySelector('.step-tracker-summary'),
  statusToggle: status.querySelector('.step-tracker-toggle-text'),
  contentArea: contentArea,
  plan: null,
  steps: [],
  stepsExpanded: false,
  userToggledSteps: false,
  activitySummary: '',
  traceRoot: null,
  traceWrap: null,
  traceDetached: false,
  labelTimer: null,
  placeholderTimer: null,
  replyVisible: false,
  persisted: false
 };
}

function _detachTraceMessageForPendingState(pendingState){
 if(!pendingState || pendingState.traceDetached || !(pendingState.steps&&pendingState.steps.length)) return;
 var chat=document.getElementById('chat');
 if(chat && pendingState.root && pendingState.root.parentNode!==chat){
  chat.appendChild(pendingState.root);
 }
 var traceRoot=document.createElement('div');
 traceRoot.className='msg assistant thinking-msg thinking-trace-msg';
 var traceWrap=document.createElement('div');
 traceWrap.className='msg-content-wrap';
 traceRoot.appendChild(_createNovaAvatar());
 traceRoot.appendChild(traceWrap);
 if(pendingState.status.parentNode===pendingState.wrap) pendingState.wrap.removeChild(pendingState.status);
 if(pendingState.planStrip.parentNode===pendingState.wrap) pendingState.wrap.removeChild(pendingState.planStrip);
 if(pendingState.tracker.parentNode===pendingState.wrap) pendingState.wrap.removeChild(pendingState.tracker);
 traceWrap.appendChild(pendingState.status);
 traceWrap.appendChild(pendingState.planStrip);
 traceWrap.appendChild(pendingState.tracker);
 if(pendingState.root && pendingState.root.parentNode){
  pendingState.root.parentNode.insertBefore(traceRoot, pendingState.root);
 }
 pendingState.traceRoot=traceRoot;
 pendingState.traceWrap=traceWrap;
 pendingState.traceDetached=true;
}

function finalizePendingAssistantMessage(pendingState, replyText){
 if(!pendingState || !pendingState.root) return;
 if(pendingState.placeholderTimer){
  clearTimeout(pendingState.placeholderTimer);
  pendingState.placeholderTimer=null;
 }
 var chat=document.getElementById('chat');
 if(chat){
  chat.appendChild(pendingState.root);
 }
 pendingState.replyVisible=true;
 if(typeof window._clearAskUserSlot==='function') window._clearAskUserSlot();
 if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
 var _stepCount=(pendingState.steps&&pendingState.steps.length)?pendingState.steps.length:0;
 var _finalState='done';
 if(_stepCount){
  for(var si=0;si<pendingState.steps.length;si++){
   var step=pendingState.steps[si];
   if(!step) continue;
   if(step.status==='error') _finalState='error';
   if(step.status==='running') step.status='done';
   if(step.kind==='process'){
    if(step.root) step.root.className='msg assistant process-msg';
    if(step.line) step.line.className='process-line done';
   }else{
    if(step.el) step.el.className='step-item '+(step.status||'done');
    if(step.iconEl) step.iconEl.className='step-icon '+(step.status||'done');
   }
  }
 }
 if(pendingState.status){
  pendingState.status.style.display=_stepCount?'':'none';
  pendingState.status.classList.remove('running','done','error','expanded','has-steps');
  pendingState.status.classList.add(_finalState);
  if(_stepCount) pendingState.status.classList.add('has-steps');
  if(_stepCount && pendingState.stepsExpanded) pendingState.status.classList.add('expanded');
  if(pendingState.statusSpinner){
   pendingState.statusSpinner.className='step-tracker-spinner '+_finalState;
  }
  if(pendingState.statusToggle){
   pendingState.statusToggle.textContent=_stepCount
    ?(pendingState.stepsExpanded?'\u6536\u8d77\u6b65\u9aa4':('\u5c55\u5f00\u6b65\u9aa4 \u00b7 '+_stepCount))
    :'';
  }
  pendingState.status.setAttribute('aria-expanded', pendingState.stepsExpanded?'true':'false');
 }
 if(pendingState.tracker){
  pendingState.tracker.style.display=(_stepCount&&pendingState.stepsExpanded)?'flex':'none';
  pendingState.tracker.classList.toggle('collapsed', !pendingState.stepsExpanded);
 }
 if(_stepCount) _detachTraceMessageForPendingState(pendingState);
 pendingState.root.className='msg assistant';
 var contentArea=pendingState.contentArea;
 if(!contentArea){
  contentArea=document.createElement('div');
  contentArea.className='msg-content';
  pendingState.wrap.appendChild(contentArea);
 }
 contentArea.style.display='';
 contentArea.innerHTML='';
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
 contentArea.appendChild(meta);
 contentArea.appendChild(bubble);
 if(!pendingState.persisted){
  _snapshotChatHistory();
  pendingState.persisted=true;
 }
 if(_sessionTaskPlan){
  var _reply=String(replyText||'');
  if(_isTaskPlanTerminal(_sessionTaskPlan) || /执行失败|当前聊天失败|后端连接失败|已停止|没接稳/.test(_reply)){
   _scheduleTaskPlanClear(1800);
  }
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
 headline.textContent=repair.headline||t('repair.recorded');
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
    detail.textContent=t('repair.done');
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

function createProcessMessage(card){
 var msgDiv=document.createElement('div');
 msgDiv.className='msg assistant process-msg';
 var content=document.createElement('div');
 content.className='msg-content process-content';
 var line=document.createElement('div');
 var status=String((card&&card.status)||'running');
 line.className='process-line '+(status==='error'?'error':(status==='running'?'running':'done'));
 var marker=document.createElement('span');
 marker.className='process-marker';
 marker.textContent=_processMarkerText(card&&card.label, status);
 var label=document.createElement('span');
 label.className='process-label';
 label.textContent=String((card&&card.label)||'')||t('chat.process');
 var detail=document.createElement('span');
 detail.className='process-detail';
 detail.textContent=String((card&&card.detail)||'');
 line.appendChild(marker);
 line.appendChild(label);
 line.appendChild(detail);
 content.appendChild(line);
 msgDiv.appendChild(_createNovaAvatar());
 msgDiv.appendChild(content);
 return {
  kind:'process',
  root:msgDiv,
  content:content,
  line:line,
  markerEl:marker,
  labelEl:label,
  detailEl:detail,
  label:String((card&&card.label)||''),
  status:status,
  summaryDetail:'',
  fullDetail:''
 };
}

function createReplyPartMessage(html){
 var msgDiv=document.createElement('div');
 msgDiv.className='msg assistant reply-part-msg';
 var content=document.createElement('div');
 content.className='msg-content';
 var bubble=document.createElement('div');
 bubble.className='bubble';
 bubble.innerHTML=String(html||'');
 content.appendChild(bubble);
 msgDiv.appendChild(_createNovaAvatar());
 msgDiv.appendChild(content);
 return {
  root:msgDiv,
  bubble:bubble
 };
}

async function send(){
 AwarenessManager.stopPolling();
 if(typeof hideWelcome==='function') hideWelcome();
 if(typeof window._clearSessionTaskPlan==='function') window._clearSessionTaskPlan();
 if(typeof window._clearAskUserSlot==='function') window._clearAskUserSlot();
 var inp=document.getElementById('inp');
 var text=inp.value.trim();
 var images=_pendingImages.slice();
 var image=images.length>0?images[0]:null;
 if(text===''&&!image)return;

 addMessage(t('chat.you'),text,'user',image);
 inp.value='';
 inp.style.height='auto';
 _pendingImages=[];
 renderImagePreviews();
 updateSendButton();

 var btn=document.getElementById('sendBtn');
 btn.classList.add('sending');
 setTimeout(function(){btn.classList.remove('sending');},500);
 _enterStopMode();
 var pendingState=buildPendingAssistantMessage();
 var chat=document.getElementById('chat');

 var replyText='';
 var replyImage='';
 var _thinkingContent='';
 var _showRawThinkingPanel=false;
  var repairData=null;
  var hasTrace=false;
  var _streamBubble=null; // 流式输出的气泡
  var _streamText=''; // 流式累积的文本
  var _streamStarted=false;

 function _clearPendingPlaceholderTimer(){
  if(pendingState.placeholderTimer){
   clearTimeout(pendingState.placeholderTimer);
   pendingState.placeholderTimer=null;
  }
 }

 function _placePendingRootAtEnd(){
  _clearPendingPlaceholderTimer();
  chat.appendChild(pendingState.root);
  pendingState.replyVisible=true;
 }

 function _detachIdlePendingRoot(){
  if(!pendingState.root || pendingState.replyVisible) return;
  if(pendingState.root.parentNode){
   pendingState.root.parentNode.removeChild(pendingState.root);
  }
 }

 pendingState.placeholderTimer=setTimeout(function(){
  if(pendingState.replyVisible || pendingState.steps.length>0 || replyText) return;
  chat.appendChild(pendingState.root);
  chat.scrollTop=chat.scrollHeight;
 },260);

 var _streamParts=[];

 function _clearStreamParts(){
  while(_streamParts.length){
   var part=_streamParts.pop();
   if(part && part.root && part.root.parentNode){
    part.root.parentNode.removeChild(part.root);
   }
  }
 }

 function _ensureTraceDetached(){
  _placePendingRootAtEnd();
  _detachTraceMessageForPendingState(pendingState);
 }

 function _looksLikeThinkingLabel(label){
  return /thinking|\u6a21\u578b\u601d\u8003/i.test(String(label||''));
 }

 function _extractToolKey(detail){
  var text=String(detail||'').trim();
  if(!text) return '';
  var parts=text.split(/\s*[\u00b7\u2022]\s*/);
  var head=String(parts[0]||'').trim();
  if(!head && parts.length>1) head=String(parts[1]||'').trim();
  return head.toLowerCase();
 }

 function _normalizeStepCard(card){
  var rawLabel=String((card&&card.label)||'').trim();
  var rawStatus=String((card&&card.status)||'running');
  var state=(rawStatus==='error'?'error':(rawStatus==='running'?'running':'done'));
  var summaryDetail=String((card&&card.detail)||'').trim();
  var fullDetail=String((card&&((card.full_detail&&String(card.full_detail).trim())||card.detail))||'').trim();
  var phase='info';
  var displayLabel=rawLabel||t('chat.process');
  if(_looksLikeThinkingLabel(rawLabel)){
   phase='thinking';
   displayLabel='Thinking';
  }else if(rawLabel==='\u8c03\u7528\u6280\u80fd'){
   phase='tool';
   displayLabel='\u8c03\u7528';
  }else if(rawLabel==='\u6280\u80fd\u5b8c\u6210'){
   phase='tool';
   displayLabel='\u5b8c\u6210';
  }else if(rawLabel==='\u6280\u80fd\u5931\u8d25'){
   phase='tool';
   displayLabel='\u5931\u8d25';
  }else if(/\u7b49\u5f85|waiting/i.test(rawLabel)){
   phase='waiting';
   displayLabel='\u7b49\u5f85';
  }
  return {
   rawLabel:rawLabel,
   status:state,
   phase:phase,
   displayLabel:displayLabel,
   summaryDetail:summaryDetail,
   fullDetail:fullDetail,
   toolKey:phase==='tool' ? _extractToolKey(summaryDetail) : ''
  };
 }

 function _buildActivitySummary(meta){
  if(!meta) return '';
  var detail=String(meta.summaryDetail||meta.fullDetail||'').trim();
  if(!detail) return meta.displayLabel||'';
  if(meta.phase==='thinking') return detail;
  if(detail.indexOf(meta.displayLabel)===0) return detail;
  return meta.displayLabel+' \u00b7 '+detail;
 }

 function _hasErroredSteps(){
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i] && pendingState.steps[i].status==='error') return true;
  }
  return false;
 }

 function _hasRunningSteps(){
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i] && pendingState.steps[i].status==='running') return true;
  }
  return false;
 }

 function _syncTrackerChrome(){
  var hasSteps=pendingState.steps.length>0;
  var state='done';
  if(_hasErroredSteps()) state='error';
  else if(_hasRunningSteps() || (!hasSteps && !_streamStarted && !replyText)) state='running';
  pendingState.status.style.display=(hasTrace||hasSteps||!replyText)?'':'none';
  pendingState.status.classList.remove('running','done','error','expanded','has-steps');
  pendingState.status.classList.add(state);
  if(hasSteps) pendingState.status.classList.add('has-steps');
  if(hasSteps && pendingState.stepsExpanded) pendingState.status.classList.add('expanded');
  if(pendingState.statusSpinner){
   pendingState.statusSpinner.className='step-tracker-spinner '+state;
  }
  if(pendingState.statusSummary){
   pendingState.statusSummary.textContent=String(pendingState.activitySummary||'').trim();
  }
  if(pendingState.statusToggle){
   pendingState.statusToggle.textContent=hasSteps ? (pendingState.stepsExpanded ? '\u6536\u8d77\u6b65\u9aa4' : ('\u5c55\u5f00\u6b65\u9aa4 \u00b7 '+pendingState.steps.length)) : '';
  }
  pendingState.status.setAttribute('aria-expanded', (hasSteps && pendingState.stepsExpanded)?'true':'false');
  if(pendingState.tracker){
   pendingState.tracker.style.display=(hasSteps && pendingState.stepsExpanded)?'flex':'none';
   pendingState.tracker.classList.toggle('collapsed', !(hasSteps && pendingState.stepsExpanded));
  }
 }

 function _setTrackerExpanded(expanded, userTriggered){
  pendingState.stepsExpanded=!!expanded;
  if(userTriggered) pendingState.userToggledSteps=true;
  _syncTrackerChrome();
 }

 pendingState.status.addEventListener('click', function(){
  if(!pendingState.steps.length) return;
  _setTrackerExpanded(!pendingState.stepsExpanded, true);
 });

 _syncTrackerChrome();

 function _setStepStatus(stepObj, newStatus){
  if(!stepObj) return;
  stepObj.status=newStatus;
  if(stepObj.kind==='process'){
   stepObj.root.className='msg assistant process-msg'+(newStatus==='running'?' is-running':'')+(newStatus==='error'?' is-error':'');
   if(stepObj.line) stepObj.line.className='process-line '+(newStatus==='error'?'error':(newStatus==='running'?'running':'done'));
   if(stepObj.markerEl) stepObj.markerEl.textContent=_processMarkerText(stepObj.label, newStatus);
   return;
  }
  stepObj.el.className='step-item '+newStatus;
  if(stepObj.iconEl) stepObj.iconEl.className='step-icon '+newStatus;
 }

 function _applyStepDetail(stepObj, detail, fullDetail){
  if(!stepObj || !stepObj.detailEl) return;
  stepObj.summaryDetail=String(detail||'').trim();
  stepObj.fullDetail=String(fullDetail||'').trim();
 if(stepObj.kind==='process'){
  if(stepObj.labelEl) stepObj.labelEl.textContent=stepObj.label||t('chat.process');
  stepObj.detailEl.textContent=stepObj.fullDetail||stepObj.summaryDetail;
  return;
 }
 stepObj.detailEl.textContent=stepObj.fullDetail||stepObj.summaryDetail;
  if(stepObj.status==='running'){
   pendingState.activitySummary=_buildActivitySummary({
    displayLabel:stepObj.displayLabel||stepObj.label||t('chat.process'),
    summaryDetail:stepObj.summaryDetail,
    fullDetail:stepObj.fullDetail,
    phase:stepObj.phase||'info'
   });
   _syncTrackerChrome();
  }
 }

 function _applyStepMeta(stepObj, meta){
  if(!stepObj || !meta) return;
  stepObj.label=meta.rawLabel;
  stepObj.phase=meta.phase;
  stepObj.toolKey=meta.toolKey;
  stepObj.displayLabel=meta.displayLabel;
  if(stepObj.labelEl) stepObj.labelEl.textContent=meta.displayLabel||t('chat.process');
  _applyStepDetail(stepObj, meta.summaryDetail, meta.fullDetail);
 }

 function _createActivityStep(meta){
  var el=document.createElement('div');
  el.className='step-item '+meta.status;
  var icon=document.createElement('span');
  icon.className='step-icon '+meta.status;
  var main=document.createElement('div');
  main.className='step-main';
  var labelEl=document.createElement('span');
  labelEl.className='step-label';
  labelEl.textContent=meta.displayLabel||t('chat.process');
  var detailEl=document.createElement('span');
  detailEl.className='step-detail';
  detailEl.textContent=meta.fullDetail||meta.summaryDetail;
  main.appendChild(labelEl);
  main.appendChild(detailEl);
  el.appendChild(icon);
  el.appendChild(main);
  pendingState.tracker.appendChild(el);
  return {
   kind:'trace',
   el:el,
   iconEl:icon,
   labelEl:labelEl,
   detailEl:detailEl,
   label:meta.rawLabel,
   displayLabel:meta.displayLabel,
   summaryDetail:meta.summaryDetail,
   fullDetail:meta.fullDetail,
   phase:meta.phase,
   toolKey:meta.toolKey,
   status:meta.status
  };
 }

 function _canMergeStep(existing, meta){
  if(!existing || !meta) return false;
  if(existing.phase==='thinking' && meta.phase==='thinking') return true;
  if(existing.phase==='tool' && meta.phase==='tool' && existing.toolKey && existing.toolKey===meta.toolKey) return true;
  if(existing.label===meta.rawLabel && existing.phase===meta.phase) return true;
  return false;
 }

 function _planCssStatus(status){
  status=String(status||'pending');
  if(status==='done') return 'done';
  if(status==='running') return 'running';
  if(status==='waiting_user') return 'waiting-user';
  if(status==='blocked' || status==='error' || status==='failed') return 'error';
  return '';
 }

 function _renderPendingPlan(plan){
  pendingState.plan=null;
  var host=pendingState.planStrip;
  if(host){
   host.style.display='none';
   host.innerHTML='';
  }
  if(!plan || !plan.items || !plan.items.length){
   if(typeof window._clearSessionTaskPlan==='function'){
    window._clearSessionTaskPlan();
   }
   return;
  }
  pendingState.plan=plan;
  if(host){
   host.style.display='';
   var goal=document.createElement('div');
   goal.className='plan-goal';
   goal.textContent=String(plan.goal||'当前任务');
   host.appendChild(goal);
   var summaryText=String(plan.summary||'').trim();
   if(summaryText){
    var summary=document.createElement('div');
    summary.className='plan-summary';
    summary.textContent=summaryText;
    host.appendChild(summary);
   }
   var items=document.createElement('div');
   items.className='plan-items';
   (plan.items||[]).forEach(function(item){
    var chip=document.createElement('div');
    chip.className='plan-item';
    var cssStatus=_planCssStatus(item&&item.status);
    if(cssStatus) chip.classList.add(cssStatus);
    chip.textContent=String((item&&item.title)||'');
    items.appendChild(chip);
   });
   host.appendChild(items);
  }
  if(typeof window._setSessionTaskPlan==='function'){
   window._setSessionTaskPlan(plan);
  }
 }

 function addStep(card){
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  _clearPendingPlaceholderTimer();
  hasTrace=true;
  var meta=_normalizeStepCard(card);
  pendingState.activitySummary=_buildActivitySummary(meta);
  _placePendingRootAtEnd();

  var steps=pendingState.steps;
  var last=steps.length>0 ? steps[steps.length-1] : null;
  var mergeTarget=null;
  if(last && _canMergeStep(last, meta)){
   mergeTarget=last;
  }else if(meta.phase==='tool' && meta.status!=='running'){
   for(var mi=steps.length-1;mi>=0;mi--){
    if(steps[mi] && steps[mi].status==='running' && _canMergeStep(steps[mi], meta)){
     mergeTarget=steps[mi];
     break;
    }
   }
  }

  if(mergeTarget){
   _applyStepMeta(mergeTarget, meta);
   _setStepStatus(mergeTarget, meta.status);
  }else{
   if(last && last.status==='running' && !_canMergeStep(last, meta)){
    _setStepStatus(last,'done');
   }
   steps.push(_createActivityStep(meta));
  }

  if(meta.status==='error'){
   _setTrackerExpanded(true, false);
  }else if(!pendingState.userToggledSteps){
   _setTrackerExpanded(steps.length<=2, false);
  }else{
   _syncTrackerChrome();
  }
  chat.scrollTop=chat.scrollHeight;
 }

 function _collapseSteps(){
  var steps=pendingState.steps;
  if(steps.length===0){
   _syncTrackerChrome();
   return;
  }
  for(var i=0;i<steps.length;i++){
   if(steps[i].status==='running') _setStepStatus(steps[i],'done');
  }
  pendingState.userToggledSteps=false;
  _setTrackerExpanded(_hasErroredSteps(), false);
 }

 function _initStreamBubble(){
  // 把所有 running 步骤标记为 done
  _placePendingRootAtEnd();
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i].status==='running') _setStepStatus(pendingState.steps[i],'done');
  }
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  _collapseSteps();
  if(pendingState.steps.length) _ensureTraceDetached();
  // 隐藏 spinner，显示内容区
  pendingState.status.style.display=pendingState.steps.length?'':'none';
  pendingState.root.className='msg assistant';
  var contentArea=pendingState.contentArea;
  contentArea.style.display='';
  contentArea.innerHTML='';
  var bubble=document.createElement('div');
  bubble.className='bubble';
  var cursor=document.createElement('span');
  cursor.className='typing-cursor';
  bubble.appendChild(cursor);
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
  contentArea.appendChild(meta);
  contentArea.appendChild(bubble);
  _streamBubble=bubble;
  _streamStarted=true;
  _streamTokenCount=0;
  _lastRenderedBlockCount=0;
  // 思考步骤结束、回复开始 → 强制滚到底部，确保用户能看到新内容
  chat.scrollTop=chat.scrollHeight;
 }

 var _scrollRAF=0; // scroll 节流
 var _renderTimer=0; // 渐进渲染节流
 var _streamTokenCount=0; // 流式 token 计数，前 N 个无条件滚动
 var _lastRenderedBlockCount=0; // 上次渲染的块数，用于 fade-in 新块

 // 判断是否在底部附近（阈值 120px），避免强制跳视图打断用户回翻
 function _nearBottom(){
  return chat.scrollHeight - chat.scrollTop - chat.clientHeight < 120;
 }

 // ── 渐进式 Markdown 渲染引擎 ──
 // 不再逐字符塞裸文本，而是把累积的 _streamText 整体跑 formatBubbleText，
 // 新出现的块自动带 fade-in 动画，光标始终在末尾。
 function _progressiveRender(){
  _renderTimer=0;
 if(!_streamBubble || !_streamText) return;
  // 用 formatBubbleText 把当前累积文本渲染成结构化 HTML
  var html=formatBubbleText(_streamText);
  // 创建临时容器解析出块元素
  var temp=document.createElement('div');
  temp.innerHTML=html;
  var blocks=[];
  while(temp.firstChild){
   blocks.push(temp.firstChild);
   temp.removeChild(temp.firstChild);
  }
  var totalBlocks=blocks.length;
  // 清空气泡内容（保留光标）
  var cursor=_streamBubble.querySelector('.typing-cursor');
  _streamBubble.innerHTML='';
  var _actualTotalBlocks=totalBlocks;
  var finalizedCount=Math.max(0,_actualTotalBlocks-1);
  while(_streamParts.length>finalizedCount){
   var removed=_streamParts.pop();
   if(removed && removed.root && removed.root.parentNode){
    removed.root.parentNode.removeChild(removed.root);
   }
  }
  var partAnchor=pendingState.root;
  for(var pi=finalizedCount-1;pi>=0;pi--){
   var finalizedHtml=blocks[pi].outerHTML;
   var part=_streamParts[pi];
   if(!part){
    part=createReplyPartMessage(finalizedHtml);
    _streamParts[pi]=part;
    chat.insertBefore(part.root, partAnchor);
   }else{
    part.bubble.innerHTML=finalizedHtml;
   }
   if(part.root && part.root.parentNode===chat){
    partAnchor=part.root;
   }
  }
  var newBlocks=[];
  if(_actualTotalBlocks>0){
   var tailBlock=blocks[_actualTotalBlocks-1];
   if(_actualTotalBlocks>_lastRenderedBlockCount){
    tailBlock.classList.add('block-fade-in');
   }
   newBlocks.push(tailBlock);
   totalBlocks=1;
  }else{
   totalBlocks=0;
  }
  // 逐块插入，新块带 fade-in
  for(var bi=0;bi<totalBlocks;bi++){
   var block=newBlocks[0]; // 始终取第一个（因为 appendChild 会从 temp 中移走）
   if(bi>=_lastRenderedBlockCount){
    block.classList.add('block-fade-in');
   }
   _streamBubble.appendChild(block);
  }
  // 光标放末尾
  if(!cursor){cursor=document.createElement('span');cursor.className='typing-cursor';}
  _streamBubble.appendChild(cursor);
  _lastRenderedBlockCount=_actualTotalBlocks;
  _streamTokenCount++;
  // 滚动控制
  if(_streamTokenCount<=5 || _nearBottom()){
   if(!_scrollRAF){
    _scrollRAF=requestAnimationFrame(function(){
     chat.scrollTop=chat.scrollHeight;
     _scrollRAF=0;
    });
   }
  }
 }

 function _appendStreamToken(token){
  if(!_streamStarted) _initStreamBubble();
  _streamText+=token;
  // 节流渐进渲染：每 80ms 最多渲染一次，避免高频 DOM 操作
  if(!_renderTimer){
   _renderTimer=setTimeout(_progressiveRender, 80);
  }
 }

 function _finalizeStream(fullText){
  if(!_streamBubble) return;
  // 清除未执行的渐进渲染定时器
  if(_renderTimer){clearTimeout(_renderTimer);_renderTimer=0;}
  // 保留已展开的 reply parts，避免最终收尾时丢掉它们与过程项之间的相对顺序。
  // 最终渲染：用完整文本做一次格式化（确保和 reply 事件的文本一致）
  _streamBubble.innerHTML=formatBubbleText(fullText);
  // 移除所有 fade-in 动画类（已经渲染完毕）
  var fadingBlocks=_streamBubble.querySelectorAll('.block-fade-in');
  for(var fi=0;fi<fadingBlocks.length;fi++){fadingBlocks[fi].classList.remove('block-fade-in');}
  var finalTemp=document.createElement('div');
  finalTemp.innerHTML=formatBubbleText(fullText);
  var finalBlocks=[];
  while(finalTemp.firstChild){
   finalBlocks.push(finalTemp.firstChild);
   finalTemp.removeChild(finalTemp.firstChild);
  }
  if(finalBlocks.length>1){
   var finalCount=finalBlocks.length-1;
   var finalAnchor=pendingState.root;
   for(var ri=finalCount-1;ri>=0;ri--){
    var finalHtml=finalBlocks[ri].outerHTML;
    var finalPart=_streamParts[ri];
    if(!finalPart){
     finalPart=createReplyPartMessage(finalHtml);
     _streamParts[ri]=finalPart;
     chat.insertBefore(finalPart.root, finalAnchor);
    }else{
     finalPart.bubble.innerHTML=finalHtml;
    }
    if(finalPart.root && finalPart.root.parentNode===chat){
     finalAnchor=finalPart.root;
    }
   }
   while(_streamParts.length>finalCount){
    var stalePart=_streamParts.pop();
    if(stalePart && stalePart.root && stalePart.root.parentNode){
     stalePart.root.parentNode.removeChild(stalePart.root);
    }
   }
   _streamBubble.innerHTML='';
   _streamBubble.appendChild(finalBlocks[finalBlocks.length-1]);
  }
  // 如果有附带图片，追加到气泡末尾
  if(replyImage){
   var img=document.createElement('img');
   img.className='bubble-image';
   img.src=replyImage;
   img.alt='截图';
   img.style.maxWidth='100%';
   img.style.maxHeight='400px';
   img.style.borderRadius='8px';
   img.style.marginTop='8px';
   img.style.cursor='pointer';
   img.onclick=function(){window.open(replyImage,'_blank');};
   _streamBubble.appendChild(img);
  }
  var meta=_streamBubble.parentNode.querySelector('.msg-meta');
  if(meta&&!meta.querySelector('.msg-copy')){
   var cpBtn=document.createElement('button');
   cpBtn.className='msg-copy';
   cpBtn.textContent=t('chat.copy');
   cpBtn.onclick=function(){navigator.clipboard.writeText(fullText).then(function(){cpBtn.textContent=t('chat.copied');setTimeout(function(){cpBtn.textContent=t('chat.copy');},1200);});};
   meta.appendChild(cpBtn);
  }
  // ── 思考折叠面板（流式路径）──
  if(_showRawThinkingPanel && _thinkingContent && _streamBubble.parentNode){
   var existPanel=_streamBubble.parentNode.querySelector('.thinking-panel');
   if(!existPanel){
    var thinkPanel=document.createElement('details');
    thinkPanel.className='thinking-panel';
    var thinkSummary=document.createElement('summary');
    thinkSummary.textContent='💭 模型思考过程';
    thinkSummary.style.cssText='cursor:pointer;font-size:12px;color:#888;padding:6px 0;user-select:none;';
    var thinkBody=document.createElement('div');
    thinkBody.style.cssText='font-size:12px;color:#999;padding:8px 12px;background:rgba(128,128,128,0.08);border-radius:8px;margin:4px 0 8px;white-space:pre-wrap;line-height:1.5;max-height:300px;overflow-y:auto;';
    thinkBody.textContent=_thinkingContent;
    thinkPanel.appendChild(thinkSummary);
    thinkPanel.appendChild(thinkBody);
    _streamBubble.parentNode.insertBefore(thinkPanel,_streamBubble);
   }
  }
  _collapseSteps();
  chat.scrollTop=chat.scrollHeight;
  if(!pendingState.persisted){
   _snapshotChatHistory();
   // 持久化 steps 摘要
   if(pendingState.steps&&pendingState.steps.length>0){
    var stepsMap=JSON.parse(localStorage.getItem('nova_steps_map')||'{}');
    var tsKey=String(Date.now());
    stepsMap[tsKey]=pendingState.steps.map(function(s){
     return {
      label:s.label||'',
      detail:(s.detailEl&&s.detailEl.textContent)||'',
      status:s.status||'done'
     };
    });
    // 只保留最近 200 条
    var keys=Object.keys(stepsMap);
    if(keys.length>200){keys.sort();keys.slice(0,keys.length-200).forEach(function(k){delete stepsMap[k];});}
    localStorage.setItem('nova_steps_map',JSON.stringify(stepsMap));
    pendingState.root.setAttribute('data-steps-key',tsKey);
   }
   pendingState.persisted=true;
  }
 }

 function showFinalReply(text){
  _placePendingRootAtEnd();
  // 把所有 running 步骤标记为 done
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i].status==='running') _setStepStatus(pendingState.steps[i],'done');
  }
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  _collapseSteps();
  if(pendingState.steps.length) _ensureTraceDetached();
  // 隐藏 spinner，显示内容区
  pendingState.status.style.display=pendingState.steps.length?'':'none';
  pendingState.root.className='msg assistant';
  var contentArea=pendingState.contentArea;
  contentArea.style.display='';
  contentArea.innerHTML='';
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
  cpBtn.textContent=t('chat.copy');
  cpBtn.onclick=function(){navigator.clipboard.writeText(text).then(function(){cpBtn.textContent=t('chat.copied');setTimeout(function(){cpBtn.textContent=t('chat.copy');},1200);});};
  meta.appendChild(cpBtn);
  contentArea.appendChild(meta);

  // ── 思考折叠面板 ──
  if(_showRawThinkingPanel && _thinkingContent){
   var thinkPanel=document.createElement('details');
   thinkPanel.className='thinking-panel';
   var thinkSummary=document.createElement('summary');
   thinkSummary.textContent='💭 模型思考过程';
   thinkSummary.style.cssText='cursor:pointer;font-size:12px;color:#888;padding:6px 0;user-select:none;';
   var thinkBody=document.createElement('div');
   thinkBody.style.cssText='font-size:12px;color:#999;padding:8px 12px;background:rgba(128,128,128,0.08);border-radius:8px;margin:4px 0 8px;white-space:pre-wrap;line-height:1.5;max-height:300px;overflow-y:auto;';
   thinkBody.textContent=_thinkingContent;
   thinkPanel.appendChild(thinkSummary);
   thinkPanel.appendChild(thinkBody);
   contentArea.appendChild(thinkPanel);
  }

  contentArea.appendChild(bubble);

  // ── 如果有附带图片（如截图），在气泡内渲染 ──
  if(replyImage){
   var img=document.createElement('img');
   img.className='bubble-image';
   img.src=replyImage;
   img.alt='截图';
   img.style.maxWidth='100%';
   img.style.maxHeight='400px';
   img.style.borderRadius='8px';
   img.style.marginTop='8px';
   img.style.cursor='pointer';
   img.onclick=function(){window.open(replyImage,'_blank');};
   bubble.appendChild(img);
  }

  // ── 渐进块动画：解析 markdown 后逐块 fade-in ──
  var formattedHtml=formatBubbleText(text);
  var temp=document.createElement('div');
  temp.innerHTML=formattedHtml;
  var allBlocks=[];
  while(temp.firstChild){allBlocks.push(temp.firstChild);temp.removeChild(temp.firstChild);}

  var blockIdx=0;
  var blockDelay=60; // 每块间隔 ms
  function revealNextBlock(){
   if(blockIdx>=allBlocks.length){
    // 所有块显示完毕 → 持久化
    _collapseSteps();
    chat.scrollTop=chat.scrollHeight;
     if(!pendingState.persisted){
      _snapshotChatHistory();
      pendingState.persisted=true;
     }
    return;
   }
   var block=allBlocks[blockIdx];
   block.classList.add('block-fade-in');
   bubble.appendChild(block);
   blockIdx++;
   if(chat.scrollHeight-chat.scrollTop-chat.clientHeight<120){
    chat.scrollTop=chat.scrollHeight;
   }
   setTimeout(revealNextBlock, blockDelay);
  }
  revealNextBlock();
 }

 try{
  _abortController=new AbortController();
  var imagesBase64=null;
  if(images&&images.length>0){
   imagesBase64=images.map(function(img){
    var commaIdx=img.indexOf(',');
    return commaIdx>=0?img.substring(commaIdx+1):img;
   });
  }
  var resp=await fetch('/chat',{
   method:'POST',
   headers:{'Content-Type':'application/json; charset=utf-8','Accept':'text/event-stream'},
   body:JSON.stringify({message:String(text||t('chat.describe.image')),image:imagesBase64?imagesBase64[0]:null,images:imagesBase64}),
   signal:_abortController.signal
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
        addStep(parsed);
        // ── CoD 状态点：轻量级，只更新 5px 指示灯颜色 ──
        try{
         var _det=String(parsed.detail||'');
         if(_det.indexOf('recall_memory')!==-1||_det.indexOf('query_knowledge')!==-1){
          _setCodDot('trace');
         }
        }catch(e){}
       }else if(currentEvent==='plan'){
        _renderPendingPlan(parsed);
       }else if(currentEvent==='reply'){
        replyText=parsed.reply||t('chat.error.retry');
        if(parsed.image) replyImage=parsed.image;
        // 本轮回复完成 → 复位状态点为金色
        try{ setTimeout(function(){_setCodDot('flash');},600); }catch(e){}
       }else if(currentEvent==='agent_step'){
        if(parsed.phase==='complete'){
         for(var si=0;si<pendingState.steps.length;si++){
          if(pendingState.steps[si].status==='running') _setStepStatus(pendingState.steps[si],'done');
         }
         }else if(parsed.phase==='waiting'){
          var _waitLabel=String(parsed.label||'').trim();
          var _waitDetail=String(parsed.detail||'').trim();
          var _runningStep=null;
          for(var wi=pendingState.steps.length-1;wi>=0;wi--){
           if(pendingState.steps[wi] && pendingState.steps[wi].status==='running'){
            _runningStep=pendingState.steps[wi];
            break;
           }
          }
          if(_runningStep){
           if(_waitLabel && _runningStep.label!==_waitLabel){
            addStep({label:_waitLabel,detail:_waitDetail||_waitLabel,status:'running',full_detail:_waitDetail||_waitLabel});
           }else if(_waitDetail){
            _applyStepDetail(_runningStep, _waitDetail, _waitDetail);
            chat.scrollTop=chat.scrollHeight;
           }
          }else if(_waitLabel || _waitDetail){
           addStep({label:_waitLabel||t('chat.process'),detail:_waitDetail||_waitLabel,status:'running',full_detail:_waitDetail||_waitLabel});
          }
         }
       }else if(currentEvent==='thinking'){
        var _thinkingText=String(parsed.content||'').replace(/<\/?think>/ig,' ').trim();
        if(_thinkingText){
         addStep({label:'模型思考',detail:_thinkingText,status:(parsed.status||'done'),full_detail:_thinkingText});
         if(_showRawThinkingPanel) _thinkingContent=_thinkingText;
        }
       }else if(currentEvent==='ask_user'){
        // agent 暂停等用户选择 → 渲染选项卡片
        _renderAskUser(parsed, pendingState);
       }else if(currentEvent==='stream'){
        _appendStreamToken(parsed.token||'');
       }else if(currentEvent==='reply'){
        replyText=parsed.reply||t('chat.error.retry');
        if(parsed.image) replyImage=parsed.image;
       }else if(currentEvent==='repair'){
        repairData=parsed;
       }else if(currentEvent==='awareness'){
        AwarenessManager.handleEvent(parsed);
       }else if(currentEvent==='model_changed'){
        var newModel=parsed.model||'';
        var newName=parsed.model_name||newModel;
        if(newModel){
         window._novaCurrentModel=newModel;
         var el=document.getElementById('modelName');
         if(el) el.textContent=newName||newModel;
         if(typeof _settingsCurrentModel!=='undefined') _settingsCurrentModel=newModel;
         if(typeof loadSettingsModels==='function') loadSettingsModels();
         if(typeof updateImageBtnState==='function') updateImageBtnState();
        }
       }
      }catch(e){}
     }
     currentEvent='';
     currentData='';
    }
   }
  }

  if(_streamStarted){
   // 流式已经显示了内容，用 reply 事件的完整文本做最终格式化
   var finalText=replyText||_streamText||t('chat.error.retry');
   _finalizeStream(finalText);
  }else if(replyText){
   showFinalReply(replyText);
  }else{
   finalizePendingAssistantMessage(pendingState, t('chat.error.retry'));
  }
  if(repairData && repairData.show){ showRepairBar(repairData); }
  _completeTaskProgress();
  AwarenessManager.startPolling();
 }catch(e){
  if(e.name==='AbortError'){
   // 用户点了停止，显示已有的部分回复或提示
   if(_streamStarted&&_streamText){
    _finalizeStream(_streamText);
   }else if(replyText){
    showFinalReply(replyText);
   }else{
    finalizePendingAssistantMessage(pendingState, t('chat.stopped')||'已停止');
   }
  }else{
   finalizePendingAssistantMessage(pendingState, t('chat.error.noconnect'));
  }
 }
 _abortController=null;
 _exitStopMode();
 chat.scrollTop=chat.scrollHeight;
}

// ── 当前任务板（输入框上方） ──
var _sessionTaskPlan=null;
var _taskPlanClearTimer=null;

function _isTaskPlanTerminal(plan){
 if(!plan || !plan.items || !plan.items.length) return true;
 var phase=String(plan.phase||'').trim();
 if(phase==='done' || phase==='failed' || phase==='blocked' || phase==='cancelled') return true;
 var hasRunning=false;
 var hasPending=false;
 var hasWaitingUser=false;
 for(var i=0;i<plan.items.length;i++){
  var status=String((plan.items[i]&&plan.items[i].status)||'pending');
  if(status==='running') hasRunning=true;
  if(status==='pending') hasPending=true;
  if(status==='waiting_user') hasWaitingUser=true;
 }
 return !hasRunning && !hasPending && !hasWaitingUser;
}

function _taskPlanStateLabel(status){
 status=String(status||'pending');
 if(status==='running') return '进行中';
 if(status==='done') return '已完成';
 if(status==='waiting_user') return '待选择';
 if(status==='blocked' || status==='error' || status==='failed') return '卡住';
 return '待执行';
}

function _taskPlanStateIcon(status){
 status=String(status||'pending');
 if(status==='running') return '◉';
 if(status==='done') return '✓';
 if(status==='blocked' || status==='error' || status==='failed') return '!';
 return '○';
}

function _taskPlanStateIconMarkup(status){
 status=String(status||'pending');
 if(status==='running'){
  return '<svg viewBox="0 0 16 16" class="task-plan-glyph task-plan-glyph-running" fill="none" aria-hidden="true"><circle class="track" cx="8" cy="8" r="5.4" stroke="currentColor" stroke-width="1.5"></circle><path class="arc" d="M12.8 8A4.8 4.8 0 0 0 8 3.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path></svg>';
 }
 if(status==='done'){
  return '<svg viewBox="0 0 16 16" class="task-plan-glyph task-plan-glyph-done" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.4" stroke="currentColor" stroke-width="1.5"></circle><path d="M5.2 8.2l1.8 1.9 3.8-4.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>';
 }
 if(status==='waiting_user'){
  return '<svg viewBox="0 0 16 16" class="task-plan-glyph task-plan-glyph-waiting" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.4" stroke="currentColor" stroke-width="1.5"></circle><circle cx="5.2" cy="8" r="0.9" fill="currentColor"></circle><circle cx="8" cy="8" r="0.9" fill="currentColor"></circle><circle cx="10.8" cy="8" r="0.9" fill="currentColor"></circle></svg>';
 }
 if(status==='blocked' || status==='error' || status==='failed'){
  return '<svg viewBox="0 0 16 16" class="task-plan-glyph task-plan-glyph-error" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.4" stroke="currentColor" stroke-width="1.5"></circle><path d="M8 4.6v4.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path><circle cx="8" cy="11.6" r="0.9" fill="currentColor"></circle></svg>';
 }
 return '<svg viewBox="0 0 16 16" class="task-plan-glyph task-plan-glyph-pending" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5.4" stroke="currentColor" stroke-width="1.5"></circle></svg>';
}

function _scheduleTaskPlanClear(delayMs){
 if(_taskPlanClearTimer){ clearTimeout(_taskPlanClearTimer); _taskPlanClearTimer=null; }
 _taskPlanClearTimer=setTimeout(function(){
  window._clearSessionTaskPlan();
 }, delayMs||2600);
}

function _renderSessionTaskPlan(){
 var board=document.getElementById('taskPlanBoard');
 if(!board) return;
 if(!_sessionTaskPlan || !_sessionTaskPlan.items || !_sessionTaskPlan.items.length){
  board.style.display='none';
  board.innerHTML='';
  return;
 }
 var plan=_sessionTaskPlan;
 var terminal=_isTaskPlanTerminal(plan);
 board.style.display='';
 board.innerHTML='';
 board.className='task-plan-board'+(terminal?' is-terminal':'');

 var head=document.createElement('div');
 head.className='task-plan-head';
 var goal=document.createElement('div');
 goal.className='task-plan-goal';
 goal.textContent=String(plan.goal||'当前任务');
 var phase=document.createElement('div');
 phase.className='task-plan-phase';
 phase.textContent=String(plan.summary||'正在推进任务');
 head.appendChild(goal);
 head.appendChild(phase);
 board.appendChild(head);

 var list=document.createElement('div');
 list.className='task-plan-list';
 (plan.items||[]).forEach(function(item,idx){
 var row=document.createElement('div');
  var status=String((item&&item.status)||'pending');
  row.className='task-plan-item '+status;
  row.title=_taskPlanStateLabel(status);

  var index=document.createElement('div');
  index.className='task-plan-index';
  index.innerHTML=_taskPlanStateIconMarkup(status);
  index.setAttribute('aria-hidden','true');

  var body=document.createElement('div');
  body.className='task-plan-body';

  var title=document.createElement('div');
  title.className='task-plan-title';
  title.textContent=String((item&&item.title)||'');
  body.appendChild(title);

  var detailText=String((item&&item.detail)||'').trim();
  if(detailText){
   var detail=document.createElement('div');
   detail.className='task-plan-detail';
   detail.textContent=detailText;
   body.appendChild(detail);
  }

  row.appendChild(index);
  row.appendChild(body);
  list.appendChild(row);
 });
 board.appendChild(list);
}

window._setSessionTaskPlan=function(plan){
 if(_taskPlanClearTimer){ clearTimeout(_taskPlanClearTimer); _taskPlanClearTimer=null; }
 _sessionTaskPlan=plan&&plan.items&&plan.items.length?plan:null;
 _renderSessionTaskPlan();
 if(_sessionTaskPlan && _isTaskPlanTerminal(_sessionTaskPlan)){
  _scheduleTaskPlanClear(2800);
 }
};

window._clearSessionTaskPlan=function(){
 if(_taskPlanClearTimer){ clearTimeout(_taskPlanClearTimer); _taskPlanClearTimer=null; }
 _sessionTaskPlan=null;
 _renderSessionTaskPlan();
};

function _getAskUserSlot(){
 var slot=document.getElementById('askUserSlot');
 if(slot) return slot;
 var inputArea=document.querySelector('.input');
 var planBoard=document.getElementById('taskPlanBoard');
 if(!inputArea || !planBoard) return null;
 slot=document.createElement('div');
 slot.id='askUserSlot';
 slot.className='ask-user-slot';
 slot.style.display='none';
 inputArea.insertBefore(slot, planBoard);
 return slot;
}

function _clearAskUserSlot(){
 var slot=document.getElementById('askUserSlot');
 if(!slot) return;
 slot.innerHTML='';
 slot.style.display='none';
}

function _dismissAskUserCard(slot, card){
 if(slot){
  _clearAskUserSlot();
  return;
 }
 if(card) card.style.display='none';
}

window._clearAskUserSlot=_clearAskUserSlot;

// ── 任务进度条（输入框上方） ──
function _addTaskProgress(label, value){
 var bar=document.getElementById('taskProgressBar');
 if(!bar)return;
 bar.style.display='';
 var item=document.createElement('div');
 item.className='task-progress-item';
 item.innerHTML='<span class="task-progress-icon">■</span><span class="task-progress-label">'+escapeHtml(label)+'</span><span class="task-progress-value">'+escapeHtml(value)+'</span>';
 item.dataset.status='working';
 var taskText=escapeHtml(String(label||'').trim());
 var valueText=escapeHtml(String(value||'').trim());
 var textHtml='<span class="task-progress-label">'+taskText+'</span>';
 if(valueText){
  textHtml+='<span class="task-progress-sep">：</span><span class="task-progress-value">'+valueText+'</span>';
 }
 if(valueText){
  textHtml='<span class="task-progress-label">'+taskText+'</span><span class="task-progress-sep">: </span><span class="task-progress-value">'+valueText+'</span>';
 }
 item.innerHTML='<span class="task-progress-icon" aria-hidden="true">'+_taskProgressWorkingSvg+'</span><span class="task-progress-text">'+textHtml+'</span>';
 bar.appendChild(item);
}

function _completeTaskProgress(){
 var bar=document.getElementById('taskProgressBar');
 if(!bar)return;
 var items=bar.querySelectorAll('.task-progress-item');
 for(var i=0;i<items.length;i++){
  if(items[i].dataset.status==='working'){
   items[i].dataset.status='done';
   var icon=items[i].querySelector('.task-progress-icon');
   if(icon){
    setTimeout(function(target){
     target.innerHTML=_taskProgressDoneSvg;
     target.classList.add('done');
    },0,icon);
   }
   if(icon){icon.textContent='✓';icon.classList.add('done');}
  }
 }
 // 5秒后淡出隐藏
 setTimeout(function(){
  bar.style.opacity='0';
  setTimeout(function(){bar.style.display='none';bar.style.opacity='';bar.innerHTML='';},500);
 },5000);
}

// ── ask_user 选项卡片渲染 ──
function _renderAskUser(data, pendingState){
 var qid=data.id||'';
 var question=data.question||'';
 var options=data.options||[];
 var slot=_getAskUserSlot();
 if(!question || !options.length){
  _clearAskUserSlot();
  return;
 }

 // 在输入框上方插入选项卡片
 var card=document.createElement('div');
 card.className='ask-user-card';
 card.innerHTML='<div class="ask-user-question">'+escapeHtml(question)+'</div>';
 var optionsDiv=document.createElement('div');
 optionsDiv.className='ask-user-options';
 // LLM 给的选项
 options.forEach(function(opt){
  var btn=document.createElement('button');
  btn.className='ask-user-option';
  btn.textContent=opt;
  btn.onclick=function(){
   var btns=optionsDiv.querySelectorAll('button');
   for(var i=0;i<btns.length;i++){btns[i].disabled=true;btns[i].classList.remove('selected');}
   btn.classList.add('selected');
   // 在输入框上方挂进度条
   _addTaskProgress(question, opt);
   // 收起选项卡片
   setTimeout(function(){ _dismissAskUserCard(slot, card); },400);
   fetch('/chat/answer',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({question_id:qid,answer:opt})
   });
  };
  optionsDiv.appendChild(btn);
 });
 // 系统兜底：都不满意
 var noneBtn=document.createElement('button');
 noneBtn.className='ask-user-option ask-user-none';
 noneBtn.textContent='都不满意';
 noneBtn.onclick=function(){
  var btns=optionsDiv.querySelectorAll('button');
  for(var i=0;i<btns.length;i++){btns[i].disabled=true;btns[i].classList.remove('selected');}
  noneBtn.classList.add('selected');
  _addTaskProgress(question, '都不满意，重新推荐');
  setTimeout(function(){ _dismissAskUserCard(slot, card); },400);
  fetch('/chat/answer',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({question_id:qid,answer:'都不满意，请换其他方案'})
  });
 };
 optionsDiv.appendChild(noneBtn);
 card.appendChild(optionsDiv);
 if(slot){
  slot.innerHTML='';
  slot.style.display='';
  slot.appendChild(card);
 }else{
  // fallback：插到聊天区底部
  var chat=document.getElementById('chat');
  chat.appendChild(card);
  chat.scrollTop=chat.scrollHeight;
 }
}

// ── 语音对话模式（点一次进入，自动循环，再点退出） ──
var _voiceMode = false;

(function(){
 var voiceBtn=document.getElementById('voiceBtn');
 if(!voiceBtn) return;

 var SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
 if(!SpeechRecognition){
  voiceBtn.style.display='none';
  return;
 }

 var recognition=new SpeechRecognition();
 recognition.lang='zh-CN';
 recognition.continuous=true;
 recognition.interimResults=true;

 var isRecording=false;
 var inp=document.getElementById('inp');
 var _silenceTimer=null; // 静默检测：无新结果后自动发送
 var _lastResultTime=0;

 voiceBtn.addEventListener('click',function(e){
  e.preventDefault();
  if(_voiceMode){ exitVoiceMode(); }
  else{ enterVoiceMode(); }
 });

 function enterVoiceMode(){
  _voiceMode=true;
  voiceBtn.classList.add('recording');
  _syncVoiceMode(true);
  startListening();
 }

 function exitVoiceMode(){
  _voiceMode=false;
  voiceBtn.classList.remove('recording');
  _syncVoiceMode(false);
  if(_silenceTimer){ clearTimeout(_silenceTimer); _silenceTimer=null; }
  if(isRecording){ try{ recognition.stop(); }catch(err){} }
  isRecording=false;
  if(inp) inp.placeholder=t('input.placeholder');
 }

 function _syncVoiceMode(enabled){
  fetch('/companion/voice_mode',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({enabled:enabled})
  }).catch(function(){});
 }

 function startListening(){
  if(!_voiceMode) return;
  if(_silenceTimer){ clearTimeout(_silenceTimer); _silenceTimer=null; }
  isRecording=true;
  _lastResultTime=0;
  if(inp){ inp.value=''; inp.placeholder=t('input.listening'); }
  try{ recognition.start(); }catch(err){}
 }

 recognition.onresult=function(e){
  var transcript='';
  var isFinal=false;
  for(var i=0;i<e.results.length;i++){
   transcript+=e.results[i][0].transcript;
   if(e.results[i].isFinal) isFinal=true;
  }
  if(inp) inp.value=transcript;
  _lastResultTime=Date.now();
  // 有最终结果后启动静默计时，1.8秒无新内容自动发送
  if(isFinal && transcript.trim()){
   if(_silenceTimer) clearTimeout(_silenceTimer);
   _silenceTimer=setTimeout(function(){
    if(!_voiceMode) return;
    try{ recognition.stop(); }catch(err){}
   },1800);
  }
 };

 recognition.onend=function(){
  isRecording=false;
  if(_silenceTimer){ clearTimeout(_silenceTimer); _silenceTimer=null; }
  if(!_voiceMode){ if(inp) inp.placeholder='\u4e0e Nova \u5bf9\u8bdd...'; return; }
  var text=(inp&&inp.value||'').trim();
  if(!text){ setTimeout(startListening,500); return; }
  if(inp) inp.placeholder=t('input.waiting');
  var replyIdBefore=_lastReplyIdForVoice||'';
  send();
  waitForReplyThenListen(replyIdBefore);
 };

 recognition.onerror=function(e){
  isRecording=false;
  if(!_voiceMode) return;
  // no-speech / aborted 是正常情况，不要太快重启
  var delay=e.error==='no-speech'?500:e.error==='aborted'?300:1000;
  setTimeout(startListening, delay);
 };

 // 等 Nova 回复完 + TTS 播完再开始听
 function waitForReplyThenListen(replyIdBefore){
  if(!_voiceMode) return;
  var polls=0;
  var gotReply=false;
  var seenTtsStart=false;
  var replyTime=0;
  var timer=setInterval(function(){
   polls++;
   if(!_voiceMode||polls>=100){ clearInterval(timer); if(_voiceMode) startListening(); return; }
   fetch('/companion/state').then(function(r){return r.json();}).then(function(s){
    if(!gotReply){
     // 阶段1：等新回复出现
     if(s.last_reply_id && s.last_reply_id!==replyIdBefore){
      gotReply=true;
      replyTime=Date.now();
      _lastReplyIdForVoice=s.last_reply_id;
      // 用文本长度估算最大等待时间（兜底）
      var text=s.last_reply_full||s.last_reply_summary||'';
      var maxWait=Math.max((text.length/3)*1000+5000, 8000);
      setTimeout(function(){
       clearInterval(timer);
       if(_voiceMode) startListening();
      }, maxWait);
     }
    }else{
     // 阶段2：等 TTS 播完
     if(s.tts_playing){
      seenTtsStart=true;
     }
     if(seenTtsStart && !s.tts_playing){
      // 确认播完了
      clearInterval(timer);
      if(_voiceMode) setTimeout(startListening,300);
     }
     // 如果等了 6 秒还没看到 tts_playing=true，伴侣窗口可能没开
     if(!seenTtsStart && Date.now()-replyTime>6000){
      clearInterval(timer);
      if(_voiceMode) startListening();
     }
    }
   }).catch(function(){});
  },600);
 }
 var _lastReplyIdForVoice='';
})();


// ── CoD 状态点：5px 指示灯，金=闪念 蓝=溯源 ──────────────────────
function _setCodDot(mode){
  var dot=document.getElementById('codStatusDot');
  if(!dot) return;
  dot.className='cod-dot '+(mode==='trace'?'cod-trace':'cod-flash');
}
