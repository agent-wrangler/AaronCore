// Task plan strip, ask-user cards, and task progress UI
// Source: chat.js lines 1970-2339

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
