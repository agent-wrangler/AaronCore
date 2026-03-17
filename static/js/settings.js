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

function renderSettingsToggleCard(title, desc, key, value, isLight){
 var cardBg=isLight?'#ffffff':'rgba(36,36,40,0.95)';
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
  ? (isLight?'linear-gradient(135deg,#6b7280,#8b5cf6)':'linear-gradient(135deg,#6b7280,#8b5cf6)')
  : (isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)');
 var actionColor=value?'#fff':(isLight?'#334155':'#e2e8f0');
 return '<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:12px;min-width:0;box-shadow:'+(isLight?'0 8px 24px rgba(0,0,0,0.06)':'0 10px 28px rgba(0,0,0,0.14)')+';">'
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
  ? (isLight?'linear-gradient(135deg,#eef2ff,#f8fafc)':'linear-gradient(135deg,rgba(100,100,110,0.18),rgba(28,28,30,0.92))')
  : (isLight?'#ffffff':'rgba(36,36,40,0.92)');
 var borderColor=active
  ? (isLight?'rgba(120,120,130,0.22)':'rgba(150,150,160,0.28)')
  : (isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)');
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var btnBg=active
  ? (isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)')
  : 'linear-gradient(135deg,#6b7280,#8b5cf6)';
 var btnColor=active?(isLight?'#334155':'#e2e8f0'):'#fff';
 return '<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:10px;box-shadow:'+(isLight?'0 8px 24px rgba(0,0,0,0.06)':'0 10px 28px rgba(0,0,0,0.14)')+';">'
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
  : (primary?'linear-gradient(135deg,#6b7280,#8b5cf6)':(isLight?'rgba(226,232,240,0.9)':'rgba(15,23,42,0.48)'));
 var color=disabled?'#94a3b8':(primary?'#fff':(isLight?'#334155':'#e2e8f0'));
 return '<button type="button" data-settings-action="'+action+'"'+(key?' data-settings-key="'+escapeHtml(key)+'"':'')+' style="position:relative;z-index:1;padding:10px 12px;border:none;border-radius:12px;background:'+bg+';color:'+color+';font-size:13px;font-weight:700;cursor:'+(disabled?'default':'pointer')+';'+(disabled?'opacity:0.68;pointer-events:none;':'')+'">'+escapeHtml(label)+'</button>';
}

function renderSettingsMetaPill(label, tone, isLight){
 var palette={
  accent:isLight?['rgba(100,100,110,0.12)','#374151']:['rgba(120,120,130,0.18)','#c7d2fe'],
  ok:isLight?['rgba(16,185,129,0.12)','#047857']:['rgba(16,185,129,0.18)','#86efac'],
  warn:isLight?['rgba(245,158,11,0.14)','#b45309']:['rgba(245,158,11,0.16)','#fde68a'],
  danger:isLight?['rgba(239,68,68,0.12)','#b91c1c']:['rgba(239,68,68,0.18)','#fca5a5'],
  muted:isLight?['rgba(148,163,184,0.12)','#475569']:['rgba(148,163,184,0.14)','#cbd5e1']
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
 var bg=isLight?'rgba(226,232,240,0.82)':'rgba(15,23,42,0.48)';
 var color=isLight?'#334155':'#cbd5e1';
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
 var cardBg=active?(isLight?'linear-gradient(135deg,#eef2ff,#f8fafc)':'linear-gradient(135deg,rgba(100,100,110,0.18),rgba(28,28,30,0.92))'):(isLight?'#ffffff':'rgba(36,36,40,0.92)');
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
 html+='<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:18px;padding:16px;box-shadow:'+(active?(isLight?'0 10px 30px rgba(100,100,110,0.08)':'0 12px 30px rgba(0,0,0,0.18)'):(isLight?'0 8px 24px rgba(0,0,0,0.05)':'0 10px 24px rgba(0,0,0,0.12)'))+';">';
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
 var cardBg=isLight?'#ffffff':'rgba(36,36,40,0.95)';
 var borderColor=isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)';
 var safeReports=Array.isArray(reports)?reports:[];
 var list=safeReports.slice(0,10);
 var activeId=settingsPanelState.activeRepairId||((list[0]&&list[0].id)||'');
 var html='';
 html+='<div style="margin-top:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:16px 18px;border-radius:14px;">';
 html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">';
 html+='<div style="display:flex;align-items:center;gap:10px;"><span style="font-size:15px;font-weight:700;color:'+textColor+';">\u4fee\u590d\u63d0\u6848</span><span style="font-size:12px;color:'+subColor+';">'+(list.length?(list.length+'\u6761'):'暂无')+'</span></div>';
 html+='<div style="display:flex;gap:8px;">'+renderSettingsActionButton('\u5237\u65b0','self-repair-refresh','',isLight,'secondary',!!settingsPanelState.repairActionBusy)+'</div>';
 html+='</div>';
 if(!list.length){
  html+='<div style="margin-top:10px;font-size:12px;color:'+subColor+';"> AI Agent \u53d1\u73b0\u95ee\u9898\u65f6\u4f1a\u81ea\u52a8\u751f\u6210\u4fee\u590d\u63d0\u6848\uff0c\u5728\u8fd9\u91cc\u5ba1\u6838\u3002</div>';
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
 var cardBg=isLight?'#ffffff':'rgba(36,36,40,0.95)';
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var borderColor=isLight?'rgba(148,163,184,0.22)':'rgba(255,255,255,0.06)';
 var html='';

 // ── 区块1：状态总览（4个数字）──
 html+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;">';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">\u7ea0\u9519\u8bb0\u5fc6</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.l7_rule_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">\u6761</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">\u884c\u4e3a\u4fee\u6b63</div><div style="font-size:22px;font-weight:800;color:'+(l7s.l7_constraint_count?'#10b981':textColor)+';">'+(l7s.l7_constraint_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">\u6761</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">\u5df2\u5b66\u77e5\u8bc6</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.l8_knowledge_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">\u6761</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">\u4fee\u590d\u63d0\u6848</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.repair_report_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">\u6761</span></div></div>';
 html+='</div>';

 // ── 区块2：持续进化 ──
 var _evo=config.enabled;
 if(!document.getElementById('nova-spin-style')){var _ss=document.createElement('style');_ss.id='nova-spin-style';_ss.textContent='@keyframes nova-spin{to{transform:rotate(360deg)}}';document.head.appendChild(_ss);}
 var _dotHtml=_evo?'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;border:2.5px solid '+(isLight?'#7c3aed':'#a78bfa')+';border-top-color:transparent;animation:nova-spin 1s linear infinite;vertical-align:middle;margin-right:10px;"></span>':'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:'+(isLight?'#cbd5e1':'#475569')+';vertical-align:middle;margin-right:10px;"></span>';
 html+='<div style="margin-top:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:18px 20px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<div><div style="display:flex;align-items:center;"><span style="font-size:16px;font-weight:700;color:'+textColor+';">'+_dotHtml+(_evo?'\u6301\u7eed\u8fdb\u5316\u4e2d':'\u8fdb\u5316\u5df2\u6682\u505c')+'</span></div><div style="font-size:12px;color:'+subColor+';margin-top:6px;">'+(_evo?'AI Agent \u4f1a\u81ea\u4e3b\u5b66\u4e60\u65b0\u77e5\u8bc6\u3001\u8bb0\u4f4f\u4f60\u7684\u7ea0\u6b63\u3001\u4e3b\u52a8\u4fee\u590d\u53d1\u73b0\u7684\u95ee\u9898':'\u5df2\u6682\u505c\u81ea\u4e3b\u5b66\u4e60\u548c\u81ea\u6211\u4fee\u590d\uff0cAI Agent \u4e0d\u4f1a\u79ef\u7d2f\u65b0\u7ecf\u9a8c')+'</div></div>';
 html+='<div data-settings-action="toggle" data-settings-key="enabled" style="flex-shrink:0;width:44px;height:24px;border-radius:12px;background:'+(_evo?(isLight?'#10b981':'#34d399'):(isLight?'#cbd5e1':'#475569'))+';cursor:pointer;position:relative;transition:background 0.2s;"><span style="position:absolute;top:2px;'+(_evo?'right:2px':'left:2px')+';width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:all 0.2s;"></span></div>';
 html+='</div>';

 // ── 区块3：修复提案审核 ──
 html+=renderSelfRepairReviewSection(config,selfRepairStatus,selfRepairReports,isLight);

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
 chat.innerHTML='<div class="settings-page" style="padding:20px;overflow:auto;height:100%;width:100%;position:relative;z-index:1;"><h2 class="page-title" style="margin-bottom:15px;">⚙️ 设置</h2><div id="settingsBox">加载中...</div></div>';
 settingsPanelState.notice='';
 settingsPanelState.error='';
 refreshSettingsData(isLight).catch(function(){
  settingsPanelState.error='设置数据加载失败';
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

