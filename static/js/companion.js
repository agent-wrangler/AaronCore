/**
 * Nova Companion — Live2D 桌面伴侣
 * 鼠标跟踪 + 对话气泡 + 情绪驱动表情 + 口型同步 + 主动搭话 + 视觉感知
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
  var currentEmotion = 'neutral';
  var lastReplyId = '';
  var lastProactiveTs = '';
  var idleTimer = null;
  var interactionBound = false;
  var pollingStarted = false;
  var isSpeaking = false;

  // ── 情绪 → Live2D 动作映射 ──
  var EMOTION_MAP = {
    'happy':     { motionGroup: 'Idle', motionIndex: 0 },
    'sad':       { motionGroup: 'Idle', motionIndex: 2 },
    'thinking':  { motionGroup: 'Idle', motionIndex: 1 },
    'surprised': { motionGroup: 'Idle', motionIndex: 4 },
    'cute':      { motionGroup: 'TapBody', motionIndex: 0 },
    'neutral':   null  // 不触发特定动作
  };

  var ACTIVITY_MAP = {
    'thinking': { motionGroup: 'Idle', motionIndex: 1 },
    'replying': { motionGroup: 'TapBody', motionIndex: 0 },
    'skill':   { motionGroup: 'Idle', motionIndex: 3 }
  };

  var TAP_REPLIES = [
    '\u5e72\u561b\u6233\u4eba\u5bb6\uff01',
    '\u55ef\uff1f\u600e\u4e86\uff5e',
    '\u4eba\u5bb6\u5728\u8fd9\u5462\uff01',
    '\u522b\u95f9\u5566\uff5e',
    '\u54ce\u5440\uff01',
    '\u8981\u6478\u6478\u5934\u624d\u884c\u54e6~',
    '\u4e3b\u4eba\u60f3\u6211\u4e86\uff1f'
  ];

  // ── 口型同步 ──
  var lipsyncCtx = null;
  var lipsyncAnalyser = null;
  var lipsyncData = null;
  var lipsyncActive = false;

  function initLipsync() {
    try {
      lipsyncCtx = new (window.AudioContext || window.webkitAudioContext)();
      lipsyncAnalyser = lipsyncCtx.createAnalyser();
      lipsyncAnalyser.fftSize = 256;
      lipsyncData = new Uint8Array(lipsyncAnalyser.frequencyBinCount);
    } catch (e) {
      console.warn('[Companion] AudioContext not available for lipsync');
    }
  }

  function startLipsyncFromAudio(audioElement) {
    if (!lipsyncCtx || !lipsyncAnalyser || !model) return;
    try {
      var source = lipsyncCtx.createMediaElementSource(audioElement);
      source.connect(lipsyncAnalyser);
      lipsyncAnalyser.connect(lipsyncCtx.destination);
      lipsyncActive = true;
      animateLipsync();
    } catch (e) {
      // 已经连接过的 audio 元素会报错，忽略
    }
  }

  function animateLipsync() {
    if (!lipsyncActive || !model || !lipsyncAnalyser) return;
    lipsyncAnalyser.getByteFrequencyData(lipsyncData);
    // 取低频段（人声主要频率）的平均音量
    var sum = 0;
    var count = Math.min(16, lipsyncData.length);
    for (var i = 0; i < count; i++) sum += lipsyncData[i];
    var volume = sum / count / 255;  // 0~1
    // 映射到嘴型参数（ParamMouthOpenY）
    try {
      var coreModel = model.internalModel.coreModel;
      var paramIndex = coreModel.getParameterIndex('ParamMouthOpenY');
      if (paramIndex >= 0) {
        coreModel.setParameterValueByIndex(paramIndex, volume * 1.2);
      }
    } catch (e) { /* model may not have this param */ }
    requestAnimationFrame(animateLipsync);
  }

  function stopLipsync() {
    lipsyncActive = false;
    // 关闭嘴巴
    if (model) {
      try {
        var coreModel = model.internalModel.coreModel;
        var paramIndex = coreModel.getParameterIndex('ParamMouthOpenY');
        if (paramIndex >= 0) coreModel.setParameterValueByIndex(paramIndex, 0);
      } catch (e) { /* ignore */ }
    }
  }

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
    initLipsync();

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
      model = await Live2DModel.from(MODEL_PATH, { autoInteract: true });

      var ow = model.internalModel.originalWidth || model.width;
      var oh = model.internalModel.originalHeight || model.height;
      var scaleX = window.innerWidth / ow;
      var scaleY = window.innerHeight / oh;
      var scale = Math.min(scaleX, scaleY);
      model.scale.set(scale);
      model.x = (window.innerWidth - ow * scale) / 2;
      model.y = (window.innerHeight - oh * scale) / 2;

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

  // ── 情绪驱动表情 ──
  // 通过 Live2D 参数直接控制表情（比动作组更细腻）
  var EMOTION_PARAMS = {
    'happy':     { ParamEyeLOpen: 1.0, ParamEyeROpen: 1.0, ParamBrowLY: 0.5, ParamBrowRY: 0.5, ParamMouthForm: 1.0 },
    'sad':       { ParamEyeLOpen: 0.5, ParamEyeROpen: 0.5, ParamBrowLY: -0.5, ParamBrowRY: -0.5, ParamMouthForm: -0.3 },
    'thinking':  { ParamEyeLOpen: 0.7, ParamEyeROpen: 0.7, ParamBrowLY: 0.3, ParamBrowRY: -0.2, ParamMouthForm: 0 },
    'surprised': { ParamEyeLOpen: 1.3, ParamEyeROpen: 1.3, ParamBrowLY: 1.0, ParamBrowRY: 1.0, ParamMouthForm: 0.5 },
    'cute':      { ParamEyeLOpen: 0.9, ParamEyeROpen: 0.9, ParamBrowLY: 0.3, ParamBrowRY: 0.3, ParamMouthForm: 0.8 },
  };

  var EMOTION_LABELS = {
    'happy': '\u2764',      // ❤
    'sad': '\ud83d\udca7',  // 💧
    'thinking': '\ud83d\udcad', // 💭
    'surprised': '\u2757',  // ❗
    'cute': '\u2728',       // ✨
  };

  var emotionResetTimer = null;

  function applyEmotionParams(emotion) {
    if (!model || !emotion || emotion === 'neutral') return;
    var params = EMOTION_PARAMS[emotion];
    if (!params) return;
    try {
      var coreModel = model.internalModel.coreModel;
      for (var paramName in params) {
        var idx = coreModel.getParameterIndex(paramName);
        if (idx >= 0) {
          coreModel.setParameterValueByIndex(idx, params[paramName]);
        }
      }
    } catch (e) { /* model may not have these params */ }

    // 3 秒后渐退回 neutral
    clearTimeout(emotionResetTimer);
    emotionResetTimer = setTimeout(function () { resetEmotionParams(); }, 3000);
  }

  function resetEmotionParams() {
    if (!model) return;
    try {
      var coreModel = model.internalModel.coreModel;
      var defaults = { ParamBrowLY: 0, ParamBrowRY: 0, ParamMouthForm: 0 };
      for (var paramName in defaults) {
        var idx = coreModel.getParameterIndex(paramName);
        if (idx >= 0) {
          coreModel.setParameterValueByIndex(idx, defaults[paramName]);
        }
      }
    } catch (e) { /* ignore */ }
  }

  function playEmotionMotion(emotion) {
    if (!model || !emotion || emotion === 'neutral') return;
    // 先用参数驱动表情
    applyEmotionParams(emotion);
    // 再播动作组
    var mapping = EMOTION_MAP[emotion];
    if (mapping) {
      playMotion(mapping.motionGroup, mapping.motionIndex, 3);
    }
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
    var emotion = state.emotion || 'neutral';

    // 活动状态变化 → 播放对应动作
    if (activity !== currentActivity) {
      currentActivity = activity;
      if (ACTIVITY_MAP[activity]) {
        var m = ACTIVITY_MAP[activity];
        playMotion(m.motionGroup, m.motionIndex, 3);
      }
      if (activity === 'thinking') {
        showBubble('\u8ba9\u6211\u60f3\u60f3...', 5000, 'thinking');
      }
    }

    // 情绪变化 → 播放情绪动作
    if (emotion !== currentEmotion) {
      currentEmotion = emotion;
      if (activity === 'idle' || activity === 'replying') {
        playEmotionMotion(emotion);
      }
    }

    // Nova 回复了新内容 → 显示气泡 + 情绪动作 + 语音播报
    if (state.last_reply_id && state.last_reply_id !== lastReplyId) {
      lastReplyId = state.last_reply_id;
      // 先播情绪动作
      playEmotionMotion(emotion);
      if (state.last_reply_summary) {
        showBubble(state.last_reply_summary, 6000, emotion);
      }
      if (state.voice_mode) {
        var ttsText = state.last_reply_full || state.last_reply_summary || '';
        if (ttsText) {
          speakReply(ttsText);
        }
      }
    }

    // 主动搭话（视觉感知触发）
    var proactive = state.proactive || {};
    if (proactive.message && proactive.ts && proactive.ts !== lastProactiveTs) {
      lastProactiveTs = proactive.ts;
      showBubble(proactive.message, 8000, 'cute');
      playEmotionMotion('cute');
      if (state.voice_mode && proactive.message) {
        speakReply(proactive.message);
      }
    }

    // 模型切换（从 Entity 页面触发）
    if (state.model && state.model !== currentModelName && availableModels[state.model]) {
      MODEL_PATH = availableModels[state.model];
      currentModelName = state.model;
      if (model) {
        app.stage.removeChild(model);
        model.destroy();
        model = null;
      }
      clearTimeout(idleTimer);
      loadModel();
    }

    currentMood = mood;
  }

  // ── TTS 流式语音播报（带口型同步） ──
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
      stopLipsync();
      reportTTSStatus(false);
    }
  }

  function playStreamUrl(url) {
    return new Promise(function (resolve) {
      if (model && typeof model.speak === 'function') {
        model.speak(url, { volume: 0.8 });
        var started = false;
        var done = false;
        var notSpeakingSince = 0;
        function finish() { if (done) return; done = true; resolve(); }
        var check = setInterval(function () {
          if (model.speaking) {
            started = true;
            notSpeakingSince = 0;
          } else if (started) {
            if (!notSpeakingSince) notSpeakingSince = Date.now();
            if (Date.now() - notSpeakingSince > 800) {
              clearInterval(check); finish();
            }
          }
        }, 150);
        setTimeout(function () { clearInterval(check); finish(); }, 60000);
      } else {
        // Fallback: Audio 元素 + 口型同步
        var audio = new Audio(url);
        audio.volume = 0.8;
        audio.crossOrigin = 'anonymous';
        audio.onended = function () { stopLipsync(); resolve(); };
        audio.onerror = function () { stopLipsync(); resolve(); };
        audio.onplay = function () { startLipsyncFromAudio(audio); };
        audio.play().catch(function () { stopLipsync(); resolve(); });
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
      if (model && currentActivity === 'idle' && !isSpeaking) {
        var idx = Math.floor(Math.random() * 8);
        playMotion('Idle', idx, 1);
      }
      scheduleRandomIdle();
    }, delay);
  }

  // ── 气泡 ──
  function showBubble(text, duration, emotion) {
    var bubble = document.getElementById('speech-bubble');
    if (!bubble) return;
    var cleanText = (text || '').replace(/\*\*/g, '');
    // 情绪标签前缀
    var emotionLabel = (emotion && EMOTION_LABELS[emotion]) ? EMOTION_LABELS[emotion] + ' ' : '';
    bubble.textContent = emotionLabel + cleanText;
    bubble.classList.add('visible');
    // 情绪对应的气泡边框色
    if (emotion && emotion !== 'neutral') {
      bubble.dataset.emotion = emotion;
    } else {
      delete bubble.dataset.emotion;
    }
    requestAnimationFrame(function () { positionBubble(bubble); });
    clearTimeout(bubble._timer);
    bubble._timer = setTimeout(function () {
      bubble.classList.remove('visible');
      delete bubble.dataset.emotion;
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

