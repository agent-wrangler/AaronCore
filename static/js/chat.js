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
 if(/思考|thinking/i.test(text)) return '·';
 if(/计划|plan/i.test(text)) return '⌁';
 return '·';
}

function _setProcessMarker(markerEl, label, status){
 if(!markerEl) return;
 var state=String(status||'done');
 markerEl.classList.toggle('is-running', state==='running');
 if(state==='running'){
  markerEl.setAttribute('aria-hidden','true');
  markerEl.innerHTML='<span></span><span></span><span></span>';
  return;
 }
 markerEl.removeAttribute('aria-hidden');
 markerEl.textContent=_processMarkerText(label, state);
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

function _mergeProcessDetailWithPrevious(detail, previous){
 var current=_splitProcessWaitSuffix(detail);
 if(current.text || !current.wait) return String(detail||'').trim();
 var prior=_splitProcessWaitSuffix(previous);
 if(!prior.text) return String(detail||'').trim();
 return prior.text+' '+current.wait;
}

function _preserveProcessWaitSuffix(detail, previous){
 var current=_splitProcessWaitSuffix(detail);
 if(current.wait) return String(detail||'').trim();
 var prior=_splitProcessWaitSuffix(previous);
 if(!current.text || !prior.wait || !prior.text) return String(detail||'').trim();
 var currentText=String(current.text||'').replace(/\s+/g,' ').trim();
 var priorText=String(prior.text||'').replace(/\s+/g,' ').trim();
 if(!currentText || !priorText) return String(detail||'').trim();
 if(currentText===priorText || currentText.indexOf(priorText)===0 || priorText.indexOf(currentText)===0){
  return currentText+' '+prior.wait;
 }
 return String(detail||'').trim();
}

function _detailHasWaitSuffix(detail){
 return !!_splitProcessWaitSuffix(detail).wait;
}

function _appendElapsedSuffix(detail, seconds){
 var text=String(detail||'').trim();
 var waited=Math.max(1, Number(seconds)||0);
 if(!waited) return text;
 if(_detailHasWaitSuffix(text)) return text;
 return text ? (text+' '+waited+'s') : (waited+'s');
}

function _renderProcessDetailMarkup(detail){
 return escapeHtml(String(detail||'').trim());
}

function _setProcessDetailContent(detailEl, detail){
 if(!detailEl) return;
 var text=String(detail||'').trim();
 detailEl.dataset.rawDetail=text;
 detailEl.textContent=text;
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
  text=text.replace(/^正在执行(?:中)?(?:\.\.\.)?$/i, '').trim();
 }
 return text;
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
   textNode.innerHTML=renderAssistantBubbleHtml(text, renderedHtml);
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

function _snapshotChatHistory(){
 var chat=document.getElementById('chat');
 if(!chat) return;
 chatHistory=chat.innerHTML;
 persistChatHistorySnapshot();
}

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
 bubble.innerHTML=renderAssistantBubbleHtml(replyText, renderedHtml);
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
 var replyHtml='';
 var replyImage='';
 var _thinkingContent='';
 var _showRawThinkingPanel=false;
  var repairData=null;
  var hasTrace=false;
  var _streamBubble=null; // 流式输出的气泡
  var _streamText=''; // 流式累积的文本
  var _streamStarted=false;
  var _suppressTypingCursor=false;

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
  _stickChatToBottom();
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
}

  function _looksLikeThinkingLabel(label){
  return /thinking|\u6a21\u578b\u601d\u8003/i.test(String(label||''));
 }

 function _looksLikeMemoryLoadLabel(label){
  return /^(?:\u8bb0\u5fc6\u52a0\u8f7d(?:\u5b8c\u6210)?|memory_load|load_memory)$/i.test(String(label||'').trim());
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

 function _collapseProcessDetail(detail, phase, status){
  var text=String(detail||'').replace(/\s+/g,' ').trim();
  if(!text) return '';
  if(String(status||'')==='error') return text;
  var limit=(phase==='thinking') ? 110 : 130;
  return text.length>limit ? (text.slice(0, limit-1)+'…') : text;
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

 function _buildThinkingProcessDetail(card, fallbackSummary, fallbackFull){
  var summaryParts=[];
  var fullParts=[];
  var lead=_stepMetaText((card&&card.decision_note)||'') || _stepMetaText((card&&card.handoff_note)||'') || _stepMetaText(fallbackSummary) || _stepMetaText(fallbackFull);
  var goal=_stepMetaText(card&&card.goal);
  var expected=_stepMetaText(card&&card.expected_output);
  var nextNeed=_stepMetaText(card&&card.next_user_need);
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

 function _buildToolProcessDetail(card, fallbackSummary, fallbackFull, state){
  var summaryParts=[];
  var fullParts=[];
  var lead=_stepMetaText(fallbackSummary) || _stepMetaText(fallbackFull) || _stepMetaText(card&&card.goal) || _stepMetaText(card&&card.handoff_note) || _stepMetaText(card&&card.expected_output);
  var goal=_stepMetaText(card&&card.goal);
  var expected=_stepMetaText(card&&card.expected_output);
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

 function _buildStructuredProcessDetail(card, phase, state, fallbackSummary, fallbackFull){
  if(phase==='thinking') return _buildThinkingProcessDetail(card, fallbackSummary, fallbackFull);
  if(phase==='tool') return _buildToolProcessDetail(card, fallbackSummary, fallbackFull, state);
  return {
   summary:_stepMetaText(fallbackSummary),
   full:_stepMetaText(fallbackFull) || _stepMetaText(fallbackSummary)
  };
 }

 function _normalizeStepCard(card){
  var rawLabel=String((card&&card.label)||'').trim();
  var rawStatus=String((card&&card.status)||'running');
  var state=(rawStatus==='error'?'error':(rawStatus==='running'?'running':'done'));
  var rawSummaryDetail=String((card&&card.detail)||'').trim();
  var rawFullDetail=String((card&&((card.full_detail&&String(card.full_detail).trim())||card.detail))||'').trim();
  var summaryDetail=rawSummaryDetail;
  var fullDetail=rawFullDetail;
  var phase='info';
  var displayLabel=rawLabel||t('chat.process');
  var toolKey='';
  var toolFallback=_toolLabelFallback(rawLabel);
  if(_looksLikeThinkingLabel(rawLabel)){
   phase='thinking';
   displayLabel='Thinking';
  }else if(_looksLikeMemoryLoadLabel(rawLabel)){
   displayLabel='memory_load';
  }else if(toolFallback){
    phase='tool';
    toolKey=_extractToolKey(rawSummaryDetail)||_extractToolKey(rawFullDetail)||toolFallback;
    displayLabel=toolKey||toolFallback||'tool';
    fullDetail=_extractToolDetail(rawFullDetail)||rawFullDetail||rawSummaryDetail;
    summaryDetail=_extractToolDetail(rawSummaryDetail)||fullDetail||rawSummaryDetail;
    fullDetail=_simplifyToolDetail(fullDetail, toolKey, state);
    summaryDetail=_simplifyToolDetail(summaryDetail, toolKey, state);
  }else if(/\u7b49\u5f85|waiting/i.test(rawLabel)){
    phase='waiting';
    displayLabel='waiting';
  }else{
    var alias=_processLabelAlias(rawLabel);
    if(alias) displayLabel=alias;
  }
  var stepKey=String((card&&card.step_key)||'').trim();
  var reasonKind=String((card&&card.reason_kind)||'').trim();
  var goal=String((card&&card.goal)||'').trim();
  var decisionNote=String((card&&card.decision_note)||'').trim();
  var handoffNote=String((card&&card.handoff_note)||'').trim();
  var expectedOutput=String((card&&card.expected_output)||'').trim();
  var nextUserNeed=String((card&&card.next_user_need)||'').trim();
  var toolName=String((card&&card.tool_name)||'').trim();
  var structuredDetail=_buildStructuredProcessDetail(card, phase, state, summaryDetail, fullDetail);
  summaryDetail=structuredDetail.summary;
  fullDetail=structuredDetail.full;
  displayLabel=_formatProcessDisplayLabel(displayLabel);
  fullDetail=_cleanProcessDetail(fullDetail, rawLabel, displayLabel, state);
  summaryDetail=_cleanProcessDetail(summaryDetail, rawLabel, displayLabel, state);
  if(!fullDetail) fullDetail=summaryDetail;
  if(!summaryDetail) summaryDetail=fullDetail;
  summaryDetail=_collapseProcessDetail(summaryDetail||fullDetail, phase, state);
  return {
   rawLabel:rawLabel,
   status:state,
   phase:phase,
   displayLabel:displayLabel,
   summaryDetail:summaryDetail,
   fullDetail:fullDetail,
   toolKey:phase==='tool' ? (toolName||toolKey||_extractToolKey(rawSummaryDetail)||_extractToolKey(rawFullDetail)) : '',
   stepKey:stepKey,
   reasonKind:reasonKind,
   goal:goal,
   decisionNote:decisionNote,
   handoffNote:handoffNote,
   expectedOutput:expectedOutput,
   nextUserNeed:nextUserNeed,
   toolName:toolName
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

 function _stepIconState(phase, status){
  var current=String(status||'done');
  if(current==='error') return 'error';
  if(phase==='thinking') return 'thinking';
  return current==='running' ? 'running' : 'done';
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
  if(pendingState.status){
   pendingState.status.style.display='none';
   pendingState.status.setAttribute('aria-expanded','false');
  }
  if(pendingState.tracker){
   pendingState.tracker.style.display='none';
   pendingState.tracker.classList.add('collapsed');
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
  var previousStatus=String(stepObj.status||'');
  if(stepObj.kind==='process'){
   if(previousStatus!=='running' && newStatus==='running'){
    stepObj.startedAt=Date.now();
   }else if(previousStatus==='running' && newStatus!=='running'){
    var elapsed=Math.max(1, Math.round((Date.now()-Number(stepObj.startedAt||Date.now()))/1000));
    var finalFull=_appendElapsedSuffix(stepObj.fullDetail||stepObj.summaryDetail, elapsed);
    var finalSummary=_appendElapsedSuffix(stepObj.summaryDetail||stepObj.fullDetail, elapsed);
    stepObj.fullDetail=finalFull;
    stepObj.summaryDetail=_collapseProcessDetail(finalSummary||finalFull, stepObj.phase, newStatus);
    _syncProcessDetailDisplay(stepObj);
   }
  }
  stepObj.status=newStatus;
  if(stepObj.kind==='process'){
   stepObj.root.className='msg assistant process-msg'+(newStatus==='running'?' is-running':'')+(newStatus==='error'?' is-error':'');
   if(stepObj.line) stepObj.line.className='process-line '+(newStatus==='error'?'error':(newStatus==='running'?'running':'done'));
   if(stepObj.markerEl) _setProcessMarker(stepObj.markerEl, stepObj.displayLabel||stepObj.label, newStatus);
   _syncProcessPhase(stepObj);
   return;
  }
  stepObj.el.className='step-item '+newStatus;
  if(stepObj.iconEl) stepObj.iconEl.className='step-icon '+_stepIconState(stepObj.phase, newStatus);
 }

 function _applyStepDetail(stepObj, detail, fullDetail){
 if(!stepObj || !stepObj.detailEl) return;
 if(stepObj.kind==='process'){
  var displayLabel=stepObj.displayLabel||stepObj.label||t('chat.process');
  var previousFull=String(stepObj.fullDetail||'').trim();
  var previousSummary=String(stepObj.summaryDetail||previousFull).trim();
  var cleanedFull=_cleanProcessDetail(fullDetail||detail, stepObj.label, displayLabel, stepObj.status);
  var cleanedSummary=_cleanProcessDetail(detail||fullDetail, stepObj.label, displayLabel, stepObj.status);
  cleanedFull=_mergeProcessDetailWithPrevious(cleanedFull, previousFull||previousSummary);
  cleanedSummary=_mergeProcessDetailWithPrevious(cleanedSummary, previousSummary||previousFull);
  if(stepObj.status==='running'){
   cleanedFull=_preserveProcessWaitSuffix(cleanedFull, previousFull||previousSummary);
   cleanedSummary=_preserveProcessWaitSuffix(cleanedSummary, previousSummary||previousFull);
  }
  if(!cleanedFull) cleanedFull=cleanedSummary;
  if(!cleanedSummary) cleanedSummary=cleanedFull;
  stepObj.summaryDetail=_collapseProcessDetail(cleanedSummary||cleanedFull, stepObj.phase, stepObj.status);
  stepObj.fullDetail=cleanedFull||stepObj.summaryDetail;
  if(stepObj.labelEl) stepObj.labelEl.textContent=stepObj.displayLabel||stepObj.label||t('chat.process');
  _syncProcessDetailDisplay(stepObj);
  return;
 }
 stepObj.summaryDetail=String(detail||'').trim();
  stepObj.fullDetail=String(fullDetail||'').trim();
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
  stepObj.stepKey=meta.stepKey;
  stepObj.reasonKind=meta.reasonKind;
  stepObj.goal=meta.goal;
  stepObj.decisionNote=meta.decisionNote;
  stepObj.handoffNote=meta.handoffNote;
  stepObj.expectedOutput=meta.expectedOutput;
  stepObj.nextUserNeed=meta.nextUserNeed;
  stepObj.toolName=meta.toolName;
  stepObj.displayLabel=meta.displayLabel;
  if(stepObj.labelEl) stepObj.labelEl.textContent=meta.displayLabel||t('chat.process');
  if(stepObj.kind==='process') _syncProcessPhase(stepObj);
  _applyStepDetail(stepObj, meta.summaryDetail, meta.fullDetail);
 }

 function _createActivityStep(meta){
  var step=createProcessMessage({
   label:meta.displayLabel||t('chat.process'),
   detail:meta.summaryDetail||meta.fullDetail,
   full_detail:meta.fullDetail||meta.summaryDetail,
   status:meta.status,
   phase:meta.phase,
   step_key:meta.stepKey,
   reason_kind:meta.reasonKind,
   goal:meta.goal,
   decision_note:meta.decisionNote,
   handoff_note:meta.handoffNote,
   expected_output:meta.expectedOutput,
   next_user_need:meta.nextUserNeed,
   tool_name:meta.toolName
  });
  step.label=meta.rawLabel;
  step.displayLabel=meta.displayLabel;
  step.summaryDetail=meta.summaryDetail;
  step.fullDetail=meta.fullDetail;
  step.phase=meta.phase;
  step.toolKey=meta.toolKey;
  step.stepKey=meta.stepKey;
  step.reasonKind=meta.reasonKind;
  step.goal=meta.goal;
  step.decisionNote=meta.decisionNote;
  step.handoffNote=meta.handoffNote;
  step.expectedOutput=meta.expectedOutput;
  step.nextUserNeed=meta.nextUserNeed;
  step.toolName=meta.toolName;
  chat.insertBefore(step.root, pendingState.root);
  return step;
 }

 function _canMergeStep(existing, meta){
  if(!existing || !meta) return false;
  if(existing.stepKey && meta.stepKey && existing.stepKey===meta.stepKey) return true;
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

  _stickChatToBottom();
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
  pendingState.root.style.display='';
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i].status==='running') _setStepStatus(pendingState.steps[i],'done');
  }
  if(pendingState.labelTimer){ clearInterval(pendingState.labelTimer); pendingState.labelTimer=null; }
  _collapseSteps();
  if(pendingState.steps.length) _ensureTraceDetached();
  // 隐藏 spinner，显示内容区
  pendingState.status.style.display='none';
  pendingState.root.className='msg assistant';
  var contentArea=pendingState.contentArea;
  contentArea.style.display='';
  contentArea.innerHTML='';
  var bubble=document.createElement('div');
  bubble.className='bubble';
  var lineEl=document.createElement('span');
  lineEl.className='stream-live-line';
  bubble.appendChild(lineEl);
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
  _streamLineEl=lineEl;
  _streamLiveText='';
  _streamRenderedText='';
  _streamFlushBuffer='';
  _streamStarted=true;
  _suppressTypingCursor=false;
  _streamTokenCount=0;
  _lastRenderedBlockCount=0;
  _destroyStreamMeasureHost();
  // 思考步骤结束、回复开始 → 强制滚到底部，确保用户能看到新内容
  _stickChatToBottom();
 }

 var _scrollRAF=0; // scroll 节流
var _renderTimer=0; // 渐进渲染节流
var _streamTokenCount=0; // 流式 token 计数，前 N 个无条件滚动
 var _lastRenderedBlockCount=0; // 上次渲染的块数，用于 fade-in 新块
var _streamLineEl=null;
var _streamLiveText='';
var _streamRenderedText='';
var _streamFlushBuffer='';
var _streamMeasureHost=null;
var _streamMeasureLine=null;

 // Stream UI invariants:
 // 1. Completed fragments must be promoted above pendingState.root so the newest text stays at the bottom.
 // 2. Fragment promotion prefers explicit newline, then visual-line overflow as fallback.
 // 3. Finalization may complete the trailing remainder, but must not flatten already promoted fragments back into one block.

 // 判断是否在底部附近（阈值 120px），避免强制跳视图打断用户回翻
 function _nearBottom(){
  return chat.scrollHeight - chat.scrollTop - chat.clientHeight < 120;
 }

 function _getStreamRenderWidth(){
  if(pendingState.contentArea){
   var contentWidth=Math.floor(pendingState.contentArea.clientWidth||0);
   if(contentWidth>0) return Math.max(contentWidth-2, 0);
  }
  if(pendingState.wrap){
   var wrapWidth=Math.floor(pendingState.wrap.clientWidth||0);
   if(wrapWidth>0) return Math.max(wrapWidth-2, 0);
  }
  if(pendingState.root){
   var rootWidth=Math.floor(pendingState.root.clientWidth||0);
   if(rootWidth>0) return Math.max(rootWidth-2, 0);
  }
  return 0;
 }

 function _destroyStreamMeasureHost(){
  if(_streamMeasureHost && _streamMeasureHost.parentNode){
   _streamMeasureHost.parentNode.removeChild(_streamMeasureHost);
  }
  _streamMeasureHost=null;
  _streamMeasureLine=null;
 }

 function _ensureStreamMeasureLine(){
  if(_streamMeasureHost && _streamMeasureLine) return _streamMeasureLine;
  var host=document.createElement('div');
  host.className='bubble';
  host.style.position='fixed';
  host.style.left='-100000px';
  host.style.top='-100000px';
  host.style.visibility='hidden';
  host.style.pointerEvents='none';
  host.style.margin='0';
  host.style.padding='0';
  host.style.border='none';
  host.style.maxWidth='none';
  host.style.minWidth='0';
  host.style.whiteSpace='pre-wrap';
  host.style.wordBreak='break-word';
  host.style.overflowWrap='break-word';
  host.setAttribute('aria-hidden','true');
  var line=document.createElement('span');
  line.className='stream-live-line';
  host.appendChild(line);
  document.body.appendChild(host);
  _streamMeasureHost=host;
  _streamMeasureLine=line;
  return line;
 }

 function _syncStreamMeasureHost(){
  var line=_ensureStreamMeasureLine();
  var width=_getStreamRenderWidth();
  if(width>0) _streamMeasureHost.style.width=width+'px';
  if(_streamBubble){
   var style=window.getComputedStyle(_streamBubble);
   _streamMeasureHost.style.font=style.font;
   _streamMeasureHost.style.lineHeight=style.lineHeight;
   _streamMeasureHost.style.letterSpacing=style.letterSpacing;
   _streamMeasureHost.style.fontKerning=style.fontKerning;
   _streamMeasureHost.style.textTransform=style.textTransform;
  }
  return line;
 }

function _streamLineHtml(line){
  var text=String(line||'');
  if(!text) return '<div class="bubble-spacer"></div>';
  var html;
  if(typeof formatMarkdownInline==='function'){
    html=formatMarkdownInline(text);
  }else{
    html=escapeHtml(text);
    html=html.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
    html=html.replace(/`([^`]+)`/g,'<code>$1</code>');
  }
  return '<p>'+html+'</p>';
}

 function _countStreamVisualLines(text){
  if(!text) return 1;
  var line=_syncStreamMeasureHost();
  line.textContent=String(text||'');
  var rects=line.getClientRects();
  if(rects && rects.length) return rects.length;
  var style=window.getComputedStyle(_streamBubble||_streamMeasureHost);
  var lineHeight=parseFloat(style.lineHeight||'0');
  if(!(lineHeight>0)) lineHeight=parseFloat(style.fontSize||'16')*1.46;
  return Math.max(1, Math.round((_streamMeasureHost.scrollHeight||lineHeight)/lineHeight));
 }

 function _fitsSingleStreamLine(text){
  if(!text) return true;
  return _countStreamVisualLines(text)<=1;
 }

 function _findStreamBreakIndex(text){
  var chars=Array.from(String(text||''));
  if(chars.length<=1) return chars.length;
  var low=1;
  var high=chars.length-1;
  var best=1;
  while(low<=high){
   var mid=Math.floor((low+high)/2);
   var candidate=chars.slice(0, mid).join('');
   if(_fitsSingleStreamLine(candidate)){
    best=mid;
    low=mid+1;
   }else{
    high=mid-1;
   }
  }
  return best;
 }

 function _removeTrailingStreamParts(keepCount){
  while(_streamParts.length>keepCount){
   var stalePart=_streamParts.pop();
   if(stalePart && stalePart.root && stalePart.root.parentNode){
    stalePart.root.parentNode.removeChild(stalePart.root);
   }
  }
 }

 function _syncPromotedStreamParts(parts){
  var normalized=Array.isArray(parts) ? parts : [];
  var anchor=pendingState.root;
  for(var i=normalized.length-1;i>=0;i--){
   var html=_streamLineHtml(normalized[i]);
   var part=_streamParts[i];
   if(!part){
    part=createReplyPartMessage(html);
    _streamParts[i]=part;
   }else if(part.bubble && part.bubble.innerHTML!==html){
    part.bubble.innerHTML=html;
   }
   if(part.root && (part.root.parentNode!==chat || part.root.nextSibling!==anchor)){
    chat.insertBefore(part.root, anchor);
   }
   anchor=part.root;
  }
  _removeTrailingStreamParts(normalized.length);
 }

 function _scheduleProgressiveRender(delay){
  if(_renderTimer || !_streamBubble) return;
  _renderTimer=setTimeout(_progressiveRender, Math.max(0, Number(delay)||0));
 }

 function _takeStreamRenderChunk(){
  if(!_streamFlushBuffer) return '';
  var chars=Array.from(_streamFlushBuffer);
  if(!chars.length) return '';
  var maxChars=chars.length>120 ? 32 : 16;
  if(chars.length<=maxChars){
   var fullChunk=_streamFlushBuffer;
   _streamFlushBuffer='';
   return fullChunk;
  }
  var minChars=Math.max(1, maxChars-8);
  var cut=maxChars;
  for(var i=maxChars;i>=minChars;i--){
   if(/[\s,.;:!?\u3001\u3002\uFF01\uFF1F\uFF1B\uFF1A]/.test(chars[i-1])){
    cut=i;
    break;
   }
  }
 var chunk=chars.slice(0, cut).join('');
 _streamFlushBuffer=chars.slice(cut).join('');
 return chunk;
}

 function _findTypingCursorHost(root){
  if(!root) return null;
  var blocks=root.querySelectorAll('.bubble p,.bubble h1,.bubble h2,.bubble h3,.bubble blockquote,li,pre');
  if(!blocks.length) return null;
  var last=blocks[blocks.length-1];
  if(last && last.tagName && last.tagName.toLowerCase()==='pre'){
   var code=last.querySelector('code');
   if(code) return code;
  }
  return last;
 }

 function _attachTypingCursor(){
  return;
 }

 function _hideTypingCursor(){
  if(!_streamBubble) return;
  var cursor=_streamBubble.querySelector('.typing-cursor');
  if(cursor && cursor.parentNode) cursor.parentNode.removeChild(cursor);
 }

 function _normalizeStreamCompareText(text){
  return String(text||'').replace(/\s+/g,' ').trim();
 }

function _chooseFinalStreamText(replyText, streamedText){
 var reply=String(replyText||'');
 var streamed=String(streamedText||'');
  if(!reply) return streamed;
  if(!streamed) return reply;
  var replyNorm=_normalizeStreamCompareText(reply);
  var streamedNorm=_normalizeStreamCompareText(streamed);
  if(!replyNorm) return streamed || reply;
  if(!streamedNorm) return reply;
  if(streamedNorm.length>replyNorm.length+8 && streamedNorm.indexOf(replyNorm)===0){
   return streamed;
  }
  if(replyNorm.length>streamedNorm.length+8 && replyNorm.indexOf(streamedNorm)===0){
   return reply;
  }
  if(streamedNorm.length>replyNorm.length+24){
   return streamed;
  }
  return reply;
 }

 function _chooseFinalStreamHtml(finalText, replyText, renderedHtml){
  var html=String(renderedHtml||'').trim();
  if(!html) return '';
  if(typeof normalizeRenderedAssistantHtml === 'function'){
    html=normalizeRenderedAssistantHtml(html);
  }
  var finalNorm=_normalizeStreamCompareText(finalText);
  var replyNorm=_normalizeStreamCompareText(replyText);
  if(!finalNorm || !replyNorm) return '';
  return finalNorm===replyNorm ? html : '';
}

 function _renderCurrentStreamLine(){
  if(!_streamBubble) return;
  _streamBubble.innerHTML=_streamLineHtml(_streamLiveText)||'<div class="bubble-spacer"></div>';
  _attachTypingCursor();
 }

 function _splitStreamFragments(text){
  var remaining=String(text||'').replace(/\r/g,'');
  var parts=[];
  while(true){
   if(!remaining) break;
   // Treat leading blank lines as paragraph separators only; do not promote them as empty reply parts.
   while(remaining.charAt(0)==='\n'){
    remaining=remaining.slice(1);
   }
   if(!remaining) break;
   var newlineIndex=remaining.indexOf('\n');
   if(newlineIndex>=0){
    // Only explicit newlines create promoted fragments. Sentence punctuation alone stays in the same message.
    var paragraphPart=remaining.slice(0, newlineIndex);
    if(paragraphPart) parts.push(paragraphPart);
    remaining=remaining.slice(newlineIndex+1);
    continue;
   }
   if(_fitsSingleStreamLine(remaining)) break;
   var chars=Array.from(remaining);
   var splitCount=_findStreamBreakIndex(remaining);
   if(splitCount<=0) splitCount=1;
   if(splitCount>=chars.length) splitCount=chars.length-1;
   parts.push(chars.slice(0, splitCount).join(''));
   remaining=chars.slice(splitCount).join('');
  }
  return {
   parts:parts,
   live:remaining
  };
 }

 function _renderStreamSnapshot(text){
  var snapshot=_splitStreamFragments(text);
  _syncPromotedStreamParts(snapshot.parts);
  _streamLiveText=snapshot.live;
  _renderCurrentStreamLine();
  _lastRenderedBlockCount=snapshot.parts.length+(_streamLiveText?1:0);
 }

 function _consumeStreamChunk(chunk){
  var incoming=String(chunk||'').replace(/\r/g,'');
  if(!incoming) return;
  _streamRenderedText+=incoming;
  _renderStreamSnapshot(_streamRenderedText);
 }

 function _progressiveRender(){
  _renderTimer=0;
  if(!_streamBubble) return;
  var chunk=_takeStreamRenderChunk();
  if(chunk) _consumeStreamChunk(chunk);
  _streamTokenCount++;
  if(_streamTokenCount<=5 || _nearBottom()){
   if(!_scrollRAF){
    _scrollRAF=requestAnimationFrame(function(){
     _stickChatToBottom();
     _scrollRAF=0;
    });
   }
  }
  if(_streamFlushBuffer){
   _scheduleProgressiveRender(_streamTokenCount<=6 ? 12 : 16);
  }
 }

function _appendStreamToken(token){
  if(!_streamStarted) _initStreamBubble();
  _streamText+=token;
  _streamFlushBuffer+=token;
  // 大 chunk 也拆成多帧显示，避免视觉上像一次性整段吐出。
  _scheduleProgressiveRender(_streamTokenCount<3 ? 8 : 16);
 }

 function _appendStreamToken(token){
  if(!_streamStarted) _initStreamBubble();
  _streamText+=token;
  _streamFlushBuffer+=token;
  // Large chunks still advance over multiple frames so the newest fragment stays anchored at the bottom.
  _scheduleProgressiveRender(_streamTokenCount<3 ? 8 : 16);
 }

 function _resetActiveStreamRender(){
  if(_renderTimer){
   clearTimeout(_renderTimer);
   _renderTimer=0;
  }
  if(_scrollRAF){
   cancelAnimationFrame(_scrollRAF);
   _scrollRAF=0;
  }
  _clearStreamParts();
  _destroyStreamMeasureHost();
  _streamBubble=null;
  _streamLineEl=null;
  _streamText='';
  _streamLiveText='';
  _streamRenderedText='';
  _streamFlushBuffer='';
  _streamTokenCount=0;
  _lastRenderedBlockCount=0;
  _streamStarted=false;
  _suppressTypingCursor=false;
  if(pendingState.contentArea){
   pendingState.contentArea.innerHTML='';
   pendingState.contentArea.style.display='none';
  }
 }

function _finalizeStream(fullText, renderedHtml){
  if(!_streamBubble) return;
  if(_renderTimer){
   clearTimeout(_renderTimer);
   _renderTimer=0;
  }
  if(_streamFlushBuffer){
   _consumeStreamChunk(_streamFlushBuffer);
   _streamFlushBuffer='';
  }
  var finalText=String(fullText||'');
  if(finalText) _streamRenderedText=finalText;
  var finalRenderText=String(_streamRenderedText||finalText||'');
  // Streaming may temporarily promote fragments as standalone reply-part messages.
  // Once the reply is complete, collapse everything back into one fully formatted bubble
  // so live messages match history re-rendering and keep list/paragraph hierarchy intact.
  _clearStreamParts();
  _streamLiveText='';
  var finalLineHtml=renderAssistantBubbleHtml(finalRenderText, renderedHtml)||'<div class="bubble-spacer"></div>';
  _streamRenderedText=finalRenderText;
  _streamBubble.innerHTML=finalLineHtml||'<div class="bubble-spacer"></div>';
  var fadingBlocks=_streamBubble.querySelectorAll('.block-fade-in');
  for(var fi=0;fi<fadingBlocks.length;fi++){fadingBlocks[fi].classList.remove('block-fade-in');}
  _streamLineEl=null;
  _streamLiveText='';
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
  _stickChatToBottom();
  _destroyStreamMeasureHost();
  if(!pendingState.persisted){
   _snapshotChatHistory();
   // 持久化 steps 摘要
   if(pendingState.steps&&pendingState.steps.length>0){
    var stepsMap=JSON.parse(localStorage.getItem('nova_steps_map')||'{}');
    var tsKey=String(Date.now());
    stepsMap[tsKey]=pendingState.steps.map(function(s){
     return {
      label:s.label||'',
      detail:s.summaryDetail||s.fullDetail||((s.detailEl&&s.detailEl.dataset&&s.detailEl.dataset.rawDetail)||''),
      full_detail:s.fullDetail||s.summaryDetail||((s.detailEl&&s.detailEl.dataset&&s.detailEl.dataset.rawDetail)||''),
      status:s.status||'done',
      step_key:s.stepKey||'',
      phase:s.phase||'',
      reason_kind:s.reasonKind||'',
      goal:s.goal||'',
      decision_note:s.decisionNote||'',
      handoff_note:s.handoffNote||'',
      expected_output:s.expectedOutput||'',
      next_user_need:s.nextUserNeed||'',
      tool_name:s.toolName||''
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

 function _renderReplyViaStream(text, renderedHtml){
  var finalText=String(text||_streamText||'').trim();
  if(!finalText) finalText=t('chat.error.retry');
  if(!_streamStarted){
   _initStreamBubble();
  }
  _streamText=finalText;
  _finalizeStream(finalText, renderedHtml);
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
        replyHtml=parsed.reply_html||'';
        if(parsed.image) replyImage=parsed.image;
        // 本轮回复完成 → 复位状态点为金色
        try{ setTimeout(function(){_setCodDot('flash');},600); }catch(e){}
        _suppressTypingCursor=true;
        _hideTypingCursor();
       }else if(currentEvent==='agent_step'){
        if(parsed.phase==='complete'){
         for(var si=0;si<pendingState.steps.length;si++){
          if(pendingState.steps[si].status==='running') _setStepStatus(pendingState.steps[si],'done');
         }
         }else if(parsed.phase==='waiting'){
          var _waitLabel=String(parsed.label||'').trim();
          var _waitDetail=String(parsed.detail||'').trim();
          var _waitStepKey=String(parsed.step_key||'').trim();
          var _runningStep=null;
          for(var wi=pendingState.steps.length-1;wi>=0;wi--){
           if(pendingState.steps[wi] && pendingState.steps[wi].status==='running' && _waitStepKey && pendingState.steps[wi].stepKey===_waitStepKey){
            _runningStep=pendingState.steps[wi];
            break;
           }
          }
          if(!_runningStep){
           for(var wj=pendingState.steps.length-1;wj>=0;wj--){
            if(pendingState.steps[wj] && pendingState.steps[wj].status==='running'){
             _runningStep=pendingState.steps[wj];
             break;
            }
           }
          }
          if(_runningStep){
           if(_waitLabel && _runningStep.label!==_waitLabel && (!_waitStepKey || _runningStep.stepKey!==_waitStepKey)){
            addStep({
             label:_waitLabel,
             detail:_waitDetail||_waitLabel,
             status:'running',
             full_detail:_waitDetail||_waitLabel,
             step_key:_waitStepKey,
             phase:parsed.phase||'waiting',
             reason_kind:parsed.reason_kind||'',
             goal:parsed.goal||'',
             decision_note:parsed.decision_note||'',
             handoff_note:parsed.handoff_note||'',
             expected_output:parsed.expected_output||'',
             next_user_need:parsed.next_user_need||'',
             tool_name:parsed.tool_name||''
            });
           }else if(_waitDetail){
           if(parsed.step_key) _runningStep.stepKey=parsed.step_key;
           _applyStepDetail(_runningStep, _waitDetail, _waitDetail);
            _stickChatToBottom();
           }
          }else if(_waitLabel || _waitDetail){
           addStep({
            label:_waitLabel||t('chat.process'),
            detail:_waitDetail||_waitLabel,
            status:'running',
            full_detail:_waitDetail||_waitLabel,
            step_key:_waitStepKey,
            phase:parsed.phase||'waiting',
            reason_kind:parsed.reason_kind||'',
            goal:parsed.goal||'',
            decision_note:parsed.decision_note||'',
            handoff_note:parsed.handoff_note||'',
            expected_output:parsed.expected_output||'',
            next_user_need:parsed.next_user_need||'',
            tool_name:parsed.tool_name||''
           });
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
       }else if(currentEvent==='stream_reset'){
        _resetActiveStreamRender();
       }else if(currentEvent==='reply'){
        replyText=parsed.reply||t('chat.error.retry');
        replyHtml=parsed.reply_html||'';
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
  var finalText=_chooseFinalStreamText(replyText, _streamText)||t('chat.error.retry');
  var finalHtml=_chooseFinalStreamHtml(finalText, replyText, replyHtml);
  _finalizeStream(finalText, finalHtml);
 }else if(replyText){
   _renderReplyViaStream(replyText, replyHtml);
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
    var abortText=_chooseFinalStreamText(replyText, _streamText)||_streamText;
    var abortHtml=_chooseFinalStreamHtml(abortText, replyText, replyHtml);
    _finalizeStream(abortText, abortHtml);
   }else if(replyText){
    _renderReplyViaStream(replyText, replyHtml);
   }else{
    finalizePendingAssistantMessage(pendingState, t('chat.stopped')||'已停止');
   }
  }else{
   finalizePendingAssistantMessage(pendingState, t('chat.error.noconnect'));
  }
 }
 _abortController=null;
 _exitStopMode();
 _stickChatToBottom();
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

var _TASK_PLAN_BOARD_ENABLED=false;

function _renderSessionTaskPlan(){
 var board=document.getElementById('taskPlanBoard');
 if(!board) return;
 if(!_TASK_PLAN_BOARD_ENABLED){
  board.style.display='none';
  board.innerHTML='';
  return;
 }
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

 function _setAskUserError(errorEl, text){
  if(!errorEl) return;
  var value=String(text||'').trim();
  errorEl.textContent=value;
  errorEl.style.display=value?'block':'none';
 }

 function _buildAskUserCustomAnswer(text){
  var trimmed=String(text||'').trim();
  if(trimmed){
   return {
    answer:'我不选上面的候选项，我的真实意思是：'+trimmed,
    preview:trimmed.length>26?trimmed.slice(0,26)+'...':trimmed
   };
  }
  return {
   answer:'我不选上面的候选项，请重新理解我的意思，并换一个方向来问我或给我新的方案。',
   preview:'拒绝这些选项，请重新理解'
  };
 }

 var card=document.createElement('div');
 card.className='ask-user-card';
 card.innerHTML='<div class="ask-user-question">'+escapeHtml(question)+'</div>';
 var optionsDiv=document.createElement('div');
 optionsDiv.className='ask-user-options';
 var customTrigger=document.createElement('button');
 customTrigger.type='button';
 customTrigger.className='ask-user-option ask-user-none';
 customTrigger.textContent='以上都不选，我自己补充';
 var customPanel=document.createElement('div');
 customPanel.className='ask-user-custom-panel';
 customPanel.innerHTML='<div class="ask-user-custom-hint">不想选上面的项时，直接写给 Nova。留空提交也会按“拒绝这些选项，请重新理解”处理。</div>';
 var customInput=document.createElement('textarea');
 customInput.className='ask-user-custom-input';
 customInput.rows=3;
 customInput.placeholder='直接写你真正想表达的意思；如果只是想拒绝这些选项，也可以留空后提交。';
 var customSubmit=document.createElement('button');
 customSubmit.type='button';
 customSubmit.className='ask-user-custom-submit';
 customSubmit.textContent='提交我的补充';
 var errorEl=document.createElement('div');
 errorEl.className='ask-user-error';
 customPanel.appendChild(customInput);
 customPanel.appendChild(customSubmit);

 function _setAskUserDisabled(disabled){
  var btns=card.querySelectorAll('button');
  for(var i=0;i<btns.length;i++) btns[i].disabled=!!disabled;
  customInput.disabled=!!disabled;
 }

 function _setCustomPanelOpen(open){
  customPanel.style.display=open?'block':'none';
  customTrigger.classList.toggle('selected', !!open);
  if(open){
   setTimeout(function(){ customInput.focus(); },0);
  }
 }

 function _submitAskUserAnswer(answerText, progressText, selectedBtn, keepCustomOpen){
  var choiceBtns=card.querySelectorAll('.ask-user-option');
  if(!qid){
   _setAskUserError(errorEl, '这轮选项已经失效了，重新让 Nova 提一次就好。');
   return;
  }
  _setAskUserError(errorEl, '');
  for(var i=0;i<choiceBtns.length;i++) choiceBtns[i].classList.remove('selected');
  if(selectedBtn) selectedBtn.classList.add('selected');
  _setAskUserDisabled(true);
  fetch('/chat/answer',{
   method:'POST',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({question_id:qid,answer:answerText})
  }).then(function(resp){
   return resp.json().catch(function(){ return {ok:false}; });
  }).then(function(payload){
   if(!(payload&&payload.ok)) throw new Error('ask_user_submit_failed');
   _addTaskProgress(question, progressText);
   setTimeout(function(){ _dismissAskUserCard(slot, card); },400);
  }).catch(function(){
   _setAskUserDisabled(false);
   if(keepCustomOpen){
    _setCustomPanelOpen(true);
   }else if(selectedBtn){
    selectedBtn.classList.remove('selected');
   }
   _setAskUserError(errorEl, '这次没有提交成功，可能这轮选项已过期了。你可以再试一次。');
  });
 }

 // LLM 给的选项
 options.forEach(function(opt){
  var btn=document.createElement('button');
  btn.type='button';
  btn.className='ask-user-option';
  btn.textContent=opt;
  btn.onclick=function(){
   _setCustomPanelOpen(false);
   _submitAskUserAnswer(opt, opt, btn, false);
  };
  optionsDiv.appendChild(btn);
 });

 customTrigger.onclick=function(){
  if(customTrigger.disabled) return;
  _setAskUserError(errorEl, '');
  _setCustomPanelOpen(customPanel.style.display!=='block');
 };

 customSubmit.onclick=function(){
  var built=_buildAskUserCustomAnswer(customInput.value);
  _submitAskUserAnswer(built.answer, built.preview, customTrigger, true);
 };

 customInput.addEventListener('keydown', function(event){
  if(event.key==='Enter' && (event.ctrlKey || event.metaKey)){
   event.preventDefault();
   customSubmit.click();
  }
 });

 optionsDiv.appendChild(customTrigger);
 optionsDiv.appendChild(customPanel);
 optionsDiv.appendChild(errorEl);
 card.appendChild(optionsDiv);
 if(slot){
  slot.innerHTML='';
  slot.style.display='';
  slot.appendChild(card);
 }else{
  // fallback：插到聊天区底部
 var chat=document.getElementById('chat');
 chat.appendChild(card);
  _stickChatToBottom();
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
