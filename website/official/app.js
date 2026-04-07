const siteConfig = {
  productName: "AaronCore",
  brandSubline: "The memory-first AI execution core",
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
  betaUrl: "mailto:hi@aaroncore.com?subject=Join%20AaronCore%20Beta",
  betaLabel: "Join Beta",
  earlyAccessLabel: "Get Early Access",
  demoUrl: "#proof",
  demoLabel: "Watch Demo",
  docsUrl: "#docs",
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
  document.title = `${siteConfig.productName} | Local-First Agent Runtime`;
  setMeta('meta[name="description"]', siteConfig.metaDescription);
  setMeta('meta[property="og:title"]', `${siteConfig.productName} | ${siteConfig.brandSubline}`);
  setMeta('meta[property="og:description"]', siteConfig.ogDescription);

  setField("site", "brandSubline", siteConfig.brandSubline);
  setField("site", "primaryDomain", siteConfig.primaryDomain);
  setField("site", "contactEmail", siteConfig.contactEmail);
  setField("site", "launchState", siteConfig.launchState);
  setField("site", "footerTagline", siteConfig.footerTagline);
  setField("site", "releaseRoute", siteConfig.releaseRoute);
  setField("site", "mailboxStatusLine", `Mailbox status: ${siteConfig.contactStatus}.`);

  document.querySelectorAll("[data-link-field]").forEach((node) => {
    const hrefKey = node.getAttribute("data-link-field");
    const labelKey = node.getAttribute("data-link-label");
    const href = siteConfig[hrefKey];
    if (href) {
      node.setAttribute("href", href);
    }
    if (labelKey && siteConfig[labelKey]) {
      node.textContent = siteConfig[labelKey];
    }
  });
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
  }, 1700);
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
  }, 3200);
}

function writeYear() {
  const yearSlot = document.getElementById("yearSlot");
  if (yearSlot) {
    yearSlot.textContent = String(new Date().getFullYear());
  }
}

applySiteState();
applyReleaseState();
initRevealAnimations();
initRuntimeLoop();
initProofTabs();
writeYear();
