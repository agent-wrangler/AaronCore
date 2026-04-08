// Settings panel state, autolearn controls, and base settings loading
// Source: settings.js lines 1-654

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
 return {
  cardBg:'var(--surface-panel)',
  cardBgActive:'var(--surface-panel-strong)',
  border:'var(--border-panel)',
  borderStrong:'var(--border-panel-strong)',
  text:'var(--text-primary)',
  sub:'var(--text-label)',
  mutedBg:'var(--surface-panel-soft)',
  mutedText:'var(--text-secondary)',
  actionPrimary:'linear-gradient(135deg,var(--tone-amber),var(--tone-amber-strong))',
  actionPrimaryText:'var(--bg-main)',
  actionSecondary:'var(--surface-panel-soft)',
  actionSecondaryText:'var(--text-secondary)',
  stateOnBg:'var(--tone-sage-soft)',
  stateOnText:'var(--tone-sage)',
  stateOffBg:'var(--surface-panel-soft)',
  stateOffText:'var(--text-secondary)',
  accentBg:'var(--tone-steel-soft)',
  accentText:'var(--tone-steel)',
  okBg:'var(--tone-sage-soft)',
  okText:'var(--tone-sage)',
  warnBg:'var(--tone-amber-soft)',
  warnText:'var(--tone-amber)',
  dangerBg:'var(--tone-danger-soft)',
  dangerText:'var(--tone-danger)',
  mutedPillBg:'var(--surface-panel-soft)',
  mutedPillText:'var(--text-secondary)',
  pathBg:'var(--surface-panel-soft)',
  pathText:'var(--text-secondary)',
  headerBg:'var(--surface-panel-soft)',
  currentRowBg:'var(--tone-amber-soft)',
  currentRowBorder:'var(--tone-amber-border)',
  softRowBg:'var(--surface-panel-soft)',
  softDashedBg:'var(--surface-panel-soft)',
  softDashedBorder:'var(--border-panel)',
  successBg:'var(--tone-sage-soft)',
  successText:'var(--tone-sage)',
  inactiveTagBg:'var(--surface-panel-soft)',
  inactiveTagText:'var(--text-label)',
  actionBorder:'var(--tone-amber-border)',
  actionText:'var(--text-secondary)',
  dialogBg:'var(--surface-panel-strong)',
  dialogInputBg:'var(--surface-panel-soft)',
  dialogOverlay:isLight?'rgba(34,29,24,0.18)':'rgba(15,14,12,0.58)',
  spinner:'var(--tone-amber)',
  toggleOn:'var(--tone-sage)',
  toggleOff:'var(--border-panel-strong)',
  currentCheck:'var(--tone-sage)',
  dangerLine:'var(--tone-danger)',
  dangerSoftBorder:'var(--tone-danger-border)',
  dangerSoftText:'var(--tone-danger)'
 };
}

function renderSettingsToggleCard(title, desc, key, value, isLight){
 var theme=getSettingsTheme(isLight);
 var cardBg=theme.cardBg;
 var borderColor=value?theme.borderStrong:theme.border;
 var titleColor=theme.text;
 var subColor=theme.sub;
 var stateBg=value?theme.stateOnBg:theme.stateOffBg;
 var stateColor=value?theme.stateOnText:theme.stateOffText;
 var actionBg=value?theme.actionPrimary:theme.actionSecondary;
 var actionColor=value?theme.actionPrimaryText:theme.actionSecondaryText;
 return '<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:12px;min-width:0;box-shadow:var(--shadow-card);">'
  +'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">'
  +'<div style="min-width:0;"><div style="font-size:15px;font-weight:700;color:'+titleColor+';margin-bottom:4px;">'+escapeHtml(title)+'</div><div style="font-size:12px;line-height:1.7;color:'+subColor+';">'+escapeHtml(desc)+'</div></div>'
  +'<span style="flex-shrink:0;padding:6px 10px;border-radius:999px;background:'+stateBg+';color:'+stateColor+';font-size:12px;font-weight:700;">'+(value?'宸插紑鍚?:'宸插叧闂?)+'</span>'
  +'</div>'
  +'<button type="button" data-settings-action="toggle" data-settings-key="'+escapeHtml(key)+'" style="margin-top:auto;padding:10px 12px;border:none;border-radius:12px;background:'+actionBg+';color:'+actionColor+';font-size:13px;font-weight:700;cursor:pointer;box-shadow:'+(value?'var(--shadow-card)':'none')+';">'+(value?'淇濇寔寮€鍚?:'鐜板湪寮€鍚?)+'</button>'
  +'</div>';
}

function autolearnPresets(){
 return {
  basic:{label:'鍩虹',desc:'涓嶈仈缃戝鏂扮煡璇嗭紝涓嶆暣鐞嗕慨澶嶆彁妗堛€傚弽棣堣蹇嗗缁堝紑鍚紝AI Agent 浼氳浣忎綘璇磋繃鐨勭籂姝ｃ€?,patch:{enabled:true,allow_knowledge_write:true,allow_web_search:false,allow_self_repair_planning:false,allow_self_repair_test_run:false,allow_self_repair_auto_apply:false,self_repair_apply_mode:'confirm'}},
  advanced:{label:'杩涢樁',desc:'浼氳仈缃戣ˉ瀛︾煡璇嗭紝浼氭暣鐞嗕慨澶嶆彁妗堝苟鍏堣窇楠岃瘉銆傜湡姝ｆ敼浠ｇ爜鍓嶅厛鍋滀笅鏉ョ粰浣犵湅銆?,patch:{enabled:true,allow_knowledge_write:true,allow_web_search:true,allow_self_repair_planning:true,allow_self_repair_test_run:true,allow_self_repair_auto_apply:false,self_repair_apply_mode:'confirm'}},
  deep:{label:'娣卞害',desc:'鍖呭惈杩涢樁鐨勫叏閮ㄨ兘鍔涳紝浣庨闄╅棶棰樺厑璁稿悗鍙拌嚜鍔ㄨ惤鍦帮紝涓珮椋庨櫓鏀瑰姩浠嶇劧浼氬仠涓嬫潵銆?,patch:{enabled:true,allow_knowledge_write:true,allow_web_search:true,allow_self_repair_planning:true,allow_self_repair_test_run:true,allow_self_repair_auto_apply:true,self_repair_apply_mode:'confirm'}}
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
 return {key:'custom',label:'鑷畾涔夌粍鍚?,desc:'褰撳墠閰嶇疆涓嶅畬鍏ㄧ瓑浜庡熀纭€銆佽繘闃躲€佹繁搴︿笁妗ｄ腑鐨勪换鎰忎竴妗ｃ€?};
}

function renderAutolearnPresetCard(key, preset, currentKey, isLight){
 var theme=getSettingsTheme(isLight);
 var active=key===currentKey;
 var cardBg=active?theme.cardBgActive:theme.cardBg;
 var borderColor=active?theme.borderStrong:theme.border;
 var textColor=theme.text;
 var subColor=theme.sub;
 var btnBg=active?theme.actionSecondary:theme.actionPrimary;
 var btnColor=active?theme.actionSecondaryText:theme.actionPrimaryText;
 return '<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:10px;box-shadow:var(--shadow-card);">'
  +'<div style="font-size:16px;font-weight:800;color:'+textColor+';">'+escapeHtml(preset.label)+'</div>'
  +'<div style="font-size:12px;line-height:1.7;color:'+subColor+';flex:1;">'+escapeHtml(preset.desc)+'</div>'
  +'<button type="button" data-settings-action="preset" data-settings-key="'+escapeHtml(key)+'" style="padding:10px 12px;border:none;border-radius:12px;background:'+btnBg+';color:'+btnColor+';font-size:13px;font-weight:700;cursor:pointer;">'+(active?'淇濇寔杩欎竴妗?:'鍒囧埌杩欎竴妗?)+'</button>'
  +'</div>';
}

function selfRepairOutcome(status){
 var safe=status&&typeof status==='object'?status:{};
 var lastAction=String(safe.last_action||safe.last_outcome||'').trim();
 if(lastAction.indexOf('applied')===0||lastAction==='auto_applied')
  return {label:'鑷姩淇敼',title:'鑷姩淇敼',desc:'宸茬粡鐪熺殑鍔ㄦ墜鏀逛簡锛屽苟鍙兘閫氳繃楠岃瘉鎴栬Е鍙戝洖婊氥€?};
 if(lastAction==='proposal_ready'||lastAction==='preview_ready'||lastAction.indexOf('plan')>=0)
  return {label:'鐢熸垚鏂规',title:'鐢熸垚鏂规',desc:'宸茬粡鏁寸悊鍑轰慨澶嶆彁妗堟垨鏀规硶棰勮銆?};
 if(lastAction==='skill_generated'||lastAction==='new_skill')
  return {label:'瑙ｉ攣鏂版妧鑳?,title:'瑙ｉ攣鏂版妧鑳?,desc:'褰撳墠涓嶆槸鏃ュ父榛樿涓婚摼锛岄€氬父淇濇寔鍏抽棴銆?};
 return {label:'绉疮缁忛獙',title:'绉疮缁忛獙',desc:'宸茬粡璁颁綇杩欐鍙嶉锛屼絾杩樻病杩涘叆鍏蜂綋淇硶钀藉湴銆?};
}

function toggleAutolearnAdvanced(){
 settingsPanelState.showAdvancedLearning=!settingsPanelState.showAdvancedLearning;
 renderSettingsPage(document.body.classList.contains('light'));
}

function formatSettingsTimestamp(value){
 var raw=String(value||'').trim();
 if(!raw) return '鍒氬垰';
 return raw.replace('T',' ').replace(/\.\d+$/,'').slice(0,16);
}

function renderSettingsActionButton(label, action, key, isLight, emphasis, disabled){
 var theme=getSettingsTheme(isLight);
 var primary=emphasis==='primary';
 var bg=disabled?theme.actionSecondary:(primary?theme.actionPrimary:theme.actionSecondary);
 var color=disabled?theme.sub:(primary?theme.actionPrimaryText:theme.actionSecondaryText);
 return '<button type="button" data-settings-action="'+action+'"'+(key?' data-settings-key="'+escapeHtml(key)+'"':'')+' style="position:relative;z-index:1;padding:10px 12px;border:none;border-radius:12px;background:'+bg+';color:'+color+';font-size:13px;font-weight:700;cursor:'+(disabled?'default':'pointer')+';'+(disabled?'opacity:0.68;pointer-events:none;':'')+'">'+escapeHtml(label)+'</button>';
}

function renderSettingsMetaPill(label, tone, isLight){
 var theme=getSettingsTheme(isLight);
 var palette={
  accent:[theme.accentBg,theme.accentText],
  ok:[theme.okBg,theme.okText],
  warn:[theme.warnBg,theme.warnText],
  danger:[theme.dangerBg,theme.dangerText],
  muted:[theme.mutedPillBg,theme.mutedPillText]
 };
 var picked=palette[tone]||palette.muted;
 return '<span style="padding:6px 10px;border-radius:999px;background:'+picked[0]+';color:'+picked[1]+';font-size:12px;font-weight:700;">'+escapeHtml(label)+'</span>';
}

function selfRepairFlowSummary(config){
 var normalized=mergeAutolearnConfig(config||{});
 var planning=normalized.allow_self_repair_planning?'鏂扮殑璐熷弽棣堜細缁х画鏁寸悊鎴愪慨澶嶆彁妗?:'鏂扮殑璐熷弽棣堟殏鏃朵笉浼氱户缁敓鎴愪慨澶嶆彁妗?;
 var lowRisk=normalized.allow_self_repair_auto_apply?'浣庨闄╄ˉ涓佸厑璁稿悗鍙拌嚜鍔ㄨ惤鍦?:'浣庨闄╄ˉ涓佷篃浼氬厛鍋滃湪鎻愭闃舵';
 var highRisk=normalized.self_repair_apply_mode==='suggest'?'涓珮椋庨櫓鏀瑰姩浼氬厛缁欎綘鐪嬫柟妗?:'涓珮椋庨櫓鏀瑰姩浼氬仠涓嬫潵绛変綘纭涓€娆?;
 return planning+'銆?+lowRisk+'锛?+highRisk+'銆?;
}

function selfRepairReportStatusMeta(report){
 var safe=report&&typeof report==='object'?report:{};
 var preview=safe.patch_preview&&typeof safe.patch_preview==='object'?safe.patch_preview:{};
 var apply=safe.apply_result&&typeof safe.apply_result==='object'?safe.apply_result:{};
 var status=String(safe.status||'').trim();
 var previewStatus=String(preview.status||'').trim();
 var applyStatus=String(apply.status||'').trim();
 if(applyStatus.indexOf('rolled_back')===0||status.indexOf('rolled_back')===0) return {label:'宸茶嚜鍔ㄥ洖婊?,tone:'warn'};
 if(applyStatus==='applied'||applyStatus==='applied_without_validation'||status==='applied'||status==='applied_without_validation') return {label:'宸插簲鐢?,tone:'ok'};
 if(previewStatus==='preview_failed'||status==='needs_attention') return {label:'闇€瑕佸鐞?,tone:'danger'};
 if(previewStatus==='preview_ready') return {label:(preview.confirmation_required===false?'鍙洿鎺ヨ惤鍦?:'寰呬綘瀹℃牳'),tone:(preview.confirmation_required===false?'ok':'accent')};
 if(status==='awaiting_confirmation') return {label:'寰呬綘纭',tone:'accent'};
 if(status==='proposal_ready') return {label:'鎻愭宸插氨缁?,tone:'accent'};
 return {label:'宸茶繘鍏ヤ慨澶嶉摼璺?,tone:'muted'};
}

function selfRepairRiskMeta(report){
 var safe=report&&typeof report==='object'?report:{};
 var preview=safe.patch_preview&&typeof safe.patch_preview==='object'?safe.patch_preview:{};
 var level=String(preview.risk_level||safe.risk_level||'').trim();
 if(level==='low') return {label:'浣庨闄?,tone:'ok'};
 if(level==='medium') return {label:'涓闄?,tone:'warn'};
 if(level==='high') return {label:'楂橀闄?,tone:'danger'};
 return {label:'椋庨櫓寰呰瘎浼?,tone:'muted'};
}

function summarizeSelfRepairValidation(report){
 var safe=report&&typeof report==='object'?report:{};
 var applyValidation=((safe.apply_result||{}).validation)||{};
 var baseValidation=safe.validation||{};
 var runs=[];
 if(applyValidation&&applyValidation.ran){
  runs=Array.isArray(applyValidation.test_runs)?applyValidation.test_runs:[];
  if(applyValidation.all_passed===true) return '搴旂敤鍚庨獙璇佸凡閫氳繃'+(runs.length?'锛屽叡 '+runs.length+' 椤?:'');
  if(applyValidation.all_passed===false) return '搴旂敤鍚庨獙璇佹湭閫氳繃锛屽凡鑷姩鍥炴粴'+(runs.length?'锛屽叡 '+runs.length+' 椤?:'');
  return '宸茬粡鎵ц搴旂敤鍚庣殑楠岃瘉';
 }
 if(baseValidation&&baseValidation.ran){
  runs=Array.isArray(baseValidation.test_runs)?baseValidation.test_runs:[];
  if(baseValidation.all_passed===true) return '鎻愭棰勬宸查€氳繃'+(runs.length?'锛屽叡 '+runs.length+' 椤?:'');
  if(baseValidation.all_passed===false) return '鎻愭棰勬鏈€氳繃锛岄渶瑕佸厛澶勭悊'+(runs.length?'锛屽叡 '+runs.length+' 椤?:'');
  return '宸茬粡鎵ц鎻愭棰勬';
 }
 return '杩欐潯鎻愭杩樻病鏈夎窇鍑洪獙璇佺粨鏋?;
}

function renderRepairPathList(paths, isLight, emptyText){
 var theme=getSettingsTheme(isLight);
 var list=(Array.isArray(paths)?paths:[]).map(function(item){ return String(item||'').trim(); }).filter(Boolean).slice(0,6);
 var subColor=theme.sub;
 if(!list.length) return '<div style="font-size:12px;color:'+subColor+';">'+escapeHtml(emptyText||'鏆傛椂娌℃湁')+'</div>';
 var bg=theme.pathBg;
 var color=theme.pathText;
 return '<div style="display:flex;flex-wrap:wrap;gap:8px;">'+list.map(function(path){
  return '<span style="padding:6px 10px;border-radius:999px;background:'+bg+';color:'+color+';font-size:12px;font-family:Consolas,monospace;">'+escapeHtml(path)+'</span>';
 }).join('')+'</div>';
}

function renderRepairDetailRow(label, bodyHtml, isLight){
 var subColor=getSettingsTheme(isLight).sub;
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
 settingsPanelState.notice=(action==='preview'?'姝ｅ湪鐢熸垚鏀瑰姩棰勮...':(action==='apply'?'姝ｅ湪搴旂敤淇鎻愭...':'姝ｅ湪鍒锋柊淇鎻愭...'));
 settingsPanelState.repairActionBusy=action+':'+targetId;
 if(targetId) settingsPanelState.activeRepairId=targetId;
 renderSettingsPage(isLight);
 if(action==='refresh'){
  settingsPanelState.repairActionBusy='';
  refreshSettingsData(isLight,'淇鎻愭鍒楄〃宸插埛鏂?).catch(function(){
   settingsPanelState.error='淇鎻愭鍒锋柊澶辫触锛岃绋嶅悗鍐嶈瘯';
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
  var notice='淇鎻愭鐘舵€佸凡鏇存柊';
  if(action==='preview') notice=previewStatus==='preview_ready'?'鏀瑰姩棰勮宸茬粡鍑嗗濂戒簡':'鏀瑰姩棰勮鐢熸垚澶辫触锛岃鐪嬪崱鐗囪鎯?;
  else if(applyStatus==='applied'||applyStatus==='applied_without_validation') notice='淇鎻愭宸茬粡搴旂敤';
  else if(applyStatus.indexOf('rolled_back')===0) notice='淇鎵ц鍚庢湭閫氳繃楠岃瘉锛屽凡缁忚嚜鍔ㄥ洖婊?;
  else if(applyStatus==='already_applied') notice='杩欐潯淇鎻愭宸茬粡搴旂敤杩囦簡';
  else if(applyStatus) notice='淇鎻愭宸插鐞嗭紝璇风湅鍗＄墖閲岀殑鏈€鏂扮姸鎬?;
  settingsPanelState.repairActionBusy='';
  return refreshSettingsData(isLight,notice);
 }).catch(function(){
  settingsPanelState.repairActionBusy='';
  settingsPanelState.error=(action==='apply'?'淇鎻愭搴旂敤澶辫触锛岃绋嶅悗鍐嶈瘯':'淇鎻愭棰勮澶辫触锛岃绋嶅悗鍐嶈瘯');
  renderSettingsPage(isLight);
 });
}

function renderSelfRepairReportCard(report, isLight, active){
 var safe=report&&typeof report==='object'?report:{};
 var preview=safe.patch_preview&&typeof safe.patch_preview==='object'?safe.patch_preview:{};
 var apply=safe.apply_result&&typeof safe.apply_result==='object'?safe.apply_result:{};
 var statusMeta=selfRepairReportStatusMeta(safe);
 var riskMeta=selfRepairRiskMeta(safe);
 var theme=getSettingsTheme(isLight);
 var textColor=theme.text;
 var subColor=theme.sub;
 var borderColor=active?theme.borderStrong:theme.border;
 var cardBg=active?theme.cardBgActive:theme.cardBg;
 var summary=cleanInlineText(safe.summary||safe.problem||'',220)||'杩欐潯淇鎻愭杩樻病鏈夌敓鎴愭憳瑕併€?;
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
 html+='<div style="background:'+cardBg+';border:1px solid '+borderColor+';border-radius:18px;padding:16px;box-shadow:var(--shadow-card);">';
 html+='<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap;">';
 html+='<div style="min-width:0;flex:1 1 420px;"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'+renderSettingsMetaPill(statusMeta.label,statusMeta.tone,isLight)+renderSettingsMetaPill(riskMeta.label,riskMeta.tone,isLight)+'</div><div style="font-size:16px;font-weight:800;color:'+textColor+';line-height:1.5;margin-top:10px;">'+escapeHtml(summary)+'</div></div>';
 html+='<div style="font-size:12px;color:'+subColor+';white-space:nowrap;">'+escapeHtml(formatSettingsTimestamp(safe.updated_at||safe.created_at))+'</div></div>';
 html+='<div style="margin-top:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">';
 html+='<div style="font-size:12px;line-height:1.7;color:'+subColor+';">'+escapeHtml(summarizeSelfRepairValidation(safe))+'</div>';
 html+='<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">';
 html+=renderSettingsActionButton(active?'鏀惰捣璇︽儏':'灞曞紑璇︽儏','self-repair-toggle',String(safe.id||''),isLight,'secondary',anyBusy);
 if(canPreview) html+=renderSettingsActionButton(isBusyPreview?'姝ｅ湪鐢熸垚...':(previewStatus==='preview_failed'?'閲嶆柊鐢熸垚棰勮':'鐢熸垚鏀瑰姩棰勮'),'self-repair-preview',String(safe.id||''),isLight,'secondary',anyBusy);
 if(canApply) html+=renderSettingsActionButton(isBusyApply?'姝ｅ湪搴旂敤...':'鎵瑰噯骞跺簲鐢?,'self-repair-apply',String(safe.id||''),isLight,'primary',anyBusy);
 html+='</div></div>';
 if(active){
  html+='<div style="margin-top:14px;padding-top:14px;border-top:1px dashed '+borderColor+';display:grid;gap:12px;">';
  if(question) html+=renderRepairDetailRow('瀵瑰簲鎻愰棶','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(question)+'</div>',isLight);
  if(feedback) html+=renderRepairDetailRow('鐢ㄦ埛鍙嶉','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(feedback)+'</div>',isLight);
  if(diagnosis) html+=renderRepairDetailRow('鎺掓煡鍒ゆ柇','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(diagnosis)+'</div>',isLight);
  html+=renderRepairDetailRow('鍊欓€夋枃浠?,renderRepairPathList(candidatePaths,isLight,'杩欐潯鎻愭杩樻病鏈夊垪鍑哄€欓€夋枃浠?),isLight);
  html+=renderRepairDetailRow('寤鸿娴嬭瘯',renderRepairPathList(testPaths,isLight,'杩欐潯鎻愭杩樻病鏈夊垪鍑哄缓璁祴璇?),isLight);
  if(previewStatus==='preview_ready'){
   html+=renderRepairDetailRow('鏀瑰姩棰勮','<div style="font-size:13px;line-height:1.8;color:'+textColor+';">'+escapeHtml(previewSummary||'宸茬粡鐢熸垚鏀瑰姩棰勮锛屽彲浠ュ厛鐪嬫枃浠惰寖鍥村拰鐗囨鍚庯紝鍐嶅湪杩欓噷鎵瑰噯搴旂敤銆?)+'</div>',isLight);
   html+=renderRepairDetailRow('鎷熸敼鏂囦欢',renderRepairPathList(previewPaths,isLight,'杩欐棰勮杩樻病鏈夊垪鍑哄叿浣撴敼鍔ㄦ枃浠?),isLight);
  }else if(previewStatus==='preview_failed'){
   html+=renderRepairDetailRow('棰勮澶辫触','<div style="font-size:13px;line-height:1.8;color:'+(isLight?'#b91c1c':'#fca5a5')+';">'+escapeHtml(previewError||'杩欐鏀瑰姩棰勮娌℃湁鎴愬姛鐢熸垚銆?)+'</div>',isLight);
  }else{
   html+=renderRepairDetailRow('瀹℃壒鍏ュ彛','<div style="font-size:13px;line-height:1.8;color:'+subColor+';">鍏堢偣"鐢熸垚鏀瑰姩棰勮"锛岀湅瀹屾枃浠惰寖鍥村拰鐗囨鍚庯紝鍐嶅湪杩欓噷鎵瑰噯搴旂敤銆?/div>',isLight);
  }
  html+='</div>';
 }
 html+='</div>';
 return html;
}

function renderSelfRepairReviewSection(config, status, reports, isLight){
 var theme=getSettingsTheme(isLight);
 var textColor=theme.text;
 var subColor=theme.sub;
 var cardBg=theme.cardBg;
 var borderColor=theme.border;
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

document.addEventListener('click',function(event){
 var button=event.target&&event.target.closest?event.target.closest('[data-model-action]'):null;
 if(!button) return;
 var action=String(button.getAttribute('data-model-action')||'').trim();
 var modelId=String(button.getAttribute('data-model-id')||'').trim();
 var providerKey=String(button.getAttribute('data-provider-key')||'').trim();
 console.log('[models][settings] action', action, modelId||providerKey||'');
 if(action==='open-dialog'){
  openModelDialog();
  return;
 }
 if(action==='toggle-provider'&&providerKey){
  _toggleProviderGroup(providerKey);
  return;
 }
 if(action==='switch'&&modelId){
  switchModel(modelId);
  return;
 }
 if(action==='switch-subscription'&&modelId){
  _switchConfiguredModelToSubscription(modelId);
  return;
 }
 if(action==='edit-dialog'&&modelId){
  openModelDialog(modelId);
  return;
 }
 if(action==='catalog-edit-dialog'&&providerKey&&modelId){
  openCatalogModelDialog(modelId, providerKey);
  return;
 }
 if(action==='enable-subscription'&&providerKey&&modelId){
  _quickEnableCatalogModel(providerKey, modelId);
  return;
 }
 if(action==='quick-add'&&providerKey&&modelId){
  _quickAddModel(providerKey, modelId);
 }
});

document.addEventListener('change',function(event){
 var node=event.target;
 if(!node||!node.matches||!node.matches('[data-settings-change="self-repair-mode"]')) return;
 saveSelfRepairMode();
});

function renderSettingsPage(isLight){
 var box=document.getElementById('settingsBox');
 if(!box) return;
 var theme=getSettingsTheme(isLight);
 var config=mergeAutolearnConfig(settingsPanelState.config||{});
 var selfRepairStatus=settingsPanelState.selfRepairStatus||{};
 var selfRepairReports=Array.isArray(settingsPanelState.selfRepairReports)?settingsPanelState.selfRepairReports:[];
 var l7s=settingsPanelState.l7Stats||{};
 var notice=settingsPanelState.error||settingsPanelState.notice||'';
 var noticeColor=settingsPanelState.error?theme.dangerText:theme.accentText;
 var cardBg=theme.cardBg;
 var textColor=theme.text;
 var subColor=theme.sub;
 var borderColor=theme.border;
 var html='';

 // 鈹€鈹€ 璇█鍒囨崲 鈹€鈹€
 var _isZh=getLang()==='zh';
 html+='<div style="margin-bottom:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:14px 18px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<span style="font-size:14px;font-weight:600;color:'+textColor+';">'+t('settings.lang')+'</span>';
 html+='<div style="display:flex;gap:6px;">';
 html+='<button onclick="setLang(\'zh\')" style="padding:6px 14px;border-radius:8px;border:1px solid '+borderColor+';background:'+(_isZh?theme.actionPrimary:cardBg)+';color:'+(_isZh?theme.actionPrimaryText:textColor)+';font-size:13px;font-weight:600;cursor:pointer;">'+t('settings.lang.zh')+'</button>';
 html+='<button onclick="setLang(\'en\')" style="padding:6px 14px;border-radius:8px;border:1px solid '+borderColor+';background:'+(!_isZh?theme.actionPrimary:cardBg)+';color:'+(!_isZh?theme.actionPrimaryText:textColor)+';font-size:13px;font-weight:600;cursor:pointer;">'+t('settings.lang.en')+'</button>';
 html+='</div></div>';

 // 鈹€鈹€ 鍖哄潡1锛氱姸鎬佹€昏锛?涓暟瀛楋級鈹€鈹€
 html+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;">';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">'+t('settings.correction')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.l7_rule_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">'+t('settings.behavior')+'</div><div style="font-size:22px;font-weight:800;color:'+(l7s.l7_constraint_count?theme.successText:textColor)+';">'+(l7s.l7_constraint_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='<div style="background:'+cardBg+';padding:16px;border-radius:14px;border:1px solid '+borderColor+';"><div style="font-size:12px;color:'+subColor+';margin-bottom:8px;">'+t('settings.knowledge')+'</div><div style="font-size:22px;font-weight:800;color:'+textColor+';">'+(l7s.l8_knowledge_count||0)+'<span style="font-size:12px;font-weight:400;color:'+subColor+';margin-left:4px;">'+t('settings.items')+'</span></div></div>';
 html+='</div>';

 // 鈹€鈹€ 鍖哄潡2锛氭寔缁繘鍖?鈹€鈹€
 var _evo=config.enabled;
 if(!document.getElementById('nova-spin-style')){var _ss=document.createElement('style');_ss.id='nova-spin-style';_ss.textContent='@keyframes nova-spin{to{transform:rotate(360deg)}}';document.head.appendChild(_ss);}
 var _dotHtml=_evo?'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;border:2.5px solid '+theme.spinner+';border-top-color:transparent;animation:nova-spin 1s linear infinite;vertical-align:middle;margin-right:10px;"></span>':'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:'+theme.stateOffText+';vertical-align:middle;margin-right:10px;"></span>';
 html+='<div style="margin-top:14px;background:'+cardBg+';border:1px solid '+borderColor+';padding:18px 20px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
 html+='<div><div style="display:flex;align-items:center;"><span style="font-size:16px;font-weight:700;color:'+textColor+';">'+_dotHtml+(_evo?t('settings.evolving'):t('settings.paused'))+'</span></div><div style="font-size:12px;color:'+subColor+';margin-top:6px;">'+(_evo?t('settings.evolve.desc.on'):t('settings.evolve.desc.off'))+'</div></div>';
 html+='<div data-settings-action="toggle" data-settings-key="enabled" style="flex-shrink:0;width:44px;height:24px;border-radius:12px;background:'+(_evo?theme.toggleOn:theme.toggleOff)+';cursor:pointer;position:relative;transition:background 0.2s;"><span style="position:absolute;top:2px;'+(_evo?'right:2px':'left:2px')+';width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:all 0.2s;"></span></div>';
 html+='</div>';

 // 鈹€鈹€ 鍖哄潡3锛氭ā鍨嬬鐞?鈹€鈹€
 html+=renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor);

 // 鈹€鈹€ 鍖哄潡4锛氫慨澶嶆彁妗堝鏍革紙宸插簾寮冿紝鏀圭敤瀵硅瘽涓?self_fix 宸ュ叿锛夆攢鈹€
 // html+=renderSelfRepairReviewSection(config,selfRepairStatus,selfRepairReports,isLight);

 box.innerHTML=html;
}

function refreshSettingsData(isLight, noticeText){
 if(noticeText!==undefined){
  settingsPanelState.notice=noticeText;
  settingsPanelState.error='';
 }
 renderSettingsPage(isLight);
 return Promise.resolve();
}

function loadSettingsPage(isLight){
 var chat=document.getElementById('chat');
 setInputVisible(false);
 if(chat) chat.innerHTML='<div class="settings-page" style="position:relative;z-index:1;"><div id="settingsBox">'+t('loading')+'</div></div>'; settingsPanelState.notice='';
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
 settingsPanelState.notice='姝ｅ湪淇濆瓨...';
 renderSettingsPage(isLight);
 fetch('/autolearn/config',{
  method:'POST',
  headers:{'Content-Type':'application/json; charset=utf-8','Accept':'application/json'},
  body:JSON.stringify(patch||{})
 }).then(function(r){return r.json();}).then(function(data){
  settingsPanelState.config=mergeAutolearnConfig((data&&data.config)||settingsPanelState.config||{});
  return refreshSettingsData(isLight,noticeText||'宸蹭繚瀛?);
 }).catch(function(){
  settingsPanelState.error='淇濆瓨澶辫触锛岃绋嶅悗鍐嶈瘯';
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
  return refreshSettingsData(isLight,next?'宸插紑鍚?:'宸插叧闂?);
 }).catch(function(){
  settingsPanelState.error='淇濆瓨澶辫触';
  renderSettingsPage(isLight);
 });
}

function applyAutolearnPreset(key){
 var presets=autolearnPresets();
 if(!presets[key]) return;
 var patch={};
 Object.keys(presets[key].patch).forEach(function(field){patch[field]=presets[key].patch[field];});
 saveAutolearnConfigPatch(patch,'宸插垏鎹㈠埌銆?+presets[key].label+'銆?);
}

function saveAutolearnAdvancedSettings(){
 var patch={
  min_query_length:clampSettingNumber((document.getElementById('autolearnMinQuery')||{}).value,2,30,4),
  search_timeout_sec:clampSettingNumber((document.getElementById('autolearnTimeout')||{}).value,3,20,5),
  max_results:clampSettingNumber((document.getElementById('autolearnMaxResults')||{}).value,1,10,5),
  max_summary_length:clampSettingNumber((document.getElementById('autolearnSummaryLimit')||{}).value,120,800,360),
  self_repair_test_timeout_sec:clampSettingNumber((document.getElementById('selfRepairTestTimeout')||{}).value,10,120,30)
 };
 saveAutolearnConfigPatch(patch,'搴曞眰鍙傛暟宸叉洿鏂?);
}

function saveSelfRepairMode(){
 var el=document.getElementById('selfRepairApplyMode');
 if(!el) return;
 saveAutolearnConfigPatch({self_repair_apply_mode:el.value},'瀹℃壒鑺傚宸叉洿鏂?);
}


