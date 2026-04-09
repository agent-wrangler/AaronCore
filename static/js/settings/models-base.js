// Model management data flow and first-pass settings model actions
// Source: settings.js lines 655-994

var _settingsModels=null;
var _settingsCurrentModel='';
var _settingsCatalog=null;
var _settingsExpandedProviders={};

function _classifyModelToProvider(mid, cfg, catalog){
 if(!catalog) return null;
 var midL=mid.toLowerCase();
 var modelName=String((cfg||{}).model||'').toLowerCase();
 var baseUrl=String((cfg||{}).base_url||'').toLowerCase();
 for(var pkey in catalog){
  if(midL.indexOf(pkey)!==-1||modelName.indexOf(pkey)!==-1) return pkey;
  var aliases=catalog[pkey].aliases||[];
  for(var i=0;i<aliases.length;i++){
   if(midL.indexOf(aliases[i])!==-1||modelName.indexOf(aliases[i])!==-1) return pkey;
  }
 }
 for(var pkey2 in catalog){
  if(catalog[pkey2].url_hint && baseUrl.indexOf(catalog[pkey2].url_hint)!==-1) return pkey2;
 }
 return null;
}

function _toggleProviderGroup(pkey, currentExpanded){
 var effectiveExpanded;
 if(typeof currentExpanded==='boolean'){
  effectiveExpanded=currentExpanded;
 }else if(_settingsExpandedProviders[pkey]!==undefined){
  effectiveExpanded=!!_settingsExpandedProviders[pkey];
 }else{
  var currentProvider=null;
  if(_settingsCurrentModel){
   var currentCfg=(_settingsModels&&_settingsModels[_settingsCurrentModel])||{};
   currentProvider=_classifyModelToProvider(_settingsCurrentModel, currentCfg, _settingsCatalog||{});
  }
  effectiveExpanded=(pkey==='_other')?!currentProvider:(pkey===currentProvider);
 }
 _settingsExpandedProviders[pkey]=!effectiveExpanded;
 renderSettingsPage(document.body.classList.contains('light'));
}

function _quickAddModel(pkey, modelId){
 if(!_settingsModels||!_settingsCatalog) return;
 var catalog=_settingsCatalog;
 var pinfo=catalog[pkey];
 if(!pinfo) return;
 var donorCfg=null;
 for(var mid in _settingsModels){
  var cfg=_settingsModels[mid]||{};
  var classified=_classifyModelToProvider(mid, cfg, catalog);
  if(classified===pkey&&_isVisibleSettingsModel(cfg)){ donorCfg=cfg; break; }
 }
 if(!donorCfg){
  alert('\u8be5\u5382\u5546\u6ca1\u6709\u5df2\u914d\u7f6e\u7684 API \u6a21\u578b\uff0c\u8bf7\u5148\u624b\u52a8\u6dfb\u52a0\u4e00\u4e2a');
  return;
 }
 if(!donorCfg.api_key||!donorCfg.base_url){
  alert('\u8be5\u5382\u5546\u6ca1\u6709\u5df2\u914d\u7f6e\u7684 API \u8fde\u63a5\uff0c\u8bf7\u5148\u624b\u52a8\u6dfb\u52a0\u4e00\u4e2a');
  return;
 }
 var cfg={
  model:modelId,
  vision:donorCfg.vision||false,
  transport:'openai_api',
  api_key:donorCfg.api_key,
  base_url:donorCfg.base_url
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

function _buildModelNameCounts(models){
 var counts={};
 Object.keys(models||{}).forEach(function(mid){
  var cfg=models[mid]||{};
  var name=String(cfg.display_name||cfg.model||mid||'').trim();
  if(!name) name=String(mid||'').trim();
  var key=name.toLowerCase();
  counts[key]=(counts[key]||0)+1;
 });
 return counts;
}

function _getModelDisplayName(mid, cfg, allModels, nameCounts){
 cfg=cfg||{};
 var base=String(cfg.display_name||cfg.model||mid||'').trim();
 if(!base) base=String(mid||'').trim();
 var counts=nameCounts||_buildModelNameCounts(allModels||{});
 if((counts[base.toLowerCase()]||0)<=1) return base;
 return base+' ['+mid+']';
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
  var models=_buildUnlockedSettingsModels(_settingsModels||{}, catalog, _settingsCurrentModel);
  var currentModel=_settingsCurrentModel;
  var displayCounts=_buildModelNameCounts(models);
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
  if(currentModel){
   currentProvider=_classifyModelToProvider(currentModel, models[currentModel], catalog);
  }
  for(var pk in catalog){
   var pi=catalog[pk];
   var configured=providerConfigured[pk]||[];
   var isExpanded=_settingsExpandedProviders[pk]!==undefined?_settingsExpandedProviders[pk]:(pk===currentProvider);
   var hasConfigured=configured.length>0;
   var providerLabel=pk.charAt(0).toUpperCase()+pk.slice(1);
   var activeModelName='';
   for(var ci=0;ci<configured.length;ci++){
    if(configured[ci]===currentModel){
     activeModelName=_getModelDisplayName(configured[ci], models[configured[ci]], models, displayCounts);
     break;
    }
   }
  var headerBg=isExpanded?(isLight?'rgba(122,116,107,0.06)':'rgba(99,102,241,0.06)'):('transparent');
   var chevron=isExpanded?'\u25BC':'\u25B6';
   html+='<div style="border:1px solid '+borderColor+';border-radius:12px;overflow:hidden;'+(isExpanded?'box-shadow:'+(isLight?'0 2px 8px rgba(0,0,0,0.04)':'0 2px 8px rgba(0,0,0,0.12)')+';':'')+'margin-bottom:2px;">';
   html+='<div onclick="_toggleProviderGroup(\''+pk+'\')" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;background:'+headerBg+';transition:background 0.15s;">';
   html+='<span style="font-size:11px;color:'+subColor+';width:14px;text-align:center;">'+chevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+textColor+';flex:1;">'+escapeHtml(providerLabel)+'</span>';
   if(activeModelName){
   html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(122,140,109,0.12)':'rgba(52,211,153,0.12)')+';color:'+(isLight?'#6f7e63':'#34d399')+';font-size:11px;font-weight:600;">'+escapeHtml(activeModelName)+'</span>';
   }else if(!hasConfigured){
    html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(148,163,184,0.1)':'rgba(148,163,184,0.1)')+';color:'+subColor+';font-size:11px;">'+t('settings.models.notconfigured')+'</span>';
   }
   html+='</div>';
   if(isExpanded){
    html+='<div style="padding:6px 14px 12px;display:flex;flex-direction:column;gap:5px;">';
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
     html+='<span style="font-size:13px;font-weight:'+(isCurrent?'700':'500')+';color:'+textColor+';flex:1;">'+escapeHtml(_getModelDisplayName(cmid, cm, models, displayCounts))+'</span>';
     html+=visionDot;
     html+='<span style="font-size:11px;color:'+subColor+';margin-right:4px;">'+escapeHtml(cmid)+'</span>';
     if(isCurrent){
      html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(122,140,109,0.12)':'rgba(52,211,153,0.12)')+';color:'+(isLight?'#6f7e63':'#34d399')+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
     }else{
      html+='<button onclick="_sidebarSwitchModel(\''+escapeHtml(cmid)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+(isLight?'rgba(122,116,107,0.24)':'rgba(99,102,241,0.3)')+';background:none;color:'+(isLight?'#6a6258':'#6366f1')+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;" onmouseenter="this.style.background=\''+(isLight?'#6a6258':'#6366f1')+'\';this.style.color=\'#fff\'" onmouseleave="this.style.background=\'none\';this.style.color=\''+(isLight?'#6a6258':'#6366f1')+'\'">'+t('settings.models.activate')+'</button>';
     }
     html+='<button onclick="openModelDialog(\''+escapeHtml(cmid)+'\')" style="padding:3px 8px;border:1px solid '+borderColor+';border-radius:5px;background:none;color:'+subColor+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
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
    html+='<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:'+(isLight?'rgba(122,116,107,0.04)':'rgba(148,163,184,0.04)')+';border:1px dashed '+(isLight?'rgba(122,116,107,0.18)':'rgba(148,163,184,0.12)')+';border-radius:10px;">';
    html+='<span style="font-size:13px;color:'+subColor+';flex:1;">'+escapeHtml(catModel.id)+'<span style="font-size:11px;margin-left:6px;opacity:0.7;">'+escapeHtml(catModel.desc)+'</span></span>';
    if(hasConfigured){
      html+='<button onclick="_quickAddModel(\''+escapeHtml(pk)+'\',\''+escapeHtml(catModel.id)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+(isLight?'rgba(122,116,107,0.24)':'rgba(99,102,241,0.3)')+';background:none;color:'+(isLight?'#6a6258':'#6366f1')+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;" onmouseenter="this.style.background=\''+(isLight?'#6a6258':'#6366f1')+'\';this.style.color=\'#fff\'" onmouseleave="this.style.background=\'none\';this.style.color=\''+(isLight?'#6a6258':'#6366f1')+'\'">'+t('settings.models.quickadd')+'</button>';
    }
    html+='<button onclick="openCatalogModelDialog(\''+escapeHtml(catModel.id)+'\',\''+escapeHtml(pk)+'\')" style="padding:3px 8px;border:1px solid '+borderColor+';border-radius:5px;background:none;color:'+subColor+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
    html+='</div>';
   }
    html+='</div>';
   }
   html+='</div>';
  }
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
     html+='<span style="font-size:13px;font-weight:'+(uCurrent?'700':'500')+';color:'+textColor+';flex:1;">'+escapeHtml(_getModelDisplayName(umid, um, models, displayCounts))+'</span>';
     html+='<span style="font-size:11px;color:'+subColor+';margin-right:4px;">'+escapeHtml(umid)+'</span>';
     if(uCurrent){
      html+='<span style="padding:3px 10px;border-radius:5px;background:'+(isLight?'rgba(122,140,109,0.12)':'rgba(52,211,153,0.12)')+';color:'+(isLight?'#6f7e63':'#34d399')+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
    }else{
      html+='<button onclick="_sidebarSwitchModel(\''+escapeHtml(umid)+'\')" style="padding:3px 10px;border-radius:5px;border:1px solid '+(isLight?'rgba(122,116,107,0.24)':'rgba(99,102,241,0.3)')+';background:none;color:'+(isLight?'#6a6258':'#6366f1')+';font-size:11px;cursor:pointer;font-weight:500;">'+t('settings.models.activate')+'</button>';
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
 return Promise.all([
  fetch('/models/config').then(function(r){return r.json();}),
  fetch('/models/catalog').then(function(r){return r.json();}).catch(function(){return {catalog:{}};})
 ]).then(function(values){
  var d=values[0]||{};
  var c=values[1]||{};
  _settingsModels=d.models||{};
  _settingsCurrentModel=d.current||'';
  _settingsCatalog=c.catalog||{};
  var unlockedModels=_buildUnlockedSettingsModels(_settingsModels, _settingsCatalog, _settingsCurrentModel);
  var nameCounts=_buildModelNameCounts(unlockedModels);
  window._novaModels={};
  Object.keys(unlockedModels).forEach(function(k){
   var cfg=unlockedModels[k]||{};
   window._novaModels[k]={model:cfg.model||k,display_name:_getModelDisplayName(k, cfg, unlockedModels, nameCounts),vision:!!cfg.vision,base_url:cfg.base_url||'',transport:cfg.transport||'',derived:!!cfg.derived,source_model:cfg.source_model||''};
  });
  window._novaCurrentModel=_settingsCurrentModel;
  window._novaCatalog=_settingsCatalog;
  var el=document.getElementById('modelName');
  var _curCfg=unlockedModels[_settingsCurrentModel]||_settingsModels[_settingsCurrentModel];
  if(el) el.textContent=_curCfg?_getModelDisplayName(_settingsCurrentModel, _curCfg, unlockedModels, nameCounts):(_settingsCurrentModel||t('unknown'));
  if(typeof updateImageBtnState==='function') updateImageBtnState();
  renderSettingsPage(document.body.classList.contains('light'));
 }).catch(function(){
  return null;
 });
}

function _isVisibleSettingsModel(cfg){
 cfg=cfg||{};
 if(_getModelTransport(cfg)!=='openai_api') return false;
 var baseUrl=String(cfg.base_url||'').trim().toLowerCase();
 var apiKey=String(cfg.api_key||'').trim().toLowerCase();
 if(!baseUrl||!apiKey) return false;
 if(baseUrl.indexOf('codex://')===0) return false;
 if(baseUrl.indexOf('xxx')!==-1||apiKey.indexOf('xxx')!==-1) return false;
 return true;
}

function _getVisibleSettingsModels(models){
 var visible={};
 Object.keys(models||{}).forEach(function(mid){
  var cfg=models[mid]||{};
  if(_isVisibleSettingsModel(cfg)) visible[mid]=cfg;
 });
 return visible;
}

function _pickVisibleProviderDonor(providerKey, visibleModels, currentModel, catalog){
 if(currentModel&&visibleModels[currentModel]&&_classifyModelToProvider(currentModel, visibleModels[currentModel], catalog)===providerKey){
  return {id:currentModel,cfg:visibleModels[currentModel]};
 }
 var keys=Object.keys(visibleModels||{});
 for(var i=0;i<keys.length;i++){
  var mid=keys[i];
  var cfg=visibleModels[mid]||{};
  if(_classifyModelToProvider(mid, cfg, catalog)===providerKey){
   return {id:mid,cfg:cfg};
  }
 }
 return null;
}

function _buildUnlockedSettingsModels(models, catalog, currentModel){
 var visibleModels=_getVisibleSettingsModels(models||{});
 var unlocked={};
 var existingKeys={};

 Object.keys(visibleModels).forEach(function(mid){
  var cfg=visibleModels[mid]||{};
  unlocked[mid]=cfg;
  existingKeys[String(mid||'').toLowerCase()]=true;
  existingKeys[String((cfg.model||mid)||'').toLowerCase()]=true;
 });

 Object.keys(catalog||{}).forEach(function(providerKey){
  var donor=_pickVisibleProviderDonor(providerKey, visibleModels, currentModel, catalog);
  if(!donor) return;
  var catalogModels=((catalog[providerKey]||{}).models)||[];
  catalogModels.forEach(function(entry){
   var modelId=String((entry&&entry.id)||'').trim();
   if(!modelId) return;
   var key=modelId.toLowerCase();
   if(existingKeys[key]) return;
   unlocked[modelId]={
    model:modelId,
    vision:!!donor.cfg.vision,
    transport:'openai_api',
    base_url:donor.cfg.base_url||'',
    api_key:donor.cfg.api_key||'',
    derived:true,
    source_model:donor.id,
    provider_key:providerKey
   };
  });
 });

 return unlocked;
}

function _getModelTransport(cfg){
 cfg=cfg||{};
 var transport=String(cfg.transport||'').trim().toLowerCase();
 if(transport) return transport;
 var baseUrl=String(cfg.base_url||'').trim().toLowerCase();
 if(baseUrl.indexOf('codex://')===0) return 'codex_cli';
 return 'openai_api';
}

function _formatModelDialogStatusMessage(kind, message){
 var text=String(message||'').trim();
 if(!text || kind!=='error') return text;
 var lang=(typeof getLang==='function' ? String(getLang()||'zh').toLowerCase() : 'zh');
 var statusMatch=text.match(/status\s+(\d{3})/i);
 var statusCode=statusMatch?String(statusMatch[1]||'').trim():'';
 var jsonStart=text.indexOf('{');
 if(jsonStart>=0){
  try{
   var payload=JSON.parse(text.slice(jsonStart));
   var errorBlock=(payload&&typeof payload.error==='object')?payload.error:payload;
   var errorType=String((errorBlock&&errorBlock.type)||payload.type||'').trim().toLowerCase();
   var errorMessage=String((errorBlock&&errorBlock.message)||payload.message||'').trim();
   if(/insufficient_balance/.test(errorType)||/insufficient balance/i.test(errorMessage)){
    return lang==='en'
     ? ('Model test failed: insufficient balance'+(statusCode?' (HTTP '+statusCode+')':'')+'.')
     : ('模型测试失败：余额不足'+(statusCode?'（HTTP '+statusCode+'）':'')+'。');
   }
   if(/context window exceeds limit/i.test(errorMessage)||(/bad_request_error/.test(errorType)&&/2013/.test(text))){
    return lang==='en'
     ? ('Model test failed: context window exceeds this model limit'+(statusCode?' (HTTP '+statusCode+')':'')+'.')
     : ('模型测试失败：上下文太长，超过了该模型的限制'+(statusCode?'（HTTP '+statusCode+'）':'')+'。');
   }
   if(errorMessage){
    return lang==='en'
     ? ('Model test failed: '+errorMessage+(statusCode?' (HTTP '+statusCode+')':''))
     : ('模型测试失败：'+errorMessage+(statusCode?'（HTTP '+statusCode+'）':''));
   }
  }catch(_err){}
 }
 return text;
}

function _setModelDialogStatus(kind, message){
 var box=document.getElementById('mdlTestStatus');
 if(!box) return;
  var isLight=document.body.classList.contains('light');
  var theme=(typeof _settingsPageTheme==='function'
   ? _settingsPageTheme(isLight)
   : {
      actionSecondary:'rgba(255,255,255,0.04)',
      border:'rgba(255,255,255,0.08)',
      dangerText:'#b91c1c',
      dangerBg:'rgba(239,68,68,0.12)',
      modelDialogSuccessText:isLight?'#708264':'#97ab89',
      modelDialogSuccessBg:isLight?'rgba(112,130,100,0.10)':'rgba(151,171,137,0.12)',
      modelDialogSuccessBorder:isLight?'rgba(112,130,100,0.22)':'rgba(151,171,137,0.24)',
      text:'#111827'
     });
 var text=_formatModelDialogStatusMessage(kind, message);
 if(!text){
  box.style.display='none';
  box.textContent='';
  return;
 }
 box.style.display='block';
 box.textContent=text;
 box.style.whiteSpace='pre-wrap';
 box.style.wordBreak='break-word';
 box.style.overflowWrap='anywhere';
 box.style.maxHeight='120px';
 box.style.overflowY='auto';
  box.style.background=kind==='error'
   ? (theme.dangerBg||theme.actionSecondary)
   : (kind==='success' ? (theme.modelDialogSuccessBg||theme.actionSecondary) : theme.actionSecondary);
  box.style.border='1px solid '+(
   kind==='error'
    ? (theme.dangerSoftBorder||theme.border)
    : (kind==='success' ? (theme.modelDialogSuccessBorder||theme.border) : theme.border)
  );
  box.style.color=kind==='error'
   ? theme.dangerText
   : (kind==='success' ? (theme.modelDialogSuccessText||theme.successText||theme.text) : theme.text);
}

function _setSettingsModelFeedback(kind, message){
 var state=(typeof _settingsPageState==='function'
  ? _settingsPageState()
  : ((typeof window!=='undefined' && window.settingsPanelState && typeof window.settingsPanelState==='object')
     ? window.settingsPanelState
     : null));
 if(!state) return;
 state.notice='';
 state.error='';
 if(kind==='error') state.error=String(message||'').trim();
 else state.notice=String(message||'').trim();
 renderSettingsPage(document.body.classList.contains('light'));
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

function saveModelConfig(mid,cfg,handlers){
 handlers=handlers||{};
 fetch('/models/config',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({id:mid,config:cfg})
 }).then(function(r){return r.json();}).then(function(d){
  if(d.ok){
   if(typeof handlers.onSuccess==='function') handlers.onSuccess(d);
   loadSettingsModels();
   return;
  }
  var msg=(d&&d.error)?d.error:'\u4fdd\u5b58\u5931\u8d25';
  if(typeof handlers.onError==='function') handlers.onError(msg,d||{});
  else alert(msg);
 }).catch(function(){
  if(typeof handlers.onError==='function') handlers.onError('\u4fdd\u5b58\u5931\u8d25',{});
  else alert('\u4fdd\u5b58\u5931\u8d25');
 });
}

function openCatalogModelDialog(modelId, providerKey){
 var seedId=String(modelId||'').trim();
 if(!seedId) return;
 openModelDialog('',{
  id:seedId,
  config:{
   model:seedId,
   vision:false,
   transport:'openai_api',
   base_url:''
  }
 });
}

function openModelDialog(editId, draftSeed){
 var isEdit=!!editId;
 var draft=(draftSeed&&typeof draftSeed==='object')?draftSeed:{};
 var draftId=!isEdit?String(draft.id||'').trim():'';
 var m=isEdit?(_settingsModels[editId]||{}):((draft.config&&typeof draft.config==='object')?draft.config:{});
 var isCurrent=isEdit&&editId===_settingsCurrentModel;
 var isLight=document.body.classList.contains('light');
 var bg=isLight?'#fbfaf7':'#1c1c1e';
 var border=isLight?'rgba(114,105,94,0.18)':'rgba(255,255,255,0.1)';
 var textColor=isLight?'#1c1c1e':'#e2e8f0';
 var subColor=isLight?'#64748b':'#94a3b8';
 var inputBg=isLight?'#f5f1ea':'rgba(255,255,255,0.06)';
 var labelStyle='font-size:12px;font-weight:600;color:'+subColor+';margin-bottom:5px;';
 var inputStyle='width:100%;padding:10px 14px;border-radius:10px;border:1px solid '+border+';background:'+inputBg+';color:'+textColor+';outline:none;font-size:13px;box-sizing:border-box;';
 var textInputAttrs=' spellcheck="false" autocapitalize="off" autocomplete="off"';
 var title=isEdit?t('settings.models.edit'):t('settings.models.add');
 var maskedKey='';
 var fullKey='';
 if(isEdit&&m.api_key){
  var k=m.api_key;
  fullKey=k;
  maskedKey=k.length>14?(k.slice(0,6)+'****'+k.slice(-4)):k.replace(/./g,'*');
 }

 var overlay=document.createElement('div');
 overlay.id='modelDialog';
 overlay.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;';

 var html='<div style="background:'+bg+';border:1px solid '+border+';border-radius:16px;padding:24px;width:420px;max-width:90vw;">';
 html+='<div style="font-size:16px;font-weight:600;color:'+textColor+';margin-bottom:18px;">'+escapeHtml(title)+'</div>';
 html+='<div style="display:flex;flex-direction:column;gap:14px;">';
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.id')+'</div>';
 html+='<input id="mdlId" value="'+escapeHtml(isEdit?editId:draftId)+'" placeholder="gpt-4o, claude-3 ..." style="'+inputStyle+(isEdit?'opacity:0.5;cursor:not-allowed;':'')+'"'+textInputAttrs+(isEdit?' disabled':'')+'></div>';
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.name')+'</div>';
 html+='<input id="mdlName" value="'+escapeHtml(m.model||'')+'" placeholder="'+t('settings.models.field.name.hint')+'" style="'+inputStyle+'"'+textInputAttrs+'></div>';
 html+='<div><div style="'+labelStyle+'">Base URL</div>';
 html+='<input id="mdlUrl" value="'+escapeHtml(m.base_url||'')+'" placeholder="https://api.openai.com/v1" style="'+inputStyle+'"'+textInputAttrs+'></div>';
 html+='<div><div style="'+labelStyle+'">API Key</div>';
 html+='<div style="position:relative;"><input id="mdlKey" value="" placeholder="'+(isEdit?(maskedKey||t('settings.models.field.key.hint')):'sk-...')+'" style="'+inputStyle+';padding-right:40px;"'+textInputAttrs+'>';
 if(isEdit&&fullKey){html+='<button type="button" id="mdlKeyToggle" onclick="(function(b){var inp=document.getElementById(\'mdlKey\');var showing=b.getAttribute(\'data-show\')===\'1\';if(!showing){inp.value=\''+escapeHtml(fullKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94\\\'/><path d=\\\'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19\\\'/><line x1=\\\'1\\\' y1=\\\'1\\\' x2=\\\'23\\\' y2=\\\'23\\\'/></svg>\';b.setAttribute(\'data-show\',\'1\');}else{inp.value=\'\';inp.placeholder=\''+escapeHtml(maskedKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\\\'/><circle cx=\\\'12\\\' cy=\\\'12\\\' r=\\\'3\\\'/></svg>\';b.setAttribute(\'data-show\',\'0\');}})(this)" data-show="0" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;opacity:0.5;color:'+subColor+';display:flex;align-items:center;" title="Show/Hide"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>';}
 html+='</div></div>';
 html+='<div id="mdlTestStatus" style="display:none;padding:10px 12px;border-radius:10px;font-size:12px;line-height:1.6;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere;max-height:120px;overflow-y:auto;"></div>';
 html+='<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">';
 if(isEdit&&!isCurrent){
  html+='<button onclick="_modelDialogDelete(\''+escapeHtml(editId)+'\')" style="padding:8px 14px;border-radius:8px;border:1px solid rgba(171,113,99,0.22);background:transparent;color:#9a665d;cursor:pointer;font-size:12px;opacity:0.7;transition:opacity 0.15s;" onmouseenter="this.style.opacity=\'1\'" onmouseleave="this.style.opacity=\'0.7\'">'+t('settings.models.delete')+'</button>';
 }
 html+='<div style="flex:1;"></div>';
 html+='<button id="mdlTestBtn" onclick="_modelDialogTest(\''+escapeHtml(isEdit?editId:'')+'\')" style="padding:8px 14px;border-radius:8px;border:1px solid '+border+';background:transparent;color:'+textColor+';cursor:pointer;font-size:13px;">'+t('settings.models.test')+'</button>';
 html+='<button onclick="document.getElementById(\'modelDialog\').remove()" style="padding:8px 18px;border-radius:8px;border:1px solid '+border+';background:transparent;color:'+textColor+';cursor:pointer;font-size:13px;">'+t('cancel')+'</button>';
 html+='<button onclick="_modelDialogSave(\''+escapeHtml(isEdit?editId:'')+'\')" style="padding:8px 18px;border-radius:8px;border:none;background:#6a6258;color:#fff;cursor:pointer;font-size:13px;">'+t('save')+'</button>';
 html+='</div></div></div>';

 overlay.innerHTML=html;
 document.body.appendChild(overlay);
 overlay.addEventListener('click',function(e){if(e.target===overlay)overlay.remove();});
 var first=isEdit?document.getElementById('mdlName'):document.getElementById('mdlId');
 if(first)setTimeout(function(){first.focus();},50);
}

function _collectModelDialogPayload(editId){
 var isEdit=!!editId;
 var theme=(typeof _settingsPageTheme==='function'
  ? _settingsPageTheme(document.body.classList.contains('light'))
  : {
     dangerText:'#b91c1c'
    });
 var idInput=document.getElementById('mdlId');
 var urlInput=document.getElementById('mdlUrl');
 var keyInput=document.getElementById('mdlKey');
 if(idInput) idInput.style.borderColor='';
 if(urlInput) urlInput.style.borderColor='';
 if(keyInput) keyInput.style.borderColor='';
 var mid=isEdit?editId:((idInput&&idInput.value)||'').trim();
 if(!mid){
  if(idInput) idInput.style.borderColor=theme.dangerText;
  return null;
 }
 var nameInput=document.getElementById('mdlName');
 var modelName=((nameInput&&nameInput.value)||'').trim()||mid;
 var baseUrl=((urlInput&&urlInput.value)||'').trim();
 if(!baseUrl){
  if(urlInput) urlInput.style.borderColor=theme.dangerText;
  return null;
 }
 var apiKey=((keyInput&&keyInput.value)||'').trim();
 if(!apiKey&&isEdit&&_settingsModels[editId]) apiKey=String(_settingsModels[editId].api_key||'').trim();
 if(!apiKey){
  if(keyInput) keyInput.style.borderColor=theme.dangerText;
  return null;
 }
 var previousVision=isEdit&&_settingsModels[editId]?!!_settingsModels[editId].vision:false;
 return {
  mid:mid,
  cfg:{
   model:modelName,
   vision:previousVision,
   transport:'openai_api',
   base_url:baseUrl,
   api_key:apiKey
  }
 };
}

function testModelConfig(mid, cfg, handlers){
 handlers=handlers||{};
 var payload={};
 if(mid) payload.id=mid;
 if(cfg&&typeof cfg==='object') payload.config=cfg;
 return fetch('/models/test',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify(payload)
 }).then(function(r){return r.json();}).then(function(d){
  if(d&&d.ok){
   if(typeof handlers.onSuccess==='function') handlers.onSuccess(d);
   return d;
  }
  var msg=(d&&d.error)?d.error:t('settings.models.test.fail');
  if(typeof handlers.onError==='function') handlers.onError(msg,d||{});
  throw new Error(msg);
 }).catch(function(err){
  var msg=(err&&err.message)?err.message:t('settings.models.test.fail');
  if(typeof handlers.onError==='function') handlers.onError(msg,{});
  throw err;
 }).finally(function(){
  if(typeof handlers.onFinally==='function') handlers.onFinally();
 });
}

function testConfiguredModel(mid, trigger){
 var btn=trigger||null;
 var originalText=btn?btn.textContent:'';
 if(btn){
  btn.disabled=true;
  btn.style.opacity='0.65';
  btn.textContent=t('settings.models.test.running');
 }
 testModelConfig(mid,null,{
  onSuccess:function(){
   _setSettingsModelFeedback('notice',t('settings.models.test.ok'));
  },
  onError:function(message){
   _setSettingsModelFeedback('error',message||t('settings.models.test.fail'));
  },
  onFinally:function(){
   if(!btn) return;
   btn.disabled=false;
   btn.style.opacity='';
   btn.textContent=originalText||t('settings.models.test');
  }
 }).catch(function(){});
}

function _modelDialogTest(editId){
 var payload=_collectModelDialogPayload(editId);
 if(!payload) return;
 var btn=document.getElementById('mdlTestBtn');
 var originalText=btn?btn.textContent:'';
 if(btn){
  btn.disabled=true;
  btn.style.opacity='0.65';
  btn.textContent=t('settings.models.test.running');
 }
 _setModelDialogStatus('info',t('settings.models.test.checking'));
 testModelConfig(payload.mid,payload.cfg,{
  onSuccess:function(){
   _setModelDialogStatus('success',t('settings.models.test.ok'));
  },
  onError:function(message){
   _setModelDialogStatus('error',message||t('settings.models.test.fail'));
  },
  onFinally:function(){
   if(!btn) return;
   btn.disabled=false;
   btn.style.opacity='';
   btn.textContent=originalText||t('settings.models.test');
  }
 }).catch(function(){});
}

function _modelDialogSave(editId){
 var payload=_collectModelDialogPayload(editId);
 if(!payload) return;
 _setModelDialogStatus('info',t('settings.saving'));
 saveModelConfig(payload.mid,payload.cfg,{
  onSuccess:function(){
   var dlg=document.getElementById('modelDialog');
   if(dlg) dlg.remove();
   _setSettingsModelFeedback('notice',t('settings.saved'));
  },
  onError:function(message){
   _setModelDialogStatus('error',message||t('settings.save.fail'));
  }
 });
}
