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
