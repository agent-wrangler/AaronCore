const siteConfig = {
  productName: "AaronCore",
  brandSubline: "Memory-first execution, built to continue",
  primaryDomain: "aaroncore.com",
  contactEmail: "hi@aaroncore.com",
  contactStatus: "setup pending",
  launchState: "Official site first",
  footerTagline: "Built for people who need more than chat.",
  releaseRoute: "aaroncore.com / future download channel",
  metaDescription:
    "AaronCore is a memory-first AI execution core built for local execution, tool calls, layered memory, and work that actually continues.",
  ogDescription:
    "A local-first desktop agent runtime with memory, execution, self-repair, and a product surface designed to ship.",
  betaUrl: "#join-beta",
  betaLabel: "Download AaronCore",
  earlyAccessLabel: "Download AaronCore",
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
          : "Calm, local-first agent runtime";

  document.title = `${siteConfig.productName} | ${titleSuffix}`;
  setMeta('meta[name="description"]', siteConfig.metaDescription);
  setMeta('meta[property="og:title"]', `${siteConfig.productName} | ${siteConfig.brandSubline}`);
  setMeta('meta[property="og:description"]', siteConfig.ogDescription);

  setField("site", "primaryDomain", siteConfig.primaryDomain);
  setField("site", "contactEmail", siteConfig.contactEmail);
  setField("site", "launchState", siteConfig.launchState);
  setField("site", "releaseRoute", siteConfig.releaseRoute);
  setField("site", "mailboxStatusLine", `Mailbox status: ${siteConfig.contactStatus}.`);

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
    "brand.subline": "Memory-first execution, built to continue",
    "nav.home": "Home",
    "nav.product": "Product",
    "nav.docs": "Docs",
    "nav.changelog": "Changelog",
    "cta.joinBeta": "Download AaronCore",
    "cta.earlyAccess": "Download AaronCore",
    "cta.seeProof": "See product proof",
    "hero.h1": "A calm runtime where AI work actually continues.",
    "hero.title": "Memory, tool calling, and continuity — without the theatrics.",
    "hero.subtitle": "Turn one request into an execution chain that survives files, tools, and sessions.",
    "hero.lede": "AaronCore is built for the moments chat products drop: repo changes, tool calls, verification, and the next step that should already be queued.",
    "footer.tagline": "Built for people who need more than chat.",
    "hero.note": "Local-first · Memory-first · Continuity-first",

    "home.stage.kicker": "Desktop runtime",
    "home.stage.h": "One surface for memory, execution, and ongoing task state.",
    "home.stage.p": "A calmer product shell for the parts that matter most: understanding intent, loading memory, calling tools, verifying changes, and keeping continuity intact.",
    "home.panel.exec.label": "Execution layer",
    "home.panel.exec.h": "Requests become task chains — not polished dead ends.",
    "home.panel.exec.p": "Files, shell, memory, and verification stay connected inside one runtime surface.",
    "home.panel.posture.label": "System posture",
    "home.panel.posture.h": "Built to carry work forward",
    "home.panel.posture.p": "State stays visible, outcomes are reviewable, and the next step stays ready.",
    "home.rail.1.h": "Understand",
    "home.rail.1.p": "turn intent into a real target",
    "home.rail.2.h": "Plan",
    "home.rail.2.p": "form a chain instead of a guess",
    "home.rail.3.h": "Execute",
    "home.rail.3.p": "move through files, shell, and state",
    "home.rail.4.h": "Stabilize",
    "home.rail.4.p": "verify, repair, and carry forward",

    "home.how.h": "From one request to one execution chain",
    "home.how.p": "The runtime keeps the flow simple: load relevant memory, form a chain, execute through tools, verify outcomes, and carry state forward.",
    "home.how.step1.h": "Remember",
    "home.how.step1.p": "load constraints, preferences, history, and long-term signals",
    "home.how.step2.h": "Plan",
    "home.how.step2.p": "turn intent into a concrete chain with a next step",
    "home.how.step3.h": "Act",
    "home.how.step3.p": "call tools, change real artifacts, and keep the state attached",
    "home.how.step4.h": "Improve",
    "home.how.step4.p": "close the loop with feedback, repair, and compounding experience",

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

    "home.signal.h": "Proof without theater",
    "home.signal.p": "AaronCore is opinionated about one thing: the work should leave a trail. Here is a compact example of how a request becomes a chain you can audit.",

    "home.use.h": "Who AaronCore is for",
    "home.use.p": "AaronCore is for people who want AI to carry real work across sessions instead of resetting at every prompt.",
    "home.use.b1": "Plan development work, connect tools, and keep execution moving",
    "home.use.b2": "Organize materials, shape scripts, and carry a production flow",
    "home.use.b3": "Remember habits, follow tasks, and cut repetitive overhead",
    "home.use.b4": "Push AI from sounding smart toward doing real work",

    "home.diff.h": "Why AaronCore feels different",
    "home.diff.p": "Other products package intelligence as style. AaronCore is designed to carry state, tools, and forward motion through a real runtime loop.",
    "home.diff.c1": "Not temporary context, but recall that accumulates and returns",
    "home.diff.c2": "Not prettier answers, but forward progress",
    "home.diff.c3": "Feedback, repair, and experience compound over time",

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
    "home.cta.h": "Give your AI a real core",
    "home.cta.p": "The public build is not attached yet, but the beta path, the release route, and the official entry surface are already in place.",
    "product.title": "A runtime that keeps work alive",
    "product.subtitle": "AaronCore is designed for execution chains: memory, tool calls, verification, and continuity — in one calm surface.",
    "product.card.continuity.h": "State survives the next prompt",
    "product.card.continuity.p": "Tasks, constraints, and the next action remain visible and reusable instead of resetting into chat history.",
    "product.card.tools.h": "Tool calls are first-class",
    "product.card.tools.p": "Files, shell, and runtime actions stay attached to the conversation, with a traceable chain from request to result.",
    "product.card.verify.h": "Outcomes are reviewable",
    "product.card.verify.p": "Completion is not a vibe. The runtime makes it clear what changed, what was checked, and what remains.",
    "product.card.repair.h": "Feedback becomes sharper runs",
    "product.card.repair.p": "When failures happen, AaronCore narrows the issue, repairs the path, and compounds experience over time.",
    "product.proof.h": "What an execution chain looks like",
    "product.proof.p": "Short, human-readable, and easy to audit. This is the default posture: do the work, show the trail.",
    "product.proof.side.h": "Designed to avoid “polished dead ends”",
    "product.proof.side.p": "The chain keeps the next step explicit. It stays attached to artifacts (files, state, verification) rather than evaporating into a final paragraph.",

    "docs.title": "A map, not a wall of text",
    "docs.subtitle": "This page is a calm index. Deep dives can link out later — the goal is orientation and trust.",
    "docs.terms.h": "Terms (kept consistent)",
    "docs.terms.p": "Memory = persistent constraints and preferences. Chain = explicit next steps. Verification = evidence of done. Repair = narrow failures and stabilize the path.",
    "docs.card.overview.h": "What AaronCore is",
    "docs.card.overview.p": "A local-first runtime focused on continuity: memory, tools, verification, and repair in one loop.",
    "docs.card.memory.h": "What persists (and why)",
    "docs.card.memory.p": "Preferences, constraints, project context, and long-running task posture — written deliberately, not magically.",
    "docs.card.exec.h": "Chains vs replies",
    "docs.card.exec.p": "Turn requests into explicit next steps with artifacts attached: files, shell, and runtime state.",
    "docs.card.tools.h": "Tool calling model",
    "docs.card.tools.p": "Tools are first-class citizens with traceable inputs/outputs and reviewable outcomes.",
    "docs.card.verify.h": "What counts as done",
    "docs.card.verify.p": "Completion is defined by checks and evidence — not by confidence or tone.",
    "docs.card.repair.h": "Feedback loops",
    "docs.card.repair.p": "Failures narrow, paths repair, and experience compounds — without hiding the trail.",
    "docs.card.bounds.h": "Boundaries",
    "docs.card.bounds.p": "Local-first posture, explicit permissions, and clear limits on what automation can touch.",
    "docs.card.release.h": "Beta + download",
    "docs.card.release.p": "Public builds attach when ready. Until then, the beta mailbox is the honest path.",
    "docs.deep.h": "Want the deep runtime write-up?",
    "docs.deep.p": "When the public docs host is wired, this index becomes the front door.",

    "changelog.title": "What changed (public surface)",
    "changelog.subtitle": "A lightweight timeline for the official site and early milestones. Honest beats hype.",
    "changelog.r1.h": "Multi-page IA + calmer narrative",
    "changelog.r1.p": "Split Home / Product / Docs / Changelog, tightened copy toward continuity + verification, and reduced “demo UI” noise on the homepage.",
    "changelog.r2.h": "Official landing refresh",
    "changelog.r2.p": "Expanded the landing narrative with stronger sections for capabilities, proof, trust, and release posture.",
    "changelog.r3.h": "Public beta build",
    "changelog.r3.p": "Not attached yet. The honest default: mailbox-first early access until downloads are wired.",

    "lang.button": "Lang",
    "lang.en": "English",
    "lang.zh": "中文",
    "lang.ja": "日本語",
    "lang.ko": "한국어"
  },
  zh: {
    "brand.subline": "记忆优先的执行内核，让工作继续",
    "nav.home": "首页",
    "nav.product": "产品",
    "nav.docs": "文档",
    "nav.changelog": "更新",
    "cta.joinBeta": "下载 AaronCore",
    "cta.earlyAccess": "下载 AaronCore",
    "cta.seeProof": "查看产品证明",
    "hero.h1": "一个冷静的运行时，让 AI 的工作真正继续。",
    "hero.title": "记忆、工具调用、连续性——不演戏。",
    "hero.subtitle": "把一次需求变成可持续的执行链，跨文件、跨工具、跨会话。",
    "hero.lede": "AaronCore 为聊天产品常掉链子的时刻而生：改仓库、跑工具、做验证，以及下一步本该自动排好队。",
    "footer.tagline": "为需要不止聊天的人而做。",
    "hero.note": "本地优先 · 记忆优先 · 连续性优先",

    "home.stage.kicker": "桌面运行时",
    "home.stage.h": "一个面板，承载记忆、执行与持续任务状态。",
    "home.stage.p": "把最重要的部分做得更冷静：理解意图、加载记忆、调用工具、验证改动，并保持连续性。",
    "home.panel.exec.label": "执行层",
    "home.panel.exec.h": "需求会变成任务链，而不是漂亮的死胡同。",
    "home.panel.exec.p": "文件、Shell、记忆与验证在同一个运行时面板里保持连接。",
    "home.panel.posture.label": "系统姿态",
    "home.panel.posture.h": "为把工作往前推而设计",
    "home.panel.posture.p": "状态可见、结果可复核、下一步随时就绪。",
    "home.rail.1.h": "理解",
    "home.rail.1.p": "把意图变成真实目标",
    "home.rail.2.h": "规划",
    "home.rail.2.p": "形成任务链，而不是猜测",
    "home.rail.3.h": "执行",
    "home.rail.3.p": "穿过文件、Shell 与状态",
    "home.rail.4.h": "稳定",
    "home.rail.4.p": "验证、修复并继续前行",

    "home.how.h": "从一句需求到一条执行链",
    "home.how.p": "流程很简单：加载相关记忆 → 形成链路 → 通过工具执行 → 验证结果 → 把状态带到下一轮。",
    "home.how.step1.h": "记住",
    "home.how.step1.p": "加载约束、偏好、历史与长期信号",
    "home.how.step2.h": "规划",
    "home.how.step2.p": "把意图变成带下一步的具体链路",
    "home.how.step3.h": "行动",
    "home.how.step3.p": "调用工具，改真实产物，并保持状态绑定",
    "home.how.step4.h": "进化",
    "home.how.step4.p": "用反馈与修复闭环，让经验复利",

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

    "home.signal.h": "不演的证明",
    "home.signal.p": "AaronCore 只坚持一件事：工作要留下轨迹。这里是一段紧凑示例，展示请求如何变成可审计的链路。",

    "home.use.h": "AaronCore 适合谁",
    "home.use.p": "适合希望 AI 把真实工作跨会话扛起来的人，而不是每次 prompt 都从零开始。",
    "home.use.b1": "规划开发工作，连接工具，让执行持续推进",
    "home.use.b2": "整理素材、打磨脚本，承载内容生产流",
    "home.use.b3": "记住习惯、跟进任务，减少重复开销",
    "home.use.b4": "把 AI 从“像很聪明”推向“真的在做事”",

    "home.diff.h": "为什么 AaronCore 不一样",
    "home.diff.p": "很多产品把智能包装成风格；AaronCore 把状态、工具与前进动能放进真实运行时闭环里。",
    "home.diff.c1": "不是临时上下文，而是可回来的累积记忆",
    "home.diff.c2": "不是更漂亮的答案，而是持续前进",
    "home.diff.c3": "反馈、修复与经验会随时间复利",

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
    "home.cta.h": "给你的 AI 一个真正的核心",
    "home.cta.p": "公开构建还没挂上，但内测路径、发布路由与官方入口面已经准备好了。",
    "product.title": "让工作继续的运行时",
    "product.subtitle": "AaronCore 面向执行链而设计：记忆、工具调用、验证与连续性，收在同一个冷静的工作面里。",
    "product.card.continuity.h": "状态跨 prompt 保持",
    "product.card.continuity.p": "任务、约束和下一步会一直可见且可复用，不会每次都退化成聊天记录里的重来。",
    "product.card.tools.h": "工具调用是第一公民",
    "product.card.tools.p": "文件、Shell 和运行时动作都和对话绑在一起，从需求到结果有可追溯的链路。",
    "product.card.verify.h": "结果可复核",
    "product.card.verify.p": "完成不是“感觉”。运行时会说清楚改了什么、检查了什么、还剩什么。",
    "product.card.repair.h": "反馈让下一次更锋利",
    "product.card.repair.p": "出错时会收窄问题、修复路径、再验证，让经验逐步复利。",
    "product.proof.h": "执行链长什么样",
    "product.proof.p": "短、可读、易审计。默认姿态：做事，并留下证据。",
    "product.proof.side.h": "避免“漂亮的死胡同”",
    "product.proof.side.p": "执行链把下一步写死在台面上，绑定真实产物（文件/状态/验证），而不是最后变成一段话就蒸发。",

    "docs.title": "一张地图，而不是一堵墙",
    "docs.subtitle": "这是一个冷静的索引页。深挖内容后面再接出去——先让你快速定位与建立信任。",
    "docs.terms.h": "术语（保持一致）",
    "docs.terms.p": "Memory=持久化的约束与偏好；Chain=明确的下一步；Verification=完成证据；Repair=收窄失败并稳定路径。",
    "docs.card.overview.h": "AaronCore 是什么",
    "docs.card.overview.p": "一个本地优先的运行时循环：记忆、工具、验证、修复与连续性合在一起。",
    "docs.card.memory.h": "哪些东西会被记住（为什么）",
    "docs.card.memory.p": "偏好、约束、项目上下文与长期任务姿态——有意写入，而不是神秘自动。",
    "docs.card.exec.h": "执行链 vs 回复",
    "docs.card.exec.p": "把请求变成明确的下一步，并把产物绑定回来：文件、Shell、运行时状态。",
    "docs.card.tools.h": "工具调用模型",
    "docs.card.tools.p": "工具是第一公民：输入/输出可追踪，结果可复核。",
    "docs.card.verify.h": "什么算完成",
    "docs.card.verify.p": "完成由检查与证据定义，不由语气或自信度定义。",
    "docs.card.repair.h": "反馈闭环",
    "docs.card.repair.p": "失败收窄、路径修复、经验复利——不隐藏轨迹。",
    "docs.card.bounds.h": "边界",
    "docs.card.bounds.p": "本地优先姿态、显式权限，以及清晰的自动化触达范围。",
    "docs.card.release.h": "内测与下载",
    "docs.card.release.p": "公开构建准备好才挂。现在的诚实路径是邮箱内测。",
    "docs.deep.h": "想看更完整的运行时说明？",
    "docs.deep.p": "当公开文档站接好后，这页会成为入口地图。",

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
    "brand.subline": "記憶優先の実行コア。仕事を続けるために。",
    "nav.home": "ホーム",
    "nav.product": "製品",
    "nav.docs": "ドキュメント",
    "nav.changelog": "更新履歴",
    "cta.joinBeta": "AaronCore をダウンロード",
    "cta.earlyAccess": "AaronCore をダウンロード",
    "cta.seeProof": "プロダクトの証拠を見る",
    "hero.h1": "AIの仕事を“続ける”ための、落ち着いたランタイム。",
    "hero.title": "記憶・ツール呼び出し・継続性。演出は不要。",
    "hero.subtitle": "1つの依頼を、ファイル/ツール/セッションを越える実行チェーンへ。",
    "hero.lede": "AaronCoreは、チャットが途切れがちな瞬間（リポジトリ変更、ツール実行、検証、次の一手）を支えるために作られました。",
    "footer.tagline": "チャット以上を求める人へ。",
    "hero.note": "LOCAL-FIRST · MEMORY-FIRST · CONTINUITY-FIRST",
    "home.stage.kicker": "Desktop runtime",
    "home.stage.h": "One surface for memory, execution, and ongoing task state.",
    "home.stage.p": "A calmer product shell for the parts that matter most: understanding intent, loading memory, calling tools, verifying changes, and keeping continuity intact.",
    "home.panel.exec.label": "Execution layer",
    "home.panel.exec.h": "Requests become task chains — not polished dead ends.",
    "home.panel.exec.p": "Files, shell, memory, and verification stay connected inside one runtime surface.",
    "home.panel.posture.label": "System posture",
    "home.panel.posture.h": "Built to carry work forward",
    "home.panel.posture.p": "State stays visible, outcomes are reviewable, and the next step stays ready.",
    "home.rail.1.h": "Understand",
    "home.rail.1.p": "turn intent into a real target",
    "home.rail.2.h": "Plan",
    "home.rail.2.p": "form a chain instead of a guess",
    "home.rail.3.h": "Execute",
    "home.rail.3.p": "move through files, shell, and state",
    "home.rail.4.h": "Stabilize",
    "home.rail.4.p": "verify, repair, and carry forward",
    "home.how.h": "From one request to one execution chain",
    "home.how.p": "Load relevant memory, form a chain, execute through tools, verify outcomes, and carry state forward.",
    "home.how.step1.h": "Remember",
    "home.how.step1.p": "load constraints, preferences, history, and long-term signals",
    "home.how.step2.h": "Plan",
    "home.how.step2.p": "turn intent into a concrete chain with a next step",
    "home.how.step3.h": "Act",
    "home.how.step3.p": "call tools, change real artifacts, and keep the state attached",
    "home.how.step4.h": "Improve",
    "home.how.step4.p": "close the loop with feedback, repair, and compounding experience",
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
    "home.signal.h": "Proof without theater",
    "home.signal.p": "The work should leave a trail. Here is a compact example of how a request becomes a chain you can audit.",
    "home.use.h": "Who AaronCore is for",
    "home.use.p": "For people who want AI to carry real work across sessions instead of resetting at every prompt.",
    "home.use.b1": "Plan development work, connect tools, and keep execution moving",
    "home.use.b2": "Organize materials, shape scripts, and carry a production flow",
    "home.use.b3": "Remember habits, follow tasks, and cut repetitive overhead",
    "home.use.b4": "Push AI from sounding smart toward doing real work",
    "home.diff.h": "Why AaronCore feels different",
    "home.diff.p": "AaronCore carries state, tools, and forward motion through a real runtime loop.",
    "home.diff.c1": "Recall that accumulates and returns",
    "home.diff.c2": "Forward progress over prettier answers",
    "home.diff.c3": "Feedback and repair compound over time",
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
    "home.cta.h": "Give your AI a real core",
    "home.cta.p": "Public build is not attached yet, but the beta path and official entry surface are in place.",
    "product.title": "仕事を続けるためのランタイム",
    "product.subtitle": "記憶・ツール呼び出し・検証・継続性を、落ち着いた1つの面にまとめた実行チェーン設計。",
    "product.card.continuity.h": "状態が次のプロンプトに残る",
    "product.card.continuity.p": "タスク、制約、次の一手が可視で再利用可能。毎回チャット履歴に埋もれてリセットしない。",
    "product.card.tools.h": "ツール呼び出しが第一級",
    "product.card.tools.p": "ファイル、Shell、ランタイム操作が会話に紐づき、依頼から結果まで追跡可能なチェーンを保つ。",
    "product.card.verify.h": "結果はレビューできる",
    "product.card.verify.p": "完了は雰囲気ではない。何が変わり、何を確認し、何が残るかが見える。",
    "product.card.repair.h": "フィードバックで次が鋭くなる",
    "product.card.repair.p": "失敗を絞り込み、経路を修復し、再検証して経験を積み上げる。",
    "product.proof.h": "実行チェーンの形",
    "product.proof.p": "短く、人間が読めて監査できる。基本姿勢：仕事をして、証跡を残す。",
    "product.proof.side.h": "“磨かれた行き止まり”を避ける",
    "product.proof.side.p": "次の一手を明示し、成果物（ファイル/状態/検証）に結びつける。最後の段落で蒸発しない。",

    "docs.title": "壁ではなく、地図",
    "docs.subtitle": "落ち着いた索引ページ。深掘りは後でリンクし、まずは把握と信頼を。",
    "docs.terms.h": "用語（統一）",
    "docs.terms.p": "Memory=永続的な制約と好み。Chain=明確な次の一手。Verification=完了の証拠。Repair=失敗を絞り込み経路を安定化。",
    "docs.card.overview.h": "AaronCoreとは",
    "docs.card.overview.p": "継続性のためのローカルファースト・ランタイム：記憶、ツール、検証、修復を1つのループに。",
    "docs.card.memory.h": "何が残る（なぜ）",
    "docs.card.memory.p": "好み、制約、プロジェクト文脈、長期タスク姿勢。意図的に書き込まれ、勝手に増えない。",
    "docs.card.exec.h": "チェーン vs 返信",
    "docs.card.exec.p": "依頼を明確な次の一手へ。成果物（ファイル/Shell/状態）を紐づける。",
    "docs.card.tools.h": "ツール呼び出しモデル",
    "docs.card.tools.p": "入出力が追跡でき、結果がレビューできる“第一級”のツール。",
    "docs.card.verify.h": "何が完了か",
    "docs.card.verify.p": "完了はチェックと証拠で定義される。自信や口調ではない。",
    "docs.card.repair.h": "フィードバックループ",
    "docs.card.repair.p": "失敗を絞り込み、修復し、経験を積み上げる。証跡は隠さない。",
    "docs.card.bounds.h": "境界",
    "docs.card.bounds.p": "ローカルファースト、明示的な権限、触れられる範囲の透明性。",
    "docs.card.release.h": "ベータとダウンロード",
    "docs.card.release.p": "公開ビルドは準備が整ってから。今はメールボックスが正直な導線。",
    "docs.deep.h": "より詳しいランタイム解説が必要？",
    "docs.deep.p": "公開ドキュメントが整ったら、この索引が入口になります。",

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
    "brand.subline": "메모리 우선 실행 코어. 일을 계속 이어가게.",
    "nav.home": "홈",
    "nav.product": "제품",
    "nav.docs": "문서",
    "nav.changelog": "업데이트",
    "cta.joinBeta": "AaronCore 다운로드",
    "cta.earlyAccess": "AaronCore 다운로드",
    "cta.seeProof": "제품 증거 보기",
    "hero.h1": "AI 작업이 ‘계속’ 이어지도록 하는 차분한 런타임.",
    "hero.title": "메모리, 툴 호출, 연속성 — 과장은 없이.",
    "hero.subtitle": "한 번의 요청을 파일/툴/세션을 넘는 실행 체인으로.",
    "hero.lede": "AaronCore는 채팅 제품이 끊기기 쉬운 순간(레포 변경, 툴 실행, 검증, 다음 단계)을 위해 만들어졌습니다.",
    "footer.tagline": "채팅 이상의 무언가가 필요한 사람을 위해.",
    "hero.note": "LOCAL-FIRST · MEMORY-FIRST · CONTINUITY-FIRST",
    "home.stage.kicker": "Desktop runtime",
    "home.stage.h": "One surface for memory, execution, and ongoing task state.",
    "home.stage.p": "A calmer product shell: understand intent, load memory, call tools, verify changes, and keep continuity intact.",
    "home.panel.exec.label": "Execution layer",
    "home.panel.exec.h": "Requests become task chains — not polished dead ends.",
    "home.panel.exec.p": "Files, shell, memory, and verification stay connected inside one runtime surface.",
    "home.panel.posture.label": "System posture",
    "home.panel.posture.h": "Built to carry work forward",
    "home.panel.posture.p": "State stays visible, outcomes are reviewable, and the next step stays ready.",
    "home.rail.1.h": "Understand",
    "home.rail.1.p": "turn intent into a real target",
    "home.rail.2.h": "Plan",
    "home.rail.2.p": "form a chain instead of a guess",
    "home.rail.3.h": "Execute",
    "home.rail.3.p": "move through files, shell, and state",
    "home.rail.4.h": "Stabilize",
    "home.rail.4.p": "verify, repair, and carry forward",
    "home.how.h": "From one request to one execution chain",
    "home.how.p": "Load relevant memory, form a chain, execute through tools, verify outcomes, and carry state forward.",
    "home.how.step1.h": "Remember",
    "home.how.step1.p": "load constraints, preferences, history, and long-term signals",
    "home.how.step2.h": "Plan",
    "home.how.step2.p": "turn intent into a concrete chain with a next step",
    "home.how.step3.h": "Act",
    "home.how.step3.p": "call tools, change real artifacts, and keep the state attached",
    "home.how.step4.h": "Improve",
    "home.how.step4.p": "close the loop with feedback, repair, and compounding experience",
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
    "home.signal.h": "Proof without theater",
    "home.signal.p": "The work should leave a trail. A compact example shows how requests become auditable chains.",
    "home.use.h": "Who AaronCore is for",
    "home.use.p": "For people who want AI to carry real work across sessions instead of resetting at every prompt.",
    "home.use.b1": "Plan development work, connect tools, and keep execution moving",
    "home.use.b2": "Organize materials, shape scripts, and carry a production flow",
    "home.use.b3": "Remember habits, follow tasks, and cut repetitive overhead",
    "home.use.b4": "Push AI from sounding smart toward doing real work",
    "home.diff.h": "Why AaronCore feels different",
    "home.diff.p": "Carry state, tools, and forward motion through a real runtime loop.",
    "home.diff.c1": "Recall that accumulates and returns",
    "home.diff.c2": "Forward progress over prettier answers",
    "home.diff.c3": "Feedback and repair compound over time",
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
    "home.cta.h": "Give your AI a real core",
    "home.cta.p": "Public build is not attached yet, but the beta path and official entry surface are in place.",
    "product.title": "일을 계속 이어가게 하는 런타임",
    "product.subtitle": "메모리, 툴 호출, 검증, 연속성을 하나의 차분한 작업면에 묶은 실행 체인 중심 설계.",
    "product.card.continuity.h": "상태가 다음 프롬프트까지 이어짐",
    "product.card.continuity.p": "작업, 제약, 다음 단계가 계속 보이고 재사용 가능하며 매번 채팅 히스토리로 리셋되지 않습니다.",
    "product.card.tools.h": "툴 호출은 1급 구성요소",
    "product.card.tools.p": "파일, 셸, 런타임 액션이 대화에 붙어 있어 요청→결과 체인이 추적 가능합니다.",
    "product.card.verify.h": "결과는 검토 가능",
    "product.card.verify.p": "완료는 분위기가 아닙니다. 무엇이 바뀌고 무엇을 확인했는지, 무엇이 남았는지 보여줍니다.",
    "product.card.repair.h": "피드백으로 다음 실행이 날카로워짐",
    "product.card.repair.p": "실패를 좁히고 경로를 수리한 뒤 다시 검증하며 경험을 축적합니다.",
    "product.proof.h": "실행 체인은 이렇게 보입니다",
    "product.proof.p": "짧고 읽기 쉽고 감사 가능합니다. 기본 자세: 일을 하고, 흔적을 남긴다.",
    "product.proof.side.h": "“예쁜 막다른길”을 피하기 위해",
    "product.proof.side.p": "다음 단계를 명시하고 산출물(파일/상태/검증)에 붙입니다. 마지막 문단으로 증발하지 않습니다.",

    "docs.title": "벽이 아니라 지도",
    "docs.subtitle": "차분한 인덱스 페이지입니다. 깊은 문서는 나중에 연결하고, 먼저 방향과 신뢰를 잡습니다.",
    "docs.terms.h": "용어(일관 유지)",
    "docs.terms.p": "Memory=지속되는 제약과 선호. Chain=명시적 다음 단계. Verification=완료 증거. Repair=실패를 좁혀 경로 안정화.",
    "docs.card.overview.h": "AaronCore란",
    "docs.card.overview.p": "연속성을 위한 로컬-퍼스트 런타임: 메모리, 툴, 검증, 수리를 하나의 루프로.",
    "docs.card.memory.h": "무엇이 남는가(왜)",
    "docs.card.memory.p": "선호, 제약, 프로젝트 맥락, 장기 작업 자세를 의도적으로 기록합니다.",
    "docs.card.exec.h": "체인 vs 답변",
    "docs.card.exec.p": "요청을 다음 단계로 바꾸고 산출물(파일/셸/상태)을 붙입니다.",
    "docs.card.tools.h": "툴 호출 모델",
    "docs.card.tools.p": "입출력이 추적되고 결과가 검토 가능한 1급 툴.",
    "docs.card.verify.h": "무엇이 완료인가",
    "docs.card.verify.p": "완료는 체크와 증거로 정의됩니다. 톤이나 자신감이 아닙니다.",
    "docs.card.repair.h": "피드백 루프",
    "docs.card.repair.p": "실패를 좁히고 수리하며 경험을 축적합니다. 흔적을 숨기지 않습니다.",
    "docs.card.bounds.h": "경계",
    "docs.card.bounds.p": "로컬-퍼스트, 명시적 권한, 자동화가 닿는 범위의 투명성.",
    "docs.card.release.h": "베타와 다운로드",
    "docs.card.release.p": "공개 빌드는 준비되면 연결합니다. 그전엔 메일 베타가 정직한 경로입니다.",
    "docs.deep.h": "더 깊은 런타임 설명이 필요하신가요?",
    "docs.deep.p": "공개 문서가 준비되면 이 인덱스가 입구가 됩니다.",

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
  setField("site", "footerTagline", t("footer.tagline", l));

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
initRuntimeLoop();
if (document.querySelector("[data-proof-tab]")) {
  initProofTabs();
}
writeYear();
initLangSwitch();
