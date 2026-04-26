// Shared app shell markup for the web UI.
// Keeps only the window chrome and shared navigation. Page content mounts separately.
document.write(String.raw`
<div class="app-shell" id="appShell">
 <div class="top-bar" id="topBar">
  <div class="top-bar-brand">
   <div class="nova-mark" aria-hidden="true">
    <img class="nova-mark-img nova-mark-img-dark" src="/static/brand/aaroncore-logo-mark-bracket-transparent.svg" alt="">
    <img class="nova-mark-img nova-mark-img-light" src="/static/brand/aaroncore-logo-mark-bracket-light-transparent.svg" alt="">
   </div>
   <div class="nova-brand-copy">
    <div class="nova-logo">AaronCore</div>
   </div>
  </div>
  <div class="top-bar-spacer top-bar-hit-area" aria-hidden="true"></div>
  </div>

 <div class="main-container">
  <div class="sidebar">
   <div class="menu active" id="m1" onclick="show(1)"><span class="icon"><svg viewBox="0 0 24 24"><path d="M4 6.5C4 5.12 5.12 4 6.5 4h11A2.5 2.5 0 0 1 20 6.5v6A2.5 2.5 0 0 1 17.5 15H10l-4 4v-4h-.5A2.5 2.5 0 0 1 4 12.5z"/></svg></span><span class="label" data-i18n="nav.chat">聊天</span></div>
   <div class="menu" id="m2" onclick="show(2)"><span class="icon"><svg viewBox="0 0 24 24"><path d="M12 3l1.8 4.6L18.5 9 14 10.7 12 15l-2-4.3L5.5 9l4.7-1.4z"/><path d="M18 15l.9 2.1L21 18l-2.1.9L18 21l-.9-2.1L15 18l2.1-.9z"/></svg></span><span class="label" data-i18n="nav.skills">技能</span></div>
   <div class="menu" id="m3" onclick="show(3)"><span class="icon"><svg viewBox="0 0 24 24"><path d="M5 19V9"/><path d="M12 19V5"/><path d="M19 19v-7"/></svg></span><span class="label" data-i18n="nav.dashboard">驾驶舱</span></div>
   <div class="menu" id="m4" onclick="show(4)"><span class="icon"><svg viewBox="0 0 24 24"><path d="M9.5 4A3.5 3.5 0 0 0 6 7.5V12a4 4 0 0 0 4 4h1"/><path d="M14.5 4A3.5 3.5 0 0 1 18 7.5V12a4 4 0 0 1-4 4h-1"/><path d="M12 8v8"/></svg></span><span class="label" data-i18n="nav.memory">记忆</span></div>
   <div class="menu" id="m6" onclick="show(6)"><span class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg></span><span class="label" data-i18n="nav.forge">Forge</span></div>
   <div class="menu" id="m5" onclick="show(5)"><span class="icon"><svg viewBox="0 0 24 24"><path d="M12 8.5A3.5 3.5 0 1 0 12 15.5A3.5 3.5 0 1 0 12 8.5Z"/><path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.6-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.6 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .6.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6h.2a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.6z"/></svg></span><span class="label" data-i18n="nav.settings">设置</span></div>
   <div class="sidebar-footer">
    <div class="qq-monitor-indicator" id="qqMonitorDot" style="display:none;">
     <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
     <span id="qqMonitorLabel">监听中</span>
    </div>
   </div>
  </div>
  <div id="pageMount" style="flex:1;min-width:0;min-height:0;display:flex;overflow:hidden;"></div>
 </div>
</div>
`);
