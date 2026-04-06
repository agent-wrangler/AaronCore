// Final settings page render and active model management UI
// Provider-unlocked, API-only model management with inline test actions.

function renderSettingsPage(isLight){
 var box=document.getElementById('settingsBox');
 if(!box) return;
 var theme=getSettingsTheme(isLight);
 var notice=settingsPanelState.error||settingsPanelState.notice||'';
 var noticeColor=settingsPanelState.error?theme.dangerText:theme.accentText;
 var html='';
 var _isZh=getLang()==='zh';
 var languageDesc=_isZh?'切换整个应用和设置页使用的语言。':'Choose the language used across the app and settings workspace.';
 var modelDesc=_isZh?'给每个 provider 连接一次 API，常用子模型会自动解锁。':'Connect one API model under a provider once, and its common catalog models unlock automatically.';
 var pageSubtitle=_isZh?'管理界面语言和模型连接。':'Manage interface language and model connections.';
 var languageRowTitle=_isZh?'界面语言':'Interface language';
 var languageRowDesc=_isZh?'改变应用界面、设置面板和辅助说明默认使用的语言。':'Change the language used by the app, settings workspace, and helper copy.';

 html+='<div class="settings-shell">';
 html+='<div class="settings-head">';
 html+='<div class="settings-head-copy">';
 html+='<h1 class="settings-title">Settings</h1>';
 html+='<p class="settings-subtitle">'+escapeHtml(pageSubtitle)+'</p>';
 html+='</div>';
 if(notice){
  html+='<div class="settings-notice" style="color:'+noticeColor+';">'+escapeHtml(notice)+'</div>';
 }
 html+='</div>';

 html+='<div class="settings-main-pane">';
 html+='<section id="settings-language" class="settings-pane">';
 html+='<div class="settings-pane-head">';
  html+='<h2 class="settings-pane-title">'+t('settings.lang')+'</h2>';
  html+='<p class="settings-pane-desc">'+escapeHtml(languageDesc)+'</p>';
 html+='</div>';
 html+='<div class="settings-row-card">';
 html+='<div class="settings-row-copy">';
 html+='<div class="settings-row-title">'+escapeHtml(languageRowTitle)+'</div>';
 html+='<div class="settings-row-desc">'+escapeHtml(languageRowDesc)+'</div>';
 html+='</div>';
 html+='<div class="settings-segmented">';
 html+='<button type="button" onclick="setLang(\'zh\')" class="settings-segment-btn '+(_isZh?'is-active':'')+'">'+t('settings.lang.zh')+'</button>';
 html+='<button type="button" onclick="setLang(\'en\')" class="settings-segment-btn '+(!_isZh?'is-active':'')+'">'+t('settings.lang.en')+'</button>';
 html+='</div>';
 html+='</div>';
 html+='</section>';

 html+='<section id="settings-models" class="settings-pane">';
 html+='<div class="settings-pane-head">';
 html+='<h2 class="settings-pane-title">Model Access</h2>';
  html+='<p class="settings-pane-desc">'+escapeHtml(modelDesc)+'</p>';
 html+='</div>';
 html+=renderModelManageSection(isLight,theme.text,theme.sub,theme.cardBg,theme.border);
 html+='</section>';
 html+='</div>';
 html+='</div>';
 box.innerHTML=html;
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
 return parts.filter(Boolean).join(' · ');
}

function _renderSettingsModelRow(rowId, cfg, allModels, displayCounts, currentModel, theme, options){
 options=options||{};
 var isCurrent=rowId===currentModel;
 var showEdit=!!options.showEdit;
 var rowBg=isCurrent?theme.currentRowBg:theme.softRowBg;
 var rowBorder=isCurrent?theme.currentRowBorder:theme.border;
 var primaryLabel=_getModelDisplayName(rowId, cfg, allModels, displayCounts);
 var metaLabel=_settingsModelEndpointMeta(rowId, cfg);
 var html='';
 html+='<div style="display:flex;align-items:center;gap:10px;padding:11px 12px;background:'+rowBg+';border:1px solid '+rowBorder+';border-radius:10px;">';
 if(isCurrent) html+='<span style="color:'+theme.currentCheck+';font-size:14px;">\u2713</span>';
 html+='<div style="min-width:0;flex:1;display:flex;flex-direction:column;gap:3px;">';
 html+='<span style="font-size:13px;font-weight:'+(isCurrent?'700':'600')+';color:'+theme.text+';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+escapeHtml(primaryLabel)+'</span>';
 html+='<span style="font-size:11px;color:'+theme.sub+';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+escapeHtml(metaLabel)+'</span>';
 html+='</div>';
 if(isCurrent){
  html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+t('settings.models.active')+'</span>';
 }else{
  html+='<button type="button" data-model-action="switch" data-model-id="'+escapeHtml(rowId)+'" style="padding:4px 10px;border-radius:999px;border:1px solid '+theme.actionBorder+';background:none;color:'+theme.actionText+';font-size:11px;cursor:pointer;font-weight:600;">'+t('settings.models.activate')+'</button>';
 }
 if(showEdit){
  html+='<button type="button" data-model-action="edit-dialog" data-model-id="'+escapeHtml(rowId)+'" style="padding:4px 10px;border-radius:999px;border:1px solid '+theme.border+';background:none;color:'+theme.sub+';font-size:11px;cursor:pointer;">'+t('settings.models.edit')+'</button>';
 }
 html+='</div>';
 return html;
}

function renderModelManageSection(isLight,textColor,subColor,cardBg,borderColor){
 var theme=getSettingsTheme(isLight);
 var savedVisibleModels=_getVisibleSettingsModels(_settingsModels||{});
 var unlockedModels=_buildUnlockedSettingsModels(_settingsModels||{}, _settingsCatalog||{}, _settingsCurrentModel);
 var displayCounts=_buildModelNameCounts(unlockedModels);
 var html='';

 html+='<div class="settings-model-shell" style="background:'+theme.cardBg+';border:1px solid '+theme.border+';">';
 html+='<div class="settings-model-topbar">';
 html+='<div class="settings-model-copy">';
 html+='<span style="font-size:15px;font-weight:700;color:'+theme.text+';">'+t('settings.models')+'</span>';
 html+='<span style="font-size:11px;color:'+theme.sub+';">Connect one API model under a provider once, and its common catalog models unlock automatically.</span>';
 html+='</div>';
 html+='<button type="button" data-model-action="open-dialog" class="settings-inline-button" style="border:1px solid '+theme.border+';background:'+theme.actionSecondary+';color:'+theme.text+';">'+t('settings.models.add')+'</button>';
 html+='</div>';
 html+='<div id="modelListBox" class="settings-provider-list">';

 if(!_settingsModels||!_settingsCatalog){
  html+='Loading...';
 }else if(Object.keys(savedVisibleModels).length===0){
  html+='<div style="padding:18px 16px;border:1px dashed '+theme.border+';border-radius:12px;background:'+theme.softRowBg+';color:'+theme.sub+';font-size:12px;line-height:1.8;">';
  html+='No provider connection is active yet. Add one API model first; after that, the common models from the same provider will appear automatically.';
  html+='</div>';
 }else{
  var shownIds={};
  Object.keys(_settingsCatalog||{}).forEach(function(providerKey){
   var donor=_pickVisibleProviderDonor(providerKey, savedVisibleModels, _settingsCurrentModel, _settingsCatalog);
   if(!donor) return;
   var providerInfo=_settingsCatalog[providerKey]||{};
   var isExpanded=_settingsExpandedProviders[providerKey]!==undefined?_settingsExpandedProviders[providerKey]:(providerKey===_classifyModelToProvider(_settingsCurrentModel, unlockedModels[_settingsCurrentModel]||savedVisibleModels[_settingsCurrentModel]||{}, _settingsCatalog));
   var chevron=isExpanded?'\u25BC':'\u25B6';
   var providerLabel=providerKey.charAt(0).toUpperCase()+providerKey.slice(1);
   var activeModelName='';
   if(_settingsCurrentModel&&_classifyModelToProvider(_settingsCurrentModel, unlockedModels[_settingsCurrentModel]||savedVisibleModels[_settingsCurrentModel]||{}, _settingsCatalog)===providerKey){
    var activeCfg=unlockedModels[_settingsCurrentModel]||savedVisibleModels[_settingsCurrentModel]||{};
    activeModelName=_getModelDisplayName(_settingsCurrentModel, activeCfg, unlockedModels, displayCounts);
   }

   html+='<div class="settings-provider-group" style="border:1px solid '+theme.border+';">';
   html+='<div data-model-action="toggle-provider" data-provider-key="'+escapeHtml(providerKey)+'" class="settings-provider-header" style="background:'+(isExpanded?theme.headerBg:'transparent')+';">';
   html+='<span style="font-size:11px;color:'+theme.sub+';width:14px;text-align:center;">'+chevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';flex:1;">'+escapeHtml(providerLabel)+'</span>';
   if(activeModelName){
    html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.successBg+';color:'+theme.successText+';font-size:11px;font-weight:600;">'+escapeHtml(activeModelName)+'</span>';
   }else{
    var modelCount=(providerInfo.models||[]).length||1;
    html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.inactiveTagBg+';color:'+theme.inactiveTagText+';font-size:11px;">'+modelCount+' models</span>';
   }
   if(donor&&donor.id){
    html+='<button type="button" data-model-action="edit-dialog" data-model-id="'+escapeHtml(donor.id)+'" class="settings-inline-button is-small" style="border:1px solid '+theme.border+';background:'+theme.actionSecondary+';color:'+theme.text+';">'+t('settings.models.edit')+'</button>';
   }
   html+='</div>';

  if(isExpanded){
    html+='<div class="settings-provider-body">';
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
      var rowCfg=(matchedId?(savedVisibleModels[matchedId]||{}):(unlockedModels[modelId]||{}));
      if(!rowCfg||!Object.keys(rowCfg).length) return;
      shownIds[rowId]=true;
      html+=_renderSettingsModelRow(rowId, rowCfg, unlockedModels, displayCounts, _settingsCurrentModel, theme, {providerKey:providerKey, showEdit:false});
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
      html+=_renderSettingsModelRow(mid, savedVisibleModels[mid]||{}, unlockedModels, displayCounts, _settingsCurrentModel, theme, {providerKey:providerKey, showEdit:false});
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
   var uncExpanded=_settingsExpandedProviders['_other']!==undefined?_settingsExpandedProviders['_other']:true;
   var uncChevron=uncExpanded?'\u25BC':'\u25B6';
   html+='<div class="settings-provider-group" style="border:1px solid '+theme.border+';">';
   html+='<div data-model-action="toggle-provider" data-provider-key="_other" class="settings-provider-header">';
   html+='<span style="font-size:11px;color:'+theme.sub+';width:14px;text-align:center;">'+uncChevron+'</span>';
   html+='<span style="font-size:14px;font-weight:600;color:'+theme.text+';flex:1;">Other</span>';
   html+='<span style="padding:3px 10px;border-radius:999px;background:'+theme.inactiveTagBg+';color:'+theme.inactiveTagText+';font-size:11px;">'+others.length+' models</span>';
   html+='</div>';
   if(uncExpanded){
    html+='<div class="settings-provider-body">';
    others.sort(function(a,b){
      var aLabel=_getModelDisplayName(a, savedVisibleModels[a]||{}, unlockedModels, displayCounts).toLowerCase();
      var bLabel=_getModelDisplayName(b, savedVisibleModels[b]||{}, unlockedModels, displayCounts).toLowerCase();
      return aLabel.localeCompare(bLabel);
    });
    others.forEach(function(mid){
      html+=_renderSettingsModelRow(mid, savedVisibleModels[mid]||{}, unlockedModels, displayCounts, _settingsCurrentModel, theme, {providerKey:'_other', showEdit:true});
    });
    html+='</div>';
   }
   html+='</div>';
  }
 }

 html+='</div></div>';
 return html;
}

function openCatalogModelDialog(modelId, providerKey){
 var seedId=String(modelId||'').trim();
 if(!seedId) return;
 openModelDialog('',{
  id:seedId,
  config:{model:seedId}
 });
}

function openModelDialog(editId, draftSeed){
 var isEdit=!!editId;
 var draft=(draftSeed&&typeof draftSeed==='object')?draftSeed:{};
 var draftId=!isEdit?String(draft.id||'').trim():'';
 var m=isEdit?(_settingsModels[editId]||{}):((draft.config&&typeof draft.config==='object')?draft.config:{});
 var isCurrent=isEdit&&editId===_settingsCurrentModel;
 var isLight=document.body.classList.contains('light');
 var theme=getSettingsTheme(isLight);
 var labelStyle='font-size:12px;font-weight:600;color:'+theme.sub+';margin-bottom:5px;';
 var inputStyle='width:100%;padding:10px 14px;border-radius:10px;border:1px solid '+theme.border+';background:'+theme.dialogInputBg+';color:'+theme.text+';outline:none;font-size:13px;box-sizing:border-box;';
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
 overlay.style.cssText='position:fixed;inset:0;background:'+theme.dialogOverlay+';z-index:9999;display:flex;align-items:center;justify-content:center;';

 var html='<div style="background:'+theme.dialogBg+';border:1px solid '+theme.border+';border-radius:16px;padding:24px;width:440px;max-width:92vw;">';
 html+='<div style="font-size:16px;font-weight:600;color:'+theme.text+';margin-bottom:18px;">'+escapeHtml(title)+'</div>';
 html+='<div style="display:flex;flex-direction:column;gap:14px;">';
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.id')+'</div>';
 html+='<input id="mdlId" value="'+escapeHtml(isEdit?editId:draftId)+'" placeholder="deepseek-chat, claude-3-7-sonnet ..." style="'+inputStyle+(isEdit?'opacity:0.5;cursor:not-allowed;':'')+'\"'+(isEdit?' disabled':'')+'></div>';
 html+='<div><div style="'+labelStyle+'">'+t('settings.models.field.name')+'</div>';
 html+='<input id="mdlName" value="'+escapeHtml(m.model||'')+'" placeholder="'+t('settings.models.field.name.hint')+'" style="'+inputStyle+'"></div>';
 html+='<div><div style="'+labelStyle+'">Base URL</div>';
 html+='<input id="mdlUrl" value="'+escapeHtml(m.base_url||'')+'" placeholder="https://api.openai.com/v1" style="'+inputStyle+'"></div>';
 html+='<div><div style="'+labelStyle+'">API Key</div>';
 html+='<div style="position:relative;"><input id="mdlKey" value="" placeholder="'+(isEdit?(maskedKey||t('settings.models.field.key.hint')):'sk-...')+'" style="'+inputStyle+';padding-right:40px;">';
 if(isEdit&&fullKey){
  html+='<button type="button" id="mdlKeyToggle" onclick="(function(b){var inp=document.getElementById(\'mdlKey\');var showing=b.getAttribute(\'data-show\')===\'1\';if(!showing){inp.value=\''+escapeHtml(fullKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94\\\'/><path d=\\\'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19\\\'/><line x1=\\\'1\\\' y1=\\\'1\\\' x2=\\\'23\\\' y2=\\\'23\\\'/></svg>\';b.setAttribute(\'data-show\',\'1\');}else{inp.value=\'\';inp.placeholder=\''+escapeHtml(maskedKey)+'\';b.innerHTML=\'<svg width=\\\'16\\\' height=\\\'16\\\' viewBox=\\\'0 0 24 24\\\' fill=\\\'none\\\' stroke=\\\'currentColor\\\' stroke-width=\\\'2\\\'><path d=\\\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\\\'/><circle cx=\\\'12\\\' cy=\\\'12\\\' r=\\\'3\\\'/></svg>\';b.setAttribute(\'data-show\',\'0\');}})(this)" data-show="0" style="position:absolute;right:8px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;padding:4px;opacity:0.5;color:'+theme.sub+';display:flex;align-items:center;" title="Show/Hide"><svg width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2\'><path d=\'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z\'/><circle cx=\'12\' cy=\'12\' r=\'3\'/></svg></button>';
 }
 html+='</div></div>';
 html+='<div style="padding:10px 12px;border:1px dashed '+theme.border+';border-radius:10px;color:'+theme.sub+';font-size:12px;line-height:1.7;">Only API-backed models appear here. Once one provider entry is saved, its common catalog models unlock automatically.</div>';
 html+='<div id="mdlTestStatus" style="display:none;padding:10px 12px;border-radius:10px;background:'+theme.actionSecondary+';border:1px solid '+theme.border+';font-size:12px;line-height:1.6;"></div>';
 html+='<div style="display:flex;align-items:center;gap:8px;margin-top:6px;">';
 if(isEdit&&!isCurrent){
  html+='<button onclick="_modelDialogDelete(\''+escapeHtml(editId)+'\')" style="padding:8px 14px;border-radius:999px;border:1px solid '+theme.dangerSoftBorder+';background:transparent;color:'+theme.dangerSoftText+';cursor:pointer;font-size:12px;opacity:0.7;transition:opacity 0.15s;" onmouseenter="this.style.opacity=\'1\'" onmouseleave="this.style.opacity=\'0.7\'">'+t('settings.models.delete')+'</button>';
 }
 html+='<div style="flex:1;"></div>';
 html+='<button onclick="document.getElementById(\'modelDialog\').remove()" style="padding:8px 18px;border-radius:999px;border:1px solid '+theme.border+';background:transparent;color:'+theme.text+';cursor:pointer;font-size:13px;">'+t('cancel')+'</button>';
 html+='<button id="mdlTestBtn" onclick="_modelDialogTest(\''+escapeHtml(isEdit?editId:'')+'\')" style="padding:8px 18px;border-radius:999px;border:1px solid '+theme.border+';background:'+theme.actionSecondary+';color:'+theme.text+';cursor:pointer;font-size:13px;">Test</button>';
 html+='<button onclick="_modelDialogSave(\''+escapeHtml(isEdit?editId:'')+'\')" style="padding:8px 18px;border-radius:999px;border:none;background:'+theme.actionPrimary+';color:'+theme.actionPrimaryText+';cursor:pointer;font-size:13px;">'+t('save')+'</button>';
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
    var sourceModels=window._novaModels||{};
    var cfg=sourceModels[mid]||_settingsModels[mid]||{};
    var label=(cfg.display_name||cfg.model||mid);
    if(el) el.textContent=label;
    if(typeof updateImageBtnState==='function') updateImageBtnState();
    setTimeout(function(){loadSettingsModels();},300);
   }else{
    console.warn('[models][settings] switch fail', mid, d&&d.error);
    alert(d.error||'Switch failed');
    loadSettingsModels();
   }
  }).catch(function(){
   console.warn('[models][settings] switch error', mid);
   alert('Switch failed');
   loadSettingsModels();
  });
}
