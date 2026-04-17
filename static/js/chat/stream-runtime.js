// Stream bubble lifecycle helpers shared by chat/stream.js.

function _createStreamRuntime(bindings){
 var pendingState=bindings.pendingState;
 var chat=bindings.chat;
 var state={
  streamBubble:null,
  streamText:'',
  streamStarted:false,
  suppressTypingCursor:false,
  streamAutoFollow:true,
  streamScrollFollowBound:false,
  scrollRAF:0,
  renderTimer:0,
  streamTokenCount:0,
  streamLineEl:null,
  streamBlocksEl:null,
  streamProtocol:'',
  streamLiveText:'',
  streamTailTimer:0
 };

 function _syncStreamAutoFollow(){
  var nearBottom=(typeof window._isChatNearBottom==='function')
   ? !!window._isChatNearBottom(180)
   : _streamIsNearBottom(chat, 220);
  state.streamAutoFollow=nearBottom;
  if(typeof window._setChatAutoStick==='function'){
   window._setChatAutoStick(nearBottom);
  }
 }

 function _attachStreamScrollFollow(){
  if(!chat || state.streamScrollFollowBound) return;
  chat.addEventListener('scroll', _syncStreamAutoFollow, {passive:true});
  state.streamScrollFollowBound=true;
  _syncStreamAutoFollow();
 }

 function _detachStreamScrollFollow(){
  if(chat && state.streamScrollFollowBound){
   chat.removeEventListener('scroll', _syncStreamAutoFollow);
  }
  state.streamScrollFollowBound=false;
 }

 function _followStreamToBottom(options){
  if(!state.streamAutoFollow) return false;
  if(typeof window._setChatAutoStick==='function'){
   window._setChatAutoStick(true);
  }
  return _stickChatToBottom(options||{threshold:220});
 }

 function _scheduleProgressiveRender(delay){
  if(state.renderTimer || !state.streamBubble) return;
  state.renderTimer=setTimeout(_progressiveRender, Math.max(0, Number(delay)||0));
 }

 function _renderStructuredStreamTail(text, html){
  state.streamLiveText=String(text||'');
  if(!state.streamLineEl) return;
  var safeHtml=String(html||'').trim();
  if(safeHtml){
   _streamEnsureBubbleVisible(state.streamBubble);
   state.streamLineEl.style.display='block';
   state.streamLineEl.innerHTML=safeHtml;
   _followStreamToBottom({threshold:220});
  }else if(state.streamLiveText){
   _streamEnsureBubbleVisible(state.streamBubble);
   state.streamLineEl.style.display='block';
   state.streamLineEl.innerHTML='';
   state.streamLineEl.textContent=typeof stripMarkdownForStreamingText==='function'
    ? stripMarkdownForStreamingText(state.streamLiveText)
    : state.streamLiveText;
   _followStreamToBottom({threshold:220});
  }else{
   state.streamLineEl.innerHTML='';
   state.streamLineEl.textContent='';
   state.streamLineEl.style.display='none';
  }
 }

 function _clearStructuredTailTimer(){
  if(state.streamTailTimer){
   clearTimeout(state.streamTailTimer);
   state.streamTailTimer=0;
  }
 }

 function _initStreamBubble(){
  bindings.placePendingRootAtEnd();
  pendingState.root.style.display='';
  for(var i=0;i<pendingState.steps.length;i++){
   if(pendingState.steps[i].status==='running') bindings.setStepStatus(pendingState.steps[i],'done');
  }
  if(pendingState.labelTimer){
   clearInterval(pendingState.labelTimer);
   pendingState.labelTimer=null;
  }
  bindings.collapseSteps();
  if(pendingState.steps.length) bindings.ensureTraceDetached();
  pendingState.status.style.display='none';
  pendingState.root.className='msg assistant';
  var contentArea=pendingState.contentArea;
  contentArea.style.display='';
  contentArea.innerHTML='';
  var bubble=document.createElement('div');
  bubble.className='bubble assistant-reply-plain';
  bubble.style.display='none';
  var blocksEl=document.createElement('div');
  blocksEl.className='stream-blocks';
  bubble.appendChild(blocksEl);
  var lineEl=document.createElement('div');
  lineEl.className='stream-live-line';
  lineEl.style.display='none';
  bubble.appendChild(lineEl);
  var meta=document.createElement('div');
  meta.className='msg-meta';
  meta.style.display='none';
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
  state.streamBubble=bubble;
  state.streamBlocksEl=blocksEl;
  state.streamLineEl=lineEl;
  state.streamProtocol='';
  state.streamText='';
  state.streamLiveText='';
  state.streamStarted=true;
  bindings.pruneLowSignalStreamWaitingSteps();
  state.suppressTypingCursor=false;
  state.streamTokenCount=0;
  _attachStreamScrollFollow();
  _followStreamToBottom({threshold:220});
  bindings.syncRunPanelHeader();
 }

 function _renderStreamSnapshot(text){
  var snapshot=String(text||'').replace(/\r/g,'');
  state.streamLiveText=snapshot;
  if(state.streamLineEl){
   if(state.streamLiveText){
    _streamEnsureBubbleVisible(state.streamBubble);
    state.streamLineEl.style.display='block';
    state.streamLineEl.textContent=typeof stripMarkdownForStreamingText==='function'
     ? stripMarkdownForStreamingText(state.streamLiveText)
     : state.streamLiveText;
    _followStreamToBottom({threshold:220});
   }else{
    state.streamLineEl.textContent='';
    state.streamLineEl.style.display='none';
   }
  }
 }

 function _progressiveRender(){
  state.renderTimer=0;
  if(!state.streamBubble) return;
  _renderStreamSnapshot(state.streamText);
  state.streamTokenCount++;
  if(state.streamAutoFollow && !state.scrollRAF){
   state.scrollRAF=requestAnimationFrame(function(){
    _followStreamToBottom({threshold:220});
    state.scrollRAF=0;
   });
  }
 }

 function _applyMarkdownIncrementalStream(payload){
  if(!state.streamStarted) _initStreamBubble();
  if(state.streamBubble && typeof applyAssistantBubbleRenderMode==='function'){
   applyAssistantBubbleRenderMode(
    state.streamBubble,
    String((payload&&payload.full_text)||''),
    String((payload&&payload.tail_html)||''),
    'markdown'
   );
  }
  state.streamProtocol='markdown_incremental';
  state.streamText=String((payload&&payload.full_text)||'');
  _appendIncrementalMarkdownBlocks(state.streamBlocksEl, payload&&payload.append, _streamEnsureBubbleVisible.bind(null, state.streamBubble));
  _renderStructuredStreamTail(
   String((payload&&payload.tail)||''),
   String((payload&&payload.tail_html)||'')
  );
 }

 function _appendStreamToken(token){
  if(!state.streamStarted) _initStreamBubble();
  if(state.streamBubble && typeof applyAssistantBubbleRenderMode==='function'){
   applyAssistantBubbleRenderMode(state.streamBubble, state.streamText+String(token||''), '', 'plain');
  }
  if(!state.streamProtocol) state.streamProtocol='text';
  state.streamText+=String(token||'');
  _scheduleProgressiveRender(36);
 }

 function _resetActiveStreamRender(){
  _detachStreamScrollFollow();
  if(state.renderTimer){
   clearTimeout(state.renderTimer);
   state.renderTimer=0;
  }
  _clearStructuredTailTimer();
  if(state.scrollRAF){
   cancelAnimationFrame(state.scrollRAF);
   state.scrollRAF=0;
  }
  _streamRemoveTrailingParts(_streamParts, 0);
  state.streamBubble=null;
  state.streamBlocksEl=null;
  state.streamLineEl=null;
  state.streamText='';
  state.streamProtocol='';
  state.streamLiveText='';
  state.streamTokenCount=0;
  state.streamStarted=false;
  state.suppressTypingCursor=false;
  bindings.setThinkingContent('');
  if(pendingState.contentArea){
   pendingState.contentArea.innerHTML='';
   pendingState.contentArea.style.display='none';
  }
 }

 function _finalizeStream(fullText){
  if(!state.streamBubble) return;
  _detachStreamScrollFollow();
  if(state.renderTimer){
   clearTimeout(state.renderTimer);
   state.renderTimer=0;
  }
  _clearStructuredTailTimer();
  var finalText=String(fullText||'');
  var finalRenderText=String(finalText||state.streamText||'');
  var finalMode=(typeof applyAssistantBubbleRenderMode==='function')
   ? applyAssistantBubbleRenderMode(
    state.streamBubble,
    finalRenderText,
    '',
    state.streamProtocol==='markdown_incremental' ? 'markdown' : ''
   )
   : (state.streamProtocol==='markdown_incremental' ? 'markdown' : 'plain');
  _streamEnsureBubbleVisible(state.streamBubble);
  if(state.streamProtocol!=='markdown_incremental' && state.streamLineEl){
   state.streamLineEl.innerHTML=(typeof renderAssistantReplyHtml==='function')
    ? renderAssistantReplyHtml(finalRenderText, '', finalMode)
    : renderAssistantBubbleHtml(finalRenderText, '');
   state.streamLineEl.style.display=finalRenderText ? 'block' : 'none';
  }
  state.streamLiveText='';
  var replyImage=bindings.getReplyImage();
  if(replyImage){
   var img=document.createElement('img');
   img.className='bubble-image';
   img.src=replyImage;
   img.alt='reply image';
   img.setAttribute('data-chat-preview-src', replyImage);
   img.style.maxWidth='100%';
   img.style.maxHeight='400px';
   img.style.borderRadius='8px';
   img.style.marginTop='8px';
   if(typeof bindChatImagePreview==='function'){
    bindChatImagePreview(img,replyImage,'reply image');
   }else{
    img.style.cursor='pointer';
    img.onclick=function(){window.open(replyImage,'_blank');};
   }
   state.streamBubble.appendChild(img);
  }
  var meta=state.streamBubble.parentNode.querySelector('.msg-meta');
  if(meta && !meta.querySelector('.msg-copy')){
   var cpBtn=document.createElement('button');
   cpBtn.className='msg-copy';
   cpBtn.textContent=t('chat.copy');
   cpBtn.onclick=function(){
    navigator.clipboard.writeText(fullText).then(function(){
     cpBtn.textContent=t('chat.copied');
     setTimeout(function(){cpBtn.textContent=t('chat.copy');},1200);
    });
   };
   meta.appendChild(cpBtn);
  }
  var thinkingContent=bindings.getThinkingContent();
  if(bindings.getShowRawThinkingPanel() && thinkingContent && state.streamBubble.parentNode){
   var existPanel=state.streamBubble.parentNode.querySelector('.thinking-panel');
   if(!existPanel){
    var thinkPanel=document.createElement('details');
    thinkPanel.className='thinking-panel';
    var thinkSummary=document.createElement('summary');
    thinkSummary.textContent='模型思考过程';
    thinkSummary.style.cssText='cursor:pointer;font-size:12px;color:#888;padding:6px 0;user-select:none;';
    var thinkBody=document.createElement('div');
    thinkBody.style.cssText='font-size:12px;color:#999;padding:8px 12px;background:rgba(128,128,128,0.08);border-radius:8px;margin:4px 0 8px;white-space:pre-wrap;line-height:1.5;max-height:300px;overflow-y:auto;';
    thinkBody.textContent=thinkingContent;
    thinkPanel.appendChild(thinkSummary);
    thinkPanel.appendChild(thinkBody);
    state.streamBubble.parentNode.insertBefore(thinkPanel,state.streamBubble);
   }
  }
  bindings.collapseSteps();
  bindings.syncRunPanelHeader();
  _followStreamToBottom({threshold:220});
  if(!pendingState.persisted){
   bindings.snapshotChatHistory();
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
      tool_name:s.toolName||'',
      parallel_group_id:s.parallelGroupId||'',
      parallel_index:s.parallelIndex||0,
      parallel_size:s.parallelSize||0,
      parallel_completed_count:s.parallelCompletedCount||0,
      parallel_success_count:s.parallelSuccessCount||0,
      parallel_failure_count:s.parallelFailureCount||0,
      parallel_tools:Array.isArray(s.parallelTools)?s.parallelTools:[]
     };
    });
    var keys=Object.keys(stepsMap);
    if(keys.length>200){
     keys.sort();
     keys.slice(0, keys.length-200).forEach(function(k){delete stepsMap[k];});
    }
    localStorage.setItem('nova_steps_map',JSON.stringify(stepsMap));
    pendingState.root.setAttribute('data-steps-key',tsKey);
   }
   pendingState.persisted=true;
  }
 }

 function _renderReplyViaStream(text){
  var finalText=String(text||state.streamText||'').trim();
  if(!finalText) finalText=t('chat.error.retry');
  if(!state.streamStarted){
   _initStreamBubble();
  }
  state.streamText=finalText;
  _finalizeStream(finalText);
 }

 return {
  applyMarkdownIncrementalStream:_applyMarkdownIncrementalStream,
  appendStreamToken:_appendStreamToken,
  finalizeStream:_finalizeStream,
  getBubble:function(){ return state.streamBubble; },
  getText:function(){ return state.streamText; },
  hasStarted:function(){ return state.streamStarted; },
  renderReplyViaStream:_renderReplyViaStream,
  resetActiveStreamRender:_resetActiveStreamRender,
  suppressTypingCursor:function(){
   state.suppressTypingCursor=true;
   _streamHideTypingCursor(state.streamBubble);
  }
 };
}
