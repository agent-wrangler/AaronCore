// ── Entity（实体）页面 ──

var _entityConfig = null;

function loadEntityPage(isLight) {
  var chat = document.getElementById('chat');
  setInputVisible(false);
  chat.innerHTML = '<div class="settings-page" style="position:relative;z-index:1;"><div id="entityBox">加载中...</div></div>';
  fetch('/companion/config').then(function(r) { return r.json(); }).then(function(cfg) {
    _entityConfig = cfg;
    // 检测实际运行状态，同步开关
    fetch('/companion/running').then(function(r) { return r.json(); }).then(function(d) {
      _entityConfig._running = d.running;
      renderEntityPage(isLight);
    }).catch(function() { renderEntityPage(isLight); });
  }).catch(function() {
    document.getElementById('entityBox').innerHTML = '<div style="color:#ef4444;">配置加载失败</div>';
  });
}

function renderEntityPage(isLight) {
  var box = document.getElementById('entityBox');
  if (!box || !_entityConfig) return;
  var cfg = _entityConfig;
  var cardBg = isLight ? '#ffffff' : 'rgba(36,36,40,0.95)';
  var textColor = isLight ? '#1c1c1e' : '#e2e8f0';
  var subColor = isLight ? '#64748b' : '#94a3b8';
  var borderColor = isLight ? 'rgba(148,163,184,0.22)' : 'rgba(255,255,255,0.06)';
  var accentColor = isLight ? '#6d28d9' : '#a78bfa';

  var html = '';

  // ── 总开关 ──
  var enabled = cfg.enabled !== false;
  var running = cfg._running;
  var statusText = enabled ? (running ? 'Entity 运行中' : 'Entity 启动中...') : 'Entity 已关闭';
  html += '<div style="margin-bottom:14px;background:' + cardBg + ';border:1px solid ' + borderColor + ';padding:18px 20px;border-radius:14px;display:flex;align-items:center;justify-content:space-between;">';
  html += '<div><div style="font-size:15px;font-weight:700;color:' + textColor + ';">' + statusText + '</div>';
  html += '<div style="font-size:12px;color:' + subColor + ';margin-top:4px;">桌面 Live2D 角色，会跟随对话做出反应</div></div>';
  html += '<div onclick="toggleEntity()" style="flex-shrink:0;width:44px;height:24px;border-radius:12px;background:' + (enabled ? (isLight ? '#10b981' : '#34d399') : (isLight ? '#cbd5e1' : '#475569')) + ';cursor:pointer;position:relative;transition:background 0.2s;">';
  html += '<span style="position:absolute;top:2px;' + (enabled ? 'right:2px' : 'left:2px') + ';width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:all 0.2s;"></span></div>';
  html += '</div>';

  // ── 模型选择 ──
  var models = cfg.models || {};
  var modelNames = Object.keys(models);
  html += '<div style="margin-bottom:14px;background:' + cardBg + ';border:1px solid ' + borderColor + ';padding:18px 20px;border-radius:14px;">';
  html += '<div style="font-size:14px;font-weight:700;color:' + textColor + ';margin-bottom:12px;">角色模型</div>';
  html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
  modelNames.forEach(function(name) {
    var active = name === cfg.model;
    html += '<button onclick="switchEntityModel(\'' + name + '\')" style="padding:8px 16px;border-radius:10px;border:1px solid ' + (active ? accentColor : borderColor) + ';background:' + (active ? (isLight ? 'rgba(109,40,217,0.08)' : 'rgba(167,139,250,0.12)') : cardBg) + ';color:' + (active ? accentColor : textColor) + ';font-size:13px;font-weight:' + (active ? '700' : '500') + ';cursor:pointer;transition:all 0.15s;">' + name + '</button>';
  });
  if (!modelNames.length) {
    html += '<div style="color:' + subColor + ';font-size:13px;">未检测到 Live2D 模型。将模型放入 static/live2d/ 目录即可。</div>';
  }
  html += '</div></div>';

  // ── TTS 语音 ──
  var voices = cfg.tts_voices || [];
  html += '<div style="margin-bottom:14px;background:' + cardBg + ';border:1px solid ' + borderColor + ';padding:18px 20px;border-radius:14px;">';
  html += '<div style="font-size:14px;font-weight:700;color:' + textColor + ';margin-bottom:12px;">语音合成</div>';
  html += '<div style="display:flex;flex-wrap:wrap;gap:8px;">';
  voices.forEach(function(v) {
    var active = v.id === cfg.tts_voice;
    html += '<button onclick="switchEntityVoice(\'' + v.id + '\')" style="padding:8px 16px;border-radius:10px;border:1px solid ' + (active ? accentColor : borderColor) + ';background:' + (active ? (isLight ? 'rgba(109,40,217,0.08)' : 'rgba(167,139,250,0.12)') : cardBg) + ';color:' + (active ? accentColor : textColor) + ';font-size:13px;font-weight:' + (active ? '700' : '500') + ';cursor:pointer;transition:all 0.15s;">' + v.name + '</button>';
  });
  html += '</div></div>';

  // ── 显示选项 ──
  var alwaysOnTop = cfg.always_on_top !== false;
  html += '<div style="margin-bottom:14px;background:' + cardBg + ';border:1px solid ' + borderColor + ';padding:18px 20px;border-radius:14px;">';
  html += '<div style="font-size:14px;font-weight:700;color:' + textColor + ';margin-bottom:14px;">显示选项</div>';

  // 置顶开关
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">';
  html += '<div><div style="font-size:13px;font-weight:600;color:' + textColor + ';">窗口置顶</div><div style="font-size:11px;color:' + subColor + ';">始终在其他窗口上方</div></div>';
  html += '<div onclick="toggleEntityOption(\'always_on_top\')" style="width:38px;height:22px;border-radius:11px;background:' + (alwaysOnTop ? (isLight ? '#10b981' : '#34d399') : (isLight ? '#cbd5e1' : '#475569')) + ';cursor:pointer;position:relative;">';
  html += '<span style="position:absolute;top:2px;' + (alwaysOnTop ? 'right:2px' : 'left:2px') + ';width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:all 0.15s;"></span></div>';
  html += '</div>';

  // 待机透明度
  var opacity = Math.round((cfg.opacity_idle || 0.3) * 100);
  html += '<div style="display:flex;align-items:center;justify-content:space-between;">';
  html += '<div><div style="font-size:13px;font-weight:600;color:' + textColor + ';">待机透明度</div><div style="font-size:11px;color:' + subColor + ';">鼠标离开后淡出至 ' + opacity + '%</div></div>';
  html += '<div style="display:flex;align-items:center;gap:8px;">';
  html += '<input type="range" min="10" max="100" value="' + opacity + '" oninput="updateOpacityLabel(this.value)" onchange="setEntityOpacity(this.value)" style="width:100px;accent-color:' + accentColor + ';">';
  html += '<span id="opacityLabel" style="font-size:12px;color:' + subColor + ';min-width:32px;text-align:right;">' + opacity + '%</span>';
  html += '</div></div>';

  html += '</div>';

  box.innerHTML = html;
}

// ── 交互函数 ──

function toggleEntity() {
  if (!_entityConfig) return;
  var isLight = document.body.classList.contains('light');
  var newEnabled = !_entityConfig.enabled;
  _entityConfig.enabled = newEnabled;
  renderEntityPage(isLight);
  fetch('/companion/toggle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: newEnabled })
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (!d.ok && newEnabled) {
      _entityConfig.enabled = false;
      renderEntityPage(isLight);
    }
  });
}

function switchEntityModel(name) {
  if (!_entityConfig || name === _entityConfig.model) return;
  var isLight = document.body.classList.contains('light');
  _entityConfig.model = name;
  renderEntityPage(isLight);
  // 先更新后端模型状态
  fetch('/companion/model/' + encodeURIComponent(name), { method: 'POST' }).then(function() {
    // 检测伴侣是否在运行，如果在运行则重启以加载新模型
    return fetch('/companion/running');
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.running) {
      // 关闭再启动，确保新模型生效
      fetch('/companion/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: false })
      }).then(function() {
        setTimeout(function() {
          fetch('/companion/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: true })
          });
        }, 1500);
      });
    }
  });
}

function switchEntityVoice(voiceId) {
  if (!_entityConfig) return;
  var isLight = document.body.classList.contains('light');
  _entityConfig.tts_voice = voiceId;
  fetch('/companion/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tts_voice: voiceId })
  });
  renderEntityPage(isLight);
}

function toggleEntityOption(key) {
  if (!_entityConfig) return;
  var isLight = document.body.classList.contains('light');
  _entityConfig[key] = !_entityConfig[key];
  var body = {};
  body[key] = _entityConfig[key];
  fetch('/companion/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  renderEntityPage(isLight);
}

function updateOpacityLabel(val) {
  var label = document.getElementById('opacityLabel');
  if (label) label.textContent = val + '%';
}

function setEntityOpacity(val) {
  if (!_entityConfig) return;
  _entityConfig.opacity_idle = parseInt(val, 10) / 100;
  fetch('/companion/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ opacity_idle: _entityConfig.opacity_idle })
  });
}
