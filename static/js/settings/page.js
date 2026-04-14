// Settings page rendering entry.
// Self-contained on purpose so Settings does not depend on autolearn UI code.

function _settingsPageState(){
 if(typeof window!=='undefined'){
  if(!window.settingsPanelState || typeof window.settingsPanelState!=='object'){
   window.settingsPanelState={notice:'',error:'',chatPresetSaving:'',chatPresetPending:''};
  }
  if(typeof window.settingsPanelState.chatPresetSaving!=='string'){
   window.settingsPanelState.chatPresetSaving='';
  }
  if(typeof window.settingsPanelState.chatPresetPending!=='string'){
   window.settingsPanelState.chatPresetPending='';
  }
  return window.settingsPanelState;
 }
 return {notice:'',error:'',chatPresetSaving:'',chatPresetPending:''};
}

var _settingsChatConfig=null;
var _settingsChatPresets=[];

function _getSettingsChatPresetMeta(){
 var isZh=(typeof getLang==='function'?getLang():'zh')==='zh';
 return [
  {
   id:'save',
   budget:2000,
   label:isZh?'省流':'Lean',
   desc:isZh?'更省消耗，适合短问短答。':'Lower cost for quick exchanges.'
  },
  {
   id:'balanced',
   budget:4000,
   label:isZh?'平衡':'Balanced',
   desc:isZh?'兼顾连续性和消耗。':'Balances continuity and cost.'
  },
  {
   id:'deep',
   budget:6000,
   label:isZh?'深聊':'Deep',
   desc:isZh?'带入更多前文，适合连续讨论。':'Brings in more recent history for ongoing discussions.'
  },
  {
   id:'immersive',
   budget:8000,
   label:isZh?'沉浸':'Immersive',
   desc:isZh?'尽量保留更多前文，适合长任务，但消耗更高。':'Keeps more context for long-running tasks at a higher cost.'
  }
 ];
}

function _getSettingsChatPresetById(presetId){
 var options=_getSettingsChatPresetMeta();
 for(var i=0;i<options.length;i++){
  if(options[i].id===presetId) return options[i];
 }
 return options[1];
}

function _getSettingsChatConfig(){
 var fallback={
  l1_recent_token_budget_preset:'balanced',
  l1_recent_token_budget:4000
 };
 var cfg=(_settingsChatConfig&&typeof _settingsChatConfig==='object')?_settingsChatConfig:{};
 var presetId=String(cfg.l1_recent_token_budget_preset||fallback.l1_recent_token_budget_preset).trim().toLowerCase();
 var preset=_getSettingsChatPresetById(presetId);
 var budget=Number(cfg.l1_recent_token_budget||preset.budget||fallback.l1_recent_token_budget);
 if(!budget||budget<1) budget=preset.budget||fallback.l1_recent_token_budget;
 return {
  l1_recent_token_budget_preset:preset.id,
  l1_recent_token_budget:budget
 };
}

function loadSettingsChatConfig(){
 return fetch('/chat/config').then(function(r){return r.json();}).then(function(data){
  _settingsChatConfig=(data&&data.config&&typeof data.config==='object')?data.config:null;
  _settingsChatPresets=Array.isArray(data&&data.presets)?data.presets.slice():[];
  return data||{};
 });
}

function refreshSettingsData(isLight){
 var state=_settingsPageState();
 return Promise.all([
  (typeof loadSettingsModels==='function' ? Promise.resolve(loadSettingsModels()) : Promise.resolve(null)),
  loadSettingsChatConfig().catch(function(){
   _settingsChatConfig=null;
   _settingsChatPresets=[];
   state.error=(typeof getLang==='function'&&getLang()==='en')
    ? 'Failed to load conversation continuity settings'
    : '对话连续性设置加载失败';
   return null;
  })
 ]).then(function(){
  renderSettingsPage(isLight);
 });
}

function _saveSettingsChatPreset(presetId){
 var state=_settingsPageState();
 var target=String(presetId||'').trim().toLowerCase();
 if(!target || state.chatPresetSaving===target) return Promise.resolve(null);
 state.notice='';
 state.error='';
 state.chatPresetSaving=target;
  state.chatPresetPending=target;
 renderSettingsPage(document.body.classList.contains('light'));
 return fetch('/chat/config',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({l1_recent_token_budget_preset:target})
 }).then(function(r){return r.json();}).then(function(data){
  if(!data||!data.ok){
   throw new Error((data&&data.error)||'save_failed');
  }
  _settingsChatConfig=(data.config&&typeof data.config==='object')?data.config:null;
  _settingsChatPresets=Array.isArray(data.presets)?data.presets.slice():_settingsChatPresets;
  state.notice=(typeof getLang==='function'&&getLang()==='en')
   ? 'Conversation continuity updated.'
   : '对话连续性已更新。';
  return data;
 }).catch(function(err){
  state.error=(typeof getLang==='function'&&getLang()==='en')
   ? 'Failed to update conversation continuity.'
   : '更新对话连续性失败。';
  throw err;
 }).finally(function(){
  state.chatPresetSaving='';
  state.chatPresetPending='';
  renderSettingsPage(document.body.classList.contains('light'));
 });
}

function _chooseSettingsChatPreset(presetId){
 var picker=document.getElementById('settingsChatPresetPicker');
 if(picker&&typeof picker.removeAttribute==='function'){
  picker.removeAttribute('open');
 }
 var current=_getSettingsChatConfig();
 if(String((current&&current.l1_recent_token_budget_preset)||'').trim().toLowerCase()===String(presetId||'').trim().toLowerCase()){
  return Promise.resolve(null);
 }
 return _saveSettingsChatPreset(presetId);
}

if(typeof document!=='undefined' && typeof window!=='undefined' && !window.__settingsPresetPickerBound){
 document.addEventListener('click',function(evt){
  var picker=document.getElementById('settingsChatPresetPicker');
  if(!picker || !picker.hasAttribute('open')) return;
  if(picker.contains(evt.target)) return;
  picker.removeAttribute('open');
 });
 window.__settingsPresetPickerBound=true;
}

function _settingsPageTheme(isLight){
 if(typeof getSettingsTheme==='function') return getSettingsTheme(isLight);
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
  providerCardBg:'var(--surface-panel)',
  currentRowBg:isLight?'rgba(112,130,100,0.10)':'rgba(151,171,137,0.12)',
  currentRowBorder:isLight?'rgba(112,130,100,0.24)':'rgba(151,171,137,0.26)',
  softRowBg:'var(--surface-panel-soft)',
  softDashedBg:'var(--surface-panel-soft)',
  softDashedBorder:'var(--border-panel)',
  successBg:'var(--tone-sage-soft)',
  successText:'var(--tone-sage)',
  modelDialogSuccessText:isLight?'#708264':'#97ab89',
  modelDialogSuccessBg:isLight?'rgba(112,130,100,0.10)':'rgba(151,171,137,0.12)',
  modelDialogSuccessBorder:isLight?'rgba(112,130,100,0.22)':'rgba(151,171,137,0.24)',
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

function renderSettingsPage(isLight){
 var box=document.getElementById('settingsBox');
 if(!box) return;
 try{
  var theme=_settingsPageTheme(isLight);
  var state=_settingsPageState();
  var notice=state.error||state.notice||'';
  var noticeColor=state.error?theme.dangerText:theme.accentText;
  var isZh=(typeof getLang==='function'?getLang():'zh')==='zh';
  var isLightTheme=document.body.classList.contains('light');
  var themeMode=(typeof getThemeMode==='function'?getThemeMode():(isLightTheme?'light':'dark'));
  var pageTitle=(typeof t==='function'?t('settings.title'):'')||(isZh?'设置':'Settings');
  var pageSubtitle=isZh?'管理语言、外观主题和模型接入。':'Manage language, appearance, and model access.';
  var languageDesc=isZh?'切换整个应用与设置页使用的语言。':'Choose the language used across the app and settings.';
  var languageRowTitle=isZh?'界面语言':'Interface language';
  var languageRowDesc=isZh?'改变应用界面、设置面板和辅助说明默认使用的语言。':'Change the language used by the app, settings workspace, and helper copy.';
  var themeTitle=(typeof t==='function'?t('settings.theme'):'')||(isZh?'外观主题':'Appearance');
  var themeDesc=(typeof t==='function'?t('settings.theme.desc'):'')||(isZh?'把浅色、深色和跟随系统主题放在设置里切换，让顶栏更干净。':'Switch light, dark, or system theme here so the title bar stays cleaner.');
  var themeRowDesc=isZh?'改变应用整体外观，或跟随系统主题。':'Change the overall appearance of the app, or follow the system theme.';
  var chatConfig=_getSettingsChatConfig();
  var pendingChatPresetId=String(state.chatPresetPending||'').trim().toLowerCase();
  var effectiveChatPresetId=pendingChatPresetId||chatConfig.l1_recent_token_budget_preset;
  var chatPreset=_getSettingsChatPresetById(effectiveChatPresetId);
  var chatTitle=isZh?'对话连续性':'Conversation continuity';
  var chatDesc=isZh?'控制每轮聊天会带入多少最近历史。更高会更连贯，但也更耗 token。':'Control how much recent history each reply carries. Higher settings feel more continuous, but cost more tokens.';
  var chatRowTitle=isZh?'历史带入强度':'Recent history depth';
  var chatRowDesc=isZh?'控制每轮会带入多少最近历史。更高更连贯，也更耗 token。':'Choose how much recent history each reply keeps. Higher settings feel more continuous, but cost more tokens.';
  var chatBudget=Number(chatPreset.budget||chatConfig.l1_recent_token_budget||4000);
  if(!chatBudget||chatBudget<1) chatBudget=4000;
  var chatBudgetText=isZh?('约 '+chatBudget+' tokens'):('About '+chatBudget+' tokens');
  var chatSavingPreset=String(state.chatPresetSaving||'').trim().toLowerCase();
  var chatSavingText=isZh?'正在保存...':'Saving...';
  var modelTitle=isZh?'模型管理':'Model access';
  var modelDesc=isZh?'按厂家分组，只展示已经对接过的模型。':'Grouped by provider. Only connected models are shown here.';

  var html='';
  html+='<div class="settings-shell">';
  html+='<div class="settings-head">';
  html+='<div class="settings-head-copy">';
  html+='<h1 class="settings-title">'+escapeHtml(pageTitle)+'</h1>';
  html+='<p class="settings-subtitle">'+escapeHtml(pageSubtitle)+'</p>';
  html+='</div>';
  if(notice){
   html+='<div class="settings-notice" style="color:'+noticeColor+';">'+escapeHtml(notice)+'</div>';
  }
  html+='</div>';

  html+='<div class="settings-main-pane">';

  html+='<section id="settings-language" class="settings-pane">';
  html+='<div class="settings-pane-head">';
  html+='<h2 class="settings-pane-title">'+escapeHtml((typeof t==='function'?t('settings.lang'):'')||(isZh?'语言':'Language'))+'</h2>';
  html+='<p class="settings-pane-desc">'+escapeHtml(languageDesc)+'</p>';
  html+='</div>';
  html+='<div class="settings-row-card">';
  html+='<div class="settings-row-copy">';
  html+='<div class="settings-row-title">'+escapeHtml(languageRowTitle)+'</div>';
  html+='<div class="settings-row-desc">'+escapeHtml(languageRowDesc)+'</div>';
  html+='</div>';
  html+='<div class="settings-segmented">';
  html+='<button type="button" onclick="setLang(\'zh\')" class="settings-segment-btn '+(isZh?'is-active':'')+'">'+escapeHtml((typeof t==='function'?t('settings.lang.zh'):'')||'中文')+'</button>';
  html+='<button type="button" onclick="setLang(\'en\')" class="settings-segment-btn '+(!isZh?'is-active':'')+'">'+escapeHtml((typeof t==='function'?t('settings.lang.en'):'')||'English')+'</button>';
  html+='</div>';
  html+='</div>';
  html+='</section>';

  html+='<section id="settings-theme" class="settings-pane">';
  html+='<div class="settings-pane-head">';
  html+='<h2 class="settings-pane-title">'+escapeHtml(themeTitle)+'</h2>';
  html+='<p class="settings-pane-desc">'+escapeHtml(themeDesc)+'</p>';
  html+='</div>';
  html+='<div class="settings-row-card">';
  html+='<div class="settings-row-copy">';
  html+='<div class="settings-row-title">'+escapeHtml(themeTitle)+'</div>';
  html+='<div class="settings-row-desc">'+escapeHtml(themeRowDesc)+'</div>';
  html+='</div>';
  html+='<div class="settings-segmented">';
  html+='<button type="button" onclick="setThemeMode(\'light\')" class="settings-segment-btn '+(themeMode==='light'?'is-active':'')+'">'+escapeHtml((typeof t==='function'?t('settings.theme.light'):'')||'Light')+'</button>';
  html+='<button type="button" onclick="setThemeMode(\'dark\')" class="settings-segment-btn '+(themeMode==='dark'?'is-active':'')+'">'+escapeHtml((typeof t==='function'?t('settings.theme.dark'):'')||'Dark')+'</button>';
  html+='<button type="button" onclick="setThemeMode(\'system\')" class="settings-segment-btn '+(themeMode==='system'?'is-active':'')+'">'+escapeHtml((typeof t==='function'?t('settings.theme.system'):'')||(isZh?'跟随系统':'System'))+'</button>';
  html+='</div>';
  html+='</div>';
  html+='</section>';

  html+='<section id="settings-chat-context" class="settings-pane">';
  html+='<div class="settings-pane-head">';
  html+='<h2 class="settings-pane-title">'+escapeHtml(chatTitle)+'</h2>';
  html+='<p class="settings-pane-desc">'+escapeHtml(chatDesc)+'</p>';
  html+='</div>';
  html+='<div class="settings-control-card">';
  html+='<div class="settings-control-row">';
  html+='<div class="settings-row-copy">';
  html+='<div class="settings-row-title">'+escapeHtml(chatRowTitle)+'</div>';
  html+='<div class="settings-row-desc">'+escapeHtml(chatRowDesc)+'</div>';
  html+='</div>';
  html+='<div class="settings-chat-controls">';
  html+='<details id="settingsChatPresetPicker" class="settings-preset-picker'+(chatSavingPreset?' is-saving':'')+'">';
  html+='<summary class="settings-preset-trigger" aria-label="'+escapeHtml(chatRowTitle)+'">';
  html+='<div class="settings-preset-copy">';
  html+='<div class="settings-preset-head">';
  html+='<span class="settings-preset-label">'+escapeHtml(chatPreset.label)+'</span>';
  html+='<span class="settings-preset-meta">'+escapeHtml(chatSavingPreset?chatSavingText:chatBudgetText)+'</span>';
  html+='</div>';
  html+='<div class="settings-preset-desc">'+escapeHtml(chatPreset.desc)+'</div>';
  html+='</div>';
  html+='<span class="settings-preset-caret">▾</span>';
  html+='</summary>';
  html+='<div class="settings-preset-menu">';
  _getSettingsChatPresetMeta().forEach(function(option){
   var isSelected=option.id===chatPreset.id;
   html+='<button type="button" class="settings-preset-option'+(isSelected?' is-active':'')+'" onclick="_chooseSettingsChatPreset(\''+escapeHtml(option.id)+'\');return false;"'+(chatSavingPreset?' disabled':'')+'>';
   html+='<div class="settings-preset-option-head">';
   html+='<span class="settings-preset-option-label">'+escapeHtml(option.label)+'</span>';
   html+='<span class="settings-preset-option-meta">'+escapeHtml((isZh?'约 ':'About ')+String(option.budget)+' tokens')+'</span>';
   html+='</div>';
   html+='<div class="settings-preset-option-desc">'+escapeHtml(option.desc)+'</div>';
   if(isSelected){
    html+='<span class="settings-preset-option-check">✓</span>';
   }
   html+='</button>';
  });
  html+='</div>';
  html+='</details>';
  html+='</div>';
  html+='</div>';
  html+='</div>';
  html+='</section>';

  html+='<section id="settings-models" class="settings-pane">';
  html+='<div class="settings-pane-head">';
  html+='<h2 class="settings-pane-title">'+escapeHtml(modelTitle)+'</h2>';
  html+='<p class="settings-pane-desc">'+escapeHtml(modelDesc)+'</p>';
  html+='</div>';
  try{
   html+=renderModelManageSection(isLight,theme.text,theme.sub,theme.cardBg,theme.border);
  }catch(modelErr){
   console.warn('[AaronCore] settings model section failed', modelErr);
   html+='<div class="settings-model-shell" style="background:'+theme.cardBg+';border:1px solid '+theme.border+';padding:18px 20px;border-radius:14px;color:'+theme.sub+';">'+escapeHtml(isZh?'模型区加载失败。':'Model section failed to load.')+'</div>';
  }
  html+='</section>';

  html+='</div>';
  html+='</div>';
  box.innerHTML=html;
 }catch(err){
  console.warn('[AaronCore] render settings page failed', err);
  var errMsg=String((err&&err.message)||err||'Unknown error');
  box.innerHTML='<div class="settings-shell"><div class="settings-head"><div class="settings-head-copy"><h1 class="settings-title">Settings</h1><p class="settings-subtitle">The settings view hit a render error: '+errMsg+'</p></div></div></div>';
 }
}

function loadSettingsPage(isLight){
 var chat=document.getElementById('chat');
 if(!chat) return;
 if(typeof setInputVisible==='function') setInputVisible(false);
 chat.innerHTML='<div class="settings-page" style="position:relative;z-index:1;"><div id="settingsBox">'+escapeHtml((typeof t==='function'?t('loading'):'')||'Loading...')+'</div></div>';
 var state=_settingsPageState();
 state.notice='';
 state.error='';
 if(typeof refreshSettingsData==='function'){
  try{
   refreshSettingsData(isLight).catch(function(){
    state.error=(typeof t==='function'?t('settings.load.fail'):'')||'Failed to load settings';
    renderSettingsPage(isLight);
   });
   return;
  }catch(e){
   console.warn('[AaronCore] refresh settings data failed', e);
  }
 }
 if(typeof loadSettingsModels==='function'){
  try{ loadSettingsModels(); }catch(e){ console.warn('[AaronCore] load settings models failed', e); }
 }
 renderSettingsPage(isLight);
}

function _settingsModelEndpointMeta(mid, cfg){
 var parts=[];
 if(cfg&&cfg.derived&&cfg.source_model){
  parts.push('via '+cfg.source_model);
 }else{
  parts.push(String(mid||'').trim());
 }
 var baseUrl=String((cfg||{}).base_url||'').trim();
 if(baseUrl){
  try{
   var parsed=new URL(baseUrl);
   if(parsed.host) parts.push(parsed.host);
  }catch(_err){}
 }
 return parts.filter(Boolean).join(' / ');
}

function _renderSettingsModelRow(rowId, cfg, allModels, displayCounts, currentModel, theme, options){
 options=options||{};
 var isCurrent=rowId===currentModel;
 var showEdit=!!options.showEdit;
 var withDivider=!!options.withDivider;
 var rowBg=isCurrent?theme.currentRowBg:'transparent';
 var primaryLabel=_getModelDisplayName(rowId, cfg, allModels, displayCounts);
 var metaLabel=_settingsModelEndpointMeta(rowId, cfg);
 var html='';
 html+='<div style="display:flex;align-items:center;gap:10px;padding:11px 14px;background:'+rowBg+';'+(withDivider?'border-top:1px solid '+theme.border+';':'')+'">';
 if(isCurrent) html+='<span style="color:'+theme.currentCheck+';font-size:14px;">\u2713</span>';
 html+='<div style="min-width:0;flex:1;display:flex;flex-direction:column;gap:3px;">';
 html+='<span style="font-size:13px;font-weight:'+(isCurrent?'700':'600')+';color:'+theme.text+';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+escapeHtml(primaryLabel)+'</span>';
 html+='<span style="font-size:11px;color:'+theme.sub+';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+escapeHtml(metaLabel)+'</span>';
 html+='</div>';
 if(isCurrent){
  html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+escapeHtml((typeof t==='function'?t('settings.models.active'):'')||'Active')+'</span>';
 }else{
  html+='<button type="button" onclick="_sidebarSwitchModel(\''+escapeHtml(rowId)+'\')" style="padding:4px 10px;border-radius:999px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:600;">'+escapeHtml((typeof t==='function'?t('settings.models.activate'):'')||'Use')+'</button>';
 }
 if(showEdit){
  html+='<button type="button" onclick="openModelDialog(\''+escapeHtml(rowId)+'\')" style="padding:4px 10px;border-radius:999px;border:1px solid '+theme.border+';background:none;color:'+theme.sub+';font-size:11px;cursor:pointer;">'+escapeHtml((typeof t==='function'?t('settings.models.edit'):'')||'Edit')+'</button>';
 }
 html+='</div>';
 return html;
}

function renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor){
 var theme=_settingsPageTheme(isLight);
 var savedVisibleModels=_getVisibleSettingsModels(_settingsModels||{});
 var unlockedModels=_buildUnlockedSettingsModels(_settingsModels||{}, _settingsCatalog||{}, _settingsCurrentModel);
 var displayCounts=_buildModelNameCounts(unlockedModels);
 var html='';

 html+='<div class="settings-model-shell" style="background:transparent;border:none;padding:0;box-shadow:none;">';
 html+='<div class="settings-model-topbar">';
 html+='<div class="settings-model-copy">';
 html+='<span style="font-size:15px;font-weight:700;color:'+theme.text+';">'+escapeHtml((typeof t==='function'?t('settings.models'):'')||'Models')+'</span>';
 html+='<span style="font-size:11px;color:'+theme.sub+';">'+escapeHtml('Connected providers are grouped here.')+'</span>';
 html+='</div>';
 html+='<button type="button" onclick="openModelDialog()" class="settings-inline-button" style="border:1px solid '+theme.border+';background:'+theme.actionSecondary+';color:'+theme.text+';">'+escapeHtml((typeof t==='function'?t('settings.models.add'):'')||'Add model')+'</button>';
 html+='</div>';
 html+='<div id="modelListBox" class="settings-provider-list">';

 if(!_settingsModels||!_settingsCatalog){
  html+='Loading...';
 }else if(Object.keys(savedVisibleModels).length===0){
  html+='<div style="padding:18px 16px;border:1px dashed '+theme.border+';border-radius:12px;background:'+theme.softRowBg+';color:'+theme.sub+';font-size:12px;line-height:1.8;">';
  html+='No provider connection is active yet. Pick a provider, choose a model, and fill in its API key first.';
  html+='</div>';
 }else{
  var shownIds={};
  Object.keys(_settingsCatalog||{}).forEach(function(providerKey){
   var donor=_pickVisibleProviderDonor(providerKey, savedVisibleModels, _settingsCurrentModel, _settingsCatalog);
   if(!donor) return;
   var providerInfo=_settingsCatalog[providerKey]||{};
   var currentCfg=unlockedModels[_settingsCurrentModel]||savedVisibleModels[_settingsCurrentModel]||{};
   var currentProvider=_classifyModelToProvider(_settingsCurrentModel||'', currentCfg, _settingsCatalog);
   var isExpanded=_settingsExpandedProviders[providerKey]!==undefined ? _settingsExpandedProviders[providerKey] : (providerKey===currentProvider);
   var chevron=isExpanded?'\u25BC':'\u25B6';
   var providerLabel=providerKey.charAt(0).toUpperCase()+providerKey.slice(1);
   var activeModelName='';
   if(_settingsCurrentModel&&currentProvider===providerKey){
    activeModelName=_getModelDisplayName(_settingsCurrentModel, currentCfg, unlockedModels, displayCounts);
   }

   html+='<div class="settings-provider-group" style="border:1px solid '+theme.border+';background:'+theme.providerCardBg+';">';
   html+='<div onclick="_toggleProviderGroup(\''+escapeHtml(providerKey)+'\','+isExpanded+')" class="settings-provider-header" style="background:'+(isExpanded?theme.headerBg:'transparent')+';">';
   html+='<span style="font-size:11px;color:'+theme.sub+';width:14px;text-align:center;">'+chevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';flex:1;">'+escapeHtml(providerLabel)+'</span>';
   if(activeModelName){
    html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+escapeHtml(activeModelName)+'</span>';
   }else{
    var modelCount=(providerInfo.models||[]).length||1;
    html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.inactiveTagBg+';color:'+theme.inactiveTagText+';font-size:11px;">'+modelCount+' models</span>';
   }
   if(donor&&donor.id){
    html+='<button type="button" onclick="openModelDialog(\''+escapeHtml(donor.id)+'\')" class="settings-inline-button is-small" style="border:1px solid '+theme.border+';background:'+theme.actionSecondary+';color:'+theme.text+';">'+escapeHtml((typeof t==='function'?t('settings.models.edit'):'')||'Edit')+'</button>';
   }
   html+='</div>';

   if(isExpanded){
    html+='<div class="settings-provider-body" style="display:flex;flex-direction:column;gap:0;padding:4px 0 8px;">';
    var providerRowCount=0;
    var matchedSaved={};
    var actualLookup={};
    Object.keys(savedVisibleModels).forEach(function(mid){
     var cfg=savedVisibleModels[mid]||{};
     if(_classifyModelToProvider(mid, cfg, _settingsCatalog)!==providerKey) return;
     actualLookup[String(mid||'').toLowerCase()]=mid;
     actualLookup[String((cfg.model||'')).toLowerCase()]=mid;
    });

    (providerInfo.models||[]).forEach(function(entry){
     var modelId=String((entry&&entry.id)||'').trim();
     if(!modelId) return;
     var matchedId=actualLookup[modelId.toLowerCase()]||'';
     if(matchedId) matchedSaved[matchedId]=true;
     var rowId=matchedId||modelId;
     var rowCfg=matchedId?(savedVisibleModels[matchedId]||{}):(unlockedModels[modelId]||{});
     if(!rowCfg||!Object.keys(rowCfg).length) return;
     shownIds[rowId]=true;
     html+=_renderSettingsModelRow(rowId, rowCfg, unlockedModels, displayCounts, _settingsCurrentModel, theme, {providerKey:providerKey,showEdit:false,withDivider:providerRowCount>0});
     providerRowCount+=1;
    });

    var extraSaved=Object.keys(savedVisibleModels).filter(function(mid){
     var cfg=savedVisibleModels[mid]||{};
     return _classifyModelToProvider(mid, cfg, _settingsCatalog)===providerKey && !matchedSaved[mid];
    });
    extraSaved.sort(function(a,b){
     var aLabel=_getModelDisplayName(a, savedVisibleModels[a]||{}, unlockedModels, displayCounts).toLowerCase();
     var bLabel=_getModelDisplayName(b, savedVisibleModels[b]||{}, unlockedModels, displayCounts).toLowerCase();
     return aLabel.localeCompare(bLabel);
    });
    extraSaved.forEach(function(mid){
     shownIds[mid]=true;
     html+=_renderSettingsModelRow(mid, savedVisibleModels[mid]||{}, unlockedModels, displayCounts, _settingsCurrentModel, theme, {providerKey:providerKey,showEdit:false,withDivider:providerRowCount>0});
     providerRowCount+=1;
    });
    html+='</div>';
   }

   html+='</div>';
  });

  var others=Object.keys(savedVisibleModels).filter(function(mid){
   var cfg=savedVisibleModels[mid]||{};
   var providerKey=_classifyModelToProvider(mid, cfg, _settingsCatalog);
   return !shownIds[mid] && !providerKey;
  });
  if(others.length>0){
   var uncExpanded=_settingsExpandedProviders._other!==undefined?_settingsExpandedProviders._other:true;
   var uncChevron=uncExpanded?'\u25BC':'\u25B6';
   html+='<div class="settings-provider-group" style="border:1px solid '+theme.border+';background:'+theme.providerCardBg+';">';
   html+='<div onclick="_toggleProviderGroup(\'_other\','+uncExpanded+')" class="settings-provider-header">';
   html+='<span style="font-size:11px;color:'+theme.sub+';width:14px;text-align:center;">'+uncChevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';flex:1;">Other</span>';
   html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.inactiveTagBg+';color:'+theme.inactiveTagText+';font-size:11px;">'+others.length+' models</span>';
   html+='</div>';
   if(uncExpanded){
    html+='<div class="settings-provider-body" style="display:flex;flex-direction:column;gap:0;padding:4px 0 8px;">';
    var otherRowCount=0;
    others.sort(function(a,b){
     var aLabel=_getModelDisplayName(a, savedVisibleModels[a]||{}, unlockedModels, displayCounts).toLowerCase();
     var bLabel=_getModelDisplayName(b, savedVisibleModels[b]||{}, unlockedModels, displayCounts).toLowerCase();
     return aLabel.localeCompare(bLabel);
    });
    others.forEach(function(mid){
     html+=_renderSettingsModelRow(mid, savedVisibleModels[mid]||{}, unlockedModels, displayCounts, _settingsCurrentModel, theme, {providerKey:'_other',showEdit:true,withDivider:otherRowCount>0});
     otherRowCount+=1;
    });
    html+='</div>';
   }
   html+='</div>';
  }
 }

 html+='</div></div>';
 return html;
}
