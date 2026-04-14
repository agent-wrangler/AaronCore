var _forgeLastData = null;
var _forgeSkillDraftStoreKey = 'nova_forge_skill_drafts_v1';
var _forgeComposerDraftStoreKey = 'nova_forge_composer_draft_v1';
var _forgeSkillDraftState = _emptyForgeSkillDraft();
var _forgeActiveDraftId = '';
var _forgeActiveStepIndex = 0;
var _forgeStepAdvancedVisible = false;
var _forgeComposerSavedAt = 0;
var _forgeDraftScalarFields = [
  'skill_name',
  'goal',
  'use_case',
  'boundary',
  'resources',
  'test_case',
  'done_when'
];
var _forgeStepKinds = ['collect', 'reason', 'create', 'image', 'publish', 'review', 'custom'];

function _emptyForgeStep() {
  return {
    kind: 'custom',
    needs_review: false,
    title: '',
    action: '',
    success: '',
    failure: ''
  };
}

function _normalizeForgeStepKind(value) {
  var key = String(value || '').trim();
  return _forgeStepKinds.indexOf(key) !== -1 ? key : 'custom';
}

function _normalizeForgeStep(input) {
  var data = input && typeof input === 'object' ? input : {};
  return {
    kind: _normalizeForgeStepKind(data.kind),
    needs_review: !!data.needs_review,
    title: String(data.title || '').trim(),
    action: String(data.action || '').trim(),
    success: String(data.success || '').trim(),
    failure: String(data.failure || '').trim()
  };
}

function _normalizeForgeStepList(steps) {
  if (!Array.isArray(steps) || !steps.length) {
    return [_emptyForgeStep()];
  }
  return steps.map(_normalizeForgeStep);
}

function _isMeaningfulForgeStep(step) {
  var row = _normalizeForgeStep(step);
  return !!(row.title || row.action || row.success || row.failure);
}

function _meaningfulForgeSteps(steps) {
  return _normalizeForgeStepList(steps).filter(_isMeaningfulForgeStep);
}

function _emptyForgeSkillDraft() {
  return {
    skill_name: '',
    goal: '',
    use_case: '',
    boundary: '',
    resources: '',
    test_case: '',
    done_when: '',
    steps: [_emptyForgeStep()]
  };
}

function _normalizeForgeSkillDraft(input) {
  var base = _emptyForgeSkillDraft();
  var data = input && typeof input === 'object' ? input : {};

  _forgeDraftScalarFields.forEach(function(key) {
    base[key] = String(data[key] || '').trim();
  });

  base.steps = _normalizeForgeStepList(data.steps);
  return base;
}

function _mergeForgeSkillDraft(seed) {
  var current = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  var next = _normalizeForgeSkillDraft(seed);

  _forgeDraftScalarFields.forEach(function(key) {
    if (!next[key]) {
      next[key] = current[key];
    }
  });
  if (!Array.isArray(seed && seed.steps) || !(seed.steps || []).length) {
    next.steps = current.steps.map(_normalizeForgeStep);
  }
  return next;
}

function _normalizeForgeActiveStepIndex(index, steps) {
  var rows = _normalizeForgeStepList(steps);
  var last = Math.max(0, rows.length - 1);
  var value = Number(index);
  if (!isFinite(value)) return 0;
  return Math.max(0, Math.min(last, Math.round(value)));
}

function _hasForgeStepAdvanced(step) {
  var row = _normalizeForgeStep(step);
  return row.kind !== 'custom' || !!row.success || !!row.failure;
}

function _isMeaningfulForgeSkillDraft(draft) {
  var data = _normalizeForgeSkillDraft(draft);
  return _forgeDraftScalarFields.some(function(key) {
    return !!data[key];
  }) || _meaningfulForgeSteps(data.steps).length > 0;
}

function _persistForgeComposerDraft() {
  try {
    var draft = _normalizeForgeSkillDraft(_forgeSkillDraftState);
    var shouldKeep = _forgeActiveDraftId || _isMeaningfulForgeSkillDraft(draft);
    if (!shouldKeep) {
      localStorage.removeItem(_forgeComposerDraftStoreKey);
      _forgeComposerSavedAt = 0;
      return;
    }
    var payload = {
      active_draft_id: String(_forgeActiveDraftId || '').trim(),
      active_step_index: _normalizeForgeActiveStepIndex(_forgeActiveStepIndex, draft.steps),
      step_advanced_visible: _forgeStepAdvancedVisible === true,
      draft: draft,
      saved_at: Date.now()
    };
    localStorage.setItem(_forgeComposerDraftStoreKey, JSON.stringify(payload));
    _forgeComposerSavedAt = payload.saved_at;
  } catch (err) {}
}

function _hydrateForgeComposerDraft() {
  try {
    var raw = localStorage.getItem(_forgeComposerDraftStoreKey);
    if (!raw) return;
    var parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return;
    var draft = _normalizeForgeSkillDraft(parsed.draft || {});
    if (!_isMeaningfulForgeSkillDraft(draft) && !parsed.active_draft_id) return;
    _forgeSkillDraftState = draft;
    _forgeActiveDraftId = String(parsed.active_draft_id || '').trim();
    _forgeActiveStepIndex = _normalizeForgeActiveStepIndex(parsed.active_step_index, draft.steps);
    _forgeStepAdvancedVisible = parsed.step_advanced_visible === true;
    _forgeComposerSavedAt = Number(parsed.saved_at || 0);
  } catch (err) {}
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
  return _forgeDraftScalarFields.some(function(key) {
    return !!draft[key];
  }) || _meaningfulForgeSteps(draft.steps).length > 0;
}

function _buildForgeQueueNeed(draft) {
  var data = _normalizeForgeSkillDraft(draft);
  if (data.skill_name && data.goal) return data.skill_name + ': ' + data.goal;
  if (data.goal) return data.goal;
  if (data.skill_name) return data.skill_name;
  var steps = _meaningfulForgeSteps(data.steps);
  return steps.length ? (steps[0].title || steps[0].action || '') : '';
}

function _syncForgeSkillField(field, value) {
  var key = String(field || '').trim();
  if (_forgeDraftScalarFields.indexOf(key) === -1) return;
  _forgeSkillDraftState = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  _forgeSkillDraftState[key] = String(value || '');
  _persistForgeComposerDraft();
}

function _updateForgeStepField(index, field, value) {
  var rowIndex = Number(index);
  var key = String(field || '').trim();
  if (!isFinite(rowIndex)) return;
  if (['kind', 'title', 'action', 'success', 'failure'].indexOf(key) === -1) return;
  _forgeSkillDraftState = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  if (!_forgeSkillDraftState.steps[rowIndex]) return;
  if (key === 'kind') {
    _forgeSkillDraftState.steps[rowIndex][key] = _normalizeForgeStepKind(value);
  } else {
    _forgeSkillDraftState.steps[rowIndex][key] = String(value || '');
  }
  _persistForgeComposerDraft();
}

function _updateForgeStepToggle(index, field, checked) {
  var rowIndex = Number(index);
  if (!isFinite(rowIndex) || String(field || '').trim() !== 'needs_review') return;
  _forgeSkillDraftState = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  if (!_forgeSkillDraftState.steps[rowIndex]) return;
  _forgeSkillDraftState.steps[rowIndex].needs_review = checked === true;
  _persistForgeComposerDraft();
}

function _readForgeSkillComposerFromDom() {
  return _normalizeForgeSkillDraft(_forgeSkillDraftState);
}

function _resetForgeDraftComposer() {
  _forgeSkillDraftState = _emptyForgeSkillDraft();
  _forgeActiveDraftId = '';
  _forgeActiveStepIndex = 0;
  _forgeStepAdvancedVisible = false;
  _persistForgeComposerDraft();
}

function _setForgeComposerMode(mode, seed) {
  _forgeSkillDraftState = _mergeForgeSkillDraft(seed || {});
  _forgeActiveDraftId = '';
  _forgeActiveStepIndex = 0;
  _forgeStepAdvancedVisible = false;
  _persistForgeComposerDraft();
  _refreshForgeComposer();
}

window._setForgeComposerMode = _setForgeComposerMode;

function selectForgeStep(index, focusId) {
  var draft = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  _forgeActiveStepIndex = _normalizeForgeActiveStepIndex(index, draft.steps);
  _forgeStepAdvancedVisible = _hasForgeStepAdvanced(draft.steps[_forgeActiveStepIndex]);
  _persistForgeComposerDraft();
  _refreshForgeComposer(focusId);
}

function addForgeStep(afterIndex) {
  var draft = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  var baseIndex = isFinite(Number(afterIndex)) ? Number(afterIndex) : draft.steps.length - 1;
  var insertAt = Math.max(0, Math.min(baseIndex + 1, draft.steps.length));
  draft.steps.splice(insertAt, 0, _emptyForgeStep());
  _forgeSkillDraftState = draft;
  _forgeActiveStepIndex = insertAt;
  _forgeStepAdvancedVisible = false;
  _persistForgeComposerDraft();
  _refreshForgeComposer('forgeStepTitle' + insertAt);
}

function removeForgeStep(index) {
  var draft = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  var rowIndex = Number(index);
  if (!isFinite(rowIndex) || rowIndex < 0 || rowIndex >= draft.steps.length) return;

  if (draft.steps.length <= 1) {
    draft.steps = [_emptyForgeStep()];
    _forgeActiveStepIndex = 0;
    _forgeStepAdvancedVisible = false;
  } else {
    draft.steps.splice(rowIndex, 1);
    if (_forgeActiveStepIndex === rowIndex) {
      _forgeActiveStepIndex = Math.max(0, Math.min(rowIndex, draft.steps.length - 1));
    } else if (_forgeActiveStepIndex > rowIndex) {
      _forgeActiveStepIndex -= 1;
    }
    _forgeStepAdvancedVisible = _hasForgeStepAdvanced(draft.steps[_forgeActiveStepIndex]);
  }

  _forgeSkillDraftState = draft;
  _persistForgeComposerDraft();
  _refreshForgeComposer('forgeStepTitle' + _forgeActiveStepIndex);
}

function moveForgeStep(index, direction) {
  var draft = _normalizeForgeSkillDraft(_forgeSkillDraftState);
  var rowIndex = Number(index);
  var dir = Number(direction);
  var target = rowIndex + dir;
  if (!isFinite(rowIndex) || !isFinite(dir)) return;
  if (rowIndex < 0 || rowIndex >= draft.steps.length) return;
  if (target < 0 || target >= draft.steps.length) return;

  var temp = draft.steps[rowIndex];
  draft.steps[rowIndex] = draft.steps[target];
  draft.steps[target] = temp;

  if (_forgeActiveStepIndex === rowIndex) {
    _forgeActiveStepIndex = target;
  } else if (_forgeActiveStepIndex === target) {
    _forgeActiveStepIndex = rowIndex;
  }

  _forgeSkillDraftState = draft;
  _persistForgeComposerDraft();
  _refreshForgeComposer('forgeStepTitle' + _forgeActiveStepIndex);
}

function toggleForgeStepAdvanced() {
  _forgeStepAdvancedVisible = !_forgeStepAdvancedVisible;
  _persistForgeComposerDraft();
  _refreshForgeComposer();
}

function _refreshForgeComposer(focusId) {
  if (_forgeLastData) {
    _renderForge(_forgeLastData);
  }
  if (!focusId) return;
  setTimeout(function() {
    var el = document.getElementById(focusId);
    if (el && typeof el.focus === 'function') {
      el.focus();
      try {
        var value = String(el.value || '');
        if (typeof el.setSelectionRange === 'function') {
          el.setSelectionRange(value.length, value.length);
        }
      } catch (err) {}
    }
  }, 0);
}

function loadLabPage() {
  var chat = document.getElementById('chat');
  setInputVisible(false);
  chat.innerHTML =
    '<div class="settings-page forge-page" style="position:relative;z-index:1;">' +
      '<div class="forge-page-head">' +
        '<div class="page-title">' + t('nav.forge') + '</div>' +
        '<div class="lab-subtitle">' + t('lab.view.subtitle') + '</div>' +
      '</div>' +
      '<div id="forgeNotice" class="forge-history-stats" style="margin:10px 0 14px; opacity:.72;"></div>' +
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
  html += '<div class="forge-card forge-workspace-card">';
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
  var steps = draft.steps;
  var activeIndex = _normalizeForgeActiveStepIndex(_forgeActiveStepIndex, steps);
  var reviewCount = steps.filter(function(step) {
    return _normalizeForgeStep(step).needs_review;
  }).length;
  var html = '';

  _forgeActiveStepIndex = activeIndex;

  html += '<div class="forge-card forge-composer-card">';
  html += '<div class="forge-card-header forge-composer-header">';
  html += '<div class="forge-card-head-copy">';
  html += '<div class="forge-card-title">' + t('lab.skill.title') + '</div>';
  html += '<div class="forge-card-desc">' + t('lab.skill.desc') + '</div>';
  html += '</div>';
  html += '<div class="forge-inline-tags">';
  if (_forgeActiveDraftId) {
    html += '<span class="forge-mini-tag">' + _esc(t('lab.badge.editingDraft')) + '</span>';
  }
  if (_forgeComposerSavedAt) {
    html += '<span class="forge-mini-tag">' + _esc(t('lab.badge.localDraft')) + '</span>';
  }
  html += '<span class="forge-mini-tag">' + _esc(tf('lab.steps.summary', steps.length)) + '</span>';
  if (reviewCount) {
    html += '<span class="forge-mini-tag forge-mini-tag-strong">' + _esc(tf('lab.meta.reviewCount', reviewCount)) + '</span>';
  }
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-summary-grid">';
  html += _renderForgeSkillField('skill_name', 'lab.skill.name', 'forgeSkillName', draft.skill_name, 'lab.skill.name.placeholder', false, false);
  html += _renderForgeSkillField('goal', 'lab.skill.goal', 'forgeSkillGoal', draft.goal, 'lab.skill.goal.placeholder', true, true);
  html += '</div>';

  html += '<div class="forge-system-strip">' + _esc(t('lab.surface.strip')) + '</div>';

  html += '<div class="forge-workbench">';
  html += '<div class="forge-lane forge-lane-main">';
  html += _renderForgeMainLane(draft, activeIndex);
  html += '</div>';
  html += '<div class="forge-lane forge-lane-side">';
  html += _renderForgeSidePanel(draft, activeIndex);
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-card-tip">' + t('lab.skill.tip') + '</div>';
  html += '</div>';
  return html;
}

function _renderForgeMainLane(draft, activeIndex) {
  var steps = draft.steps;
  var html = '';

  html += '<div class="forge-pane-head forge-main-head">';
  html += '<div class="forge-pane-head-copy">';
  html += '<div class="forge-section-title">' + t('lab.steps.title') + '</div>';
  html += '<div class="forge-section-note">' + t('lab.editor.note') + '</div>';
  html += '</div>';
  html += '<div class="forge-step-editor-kicker">' + _esc(tf('lab.editor.stepLabel', activeIndex + 1)) + '</div>';
  html += '</div>';

  html += '<div class="forge-main-rail">';
  html += '<div class="forge-step-stack">';
  steps.forEach(function(step, index) {
    html += _renderForgeStepCard(step, index, index === activeIndex);
  });
  html += '</div>';
  html += '<div class="forge-step-create">';
  html += '<button class="forge-action-btn primary" onclick="addForgeStep(' + activeIndex + ')">' + t('lab.steps.add') + '</button>';
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-main-editor">';
  html += _renderForgeStepEditor(draft, activeIndex, true);
  html += '</div>';

  return html;
}

function _renderForgeStepRail(draft, activeIndex) {
  var steps = draft.steps;
  var html = '';

  html += '<div class="forge-pane-head">';
  html += '<div class="forge-pane-head-copy">';
  html += '<div class="forge-section-title">' + t('lab.rail.title') + '</div>';
  html += '<div class="forge-section-note">' + t('lab.rail.note') + '</div>';
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-step-stack">';
  steps.forEach(function(step, index) {
    html += _renderForgeStepCard(step, index, index === activeIndex);
  });
  html += '</div>';

  html += '<div class="forge-step-create">';
  html += '<button class="forge-action-btn primary" onclick="addForgeStep(' + activeIndex + ')">' + t('lab.steps.add') + '</button>';
  html += '</div>';
  return html;
}

function _renderForgeStepCard(step, index, isActive) {
  var row = _normalizeForgeStep(step);
  var html = '';
  var tags = '';

  html += '<button type="button" class="forge-step-card' + (isActive ? ' active' : '') + '" onclick="selectForgeStep(' + index + ', \'forgeStepTitle' + index + '\')">';
  html += '<div class="forge-step-card-top">';
  html += '<span class="forge-step-card-index">' + (index + 1) + '</span>';
  html += '<span class="forge-step-card-title">' + _esc(row.title || tf('lab.steps.defaultName', index + 1)) + '</span>';
  html += '</div>';
  if (row.kind !== 'custom') {
    tags += '<span class="forge-mini-tag">' + _esc(t('lab.step.kind.' + row.kind)) + '</span>';
  }
  if (row.needs_review) {
    tags += '<span class="forge-mini-tag forge-mini-tag-strong">' + _esc(t('lab.badge.needsReview')) + '</span>';
  }
  if (tags) {
    html += '<div class="forge-step-card-tags">' + tags + '</div>';
  }
  if (row.action) {
    html += '<div class="forge-step-card-text">' + _esc(_trimForgeText(row.action, 110)) + '</div>';
  }
  html += '</button>';

  return html;
}

function _renderForgeStepEditor(draft, activeIndex, embedded) {
  var steps = draft.steps;
  var row = _normalizeForgeStep(steps[activeIndex] || _emptyForgeStep());
  var showAdvanced = _forgeStepAdvancedVisible || _hasForgeStepAdvanced(row);
  var html = '';

  if (!embedded) {
    html += '<div class="forge-pane-head">';
    html += '<div class="forge-pane-head-copy">';
    html += '<div class="forge-section-title">' + t('lab.editor.title') + '</div>';
    html += '<div class="forge-section-note">' + t('lab.editor.note') + '</div>';
    html += '</div>';
    html += '<div class="forge-step-editor-kicker">' + _esc(tf('lab.editor.stepLabel', activeIndex + 1)) + '</div>';
    html += '</div>';
  }

  html += '<div class="forge-step-editor' + (embedded ? ' forge-step-editor-embedded' : '') + '">';
  html += '<div class="forge-step-editor-top">';
  html += '<div class="forge-step-row-title">' + _esc(row.title || tf('lab.steps.defaultName', activeIndex + 1)) + '</div>';
  html += '<div class="forge-step-toolbar">';
  html += '<button class="forge-step-tool" onclick="moveForgeStep(' + activeIndex + ', -1)"' + (activeIndex === 0 ? ' disabled' : '') + '>' + t('lab.action.moveUp') + '</button>';
  html += '<button class="forge-step-tool" onclick="moveForgeStep(' + activeIndex + ', 1)"' + (activeIndex === steps.length - 1 ? ' disabled' : '') + '>' + t('lab.action.moveDown') + '</button>';
  html += '<button class="forge-step-tool danger" onclick="removeForgeStep(' + activeIndex + ')">' + t('lab.action.deleteStep') + '</button>';
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-step-meta">';
  html += '<label class="forge-check">';
  html += '<input type="checkbox" ' + (row.needs_review ? 'checked ' : '') + 'onchange="_updateForgeStepToggle(' + activeIndex + ', \'needs_review\', this.checked)">';
  html += '<span>' + t('lab.step.needsReview') + '</span>';
  html += '</label>';
  html += '</div>';

  html += '<div class="forge-step-grid">';
  html += _renderForgeStepField(activeIndex, 'title', 'lab.step.title', 'forgeStepTitle' + activeIndex, row.title, 'lab.step.title.placeholder', false, false);
  html += _renderForgeStepField(activeIndex, 'action', 'lab.step.action', 'forgeStepAction' + activeIndex, row.action, 'lab.step.action.placeholder', true, true);
  html += '</div>';

  html += '<div class="forge-step-detail-toggle">';
  html += '<button class="forge-action-btn" onclick="toggleForgeStepAdvanced()">' + t(showAdvanced ? 'lab.step.detail.hide' : 'lab.step.detail.show') + '</button>';
  html += '</div>';

  if (showAdvanced) {
    html += '<div class="forge-step-advanced">';
    html += '<div class="forge-step-meta forge-step-meta-advanced">';
    html += '<label class="forge-field forge-field-compact">';
    html += '<span class="forge-field-label">' + t('lab.step.kind') + '</span>';
    html += '<select id="forgeStepKind' + activeIndex + '" class="forge-input forge-select" onchange="_updateForgeStepField(' + activeIndex + ', \'kind\', this.value)">';
    _forgeStepKinds.forEach(function(kind) {
      html += '<option value="' + _escAttr(kind) + '"' + (row.kind === kind ? ' selected' : '') + '>' + _esc(t('lab.step.kind.' + kind)) + '</option>';
    });
    html += '</select>';
    html += '</label>';
    html += '</div>';
    html += '<div class="forge-step-grid">';
    html += _renderForgeStepField(activeIndex, 'success', 'lab.step.success', 'forgeStepSuccess' + activeIndex, row.success, 'lab.step.success.placeholder', true, false);
    html += _renderForgeStepField(activeIndex, 'failure', 'lab.step.failure', 'forgeStepFailure' + activeIndex, row.failure, 'lab.step.failure.placeholder', true, false);
    html += '</div>';
    html += '</div>';
  }
  html += '</div>';

  return html;
}

function _renderForgeSidePanel(draft, activeIndex) {
  var html = '';
  var actionKey = _forgeActiveDraftId ? 'lab.action.saveWholeDraft' : 'lab.action.queueDraft';
  var hasDraft = _isMeaningfulForgeSkillDraft(draft);

  html += '<div class="forge-side-block">';
  html += '<div class="forge-pane-head">';
  html += '<div class="forge-pane-head-copy">';
  html += '<div class="forge-section-title">' + t('lab.preview.title') + '</div>';
  html += '<div class="forge-section-note">' + t('lab.preview.note') + '</div>';
  html += '</div>';
  html += '</div>';
  html += _renderForgeFlowPreview(draft, activeIndex);
  html += '</div>';

  html += '<div class="forge-side-block">';
  html += '<div class="forge-pane-head">';
  html += '<div class="forge-pane-head-copy">';
  html += '<div class="forge-section-title">' + t('lab.verify.title') + '</div>';
  html += '<div class="forge-section-note">' + t('lab.verify.note') + '</div>';
  html += '</div>';
  html += '</div>';
  html += '<div class="forge-form-grid forge-side-form">';
  html += _renderForgeSkillField('use_case', 'lab.skill.useCase', 'forgeSkillUseCase', draft.use_case, 'lab.skill.useCase.placeholder', true, true);
  html += _renderForgeSkillField('test_case', 'lab.skill.testCase', 'forgeSkillTestCase', draft.test_case, 'lab.skill.testCase.placeholder', true, true);
  html += _renderForgeSkillField('done_when', 'lab.skill.doneWhen', 'forgeSkillDoneWhen', draft.done_when, 'lab.skill.doneWhen.placeholder', true, true);
  html += _renderForgeSkillField('boundary', 'lab.skill.boundary', 'forgeSkillBoundary', draft.boundary, 'lab.skill.boundary.placeholder', true, true);
  html += _renderForgeSkillField('resources', 'lab.skill.resources', 'forgeSkillResources', draft.resources, 'lab.skill.resources.placeholder', true, true);
  html += '</div>';
  html += '</div>';

  html += '<div class="forge-system-note">';
  html += '<div class="forge-system-note-title">' + t('lab.surface.title') + '</div>';
  html += '<div class="forge-system-note-text">' + t('lab.surface.note') + '</div>';
  html += '</div>';

  html += '<div class="forge-submit-card">';
  html += '<div class="forge-system-note-title">' + t('lab.submit.title') + '</div>';
  html += '<div class="forge-system-note-text">' + t('lab.submit.note') + '</div>';
  html += '<div class="forge-submit-status">' + _esc(hasDraft ? t('lab.submit.status.saved') : t('lab.submit.status.empty')) + '</div>';
  html += '<div class="forge-history-actions forge-submit-actions">';
  html += '<button class="forge-btn forge-btn-compact" onclick="saveForgeSkillDraft(this)">' + t(actionKey) + '</button>';
  if (_forgeActiveDraftId || hasDraft) {
    html += '<button class="forge-action-btn" onclick="resetForgeSkillDraftComposer()">' + t('lab.action.newSkillDraft') + '</button>';
  }
  html += '</div>';
  html += '</div>';

  return html;
}

function _renderForgeFlowPreview(draft, activeIndex) {
  var rows = _normalizeForgeStepList(draft.steps);
  var hasMeaningful = _meaningfulForgeSteps(rows).length > 0;
  var html = '<div class="forge-flow-preview">';

  if (!hasMeaningful) {
    html += '<div class="forge-preview-empty">' + t('lab.preview.empty') + '</div>';
    html += '</div>';
    return html;
  }

  html += '<div class="forge-flow-track">';
  rows.forEach(function(step, index) {
    var row = _normalizeForgeStep(step);
    var tags = '';
    html += '<button type="button" class="forge-flow-chip' + (index === activeIndex ? ' active' : '') + '" onclick="selectForgeStep(' + index + ', \'forgeStepTitle' + index + '\')">';
    html += '<div class="forge-flow-chip-top">';
    html += '<span class="forge-flow-chip-index">' + (index + 1) + '</span>';
    if (row.kind !== 'custom') {
      tags += '<span class="forge-mini-tag">' + _esc(t('lab.step.kind.' + row.kind)) + '</span>';
    }
    if (row.needs_review) {
      tags += '<span class="forge-mini-tag forge-mini-tag-strong">' + _esc(t('lab.badge.needsReview')) + '</span>';
    }
    if (tags) {
      html += tags;
    }
    html += '</div>';
    html += '<div class="forge-flow-chip-title">' + _esc(row.title || tf('lab.steps.defaultName', index + 1)) + '</div>';
    if (row.action) {
      html += '<div class="forge-flow-chip-text">' + _esc(_trimForgeText(row.action, 110)) + '</div>';
    }
    html += '</button>';
  });
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

function _renderForgeStepField(index, field, labelKey, id, value, placeholderKey, multiline, fullWidth) {
  var html = '';
  html += '<label class="forge-field' + (fullWidth ? ' full' : '') + '">';
  html += '<span class="forge-field-label">' + t(labelKey) + '</span>';
  if (multiline) {
    html += '<textarea id="' + id + '" class="forge-input forge-textarea forge-step-textarea" placeholder="' + _escAttr(t(placeholderKey)) + '" oninput="_updateForgeStepField(' + index + ', \'' + _escAttr(field) + '\', this.value)">' + _esc(value) + '</textarea>';
  } else {
    html += '<input id="' + id + '" class="forge-input" placeholder="' + _escAttr(t(placeholderKey)) + '" value="' + _escAttr(value) + '" oninput="_updateForgeStepField(' + index + ', \'' + _escAttr(field) + '\', this.value)">';
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
  var steps = _meaningfulForgeSteps(draft.steps);
  var reviewCount = steps.filter(function(step) {
    return _normalizeForgeStep(step).needs_review;
  }).length;
  var text = '';

  text += '<div class="forge-history-item">';
  text += '<div class="forge-history-header">';
  text += '<div class="forge-history-label">' + _esc(draft.skill_name || item.need || item.query || t('lab.unnamed.skill')) + '</div>';
  text += '<div class="forge-status-badge ' + _badgeClass(item.status) + '">' + _esc(_statusText(item.status)) + '</div>';
  text += '</div>';
  text += '<div class="forge-inline-tags"><span class="forge-mini-tag">' + _esc(t('lab.badge.skillDraft')) + '</span>';
  if (reviewCount) {
    text += '<span class="forge-mini-tag forge-mini-tag-strong">' + _esc(tf('lab.meta.reviewCount', reviewCount)) + '</span>';
  }
  text += '</div>';
  if (draft.goal) {
    text += '<div class="forge-history-goal">' + t('lab.goal') + ': ' + _esc(draft.goal) + '</div>';
  }
  if (steps.length) {
    text += '<div class="forge-history-goal">' + _esc(tf('lab.meta.stepCount', String(steps.length))) + ' 路 ' + _esc(_summarizeForgeSteps(steps)) + '</div>';
  }
  if (draft.test_case) {
    text += '<div class="forge-history-goal">' + t('lab.meta.testCase') + ': ' + _esc(_trimForgeText(draft.test_case, 100)) + '</div>';
  }
  if (draft.done_when) {
    text += '<div class="forge-history-goal">' + t('lab.meta.doneWhen') + ': ' + _esc(_trimForgeText(draft.done_when, 100)) + '</div>';
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
  if (!_hasForgeSkillDraft(id)) return;
  _forgeActiveDraftId = id;
  _forgeSkillDraftState = _getForgeSkillDraft(id);
  _forgeActiveStepIndex = 0;
  _forgeStepAdvancedVisible = _hasForgeStepAdvanced(_forgeSkillDraftState.steps[0]);
  _persistForgeComposerDraft();
  _setForgeNotice(t('lab.notice.resumeDraft'));
  _refreshForgeComposer('forgeSkillName');
}

function resetForgeSkillDraftComposer() {
  _resetForgeDraftComposer();
  _setForgeNotice('');
  _refreshForgeComposer('forgeSkillName');
}

function _summarizeForgeSteps(steps) {
  var rows = _meaningfulForgeSteps(steps);
  if (!rows.length) return '';
  var summary = rows.slice(0, 3).map(function(step, index) {
    var kind = t('lab.step.kind.' + step.kind);
    var title = step.title || step.action || tf('lab.steps.defaultName', String(index + 1));
    return kind + ' ' + title;
  }).join(' -> ');
  if (rows.length > 3) summary += '...';
  return summary;
}

function _trimForgeText(text, maxLength) {
  var value = String(text || '').replace(/\s+/g, ' ').trim();
  var limit = Math.max(1, Number(maxLength) || 100);
  if (value.length > limit) return value.slice(0, limit) + '...';
  return value;
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

_hydrateForgeComposerDraft();
