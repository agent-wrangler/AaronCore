function loadLabPage() {
  var chat = document.getElementById('chat');
  setInputVisible(false);
  chat.innerHTML =
    '<div class="settings-page" style="position:relative;z-index:1;">' +
      '<div class="lab-subtitle">' + t('lab.view.subtitle') + '</div>' +
      '<div id="forgeNotice" class="forge-history-stats" style="margin:8px 0 14px; opacity:.72;"></div>' +
      '<div id="labBox"><div style="opacity:.72;">' + t('lab.loading') + '</div></div>' +
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
        box.innerHTML = '<div style="color:#ef4444;">' + t('lab.fetch.fail') + '</div>';
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
  html += '<div class="forge-card-title">' + t('lab.input.title') + '</div>';
  html += '<div class="forge-card-desc">' + t('lab.input.desc') + '</div>';
  html += '<div class="forge-input-row">';
  html += '<input id="forgeNeed" class="forge-input" placeholder="' + _escAttr(t('lab.input.placeholder')) + '">';
  html += '<button class="forge-btn" onclick="submitForgeNeed()">' + t('lab.input.submit') + '</button>';
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-card">';
  html += '<div class="forge-card-title">' + t('lab.overview.title') + '</div>';
  html += '<div class="forge-history-stats">' + tf(
    'lab.overview.summary',
    summary.queued || 0,
    summary.failed_runs || 0,
    summary.repair_reports || 0,
    summary.active_rules || 0
  ) + '</div>';
  html += '</div>';

  html += _renderForgeSection(t('lab.section.queue'), queue, function(item) {
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.need || item.query || t('lab.unnamed.need')) + '</div>';
    text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
    text += '</div>';
    if (item.source) {
      text += '<div class="forge-history-goal">' + t('lab.source') + ': ' + _esc(item.source) + '</div>';
    }
    text += '<div class="forge-history-stats">' + _esc(_fmtTime(item.updated_at || item.created_at)) + '</div>';
    text += '<div class="forge-history-actions">';
    if (item.status === 'queued') {
      text += '<button class="forge-action-btn primary" onclick="startLabExperiment(\'' + _escAttr(item.id) + '\')">' + t('lab.action.start') + '</button>';
    }
    if (item.status !== 'promoted') {
      text += '<button class="forge-action-btn" onclick="applyLabResult(\'' + _escAttr(item.id) + '\')">' + t('lab.action.promote') + '</button>';
    }
    text += '</div>';
    text += '</div>';
    return text;
  });

  html += _renderForgeSection(t('lab.section.failed'), failedRuns, function(item) {
    var meta = item.meta || {};
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.title || t('lab.unnamed.skill')) + '</div>';
    text += '<div class="forge-status-badge danger">' + t('lab.status.queued') + '</div>';
    text += '</div>';
    if (item.goal) {
      text += '<div class="forge-history-goal">' + t('lab.goal') + ': ' + _esc(item.goal) + '</div>';
    }
    text += '<div class="forge-history-stats">' + _esc(item.subtitle || t('lab.meta.noLoop')) + '</div>';
    if (meta.repair_hint) {
      text += '<div class="forge-history-goal">' + t('lab.meta.repairHint') + ': ' + _esc(meta.repair_hint) + '</div>';
    }
    text += '</div>';
    return text;
  });

  html += _renderForgeSection(t('lab.section.reports'), reports, function(item) {
    var meta = item.meta || {};
    var previewText = '';
    var text = '';

    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.title || t('lab.report.default')) + '</div>';
    text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
    text += '</div>';
    if (item.goal) {
      text += '<div class="forge-history-goal">' + t('lab.relatedIssue') + ': ' + _esc(item.goal) + '</div>';
    }
    text += '<div class="forge-history-stats">' + _esc(item.subtitle || item.summary || t('lab.meta.defaultReport')) + '</div>';
    if (meta.risk_level) {
      text += '<div class="forge-history-goal">' + t('lab.risk') + ': ' + _esc(meta.risk_level) + '</div>';
    }
    if (meta.preview_status || meta.preview_error || meta.preview_summary) {
      previewText = meta.preview_summary || meta.preview_error || meta.preview_decision_reason || '';
      if (!previewText && meta.preview_status) {
        previewText = t('lab.preview.placeholder');
      }
      text += '<div class="forge-history-goal">' + t('lab.preview') + ': ' + _esc(meta.preview_status || t('unknown')) + (previewText ? ' / ' + _esc(_trimPreview(previewText)) : '') + '</div>';
    }
    text += '<div class="forge-history-actions">';
    text += '<button class="forge-action-btn primary" onclick="previewForgeReport(\'' + _escAttr(item.id) + '\', this)">' + t('lab.action.preview') + '</button>';
    text += '</div>';
    text += '</div>';
    return text;
  });

  html += _renderForgeSection(t('lab.section.rules'), rules, function(item) {
    var meta = item.meta || {};
    var text = '';
    text += '<div class="forge-history-item">';
    text += '<div class="forge-history-header">';
    text += '<div class="forge-history-label">' + _esc(item.title || t('lab.rule.default')) + '</div>';
    text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
    text += '</div>';
    text += '<div class="forge-history-stats">' + _esc(item.subtitle || item.summary || t('lab.meta.defaultRule')) + '</div>';
    if (meta.hit_count) {
      text += '<div class="forge-history-goal">' + _esc(tf('lab.meta.hitCount', String(meta.hit_count))) + '</div>';
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
    html += '<div class="forge-history-stats" style="opacity:.72;">' + t('lab.section.empty') + '</div>';
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
  _setForgeNotice(t('lab.notice.previewing'));
  if (buttonEl) {
    buttonEl.disabled = true;
    buttonEl.dataset.label = buttonEl.textContent;
    buttonEl.textContent = t('lab.forging') + '...';
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
      var detail = preview.error || preview.summary || preview.decision_reason || '';
      if (status === 'preview_ready') {
        _setForgeNotice(t('lab.notice.previewReady'));
      } else if (status) {
        _setForgeNotice(tf('lab.notice.previewResult', status, detail ? ' / ' + _trimPreview(detail) : ''));
      } else {
        _setForgeNotice(tf('lab.notice.previewResult', t('unknown'), ''));
      }
    } else {
      _setForgeNotice(tf('lab.notice.previewFailed', ((data && data.error) || t('unknown'))));
    }
    _fetchForgeData();
  }).catch(function() {
    _setForgeNotice(t('lab.notice.previewCatch'));
    _fetchForgeData();
  }).finally(function() {
    if (buttonEl) {
      buttonEl.disabled = false;
      buttonEl.textContent = buttonEl.dataset.label || t('lab.action.preview');
    }
  });
}

function _statusText(status) {
  var key = String(status || '').trim();
  return {
    queued: t('lab.status.queued'),
    reviewing: t('lab.status.reviewing'),
    promoted: t('lab.status.promoted'),
    active: t('lab.status.active'),
    disabled: t('lab.status.disabled'),
    needs_attention: t('lab.status.needs_attention')
  }[key] || key || t('unknown');
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
  if (value.length > 120) return value.slice(0, 120) + '...';
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
