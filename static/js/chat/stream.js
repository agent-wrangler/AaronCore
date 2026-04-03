// Send flow, SSE handling, stream rendering, and thinking steps
// Source: chat.js lines 712-1968

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
