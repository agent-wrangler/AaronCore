// L7 锻造炉

function loadLabPage() {
  var chat = document.getElementById('chat');
  setInputVisible(false);
  chat.innerHTML =
    '<div class="settings-page" style="position:relative;z-index:1;">' +
      '<div class="lab-subtitle">这里先收失败样本、修正提案和可晋升经验，再决定什么值得真正锻进 L7。</div>' +
      '<div id="forgeNotice" class="forge-history-stats" style="margin:8px 0 14px; opacity:.72;"></div>' +
      '<div id="labBox"><div style="opacity:.72;">正在点亮锻造炉…</div></div>' +
    '</div>';
  _fetchForgeData();
}

function _fetchForgeData() {
  fetch('/lab/status')
    .then(function(r) { return r.json(); })
    .then(function(data) { _renderForge(data || {}); })
    .catch(function() {
      var box = document.getElementById('labBox');
      if (box) {
        box.innerHTML = '<div style="color:#ef4444;">锻造炉暂时没有点亮成功</div>';
      }
    });
}

function _renderForge(data) {
  var box = document.getElementById('labBox');
  if (!box) return;

  var summary = data.summary || {};
  var queue = data.queue || [];
  var failedRuns = data.failed_runs || [];
  var reports = data.reports || [];
  var rules = data.rules || [];

  var html = '';

  html += '<div class="forge-card forge-input-card">';
  html += '<div class="forge-card-title">投炉入口</div>';
  html += '<div class="forge-card-desc">先把值得锻的失败场景、纠偏线索或新问题放进来。这里只收候选，先观察、预演、再决定是否晋升。</div>';
  html += '<div class="forge-input-row">';
  html += '<input id="forgeNeed" class="forge-input" placeholder="比如：网页只打开了首页，却误判成搜索已经完成">';
  html += '<button class="forge-btn" onclick="submitForgeNeed()">投入锻造炉</button>';
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-card">';
  html += '<div class="forge-card-title">炉内概况</div>';
  html += '<div class="forge-history-stats">待锻候选 ' + (summary.queued || 0) + ' · 失败轨迹 ' + (summary.failed_runs || 0) + ' · 修正提案 ' + (summary.repair_reports || 0) + ' · 已晋升规则 ' + (summary.active_rules || 0) + '</div>';
  html += '</div>';

  html += _renderForgeSection('待锻候选', queue, function(item) {
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.need || item.query || '未命名需求') + '</div>';
    text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
    text += '</div>';
    if (item.source) {
      text += '<div class="forge-history-goal">来源：' + _esc(item.source) + '</div>';
    }
    text += '<div class="forge-history-stats">' + _esc(_fmtTime(item.updated_at || item.created_at)) + '</div>';
    text += '<div class="forge-history-actions">';
    if (item.status === 'queued') {
      text += '<button class="forge-action-btn primary" onclick="startLabExperiment(\'' + _escAttr(item.id) + '\')">开始锻造</button>';
    }
    if (item.status !== 'promoted') {
      text += '<button class="forge-action-btn" onclick="applyLabResult(\'' + _escAttr(item.id) + '\')">标记可晋升</button>';
    }
    text += '</div>';
    text += '</div>';
    return text;
  });

  html += _renderForgeSection('失败样本', failedRuns, function(item) {
    var meta = item.meta || {};
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.title || '未命名技能') + '</div>';
    text += '<div class="forge-status-badge danger">待锻</div>';
    text += '</div>';
    if (item.goal) {
      text += '<div class="forge-history-goal">目标：' + _esc(item.goal) + '</div>';
    }
    text += '<div class="forge-history-stats">' + _esc(item.subtitle || '这次执行没有闭环') + '</div>';
    if (meta.repair_hint) {
      text += '<div class="forge-history-goal">repair_hint：' + _esc(meta.repair_hint) + '</div>';
    }
    text += '</div>';
    return text;
  });

  html += _renderForgeSection('修正提案', reports, function(item) {
    var meta = item.meta || {};
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.title || 'L7 提案') + '</div>';
    text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
    text += '</div>';
    if (item.goal) {
      text += '<div class="forge-history-goal">相关问题：' + _esc(item.goal) + '</div>';
    }
    text += '<div class="forge-history-stats">' + _esc(item.subtitle || item.summary || '已生成一条候选提案') + '</div>';
    if (meta.risk_level) {
      text += '<div class="forge-history-goal">风险：' + _esc(meta.risk_level) + '</div>';
    }
    if (meta.preview_status || meta.preview_error || meta.preview_summary) {
      var previewText = meta.preview_summary || meta.preview_error || meta.preview_decision || '';
      if (!previewText && meta.preview_status) {
        previewText = '当前没有更多细节。';
      }
      text += '<div class="forge-history-goal">最近试炼：' + _esc(meta.preview_status || 'unknown') + (previewText ? ' / ' + _esc(_trimPreview(previewText)) : '') + '</div>';
    }
    text += '<div class="forge-history-actions">';
    text += '<button class="forge-action-btn primary" onclick="previewForgeReport(\'' + _escAttr(item.id) + '\', this)">试炼验证</button>';
    text += '</div>';
    text += '</div>';
    return text;
  });

  html += _renderForgeSection('已晋升的 L7 规则', rules, function(item) {
    var meta = item.meta || {};
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.title || 'L7 规则') + '</div>';
    text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
    text += '</div>';
    text += '<div class="forge-history-stats">' + _esc(item.subtitle || item.summary || '一条已启用规则') + '</div>';
    if (meta.hit_count) {
      text += '<div class="forge-history-goal">命中 ' + _esc(String(meta.hit_count)) + ' 次</div>';
    }
    text += '</div>';
    return text;
  });

  box.innerHTML = html;
}

function _renderForgeSection(title, rows, renderItem) {
  var html = '<div class="forge-card">';
  html += '<div class="forge-card-title">' + title + '</div>';
  if (!rows || !rows.length) {
    html += '<div class="forge-history-stats" style="opacity:.72;">这一栏暂时还是空的</div>';
    html += '</div>';
    return html;
  }
  rows.forEach(function(item) {
    html += renderItem(item || {});
  });
  html += '</div>';
  return html;
}

function submitForgeNeed() {
  var inp = document.getElementById('forgeNeed');
  var need = (inp && inp.value || '').trim();
  if (!need) return;
  inp.disabled = true;
  fetch('/lab/experiment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal: need, rounds: 1 })
  }).then(function(r) { return r.json(); }).then(function() {
    inp.disabled = false;
    inp.value = '';
    _fetchForgeData();
  }).catch(function() {
    inp.disabled = false;
  });
}

function startLabExperiment(expId) {
  fetch('/lab/start/' + expId, { method: 'POST' }).then(function() {
    _fetchForgeData();
  });
}

function stopLabExperiment() {
  fetch('/lab/stop', { method: 'POST' }).then(function() {
    _fetchForgeData();
  });
}

function applyLabResult(expId) {
  fetch('/lab/apply/' + expId, { method: 'POST' }).then(function() {
    _fetchForgeData();
  });
}

function previewForgeReport(reportId, buttonEl) {
  _setForgeNotice('正在试炼这条修正提案…');
  if (buttonEl) {
    buttonEl.disabled = true;
    buttonEl.dataset.label = buttonEl.textContent;
    buttonEl.textContent = '试炼中…';
  }
  fetch('/self_repair/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ report_id: reportId, auto_apply: false, run_validation: true })
  }).then(function(r) { return r.json(); }).then(function(data) {
    var report = data && data.report ? data.report : {};
    var preview = report.patch_preview || {};
    if (data && data.ok) {
      var status = String(preview.status || '').trim();
      if (status === 'preview_ready') {
        _setForgeNotice('试炼完成：这条提案已经通过预演，可以继续往下看。');
      } else if (status) {
        var detail = preview.error || preview.summary || preview.decision_reason || '';
        _setForgeNotice('试炼完成：当前结果是 ' + status + (detail ? ' / ' + _trimPreview(detail) : '') + '。');
      } else {
        _setForgeNotice('试炼完成：这条提案已经重新预演过了。');
      }
    } else {
      _setForgeNotice('试炼失败：' + ((data && data.error) || '暂时没有拿到结果。'));
    }
    _fetchForgeData();
  }).catch(function() {
    _setForgeNotice('试炼失败：这次没有顺利跑通。');
    _fetchForgeData();
  }).finally(function() {
    if (buttonEl) {
      buttonEl.disabled = false;
      buttonEl.textContent = buttonEl.dataset.label || '试炼验证';
    }
  });
}

function _statusText(status) {
  var key = String(status || '').trim();
  return {
    queued: '待入炉',
    reviewing: '锻造中',
    promoted: '可晋升',
    active: '已晋升',
    disabled: '已封存',
    needs_attention: '待观察'
  }[key] || key || '未知';
}

function _badgeClass(status) {
  var key = String(status || '').trim();
  if (key === 'queued' || key === 'reviewing') return 'running';
  if (key === 'promoted' || key === 'active') return 'completed';
  if (key === 'disabled') return 'stopped';
  return 'danger';
}

function _fmtTime(value) {
  var text = String(value || '').trim();
  if (!text) return '';
  return text.replace('T', ' ').slice(0, 16);
}

function _trimPreview(text) {
  var value = String(text || '').replace(/\s+/g, ' ').trim();
  if (value.length > 120) return value.slice(0, 120) + '…';
  return value;
}

function _setForgeNotice(text) {
  var el = document.getElementById('forgeNotice');
  if (!el) return;
  el.textContent = String(text || '').trim();
}

function _esc(text) {
  if (typeof _escHtml === 'function') return _escHtml(String(text || ''));
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function _escAttr(text) {
  return _esc(text).replace(/"/g, '&quot;');
}
