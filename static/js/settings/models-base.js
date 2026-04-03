// Model management data flow and first-pass settings model actions
// Source: settings.js lines 655-994

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

