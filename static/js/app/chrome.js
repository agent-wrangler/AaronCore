// Theme, shell chrome, sidebar, and welcome helpers
// Source: app.js lines 1-156

var _SVG_SUN='<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
var _SVG_MOON='<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
var _themeMode='light';
var _resolvedTheme='light';
var _themeMediaQuery=null;
var _themeMediaBound=false;
var _nativeSystemTheme='';
var _systemThemePollTimer=0;
var _systemThemeRequest=null;
var _nativeThemeEventBound=false;
function _syncThemeIcon(){
 var btn=document.getElementById('themeBtn');
 if(!btn) return;
 btn.innerHTML=document.body.classList.contains('light')?_SVG_SUN:_SVG_MOON;
}
function _syncTitleBar(theme){
 if(window.novaShell) window.novaShell.setTheme(theme);
 else if(window.pywebview&&window.pywebview.api&&window.pywebview.api.set_theme)
  window.pywebview.api.set_theme(theme);
}

function _syncWindowBackdrop(theme){
 var bg=theme==='light'?'#ffffff':'#262521';
 var useTransparentShell=!!(window.novaShell&&window.novaShell.transparentShell===true);
 document.documentElement.classList.remove('theme-light','theme-dark');
 document.documentElement.classList.add(theme==='light'?'theme-light':'theme-dark');
 document.documentElement.style.backgroundColor=useTransparentShell?'transparent':bg;
 if(document.body) document.body.style.backgroundColor=useTransparentShell?'transparent':bg;
  var shell=document.getElementById('windowShell');
  if(shell) shell.style.backgroundColor=bg;
}

function _normalizeThemeMode(theme){
 var normalized=String(theme||'').toLowerCase();
 if(normalized==='dark') return 'dark';
 if(normalized==='system') return 'system';
 return 'light';
}

function _themeChangeRerender(){
 var currentTab=window._currentTab||1;
 if(currentTab!==1 && _themeNeedsViewRerender(currentTab)){
  setTimeout(function(){
   if(typeof show==='function' && window._currentTab===currentTab){
    show(currentTab);
   }
  },0);
 }
}

function _handleSystemThemeChange(){
 if(_themeMode!=='system') return;
 _applyTheme('system', {persist:false, skipNativeSync:true});
 _themeChangeRerender();
}

function _ensureThemeMediaQuery(){
 if(!_themeMediaQuery && typeof window.matchMedia==='function'){
  _themeMediaQuery=window.matchMedia('(prefers-color-scheme: dark)');
 }
 if(_themeMediaQuery && !_themeMediaBound){
  if(typeof _themeMediaQuery.addEventListener==='function'){
   _themeMediaQuery.addEventListener('change', _handleSystemThemeChange);
  }else if(typeof _themeMediaQuery.addListener==='function'){
   _themeMediaQuery.addListener(_handleSystemThemeChange);
  }
  _themeMediaBound=true;
 }
 return _themeMediaQuery;
}

function _normalizeResolvedTheme(theme){
 return String(theme||'').toLowerCase()==='dark' ? 'dark' : 'light';
}

function _bindNativeThemeEvents(){
 if(_nativeThemeEventBound || typeof window==='undefined' || !window.addEventListener) return;
 if(window.novaShell&&typeof window.novaShell.onSystemTheme==='function'){
  window.novaShell.onSystemTheme(function(detail){
   var theme=_normalizeResolvedTheme(detail&&detail.theme);
   var changed=_nativeSystemTheme!==theme;
   _nativeSystemTheme=theme;
   if(changed && _themeMode==='system'){
    _applyTheme('system', {persist:false, skipNativeSync:true});
    _themeChangeRerender();
   }
  });
 }
 window.addEventListener('aaroncore-system-theme', function(event){
  var detail=event&&event.detail ? event.detail : {};
  var theme=_normalizeResolvedTheme(detail&&detail.theme);
  var changed=_nativeSystemTheme!==theme;
  _nativeSystemTheme=theme;
  if(changed && _themeMode==='system'){
   _applyTheme('system', {persist:false, skipNativeSync:true});
   _themeChangeRerender();
  }
 });
 _nativeThemeEventBound=true;
}

function _readNativeSystemTheme(){
 try{
  if(window.pywebview&&window.pywebview.api&&typeof window.pywebview.api.get_system_theme==='function'){
   return Promise.resolve(window.pywebview.api.get_system_theme()).then(function(theme){
    return _normalizeResolvedTheme(theme);
   });
  }
 }catch(e){}
 try{
  if(window.novaShell&&typeof window.novaShell.getSystemTheme==='function'){
   return Promise.resolve(window.novaShell.getSystemTheme()).then(function(theme){
    return _normalizeResolvedTheme(theme);
   });
  }
 }catch(e){}
 return Promise.resolve('');
}

function _clearSystemThemePolling(){
 if(_systemThemePollTimer){
  clearInterval(_systemThemePollTimer);
  _systemThemePollTimer=0;
 }
}

function _refreshNativeSystemTheme(options){
 if(_systemThemeRequest) return _systemThemeRequest;
 _systemThemeRequest=_readNativeSystemTheme().then(function(theme){
  if(theme==='dark' || theme==='light'){
   var changed=_nativeSystemTheme!==theme;
   _nativeSystemTheme=theme;
   if(changed && _themeMode==='system'){
    _applyTheme('system', {
     persist:false,
     skipNativeSync:true,
     deferTitlebar:!!(options&&options.deferTitlebar)
    });
    _themeChangeRerender();
   }
  }
  return _nativeSystemTheme||'';
 }).catch(function(){
  return _nativeSystemTheme||'';
 }).finally(function(){
  _systemThemeRequest=null;
 });
 return _systemThemeRequest;
}

function _syncSystemThemeTracking(options){
 _bindNativeThemeEvents();
 if(_themeMode!=='system'){
  _clearSystemThemePolling();
  return;
 }
 _refreshNativeSystemTheme(options);
 if(!_systemThemePollTimer){
  _systemThemePollTimer=setInterval(function(){
   _refreshNativeSystemTheme();
  },3000);
 }
}

function _resolveTheme(themeMode){
 var mode=_normalizeThemeMode(themeMode);
 if(mode!=='system') return mode;
 if(_nativeSystemTheme==='dark' || _nativeSystemTheme==='light'){
  return _nativeSystemTheme;
 }
 var media=_ensureThemeMediaQuery();
 return media&&media.matches ? 'dark' : 'light';
}

function _applyTheme(theme, options){
 var mode=_normalizeThemeMode(theme);
 var target=_resolveTheme(mode);
 _themeMode=mode;
 _resolvedTheme=target;
 if(document.documentElement){
  document.documentElement.setAttribute('data-theme-mode', mode);
 }
 try{
  if(!(options&&options.persist===false)){
   localStorage.setItem('nova_theme',mode);
   localStorage.setItem('novaTheme',mode);
  }
 }catch(e){}
 if(!document.body){
  if(!(options&&options.skipNativeSync)){
   _syncSystemThemeTracking(options);
  }else if(_themeMode!=='system'){
   _clearSystemThemePolling();
  }
  if(!options||!options.deferTitlebar){
   _syncTitleBar(target);
  }
  return target;
 }
 document.body.classList.remove('light','dark');
 document.body.classList.add(target);
 document.body.setAttribute('data-theme-mode', mode);
 _syncWindowBackdrop(target);
 _syncThemeIcon();
 if(!options||!options.deferTitlebar){
  _syncTitleBar(target);
 }
 if(!(options&&options.skipNativeSync)){
  _syncSystemThemeTracking(options);
 }else if(_themeMode!=='system'){
  _clearSystemThemePolling();
 }
 return target;
}

function _themeNeedsViewRerender(tab){
 var safeTab=Number(tab||0);
 return safeTab===5;
}

function toggleTheme(){
 var body=document.body;
 _applyTheme(body.classList.contains('dark')?'light':'dark');
 _themeChangeRerender();
}

function setThemeMode(theme){
 _applyTheme(theme);
 _themeChangeRerender();
 return _themeMode;
}

function getThemeMode(){
 return _themeMode;
}

function getResolvedTheme(){
 return _resolvedTheme;
}

/* ===== 侧边栏拉伸功能 ===== */
function initSidebarResize(){
 var sidebar=document.querySelector('.sidebar');
 var isResizing=false;
 var startX,startWidth;
 var MIN_SIDEBAR_WIDTH=200;
 var MAX_SIDEBAR_WIDTH=400;
 var DEFAULT_SIDEBAR_WIDTH=MIN_SIDEBAR_WIDTH;
 
 function startResize(e){
  isResizing=true;
  startX=e.clientX||e.touches[0].clientX;
  startWidth=parseInt(getComputedStyle(sidebar).width,10);
  document.addEventListener('mousemove',resize);
  document.addEventListener('mouseup',stopResize);
  document.addEventListener('touchmove',resize);
  document.addEventListener('touchend',stopResize);
  sidebar.style.transition='none';
  document.body.style.userSelect='none';
 }
 
 function resize(e){
  if(!isResizing)return;
  var clientX=e.clientX||(e.touches&&e.touches[0].clientX);
  if(!clientX)return;
  
  var diff=clientX-startX;
   var newWidth=Math.max(MIN_SIDEBAR_WIDTH,Math.min(MAX_SIDEBAR_WIDTH,startWidth+diff));
   sidebar.style.width=newWidth+'px';
 }
 
 function stopResize(){
  if(!isResizing)return;
  isResizing=false;
  sidebar.style.transition='width 0.2s';
  document.body.style.userSelect='';
  document.removeEventListener('mousemove',resize);
  document.removeEventListener('mouseup',stopResize);
  document.removeEventListener('touchmove',resize);
  document.removeEventListener('touchend',stopResize);
  
  // 保存宽度到本地存储
  localStorage.setItem('nova_sidebar_width',sidebar.style.width);
 }
 
 // 添加事件监听
 sidebar.addEventListener('mousedown',function(e){
  if(e.offsetX>sidebar.offsetWidth-8){
   startResize(e);
  }
 });
 
 sidebar.addEventListener('touchstart',function(e){
  var touchX=e.touches[0].clientX;
  var rect=sidebar.getBoundingClientRect();
  if(touchX>rect.right-20){
   startResize(e);
  }
 });
 
 // 加载保存的宽度
  var savedWidth=localStorage.getItem('nova_sidebar_width');
  if(savedWidth){
   sidebar.style.width=savedWidth;
  }else{
   sidebar.style.width=DEFAULT_SIDEBAR_WIDTH+'px';
  }
}

// setInputVisible is in utils.js

// 快捷发送（欢迎页按钮）
function quickSend(text){
 var inp=document.getElementById('inp');
 inp.value=text;
 send();
}

// 隐藏欢迎页
function loadWelcomeNews(){
 return;
 var el=document.getElementById('welcomeNewsList');
 if(!el) return;
 fetch('/skills/news/headlines').then(function(r){return r.json();}).then(function(d){
  var items=d.headlines||d.items||[];
  if(!items.length){el.innerHTML='<div style="color:#6b7280;font-size:13px;">'+t('welcome.news.empty')+'</div>';return;}
  el.innerHTML=items.slice(0,6).map(function(item){
   var title=typeof item==='string'?item:(item.title||item.text||'');
   return '<div class="welcome-news-item" onclick="quickSend(\'帮我介绍一下：'+title.replace(/'/g,'')+'\')">'+title+'</div>';
  }).join('');
 }).catch(function(){
  el.innerHTML='<div style="color:#6b7280;font-size:13px;">'+t('welcome.news.offline')+'</div>';
 });
}
function hideWelcome(){
 var w=document.getElementById('welcomePage');
 if(w) w.style.display='none';
}

function _setModelLabel(label){
 ['modelName','topModelName'].forEach(function(id){
  var el=document.getElementById(id);
  if(el) el.textContent=label;
 });
}
