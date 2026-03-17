/**
 * Nova Companion — Live2D 桌面伴侣
 * 鼠标跟踪 + 对话气泡 + 丰富互动 + 状态同步
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
      // autoInteract: true → 模型自动跟踪鼠标
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
    // hit area 点击
    model.on('hit', function (hitAreas) {
      if (hitAreas.includes('Body')) {
        playMotion('TapBody', 0, 3);
        var reply = TAP_REPLIES[Math.floor(Math.random() * TAP_REPLIES.length)];
        showBubble(reply);
      }
    });

    // 如果没命中 hitArea，也响应普通点击
    model.on('pointertap', function (e) {
      // 随机播放一个 idle 动作作为反应
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
      var prev = currentActivity;
      currentActivity = activity;
      if (ACTIVITY_MAP[activity]) {
        var m = ACTIVITY_MAP[activity];
        playMotion(m.motionGroup, m.motionIndex, 3);
      }
      // 从 thinking 进入 → 显示思考气泡
      if (activity === 'thinking') {
        showBubble('\u8ba9\u6211\u60f3\u60f3...', 5000);
      }
    }

    // Nova 回复了新内容 → 显示气泡摘要
    if (state.last_reply_id && state.last_reply_id !== lastReplyId) {
      lastReplyId = state.last_reply_id;
      if (state.last_reply_summary) {
        showBubble(state.last_reply_summary, 6000);
      }
    }

    currentMood = mood;
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
    bubble.textContent = text;
    bubble.classList.add('visible');

    // 等渲染完再定位，否则 offsetWidth 为 0
    requestAnimationFrame(function () {
      positionBubble(bubble);
    });

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
    var bw = bubble.offsetWidth || 200;
    var bh = bubble.offsetHeight || 40;
    // 气泡在模型头顶上方
    var left = modelCenterX - bw / 2;
    var top = modelTop - bh - 12;
    // 边界保护
    left = Math.max(5, Math.min(left, window.innerWidth - bw - 5));
    top = Math.max(5, top);
    bubble.style.left = left + 'px';
    bubble.style.top = top + 'px';
  }

  // ── 淡出 + 长按拖拽 ──
  function bindInteraction() {
    // 长按拖拽
    var dragState = { active: false, startX: 0, startY: 0, timer: null, moved: false };
    var DRAG_DELAY = 200; // 按住 200ms 进入拖拽模式

    document.addEventListener('mousedown', function (e) {
      if (e.button !== 0) return;
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
      // 还没进入拖拽模式但已经移动了一定距离，立即进入
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

    // 淡出
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
      // 移除旧模型
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
      // 重建菜单项的勾选状态
      var items = menu.children;
      var names = Object.keys(availableModels);
      for (var i = 0; i < items.length; i++) {
        items[i].textContent = (names[i] === currentModelName ? '\u2713 ' : '   ') + names[i];
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
