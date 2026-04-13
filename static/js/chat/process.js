// Process tracker helpers and shared chat detail utilities
// Source: chat.js lines 1-159

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

function _isEnglishProcessUi(){
 try{
  if(typeof getLang==='function'){
   return String(getLang()||'zh').toLowerCase()==='en';
  }
 }catch(e){}
 try{
  if(typeof _lang!=='undefined'){
   return String(_lang||'zh').toLowerCase()==='en';
  }
 }catch(e){}
 return false;
}

function _processUiText(zhText, enText){
 return _isEnglishProcessUi() ? String(enText||zhText||'') : String(zhText||enText||'');
}

function _processMetaPrefix(kind){
 var map={
  decision:['判断基线：','Decision: '],
  handoff:['接手方式：','Handoff: '],
  goal:['目标：','Goal: '],
  expected_output:['预期产出：','Expected Output: '],
  next_need:['下一步可能关心：','Next Need: '],
  expected:['预期：','Expected: ']
 };
 var pair=map[String(kind||'').trim()]||['',''];
 return _processUiText(pair[0], pair[1]);
}

function _formatProcessDisplayLabel(label){
 var text=String(label||'').trim();
 if(!text) return text;
 var aliases={
  thinking:'Thinking',
  process:'Process',
  tool:'Tool',
  waiting:'Waiting',
  memory_load:'Memory Load',
  load_memory:'Memory Load',
  persona_switch:'Persona Switch',
  model_switch:'Model Switch',
  organize_results:'Organize Results',
  compose_reply:'Compose Reply',
  recall_memory:'Recall Memory',
  web_search:'Web Search',
  parallel_tools:'Parallel Tools',
  'parallel tools':'Parallel Tools',
  'PARALLEL CALL':'Parallel Call',
  'PARALLEL RUN':'Parallel Run',
  'PARALLEL DONE':'Parallel Done',
  'PARALLEL RESULT':'Parallel Result',
  '模型思考':'Thinking',
  'Thinking':'Thinking',
  '调用技能':'Tool Call',
  '技能完成':'Tool Complete',
  '技能失败':'Tool Failed',
  '联网搜索':'Web Search',
  '搜索完成':'Search Complete',
  '搜索失败':'Search Failed',
  '检索记忆':'Recall Memory',
  '检索失败':'Recall Failed',
  '记忆就绪':'Memory Ready',
  '等待':'Waiting',
  '等待接手':'Needs Handoff',
  '参数待补':'Needs Args',
  '技能中断':'Interrupted',
  '备用路径失败':'Fallback Failed',
  '重试失败':'Retry Failed'
 };
 if(aliases[text]) return aliases[text];
 text=text.replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();
 if(!text) return '';
 return text.split(' ').map(function(word){
  if(!word) return '';
  if(/^[A-Z0-9]{2,}$/.test(word)) return word;
  return word.charAt(0).toUpperCase()+word.slice(1).toLowerCase();
 }).join(' ');
}

function _translateProcessDetailText(detail){
 var text=String(detail||'').trim();
 if(!text) return '';
 if(!_isEnglishProcessUi()) return text;
 text=text.replace(/我先理解你这句「(.+?)」，判断是直接回答还是先调用工具。?/g, 'I\'ll first understand "$1" and decide whether to answer directly or call a tool.');
 text=text.replace(/我先接住上一步结果，判断是继续调用工具还是整理成最终回答。?/g, 'I\'ll take the previous result and decide whether to keep using tools or shape the final reply.');
 text=text.replace(/这是实时信息，直接凭记忆不稳。?我先核实「(.+?)」的最新天气，再根据结果给你一个简洁结论。?/g, 'This is live information, so memory alone is not reliable. I\'ll verify the latest weather for "$1" first, then give a concise conclusion.');
 text=text.replace(/我先把这一步需要核实的信息查清楚，再继续回答。当前先调用「(.+?)」确认「(.+?)」。?/g, 'I\'ll verify the information needed for this step before continuing. First I\'m calling "$1" to confirm "$2".');
 text=text.replace(/我先调用「(.+?)」把关键事实拿到，再继续整理最终答复。?/g, 'I\'ll call "$1" first to gather the key facts, then I\'ll shape the final reply.');
 text=text.replace(/这一轮更像是直接回应，不需要再调用工具。?我会先结合当前对话上下文直接给出答复。?/g, 'This looks like a direct response, so no extra tools are needed. I\'ll answer from the current conversation context.');
 text=text.replace(/这一轮更像是直接回应，不需要再调用工具。?我会直接围绕你这句话给出答复。?/g, 'This looks like a direct response, so no extra tools are needed. I\'ll answer directly from your latest message.');
 text=text.replace(/上一步\s*(.+?)\s*没走通，切到这条路径/g, 'Previous step $1 did not work, switching path');
 text=text.replace(/这一批同时起跑\s*(\d+)\s*个工具[:：]?\s*/g, 'Launching $1 tools in parallel: ');
 text=text.replace(/(\d+)\s*个工具同时在跑，已收回\s*(\d+\/\d+)/g, '$1 tools running in parallel, collected $2');
 text=text.replace(/(\d+)\s*个工具已经收口/g, '$1 tools settled');
 text=text.replace(/成功\s*(\d+)\s*个/g, '$1 succeeded');
 text=text.replace(/失败\s*(\d+)\s*个/g, '$1 failed');
 text=text.replace(/还在跑\s*(\d+)\s*个/g, '$1 still running');
 text=text.replace(/都已完成/g, 'All completed');
 text=text.replace(/这一批[:：]\s*/g, 'Batch: ');
 text=text.replace(/根据上一轮结果继续重试/g, 'Retrying from the previous result');
 text=text.replace(/沿着上一条结果继续推进/g, 'Continuing from the previous result');
 text=text.replace(/切换路径后完成/g, 'Completed after switching path');
 text=text.replace(/重试后完成/g, 'Completed after retry');
 text=text.replace(/继续推进完成/g, 'Continued to completion');
 text=text.replace(/需要用户接手/g, 'Needs user handoff');
 text=text.replace(/参数还不完整/g, 'Arguments still incomplete');
 text=text.replace(/这一轮中断了，没拿到完整结果/g, 'Interrupted before a complete result arrived');
 text=text.replace(/执行时抛异常了/g, 'Execution raised an exception');
 text=text.replace(/执行链中断了/g, 'Execution chain interrupted');
 text=text.replace(/切换后的这条路径也没走通/g, 'Fallback path also failed');
 text=text.replace(/这次重试还是没走通/g, 'Retry still failed');
 text=text.replace(/正在等待工具执行结果/g, 'Waiting for tool result');
 text=text.replace(/正在等待模型继续输出/g, 'Waiting for model output');
 text=text.replace(/正在继续分析下一步动作/g, 'Analyzing the next action');
 text=text.replace(/判断基线[:：]\s*/g, 'Decision: ');
 text=text.replace(/接手方式[:：]\s*/g, 'Handoff: ');
 text=text.replace(/目标[:：]\s*/g, 'Goal: ');
 text=text.replace(/预期产出[:：]\s*/g, 'Expected Output: ');
 text=text.replace(/下一步可能关心[:：]\s*/g, 'Next Need: ');
 text=text.replace(/预期[:：]\s*/g, 'Expected: ');
 text=text.replace(/判断是直接回答还是先调用工具/g, 'Decide whether to answer directly or call a tool first');
 text=text.replace(/最新天气和一个可直接用的简洁结论/g, 'The latest weather plus a concise answer ready to use');
 text=text.replace(/围绕「(.+?)」拿到可靠结果/g, 'Get a reliable result for "$1"');
 text=text.replace(/拿到\s+(.+?)\s+的关键结果/g, 'Get the key result from $1');
 text=text.replace(/拿到这一步需要的关键信息/g, 'Get the key information needed for this step');
 text=text.replace(/今天状态、出门安排或要不要带伞/g, 'Today\'s conditions, whether to head out, and whether an umbrella is needed');
 text=text.replace(/最新结论、怎么做，或要不要继续展开/g, 'The latest conclusion, what to do next, and whether to go deeper');
 text=text.replace(/把上下文接回当前问题后的明确结论/g, 'A clear conclusion once the context is reattached to the current question');
 text=text.replace(/今天最值得先关注的实时信息/g, 'The live information most worth checking first today');
 text=text.replace(/一个能直接接住当前话题的结论/g, 'A conclusion that can directly carry the current topic');
 text=text.replace(/先交给「(.+?)」把这一步需要的依据拿到/g, 'Hand this step to "$1" first so it can gather the needed evidence');
 text=text.replace(/先拿到这一步需要的关键依据/g, 'Gather the key evidence needed for this step first');
 text=text.replace(/\s+/g,' ').trim();
 return text;
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

function _normalizePositiveStepCount(value){
 var parsed=parseInt(value, 10);
 return isFinite(parsed) && parsed>0 ? parsed : 0;
}

function _normalizeStepNameList(value){
 var source=Array.isArray(value) ? value : [];
 var seen={};
 var list=[];
 for(var i=0;i<source.length;i++){
  var text=String(source[i]||'').trim();
  var key=text.toLowerCase();
  if(!text || seen[key]) continue;
  seen[key]=true;
  list.push(text);
 }
 return list;
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
 if(text==='PARALLEL CALL' || text==='PARALLEL RUN' || text==='PARALLEL DONE' || text==='PARALLEL RESULT') return 'parallel_tools';
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
