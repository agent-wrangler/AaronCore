// Send flow, SSE handling, stream rendering, and thinking steps
// Source: chat.js lines 712-1968

var _runPanelStoreKey='nova_run_panel_open';
var _runPanelUserOpen=true;
var _runPanelTabVisible=true;

function _normalizeRunPanelDom(){
 var host=document.getElementById('runPanel');
 if(!host) return;
 host.innerHTML=''
  +'<div class="run-panel-header">'
  +'<div class="run-panel-header-main">'
  +'<div class="run-panel-kicker-row">'
  +'<div class="run-panel-kicker" id="runPanelKicker">Current Run</div>'
  +'<div class="run-panel-status-pill state-idle" id="runPanelStatus">Idle ? 0 / 0</div>'
  +'</div>'
  +'<div class="run-panel-task" id="runPanelTask">Elapsed ? 00:00</div>'
  +'<div class="run-panel-meta" id="runPanelMeta">0 files ? 0 tools ? 0 errors</div>'
  +'</div>'
  +'<button class="run-panel-close" id="runPanelCloseBtn" type="button" onclick="toggleRunPanel(false)" title="Hide run panel" aria-label="Hide run panel">'
  +'<svg viewBox="0 0 24 24" fill="none" width="14" height="14" aria-hidden="true">'
  +'<path d="M9 6l6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
  +'</svg>'
  +'</button>'
  +'</div>'
  +'<div class="run-panel-summary" aria-hidden="true">'
  +'<div class="run-panel-summary-item">'
  +'<div class="run-panel-summary-label">Progress</div>'
  +'<div class="run-panel-summary-value" id="runPanelProgress">0 / 0</div>'
  +'</div>'
  +'<div class="run-panel-summary-item">'
  +'<div class="run-panel-summary-label">Current Action</div>'
  +'<div class="run-panel-summary-value run-panel-summary-text" id="runPanelAction">Waiting for first step</div>'
  +'</div>'
  +'<div class="run-panel-summary-item">'
  +'<div class="run-panel-summary-label">Outputs</div>'
  +'<div class="run-panel-summary-value run-panel-summary-text" id="runPanelOutputs">0 files ? 0 tools ? 0 errors</div>'
  +'</div>'
  +'</div>'
  +'<div class="run-panel-stream" id="runPanelStream">'
  +'<div class="run-panel-empty" id="runPanelEmpty">Run stream will appear here.</div>'
  +'</div>';
}

function _mountRunPanelLayout(){
 var main=document.querySelector('.main');
 var shell=document.getElementById('chatShell');
 if(!main || !shell) return;
 var content=main.querySelector('.content');
 var host=document.getElementById('runPanel');
 var input=document.querySelector('.main > .input');
 var stageWrap=document.getElementById('mainStage');
 if(!stageWrap){
  stageWrap=document.createElement('div');
  stageWrap.id='mainStage';
  stageWrap.className='main-stage';
 }
 if(stageWrap.parentNode!==main){
  main.insertBefore(stageWrap, main.firstChild||null);
 }
 if(content && content.parentNode!==stageWrap){
  stageWrap.appendChild(content);
 }
 if(input && input.parentNode!==stageWrap){
  stageWrap.appendChild(input);
 }
 if(host && host.parentNode!==main){
  main.appendChild(host);
 }else if(host && main.lastElementChild!==host){
  main.appendChild(host);
 }
}

function _getRunPanelEls(){
 var shell=document.getElementById('chatShell');
 var main=document.querySelector('.main');
 if(!shell || !main) return null;
 return {
  main:main,
  shell:shell,
  stage:document.getElementById('mainStage'),
  host:document.getElementById('runPanel'),
  btn:document.getElementById('runPanelBtn'),
  inlineToggle:document.getElementById('runPanelInlineToggle'),
  kicker:document.getElementById('runPanelKicker'),
  closeBtn:document.getElementById('runPanelCloseBtn'),
  status:document.getElementById('runPanelStatus'),
  task:document.getElementById('runPanelTask'),
  meta:document.getElementById('runPanelMeta'),
  progress:document.getElementById('runPanelProgress'),
  action:document.getElementById('runPanelAction'),
  outputs:document.getElementById('runPanelOutputs'),
  stream:document.getElementById('runPanelStream'),
  empty:document.getElementById('runPanelEmpty')
 };
}

function _ensureRunPanelMetaLine(els){
 if(!els || !els.host) return null;
 if(els.meta) return els.meta;
 var headerMain=els.host.querySelector('.run-panel-header-main');
 if(!headerMain) return null;
 var meta=document.createElement('div');
 meta.id='runPanelMeta';
 meta.className='run-panel-meta';
 headerMain.appendChild(meta);
 els.meta=meta;
 return meta;
}

function _formatRunPanelOutputs(fileCount, toolCount, errorCount){
 return String(fileCount||0)+' 个文件 · '+String(toolCount||0)+' 个工具 · '+String(errorCount||0)+' 个异常';
}

var _runPanelCopy={
 show:'\u663e\u793a\u8fd0\u884c\u9762\u677f',
 hide:'\u9690\u85cf\u8fd0\u884c\u9762\u677f',
 kicker:'[RUN #000 | READY]',
 progress:'\u8fdb\u5ea6',
 action:'\u5f53\u524d\u52a8\u4f5c',
 outputs:'TOOLS',
 idle:'STATUS:    [IDLE] READY (0/0)',
 taskIdle:'ELAPSED:   00:00',
 actionIdle:'\u6682\u65e0\u6d3b\u52a8',
 empty:'AGENT STANDBY · Awaiting current run...'
};

var _runPanelEmptyCopy={
 idle:'AGENT STANDBY · Awaiting current run...',
 open:'RUNTIME CHANNEL OPEN · Awaiting agent events...',
 quiet:'RUNTIME CHANNEL OPEN · No events emitted.',
 error:'RUNTIME CHANNEL ERROR · Agent unavailable.',
 stopped:'RUNTIME CHANNEL CLOSED · Run interrupted.'
};

function _setRunPanelEmptyState(kind){
 var text=_runPanelEmptyCopy[kind]||_runPanelEmptyCopy.idle;
 _runPanelCopy.empty=text;
 var els=(typeof _getRunPanelEls==='function') ? _getRunPanelEls() : null;
 if(els && els.empty) els.empty.textContent=text;
}

function _formatRunPanelOutputs(fileCount, toolCount, errorCount){
 return String(fileCount||0)+' \u4e2a\u6587\u4ef6 \u00b7 '+String(toolCount||0)+' \u6b21\u5de5\u5177 \u00b7 '+String(errorCount||0)+' \u4e2a\u5f02\u5e38';
}

function _readRunPanelPref(){
 try{
  var raw=localStorage.getItem(_runPanelStoreKey);
  if(raw===null) return true;
  return !(raw==='0' || raw==='false');
 }catch(e){
  return true;
 }
}

function _writeRunPanelPref(open){
 try{
  localStorage.setItem(_runPanelStoreKey, open ? 'true' : 'false');
 }catch(e){}
}

function _applyRunPanelUiState(){
 var els=_getRunPanelEls();
 if(!els || !els.shell || !els.main) return;
 var open=!!(_runPanelUserOpen && _runPanelTabVisible);
 els.main.classList.toggle('run-panel-open', open);
 els.main.classList.toggle('run-panel-collapsed', !open);
 els.shell.classList.toggle('run-panel-open', open);
 els.shell.classList.toggle('run-panel-collapsed', !open);
 if(els.host) els.host.style.display=_runPanelTabVisible ? '' : 'none';
 if(els.btn){
  els.btn.style.display=_runPanelTabVisible ? '' : 'none';
  els.btn.classList.toggle('is-active', open);
  els.btn.setAttribute('aria-pressed', open ? 'true' : 'false');
  els.btn.title=open ? '隐藏运行面板' : '显示运行面板';
  }
 if(els.closeBtn) els.closeBtn.title='隐藏运行面板';
}

function _applyRunPanelUiState(){
 var els=_getRunPanelEls();
 if(!els || !els.shell || !els.main) return;
 var open=!!(_runPanelUserOpen && _runPanelTabVisible);
 els.main.classList.toggle('run-panel-open', open);
 els.main.classList.toggle('run-panel-collapsed', !open);
 els.shell.classList.toggle('run-panel-open', open);
 els.shell.classList.toggle('run-panel-collapsed', !open);
 if(els.host) els.host.style.display=_runPanelTabVisible ? '' : 'none';
 if(els.btn){
  els.btn.style.display=_runPanelTabVisible ? '' : 'none';
  els.btn.classList.toggle('is-active', open);
  els.btn.setAttribute('aria-pressed', open ? 'true' : 'false');
  els.btn.title=open ? _runPanelCopy.hide : _runPanelCopy.show;
 }
 if(els.inlineToggle){
  var showInline=_runPanelTabVisible && !open;
  els.inlineToggle.classList.toggle('is-visible', showInline);
  els.inlineToggle.setAttribute('aria-hidden', showInline ? 'false' : 'true');
  els.inlineToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  els.inlineToggle.title=_runPanelCopy.show;
 }
 if(els.closeBtn) els.closeBtn.title=_runPanelCopy.hide;
}

function toggleRunPanel(forceOpen){
 if(typeof forceOpen==='boolean') _runPanelUserOpen=!!forceOpen;
 else _runPanelUserOpen=!_runPanelUserOpen;
 _writeRunPanelPref(_runPanelUserOpen);
 _applyRunPanelUiState();
 return false;
}

function _setRunPanelTabState(isChatTab){
 _runPanelTabVisible=!!isChatTab;
 _applyRunPanelUiState();
}

window.toggleRunPanel=toggleRunPanel;
window._setRunPanelTabState=_setRunPanelTabState;

(function _initRunPanelUi(){
 _runPanelUserOpen=_readRunPanelPref();
 _normalizeRunPanelDom();
 _mountRunPanelLayout();
 var els=_getRunPanelEls();
 if(els){
  _ensureRunPanelMetaLine(els);
  var summaryLabels=els.host ? els.host.querySelectorAll('.run-panel-summary-label') : [];
  if(els.kicker) els.kicker.textContent='本轮运行';
  if(summaryLabels[0]) summaryLabels[0].textContent='进度';
  if(summaryLabels[1]) summaryLabels[1].textContent='当前动作';
  if(summaryLabels[2]) summaryLabels[2].textContent='已产出';
  if(els.status) els.status.textContent='空闲';
  if(els.task) els.task.textContent='这里会实时显示本轮思考和动作。';
  if(els.progress) els.progress.textContent='0 / 0';
  if(els.action) els.action.textContent='等待第一个动作';
  if(els.outputs) els.outputs.textContent=_formatRunPanelOutputs(0, 0, 0);
  if(els.empty) els.empty.textContent='开始一轮真实任务后，这里会实时显示思考、动作和执行过程。';
 }
 _applyRunPanelUiState();
})();

(function _refreshRunPanelUiCopy(){
 var els=_getRunPanelEls();
 if(!els) return;
 _ensureRunPanelMetaLine(els);
 var summaryLabels=els.host ? els.host.querySelectorAll('.run-panel-summary-label') : [];
 if(els.kicker) els.kicker.textContent=_runPanelCopy.kicker;
  if(summaryLabels[0]) summaryLabels[0].textContent=_runPanelCopy.progress;
  if(summaryLabels[1]) summaryLabels[1].textContent=_runPanelCopy.action;
  if(summaryLabels[2]) summaryLabels[2].textContent=_runPanelCopy.outputs;
 if(els.status) els.status.textContent=_runPanelCopy.idle+' · 0 / 0';
 if(els.task) els.task.textContent=_runPanelCopy.actionIdle;
 if(els.progress) els.progress.textContent='0 / 0';
 if(els.action) els.action.textContent=_runPanelCopy.actionIdle;
 if(els.outputs) els.outputs.textContent=_formatRunPanelOutputs(0,0,0);
 if(els.empty) els.empty.textContent=_runPanelCopy.empty;
 _applyRunPanelUiState();
})();

(function _finalizeRunPanelStaticCopy(){
 var els=_getRunPanelEls();
 if(!els) return;
 _ensureRunPanelMetaLine(els);
 if(els.kicker) els.kicker.textContent=_runPanelCopy.kicker;
 if(els.status) els.status.textContent=_runPanelCopy.idle+' \u00b7 0 / 0';
 if(els.task) els.task.textContent='\u603b\u8017\u65f6 \u00b7 00:00';
 if(els.meta) els.meta.textContent=_formatRunPanelOutputs(0,0,0);
 if(els.empty) els.empty.textContent=_runPanelCopy.empty;
})();

var _runPanelConsoleCounterKey='nova_run_panel_console_counter';

function _readRunPanelConsoleCounter(){
 try{
  var raw=localStorage.getItem(_runPanelConsoleCounterKey);
  var parsed=parseInt(raw,10);
  return isFinite(parsed) && parsed>0 ? parsed : 0;
 }catch(e){
  return 0;
 }
}

function _nextRunPanelConsoleCounter(){
 var next=_readRunPanelConsoleCounter()+1;
 try{
  localStorage.setItem(_runPanelConsoleCounterKey, String(next));
 }catch(e){}
 return next;
}

function _formatRunPanelConsoleSeq(value){
 return String(Math.max(0, parseInt(value,10)||0)).padStart(3,'0');
}

function _formatRunPanelConsoleTimestamp(value){
 if(!value) return 'READY';
 var d=new Date(value);
 if(isNaN(d.getTime())) return 'READY';
 var y=String(d.getFullYear());
 var m=String(d.getMonth()+1).padStart(2,'0');
 var day=String(d.getDate()).padStart(2,'0');
 var hh=String(d.getHours()).padStart(2,'0');
 var mm=String(d.getMinutes()).padStart(2,'0');
 var ss=String(d.getSeconds()).padStart(2,'0');
 return y+'-'+m+'-'+day+' '+hh+':'+mm+':'+ss;
}

function _estimateRunPanelConsoleTokens(value){
 var text=String(value||'').trim();
 if(!text) return 0;
 var cjk=(text.match(/[\u3400-\u9fff]/g)||[]).length;
 var latin=(text.replace(/[\u3400-\u9fff]/g,' ').match(/[A-Za-z0-9_]+/g)||[]).length;
 var symbols=(text.match(/[^\sA-Za-z0-9_\u3400-\u9fff]/g)||[]).length;
 return Math.max(1, cjk + Math.ceil(latin*0.75) + Math.ceil(symbols*0.25));
}

function _formatRunPanelConsoleHeader(runNumber, startedAt){
 return '[RUN #'+_formatRunPanelConsoleSeq(runNumber)+' | '+_formatRunPanelConsoleTimestamp(startedAt)+']';
}

function _formatRunPanelConsoleStatus(statusKey, progressCurrent, totalSteps){
 var marker='IDLE';
 var label='READY';
 if(statusKey==='thinking'){
  marker='...';
  label='THINKING';
 }else if(statusKey==='tool'){
  marker='RUN';
  label='TOOLING';
 }else if(statusKey==='waiting'){
  marker='WAIT';
  label='WAITING';
 }else if(statusKey==='running'){
  marker='RUN';
  label='RUNNING';
 }else if(statusKey==='done'){
  marker='OK';
  label='COMPLETED';
 }else if(statusKey==='error'){
  marker='ERR';
  label='FAILED';
 }
 return 'STATUS:    ['+marker+'] '+label+' ('+String(progressCurrent||0)+'/'+String(totalSteps||0)+')';
}

function _formatRunPanelTokenLine(inputTokens, outputTokens){
 return 'TOKENS:    ~'+String(inputTokens||0)+' / ~'+String(outputTokens||0)+' (in/out)';
}

function _formatRunPanelToolLine(fileCount, toolCount, errorCount){
 return 'TOOLS:     '+String(toolCount||0)+' CALLS | '+String(errorCount||0)+' ERRORS | '+String(fileCount||0)+' FILES';
}

function _normalizeRunPanelConsoleDom(){
 var host=document.getElementById('runPanel');
 if(!host) return;
 host.innerHTML=''
  +'<div class="run-panel-header">'
  +'<div class="run-panel-header-main">'
  +'<div class="run-panel-kicker" id="runPanelKicker">[RUN #000 | READY]</div>'
  +'<div class="run-panel-status-pill state-idle" id="runPanelStatus">STATUS:    [IDLE] READY (0/0)</div>'
  +'<div class="run-panel-task" id="runPanelTask">ELAPSED:   00:00</div>'
  +'<div class="run-panel-meta" id="runPanelMeta">TOKENS:    ~0 / ~0 (in/out)</div>'
  +'<div class="run-panel-outputs" id="runPanelOutputs">TOOLS:     0 CALLS | 0 ERRORS | 0 FILES</div>'
  +'</div>'
  +'</div>'
  +'<div class="run-panel-stream" id="runPanelStream">'
  +'<div class="run-panel-empty" id="runPanelEmpty">Run stream will appear here.</div>'
  +'</div>';
}

(function _rebuildRunPanelConsoleUi(){
 _normalizeRunPanelConsoleDom();
 _mountRunPanelLayout();
 var els=_getRunPanelEls();
 if(!els) return;
 if(els.kicker) els.kicker.textContent='[RUN #000 | READY]';
 if(els.status) els.status.textContent='STATUS:    [IDLE] READY (0/0)';
 if(els.task) els.task.textContent='ELAPSED:   00:00';
 if(els.meta) els.meta.textContent='TOKENS:    ~0 / ~0 (in/out)';
 if(els.outputs) els.outputs.textContent='TOOLS:     0 CALLS | 0 ERRORS | 0 FILES';
 if(els.empty) els.empty.textContent=_runPanelCopy.empty;
 _applyRunPanelUiState();
})();

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
var _runPanelEls=_getRunPanelEls();
var _runPromptText=String(text||'').replace(/\s+/g,' ').trim();
var _runNumber=_nextRunPanelConsoleCounter();
var _runStartedAt=Date.now();
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
  var _streamBubble=null; // 流式输出的气泡
  var _streamText=''; // 流式累积的文本
  var _streamStarted=false;
  var _suppressTypingCursor=false;
  var _streamAutoFollow=true;
  var _streamScrollFollowBound=false;

 function _truncateRunText(value, limit){
  var textValue=String(value||'').replace(/\s+/g,' ').trim();
  if(!textValue) return '';
  if(textValue.length<=limit) return textValue;
  return textValue.slice(0, Math.max(0, limit-1))+'…';
 }

 function _extractRunFiles(textValue){
  var text=String(textValue||'');
  if(!text) return [];
  var matches=text.match(/(?:[A-Za-z]:)?[\w./\\-]+\.(?:css|js|py|html|json|md|ts|tsx|jsx|yml|yaml|txt|ttf|otf|svg)/ig) || [];
  var seen={};
  var files=[];
  for(var i=0;i<matches.length;i++){
   var file=String(matches[i]||'').replace(/[),.;:]+$/,'').trim();
   if(!file || seen[file.toLowerCase()]) continue;
   seen[file.toLowerCase()]=true;
   files.push(file);
  }
  return files;
 }

 function _runPanelStateKey(status, phase){
  if(status==='error') return 'error';
  if(status==='running'){
   if(phase==='thinking') return 'thinking';
   if(phase==='tool') return 'tool';
   if(phase==='waiting') return 'waiting';
   return 'running';
  }
  return status==='done' ? 'done' : 'idle';
 }

 function _runPanelStatusText(statusKey){
  if(statusKey==='error') return '异常';
  if(statusKey==='thinking') return '思考中';
  if(statusKey==='tool') return '调用工具';
  if(statusKey==='waiting') return '等待中';
  if(statusKey==='running') return '执行中';
  if(statusKey==='done') return '已完成';
  return '空闲';
 }

 function _runPanelStepStateText(stepObj){
  if(!stepObj) return '';
  var key=_runPanelStateKey(stepObj.status, stepObj.phase);
  if(key==='error') return '异常';
  if(key==='thinking') return '思考';
  if(key==='tool') return '工具';
  if(key==='waiting') return '等待';
  if(key==='running') return '进行中';
  return '完成';
 }

 function _runPanelStatusText(statusKey){
  if(statusKey==='error') return '\u5f02\u5e38';
  if(statusKey==='thinking') return '\u601d\u8003\u4e2d';
  if(statusKey==='tool') return '\u8c03\u7528\u5de5\u5177';
  if(statusKey==='waiting') return '\u7b49\u5f85\u4e2d';
  if(statusKey==='running') return '\u6267\u884c\u4e2d';
  if(statusKey==='done') return '\u5df2\u5b8c\u6210';
  return '\u7a7a\u95f2';
 }

function _runPanelStepStateText(stepObj){
 if(!stepObj) return '';
 var key=_runPanelStateKey(stepObj.status, stepObj.phase);
 if(key==='error') return '\u5f02\u5e38';
 if(key==='thinking') return '\u601d\u8003';
 if(key==='tool') return '\u5de5\u5177';
 if(key==='waiting') return '\u7b49\u5f85';
 if(key==='running') return '\u8fdb\u884c\u4e2d';
 return '\u5b8c\u6210';
}

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

function _escapeRunPanelText(value){
 return String(value||'')
  .replace(/&/g,'&amp;')
  .replace(/</g,'&lt;')
  .replace(/>/g,'&gt;')
  .replace(/"/g,'&quot;')
  .replace(/'/g,'&#39;');
}

function _getRunPanelStepDetailParts(stepObj){
 var raw=String((stepObj && (stepObj.fullDetail||stepObj.summaryDetail||stepObj.displayLabel||stepObj.label))||'').trim();
 if(!raw) return {text:'', wait:''};
 if(typeof _splitProcessWaitSuffix==='function'){
  var split=_splitProcessWaitSuffix(raw);
  return {
   text:String((split&&split.text)||raw).trim(),
   wait:String((split&&split.wait)||'').trim()
  };
 }
 return {text:raw, wait:''};
}

function _getRunPanelStepElapsed(stepObj){
 if(!stepObj) return '';
 var parts=_getRunPanelStepDetailParts(stepObj);
 if(parts.wait) return parts.wait;
 if(stepObj.status==='running' && stepObj.startedAt){
  var seconds=Math.max(1, Math.round((Date.now()-Number(stepObj.startedAt||Date.now()))/1000));
  return String(seconds)+'s';
 }
 return '';
}

function _getRunPanelStepIconClass(stepObj){
 if(!stepObj) return 'state-pending phase-info';
 var status=String(stepObj.status||'pending');
 var phase=String(stepObj.phase||'info');
 return 'status-'+status+' phase-'+phase;
}

function _getRunPanelStepBadge(stepObj){
 if(!stepObj) return '[WAIT]';
 var status=String(stepObj.status||'pending');
 var phase=String(stepObj.phase||'info');
 if(status==='error') return '[ERR]';
 if(status==='running' && phase==='waiting') return '[WAIT]';
 if(status==='running') return '[RUN]';
 if(status==='done') return '[OK]';
 return '[WAIT]';
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

function _detachRunPanelScrollFollow(){
 if(_runPanelEls && _runPanelEls.stream && _runPanelScrollFollowBound){
  _runPanelEls.stream.removeEventListener('scroll', _syncRunPanelAutoFollow);
 }
 _runPanelScrollFollowBound=false;
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
  var labelText=_escapeRunPanelText(missing ? ('step_'+(i+1)) : (step.displayLabel||step.label||t('chat.process')));
  var detailParts=missing ? {text:'\u6b65\u9aa4\u6570\u636e\u6682\u672a\u5c31\u7eea\uff0c\u7b49\u5f85\u540e\u7eed\u5237\u65b0\u3002', wait:''} : _getRunPanelStepDetailParts(step);
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

function _collectStepToolNames(step){
 var names=(typeof _normalizeStepNameList==='function') ? _normalizeStepNameList(step&&step.parallelTools) : [];
 if(names.length) return names;
 var primary=String((step&&(step.toolName||step.toolKey))||'').trim();
 return primary ? [primary] : [];
}

  function _syncRunPanelHeader(){
  if(!_runPanelEls) return;
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
  else if(_streamStarted || steps.length) statusKey='running';
  if(replyText) statusKey='done';
  var currentAction=_truncateRunText(
   pendingState.activitySummary
   || (runningStep && (runningStep.fullDetail||runningStep.summaryDetail||runningStep.displayLabel||runningStep.label))
   || (latestStep && (latestStep.fullDetail||latestStep.summaryDetail||latestStep.displayLabel||latestStep.label))
   || '',
   120
  );
  if(!currentAction){
   if(_streamStarted && !replyText) currentAction='正在输出回复';
   else if(steps.length) currentAction='等待下一步动作';
   else currentAction='等待第一个动作';
  }
  if(_runPanelEls.task){
   _runPanelEls.task.textContent=_runPromptText ? _truncateRunText(_runPromptText, 120) : '这里会实时显示本轮思考和动作。';
  }
  if(_runPanelEls.status){
   _runPanelEls.status.textContent=_runPanelStatusText(statusKey);
   _runPanelEls.status.className='run-panel-status-pill state-'+statusKey;
  }
  if(_runPanelEls.progress){
   _runPanelEls.progress.textContent=(progressCurrent||0)+' / '+(totalSteps||0);
  }
  if(_runPanelEls.action){
   _runPanelEls.action.textContent=currentAction;
  }
  if(_runPanelEls.outputs){
   _runPanelEls.outputs.textContent=_formatRunPanelOutputs(Object.keys(fileMap).length, Object.keys(toolMap).length, errorCount);
  }
  if(_runPanelEls.task && !_runPromptText){
   _runPanelEls.task.textContent=_runPanelCopy.taskIdle;
  }
  if(_runPanelEls.action && !steps.length && !_streamStarted && !replyText){
   _runPanelEls.action.textContent=_runPanelCopy.actionIdle;
  }
 }

  function _syncRunPanelHeader(){
   if(!_runPanelEls) return;
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
   else if(_streamStarted || steps.length) statusKey='running';
   if(replyText) statusKey='done';
   var currentAction=_truncateRunText(
    pendingState.activitySummary
    || (runningStep && (runningStep.fullDetail||runningStep.summaryDetail||runningStep.displayLabel||runningStep.label))
    || (latestStep && (latestStep.fullDetail||latestStep.summaryDetail||latestStep.displayLabel||latestStep.label))
    || '',
    120
   );
   if(!currentAction){
    if(_streamStarted && !replyText) currentAction='正在输出回复';
    else if(steps.length) currentAction='等待下一步动作';
    else currentAction=_runPanelCopy.actionIdle;
   }
   if(_runPanelEls.status){
    _runPanelEls.status.textContent=_runPanelStatusText(statusKey)+' · '+(progressCurrent||0)+' / '+(totalSteps||0);
    _runPanelEls.status.className='run-panel-status-pill state-'+statusKey;
   }
   if(_runPanelEls.task){
    _runPanelEls.task.textContent=currentAction;
   }
   if(_runPanelEls.progress){
    _runPanelEls.progress.textContent=(progressCurrent||0)+' / '+(totalSteps||0);
   }
   if(_runPanelEls.action){
    _runPanelEls.action.textContent=currentAction;
   }
   if(_runPanelEls.outputs){
    _runPanelEls.outputs.textContent=_formatRunPanelOutputs(Object.keys(fileMap).length, Object.keys(toolMap).length, errorCount);
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
   else if(_streamStarted || steps.length) statusKey='running';
   if(replyText) statusKey='done';
   var currentAction=_truncateRunText(
    pendingState.activitySummary
    || (runningStep && (runningStep.fullDetail||runningStep.summaryDetail||runningStep.displayLabel||runningStep.label))
    || (latestStep && (latestStep.fullDetail||latestStep.summaryDetail||latestStep.displayLabel||latestStep.label))
    || '',
    120
   );
   if(!currentAction){
    if(_streamStarted && !replyText) currentAction='\u6b63\u5728\u8f93\u51fa\u56de\u590d';
    else if(steps.length) currentAction='\u7b49\u5f85\u4e0b\u4e00\u4e2a\u52a8\u4f5c';
    else currentAction=_runPanelCopy.actionIdle;
   }
  if(_runPanelEls.status){
    _runPanelEls.status.textContent=_formatRunPanelConsoleStatus(statusKey, progressCurrent, totalSteps);
    _runPanelEls.status.className='run-panel-status-pill state-'+statusKey;
   }
   var outputTokenCount=_estimateRunPanelConsoleTokens(replyText||_streamText||'');
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

 function _detachIdlePendingRoot(){
  if(!pendingState.root || pendingState.replyVisible) return;
  if(pendingState.root.parentNode){
   pendingState.root.parentNode.removeChild(pendingState.root);
  }
 }

 function _syncStreamAutoFollow(){
  var nearBottom=(typeof window._isChatNearBottom==='function')
   ? !!window._isChatNearBottom(180)
   : _nearBottom();
  _streamAutoFollow=nearBottom;
  if(typeof window._setChatAutoStick==='function'){
   window._setChatAutoStick(nearBottom);
  }
 }

 function _attachStreamScrollFollow(){
  if(!chat || _streamScrollFollowBound) return;
  chat.addEventListener('scroll', _syncStreamAutoFollow, {passive:true});
  _streamScrollFollowBound=true;
  _syncStreamAutoFollow();
 }

 function _detachStreamScrollFollow(){
  if(chat && _streamScrollFollowBound){
   chat.removeEventListener('scroll', _syncStreamAutoFollow);
  }
  _streamScrollFollowBound=false;
 }

 function _followStreamToBottom(options){
  if(!_streamAutoFollow) return false;
  if(typeof window._setChatAutoStick==='function'){
   window._setChatAutoStick(true);
  }
  return _stickChatToBottom(options||{threshold:220});
 }

 pendingState.placeholderTimer=setTimeout(function(){
  if(pendingState.replyVisible || pendingState.steps.length>0 || replyText) return;
  chat.appendChild(pendingState.root);
  _stickChatToBottom();
 },260);

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
  var parallelSize=(typeof _normalizePositiveStepCount==='function') ? _normalizePositiveStepCount(card&&card.parallel_size) : 0;
  _appendUniqueStepMeta(summaryParts, lead, '');
  _appendUniqueStepMeta(fullParts, lead, '');
  if(parallelSize<=1 && String(state||'')==='running' && goal){
   _appendUniqueStepMeta(fullParts, goal, '目标：');
  }
  if(parallelSize<=1 && String(state||'')==='running' && expected){
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
  var explicitPhase=String((card&&card.phase)||'').trim().toLowerCase();
  var parallelGroupId=String((card&&card.parallel_group_id)||'').trim();
  var parallelIndex=(typeof _normalizePositiveStepCount==='function') ? _normalizePositiveStepCount(card&&card.parallel_index) : 0;
  var parallelSize=(typeof _normalizePositiveStepCount==='function') ? _normalizePositiveStepCount(card&&card.parallel_size) : 0;
  var parallelCompletedCount=(typeof _normalizePositiveStepCount==='function') ? _normalizePositiveStepCount(card&&card.parallel_completed_count) : 0;
  var parallelSuccessCount=(typeof _normalizePositiveStepCount==='function') ? _normalizePositiveStepCount(card&&card.parallel_success_count) : 0;
  var parallelFailureCount=(typeof _normalizePositiveStepCount==='function') ? _normalizePositiveStepCount(card&&card.parallel_failure_count) : 0;
  var parallelTools=(typeof _normalizeStepNameList==='function') ? _normalizeStepNameList(card&&card.parallel_tools) : [];
  var toolName=String((card&&card.tool_name)||'').trim();
  var phase='info';
  var displayLabel=rawLabel||t('chat.process');
  var toolKey='';
  var toolFallback=_toolLabelFallback(rawLabel);
  var isParallelTool=!!(parallelGroupId && parallelSize>1);
  if(explicitPhase==='thinking' || (!explicitPhase && _looksLikeThinkingLabel(rawLabel))){
   phase='thinking';
   displayLabel='Thinking';
  }else if((explicitPhase==='info' || !explicitPhase) && _looksLikeMemoryLoadLabel(rawLabel)){
   displayLabel='memory_load';
  }else if(explicitPhase==='tool' || toolFallback){
    phase='tool';
    toolKey=toolName||_extractToolKey(rawSummaryDetail)||_extractToolKey(rawFullDetail)||toolFallback||(parallelTools[0]||'');
    displayLabel=isParallelTool ? (rawLabel||'并行调用') : (toolKey||toolFallback||rawLabel||'tool');
    fullDetail=_extractToolDetail(rawFullDetail)||rawFullDetail||rawSummaryDetail;
    summaryDetail=_extractToolDetail(rawSummaryDetail)||fullDetail||rawSummaryDetail;
    fullDetail=_simplifyToolDetail(fullDetail, isParallelTool ? '' : toolKey, state);
    summaryDetail=_simplifyToolDetail(summaryDetail, isParallelTool ? '' : toolKey, state);
  }else if(explicitPhase==='waiting' || /\u7b49\u5f85|waiting/i.test(rawLabel)){
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
   toolName:toolName,
   parallelGroupId:parallelGroupId,
   parallelIndex:parallelIndex,
   parallelSize:parallelSize,
   parallelCompletedCount:parallelCompletedCount,
   parallelSuccessCount:parallelSuccessCount,
   parallelFailureCount:parallelFailureCount,
   parallelTools:parallelTools
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
  chat.insertBefore(step.root, pendingState.root);
  return step;
}

 function _canMergeStep(existing, meta){
  if(!existing || !meta) return false;
  if(existing.stepKey && meta.stepKey && existing.stepKey===meta.stepKey) return true;
  if(existing.phase==='thinking' && meta.phase==='thinking'){
   var existingThinking=String(existing.fullDetail||existing.summaryDetail||'').trim();
   var nextThinking=String(meta.fullDetail||meta.summaryDetail||'').trim();
   if(existingThinking && nextThinking && (_stepMetaContains(existingThinking, nextThinking) || _stepMetaContains(nextThinking, existingThinking))){
    return true;
   }
   return false;
  }
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
   _applyStepMeta(mergeTarget, meta);
   _setStepStatus(mergeTarget, meta.status);
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
  bubble.className='bubble assistant-reply-markdown';
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
  _streamBubble=bubble;
  _streamBlocksEl=blocksEl;
  _streamLineEl=lineEl;
  _streamProtocol='';
  _streamText='';
  _streamLiveText='';
  _streamStarted=true;
  _suppressTypingCursor=false;
  _streamTokenCount=0;
  _attachStreamScrollFollow();
  _followStreamToBottom({threshold:220});
  _syncRunPanelHeader();
 }

 var _scrollRAF=0; // scroll 节流
var _renderTimer=0; // 渐进渲染节流
var _streamTokenCount=0; // 流式 token 计数，前 N 个无条件滚动
 var _lastRenderedBlockCount=0; // 上次渲染的块数，用于 fade-in 新块
var _streamLineEl=null;
var _streamBlocksEl=null;
var _streamProtocol='';
var _streamLiveText='';
var _streamTailTargetText='';
var _streamTailDisplayText='';
var _streamTailTimer=0;
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
  return chat.scrollHeight - chat.scrollTop - chat.clientHeight < 220;
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
    html=html.replace(/\*\*(.+?)\*\*/g,'$1');
    html=html.replace(/__(.+?)__/g,'$1');
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
  var maxChars=chars.length>240 ? 64 : 28;
  if(chars.length<=maxChars){
   var fullChunk=_streamFlushBuffer;
   _streamFlushBuffer='';
   return fullChunk;
  }
  var minChars=Math.max(1, maxChars-12);
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
  if(reply) return reply;
  return streamed;
 }

function _findHardStreamBoundary(text){
  var source=String(text||'').replace(/\r/g,'');
  if(!source) return 0;
  var lines=source.split('\n');
  var offset=0;
  var inFence=false;
  var lastBoundary=0;
  for(var i=0;i<lines.length;i++){
   var line=lines[i];
   var trimmed=String(line||'').trim();
   var lineEnd=offset+line.length;
   var blockEnd=(i<lines.length-1) ? (lineEnd+1) : lineEnd;
   var lineHasBreak=i<lines.length-1;
   if(/^```/.test(trimmed)){
    inFence=!inFence;
    if(!inFence && lineHasBreak) lastBoundary=blockEnd;
    offset=blockEnd;
    continue;
   }
   if(inFence){
    offset=blockEnd;
    continue;
   }
   if(!lineHasBreak){
    offset=blockEnd;
    continue;
   }
   if(trimmed==='' && blockEnd>0){
    lastBoundary=blockEnd;
   }else if(/^(?:#{1,6}\s|[-*+]\s+|\d+[.)]\s+|>\s?)/.test(trimmed)){
    lastBoundary=blockEnd;
   }
   offset=blockEnd;
  }
  return lastBoundary;
 }

function _findSoftStreamBoundary(text){
  return 0;
}

function _extractRenderableStreamState(text){
  var source=String(text||'').replace(/\r/g,'');
  if(!source) return {committed:'', pending:''};
  var boundary=_findHardStreamBoundary(source);
  if(boundary<=0) return {committed:'', pending:source};
  return {
   committed:source.slice(0, boundary),
   pending:source.slice(boundary)
  };
}

function _ensureStreamBubbleVisible(){
  if(!_streamBubble) return;
  _streamBubble.style.display='';
  var meta=_streamBubble.parentNode ? _streamBubble.parentNode.querySelector('.msg-meta') : null;
  if(meta) meta.style.display='';
}

function _appendRenderedNodes(target, text){
  if(!target) return false;
  var html=renderAssistantBubbleHtml(String(text||''), '')||'';
  if(!String(html||'').trim()) return false;
  return _appendRenderedHtml(target, html);
}

function _appendRenderedHtml(target, html){
  if(!target) return false;
  var safeHtml=String(html||'').trim();
  if(!safeHtml) return false;
  var frag=document.createElement('div');
  frag.innerHTML=safeHtml;
  while(frag.firstChild){
   target.appendChild(frag.firstChild);
  }
  return true;
}

function _appendIncrementalMarkdownBlocks(blocks){
  if(!_streamBlocksEl || !Array.isArray(blocks) || !blocks.length) return;
  _ensureStreamBubbleVisible();
  for(var i=0;i<blocks.length;i++){
   var block=blocks[i]||{};
   if(String(block.kind||'')!=='markdown_block') continue;
   _appendRenderedHtml(_streamBlocksEl, block.html||'');
  }
}

function _renderStructuredStreamTail(text, html){
  _streamLiveText=String(text||'');
  if(!_streamLineEl) return;
  var safeHtml=String(html||'').trim();
  if(safeHtml){
   _ensureStreamBubbleVisible();
   _streamLineEl.style.display='block';
   _streamLineEl.innerHTML=safeHtml;
   _followStreamToBottom({threshold:220});
  }else if(_streamLiveText){
   _ensureStreamBubbleVisible();
   _streamLineEl.style.display='block';
   _streamLineEl.innerHTML='';
   _streamLineEl.textContent=typeof stripMarkdownForStreamingText==='function'
    ? stripMarkdownForStreamingText(_streamLiveText)
    : _streamLiveText;
   _followStreamToBottom({threshold:220});
  }else{
   _streamLineEl.innerHTML='';
   _streamLineEl.textContent='';
   _streamLineEl.style.display='none';
  }
}

function _clearStructuredTailTimer(){
  if(_streamTailTimer){
   clearTimeout(_streamTailTimer);
   _streamTailTimer=0;
  }
}

function _pickStructuredTailChunk(remaining){
  var chars=Array.from(String(remaining||''));
  if(!chars.length) return '';
  var maxChars=chars.length>24 ? 8 : 5;
  var minChars=Math.min(3, maxChars);
  var cut=Math.min(maxChars, chars.length);
  for(var i=cut;i>=minChars;i--){
   var joined=chars.slice(0, i).join('');
   var last=chars[i-1] || '';
   if(/\n/.test(last)) return joined;
   if(/[，。、；：！？,.!?;:]/.test(last)) return joined;
  }
  return chars.slice(0, cut).join('');
}

function _pumpStructuredTail(){
  _streamTailTimer=0;
  if(_streamTailDisplayText===_streamTailTargetText){
   _renderStructuredStreamTail(_streamTailDisplayText);
   return;
  }
  if(_streamTailTargetText.indexOf(_streamTailDisplayText)!==0){
   _streamTailDisplayText=_streamTailTargetText;
   _renderStructuredStreamTail(_streamTailDisplayText);
   return;
  }
  var remaining=_streamTailTargetText.slice(_streamTailDisplayText.length);
  var nextChunk=_pickStructuredTailChunk(remaining);
  if(!nextChunk){
   _streamTailDisplayText=_streamTailTargetText;
  }else{
   _streamTailDisplayText+=nextChunk;
  }
  _renderStructuredStreamTail(_streamTailDisplayText);
  if(_streamTailDisplayText!==_streamTailTargetText){
   _streamTailTimer=setTimeout(_pumpStructuredTail, 26);
  }
}

function _syncStructuredStreamTail(tailText){
  var nextTarget=String(tailText||'');
  _clearStructuredTailTimer();
  _streamTailTargetText=nextTarget;
  if(!nextTarget){
   _streamTailDisplayText='';
   _renderStructuredStreamTail('');
   return;
  }
  _streamTailDisplayText=nextTarget;
  _renderStructuredStreamTail(_streamTailDisplayText);
}

function _applyMarkdownIncrementalStream(payload){
  if(!_streamStarted) _initStreamBubble();
  _streamProtocol='markdown_incremental';
  _streamText=String((payload&&payload.full_text)||'');
  _appendIncrementalMarkdownBlocks(payload&&payload.append);
  _renderStructuredStreamTail(
   String((payload&&payload.tail)||''),
   String((payload&&payload.tail_html)||'')
  );
}

function _renderCommittedStreamBubble(text){
  if(!_streamBubble) return;
  var committed=String(text||'').replace(/\r/g,'');
  var wasHidden=_streamBubble.style.display==='none';
  _streamLiveText='';
  _ensureStreamBubbleVisible();
  if(_streamLineEl){
   _streamLineEl.textContent=typeof stripMarkdownForStreamingText==='function'
    ? stripMarkdownForStreamingText(committed)
    : committed;
   _streamLineEl.style.display=committed ? 'block' : 'none';
  }
  if(wasHidden || _streamAutoFollow){
   _followStreamToBottom({threshold:220});
  }
}

function _renderStreamSnapshot(text){
  var snapshot=String(text||'').replace(/\r/g,'');
  _streamLiveText=snapshot;
  if(_streamLineEl){
   if(_streamLiveText){
    _ensureStreamBubbleVisible();
    _streamLineEl.style.display='block';
    _streamLineEl.textContent=typeof stripMarkdownForStreamingText==='function'
     ? stripMarkdownForStreamingText(_streamLiveText)
     : _streamLiveText;
    _followStreamToBottom({threshold:220});
   }else{
    _streamLineEl.textContent='';
    _streamLineEl.style.display='none';
   }
  }
}

function _progressiveRender(){
  _renderTimer=0;
  if(!_streamBubble) return;
  _renderStreamSnapshot(_streamText);
  _streamTokenCount++;
  if(_streamAutoFollow){
   if(!_scrollRAF){
    _scrollRAF=requestAnimationFrame(function(){
     _followStreamToBottom({threshold:220});
     _scrollRAF=0;
    });
   }
  }
}

function _appendStreamToken(token){
  if(!_streamStarted) _initStreamBubble();
  if(!_streamProtocol) _streamProtocol='text';
  _streamText+=String(token||'');
  _scheduleProgressiveRender(36);
 }

function _resetActiveStreamRender(){
  _detachStreamScrollFollow();
  if(_renderTimer){
   clearTimeout(_renderTimer);
   _renderTimer=0;
  }
  _clearStructuredTailTimer();
  if(_scrollRAF){
   cancelAnimationFrame(_scrollRAF);
   _scrollRAF=0;
  }
  _removeTrailingStreamParts(0);
  _streamBubble=null;
  _streamBlocksEl=null;
  _streamLineEl=null;
  _streamText='';
  _streamProtocol='';
  _streamLiveText='';
  _streamTokenCount=0;
  _streamStarted=false;
  _suppressTypingCursor=false;
  _thinkingContent='';
  if(pendingState.contentArea){
   pendingState.contentArea.innerHTML='';
   pendingState.contentArea.style.display='none';
  }
 }

function _finalizeStream(fullText){
  if(!_streamBubble) return;
  _detachStreamScrollFollow();
  if(_renderTimer){
   clearTimeout(_renderTimer);
   _renderTimer=0;
  }
  _clearStructuredTailTimer();
  var finalText=String(fullText||'');
  var finalRenderText=String(finalText||_streamText||'');
  _ensureStreamBubbleVisible();
  if(_streamProtocol!=='markdown_incremental' && _streamLineEl){
   _streamLineEl.innerHTML='';
   _streamLineEl.textContent=typeof stripMarkdownForStreamingText==='function'
    ? stripMarkdownForStreamingText(finalRenderText)
    : finalRenderText;
   _streamLineEl.style.display=finalRenderText ? 'block' : 'none';
  }
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
  _syncRunPanelHeader();
  _followStreamToBottom({threshold:220});
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
    // 只保留最近 200 条
    var keys=Object.keys(stepsMap);
    if(keys.length>200){keys.sort();keys.slice(0,keys.length-200).forEach(function(k){delete stepsMap[k];});}
    localStorage.setItem('nova_steps_map',JSON.stringify(stepsMap));
    pendingState.root.setAttribute('data-steps-key',tsKey);
   }
   pendingState.persisted=true;
  }
 }

function _renderReplyViaStream(text){
  var finalText=String(text||_streamText||'').trim();
  if(!finalText) finalText=t('chat.error.retry');
  if(!_streamStarted){
   _initStreamBubble();
  }
  _streamText=finalText;
  _finalizeStream(finalText);
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
       if(parsed&&parsed.format==='markdown_incremental'){
        _applyMarkdownIncrementalStream(parsed);
       }else{
        _appendStreamToken(parsed.token||'');
       }
       }else if(currentEvent==='stream_reset'){
        _resetActiveStreamRender();
        _tombstoneAbandonedStreamAttempt();
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

 var finalText=_chooseFinalStreamText(replyText, _streamText)||'';
if(_streamStarted && finalText){
  _finalizeStream(finalText);
  if(!(pendingState.steps&&pendingState.steps.length)) _setRunPanelEmptyState('quiet');
 }else if(finalText){
   _renderReplyViaStream(finalText);
   if(!(pendingState.steps&&pendingState.steps.length)) _setRunPanelEmptyState('quiet');
  }else{
   _setRunPanelEmptyState('quiet');
   finalizePendingAssistantMessage(pendingState, t('chat.error.retry'));
  }
  if(repairData && repairData.show){ showRepairBar(repairData); }
  _completeTaskProgress();
  AwarenessManager.startPolling();
 }catch(e){
  if(e.name==='AbortError'){
   _setRunPanelEmptyState('stopped');
   // 用户点了停止，显示已有的部分回复或提示
   var abortText=_chooseFinalStreamText(replyText, _streamText)||_streamText||'';
   if(_streamStarted&&abortText){
    _finalizeStream(abortText);
   }else if(abortText){
    _renderReplyViaStream(abortText);
   }else{
    finalizePendingAssistantMessage(pendingState, t('chat.stopped')||'已停止');
   }
  }else{
   _setRunPanelEmptyState('error');
   finalizePendingAssistantMessage(pendingState, t('chat.error.noconnect'));
  }
 }
 _stopRunElapsedClock();
 _syncRunPanelHeader();
 _abortController=null;
 _exitStopMode();
 _stickChatToBottom();
}
