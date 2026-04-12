var _forgeLastData = null;
var _forgeSkillDraftStoreKey = 'nova_forge_skill_drafts_v1';
var _forgeSkillDraftState = _emptyForgeSkillDraft();
var _forgeActiveDraftId = '';

function _emptyForgeSkillDraft() {
  return {
    skill_name: '',
    goal: '',
    use_case: '',
    boundary: '',
    resources: ''
  };
}

function _normalizeForgeSkillDraft(input) {
  var base = _emptyForgeSkillDraft();
  var data = input && typeof input === 'object' ? input : {};
  Object.keys(base).forEach(function(key) {
    base[key] = String(data[key] || '').trim();
  });
  return base;
}

function _mergeForgeSkillDraft(seed) {
  var current = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  var next = _normalizeForgeSkillDraft(seed);
  Object.keys(current).forEach(function(key) {
    if (!next[key]) next[key] = current[key];
  });
  return next;
}

function _loadForgeSkillDraftIndex() {
  try {
    var raw = localStorage.getItem(_forgeSkillDraftStoreKey);
    var parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (err) {
    return {};
  }
}

function _saveForgeSkillDraftIndex(index) {
  try {
    localStorage.setItem(_forgeSkillDraftStoreKey, JSON.stringify(index || {}));
  } catch (err) {}
}

function _rememberForgeSkillDraft(expId, draft) {
  var id = String(expId || '').trim();
  if (!id) return;
  var index = _loadForgeSkillDraftIndex();
  index[id] = Object.assign(_normalizeForgeSkillDraft(draft), {
    saved_at: Date.now()
  });

  var keys = Object.keys(index);
  if (keys.length > 80) {
    keys.sort(function(a, b) {
      var aTime = Number((index[a] || {}).saved_at || 0);
      var bTime = Number((index[b] || {}).saved_at || 0);
      return bTime - aTime;
    });
    var trimmed = {};
    keys.slice(0, 80).forEach(function(key) {
      trimmed[key] = index[key];
    });
    index = trimmed;
  }

  _saveForgeSkillDraftIndex(index);
}

function _getForgeSkillDraft(expId) {
  var index = _loadForgeSkillDraftIndex();
  return _normalizeForgeSkillDraft(index[String(expId || '').trim()] || {});
}

function _hasForgeSkillDraft(expId) {
  var draft = _getForgeSkillDraft(expId);
  return !!(draft.skill_name || draft.goal || draft.use_case || draft.boundary || draft.resources);
}

function _buildForgeQueueNeed(draft) {
  var data = _normalizeForgeSkillDraft(draft);
  if (data.skill_name && data.goal) return data.skill_name + ': ' + data.goal;
  return data.goal || data.skill_name || '';
}

function _syncForgeSkillField(field, value) {
  var key = String(field || '').trim();
  if (!_forgeSkillDraftState || typeof _forgeSkillDraftState !== 'object') {
    _forgeSkillDraftState = _emptyForgeSkillDraft();
  }
  if (!Object.prototype.hasOwnProperty.call(_forgeSkillDraftState, key)) return;
  _forgeSkillDraftState[key] = String(value || '');
}

function _readForgeSkillComposerFromDom() {
  var next = _emptyForgeSkillDraft();
  [
    ['skill_name', 'forgeSkillName'],
    ['goal', 'forgeSkillGoal'],
    ['use_case', 'forgeSkillUseCase'],
    ['boundary', 'forgeSkillBoundary'],
    ['resources', 'forgeSkillResources']
  ].forEach(function(pair) {
    var field = pair[0];
    var id = pair[1];
    var el = document.getElementById(id);
    next[field] = String((el && el.value) || _forgeSkillDraftState[field] || '').trim();
  });
  _forgeSkillDraftState = next;
  return next;
}

function _resetForgeDraftComposer() {
  _forgeSkillDraftState = _emptyForgeSkillDraft();
  _forgeActiveDraftId = '';
}

function _setForgeComposerMode(mode, seed) {
  _forgeSkillDraftState = _mergeForgeSkillDraft(seed || {});
  _forgeActiveDraftId = '';
  if (window._currentTab === 6 && _forgeLastData) {
    _renderForge(_forgeLastData);
  }
}

window._setForgeComposerMode = _setForgeComposerMode;

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
    .then(function(data) {
      _forgeLastData = data || {};
      _renderForge(_forgeLastData);
    })
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

  var queue = Array.isArray(data.queue) ? data.queue : [];
  var drafts = queue.filter(function(item) {
    return _hasForgeSkillDraft(item && item.id);
  });

  var html = '';
  html += _renderForgeComposerCard();
  html += '<div class="forge-card">';
  html += '<div class="forge-card-title">' + t('lab.workspace.title') + '</div>';
  html += '<div class="forge-card-desc">' + t('lab.workspace.desc') + '</div>';
  html += '<div class="forge-history-stats">' + tf('lab.workspace.summary', drafts.length) + '</div>';
  html += '</div>';
  html += _renderForgeSection(
    t('lab.section.drafts'),
    drafts,
    _renderForgeDraftItem,
    t('lab.section.drafts.empty')
  );

  box.innerHTML = html;
}

function _renderForgeComposerCard() {
  var draft = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  var actionKey = _forgeActiveDraftId ? 'lab.action.updateSkill' : 'lab.action.saveSkill';
  var html = '';

  html += '<div class="forge-card forge-input-card">';
  html += '<div class="forge-card-title">' + t('lab.skill.title') + '</div>';
  html += '<div class="forge-card-desc">' + t('lab.skill.desc') + '</div>';
  if (_forgeActiveDraftId) {
    html += '<div class="forge-inline-tags"><span class="forge-mini-tag">' + _esc(t('lab.badge.editingDraft')) + '</span></div>';
  }
  html += '<div class="forge-form-grid">';
  html += _renderForgeSkillField('skill_name', 'lab.skill.name', 'forgeSkillName', draft.skill_name, 'lab.skill.name.placeholder', false, false);
  html += _renderForgeSkillField('goal', 'lab.skill.goal', 'forgeSkillGoal', draft.goal, 'lab.skill.goal.placeholder', true, true);
  html += _renderForgeSkillField('use_case', 'lab.skill.useCase', 'forgeSkillUseCase', draft.use_case, 'lab.skill.useCase.placeholder', true, false);
  html += _renderForgeSkillField('boundary', 'lab.skill.boundary', 'forgeSkillBoundary', draft.boundary, 'lab.skill.boundary.placeholder', true, false);
  html += _renderForgeSkillField('resources', 'lab.skill.resources', 'forgeSkillResources', draft.resources, 'lab.skill.resources.placeholder', true, true);
  html += '</div>';
  html += '<div class="forge-card-tip">' + t('lab.skill.tip') + '</div>';
  html += '<div class="forge-history-actions forge-composer-actions">';
  html += '<button class="forge-btn" onclick="saveForgeSkillDraft(this)">' + t(actionKey) + '</button>';
  if (_forgeActiveDraftId) {
    html += '<button class="forge-action-btn" onclick="resetForgeSkillDraftComposer()">' + t('lab.action.newSkillDraft') + '</button>';
  }
  html += '</div>';
  html += '</div>';
  return html;
}

function _renderForgeSkillField(field, labelKey, id, value, placeholderKey, multiline, fullWidth) {
  var html = '';
  html += '<label class="forge-field' + (fullWidth ? ' full' : '') + '">';
  html += '<span class="forge-field-label">' + t(labelKey) + '</span>';
  if (multiline) {
    html += '<textarea id="' + id + '" class="forge-input forge-textarea" placeholder="' + _escAttr(t(placeholderKey)) + '" oninput="_syncForgeSkillField(\'' + _escAttr(field) + '\', this.value)">' + _esc(value) + '</textarea>';
  } else {
    html += '<input id="' + id + '" class="forge-input" placeholder="' + _escAttr(t(placeholderKey)) + '" value="' + _escAttr(value) + '" oninput="_syncForgeSkillField(\'' + _escAttr(field) + '\', this.value)">';
  }
  html += '</label>';
  return html;
}

function _renderForgeSection(title, rows, renderItem, emptyText) {
  var html = '<div class="forge-card">';
  html += '<div class="forge-card-title">' + title + '</div>';
  if (!rows || !rows.length) {
    html += '<div class="forge-history-stats" style="opacity:.72;">' + (emptyText || t('lab.section.empty')) + '</div>';
    html += '</div>';
    return html;
  }
  rows.forEach(function(item) {
    html += renderItem(item || {});
  });
  html += '</div>';
  return html;
}

function _renderForgeDraftItem(item) {
  var draft = _getForgeSkillDraft(item.id);
  var text = '';
  text += '<div class="forge-history-item">';
  text += '<div class="forge-history-header">';
  text += '<div class="forge-history-label">' + _esc(draft.skill_name || item.need || item.query || t('lab.unnamed.skill')) + '</div>';
  text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
  text += '</div>';
  text += '<div class="forge-inline-tags"><span class="forge-mini-tag">' + _esc(t('lab.badge.skillDraft')) + '</span></div>';
  if (draft.goal) {
    text += '<div class="forge-history-goal">' + t('lab.goal') + ': ' + _esc(draft.goal) + '</div>';
  }
  if (draft.use_case) {
    text += '<div class="forge-history-goal">' + t('lab.meta.useCase') + ': ' + _esc(draft.use_case) + '</div>';
  }
  if (draft.boundary) {
    text += '<div class="forge-history-goal">' + t('lab.meta.boundary') + ': ' + _esc(draft.boundary) + '</div>';
  }
  if (draft.resources) {
    text += '<div class="forge-history-goal">' + t('lab.meta.resources') + ': ' + _esc(draft.resources) + '</div>';
  }
  text += '<div class="forge-history-stats">' + _esc(_fmtTime(item.updated_at || item.created_at)) + '</div>';
  text += '<div class="forge-history-actions">';
  text += '<button class="forge-action-btn primary" onclick="resumeForgeSkillDraft(\'' + _escAttr(item.id) + '\')">' + t('lab.action.continueDraft') + '</button>';
  text += '</div>';
  text += '</div>';
  return text;
}

function saveForgeSkillDraft(buttonEl) {
  var draft = _readForgeSkillComposerFromDom();
  var need = _buildForgeQueueNeed(draft);
  if (!need) {
    _setForgeNotice(t('lab.notice.skillGoalRequired'));
    return;
  }

  if (_forgeActiveDraftId) {
    _rememberForgeSkillDraft(_forgeActiveDraftId, draft);
    _resetForgeDraftComposer();
    _setForgeNotice(t('lab.notice.skillUpdated'));
    _fetchForgeData();
    return;
  }

  if (buttonEl) {
    buttonEl.disabled = true;
    buttonEl.dataset.label = buttonEl.textContent;
    buttonEl.textContent = t('lab.input.submit');
  }

  fetch('/lab/experiment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal: need, rounds: 1 })
  }).then(function(r) { return r.json(); }).then(function(data) {
    var experiment = data && data.experiment ? data.experiment : null;
    if (experiment && experiment.id) {
      _rememberForgeSkillDraft(experiment.id, draft);
    }
    _resetForgeDraftComposer();
    _setForgeNotice(t('lab.notice.skillQueued'));
    _fetchForgeData();
  }).catch(function() {
    _setForgeNotice(t('network.error'));
  }).finally(function() {
    if (buttonEl) {
      buttonEl.disabled = false;
      buttonEl.textContent = buttonEl.dataset.label || t('lab.action.saveSkill');
    }
  });
}

function resumeForgeSkillDraft(expId) {
  var id = String(expId || '').trim();
  if (!id) return;
  var draft = _getForgeSkillDraft(id);
  if (!_hasForgeSkillDraft(id)) return;
  _forgeActiveDraftId = id;
  _forgeSkillDraftState = draft;
  _setForgeNotice(t('lab.notice.resumeDraft'));
  if (_forgeLastData) {
    _renderForge(_forgeLastData);
  }
  setTimeout(function() {
    var el = document.getElementById('forgeSkillName') || document.getElementById('forgeSkillGoal');
    if (el && typeof el.focus === 'function') el.focus();
  }, 0);
}

function resetForgeSkillDraftComposer() {
  _resetForgeDraftComposer();
  _setForgeNotice('');
  if (_forgeLastData) {
    _renderForge(_forgeLastData);
  }
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
