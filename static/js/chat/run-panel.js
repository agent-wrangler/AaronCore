// Run panel layout, preferences, and shared console helpers.
// Extracted from chat/stream.js so transport logic stays focused on SSE flow.

var _runPanelStoreKey='nova_run_panel_open';
var _runPanelWidthKey='nova_run_panel_width';
var _runPanelConsoleCounterKey='nova_run_panel_console_counter';
var _runPanelUserOpen=true;
var _runPanelTabVisible=true;
var _runPanelBusy=false;
var _runPanelWidth=null;
var _runPanelResizeBound=false;
var _pendingModelSwitchNote=null;

var _runPanelCopy={
 show:'Show Run Panel',
 hide:'Hide Run Panel',
 kicker:'[RUN #000 | READY]',
 idle:'STATUS:    [IDLE] READY (0/0)',
 taskIdle:'ELAPSED:   00:00',
 actionIdle:'No active step',
 progress:'Progress',
 action:'Current Action',
 empty:'AGENT STANDBY \u00b7 Awaiting current run...'
};

var _runPanelEmptyCopy={
 idle:'AGENT STANDBY \u00b7 Awaiting current run...',
 open:'RUNTIME CHANNEL OPEN \u00b7 Awaiting agent events...',
 quiet:'RUNTIME CHANNEL OPEN \u00b7 No events emitted.',
 error:'RUNTIME CHANNEL ERROR \u00b7 Agent unavailable.',
 stopped:'RUNTIME CHANNEL CLOSED \u00b7 Run interrupted.'
};

function _normalizeRunPanelDom(){
 var host=document.getElementById('runPanel');
 if(!host) return;
 host.innerHTML=''
  +'<div class="run-panel-header">'
  +'<div class="run-panel-header-main">'
  +'<div class="run-panel-kicker-row">'
  +'<div class="run-panel-kicker-top">'
  +'<div class="run-panel-kicker" id="runPanelKicker">'+_runPanelCopy.kicker+'</div>'
  +'<button class="run-panel-close" id="runPanelCloseBtn" type="button" onclick="toggleRunPanel(false)" title="'+_runPanelCopy.hide+'" aria-label="'+_runPanelCopy.hide+'">'
  +'<svg viewBox="0 0 24 24" fill="none" width="12" height="12" aria-hidden="true">'
  +'<path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>'
  +'</svg>'
  +'</button>'
  +'</div>'
  +'<div class="run-panel-status-pill state-idle" id="runPanelStatus">'+_runPanelCopy.idle+'</div>'
  +'</div>'
  +'<div class="run-panel-task" id="runPanelTask">'+_runPanelCopy.taskIdle+'</div>'
  +'<div class="run-panel-meta" id="runPanelMeta">TOKENS:    ~0 / ~0 (in/out)</div>'
  +'<div class="run-panel-outputs" id="runPanelOutputs">TOOLS:     0 CALLS | 0 ERRORS | 0 FILES</div>'
  +'</div>'
  +'</div>'
  +'<div class="run-panel-summary" aria-hidden="true">'
  +'<div class="run-panel-summary-item">'
  +'<div class="run-panel-summary-label">'+_runPanelCopy.progress+'</div>'
  +'<div class="run-panel-summary-value" id="runPanelProgress">0 / 0</div>'
  +'</div>'
  +'<div class="run-panel-summary-item">'
  +'<div class="run-panel-summary-label">'+_runPanelCopy.action+'</div>'
  +'<div class="run-panel-summary-value run-panel-summary-text" id="runPanelAction">'+_runPanelCopy.actionIdle+'</div>'
  +'</div>'
  +'</div>'
  +'<div class="run-panel-stream" id="runPanelStream">'
  +'<div class="run-panel-empty" id="runPanelEmpty">'+_runPanelCopy.empty+'</div>'
  +'</div>';
}

function _mountRunPanelLayout(){
 var main=document.querySelector('.main');
 var shell=document.getElementById('chatShell');
 if(!main || !shell) return;
 var content=main.querySelector('.content');
 var host=document.getElementById('runPanel');
 var resizer=document.getElementById('runPanelResizer');
 var input=document.querySelector('.main > .input');
 var stageWrap=document.getElementById('mainStage');
 if(!stageWrap){
  stageWrap=document.createElement('div');
  stageWrap.id='mainStage';
  stageWrap.className='main-stage';
 }
 if(!resizer){
  resizer=document.createElement('div');
  resizer.id='runPanelResizer';
  resizer.className='run-panel-resizer';
  resizer.setAttribute('aria-hidden','true');
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
 if(resizer.parentNode!==main){
  main.appendChild(resizer);
 }
 if(host && host.parentNode!==main){
  main.appendChild(host);
 }else if(host && main.lastElementChild!==host){
  main.appendChild(host);
 }
 if(host && resizer && resizer.nextElementSibling!==host){
  main.insertBefore(resizer, host);
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
  resizer:document.getElementById('runPanelResizer'),
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

function _setRunPanelEmptyState(kind){
 var text=_runPanelEmptyCopy[kind]||_runPanelEmptyCopy.idle;
 _runPanelCopy.empty=text;
 var els=_getRunPanelEls();
 if(els && els.empty) els.empty.textContent=text;
}

function _formatRunPanelOutputs(fileCount, toolCount, errorCount){
 return String(fileCount||0)+' files \u00b7 '+String(toolCount||0)+' tools \u00b7 '+String(errorCount||0)+' errors';
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

function _readRunPanelWidth(){
 try{
  var raw=parseInt(localStorage.getItem(_runPanelWidthKey)||'', 10);
  return isFinite(raw) && raw>0 ? raw : null;
 }catch(e){
  return null;
 }
}

function _writeRunPanelWidth(width){
 try{
  localStorage.setItem(_runPanelWidthKey, String(Math.round(width||0)));
 }catch(e){}
}

function _getRunPanelWidthBounds(mainWidth){
 var total=Math.max(Number(mainWidth)||0, 0);
 var min=300;
 var chatMin=360;
 var max=Math.min(860, Math.max(420, total-chatMin));
 if(max<min) max=min;
  return { min:min, max:max };
}

function _applyRunPanelWidth(width){
 var els=_getRunPanelEls();
 if(!els || !els.main) return null;
 if(window.innerWidth<=760){
  els.main.style.removeProperty('--run-panel-width');
  return null;
 }
 var bounds=_getRunPanelWidthBounds(els.main.clientWidth||window.innerWidth);
 var next=Number(width);
 if(!isFinite(next) || next<=0){
  next=_runPanelWidth||_readRunPanelWidth()||390;
 }
 next=Math.max(bounds.min, Math.min(bounds.max, next));
 _runPanelWidth=next;
 els.main.style.setProperty('--run-panel-width', next+'px');
 return next;
}

function _initRunPanelResize(){
 var els=_getRunPanelEls();
 if(!els || !els.main || !els.resizer || !els.host || _runPanelResizeBound) return;
 var isResizing=false;
 var startX=0;
 var startWidth=0;
 function getClientX(e){
  return e && (typeof e.clientX==='number' ? e.clientX : (e.touches && e.touches[0] && e.touches[0].clientX));
 }
 function startResize(e){
  if(window.innerWidth<=760 || !_runPanelUserOpen || !_runPanelTabVisible) return;
  var clientX=getClientX(e);
  if(typeof clientX!=='number') return;
  isResizing=true;
  startX=clientX;
  startWidth=_applyRunPanelWidth()||els.host.getBoundingClientRect().width;
  document.body.classList.add('is-resizing-run-panel');
  document.body.style.userSelect='none';
  document.addEventListener('mousemove', onResize);
  document.addEventListener('mouseup', stopResize);
  document.addEventListener('touchmove', onResize, {passive:false});
  document.addEventListener('touchend', stopResize);
  e.preventDefault();
 }
 function onResize(e){
  if(!isResizing) return;
  var clientX=getClientX(e);
  if(typeof clientX!=='number') return;
  var next=startWidth+(startX-clientX);
  var applied=_applyRunPanelWidth(next);
  if(applied) _runPanelWidth=applied;
  if(e.cancelable) e.preventDefault();
 }
 function stopResize(){
  if(!isResizing) return;
  isResizing=false;
  document.body.classList.remove('is-resizing-run-panel');
  document.body.style.userSelect='';
  document.removeEventListener('mousemove', onResize);
  document.removeEventListener('mouseup', stopResize);
  document.removeEventListener('touchmove', onResize);
  document.removeEventListener('touchend', stopResize);
  if(_runPanelWidth) _writeRunPanelWidth(_runPanelWidth);
 }
 els.resizer.addEventListener('mousedown', startResize);
 els.resizer.addEventListener('touchstart', startResize, {passive:false});
 window.addEventListener('resize', function(){
  _applyRunPanelWidth(_runPanelWidth||_readRunPanelWidth()||390);
 });
 _runPanelResizeBound=true;
}

function _setRunPanelBusyState(isBusy){
 _runPanelBusy=!!isBusy;
 var els=_getRunPanelEls();
 if(!els) return;
 if(els.btn) els.btn.classList.toggle('is-busy', _runPanelBusy);
 if(els.inlineToggle) els.inlineToggle.classList.toggle('is-busy', _runPanelBusy);
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
  els.btn.classList.toggle('is-busy', _runPanelBusy);
  els.btn.setAttribute('aria-pressed', open ? 'true' : 'false');
  els.btn.title=open ? _runPanelCopy.hide : _runPanelCopy.show;
 }
 if(els.inlineToggle){
  var showInline=_runPanelTabVisible && !open;
  els.inlineToggle.classList.toggle('is-visible', showInline);
  els.inlineToggle.classList.toggle('is-busy', _runPanelBusy);
  els.inlineToggle.setAttribute('aria-hidden', showInline ? 'false' : 'true');
  els.inlineToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  els.inlineToggle.title=_runPanelCopy.show;
 }
 if(els.closeBtn) els.closeBtn.title=_runPanelCopy.hide;
 _applyRunPanelWidth(_runPanelWidth||_readRunPanelWidth()||390);
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

function _queueModelSwitchNote(payload){
 if(!payload) return;
 var nextName=String(payload.model_name||payload.model||'').trim();
 if(!nextName) return;
 var labelEl=document.getElementById('modelName');
 var previousName=String(payload.previous_model_name||'').trim();
 if(!previousName && labelEl){
  previousName=String(labelEl.textContent||'').trim();
 }
 if(!previousName){
  previousName=String(window._novaCurrentModel||'').trim();
 }
 if(previousName===nextName){
  previousName=String(payload.previous_model||'').trim();
 }
 _pendingModelSwitchNote={
  from:previousName,
  to:nextName,
  toId:String(payload.model||'').trim()
 };
}

function _flushPendingModelSwitchNote(){
 if(!_pendingModelSwitchNote || typeof addChatEventNote!=='function') return;
 var note=_pendingModelSwitchNote;
 _pendingModelSwitchNote=null;
 var text=note.from && note.from!==note.to
  ? (note.from+' -> '+note.to)
  : (note.to||note.toId||'');
 if(!text) return;
 addChatEventNote('model-switch', 'MODEL SWITCH', text);
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

(function _initRunPanelUi(){
 _runPanelUserOpen=_readRunPanelPref();
 _normalizeRunPanelDom();
 _mountRunPanelLayout();
 _initRunPanelResize();
 var els=_getRunPanelEls();
 if(els){
  _ensureRunPanelMetaLine(els);
  if(els.kicker) els.kicker.textContent=_runPanelCopy.kicker;
  if(els.status) els.status.textContent=_runPanelCopy.idle;
  if(els.task) els.task.textContent=_runPanelCopy.taskIdle;
  if(els.meta) els.meta.textContent=_formatRunPanelTokenLine(0, 0);
  if(els.outputs) els.outputs.textContent=_formatRunPanelToolLine(0, 0, 0);
  if(els.progress) els.progress.textContent='0 / 0';
  if(els.action) els.action.textContent=_runPanelCopy.actionIdle;
  if(els.empty) els.empty.textContent=_runPanelCopy.empty;
 }
 _applyRunPanelUiState();
})();
