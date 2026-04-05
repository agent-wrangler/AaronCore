const siteConfig = {
  productName: "AaronCore",
  brandSubline: "Official release surface",
  primaryDomain: "aaroncore.com",
  contactEmail: "hi@aaroncore.com",
  contactStatus: "setup pending",
  launchState: "Official site first",
  footerTagline: "Official home for releases, notes, and downloads.",
  releaseRoute: "aaroncore.com / future download channel",
  metaDescription:
    "AaronCore is a local-first desktop agent runtime built around execution, tool calls, layered memory, and a clear release surface.",
  ogDescription:
    "A local-first desktop agent runtime with tool-call execution, layered memory, and a clean release surface."
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
  setMeta('meta[property="og:title"]', `${siteConfig.productName} | Local-First Agent Runtime`);
  setMeta('meta[property="og:description"]', siteConfig.ogDescription);

  setField("site", "brandSubline", siteConfig.brandSubline);
  setField("site", "primaryDomain", siteConfig.primaryDomain);
  setField("site", "contactEmail", siteConfig.contactEmail);
  setField("site", "launchState", siteConfig.launchState);
  setField("site", "footerTagline", siteConfig.footerTagline);
  setField("site", "releaseRoute", siteConfig.releaseRoute);
  setField("site", "mailboxStatusLine", `Mailbox status: ${siteConfig.contactStatus}.`);
}

function applyReleaseState() {
  const downloadBtn = document.getElementById("downloadBtn");
  const heroDownloadLink = document.getElementById("heroDownloadLink");
  const note = document.getElementById("downloadNote");

  setField("release", "version", releaseConfig.version);

  if (!downloadBtn || !heroDownloadLink || !note) {
    return;
  }

  if (releaseConfig.available && releaseConfig.url) {
    downloadBtn.textContent = releaseConfig.label;
    downloadBtn.href = releaseConfig.url;
    downloadBtn.classList.remove("disabled");
    downloadBtn.setAttribute("aria-disabled", "false");
    downloadBtn.setAttribute("target", "_blank");
    downloadBtn.setAttribute("rel", "noreferrer");

    heroDownloadLink.textContent = releaseConfig.label;
    heroDownloadLink.href = releaseConfig.url;
    heroDownloadLink.setAttribute("target", "_blank");
    heroDownloadLink.setAttribute("rel", "noreferrer");

    note.textContent = releaseConfig.noteWhenOpen;
    return;
  }

  downloadBtn.textContent = releaseConfig.fallbackLabel;
  downloadBtn.href = "#download";
  downloadBtn.classList.add("disabled");
  downloadBtn.setAttribute("aria-disabled", "true");
  downloadBtn.removeAttribute("target");
  downloadBtn.removeAttribute("rel");

  heroDownloadLink.textContent = releaseConfig.fallbackLabel;
  heroDownloadLink.href = "#download";
  heroDownloadLink.removeAttribute("target");
  heroDownloadLink.removeAttribute("rel");

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

function writeYear() {
  const yearSlot = document.getElementById("yearSlot");
  if (yearSlot) {
    yearSlot.textContent = String(new Date().getFullYear());
  }
}

applySiteState();
applyReleaseState();
initRevealAnimations();
writeYear();
