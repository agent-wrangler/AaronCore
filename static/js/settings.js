var settingsPanelState={
 stats:null,
 config:null,
 notice:'',
 error:'',
 selfRepairStatus:null,
 selfRepairReports:[],
 activeRepairId:'',
 repairActionBusy:'',
 showAdvancedLearning:false,
 l7Stats:null
};

function defaultAutolearnConfig(){
 return {
  enabled:true,
  allow_web_search:true,
  allow_knowledge_write:true,
  allow_feedback_relearn:true,
  allow_skill_generation:false,
  allow_self_repair_planning:false,
  allow_self_repair_test_run:false,
  allow_self_repair_auto_apply:false,
  self_repair_apply_mode:'confirm',
  self_repair_test_timeout_sec:30,
  mode:'shadow',
  min_query_length:4,
  search_timeout_sec:5,
  max_results:5,
  max_summary_length:360
 };
}

function mergeAutolearnConfig(config){
 var merged=defaultAutolearnConfig();
 if(config && typeof config==='object'){
  Object.keys(merged).forEach(function(key){
   if(config[key]!==undefined) merged[key]=config[key];
  });
 }
 return merged;
}

function clampSettingNumber(value,min,max,fallback){
 var num=parseInt(value,10);
 if(isNaN(num)) return fallback;
 return Math.max(min, Math.min(max, num));
}

function getSettingsTheme(isLight){
 return isLight?{
  cardBg:'var(--bg-card)',
  cardBgActive:'linear-gradient(135deg,#f7f4ef,#f2ede6)',
  border:'rgba(148,163,184,0.22)',
  borderStrong:'rgba(120,120,130,0.24)',
  text:'#1c1c1e',
  sub:'#64748b',
  mutedBg:'rgba(226,232,240,0.9)',
  mutedText:'#334155',
  actionPrimary:'linear-gradient(135deg,#6f685e,#8a8174)',
  actionPrimaryText:'#fff',
  actionSecondary:'rgba(226,232,240,0.9)',
  actionSecondaryText:'#334155',
  stateOnBg:'rgba(100,100,110,0.12)',
  stateOnText:'#374151',
  stateOffBg:'rgba(148,163,184,0.12)',
  stateOffText:'#475569',
  accentBg:'rgba(100,100,110,0.12)',
  accentText:'#374151',
  okBg:'rgba(121,140,109,0.14)',
  okText:'#68795f',
  warnBg:'rgba(177,145,89,0.15)',
  warnText:'#8f6d3f',
  dangerBg:'rgba(171,113,99,0.14)',
  dangerText:'#8b5e55',
  mutedPillBg:'rgba(125,118,108,0.12)',
  mutedPillText:'#6a6258',
  pathBg:'rgba(125,118,108,0.1)',
  pathText:'#5f584f',
  headerBg:'rgba(122,116,107,0.06)',
  currentRowBg:'rgba(122,116,107,0.08)',
  currentRowBorder:'rgba(122,116,107,0.22)',
  softRowBg:'#f7f4ef',
  softDashedBg:'rgba(122,116,107,0.04)',
  softDashedBorder:'rgba(122,116,107,0.18)',
  successBg:'rgba(122,140,109,0.12)',
  successText:'#6f7e63',
  inactiveTagBg:'rgba(148,163,184,0.1)',
  inactiveTagText:'#64748b',
  actionBorder:'rgba(122,116,107,0.24)',
  actionText:'#6a6258',
  dialogBg:'#fbfaf7',
  dialogInputBg:'#f5f1ea',
  dialogOverlay:'rgba(0,0,0,0.5)',
  spinner:'#7c3aed',
  toggleOn:'#7a876d',
  toggleOff:'#d8d0c7',
  currentCheck:'#6f7e63',
  dangerLine:'#b91c1c',
  dangerSoftBorder:'rgba(171,113,99,0.22)',
  dangerSoftText:'#9a665d'
 }:{
  cardBg:'rgba(46,43,38,0.95)',
  cardBgActive:'linear-gradient(135deg,rgba(58,54,48,0.94),rgba(47,44,39,0.98))',
  border:'rgba(228,220,204,0.07)',
  borderStrong:'rgba(228,220,204,0.1)',
  text:'#efe8db',
  sub:'#978f82',
  mutedBg:'rgba(255,255,255,0.04)',
  mutedText:'#e4dccf',
  actionPrimary:'linear-gradient(135deg,#9e907c,#7e725f)',
  actionPrimaryText:'#fffaf2',
  actionSecondary:'rgba(255,255,255,0.04)',
  actionSecondaryText:'#e4dccf',
  stateOnBg:'rgba(123,133,103,0.12)',
  stateOnText:'#bcc5af',
  stateOffBg:'rgba(255,255,255,0.06)',
  stateOffText:'#c7beaf',
  accentBg:'rgba(167,148,108,0.12)',
  accentText:'#d8ccb4',
  okBg:'rgba(123,133,103,0.14)',
  okText:'#bcc5af',
  warnBg:'rgba(171,148,103,0.14)',
  warnText:'#d5c091',
  dangerBg:'rgba(171,113,99,0.16)',
  dangerText:'#d7aca4',
  mutedPillBg:'rgba(255,255,255,0.06)',
  mutedPillText:'#c7beaf',
  pathBg:'rgba(255,255,255,0.04)',
  pathText:'#d1c8ba',
  headerBg:'rgba(255,255,255,0.03)',
  currentRowBg:'rgba(167,148,108,0.08)',
  currentRowBorder:'rgba(167,148,108,0.22)',
  softRowBg:'rgba(255,255,255,0.025)',
  softDashedBg:'rgba(255,255,255,0.02)',
  softDashedBorder:'rgba(228,220,204,0.08)',
  successBg:'rgba(123,133,103,0.12)',
  successText:'#bcc5af',
  inactiveTagBg:'rgba(255,255,255,0.05)',
  inactiveTagText:'#a49c8e',
  actionBorder:'rgba(167,148,108,0.22)',
  actionText:'#d8ccb4',
  dialogBg:'rgba(38,36,32,0.98)',
  dialogInputBg:'rgba(255,255,255,0.04)',
  dialogOverlay:'rgba(15,14,12,0.58)',
  spinner:'#b49e85',
  toggleOn:'#8d9979',
  toggleOff:'#5a554c',
  currentCheck:'#bcc5af',
  dangerLine:'#d7aca4',
  dangerSoftBorder:'rgba(171,113,99,0.22)',
  dangerSoftText:'#d7aca4'
 };
}

function renderSettingsToggleCard(title, desc, key, value, isLight){
 var cardBg=isLight?'var(--bg-card)':'rgba(36,36,40,0.95)';
 var borderColor=value
  ? (isLight?'rgba(120,120,130,0.24)':'rgba(150,150,160,0.28)')
  : (isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)');
 var titleColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var stateBg=value
  ? (isLight?'rgba(100,100,110,0.12)':'rgba(120,120,130,0.18)')
  : (isLight?'rgba(148,163,184,0.12)':'rgba(148,163,184,0.12)');
 var stateColor=value?(isLight?'#374151':'#c7d2fe'):(isLight?'#475569':'#cbd5e1');
 var actionBg=value
  ? (isLight?'linear-gradient(135deg,#6f685e,#8a8174)':'linear-gradient(135deg,#6b7280,#8b5cf6)')
  : (isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)');
 var actionColor=value?'#fff':(isLight?'#334155':'#e2e8f0');
 return '<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:12px;min-width:0;box-shadow:'+(isLight?'0 8px 24px rgba(34,29,24,0.05)':'0 10px 28px rgba(0,0,0,0.14)')+';">'
  +'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">'
  +'<div style="min-width:0;"><div style="font-size:15px;font-weight:700;color:'+titleColor+';margin-bottom:4px;">'+escapeHtml(title)+'</div><div style="font-size:12px;line-height:1.7;color:'+subColor+';">'+escapeHtml(desc)+'</div></div>'
  +'<span style="flex-shrink:0;padding:6px 10px;border-radius:999px;background:'+stateBg+';color:'+stateColor+';font-size:12px;font-weight:700;">'+(value?'已开启':'已关闭')+'</span>'
  +'</div>'
  +'<button type="button" data-settings-action="toggle" data-settings-key="'+escapeHtml(key)+'" style="margin-top:auto;padding:10px 12px;border:none;border-radius:12px;background:'+actionBg+';color:'+actionColor+';font-size:13px;font-weight:700;cursor:pointer;box-shadow:'+(value?'0 8px 20px rgba(120,120,130,0.18)':'none')+';">'+(value?'保持开启':'现在开启')+'</button>'
  +'</div>';
}

function autolearnPresets(){
 return {
  basic:{label:'基础',desc:'不联网学新知识，不整理修复提案。反馈记忆始终开启，AI Agent 会记住你说过的纠正。',patch:{enabled:true,allow_knowledge_write:true,allow_web_search:false,allow_self_repair_planning:false,allow_self_repair_test_run:false,allow_self_repair_auto_apply:false,self_repair_apply_mode:'confirm'}},
  advanced:{label:'进阶',desc:'会联网补学知识，会整理修复提案并先跑验证。真正改代码前先停下来给你看。',patch:{enabled:true,allow_knowledge_write:true,allow_web_search:true,allow_self_repair_planning:true,allow_self_repair_test_run:true,allow_self_repair_auto_apply:false,self_repair_apply_mode:'confirm'}},
  deep:{label:'深度',desc:'包含进阶的全部能力，低风险问题允许后台自动落地，中高风险改动仍然会停下来。',patch:{enabled:true,allow_knowledge_write:true,allow_web_search:true,allow_self_repair_planning:true,allow_self_repair_test_run:true,allow_self_repair_auto_apply:true,self_repair_apply_mode:'confirm'}}
 };
}

function currentAutolearnPreset(config){
 var presets=autolearnPresets();
 for(var key in presets){
  var p=presets[key];
  var match=true;
  for(var field in p.patch){
   if(config[field]!==p.patch[field]){ match=false; break; }
  }
  if(match) return {key:key,label:p.label,desc:p.desc};
 }
 return {key:'custom',label:'自定义组合',desc:'当前配置不完全等于基础、进阶、深度三档中的任意一档。'};
}

function renderAutolearnPresetCard(key, preset, currentKey, isLight){
 var active=key===currentKey;
 var cardBg=active
  ? (isLight?'linear-gradient(135deg,#f7f4ef,#f2ede6)':'linear-gradient(135deg,rgba(100,100,110,0.18),rgba(28,28,30,0.92))')
  : (isLight?'var(--bg-card)':'rgba(36,36,40,0.92)');
 var borderColor=active
  ? (isLight?'rgba(120,120,130,0.22)':'rgba(150,150,160,0.28)')
  : (isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)');
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var btnBg=active
  ? (isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)')
  : 'linear-gradient(135deg,#6f685e,#8a8174)';
 var btnColor=active?(isLight?'#334155':'#e2e8f0'):'#fff';
 return '<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:10px;box-shadow:'+(isLight?'0 8px 24px rgba(34,29,24,0.05)':'0 10px 28px rgba(0,0,0,0.14)')+';">'
  +'<div style="font-size:16px;font-weight:800;color:'+textColor+';">'+escapeHtml(preset.label)+'</div>'
  +'<div style="font-size:12px;line-height:1.7;color:'+subColor+';flex:1;">'+escapeHtml(preset.desc)+'</div>'
  +'<button type="button" data-settings-action="preset" data-settings-key="'+escapeHtml(key)+'" style="padding:10px 12px;border:none;border-radius:12px;background:'+btnBg+';color:'+btnColor+';font-size:13px;font-weight:700;cursor:pointer;">'+(active?'保持这一档':'切到这一档')+'</button>'
  +'</div>';
}

function selfRepairOutcome(status){
 var safe=status&&typeof status==='object'?status:{};
 var lastAction=String(safe.last_action||safe.last_outcome||'').trim();
 if(lastAction.indexOf('applied')===0||lastAction==='auto_applied')
  return {label:'自动修改',title:'自动修改',desc:'已经真的动手改了，并可能通过验证或触发回滚。'};
 if(lastAction==='proposal_ready'||lastAction==='preview_ready'||lastAction.indexOf('plan')>=0)
  return {label:'生成方案',title:'生成方案',desc:'已经整理出修复提案或改法预览。'};
 if(lastAction==='skill_generated'||lastAction==='new_skill')
  return {label:'解锁新技能',title:'解锁新技能',desc:'当前不是日常默认主链，通常保持关闭。'};
 return {label:'积累经验',title:'积累经验',desc:'已经记住这次反馈，但还没进入具体修法落地。'};
}

function toggleAutolearnAdvanced(){
 settingsPanelState.showAdvancedLearning=!settingsPanelState.showAdvancedLearning;
 renderSettingsPage(document.body.classList.contains('light'));
}

function formatSettingsTimestamp(value){
 var raw=String(value||'').trim();
 if(!raw) return '刚刚';
 return raw.replace('T',' ').replace(/\.\d+$/,'').slice(0,16);
}

function renderSettingsActionButton(label, action, key, isLight, emphasis, disabled){
 var primary=emphasis==='primary';
 var bg=disabled
  ? (isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)')
  : (primary?'linear-gradient(135deg,#6f685e,#8a8174)':(isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)'));
 var color=disabled?'#94a3b8':(primary?'#fff':(isLight?'#334155':'#e2e8f0'));
 return '<button type="button" data-settings-action="'+action+'"'+(key?' data-settings-key="'+escapeHtml(key)+'"':'')+' style="position:relative;z-index:1;padding:10px 12px;border:none;border-radius:12px;background:'+bg+';color:'+color+';font-size:13px;font-weight:700;cursor:'+(disabled?'default':'pointer')+';'+(disabled?'opacity:0.68;pointer-events:none;':'')+'">'+escapeHtml(label)+'</button>';
}

function renderSettingsMetaPill(label, tone, isLight){
 var palette={
  accent:isLight?['rgba(100,100,110,0.12)','#374151']:['rgba(120,120,130,0.18)','#c7d2fe'],
  ok:isLight?['rgba(121,140,109,0.14)','#68795f']:['rgba(16,185,129,0.18)','#86efac'],
  warn:isLight?['rgba(177,145,89,0.15)','#8f6d3f']:['rgba(245,158,11,0.16)','#fde68a'],
  danger:isLight?['rgba(171,113,99,0.14)','#8b5e55']:['rgba(239,68,68,0.18)','#fca5a5'],
  muted:isLight?['rgba(125,118,108,0.12)','#6a6258']:['rgba(148,163,184,0.14)','#cbd5e1']
 };
 var picked=palette[tone]||palette.muted;
 return '<span style="padding:6px 10px;border-radius:999px;background:'+picked[0]+';color:'+picked[1]+';font-size:12px;font-weight:700;">'+escapeHtml(label)+'</span>';
}

function selfRepairFlowSummary(config){
 var normalized=mergeAutolearnConfig(config||{});
 var planning=normalized.allow_self_repair_planning?'新的负反馈会继续整理成修复提案':'新的负反馈暂时不会继续生成修复提案';
 var lowRisk=normalized.allow_self_repair_auto_apply?'低风险补丁允许后台自动落地':'低风险补丁也会先停在提案阶段';
 var highRisk=normalized.self_repair_apply_mode==='suggest'?'中高风险改动会先给你看方案':'中高风险改动会停下来等你确认一次';
 return planning+'。'+lowRisk+'，'+highRisk+'。';
}

function selfRepairReportStatusMeta(report){
 var safe=report&&typeof report==='object'?report:{};
 var preview=safe.patch_preview&&typeof safe.patch_preview==='object'?safe.patch_preview:{};
 var apply=safe.apply_result&&typeof safe.apply_result==='object'?safe.apply_result:{};
 var status=String(safe.status||'').trim();
 var previewStatus=String(preview.status||'').trim();
 var applyStatus=String(apply.status||'').trim();
 if(applyStatus.indexOf('rolled_back')===0||status.indexOf('rolled_back')===0) return {label:'已自动回滚',tone:'warn'};
 if(applyStatus==='applied'||applyStatus==='applied_without_validation'||status==='applied'||status==='applied_without_validation') return {label:'已应用',tone:'ok'};
 if(previewStatus==='preview_failed'||status==='needs_attention') return {label:'需要处理',tone:'danger'};
 if(previewStatus==='preview_ready') return {label:(preview.confirmation_required===false?'可直接落地':'待你审核'),tone:(preview.confirmation_required===false?'ok':'accent')};
 if(status==='awaiting_confirmation') return {label:'待你确认',tone:'accent'};
 if(status==='proposal_ready') return {label:'提案已就绪',tone:'accent'};
 return {label:'已进入修复链路',tone:'muted'};
}

function selfRepairRiskMeta(report){
 var safe=report&&typeof report==='object'?report:{};
 var preview=safe.patch_preview&&typeof safe.patch_preview==='object'?safe.patch_preview:{};
 var level=String(preview.risk_level||safe.risk_level||'').trim();
 if(level==='low') return {label:'低风险',tone:'ok'};
 if(level==='medium') return {label:'中风险',tone:'warn'};
 if(level==='high') return {label:'高风险',tone:'danger'};
 return {label:'风险待评估',tone:'muted'};
}

function summarizeSelfRepairValidation(report){
 var safe=report&&typeof report==='object'?report:{};
 var applyValidation=((safe.apply_result||{}).validation)||{};
 var baseValidation=safe.validation||{};
 var runs=[];
 if(applyValidation&&applyValidation.ran){
  runs=Array.isArray(applyValidation.test_runs)?applyValidation.test_runs:[];
  if(applyValidation.all_passed===true) return '应用后验证已通过'+(runs.length?'，共 '+runs.length+' 项':'');
  if(applyValidation.all_passed===false) return '应用后验证未通过，已自动回滚'+(runs.length?'，共 '+runs.length+' 项':'');
  return '已经执行应用后的验证';
 }
 if(baseValidation&&baseValidation.ran){
  runs=Array.isArray(baseValidation.test_runs)?baseValidation.test_runs:[];
  if(baseValidation.all_passed===true) return '提案预检已通过'+(runs.length?'，共 '+runs.length+' 项':'');
  if(baseValidation.all_passed===false) return '提案预检未通过，需要先处理'+(runs.length?'，共 '+runs.length+' 项':'');
  return '已经执行提案预检';
 }
 return '这条提案还没有跑出验证结果';
}

function renderRepairPathList(paths, isLight, emptyText){
 var list=(Array.isArray(paths)?paths:[]).map(function(item){ return String(item||'').trim(); }).filter(Boolean).slice(0,6);
 var subColor=isLight?'#64748b':'#94a3b8';
 if(!list.length) return '<div style="font-size:12px;color:'+subColor+';">'+escapeHtml(emptyText||'暂时没有')+'</div>';
 var bg=isLight?'rgba(125,118,108,0.1)':'rgba(15,23,42,0.48)';
 var color=isLight?'#5f584f':'#cbd5e1';
 return '<div style="display:flex;flex-wrap:wrap;gap:8px;">'+list.map(function(path){
  return '<span style="padding:6px 10px;border-radius:999px;background:'+bg+';color:'+color+';font-size:12px;font-family:Consolas,monospace;">'+escapeHtml(path)+'</span>';
 }).join('')+'</div>';
}

function renderRepairDetailRow(label, bodyHtml, isLight){
 var subColor=isLight?'#64748b':'#94a3b8';
 return '<div><div style="font-size:12px;color:'+subColor+';margin-bottom:6px;">'+escapeHtml(label)+'</div>'+bodyHtml+'</div>';
}

function toggleSelfRepairReportDetails(reportId){
 var nextId=String(reportId||'').trim();
 settingsPanelState.activeRepairId=settingsPanelState.activeRepairId===nextId?'':nextId;
 renderSettingsPage(document.body.classList.contains('light'));
}

function runSelfRepairAction(action, reportId){
 var isLight=document.body.classList.contains('light');
 var targetId=String(reportId||'').trim();
 if(action!=='refresh'&&!targetId) return;
 settingsPanelState.error='';
 settingsPanelState.notice=(action==='preview'?'正在生成改动预览...':(action==='apply'?'正在应用修复提案...':'正在刷新修复提案...'));
 settingsPanelState.repairActionBusy=action+':'+targetId;
 if(targetId) settingsPanelState.activeRepairId=targetId;
 renderSettingsPage(isLight);
 if(action==='refresh'){
  settingsPanelState.repairActionBusy='';
  refreshSettingsData(isLight,'修复提案列表已刷新').catch(function(){
   settingsPanelState.error='修复提案刷新失败，请稍后再试';
   renderSettingsPage(isLight);
  });
  return;
 }
 var endpoint=action==='apply'?'/self_repair/apply':'/self_repair/preview';
 var payload=action==='apply'?{report_id:targetId}:{report_id:targetId,auto_apply:false,run_validation:true};
 fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8','Accept':'application/json'},body:JSON.stringify(payload)}).then(function(r){return r.json();}).then(function(data){
  if(!data||data.ok===false) throw new Error((data&&data.error)||'unknown_error');
  var report=(data&&data.report)||{};
  var applyStatus=String(((report.apply_result||{}).status)||'').trim();
  var previewStatus=String((((report.patch_preview||{}).status)||'')).trim();
  var notice='修复提案状态已更新';
  if(action==='preview') notice=previewStatus==='preview_ready'?'改动预览已经准备好了':'改动预览生成失败，请看卡片详情';
  else if(applyStatus==='applied'||applyStatus==='applied_without_validation') notice='修复提案已经应用';
  else if(applyStatus.indexOf('rolled_back')===0) notice='修复执行后未通过验证，已经自动回滚';
  else if(applyStatus==='already_applied') notice='这条修复提案已经应用过了';
  else if(applyStatus) notice='修复提案已处理，请看卡片里的最新状态';
  settingsPanelState.repairActionBusy='';
  return refreshSettingsData(isLight,notice);
 }).catch(function(){
  settingsPanelState.repairActionBusy='';
  settingsPanelState.error=(action==='apply'?'修复提案应用失败，请稍后再试':'修复提案预览失败，请稍后再试');
  renderSettingsPage(isLight);
 });
}

function renderSelfRepairReportCard(report, isLight, active){
 var safe=report&&typeof report==='object'?report:{};
 var preview=safe.patch_preview&&typeof safe.patch_preview==='object'?safe.patch_preview:{};
 var apply=safe.apply_result&&typeof safe.apply_result==='object'?safe.apply_result:{};
 var statusMeta=selfRepairReportStatusMeta(safe);
 var riskMeta=selfRepairRiskMeta(safe);
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var borderColor=active?(isLight?'rgba(120,120,130,0.22)':'rgba(150,150,160,0.28)'):(isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)');
 var cardBg=active?(isLight?'linear-gradient(135deg,#f7f4ef,#f2ede6)':'linear-gradient(135deg,rgba(100,100,110,0.18),rgba(28,28,30,0.92))'):(isLight?'var(--bg-card)':'rgba(36,36,40,0.92)');
 var summary=cleanInlineText(safe.summary||safe.problem||'',220)||'这条修复提案还没有生成摘要。';
 var diagnosis=cleanInlineText(safe.diagnosis||safe.fix||'',240);
 var question=cleanInlineText(safe.last_question||'',140);
 var feedback=cleanInlineText(safe.user_feedback||'',140);
 var previewStatus=String(preview.status||'').trim();
 var applyStatus=String(apply.status||'').trim();
 var previewSummary=cleanInlineText(preview.summary||'',220);
 var previewError=cleanInlineText(preview.error||'',200);
 var candidatePaths=(Array.isArray(safe.candidate_files)?safe.candidate_files:[]).map(function(item){return String(((item||{}).path)||'').trim();}).filter(Boolean);
 var testPaths=(Array.isArray(safe.suggested_tests)?safe.suggested_tests:[]).map(function(item){return String(((item||{}).path)||'').trim();}).filter(Boolean);
 var previewEdits=(Array.isArray(preview.edits)?preview.edits:[]).slice(0,2);
 var previewPaths=previewEdits.map(function(item){return String(((item||{}).path)||'').trim();}).filter(Boolean);
 var anyBusy=!!settingsPanelState.repairActionBusy;
 var isBusyPreview=settingsPanelState.repairActionBusy===('preview:'+String(safe.id||''));
 var isBusyApply=settingsPanelState.repairActionBusy===('apply:'+String(safe.id||''));
 var canPreview=applyStatus!=='applied'&&applyStatus!=='applied_without_validation'&&previewStatus!=='preview_ready';
 var canApply=previewStatus==='preview_ready'&&applyStatus!=='applied'&&applyStatus!=='applied_without_validation';
 var html='';
 html+='<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:18px;padding:16px;box-shadow:'+(active?(isLight?'0 10px 30px rgba(34,29,24,0.06)':'0 12px 30px rgba(0,0,0,0.18)'):(isLight?'0 8px 24px rgba(34,29,24,0.05)':'0 10px 24px rgba(0,0,0,0.12)'))+';">';
 html+='<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;">';
 html+='<div style="min-width:0;flex:1 1 420px;"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'+renderSettingsMetaPill(statusMeta.label,statusMeta.tone,isLight)+renderSettingsMetaPill(riskMeta.label,riskMeta.tone,isLight)+'</div><div style="font-size:16px;font-weight:800;color:'+textColor+';line-height:1.5;margin-top:10px;">'+escapeHtml(summary)+'</div></div>';
 html+='<div style="font-size:12px;color:'+subColor+';white-space:nowrap;">'+escapeHtml(formatSettingsTimestamp(safe.updated_at||safe.created_at))+'</div></div>';
 html+='<div style="margin-top:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">';
 html+='<div style="font-size:12px;line-height:1.7;color:'+subColor+';">'+escapeHtml(summarizeSelfRepairValidation(safe))+'</div>';
 html+='<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">';
 html+=renderSettingsActionButton(active?'收起详情':'展开详情','self-repair-toggle',String(safe.id||''),isLight,'secondary',anyBusy);
 if(canPreview) html+=renderSettingsActionButton(isBusyPreview?'正在生成...':(previewStatus==='preview_failed'?'重新生成预览':'生成改动预览'),'self-repair-preview',String(safe.id||''),isLight,'secondary',anyBusy);
 if(canApply) html+=renderSettingsActionButton(isBusyApply?'正在应用...':'批准并应用','self-repair-apply',String(safe.id||''),isLight,'primary',anyBusy);
 html+='</div></div>';
 if(active){
  html+='<div style="margin-top:14px;padding-top:14px;border-top:1px dashed '+borderColor+';display:grid;gap:12px;">';
  if(question) html+=renderRepairDetailRow('对应提问','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(question)+'</div>',isLight);
  if(feedback) html+=renderRepairDetailRow('用户反馈','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(feedback)+'</div>',isLight);
  if(diagnosis) html+=renderRepairDetailRow('排查判断','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(diagnosis)+'</div>',isLight);
  html+=renderRepairDetailRow('候选文件',renderRepairPathList(candidatePaths,isLight,'这条提案还没有列出候选文件'),isLight);
  html+=renderRepairDetailRow('建议测试',renderRepairPathList(testPaths,isLight,'这条提案还没有列出建议测试'),isLight);
  if(previewStatus==='preview_ready'){
   html+=renderRepairDetailRow('改动预览','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(previewSummary||'已经生成改动预览，可以先看文件范围和片段后，再在这里批准应用。')+'</div>',isLight);
   html+=renderRepairDetailRow('拟改文件',renderRepairPathList(previewPaths,isLight,'这次预览还没有列出具体改动文件'),isLight);
  }else if(previewStatus==='preview_failed'){
   html+=renderRepairDetailRow('预览失败','<div style="font-size:13px;line-height:1.8;color:'+(isLight?'#b91c1c':'#fca5a5')+';">'+escapeHtml(previewError||'这次改动预览没有成功生成。')+'</div>',isLight);
  }else{
   html+=renderRepairDetailRow('审批入口','<div style="font-size:13px;line-height:1.8;color:'+subColor+';">先点"生成改动预览"，看完文件范围和片段后，再在这里批准应用。</div>',isLight);
  }
  html+='</div>';
 }
 html+='</div>';
 return html;
}

function renderSelfRepairReviewSection(config, status, reports, isLight){
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var cardBg=isLight?'var(--bg-card)':'rgba(36,36,40,0.95)';
 var borderColor=isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)';
 var safeReports=Array.isArray(reports)?reports:[];
 var list=safeReports.slice(0,10);
 var activeId=settingsPanelState.activeRepairId||((list[0]&&list[0].id)||'');
 var html='';
 html+='<div style="margin-top:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:16px 18px;border-radius:14px;">';
 html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">';
 html+='<div style="display:flex;align-items:center;gap:10px;"><span style="font-size:15px;font-weight:700;color:'+textColor+';">'+t('settings.repair.title')+'</span><span style="font-size:12px;color:'+subColor+';">'+(list.length?(list.length+' '+t('settings.items')):'')+'</span></div>';
 html+='<div style="display:flex;gap:8px;">'+renderSettingsActionButton(t('settings.repair.refresh'),'self-repair-refresh','',isLight,'secondary',!!settingsPanelState.repairActionBusy)+'</div>';
 html+='</div>';
 if(!list.length){
  html+='<div style="margin-top:10px;font-size:12px;color:'+subColor+';">'+t('settings.repair.empty')+'</div>';
 }else{
  html+='<div style="margin-top:12px;display:grid;gap:10px;">'+list.map(function(report){
   return renderSelfRepairReportCard(report,isLight,String(report&&report.id||'')===String(activeId||''));
  }).join('')+'</div>';
 }
 html+='</div>';
 return html;
}

function handleSettingsAction(action, detail){
 detail=detail||{};
 if(action==='toggle'){ if(detail.key) toggleAutolearnSetting(detail.key); return; }
 if(action==='preset'){ if(detail.key) applyAutolearnPreset(detail.key); return; }
 if(action==='advanced-toggle'){ toggleAutolearnAdvanced(); return; }
 if(action==='advanced-save'){ saveAutolearnAdvancedSettings(); return; }
 if(action==='self-repair-refresh'){ runSelfRepairAction('refresh',''); return; }
 if(action==='self-repair-toggle'){ toggleSelfRepairReportDetails(detail.key); return; }
 if(action==='self-repair-preview'){ runSelfRepairAction('preview',detail.key); return; }
 if(action==='self-repair-apply'){ runSelfRepairAction('apply',detail.key); }
}

document.addEventListener('click',function(event){
 var button=event.target&&event.target.closest?event.target.closest('[data-settings-action]'):null;
 if(!button) return;
 handleSettingsAction(button.getAttribute('data-settings-action'),{key:button.getAttribute('data-settings-key')||''});
});

document.addEventListener('change',function(event){
 var node=event.target;
 if(!node||!node.matches||!node.matches('[data-settings-change="self-repair-mode"]')) return;
 saveSelfRepairMode();
});

function renderSettingsPage(isLight){
 var box=document.getElementById('settingsBox');
 if(!box) return;
 var config=mergeAutolearnConfig(settingsPanelState.config||{});
 var selfRepairStatus=settingsPanelState.selfRepairStatus||{};
 var selfRepairReports=Array.isArray(settingsPanelState.selfRepairReports)?settingsPanelState.selfRepairReports:[];
 var l7s=settingsPanelState.l7Stats||{};
 var notice=settingsPanelState.error||settingsPanelState.notice||'';
 var noticeColor=settingsPanelState.error?'#ef4444':(isLight?'#374151':'#c7d2fe');
 var cardBg=isLight?'var(--bg-card)':'rgba(36,36,40,0.95)';
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var borderColor=isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)';
 var html='';

 // ── 语言切换 ──
 var _isZh=getLang()==='zh';
 html+='<div style="margin-bottom:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:14px 18px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<span style="font-size:14px;font-weight:600;color:'+textColor+';">'+t('settings.lang')+'</span>';
 html+='<div style="display:flex;gap:6px;">';
 html+='<button onclick="setLang(\'zh\')" style="padding:6px 14px;border-radius:8px;border:1px solid '+borderColor+';background:'+(_isZh?'linear-gradient(135deg,#6f685e,#8a8174)':cardBg)+';color:'+(_isZh?'#fff':textColor)+';font-size:13px;font-weight:600;cursor:pointer;">'+t('settings.lang.zh')+'</button>';
 html+='<button onclick="setLang(\'en\')" style="padding:6px 14px;border-radius:8px;border:1px solid '+borderColor+';background:'+(!_isZh?'linear-gradient(135deg,#6f685e,#8a8174)':cardBg)+';color:'+(!_isZh?'#fff':textColor)+';font-size:13px;font-weight:600;cursor:pointer;">'+t('settings.lang.en')+'</button>';
 html+='</div></div>';

 // ── 区块1：状态总览（4个数字）──
 html+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;">';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">'+t('settings.correction')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.l7_rule_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">'+t('settings.behavior')+'</div><div style="font-size:22px;font-weight:800;color:'+(l7s.l7_constraint_count?'#6f7e63':textColor)+';">'+(l7s.l7_constraint_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">'+t('settings.knowledge')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.l8_knowledge_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='</div>';

 // ── 区块2：持续进化 ──
 var _evo=config.enabled;
 if(!document.getElementById('nova-spin-style')){var _ss=document.createElement('style');_ss.id='nova-spin-style';_ss.textContent='@keyframes nova-spin{to{transform:rotate(360deg)}}';document.head.appendChild(_ss);}
 var _dotHtml=_evo?'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;border:2.5px solid '+(isLight?'#7c3aed':'#a78bfa')+';border-top-color:transparent;animation:nova-spin 1s linear infinite;vertical-align:middle;margin-right:10px;"></span>':'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:'+(isLight?'#cbd5e1':'#475569')+';vertical-align:middle;margin-right:10px;"></span>';
 html+='<div style="margin-top:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:18px 20px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<div><div style="display:flex;align-items:center;"><span style="font-size:16px;font-weight:700;color:'+textColor+';">'+_dotHtml+(_evo?t('settings.evolving'):t('settings.paused'))+'</span></div><div style="font-size:12px;color:'+subColor+';margin-top:6px;">'+(_evo?t('settings.evolve.desc.on'):t('settings.evolve.desc.off'))+'</div></div>';
 html+='<div data-settings-action="toggle" data-settings-key="enabled" style="flex-shrink:0;width:44px;height:24px;border-radius:12px;background:'+(_evo?(isLight?'#7a876d':'#34d399'):(isLight?'#d8d0c7':'#475569'))+';cursor:pointer;position:relative;transition:background 0.2s;"><span style="position:absolute;top:2px;'+(_evo?'right:2px':'left:2px')+';width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:all 0.2s;"></span></div>';
 html+='</div>';

 // ── 区块3：模型管理 ──
 html+=renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor);

 // ── 区块4：修复提案审核（已废弃，改用对话中 self_fix 工具）──
 // html+=renderSelfRepairReviewSection(config,selfRepairStatus,selfRepairReports,isLight);

 box.innerHTML=html;
}

function refreshSettingsData(isLight, noticeText){
 return Promise.all([
  fetch('/stats').then(function(r){return r.json();}),
  fetch('/autolearn/config').then(function(r){return r.json();}),
  fetch('/self_repair/status').then(function(r){return r.json();}),
  fetch('/self_repair/reports?limit=6').then(function(r){return r.json();}).catch(function(){return {reports:[]};}),
  fetch('/l7/stats').then(function(r){return r.json();}).catch(function(){return {};})
 ]).then(function(values){
  var statsResp=values[0]||{};
  var configResp=values[1]||{};
  var statusResp=values[2]||{};
  var reportsResp=values[3]||{};
  var l7Resp=values[4]||{};
  settingsPanelState.stats=statsResp.stats||statsResp||{};
  settingsPanelState.config=mergeAutolearnConfig((configResp&&configResp.config)||settingsPanelState.config||{});
  settingsPanelState.selfRepairStatus=(statusResp&&statusResp.status)||settingsPanelState.selfRepairStatus||{};
  settingsPanelState.selfRepairReports=Array.isArray(reportsResp&&reportsResp.reports)?reportsResp.reports:[];
  settingsPanelState.l7Stats=l7Resp;
  if(settingsPanelState.activeRepairId){
   var stillExists=settingsPanelState.selfRepairReports.some(function(item){return String((item||{}).id||'')===String(settingsPanelState.activeRepairId||'');});
   if(!stillExists) settingsPanelState.activeRepairId=(settingsPanelState.selfRepairReports[0]&&settingsPanelState.selfRepairReports[0].id)||'';
  }else{
   settingsPanelState.activeRepairId=(settingsPanelState.selfRepairReports[0]&&settingsPanelState.selfRepairReports[0].id)||'';
  }
  if(noticeText!==undefined){settingsPanelState.notice=noticeText;settingsPanelState.error='';}
  renderSettingsPage(isLight);
 });
}

function loadSettingsPage(isLight){
 var chat=document.getElementById('chat');
 setInputVisible(false);
 chat.innerHTML='<div class="settings-page" style="position:relative;z-index:1;"><div id="settingsBox">'+t('loading')+'</div></div>';
 settingsPanelState.notice='';
 settingsPanelState.error='';
 loadSettingsModels();
 refreshSettingsData(isLight).catch(function(){
  settingsPanelState.error=t('settings.load.fail');
  renderSettingsPage(isLight);
 });
}

function saveAutolearnConfigPatch(patch, noticeText){
 var isLight=document.body.classList.contains('light');
 settingsPanelState.error='';
 settingsPanelState.notice='正在保存...';
 renderSettingsPage(isLight);
 fetch('/autolearn/config',{
  method:'POST',
  headers:{'Content-Type':'application/json; charset=utf-8','Accept':'application/json'},
  body:JSON.stringify(patch||{})
 }).then(function(r){return r.json();}).then(function(data){
  settingsPanelState.config=mergeAutolearnConfig((data&&data.config)||settingsPanelState.config||{});
  return refreshSettingsData(isLight,noticeText||'已保存');
 }).catch(function(){
  settingsPanelState.error='保存失败，请稍后再试';
  renderSettingsPage(isLight);
 });
}

function toggleAutolearnSetting(key){
 if(!settingsPanelState.config) settingsPanelState.config={};
 var next=!mergeAutolearnConfig(settingsPanelState.config)[key];
 settingsPanelState.config[key]=next;
 console.log('[settings] toggle', key, '->', next, 'config.enabled=', settingsPanelState.config.enabled);
 var isLight=document.body.classList.contains('light');
 settingsPanelState.notice='';
 settingsPanelState.error='';
 renderSettingsPage(isLight);
 var patch={};patch[key]=next;
 fetch('/autolearn/config',{
  method:'POST',
  headers:{'Content-Type':'application/json; charset=utf-8','Accept':'application/json'},
  body:JSON.stringify(patch)
 }).then(function(r){return r.json();}).then(function(data){
  settingsPanelState.config=mergeAutolearnConfig((data&&data.config)||settingsPanelState.config||{});
  return refreshSettingsData(isLight,next?'已开启':'已关闭');
 }).catch(function(){
  settingsPanelState.error='保存失败';
  renderSettingsPage(isLight);
 });
}

function applyAutolearnPreset(key){
 var presets=autolearnPresets();
 if(!presets[key]) return;
 var patch={};
 Object.keys(presets[key].patch).forEach(function(field){patch[field]=presets[key].patch[field];});
 saveAutolearnConfigPatch(patch,'已切换到「'+presets[key].label+'」');
}

function saveAutolearnAdvancedSettings(){
 var patch={
  min_query_length:clampSettingNumber((document.getElementById('autolearnMinQuery')||{}).value,2,30,4),
  search_timeout_sec:clampSettingNumber((document.getElementById('autolearnTimeout')||{}).value,3,20,5),
  max_results:clampSettingNumber((document.getElementById('autolearnMaxResults')||{}).value,1,10,5),
  max_summary_length:clampSettingNumber((document.getElementById('autolearnSummaryLimit')||{}).value,120,800,360),
  self_repair_test_timeout_sec:clampSettingNumber((document.getElementById('selfRepairTestTimeout')||{}).value,10,120,30)
 };
 saveAutolearnConfigPatch(patch,'底层参数已更新');
}

function saveSelfRepairMode(){
 var el=document.getElementById('selfRepairApplyMode');
 if(!el) return;
 saveAutolearnConfigPatch({self_repair_apply_mode:el.value},'审批节奏已更新');
}

// ── 模型管理 ──
var _settingsModels=null;
var _settingsCurrentModel='';
var _settingsCatalog=null;
var _settingsExpandedProviders={};

function _classifyModelToProvider(mid, cfg, catalog){
 if(!catalog) return null;
 var midL=mid.toLowerCase();
 var modelName=String((cfg||{}).model||'').toLowerCase();
 var baseUrl=String((cfg||{}).base_url||'').toLowerCase();
 // 第一轮：按模型 ID / 模型名 / 别名匹配（优先级高）
 for(var pkey in catalog){
  if(midL.indexOf(pkey)!==-1||modelName.indexOf(pkey)!==-1) return pkey;
  var aliases=catalog[pkey].aliases||[];
  for(var i=0;i<aliases.length;i++){
   if(midL.indexOf(aliases[i])!==-1||modelName.indexOf(aliases[i])!==-1) return pkey;
  }
 }
 // 第二轮：按 base_url 匹配（兜底）
 for(var pkey2 in catalog){
  if(catalog[pkey2].url_hint && baseUrl.indexOf(catalog[pkey2].url_hint)!==-1) return pkey2;
 }
 return null;
}

function _toggleProviderGroup(pkey){
 _settingsExpandedProviders[pkey]=!_settingsExpandedProviders[pkey];
 renderSettingsPage(document.body.classList.contains('light'));
}

function _quickAddModel(pkey, modelId){
 if(!_settingsModels||!_settingsCatalog) return;
 var catalog=_settingsCatalog;
 var pinfo=catalog[pkey];
 if(!pinfo) return;
 // 找同厂商已有配置作为 donor
 var donorCfg=null;
 for(var mid in _settingsModels){
  var classified=_classifyModelToProvider(mid, _settingsModels[mid], catalog);
  if(classified===pkey){ donorCfg=_settingsModels[mid]; break; }
 }
 if(!donorCfg||!donorCfg.api_key||!donorCfg.base_url){
  alert('\u8be5\u5382\u5546\u6ca1\u6709\u5df2\u914d\u7f6e\u7684\u6a21\u578b\uff0c\u8bf7\u5148\u624b\u52a8\u6dfb\u52a0\u4e00\u4e2a');
  return;
 }
 var cfg={
  api_key:donorCfg.api_key,
  base_url:donorCfg.base_url,
  model:modelId,
  vision:donorCfg.vision||false
 };
 fetch('/models/config',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({id:modelId,config:cfg})
 }).then(function(r){return r.json();}).then(function(d){
  if(d.ok) loadSettingsModels();
  else alert(d.error||'\u6dfb\u52a0\u5931\u8d25');
 }).catch(function(){alert('\u6dfb\u52a0\u5931\u8d25');});
}

function renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor){
 var html='';
 html+='<div style="margin-top:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:18px 20px;border-radius:14px;">';
 html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;">';
 html+='<span style="font-size:15px;font-weight:700;color:'+textColor+';">'+t('settings.models')+'</span>';
 html+='<button type="button" onclick="openModelDialog()" style="padding:6px 14px;border:1px solid '+borderColor+';border-radius:8px;background:none;color:'+textColor+';font-size:12px;cursor:pointer;">'+t('settings.models.add')+'</button>';
 html+='</div>';
 html+='<div id="modelListBox" style="display:flex;flex-direction:column;gap:8px;">';
 if(!_settingsModels||!_settingsCatalog){
  html+='\u52a0\u8f7d\u4e2d...';
 }else{
  var catalog=_settingsCatalog;
  var models=_settingsModels;
  var currentModel=_settingsCurrentModel;
  // 按厂商分组已配置模型
  var providerConfigured={};
  var uncategorized=[];
  for(var mid in models){
   var pkey=_classifyModelToProvider(mid, models[mid], catalog);
   if(pkey){
    if(!providerConfigured[pkey]) providerConfigured[pkey]=[];
    providerConfigured[pkey].push(mid);
   }else{
    uncategorized.push(mid);
   }
  }
  // 确定哪些厂商默认展开（有当前使用模型的厂商）
  var currentProvider=null;
  if(currentModel){
   currentProvider=_classifyModelToProvider(currentModel, models[currentModel], catalog);
  }
  // 渲染每个 catalog 厂商
  for(var pk in catalog){
   var pi=catalog[pk];
   var configured=providerConfigured[pk]||[];
   var isExpanded=_settingsExpandedProviders[pk]!==undefined?_settingsExpandedProviders[pk]:(pk===currentProvider);
   var hasConfigured=configured.length>0;
   var providerLabel=pk.charAt(0).toUpperCase()+pk.slice(1);
   // 找当前使用的模型名
   var activeModelName='';
   for(var ci=0;ci<configured.length;ci++){
    if(configured[ci]===currentModel){
     activeModelName=(models[configured[ci]]||{}).model||configured[ci];
     break;
    }
   }
  var headerBg=isExpanded?(isLight?'rgba(122,116,107,0.06)':'rgba(99,102,241,0.06)'):('transparent');
   var chevron=isExpanded?'\u25BC':'\u25B6';
   html+='<div style="border:1px solid '+borderColor+';border-radius:12px;overflow:hidden;'+(isExpanded?'box-shadow:'+(isLight?'0 2px 8px rgba(0,0,0,0.04)':'0 2px 8px rgba(0,0,0,0.12)')+';':'')+'margin-bottom:2px;">';
   // 折叠头
   html+='<div onclick="_toggleProviderGroup(\''+pk+'\')" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;background:'+headerBg+';transition:background 0.15s;">';
   html+='<span style="font-size:11px;color:'+subColor+';width:14px;text-align:center;">'+chevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+textColor+';flex:1;">'+escapeHtml(providerLabel)+'</span>';
   if(activeModelName){
   html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(122,140,109,0.12)':'rgba(52,211,153,0.12)')+';color:'+(isLight?'#6f7e63':'#34d399')+';font-size:11px;font-weight:600;">'+escapeHtml(activeModelName)+'</span>';
   }else if(!hasConfigured){
    html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(148,163,184,0.1)':'rgba(148,163,184,0.1)')+';color:'+subColor+';font-size:11px;">'+t('settings.models.notconfigured')+'</span>';
   }
   html+='</div>';
   // 展开内容
   if(isExpanded){
    html+='<div style="padding:6px 14px 12px;display:flex;flex-direction:column;gap:5px;">';
    // 已配置模型
    for(var j=0;j<configured.length;j++){
     var cmid=configured[j];
     var cm=models[cmid]||{};
     var isCurrent=cmid===currentModel;
    var rowBg=isCurrent?(isLight?'rgba(122,116,107,0.08)':'rgba(59,130,246,0.1)'):(isLight?'#f7f4ef':'rgba(28,28,30,0.6)');
    var rowBorder=isCurrent?(isLight?'rgba(122,116,107,0.22)':'rgba(96,165,250,0.3)'):borderColor;
    var visionDot=cm.vision?'<span style="width:6px;height:6px;border-radius:50%;background:#8a948f;display:inline-block;margin-left:4px;" title="'+t('settings.models.vision')+'"></span>':'';
    var checkMark=isCurrent?'<span style="color:'+(isLight?'#6f7e63':'#34d399')+';font-size:14px;margin-right:6px;">\u2713</span>':'';
     html+='<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;background:'+rowBg+';border:1px solid '+rowBorder+';border-radius:10px;transition:all 0.15s;">';
     html+=checkMark;
     html+='<span style="font-size:13px;font-weight:'+(isCurrent?'700':'500')+';color:'+textColor+';flex:1;">'+escapeHtml(cm.model||cmid)+'</span>';
     html+=visionDot;
     html+='<span style="font-size:11px;color:'+subColor+';margin-right:4px;">'+escapeHtml(cmid)+'</span>';
     if(isCurrent){
      html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(122,140,109,0.12)':'rgba(52,211,153,0.12)')+';color:'+(isLight?'#6f7e63':'#34d399')+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
    }else{
      html+='<button onclick="switchModel(\''+escapeHtml(cmid)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+(isLight?'rgba(122,116,107,0.24)':'rgba(99,102,241,0.3)')+';background:none;color:'+(isLight?'#6a6258':'#6366f1')+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;" onmouseenter="this.style.background=\''+(isLight?'#6a6258':'#6366f1')+'\';this.style.color=\'#fff\'" onmouseleave="this.style.background=\'none\';this.style.color=\''+(isLight?'#6a6258':'#6366f1')+'\'">'+t('settings.models.activate')+'</button>';
     }
     html+='<button onclick="openModelDialog(\''+escapeHtml(cmid)+'\')" style="padding:3px 8px;border:1px solid '+borderColor+';border-radius:5px;background:none;color:'+subColor+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
     html+='</div>';
    }
    // catalog 中未配置的模型
    var configuredIds={};
    for(var k=0;k<configured.length;k++){
     configuredIds[configured[k].toLowerCase()]=true;
     var mname=((models[configured[k]]||{}).model||'').toLowerCase();
     if(mname) configuredIds[mname]=true;
    }
    var catalogModels=pi.models||[];
    for(var m=0;m<catalogModels.length;m++){
     var catModel=catalogModels[m];
     if(configuredIds[catModel.id.toLowerCase()]) continue;
    html+='<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:'+(isLight?'rgba(122,116,107,0.04)':'rgba(148,163,184,0.04)')+';border:1px dashed '+(isLight?'rgba(122,116,107,0.18)':'rgba(148,163,184,0.12)')+';border-radius:10px;">';
     html+='<span style="font-size:13px;color:'+subColor+';flex:1;">'+escapeHtml(catModel.id)+'<span style="font-size:11px;margin-left:6px;opacity:0.7;">'+escapeHtml(catModel.desc)+'</span></span>';
     if(hasConfigured){
      html+='<button onclick="_quickAddModel(\''+escapeHtml(pk)+'\',\''+escapeHtml(catModel.id)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+(isLight?'rgba(122,116,107,0.24)':'rgba(99,102,241,0.3)')+';background:none;color:'+(isLight?'#6a6258':'#6366f1')+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;" onmouseenter="this.style.background=\''+(isLight?'#6a6258':'#6366f1')+'\';this.style.color=\'#fff\'" onmouseleave="this.style.background=\'none\';this.style.color=\''+(isLight?'#6a6258':'#6366f1')+'\'">'+t('settings.models.quickadd')+'</button>';
     }
     html+='</div>';
    }
    html+='</div>';
   }
   html+='</div>';
  }
  // 未分类模型
  if(uncategorized.length>0){
   var uncExpanded=_settingsExpandedProviders['_other']!==undefined?_settingsExpandedProviders['_other']:(!currentProvider);
   var uncChevron=uncExpanded?'\u25BC':'\u25B6';
   html+='<div style="border:1px solid '+borderColor+';border-radius:12px;overflow:hidden;margin-bottom:2px;">';
   html+='<div onclick="_toggleProviderGroup(\'_other\')" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;">';
   html+='<span style="font-size:11px;color:'+subColor+';width:14px;text-align:center;">'+uncChevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+textColor+';flex:1;">Other</span>';
   html+='</div>';
   if(uncExpanded){
    html+='<div style="padding:6px 14px 12px;display:flex;flex-direction:column;gap:5px;">';
    for(var u=0;u<uncategorized.length;u++){
     var umid=uncategorized[u];
     var um=models[umid]||{};
     var uCurrent=umid===currentModel;
     var uRowBg=uCurrent?(isLight?'rgba(122,116,107,0.08)':'rgba(59,130,246,0.1)'):(isLight?'#f7f4ef':'rgba(28,28,30,0.6)');
     var uRowBorder=uCurrent?(isLight?'rgba(122,116,107,0.22)':'rgba(96,165,250,0.3)'):borderColor;
     html+='<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;background:'+uRowBg+';border:1px solid '+uRowBorder+';border-radius:10px;">';
     if(uCurrent) html+='<span style="color:'+(isLight?'#6f7e63':'#34d399')+';font-size:14px;margin-right:6px;">\u2713</span>';
     html+='<span style="font-size:13px;font-weight:'+(uCurrent?'700':'500')+';color:'+textColor+';flex:1;">'+escapeHtml(um.model||umid)+'</span>';
     html+='<span style="font-size:11px;color:'+subColor+';margin-right:4px;">'+escapeHtml(umid)+'</span>';
     if(uCurrent){
      html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(122,140,109,0.12)':'rgba(52,211,153,0.12)')+';color:'+(isLight?'#6f7e63':'#34d399')+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
    }else{
      html+='<button onclick="switchModel(\''+escapeHtml(umid)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+(isLight?'rgba(122,116,107,0.24)':'rgba(99,102,241,0.3)')+';background:none;color:'+(isLight?'#6a6258':'#6366f1')+';font-size:11px;cursor:pointer;font-weight:500;">'+t('settings.models.activate')+'</button>';
     }
     html+='<button onclick="openModelDialog(\''+escapeHtml(umid)+'\')" style="padding:3px 8px;border:1px solid '+borderColor+';border-radius:5px;background:none;color:'+subColor+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
     html+='</div>';
    }
    html+='</div>';
   }
   html+='</div>';
  }
 }
 html+='</div></div>';
 return html;
}

function loadSettingsModels(){
 Promise.all([
  fetch('/models/config').then(function(r){return r.json();}),
  fetch('/models/catalog').then(function(r){return r.json();}).catch(function(){return {catalog:{}};})
 ]).then(function(values){
  var d=values[0]||{};
  var c=values[1]||{};
  _settingsModels=d.models||{};
  _settingsCurrentModel=d.current||'';
  _settingsCatalog=c.catalog||{};
  // 同步侧边栏
  window._novaModels={};
  Object.keys(_settingsModels).forEach(function(k){
   window._novaModels[k]={model:(_settingsModels[k]||{}).model||k,vision:!!(_settingsModels[k]||{}).vision,base_url:(_settingsModels[k]||{}).base_url||''};
  });
  window._novaCurrentModel=_settingsCurrentModel;
  window._novaCatalog=_settingsCatalog;
  var el=document.getElementById('modelName');
  var _curCfg=_settingsModels[_settingsCurrentModel];
  if(el) el.textContent=(_curCfg&&_curCfg.model)?_curCfg.model:(_settingsCurrentModel||t('unknown'));
  if(typeof updateImageBtnState==='function') updateImageBtnState();
  renderSettingsPage(document.body.classList.contains('light'));
 }).catch(function(){});
}

function openModelDialog(editId){
 var isEdit=!!editId;
 var m=isEdit?(_settingsModels[editId]||{}):{};
 var isCurrent=isEdit&&editId===_settingsCurrentModel;
 var isLight=document.body.classList.contains('light');
 var bg=isLight?'#fbfaf7':'#1c1c1e';
 var border=isLight?'rgba(114,105,94,0.18)':'rgba(255,255,255,0.1)';
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var inputBg=isLight?'#f5f1ea':'rgba(255,255,255,0.06)';
 var labelStyle='font-size:12px;font-weight:600;color:'+subColor+';margin-bottom:5px;';
 var inputStyle='width:100%;padding:10px 14px;border-radius:10px;border:1px solid '+border+';background:'+inputBg+';color:'+textColor+';outline:none;font-size:13px;box-sizing:border-box;';
 var title=isEdit?t('settings.models.edit'):t('settings.models.add');

 var overlay=document.createElement('div');
 overlay.id='modelDialog';
 overlay.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;';

 var html='<div style="background:'+bg+';border:1px solid '+border+';border-radius:16px;padding:24px;width:420px;max-width:90vw;">';
 html+='<div style="font-size:16px;font-weight:600;color:'+textColor+';margin-bottom:18px;">'+escapeHtml(title)+'</div>';
 html+='<div style="display:flex;flex-direction:column;gap:14px;">';

 // 模型 ID
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.id')+'</div>';
 html+='<input id="mdlId" value="'+escapeHtml(isEdit?editId:'')+'" placeholder="gpt-4o, claude-3 ..." style="'+inputStyle+(isEdit?'opacity:0.5;cursor:not-allowed;':'')+'\"'+(isEdit?' disabled':'')+'></div>';

 // 模型名称
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.name')+'</div>';
 html+='<input id="mdlName" value="'+escapeHtml(m.model||'')+'" placeholder="'+t('settings.models.field.name.hint')+'" style="'+inputStyle+'"></div>';

 // Base URL
 html+='<div><div style="'+labelStyle+'">Base URL</div>';
 html+='<input id="mdlUrl" value="'+escapeHtml(m.base_url||'')+'" placeholder="https://api.openai.com/v1" style="'+inputStyle+'"></div>';

 // API Key
 html+='<div><div style="'+labelStyle+'">API Key</div>';
 var maskedKey='';
 var fullKey='';
 if(isEdit&&m.api_key){var k=m.api_key;fullKey=k;maskedKey=k.length>14?(k.slice(0,6)+'****'+k.slice(-4)):k.replace(/./g,'*');}
 html+='<div style="position:relative;"><input id="mdlKey" value="" placeholder="'+(isEdit?(maskedKey||t('settings.models.field.key.hint')):'sk-...')+'" style="'+inputStyle+';padding-right:40px;">';
 if(isEdit&&fullKey){html+='<button type="button" id="mdlKeyToggle" onclick="(function(b){var inp=document.getElementById(\'mdlKey\');var showing=b.getAttribute(\'data-show\')===\'1\';if(!showing){inp.value=\''+escapeHtml(fullKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94\\\'/><path d=\\\'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19\\\'/><line x1=\\\'1\\\' y1=\\\'1\\\' x2=\\\'23\\\' y2=\\\'23\\\'/></svg>\';b.setAttribute(\'data-show\',\'1\');}else{inp.value=\'\';inp.placeholder=\''+escapeHtml(maskedKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\\\'/><circle cx=\\\'12\\\' cy=\\\'12\\\' r=\\\'3\\\'/></svg>\';b.setAttribute(\'data-show\',\'0\');}})(this)" data-show="0" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;opacity:0.5;color:'+subColor+';display:flex;align-items:center;" title="Show/Hide"><svg width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\'><path d=\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\'/><circle cx=\'12\' cy=\'12\' r=\'3\'/></svg></button>';}
 html+='</div></div>';

 // 视觉支持 toggle
 var checked=m.vision?'checked':'';
 html+='<label style="display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none;">';
 html+='<input id="mdlVision" type="checkbox" '+checked+' style="width:16px;height:16px;accent-color:#7a7267;">';
 html+='<span style="font-size:13px;color:'+textColor+';">'+t('settings.models.vision')+'</span></label>';

 // 底部按钮行
 html+='<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">';
 // 删除按钮（编辑模式 + 非当前模型）
 if(isEdit&&!isCurrent){
  html+='<button onclick="_modelDialogDelete(\''+escapeHtml(editId)+'\')" style="padding:8px 14px;border-radius:8px;border:1px solid rgba(171,113,99,0.22);background:transparent;color:#9a665d;cursor:pointer;font-size:12px;opacity:0.7;transition:opacity 0.15s;" onmouseenter="this.style.opacity=\'1\'" onmouseleave="this.style.opacity=\'0.7\'">'+t('settings.models.delete')+'</button>';
 }
 html+='<div style="flex:1;"></div>';
 html+='<button onclick="document.getElementById(\'modelDialog\').remove()" style="padding:8px 18px;border-radius:8px;border:1px solid '+border+';background:transparent;color:'+textColor+';cursor:pointer;font-size:13px;">'+t('cancel')+'</button>';
 html+='<button onclick="_modelDialogSave(\''+escapeHtml(isEdit?editId:'')+'\')" style="padding:8px 18px;border-radius:8px;border:none;background:#6a6258;color:#fff;cursor:pointer;font-size:13px;">'+t('save')+'</button>';
 html+='</div></div></div>';

 overlay.innerHTML=html;
 document.body.appendChild(overlay);
 overlay.addEventListener('click',function(e){if(e.target===overlay)overlay.remove();});
 // 自动聚焦第一个可编辑字段
 var first=isEdit?document.getElementById('mdlName'):document.getElementById('mdlId');
 if(first)setTimeout(function(){first.focus();},50);
}

function _modelDialogSave(editId){
 var isEdit=!!editId;
 var mid=isEdit?editId:(document.getElementById('mdlId').value||'').trim();
 if(!mid){document.getElementById('mdlId').style.borderColor='#ef4444';return;}
 var modelName=(document.getElementById('mdlName').value||'').trim()||mid;
 var baseUrl=(document.getElementById('mdlUrl').value||'').trim();
 if(!baseUrl){document.getElementById('mdlUrl').style.borderColor='#ef4444';return;}
 var apiKey=(document.getElementById('mdlKey').value||'').trim();
 if(!isEdit&&!apiKey){document.getElementById('mdlKey').style.borderColor='#ef4444';return;}
 var vision=document.getElementById('mdlVision').checked;
 var cfg={base_url:baseUrl,model:modelName,vision:vision};
 if(apiKey) cfg.api_key=apiKey;
 else if(isEdit&&_settingsModels[editId]) cfg.api_key=_settingsModels[editId].api_key;
 saveModelConfig(mid,cfg);
 var dlg=document.getElementById('modelDialog');
 if(dlg)dlg.remove();
}

function _modelDialogDelete(mid){
 if(!confirm(t('settings.models.delete.confirm')+' '+mid+' ?'))return;
 fetch('/models/config',{
  method:'DELETE',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({id:mid})
 }).then(function(r){return r.json();}).then(function(d){
  if(d.ok){var dlg=document.getElementById('modelDialog');if(dlg)dlg.remove();loadSettingsModels();}
  else alert(d.error||t('settings.models.delete.fail'));
 }).catch(function(){alert(t('settings.models.delete.fail'));});
}

function saveModelConfig(mid,cfg){
 fetch('/models/config',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({id:mid,config:cfg})
 }).then(function(r){return r.json();}).then(function(d){
  if(d.ok) loadSettingsModels();
  else alert(d.error||'\u4fdd\u5b58\u5931\u8d25');
 }).catch(function(){alert('\u4fdd\u5b58\u5931\u8d25');});
}

function renderSettingsPage(isLight){
 var box=document.getElementById('settingsBox');
 if(!box) return;
 var theme=getSettingsTheme(isLight);
 var config=mergeAutolearnConfig(settingsPanelState.config||{});
 var l7s=settingsPanelState.l7Stats||{};
 var notice=settingsPanelState.error||settingsPanelState.notice||'';
 var noticeColor=settingsPanelState.error?'#ef4444':theme.accentText;
 var html='';
 var _isZh=getLang()==='zh';

 if(notice){
  html+='<div style="margin-bottom:14px;background:'+theme.cardBg+';border:1px solid '+theme.border+';padding:12px 16px;border-radius:14px;color:'+noticeColor+';font-size:12px;line-height:1.7;">'+escapeHtml(notice)+'</div>';
 }

 html+='<div style="margin-bottom:14px;background:'+theme.cardBg+';border:1px solid '+theme.border+';padding:14px 18px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';">'+t('settings.lang')+'</span>';
 html+='<div style="display:flex;gap:6px;">';
 html+='<button onclick="setLang(\'zh\')" style="padding:6px 14px;border-radius:8px;border:1px solid '+theme.border+';background:'+(_isZh?theme.actionPrimary:theme.cardBg)+';color:'+(_isZh?theme.actionPrimaryText:theme.text)+';font-size:13px;font-weight:600;cursor:pointer;">'+t('settings.lang.zh')+'</button>';
 html+='<button onclick="setLang(\'en\')" style="padding:6px 14px;border-radius:8px;border:1px solid '+theme.border+';background:'+(!_isZh?theme.actionPrimary:theme.cardBg)+';color:'+(!_isZh?theme.actionPrimaryText:theme.text)+';font-size:13px;font-weight:600;cursor:pointer;">'+t('settings.lang.en')+'</button>';
 html+='</div></div>';

 html+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;">';
 html+='<div style="background:'+theme.cardBg+';padding:16px;border-radius:14px;border:1px solid '+theme.border+';"><div style="font-size:12px;color:'+theme.sub+';margin-bottom:8px;">'+t('settings.correction')+'</div><div style="font-size:22px;font-weight:800;color:'+theme.text+';">'+(l7s.l7_rule_count||0)+'<span style="font-size:12px;font-weight:400;color:'+theme.sub+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='<div style="background:'+theme.cardBg+';padding:16px;border-radius:14px;border:1px solid '+theme.border+';"><div style="font-size:12px;color:'+theme.sub+';margin-bottom:8px;">'+t('settings.behavior')+'</div><div style="font-size:22px;font-weight:800;color:'+(l7s.l7_constraint_count?theme.okText:theme.text)+';">'+(l7s.l7_constraint_count||0)+'<span style="font-size:12px;font-weight:400;color:'+theme.sub+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='<div style="background:'+theme.cardBg+';padding:16px;border-radius:14px;border:1px solid '+theme.border+';"><div style="font-size:12px;color:'+theme.sub+';margin-bottom:8px;">'+t('settings.knowledge')+'</div><div style="font-size:22px;font-weight:800;color:'+theme.text+';">'+(l7s.l8_knowledge_count||0)+'<span style="font-size:12px;font-weight:400;color:'+theme.sub+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='</div>';

 var _evo=config.enabled;
 if(!document.getElementById('nova-spin-style')){var _ss=document.createElement('style');_ss.id='nova-spin-style';_ss.textContent='@keyframes nova-spin{to{transform:rotate(360deg)}}';document.head.appendChild(_ss);}
 var _dotHtml=_evo?'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;border:2.5px solid '+theme.spinner+';border-top-color:transparent;animation:nova-spin 1s linear infinite;vertical-align:middle;margin-right:10px;"></span>':'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:'+theme.toggleOff+';vertical-align:middle;margin-right:10px;"></span>';
 html+='<div style="margin-top:14px;background:'+theme.cardBg+';border:1px solid '+theme.border+';padding:18px 20px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<div><div style="display:flex;align-items:center;"><span style="font-size:16px;font-weight:700;color:'+theme.text+';">'+_dotHtml+(_evo?t('settings.evolving'):t('settings.paused'))+'</span></div><div style="font-size:12px;color:'+theme.sub+';margin-top:6px;">'+(_evo?t('settings.evolve.desc.on'):t('settings.evolve.desc.off'))+'</div></div>';
 html+='<div data-settings-action="toggle" data-settings-key="enabled" style="flex-shrink:0;width:44px;height:24px;border-radius:12px;background:'+(_evo?theme.toggleOn:theme.toggleOff)+';cursor:pointer;position:relative;transition:background 0.2s;"><span style="position:absolute;top:2px;'+(_evo?'right:2px':'left:2px')+';width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:all 0.2s;"></span></div>';
 html+='</div>';

 html+=renderModelManageSection(isLight,theme.text,theme.sub,theme.cardBg,theme.border);
 box.innerHTML=html;
}

function renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor){
 var theme=getSettingsTheme(isLight);
 var html='';
 html+='<div style="margin-top:14px;background:'+theme.cardBg+';border:1px solid '+theme.border+';padding:18px 20px;border-radius:14px;">';
 html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;">';
 html+='<span style="font-size:15px;font-weight:700;color:'+theme.text+';">'+t('settings.models')+'</span>';
 html+='<button type="button" onclick="openModelDialog()" style="padding:6px 14px;border:1px solid '+theme.border+';border-radius:8px;background:rgba(255,255,255,0.03);color:'+theme.text+';font-size:12px;cursor:pointer;">'+t('settings.models.add')+'</button>';
 html+='</div>';
 html+='<div id="modelListBox" style="display:flex;flex-direction:column;gap:8px;">';
 if(!_settingsModels||!_settingsCatalog){
  html+='\u52a0\u8f7d\u4e2d...';
 }else{
  var catalog=_settingsCatalog;
  var models=_settingsModels;
  var currentModel=_settingsCurrentModel;
  var providerConfigured={};
  var uncategorized=[];
  for(var mid in models){
   var pkey=_classifyModelToProvider(mid, models[mid], catalog);
   if(pkey){
    if(!providerConfigured[pkey]) providerConfigured[pkey]=[];
    providerConfigured[pkey].push(mid);
   }else{
    uncategorized.push(mid);
   }
  }
  var currentProvider=null;
  if(currentModel) currentProvider=_classifyModelToProvider(currentModel, models[currentModel], catalog);
  for(var pk in catalog){
   var pi=catalog[pk];
   var configured=providerConfigured[pk]||[];
   var isExpanded=_settingsExpandedProviders[pk]!==undefined?_settingsExpandedProviders[pk]:(pk===currentProvider);
   var hasConfigured=configured.length>0;
   var providerLabel=pk.charAt(0).toUpperCase()+pk.slice(1);
   var activeModelName='';
   for(var ci=0;ci<configured.length;ci++){
    if(configured[ci]===currentModel){
     activeModelName=(models[configured[ci]]||{}).model||configured[ci];
     break;
    }
   }
   var headerBg=isExpanded?theme.headerBg:'transparent';
   var chevron=isExpanded?'\u25BC':'\u25B6';
   html+='<div style="border:1px solid '+theme.border+';border-radius:12px;overflow:hidden;'+(isExpanded?'box-shadow:0 2px 8px rgba(0,0,0,0.12);':'')+'margin-bottom:2px;">';
   html+='<div onclick="_toggleProviderGroup(\''+pk+'\')" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;background:'+headerBg+';transition:background 0.15s;">';
   html+='<span style="font-size:11px;color:'+theme.sub+';width:14px;text-align:center;">'+chevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';flex:1;">'+escapeHtml(providerLabel)+'</span>';
   if(activeModelName){
    html+='<span style="padding:3px 10px;border-radius:5px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+escapeHtml(activeModelName)+'</span>';
   }else if(!hasConfigured){
    html+='<span style="padding:3px 10px;border-radius:5px;background:'+theme.inactiveTagBg+';color:'+theme.inactiveTagText+';font-size:11px;">'+t('settings.models.notconfigured')+'</span>';
   }
   html+='</div>';
   if(isExpanded){
    html+='<div style="padding:6px 14px 12px;display:flex;flex-direction:column;gap:5px;">';
    for(var j=0;j<configured.length;j++){
     var cmid=configured[j];
     var cm=models[cmid]||{};
     var isCurrent=cmid===currentModel;
     var rowBg=isCurrent?theme.currentRowBg:theme.softRowBg;
     var rowBorder=isCurrent?theme.currentRowBorder:theme.border;
     var visionDot=cm.vision?'<span style="width:6px;height:6px;border-radius:50%;background:#8a948f;display:inline-block;margin-left:4px;" title="'+t('settings.models.vision')+'"></span>':'';
     var checkMark=isCurrent?'<span style="color:'+theme.currentCheck+';font-size:14px;margin-right:6px;">\u2713</span>':'';
     html+='<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;background:'+rowBg+';border:1px solid '+rowBorder+';border-radius:10px;transition:all 0.15s;">';
     html+=checkMark;
     html+='<span style="font-size:13px;font-weight:'+(isCurrent?'700':'500')+';color:'+theme.text+';flex:1;">'+escapeHtml(cm.model||cmid)+'</span>';
     html+=visionDot;
     html+='<span style="font-size:11px;color:'+theme.sub+';margin-right:4px;">'+escapeHtml(cmid)+'</span>';
     if(isCurrent){
      html+='<span style="padding:3px 10px;border-radius:5px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
     }else{
      html+='<button onclick="switchModel(\''+escapeHtml(cmid)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;" onmouseenter="this.style.background=\''+theme.actionText+'\';this.style.color=\'#fff\'" onmouseleave="this.style.background=\'none\';this.style.color=\''+theme.actionText+'\'">'+t('settings.models.activate')+'</button>';
     }
     html+='<button onclick="openModelDialog(\''+escapeHtml(cmid)+'\')" style="padding:3px 8px;border:1px solid '+theme.border+';border-radius:5px;background:none;color:'+theme.sub+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
     html+='</div>';
    }
    var configuredIds={};
    for(var k=0;k<configured.length;k++){
     configuredIds[configured[k].toLowerCase()]=true;
     var mname=((models[configured[k]]||{}).model||'').toLowerCase();
     if(mname) configuredIds[mname]=true;
    }
    var catalogModels=pi.models||[];
    for(var m=0;m<catalogModels.length;m++){
     var catModel=catalogModels[m];
     if(configuredIds[catModel.id.toLowerCase()]) continue;
     html+='<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:'+theme.softDashedBg+';border:1px dashed '+theme.softDashedBorder+';border-radius:10px;">';
     html+='<span style="font-size:13px;color:'+theme.sub+';flex:1;">'+escapeHtml(catModel.id)+'<span style="font-size:11px;margin-left:6px;opacity:0.7;">'+escapeHtml(catModel.desc)+'</span></span>';
     if(hasConfigured){
      html+='<button onclick="_quickAddModel(\''+escapeHtml(pk)+'\',\''+escapeHtml(catModel.id)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;" onmouseenter="this.style.background=\''+theme.actionText+'\';this.style.color=\'#fff\'" onmouseleave="this.style.background=\'none\';this.style.color=\''+theme.actionText+'\'">'+t('settings.models.quickadd')+'</button>';
     }
     html+='</div>';
    }
    html+='</div>';
   }
   html+='</div>';
  }
  if(uncategorized.length>0){
   var uncExpanded=_settingsExpandedProviders['_other']!==undefined?_settingsExpandedProviders['_other']:(!currentProvider);
   var uncChevron=uncExpanded?'\u25BC':'\u25B6';
   html+='<div style="border:1px solid '+theme.border+';border-radius:12px;overflow:hidden;margin-bottom:2px;">';
   html+='<div onclick="_toggleProviderGroup(\'_other\')" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;">';
   html+='<span style="font-size:11px;color:'+theme.sub+';width:14px;text-align:center;">'+uncChevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';flex:1;">Other</span>';
   html+='</div>';
   if(uncExpanded){
    html+='<div style="padding:6px 14px 12px;display:flex;flex-direction:column;gap:5px;">';
    for(var u=0;u<uncategorized.length;u++){
     var umid=uncategorized[u];
     var um=models[umid]||{};
     var uCurrent=umid===currentModel;
     var uRowBg=uCurrent?theme.currentRowBg:theme.softRowBg;
     var uRowBorder=uCurrent?theme.currentRowBorder:theme.border;
     html+='<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;background:'+uRowBg+';border:1px solid '+uRowBorder+';border-radius:10px;">';
     if(uCurrent) html+='<span style="color:'+theme.currentCheck+';font-size:14px;margin-right:6px;">\u2713</span>';
     html+='<span style="font-size:13px;font-weight:'+(uCurrent?'700':'500')+';color:'+theme.text+';flex:1;">'+escapeHtml(um.model||umid)+'</span>';
     html+='<span style="font-size:11px;color:'+theme.sub+';margin-right:4px;">'+escapeHtml(umid)+'</span>';
     if(uCurrent){
      html+='<span style="padding:3px 10px;border-radius:5px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
     }else{
      html+='<button onclick="switchModel(\''+escapeHtml(umid)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:500;">'+t('settings.models.activate')+'</button>';
     }
     html+='<button onclick="openModelDialog(\''+escapeHtml(umid)+'\')" style="padding:3px 8px;border:1px solid '+theme.border+';border-radius:5px;background:none;color:'+theme.sub+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
     html+='</div>';
    }
    html+='</div>';
   }
   html+='</div>';
  }
 }
 html+='</div></div>';
 return html;
}

function openModelDialog(editId){
 var isEdit=!!editId;
 var m=isEdit?(_settingsModels[editId]||{}):{};
 var isCurrent=isEdit&&editId===_settingsCurrentModel;
 var isLight=document.body.classList.contains('light');
 var theme=getSettingsTheme(isLight);
 var labelStyle='font-size:12px;font-weight:600;color:'+theme.sub+';margin-bottom:5px;';
 var inputStyle='width:100%;padding:10px 14px;border-radius:10px;border:1px solid '+theme.border+';background:'+theme.dialogInputBg+';color:'+theme.text+';outline:none;font-size:13px;box-sizing:border-box;';
 var title=isEdit?t('settings.models.edit'):t('settings.models.add');

 var overlay=document.createElement('div');
 overlay.id='modelDialog';
 overlay.style.cssText='position:fixed;inset:0;background:'+theme.dialogOverlay+';z-index:9999;display:flex;align-items:center;justify-content:center;';

 var html='<div style="background:'+theme.dialogBg+';border:1px solid '+theme.border+';border-radius:16px;padding:24px;width:420px;max-width:90vw;">';
 html+='<div style="font-size:16px;font-weight:600;color:'+theme.text+';margin-bottom:18px;">'+escapeHtml(title)+'</div>';
 html+='<div style="display:flex;flex-direction:column;gap:14px;">';
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.id')+'</div>';
 html+='<input id="mdlId" value="'+escapeHtml(isEdit?editId:'')+'" placeholder="gpt-4o, claude-3 ..." style="'+inputStyle+(isEdit?'opacity:0.5;cursor:not-allowed;':'')+'\"'+(isEdit?' disabled':'')+'></div>';
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.name')+'</div>';
 html+='<input id="mdlName" value="'+escapeHtml(m.model||'')+'" placeholder="'+t('settings.models.field.name.hint')+'" style="'+inputStyle+'"></div>';
 html+='<div><div style="'+labelStyle+'">Base URL</div>';
 html+='<input id="mdlUrl" value="'+escapeHtml(m.base_url||'')+'" placeholder="https://api.openai.com/v1" style="'+inputStyle+'"></div>';
 html+='<div><div style="'+labelStyle+'">API Key</div>';
 var maskedKey='';
 var fullKey='';
 if(isEdit&&m.api_key){var k=m.api_key;fullKey=k;maskedKey=k.length>14?(k.slice(0,6)+'****'+k.slice(-4)):k.replace(/./g,'*');}
 html+='<div style="position:relative;"><input id="mdlKey" value="" placeholder="'+(isEdit?(maskedKey||t('settings.models.field.key.hint')):'sk-...')+'" style="'+inputStyle+';padding-right:40px;">';
 if(isEdit&&fullKey){html+='<button type="button" id="mdlKeyToggle" onclick="(function(b){var inp=document.getElementById(\'mdlKey\');var showing=b.getAttribute(\'data-show\')===\'1\';if(!showing){inp.value=\''+escapeHtml(fullKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94\\\'/><path d=\\\'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19\\\'/><line x1=\\\'1\\\' y1=\\\'1\\\' x2=\\\'23\\\' y2=\\\'23\\\'/></svg>\';b.setAttribute(\'data-show\',\'1\');}else{inp.value=\'\';inp.placeholder=\''+escapeHtml(maskedKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\\\'/><circle cx=\\\'12\\\' cy=\\\'12\\\' r=\\\'3\\\'/></svg>\';b.setAttribute(\'data-show\',\'0\');}})(this)" data-show="0" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;opacity:0.5;color:'+theme.sub+';display:flex;align-items:center;" title="Show/Hide"><svg width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\'><path d=\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\'/><circle cx=\'12\' cy=\'12\' r=\'3\'/></svg></button>';}
 html+='</div></div>';
 var checked=m.vision?'checked':'';
 html+='<label style="display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none;">';
 html+='<input id="mdlVision" type="checkbox" '+checked+' style="width:16px;height:16px;accent-color:'+(isLight?'#7a7267':'#9e907c')+';">';
 html+='<span style="font-size:13px;color:'+theme.text+';">'+t('settings.models.vision')+'</span></label>';
 html+='<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">';
 if(isEdit&&!isCurrent){
  html+='<button onclick="_modelDialogDelete(\''+escapeHtml(editId)+'\')" style="padding:8px 14px;border-radius:8px;border:1px solid '+theme.dangerSoftBorder+';background:transparent;color:'+theme.dangerSoftText+';cursor:pointer;font-size:12px;opacity:0.7;transition:opacity 0.15s;" onmouseenter="this.style.opacity=\'1\'" onmouseleave="this.style.opacity=\'0.7\'">'+t('settings.models.delete')+'</button>';
 }
 html+='<div style="flex:1;"></div>';
 html+='<button onclick="document.getElementById(\'modelDialog\').remove()" style="padding:8px 18px;border-radius:8px;border:1px solid '+theme.border+';background:transparent;color:'+theme.text+';cursor:pointer;font-size:13px;">'+t('cancel')+'</button>';
 html+='<button onclick="_modelDialogSave(\''+escapeHtml(isEdit?editId:'')+'\')" style="padding:8px 18px;border-radius:8px;border:none;background:'+theme.actionPrimary+';color:'+theme.actionPrimaryText+';cursor:pointer;font-size:13px;">'+t('save')+'</button>';
 html+='</div></div></div>';

 overlay.innerHTML=html;
 document.body.appendChild(overlay);
 overlay.addEventListener('click',function(e){if(e.target===overlay)overlay.remove();});
 var first=isEdit?document.getElementById('mdlName'):document.getElementById('mdlId');
 if(first)setTimeout(function(){first.focus();},50);
}


function switchModel(mid){
 if(mid===_settingsCurrentModel) return;
 // 即时视觉反馈：禁用所有启用按钮
 var btns=document.querySelectorAll('[onclick*="switchModel"]');
 btns.forEach(function(el){el.style.pointerEvents='none';el.style.opacity='0.5';});
 var clicked=null;
 btns.forEach(function(el){if(el.getAttribute('onclick').indexOf(mid)!==-1){clicked=el;}});
 if(clicked){clicked.style.opacity='1';clicked.textContent=t('settings.models.switching');}
 fetch('/model/'+encodeURIComponent(mid),{method:'POST'})
  .then(function(r){return r.json();})
  .then(function(d){
   if(d.ok||d.model){
    _settingsCurrentModel=mid;
    window._novaCurrentModel=mid;
    var el=document.getElementById('modelName');
    var _sw=(_settingsModels[mid]||{}).model||mid;
    if(el) el.textContent=_sw;
    if(typeof updateImageBtnState==='function') updateImageBtnState();
    // 延迟刷新，让用户先看到切换成功
    setTimeout(function(){loadSettingsModels();},300);
   }else{
    alert(d.error||'\u5207\u6362\u5931\u8d25');
    loadSettingsModels();
   }
  }).catch(function(){
   alert('\u5207\u6362\u5931\u8d25');
   loadSettingsModels();
  });
}

