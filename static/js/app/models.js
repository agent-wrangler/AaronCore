// Model switching, vision availability, and stats entry loading
// Source: app.js lines 1770-1966

// ── 模型选择器 ──
function toggleModelDropdown(e){
 e.stopPropagation();
 var dd=document.getElementById('modelDropdown');
 if(!dd)return;
 if(dd.style.display!=='none'){
  dd.style.display='none';
  return;
 }
 var models=window._novaModels||{};
 var current=window._novaCurrentModel||'';
 var catalog=window._novaCatalog||null;
 var html='';
 if(catalog&&Object.keys(catalog).length>0){
  // 按厂商分组
  var grouped={};
  var uncategorized=[];
  Object.keys(models).forEach(function(mid){
   var m=models[mid];
   var midL=mid.toLowerCase();
   var mNameL=String((m||{}).model||'').toLowerCase();
   var mUrlL=String((m||{}).base_url||'').toLowerCase();
   var pkey=null;
   // 第一轮：按模型 ID / 模型名 / 别名匹配（优先级高）
   for(var pk in catalog){
    if(midL.indexOf(pk)!==-1||mNameL.indexOf(pk)!==-1){pkey=pk;break;}
    var aliases=catalog[pk].aliases||[];
    for(var i=0;i<aliases.length;i++){if(midL.indexOf(aliases[i])!==-1||mNameL.indexOf(aliases[i])!==-1){pkey=pk;break;}}
    if(pkey)break;
   }
   // 第二轮：按 base_url 匹配（兜底）
   if(!pkey){
    for(var pk2 in catalog){
     if(catalog[pk2].url_hint&&mUrlL.indexOf(catalog[pk2].url_hint)!==-1){pkey=pk2;break;}
    }
   }
   if(pkey){
    if(!grouped[pkey])grouped[pkey]=[];
    grouped[pkey].push(mid);
   }else{
    uncategorized.push(mid);
   }
  });
  var first=true;
  for(var pk in catalog){
   var items=grouped[pk];
   if(!items||items.length===0) continue;
   if(!first) html+='<div style="height:1px;background:rgba(128,128,128,0.15);margin:4px 0;"></div>';
   first=false;
   var label=pk.charAt(0).toUpperCase()+pk.slice(1);
   html+='<div class="model-dropdown-header">'+label+'</div>';
   items.forEach(function(mid){
    var m=models[mid];
    var displayName=m.display_name||m.model||mid;
    var active=mid===current?' active':'';
    var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
    html+='<div class="model-dropdown-item'+active+'" data-model-id="'+escapeHtml(mid)+'">'+displayName+vision+'</div>';
   });
  }
  if(uncategorized.length>0){
   if(!first) html+='<div style="height:1px;background:rgba(128,128,128,0.15);margin:4px 0;"></div>';
   html+='<div class="model-dropdown-header">Other</div>';
   uncategorized.forEach(function(mid){
    var m=models[mid];
    var displayName=m.display_name||m.model||mid;
    var active=mid===current?' active':'';
    var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
    html+='<div class="model-dropdown-item'+active+'" data-model-id="'+escapeHtml(mid)+'">'+displayName+vision+'</div>';
   });
  }
 }else{
  // fallback: 无 catalog 时扁平列表
  Object.keys(models).forEach(function(mid){
   var m=models[mid];
   var displayName=m.display_name||m.model||mid;
   var active=mid===current?' active':'';
   var vision=m.vision?' <span class="model-vision-tag">'+t('model.vision')+'</span>':'';
   html+='<div class="model-dropdown-item'+active+'" data-model-id="'+escapeHtml(mid)+'">'+displayName+vision+'</div>';
  });
 }
 dd.innerHTML=html;
 dd.onclick=function(evt){
  evt.stopPropagation();
  var target=evt.target;
  if(!target||!target.closest) return;
  var item=target.closest('.model-dropdown-item[data-model-id]');
  if(!item) return;
  var modelId=String(item.getAttribute('data-model-id')||'').trim();
  if(!modelId) return;
  console.log('[models][sidebar] click', modelId);
  _sidebarSwitchModel(modelId);
 };
 dd.style.display='block';
 // 点击其他地方关闭
 setTimeout(function(){
  document.addEventListener('click',_closeModelDropdown,{once:true});
 },0);
}
function _closeModelDropdown(){
 var dd=document.getElementById('modelDropdown');
 if(dd) dd.style.display='none';
}
function _resetModelSwitchButtons(){
 var items=document.querySelectorAll('[onclick*="switchModel"],[onclick*="_sidebarSwitchModel"],[data-model-action="switch"]');
 items.forEach(function(it){
  it.style.pointerEvents='';
  it.style.opacity='';
  it.style.outline='';
  it.style.outlineOffset='';
 });
 return items;
}
function _restoreModelSwitchState(previousModel, previousLabel, previousSettingsModel){
 window._novaCurrentModel=previousModel||'';
 _setModelLabel(previousLabel||t('unknown'));
 if(typeof _settingsCurrentModel!=='undefined'){
  _settingsCurrentModel=previousSettingsModel||'';
 }
 _resetModelSwitchButtons();
 if(typeof updateImageBtnState==='function') updateImageBtnState();
}
function _alertModelSwitchFailure(detail){
 var text=String(detail||'').trim()||'切换失败，请检查模型配置或网络连接';
 try{
  alert(text);
 }catch(_err){}
}
function _emitSidebarModelSwitchNote(fromLabel, toLabel){
 if(window._currentTab!==1) return;
 if(typeof addChatEventNote!=='function') return;
 var previous=String(fromLabel||'').trim();
 var next=String(toLabel||'').trim();
 if(!next || previous===next) return;
 var text=previous ? (previous+' → '+next) : next;
 addChatEventNote('model-switch', 'MODEL SWITCH', text);
}
function _sidebarSwitchModel(mid){
 // 即时关闭 dropdown
 var dd=document.getElementById('modelDropdown');
 if(dd) dd.style.display='none';
 var previousModel=window._novaCurrentModel||'';
  if(mid===previousModel) return;
  console.log('[models][sidebar] switch start', mid, 'current=', previousModel||'');
 var previousSettingsModel=(typeof _settingsCurrentModel!=='undefined')?_settingsCurrentModel:'';
 var previousCfg=(window._novaModels||{})[previousModel];
 var previousLabel=(previousCfg&&(previousCfg.display_name||previousCfg.model))?(previousCfg.display_name||previousCfg.model):(previousModel||t('unknown'));
 // 即时更新侧边栏显示
 window._novaCurrentModel=mid;
 var _m=(window._novaModels||{})[mid];
 _setModelLabel((_m&&(_m.display_name||_m.model))?(_m.display_name||_m.model):mid);
 // 如果在设置页，即时高亮
 var items=_resetModelSwitchButtons();
 items.forEach(function(it){it.style.pointerEvents='none';it.style.opacity='0.5';});
 var clicked=null;
 items.forEach(function(it){
  var targetMid=String(it.getAttribute('data-model-id')||'').trim();
  var onclick=String(it.getAttribute('onclick')||'');
  if(targetMid===mid||onclick.indexOf(mid)!==-1){clicked=it;}
 });
 if(clicked){clicked.style.opacity='1';clicked.style.outline='2px solid #60a5fa';clicked.style.outlineOffset='-2px';}
 fetch('/model/'+encodeURIComponent(mid),{method:'POST'}).then(r=>r.json()).then(function(d){
  if(d.ok){
   console.log('[models][sidebar] switch ok', mid);
   _resetModelSwitchButtons();
   if(typeof updateImageBtnState==='function') updateImageBtnState();
   _emitSidebarModelSwitchNote(previousLabel, (_m&&(_m.display_name||_m.model))?(_m.display_name||_m.model):mid);
   if(typeof _settingsCurrentModel!=='undefined'){
    _settingsCurrentModel=mid;
    setTimeout(function(){if(typeof loadSettingsModels==='function') loadSettingsModels();},300);
   }
  }else{
   console.warn('[models][sidebar] switch fail', mid, d&&d.error);
   // 回滚
   _restoreModelSwitchState(previousModel, previousLabel, previousSettingsModel);
   _alertModelSwitchFailure(d&&d.error);
  }
 }).catch(function(){
  console.warn('[models][sidebar] switch error', mid);
  _restoreModelSwitchState(previousModel, previousLabel, previousSettingsModel);
  _alertModelSwitchFailure('');
 });
}
function updateImageBtnState(){
 var btn=document.getElementById('imageUploadBtn');
 if(!btn)return;
 var models=window._novaModels||{};
 var current=window._novaCurrentModel||'';
 // 只要有任何一个模型支持 vision 就启用（会自动 fallback）
 var anyVision=Object.keys(models).some(function(k){return models[k].vision;});
 btn.disabled=!anyVision;
 btn.title=anyVision?t('model.upload.title'):t('model.no.vision');
}

function loadStatsData(){
  var box=document.getElementById('statsBox');
  if(!box) return;
  var btn=document.querySelector('.stats-refresh-btn');
  if(btn) btn.classList.add('spinning');
  fetch('/stats').then(function(r){return r.json()}).then(function(d){
    var s=d.stats||d||{};
    box.innerHTML=renderStats(s);
    if(btn) btn.classList.remove('spinning');
  }).catch(function(){
    box.innerHTML='<div style="color:#ef4444;">'+t('dash.load.fail')+'</div>';
    if(btn) btn.classList.remove('spinning');
  });
}
