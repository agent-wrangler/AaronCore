// Window shell controls and drag behavior extracted from output.html.
var _isElectron = typeof window.novaShell !== 'undefined';
var _isPywebview = typeof window.pywebview !== 'undefined';
var _isNativeShellHost = new URLSearchParams(window.location.search).get('native_shell') === '1';
var _hasManagedWindow = !!(_isElectron || _isPywebview);
var _usesNativeWindowControls = !!(_isElectron && window.novaShell && window.novaShell.windowControlsMode === 'native-overlay');
var _windowShell = document.getElementById('windowShell');

if (_isNativeShellHost) {
  document.body.classList.add('native-shell-host');
}

if (_usesNativeWindowControls) {
  document.body.classList.add('native-window-controls');
}

if (!_hasManagedWindow) {
  document.querySelectorAll('.win-btn').forEach(function(btn){
    btn.style.display = 'none';
    btn.setAttribute('aria-hidden', 'true');
    btn.tabIndex = -1;
  });
}

function _applyWindowState(state){
  if(!_windowShell)return;
  var maximized=!!(state&&state.maximized);
  var fullscreen=!!(state&&state.fullscreen);
  _windowShell.classList.toggle('is-maximized',maximized||fullscreen);
}

if(_isElectron&&window.novaShell.onWindowState){
  window.novaShell.onWindowState(_applyWindowState);
}

function _winMinimize() {
  if (_isElectron) window.novaShell.minimize();
  else if (_isPywebview) window.pywebview.api.minimize();
}
function _winMaximize() {
  if (_isElectron) window.novaShell.maximize();
  else if (_isPywebview) window.pywebview.api.toggle_maximize();
}
function _winClose() {
  if (_isElectron) window.novaShell.close();
  else if (_isPywebview) window.pywebview.api.close_window();
}

(function(){
  if(_usesNativeWindowControls || !_hasManagedWindow)return;
  var bar=document.getElementById('topBar');
  if(!bar)return;
  var dragging=false, lastX=0, lastY=0;
  var lastClickTime=0;

  bar.addEventListener('mousedown',function(e){
    if(e.target.closest('button'))return;
    var now=Date.now();
    if(now-lastClickTime<300){
      _winMaximize();
      lastClickTime=0;
      return;
    }
    lastClickTime=now;
    dragging=true;
    lastX=e.screenX;
    lastY=e.screenY;
    e.preventDefault();
  });

  document.addEventListener('mousemove',function(e){
    if(!dragging)return;
    var dx=e.screenX-lastX;
    var dy=e.screenY-lastY;
    lastX=e.screenX;
    lastY=e.screenY;
    if(window.novaShell&&window.novaShell.dragBy) window.novaShell.dragBy(dx,dy);
  });

  document.addEventListener('mouseup',function(){
    dragging=false;
  });

  bar.style.cursor='default';
})();