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

 addMessage(t('chat.you'),text,'user',image,'',images);
 inp.value='';
 inp.style.height='auto';
 _pendingImages=[];
 renderImagePreviews();
 updateSendButton();

 var btn=document.getElementById('sendBtn');
 btn.classList.add('sending');
 setTimeout(function(){btn.classList.remove('sending');},500);
 _enterStopMode();
 _dispatchChatRequestState('started', {
  source:'send',
  text_length:text.length,
  image_count:images.length,
  voice_mode:!!window._voiceMode
 });
var pendingState=buildPendingAssistantMessage();
var chat=document.getElementById('chat');
var _runPanelEls=_getRunPanelEls();
var _runPromptText=String(text||'').replace(/\s+/g,' ').trim();
var _runNumber=_nextRunPanelConsoleCounter();
var _runStartedAt=Date.now();
_pendingModelSwitchNote=null;
var _runFinishedAt=0;
var _runElapsedTimer=0;
var _runPanelAutoFollow=true;
var _runPanelScrollFollowBound=false;
var _runPanelFollowRAF=0;

  var replyText='';
  var replyImage='';
  var _thinkingContent='';
  var _showRawThinkingPanel=false;
  var repairData=null;
  var hasTrace=false;
  var _streamRuntime=null;



function _formatRunElapsedLabel(){
 var endAt=_runFinishedAt||Date.now();
 var totalSeconds=Math.max(0, Math.floor((endAt-Number(_runStartedAt||endAt))/1000));
 var hours=Math.floor(totalSeconds/3600);
 var minutes=Math.floor((totalSeconds%3600)/60);
 var seconds=totalSeconds%60;
 if(hours>0){
  return String(hours).padStart(2,'0')+':'+String(minutes).padStart(2,'0')+':'+String(seconds).padStart(2,'0');
 }
 return String(minutes).padStart(2,'0')+':'+String(seconds).padStart(2,'0');
}


function _isRunPanelNearBottom(threshold){
 if(!_runPanelEls || !_runPanelEls.stream) return true;
 var host=_runPanelEls.stream;
 var gap=host.scrollHeight-host.scrollTop-host.clientHeight;
 return gap < (typeof threshold==='number' ? threshold : 72);
}

function _syncRunPanelAutoFollow(){
 _runPanelAutoFollow=_isRunPanelNearBottom(72);
}

function _attachRunPanelScrollFollow(){
 if(!_runPanelEls || !_runPanelEls.stream || _runPanelScrollFollowBound) return;
 _runPanelEls.stream.addEventListener('scroll', _syncRunPanelAutoFollow, {passive:true});
 _runPanelScrollFollowBound=true;
 _syncRunPanelAutoFollow();
}

function _queueRunPanelFollow(force){
 if(!_runPanelEls || !_runPanelEls.stream) return;
 if(!force && !_runPanelAutoFollow) return;
 if(_runPanelFollowRAF){
  cancelAnimationFrame(_runPanelFollowRAF);
 }
 _runPanelFollowRAF=requestAnimationFrame(function(){
  _runPanelFollowRAF=0;
  requestAnimationFrame(function(){
   if(!_runPanelEls || !_runPanelEls.stream) return;
   if(!force && !_runPanelAutoFollow) return;
   var host=_runPanelEls.stream;
   host.scrollTop=host.scrollHeight;
  });
 });
}

function _ensureRunPanelEntries(){
 if(!_runPanelEls || !_runPanelEls.stream) return;
 var shouldFollow=_runPanelAutoFollow;
 var steps=pendingState.steps||[];
 _runPanelEls.stream.setAttribute('data-step-count', String(steps.length));
 if(!steps.length){
  _runPanelEls.stream.innerHTML='<div class="run-panel-empty" id="runPanelEmpty">'+_escapeRunPanelText(_runPanelCopy.empty)+'</div>';
  _runPanelEls.empty=document.getElementById('runPanelEmpty');
  _queueRunPanelFollow(shouldFollow);
  return;
 }
 var html='';
 var renderedCount=0;
 for(var i=0;i<steps.length;i++){
  var step=steps[i];
  var missing=!step;
  var labelText=_escapeRunPanelText(missing ? ('step_'+(i+1)) : (step.displayLabel||step.label||'Process'));
  var detailParts=missing ? {text:'Step data is not ready yet. Waiting for the next refresh.', wait:''} : _getRunPanelStepDetailParts(step);
  var stateText=_escapeRunPanelText(missing ? '' : _getRunPanelStepElapsed(step));
  var detailText=_escapeRunPanelText(detailParts.text||labelText);
  var phaseName=missing ? 'info' : String(step.phase||'info');
  var statusName=missing ? 'pending' : String(step.status||'done');
  var iconClass=_escapeRunPanelText(missing ? 'status-pending phase-info' : _getRunPanelStepIconClass(step));
  var badgeText=_escapeRunPanelText(missing ? '[WAIT]' : _getRunPanelStepBadge(step));
  html+=''
   +'<div class="run-stream-entry phase-'+_escapeRunPanelText(phaseName)+' status-'+_escapeRunPanelText(statusName)+'">'
   +'<div class="run-stream-entry-body">'
   +'<div class="run-stream-entry-meta">'
   +'<div class="run-stream-entry-title">'
   +'<div class="run-stream-entry-label">'+labelText+'</div>'
   +'<span class="run-stream-entry-icon '+iconClass+'" aria-hidden="true">'+badgeText+'</span>'
   +'</div>'
   +'<div class="run-stream-entry-state">'+stateText+'</div>'
   +'</div>'
   +'<div class="run-stream-entry-text">'+detailText+'</div>'
   +'</div>'
   +'</div>';
  renderedCount++;
 }
 _runPanelEls.stream.innerHTML=html;
 _runPanelEls.stream.setAttribute('data-rendered-count', String(renderedCount));
 _runPanelEls.empty=_runPanelEls.stream.querySelector('#runPanelEmpty');
 _queueRunPanelFollow(shouldFollow);
}

function _startRunElapsedClock(){
 if(_runElapsedTimer) clearInterval(_runElapsedTimer);
 _runElapsedTimer=setInterval(function(){
  _syncRunPanelHeader();
 },1000);
}

function _stopRunElapsedClock(){
 if(!_runFinishedAt) _runFinishedAt=Date.now();
 if(_runElapsedTimer){
  clearInterval(_runElapsedTimer);
  _runElapsedTimer=0;
 }
}



  function _syncRunPanelHeader(){
   if(!_runPanelEls) return;
   _ensureRunPanelMetaLine(_runPanelEls);
   _ensureRunPanelEntries();
   var steps=pendingState.steps||[];
   var runningStep=null;
   var latestStep=steps.length ? steps[steps.length-1] : null;
   var errorCount=0;
   var toolMap={};
   var fileMap={};
   for(var i=0;i<steps.length;i++){
    var step=steps[i];
    if(!step) continue;
    if(step.status==='running') runningStep=step;
    if(step.status==='error') errorCount++;
    var toolNames=_collectStepToolNames(step);
    for(var ti=0;ti<toolNames.length;ti++){
     var toolKey=String(toolNames[ti]||'').trim();
     if(toolKey) toolMap[toolKey.toLowerCase()]=toolKey;
    }
    var fileSources=[
     step.label,
     step.displayLabel,
     step.summaryDetail,
     step.fullDetail,
     step.goal,
     step.expectedOutput,
     step.nextUserNeed
    ];
    for(var fi=0;fi<fileSources.length;fi++){
     var files=_extractRunFiles(fileSources[fi]);
     for(var fj=0;fj<files.length;fj++){
      fileMap[files[fj].toLowerCase()]=files[fj];
     }
    }
   }
   var totalSteps=steps.length;
   if(pendingState.plan && pendingState.plan.items && pendingState.plan.items.length){
    totalSteps=Math.max(totalSteps, pendingState.plan.items.length);
   }
   var progressCurrent=steps.length;
   if(totalSteps===0) progressCurrent=0;
   if(progressCurrent>totalSteps) progressCurrent=totalSteps;
   var statusKey='idle';
   if(errorCount>0) statusKey='error';
   else if(runningStep) statusKey=_runPanelStateKey(runningStep.status, runningStep.phase);
   else if(_streamRuntime.hasStarted() || steps.length) statusKey='running';
   if(replyText) statusKey='done';
   var currentAction=_truncateRunText(
    pendingState.activitySummary
    || (runningStep && (runningStep.fullDetail||runningStep.summaryDetail||runningStep.displayLabel||runningStep.label))
    || (latestStep && (latestStep.fullDetail||latestStep.summaryDetail||latestStep.displayLabel||latestStep.label))
    || '',
    120
   );
  if(!currentAction){
    if(_streamRuntime.hasStarted() && !replyText) currentAction='Streaming reply';
    else if(steps.length) currentAction='Waiting for next action';
    else currentAction=_runPanelCopy.actionIdle;
   }
  _setRunPanelBusyState(statusKey==='thinking');
  if(_runPanelEls.status){
    _runPanelEls.status.textContent=_formatRunPanelConsoleStatus(statusKey, progressCurrent, totalSteps);
    _runPanelEls.status.className='run-panel-status-pill state-'+statusKey;
   }
   var outputTokenCount=_estimateRunPanelConsoleTokens(replyText||_streamRuntime.getText()||'');
   var inputTokenCount=_estimateRunPanelConsoleTokens(_runPromptText||'');
   if(_runPanelEls.kicker){
    _runPanelEls.kicker.textContent=_formatRunPanelConsoleHeader(_runNumber, _runStartedAt);
   }
   if(_runPanelEls.task){
    _runPanelEls.task.textContent='ELAPSED:   '+_formatRunElapsedLabel();
   }
   if(_runPanelEls.meta){
    _runPanelEls.meta.textContent=_formatRunPanelTokenLine(inputTokenCount, outputTokenCount);
   }
   if(_runPanelEls.progress){
    _runPanelEls.progress.textContent=(progressCurrent||0)+' / '+(totalSteps||0);
   }
   if(_runPanelEls.action){
    _runPanelEls.action.textContent=currentAction;
   }
   if(_runPanelEls.outputs){
    _runPanelEls.outputs.textContent=_formatRunPanelToolLine(Object.keys(fileMap).length, Object.keys(toolMap).length, errorCount);
   }
  }

function _syncRunPanelEntry(stepObj){
 if(!_runPanelEls || !stepObj) return;
 _ensureRunPanelEntries();
 }

 function _appendRunPanelEntry(stepObj){
  if(!_runPanelEls || !stepObj || !_runPanelEls.stream) return;
  stepObj.runPanelEl=null;
  stepObj.runPanelLabelEl=null;
  stepObj.runPanelStateEl=null;
  stepObj.runPanelTextEl=null;
  _ensureRunPanelEntries();
 }

function _resetRunPanelForCurrentRun(){
 if(!_runPanelEls) return;
 _attachRunPanelScrollFollow();
 _runPanelAutoFollow=true;
 if(_runPanelEls.stream) _runPanelEls.stream.innerHTML='';
 if(_runPanelEls.empty){
  _runPanelEls.empty.style.display='';
  if(_runPanelEls.stream) _runPanelEls.stream.appendChild(_runPanelEls.empty);
 }
  _setRunPanelEmptyState('idle');
  _runFinishedAt=0;
 _queueRunPanelFollow(true);
 _startRunElapsedClock();
 _syncRunPanelHeader();
}

 var _streamRuntime=_createStreamRuntime({
  chat:chat,
  pendingState:pendingState,
  collapseSteps:_collapseSteps,
  ensureTraceDetached:_ensureTraceDetached,
  getReplyImage:function(){ return replyImage; },
  getShowRawThinkingPanel:function(){ return _showRawThinkingPanel; },
  getThinkingContent:function(){ return _thinkingContent; },
  placePendingRootAtEnd:_placePendingRootAtEnd,
  pruneLowSignalStreamWaitingSteps:_pruneLowSignalStreamWaitingSteps,
  setStepStatus:_setStepStatus,
  setThinkingContent:function(value){ _thinkingContent=String(value||''); },
  snapshotChatHistory:_snapshotChatHistory,
  syncRunPanelHeader:_syncRunPanelHeader
 });

 _resetRunPanelForCurrentRun();

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

pendingState.placeholderTimer=setTimeout(function(){
  if(pendingState.replyVisible || pendingState.steps.length>0 || replyText) return;
  chat.appendChild(pendingState.root);
  _stickChatToBottom();
 },260);

function _ensureTraceDetached(){
  _placePendingRootAtEnd();
}


 function _isLowSignalStreamWaitingStep(stepLike){
  if(!stepLike) return false;
  if(!(_streamRuntime.hasStarted() || _streamRuntime.getText() || replyText)) return false;
  var phase=String(_stepLikeField(stepLike, 'phase', 'phase')||'').trim().toLowerCase();
  if(phase!=='waiting') return false;
 var toolName=String(_stepLikeField(stepLike, 'tool_name', 'toolName')||'').trim();
  if(toolName) return false;
  var stepKey=String(_stepLikeField(stepLike, 'step_key', 'stepKey')||'').trim();
  if(stepKey && stepKey.indexOf('thinking:decision')!==0) return false;
  var reasonKind=String(_stepLikeField(stepLike, 'reason_kind', 'reasonKind')||'').trim();
  var goal=String(_stepLikeField(stepLike, 'goal', 'goal')||'').trim();
  var decisionNote=String(_stepLikeField(stepLike, 'decision_note', 'decisionNote')||'').trim();
  var handoffNote=String(_stepLikeField(stepLike, 'handoff_note', 'handoffNote')||'').trim();
  var expectedOutput=String(_stepLikeField(stepLike, 'expected_output', 'expectedOutput')||'').trim();
  var nextUserNeed=String(_stepLikeField(stepLike, 'next_user_need', 'nextUserNeed')||'').trim();
  return !(reasonKind || goal || decisionNote || handoffNote || expectedOutput || nextUserNeed);
 }

 function _pruneLowSignalStreamWaitingSteps(){
  if(!pendingState || !pendingState.steps || !pendingState.steps.length) return;
  var kept=[];
  var removed=false;
  for(var i=0;i<pendingState.steps.length;i++){
   var step=pendingState.steps[i];
   if(_isLowSignalStreamWaitingStep(step)){
    removed=true;
    if(step && step.root && step.root.parentNode){
     step.root.parentNode.removeChild(step.root);
    }
    continue;
   }
   kept.push(step);
  }
  if(!removed) return;
  pendingState.steps=kept;
  if(kept.length){
   var last=kept[kept.length-1];
   pendingState.activitySummary=_buildActivitySummary({
    displayLabel:last.displayLabel||last.label||t('chat.process'),
    summaryDetail:last.summaryDetail||'',
    fullDetail:last.fullDetail||'',
    phase:last.phase||'info'
   });
  }else{
   pendingState.activitySummary='';
   _setRunPanelEmptyState('quiet');
  }
  _ensureRunPanelEntries();
  _syncRunPanelHeader();
 }


 function _hasErroredSteps(){
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i] && pendingState.steps[i].status==='error') return true;
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
   _syncRunPanelEntry(stepObj);
   _syncRunPanelHeader();
   return;
  }
  stepObj.el.className='step-item '+newStatus;
  if(stepObj.iconEl) stepObj.iconEl.className='step-icon '+_stepIconState(stepObj.phase, newStatus);
  _syncRunPanelEntry(stepObj);
  _syncRunPanelHeader();
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
   _syncRunPanelEntry(stepObj);
   _syncRunPanelHeader();
   return;
  }
  stepObj.summaryDetail=String(detail||'').trim();
   stepObj.fullDetail=String(fullDetail||'').trim();
   stepObj.detailEl.textContent=stepObj.fullDetail||stepObj.summaryDetail;
   _syncRunPanelEntry(stepObj);
   if(stepObj.status==='running'){
    pendingState.activitySummary=_buildActivitySummary({
     displayLabel:stepObj.displayLabel||stepObj.label||t('chat.process'),
    summaryDetail:stepObj.summaryDetail,
    fullDetail:stepObj.fullDetail,
    phase:stepObj.phase||'info'
    });
    _syncTrackerChrome();
  }
   _syncRunPanelHeader();
  }

 function _thinkingStepText(stepLike){
  return String((stepLike&&((stepLike.fullDetail||stepLike.summaryDetail||'')))||'').replace(/\s+/g,' ').trim();
 }

function _shouldSplitThinkingRevision(existing, meta){
  if(!existing || !meta) return false;
  if(existing.phase!=='thinking' || meta.phase!=='thinking') return false;
  if(!existing.stepKey || !meta.stepKey || existing.stepKey!==meta.stepKey) return false;
  if(existing.status==='error' || meta.status==='error') return false;
  var currentRevision=Math.max(1, parseInt(existing.thinkingRevision, 10)||1);
  if(currentRevision>=2) return false;
  var previousText=_thinkingStepText(existing);
  var nextText=_thinkingStepText(meta);
  if(!previousText || !nextText || previousText===nextText) return false;
  return true;
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
  stepObj.parallelGroupId=meta.parallelGroupId;
  stepObj.parallelIndex=meta.parallelIndex;
  stepObj.parallelSize=meta.parallelSize;
  stepObj.parallelCompletedCount=meta.parallelCompletedCount;
  stepObj.parallelSuccessCount=meta.parallelSuccessCount;
  stepObj.parallelFailureCount=meta.parallelFailureCount;
  stepObj.parallelTools=meta.parallelTools;
  stepObj.thinkingRevision=(meta.phase==='thinking') ? (Math.max(1, parseInt(meta.thinkingRevision, 10)||1)) : 0;
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
   tool_name:meta.toolName,
   parallel_group_id:meta.parallelGroupId,
   parallel_index:meta.parallelIndex,
   parallel_size:meta.parallelSize,
   parallel_completed_count:meta.parallelCompletedCount,
   parallel_success_count:meta.parallelSuccessCount,
   parallel_failure_count:meta.parallelFailureCount,
   parallel_tools:meta.parallelTools
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
  step.parallelGroupId=meta.parallelGroupId;
  step.parallelIndex=meta.parallelIndex;
  step.parallelSize=meta.parallelSize;
  step.parallelCompletedCount=meta.parallelCompletedCount;
  step.parallelSuccessCount=meta.parallelSuccessCount;
  step.parallelFailureCount=meta.parallelFailureCount;
  step.parallelTools=meta.parallelTools;
  step.thinkingRevision=(meta.phase==='thinking') ? (Math.max(1, parseInt(meta.thinkingRevision, 10)||1)) : 0;
  chat.insertBefore(step.root, pendingState.root);
  return step;
}

function _renderPendingPlan(plan){
  pendingState.plan=null;
  var host=pendingState.planStrip;
  var shouldRenderInChat=typeof window._isTaskPlanBoardEnabled==='function'
   ? window._isTaskPlanBoardEnabled()
   : true;
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
  if(host && shouldRenderInChat){
   host.style.display='';
   var goal=document.createElement('div');
   goal.className='plan-goal';
   goal.textContent=String(plan.goal||'\u5f53\u524d\u4efb\u52a1');
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
  _syncRunPanelHeader();
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
   if(_shouldSplitThinkingRevision(mergeTarget, meta)){
    _setStepStatus(mergeTarget,'done');
    meta.thinkingRevision=Math.max(2, (parseInt(mergeTarget.thinkingRevision,10)||1)+1);
    var splitStep=_createActivityStep(meta);
    steps.push(splitStep);
    _appendRunPanelEntry(splitStep);
   }else{
   _applyStepMeta(mergeTarget, meta);
   var preserveDoneThinking=(
    _streamRuntime.hasStarted()
    && mergeTarget.phase==='thinking'
    && meta.phase==='thinking'
    && mergeTarget.status==='done'
    && !!mergeTarget.stepKey
    && !!meta.stepKey
    && mergeTarget.stepKey===meta.stepKey
   );
   _setStepStatus(mergeTarget, preserveDoneThinking ? 'done' : meta.status);
   }
  }else{
   if(last && last.status==='running' && !_canMergeStep(last, meta)){
    _setStepStatus(last,'done');
   }
   var createdStep=_createActivityStep(meta);
   steps.push(createdStep);
   _appendRunPanelEntry(createdStep);
  }

  _syncRunPanelHeader();
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

 function _tombstoneAbandonedStreamAttempt(){
  var kept=[];
  for(var i=0;i<pendingState.steps.length;i++){
   var step=pendingState.steps[i];
   var phase=String((step&&step.phase)||'').toLowerCase();
   if(phase==='thinking' || phase==='tool' || phase==='waiting'){
    if(step && step.root && step.root.parentNode){
     step.root.parentNode.removeChild(step.root);
    }
    continue;
   }
   kept.push(step);
  }
  pendingState.steps=kept;
  if(kept.length){
   var last=kept[kept.length-1];
   pendingState.activitySummary=_buildActivitySummary({
    displayLabel:last.displayLabel||last.label||t('chat.process'),
    summaryDetail:last.summaryDetail||'',
    fullDetail:last.fullDetail||'',
    phase:last.phase||'info'
   });
  }else{
   pendingState.activitySummary='';
   pendingState.userToggledSteps=false;
   _setRunPanelEmptyState('quiet');
  }
  _ensureRunPanelEntries();
  _syncRunPanelHeader();
  _syncTrackerChrome();
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
   body:JSON.stringify({message:String(text||t('chat.describe.image')),image:imagesBase64?imagesBase64[0]:null,images:imagesBase64,ui_lang:(typeof getLang==='function'?String(getLang()||'zh'):'zh')}),
   signal:_abortController.signal
  });

  if(!resp.ok){
   throw new Error('chat_http_'+String(resp.status||0));
  }

  var reader=resp.body.getReader();
  _setRunPanelEmptyState('open');
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
        // 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾剧懓顪冪€ｎ亝鎹ｉ柣顓炴閵嗘帒顫濋敐鍛闁诲氦顫夊ú锕傚垂鐠鸿櫣鏆︾紒瀣嚦閺冨牆鐒垫い鎺戝绾惧ジ鏌曟繝蹇擃洭缂佲檧鍋撳┑鐘垫暩婵挳宕愮紒妯绘珷闁哄洨濮峰Λ顖炴煙椤栧棗鐬奸崥瀣⒑閸濆嫮鐏遍柛鐘崇墪閻ｅ嘲顭ㄩ崱鈺傂梺姹囧焺閸ㄩ亶鎯勯鐐茶摕闁挎繂顦粻濠氭煕閹邦剙绾ф繛鍫濐煼濮婃椽宕崟顒佹嫳缂備礁顑嗛悧婊呭垝鐠囨祴妲堥柕蹇曞Х椤旀捇姊洪崨濠傚闁轰讲鏅犻弫鍌炴偩瀹€鈧?CoD 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌ｉ幋锝呅撻柛銈呭閺屾盯骞橀懠顒夋М闂佹悶鍔嶇换鍐Φ閸曨垰鍐€妞ゆ劦婢€濮规姊洪柅鐐茶嫰婢у墽绱掗悩铏碍闁伙綁鏀辩缓鐣岀矙鐠囦勘鍔戦弻鏇熷緞濞戙垺顎嶉悶姘剧秮濮婂宕掑▎鎴М闂佸湱鈷堥崑鍡欏垝濞嗘劗鐟归柍褜鍓欓悾鐑藉閿涘嫰妾梺鍛婄☉閿曘倝鍩€椤掆偓濞硷繝寮诲☉鈶┾偓锕傚箣濠靛懐鎸夊┑鐐茬摠缁秶鍒掗幘璇茶摕闁绘柨鎲＄紞鍥煕閹炬鍟悡鍌炴⒒娴ｅ憡鍟炴慨濠傤煼瀵偅绻濆顒冩憰濠电偞鍨剁划搴ㄦ偪閳ь剟姊虹憴鍕姢濠⒀冮叄瀹曟繈顢涢悙绮规嫼闂佸憡绻傜€氼厼锕㈤幍顔剧＜閻庯綆鍋呭畷宀勬煕閳规儳浜炬俊鐐€栫敮鎺楁晝閿曞倸绀嗛柡澶嬵儥閻斿棛鎲稿鍚よ顦版惔鈥崇亰闂佸搫鍟悧婊堝极鐎ｎ喗鐓冪憸婊堝礈閻斿鍤曞┑鐘宠壘閻掓椽鏌涢幇銊︽珔妞ゅ孩鎹囧娲川婵犲嫮绱伴梺绋垮閻╊垱鎱ㄩ埀顒勫箳閾忣偆顩叉繝濠傚娴滄粓鏌熼弶鍨暢闁诡喛鍋愮槐鎺楁偐闂堟稐鎴烽梺閫炲苯澧叉い顐㈩槸鐓ゆ慨妞诲亾闁靛棗鍟换婵嬪磼濠婂嫭顔曢梻渚€娼ц墝闁哄應鏅犲顐ｇ節閸ャ劎鍘遍棅顐㈡处閹告悂骞冮幋锔界厸闁糕剝锕懓鎸庢叏婵犲偆鐓肩€规洘甯掗～婵嬵敄閽樺澹曢梺褰掓？缁€浣哄瑜版帗鐓熼柟杈剧到琚氶梺绋匡工濞硷繝寮婚妸鈺佸嵆婵鍩栭鏍ㄧ箾鐎涙鐭婄紓宥咃躬瀵鈽夐姀鐘电杸闂佺绻愰幗婊堝礄瑜版帗鍊甸悷娆忓缁€鍐煟閹垮嫮绡€鐎殿喖顭烽幃銏ゅ礂閻撳簶鍋撶紒妯圭箚妞ゆ牗绮庣敮娑㈡煕鎼达繝顎楅柍瑙勫灴閹瑩鎳犻鈧。鍦磽娓氬洤鏋熼柣鐔叉櫅椤曪絿鎷犲ù瀣潔闂侀潧绻掓慨鍫ュΩ閿旇桨绨婚梺鍝勫暙閸婂摜鏁懜鐐逛簻妞ゆ劦鍋傞柇顖涙叏婵犲啯銇濈€规洦鍋婂畷鐔碱敆閳ь剟顢撳☉銏♀拺闁告稑锕ョ亸鐢告煕閻樺磭澧甸柣娑卞櫍瀹曟﹢鈥﹂幋鐐茬紦闂備線鈧偛鑻晶瀛橆殽閻愭彃鏆欓柍璇查叄楠炴﹢寮堕幋鐐垫澓濠电姷鏁搁崑娑㈡偋婵犲嫧鍋撶粭娑樻硽婢跺绶為悗锝庡墰閻﹀牓姊哄Ч鍥х伈婵炰匠鍕浄闁挎洖鍊归悡鏇㈡煏閸繄鍑归梺顓у灣閳ь剝顫夊ú鏍偉閸忛棿绻嗘慨婵嗙焾濡茶螖閻橀潧浠﹂柛鏃€鐟ラ～蹇曠磼濡顎撻柣鐔哥懃鐎氼剚绂掗埡鍛拺缂佸鐏濋銏㈢磼椤旇姤灏柣锝囧厴婵℃悂鍩℃繝鍐╂珦闂備浇濮ら敋妞わ缚鍗抽幃姗€宕奸妷锔规嫽?5px 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾剧懓顪冪€ｎ亝鎹ｉ柣顓炴闇夐柨婵嗩槹娴溿倝鏌ら弶鎸庡仴婵﹥妞介、妤呭焵椤掑倻鐭撴い鏇楀亾闁糕斁鍋撳銈嗗笒閿曪箓鎮鹃悽纰樺亾鐟欏嫭绀堥柛妯犲洠鈧箓宕归瑙勬杸闂佹悶鍎崝濠冪閵忥紕绡€缁剧増锚婢ф煡鏌熼鐓庘偓鍨暦濞差亜鐒洪柛鎰ㄦ櫅椤庢捇姊洪崨濠冪闁绘牜鍘ч‖濠囶敋閳ь剟寮婚悢鍝ョ懝闁割煈鍠栭‖鍫ユ煣娴兼瑧绉柡灞剧洴閳ワ箓骞嬪┑鍥╀壕闂備礁鎲￠敃鈺呭磻婵犲偆娼栭柧蹇撴贡閻瑩鏌涢弽鐢电瘈缂佽埖鎸冲铏瑰寲閺囩喐鐝曢梺缁橆殘婵灚绌辨繝鍥ㄥ仺缂佸娉曢ˇ鏉款渻閵堝棛澧柤褰掔畺瀹曨剟濡搁妷顔藉瘜闂侀潧鐗嗗Λ妤佹叏閸岀偞鐓曢柕濠庣厛濞兼劗绱掗弮鍌氭瀾鐎垫澘瀚伴獮鍥敇濞戞瑥顏归梻鍌欑閹诧紕鎹㈤崒婧惧亾濮橆剙妲婚崡閬嶆煕濠靛嫬鍔ょ痪鍓ф櫕閳ь剙绠嶉崕閬嶅箯閹达妇鍙曟い鎺戝€甸崑?闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾剧懓顪冪€ｎ亝鎹ｉ柣顓炴閵嗘帒顫濋敐鍛闁诲氦顫夊ú锕傚垂鐠鸿櫣鏆︾紒瀣嚦閺冨牆鐒垫い鎺戝绾惧ジ鏌曟繝蹇擃洭缂佲檧鍋撳┑鐘垫暩婵挳宕愮紒妯绘珷闁哄洨濮峰Λ顖炴煙椤栧棗鐬奸崥瀣⒑閸濆嫮鐏遍柛鐘崇墪閻ｅ嘲顭ㄩ崱鈺傂梺姹囧焺閸ㄩ亶鎯勯鐐茶摕闁挎繂顦粻濠氭煕閹邦剙绾ф繛鍫濐煼濮婃椽宕崟顒佹嫳缂備礁顑嗛悧婊呭垝鐠囨祴妲堥柕蹇曞Х椤旀捇姊洪崨濠傚闁轰讲鏅犻弫鍌炴偩瀹€鈧?
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
        // 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾剧懓顪冪€ｎ亝鎹ｉ柣顓炴閵嗘帒顫濋敐鍛婵°倗濮烽崑鐐烘偋閻樻眹鈧線寮撮姀鈩冩珕闂佽姤锚椤︻喚绱旈弴鐔虹瘈闁汇垽娼у瓭闂佹寧娲忛崐婵嬪箖瑜斿畷鍗炩枎閹寸姷鍔堕梻浣稿閸嬪棝宕伴幘璺哄К闁逞屽墴濮婂宕掑鍗烆杸婵炴挻纰嶉〃濠傜暦閺囥垹绠涢柣妤€鐗忛崢閬嶆煟鎼搭垳鍒伴柛姘ｅ亾闂備緡鍙庨崹鍫曞蓟閿涘嫪娌柛鎾楀嫬鍨遍梻浣虹《閺呮稓鈧碍婢橀悾宄邦潨閳ь剟銆侀弮鈧幏鍛嫚閳╁啰绉鹃梻鍌氬€搁崐鐑芥嚄閸撲礁鍨濇い鏍仜缁€澶愭煛閸ャ儱鐏柡鍛箖閵囧嫯绠涢幘璺侯暫闂佽棄鍟伴崰鏍蓟閵娿儮鏀介柛鈾€鏅滅瑧缂傚倷鑳舵慨鐢电矙閹烘桅闁告洦鍨扮粻宕団偓骞垮劚閻楁粓宕ぐ鎺撯拺闁告繂瀚烽崕鎰版煟閻旀潙鍔﹂柛鈺冨仱楠炲鏁冮埀顒勬倿濞差亝鐓曢柟鎵虫櫅婵¤法绱掓担绋挎Щ妞ゎ亜鍟存俊鑸垫償閳ュ磭顔掗梻浣侯焾缁绘垿鏁冮姀銈嗗仒妞ゆ洍鍋撶€规洘锕㈡俊鍛婃償閵忊槅妫冮悗瑙勬磸閸旀垿銆佸▎鎾粹拻閻庨潧鎲￠弳浼存⒒閸屾艾鈧兘鎳楅崜浣稿灊妞ゆ牜鍋戦埀顒€鍟村畷銊р偓娑櫭禍杈ㄧ節閻㈤潧孝婵炲眰鍊楃划濠氼敍閻愮补鎷哄銈嗗坊閸嬫挾绱掓径灞炬毈闁?闂?濠电姷鏁告慨鐑藉极閸涘﹥鍙忛柣鎴ｆ閺嬩線鏌涘☉姗堟敾闁告瑥绻愰湁闁稿繐鍚嬬紞鎴︽煕閵娿儱鈧潡寮婚敐澶婄鐎规洖娲ら崫娲⒑閸濆嫷鍎愰柣妤侇殘閹广垹鈽夐姀鐘殿吅闂佺粯鍔曢顓炩枔閵堝鈷戞繛鑼额嚙楠炴鏌熼幖浣虹暫闁糕斁鍋撳銈嗗笒閸犳艾顭囬幇顓犵闁告瑥顦辨晶顏堟偂閵堝鐓忓┑鐐戝啯鍣介柣鎺戝悑缁绘繈鎮介棃娴躲垺绻涚拠褏鐣甸柟顕嗙節瀵挳鎮㈤搹璇″晭闂備胶鎳撻顓㈠磿閹扮増鍊垮ù鐘差儐閻撴瑩鏌ｉ敐鍛板闁宠鐗撻弻锛勪沪閸撗佲偓鎺楁煃瑜滈崜銊х礊閸℃稑纾婚柛鏇ㄥ墯閸欏繒鈧箍鍎遍ˇ浼存偂濞戙垺鍊堕柣鎰邦杺閸ゆ瑩鏌嶈閸撴氨鎹㈤崒鐐村仼闁绘垹鐡旈弫鍐煥閺囨浜鹃柛鐑嗗灠椤啴濡堕崱姗嗘⒖婵犳鍠撻崐婵嬪箚娴ｅ壊鐓ラ柛顐ゅ暱閹风粯绻涙潏鍓у閻犫偓閿曞倹鍊块柣鎰靛厵娴滄粓鏌熺€涙绠栨い銉ｅ灪椤ㄣ儵鎮欓弶鎴濐潔缂備胶绮换鍌烇綖濠靛鏁嗛柛灞诲€曢弫鎼佹⒒閸屾瑧顦﹂柟璇х磿缁瑩骞掗幋顓犲姺濠电偛妫欓崝鏇㈩敋闁秵鐓熸俊顖濆亹鐢盯鏌ｉ幘瀛樼闁哄矉绻濆畷鍫曞Ψ閵夈儺鐎辩紓鍌欓檷閸斿矂鈥﹂悜钘夌畺婵°倕鎳庨崹鍌涖亜閹扳晛鐏紒浣哄厴濮婅櫣鈧湱濯鎰版煕閵娿儲鍋ユ鐐插暙閳诲酣骞樺畷鍥崜闂備胶鎳撻顓熸叏閸愬樊娴栭柟鍓х帛閳锋帒霉閿濆洨鎽傛繛鍏煎姍閺岋綁鍩勯崘鈺冾槹濡炪們鍨烘穱娲囪ぐ鎺撶厓闁靛闄勯ˉ鍫⑩偓瑙勬礃閿曘垽宕洪敓鐘茬闁绘劦鍓涢妶顐︽⒒娴ｇ瓔鍤欓柛鎴犳櫕缁辩偤宕卞Ο纰辨锤濡炪倕绻愮€氣偓婵炴垯鍨洪悡銉╂倵閿濆倹娅囩紒鐘冲哺濮婃椽妫冨☉姘暫缂備胶绮敮鈥崇暦濮橆厼顕遍悗娑欘焽閸橀亶姊虹紒妯荤；缂佲偓娓氣偓閹﹢鏁傞柨顖氫壕?
        try{ setTimeout(function(){_setCodDot('flash');},600); }catch(e){}
        _streamRuntime.suppressTypingCursor();
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
           var _preserveThinkingStep=(_runningStep.phase==='thinking');
           if(_preserveThinkingStep){
            if(parsed.step_key) _runningStep.stepKey=parsed.step_key;
            if(_waitDetail){
             _syncRunPanelEntry(_runningStep);
             _syncRunPanelHeader();
             _stickChatToBottom();
            }
           }else if(_waitLabel && _runningStep.label!==_waitLabel && (!_waitStepKey || _runningStep.stepKey!==_waitStepKey)){
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
           // Keep raw thinking text visible when the runtime is only reporting an idle/waiting heartbeat.
           if(_runningStep.phase==='thinking'){
            _syncRunPanelEntry(_runningStep);
            _syncRunPanelHeader();
           }else{
            _applyStepDetail(_runningStep, _waitDetail, _waitDetail);
           }
            _stickChatToBottom();
           }
          }else if(_waitLabel || _waitDetail){
           if(_isLowSignalStreamWaitingStep(parsed)){
            _syncRunPanelHeader();
           }else{
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
         }
       }else if(currentEvent==='thinking'){
        var _thinkingText=String(parsed.content||'').replace(/<\/?think>/ig,' ').trim();
        if(_thinkingText){
          addStep({label:'thinking',detail:_thinkingText,status:(parsed.status||'done'),full_detail:_thinkingText});
         if(_showRawThinkingPanel) _thinkingContent=_thinkingText;
        }
       }else if(currentEvent==='ask_user'){
        // agent 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾剧懓顪冪€ｎ亝鎹ｉ柣顓炴閵嗘帒顫濋敐鍛婵°倗濮烽崑鐐烘偋閻樻眹鈧線寮撮姀鐘靛幀闂佸吋浜介崕鎶藉煡婢舵劖鎳氶柡宥庡幗閻撴洘绻涢幋婵嗚埞妤犵偞锕㈤弻銊モ槈濞嗘垶鍣板┑顔硷攻濡炶棄鐣烽妸锔剧瘈闁告洏鍔嶉～宥夋⒒娴ｇ懓顕滄繛娴嬫櫇缁骞樼拠鍙傘儵鏌涘☉妯兼憼闁稿﹤顭烽弻銈夊箒閹烘垵濮㈤梺鍛婎焾濡嫰鍩為幋锕€鐓￠柛鈩冾殘娴犫晠姊洪崨濠呭妞ゆ垵顦锝夊箮閽樺鍘告繛鎾磋壘濞诧妇鈧潧鐭傚娲嚒閵堝懏鐎惧┑鐘灪閿曘垹顕ｉ搹顐ｇ秶闁靛绲肩花璇差渻閵堝棙灏ㄩ柛鎾寸箘濞戠敻宕奸弴鐔哄幍闂佽崵鍠愬姗€顢旈銏＄厵妞ゆ梻鏅惌濠囨懚閿濆洨纾藉ù锝咁潠椤忓牜鏁傚ù鐓庣摠閳锋帡鏌涚仦鍓ф噮妞わ讣绠撻弻鐔哄枈閸楃偘绨婚柧鑽ゅ仦娣囧﹪濡堕崨顓熸閻庤娲栧鍫曞箞閵娿儺娓婚悹鍥紦婢规洟鏌ｆ惔銏╁晱闁哥姵鐗犻垾锕傛倻閽樺鐣洪梺闈涚箞閸ㄦ椽宕戝鈧弻宥夊Ψ閵夈儱绗繝銏ｎ潐濞茬喎顫忛崫鍕懷囧炊瑜忔禒鎯ь渻閵堝棙鈷愰柣妤冨█楠炲啴鎮欏ǎ顒€浜濋梺鍛婂姀閺呮繈宕㈤崡鐐╂斀闁宠棄妫楅悘锝囩磼椤曞懎鐏ｅù婊勬倐閺佸啴宕掑☉姘箰闂佽绻掗崑鐔煎疾椤愩垺姣勫┑锛勫亼娴煎洭宕掑鍛床闂備礁鎼張顒勬儎椤栫偟宓佹俊顖氱毞閸嬫捇妫冨☉娆忔殘闂侀潻绲奸崡鎶藉蓟閿曗偓铻ｉ柤濮愬€楅悿鍕⒑閸濆嫮鐏遍柛鐘查叄閸┿垽骞樼拠鎻掔€銈嗘⒒閺咁偅绂嶉幇鐗堚拻?闂?婵犵數濮烽弫鍛婃叏閻戣棄鏋侀柛娑橈攻閸欏繘鏌ｉ幋锝嗩棄闁哄绶氶弻鐔兼⒒鐎靛壊妲紒鐐劤椤兘寮婚敐澶婄疀妞ゆ帊鐒﹂崕鎾剁磽娴ｅ搫校濠㈢懓妫涘Σ鎰板箳閺傚搫浜鹃柨婵嗛娴滀粙鏌涙惔娑樺姦闁哄本鐩俊鍫曞幢濡⒈妲归梻浣告惈閺堫剟鎯勯鐐偓渚€寮撮姀鈩冩珳闂佺硶鍓濋悷顖毼ｆ导瀛樷拻濞达絼璀﹂悞鐐亜閹存繃鍤囩€规洘鍔欏畷绋课旈埀顒傜不閺嶃劋绻嗛柕鍫濇噺閸ｆ椽鏌￠崨顔惧弨妤犵偞鐗滈崚鎺楁偡閺夊簱鎷ら梻浣筋嚙缁绘劗绮旈悷閭︽綎闁惧繐婀辩壕鍏间繆椤栨繃顏犳い鎴濆椤啴濡堕崱妯垮亖闂佹悶鍎荤徊娲磻閹剧粯鏅濋柛灞惧哺閺佹粌鈹戞幊閸婃挾绮堟担绯曟灁婵犻潧顑嗛埛鎺楁煕鐏炵偓鐨戝褎绋撶槐鎺斺偓锝庡亜閻忔挳鏌ㄥ┑鍫濅槐鐎规洖鐖奸、妤佹媴閸欏顏归梻鍌氬€风欢锟犲磻閸℃稑纾绘繛鎴欏灪閸ゆ劖銇勯弽銊р姇婵炲懐濮甸妵鍕棘閸喒鎸冪紒鎯у⒔閸樠団€︾捄銊﹀磯闁绘垶蓱閹烽亶姊洪幖鐐测偓鎰板磻閹剧粯鈷掑ù锝夘棑娑撹尙绱掗幓鎺撳仴鐎规洘顨呴～婊堝焵椤掆偓椤曪綁顢曢敃鈧粻鑽ょ磽娴ｅ顏呯瑜版帗鈷戦柟顖嗗嫮顩伴梺绋款儏閹虫﹢骞冮悽鍓叉晝闁挎棁袙閹风粯绻涙潏鍓у埌闁硅绻濆畷顖炴倷鐎靛摜顔曢柣鐘叉厂閸涱垱娈奸柣搴ゎ潐濞叉﹢宕归崸妤冨祦闁圭儤鍤﹂弮鍫濈劦妞ゆ巻鍋撻弫?
        _renderAskUser(parsed, pendingState);
      }else if(currentEvent==='stream'){
       if(parsed&&parsed.format==='markdown_incremental'){
        _streamRuntime.applyMarkdownIncrementalStream(parsed);
       }else{
        _streamRuntime.appendStreamToken(parsed.token||'');
       }
       }else if(currentEvent==='stream_reset'){
        _streamRuntime.resetActiveStreamRender();
        _tombstoneAbandonedStreamAttempt();
      }else if(currentEvent==='repair'){
       repairData=parsed;
      }else if(currentEvent==='awareness'){
       AwarenessManager.handleEvent(parsed);
       }else if(currentEvent==='model_changed'){
        var newModel=parsed.model||'';
        var newName=parsed.model_name||newModel;
        _queueModelSwitchNote({
         model:newModel,
         model_name:newName
        });
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

 var finalText=_chooseFinalStreamText(replyText, _streamRuntime.getText())||'';
if(_streamRuntime.hasStarted() && finalText){
  _streamRuntime.finalizeStream(finalText);
  if(!(pendingState.steps&&pendingState.steps.length)) _setRunPanelEmptyState('quiet');
 }else if(finalText){
   _streamRuntime.renderReplyViaStream(finalText);
   if(!(pendingState.steps&&pendingState.steps.length)) _setRunPanelEmptyState('quiet');
 }else{
   _setRunPanelEmptyState('quiet');
   finalizePendingAssistantMessage(pendingState, t('chat.error.retry'));
  }
  _dispatchChatRequestState('completed', {
   source:'send',
   has_reply:!!finalText,
   reply_text:finalText,
   voice_mode:!!window._voiceMode
  });
  _flushPendingModelSwitchNote();
  if(repairData && repairData.show){ showRepairBar(repairData); }
  _completeTaskProgress();
  AwarenessManager.startPolling();
 }catch(e){
  if(e.name==='AbortError'){
   _setRunPanelEmptyState('stopped');
   // 闂傚倸鍊搁崐鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌ｉ幋锝呅撻柛濠傛健閺屻劑寮村Δ鈧禍鎯ь渻閵堝簼绨婚柛鐔告綑閻ｇ柉銇愰幒婵囨櫔闂佸憡渚楅崹鐗堟叏濞差亝鈷掑ù锝勮濞兼帡鏌涢弴鐐典粵闁伙絽澧庣槐鎾存媴閹绘帊澹曞┑鐘灱濞夋稒寰勯崶顒€纾婚柟鎹愬吹瀹撲線鏌涢…鎴濇灈濠殿喖楠搁—鍐Χ韫囨挾妲ｉ梺鎼炲姀濞夋盯顢氶敐鍡楊嚤闁哄鍤﹂妸鈺傜叆闁哄倸鐏濋埛鏃€銇勯弮鈧ú鐔奉潖濞差亝鍋￠柟娈垮枟閹插ジ姊洪懡銈呮瀭闁稿海鏁婚獮鍐潨閳ь剟銆侀弮鍫濋唶闁绘柨鎼獮鍫濃攽閻樺灚鏆╁┑顔碱嚟閳ь剚鍑归崜鐔风暦閵忊懇鍋撳☉娅虫垿宕ｈ箛鎾斀闁绘ɑ褰冮弳鐐烘煏閸ャ劎绠栭柕鍥у婵偓闁斥晛鍟伴ˇ浼存⒑鏉炴壆鍔嶉柛鏃€鐟ラ悾鐑藉醇閺囩倣銊╂煏韫囨洖小濠㈣娲熷娲捶椤撶偛濡哄銈冨妼濡繈骞冮敓鐘插嵆闁靛骏绱曢崢浠嬫⒑閸濆嫬鈧悂鎮樺┑鍡忔灁闁冲搫鎳忛ˉ濠冦亜閹烘埈妲稿褎鎸抽弻鈥崇暆鐎ｎ剛锛熸繛瀵稿缁犳挸鐣峰鍡╂Ч闂侀€炲苯澧悽顖ょ節瀵顓奸崼顐ｎ€囬梻浣告啞閹稿爼宕濇惔锝嗩潟闁绘劕鎼獮銏＄箾閹寸儐鐒介柨娑欑洴濮婅櫣鍖栭弴鐐测拤缂備礁顑嗙敮鈥崇暦閺囩倣鏃堝川椤斿皷鍋撻悽鍛婄叆婵犻潧妫濋妤€霉濠婂嫮澧棁澶嬬節婵犲倸顏柣顓熷浮閺屸€崇暆閳ь剟宕伴弽顓炵畺婵犲﹤鍚橀悢鐑樺珰闁告瑥顦伴鍌氣攽閻樺灚鏆╅柛瀣☉椤曪綁宕奸弴鐐殿唶闂佽鍎煎Λ鍕嫅閻斿吋鐓冮柍杞扮閺嗙偛鈹戦娑欏唉闁哄本绋戦埞鎴﹀礋椤愩垹顥濋梻渚€娼ч悧鍡涘箖閼愁垬浜归柟鐑樻尭娴滃ジ姊洪崨濠佺繁闁搞劍濞婂鎶藉Χ婢跺鎷洪柣鐘叉礌閳ь剝娅曢悘宥夋⒑閼姐倕鏆遍柡鍛█婵″瓨绗熼埀顒€顕ｆ禒瀣垫晣闁绘棃鏀遍悿鍛存⒒娓氣偓濞佳囨晬韫囨稑纾兼繝濠傛閸橆厾绱撻崒姘偓鎼佸磹閹间礁纾归柟闂寸绾惧綊鏌熼梻瀵割槮缁惧墽鎳撻—鍐偓锝庝簻椤掋垹鈹戦姘ュ仮闁哄矉绱曟禒锔炬嫚閹绘帒顫撶紓浣哄亾閸庢娊鈥﹂悜钘夎摕闁绘梻鍘х粈鍫㈡喐韫囨洘鏆滄繛鎴欏灪閻撶喖鏌熼幆褏鎽犵紒鈧崘顏嗙＜缂備焦顭囩粻鐐翠繆椤愩垹鏆欓柍钘夘槸閳诲骸螣濞茬粯锛囨繝纰夌磿閸嬫垿宕愰弴鐘冲床闁糕剝绋戦悿楣冩煟濡鍤欓柦鍐枑缁绘盯骞嬪▎蹇曚患闁搞儲鎸冲铏瑰寲閺囩偛鈷夊銈冨妼濡盯骞忛悩缁樺€烽柣鎴炃氶幏娲⒑閸涘﹦绠撻悗姘煎櫍閹偟鎹勯妸褏锛滅紓鍌欑劍椤洨绮婚幘缁樼厽闁挎繂娲ら崢鎾煙椤旂懓澧查柟顖涙煥铻ｇ紓浣股戝鎴︽⒒閸屾瑧顦︾紓宥咃躬瀹曟垶绻濋崶褍鍋嶅┑鐘诧工閻楀棙鍎梻渚€娼чˇ顓㈠垂濞差亜妫橀柍褜鍓熷缁樻媴閾忕懓绗￠梺鍛婃⒐椤洦绂嶇粙搴撴瀻闁归偊鍘介悵宄扳攽閻愭潙鐏熼柛銊︽そ閹繝寮撮姀锛勫帾婵犵數鍋涢悘婵嬪礉濠婂牊鐓曢悗锝冨妼閸斻倝鏌嶈閸撴岸顢欓弽顓炵獥闁哄稁鍘搁埀顒婄畱閻ｏ繝骞嶉鑺ヮ啎濠电娀娼ч崐濠氣€﹂崼婵囨殰闂傚倷绶氬褔藝椤栨粏濮抽柛顐ｆ礀閻ら箖鏌ｅΟ娆惧殭闁藉啰鍠栭弻锟犲炊閳轰焦鐎荤紓浣稿閸嬨倝寮诲☉銏╂晝闁挎繂娲ㄩ悾鍨節濞堝灝鏋旈柛銊ㄦ椤繐煤椤忓懐鍔甸梺缁樺姌鐏忣亞鈧碍婢橀…鑳檨闁哥姵顨婃俊鐢稿礋椤栵絾鏅ｉ梺缁樕戣ぐ鍐嵁鐎ｎ喗鍊垫繛鍫濈仢閺嬶附銇勯弴鍡楁搐閻撯€愁熆閼搁潧濮囨い顐㈡嚇閺岋絽螣閼姐倕鈪甸梺鍛婃煥闁帮綁鐛径宀€鐭欐繛鍡樺劤閹垿姊虹化鏇炲⒉闁荤噥鍨伴湁闁告洦鍋€閺€浠嬫煟濡鍤嬬€规悶鍎甸幃妤€顫濋妷銉ヮ瀴缂備礁鍊哥粔鎾€﹂妸鈺侀唶闁绘柨鎼鎶芥⒒娴ｅ憡鎯堥柛鐕佸亰瀹曟劙鎮烽幍铏€洪梺鍝勬储閸ㄦ椽鎮￠弴鐔虹闁糕剝顨夌€氭澘霉濠婂嫬鍔ら柍瑙勫灦楠炲﹪鏌涙繝鍐炬畷闁逛究鍔戦幃婊堟寠婢跺矉绱辨繝鐢靛仦閸垶宕洪崟顖氭瀬闁告洦鍋掗悢鍡涙偣鏉炴媽顒熼柣鎿冨墴閺屾盯濡堕崱妯碱槬闂傚洤顦甸弻锝呂熼悜妯锋灆闂佺楠哥换姗€鐛崱娑欏亜闁稿繐鐨烽幏娲⒒閸屾氨澧涢柛鎰吹濡叉劙鏁撻悩宕囧幈闂佽婢樻晶搴ㄥ礆閺夋５鐟邦煥閸垻鏆梺鍝勭灱閸犳牠骞冨鍏剧喖鎮滈埡鍌氼伜缂傚倷鑳堕崑鎾崇暦濡綍娑㈠礋椤栨稓鐣抽梻鍌欑劍鐎笛呮崲閸屾娑樜旈崘銊х瓘闁荤姴娲╅ˉ?
   var abortText=_chooseFinalStreamText(replyText, _streamRuntime.getText())||_streamRuntime.getText()||'';
   if(_streamRuntime.hasStarted()&&abortText){
    _streamRuntime.finalizeStream(abortText);
   }else if(abortText){
    _streamRuntime.renderReplyViaStream(abortText);
   }else{
    finalizePendingAssistantMessage(pendingState, t('chat.stopped')||'\u5df2\u505c\u6b62');
   }
   _dispatchChatRequestState('aborted', {
    source:'send',
    has_reply:!!abortText,
    reply_text:abortText,
    voice_mode:!!window._voiceMode
   });
  }else{
   _setRunPanelEmptyState('error');
   finalizePendingAssistantMessage(pendingState, t('chat.error.noconnect'));
   _dispatchChatRequestState('error', {
    source:'send',
    error_name:String(e&&e.name||'Error'),
    error_message:String(e&&e.message||''),
    voice_mode:!!window._voiceMode
   });
  }
  _pendingModelSwitchNote=null;
 }
 _stopRunElapsedClock();
 _syncRunPanelHeader();
 _abortController=null;
 _exitStopMode();
 _stickChatToBottom();
}


