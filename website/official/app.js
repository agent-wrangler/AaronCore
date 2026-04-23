const siteConfig = {
  productName: "AaronCore",
  brandSubline: "Memory that comes back naturally",
  primaryDomain: "aaroncore.com",
  contactLabel: "hello@aaroncore.com",
  contactUrl: "mailto:hello@aaroncore.com",
  contactStatus: "direct email for access, partnerships, and questions",
  launchState: "Official site first",
  releaseRoute: "aaroncore.com / future download channel",
  metaDescription:
    "A memory-first agent project exploring how understanding, continuity, and action can grow from memory.",
  ogDescription:
    "AaronCore explores how agents can build real continuity through memory instead of isolated, one-off responses.",
  betaUrl: "./beta.html",
  betaLabel: "Join Beta",
  earlyAccessLabel: "Join Beta",
  demoUrl: "./product.html#proof",
  demoLabel: "See proof",
  docsUrl: "./docs.html",
  docsLabel: "Research"
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
  const pageTitle = String(document.body?.dataset?.pageTitle || "").trim();
  const pageDescription = String(document.body?.dataset?.pageDescription || "").trim();
  const pageOgTitle = String(document.body?.dataset?.pageOgTitle || "").trim();
  const pageOgDescription = String(document.body?.dataset?.pageOgDescription || "").trim();
  const titleSuffix =
    page === "product"
      ? "Product"
      : page === "docs"
        ? "Research"
        : page === "papers"
          ? "Papers"
        : page === "beta"
          ? "Beta"
        : page === "changelog"
          ? "Changelog"
          : "AI that remembers you";

  document.title = `${siteConfig.productName} | ${pageTitle || titleSuffix}`;
  setMeta('meta[name="description"]', pageDescription || siteConfig.metaDescription);
  setMeta(
    'meta[property="og:title"]',
    pageOgTitle || `${siteConfig.productName} | ${pageTitle || siteConfig.brandSubline}`
  );
  setMeta('meta[property="og:description"]', pageOgDescription || pageDescription || siteConfig.ogDescription);

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
    "nav.docs": "Research",
    "nav.papers": "Papers",
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

    "docs.title": "Research",
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
    "changelog.r1.p": "Split Home / Product / Research / Changelog, tightened copy toward continuity + verification, and reduced “demo UI” noise on the homepage.",
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
    "nav.docs": "\u7814\u7a76",
    "nav.papers": "\u8bba\u6587",
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

    "docs.title": "\u7814\u7a76",
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
    "changelog.r1.p": "\u62c6\u5206 Home/Product/Research/Changelog\uff0c\u6587\u6848\u805a\u7126\u8fde\u7eed\u6027\u4e0e\u53ef\u9a8c\u8bc1\uff0c\u5e76\u964d\u4f4e\u9996\u9875\u201c\u6f14\u793a UI\u201d\u566a\u97f3\u3002",
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
    "nav.docs": "\u7814\u7a76",
    "nav.papers": "\u8ad6\u6587",
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

    "docs.title": "\u7814\u7a76",
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
    "changelog.r1.p": "Home/Product/Research/Changelog \u306b\u5206\u5272\u3057\u3001\u7d99\u7d9a\u6027\u3068\u691c\u8a3c\u306b\u7126\u70b9\u3092\u5408\u308f\u305b\u3001\u30db\u30fc\u30e0\u306e\u30c7\u30e2\u611f\u3092\u6291\u5236\u3002",
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
    "nav.docs": "\uc5f0\uad6c",
    "nav.papers": "\ub17c\ubb38",
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

    "docs.title": "\uc5f0\uad6c",
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
    "changelog.r1.p": "Home/Product/Research/Changelog\ub85c \ubd84\ub9ac\ud558\uace0 \uc5f0\uc18d\uc131\uacfc \uac80\uc99d\uc5d0 \ucd08\uc810\uc744 \ub9de\ucdb0 \ud648\uc758 \ub370\ubaa8 \ub290\ub08c\uc744 \uc904\uc600\uc2b5\ub2c8\ub2e4.",
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

Object.assign(I18N.en, {
  "docs.index.nav.all": "All",
  "docs.index.title": "Research",
  "docs.index.subtitle": "Start here. This page is only the index to the public material.",
  "docs.index.order.label": "Read in order",
  "docs.index.order.desc": "Paper first. Product second. Changelog when you want the latest public changes.",
  "docs.index.item.paper.type": "Paper",
  "docs.index.item.paper.date": "April 16, 2026",
  "docs.index.item.paper.title": "The Core of Agent Products Is Continuity",
  "docs.index.item.paper.desc": "Why continuity sits at the core of agent products, and how memory and runtime state make it real.",
  "docs.index.item.product.type": "Product",
  "docs.index.item.product.date": "April 16, 2026",
  "docs.index.item.product.title": "Product",
  "docs.index.item.product.desc": "What AaronCore does, how memory appears in use, and the current public posture.",
  "docs.index.item.changelog.type": "Changelog",
  "docs.index.item.changelog.date": "April 16, 2026",
  "docs.index.item.changelog.title": "Changelog",
  "docs.index.item.changelog.desc": "A short record of what changed on the site and the public surface."
});

Object.assign(I18N.zh, {
  "docs.index.nav.all": "全部",
  "docs.index.title": "\u7814\u7a76",
  "docs.index.subtitle": "从这里开始。本页只负责把你带到公开材料。",
  "docs.index.order.label": "阅读顺序",
  "docs.index.order.desc": "先看论文，再看产品页；如果你想知道公开表面最近变了什么，再看更新记录。",
  "docs.index.item.paper.type": "论文",
  "docs.index.item.paper.date": "2026年4月16日",
  "docs.index.item.paper.title": "Agent 产品的核心是连续性",
  "docs.index.item.paper.desc": "为什么连续性是 Agent 产品的核心，以及记忆与运行时状态如何让它成立。",
  "docs.index.item.product.type": "产品",
  "docs.index.item.product.date": "2026年4月16日",
  "docs.index.item.product.title": "产品页",
  "docs.index.item.product.desc": "AaronCore 现在对外在讲什么，记忆如何在使用中出现，以及当前的公开姿态。",
  "docs.index.item.changelog.type": "更新",
  "docs.index.item.changelog.date": "2026年4月16日",
  "docs.index.item.changelog.title": "更新记录",
  "docs.index.item.changelog.desc": "网站和公开表面改了什么，都在这里做简短记录。"
});

Object.assign(I18N.ja, {
  "docs.index.nav.all": "すべて",
  "docs.index.title": "\u7814\u7a76",
  "docs.index.subtitle": "ここから始めてください。このページは公開されている内容への索引だけです。",
  "docs.index.order.label": "読む順番",
  "docs.index.order.desc": "まず論文、次に製品ページ。公開面で最近何が変わったかを見たいときだけ更新履歴を読めば十分です。",
  "docs.index.item.paper.type": "論文",
  "docs.index.item.paper.date": "2026年4月16日",
  "docs.index.item.paper.title": "The Core of Agent Products Is Continuity",
  "docs.index.item.paper.desc": "連続性、記憶、ランタイム状態についての中核となる文章。",
  "docs.index.item.product.type": "製品",
  "docs.index.item.product.date": "2026年4月16日",
  "docs.index.item.product.title": "製品ページ",
  "docs.index.item.product.desc": "AaronCore が何をするのか、記憶がどう現れるのか、そして現在の公開姿勢をまとめています。",
  "docs.index.item.changelog.type": "更新",
  "docs.index.item.changelog.date": "2026年4月16日",
  "docs.index.item.changelog.title": "更新履歴",
  "docs.index.item.changelog.desc": "サイトと公開面で変わったことを短く記録しています。"
});

Object.assign(I18N.ko, {
  "docs.index.nav.all": "전체",
  "docs.index.title": "\uc5f0\uad6c",
  "docs.index.subtitle": "여기서 시작하면 됩니다. 이 페이지는 공개 자료로 들어가는 인덱스만 담당합니다.",
  "docs.index.order.label": "읽는 순서",
  "docs.index.order.desc": "먼저 논문, 그다음 제품 페이지. 공개 표면에서 최근 무엇이 바뀌었는지 보고 싶을 때만 변경 기록을 보면 됩니다.",
  "docs.index.item.paper.type": "논문",
  "docs.index.item.paper.date": "2026년 4월 16일",
  "docs.index.item.paper.title": "The Core of Agent Products Is Continuity",
  "docs.index.item.paper.desc": "연속성, 기억, 런타임 상태에 대한 핵심 글입니다.",
  "docs.index.item.product.type": "제품",
  "docs.index.item.product.date": "2026년 4월 16일",
  "docs.index.item.product.title": "제품 페이지",
  "docs.index.item.product.desc": "AaronCore가 무엇을 하는지, 기억이 사용 중 어떻게 드러나는지, 그리고 현재의 공개 태도를 정리합니다.",
  "docs.index.item.changelog.type": "업데이트",
  "docs.index.item.changelog.date": "2026년 4월 16일",
  "docs.index.item.changelog.title": "변경 기록",
  "docs.index.item.changelog.desc": "사이트와 공개 표면에서 바뀐 내용을 짧게 기록합니다."
});

Object.assign(I18N.en, {
  "home.diff.h": "Less reset. More room to work.",
  "home.diff.p": "Memory matters because it cuts repeated setup, keeps the loop lighter, and leaves more of the token budget for the current move.",
  "home.diff.c1": "Memory stays live, not reset every turn",
  "home.diff.c1.p": "Context, preference, and task state remain in the loop, so the conversation keeps moving instead of rebooting at every turn.",
  "home.diff.c2": "Less retelling. Less token burn.",
  "home.diff.c2.p": "Only the memory that matters comes forward, instead of dragging the whole transcript back into every turn.",
  "home.diff.c3": "Keep the budget for execution, not for rebuilding context",
  "home.diff.c3.p": "A lighter loop leaves more room for tools, task state, and verification instead of spending turns reconstructing the same background.",
  "home.cap.route.h": "Runtime routes by state, not by noise",
  "home.cap.route.p": "The runtime activates recall, chat, tool use, or verification based on what the turn actually needs.",
  "home.cap.route.s1": "Recall",
  "home.cap.route.s2": "Chat",
  "home.cap.route.s3": "Tools",
  "home.cap.route.s4": "Verify",
  "home.cap.state.h": "Task state survives between moves",
  "home.cap.state.p": "Progress, blockers, and the latest action stay attached, so the loop can continue instead of re-guessing from scratch.",
  "home.cap.verify.h": "Done means checked, not declared",
  "home.cap.verify.p": "A run should end with a result, the changed artifact, and enough trace to see why it counts."
});

Object.assign(I18N.zh, {
  "home.diff.h": "少重置，给执行留出空间",
  "home.diff.p": "记忆的价值不是堆更多上下文，而是减少重复前情，让当前回合更轻，把 token 留给这一步真正要做的事。",
  "home.diff.c1": "记忆永续，不是回合重置",
  "home.diff.c1.p": "上下文、偏好和任务状态不会每一轮都清空，所以对话像同一条流继续往前，而不是反复重新开机。",
  "home.diff.c2": "少复述，也少烧 tokens",
  "home.diff.c2.p": "不是把整段历史反复拖回当前回合，而是只把这一刻真正有用的记忆带上来。",
  "home.diff.c3": "把 token 留给执行，不留给前情重建",
  "home.diff.c3.p": "循环越轻，工具调用、任务状态和验证越能直接接上，而不是先花掉一轮去补背景。",
  "home.cap.route.h": "运行时按状态分流，而不是按噪音乱跳",
  "home.cap.route.p": "这一轮到底该走回忆、对话、工具还是验证，由运行时根据当前状态来决定。",
  "home.cap.route.s1": "回忆",
  "home.cap.route.s2": "对话",
  "home.cap.route.s3": "工具",
  "home.cap.route.s4": "验证",
  "home.cap.state.h": "任务状态会跟着一轮轮动作继续活着",
  "home.cap.state.p": "进度、阻塞点和最近一次动作会一直挂着，这样系统不是每一步都从头再猜。",
  "home.cap.verify.h": "完成，不是嘴上说完成",
  "home.cap.verify.p": "一次运行结束时，应该留下结果、改动过的东西，以及足够解释“为什么算完成”的轨迹。"
});

Object.assign(I18N.ja, {
  "home.diff.h": "リセットを減らし、実行の余白を増やす。",
  "home.diff.p": "記憶の価値は文脈を積み上げることではなく、前置きの繰り返しを減らし、そのターンで必要な仕事にトークンを回せることにある。",
  "home.diff.c1": "記憶は各ターンでリセットされない",
  "home.diff.c1.p": "文脈、好み、タスク状態がループの中に残るので、会話は毎回再起動せず一続きの流れとして進む。",
  "home.diff.c2": "言い直しを減らし、トークンも減らす",
  "home.diff.c2.p": "毎ターンすべての履歴を引きずるのではなく、その瞬間に必要な記憶だけを前に出す。",
  "home.diff.c3": "トークンは前置きではなく実行に使う",
  "home.diff.c3.p": "ループが軽いほど、ツール実行、タスク状態、検証がそのままつながり、背景の再構築にターンを使わない。",
  "home.cap.route.h": "ランタイムはノイズではなく状態で分流する",
  "home.cap.route.p": "このターンで想起、会話、ツール、検証のどこに入るべきかを、現在の状態から決める。",
  "home.cap.route.s1": "想起",
  "home.cap.route.s2": "会話",
  "home.cap.route.s3": "ツール",
  "home.cap.route.s4": "検証",
  "home.cap.state.h": "タスク状態は手順のあいだも生き続ける",
  "home.cap.state.p": "進捗、詰まり、直前の行動がぶら下がったままなので、毎回最初から推測し直さなくていい。",
  "home.cap.verify.h": "完了は宣言ではなく検証で決まる",
  "home.cap.verify.p": "実行の終わりには、結果と変更点、そしてなぜ完了と言えるのか分かるだけの痕跡が残るべきだ。"
});

Object.assign(I18N.ko, {
  "home.diff.h": "리셋을 줄이고, 실행을 위한 공간을 남긴다.",
  "home.diff.p": "기억의 가치는 문맥을 더 쌓는 데 있지 않고, 반복 설명을 줄여 지금 이 턴의 일에 토큰을 쓰게 하는 데 있다.",
  "home.diff.c1": "기억은 턴마다 리셋되지 않는다",
  "home.diff.c1.p": "문맥, 선호, 작업 상태가 루프 안에 남아 있으니 대화는 매번 다시 부팅되지 않고 한 흐름으로 이어진다.",
  "home.diff.c2": "덜 다시 설명하고, 토큰도 덜 쓴다",
  "home.diff.c2.p": "매 턴 전체 기록을 다시 끌고 오는 대신, 지금 필요한 기억만 앞으로 가져온다.",
  "home.diff.c3": "토큰은 배경 복원보다 실행에 써야 한다",
  "home.diff.c3.p": "루프가 가벼울수록 도구 실행, 작업 상태, 검증이 바로 이어지고 배경을 다시 세우는 데 턴을 낭비하지 않는다.",
  "home.cap.route.h": "런타임은 소음이 아니라 상태를 보고 분기한다",
  "home.cap.route.p": "이번 턴이 회상, 대화, 도구, 검증 중 어디로 들어가야 하는지는 현재 상태를 보고 결정한다.",
  "home.cap.route.s1": "회상",
  "home.cap.route.s2": "대화",
  "home.cap.route.s3": "도구",
  "home.cap.route.s4": "검증",
  "home.cap.state.h": "작업 상태는 단계 사이에서도 살아남는다",
  "home.cap.state.p": "진행도, 막힌 지점, 마지막 행동이 붙어 있으니 매번 처음부터 다시 추측할 필요가 없다.",
  "home.cap.verify.h": "완료는 선언이 아니라 검증이다",
  "home.cap.verify.p": "한 번의 실행은 결과, 바뀐 산출물, 그리고 왜 완료로 볼 수 있는지 설명할 흔적을 남겨야 한다."
});

Object.assign(I18N.en, {
  "home.diff.h": "Memory should stop eating the turn.",
  "home.diff.p": "Its job is to minimize resets, shrink the context overhead, and leave the token budget for the move that matters now.",
  "home.diff.c1": "Persistent memory, not turn-by-turn amnesia",
  "home.diff.c1.p": "The user should not have to reintroduce themselves, their preferences, and the active task on every pass.",
  "home.diff.c2": "Less background recap. Less token waste.",
  "home.diff.c2.p": "Only the memory that matters now should come forward, instead of hauling the full transcript into every turn.",
  "home.diff.c3": "The lighter the context, the faster the work",
  "home.diff.c3.p": "When the background does not need to be rebuilt, tools, task state, and verification can connect directly.",
  "home.cap.route.h": "One runtime. Different surfaces.",
  "home.cap.route.p": "Recall, chat, tool use, and verification are distinct surfaces. The runtime chooses the one this turn actually needs.",
  "home.cap.state.h": "State carries the line of work",
  "home.cap.state.p": "Progress, blockers, and the last action stay attached, so the next move continues instead of guessing.",
  "home.cap.verify.h": "A finish should leave proof",
  "home.cap.verify.p": "The run ends with a result, the changed artifact, and enough trace to inspect why it counts."
});

Object.assign(I18N.zh, {
  "home.diff.h": "记忆，不该吃掉这一回合。",
  "home.diff.p": "它的作用不是把上下文越堆越厚，而是压低重置感、压缩前情成本，把 token 留给当前真正要做的动作。",
  "home.diff.c1": "记忆永续，不是回合失忆",
  "home.diff.c1.p": "用户不该每一轮都重新介绍自己、偏好和当前任务。它们应该一直活在同一条工作线上。",
  "home.diff.c2": "少讲背景，少烧 tokens",
  "home.diff.c2.p": "被带到眼前的应该只是此刻真正有用的记忆，而不是把整段历史每轮重拖一遍。",
  "home.diff.c3": "上下文越轻，执行越快接上",
  "home.diff.c3.p": "当前情境不用反复重建，工具、任务状态和验证才能直接接进这一轮动作里。",
  "home.cap.route.h": "一个运行时，不同表面。",
  "home.cap.route.p": "回忆、对话、工具调用、验证是不同表面。当前这一轮该进哪一层，由运行时自己判断。",
  "home.cap.state.h": "状态把这条工作线扛下去",
  "home.cap.state.p": "进度、阻塞点和上一步动作始终挂着，所以系统是在继续，而不是在猜。",
  "home.cap.verify.h": "收尾，得留下证据",
  "home.cap.verify.p": "一次运行结束时，要留下结果、改动过的东西，以及足够解释它为什么算完成的轨迹。"
});

Object.assign(I18N.ja, {
  "home.diff.h": "記憶は、このターンを食ってはいけない。",
  "home.diff.p": "役目は文脈を厚く積むことではなく、リセット感を減らし、前置きのコストを縮め、そのターンで本当に必要な動きにトークンを残すことだ。",
  "home.diff.c1": "記憶は持続する。ターンごとに失われない",
  "home.diff.c1.p": "ユーザーが毎ターン、自分のこと、好み、いまの作業を言い直す必要はない。それらは同じ仕事の線に残り続けるべきだ。",
  "home.diff.c2": "背景説明を減らし、トークンも減らす",
  "home.diff.c2.p": "前に出るべきなのは、その瞬間に本当に必要な記憶だけであって、履歴全体を毎回引きずることではない。",
  "home.diff.c3": "文脈が軽いほど、実行は速くつながる",
  "home.diff.c3.p": "背景を何度も組み直さなくてよければ、ツール、タスク状態、検証がそのターンに直接つながる。",
  "home.cap.route.h": "ひとつのランタイム。複数の面。",
  "home.cap.route.p": "想起、会話、ツール実行、検証は別の面だ。このターンでどこに入るべきかをランタイムが選ぶ。",
  "home.cap.state.h": "状態が仕事の線を運び続ける",
  "home.cap.state.p": "進捗、詰まり、直前の行動が残るので、システムは推測ではなく継続として動ける。",
  "home.cap.verify.h": "終わりには証拠が要る",
  "home.cap.verify.p": "実行の終わりには、結果、変更物、そしてなぜ完了と見なせるのかを確かめられる痕跡が残るべきだ。"
});

Object.assign(I18N.ko, {
  "home.diff.h": "기억이 이 턴을 잡아먹어서는 안 된다.",
  "home.diff.p": "기억의 역할은 문맥을 두껍게 쌓는 것이 아니라, 리셋감을 줄이고 배경 비용을 압축해 지금 필요한 움직임에 토큰을 남기는 데 있다.",
  "home.diff.c1": "기억은 지속된다. 턴마다 잃어버리지 않는다",
  "home.diff.c1.p": "사용자가 매 턴마다 자기 자신, 선호, 현재 작업을 다시 소개할 필요는 없다. 그것들은 같은 작업선 위에 계속 살아 있어야 한다.",
  "home.diff.c2": "배경 설명을 줄이고, 토큰도 줄인다",
  "home.diff.c2.p": "앞으로 나와야 하는 것은 지금 정말 필요한 기억뿐이지, 전체 기록을 매번 다시 끌고 오는 일이 아니다.",
  "home.diff.c3": "문맥이 가벼울수록 실행은 더 빨리 붙는다",
  "home.diff.c3.p": "배경을 반복해서 다시 세우지 않아도 되면, 도구 실행, 작업 상태, 검증이 이번 턴에 바로 이어질 수 있다.",
  "home.cap.route.h": "하나의 런타임. 서로 다른 표면.",
  "home.cap.route.p": "회상, 대화, 도구 실행, 검증은 서로 다른 표면이다. 이번 턴이 어디로 들어가야 하는지는 런타임이 고른다.",
  "home.cap.state.h": "상태가 이 작업선을 계속 들고 간다",
  "home.cap.state.p": "진행도, 막힌 지점, 직전 행동이 남아 있으니 시스템은 추측이 아니라 연속성으로 움직일 수 있다.",
  "home.cap.verify.h": "끝에는 증거가 남아야 한다",
  "home.cap.verify.p": "한 번의 실행이 끝날 때는 결과, 바뀐 산출물, 그리고 왜 완료로 볼 수 있는지 확인할 흔적이 남아야 한다."
});

Object.assign(I18N.en, {
  "home.diff.h": "Persistent memory keeps the token budget for execution.",
  "home.diff.p": "When context, preference, and task state stay live, the runtime stops reloading the same background every turn. That is where token savings start: less recap, less prompt overhead, more room for tools, state progression, and verification.",
  "home.diff.c1": "Memory persistence replaces repeated setup",
  "home.diff.c1.p": "The user should not have to restate identity, preference, and the active task every turn. Those belong to the same line of work.",
  "home.diff.c2": "Bring back the useful past, not the whole transcript",
  "home.diff.c2.p": "Token savings do not come from deleting memory. They come from surfacing the relevant past instead of replaying the entire history on every pass.",
  "home.diff.c3": "Spend the budget on action, not recap",
  "home.diff.c3.p": "A lighter context leaves more room for tool use, task state, and verification instead of paying again for background reconstruction."
});

Object.assign(I18N.zh, {
  "home.diff.h": "记忆永续，把 token 留给执行。",
  "home.diff.p": "当上下文、偏好和任务状态一直在线，系统就不用每一轮都把同样的前情重新装载。token 的节省就从这里开始：少复述、少铺背景，把预算留给工具调用、状态推进和验证。",
  "home.diff.c1": "记忆永续，替代重复开场",
  "home.diff.c1.p": "用户不该每一轮都重新介绍自己、偏好和当前任务。这些东西本来就该挂在同一条工作线上。",
  "home.diff.c2": "带回有用前情，不重拖整段历史",
  "home.diff.c2.p": "节省 token 不是靠删记忆，而是只把这一刻真正相关的那部分提上来，而不是每次都把整段对话重放一遍。",
  "home.diff.c3": "把预算花在动作上，不花在复述上",
  "home.diff.c3.p": "上下文越轻，工具调用、任务状态和验证越能直接接上，预算留给执行，而不是留给背景重建。"
});

Object.assign(I18N.ja, {
  "home.diff.h": "持続する記憶が、トークンを実行に回す。",
  "home.diff.p": "文脈、好み、タスク状態が生き続けていれば、毎ターン同じ前提を読み直す必要がない。トークン節約はここから始まる。言い直しを減らし、背景説明を減らし、予算をツール実行、状態更新、検証に回せる。",
  "home.diff.c1": "持続する記憶が、毎回の再設定を減らす",
  "home.diff.c1.p": "ユーザーは毎ターン、自分のこと、好み、現在のタスクを言い直すべきではない。それらは同じ仕事の流れに残り続けるべきだ。",
  "home.diff.c2": "必要な過去だけを戻し、履歴全体は引きずらない",
  "home.diff.c2.p": "トークン節約は記憶を消すことから生まれない。その瞬間に関係する過去だけを前に出し、毎回すべての履歴を再生しないことから生まれる。",
  "home.diff.c3": "予算は前置きではなく実行に使う",
  "home.diff.c3.p": "文脈が軽いほど、ツール実行、タスク状態、検証がそのままつながり、背景の再構築にもう一度コストを払わずに済む。"
});

Object.assign(I18N.ko, {
  "home.diff.h": "지속되는 기억이 토큰을 실행에 남긴다.",
  "home.diff.p": "문맥, 선호, 작업 상태가 계속 살아 있으면 매 턴마다 같은 배경을 다시 불러올 필요가 없다. 토큰 절약은 여기서 시작된다. 반복 설명과 배경 복원을 줄이고, 예산을 도구 실행, 상태 진행, 검증에 남긴다.",
  "home.diff.c1": "지속되는 기억이 반복 설정을 대신한다",
  "home.diff.c1.p": "사용자는 매 턴마다 자기 자신, 선호, 현재 작업을 다시 설명할 필요가 없다. 그것들은 같은 작업선에 계속 붙어 있어야 한다.",
  "home.diff.c2": "필요한 과거만 다시 가져오고, 전체 기록은 끌지 않는다",
  "home.diff.c2.p": "토큰 절약은 기억을 지우는 데서 오지 않는다. 지금 관련 있는 과거만 앞으로 가져오고, 매번 전체 대화를 다시 재생하지 않는 데서 나온다.",
  "home.diff.c3": "예산은 복습이 아니라 실행에 써야 한다",
  "home.diff.c3.p": "문맥이 가벼울수록 도구 실행, 작업 상태, 검증이 바로 이어지고, 배경을 다시 세우는 데 비용을 또 쓰지 않아도 된다."
});

Object.assign(I18N.en, {
  "home.diff.stat.1.label": "50-message session",
  "home.diff.stat.2.label": "100-message session",
  "home.diff.stat.3.label": "200-message session",
  "home.diff.stat.saved": "saved from prompt recap",
  "home.diff.stat.note": "Balanced 4000-token recent-budget benchmark based on long-session replay estimates.",
  "home.diff.band.1": "Tools",
  "home.diff.band.2": "Task state",
  "home.diff.band.3": "Verification",
  "product.proof.cta": "Research index",
  "product.surface.h": "How that shows up in use",
  "product.surface.p": "Once the proof is clear, the rest of the product reads as four user-facing behaviors: natural flashback, time recall, remembered posture, and cleaner memory hygiene."
});

Object.assign(I18N.zh, {
  "home.diff.stat.1.label": "50 条消息会话",
  "home.diff.stat.2.label": "100 条消息会话",
  "home.diff.stat.3.label": "200 条消息会话",
  "home.diff.stat.saved": "前情重述开销下降",
  "home.diff.stat.note": "基于 balanced 4000-token recent budget 的长会话 replay 估算基准。",
  "home.diff.band.1": "工具调用",
  "home.diff.band.2": "任务状态",
  "home.diff.band.3": "验证",
  "product.proof.cta": "研究索引",
  "product.surface.h": "它在使用里怎么出现",
  "product.surface.p": "当这层证明先站住，后面的产品描述就会清楚得多：自然闪回、按时间回忆、记得你的交流姿态，以及更干净的记忆卫生。"
});

Object.assign(I18N.ja, {
  "home.diff.stat.1.label": "50メッセージのセッション",
  "home.diff.stat.2.label": "100メッセージのセッション",
  "home.diff.stat.3.label": "200メッセージのセッション",
  "home.diff.stat.saved": "前置きの再投入を削減",
  "home.diff.stat.note": "balanced 4000-token recent budget を前提にした長会話 replay 推定ベンチマーク。",
  "home.diff.band.1": "ツール",
  "home.diff.band.2": "タスク状態",
  "home.diff.band.3": "検証",
  "product.proof.cta": "研究索引",
  "product.surface.h": "それが使用時にどう現れるか",
  "product.surface.p": "この証明が先に見えていれば、あとの製品説明は四つの振る舞いとして読める。自然な想起、時間による振り返り、会話姿勢の持続、そしてより清潔な記憶衛生だ。"
});

Object.assign(I18N.ko, {
  "home.diff.stat.1.label": "50개 메시지 세션",
  "home.diff.stat.2.label": "100개 메시지 세션",
  "home.diff.stat.3.label": "200개 메시지 세션",
  "home.diff.stat.saved": "배경 재설명 비용 절감",
  "home.diff.stat.note": "balanced 4000-token recent budget 기준의 장기 세션 replay 추정 벤치마크.",
  "home.diff.band.1": "도구 실행",
  "home.diff.band.2": "작업 상태",
  "home.diff.band.3": "검증",
  "product.proof.cta": "리서치 인덱스",
  "product.surface.h": "이것이 사용 중에 드러나는 방식",
  "product.surface.p": "이 증명이 먼저 서 있으면, 이후의 제품 설명은 네 가지 사용자-facing 동작으로 읽힌다. 자연스러운 회상, 시간 회고, 기억된 대화 자세, 그리고 더 깨끗한 기억 위생이다."
});

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
  const ariaNodes = Array.from(document.querySelectorAll("[data-i18n-aria-label]"));
  ariaNodes.forEach((node) => {
    const key = String(node.getAttribute("data-i18n-aria-label") || "").trim();
    if (!key) return;
    const value = t(key, l);
    if (value) node.setAttribute("aria-label", value);
  });
  // site fields that used to be injected
  setField("site", "brandSubline", t("brand.subline", l));
  syncBetaSelectLabels(l);

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
    papers: "./docs.html",
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

function initDocsIndexNav() {
  const tabs = Array.from(document.querySelectorAll("[data-docs-filter]"));
  const records = Array.from(document.querySelectorAll("[data-docs-record]"));
  const emptyState = document.querySelector("[data-docs-empty]");

  if (!tabs.length || !records.length) {
    return;
  }

  const readPublishedAt = (record) => {
    const raw = String(record.getAttribute("data-docs-published-at") || "").trim();
    if (!raw) {
      return Number.NEGATIVE_INFINITY;
    }
    const stamp = Date.parse(raw);
    return Number.isFinite(stamp) ? stamp : Number.NEGATIVE_INFINITY;
  };

  const groupedRecords = new Map();
  records.forEach((record, index) => {
    const parent = record.parentElement;
    if (!parent) {
      return;
    }
    if (!groupedRecords.has(parent)) {
      groupedRecords.set(parent, []);
    }
    groupedRecords.get(parent).push({ record, index });
  });

  groupedRecords.forEach((items, parent) => {
    items
      .sort((left, right) => {
        const timeDelta = readPublishedAt(right.record) - readPublishedAt(left.record);
        if (timeDelta !== 0) {
          return timeDelta;
        }
        return left.index - right.index;
      })
      .forEach(({ record }) => {
        parent.appendChild(record);
      });
  });

  const validFilters = new Set(["all", ...tabs
    .map((tab) => String(tab.getAttribute("data-docs-filter") || "").trim().toLowerCase())
    .filter(Boolean)]);

  const readFilterFromHash = () => {
    const hash = String(window.location.hash || "").trim().toLowerCase();
    if (hash.startsWith("#docs-")) {
      const nextFilter = hash.slice("#docs-".length);
      if (validFilters.has(nextFilter)) {
        return nextFilter;
      }
    }
    return "all";
  };

  const writeHash = (filter) => {
    const nextHash = filter === "all" ? "#docs-all" : `#docs-${filter}`;
    const nextUrl = `${window.location.pathname}${window.location.search}${nextHash}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (nextUrl !== currentUrl) {
      window.history.replaceState(null, "", nextUrl);
    }
  };

  const activate = (filter, options = {}) => {
    const nextFilter = validFilters.has(filter) ? filter : "all";
    let visibleCount = 0;

    tabs.forEach((tab) => {
      const isActive = tab.getAttribute("data-docs-filter") === nextFilter;
      tab.classList.toggle("is-active", isActive);
      if (isActive) {
        tab.setAttribute("aria-current", "page");
      } else {
        tab.removeAttribute("aria-current");
      }
    });

    records.forEach((record) => {
      const kind = record.getAttribute("data-docs-record");
      const shouldShow = nextFilter === "all" || kind === nextFilter;
      record.classList.toggle("is-hidden", !shouldShow);
      record.hidden = !shouldShow;
      if (shouldShow) {
        visibleCount += 1;
      }
    });

    if (emptyState) {
      emptyState.hidden = visibleCount > 0;
    }

    if (options.writeHash !== false) {
      writeHash(nextFilter);
    }
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", (event) => {
      event.preventDefault();
      activate(tab.getAttribute("data-docs-filter") || "all");
    });
  });

  window.addEventListener("hashchange", () => {
    activate(readFilterFromHash(), { writeHash: false });
  });

  activate(readFilterFromHash(), { writeHash: false });
}

function initBetaWaitlistForm() {
  const form = document.querySelector("[data-beta-form]");
  if (!(form instanceof HTMLFormElement)) {
    return;
  }

  const emailInput = form.querySelector('input[name="email"]');
  const useCaseInput = form.querySelector('input[name="useCase"]');
  const trapInput = form.querySelector('input[name="website"]');
  const submitButton = form.querySelector('button[type="submit"]');
  const statusNode = form.querySelector("[data-beta-status]");
  const selectShell = form.querySelector("[data-beta-select]");
  const selectTrigger = form.querySelector("[data-beta-select-trigger]");
  const selectMenu = form.querySelector("[data-beta-select-menu]");
  const selectOptions = Array.from(form.querySelectorAll("[data-beta-select-option]"));
  if (
    !(emailInput instanceof HTMLInputElement) ||
    !(useCaseInput instanceof HTMLInputElement) ||
    !(submitButton instanceof HTMLButtonElement) ||
    !(statusNode instanceof HTMLElement) ||
    !(selectShell instanceof HTMLElement) ||
    !(selectTrigger instanceof HTMLButtonElement) ||
    !(selectMenu instanceof HTMLElement) ||
    !selectOptions.length
  ) {
    return;
  }

  const closeSelect = () => {
    selectShell.classList.remove("is-open");
    selectTrigger.setAttribute("aria-expanded", "false");
    selectMenu.hidden = true;
  };

  const openSelect = () => {
    selectShell.classList.add("is-open");
    selectTrigger.setAttribute("aria-expanded", "true");
    selectMenu.hidden = false;
  };

  const setStatus = (key, tone) => {
    const lang = getLang();
    statusNode.textContent = key ? t(key, lang) : "";
    statusNode.classList.remove("is-success", "is-error");
    if (tone) {
      statusNode.classList.add(`is-${tone}`);
    }
  };

  selectTrigger.addEventListener("click", () => {
    if (selectShell.classList.contains("is-open")) {
      closeSelect();
      return;
    }
    openSelect();
  });

  selectOptions.forEach((option) => {
    option.addEventListener("click", () => {
      useCaseInput.value = String(option.dataset.value || "").trim();
      syncBetaSelectLabels();
      closeSelect();
      setStatus("", "");
    });
  });

  document.addEventListener("click", (event) => {
    if (!(event.target instanceof Node) || selectShell.contains(event.target)) {
      return;
    }
    closeSelect();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSelect();
    }
  });

  syncBetaSelectLabels();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) {
      return;
    }

    const email = emailInput.value.trim();
    const useCase = useCaseInput.value.trim();
    const selectedOption = selectOptions.find((option) => String(option.dataset.value || "").trim() === useCase);
    const useCaseLabel = String(selectedOption?.textContent || useCase).trim();
    const lang = String(document.documentElement.getAttribute("lang") || getLang()).trim();
    const website = trapInput instanceof HTMLInputElement ? trapInput.value.trim() : "";

    if (!useCase) {
      setStatus("home.beta.form.invalid", "error");
      openSelect();
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = t("home.beta.form.submitting", lang);
    setStatus("", "");

    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          useCase,
          useCaseLabel,
          lang,
          source: "aaroncore.com / beta",
          website,
        }),
      });

      if (!response.ok) {
        const messageKey =
          response.status === 400
            ? "home.beta.form.invalid"
            : response.status === 503
              ? "home.beta.form.unavailable"
              : "home.beta.form.error";
        throw new Error(messageKey);
      }

      form.reset();
      useCaseInput.value = "";
      syncBetaSelectLabels();
      closeSelect();
      setStatus("home.beta.form.success", "success");
    } catch (error) {
      const messageKey =
        error instanceof Error && error.message
          ? error.message
          : "home.beta.form.error";
      setStatus(messageKey, "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = t("home.beta.form.submit", getLang());
    }
  });
}

function syncBetaSelectLabels(lang = getLang()) {
  document.querySelectorAll("[data-beta-select]").forEach((shell) => {
    if (!(shell instanceof HTMLElement)) {
      return;
    }

    const input = shell.querySelector('input[name="useCase"]');
    const triggerText = shell.querySelector("[data-beta-select-trigger-text]");
    const options = Array.from(shell.querySelectorAll("[data-beta-select-option]"));
    if (!(input instanceof HTMLInputElement) || !(triggerText instanceof HTMLElement)) {
      return;
    }

    const selectedValue = input.value.trim();
    const selectedOption = options.find(
      (option) => option instanceof HTMLElement && String(option.dataset.value || "").trim() === selectedValue
    );

    options.forEach((option) => {
      if (option instanceof HTMLElement) {
        option.setAttribute("aria-selected", option === selectedOption ? "true" : "false");
      }
    });

    if (selectedOption instanceof HTMLElement) {
      triggerText.textContent = selectedOption.textContent || "";
      shell.classList.remove("is-placeholder");
      return;
    }

    const placeholderKey = String(triggerText.dataset.placeholderKey || "").trim();
    triggerText.textContent = placeholderKey ? t(placeholderKey, lang) : "";
    shell.classList.add("is-placeholder");
  });
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
  const pulseSpecs = [
    { branchId: "agent-inner", tone: "cool", size: 2.2, durationMs: 3600, delayMs: 120 },
    { branchId: "agent-inner", tone: "warm", size: 1.9, durationMs: 5200, delayMs: 1680, reverse: true },
    { branchId: "agent-mid", tone: "warm", size: 2.8, durationMs: 5200, delayMs: 640 },
    { branchId: "agent-mid", tone: "cool", size: 2.2, durationMs: 6800, delayMs: 2460, reverse: true },
    { branchId: "agent-primary", tone: "cool", size: 3.1, durationMs: 7600, delayMs: 1140 },
    { branchId: "agent-primary", tone: "warm", size: 2.6, durationMs: 9400, delayMs: 4820, reverse: true },
    { branchId: "agent-field", tone: "cool", size: 1.8, durationMs: 9800, delayMs: 3240 },
    { branchId: "llm-core-ring", tone: "cool", size: 1.7, durationMs: 4200, delayMs: 900 },
    { branchId: "llm-core-ring", tone: "warm", size: 1.5, durationMs: 5600, delayMs: 2840, reverse: true }
  ];
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
          ? 0.1 + shimmer * 0.08
          : 0.08 + shimmer * 0.07;

        pulse.glow.setAttribute("cx", point.x.toFixed(2));
        pulse.glow.setAttribute("cy", point.y.toFixed(2));
        pulse.glow.setAttribute("r", pulse.size.toFixed(2));
        pulse.glow.style.opacity = opacity.toFixed(3);

        pulse.coreNode.setAttribute("cx", point.x.toFixed(2));
        pulse.coreNode.setAttribute("cy", point.y.toFixed(2));
        pulse.coreNode.style.opacity = Math.min(0.26, opacity + 0.06).toFixed(3);
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

Object.assign(I18N.en, {
  "docs.index.nav.all": "All",
  "docs.index.nav.researchNotes": "Research Notes",
  "docs.index.nav.experiments": "Experiments & Explorations",
  "docs.index.nav.milestones": "Milestones",
  "docs.index.nav.openSource": "Open Source Results",
  "docs.index.subtitle": "A small shelf of essays and notes. Start with the long argument, then move through the smaller claims.",
  "docs.index.order.label": "Shelf",
  "docs.index.order.desc": "Essays carry the full argument. Notes pull out the claims worth revisiting.",
  "docs.index.item.essay.type": "Research Note",
  "docs.index.item.essay.date": "April 16, 2026",
  "docs.index.item.essay.title": "The Core of Agent Products Is Continuity",
  "docs.index.item.essay.desc": "Why continuity sits at the core of agent products, and how memory and runtime state make it real.",
  "docs.index.item.intentExperiment.type": "Experiment",
  "docs.index.item.intentExperiment.date": "April 16, 2026",
  "docs.index.item.intentExperiment.title": "From Intent Routing to Interaction Governance",
  "docs.index.item.intentExperiment.desc": "An archived exploration of false tool triggers, action governance, and why this path did not become AaronCore's main architecture.",
  "docs.index.item.memory.type": "Research Note",
  "docs.index.item.memory.date": "April 16, 2026",
  "docs.index.item.memory.title": "Memory Is Not a Feature",
  "docs.index.item.memory.desc": "Why memory belongs to runtime behavior instead of a detachable feature list.",
  "docs.index.item.continuity.type": "Research Note",
  "docs.index.item.continuity.date": "April 16, 2026",
  "docs.index.item.continuity.title": "Continuity Breaks Before Intelligence",
  "docs.index.item.continuity.desc": "Why agents fail when work stops accumulating across turns, even before model quality becomes the bottleneck.",
  "docs.index.item.state.type": "Research Note",
  "docs.index.item.state.date": "April 16, 2026",
  "docs.index.item.state.title": "State Beats Prompt Tricks",
  "docs.index.item.state.desc": "Why explicit task state matters more than clever phrasing once execution starts.",
  "docs.index.item.taskSkeleton.type": "Research Note",
  "docs.index.item.taskSkeleton.date": "April 23, 2026",
  "docs.index.item.taskSkeleton.title": "Action Logs Are Not Task Progress",
  "docs.index.item.taskSkeleton.desc": "Why complex tasks need a skeleton, not just an action log, and why this remains an active AaronCore research direction.",
  "docs.index.item.visionLocal.type": "Open Source Result",
  "docs.index.item.visionLocal.date": "April 23, 2026",
  "docs.index.item.visionLocal.title": "Vision Local Context",
  "docs.index.item.visionLocal.desc": "Why AaronCore opened a local screenshot-understanding layer as a standalone module, and what this open-source result is meant to own.",
  "docs.index.item.visionLocal.link": "GitHub Repository",
  "docs.index.item.visionLocal.linkLabel": "Open GitHub repository",
  "docs.index.item.feedbackRules.type": "Research Note",
  "docs.index.item.feedbackRules.date": "April 23, 2026",
  "docs.index.item.feedbackRules.title": "Feedback Should Become Rules",
  "docs.index.item.feedbackRules.desc": "Why agent feedback should be classified, scoped, and turned into durable behavior instead of leaking into memory as residue.",
  "docs.index.empty.label": "No entries yet"
});

Object.assign(I18N.zh, {
  "docs.index.nav.all": "\u5168\u90e8",
  "docs.index.nav.researchNotes": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.nav.experiments": "\u5b9e\u9a8c\u4e0e\u63a2\u7d22",
  "docs.index.nav.milestones": "\u91cc\u7a0b\u7891",
  "docs.index.nav.openSource": "\u5f00\u6e90\u6210\u679c",
  "docs.index.subtitle": "\u8fd9\u91cc\u662f AaronCore \u7684\u5c0f\u578b\u9986\u85cf\u67b6\uff1a\u5148\u8bfb\u5b8c\u6574\u6587\u7ae0\uff0c\u518d\u8fdb\u5165\u90a3\u4e9b\u503c\u5f97\u53cd\u590d\u56de\u770b\u7684\u89c2\u70b9\u3002",
  "docs.index.order.label": "\u9986\u85cf",
  "docs.index.order.desc": "\u6587\u7ae0\u627f\u8f7d\u5b8c\u6574\u8bba\u8ff0\uff0c\u7b14\u8bb0\u62bd\u51fa\u5176\u4e2d\u503c\u5f97\u53cd\u590d\u91cd\u8bfb\u7684\u90e8\u5206\u3002",
  "docs.index.item.essay.type": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.item.essay.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.essay.title": "Agent \u4ea7\u54c1\u7684\u6838\u5fc3\u662f\u8fde\u7eed\u6027",
  "docs.index.item.essay.desc": "\u4e3a\u4ec0\u4e48\u8fde\u7eed\u6027\u662f Agent \u4ea7\u54c1\u7684\u6838\u5fc3\uff0c\u4ee5\u53ca\u8bb0\u5fc6\u4e0e\u8fd0\u884c\u65f6\u72b6\u6001\u5982\u4f55\u8ba9\u5b83\u6210\u7acb\u3002",
  "docs.index.item.intentExperiment.type": "\u5b9e\u9a8c",
  "docs.index.item.intentExperiment.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.intentExperiment.title": "\u4ece\u610f\u56fe\u8def\u7531\u5230\u4ea4\u4e92\u6cbb\u7406",
  "docs.index.item.intentExperiment.desc": "\u4e00\u6b21\u5173\u4e8e\u8bef\u89e6\u53d1\u3001\u884c\u52a8\u6cbb\u7406\u4e0e\u67b6\u6784\u8fb9\u754c\u7684\u5f52\u6863\u63a2\u7d22\uff0c\u4e5f\u8bf4\u660e\u4e86\u4e3a\u4ec0\u4e48\u8fd9\u6761\u8def\u6ca1\u6709\u6210\u4e3a AaronCore \u7684\u4e3b\u7ebf\u3002",
  "docs.index.item.memory.type": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.item.memory.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.memory.title": "\u8bb0\u5fc6\u4e0d\u662f\u529f\u80fd",
  "docs.index.item.memory.desc": "\u4e3a\u4ec0\u4e48\u8bb0\u5fc6\u5c5e\u4e8e\u8fd0\u884c\u65f6\u884c\u4e3a\uff0c\u800c\u4e0d\u662f\u53ef\u4ee5\u5355\u72ec\u5217\u51fa\u7684\u4e00\u4e2a\u529f\u80fd\u70b9\u3002",
  "docs.index.item.continuity.type": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.item.continuity.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.continuity.title": "\u8fde\u7eed\u6027\u4f1a\u5728\u667a\u80fd\u4e4b\u524d\u5148\u65ad\u88c2",
  "docs.index.item.continuity.desc": "\u4e3a\u4ec0\u4e48 agent \u7684\u5931\u8d25\uff0c\u5f80\u5f80\u53d1\u751f\u5728\u5de5\u4f5c\u65e0\u6cd5\u8de8\u56de\u5408\u79ef\u7d2f\u7684\u65f6\u5019\uff0c\u800c\u4e0d\u662f\u5148\u8f93\u5728\u6a21\u578b\u80fd\u529b\u3002",
  "docs.index.item.state.type": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.item.state.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.state.title": "\u663e\u5f0f\u72b6\u6001\u6bd4 prompt \u6280\u5de7\u66f4\u91cd\u8981",
  "docs.index.item.state.desc": "\u4e00\u65e6\u5f00\u59cb\u6267\u884c\uff0c\u660e\u786e\u7684\u4efb\u52a1\u72b6\u6001\u6bd4\u66f4\u8054\u54e8\u7684\u63aa\u8f9e\u66f4\u6709\u7528\u3002",
  "docs.index.item.taskSkeleton.type": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.item.taskSkeleton.date": "2026\u5e744\u670823\u65e5",
  "docs.index.item.taskSkeleton.title": "\u6b65\u9aa4\u65e5\u5fd7\u4e0d\u7b49\u4e8e\u4efb\u52a1\u8fdb\u5ea6",
  "docs.index.item.taskSkeleton.desc": "\u4e3a\u4ec0\u4e48\u590d\u6742\u4efb\u52a1\u9700\u8981\u4e00\u4e2a\u4efb\u52a1\u9aa8\u67b6\uff0c\u800c\u4e0d\u53ea\u662f\u4e00\u4e32 action log\uff0c\u4e5f\u4e3a\u4ec0\u4e48\u8fd9\u4ecd\u7136\u662f AaronCore \u6b63\u5728\u63a2\u7d22\u7684\u7814\u7a76\u65b9\u5411\u3002",
  "docs.index.item.visionLocal.type": "\u5f00\u6e90\u6210\u679c",
  "docs.index.item.visionLocal.date": "2026\u5e744\u670823\u65e5",
  "docs.index.item.visionLocal.title": "Vision Local Context",
  "docs.index.item.visionLocal.desc": "\u4e3a\u4ec0\u4e48 AaronCore \u628a\u4e00\u4e2a\u672c\u5730\u622a\u56fe\u7406\u89e3\u5c42\u62c6\u51fa\u6210\u72ec\u7acb\u6a21\u5757\u5f00\u6e90\uff0c\u4ee5\u53ca\u8fd9\u4e2a open-source result \u6253\u7b97\u771f\u6b63\u627f\u62c5\u4ec0\u4e48\u8fb9\u754c\u3002",
  "docs.index.item.visionLocal.link": "GitHub \u4ed3\u5e93",
  "docs.index.item.visionLocal.linkLabel": "\u6253\u5f00 GitHub \u4ed3\u5e93",
  "docs.index.item.feedbackRules.type": "\u7814\u7a76\u7b14\u8bb0",
  "docs.index.item.feedbackRules.date": "2026\u5e744\u670823\u65e5",
  "docs.index.item.feedbackRules.title": "\u53cd\u9988\u5e94\u8be5\u6c89\u6dc0\u6210\u89c4\u5219",
  "docs.index.item.feedbackRules.desc": "\u4e3a\u4ec0\u4e48 agent \u7684\u53cd\u9988\u4e0d\u8be5\u53ea\u662f\u7559\u5728\u8bb0\u5fc6\u91cc\u7684\u6b8b\u6e23\uff0c\u800c\u5e94\u8be5\u5148\u88ab\u5206\u7c7b\u3001\u9650\u5b9a\u4f5c\u7528\u8303\u56f4\uff0c\u518d\u53d8\u6210\u53ef\u6301\u7eed\u7684\u884c\u4e3a\u89c4\u5219\u3002",
  "docs.index.empty.label": "\u6682\u65f6\u8fd8\u6ca1\u6709\u6761\u76ee"
});

Object.assign(I18N.ja, {
  "docs.index.nav.all": "\u3059\u3079\u3066",
  "docs.index.nav.researchNotes": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.nav.experiments": "\u5b9f\u9a13\u3068\u63a2\u7d22",
  "docs.index.nav.milestones": "\u30de\u30a4\u30eb\u30b9\u30c8\u30fc\u30f3",
  "docs.index.nav.openSource": "\u30aa\u30fc\u30d7\u30f3\u30bd\u30fc\u30b9\u6210\u679c",
  "docs.index.subtitle": "AaronCore \u306e\u5c0f\u3055\u306a\u8535\u66f8\u68da\u3067\u3059\u3002\u307e\u305a\u9577\u3044\u8ad6\u8003\u3092\u8aad\u307f\u3001\u305d\u306e\u5f8c\u306b\u6838\u5fc3\u7684\u306a\u4e3b\u5f35\u3060\u3051\u3092\u8f9e\u66f8\u306e\u3088\u3046\u306b\u8fd4\u305b\u307e\u3059\u3002",
  "docs.index.order.label": "\u8535\u66f8",
  "docs.index.order.desc": "\u8ad6\u8003\u304c\u5168\u4f53\u306e\u8ad6\u7406\u3092\u62c5\u3044\u3001\u30ce\u30fc\u30c8\u304c\u7e70\u308a\u8fd4\u3057\u623b\u308a\u305f\u3044\u8ad6\u70b9\u3092\u62bd\u51fa\u3057\u307e\u3059\u3002",
  "docs.index.item.essay.type": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.item.essay.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.essay.title": "The Core of Agent Products Is Continuity",
  "docs.index.item.essay.desc": "AaronCore \u3092\u8a9e\u308b\u4e0a\u3067\u306e\u51fa\u767a\u70b9\u3068\u3057\u3066\u3001\u8a18\u61b6\u3001\u9023\u7d9a\u6027\u3001\u30e9\u30f3\u30bf\u30a4\u30e0\u72b6\u614b\u3092\u6271\u3044\u307e\u3059\u3002",
  "docs.index.item.intentExperiment.type": "Experiment",
  "docs.index.item.intentExperiment.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.intentExperiment.title": "From Intent Routing to Interaction Governance",
  "docs.index.item.intentExperiment.desc": "An archived exploration of false tool triggers, action governance, and why this path did not become AaronCore's main architecture.",
  "docs.index.item.memory.type": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.item.memory.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.memory.title": "Memory Is Not a Feature",
  "docs.index.item.memory.desc": "\u8a18\u61b6\u304c\u72ec\u7acb\u3057\u305f\u6a5f\u80fd\u30ea\u30b9\u30c8\u3067\u306f\u306a\u304f\u3001\u30e9\u30f3\u30bf\u30a4\u30e0\u306e\u632f\u308b\u821e\u3044\u306b\u5c5e\u3059\u308b\u7406\u7531\u3002",
  "docs.index.item.continuity.type": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.item.continuity.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.continuity.title": "Continuity Breaks Before Intelligence",
  "docs.index.item.continuity.desc": "\u30e2\u30c7\u30eb\u306e\u80fd\u529b\u304c\u554f\u984c\u306b\u306a\u308b\u524d\u306b\u3001\u4ed5\u4e8b\u304c\u30bf\u30fc\u30f3\u3092\u8d85\u3048\u3066\u84c4\u7a4d\u3067\u304d\u306a\u3044\u3053\u3068\u304c agent \u306e\u5931\u6557\u3092\u751f\u3080\u7406\u7531\u3002",
  "docs.index.item.state.type": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.item.state.date": "2026\u5e744\u670816\u65e5",
  "docs.index.item.state.title": "State Beats Prompt Tricks",
  "docs.index.item.state.desc": "\u5b9f\u884c\u304c\u59cb\u307e\u3063\u305f\u5f8c\u306f\u3001\u5de7\u307f\u306a\u8a00\u3044\u56de\u3057\u3088\u308a\u3082\u660e\u793a\u7684\u306a\u30bf\u30b9\u30af\u72b6\u614b\u306e\u65b9\u304c\u91cd\u8981\u3067\u3059\u3002",
  "docs.index.item.taskSkeleton.type": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.item.taskSkeleton.date": "2026\u5e744\u670823\u65e5",
  "docs.index.item.taskSkeleton.title": "\u30a2\u30af\u30b7\u30e7\u30f3\u30ed\u30b0\u306f\u30bf\u30b9\u30af\u9032\u6357\u3067\u306f\u306a\u3044",
  "docs.index.item.taskSkeleton.desc": "\u306a\u305c\u8907\u96d1\u306a\u4ed5\u4e8b\u306b\u306f action log \u3060\u3051\u3067\u306a\u304f task skeleton \u304c\u5fc5\u8981\u306a\u306e\u304b\u3002\u305d\u3057\u3066\u306a\u305c\u3053\u308c\u304c AaronCore \u306b\u3068\u3063\u3066\u307e\u3060\u63a2\u7d22\u4e2d\u306e\u7814\u7a76\u30c6\u30fc\u30de\u306a\u306e\u304b\u3002",
  "docs.index.item.visionLocal.type": "\u30aa\u30fc\u30d7\u30f3\u30bd\u30fc\u30b9\u6210\u679c",
  "docs.index.item.visionLocal.date": "2026\u5e744\u670823\u65e5",
  "docs.index.item.visionLocal.title": "Vision Local Context",
  "docs.index.item.visionLocal.desc": "\u306a\u305c AaronCore \u304c\u30ed\u30fc\u30ab\u30eb\u306e\u30b9\u30af\u30ea\u30fc\u30f3\u30b7\u30e7\u30c3\u30c8\u7406\u89e3\u5c64\u3092\u72ec\u7acb\u30e2\u30b8\u30e5\u30fc\u30eb\u3068\u3057\u3066\u516c\u958b\u3057\u305f\u306e\u304b\u3002\u305d\u3057\u3066\u3053\u306e open-source result \u304c\u3069\u3053\u307e\u3067\u3092\u62c5\u3046\u3079\u304d\u304b\u3092\u8aac\u660e\u3057\u307e\u3059\u3002",
  "docs.index.item.visionLocal.link": "GitHub Repository",
  "docs.index.item.visionLocal.linkLabel": "GitHub \u30ea\u30dd\u30b8\u30c8\u30ea\u3092\u958b\u304f",
  "docs.index.item.feedbackRules.type": "\u7814\u7a76\u30ce\u30fc\u30c8",
  "docs.index.item.feedbackRules.date": "2026\u5e744\u670823\u65e5",
  "docs.index.item.feedbackRules.title": "\u30d5\u30a3\u30fc\u30c9\u30d0\u30c3\u30af\u306f\u30eb\u30fc\u30eb\u306b\u306a\u308b\u3079\u304d\u3060",
  "docs.index.item.feedbackRules.desc": "agent \u3078\u306e\u4fee\u6b63\u304c\u8a18\u61b6\u306e\u6b8b\u6e23\u3068\u3057\u3066\u6f0f\u308c\u308b\u306e\u3067\u306f\u306a\u304f\u3001\u307e\u305a\u5206\u985e\u3068\u9069\u7528\u7bc4\u56f2\u306e\u8a2d\u5b9a\u3092\u7d4c\u3066\u3001\u6301\u7d9a\u7684\u306a\u632f\u308b\u821e\u3044\u306b\u5909\u63db\u3055\u308c\u308b\u3079\u304d\u7406\u7531\u3002",
  "docs.index.empty.label": "\u307e\u3060\u9805\u76ee\u306f\u3042\u308a\u307e\u305b\u3093"
});

Object.assign(I18N.ko, {
  "docs.index.nav.all": "\uc804\uccb4",
  "docs.index.nav.researchNotes": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.nav.experiments": "\uc2e4\ud5d8\uacfc \ud0d0\uc0c9",
  "docs.index.nav.milestones": "\ub9c8\uc77c\uc2a4\ud1a4",
  "docs.index.nav.openSource": "\uc624\ud508\uc18c\uc2a4 \uc131\uacfc",
  "docs.index.subtitle": "AaronCore \uc5f0\uad6c \uae00\uacfc \uba54\ubaa8\ub97c \ubaa8\uc544 \ub450\ub294 \uc791\uc740 \uc11c\uac00\uc785\ub2c8\ub2e4. \uba3c\uc800 \uae34 \uae00\uc744 \uc77d\uace0, \uadf8 \ub2e4\uc74c \ud575\uc2ec \ub17c\uc810\uc744 \ub178\ud2b8\ucc98\ub7fc \ub2e4\uc2dc \ub4e4\uc5ec\ub2e4\ubcf4\uba74 \ub429\ub2c8\ub2e4.",
  "docs.index.order.label": "\uc11c\uac00",
  "docs.index.order.desc": "\uae00\uc740 \uc804\uccb4 \ub17c\uc9c0\ub97c \ub2f4\uace0, \ub178\ud2b8\ub294 \ub2e4\uc2dc \ubcfc \uac00\uce58\uac00 \uc788\ub294 \ub17c\uc810\ub9cc \uac00\ub824 \ub0c5\ub2c8\ub2e4.",
  "docs.index.item.essay.type": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.item.essay.date": "2026\ub144 4\uc6d4 16\uc77c",
  "docs.index.item.essay.title": "The Core of Agent Products Is Continuity",
  "docs.index.item.essay.desc": "\uae30\uc5b5, \uc5f0\uc18d\uc131, \ub7f0\ud0c0\uc784 \uc0c1\ud0dc\ub97c AaronCore\uc758 \ucd9c\ubc1c\uc810\uc73c\ub85c \ub2e4\ub8f9\ub2c8\ub2e4.",
  "docs.index.item.intentExperiment.type": "Experiment",
  "docs.index.item.intentExperiment.date": "2026\ub144 4\uc6d4 16\uc77c",
  "docs.index.item.intentExperiment.title": "From Intent Routing to Interaction Governance",
  "docs.index.item.intentExperiment.desc": "An archived exploration of false tool triggers, action governance, and why this path did not become AaronCore's main architecture.",
  "docs.index.item.memory.type": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.item.memory.date": "2026\ub144 4\uc6d4 16\uc77c",
  "docs.index.item.memory.title": "Memory Is Not a Feature",
  "docs.index.item.memory.desc": "\uae30\uc5b5\uc774 \ub530\ub85c \ubd84\ub9ac\ub41c \uae30\ub2a5 \ubaa9\ub85d\uc774 \uc544\ub2c8\ub77c \ub7f0\ud0c0\uc784 \ud589\ub3d9\uc5d0 \uc18d\ud558\ub294 \uc774\uc720.",
  "docs.index.item.continuity.type": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.item.continuity.date": "2026\ub144 4\uc6d4 16\uc77c",
  "docs.index.item.continuity.title": "Continuity Breaks Before Intelligence",
  "docs.index.item.continuity.desc": "\ubaa8\ub378 \uc131\ub2a5\uc774 \ubb38\uc81c\uac00 \ub418\uae30 \uc804\uc5d0, \uc77c\uc774 \ud134\uc744 \ub118\uc5b4 \uc313\uc774\uc9c0 \ubabb\ud558\ub294 \uac83\uc774 agent \uc2e4\ud328\ub97c \ub9cc\ub4dc\ub294 \uc774\uc720.",
  "docs.index.item.state.type": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.item.state.date": "2026\ub144 4\uc6d4 16\uc77c",
  "docs.index.item.state.title": "State Beats Prompt Tricks",
  "docs.index.item.state.desc": "\uc2e4\ud589\uc774 \uc2dc\uc791\ub418\uba74, \uc601\ub9ac\ud55c \ubb38\uc7a5 \uae30\uc220\ubcf4\ub2e4 \uba85\uc2dc\uc801\uc778 \ud0dc\uc2a4\ud06c \uc0c1\ud0dc\uac00 \ub354 \uc911\uc694\ud569\ub2c8\ub2e4.",
  "docs.index.item.taskSkeleton.type": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.item.taskSkeleton.date": "2026\ub144 4\uc6d4 23\uc77c",
  "docs.index.item.taskSkeleton.title": "\uc561\uc158 \ub85c\uadf8\ub294 \ud0dc\uc2a4\ud06c \uc9c4\ud589\uc774 \uc544\ub2c8\ub2e4",
  "docs.index.item.taskSkeleton.desc": "\uc65c \ubcf5\uc7a1\ud55c \uc791\uc5c5\uc5d0\ub294 action log\ub9cc\uc73c\ub85c\ub294 \ubd80\uc871\ud558\uace0 task skeleton\uc774 \ud544\uc694\ud55c\uc9c0, \uadf8\ub9ac\uace0 \uc65c \uc774\uac83\uc774 AaronCore\uc5d0\uc11c \uc5ec\uc804\ud788 \ud0d0\uc0c9 \uc911\uc778 \uc5f0\uad6c \ubc29\ud5a5\uc778\uc9c0\ub97c \uc124\uba85\ud569\ub2c8\ub2e4.",
  "docs.index.item.visionLocal.type": "\uc624\ud508\uc18c\uc2a4 \uc131\uacfc",
  "docs.index.item.visionLocal.date": "2026\ub144 4\uc6d4 23\uc77c",
  "docs.index.item.visionLocal.title": "Vision Local Context",
  "docs.index.item.visionLocal.desc": "AaronCore\uac00 \uc65c \ub85c\uceec \uc2a4\ud06c\ub9b0\uc0f7 \uc774\ud574 \ub808\uc774\uc5b4\ub97c \ub3c5\ub9bd \ubaa8\ub4c8\ub85c \uc624\ud508\uc18c\uc2a4\ud654\ud588\ub294\uc9c0, \uadf8\ub9ac\uace0 \uc774 open-source result\uac00 \uc2e4\uc81c\ub85c \uc5b4\ub514\uae4c\uc9c0\ub97c \ub9e1\uc544\uc57c \ud558\ub294\uc9c0\ub97c \uc124\uba85\ud569\ub2c8\ub2e4.",
  "docs.index.item.visionLocal.link": "GitHub Repository",
  "docs.index.item.visionLocal.linkLabel": "GitHub \uc800\uc7a5\uc18c \uc5f4\uae30",
  "docs.index.item.feedbackRules.type": "\uc5f0\uad6c \ub178\ud2b8",
  "docs.index.item.feedbackRules.date": "2026\ub144 4\uc6d4 23\uc77c",
  "docs.index.item.feedbackRules.title": "\ud53c\ub4dc\ubc31\uc740 \uaddc\uce59\uc774 \ub418\uc5b4\uc57c \ud55c\ub2e4",
  "docs.index.item.feedbackRules.desc": "agent \ud53c\ub4dc\ubc31\uc740 \uae30\uc5b5 \uc18d \uc794\uc5ec\ubb3c\ub85c \ub0a8\ub294 \ub300\uc2e0, \uba3c\uc800 \ubd84\ub958\ub418\uace0 \uc801\uc6a9 \ubc94\uc704\uac00 \uc815\ud574\uc9c4 \ub4a4 \uc9c0\uc18d \uac00\ub2a5\ud55c \ud589\ub3d9 \uaddc\uce59\uc73c\ub85c \ubc14\ub00c\uc5b4\uc57c \ud55c\ub2e4.",
  "docs.index.empty.label": "\uc544\uc9c1 \ud56d\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4"
});

Object.assign(I18N.en, {
  "cta.emailWaitlist": "Email Waitlist",
  "home.beta.h": "Beta access is being actively prepared.",
  "home.beta.p": "The first public beta is still being assembled. Leave an email and AaronCore will reach out when the next batch opens.",
  "home.beta.state.label": "Current state",
  "home.beta.state.value": "Developer is actively preparing the beta",
  "home.beta.inbox.label": "Waitlist inbox",
  "home.beta.form.label": "Leave your email",
  "home.beta.form.usecase.label": "What do you want to use AaronCore for?",
  "home.beta.form.usecase.placeholder": "Choose a use case",
  "home.beta.form.usecase.coding": "Coding",
  "home.beta.form.usecase.research": "Research",
  "home.beta.form.usecase.writing": "Writing",
  "home.beta.form.usecase.assistant": "Daily assistance",
  "home.beta.form.usecase.execution": "Multi-step execution",
  "home.beta.form.usecase.memory": "Long-term memory",
  "home.beta.form.usecase.other": "Other",
  "home.beta.form.submit": "Join the waitlist",
  "home.beta.form.submitting": "Joining...",
  "home.beta.form.note": "Submitting adds you directly to the AaronCore waitlist.",
  "home.beta.form.success": "You're on the waitlist. AaronCore will reach out when the next batch opens.",
  "home.beta.form.invalid": "Please check the email and use case, then try again.",
  "home.beta.form.unavailable": "The waitlist backend is not live yet. Email hello@aaroncore.com for now.",
  "home.beta.form.error": "Something slipped while saving your request. Please try again.",
  "beta.title": "Join the AaronCore beta",
  "beta.subtitle": "The first public beta is being prepared. Leave an email and AaronCore will reach out when the next batch opens.",
  "beta.status.h": "Current rollout",
  "beta.status.p": "AaronCore is not opening the beta broadly yet. Access starts from the waitlist and expands in small batches.",
  "beta.access.label": "Access model",
  "beta.access.value": "Waitlist first. Invitations go out in small batches."
});

Object.assign(I18N.zh, {
  "cta.emailWaitlist": "\u90ae\u4ef6\u62a5\u540d",
  "home.beta.h": "\u52a0\u5165\u5185\u6d4b\uff0c\u5148\u7559\u4e2a\u90ae\u7bb1\u3002",
  "home.beta.p": "AaronCore \u7684\u9996\u8f6e\u516c\u5f00\u5185\u6d4b\u8fd8\u5728\u7b79\u5907\u4e2d\u3002\u4f60\u53ef\u4ee5\u5148\u628a\u90ae\u7bb1\u7559\u4e0b\uff0c\u4e0b\u4e00\u6279\u5f00\u653e\u65f6\u4f1a\u4f18\u5148\u8054\u7cfb\u4f60\u3002",
  "home.beta.state.label": "\u5f53\u524d\u72b6\u6001",
  "home.beta.state.value": "\u5f00\u53d1\u8005\u6b63\u5728\u79ef\u6781\u7b79\u5907\u4e2d",
  "home.beta.inbox.label": "\u62a5\u540d\u90ae\u7bb1",
  "home.beta.form.label": "\u90ae\u7bb1",
  "home.beta.form.usecase.label": "\u4f60\u60f3\u7528 AaronCore \u505a\u4ec0\u4e48\uff1f",
  "home.beta.form.usecase.placeholder": "\u9009\u62e9\u4e00\u4e2a\u7528\u9014",
  "home.beta.form.usecase.coding": "\u5199\u4ee3\u7801",
  "home.beta.form.usecase.research": "\u7814\u7a76 / \u67e5\u8d44\u6599",
  "home.beta.form.usecase.writing": "\u5199\u4f5c",
  "home.beta.form.usecase.assistant": "\u65e5\u5e38\u52a9\u7406",
  "home.beta.form.usecase.execution": "\u591a\u6b65\u9aa4\u4efb\u52a1\u6267\u884c",
  "home.beta.form.usecase.memory": "\u957f\u671f\u8bb0\u5fc6 / \u966a\u4f34",
  "home.beta.form.usecase.other": "\u5176\u4ed6",
  "home.beta.form.submit": "\u52a0\u5165\u7b49\u5f85\u540d\u5355",
  "home.beta.form.submitting": "\u6b63\u5728\u63d0\u4ea4...",
  "home.beta.form.note": "\u63d0\u4ea4\u540e\u4f1a\u76f4\u63a5\u8fdb\u5165 AaronCore \u7684\u7b49\u5f85\u540d\u5355\u3002",
  "home.beta.form.success": "\u4f60\u5df2\u52a0\u5165\u7b49\u5f85\u540d\u5355\uff0c\u4e0b\u4e00\u6279\u5f00\u653e\u65f6 AaronCore \u4f1a\u4f18\u5148\u8054\u7cfb\u4f60\u3002",
  "home.beta.form.invalid": "\u8bf7\u68c0\u67e5\u90ae\u7bb1\u548c\u7528\u9014\u518d\u63d0\u4ea4\u3002",
  "home.beta.form.unavailable": "\u7b49\u5f85\u540d\u5355\u540e\u7aef\u8fd8\u6ca1\u6b63\u5f0f\u751f\u6548\uff0c\u73b0\u5728\u53ef\u4ee5\u5148\u53d1\u90ae\u4ef6\u5230 hello@aaroncore.com\u3002",
  "home.beta.form.error": "\u4fdd\u5b58\u62a5\u540d\u65f6\u51fa\u4e86\u70b9\u95ee\u9898\uff0c\u518d\u8bd5\u4e00\u6b21\u5427\u3002",
  "beta.title": "\u52a0\u5165 AaronCore \u5185\u6d4b",
  "beta.subtitle": "\u9996\u8f6e\u516c\u5f00\u5185\u6d4b\u6b63\u5728\u7b79\u5907\u4e2d\u3002\u4f60\u53ef\u4ee5\u5148\u7559\u4e0b\u90ae\u7bb1\uff0c\u4e0b\u4e00\u6279\u5f00\u653e\u65f6\u4f1a\u4f18\u5148\u8054\u7cfb\u4f60\u3002",
  "beta.status.h": "\u5f53\u524d\u5b89\u6392",
  "beta.status.p": "AaronCore \u8fd8\u6ca1\u6709\u5927\u8303\u56f4\u5f00\u653e\u5185\u6d4b\u3002\u73b0\u5728\u5148\u4ece\u7b49\u5f85\u540d\u5355\u5f00\u59cb\uff0c\u518d\u6309\u5c0f\u6279\u6b21\u53d1\u51fa\u9080\u8bf7\u3002",
  "beta.access.label": "\u5f00\u653e\u65b9\u5f0f",
  "beta.access.value": "\u5148\u52a0\u5165\u7b49\u5f85\u540d\u5355\uff0c\u9080\u8bf7\u4f1a\u6309\u5c0f\u6279\u6b21\u53d1\u51fa\u3002"
});

Object.assign(I18N.ja, {
  "cta.emailWaitlist": "\u30e1\u30fc\u30eb\u3067\u53c2\u52a0",
  "home.beta.h": "\u30d9\u30fc\u30bf\u53c2\u52a0\u3092\u53d7\u3051\u4ed8\u3051\u3066\u3044\u307e\u3059\u3002",
  "home.beta.p": "\u6700\u521d\u306e\u516c\u958b\u30d9\u30fc\u30bf\u306f\u307e\u3060\u6e96\u5099\u4e2d\u3067\u3059\u3002\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3092\u6b8b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\u6b21\u306e\u67a0\u304c\u958b\u3044\u305f\u3068\u304d\u306b\u3054\u9023\u7d61\u3057\u307e\u3059\u3002",
  "home.beta.state.label": "\u73fe\u5728\u306e\u72b6\u614b",
  "home.beta.state.value": "\u958b\u767a\u8005\u304c\u30d9\u30fc\u30bf\u3092\u7a4d\u6975\u7684\u306b\u6e96\u5099\u4e2d",
  "home.beta.inbox.label": "\u53d7\u4ed8\u30e1\u30fc\u30eb",
  "home.beta.form.label": "\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9",
  "home.beta.form.usecase.label": "AaronCore \u3092\u4f55\u306b\u4f7f\u3044\u305f\u3044\u3067\u3059\u304b\uff1f",
  "home.beta.form.usecase.placeholder": "\u7528\u9014\u3092\u9078\u3093\u3067\u304f\u3060\u3055\u3044",
  "home.beta.form.usecase.coding": "\u30b3\u30fc\u30c7\u30a3\u30f3\u30b0",
  "home.beta.form.usecase.research": "\u30ea\u30b5\u30fc\u30c1",
  "home.beta.form.usecase.writing": "\u30e9\u30a4\u30c6\u30a3\u30f3\u30b0",
  "home.beta.form.usecase.assistant": "\u65e5\u5e38\u30a2\u30b7\u30b9\u30bf\u30f3\u30c8",
  "home.beta.form.usecase.execution": "\u8907\u6570\u30b9\u30c6\u30c3\u30d7\u306e\u5b9f\u884c",
  "home.beta.form.usecase.memory": "\u9577\u671f\u8a18\u61b6\u30fb\u4f34\u8d70",
  "home.beta.form.usecase.other": "\u305d\u306e\u4ed6",
  "home.beta.form.submit": "\u30a6\u30a7\u30a4\u30c8\u30ea\u30b9\u30c8\u306b\u53c2\u52a0",
  "home.beta.form.submitting": "\u9001\u4fe1\u4e2d...",
  "home.beta.form.note": "\u9001\u4fe1\u3059\u308b\u3068 AaronCore \u306e\u30a6\u30a7\u30a4\u30c8\u30ea\u30b9\u30c8\u306b\u76f4\u63a5\u767b\u9332\u3055\u308c\u307e\u3059\u3002",
  "home.beta.form.success": "\u30a6\u30a7\u30a4\u30c8\u30ea\u30b9\u30c8\u306b\u767b\u9332\u3055\u308c\u307e\u3057\u305f\u3002\u6b21\u306e\u67a0\u304c\u958b\u3044\u305f\u3089 AaronCore \u304b\u3089\u3054\u9023\u7d61\u3057\u307e\u3059\u3002",
  "home.beta.form.invalid": "\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3068\u7528\u9014\u3092\u78ba\u8a8d\u3057\u3066\u3001\u3082\u3046\u4e00\u5ea6\u304a\u8a66\u3057\u304f\u3060\u3055\u3044\u3002",
  "home.beta.form.unavailable": "\u30a6\u30a7\u30a4\u30c8\u30ea\u30b9\u30c8\u306e\u53d7\u4ed8\u304c\u307e\u3060\u6709\u52b9\u306b\u306a\u3063\u3066\u3044\u307e\u305b\u3093\u3002\u73fe\u5728\u306f hello@aaroncore.com \u3078\u76f4\u63a5\u30e1\u30fc\u30eb\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
  "home.beta.form.error": "\u7533\u3057\u8fbc\u307f\u306e\u4fdd\u5b58\u4e2d\u306b\u554f\u984c\u304c\u767a\u751f\u3057\u307e\u3057\u305f\u3002\u3082\u3046\u4e00\u5ea6\u304a\u8a66\u3057\u304f\u3060\u3055\u3044\u3002",
  "beta.title": "AaronCore \u30d9\u30fc\u30bf\u306b\u53c2\u52a0",
  "beta.subtitle": "\u6700\u521d\u306e\u516c\u958b\u30d9\u30fc\u30bf\u306f\u73fe\u5728\u6e96\u5099\u4e2d\u3067\u3059\u3002\u30e1\u30fc\u30eb\u3092\u6b8b\u3057\u3066\u304f\u3060\u3055\u3044\u3002\u6b21\u306e\u67a0\u304c\u958b\u3044\u305f\u3068\u304d\u306b\u3054\u9023\u7d61\u3057\u307e\u3059\u3002",
  "beta.status.h": "\u73fe\u5728\u306e\u958b\u653e\u65b9\u91dd",
  "beta.status.p": "AaronCore \u306f\u307e\u3060\u5e83\u304f\u30d9\u30fc\u30bf\u3092\u958b\u653e\u3057\u3066\u3044\u307e\u305b\u3093\u3002\u307e\u305a\u30a6\u30a7\u30a4\u30c8\u30ea\u30b9\u30c8\u304b\u3089\u59cb\u3081\u3001\u5c0f\u3055\u306a\u67a0\u3067\u9806\u6b21\u62db\u5f85\u3057\u307e\u3059\u3002",
  "beta.access.label": "\u53c2\u52a0\u65b9\u6cd5",
  "beta.access.value": "\u307e\u305a\u30a6\u30a7\u30a4\u30c8\u30ea\u30b9\u30c8\u306b\u767b\u9332\u3057\u3001\u62db\u5f85\u306f\u5c0f\u3055\u306a\u67a0\u3054\u3068\u306b\u9001\u3089\u308c\u307e\u3059\u3002"
});

Object.assign(I18N.ko, {
  "cta.emailWaitlist": "\uba54\uc77c\ub85c \uc2e0\uccad",
  "home.beta.h": "\ubca0\ud0c0 \ucc38\uc5ec \uc900\ube44\uac00 \uc9c4\ud589 \uc911\uc785\ub2c8\ub2e4.",
  "home.beta.p": "\uccab \uacf5\uac1c \ubca0\ud0c0\ub294 \uc544\uc9c1 \uc900\ube44 \uc911\uc785\ub2c8\ub2e4. \uc774\uba54\uc77c\uc744 \ub0a8\uaca8 \uc8fc\uc2dc\uba74 \ub2e4\uc74c \ucc28\uc218\uac00 \uc5f4\ub9b4 \ub54c \uc5f0\ub77d\ub4dc\ub9ac\uaca0\uc2b5\ub2c8\ub2e4.",
  "home.beta.state.label": "\ud604\uc7ac \uc0c1\ud0dc",
  "home.beta.state.value": "\uac1c\ubc1c\uc790\uac00 \ubca0\ud0c0\ub97c \uc801\uadf9\uc801\uc73c\ub85c \uc900\ube44 \uc911",
  "home.beta.inbox.label": "\ub300\uae30\uc790 \uba54\uc77c",
  "home.beta.form.label": "\uc774\uba54\uc77c",
  "home.beta.form.usecase.label": "AaronCore\ub97c \ubb34\uc5c7\uc5d0 \uc4f0\uace0 \uc2f6\ub098\uc694?",
  "home.beta.form.usecase.placeholder": "\uc6a9\ub3c4\ub97c \uc120\ud0dd\ud558\uc138\uc694",
  "home.beta.form.usecase.coding": "\ucf54\ub529",
  "home.beta.form.usecase.research": "\ub9ac\uc11c\uce58",
  "home.beta.form.usecase.writing": "\uae00\uc4f0\uae30",
  "home.beta.form.usecase.assistant": "\uc77c\uc0c1 \uc5b4\uc2dc\uc2a4\ud134\ud2b8",
  "home.beta.form.usecase.execution": "\ub2e4\ub2e8\uacc4 \uc791\uc5c5 \uc2e4\ud589",
  "home.beta.form.usecase.memory": "\uc7a5\uae30 \uae30\uc5b5 / \ub3d9\ud589",
  "home.beta.form.usecase.other": "\uae30\ud0c0",
  "home.beta.form.submit": "\ub300\uae30 \uba85\ub2e8 \ucc38\uc5ec",
  "home.beta.form.submitting": "\uc81c\ucd9c \uc911...",
  "home.beta.form.note": "\uc81c\ucd9c\ud558\uba74 AaronCore \ub300\uae30 \uba85\ub2e8\uc5d0 \ubc14\ub85c \ub4f1\ub85d\ub429\ub2c8\ub2e4.",
  "home.beta.form.success": "\ub300\uae30 \uba85\ub2e8\uc5d0 \ub4f1\ub85d\ub418\uc5c8\uc2b5\ub2c8\ub2e4. \ub2e4\uc74c \ucc28\uc218\uac00 \uc5f4\ub9ac\uba74 AaronCore\uac00 \uc5f0\ub77d\ub4dc\ub9b4\uac8c\uc694.",
  "home.beta.form.invalid": "\uc774\uba54\uc77c\uacfc \uc6a9\ub3c4\ub97c \ud655\uc778\ud55c \ub4a4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.",
  "home.beta.form.unavailable": "\ub300\uae30 \uba85\ub2e8 \ubc31\uc5d4\ub4dc\uac00 \uc544\uc9c1 \ud65c\uc131\ud654\ub418\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4. \uc9c0\uae08\uc740 hello@aaroncore.com \uc73c\ub85c \uba3c\uc800 \uba54\uc77c \ubcf4\ub0b4 \uc8fc\uc138\uc694.",
  "home.beta.form.error": "\uc2e0\uccad\uc744 \uc800\uc7a5\ud558\ub294 \uc911 \ubb38\uc81c\uac00 \uc0dd\uacbc\uc2b5\ub2c8\ub2e4. \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694.",
  "beta.title": "AaronCore \ubca0\ud0c0 \ucc38\uc5ec",
  "beta.subtitle": "\uccab \uacf5\uac1c \ubca0\ud0c0\ub294 \ud604\uc7ac \uc900\ube44 \uc911\uc785\ub2c8\ub2e4. \uc774\uba54\uc77c\uc744 \ub0a8\uaca8 \uc8fc\uc2dc\uba74 \ub2e4\uc74c \ucc28\uc218\uac00 \uc5f4\ub9b4 \ub54c \uc5f0\ub77d\ub4dc\ub9ac\uaca0\uc2b5\ub2c8\ub2e4.",
  "beta.status.h": "\ud604\uc7ac \uc624\ud508 \ubc29\uc2dd",
  "beta.status.p": "AaronCore\ub294 \uc544\uc9c1 \ubca0\ud0c0\ub97c \ub113\uac8c \uc5f4\uc9c0 \uc54a\uace0 \uc788\uc2b5\ub2c8\ub2e4. \uba3c\uc800 \ub300\uae30 \uba85\ub2e8\uc73c\ub85c \uc2dc\uc791\ud558\uace0, \uc791\uc740 \ub2e8\uc704\ub85c \uc21c\ucc28 \ucd08\ub300\ud560 \uc608\uc815\uc785\ub2c8\ub2e4.",
  "beta.access.label": "\ucc38\uc5ec \ubc29\uc2dd",
  "beta.access.value": "\uba3c\uc800 \ub300\uae30 \uba85\ub2e8\uc5d0 \uc62c\ub77c\uac00\uace0, \ucd08\ub300\ub294 \uc791\uc740 \ub2e8\uc704\ub85c \uc21c\ucc28 \ubc1c\uc1a1\ub429\ub2c8\ub2e4."
});

Object.assign(I18N.en, {
  "product.subtitle": "AaronCore keeps memory live inside the runtime so recall, continuity, and remembered posture can show up during real work.",
  "product.proof.p": "The point is not storage by itself. The point is that earlier state can return in the same working thread.",
  "product.proof.side.h": "Designed to continue the thread, not replay the whole past",
  "product.proof.side.p": "Memory should return only where it helps: enough to move forward, verify, and stay in the same line of work.",
  "product.surface.h": "Four user-facing behaviors",
  "product.surface.p": "Once memory stays inside the runtime, the product reads as four visible behaviors instead of one vague memory claim.",
  "product.proof.flow.user.label": "User",
  "product.proof.flow.user.body": "Did that fix actually work?",
  "product.proof.flow.memory.label": "Memory",
  "product.proof.flow.memory.body": "Earlier repair state, changed files, and the last verification pass come back into scope.",
  "product.proof.flow.runtime.label": "Runtime",
  "product.proof.flow.runtime.body": "The loop keeps the active task, tool output, and blocker state attached instead of rebuilding the setup.",
  "product.proof.flow.reply.label": "AaronCore",
  "product.proof.flow.reply.body": "Yes. The repair path stayed live, so the answer can continue the same thread and point to what changed.",
  "changelog.title": "Changelog",
  "changelog.subtitle": "A short record of what changed on the site, the access path, and the public product surface.",
  "changelog.r1.h": "Official site launch",
  "changelog.r1.p": "The official site is now live, followed by a round of copy, structure, and access-flow refinements.",
  "changelog.r2.h": "Homepage and runtime story tightened",
  "changelog.r2.p": "The landing page now leans harder on runtime flow, token savings, and a calmer visual hierarchy.",
  "changelog.r3.h": "Waitlist-first beta access",
  "changelog.r3.p": "Beta access now starts from a dedicated waitlist page while the direct download path stays closed."
});

Object.assign(I18N.zh, {
  "product.subtitle": "AaronCore 让记忆持续留在运行时里，让回忆、连续性和交流姿态能在真实工作里直接出现。",
  "product.proof.p": "重点不是单独存下来了什么，而是更早的状态能不能在同一条工作线程里回来。",
  "product.proof.side.h": "目标是把线程续上，不是把过去整段重放一遍",
  "product.proof.side.p": "记忆只该在有帮助的时候回来: 够继续推进、够做验证，也够留在同一条工作线上。",
  "product.surface.h": "四种对用户可见的表现",
  "product.surface.p": "当记忆真正留在运行时里，产品读起来就会变成四种明确行为，而不是一句模糊的“我会记住你”。",
  "product.proof.flow.user.label": "用户",
  "product.proof.flow.user.body": "那个修复后来真的生效了吗？",
  "product.proof.flow.memory.label": "记忆",
  "product.proof.flow.memory.body": "更早的修复状态、改动过的文件，以及上一次验证结果一起被拉回当前范围。",
  "product.proof.flow.runtime.label": "运行时",
  "product.proof.flow.runtime.body": "这条链路会继续挂住当前任务、工具输出和阻塞状态，而不是重新把前情搭一遍。",
  "product.proof.flow.reply.label": "AaronCore",
  "product.proof.flow.reply.body": "生效了。因为修复路径一直是连着的，所以现在可以沿着同一条线程继续回答，并把改动点指出来。",
  "changelog.title": "更新记录",
  "changelog.subtitle": "",
  "changelog.r1.h": "官方网站上线",
  "changelog.r1.p": "官方网站现已上线，随后对页面文案、结构和访问体验做了一轮优化。",
  "changelog.r2.h": "首页和运行时叙事收紧",
  "changelog.r2.p": "首页现在更集中在运行时链路、token 节省和更克制的视觉层级上。",
  "changelog.r3.h": "先走等待名单的内测入口",
  "changelog.r3.p": "内测访问现在从独立等待名单页进入，直接下载路径继续保持关闭。"
});

Object.assign(I18N.ja, {
  "product.subtitle": "AaronCore は記憶をランタイムの中に保持し、想起、連続性、会話姿勢が実際の作業の中で現れるようにします。",
  "product.proof.p": "重要なのは単なる保存ではなく、以前の状態が同じ作業スレッドの中に戻ってこられることです。",
  "product.proof.side.h": "過去を丸ごと再生するのではなく、同じスレッドを続けるための設計",
  "product.proof.side.p": "記憶は必要な場面でだけ戻ればいい。前に進み、検証し、同じ仕事の流れに留まれるだけで十分です。",
  "product.surface.h": "ユーザーに見える四つの振る舞い",
  "product.surface.p": "記憶がランタイムの中に留まると、製品は曖昧な約束ではなく四つの具体的な振る舞いとして読めます。",
  "product.proof.flow.user.label": "User",
  "product.proof.flow.user.body": "その修正、本当に効いていた？",
  "product.proof.flow.memory.label": "Memory",
  "product.proof.flow.memory.body": "先の修正状態、変更ファイル、直前の検証結果がいまの文脈に戻ってきます。",
  "product.proof.flow.runtime.label": "Runtime",
  "product.proof.flow.runtime.body": "このループは現在のタスク、ツール出力、ブロッカー状態を保持し、前提を組み直しません。",
  "product.proof.flow.reply.label": "AaronCore",
  "product.proof.flow.reply.body": "効いています。修正経路が生きたままなので、同じスレッドを続けながら何が変わったかまで答えられます。",
  "changelog.title": "公開変更履歴",
  "changelog.subtitle": "サイト、アクセス導線、公開プロダクト面で変わったことを短く記録します。",
  "changelog.r1.h": "研究、製品、更新を分離",
  "changelog.r1.p": "公開サイトをより明快なページに分け、それぞれが一つの役割を持つようにしました。",
  "changelog.r2.h": "ホームとランタイム叙述を整理",
  "changelog.r2.p": "ホームはランタイムの流れ、トークン節約、落ち着いた視覚階層により集中する構成になりました。",
  "changelog.r3.h": "ウェイトリスト先行のベータ導線",
  "changelog.r3.p": "ベータ参加は専用のウェイトリストページから始まり、直接ダウンロードはまだ閉じています。"
});

Object.assign(I18N.ko, {
  "product.subtitle": "AaronCore는 기억을 런타임 안에 살아 있게 두어 회상, 연속성, 대화 자세가 실제 작업 중에 드러나게 합니다.",
  "product.proof.p": "중요한 것은 단순 저장이 아니라, 더 이른 상태가 같은 작업 흐름 안으로 다시 돌아올 수 있는가입니다.",
  "product.proof.side.h": "과거 전체를 다시 재생하는 것이 아니라 같은 스레드를 이어 가기 위한 설계",
  "product.proof.side.p": "기억은 도움이 되는 지점에서만 돌아오면 됩니다. 앞으로 나아가고, 검증하고, 같은 작업선에 머물 수 있을 만큼이면 충분합니다.",
  "product.surface.h": "사용자에게 보이는 네 가지 동작",
  "product.surface.p": "기억이 런타임 안에 머물면, 제품은 막연한 약속이 아니라 네 가지 분명한 동작으로 읽히게 됩니다.",
  "product.proof.flow.user.label": "User",
  "product.proof.flow.user.body": "그 수정, 결국 제대로 먹혔어?",
  "product.proof.flow.memory.label": "Memory",
  "product.proof.flow.memory.body": "이전의 수정 상태, 바뀐 파일, 마지막 검증 결과가 현재 범위로 다시 돌아옵니다.",
  "product.proof.flow.runtime.label": "Runtime",
  "product.proof.flow.runtime.body": "이 루프는 현재 작업, 도구 출력, 막힘 상태를 붙들고 있어서 전제를 다시 깔지 않습니다.",
  "product.proof.flow.reply.label": "AaronCore",
  "product.proof.flow.reply.body": "네, 먹혔습니다. 수정 경로가 계속 살아 있었기 때문에 같은 스레드를 이어 가면서 무엇이 바뀌었는지도 짚을 수 있습니다.",
  "changelog.title": "공개 변경 기록",
  "changelog.subtitle": "사이트, 접근 경로, 공개 제품 표면에서 달라진 점을 짧게 기록합니다.",
  "changelog.r1.h": "연구, 제품, 변경 기록 분리",
  "changelog.r1.p": "공개 사이트를 더 분명한 페이지로 나누어 각 페이지가 한 가지 역할만 맡도록 정리했습니다.",
  "changelog.r2.h": "홈페이지와 런타임 서사 정리",
  "changelog.r2.p": "홈페이지는 이제 런타임 흐름, 토큰 절감, 더 차분한 시각 계층에 더 집중합니다.",
  "changelog.r3.h": "대기 명단 우선 베타 접근",
  "changelog.r3.p": "베타 접근은 전용 대기 명단 페이지에서 시작하고, 직접 다운로드 경로는 아직 닫혀 있습니다."
});

Object.assign(I18N.en, {
  "product.title": "AaronCore",
  "product.subtitle": "Memory, state, and action stay in the same thread.",
  "product.scope.h": "What AaronCore actually owns",
  "product.scope.p": "The model is still the model. AaronCore sits above it and owns the part users actually feel over time: memory, runtime state, routing, and execution flow.",
  "product.scope.note.label": "Current posture",
  "product.scope.note.h": "Bring your own model. AaronCore handles the agent layer.",
  "product.scope.note.p": "The product is not the base model itself. It is the layer that remembers, carries work forward, chooses the right surface, and returns checked results.",
  "product.scope.memory.h": "Memory that stays with the thread",
  "product.scope.memory.p": "Useful past context, preference, and relationship posture stay attached, so the user does not have to restate the same background every time.",
  "product.scope.state.h": "Runtime state that survives the last turn",
  "product.scope.state.p": "Current task, recent action, tool output, blocker, and next step can stay alive instead of being rebuilt from the transcript.",
  "product.scope.execution.h": "Routing and execution that can actually move work",
  "product.scope.execution.p": "AaronCore decides when a turn needs recall, conversation, tool use, or a direct next action, then keeps that path moving.",
  "product.scope.verify.h": "Verification before it calls something done",
  "product.scope.verify.p": "The loop should close with a checked result, not just a confident sentence. That is part of the product, not an afterthought.",
  "product.surface.h": "Where it already helps",
  "product.surface.p": "The public surface is still compact. These are the jobs AaronCore is already being shaped around.",
  "product.use.memory.h": "Long-term memory and companionship",
  "product.use.memory.p": "Conversations can keep their background, emotional posture, and personal context instead of feeling like a reset every day.",
  "product.use.coding.h": "Coding",
  "product.use.coding.p": "Task state, changed files, blockers, and verification can remain attached so code work can continue across turns instead of being re-explained.",
  "product.use.research.h": "Research and recall",
  "product.use.research.p": "You can ask what was discussed today, yesterday, or last week without manually rebuilding the context every time.",
  "product.use.writing.h": "Writing and daily assistance",
  "product.use.writing.p": "Style, preference, and the ongoing line of work can stay steady, which makes ordinary help feel less disposable.",
  "product.use.execution.h": "Multi-step execution",
  "product.use.execution.p": "AaronCore is being shaped for work that has to continue across routing, tool use, repair, and final verification instead of ending at one answer."
});

Object.assign(I18N.zh, {
  "product.title": "AaronCore",
  "product.subtitle": "\u8ba9\u8bb0\u5fc6\u3001\u72b6\u6001\u548c\u6267\u884c\u7559\u5728\u540c\u4e00\u6761\u7ebf\u7a0b\u91cc\u3002",
  "product.scope.h": "AaronCore \u771f\u6b63\u8d1f\u8d23\u7684\u662f\u4ec0\u4e48",
  "product.scope.p": "\u6a21\u578b\u8fd8\u662f\u6a21\u578b\u3002AaronCore \u5728\u5b83\u4e4b\u4e0a\uff0c\u8d1f\u8d23\u7528\u6237\u4f1a\u957f\u671f\u611f\u53d7\u5230\u7684\u90a3\u4e00\u5c42\uff1a\u8bb0\u5fc6\u3001\u8fd0\u884c\u65f6\u72b6\u6001\u3001\u5206\u6d41\u548c\u6267\u884c\u94fe\u8def\u3002",
  "product.scope.note.label": "\u5f53\u524d\u59ff\u6001",
  "product.scope.note.h": "\u6a21\u578b\u4f60\u81ea\u5df1\u63a5\u3002AaronCore \u8d1f\u8d23 agent \u8fd9\u4e00\u5c42\u3002",
  "product.scope.note.p": "\u8fd9\u4e2a\u4ea7\u54c1\u5356\u7684\u4e0d\u662f\u5e95\u5c42\u6a21\u578b\u672c\u8eab\uff0c\u800c\u662f\u90a3\u5c42\u4f1a\u8bb0\u4f4f\u3001\u4f1a\u7eed\u4e0a\u5de5\u4f5c\u3001\u4f1a\u9009\u5bf9\u754c\u9762\uff0c\u4e5f\u4f1a\u628a\u7ed3\u679c\u9a8c\u5b8c\u518d\u4ea4\u56de\u6765\u7684 agent \u673a\u5236\u3002",
  "product.scope.memory.h": "\u8bb0\u5fc6\u4f1a\u8ddf\u7740\u8fd9\u6761\u7ebf\u7a0b\u4e00\u76f4\u5728",
  "product.scope.memory.p": "\u6709\u7528\u7684\u524d\u60c5\u3001\u504f\u597d\u548c\u5173\u7cfb\u59ff\u6001\u4f1a\u7ee7\u7eed\u6302\u7740\uff0c\u7528\u6237\u4e0d\u7528\u6bcf\u6b21\u90fd\u628a\u540c\u4e00\u6bb5\u80cc\u666f\u91cd\u65b0\u8bb2\u4e00\u904d\u3002",
  "product.scope.state.h": "\u8fd0\u884c\u65f6\u72b6\u6001\u4e0d\u4f1a\u8ddf\u7740\u4e0a\u4e00\u8f6e\u4e00\u8d77\u6d88\u5931",
  "product.scope.state.p": "\u5f53\u524d\u4efb\u52a1\u3001\u6700\u8fd1\u52a8\u4f5c\u3001\u5de5\u5177\u8f93\u51fa\u3001\u963b\u585e\u70b9\u548c\u4e0b\u4e00\u6b65\u90fd\u80fd\u7ee7\u7eed\u6d3b\u7740\uff0c\u800c\u4e0d\u662f\u518d\u4ece\u5bf9\u8bdd\u8bb0\u5f55\u91cc\u91cd\u642d\u4e00\u6b21\u3002",
  "product.scope.execution.h": "\u5206\u6d41\u548c\u6267\u884c\u771f\u7684\u80fd\u628a\u5de5\u4f5c\u5f80\u524d\u63a8",
  "product.scope.execution.p": "AaronCore \u4f1a\u5224\u65ad\u8fd9\u4e00\u8f6e\u8be5\u8d70\u56de\u5fc6\u3001\u5bf9\u8bdd\u3001\u5de5\u5177\u8fd8\u662f\u76f4\u63a5\u884c\u52a8\uff0c\u7136\u540e\u628a\u90a3\u6761\u8def\u5f84\u7ee7\u7eed\u63a8\u8fdb\u3002",
  "product.scope.verify.h": "\u4e0d\u662f\u5148\u8bf4\u5b8c\u6210\uff0c\u800c\u662f\u5148\u505a\u9a8c\u8bc1",
  "product.scope.verify.p": "\u4e00\u4e2a\u56de\u5408\u5e94\u8be5\u4ee5\u9a8c\u8bc1\u8fc7\u7684\u7ed3\u679c\u6536\u5c3e\uff0c\u800c\u4e0d\u662f\u53ea\u5269\u4e0b\u4e00\u53e5\u5f88\u6709\u628a\u63e1\u7684\u8bdd\u3002\u8fd9\u4e5f\u662f\u4ea7\u54c1\u7684\u4e00\u90e8\u5206\u3002",
  "product.surface.h": "\u5b83\u73b0\u5728\u5df2\u7ecf\u9002\u5408\u505a\u4ec0\u4e48",
  "product.surface.p": "\u516c\u5f00\u8868\u9762\u8fd8\u4e0d\u5927\uff0c\u4f46 AaronCore \u5df2\u7ecf\u5728\u671d\u8fd9\u4e9b\u4efb\u52a1\u5f62\u6001\u6301\u7eed\u6536\u62e2\u3002",
  "product.use.memory.h": "\u957f\u671f\u8bb0\u5fc6 / \u966a\u4f34",
  "product.use.memory.p": "\u5bf9\u8bdd\u53ef\u4ee5\u4fdd\u7559\u80cc\u666f\u3001\u60c5\u7eea\u59ff\u6001\u548c\u4e2a\u4eba\u4e0a\u4e0b\u6587\uff0c\u800c\u4e0d\u662f\u6bcf\u5929\u90fd\u50cf\u91cd\u65b0\u8ba4\u8bc6\u4e00\u904d\u3002",
  "product.use.coding.h": "\u5199\u4ee3\u7801",
  "product.use.coding.p": "\u4efb\u52a1\u72b6\u6001\u3001\u6539\u52a8\u8fc7\u7684\u6587\u4ef6\u3001\u963b\u585e\u70b9\u548c\u9a8c\u8bc1\u7ed3\u679c\u53ef\u4ee5\u4e00\u76f4\u6302\u7740\uff0c\u4ee3\u7801\u5de5\u4f5c\u4e0d\u7528\u4e00\u8f6e\u8f6e\u91cd\u65b0\u89e3\u91ca\u3002",
  "product.use.research.h": "\u7814\u7a76 / \u56de\u5fc6",
  "product.use.research.p": "\u4f60\u53ef\u4ee5\u76f4\u63a5\u95ee\u4eca\u5929\u3001\u6628\u5929\u6216\u4e0a\u5468\u804a\u8fc7\u4ec0\u4e48\uff0c\u4e0d\u7528\u6bcf\u6b21\u90fd\u624b\u52a8\u628a\u4e0a\u4e0b\u6587\u518d\u62fc\u8d77\u6765\u3002",
  "product.use.writing.h": "\u5199\u4f5c / \u65e5\u5e38\u8f85\u52a9",
  "product.use.writing.p": "\u98ce\u683c\u3001\u504f\u597d\u548c\u6b63\u5728\u505a\u7684\u7ebf\u7d22\u80fd\u4fdd\u6301\u7a33\u5b9a\uff0c\u6240\u4ee5\u666e\u901a\u5e2e\u52a9\u4e5f\u4e0d\u4f1a\u663e\u5f97\u4e00\u6b21\u6027\u3002",
  "product.use.execution.h": "\u591a\u6b65\u9aa4\u4efb\u52a1\u6267\u884c",
  "product.use.execution.p": "AaronCore \u6b63\u5728\u88ab\u6253\u78e8\u6210\u80fd\u8de8\u5206\u6d41\u3001\u5de5\u5177\u8c03\u7528\u3001\u4fee\u590d\u548c\u6700\u7ec8\u9a8c\u8bc1\u4e00\u8def\u8d70\u5b8c\u7684\u7cfb\u7edf\uff0c\u800c\u4e0d\u662f\u505c\u5728\u4e00\u53e5\u56de\u7b54\u3002"
});

Object.assign(I18N.ja, {
  "product.title": "AaronCore",
  "product.subtitle": "\u8a18\u61b6\u3001\u72b6\u614b\u3001\u5b9f\u884c\u3092\u540c\u3058\u30b9\u30ec\u30c3\u30c9\u306b\u7559\u3081\u308b\u3002",
  "product.scope.h": "AaronCore \u304c\u5b9f\u969b\u306b\u62c5\u3046\u3082\u306e",
  "product.scope.p": "\u30e2\u30c7\u30eb\u306f\u3042\u304f\u307e\u3067\u30e2\u30c7\u30eb\u3067\u3059\u3002AaronCore \u306f\u305d\u306e\u4e0a\u3067\u3001\u30e6\u30fc\u30b6\u30fc\u304c\u6642\u9593\u3092\u304b\u3051\u3066\u4f53\u611f\u3059\u308b\u5c64\u3001\u3064\u307e\u308a\u8a18\u61b6\u3001\u30e9\u30f3\u30bf\u30a4\u30e0\u72b6\u614b\u3001\u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u3001\u5b9f\u884c\u30d5\u30ed\u30fc\u3092\u62c5\u3044\u307e\u3059\u3002",
  "product.scope.note.label": "\u73fe\u5728\u306e\u59ff\u52e2",
  "product.scope.note.h": "\u30e2\u30c7\u30eb\u306f\u6301\u3061\u8fbc\u307f\u3002AaronCore \u304c agent \u30ec\u30a4\u30e4\u30fc\u3092\u62c5\u3044\u307e\u3059\u3002",
  "product.scope.note.p": "\u3053\u306e\u88fd\u54c1\u304c\u58f2\u308b\u306e\u306f\u57fa\u76e4\u30e2\u30c7\u30eb\u305d\u306e\u3082\u306e\u3067\u306f\u306a\u304f\u3001\u8a18\u61b6\u3057\u3001\u4f5c\u696d\u3092\u5f15\u304d\u7d99\u304e\u3001\u9069\u5207\u306a\u9762\u3092\u9078\u3073\u3001\u691c\u8a3c\u6e08\u307f\u306e\u7d50\u679c\u3092\u8fd4\u3059 agent \u306e\u4ed5\u7d44\u307f\u3067\u3059\u3002",
  "product.scope.memory.h": "\u30b9\u30ec\u30c3\u30c9\u306b\u6b8b\u308a\u7d9a\u3051\u308b\u8a18\u61b6",
  "product.scope.memory.p": "\u6709\u7528\u306a\u904e\u53bb\u306e\u6587\u8108\u3001\u597d\u307f\u3001\u95a2\u4fc2\u59ff\u52e2\u304c\u6b8b\u308b\u306e\u3067\u3001\u540c\u3058\u80cc\u666f\u3092\u6bce\u56de\u8a00\u3044\u76f4\u3059\u5fc5\u8981\u304c\u3042\u308a\u307e\u305b\u3093\u3002",
  "product.scope.state.h": "\u524d\u306e\u30bf\u30fc\u30f3\u3067\u6d88\u3048\u306a\u3044\u30e9\u30f3\u30bf\u30a4\u30e0\u72b6\u614b",
  "product.scope.state.p": "\u73fe\u5728\u306e\u30bf\u30b9\u30af\u3001\u76f4\u524d\u306e\u884c\u52d5\u3001\u30c4\u30fc\u30eb\u51fa\u529b\u3001\u30d6\u30ed\u30c3\u30ab\u30fc\u3001\u6b21\u306e\u4e00\u624b\u304c\u3001\u5c65\u6b74\u304b\u3089\u7d44\u307f\u76f4\u3055\u306a\u304f\u3066\u3082\u751f\u304d\u7d9a\u3051\u307e\u3059\u3002",
  "product.scope.execution.h": "\u5b9f\u969b\u306b\u4ed5\u4e8b\u3092\u9032\u3081\u308b\u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u3068\u5b9f\u884c",
  "product.scope.execution.p": "\u3053\u306e\u30bf\u30fc\u30f3\u3067\u60f3\u8d77\u3001\u4f1a\u8a71\u3001\u30c4\u30fc\u30eb\u3001\u76f4\u63a5\u884c\u52d5\u306e\u3069\u308c\u304c\u5fc5\u8981\u304b\u3092\u5224\u65ad\u3057\u3001\u305d\u306e\u7d4c\u8def\u3092\u7d99\u7d9a\u3057\u3066\u9032\u3081\u307e\u3059\u3002",
  "product.scope.verify.h": "\u5b8c\u4e86\u3068\u547c\u3076\u524d\u306b\u691c\u8a3c\u3059\u308b",
  "product.scope.verify.p": "\u30eb\u30fc\u30d7\u306f\u81ea\u4fe1\u306e\u3042\u308b\u4e00\u6587\u3067\u306f\u306a\u304f\u3001\u78ba\u8a8d\u6e08\u307f\u306e\u7d50\u679c\u3067\u9589\u3058\u308b\u3079\u304d\u3067\u3059\u3002\u305d\u308c\u3082\u88fd\u54c1\u306e\u4e00\u90e8\u3067\u3059\u3002",
  "product.surface.h": "\u3044\u307e\u65e2\u306b\u5f79\u7acb\u3064\u5834\u6240",
  "product.surface.p": "\u516c\u958b\u3055\u308c\u3066\u3044\u308b\u9762\u306f\u307e\u3060\u5c0f\u3055\u3044\u3067\u3059\u304c\u3001AaronCore \u306f\u3059\u3067\u306b\u3053\u308c\u3089\u306e\u4ed5\u4e8b\u306b\u5411\u3051\u3066\u5f62\u3092\u6574\u3048\u3066\u3044\u307e\u3059\u3002",
  "product.use.memory.h": "\u9577\u671f\u8a18\u61b6 / \u4f34\u8d70",
  "product.use.memory.p": "\u4f1a\u8a71\u306e\u80cc\u666f\u3001\u611f\u60c5\u306e\u59ff\u52e2\u3001\u500b\u4eba\u7684\u306a\u6587\u8108\u3092\u4fdd\u3066\u308b\u306e\u3067\u3001\u6bce\u65e5\u30ea\u30bb\u30c3\u30c8\u3055\u308c\u305f\u3088\u3046\u306b\u611f\u3058\u307e\u305b\u3093\u3002",
  "product.use.coding.h": "\u30b3\u30fc\u30c7\u30a3\u30f3\u30b0",
  "product.use.coding.p": "\u30bf\u30b9\u30af\u72b6\u614b\u3001\u5909\u66f4\u30d5\u30a1\u30a4\u30eb\u3001\u30d6\u30ed\u30c3\u30ab\u30fc\u3001\u691c\u8a3c\u7d50\u679c\u304c\u3076\u3089\u4e0b\u304c\u3063\u305f\u307e\u307e\u306a\u306e\u3067\u3001\u30b3\u30fc\u30c9\u4f5c\u696d\u3092\u6bce\u30bf\u30fc\u30f3\u8aac\u660e\u3057\u76f4\u3055\u305a\u306b\u6e08\u307f\u307e\u3059\u3002",
  "product.use.research.h": "\u30ea\u30b5\u30fc\u30c1 / \u60f3\u8d77",
  "product.use.research.p": "\u4eca\u65e5\u3001\u6628\u65e5\u3001\u5148\u9031\u306b\u8a71\u3057\u305f\u3053\u3068\u3092\u3001\u6bce\u56de\u6587\u8108\u3092\u7d44\u307f\u76f4\u3055\u305a\u306b\u5c0b\u306d\u3089\u308c\u307e\u3059\u3002",
  "product.use.writing.h": "\u57f7\u7b46 / \u65e5\u5e38\u88dc\u52a9",
  "product.use.writing.p": "\u6587\u4f53\u3001\u597d\u307f\u3001\u9032\u884c\u4e2d\u306e\u4f5c\u696d\u7dda\u304c\u5b89\u5b9a\u3059\u308b\u305f\u3081\u3001\u65e5\u5e38\u7684\u306a\u88dc\u52a9\u3082\u4f7f\u3044\u6368\u3066\u307d\u304f\u306a\u308a\u307e\u305b\u3093\u3002",
  "product.use.execution.h": "\u8907\u6570\u30b9\u30c6\u30c3\u30d7\u306e\u5b9f\u884c",
  "product.use.execution.p": "AaronCore \u306f\u3001\u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u3001\u30c4\u30fc\u30eb\u547c\u3073\u51fa\u3057\u3001\u4fee\u5fa9\u3001\u6700\u7d42\u691c\u8a3c\u307e\u3067\u3092\u4e00\u7d9a\u304d\u3067\u9032\u3081\u308b\u4ed5\u4e8b\u306e\u305f\u3081\u306b\u78e8\u304b\u308c\u3066\u3044\u307e\u3059\u3002"
});

Object.assign(I18N.ko, {
  "product.title": "AaronCore",
  "product.subtitle": "\uae30\uc5b5, \uc0c1\ud0dc, \uc2e4\ud589\uc744 \uac19\uc740 \uc2a4\ub808\ub4dc\uc5d0 \ub0a8\uaca8 \ub461\ub2c8\ub2e4.",
  "product.scope.h": "AaronCore\uac00 \uc2e4\uc81c\ub85c \ub9e1\ub294 \uac83",
  "product.scope.p": "\ubaa8\ub378\uc740 \uc5ec\uc804\ud788 \ubaa8\ub378\uc785\ub2c8\ub2e4. AaronCore\ub294 \uadf8 \uc704\uc5d0\uc11c \uc0ac\uc6a9\uc790\uac00 \uc2dc\uac04\uc774 \uc9c0\ub098\uba70 \uccb4\uac10\ud558\ub294 \uce35, \uc989 \uae30\uc5b5, \ub7f0\ud0c0\uc784 \uc0c1\ud0dc, \ub77c\uc6b0\ud305, \uc2e4\ud589 \ud750\ub984\uc744 \ub9e1\uc2b5\ub2c8\ub2e4.",
  "product.scope.note.label": "\ud604\uc7ac \ud3ec\uc9c0\uc158",
  "product.scope.note.h": "\ubaa8\ub378\uc740 \uc9c1\uc811 \uc5f0\uacb0\ud558\uace0, AaronCore\uac00 agent \ub808\uc774\uc5b4\ub97c \ub9e1\uc2b5\ub2c8\ub2e4.",
  "product.scope.note.p": "\uc774 \uc81c\ud488\uc774 \ud30c\ub294 \uac83\uc740 \uae30\ubc18 \ubaa8\ub378 \uc790\uccb4\uac00 \uc544\ub2c8\ub77c, \uae30\uc5b5\ud558\uace0, \uc77c\uc744 \uc774\uc5b4 \uc8fc\uace0, \ub9de\ub294 \ud45c\uba74\uc744 \uace0\ub974\uace0, \uac80\uc99d\ub41c \uacb0\uacfc\ub97c \ub3cc\ub824\uc8fc\ub294 agent \uba54\ucee4\ub2c8\uc998\uc785\ub2c8\ub2e4.",
  "product.scope.memory.h": "\uc2a4\ub808\ub4dc\uc5d0 \ubd99\uc5b4 \uc788\ub294 \uae30\uc5b5",
  "product.scope.memory.p": "\uc720\uc6a9\ud55c \uacfc\uac70 \ub9e5\ub77d, \uc120\ud638, \uad00\uacc4 \uc790\uc138\uac00 \ubd99\uc5b4 \uc788\uc5b4\uc11c \uac19\uc740 \ubc30\uacbd\uc744 \ub9e4\ubc88 \ub2e4\uc2dc \uc124\uba85\ud558\uc9c0 \uc54a\uc544\ub3c4 \ub429\ub2c8\ub2e4.",
  "product.scope.state.h": "\uc774\uc804 \ud134\uc5d0\uc11c \uc0ac\ub77c\uc9c0\uc9c0 \uc54a\ub294 \ub7f0\ud0c0\uc784 \uc0c1\ud0dc",
  "product.scope.state.p": "\ud604\uc7ac \uc791\uc5c5, \ucd5c\uadfc \ud589\ub3d9, \ub3c4\uad6c \ucd9c\ub825, \ub9c9\ud798, \ub2e4\uc74c \ub2e8\uacc4\uac00 \ub300\ud654 \uae30\ub85d\uc5d0\uc11c \ub2e4\uc2dc \uc870\ub9bd\ub418\uc9c0 \uc54a\uace0 \uadf8\ub300\ub85c \uc0b4\uc544 \uc788\uc2b5\ub2c8\ub2e4.",
  "product.scope.execution.h": "\uc2e4\uc81c\ub85c \uc77c\uc744 \uc6c0\uc9c1\uc774\ub294 \ub77c\uc6b0\ud305\uacfc \uc2e4\ud589",
  "product.scope.execution.p": "\uc774\ubc88 \ud134\uc774 \ud68c\uc0c1, \ub300\ud654, \ub3c4\uad6c \uc0ac\uc6a9, \uc9c1\uc811 \ud589\ub3d9 \uc911 \ubb34\uc5c7\uc744 \ud544\uc694\ub85c \ud558\ub294\uc9c0 \ud310\ub2e8\ud558\uace0 \uadf8 \uacbd\ub85c\ub97c \uacc4\uc18d \ubc00\uc5b4 \uac11\ub2c8\ub2e4.",
  "product.scope.verify.h": "\ub05d\ub0ac\ub2e4\uace0 \ub9d0\ud558\uae30 \uc804\uc5d0 \uac80\uc99d",
  "product.scope.verify.p": "\ub8e8\ud504\ub294 \uc790\uc2e0\uac10 \uc788\ub294 \ubb38\uc7a5 \ud558\ub098\uac00 \uc544\ub2c8\ub77c \ud655\uc778\ub41c \uacb0\uacfc\ub85c \ub2eb\ud600\uc57c \ud569\ub2c8\ub2e4. \uc774\uac83\ub3c4 \uc81c\ud488\uc758 \uc77c\ubd80\uc785\ub2c8\ub2e4.",
  "product.surface.h": "\uc9c0\uae08 \uc774\ubbf8 \ub3c4\uc6c0\uc774 \ub418\ub294 \uacf3",
  "product.surface.p": "\uacf5\uac1c\ub41c \ud45c\uba74\uc740 \uc544\uc9c1 \uc791\uc9c0\ub9cc, AaronCore\ub294 \uc774\ubbf8 \uc774\ub7f0 \uc791\uc5c5 \ud615\ud0dc\ub97c \ud5a5\ud574 \ub2e4\ub4ec\uc5b4\uc9c0\uace0 \uc788\uc2b5\ub2c8\ub2e4.",
  "product.use.memory.h": "\uc7a5\uae30 \uae30\uc5b5 / \ub3d9\ud589",
  "product.use.memory.p": "\ub300\ud654\uac00 \ubc30\uacbd, \uac10\uc815\uc758 \uc790\uc138, \uac1c\uc778 \ub9e5\ub77d\uc744 \uc720\uc9c0\ud560 \uc218 \uc788\uc5b4\uc11c \ub9e4\uc77c \uc0c8\ub85c \uc2dc\uc791\ud558\ub294 \ub290\ub08c\uc774 \uc904\uc5b4\ub4ed\ub2c8\ub2e4.",
  "product.use.coding.h": "\ucf54\ub529",
  "product.use.coding.p": "\uc791\uc5c5 \uc0c1\ud0dc, \ubc14\ub010 \ud30c\uc77c, \ub9c9\ud798, \uac80\uc99d \uacb0\uacfc\uac00 \uacc4\uc18d \ubd99\uc5b4 \uc788\uc5b4 \ucf54\ub4dc \uc791\uc5c5\uc744 \ud134\ub9c8\ub2e4 \ub2e4\uc2dc \uc124\uba85\ud560 \ud544\uc694\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
  "product.use.research.h": "\ub9ac\uc11c\uce58 / \ud68c\uc0c1",
  "product.use.research.p": "\uc624\ub298, \uc5b4\uc81c, \uc9c0\ub09c\uc8fc\uc5d0 \ubb34\uc5c7\uc744 \uc774\uc57c\uae30\ud588\ub294\uc9c0 \ub9e4\ubc88 \ubb38\ub9e5\uc744 \ub2e4\uc2dc \ub9cc\ub4e4\uc9c0 \uc54a\uace0 \ubb3c\uc5b4\ubcfc \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
  "product.use.writing.h": "\uae00\uc4f0\uae30 / \uc77c\uc0c1 \ubcf4\uc870",
  "product.use.writing.p": "\ubb38\uccb4, \uc120\ud638, \uc9c4\ud589 \uc911\uc778 \uc791\uc5c5\uc120\uc774 \uc548\uc815\uc801\uc73c\ub85c \uc720\uc9c0\ub418\uc5b4 \uc77c\uc0c1\uc801\uc778 \ub3c4\uc6c0\ub3c4 \uc77c\ud68c\uc6a9\ucc98\ub7fc \ub290\uaef4\uc9c0\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
  "product.use.execution.h": "\ub2e4\ub2e8\uacc4 \uc791\uc5c5 \uc2e4\ud589",
  "product.use.execution.p": "AaronCore\ub294 \ub77c\uc6b0\ud305, \ub3c4\uad6c \ud638\ucd9c, \uc218\ub9ac, \ucd5c\uc885 \uac80\uc99d\uae4c\uc9c0 \ud55c \ud750\ub984\uc73c\ub85c \uc774\uc5b4\uc9c0\ub294 \uc791\uc5c5\uc744 \uc704\ud574 \ub2e4\ub4ec\uc5b4\uc9c0\uace0 \uc788\uc2b5\ub2c8\ub2e4."
});

Object.assign(I18N.en, {
  "home.diff.c3": "Continuity stays intact without repeated reloads.",
  "home.diff.c3.p": "The lighter the context becomes, the more seamlessly tool calls, task state, and verification can carry forward, without replaying the same setup."
});

Object.assign(I18N.zh, {
  "home.diff.h": "\u8bb0\u5fc6\u6c38\u7eed\uff0c\u8282\u7701 Tokens \u6d88\u8017\u3002",
  "home.diff.p": "\u5f53\u4e0a\u4e0b\u6587\u3001\u504f\u597d\u4e0e\u4efb\u52a1\u72b6\u6001\u59cb\u7ec8\u5728\u7ebf\uff0c\u7cfb\u7edf\u65e0\u9700\u5168\u91cf\u52a0\u8f7d\u91cd\u590d\u524d\u60c5\u3002Tokens \u8282\u7701\u7531\u6b64\u5f00\u59cb\uff1a\u5c11\u590d\u8ff0\u3001\u5c11\u94fa\u57ab\uff0c\u8ba9\u9ad8\u6548\u8d2f\u7a7f\u59cb\u7ec8\uff0c\u8d8a\u7528\u8d8a\u7701\u3002",
  "home.diff.c3": "\u51cf\u5c11\u524d\u60c5\u91cd\u8f7d\uff0c\u6d41\u7a0b\u81ea\u7136\u8fde\u8d2f\u3002",
  "home.diff.c3.p": "\u4e0a\u4e0b\u6587\u8d8a\u8f7b\u91cf\u5316\uff0c\u5de5\u5177\u8c03\u7528\u3001\u4efb\u52a1\u72b6\u6001\u4e0e\u6821\u9a8c\u73af\u8282\u8d8a\u80fd\u65e0\u7f1d\u627f\u63a5\uff0c\u544a\u522b\u91cd\u590d\u94fa\u9648\u3002"
});

Object.assign(I18N.ja, {
  "home.diff.c3": "\u524d\u63d0\u306e\u518d\u8aad\u307f\u8fbc\u307f\u304c\u6e1b\u308b\u307b\u3069\u3001\u6d41\u308c\u306f\u81ea\u7136\u306b\u3064\u306a\u304c\u308b\u3002",
  "home.diff.c3.p": "\u6587\u8108\u304c\u8efd\u3044\u307b\u3069\u3001\u30c4\u30fc\u30eb\u5b9f\u884c\u3001\u30bf\u30b9\u30af\u72b6\u614b\u3001\u691c\u8a3c\u306e\u5404\u5de5\u7a0b\u306f\u3088\u308a\u30b7\u30fc\u30e0\u30ec\u30b9\u306b\u3064\u306a\u304c\u308a\u3001\u540c\u3058\u524d\u63d0\u8aac\u660e\u3092\u4f55\u5ea6\u3082\u6577\u304d\u76f4\u3055\u305a\u306b\u6e08\u3080\u3002"
});

Object.assign(I18N.ko, {
  "home.diff.c3": "\uc804\ud6c4 \ub9e5\ub77d \uc7ac\uc801\uc7ac\uac00 \uc904\uc5b4\ub4e4\uc218\ub85d \ud750\ub984\uc740 \uc790\uc5f0\uc2a4\ub7fd\uac8c \uc774\uc5b4\uc9c4\ub2e4.",
  "home.diff.c3.p": "\ubb38\ub9e5\uc774 \uac00\ubcbc\uc6cc\uc9c8\uc218\ub85d \ub3c4\uad6c \ud638\ucd9c, \uc791\uc5c5 \uc0c1\ud0dc, \uac80\uc99d \ub2e8\uacc4\ub294 \ub354 \ub9e4\ub044\ub7fd\uac8c \uc774\uc5b4\uc9c0\uace0, \uac19\uc740 \ubc30\uacbd \uc124\uba85\uc744 \ubc18\ubcf5\ud574\uc11c \ub2e4\uc2dc \uae54\uc9c0 \uc54a\uc544\ub3c4 \ub41c\ub2e4."
});

applySiteState();
initTopNavActiveState();
applyReleaseState();
initRevealAnimations();
initHeroMemoryParticles();
initRuntimeLoop();
if (document.querySelector("[data-proof-tab]")) {
  initProofTabs();
}
if (document.querySelector("[data-docs-filter]")) {
  initDocsIndexNav();
}
if (document.querySelector("[data-beta-form]")) {
  initBetaWaitlistForm();
}
writeYear();
initLangSwitch();
