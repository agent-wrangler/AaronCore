// Final settings page render and active model management UI
// Source: settings.js lines 995-1241

function renderSettingsPage(isLight){
 var box=document.getElementById('settingsBox');
 if(!box) return;
 var theme=getSettingsTheme(isLight);
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

 html+=renderModelManageSection(isLight,theme.text,theme.sub,theme.cardBg,theme.border);
 box.innerHTML=html;
}

function renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor){
 var theme=getSettingsTheme(isLight);
 var html='';
 html+='<div style="margin-top:14px;background:'+theme.cardBg+';border:1px solid '+theme.border+';padding:18px 20px;border-radius:14px;">';
 html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;">';
 html+='<span style="font-size:15px;font-weight:700;color:'+theme.text+';">'+t('settings.models')+'</span>';
 html+='<button type="button" data-model-action="open-dialog" style="padding:6px 14px;border:1px solid '+theme.border+';border-radius:8px;background:rgba(255,255,255,0.03);color:'+theme.text+';font-size:12px;cursor:pointer;">'+t('settings.models.add')+'</button>';
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
   html+='<div data-model-action="toggle-provider" data-provider-key="'+escapeHtml(pk)+'" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;background:'+headerBg+';transition:background 0.15s;">';
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
      html+='<button type="button" data-model-action="switch" data-model-id="'+escapeHtml(cmid)+'" style="padding:3px 10px;border-radius:5px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;">'+t('settings.models.activate')+'</button>';
     }
     html+='<button type="button" data-model-action="edit-dialog" data-model-id="'+escapeHtml(cmid)+'" style="padding:3px 8px;border:1px solid '+theme.border+';border-radius:5px;background:none;color:'+theme.sub+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
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
      html+='<button type="button" data-model-action="quick-add" data-provider-key="'+escapeHtml(pk)+'" data-model-id="'+escapeHtml(catModel.id)+'" style="padding:3px 10px;border-radius:5px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:500;transition:all 0.15s;">'+t('settings.models.quickadd')+'</button>';
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
   html+='<div data-model-action="toggle-provider" data-provider-key="_other" style="display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;">';
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
      html+='<button type="button" data-model-action="switch" data-model-id="'+escapeHtml(umid)+'" style="padding:3px 10px;border-radius:5px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:500;">'+t('settings.models.activate')+'</button>';
     }
     html+='<button type="button" data-model-action="edit-dialog" data-model-id="'+escapeHtml(umid)+'" style="padding:3px 8px;border:1px solid '+theme.border+';border-radius:5px;background:none;color:'+theme.sub+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
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
 console.log('[models][settings] switch start', mid, 'current=', _settingsCurrentModel||'');
 // 即时视觉反馈：禁用所有启用按钮
 var btns=document.querySelectorAll('[data-model-action="switch"],[onclick*="switchModel"]');
 btns.forEach(function(el){el.style.pointerEvents='none';el.style.opacity='0.5';});
 var clicked=null;
 btns.forEach(function(el){
  var targetMid=String(el.getAttribute('data-model-id')||'').trim();
  var onclick=String(el.getAttribute('onclick')||'');
  if(targetMid===mid||onclick.indexOf(mid)!==-1){clicked=el;}
 });
 if(clicked){clicked.style.opacity='1';clicked.textContent=t('settings.models.switching');}
 fetch('/model/'+encodeURIComponent(mid),{method:'POST'})
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.ok||d.model){
     console.log('[models][settings] switch ok', mid);
    _settingsCurrentModel=mid;
    window._novaCurrentModel=mid;
    var el=document.getElementById('modelName');
    var _sw=(_settingsModels[mid]||{}).model||mid;
    if(el) el.textContent=_sw;
    if(typeof updateImageBtnState==='function') updateImageBtnState();
    // 延迟刷新，让用户先看到切换成功
    setTimeout(function(){loadSettingsModels();},300);
    }else{
     console.warn('[models][settings] switch fail', mid, d&&d.error);
    alert(d.error||'\u5207\u6362\u5931\u8d25');
    loadSettingsModels();
   }
   }).catch(function(){
    console.warn('[models][settings] switch error', mid);
   alert('\u5207\u6362\u5931\u8d25');
   loadSettingsModels();
  });
}

