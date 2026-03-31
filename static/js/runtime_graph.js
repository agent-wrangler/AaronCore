window._runtimeGraphState = window._runtimeGraphState || {
 data: null,
 selectedRunId: '',
 standalone: false,
 viewMode: 'focus',
 autoRefreshEnabled: true,
 autoRefreshMs: 15000,
 autoRefreshTimer: 0,
 lastLoadedAt: 0,
 isLoading: false,
};

function _runtimeGraphEscape(value) {
 if (typeof escapeHtml === 'function') return escapeHtml(value);
 return String(value == null ? '' : value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;');
}

function _runtimeGraphNodeSubtitle(node) {
 var subtitle = String((node && node.subtitle) || '').trim();
 if (subtitle) return subtitle;
 var path = String((node && node.path) || '').trim();
 var label = String((node && node.label) || '').trim();
 if (path && path !== label) return path;
 return '';
}

function _runtimeGraphNodeKindLabel(node) {
 var kind = String((node && node.kind) || '').trim();
 var cluster = String((node && node.cluster_label) || '').trim();
 if (kind === 'runtime') return '运行步骤';
 if (kind === 'tool') return '技能调用';
 if (kind === 'route') return '接口路由';
 if (kind === 'core') return '核心模块';
 if (kind === 'page') return '页面壳子';
 if (kind === 'script') return '前端脚本';
 if (kind === 'style') return '页面样式';
 if (kind === 'test') return '测试文件';
 if (kind === 'file') return cluster ? (cluster + '文件') : '代码文件';
 return cluster || '代码节点';
}

function _runtimeGraphNodeStatusLabel(nodeId, activeSet, errorSet) {
 if (errorSet && errorSet[nodeId]) return '当前卡点';
 if (activeSet && activeSet[nodeId]) return '本轮经过';
 return '静态参考';
}

function _runtimeGraphNodeDetailLine(node) {
 var path = String((node && node.path) || '').trim();
 var subtitle = _runtimeGraphNodeSubtitle(node);
 if (path && path !== subtitle) return path;
 return _runtimeGraphNodeKindLabel(node);
}

function _runtimeGraphRenderFocusNode(node, subtitle, statusText) {
 var detailLine = _runtimeGraphNodeDetailLine(node);
 return '' +
  '<div class="runtime-node-top">' +
   '<div class="runtime-node-tag">' + _runtimeGraphEscape(node.cluster_label || '') + '</div>' +
   '<div class="runtime-node-status ' + (statusText === '当前卡点' ? 'is-error' : (statusText === '本轮经过' ? 'is-active' : '')) + '">' + _runtimeGraphEscape(statusText) + '</div>' +
  '</div>' +
  '<div class="runtime-node-title">' + _runtimeGraphEscape(node.label || node.id) + '</div>' +
  (subtitle ? ('<div class="runtime-node-subtitle">' + _runtimeGraphEscape(subtitle) + '</div>') : '') +
  '<div class="runtime-node-detail">' + _runtimeGraphEscape(detailLine) + '</div>' +
  '<div class="runtime-node-foot">' +
   '<span class="runtime-node-foot-label">类型</span>' +
   '<strong>' + _runtimeGraphEscape(_runtimeGraphNodeKindLabel(node)) + '</strong>' +
  '</div>';
}

function _runtimeGraphPageMarkup() {
 return '' +
  '<div class="runtime-graph-page">' +
   '<div class="runtime-graph-header">' +
    '<div>' +
     '<div class="page-title">' +
      '<svg viewBox="0 0 24 24"><circle cx="5" cy="7" r="2.2"/><circle cx="12" cy="5" r="2.2"/><circle cx="19" cy="8" r="2.2"/><circle cx="8" cy="18" r="2.2"/><circle cx="17" cy="18" r="2.2"/><path d="M6.8 6.3l3.4-1.1"/><path d="M13.9 5.8l3.2 1.4"/><path d="M6.4 8.6l1.8 7.2"/><path d="M18.1 10.2l-1 5.6"/><path d="M9.9 18h4.9"/><path d="M10 16.6l1.2-9.1"/><path d="M12.9 7.1l2.8 8.5"/></svg>' +
      '运行图谱' +
     '</div>' +
     '<div class="runtime-graph-subtitle">全量代码底图直接摊开，最近几轮任务的真实路径和卡点叠在上面。</div>' +
    '</div>' +
    '<div class="runtime-graph-actions">' +
     '<div class="runtime-graph-sync-note" id="runtimeGraphSyncNote">自动刷新开启后会每 15 秒同步一次。</div>' +
     '<button class="runtime-graph-refresh runtime-graph-refresh-secondary" id="runtimeGraphAutoRefreshBtn" type="button" onclick="_toggleRuntimeGraphAutoRefresh()">自动刷新：开</button>' +
     '<button class="runtime-graph-refresh" type="button" onclick="_loadRuntimeGraphData(true)">刷新图谱</button>' +
    '</div>' +
   '</div>' +
   '<div class="runtime-graph-summary" id="runtimeGraphSummary"></div>' +
   '<div class="runtime-graph-layout">' +
    '<div class="runtime-graph-sidebar">' +
     '<div class="runtime-graph-panel">' +
      '<div class="runtime-graph-panel-title">最近任务</div>' +
      '<div class="runtime-graph-panel-subtitle">点击右侧任务，主图会同步高亮；切到全量底图时再看下面的步骤拆解。</div>' +
      '<div id="runtimeGraphRuns"></div>' +
     '</div>' +
    '</div>' +
    '<div class="runtime-graph-main">' +
     '<div class="runtime-graph-toolbar">' +
      '<div class="runtime-graph-status" id="runtimeGraphStatus">正在读取代码结构…</div>' +
      '<div class="runtime-graph-toolbar-right">' +
       '<div class="runtime-graph-mode-switch" id="runtimeGraphModeSwitch">' +
        '<button class="runtime-graph-mode-btn" type="button" data-mode="focus" onclick="_setRuntimeGraphViewMode(\'focus\')">流程聚焦</button>' +
        '<button class="runtime-graph-mode-btn" type="button" data-mode="all" onclick="_setRuntimeGraphViewMode(\'all\')">全量底图</button>' +
       '</div>' +
       '<div class="runtime-graph-legend">' +
        '<span class="runtime-graph-dot runtime"></span>运行节点' +
        '<span class="runtime-graph-dot active"></span>本轮经过' +
        '<span class="runtime-graph-dot error"></span>当前卡点' +
       '</div>' +
      '</div>' +
     '</div>' +
     '<div class="runtime-graph-viewport" id="runtimeGraphViewport">' +
      '<div class="runtime-graph-stage" id="runtimeGraphStage"></div>' +
     '</div>' +
     '<div class="runtime-graph-flow-panel" id="runtimeGraphFlowPanel">' +
      '<div class="runtime-graph-flow-head">' +
       '<div>' +
        '<div class="runtime-graph-panel-title" id="runtimeGraphFlowTitle">当前任务步骤</div>' +
        '<div class="runtime-graph-panel-subtitle" id="runtimeGraphStepHeadline">正在等待图谱数据…</div>' +
       '</div>' +
       '<div class="runtime-graph-flow-mode" id="runtimeGraphFlowMode">全量底图</div>' +
      '</div>' +
      '<div class="runtime-graph-flow-meta" id="runtimeGraphFlowMeta"></div>' +
      '<div id="runtimeGraphSteps"></div>' +
     '</div>' +
    '</div>' +
   '</div>' +
  '</div>';
}

function loadRuntimeGraphPage() {
 var chat = document.getElementById('chat');
 if (!chat) return;
 window._runtimeGraphState.standalone = false;
 if (typeof setInputVisible === 'function') setInputVisible(false);
 chat.innerHTML = _runtimeGraphPageMarkup();
 _syncRuntimeGraphAutoRefresh();
 _loadRuntimeGraphData(false);
}

function mountStandaloneRuntimeGraphPage(containerId) {
 var root = document.getElementById(containerId || 'runtimeGraphStandaloneRoot');
 if (!root) return;
 window._runtimeGraphState.standalone = true;
 root.innerHTML = _runtimeGraphPageMarkup();
 _syncRuntimeGraphAutoRefresh();
 _loadRuntimeGraphData(false);
}

function _loadRuntimeGraphData(forceReload) {
 if (window._runtimeGraphState.isLoading) return;
 window._runtimeGraphState.isLoading = true;
 var statusEl = document.getElementById('runtimeGraphStatus');
 if (statusEl) statusEl.textContent = '正在读取代码结构和最近运行轨迹…';
 var url = '/runtime_graph?limit=12';
 if (forceReload) url += '&_=' + Date.now();
 fetch(url)
  .then(function(r) { return r.json(); })
  .then(function(data) {
   window._runtimeGraphState.data = data || {};
   window._runtimeGraphState.lastLoadedAt = Date.now();
   window._runtimeGraphState.isLoading = false;
   var runs = (data && data.runs) || [];
   var selected = window._runtimeGraphState.selectedRunId;
   var stillExists = runs.some(function(run) { return run.id === selected; });
   window._runtimeGraphState.selectedRunId = stillExists ? selected : ((runs[0] && runs[0].id) || '');
   _renderRuntimeGraphPage();
  })
  .catch(function(err) {
   console.warn('[runtime-graph] load failed', err);
   window._runtimeGraphState.isLoading = false;
   if (statusEl) statusEl.textContent = '图谱加载失败';
   var stage = document.getElementById('runtimeGraphStage');
   if (stage) {
    stage.innerHTML = '<div class="runtime-graph-empty">图谱数据暂时没有加载成功。</div>';
   }
   _renderRuntimeGraphRefreshState();
  });
}

function _selectRuntimeGraphRun(runId) {
 window._runtimeGraphState.selectedRunId = runId || '';
 _renderRuntimeGraphPage();
}

function _setRuntimeGraphViewMode(mode) {
 if (mode !== 'focus') mode = 'all';
 window._runtimeGraphState.viewMode = mode;
 _renderRuntimeGraphPage();
}

function _runtimeGraphFormatClock(raw) {
 if (!raw) return '--:--:--';
 try {
  var dt = new Date(raw);
  if (isNaN(dt.getTime())) return '--:--:--';
  var hh = String(dt.getHours()).padStart(2, '0');
  var mi = String(dt.getMinutes()).padStart(2, '0');
  var ss = String(dt.getSeconds()).padStart(2, '0');
  return hh + ':' + mi + ':' + ss;
 } catch (e) {
  return '--:--:--';
 }
}

function _runtimeGraphCanAutoRefresh() {
 return !!(window._runtimeGraphState.standalone || window._currentTab === 8 || _runtimeGraphHasStandaloneRoot());
}

function _syncRuntimeGraphAutoRefresh() {
 if (window._runtimeGraphState.autoRefreshTimer) {
  clearInterval(window._runtimeGraphState.autoRefreshTimer);
  window._runtimeGraphState.autoRefreshTimer = 0;
 }
 if (!window._runtimeGraphState.autoRefreshEnabled) return;
 if (document.hidden) return;
 if (!_runtimeGraphCanAutoRefresh()) return;
 window._runtimeGraphState.autoRefreshTimer = window.setInterval(function() {
  if (document.hidden || !_runtimeGraphCanAutoRefresh()) return;
  _loadRuntimeGraphData(true);
 }, window._runtimeGraphState.autoRefreshMs);
}

function _toggleRuntimeGraphAutoRefresh() {
 window._runtimeGraphState.autoRefreshEnabled = !window._runtimeGraphState.autoRefreshEnabled;
 _renderRuntimeGraphRefreshState();
 _syncRuntimeGraphAutoRefresh();
 if (window._runtimeGraphState.autoRefreshEnabled && !document.hidden && _runtimeGraphCanAutoRefresh()) {
  _loadRuntimeGraphData(true);
 }
}

function _renderRuntimeGraphRefreshState() {
 var btn = document.getElementById('runtimeGraphAutoRefreshBtn');
 var note = document.getElementById('runtimeGraphSyncNote');
 var enabled = !!window._runtimeGraphState.autoRefreshEnabled;
 if (btn) {
  btn.textContent = enabled ? '自动刷新：开' : '自动刷新：关';
  btn.classList.toggle('is-active', enabled);
 }
 if (note) {
  if (enabled) {
   var lastText = window._runtimeGraphState.lastLoadedAt ? ('最近同步 ' + _runtimeGraphFormatClock(window._runtimeGraphState.lastLoadedAt)) : '等待首次同步';
   note.textContent = '自动刷新每 15 秒同步一次 · ' + lastText;
  } else {
   note.textContent = '自动刷新已暂停，点右侧按钮可恢复。';
  }
 }
}

function _runtimeGraphSelectedRun(data) {
 var runs = (data && data.runs) || [];
 var selectedId = window._runtimeGraphState.selectedRunId;
 for (var i = 0; i < runs.length; i++) {
  if (runs[i].id === selectedId) return runs[i];
 }
 return runs[0] || null;
}

function _renderRuntimeGraphPage() {
 var data = window._runtimeGraphState.data || {};
 var runs = data.runs || [];
 var selectedRun = _runtimeGraphSelectedRun(data);
 if (selectedRun) window._runtimeGraphState.selectedRunId = selectedRun.id;
 _renderRuntimeGraphRefreshState();
 _renderRuntimeGraphModeSwitch(!!selectedRun);
 _renderRuntimeGraphSummary(data, selectedRun);
 _renderRuntimeGraphRuns(runs, selectedRun);
 _renderRuntimeGraphSteps(selectedRun);
 _renderRuntimeGraphBoard(data, selectedRun);
}

function _renderRuntimeGraphModeSwitch(hasRun) {
 var box = document.getElementById('runtimeGraphModeSwitch');
 if (!box) return;
 if (!hasRun && window._runtimeGraphState.viewMode === 'focus') {
  window._runtimeGraphState.viewMode = 'all';
 }
 box.querySelectorAll('.runtime-graph-mode-btn').forEach(function(btn) {
  var mode = btn.getAttribute('data-mode') || 'all';
  var active = mode === window._runtimeGraphState.viewMode;
  btn.classList.toggle('is-active', active);
  btn.disabled = mode === 'focus' && !hasRun;
 });
}

function _renderRuntimeGraphSummary(data, selectedRun) {
 var box = document.getElementById('runtimeGraphSummary');
 if (!box) return;
 var summary = data.summary || {};
 var stuck = selectedRun && selectedRun.stuck ? _runtimeGraphTrim(selectedRun.stuck, 64) : '当前没有错误卡点';
 box.innerHTML =
  '<div class="runtime-graph-stat">' +
   '<div class="runtime-graph-stat-label">代码文件</div>' +
   '<div class="runtime-graph-stat-value">' + _runtimeGraphCount(summary.file_count || 0) + '</div>' +
   '<div class="runtime-graph-stat-note">当前底图里真正摊开的源码文件</div>' +
  '</div>' +
  '<div class="runtime-graph-stat">' +
   '<div class="runtime-graph-stat-label">静态连线</div>' +
   '<div class="runtime-graph-stat-value">' + _runtimeGraphCount(summary.edge_count || 0) + '</div>' +
   '<div class="runtime-graph-stat-note">import / 页面引用 / 前端接口调用</div>' +
  '</div>' +
  '<div class="runtime-graph-stat">' +
   '<div class="runtime-graph-stat-label">最近任务</div>' +
   '<div class="runtime-graph-stat-value">' + _runtimeGraphCount(summary.run_count || 0) + '</div>' +
   '<div class="runtime-graph-stat-note">从历史过程里抽出来的真实运行轨迹</div>' +
  '</div>' +
  '<div class="runtime-graph-stat ' + ((selectedRun && selectedRun.status === 'error') ? 'is-error' : '') + '">' +
   '<div class="runtime-graph-stat-label">当前卡点</div>' +
   '<div class="runtime-graph-stat-value runtime-graph-stat-text">' + _runtimeGraphEscape(stuck) + '</div>' +
   '<div class="runtime-graph-stat-note">' + _runtimeGraphEscape(selectedRun ? ('触发：' + _runtimeGraphTrim(selectedRun.trigger || '', 40)) : '等待任务选中') + '</div>' +
  '</div>';
}

function _renderRuntimeGraphRuns(runs, selectedRun) {
 var box = document.getElementById('runtimeGraphRuns');
 if (!box) return;
 if (!runs || !runs.length) {
  box.innerHTML = '<div class="runtime-graph-empty">还没有找到带过程记录的任务。</div>';
  return;
 }
 var html = '';
 runs.forEach(function(run) {
  var active = selectedRun && run.id === selectedRun.id;
  var cls = 'runtime-run-card' + (active ? ' is-active' : '') + (run.status === 'error' ? ' is-error' : '');
  html += '<button class="' + cls + '" data-run-id="' + _runtimeGraphEscape(run.id) + '" type="button">' +
   '<div class="runtime-run-head">' +
    '<span class="runtime-run-time">' + _runtimeGraphEscape(_runtimeGraphFormatTime(run.time)) + '</span>' +
    '<span class="runtime-run-state">' + (run.status === 'error' ? '卡住' : '跑通') + '</span>' +
   '</div>' +
   '<div class="runtime-run-preview">' + _runtimeGraphEscape(run.preview || '这轮没有可见回复摘要') + '</div>' +
   '<div class="runtime-run-meta"><span>触发</span><strong>' + _runtimeGraphEscape(_runtimeGraphTrim(run.trigger || '未记录', 58)) + '</strong></div>' +
   '<div class="runtime-run-meta ' + (run.stuck ? 'danger' : '') + '"><span>卡点</span><strong>' + _runtimeGraphEscape(_runtimeGraphTrim(run.stuck || '无', 58)) + '</strong></div>' +
  '</button>';
 });
 box.innerHTML = html;
 box.querySelectorAll('.runtime-run-card').forEach(function(btn) {
  btn.onclick = function() { _selectRuntimeGraphRun(btn.getAttribute('data-run-id')); };
 });
}

function _renderRuntimeGraphSteps(selectedRun) {
 var box = document.getElementById('runtimeGraphSteps');
 var headline = document.getElementById('runtimeGraphStepHeadline');
 var title = document.getElementById('runtimeGraphFlowTitle');
 var mode = document.getElementById('runtimeGraphFlowMode');
 var meta = document.getElementById('runtimeGraphFlowMeta');
 var panel = document.getElementById('runtimeGraphFlowPanel');
 var focusMode = window._runtimeGraphState.viewMode === 'focus' && !!selectedRun;
 if (!box || !headline || !title || !mode || !meta || !panel) return;
 panel.classList.toggle('is-hidden', focusMode);
 if (focusMode) return;
 title.textContent = focusMode ? '流程聚焦 · 本轮步骤' : '当前任务步骤';
 mode.textContent = focusMode ? '流程聚焦' : '全量底图中的当前路径';
 mode.classList.toggle('is-focus', focusMode);
 if (!selectedRun) {
  headline.textContent = '还没有选中的任务。';
  meta.innerHTML = '';
  box.innerHTML = '<div class="runtime-graph-empty">先点击一轮任务，再看详细步骤。</div>';
  return;
 }
 headline.textContent = '当前高亮：' + _runtimeGraphFormatTime(selectedRun.time) + ' / ' + (selectedRun.status === 'error' ? '有错误' : '已跑通');
 meta.innerHTML =
  '<div class="runtime-graph-flow-chip">' +
   '<span class="runtime-graph-flow-chip-label">触发</span>' +
   '<strong>' + _runtimeGraphEscape(_runtimeGraphTrim(selectedRun.trigger || '未记录', 80)) + '</strong>' +
  '</div>' +
  '<div class="runtime-graph-flow-chip">' +
   '<span class="runtime-graph-flow-chip-label">回复</span>' +
   '<strong>' + _runtimeGraphEscape(_runtimeGraphTrim(selectedRun.preview || '这轮没有可见回复摘要', 92)) + '</strong>' +
  '</div>' +
  '<div class="runtime-graph-flow-chip' + (selectedRun.stuck ? ' is-error' : '') + '">' +
   '<span class="runtime-graph-flow-chip-label">卡点</span>' +
   '<strong>' + _runtimeGraphEscape(_runtimeGraphTrim(selectedRun.stuck || '无', 80)) + '</strong>' +
  '</div>';
 var html = '';
 (selectedRun.steps || []).forEach(function(step, index) {
  var cls = 'runtime-step-row' + (step.status === 'error' ? ' is-error' : '');
  var targets = (step.targets || []).length ? ('目标节点：' + (step.targets || []).join(' -> ')) : '这一步没有落到具体节点';
  html += '<div class="' + cls + '">' +
   '<div class="runtime-step-index">' + (index + 1) + '</div>' +
   '<div class="runtime-step-body">' +
    '<div class="runtime-step-label">' + _runtimeGraphEscape(step.label || '步骤') + '</div>' +
    '<div class="runtime-step-detail">' + _runtimeGraphEscape(step.detail || '') + '</div>' +
    '<div class="runtime-step-targets">' + _runtimeGraphEscape(targets) + '</div>' +
   '</div>' +
  '</div>';
 });
 box.innerHTML = html || '<div class="runtime-graph-empty">这轮任务没有步骤明细。</div>';
}

function _renderRuntimeGraphBoard(data, selectedRun) {
 var stage = document.getElementById('runtimeGraphStage');
 var viewport = document.getElementById('runtimeGraphViewport');
 var statusEl = document.getElementById('runtimeGraphStatus');
 if (!stage) return;
 var board = _runtimeGraphBuildBoard(data, selectedRun);
 var nodes = board.nodes || [];
 if (!nodes.length) {
  stage.innerHTML = '<div class="runtime-graph-empty">当前还没有可展示的节点。</div>';
  if (statusEl) statusEl.textContent = '没有拿到任何图谱节点';
  return;
 }
 var layout = board.focusMode ? _runtimeGraphFocusLayout(nodes, board.sequence) : _runtimeGraphLayout(nodes);
 var positions = layout.positions || {};
 var activeSet = _runtimeGraphSet(board.activeIds || []);
 var errorSet = _runtimeGraphSet(board.errorIds || []);
 var staticEdges = (board.staticEdges || []).filter(function(edge) {
  return positions[edge.source] && positions[edge.target];
 });
 var pathEdges = board.pathEdges || [];
 var fitScale = _runtimeGraphFitScale(layout, viewport, board.focusMode);
 var scaledWidth = layout.width * fitScale;
 var scaledHeight = layout.height * fitScale;
 var viewportWidth = viewport ? viewport.clientWidth : 0;
 var viewportHeight = viewport ? viewport.clientHeight : 0;
 var offsetX = board.focusMode ? Math.max(12, (viewportWidth - scaledWidth) / 2) : 0;
 var offsetY = board.focusMode ? Math.max(12, (viewportHeight - scaledHeight) / 2) : 0;
 stage.classList.toggle('is-focus', !!board.focusMode);
 stage.style.width = Math.max(viewportWidth || 0, scaledWidth + offsetX * 2) + 'px';
 stage.style.height = Math.max(viewportHeight || 0, scaledHeight + offsetY * 2) + 'px';
 stage.innerHTML = '<div class="runtime-graph-canvas' + (board.focusMode ? ' is-focus' : '') + '" style="width:' + layout.width + 'px;height:' + layout.height + 'px;transform:translate(' + offsetX + 'px,' + offsetY + 'px) scale(' + fitScale + ');">' +
  _runtimeGraphRenderSvg(layout, staticEdges, pathEdges) +
  _runtimeGraphRenderGroups(layout.groups || []) +
  _runtimeGraphRenderNodes(layout.nodes, positions, activeSet, errorSet, board.focusMode) +
  '</div>';
 stage.querySelectorAll('.runtime-graph-node').forEach(function(nodeEl) {
  nodeEl.onclick = function() {
   var path = nodeEl.getAttribute('data-path') || '';
   var subtitle = nodeEl.getAttribute('data-subtitle') || '';
   if (statusEl) statusEl.textContent = subtitle && path ? (subtitle + ' · ' + path) : (subtitle || path || '节点详情');
  };
  nodeEl.onmouseenter = function() {
   var path = nodeEl.getAttribute('data-path') || '';
   var subtitle = nodeEl.getAttribute('data-subtitle') || '';
   if (statusEl && (path || subtitle)) statusEl.textContent = subtitle && path ? (subtitle + ' · ' + path) : (subtitle || path);
  };
 });
 if (statusEl) {
  if (board.focusMode && selectedRun) {
   statusEl.textContent = '流程聚焦：正在尽量把这一轮路径压进一屏';
  } else {
   statusEl.textContent = selectedRun
    ? ('当前高亮：' + _runtimeGraphTrim(selectedRun.preview || selectedRun.trigger || '', 88))
    : '当前显示全量代码底图';
  }
 }
}

function _runtimeGraphVisibleNodes(data, selectedRun) {
 var nodes = [];
 var seen = {};
 (data.nodes || []).forEach(function(node) {
  if (!node || !node.id || seen[node.id]) return;
  seen[node.id] = true;
  nodes.push(_runtimeGraphClone(node));
 });
 ((selectedRun && selectedRun.external_nodes) || []).forEach(function(node) {
  if (!node || !node.id || seen[node.id]) return;
  seen[node.id] = true;
  nodes.push(_runtimeGraphClone(node));
 });
 return nodes;
}

function _runtimeGraphBuildBoard(data, selectedRun) {
 var allNodes = _runtimeGraphVisibleNodes(data, selectedRun);
 var activeIds = (selectedRun && selectedRun.node_ids) || [];
 var errorIds = (selectedRun && selectedRun.error_node_ids) || [];
 var pathEdges = (selectedRun && selectedRun.path_edges) || [];
 var focusMode = window._runtimeGraphState.viewMode === 'focus' && !!selectedRun;
 if (!focusMode) {
  return {
   nodes: allNodes,
   activeIds: activeIds,
   errorIds: errorIds,
   pathEdges: pathEdges,
   staticEdges: data.edges || [],
   focusMode: false,
   sequence: [],
  };
 }

 var nodeMap = {};
 allNodes.forEach(function(node) { nodeMap[node.id] = node; });
 var sequence = _runtimeGraphFocusSequence(selectedRun);
 var visibleIds = {};
 sequence.forEach(function(id) { visibleIds[id] = true; });
 activeIds.forEach(function(id) { visibleIds[id] = true; });
 errorIds.forEach(function(id) { visibleIds[id] = true; });
 ((selectedRun && selectedRun.external_nodes) || []).forEach(function(node) {
  if (node && node.id) visibleIds[node.id] = true;
 });

 var nodes = [];
 Object.keys(visibleIds).forEach(function(id) {
  if (nodeMap[id]) nodes.push(_runtimeGraphClone(nodeMap[id]));
 });
 nodes.sort(function(a, b) {
  var ai = sequence.indexOf(a.id);
  var bi = sequence.indexOf(b.id);
  if (ai === -1 && bi === -1) return String(a.path || a.label || '').localeCompare(String(b.path || b.label || ''));
  if (ai === -1) return 1;
  if (bi === -1) return -1;
  return ai - bi;
 });

 var staticEdges = (data.edges || []).filter(function(edge) {
  return visibleIds[edge.source] && visibleIds[edge.target];
 });
 return {
  nodes: nodes,
  activeIds: activeIds,
  errorIds: errorIds,
  pathEdges: pathEdges.filter(function(edge) { return visibleIds[edge.source] && visibleIds[edge.target]; }),
  staticEdges: staticEdges,
  focusMode: true,
  sequence: sequence,
 };
}

function _runtimeGraphFocusSequence(selectedRun) {
 var ordered = [];
 var seen = {};
 function push(id) {
  if (!id || seen[id]) return;
  seen[id] = true;
  ordered.push(id);
 }
 ((selectedRun && selectedRun.path_edges) || []).forEach(function(edge) {
  push(edge.source);
  push(edge.target);
 });
 if (!ordered.length) {
  ((selectedRun && selectedRun.node_ids) || []).forEach(push);
 }
 return ordered;
}

function _runtimeGraphLayout(nodes) {
 var groupMap = {};
 nodes.forEach(function(node) {
  var key = node.cluster || 'misc';
  if (!groupMap[key]) {
    groupMap[key] = {
     key: key,
     label: node.cluster_label || key,
     rank: Number(node.cluster_rank || 999),
     color: node.cluster_color || '#64748b',
     nodes: [],
    };
  }
  groupMap[key].nodes.push(node);
 });
 var groups = Object.keys(groupMap).map(function(key) { return groupMap[key]; });
 groups.sort(function(a, b) {
  if (a.rank !== b.rank) return a.rank - b.rank;
  return String(a.label).localeCompare(String(b.label));
 });

 var cursorX = 24;
 var width = 0;
 var height = 0;
 var maxRows = 18;
 var nodeWidth = 226;
 var nodeHeight = 42;
 var rowGap = 12;
 var colGap = 18;
 var groupGap = 34;
 var groupHeader = 88;
 var groupPadding = 14;
 var positions = {};

 groups.forEach(function(group) {
  group.nodes.sort(function(a, b) {
   var pathA = String(a.path || a.label || '');
   var pathB = String(b.path || b.label || '');
   return pathA.localeCompare(pathB);
  });
  var rows = Math.max(1, Math.min(maxRows, group.nodes.length));
  var cols = Math.max(1, Math.ceil(group.nodes.length / rows));
  var bodyRows = Math.min(rows, group.nodes.length);
  var blockWidth = groupPadding * 2 + cols * nodeWidth + Math.max(0, cols - 1) * colGap;
  var blockHeight = groupHeader + bodyRows * nodeHeight + Math.max(0, bodyRows - 1) * rowGap + groupPadding;
  group.x = cursorX;
  group.y = 22;
  group.width = blockWidth;
  group.height = blockHeight;
  group.nodes.forEach(function(node, index) {
   var col = Math.floor(index / rows);
   var row = index % rows;
   var x = cursorX + groupPadding + col * (nodeWidth + colGap);
   var y = 22 + groupHeader + row * (nodeHeight + rowGap);
   positions[node.id] = { x: x, y: y, width: nodeWidth, height: nodeHeight };
  });
  cursorX += blockWidth + groupGap;
  width = Math.max(width, cursorX);
  height = Math.max(height, blockHeight + 44);
 });

 return {
  width: Math.max(width, 1200),
  height: Math.max(height, 760),
  groups: groups,
  nodes: nodes,
  positions: positions,
 };
}

function _runtimeGraphFocusLayout(nodes, sequence) {
 var positions = {};
 var ordered = [];
 var nodeMap = {};
 (nodes || []).forEach(function(node) { nodeMap[node.id] = node; });
 (sequence || []).forEach(function(id) {
  if (nodeMap[id]) ordered.push(nodeMap[id]);
 });
 (nodes || []).forEach(function(node) {
  if (ordered.indexOf(node) === -1) ordered.push(node);
 });

 var cols = Math.max(2, Math.min(4, Math.ceil(Math.sqrt(Math.max(ordered.length, 1)) * 1.35)));
 var nodeWidth = 232;
 var nodeHeight = 112;
 var colGap = 18;
 var rowGap = 18;
 var padding = 24;
 var rows = Math.max(1, Math.ceil(ordered.length / cols));

 ordered.forEach(function(node, index) {
  var col = index % cols;
  var row = Math.floor(index / cols);
  positions[node.id] = {
   x: padding + col * (nodeWidth + colGap),
   y: padding + row * (nodeHeight + rowGap),
   width: nodeWidth,
   height: nodeHeight,
  };
 });

 return {
  width: Math.max(480, padding * 2 + cols * nodeWidth + Math.max(0, cols - 1) * colGap),
  height: Math.max(240, padding * 2 + rows * nodeHeight + Math.max(0, rows - 1) * rowGap),
  groups: [],
  nodes: ordered,
  positions: positions,
 };
}

function _runtimeGraphFitScale(layout, viewport, focusMode) {
 if (!focusMode || !viewport) return 1;
 var availableWidth = Math.max(320, viewport.clientWidth - 28);
 var availableHeight = Math.max(320, viewport.clientHeight - 28);
 if (!availableWidth || !availableHeight) return 1;
 return Math.min(1, availableWidth / layout.width, availableHeight / layout.height);
}

function _runtimeGraphRenderSvg(layout, staticEdges, pathEdges) {
 var html = '<svg class="runtime-graph-links" width="' + layout.width + '" height="' + layout.height + '" viewBox="0 0 ' + layout.width + ' ' + layout.height + '" preserveAspectRatio="xMinYMin meet">';
 staticEdges.forEach(function(edge) {
  var from = layout.positions[edge.source];
  var to = layout.positions[edge.target];
  if (!from || !to) return;
  html += '<path class="runtime-link runtime-link-' + _runtimeGraphEscape(edge.kind || 'import') + '" d="' + _runtimeGraphCurve(from, to) + '"></path>';
 });
 pathEdges.forEach(function(edge) {
  var from = layout.positions[edge.source];
  var to = layout.positions[edge.target];
  if (!from || !to) return;
  html += '<path class="runtime-link runtime-link-live" d="' + _runtimeGraphCurve(from, to) + '"></path>';
 });
 html += '</svg>';
 return html;
}

function _runtimeGraphRenderGroups(groups) {
 var html = '';
 groups.forEach(function(group) {
  html += '<div class="runtime-graph-group" style="left:' + group.x + 'px;top:' + group.y + 'px;width:' + group.width + 'px;height:' + group.height + 'px;border-color:' + group.color + '22;background:linear-gradient(180deg,' + group.color + '10,rgba(255,255,255,0.02));">' +
   '<div class="runtime-graph-group-head">' +
    '<div class="runtime-graph-group-title">' + _runtimeGraphEscape(group.label) + '</div>' +
    '<div class="runtime-graph-group-count">' + group.nodes.length + ' 个节点</div>' +
   '</div>' +
  '</div>';
 });
 return html;
}

function _runtimeGraphRenderNodes(nodes, positions, activeSet, errorSet, compactMode) {
 var html = '';
 nodes.forEach(function(node) {
  var pos = positions[node.id];
  if (!pos) return;
  var cls = 'runtime-graph-node kind-' + _runtimeGraphSafeClass(node.kind || 'file');
  if (activeSet[node.id]) cls += ' is-active';
  if (errorSet[node.id]) cls += ' is-error';
 if ((node.cluster || '') === 'runtime') cls += ' is-runtime';
 if ((node.cluster || '') === 'external') cls += ' is-external';
 if (compactMode) cls += ' is-compact';
  var subtitle = _runtimeGraphNodeSubtitle(node);
  var statusText = _runtimeGraphNodeStatusLabel(node.id, activeSet, errorSet);
  var hoverText = subtitle && node.path ? (subtitle + ' · ' + node.path) : (subtitle || node.path || node.label || node.id);
  html += '<button class="' + cls + '" data-path="' + _runtimeGraphEscape(node.path || '') + '" data-subtitle="' + _runtimeGraphEscape(subtitle) + '" title="' + _runtimeGraphEscape(hoverText) + '" type="button" style="left:' + pos.x + 'px;top:' + pos.y + 'px;width:' + pos.width + 'px;height:' + pos.height + 'px;border-color:' + _runtimeGraphEscape(node.cluster_color || '#64748b') + '55;">' +
   (compactMode
    ? _runtimeGraphRenderFocusNode(node, subtitle, statusText)
    : ('<div class="runtime-node-title">' + _runtimeGraphEscape(node.label || node.id) + '</div>' + (subtitle ? ('<div class="runtime-node-subtitle">' + _runtimeGraphEscape(subtitle) + '</div>') : ''))) +
  '</button>';
 });
 return html;
}

function _runtimeGraphCurve(from, to) {
 var x1 = from.x + from.width;
 var y1 = from.y + from.height / 2;
 var x2 = to.x;
 var y2 = to.y + to.height / 2;
 var dx = Math.max(42, Math.abs(x2 - x1) * 0.44);
 return 'M' + x1 + ' ' + y1 + ' C ' + (x1 + dx) + ' ' + y1 + ', ' + (x2 - dx) + ' ' + y2 + ', ' + x2 + ' ' + y2;
}

function _runtimeGraphFormatTime(raw) {
 if (!raw) return '未知时间';
 try {
  var dt = new Date(raw);
  if (isNaN(dt.getTime())) return String(raw);
  var mm = String(dt.getMonth() + 1).padStart(2, '0');
  var dd = String(dt.getDate()).padStart(2, '0');
  var hh = String(dt.getHours()).padStart(2, '0');
  var mi = String(dt.getMinutes()).padStart(2, '0');
  return mm + '-' + dd + ' ' + hh + ':' + mi;
 } catch (e) {
  return String(raw);
 }
}

function _runtimeGraphTrim(text, limit) {
 var normalized = String(text || '').replace(/\s+/g, ' ').trim();
 if (normalized.length <= limit) return normalized;
 return normalized.slice(0, Math.max(0, limit - 1)) + '…';
}

function _runtimeGraphCount(value) {
 return String(Number(value || 0));
}

function _runtimeGraphSet(items) {
 var out = {};
 (items || []).forEach(function(item) { out[item] = true; });
 return out;
}

function _runtimeGraphClone(obj) {
 var copy = {};
 Object.keys(obj || {}).forEach(function(key) { copy[key] = obj[key]; });
 return copy;
}

function _runtimeGraphSafeClass(value) {
 return String(value || '').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
}

function _runtimeGraphHasStandaloneRoot() {
 return !!document.getElementById('runtimeGraphStandaloneRoot');
}

window.addEventListener('DOMContentLoaded', function() {
 if (_runtimeGraphHasStandaloneRoot()) {
  mountStandaloneRuntimeGraphPage('runtimeGraphStandaloneRoot');
 }
});

window.addEventListener('resize', function() {
 if (window._runtimeGraphState && window._runtimeGraphState.data) {
  if (window._runtimeGraphState.standalone || window._currentTab === 8) {
   _renderRuntimeGraphPage();
  }
 }
});

document.addEventListener('visibilitychange', function() {
 _syncRuntimeGraphAutoRefresh();
 if (!document.hidden && window._runtimeGraphState.autoRefreshEnabled && _runtimeGraphCanAutoRefresh()) {
  _loadRuntimeGraphData(true);
 }
});

window.addEventListener('beforeunload', function() {
 if (window._runtimeGraphState.autoRefreshTimer) {
  clearInterval(window._runtimeGraphState.autoRefreshTimer);
  window._runtimeGraphState.autoRefreshTimer = 0;
 }
});
