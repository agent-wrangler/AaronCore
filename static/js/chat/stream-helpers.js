// Shared helpers for chat/stream.js.

function _truncateRunText(value, limit){
 var textValue=String(value||'').replace(/\s+/g,' ').trim();
 if(!textValue) return '';
 if(textValue.length<=limit) return textValue;
 return textValue.slice(0, Math.max(0, limit-3))+'...';
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

function _collectStepToolNames(step){
 var names=(typeof _normalizeStepNameList==='function') ? _normalizeStepNameList(step&&step.parallelTools) : [];
 if(names.length) return names;
 var primary=String((step&&(step.toolName||step.toolKey))||'').trim();
 return primary ? [primary] : [];
}

function _stepLikeField(stepLike, snakeKey, camelKey){
 if(!stepLike) return '';
 var camelValue=stepLike[camelKey];
 if(camelValue!==undefined && camelValue!==null) return camelValue;
 var snakeValue=stepLike[snakeKey];
 return snakeValue!==undefined && snakeValue!==null ? snakeValue : '';
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

function _appendIncrementalMarkdownBlocks(target, blocks, ensureVisible){
 if(!target || !Array.isArray(blocks) || !blocks.length) return;
 if(typeof ensureVisible==='function') ensureVisible();
 for(var i=0;i<blocks.length;i++){
  var block=blocks[i]||{};
  if(String(block.kind||'')!=='markdown_block') continue;
  _appendRenderedHtml(target, block.html||'');
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
  if(/[,\.\!\?\;\:\u3001\u3002\uFF01\uFF1F\uFF1B\uFF1A]/.test(last)) return joined;
 }
 return chars.slice(0, cut).join('');
}

function _streamIsNearBottom(chat, threshold){
 if(!chat) return true;
 return chat.scrollHeight - chat.scrollTop - chat.clientHeight < (typeof threshold==='number' ? threshold : 220);
}

function _streamHideTypingCursor(streamBubble){
 if(!streamBubble) return;
 var cursor=streamBubble.querySelector('.typing-cursor');
 if(cursor && cursor.parentNode) cursor.parentNode.removeChild(cursor);
}

function _streamEnsureBubbleVisible(streamBubble){
 if(!streamBubble) return;
 streamBubble.style.display='';
 var meta=streamBubble.parentNode ? streamBubble.parentNode.querySelector('.msg-meta') : null;
 if(meta) meta.style.display='';
}

function _streamRemoveTrailingParts(streamParts, keepCount){
 var parts=Array.isArray(streamParts) ? streamParts : [];
 while(parts.length>keepCount){
  var stalePart=parts.pop();
  if(stalePart && stalePart.root && stalePart.root.parentNode){
   stalePart.root.parentNode.removeChild(stalePart.root);
  }
 }
}
