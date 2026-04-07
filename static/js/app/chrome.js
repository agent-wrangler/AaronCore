// Theme, shell chrome, sidebar, and welcome helpers
// Source: app.js lines 1-156

var _SVG_SUN='<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
var _SVG_MOON='<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
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

function _normalizeTheme(theme){
 var normalized=String(theme||'').toLowerCase();
 return normalized==='dark' ? 'dark' : 'light';
}

function _applyTheme(theme, options){
 var target=_normalizeTheme(theme);
 if(!document.body) return target;
 document.body.classList.remove('light','dark');
 document.body.classList.add(target);
 localStorage.setItem('nova_theme',target);
 _syncWindowBackdrop(target);
 _syncThemeIcon();
 if(!options||!options.deferTitlebar){
  _syncTitleBar(target);
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
 var currentTab=window._currentTab||1;
 if(currentTab!==1 && _themeNeedsViewRerender(currentTab)){
  setTimeout(function(){
   if(typeof show==='function' && window._currentTab===currentTab){
    show(currentTab);
   }
  },0);
 }
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
