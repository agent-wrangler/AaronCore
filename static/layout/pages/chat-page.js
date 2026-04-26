// Chat page shell markup for the desktop client.
// Mounted into the shared shell so chat UI owns its DOM in one place.
(function(){
 var host=document.getElementById('pageMount');
 if(!host) return;
 host.innerHTML=String.raw`
<div class="main">
 <div class="content">
  <style>@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}</style>
  <div class="chat-shell run-panel-open" id="chatShell">
   <div class="chat-stage">
    <button id="runPanelInlineToggle" class="run-panel-inline-toggle" type="button" onclick="toggleRunPanel(true)" title="Open run panel" aria-label="Open run panel" aria-hidden="true">
   <svg viewBox="0 0 1024 1024" width="15" height="15" aria-hidden="true"><g fill="currentColor" stroke="currentColor" stroke-width="42" stroke-linejoin="round" stroke-linecap="round"><path d="M272.238 699.319a29.22 29.22 0 0 1 19.895 36.352C260.462 844.069 270.702 896 285.33 904.485c9.655 5.485 35.987 0.438 78.775-32.11 44.837-34.085 95.817-88.869 147.383-158.354a29.403 29.403 0 0 1 47.104 34.962c-54.857 73.874-109.86 132.754-159.013 170.13-40.301 30.72-75.702 46.08-105.545 46.08l-10.24-0.585A73.216 73.216 0 0 1 256 955.246c-49.883-28.819-56.832-110.446-20.114-235.96a29.257 29.257 0 0 1 36.352-19.967z"/><path d="M256 68.389c25.234-14.629 56.686-13.02 93.403 4.608 29.404 14.043 62.245 38.546 97.792 72.704 70.364 67.584 145.262 167.643 211.09 281.526a1584.384 1584.384 0 0 1 88.065 176.421c47.104-6.437 98.084-21.065 98.67-21.211 95.085-27.575 120.246-58.368 120.246-70.73 0-10.459-16.018-29.622-60.855-49.444-47.323-20.992-114.614-37.742-194.56-48.42h-0.365c-0.659-0.147-8.046-1.171-19.749-2.634a29.403 29.403 0 0 1 7.314-58.222c11.996 1.463 19.53 2.56 20.92 2.78C810.13 368.128 1024 407.99 1024 511.854c0 29.11-17.042 55.588-50.688 78.555-26.917 18.432-64.585 34.67-111.909 48.42-2.413 0.732-46.518 13.24-93.11 20.846 11.63 31.89 21.284 62.538 28.379 91.283 11.85 47.835 16.457 88.503 13.897 121.051-3.072 40.594-17.335 68.681-42.569 83.237-11.337 6.583-23.99 9.728-37.815 9.728l-8.777-0.366c-44.617-4.315-100.498-40.229-164.571-106.57a29.33 29.33 0 0 1 42.203-40.74c34.67 35.84 67.291 62.464 94.281 77.02 20.334 10.971 37.303 14.628 45.349 10.02 10.752-6.29 24.722-43.447 1.024-139.41-22.09-89.527-69.047-199.095-132.17-308.37-63.122-109.276-134.436-204.727-200.85-268.58-71.314-68.536-110.445-74.972-121.27-68.755-14.922 8.558-25.162 61.879 8.191 173.348a29.294 29.294 0 0 1-56.173 16.677c-38.4-128.366-31.89-211.675 18.578-240.86z"/><path d="M495.47 342.894a29.294 29.294 0 0 1 2.925 58.514c-128.731 6.583-244.004 22.674-324.534 45.349-90.77 25.6-115.127 52.882-115.2 65.024 0 12.068 25.16 43.154 120.246 70.656 88.576 25.6 206.848 39.716 333.093 39.716 33.792 0 67.51-1.024 100.206-3.072a29.294 29.294 0 1 1 3.657 58.588c-33.865 2.12-68.828 3.145-103.863 3.145l-49.006-0.732c-113.225-3.218-218.404-17.627-300.397-41.399-47.324-13.677-84.992-29.842-111.909-48.274C17.042 567.37 0 540.891 0 511.781c0-29.111 16.823-54.565 49.737-76.362 25.6-16.969 62.025-32.182 108.252-45.202 85.796-24.137 202.532-40.448 337.48-47.323z"/><path d="M349.403 455.9a29.33 29.33 0 0 1 51.347 28.379c-13.897 25.161-27.063 50.615-39.132 75.63a29.367 29.367 0 1 1-52.809-25.6c12.58-25.893 26.258-52.298 40.594-78.41z m200.339-282.77C641.902 75.336 717.385 39.277 768 68.534c48.055 27.721 56.32 105.033 23.698 223.451a29.294 29.294 0 0 1-28.306 21.504l-7.826-1.097a29.257 29.257 0 0 1-20.48-35.986C765 167.863 750.446 126.17 738.67 119.296c-14.995-8.63-66.34 9.216-146.286 94.062a29.33 29.33 0 1 1-42.642-40.229z"/></g></svg>
   <span>Run</span>
  </button>
    <button id="scrollToBottomBtn" class="scroll-to-bottom-btn" onclick="scrollToBottom()" title="Scroll to bottom" data-i18n-title="chat.scrollBottom" style="display:none">
   <svg viewBox="0 0 24 24" fill="none" width="18" height="18"><path d="M12 5v14M5 12l7 7 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>
  <div class="chat" id="chat">
   <!-- 娆㈣繋椤碉紙鑱婂ぉ涓虹┖鏃舵樉绀猴級 -->
   <div class="welcome" id="welcomePage">
    <div class="welcome-left">
     <div class="welcome-avatar">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" width="32" height="32"><path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.5V11h2a2 2 0 0 1 2 2v1h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2v-1H5a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1v-1a2 2 0 0 1 2-2h2V9.5C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z"/></svg>
     </div>
     <div class="welcome-title" data-i18n="welcome.title">今天想聊点什么？</div>
    <div class="welcome-sub" data-i18n="welcome.sub">AaronCore 已就绪，记忆、技能、联网全部在线</div>
     <div class="welcome-actions">
      <div class="welcome-chip" onclick="quickSend('今天常州天气怎么样')" data-i18n="welcome.chip.weather">查天气</div>
      <div class="welcome-chip" onclick="quickSend('给我讲个笑话')" data-i18n="welcome.chip.joke">讲笑话</div>
      <div class="welcome-chip" onclick="quickSend('你还记得我吗')" data-i18n="welcome.chip.memory">记忆测试</div>
      <div class="welcome-chip" onclick="quickSend('你都会什么技能')" data-i18n="welcome.chip.skills">技能列表</div>
     </div>
    </div>
    <div class="welcome-right" id="welcomeNews">
     <div class="welcome-news-title" data-i18n="welcome.news.title">今日热点</div>
     <div class="welcome-news-list" id="welcomeNewsList" data-i18n="welcome.news.loading">加载中...</div>
    </div>
   </div>
   </div>
   <aside class="run-panel" id="runPanel">
    <div class="run-panel-header">
     <div class="run-panel-header-main">
      <div class="run-panel-kicker-row">
       <div class="run-panel-kicker" id="runPanelKicker">Current Run</div>
       <div class="run-panel-status-pill state-idle" id="runPanelStatus">缁屾椽妫?/div>
      </div>
      <div class="run-panel-task" id="runPanelTask">鏉╂瑩鍣锋导姘杽閺冭埖妯夌粈鐑樻拱鏉烆喗鈧繆鈧啫鎷伴崝銊ょ稊閵?/div>
     </div>
     </div>
    <div class="run-panel-summary">
     <div class="run-panel-summary-item">
      <div class="run-panel-summary-label">鏉╂稑瀹?/div>
      <div class="run-panel-summary-value" id="runPanelProgress">0 / 0</div>
     </div>
     <div class="run-panel-summary-item">
      <div class="run-panel-summary-label">瑜版挸澧犻崝銊ょ稊</div>
      <div class="run-panel-summary-value run-panel-summary-text" id="runPanelAction">缁涘绶熼弬鎵畱閸斻劋缍?/div>
     </div>
     <div class="run-panel-summary-item">
      <div class="run-panel-summary-label">瀹歌弓楠囬崙?/div>
      <div class="run-panel-summary-value run-panel-summary-text" id="runPanelOutputs">0 閺傚洣娆?璺?0 瀹搞儱鍙?璺?0 瀵倸鐖?/div>
     </div>
    </div>
    <div class="run-panel-stream" id="runPanelStream">
     <div class="run-panel-empty" id="runPanelEmpty">瀵偓婵绔存潪顔绘崲閸斺€虫倵閿涘矁绻栭柌宀€娈?Run Stream 娴兼艾鐤勯弮鑸垫▔缁€鐑樷偓婵娾偓鍐︹偓浣稿З娴ｆ粌鎷伴幍褑顢戞潻鍥┾柤閵?/div>
    </div>
   </aside>
  </div>
  <div class="settings-page-host" id="settingsPageRoot" style="display:none;height:100%;overflow:auto;"></div>
 </div>
 <div class="input">
  <div class="repair-bar" id="repairBar" style="display:none;">
   <div class="repair-bar-inner">
    <div class="repair-bar-icon">
     <span class="repair-bar-chip" id="repairChip">L7</span>
    </div>
    <div class="repair-bar-text">
     <span class="repair-bar-headline" id="repairHeadline"></span>
     <span class="repair-bar-detail" id="repairDetail"></span>
    </div>
    <button class="repair-bar-close" onclick="hideRepairBar()" title="鍏抽棴" data-i18n-title="close">&times;</button>
   </div>
   <div class="repair-bar-progress"><div class="repair-bar-progress-fill" id="repairProgress"></div></div>
  </div>
  <div class="task-progress-bar" id="taskProgressBar" style="display:none;"></div>
  <div class="ask-user-slot" id="askUserSlot" style="display:none;"></div>
  <div class="task-plan-board" id="taskPlanBoard" style="display:none;"></div>
  <div class="input-container">
   <div id="codStatusDot" class="cod-dot cod-flash" title="CoD routing status" data-i18n-title="cod.status"></div>
   <input type="file" id="imageFileInput" accept="image/*" multiple style="display:none" onchange="handleImageFile(this)">
   <div class="inp-wrap">
    <div class="image-preview-bar" id="imagePreviewBar" style="display:none;"></div>
    <div class="inp-field-shell">
  <textarea id="inp" placeholder="与 AaronCore 对话..." data-i18n-placeholder="input.placeholder" spellcheck="false" autocorrect="off" autocapitalize="off" data-gramm="false" data-ms-editor="false" onkeydown="if(event.keyCode==13&&!event.shiftKey){event.preventDefault();send();}"></textarea>
    </div>
    <div class="inp-actions">
      <div class="model-selector-wrap composer-model-selector">
       <button class="model-selector-btn" id="modelSelectorBtn" type="button" onclick="toggleModelDropdown(event)" aria-haspopup="listbox" aria-expanded="false">
        <span id="modelName" data-i18n="loading">Loading...</span>
        <svg class="model-chevron" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
       </button>
       <div class="model-dropdown" id="modelDropdown" style="display:none;"></div>
      </div>
      <button class="image-upload-btn" id="imageUploadBtn" onclick="document.getElementById('imageFileInput').click()" title="上传图片" data-i18n-title="input.upload">
      <svg viewBox="0 0 24 24" fill="none" width="18" height="18"><path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
     </button>
     <div class="inp-actions-spacer"></div>
     <span class="inp-shortcut-hint" data-i18n="input.shortcutHint">Enter to send · Shift+Enter for newline</span>
      <button class="send-btn" onclick="if(this.classList.contains('stop-mode')){_stopGeneration();}else{send();}" id="sendBtn" title="发送消息" data-i18n-title="input.send">
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
       <path d="M12 18V6.5" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/>
       <path d="M7 11.2L12 6.5L17 11.2" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
     </button>
    </div>
   </div>
  </div>
 </div>
`;
})();
