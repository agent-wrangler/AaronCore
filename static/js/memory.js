function toggleCat(el) {
  var next = el.nextElementSibling;
  var arrow = el.querySelector("span:last-child");
  if (next.style.display === "none") {
    next.style.display = "block";
    arrow.innerHTML = "-";
  } else {
    next.style.display = "none";
    arrow.innerHTML = "+";
  }
}

var currentMemoryFilter = "all";
var MEM_PAGE_SIZE = 20;
var _memCurrentPage = 1;
var _memFilteredItems = [];

function _memRenderPage() {
  var labelColor = "var(--text-label)";
  var textColor = "var(--text-primary)";
  var cardBg = "var(--surface-panel)";
  var borderColor = "var(--border-panel)";

  var total = _memFilteredItems.length;
  var totalPages = Math.max(1, Math.ceil(total / MEM_PAGE_SIZE));
  _memCurrentPage = Math.max(1, Math.min(_memCurrentPage, totalPages));

  var start = (_memCurrentPage - 1) * MEM_PAGE_SIZE;
  var pageItems = _memFilteredItems.slice(start, start + MEM_PAGE_SIZE);

  var grouped = {};
  var dates = [];
  pageItems.forEach(function (eventItem) {
    var date = (eventItem.time || "").substring(0, 10) || "未知日期";
    if (!grouped[date]) {
      grouped[date] = [];
      dates.push(date);
    }
    grouped[date].push(eventItem);
  });
  dates.sort().reverse();

  var html = "";
  dates.forEach(function (date) {
    var label = _memoryDateLabel(date);
    html += '<div class="mem-date-group">';
    html +=
      '<div class="mem-date-label" style="font-size:11px;color:' +
      labelColor +
      ";margin:18px 0 8px 0;font-weight:600;letter-spacing:0.24px;\">" +
      escapeHtml(label) +
      "</div>";

    grouped[date].forEach(function (eventItem) {
      var view = memoryEventCopy(eventItem);
      var layer = eventItem.layer || "MEM";
      var tagCls = "mem-tag mem-tag-" + (/^L[1-8]$/.test(layer) ? layer : "default");
      var time = eventItem.time ? String(eventItem.time).replace("T", " ").substring(11, 16) : "";

      html +=
        '<div class="mem-item" data-layer="' +
        escapeHtml(layer) +
        '" style="padding:16px 18px;background:' +
        cardBg +
        ";border:1px solid " +
        borderColor +
        ';border-radius:16px;margin-bottom:10px;position:relative;overflow:hidden;">';
      html +=
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px;"><div style="display:flex;align-items:center;gap:8px;min-width:0;"><span class="' +
        tagCls +
        '">' +
        escapeHtml(layer) +
        '</span><span style="font-size:15px;font-weight:600;color:' +
        textColor +
        ';letter-spacing:0.2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
        escapeHtml(view.title) +
        '</span></div><span style="font-size:11px;color:' +
        labelColor +
        ';flex-shrink:0;">' +
        escapeHtml(time) +
        "</span></div>";
      html += '<div style="font-size:13px;color:var(--text-secondary);line-height:1.82;">' + view.content + "</div>";
      html += "</div>";
    });

    html += "</div>";
  });

  if (!html) {
    html = '<div style="color:' + labelColor + ';">没有匹配的记忆事件</div>';
  }

  var btnBase =
    "padding:7px 14px;border-radius:10px;border:1px solid var(--border-chip);background:var(--bg-chip);color:var(--text-primary);font-size:13px;cursor:pointer;";
  var btnDisabled =
    "padding:7px 14px;border-radius:10px;border:1px solid var(--border-card);background:transparent;color:var(--text-label);font-size:13px;cursor:default;opacity:0.5;";

  html += '<div style="display:flex;align-items:center;justify-content:center;gap:12px;margin-top:20px;padding-bottom:8px;">';
  html +=
    '<button style="' +
    (_memCurrentPage <= 1 ? btnDisabled : btnBase) +
    '" onclick="memGoPage(' +
    (_memCurrentPage - 1) +
    ')" ' +
    (_memCurrentPage <= 1 ? "disabled" : "") +
    ">← 上一页</button>";
  html +=
    '<span style="font-size:13px;color:' +
    labelColor +
    ';">第 ' +
    _memCurrentPage +
    " 页 / 共 " +
    totalPages +
    " 页（" +
    total +
    " 条）</span>";
  html +=
    '<button style="' +
    (_memCurrentPage >= totalPages ? btnDisabled : btnBase) +
    '" onclick="memGoPage(' +
    (_memCurrentPage + 1) +
    ')" ' +
    (_memCurrentPage >= totalPages ? "disabled" : "") +
    ">下一页 →</button>";
  html += "</div>";

  var timeline = document.getElementById("memoryTimeline");
  if (timeline) {
    timeline.innerHTML = html;
  }

  var scrollContainer = document.getElementById("memScroll");
  if (scrollContainer) {
    scrollContainer.scrollTop = 0;
  }
}

function _memoryDateLabel(date) {
  var now = new Date();
  var today =
    now.getFullYear() +
    "-" +
    String(now.getMonth() + 1).padStart(2, "0") +
    "-" +
    String(now.getDate()).padStart(2, "0");
  var yesterdayDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
  var yesterday =
    yesterdayDate.getFullYear() +
    "-" +
    String(yesterdayDate.getMonth() + 1).padStart(2, "0") +
    "-" +
    String(yesterdayDate.getDate()).padStart(2, "0");

  if (date === today) return "今天";
  if (date === yesterday) return "昨天";
  return date;
}

function memGoPage(page) {
  _memCurrentPage = page;
  _memRenderPage();
}

function syncMemoryDateGroups() {
}

function filterMemBySearch(query) {
  query = (query || "").toLowerCase();
  var allEvents = window._memAllEvents || [];
  _memFilteredItems = allEvents.filter(function (eventItem) {
    var metaText = "";
    try {
      metaText = JSON.stringify(eventItem.meta || {});
    } catch (err) {
      metaText = "";
    }
    var text = ((eventItem.content || "") + (eventItem.title || "") + metaText).toLowerCase();
    var matchesText = !query || text.includes(query);
    var matchesLayer = currentMemoryFilter === "all" || eventItem.layer === currentMemoryFilter;
    return matchesText && matchesLayer;
  });
  _memCurrentPage = 1;
  _memRenderPage();
}

function setMemoryFilter(layer, el) {
  currentMemoryFilter = layer;
  document.querySelectorAll(".mem-chip").forEach(function (node) {
    node.style.background = "var(--bg-chip)";
    node.style.color = "var(--text-chip)";
    node.style.borderColor = "var(--border-chip)";
  });
  if (el) {
    el.style.background = "linear-gradient(135deg, #7a7267 0%, #625b52 100%)";
    el.style.color = "#ffffff";
    el.style.borderColor = "transparent";
  }
  filterMemBySearch((document.getElementById("memorySearch") || {}).value || "");
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function safeText(text) {
  return escapeHtml(String(text || "").replace(/\u0000/g, "").trim());
}

function safeMultiline(text) {
  return safeText(text).replace(/\r?\n+/g, "<br>");
}

function emphasizeQuoted(text) {
  return String(text || "").replace(
    /「([^」]+)」/g,
    '<strong style="font-weight:700;letter-spacing:0.2px;">「$1」</strong>'
  );
}

function detectSkillName(text) {
  text = String(text || "");
  var boxed = text.match(/【([^】]+)】/);
  if (boxed) return boxed[1];

  var square = text.match(/\[([^\]]+)\]/);
  if (square) return square[1];

  var quoted = text.match(/「([^」]+)」/);
  if (quoted) return quoted[1];

  var slashLead = text.match(/^\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*\//);
  if (slashLead) return slashLead[1];

  var known = text.match(/\b(story|weather|draw|run_code|llm_chat|web_search|open_target)\b/i);
  return known ? known[1] : "";
}

function isDirtyText(text) {
  text = String(text || "");
  return /\?\?\?|�|锟斤拷|\u0000|\u0001|\u0002/.test(text);
}

function layerLabel(layer) {
  if (layer === "L1") return "记忆粒子";
  if (layer === "L2") return "记忆凝结";
  if (layer === "L3") return "记忆结晶";
  if (layer === "L4") return "人格图谱";
  if (layer === "L5") return "方法经验";
  if (layer === "L6") return "执行轨迹";
  if (layer === "L7") return "反馈学习";
  if (layer === "L8") return "已学知识";
  return "系统事件";
}

function memoryEventCopy(eventItem) {
  var layer = eventItem.layer || "Lx";
  var meta = normalizeMemoryMeta(eventItem);
  var rawContent = eventItem.content || "";
  var rawTitle = eventItem.title || "";
  var type = eventItem.event_type || "";

  return {
    title: memoryEventTitle(layer, meta, rawTitle),
    content: emphasizeQuoted(memoryEventContent(layer, meta, rawContent, type)),
  };
}

function normalizeMemoryMeta(eventItem) {
  var meta = eventItem.meta || {};
  if (meta.kind) return meta;
  return inferLegacyMemoryMeta(eventItem.layer || "", eventItem.title || "", eventItem.content || "", eventItem.event_type || "");
}

function isGenericL8Title(title) {
  title = String(title || "").trim();
  return (
    !title ||
    title === "能力进化" ||
    title === "成长经验" ||
    title === "已学知识" ||
    title === "自主学习" ||
    title === "对话结晶"
  );
}

function extractLegacyL8Query(rawTitle, rawContent) {
  var title = String(rawTitle || "").trim();
  var content = String(rawContent || "").trim();
  var patterns = [
    /学到[「“"]([^」”"\n]+)[」”"]/,
    /习得经验[:：]\s*[「“"]([^」”"\n]+)[」”"]/,
    /学习了[「“"]([^」”"\n]+)[」”"]/,
    /主题[:：]\s*([^\n：:]+)/,
  ];
  var i = 0;
  var match = null;

  if (!isGenericL8Title(title)) return title;

  for (i = 0; i < patterns.length; i += 1) {
    match = content.match(patterns[i]);
    if (match && match[1]) return String(match[1]).trim();
  }

  match = content.match(/^([^：:\n]{2,60})[:：]/);
  if (match && match[1]) return String(match[1]).trim();

  match = content.match(/^([^\n]{2,60})$/);
  if (match && match[1]) return String(match[1]).trim();

  return "";
}

function extractLegacyL8Summary(rawContent, query) {
  var summary = String(rawContent || "").trim();
  var escapedQuery = String(query || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  if (!summary) return "";

  summary = summary
    .replace(/^学到[「“"][^」”"]+[」”][：:，,\s]*/, "")
    .replace(/^习得经验[：:]\s*[「“"][^」”"]+[」”][：:，,\s]*/, "")
    .replace(/^学习了[「“"][^」”"]+[」”][：:，,\s]*/, "")
    .replace(/^主题[：:]\s*[^：:\n]+[：:，,\s]*/, "")
    .trim();

  if (escapedQuery) {
    summary = summary
      .replace(new RegExp("^" + escapedQuery + "[：:，,\\s]*"), "")
      .trim();
  }

  return summary;
}

function inferLegacyMemoryMeta(layer, rawTitle, rawContent, type) {
  var title = String(rawTitle || "");
  var content = String(rawContent || "");
  var skill = detectSkillName(content);

  if (layer === "L5") {
    var successCount = parseMemoryCount(content, /已沉淀\s*(\d+)\s*次/);
    var visibleCount = parseMemoryCount(content, /已掌握\s*(\d+)\s*项技能/);
    var isLegacyMethod = title.indexOf("成功经验") !== -1 || successCount > 0;
    var isLegacyAbility =
      title.indexOf("技能矩阵") !== -1 ||
      type === "skill" ||
      content.indexOf("解锁新技能") !== -1 ||
      content.indexOf("掌握了新技能") !== -1;

    if (isLegacyMethod) {
      return {
        kind: "method_experience",
        skill: skill,
        summary: content,
        success_count: successCount,
        inferred_from_legacy: true,
      };
    }

    if (isLegacyAbility) {
      return {
        kind: "ability_hint",
        skill: skill,
        visible_count: visibleCount,
        inferred_from_legacy: true,
      };
    }
  }

  if (layer === "L6") {
    var executionCount = parseMemoryCount(content, /累计\s*(\d+)\s*次/);
    var observedMatch = content.match(/observed=([^/]+)/);
    var driftMatch = content.match(/drift=([^/]+)/);
    var summary = extractLegacyExecutionSummary(content, skill);
    var isLegacyExecutionCount =
      title.indexOf("技能执行") !== -1 ||
      content.indexOf("使用了：") !== -1 ||
      content.indexOf("完成了一次技能调用") !== -1;

    if (isLegacyExecutionCount) {
      return {
        kind: "execution_count",
        skill: skill,
        count: executionCount,
        status_note: content,
        inferred_from_legacy: true,
      };
    }

    if (title.indexOf("执行轨迹") !== -1 || type === "evolution") {
      return {
        kind: "execution_trace",
        skill: skill,
        summary: summary,
        verified: /verified|已验证/.test(content),
        observed_state: observedMatch ? String(observedMatch[1] || "").trim() : "",
        drift_reason: driftMatch ? String(driftMatch[1] || "").trim() : "",
        inferred_from_legacy: true,
      };
    }
  }

  if (layer === "L8") {
    var l8Query = extractLegacyL8Query(title, content);
    return {
      kind: "self_learned",
      query: l8Query,
      summary: extractLegacyL8Summary(content, l8Query),
      inferred_from_legacy: true,
    };
  }

  return {};
}

function parseMemoryCount(text, pattern) {
  var match = String(text || "").match(pattern);
  if (!match) return 0;
  return Number(match[1]) || 0;
}

function extractLegacyExecutionSummary(content, skill) {
  var text = String(content || "").trim();
  if (!text) return "";
  if (skill) {
    text = text.replace(skill, "").replace(/^[/\s-]+/, "").trim();
  }
  return text;
}

function memoryEventTitle(layer, meta, rawTitle) {
  if (meta.kind === "l2_impression") return safeText(meta.type_label) || "记忆凝结";
  if (meta.kind === "method_experience") return "方法经验";
  if (meta.kind === "ability_hint") return "能力线索";
  if (meta.kind === "execution_trace" || meta.kind === "execution_count") return "执行轨迹";
  if (meta.kind === "self_learned") return "自主学习";
  if (meta.kind === "dialogue_crystal") return "对话结晶";
  if (meta.kind === "feedback_relearn") return "纠偏补学";
  return rawTitle || layerLabel(layer);
}

function memoryEventContent(layer, meta, rawContent, type) {
  if (meta.kind === "l2_impression") return buildL2ImpressionContent(meta, rawContent);
  if (meta.kind === "method_experience") return buildMethodExperienceContent(meta, rawContent);
  if (meta.kind === "ability_hint") return buildAbilityHintContent(meta, rawContent);
  if (meta.kind === "execution_trace") return buildExecutionTraceContent(meta, rawContent);
  if (meta.kind === "execution_count") return buildExecutionCountContent(meta, rawContent);
  if (meta.kind === "self_learned" || meta.kind === "dialogue_crystal" || meta.kind === "feedback_relearn") {
    return buildL8KnowledgeContent(meta, rawContent);
  }
  return buildGenericMemoryContent(layer, rawContent, type);
}

function buildL2ImpressionContent(meta, rawContent) {
  var memoryType = safeText(meta.memory_type || "general");
  var userText = safeText(meta.user_text || "");
  var aiBrief = safeMultiline(meta.ai_brief || "");
  var hitCount = Number(meta.hit_count) || 0;
  var repeatCount = Number(meta.repeat_count) || 1;
  var crystallized = meta.crystallized === true;
  var retentionLabel = safeText(meta.retention_label || "");
  var retentionReason = safeText(meta.retention_reason || "");
  var lines = [];

  if (memoryType === "fact") lines.push("记住了一个用户事实：" + userText);
  else if (memoryType === "preference") lines.push("捕捉到一个偏好倾向：" + userText);
  else if (memoryType === "rule") lines.push("留住了一条当前约束：" + userText);
  else if (memoryType === "project") lines.push("捕捉到一个项目线索：" + userText);
  else if (memoryType === "goal") lines.push("识别到一个目标方向：" + userText);
  else if (memoryType === "decision") lines.push("留住了一次选择倾向：" + userText);
  else if (memoryType === "knowledge") lines.push("留下了一个知识问题：" + userText);
  else if (memoryType === "correction") lines.push("记下了一次纠正反馈：" + userText);
  else if (memoryType === "skill_demand") lines.push("保留了一条需求线索：" + userText);
  else if (userText && repeatCount > 1) lines.push("近期反复出现的对话印象：" + userText);
  else if (userText) lines.push("凝结了一段对话印象：" + userText);
  else if (rawContent && !isDirtyText(rawContent)) lines.push("凝结了一段对话印象：" + safeMultiline(rawContent));
  else lines.push("凝结了一段对话印象，留作短期上下文的兜底记忆。");

  if (aiBrief) lines.push("当时回应：" + aiBrief);
  if (repeatCount > 1) lines.push("重复出现：" + repeatCount + " 次");
  if (crystallized) lines.push("状态：已分发到更高层继续沉淀");
  else if (hitCount > 0) lines.push("复用：" + hitCount + " 次");
  else lines.push("状态：保留在 L2 作为短期兜底记忆");
  if (retentionLabel) {
    lines.push("保留策略：" + retentionLabel + (retentionReason ? "（" + retentionReason + "）" : ""));
  }

  return lines.join("<br>");
}

function buildMethodExperienceContent(meta, rawContent) {
  var skill = safeText(meta.skill || detectSkillName(rawContent));
  var summary = safeMultiline(meta.summary || rawContent);
  var successCount = Number(meta.success_count) || 0;
  var lines = [];

  if (skill) lines.push("围绕「" + skill + "」沉淀出一条可复用方法");
  else lines.push("从一次稳定成功路径中提炼出可复用方法");

  if (summary) lines.push("摘要：" + summary);
  if (successCount > 0) lines.push("沉淀次数：" + successCount + " 次");

  return lines.join("<br>");
}

function buildAbilityHintContent(meta, rawContent) {
  var skill = safeText(meta.skill || detectSkillName(rawContent));
  var visibleCount = Number(meta.visible_count) || 0;
  var lines = [];

  if (skill) lines.push("在 L5 中保留了「" + skill + "」这条能力线索");
  else lines.push("在 L5 中保留了一条新的能力线索");

  if (visibleCount > 0) lines.push("当前 L5 可见：" + visibleCount + " 项");

  return lines.join("<br>");
}

function buildExecutionTraceContent(meta, rawContent) {
  var skill = safeText(meta.skill || detectSkillName(rawContent));
  var summary = safeMultiline(meta.summary);
  var observed = safeMultiline(meta.observed_state);
  var driftReason = safeMultiline(meta.drift_reason);
  var verificationMode = safeText(meta.verification_mode);
  var verificationDetail = safeMultiline(meta.verification_detail);
  var verified = meta.verified;
  var lines = [];

  if (skill) lines.push("技能：「" + skill + "」");
  if (summary) lines.push("摘要：" + summary);
  else if (rawContent && !isDirtyText(rawContent)) lines.push("记录：" + safeMultiline(rawContent));

  if (verified === true) lines.push("状态：已验证");
  else if (driftReason) lines.push("状态：发生偏移");
  else lines.push("状态：已记录");

  if (verificationMode) lines.push("核验方式：" + verificationMode);
  if (verificationDetail) lines.push("核验细节：" + verificationDetail);
  if (driftReason) lines.push("偏移：" + driftReason);
  if (observed) lines.push("观测：" + observed);

  return lines.join("<br>");
}

function buildExecutionCountContent(meta, rawContent) {
  var skill = safeText(meta.skill || detectSkillName(rawContent));
  var count = Number(meta.count) || 0;
  var note = safeMultiline(meta.status_note || rawContent);
  var lines = [];

  if (skill) lines.push("技能：「" + skill + "」");
  if (count > 0) lines.push("累计轨迹：" + count + " 次");
  if (note) lines.push("状态：" + note);

  return lines.join("<br>");
}

function buildL8KnowledgeContent(meta, rawContent) {
  var query = safeText(meta.query || "");
  var summary = safeMultiline(meta.summary || rawContent);
  var sourceLabel = safeText(meta.source_label || "");
  var primaryScene = safeText(meta.primary_scene || "");
  var secondaryScene = safeText(meta.secondary_scene || "");
  var hitCount = Number(meta.hit_count) || 0;
  var lines = [];

  if (query) lines.push("主题：" + query);
  if (summary) lines.push("摘要：" + summary);
  if (sourceLabel) lines.push("来源：" + sourceLabel);
  if (primaryScene || secondaryScene) {
    lines.push("场景：" + [primaryScene, secondaryScene].filter(Boolean).join(" / "));
  }
  if (hitCount > 0) lines.push("复用：" + hitCount + " 次");
  else lines.push("状态：已沉淀为新的知识卡片");

  return lines.join("<br>");
}

function buildGenericMemoryContent(layer, rawContent, type) {
  if (!rawContent || isDirtyText(rawContent)) {
    if (layer === "L2") return "凝结了一段对话印象，这次交流留下了值得记住的痕迹。";
    if (layer === "L3") return "生成了一枚新的记忆结晶，这段内容已经开始形成稳定结构。";
    if (layer === "L4") return "人格图谱补全了一笔，后续回复会更贴近现在这版 Nova 的气质。";
    if (layer === "L5") return "L5 里沉淀出一条新的方法线索，后续复杂任务可以继续复用。";
    if (layer === "L6") return "记录下一次真实执行轨迹，后续会继续作为方法沉淀的素材。";
    if (layer === "L7") return "收到一条新的反馈，这次修正会继续影响后续判断。";
    if (layer === "L8") return "沉淀了一张新的已学知识卡片，后续会在相似问题里复用。";
    if (layer === "L1") return "捕捉到一枚新的记忆粒子，已经进入感知层等待沉淀。";
    return safeText(type) || "记录了一次新的系统变化。";
  }

  if (layer === "L2") {
    return "凝结了一段对话印象：" + safeMultiline(rawContent);
  }
  return safeMultiline(rawContent) || safeText(type) || "记录了一次新的系统变化。";
}

function memoryGrowthProfile(counts) {
  counts = counts || {};
  var l1 = Math.min(Number(counts.L1) || 0, 500);
  var l2 = Math.min(Number(counts.L2) || 0, 600);
  var l3 = Number(counts.L3) || 0;
  var l4 = Number(counts.L4) || 0;
  var l5 = Number(counts.L5) || 0;
  var l6 = Number(counts.L6) || 0;
  var l7 = Number(counts.L7) || 0;
  var l8 = Number(counts.L8) || 0;
  var totalExp = l1 * 1 + l2 * 5 + l3 * 12 + l4 * 20 + l5 * 8 + l6 * 3 + l7 * 15 + l8 * 10;
  var level = 1;
  var spent = 0;
  var nextNeed = 100;

  while (totalExp >= spent + nextNeed) {
    spent += nextNeed;
    level += 1;
    nextNeed = 100 + (level - 1) * 20;
  }

  var currentExp = Math.max(0, totalExp - spent);
  var remainingExp = Math.max(0, nextNeed - currentExp);
  var progressPercent = nextNeed > 0 ? Math.max(0, Math.min(100, Math.round((currentExp / nextNeed) * 100))) : 100;

  return {
    totalExp: totalExp,
    level: level,
    currentExp: currentExp,
    nextNeed: nextNeed,
    remainingExp: remainingExp,
    progressPercent: progressPercent,
  };
}

function formatGrowthNumber(n) {
  return (Number(n) || 0).toLocaleString("zh-CN");
}

function memoryOverviewColumns() {
  var contentWidth = Math.max(0, window.innerWidth - 320);
  if (contentWidth < 640) return "repeat(2,minmax(0,1fr))";
  return "minmax(250px,1.45fr) repeat(3,minmax(0,0.78fr))";
}
