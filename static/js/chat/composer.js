// Composer interactions, image previews, and message shells
// Source: chat.js lines 161-710

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
 if(!btn) return;
 btn.disabled=false;
 btn.classList.add('stop-mode');
 btn.innerHTML=_stopSvg;
 _setSendButtonA11yState(btn, 'input.stop', 'Stop response');
}

function _setSendButtonA11yState(btn, titleKey, fallback){
 if(!btn) return;
 if(titleKey){
  btn.setAttribute('data-i18n-title', titleKey);
 }
 var label=(typeof t==='function' && titleKey) ? t(titleKey) : String(fallback||'');
 if(!label && titleKey) label=titleKey;
 btn.title=label;
 btn.setAttribute('aria-label', label);
}

function _exitStopMode(){
 var btn=document.getElementById('sendBtn');
 if(!btn) return;
 btn.classList.remove('stop-mode');
 btn.innerHTML=_sendSvg;
 _setSendButtonA11yState(btn, 'input.send', 'Send message');
 updateSendButton();
}

function _stopGeneration(){
 if(_abortController){
  _abortController.abort();
  _abortController=null;
 }
}

function addMessage(sender,text,type,imageUrl,renderedHtml){
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
 if(type!=='user'){
  if(typeof applyAssistantBubbleRenderMode==='function'){
   applyAssistantBubbleRenderMode(bubble, text, renderedHtml);
  }else{
   bubble.classList.add('assistant-reply-markdown');
  }
 }
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
   textNode.innerHTML=typeof renderAssistantReplyHtml==='function'
    ? renderAssistantReplyHtml(text, renderedHtml)
    : renderAssistantBubbleHtml(text, renderedHtml);
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
 if(type==='user' && typeof window._setChatAutoStick==='function'){
  window._setChatAutoStick(true);
 }
 _stickChatToBottom(type==='user' ? {force:true, lock_ms:240} : {});
 
 // 保存到历史
 if(type==='user'||type==='assistant'){
  chatHistory+=msgDiv.outerHTML;
  persistChatHistorySnapshot();
 }
}

function addChatEventNote(kind, label, text, detail){
 var chat=document.getElementById('chat');
 if(!chat) return null;
 var row=document.createElement('div');
 row.className='chat-event-note';
 if(kind) row.classList.add('chat-event-note-'+String(kind).trim().toLowerCase());
 row.setAttribute('data-note-kind', String(kind||'info').trim().toLowerCase());

 var line=document.createElement('div');
 line.className='chat-event-note-line';

 var chip=document.createElement('span');
 chip.className='chat-event-note-chip';
 chip.textContent=String(label||'EVENT').trim()||'EVENT';

 var main=document.createElement('span');
 main.className='chat-event-note-text';
 main.textContent=String(text||'').trim();

 var time=document.createElement('span');
 time.className='chat-event-note-time';
 time.textContent=T();

 line.appendChild(chip);
 if(main.textContent){
  line.appendChild(main);
 }
 line.appendChild(time);
 row.appendChild(line);

 var detailText=String(detail||'').trim();
 if(detailText){
  var detailEl=document.createElement('div');
  detailEl.className='chat-event-note-detail';
  detailEl.textContent=detailText;
  row.appendChild(detailEl);
 }

 chat.appendChild(row);
 _stickChatToBottom({threshold:220});
 _snapshotChatHistory();
 return row;
}

function _snapshotChatHistory(options){
 options=options||{};
 var chat=document.getElementById('chat');
 if(!chat) return false;
 var currentHtml=String(chat.innerHTML||'');
 if(!currentHtml.trim()){
  if(options.allowEmpty===true){
   chatHistory='';
   persistChatHistorySnapshot();
   return true;
  }
  return false;
 }
 var looksLikeChat=(typeof window._looksLikeChatSnapshot==='function')
  ? window._looksLikeChatSnapshot(currentHtml)
  : /class="msg\b|class="welcome\b|thinking-msg|process-msg|reply-part-msg/.test(currentHtml);
 if(!looksLikeChat) return false;
 chatHistory=currentHtml;
 persistChatHistorySnapshot();
 return true;
}
window._snapshotChatHistory=_snapshotChatHistory;

function _stickChatToBottom(options){
 if(typeof window._maybePinChatToBottom==='function'){
  return window._maybePinChatToBottom(options||{});
 }
 var chat=document.getElementById('chat');
 if(!chat) return false;
 chat.scrollTop=chat.scrollHeight;
 return true;
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
 msgDiv.style.display='none';

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
  +'<span class="step-tracker-spinner thinking running" aria-hidden="true"></span>'
  +'<span class="step-tracker-title">Thinking</span>'
  +'</span>'
  +'<span class="step-tracker-summary"></span>'
  +'<span class="step-tracker-toggle-text"></span>';
 status.style.display='none';

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

function finalizePendingAssistantMessage(pendingState, replyText, renderedHtml){
 if(!pendingState || !pendingState.root) return;
 if(pendingState.placeholderTimer){
  clearTimeout(pendingState.placeholderTimer);
  pendingState.placeholderTimer=null;
 }
 var chat=document.getElementById('chat');
 if(chat){
  chat.appendChild(pendingState.root);
 }
 pendingState.root.style.display='';
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
  pendingState.status.style.display='none';
  pendingState.status.setAttribute('aria-expanded','false');
 }
 if(pendingState.tracker){
  pendingState.tracker.style.display='none';
  pendingState.tracker.classList.add('collapsed');
 }
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
 if(typeof applyAssistantBubbleRenderMode==='function'){
  applyAssistantBubbleRenderMode(bubble, replyText, renderedHtml);
 }
 bubble.innerHTML=typeof renderAssistantReplyHtml==='function'
  ? renderAssistantReplyHtml(replyText, renderedHtml)
  : renderAssistantBubbleHtml(replyText, renderedHtml);
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

function _syncProcessPhase(stepObj){
 if(!stepObj || stepObj.kind!=='process') return;
 var phase=String(stepObj.phase||'info');
 if(stepObj.root){
  stepObj.root.classList.remove('phase-thinking','phase-tool','phase-waiting','phase-info');
  stepObj.root.classList.add('phase-'+phase);
 }
 if(stepObj.line){
  stepObj.line.classList.remove('phase-thinking','phase-tool','phase-waiting','phase-info');
  stepObj.line.classList.add('phase-'+phase);
 }
 if(stepObj.markerEl){
  stepObj.markerEl.classList.toggle('thinking-marker', phase==='thinking');
 }
}

function _syncProcessDetailDisplay(stepObj){
 if(!stepObj || stepObj.kind!=='process' || !stepObj.detailEl) return;
 var summary=String(stepObj.summaryDetail||'').trim();
 var full=String(stepObj.fullDetail||summary).trim();
 var expandable=!!(summary && full && summary!==full);
 if(!expandable) stepObj.expanded=false;
 stepObj.expandable=expandable;
 if(stepObj.root){
  stepObj.root.classList.toggle('expandable', expandable);
  stepObj.root.classList.toggle('expanded', expandable && !!stepObj.expanded);
 }
 if(stepObj.line){
  stepObj.line.classList.toggle('expandable', expandable);
  stepObj.line.classList.toggle('expanded', expandable && !!stepObj.expanded);
 }
 _setProcessDetailContent(stepObj.detailEl, (expandable && !stepObj.expanded) ? summary : full);
}

function showRepairBar(repair){
 // Chat page: fully disable repair/feedback bar UI (L7/self-repair progress).
 // Backend may still record feedback and generate proposals; we just don't interrupt the user here.
 hideRepairBar();
 return;
 var bar=document.getElementById('repairBar');
 var chip=document.getElementById('repairChip');
 var headline=document.getElementById('repairHeadline');
 var detail=document.getElementById('repairDetail');
 var progress=document.getElementById('repairProgress');
 if(!bar||!headline||!detail||!progress) return;

 if(bar._repairTimer){ clearInterval(bar._repairTimer); bar._repairTimer=null; }
 var stage=String(repair.stage||'').trim().toLowerCase();
 bar.dataset.state=repair.watch ? 'watch' : (stage||'logged');
 if(chip){
  var chipText='L7';
  if(repair.watch) chipText='FIX';
  if(stage==='done' || Number(repair.progress||0)>=100) chipText='OK';
  chip.textContent=chipText;
 }
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
    bar.dataset.state='done';
    if(chip) chip.textContent='OK';
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
 bar.removeAttribute('data-state');
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
 var phase=String((card&&card.phase)||'info');
  line.className='process-line '+(status==='error'?'error':(status==='running'?'running':'done'));
  var marker=document.createElement('span');
  marker.className='process-marker';
  _setProcessMarker(marker, card&&card.label, status);
 var label=document.createElement('span');
 label.className='process-label';
  label.textContent=_formatProcessDisplayLabel(String((card&&card.label)||''))||t('chat.process');
 var detail=document.createElement('span');
 detail.className='process-detail';
 detail.textContent=String((card&&card.detail)||'');
 line.appendChild(marker);
 line.appendChild(label);
 line.appendChild(detail);
 content.appendChild(line);
 msgDiv.appendChild(_createNovaAvatar());
 msgDiv.appendChild(content);
 var processStep={
  kind:'process',
  root:msgDiv,
  content:content,
  line:line,
  markerEl:marker,
  labelEl:label,
  detailEl:detail,
  label:String((card&&card.label)||''),
  status:status,
  summaryDetail:String((card&&card.detail)||'').trim(),
  fullDetail:String((card&&((card.full_detail&&String(card.full_detail).trim())||card.detail))||'').trim(),
  phase:phase,
  stepKey:String((card&&card.step_key)||'').trim(),
  reasonKind:String((card&&card.reason_kind)||'').trim(),
  goal:String((card&&card.goal)||'').trim(),
  decisionNote:String((card&&card.decision_note)||'').trim(),
  handoffNote:String((card&&card.handoff_note)||'').trim(),
  expectedOutput:String((card&&card.expected_output)||'').trim(),
  nextUserNeed:String((card&&card.next_user_need)||'').trim(),
  toolName:String((card&&card.tool_name)||'').trim(),
  parallelGroupId:String((card&&card.parallel_group_id)||'').trim(),
  parallelIndex:typeof _normalizePositiveStepCount==='function' ? _normalizePositiveStepCount(card&&card.parallel_index) : 0,
  parallelSize:typeof _normalizePositiveStepCount==='function' ? _normalizePositiveStepCount(card&&card.parallel_size) : 0,
  parallelCompletedCount:typeof _normalizePositiveStepCount==='function' ? _normalizePositiveStepCount(card&&card.parallel_completed_count) : 0,
  parallelSuccessCount:typeof _normalizePositiveStepCount==='function' ? _normalizePositiveStepCount(card&&card.parallel_success_count) : 0,
  parallelFailureCount:typeof _normalizePositiveStepCount==='function' ? _normalizePositiveStepCount(card&&card.parallel_failure_count) : 0,
  parallelTools:typeof _normalizeStepNameList==='function' ? _normalizeStepNameList(card&&card.parallel_tools) : [],
  startedAt:Date.now(),
  expanded:false,
  expandable:false
 };
 processStep.root.addEventListener('click', function(){
  if(!processStep.expandable) return;
  processStep.expanded=!processStep.expanded;
  _syncProcessDetailDisplay(processStep);
 });
 _syncProcessPhase(processStep);
 _syncProcessDetailDisplay(processStep);
 return processStep;
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
