const siteConfig = {
  productName: "AaronCore",
  brandSubline: "Memory that comes back naturally",
  primaryDomain: "aaroncore.com",
  contactLabel: "GitHub Issues",
  contactUrl: "https://github.com/agent-wrangler/AaronCore/issues",
  contactStatus: "public contact lives on GitHub for now",
  launchState: "Official site first",
  releaseRoute: "aaroncore.com / future download channel",
  metaDescription:
    "A memory-first agent project exploring how understanding, continuity, and action can grow from memory.",
  ogDescription:
    "AaronCore explores how agents can build real continuity through memory instead of isolated, one-off responses.",
  betaUrl: "#join-beta",
  betaLabel: "Join Beta",
  earlyAccessLabel: "Join Beta",
  demoUrl: "./product.html#proof",
  demoLabel: "See proof",
  docsUrl: "./docs.html",
  docsLabel: "Docs"
};

const releaseConfig = {
  available: false,
  url: "",
  label: "Download AaronCore",
  fallbackLabel: "Download Pending",
  version: "Beta pending",
  noteWhenLocked: "Public build is not attached yet.",
  noteWhenOpen: "Direct download is now live."
};

function setMeta(selector, value) {
  const node = document.querySelector(selector);
  if (node) {
    node.setAttribute("content", value);
  }
}

function setField(group, name, value) {
  document.querySelectorAll(`[data-${group}-field="${name}"]`).forEach((node) => {
    node.textContent = value;
  });
}

function applySiteState() {
  const page = String(document.body?.dataset?.page || "").trim();
  const titleSuffix =
    page === "product"
      ? "Product"
      : page === "docs"
        ? "Docs"
        : page === "changelog"
          ? "Changelog"
          : "AI that remembers you";

  document.title = `${siteConfig.productName} | ${titleSuffix}`;
  setMeta('meta[name="description"]', siteConfig.metaDescription);
  setMeta('meta[property="og:title"]', `${siteConfig.productName} | ${siteConfig.brandSubline}`);
  setMeta('meta[property="og:description"]', siteConfig.ogDescription);

  setField("site", "primaryDomain", siteConfig.primaryDomain);
  setField("site", "contactLabel", siteConfig.contactLabel);
  setField("site", "launchState", siteConfig.launchState);
  setField("site", "releaseRoute", siteConfig.releaseRoute);

  document.querySelectorAll("[data-link-field]").forEach((node) => {
    const hrefKey = node.getAttribute("data-link-field");
    const labelKey = node.getAttribute("data-link-label");
    const href = siteConfig[hrefKey];
    if (href) {
      node.setAttribute("href", href);
    }
    if (labelKey && siteConfig[labelKey] && !node.hasAttribute("data-i18n")) {
      node.textContent = siteConfig[labelKey];
    }
  });
}

const LANG_STORAGE_KEY = "aaroncore_site_lang";
const LANGS = ["en", "zh", "ja", "ko"];

const I18N = {
  en: {
    "brand.subline": "Memory that comes back naturally",
    "nav.home": "Home",
    "nav.product": "Product",
    "nav.docs": "Docs",
    "nav.changelog": "Changelog",
    "cta.joinBeta": "Join Beta",
    "cta.earlyAccess": "Join Beta",
    "cta.seeProof": "See product proof",
    "hero.h1Line1": "The real core",
    "hero.h1Line2": "starts with",
    "hero.h1Line3": "memory.",
    "hero.title": "When AI remembers you, everything that follows can continue naturally.",
    "hero.subtitle": "Familiarity, context, and task state should not be wiped clean every turn.",
    "hero.lede": "AaronCore does not treat memory as a standalone feature. It turns memory into the starting point for understanding, continuity, and action.",
    "hero.note": "Memory · Continuity · Action",
    "home.stage.kicker": "Desktop runtime",
    "home.stage.h": "One desktop loop for memory, tools, task state, and verification.",
    "home.stage.p": "AaronCore keeps context live while it routes the next step, runs tools, tracks progress, and leaves a result you can actually check.",
    "home.panel.exec.label": "What it does",
    "home.panel.exec.h": "The runtime can hold context, call tools, and keep moving without dropping the thread.",
    "home.panel.exec.p": "Task state, routing, and tool results stay attached while the work advances.",
    "home.panel.posture.label": "Why it matters",
    "home.panel.posture.h": "Continuity turns into forward motion",
    "home.panel.posture.p": "Memory matters because it stays connected to execution, verification, and the current desktop session.",
    "home.rail.1.h": "Anchor",
    "home.rail.1.p": "load current context, task state, and user intent",
    "home.rail.2.h": "Route",
    "home.rail.2.p": "activate the right surface: chat, tool use, recall, or verification",
    "home.rail.3.h": "Act",
    "home.rail.3.p": "run tools and push the task forward inside the same runtime",
    "home.rail.4.h": "Verify",
    "home.rail.4.p": "check the result and keep a trace of what actually changed",

    "home.how.h": "Why the conversations feel different",
    "home.how.p": "AaronCore does not just keep more context. It separates memory into layers, filters noise, and feeds the right memory back at the right moment.",
    "home.how.step1.h": "Flashback feels natural",
    "home.how.step1.p": "old threads resurface through state resonance, not crude keyword spam",
    "home.how.step2.h": "Time recall is built in",
    "home.how.step2.p": "you can ask what you talked about today, yesterday, or last week",
    "home.how.step3.h": "Persona keeps showing up",
    "home.how.step3.p": "preferences, dislikes, city, relationship, and rules feed back into replies",
    "home.how.step4.h": "Memory stays clean",
    "home.how.step4.p": "low-signal turns and polluted context are filtered before they become memory",

    "home.cap.h": "Built for execution, not just answers",
    "home.cap.p": "Memory, execution, routing, and verification live inside one runtime designed to move work forward.",
    "home.cap.exec.h": "The point is not to answer beautifully. The point is to move the work.",
    "home.cap.exec.p": "AaronCore holds memory, carries task state, calls tools, and keeps going until the work is actually done — with a verifiable trail.",
    "home.cap.memory.h": "Recall that shapes execution",
    "home.cap.memory.p": "Memory exists to make the next action sharper — not to sprinkle personalization over a reset loop.",
    "home.cap.route.h": "Capabilities routed by context",
    "home.cap.route.p": "The runtime activates the right surface at the right time — without noisy keyword theatrics.",
    "home.cap.repair.h": "Correct through evidence, not prettier retries",
    "home.cap.repair.p": "When something slips, the loop narrows the failure, repairs the path, and verifies again.",

    "home.signal.h": "A memory proof",
    "home.signal.p": "These features are implemented in the stack already. The point is not bigger storage. The point is better conversation.",

    "home.use.h": "Who AaronCore is for",
    "home.use.p": "AaronCore is for people who want AI to carry real work across sessions instead of resetting at every prompt.",
    "home.use.b1": "Plan development work, connect tools, and keep execution moving",
    "home.use.b2": "Organize materials, shape scripts, and carry a production flow",
    "home.use.b3": "Remember habits, follow tasks, and cut repetitive overhead",
    "home.use.b4": "Push AI from sounding smart toward doing real work",

    "home.diff.h": "What makes the memory feel stronger",
    "home.diff.p": "AaronCore is built around memory the user can actually feel: natural flashback, time recall, and cleaner long-term continuity.",
    "home.diff.c1": "Old threads can come back like memory, not search results",
    "home.diff.c2": "You can ask what you talked about today, yesterday, or last week",
    "home.diff.c3": "Noise is filtered so continuity stays sharp instead of bloated",

    "home.trust.h": "Transparent by design",
    "home.trust.p": "AaronCore is built to make the path from request to result understandable, reviewable, and dependable.",
    "home.trust.i1.h": "Traceable steps",
    "home.trust.i1.p": "The path from request to execution stays visible.",
    "home.trust.i2.h": "Verifiable results",
    "home.trust.i2.p": "The runtime shows what changed and why it counts as done.",
    "home.trust.i3.h": "Controlled memory writes",
    "home.trust.i3.p": "Memory stays deliberate instead of mysterious.",
    "home.trust.i4.h": "Extendable boundaries",
    "home.trust.i4.p": "The system makes clear what it can do now and what can expand later.",

    "home.docs.h": "Go deeper when you want the runtime model, memory system, and execution details",
    "home.cta.h": "If you want AI that remembers, start here",
    "home.cta.p": "AaronCore is being built around one promise: conversations should accumulate, return, and feel personal without turning into memory sludge.",
    "product.title": "Memory that comes back when it matters",
    "product.subtitle": "AaronCore turns memory into a live part of conversation and work: recall, continuity, persona, and a clearer path to action.",
    "product.card.continuity.h": "Flashback can feel natural",
    "product.card.continuity.p": "When the current state resonates with an older thread, AaronCore can bring it back without making the user restate everything.",
    "product.card.tools.h": "You can ask for time recall",
    "product.card.tools.p": "It can answer questions like what you talked about today, yesterday, or last week using history plus relevant memory snippets.",
    "product.card.verify.h": "It remembers how to talk to you",
    "product.card.verify.p": "Preferences, dislikes, relationship posture, and interaction rules are condensed back into the reply path.",
    "product.card.repair.h": "Memory stays sharp, not bloated",
    "product.card.repair.p": "Low-signal turns, think blocks, and polluted context are filtered so continuity gets cleaner over time.",
    "product.proof.h": "What memory looks like in practice",
    "product.proof.p": "The memory system is not just storage. It comes back into the reply as flashback, recap, and persona continuity.",
    "product.proof.side.h": "Designed to feel remembered, not artificially stuffed",
    "product.proof.side.p": "The goal is not to dump a search result into chat. The goal is to bring back the right memory at the right moment, naturally.",

    "docs.title": "A map to the memory system",
    "docs.subtitle": "Start with how memory shows up in practice: recall, continuity, persona, hygiene, and boundaries.",
    "docs.terms.h": "Core terms",
    "docs.terms.p": "Flashback = old-thread resonance. Recall = summarize conversation by time. Persona = preferences, relationship, and style continuity. Hygiene = filter noisy memory before it sticks.",
    "docs.card.overview.h": "What the memory system is",
    "docs.card.overview.p": "A layered memory stack that writes, filters, recalls, and reinjects memory back into conversation.",
    "docs.card.memory.h": "Flashback",
    "docs.card.memory.p": "Old repair threads, emotional cues, or project states can resurface as natural hints instead of keyword dumps.",
    "docs.card.exec.h": "Time recall",
    "docs.card.exec.p": "Ask what you talked about today, yesterday, or last week and get a recap from chat history plus memory snippets.",
    "docs.card.tools.h": "Persona continuity",
    "docs.card.tools.p": "Preferences, dislikes, city, relationship posture, and interaction rules feed back into how AaronCore replies.",
    "docs.card.verify.h": "Memory hygiene",
    "docs.card.verify.p": "Think blocks, low-signal turns, and polluted context are filtered so long-term continuity stays cleaner.",
    "docs.card.repair.h": "Retrieval posture",
    "docs.card.repair.p": "Flashback is driven by resonance and continuity, not just plain keyword hits.",
    "docs.card.bounds.h": "Boundaries",
    "docs.card.bounds.p": "The memory layers stay split by role so facts, experiences, rules, and knowledge do not collapse into one bucket.",
    "docs.card.release.h": "Beta + download",
    "docs.card.release.p": "Public builds attach when ready. Until then, GitHub is the honest path.",
    "docs.deep.h": "Want the deeper architecture write-up?",
    "docs.deep.p": "The public docs can expand later. This page is the short map to the memory features users actually feel.",

    "changelog.title": "What changed (public surface)",
    "changelog.subtitle": "A lightweight timeline for the official site and early milestones. Honest beats hype.",
    "changelog.r1.h": "Multi-page IA + calmer narrative",
    "changelog.r1.p": "Split Home / Product / Docs / Changelog, tightened copy toward continuity + verification, and reduced “demo UI” noise on the homepage.",
    "changelog.r2.h": "Official landing refresh",
    "changelog.r2.p": "Expanded the landing narrative with stronger sections for capabilities, proof, trust, and release posture.",
    "changelog.r3.h": "Public beta build",
    "changelog.r3.p": "Not attached yet. The honest default: GitHub-first early access until downloads are wired.",

    "lang.button": "Lang",
    "lang.en": "English",
    "lang.zh": "中文",
    "lang.ja": "日本語",
    "lang.ko": "한국어"
  },
  zh: {
    "brand.subline": "让 AI 真正记住你",
    "nav.home": "首页",
    "nav.product": "产品",
    "nav.docs": "文档",
    "nav.changelog": "更新",
    "cta.joinBeta": "加入内测",
    "cta.earlyAccess": "加入内测",
    "cta.seeProof": "查看产品证明",
    "hero.h1Line1": "真正的核心",
    "hero.h1Line2": "从记忆",
    "hero.h1Line3": "开始",
    "hero.title": "当 AI 记得你，后面的延续都会变得自然。",
    "hero.subtitle": "关系感、上下文、任务状态，不该每一轮都被清空。",
    "hero.lede": "AaronCore 不把记忆当成一个孤立功能，而是把它变成理解、延续与行动的起点。",
    "hero.note": "记忆 · 延续 · 行动",
    "home.stage.kicker": "桌面运行时",
    "home.stage.h": "把记忆、工具、任务状态和验证收进同一条桌面链路。",
    "home.stage.p": "AaronCore 让上下文持续在线，在同一轮里决定下一步、调用工具、跟踪进度，并留下真正可检查的结果。",
    "home.panel.exec.label": "它实际在做什么",
    "home.panel.exec.h": "这个运行时能挂住上下文、调起工具，并且不断线地往前推进。",
    "home.panel.exec.p": "任务状态、路由结果和工具输出会一起挂着，不会做一步丢一步。",
    "home.panel.posture.label": "为什么这很重要",
    "home.panel.posture.h": "延续感会真正变成推进力",
    "home.panel.posture.p": "记忆之所以有价值，是因为它始终连着执行、验证和当前桌面会话。",
    "home.rail.1.h": "锚定当前",
    "home.rail.1.p": "装入当前上下文、任务状态和用户意图",
    "home.rail.2.h": "路由",
    "home.rail.2.p": "激活当前最合适的能力面：聊天、工具、回忆或验证",
    "home.rail.3.h": "执行",
    "home.rail.3.p": "在同一运行时里调用工具，把任务往前推",
    "home.rail.4.h": "验证",
    "home.rail.4.p": "检查结果，并留下真正发生了什么的轨迹",

    "home.how.h": "为什么聊起来不一样",
    "home.how.p": "AaronCore 不是单纯塞更多上下文，而是把记忆分层、过滤噪音，再在合适的时候把合适的记忆送回回复里。",
    "home.how.step1.h": "闪回是自然的",
    "home.how.step1.p": "旧线程靠状态共振回来，不是粗暴关键词拼接",
    "home.how.step2.h": "时间回忆是内建的",
    "home.how.step2.p": "你可以直接问今天、昨天、上周聊了什么",
    "home.how.step3.h": "人格会持续出现",
    "home.how.step3.p": "偏好、反感、城市、关系和规则都会重新影响回复",
    "home.how.step4.h": "记忆是干净的",
    "home.how.step4.p": "低信号对话和污染上下文会在写入前被过滤",

    "home.cap.h": "为执行而生，而不只是回答",
    "home.cap.p": "记忆、执行、路由与验证收在同一个运行时里，专为把工作推进而设计。",
    "home.cap.exec.h": "重点不是答得漂亮，而是把事推进。",
    "home.cap.exec.p": "AaronCore 记得住、扛得起任务状态、能调用工具，并一直走到真正完成——而且留有可验证的轨迹。",
    "home.cap.memory.h": "会影响执行的回忆",
    "home.cap.memory.p": "记忆是为了让下一步更锋利，而不是给“每次重来”的循环撒点个性化。",
    "home.cap.route.h": "按上下文激活能力",
    "home.cap.route.p": "运行时在对的时候启用对的能力，而不是靠噪音关键词演戏。",
    "home.cap.repair.h": "用证据纠正，而不是更好看的重试",
    "home.cap.repair.p": "一旦偏差出现，闭环会收窄失败、修复路径、再验证。",

    "home.signal.h": "一个记忆证明",
    "home.signal.p": "这些不是想象中的功能，而是已经接进系统里的能力。重点不是存得更多，而是聊得更像记得你。",

    "home.use.h": "AaronCore 适合谁",
    "home.use.p": "适合希望 AI 把真实工作跨会话扛起来的人，而不是每次 prompt 都从零开始。",
    "home.use.b1": "规划开发工作，连接工具，让执行持续推进",
    "home.use.b2": "整理素材、打磨脚本，承载内容生产流",
    "home.use.b3": "记住习惯、跟进任务，减少重复开销",
    "home.use.b4": "把 AI 从“像很聪明”推向“真的在做事”",

    "home.diff.h": "为什么这套记忆更有感觉",
    "home.diff.p": "AaronCore 做的是用户真的能感知到的记忆：自然闪回、按时间回忆，以及更干净的长期连续性。",
    "home.diff.c1": "旧话题回来时更像想起一段经历，而不是贴一条搜索结果",
    "home.diff.c2": "你可以直接问今天、昨天、上周聊过什么",
    "home.diff.c3": "噪音会被过滤，连续性越用越清晰，而不是越用越糊",

    "home.trust.h": "透明是默认",
    "home.trust.p": "AaronCore 让从请求到结果的路径可理解、可复核、可信赖。",
    "home.trust.i1.h": "步骤可追踪",
    "home.trust.i1.p": "从请求到执行的路径始终可见。",
    "home.trust.i2.h": "结果可验证",
    "home.trust.i2.p": "运行时会展示改了什么，以及为什么算完成。",
    "home.trust.i3.h": "记忆写入可控",
    "home.trust.i3.p": "记忆是有意的，不是神秘的。",
    "home.trust.i4.h": "边界可扩展",
    "home.trust.i4.p": "清楚说明现在能做什么、以后能扩到哪里。",

    "home.docs.h": "当你想看运行时模型、记忆系统与执行细节时，再深入",
    "home.cta.h": "如果你想要一个真的会记住你的 AI，就从这里开始",
    "home.cta.p": "AaronCore 想做的是一件事：让对话能积累、能回来、能越来越像认识你，而不是最后变成一锅记忆糊。",
    "product.title": "会在需要时想起你的记忆",
    "product.subtitle": "AaronCore 让记忆真正参与对话：记忆闪回、时间回忆、人格连续性，以及记忆卫生。",
    "product.card.continuity.h": "闪回可以很自然",
    "product.card.continuity.p": "当当前状态和旧线程产生共振时，AaronCore 会把它自然带回来，而不是让用户把前情重讲一遍。",
    "product.card.tools.h": "你可以直接让它按时间回忆",
    "product.card.tools.p": "像“我们今天聊了什么”“昨天说到哪了”“上周讨论过什么”这类问题，它会用历史记录加相关记忆片段来回答。",
    "product.card.verify.h": "它记得该怎么和你说话",
    "product.card.verify.p": "偏好、反感、关系姿态和交互规则会被压回回复链路，聊天不会每轮都陌生。",
    "product.card.repair.h": "记忆会越来越锋利，不会越积越脏",
    "product.card.repair.p": "低信号对话、think 污染和脏上下文会被过滤掉，让连续性保持清爽。",
    "product.proof.h": "记忆在真实对话里长什么样",
    "product.proof.p": "这套记忆不是存档柜，而是会作为闪回、回顾和人格连续性重新进入回复。",
    "product.proof.side.h": "目标是被记住，不是被硬塞满",
    "product.proof.side.p": "重点不是把检索结果生硬塞进聊天，而是在对的时候自然把对的记忆带回来。",

    "docs.title": "记忆系统地图",
    "docs.subtitle": "先看用户能直接感知到的部分：记忆闪回、时间回忆、人格连续性和记忆卫生。",
    "docs.terms.h": "核心术语",
    "docs.terms.p": "Flashback=旧线程共振联想；Recall=按时间总结对话；Persona=偏好、关系与说话风格连续；Hygiene=在写入前过滤脏记忆。",
    "docs.card.overview.h": "这套记忆系统是什么",
    "docs.card.overview.p": "一个分层记忆系统：会写入、过滤、召回，并把记忆重新送回对话。",
    "docs.card.memory.h": "记忆闪回",
    "docs.card.memory.p": "旧的修复线程、情绪线索或项目状态会自然浮上来，而不是变成关键词命中清单。",
    "docs.card.exec.h": "时间回忆",
    "docs.card.exec.p": "你可以直接问今天、昨天或上周聊过什么，它会结合聊天历史和相关记忆片段来回顾。",
    "docs.card.tools.h": "人格连续性",
    "docs.card.tools.p": "偏好、反感、城市、关系姿态和交互规则会重新影响 AaronCore 的回复方式。",
    "docs.card.verify.h": "记忆卫生",
    "docs.card.verify.p": "think 块、低信号对话和污染上下文会被过滤，让长期连续性保持更干净。",
    "docs.card.repair.h": "召回姿态",
    "docs.card.repair.p": "flashback 的主体是状态共振和任务连续性，不是普通关键词检索。",
    "docs.card.bounds.h": "边界",
    "docs.card.bounds.p": "各层记忆职责分开，事实、经历、规则和知识不会混成一个桶。",
    "docs.card.release.h": "内测与下载",
    "docs.card.release.p": "公开构建准备好才挂。现在的诚实路径是邮箱内测。",
    "docs.deep.h": "想看更深的架构写法？",
    "docs.deep.p": "公开文档以后可以继续展开，这里先做一张用户能快速理解的记忆地图。",

    "changelog.title": "更新记录（对外表面）",
    "changelog.subtitle": "官网与里程碑的轻量时间线。诚实胜过夸张。",
    "changelog.r1.h": "四页架构 + 更冷静叙事",
    "changelog.r1.p": "拆分 Home/Product/Docs/Changelog，文案聚焦连续性与可验证，并降低首页“演示 UI”噪音。",
    "changelog.r2.h": "官网基础版落地",
    "changelog.r2.p": "补齐能力、证明、信任与发布姿态的基本结构。",
    "changelog.r3.h": "公开内测构建",
    "changelog.r3.p": "暂未挂载。默认走邮箱内测，下载链路准备好再公开。",

    "lang.button": "语言",
    "lang.en": "English",
    "lang.zh": "中文",
    "lang.ja": "日本語",
    "lang.ko": "한국어"
  },
  ja: {
    "brand.subline": "Memory that comes back naturally",
    "nav.home": "ホーム",
    "nav.product": "製品",
    "nav.docs": "ドキュメント",
    "nav.changelog": "更新履歴",
    "cta.joinBeta": "ベータに参加",
    "cta.earlyAccess": "ベータに参加",
    "cta.seeProof": "プロダクトの証拠を見る",
    "hero.h1Line1": "本当のコアは",
    "hero.h1Line2": "記憶から",
    "hero.h1Line3": "始まる。",
    "hero.title": "When AI remembers you, everything that follows can continue naturally.",
    "hero.subtitle": "Familiarity, context, and task state should not be wiped clean every turn.",
    "hero.lede": "AaronCore does not treat memory as a standalone feature. It turns memory into the starting point for understanding, continuity, and action.",
    "hero.note": "Memory · Continuity · Action",
    "home.stage.kicker": "Memory runtime",
    "home.stage.h": "Memory that shows up in conversation, not just in storage.",
    "home.stage.p": "AaronCore can surface old threads as natural flashbacks, answer what you talked about today, and keep preferences in the loop.",
    "home.panel.exec.label": "What you feel",
    "home.panel.exec.h": "The assistant can naturally pick up old threads without making you repeat yourself.",
    "home.panel.exec.p": "Flashback hints, time recall, and persona memory all feed back into the reply.",
    "home.panel.posture.label": "Why it lands",
    "home.panel.posture.h": "Chat feels remembered, not restarted",
    "home.panel.posture.p": "Preferences, relationship tone, and ongoing work stay attached instead of resetting every session.",
    "home.rail.1.h": "Remember",
    "home.rail.1.p": "keep preferences, rules, and relationship posture attached",
    "home.rail.2.h": "Flash back",
    "home.rail.2.p": "surface old threads through state resonance",
    "home.rail.3.h": "Recall",
    "home.rail.3.p": "answer what you talked about today, yesterday, or last week",
    "home.rail.4.h": "Stay consistent",
    "home.rail.4.p": "keep tone and continuity steady across turns",
    "home.how.h": "Why the conversations feel different",
    "home.how.p": "AaronCore separates memory into layers, filters noise, and feeds the right memory back at the right moment.",
    "home.how.step1.h": "Flashback feels natural",
    "home.how.step1.p": "old threads resurface through state resonance, not crude keyword spam",
    "home.how.step2.h": "Time recall is built in",
    "home.how.step2.p": "you can ask what you talked about today, yesterday, or last week",
    "home.how.step3.h": "Persona keeps showing up",
    "home.how.step3.p": "preferences, dislikes, city, relationship, and rules feed back into replies",
    "home.how.step4.h": "Memory stays clean",
    "home.how.step4.p": "low-signal turns and polluted context are filtered before they become memory",
    "home.cap.h": "Built for execution, not just answers",
    "home.cap.p": "Memory, execution, routing, and verification live inside one runtime designed to move work forward.",
    "home.cap.exec.h": "The point is not to answer beautifully. The point is to move the work.",
    "home.cap.exec.p": "AaronCore holds memory, carries task state, calls tools, and keeps going until the work is actually done — with a verifiable trail.",
    "home.cap.memory.h": "Recall that shapes execution",
    "home.cap.memory.p": "Memory exists to make the next action sharper — not to sprinkle personalization over a reset loop.",
    "home.cap.route.h": "Capabilities routed by context",
    "home.cap.route.p": "The runtime activates the right surface at the right time — without noisy keyword theatrics.",
    "home.cap.repair.h": "Correct through evidence, not prettier retries",
    "home.cap.repair.p": "When something slips, the loop narrows the failure, repairs the path, and verifies again.",
    "home.signal.h": "A memory proof",
    "home.signal.p": "These features are already implemented. The point is not bigger storage. The point is better conversation.",
    "home.use.h": "Who AaronCore is for",
    "home.use.p": "For people who want AI to carry real work across sessions instead of resetting at every prompt.",
    "home.use.b1": "Plan development work, connect tools, and keep execution moving",
    "home.use.b2": "Organize materials, shape scripts, and carry a production flow",
    "home.use.b3": "Remember habits, follow tasks, and cut repetitive overhead",
    "home.use.b4": "Push AI from sounding smart toward doing real work",
    "home.diff.h": "What makes the memory feel stronger",
    "home.diff.p": "AaronCore is built around memory the user can actually feel: natural flashback, time recall, and cleaner long-term continuity.",
    "home.diff.c1": "Old threads can come back like memory, not search results",
    "home.diff.c2": "You can ask what you talked about today, yesterday, or last week",
    "home.diff.c3": "Noise is filtered so continuity stays sharp instead of bloated",
    "home.trust.h": "Transparent by design",
    "home.trust.p": "Make the path from request to result understandable, reviewable, and dependable.",
    "home.trust.i1.h": "Traceable steps",
    "home.trust.i1.p": "The path from request to execution stays visible.",
    "home.trust.i2.h": "Verifiable results",
    "home.trust.i2.p": "Shows what changed and why it counts as done.",
    "home.trust.i3.h": "Controlled memory writes",
    "home.trust.i3.p": "Memory stays deliberate instead of mysterious.",
    "home.trust.i4.h": "Extendable boundaries",
    "home.trust.i4.p": "Clear on what it can do now and what can expand later.",
    "home.docs.h": "Go deeper when you want the runtime model, memory system, and execution details",
    "home.cta.h": "If you want AI that remembers, start here",
    "home.cta.p": "AaronCore is being built around one promise: conversations should accumulate, return, and feel personal without turning into memory sludge.",
    "product.title": "Memory that comes back when it matters",
    "product.subtitle": "AaronCore turns memory into a live part of conversation and work: recall, continuity, persona, and a clearer path to action.",
    "product.card.continuity.h": "Flashback can feel natural",
    "product.card.continuity.p": "When the current state resonates with an older thread, AaronCore can bring it back without making the user restate everything.",
    "product.card.tools.h": "You can ask for time recall",
    "product.card.tools.p": "It can answer questions like what you talked about today, yesterday, or last week using history plus relevant memory snippets.",
    "product.card.verify.h": "It remembers how to talk to you",
    "product.card.verify.p": "Preferences, dislikes, relationship posture, and interaction rules are condensed back into the reply path.",
    "product.card.repair.h": "Memory stays sharp, not bloated",
    "product.card.repair.p": "Low-signal turns, think blocks, and polluted context are filtered so continuity gets cleaner over time.",
    "product.proof.h": "What memory looks like in practice",
    "product.proof.p": "The memory system is not just storage. It comes back into the reply as flashback, recap, and persona continuity.",
    "product.proof.side.h": "Designed to feel remembered, not artificially stuffed",
    "product.proof.side.p": "The goal is to bring back the right memory at the right moment, naturally.",

    "docs.title": "A map to the memory system",
    "docs.subtitle": "Start with how memory shows up in practice: recall, continuity, persona, hygiene, and boundaries.",
    "docs.terms.h": "Core terms",
    "docs.terms.p": "Flashback = old-thread resonance. Recall = summarize conversation by time. Persona = preferences, relationship, and style continuity. Hygiene = filter noisy memory before it sticks.",
    "docs.card.overview.h": "What the memory system is",
    "docs.card.overview.p": "A layered memory stack that writes, filters, recalls, and reinjects memory back into conversation.",
    "docs.card.memory.h": "Flashback",
    "docs.card.memory.p": "Old repair threads, emotional cues, or project states can resurface as natural hints instead of keyword dumps.",
    "docs.card.exec.h": "Time recall",
    "docs.card.exec.p": "Ask what you talked about today, yesterday, or last week and get a recap from chat history plus memory snippets.",
    "docs.card.tools.h": "Persona continuity",
    "docs.card.tools.p": "Preferences, dislikes, city, relationship posture, and interaction rules feed back into how AaronCore replies.",
    "docs.card.verify.h": "Memory hygiene",
    "docs.card.verify.p": "Think blocks, low-signal turns, and polluted context are filtered so long-term continuity stays cleaner.",
    "docs.card.repair.h": "Retrieval posture",
    "docs.card.repair.p": "Flashback is driven by resonance and continuity, not just plain keyword hits.",
    "docs.card.bounds.h": "境界",
    "docs.card.bounds.p": "The memory layers stay split by role so facts, experiences, rules, and knowledge do not collapse into one bucket.",
    "docs.card.release.h": "ベータとダウンロード",
    "docs.card.release.p": "公開ビルドは準備が整ってから。今はメールボックスが正直な導線。",
    "docs.deep.h": "Want the deeper architecture write-up?",
    "docs.deep.p": "The public docs can expand later. This page is the short map to the memory features users actually feel.",

    "changelog.title": "変更履歴（公開面）",
    "changelog.subtitle": "公式サイトと初期マイルストーンの軽量タイムライン。誇張より誠実。",
    "changelog.r1.h": "4ページ構成 + 落ち着いた叙事",
    "changelog.r1.p": "Home/Product/Docs/Changelog に分割し、継続性と検証に焦点を合わせ、ホームのデモ感を抑制。",
    "changelog.r2.h": "公式ランディング整備",
    "changelog.r2.p": "能力、証拠、信頼、リリース姿勢の基本セクションを追加。",
    "changelog.r3.h": "公開ベータビルド",
    "changelog.r3.p": "まだ未添付。整うまでメール導線を維持。",

    "lang.button": "言語",
    "lang.en": "English",
    "lang.zh": "中文",
    "lang.ja": "日本語",
    "lang.ko": "한국어"
  },
  ko: {
    "brand.subline": "Memory that comes back naturally",
    "nav.home": "홈",
    "nav.product": "제품",
    "nav.docs": "문서",
    "nav.changelog": "업데이트",
    "cta.joinBeta": "베타 참여",
    "cta.earlyAccess": "베타 참여",
    "cta.seeProof": "제품 증거 보기",
    "hero.h1Line1": "진짜 코어는",
    "hero.h1Line2": "기억에서",
    "hero.h1Line3": "시작된다.",
    "hero.title": "When AI remembers you, everything that follows can continue naturally.",
    "hero.subtitle": "Familiarity, context, and task state should not be wiped clean every turn.",
    "hero.lede": "AaronCore does not treat memory as a standalone feature. It turns memory into the starting point for understanding, continuity, and action.",
    "hero.note": "Memory · Continuity · Action",
    "home.stage.kicker": "Memory runtime",
    "home.stage.h": "Memory that shows up in conversation, not just in storage.",
    "home.stage.p": "AaronCore can surface old threads as natural flashbacks, answer what you talked about today, and keep preferences in the loop.",
    "home.panel.exec.label": "What you feel",
    "home.panel.exec.h": "The assistant can naturally pick up old threads without making you repeat yourself.",
    "home.panel.exec.p": "Flashback hints, time recall, and persona memory all feed back into the reply.",
    "home.panel.posture.label": "Why it lands",
    "home.panel.posture.h": "Chat feels remembered, not restarted",
    "home.panel.posture.p": "Preferences, relationship tone, and ongoing work stay attached instead of resetting every session.",
    "home.rail.1.h": "Remember",
    "home.rail.1.p": "keep preferences, rules, and relationship posture attached",
    "home.rail.2.h": "Flash back",
    "home.rail.2.p": "surface old threads through state resonance",
    "home.rail.3.h": "Recall",
    "home.rail.3.p": "answer what you talked about today, yesterday, or last week",
    "home.rail.4.h": "Stay consistent",
    "home.rail.4.p": "keep tone and continuity steady across turns",
    "home.how.h": "Why the conversations feel different",
    "home.how.p": "AaronCore separates memory into layers, filters noise, and feeds the right memory back at the right moment.",
    "home.how.step1.h": "Flashback feels natural",
    "home.how.step1.p": "old threads resurface through state resonance, not crude keyword spam",
    "home.how.step2.h": "Time recall is built in",
    "home.how.step2.p": "you can ask what you talked about today, yesterday, or last week",
    "home.how.step3.h": "Persona keeps showing up",
    "home.how.step3.p": "preferences, dislikes, city, relationship, and rules feed back into replies",
    "home.how.step4.h": "Memory stays clean",
    "home.how.step4.p": "low-signal turns and polluted context are filtered before they become memory",
    "home.cap.h": "Built for execution, not just answers",
    "home.cap.p": "Memory, execution, routing, and verification live inside one runtime designed to move work forward.",
    "home.cap.exec.h": "Not beautiful answers. Forward progress.",
    "home.cap.exec.p": "AaronCore carries memory and task state, calls tools, and keeps going until the work is done — with a verifiable trail.",
    "home.cap.memory.h": "Recall that shapes execution",
    "home.cap.memory.p": "Memory makes the next action sharper — not personalization on a reset loop.",
    "home.cap.route.h": "Capabilities routed by context",
    "home.cap.route.p": "Activate the right surface at the right time — without noisy keyword theatrics.",
    "home.cap.repair.h": "Correct through evidence",
    "home.cap.repair.p": "Narrow failures, repair the path, and verify again.",
    "home.signal.h": "A memory proof",
    "home.signal.p": "These features are already implemented. The point is not bigger storage. The point is better conversation.",
    "home.use.h": "Who AaronCore is for",
    "home.use.p": "For people who want AI to carry real work across sessions instead of resetting at every prompt.",
    "home.use.b1": "Plan development work, connect tools, and keep execution moving",
    "home.use.b2": "Organize materials, shape scripts, and carry a production flow",
    "home.use.b3": "Remember habits, follow tasks, and cut repetitive overhead",
    "home.use.b4": "Push AI from sounding smart toward doing real work",
    "home.diff.h": "What makes the memory feel stronger",
    "home.diff.p": "AaronCore is built around memory the user can actually feel: natural flashback, time recall, and cleaner long-term continuity.",
    "home.diff.c1": "Old threads can come back like memory, not search results",
    "home.diff.c2": "You can ask what you talked about today, yesterday, or last week",
    "home.diff.c3": "Noise is filtered so continuity stays sharp instead of bloated",
    "home.trust.h": "Transparent by design",
    "home.trust.p": "Make the path from request to result understandable, reviewable, and dependable.",
    "home.trust.i1.h": "Traceable steps",
    "home.trust.i1.p": "The path from request to execution stays visible.",
    "home.trust.i2.h": "Verifiable results",
    "home.trust.i2.p": "Shows what changed and why it counts as done.",
    "home.trust.i3.h": "Controlled memory writes",
    "home.trust.i3.p": "Memory stays deliberate instead of mysterious.",
    "home.trust.i4.h": "Extendable boundaries",
    "home.trust.i4.p": "Clear on what it can do now and what can expand later.",
    "home.docs.h": "Go deeper when you want the runtime model, memory system, and execution details",
    "home.cta.h": "If you want AI that remembers, start here",
    "home.cta.p": "AaronCore is being built around one promise: conversations should accumulate, return, and feel personal without turning into memory sludge.",
    "product.title": "Memory that comes back when it matters",
    "product.subtitle": "AaronCore turns memory into a live part of conversation and work: recall, continuity, persona, and a clearer path to action.",
    "product.card.continuity.h": "Flashback can feel natural",
    "product.card.continuity.p": "When the current state resonates with an older thread, AaronCore can bring it back without making the user restate everything.",
    "product.card.tools.h": "You can ask for time recall",
    "product.card.tools.p": "It can answer questions like what you talked about today, yesterday, or last week using history plus relevant memory snippets.",
    "product.card.verify.h": "It remembers how to talk to you",
    "product.card.verify.p": "Preferences, dislikes, relationship posture, and interaction rules are condensed back into the reply path.",
    "product.card.repair.h": "Memory stays sharp, not bloated",
    "product.card.repair.p": "Low-signal turns, think blocks, and polluted context are filtered so continuity gets cleaner over time.",
    "product.proof.h": "What memory looks like in practice",
    "product.proof.p": "The memory system is not just storage. It comes back into the reply as flashback, recap, and persona continuity.",
    "product.proof.side.h": "Designed to feel remembered, not artificially stuffed",
    "product.proof.side.p": "The goal is to bring back the right memory at the right moment, naturally.",

    "docs.title": "A map to the memory system",
    "docs.subtitle": "Start with how memory shows up in practice: recall, continuity, persona, hygiene, and boundaries.",
    "docs.terms.h": "Core terms",
    "docs.terms.p": "Flashback = old-thread resonance. Recall = summarize conversation by time. Persona = preferences, relationship, and style continuity. Hygiene = filter noisy memory before it sticks.",
    "docs.card.overview.h": "What the memory system is",
    "docs.card.overview.p": "A layered memory stack that writes, filters, recalls, and reinjects memory back into conversation.",
    "docs.card.memory.h": "Flashback",
    "docs.card.memory.p": "Old repair threads, emotional cues, or project states can resurface as natural hints instead of keyword dumps.",
    "docs.card.exec.h": "Time recall",
    "docs.card.exec.p": "Ask what you talked about today, yesterday, or last week and get a recap from chat history plus memory snippets.",
    "docs.card.tools.h": "Persona continuity",
    "docs.card.tools.p": "Preferences, dislikes, city, relationship posture, and interaction rules feed back into how AaronCore replies.",
    "docs.card.verify.h": "Memory hygiene",
    "docs.card.verify.p": "Think blocks, low-signal turns, and polluted context are filtered so long-term continuity stays cleaner.",
    "docs.card.repair.h": "Retrieval posture",
    "docs.card.repair.p": "Flashback is driven by resonance and continuity, not just plain keyword hits.",
    "docs.card.bounds.h": "경계",
    "docs.card.bounds.p": "The memory layers stay split by role so facts, experiences, rules, and knowledge do not collapse into one bucket.",
    "docs.card.release.h": "베타와 다운로드",
    "docs.card.release.p": "공개 빌드는 준비되면 연결합니다. 그전엔 메일 베타가 정직한 경로입니다.",
    "docs.deep.h": "Want the deeper architecture write-up?",
    "docs.deep.p": "The public docs can expand later. This page is the short map to the memory features users actually feel.",

    "changelog.title": "변경 사항(공개 표면)",
    "changelog.subtitle": "공식 사이트와 초기 마일스톤의 가벼운 타임라인. 과장보다 정직.",
    "changelog.r1.h": "4페이지 IA + 차분한 내러티브",
    "changelog.r1.p": "Home/Product/Docs/Changelog로 분리하고 연속성과 검증에 초점을 맞춰 홈의 데모 느낌을 줄였습니다.",
    "changelog.r2.h": "공식 랜딩 정리",
    "changelog.r2.p": "능력, 증거, 신뢰, 릴리즈 자세 섹션을 보강했습니다.",
    "changelog.r3.h": "공개 베타 빌드",
    "changelog.r3.p": "아직 미연결. 준비될 때까지 메일 경로를 유지합니다.",

    "lang.button": "언어",
    "lang.en": "English",
    "lang.zh": "中文",
    "lang.ja": "日本語",
    "lang.ko": "한국어"
  }
};

function getLang() {
  try {
    const saved = String(window.localStorage.getItem(LANG_STORAGE_KEY) || "").trim().toLowerCase();
    if (LANGS.includes(saved)) return saved;
  } catch {}
  const nav = (navigator.language || "en").toLowerCase();
  if (nav.startsWith("zh")) return "zh";
  if (nav.startsWith("ja")) return "ja";
  if (nav.startsWith("ko")) return "ko";
  return "en";
}

function setLang(lang) {
  const l = LANGS.includes(lang) ? lang : "en";
  try { window.localStorage.setItem(LANG_STORAGE_KEY, l); } catch {}
  applyI18n(l);
}

function t(key, lang) {
  const l = LANGS.includes(lang) ? lang : getLang();
  return (I18N[l] && I18N[l][key]) || (I18N.en && I18N.en[key]) || "";
}

function applyI18n(lang) {
  const l = LANGS.includes(lang) ? lang : getLang();
  document.documentElement.setAttribute("lang", l === "zh" ? "zh-CN" : l);
  const nodes = Array.from(document.querySelectorAll("[data-i18n]"));
  nodes.forEach((node) => {
    const key = String(node.getAttribute("data-i18n") || "").trim();
    if (!key) return;
    const value = t(key, l);
    if (value) node.textContent = value;
  });
  // site fields that used to be injected
  setField("site", "brandSubline", t("brand.subline", l));

  const btn = document.getElementById("langBtn");
  if (btn) btn.textContent = l.toUpperCase();
}

function initLangSwitch() {
  const root = document.getElementById("langSwitch");
  const btn = document.getElementById("langBtn");
  const menu = document.getElementById("langMenu");
  if (!root || !btn || !menu) return;

  const close = () => root.classList.remove("open");
  const toggle = () => root.classList.toggle("open");

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggle();
  });

  document.addEventListener("click", close);
  menu.addEventListener("click", (e) => {
    const target = e.target && e.target.closest ? e.target.closest("[data-lang]") : null;
    if (!target) return;
    e.preventDefault();
    const lang = String(target.getAttribute("data-lang") || "").trim().toLowerCase();
    close();
    setLang(lang);
  });

  applyI18n(getLang());
}

function initTopNavActiveState() {
  const page = String(document.body?.dataset?.page || "").trim();
  if (!page) {
    return;
  }

  const links = Array.from(document.querySelectorAll(".topnav a"));
  links.forEach((node) => node.classList.remove("is-active"));

  const map = {
    home: "./index.html",
    product: "./product.html",
    docs: "./docs.html",
    changelog: "./changelog.html"
  };

  const target = map[page];
  if (!target) {
    return;
  }

  const match = links.find((node) => {
    const href = String(node.getAttribute("href") || "");
    return href === target;
  });

  if (match) {
    match.classList.add("is-active");
  }
}

function applyReleaseState() {
  const downloadBtn = document.getElementById("downloadBtn");
  const note = document.getElementById("downloadNote");

  setField("release", "version", releaseConfig.version);

  if (!downloadBtn || !note) {
    return;
  }

  if (releaseConfig.available && releaseConfig.url) {
    downloadBtn.textContent = releaseConfig.label;
    downloadBtn.href = releaseConfig.url;
    downloadBtn.classList.remove("disabled");
    downloadBtn.setAttribute("aria-disabled", "false");
    downloadBtn.setAttribute("target", "_blank");
    downloadBtn.setAttribute("rel", "noreferrer");
    note.textContent = releaseConfig.noteWhenOpen;
    return;
  }

  downloadBtn.textContent = releaseConfig.fallbackLabel;
  downloadBtn.href = "#join-beta";
  downloadBtn.classList.add("disabled");
  downloadBtn.setAttribute("aria-disabled", "true");
  downloadBtn.removeAttribute("target");
  downloadBtn.removeAttribute("rel");
  note.textContent = releaseConfig.noteWhenLocked;
}

function initRevealAnimations() {
  const targets = Array.from(document.querySelectorAll(".reveal"));
  if (!targets.length) {
    return;
  }

  if (!("IntersectionObserver" in window)) {
    targets.forEach((item) => item.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) {
        return;
      }
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.12 });

  targets.forEach((item) => observer.observe(item));
}

function initRuntimeLoop() {
  const steps = Array.from(document.querySelectorAll("[data-runtime-step]"));
  const logs = Array.from(document.querySelectorAll("[data-runtime-log]"));

  if (!steps.length || steps.length !== logs.length) {
    return;
  }

  let activeIndex = 0;

  const paint = () => {
    steps.forEach((node, index) => node.classList.toggle("is-active", index === activeIndex));
    logs.forEach((node, index) => node.classList.toggle("is-active", index === activeIndex));
  };

  paint();

  window.setInterval(() => {
    activeIndex = (activeIndex + 1) % steps.length;
    paint();
  }, 2400);
}

function initProofTabs() {
  const tabs = Array.from(document.querySelectorAll("[data-proof-tab]"));
  const panes = Array.from(document.querySelectorAll("[data-proof-pane]"));

  if (!tabs.length || !panes.length) {
    return;
  }

  let activeName = tabs[0].getAttribute("data-proof-tab");
  let autoRotate = true;

  const activate = (name) => {
    activeName = name;
    tabs.forEach((tab) => tab.classList.toggle("is-active", tab.getAttribute("data-proof-tab") === name));
    panes.forEach((pane) => pane.classList.toggle("is-active", pane.getAttribute("data-proof-pane") === name));
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      autoRotate = false;
      activate(tab.getAttribute("data-proof-tab"));
    });
  });

  activate(activeName);

  window.setInterval(() => {
    if (!autoRotate) {
      return;
    }
    const currentIndex = tabs.findIndex((tab) => tab.getAttribute("data-proof-tab") === activeName);
    const nextIndex = (currentIndex + 1) % tabs.length;
    activate(tabs[nextIndex].getAttribute("data-proof-tab"));
  }, 5200);
}

function initHeroMemoryParticles() {
  const stages = Array.from(document.querySelectorAll("[data-neuron-stage]"));
  if (!stages.length) {
    return;
  }

  const prefersReducedMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const supportsPathMotion =
    typeof window.SVGPathElement !== "undefined" &&
    "getPointAtLength" in window.SVGPathElement.prototype;

  const SVG_NS = "http://www.w3.org/2000/svg";
  const AGENT_X = 660;
  const AGENT_Y = 344;
  const LLM_X = 930;
  const LLM_Y = 316;
  const pt = (x, y) => ({ x, y });
  const RADII = {
    agentCore: 24,
    agentInner: 42,
    agentMid: 72,
    agentPrimary: 112,
    agentField: 148,
    agentFar: 198,
    llmCore: 24,
    llmSat: 42,
    llmOuter: 58
  };
  const polarPoint = (cx, cy, radius, angleDeg) => {
    const angle = (angleDeg * Math.PI) / 180;
    return {
      x: cx + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius
    };
  };
  const branchSpecs = [
    { id: "agent-core-ring", tone: "warm", width: 1.38, kind: "circle", cx: AGENT_X, cy: AGENT_Y, r: RADII.agentCore },
    { id: "agent-inner", tone: "secondary", width: 1.08, kind: "circle", cx: AGENT_X, cy: AGENT_Y, r: RADII.agentInner },
    { id: "agent-mid", tone: "main", width: 1.56, kind: "circle", cx: AGENT_X, cy: AGENT_Y, r: RADII.agentMid },
    { id: "agent-primary", tone: "main", width: 2.04, kind: "circle", cx: AGENT_X, cy: AGENT_Y, r: RADII.agentPrimary },
    { id: "agent-field", tone: "secondary", width: 0.76, kind: "circle", cx: AGENT_X, cy: AGENT_Y, r: RADII.agentField },
    { id: "agent-far", tone: "faint", width: 0.34, kind: "circle", cx: AGENT_X, cy: AGENT_Y, r: RADII.agentFar },
    { id: "llm-core-ring", tone: "secondary", width: 0.94, kind: "circle", cx: LLM_X, cy: LLM_Y, r: RADII.llmCore }
  ];
  const nodeSpecs = [
    { x: AGENT_X, y: AGENT_Y, kind: "agent-core", size: 6.8 },
    {
      x: AGENT_X - 112,
      y: AGENT_Y + 52,
      kind: "spark",
      size: 0.98,
      motion: {
        cx: AGENT_X - 110,
        cy: AGENT_Y + 54,
        radius: 12,
        angleDeg: 148,
        durationMs: 5600,
        delayMs: 240,
        radiusWobble: 1.8,
        wobbleMs: 2200,
        reverse: true
      }
    },
    {
      x: AGENT_X + 142,
      y: AGENT_Y - 84,
      kind: "satellite",
      size: 1.96,
      motion: {
        cx: AGENT_X + 138,
        cy: AGENT_Y - 86,
        radius: 14,
        angleDeg: 308,
        durationMs: 6400,
        delayMs: 1100,
        radiusWobble: 1.6,
        wobbleMs: 2600
      }
    },
    {
      x: AGENT_X + 176,
      y: AGENT_Y + 74,
      kind: "warm",
      size: 1.88,
      motion: {
        cx: AGENT_X + 172,
        cy: AGENT_Y + 72,
        radius: 16,
        angleDeg: 36,
        durationMs: 5200,
        delayMs: 1820,
        radiusWobble: 2.2,
        wobbleMs: 2400
      }
    },
    {
      x: AGENT_X - 18,
      y: AGENT_Y - 138,
      kind: "spark",
      size: 0.92,
      motion: {
        cx: AGENT_X - 20,
        cy: AGENT_Y - 136,
        radius: 11,
        angleDeg: 254,
        durationMs: 6000,
        delayMs: 760,
        radiusWobble: 1.4,
        wobbleMs: 2000,
        reverse: true
      }
    },
    {
      x: LLM_X - 54,
      y: LLM_Y - 72,
      kind: "satellite",
      size: 2.02,
      motion: {
        cx: LLM_X - 56,
        cy: LLM_Y - 70,
        radius: 16,
        angleDeg: 228,
        durationMs: 5600,
        delayMs: 800,
        radiusWobble: 2.2,
        wobbleMs: 2200,
        reverse: true
      }
    },
    {
      x: LLM_X + 46,
      y: LLM_Y + 24,
      kind: "spark",
      size: 0.94,
      motion: {
        cx: LLM_X + 42,
        cy: LLM_Y + 22,
        radius: 20,
        angleDeg: 18,
        durationMs: 3600,
        delayMs: 1600,
        radiusWobble: 3.2,
        wobbleMs: 1800
      }
    }
  ];
  const pulseSpecs = [];
  const orbiterSpecs = [
    { branchId: "agent-inner", tone: "cool", size: 1.74, glowSize: 3.8, durationMs: 7200, delayMs: 900 },
    { branchId: "agent-mid", tone: "warm", size: 2.18, glowSize: 4.9, durationMs: 9800, delayMs: 1400 },
    { branchId: "agent-primary", tone: "cool", size: 2.34, glowSize: 5.3, durationMs: 13200, delayMs: 5200, reverse: true },
    { branchId: "agent-field", tone: "cool", size: 1.72, glowSize: 3.9, durationMs: 18600, delayMs: 8600 },
    { branchId: "llm-core-ring", tone: "cool", size: 1.28, glowSize: 2.8, durationMs: 7200, delayMs: 3100 }
  ];

  const createSvgNode = (tagName, attrs = {}) => {
    const node = document.createElementNS(SVG_NS, tagName);
    Object.entries(attrs).forEach(([key, value]) => {
      node.setAttribute(key, String(value));
    });
    return node;
  };

  const clearChildren = (node) => {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  };

  const smoothPath = (points) => {
    if (points.length < 2) {
      return "";
    }
    let d = `M ${points[0].x} ${points[0].y}`;
    if (points.length === 2) {
      return `${d} L ${points[1].x} ${points[1].y}`;
    }
    for (let index = 1; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const midX = (current.x + next.x) / 2;
      const midY = (current.y + next.y) / 2;
      d += ` Q ${current.x} ${current.y} ${midX} ${midY}`;
    }
    const penultimate = points[points.length - 2];
    const last = points[points.length - 1];
    d += ` Q ${penultimate.x} ${penultimate.y} ${last.x} ${last.y}`;
    return d;
  };

  const circlePath = (cx, cy, r) =>
    `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy}`;

  const normalizeAngleDelta = (value) => {
    const twoPi = Math.PI * 2;
    return ((value % twoPi) + twoPi) % twoPi;
  };

  const arcPath = (cx, cy, r, startAngle, endAngle, sweepFlagOverride = null, largeArcFlagOverride = null) => {
    const start = {
      x: cx + (Math.cos(startAngle) * r),
      y: cy + (Math.sin(startAngle) * r)
    };
    const end = {
      x: cx + (Math.cos(endAngle) * r),
      y: cy + (Math.sin(endAngle) * r)
    };
    const clockwiseDelta = normalizeAngleDelta(endAngle - startAngle);
    const counterClockwiseDelta = normalizeAngleDelta(startAngle - endAngle);
    const sweepFlag = sweepFlagOverride === null ? (clockwiseDelta <= counterClockwiseDelta ? 1 : 0) : sweepFlagOverride;
    const travel = sweepFlag === 1 ? clockwiseDelta : counterClockwiseDelta;
    const largeArcFlag = largeArcFlagOverride === null ? (travel > Math.PI ? 1 : 0) : largeArcFlagOverride;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} ${sweepFlag} ${end.x} ${end.y}`;
  };

  const buildBranchPath = (spec) => {
    if (spec.kind === "circle") {
      return circlePath(spec.cx, spec.cy, spec.r);
    }
    if (spec.kind === "arc") {
      return arcPath(spec.cx, spec.cy, spec.r, spec.startAngle, spec.endAngle, spec.sweepFlag, spec.largeArcFlag);
    }
    return smoothPath(spec.points || []);
  };

  const branchStroke = (tone) => {
    if (tone === "warm") {
      return "url(#neuron-branch-warm)";
    }
    if (tone === "secondary") {
      return "url(#neuron-branch-secondary)";
    }
    if (tone === "faint") {
      return "rgba(245, 244, 239, 0.085)";
    }
    return "url(#neuron-branch-main)";
  };

  const branchGlowStroke = (tone) => {
    if (tone === "warm") {
      return "rgba(217, 119, 87, 0.05)";
    }
    if (tone === "secondary") {
      return "rgba(245, 244, 239, 0.055)";
    }
    if (tone === "faint") {
      return "rgba(245, 244, 239, 0.028)";
    }
    return "rgba(245, 244, 239, 0.05)";
  };

  const branchHighlightStroke = (tone) => {
    if (tone === "warm") {
      return "rgba(255, 244, 236, 0.14)";
    }
    return "rgba(245, 244, 239, 0.18)";
  };

  stages.forEach((stage) => {
    const svg = stage.querySelector("[data-neuron-field]");
    const faintLayer = stage.querySelector("[data-neuron-faint]");
    const branchLayer = stage.querySelector("[data-neuron-branches]");
    const nodeLayer = stage.querySelector("[data-neuron-nodes]");
    const pulseLayer = stage.querySelector("[data-neuron-pulses]");

    if (!svg || !faintLayer || !branchLayer || !nodeLayer || !pulseLayer) {
      return;
    }

    clearChildren(faintLayer);
    clearChildren(branchLayer);
    clearChildren(nodeLayer);
    clearChildren(pulseLayer);

    const branchPaths = new Map();
    branchSpecs.forEach((spec) => {
      const layer = spec.tone === "faint" ? faintLayer : branchLayer;
      const d = buildBranchPath(spec);

      const glow = createSvgNode("path", {
        d,
        class: `neuron-trace neuron-trace-glow neuron-trace-${spec.tone}`,
        "data-tone": spec.tone
      });
      glow.setAttribute("stroke", branchGlowStroke(spec.tone));
        glow.setAttribute("stroke-width", (spec.width * (spec.tone === "faint" ? 1.14 : 1.34)).toFixed(2));
      layer.appendChild(glow);

      const main = createSvgNode("path", {
        d,
        id: `neuron-path-${spec.id}`,
        class: `neuron-trace neuron-trace-main neuron-trace-${spec.tone}`,
        "data-tone": spec.tone
      });
      main.setAttribute("stroke", branchStroke(spec.tone));
      main.setAttribute("stroke-width", spec.width.toFixed(2));
      layer.appendChild(main);

      if (spec.tone !== "faint") {
        const highlight = createSvgNode("path", {
          d,
          class: `neuron-trace neuron-trace-highlight neuron-trace-${spec.tone}`,
          "data-tone": spec.tone
        });
        highlight.setAttribute("stroke", branchHighlightStroke(spec.tone));
        highlight.setAttribute("stroke-width", Math.max(0.52, spec.width * 0.1).toFixed(2));
        layer.appendChild(highlight);
      }

      branchPaths.set(spec.id, main);
    });

    let coreVisual = null;
    const movingNodes = [];
    nodeSpecs.forEach((spec) => {
      if (spec.kind === "core" || spec.kind === "agent-core") {
        const isAgentCore = spec.kind === "agent-core";
        const outer = createSvgNode("circle", {
          cx: spec.x,
          cy: spec.y,
          r: (spec.size * (isAgentCore ? 4.45 : 4.0)).toFixed(2),
          class: "neuron-node-glow"
        });
        outer.setAttribute("fill", isAgentCore ? "rgba(217, 119, 87, 0.05)" : "rgba(245, 244, 239, 0.025)");
        nodeLayer.appendChild(outer);

        const inner = createSvgNode("circle", {
          cx: spec.x,
          cy: spec.y,
          r: (spec.size * (isAgentCore ? 2.72 : 2.25)).toFixed(2),
          class: "neuron-node-glow"
        });
        inner.setAttribute("fill", isAgentCore ? "rgba(255, 228, 214, 0.11)" : "rgba(217, 119, 87, 0.08)");
        nodeLayer.appendChild(inner);

        const shell = isAgentCore ? createSvgNode("circle", {
          cx: spec.x,
          cy: spec.y,
          r: (spec.size * 1.7).toFixed(2),
          class: "neuron-node-glow"
        }) : null;
        if (shell) {
          shell.setAttribute("fill", "none");
          shell.setAttribute("stroke", "rgba(217, 119, 87, 0.18)");
          shell.setAttribute("stroke-width", "1.02");
          shell.style.opacity = "0.34";
          nodeLayer.appendChild(shell);
        }

        const coreNode = createSvgNode("circle", {
          cx: spec.x,
          cy: spec.y,
          r: (spec.size * (isAgentCore ? 1.28 : 1.18)).toFixed(2),
          class: "neuron-node-core"
        });
        coreNode.setAttribute("fill", "url(#neuron-core-fill)");
        nodeLayer.appendChild(coreNode);

        const hotCenter = createSvgNode("circle", {
          cx: spec.x,
          cy: spec.y,
          r: (spec.size * (isAgentCore ? 0.32 : 0.38)).toFixed(2),
          class: "neuron-node-core"
        });
        hotCenter.setAttribute("fill", "rgba(255, 255, 255, 0.98)");
        nodeLayer.appendChild(hotCenter);

        coreVisual = {
          size: spec.size,
          isAgentCore,
          outer,
          inner,
          shell,
          coreNode,
          hotCenter
        };
        return;
      }

      const glow = createSvgNode("circle", {
        cx: spec.x,
        cy: spec.y,
        r: (spec.size * (spec.kind === "spark" ? 1.5 : 2.15)).toFixed(2),
        class: "neuron-node-glow"
      });
      glow.setAttribute("fill", spec.kind === "warm" ? "rgba(217, 119, 87, 0.04)" : "rgba(245, 244, 239, 0.03)");
      nodeLayer.appendChild(glow);

      const node = createSvgNode("circle", {
        cx: spec.x,
        cy: spec.y,
        r: spec.size.toFixed(2),
        class: spec.kind === "spark" ? "neuron-node-spark" : "neuron-node-satellite"
      });
      node.setAttribute("fill", spec.kind === "warm" ? "rgba(255, 230, 214, 0.34)" : "url(#neuron-node-fill)");
      nodeLayer.appendChild(node);

      const center = createSvgNode("circle", {
        cx: spec.x,
        cy: spec.y,
        r: Math.max(1.2, spec.size * 0.22).toFixed(2),
        class: "neuron-node-spark"
      });
      center.setAttribute("fill", "rgba(255, 255, 255, 0.94)");
      nodeLayer.appendChild(center);

      if (spec.motion) {
        const seededProgress = ((((spec.motion.delayMs || 0) % spec.motion.durationMs) + spec.motion.durationMs) % spec.motion.durationMs) / spec.motion.durationMs;
        movingNodes.push({
          spec,
          glow,
          node,
          center,
          phase: movingNodes.length * 0.74,
          progress: spec.motion.reverse ? (1 - seededProgress + 1) % 1 : seededProgress
        });
      }
    });

    stage.dataset.neuronRendered = "true";

    const pulses = supportsPathMotion ? pulseSpecs.map((spec, index) => {
      const path = branchPaths.get(spec.branchId);
      if (!path) {
        return null;
      }

      const length = path.getTotalLength();
      if (!length) {
        return null;
      }

      const glow = createSvgNode("circle", {
        cx: "0",
        cy: "0",
        r: spec.size.toFixed(2),
        class: `neuron-pulse ${spec.tone === "warm" ? "neuron-pulse-warm" : "neuron-pulse-cool"}`
      });
      const coreNode = createSvgNode("circle", {
        cx: "0",
        cy: "0",
        r: Math.max(0.9, spec.size * 0.22).toFixed(2),
        class: "neuron-pulse"
      });
      coreNode.setAttribute("fill", "rgba(255, 255, 255, 0.96)");

      pulseLayer.appendChild(glow);
      pulseLayer.appendChild(coreNode);

      const seededProgress = ((((spec.delayMs || 0) % spec.durationMs) + spec.durationMs) % spec.durationMs) / spec.durationMs;
      return {
        ...spec,
        path,
        length,
        glow,
        coreNode,
        phase: index * 0.82,
        progress: spec.reverse ? (1 - seededProgress + 1) % 1 : seededProgress
      };
    }).filter(Boolean) : [];
    const orbiters = supportsPathMotion ? orbiterSpecs.map((spec, index) => {
      const path = branchPaths.get(spec.branchId);
      if (!path) {
        return null;
      }

      const length = path.getTotalLength();
      if (!length) {
        return null;
      }

      const glow = createSvgNode("circle", {
        cx: "0",
        cy: "0",
        r: spec.glowSize.toFixed(2),
        class: "neuron-node-glow"
      });
      glow.setAttribute("fill", spec.tone === "warm" ? "rgba(217, 119, 87, 0.16)" : "rgba(245, 244, 239, 0.12)");
      pulseLayer.appendChild(glow);

      const shell = createSvgNode("circle", {
        cx: "0",
        cy: "0",
        r: (spec.size * 1.55).toFixed(2),
        class: "neuron-node-satellite"
      });
      shell.setAttribute("fill", "rgba(255, 255, 255, 0.12)");
      pulseLayer.appendChild(shell);

      const coreNode = createSvgNode("circle", {
        cx: "0",
        cy: "0",
        r: spec.size.toFixed(2),
        class: "neuron-node-satellite"
      });
      coreNode.setAttribute("fill", spec.tone === "warm" ? "rgba(255, 236, 224, 0.94)" : "rgba(255, 255, 255, 0.94)");
      pulseLayer.appendChild(coreNode);

      const hot = createSvgNode("circle", {
        cx: "0",
        cy: "0",
        r: Math.max(0.9, spec.size * 0.34).toFixed(2),
        class: "neuron-node-spark"
      });
      hot.setAttribute("fill", "rgba(255, 255, 255, 0.98)");
      pulseLayer.appendChild(hot);

      const seededProgress = ((((spec.delayMs || 0) % spec.durationMs) + spec.durationMs) % spec.durationMs) / spec.durationMs;
      return {
        ...spec,
        path,
        length,
        glow,
        shell,
        coreNode,
        hot,
        phase: index * 1.14,
        progress: spec.reverse ? (1 - seededProgress + 1) % 1 : seededProgress
      };
    }).filter(Boolean) : [];

    const renderPulseFrame = (now) => {
      if (coreVisual) {
        const breath = (Math.sin(now / 2400) + 1) / 2;
        const outerBase = coreVisual.isAgentCore ? 4.15 : 3.7;
        const outerDrift = coreVisual.isAgentCore ? 0.22 : 0.16;
        const innerBase = coreVisual.isAgentCore ? 2.56 : 2.04;
        const innerDrift = coreVisual.isAgentCore ? 0.08 : 0.06;
        const coreBase = coreVisual.isAgentCore ? 1.12 : 1.02;
        const coreDrift = coreVisual.isAgentCore ? 0.014 : 0.01;
        const centerBase = coreVisual.isAgentCore ? 0.24 : 0.28;
        const centerDrift = coreVisual.isAgentCore ? 0.012 : 0.01;
        coreVisual.outer.setAttribute("r", (coreVisual.size * (outerBase + breath * outerDrift)).toFixed(2));
        coreVisual.inner.setAttribute("r", (coreVisual.size * (innerBase + breath * innerDrift)).toFixed(2));
        if (coreVisual.shell) {
          coreVisual.shell.setAttribute("r", (coreVisual.size * (1.62 + breath * 0.06)).toFixed(2));
          coreVisual.shell.style.opacity = (0.26 + breath * 0.08).toFixed(3);
        }
        coreVisual.coreNode.setAttribute("r", (coreVisual.size * (coreBase + breath * coreDrift)).toFixed(2));
        coreVisual.hotCenter.setAttribute("r", (coreVisual.size * (centerBase + breath * centerDrift)).toFixed(2));
        coreVisual.outer.style.opacity = (coreVisual.isAgentCore ? 0.036 + breath * 0.018 : 0.02 + breath * 0.012).toFixed(3);
        coreVisual.inner.style.opacity = (coreVisual.isAgentCore ? 0.06 + breath * 0.024 : 0.04 + breath * 0.016).toFixed(3);
      }

      pulses.forEach((pulse) => {
        const shimmer = (Math.sin((now / 520) + pulse.phase) + 1) / 2;
        const point = pulse.path.getPointAtLength(pulse.progress * pulse.length);
        const opacity = pulse.tone === "warm"
          ? 0.06 + shimmer * 0.04
          : 0.05 + shimmer * 0.04;

        pulse.glow.setAttribute("cx", point.x.toFixed(2));
        pulse.glow.setAttribute("cy", point.y.toFixed(2));
        pulse.glow.setAttribute("r", pulse.size.toFixed(2));
        pulse.glow.style.opacity = opacity.toFixed(3);

        pulse.coreNode.setAttribute("cx", point.x.toFixed(2));
        pulse.coreNode.setAttribute("cy", point.y.toFixed(2));
        pulse.coreNode.style.opacity = Math.min(0.18, opacity + 0.04).toFixed(3);
      });

      movingNodes.forEach((particle) => {
        const motion = particle.spec.motion;
        if (!motion) {
          return;
        }
        const shimmer = (Math.sin((now / 680) + particle.phase) + 1) / 2;
        const direction = motion.reverse ? -1 : 1;
        const angle = motion.angleDeg + (particle.progress * 360 * direction);
        const radiusOffset = motion.radiusWobble
          ? Math.sin((now / (motion.wobbleMs || 2200)) + particle.phase) * motion.radiusWobble
          : 0;
        const point = polarPoint(motion.cx, motion.cy, motion.radius + radiusOffset, angle);

        particle.glow.setAttribute("cx", point.x.toFixed(2));
        particle.glow.setAttribute("cy", point.y.toFixed(2));
        particle.glow.style.opacity = (particle.spec.kind === "spark" ? 0.12 + shimmer * 0.08 : 0.12 + shimmer * 0.08).toFixed(3);

        particle.node.setAttribute("cx", point.x.toFixed(2));
        particle.node.setAttribute("cy", point.y.toFixed(2));
        particle.node.style.opacity = (particle.spec.kind === "spark" ? 0.62 + shimmer * 0.14 : 0.62 + shimmer * 0.14).toFixed(3);

        particle.center.setAttribute("cx", point.x.toFixed(2));
        particle.center.setAttribute("cy", point.y.toFixed(2));
        particle.center.style.opacity = (0.74 + shimmer * 0.14).toFixed(3);
      });

      orbiters.forEach((orbiter) => {
        const shimmer = (Math.sin((now / 720) + orbiter.phase) + 1) / 2;
        const point = orbiter.path.getPointAtLength(orbiter.progress * orbiter.length);
        const glowOpacity = orbiter.tone === "warm"
          ? 0.16 + shimmer * 0.08
          : 0.14 + shimmer * 0.08;

        orbiter.glow.setAttribute("cx", point.x.toFixed(2));
        orbiter.glow.setAttribute("cy", point.y.toFixed(2));
        orbiter.glow.style.opacity = glowOpacity.toFixed(3);

        orbiter.shell.setAttribute("cx", point.x.toFixed(2));
        orbiter.shell.setAttribute("cy", point.y.toFixed(2));
        orbiter.shell.style.opacity = (0.3 + shimmer * 0.1).toFixed(3);

        orbiter.coreNode.setAttribute("cx", point.x.toFixed(2));
        orbiter.coreNode.setAttribute("cy", point.y.toFixed(2));
        orbiter.coreNode.style.opacity = (0.84 + shimmer * 0.08).toFixed(3);

        orbiter.hot.setAttribute("cx", point.x.toFixed(2));
        orbiter.hot.setAttribute("cy", point.y.toFixed(2));
        orbiter.hot.style.opacity = (0.66 + shimmer * 0.12).toFixed(3);
      });
    };

    if (prefersReducedMotion || !supportsPathMotion || (!pulses.length && !orbiters.length && !movingNodes.length)) {
      renderPulseFrame(0);
      return;
    }

    let rafId = 0;
    let lastFrameTime = 0;

    const render = (now) => {
      if (!lastFrameTime) {
        lastFrameTime = now;
      }
      const dt = Math.min(34, Math.max(12, now - lastFrameTime));
      lastFrameTime = now;

      pulses.forEach((pulse) => {
        const direction = pulse.reverse ? -1 : 1;
        const velocity = (dt / pulse.durationMs) * (pulse.tone === "warm" ? 1.18 : 1) * direction;
        pulse.progress = (pulse.progress + velocity + 1) % 1;
      });
      movingNodes.forEach((particle) => {
        const motion = particle.spec.motion;
        if (!motion) {
          return;
        }
        const direction = motion.reverse ? -1 : 1;
        const velocity = (dt / motion.durationMs) * (particle.spec.kind === "spark" ? 0.92 : 1) * direction;
        particle.progress = (particle.progress + velocity + 1) % 1;
      });
      orbiters.forEach((orbiter) => {
        const direction = orbiter.reverse ? -1 : 1;
        const velocity = (dt / orbiter.durationMs) * (orbiter.tone === "warm" ? 1.06 : 1) * direction;
        orbiter.progress = (orbiter.progress + velocity + 1) % 1;
      });

      renderPulseFrame(now);
      rafId = window.requestAnimationFrame(render);
    };

    const start = () => {
      if (!rafId) {
        rafId = window.requestAnimationFrame(render);
      }
    };

    const stop = () => {
      if (rafId) {
        window.cancelAnimationFrame(rafId);
        rafId = 0;
      }
      lastFrameTime = 0;
    };

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        stop();
        return;
      }
      start();
    });

    start();
  });
}

function writeYear() {
  const yearSlot = document.getElementById("yearSlot");
  if (yearSlot) {
    yearSlot.textContent = String(new Date().getFullYear());
  }
}

applySiteState();
initTopNavActiveState();
applyReleaseState();
initRevealAnimations();
initHeroMemoryParticles();
initRuntimeLoop();
if (document.querySelector("[data-proof-tab]")) {
  initProofTabs();
}
writeYear();
initLangSwitch();
