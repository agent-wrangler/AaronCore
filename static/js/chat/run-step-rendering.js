// Run step normalization and rendering helpers shared by chat stream flow.
// Extracted from chat/stream.js so the send loop can focus on transport/state.

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
 return String(parts.slice(1).join(' \u00b7 ')).trim();
}

function _collapseProcessDetail(detail, phase, status){
 var text=String(detail||'').replace(/\s+/g,' ').trim();
 if(!text) return '';
 if(String(status||'')==='error') return text;
 var limit=(phase==='thinking') ? 110 : 130;
 return text.length>limit ? (text.slice(0, Math.max(0, limit-3))+'...') : text;
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
 var emittedSummary=_stepMetaText(fallbackSummary);
 var emittedFull=_stepMetaText(fallbackFull);
 var lead=emittedFull || emittedSummary || _stepMetaText((card&&card.decision_note)||'') || _stepMetaText((card&&card.handoff_note)||'');
 var decisionNote=_stepMetaText(card&&card.decision_note);
 var handoffNote=_stepMetaText(card&&card.handoff_note);
 var goal=_stepMetaText(card&&card.goal);
 var expected=_stepMetaText(card&&card.expected_output);
 var nextNeed=_stepMetaText(card&&card.next_user_need);
 _appendUniqueStepMeta(summaryParts, lead, '');
 _appendUniqueStepMeta(fullParts, lead, '');
 if(decisionNote && !_stepMetaContains(lead, decisionNote)){
  _appendUniqueStepMeta(fullParts, decisionNote, '\u5224\u65ad\u57fa\u7ebf\uff1a');
 }
 if(handoffNote && !_stepMetaContains(lead, handoffNote)){
  _appendUniqueStepMeta(fullParts, handoffNote, '\u63a5\u624b\u65b9\u5f0f\uff1a');
 }
 if(goal){
  _appendUniqueStepMeta(summaryParts, goal, '\u76ee\u6807\uff1a');
  _appendUniqueStepMeta(fullParts, goal, '\u76ee\u6807\uff1a');
 }
 if(expected){
  _appendUniqueStepMeta(fullParts, expected, '\u9884\u671f\u4ea7\u51fa\uff1a');
 }
 if(nextNeed){
  _appendUniqueStepMeta(fullParts, nextNeed, '\u4e0b\u4e00\u6b65\u53ef\u80fd\u5173\u5fc3\uff1a');
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
  _appendUniqueStepMeta(fullParts, goal, '\u76ee\u6807\uff1a');
 }
 if(parallelSize<=1 && String(state||'')==='running' && expected){
  _appendUniqueStepMeta(fullParts, expected, '\u9884\u671f\uff1a');
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
  displayLabel=isParallelTool ? (rawLabel||'parallel tools') : (toolKey||toolFallback||rawLabel||'tool');
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

function _canMergeStep(existing, meta){
 if(!existing || !meta) return false;
 if(existing.stepKey && meta.stepKey && existing.stepKey===meta.stepKey) return true;
 if(existing.phase==='thinking' && meta.phase==='thinking'){
  if(existing.stepKey && meta.stepKey && existing.stepKey!==meta.stepKey) return false;
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
