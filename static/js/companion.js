/**
 * Nova Companion — Live2D 桌面伴侣
 * 鼠标跟踪 + 对话气泡 + 丰富互动 + 状态同步 + 语音交互
 */
(function () {
  'use strict';

  var MODEL_PATH = '/static/live2d/Hiyori/Hiyori.model3.json';
  var currentModelName = 'Hiyori';
  var availableModels = {};
  var POLL_INTERVAL = 1500;
  var IDLE_MOTION_MIN = 10000;
  var IDLE_MOTION_MAX = 25000;

  var model = null;
  var app = null;
  var currentActivity = 'idle';
  var currentMood = '';
  var lastReplyId = '';
  var idleTimer = null;
  var interactionBound = false;
  var pollingStarted = false;
  var isSpeaking = false;  // TTS 正在播放

  var ACTIVITY_MAP = {
    'thinking': { motionGroup: 'Idle', motionIndex: 1 },
    'replying': { motionGroup: 'TapBody', motionIndex: 0 },
    'skill':   { motionGroup: 'Idle', motionIndex: 3 }
  };

  // 点击身体的随机回复
  var TAP_REPLIES = [
    '\u5e72\u561b\u6233\u4eba\u5bb6\uff01',
    '\u55ef\uff1f\u600e\u4e86\uff5e',
    '\u4eba\u5bb6\u5728\u8fd9\u5462\uff01',
    '\u522b\u95f9\u5566\uff5e',
    '\u54ce\u5440\uff01',
    '\u8981\u6478\u6478\u5934\u624d\u884c\u54e6~',
    '\u4e3b\u4eba\u60f3\u6211\u4e86\uff1f'
  ];

  // ── 初始化 ──
  function initApp() {
    var canvas = document.getElementById('live2d-canvas');
    app = new PIXI.Application({
      view: canvas,
      transparent: true,
      backgroundAlpha: 0,
      resizeTo: window,
      antialias: true,
    });
    app.ticker.maxFPS = 30;

    // 先获取模型列表和当前选择，再加载
    fetch('/companion/models').then(function (r) { return r.json(); }).then(function (data) {
      availableModels = data.models || {};
      if (data.current && availableModels[data.current]) {
        currentModelName = data.current;
        MODEL_PATH = availableModels[data.current];
      }
      loadModel();
      buildContextMenu();
    }).catch(function () {
      loadModel();
    });
  }

  async function loadModel() {
    var loading = document.getElementById('loading');
    try {
      var Live2DModel = PIXI.live2d.Live2DModel;
      // autoInteract: true -> 模型自动跟踪鼠标
      model = await Live2DModel.from(MODEL_PATH, { autoInteract: true });

      var ow = model.internalModel.originalWidth || model.width;
      var oh = model.internalModel.originalHeight || model.height;
      var scaleX = window.innerWidth / ow;
      var scaleY = window.innerHeight / oh;
      var scale = Math.min(scaleX, scaleY);
      model.scale.set(scale);
      model.x = (window.innerWidth - ow * scale) / 2;
      model.y = (window.innerHeight - oh * scale) / 2;

      // 让模型可交互（接收鼠标事件）
      model.interactive = true;
      model.buttonMode = true;

      app.stage.addChild(model);
      if (loading) loading.classList.add('hidden');

      if (!pollingStarted) { startPolling(); pollingStarted = true; }
      scheduleRandomIdle();
      if (!interactionBound) { bindInteraction(); interactionBound = true; }
      bindModelTap();

      console.log('[Companion] Model loaded');
    } catch (err) {
      console.error('[Companion] Model load failed:', err);
      if (loading) loading.textContent = 'Live2D \u6a21\u578b\u52a0\u8f7d\u5931\u8d25';
    }
  }

  // ── 点击互动 ──
  function bindModelTap() {
    model.on('hit', function (hitAreas) {
      if (hitAreas.includes('Body')) {
        playMotion('TapBody', 0, 3);
        var reply = TAP_REPLIES[Math.floor(Math.random() * TAP_REPLIES.length)];
        showBubble(reply);
      }
    });
    model.on('pointertap', function (e) {
      var idx = Math.floor(Math.random() * 8);
      playMotion('Idle', idx, 2);
    });
  }

  function playMotion(group, index, priority) {
    if (!model) return;
    try { model.motion(group, index, priority || 2); } catch (e) { /* ignore */ }
  }

  // ── 状态轮询 ──
  function startPolling() {
    setInterval(pollState, POLL_INTERVAL);
    pollState();
  }

  async function pollState() {
    try {
      var resp = await fetch('/companion/state');
      if (!resp.ok) return;
      var state = await resp.json();
      handleStateChange(state);
    } catch (e) { /* backend not ready */ }
  }

  function handleStateChange(state) {
    var activity = state.activity || 'idle';
    var mood = state.mood || '';

    if (activity !== currentActivity) {
      currentActivity = activity;
      if (ACTIVITY_MAP[activity]) {
        var m = ACTIVITY_MAP[activity];
        playMotion(m.motionGroup, m.motionIndex, 3);
      }
      if (activity === 'thinking') {
        showBubble('\u8ba9\u6211\u60f3\u60f3...', 5000);
      }
    }

    // Nova 回复了新内容 -> 显示气泡 + 语音播报
    if (state.last_reply_id && state.last_reply_id !== lastReplyId) {
      lastReplyId = state.last_reply_id;
      if (state.last_reply_summary) {
        showBubble(state.last_reply_summary, 6000);
      }
      var ttsText = state.last_reply_full || state.last_reply_summary || '';
      if (ttsText) {
        speakReply(ttsText);
      }
    }

    currentMood = mood;
  }

  // ── TTS 流式语音播报（整段文本一次性流式） ──
  var ttsPlaying = false;

  async function speakReply(text) {
    if (!text || ttsPlaying) return;
    if (text.length > 500) text = text.substring(0, 500);

    ttsPlaying = true;
    isSpeaking = true;
    reportTTSStatus(true);

    var url = '/tts_stream?text=' + encodeURIComponent(text);

    try {
      await playStreamUrl(url);
    } catch (e) {
      console.warn('[Companion] TTS error:', e);
    } finally {
      isSpeaking = false;
      ttsPlaying = false;
      reportTTSStatus(false);
    }
  }

  function playStreamUrl(url) {
    return new Promise(function (resolve) {
      if (model && typeof model.speak === 'function') {
        model.speak(url, { volume: 0.8 });
        // 等音频真正开始播再检测结束
        var started = false;
        var done = false;
        function finish() { if (done) return; done = true; resolve(); }
        var check = setInterval(function () {
          if (model.speaking) { started = true; }
          if (started && !model.speaking) { clearInterval(check); finish(); }
        }, 200);
        setTimeout(function () { clearInterval(check); finish(); }, 60000);
      } else {
        var audio = new Audio(url);
        audio.volume = 0.8;
        audio.onended = resolve;
        audio.onerror = resolve;
        audio.play().catch(resolve);
      }
    });
  }

  function reportTTSStatus(playing) {
    fetch('/companion/tts_status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ playing: playing })
    }).catch(function(){});
  }

  // ── 随机 idle ──
  function scheduleRandomIdle() {
    var delay = IDLE_MOTION_MIN + Math.random() * (IDLE_MOTION_MAX - IDLE_MOTION_MIN);
    idleTimer = setTimeout(function () {
      if (model && currentActivity === 'idle') {
        var idx = Math.floor(Math.random() * 8);
        playMotion('Idle', idx, 1);
      }
      scheduleRandomIdle();
    }, delay);
  }

  // ── 气泡（跟随模型位置） ──
  function showBubble(text, duration) {
    var bubble = document.getElementById('speech-bubble');
    if (!bubble) return;
    bubble.textContent = (text || '').replace(/\*\*/g, '');
    bubble.classList.add('visible');
    requestAnimationFrame(function () { positionBubble(bubble); });
    clearTimeout(bubble._timer);
    bubble._timer = setTimeout(function () {
      bubble.classList.remove('visible');
    }, duration || 2500);
  }

  function positionBubble(bubble) {
    if (!model || !bubble) return;
    var scale = model.scale.x;
    var ow = model.internalModel.originalWidth || model.width / scale;
    var modelCenterX = model.x + (ow * scale * 0.5);
    var modelTop = model.y;
    var bw = bubble.offsetWidth || 220;
    var bh = bubble.offsetHeight || 60;
    var left = Math.max(5, Math.min(modelCenterX - bw / 2, window.innerWidth - bw - 5));
    var top = Math.max(5, modelTop - bh - 10);
    bubble.style.left = left + 'px';
    bubble.style.top = top + 'px';
    bubble.dataset.placement = 'top';
  }

  // ── 淡出 + 长按拖拽 ──
  function bindInteraction() {
    var dragState = { active: false, startX: 0, startY: 0, timer: null, moved: false };
    var DRAG_DELAY = 200;

    document.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
      if (e.target.closest('#mic-area')) return;
      dragState.startX = e.screenX;
      dragState.startY = e.screenY;
      dragState.moved = false;
      dragState.timer = setTimeout(function () {
        dragState.active = true;
      }, DRAG_DELAY);
    });

    document.addEventListener('mousemove', function (e) {
      if (!dragState.active && !dragState.timer) return;
      var dx = e.screenX - dragState.startX;
      var dy = e.screenY - dragState.startY;
      if (!dragState.active && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
        clearTimeout(dragState.timer);
        dragState.active = true;
      }
      if (dragState.active) {
        dragState.startX = e.screenX;
        dragState.startY = e.screenY;
        dragState.moved = true;
        if (window.electronAPI && window.electronAPI.moveWindow) {
          window.electronAPI.moveWindow(dx, dy);
        }
      }
    });

    document.addEventListener('mouseup', function () {
      clearTimeout(dragState.timer);
      dragState.timer = null;
      dragState.active = false;
    });

    var fadeTimer = null;
    document.addEventListener('mouseenter', function () {
      fadeTimer = setTimeout(function () { document.body.classList.add('faded'); }, 3000);
    });
    document.addEventListener('mouseleave', function () {
      clearTimeout(fadeTimer);
      document.body.classList.remove('faded');
    });
    document.addEventListener('mousemove', function () {
      if (document.body.classList.contains('faded')) document.body.classList.remove('faded');
      clearTimeout(fadeTimer);
      fadeTimer = setTimeout(function () {
        document.body.classList.add('faded');
      }, 3000);
    });
  }

  // ── 切换模型 ──
  async function switchModel(name) {
    if (!availableModels[name] || name === currentModelName) return;
    try {
      var resp = await fetch('/companion/model/' + name, { method: 'POST' });
      var data = await resp.json();
      if (!data.ok) return;
      MODEL_PATH = data.path;
      currentModelName = name;
      if (model) {
        app.stage.removeChild(model);
        model.destroy();
        model = null;
      }
      clearTimeout(idleTimer);
      loadModel();
      showBubble('\u6362\u88c5\u5b8c\u6210\uff5e', 2000);
    } catch (e) { /* ignore */ }
  }

  // ── 右键菜单 ──
  function buildContextMenu() {
    var menu = document.createElement('div');
    menu.id = 'ctx-menu';
    menu.style.cssText = 'display:none;position:fixed;z-index:999;background:rgba(25,25,45,0.95);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:6px 0;min-width:140px;backdrop-filter:blur(10px);box-shadow:0 8px 30px rgba(0,0,0,0.4);font-family:system-ui,"Microsoft YaHei",sans-serif;font-size:13px;';

    var names = Object.keys(availableModels);
    for (var i = 0; i < names.length; i++) {
      (function (n) {
        var item = document.createElement('div');
        item.textContent = (n === currentModelName ? '\u2713 ' : '   ') + n;
        item.style.cssText = 'padding:8px 16px;color:#e8e8f0;cursor:pointer;transition:background 0.15s;';
        item.addEventListener('mouseenter', function () { item.style.background = 'rgba(255,255,255,0.1)'; });
        item.addEventListener('mouseleave', function () { item.style.background = 'none'; });
        item.addEventListener('click', function () {
          menu.style.display = 'none';
          switchModel(n);
        });
        menu.appendChild(item);
      })(names[i]);
    }

    document.body.appendChild(menu);

    document.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      var items = menu.children;
      var menuNames = Object.keys(availableModels);
      for (var j = 0; j < items.length; j++) {
        items[j].textContent = (menuNames[j] === currentModelName ? '\u2713 ' : '   ') + menuNames[j];
      }
      menu.style.display = 'block';
      menu.style.left = Math.min(e.clientX, window.innerWidth - 160) + 'px';
      menu.style.top = Math.min(e.clientY, window.innerHeight - menu.offsetHeight - 10) + 'px';
    });

    document.addEventListener('click', function () {
      menu.style.display = 'none';
    });
  }

  window.addEventListener('resize', function () {
    if (!model) return;
    var ow = model.internalModel.originalWidth || model.width / model.scale.x;
    var oh = model.internalModel.originalHeight || model.height / model.scale.y;
    var scaleX = window.innerWidth / ow;
    var scaleY = window.innerHeight / oh;
    var scale = Math.min(scaleX, scaleY);
    model.scale.set(scale);
    model.x = (window.innerWidth - ow * scale) / 2;
    model.y = (window.innerHeight - oh * scale) / 2;
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
})();