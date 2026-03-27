/* KDP AdCopy Generator – Frontend Logic */

// ── PWA Service Worker ───────────────────────────────────────────────────────
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/static/service-worker.js")
      .then((reg) => console.log("SW registered:", reg.scope))
      .catch((err) => console.warn("SW registration failed:", err));
  });
}

// ── Tab Switcher ─────────────────────────────────────────────────────────────
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.tab;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById("tab-" + target).classList.remove("hidden");
  });
});

// ── Shared helpers ───────────────────────────────────────────────────────────
function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderAdItem(text, accentClass) {
  const safe = esc(text);
  const raw = text.replace(/'/g, "\\'");
  return `<div class="ad-item${accentClass ? " " + accentClass : ""}">
    <span>${safe}</span>
    <button class="copy-btn" onclick="copyItem(this,'${raw}')">Copy</button>
  </div>`;
}

function renderList(containerId, items, accentClass) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = items.map((i) => renderAdItem(i, accentClass)).join("");
}

function renderProductCard(containerId, product) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `
    ${product.image ? `<img class="product-img" src="${esc(product.image)}" alt="Product" onerror="this.style.display='none'">` : ""}
    <div class="product-info">
      <h3>${esc(product.title || "Product")}</h3>
      ${product.url ? `<a href="${esc(product.url)}" target="_blank" rel="noopener">View on Amazon ↗</a>` : ""}
    </div>`;
}

function setLoading(btnId, textId, loadingId, on) {
  const btn = document.getElementById(btnId);
  if (btn) btn.disabled = on;
  const txt = document.getElementById(textId);
  if (txt) txt.classList.toggle("hidden", on);
  const ld = document.getElementById(loadingId);
  if (ld) ld.classList.toggle("hidden", !on);
}

function showError(bannerId, msg) {
  const el = document.getElementById(bannerId);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideError(bannerId) {
  const el = document.getElementById(bannerId);
  if (el) el.classList.add("hidden");
}

async function exportFile(endpoint, filename, mime, resultData) {
  if (!resultData) return;
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(resultData),
    });
    if (!res.ok) { alert("Export failed."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("Export error: " + err.message);
  }
}

// ── Copy to Clipboard ────────────────────────────────────────────────────────
function copyItem(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(() => { btn.textContent = "Copy"; btn.classList.remove("copied"); }, 1800);
  });
}

// ════════════════════════════════════════════════════════════════════════════
// AD COPY SECTION
// ════════════════════════════════════════════════════════════════════════════
let currentAdResult = null;

const adForm = document.getElementById("generateForm");
if (adForm) {
  adForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setLoading("generateBtn", "btnText", "btnLoading", true);
    hideError("errorBanner");
    document.getElementById("results").classList.add("hidden");

    const payload = {
      url: adForm.url.value.trim(),
      title: adForm.title.value.trim(),
      description: adForm.description.value.trim(),
      keywords: adForm.keywords.value.trim(),
      target_audience: adForm.target_audience.value.trim(),
      platform: adForm.platform.value,
      tone: adForm.tone.value,
      min_words: parseInt(adForm.min_words.value) || 30,
      max_words: parseInt(adForm.max_words.value) || 100,
    };

    try {
      const res = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) { showError("errorBanner", data.error || "Something went wrong."); return; }
      currentAdResult = data;
      renderAdResults(data);
      document.getElementById("results").classList.remove("hidden");
      document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showError("errorBanner", "Network error: " + err.message);
    } finally {
      setLoading("generateBtn", "btnText", "btnLoading", false);
    }
  });
}

function renderAdResults(data) {
  renderProductCard("productInfo", data.product || {});
  renderList("headlines", data.headlines || []);
  renderList("hooks", data.hooks || [], "pink-item");
  renderList("shortAds", data.short_ads || [], "yellow-item");
  renderList("longAds", data.long_ads || [], "long-item");

  const kwEl = document.getElementById("keywords");
  if (kwEl) {
    kwEl.innerHTML = (data.keywords || []).map((k) => `<span class="kw-tag">${esc(k)}</span>`).join("");
  }
}

document.getElementById("exportHtml")?.addEventListener("click", () =>
  exportFile("/export/html", "ad_copy.html", "text/html", currentAdResult)
);
document.getElementById("exportZip")?.addEventListener("click", () =>
  exportFile("/export/zip", "ad_copy.zip", "application/zip", currentAdResult)
);

// ════════════════════════════════════════════════════════════════════════════
// EMAIL ADCOPY SECTION
// ════════════════════════════════════════════════════════════════════════════
let currentEmailResult = null;

const emailForm = document.getElementById("emailForm");
if (emailForm) {
  emailForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setLoading("emailBtn", "emailBtnText", "emailBtnLoading", true);
    hideError("emailErrorBanner");
    document.getElementById("emailResults").classList.add("hidden");

    const payload = {
      url: emailForm.url.value.trim(),
      title: emailForm.title.value.trim(),
      description: emailForm.description.value.trim(),
      keywords: emailForm.keywords.value.trim(),
      target_audience: emailForm.target_audience.value.trim(),
      email_type: emailForm.email_type.value,
      tone: emailForm.tone.value,
      min_words: parseInt(emailForm.min_words.value) || 50,
      max_words: parseInt(emailForm.max_words.value) || 150,
    };

    try {
      const res = await fetch("/generate/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) { showError("emailErrorBanner", data.error || "Something went wrong."); return; }
      currentEmailResult = data;
      renderEmailResults(data);
      document.getElementById("emailResults").classList.remove("hidden");
      document.getElementById("emailResults").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showError("emailErrorBanner", "Network error: " + err.message);
    } finally {
      setLoading("emailBtn", "emailBtnText", "emailBtnLoading", false);
    }
  });
}

function renderEmailResults(data) {
  renderProductCard("emailProductInfo", data.product || {});
  renderList("subjectLines", data.subject_lines || [], "green-item");
  renderList("previewTexts", data.preview_texts || [], "yellow-item");
  renderList("shortBodies", data.short_bodies || []);
  renderList("longBodies", data.long_bodies || [], "long-item");

  const ctaEl = document.getElementById("ctas");
  if (ctaEl) {
    ctaEl.innerHTML = (data.ctas || [])
      .map((c) => `<span class="kw-tag email-cta-tag">${esc(c)}</span>`)
      .join("");
  }
}

document.getElementById("exportEmailHtml")?.addEventListener("click", () =>
  exportFile("/export/email/html", "email_ad_copy.html", "text/html", currentEmailResult)
);
document.getElementById("exportEmailZip")?.addEventListener("click", () =>
  exportFile("/export/email/zip", "email_ad_copy.zip", "application/zip", currentEmailResult)
);

// ─── Social Media ─────────────────────────────────────────────────────────────

const SOC_CONFIG = {
  twitter:   { label: "Connect X",         icon: "𝕏",  connectedColor: "#000" },
  reddit:    { label: "Connect Reddit",     icon: "🟠", connectedColor: "#ff4500" },
  facebook:  { label: "Connect Facebook",   icon: "🔵", connectedColor: "#1877f2" },
  pinterest: { label: "Connect Pinterest",  icon: "📌", connectedColor: "#e60023" },
};
const SOC_PLATFORMS = Object.keys(SOC_CONFIG);
let socialStatus = {};
let currentPostPlatform = null;
let currentPostSource = "ads";

// Load social status on page load
async function loadSocialStatus() {
  try {
    const res = await fetch("/social/status");
    socialStatus = await res.json();
    SOC_PLATFORMS.forEach(p => {
      const info = socialStatus[p];
      const btn = document.querySelector(`.soc-btn.soc-${p}`);
      const disc = document.getElementById(`soc-${p}-disc`);
      const label = document.getElementById(`soc-${p}-label`);
      if (!btn) return;
      if (info && info.connected) {
        btn.classList.add("connected");
        if (label) label.textContent = info.username || "Connected";
        if (disc) disc.classList.remove("hidden");
      } else {
        btn.classList.remove("connected");
        if (label) label.textContent = SOC_CONFIG[p].label;
        if (disc) disc.classList.add("hidden");
      }
    });
  } catch (e) {
    console.error("Could not load social status", e);
  }
}

function socialConnect(platform) {
  const popup = window.open(
    `/social/connect/${platform}`,
    `Connect ${platform}`,
    "width=600,height=700,left=200,top=100"
  );
  const handler = (e) => {
    if (e.data && e.data.social === platform) {
      window.removeEventListener("message", handler);
      if (popup && !popup.closed) popup.close();
      if (e.data.ok) {
        showToast(`${platform} connected!`, "success");
        loadSocialStatus();
      } else {
        showToast(`Error: ${e.data.error}`, "error");
      }
    }
  };
  window.addEventListener("message", handler);
}

async function socialDisconnect(platform) {
  await fetch(`/social/disconnect/${platform}`);
  socialStatus[platform] = { connected: false, username: null };
  loadSocialStatus();
  showToast(`${platform} disconnected`, "info");
}

// ── Post Modal ─────────────────────────────────────────────────────────────

function openPostModal(source) {
  currentPostSource = source;

  // Check if at least one platform is connected
  const connected = SOC_PLATFORMS.filter(p => socialStatus[p] && socialStatus[p].connected);
  if (connected.length === 0) {
    showToast("Connect at least one social account above to post.", "error");
    return;
  }

  // Build quick-pick buttons from current results
  buildQuickPick(source);

  // Reset modal
  document.getElementById("modalText").value = "";
  document.getElementById("modalError").classList.add("hidden");
  document.getElementById("modalPostText").classList.remove("hidden");
  document.getElementById("modalPostLoading").classList.add("hidden");
  document.getElementById("redditFields").classList.add("hidden");
  document.getElementById("pinterestFields").classList.add("hidden");
  document.getElementById("charCounter").textContent = "";
  currentPostPlatform = null;

  // Build platform selector
  const title = document.getElementById("modalTitle");
  const icon = document.getElementById("modalPlatformIcon");
  title.textContent = "Choose Platform & Post";
  icon.innerHTML = buildPlatformSelector(connected);

  document.getElementById("postModal").classList.remove("hidden");
}

function buildPlatformSelector(connected) {
  return connected.map(p => {
    const cfg = SOC_CONFIG[p];
    return `<button class="qp-btn" onclick="selectPlatform('${p}',this)" style="font-size:.95rem;padding:8px 16px">
      ${cfg.icon} ${capitalise(p)}
    </button>`;
  }).join("");
}

async function selectPlatform(platform, el) {
  currentPostPlatform = platform;
  document.querySelectorAll("#modalPlatformIcon .qp-btn").forEach(b => b.classList.remove("selected"));
  el.classList.add("selected");
  document.getElementById("modalTitle").textContent = `Post to ${capitalise(platform)}`;

  // Show/hide platform-specific fields
  const showReddit    = platform === "reddit";
  const showPinterest = platform === "pinterest";
  document.getElementById("redditFields").classList.toggle("hidden", !showReddit);
  document.getElementById("pinterestFields").classList.toggle("hidden", !showPinterest);

  // Set char counter for Twitter
  if (platform === "twitter") {
    document.getElementById("charCounter").textContent = "(280 char limit)";
  } else {
    document.getElementById("charCounter").textContent = "";
  }

  // Load Pinterest boards
  if (showPinterest) {
    const sel = document.getElementById("pinterestBoard");
    sel.innerHTML = '<option value="">Loading…</option>';
    try {
      const res = await fetch("/social/pinterest/boards");
      const data = await res.json();
      if (data.boards && data.boards.length > 0) {
        sel.innerHTML = data.boards.map(b => `<option value="${b.id}">${b.name}</option>`).join("");
      } else {
        sel.innerHTML = '<option value="">No boards found – enter board ID manually</option>';
      }
    } catch (e) {
      sel.innerHTML = '<option value="">Error loading boards</option>';
    }
  }
}

function buildQuickPick(source) {
  const container = document.getElementById("modalQuickPick");
  const items = [];

  if (source === "ads" && currentResult) {
    const r = currentResult;
    if (r.headlines) r.headlines.forEach(h => items.push({ label: "Headline", text: h }));
    if (r.hooks)     r.hooks.forEach(h     => items.push({ label: "Hook",     text: h }));
    if (r.short_ads) r.short_ads.forEach(a => items.push({ label: "Short Ad", text: a }));
    if (r.long_ads)  r.long_ads.slice(0,2).forEach(a => items.push({ label: "Long Ad", text: a }));
  } else if (source === "emails" && currentEmailResult) {
    const r = currentEmailResult;
    if (r.subject_lines)  r.subject_lines.forEach(s  => items.push({ label: "Subject", text: s }));
    if (r.preview_texts)  r.preview_texts.forEach(pt => items.push({ label: "Preview", text: pt }));
    if (r.short_bodies)   r.short_bodies.forEach(b   => items.push({ label: "Short Body", text: b }));
    if (r.ctas)           r.ctas.forEach(c            => items.push({ label: "CTA", text: c }));
  }

  container.innerHTML = items.slice(0, 12).map(it =>
    `<button class="qp-btn" title="${esc(it.text)}" onclick="pickText(this, \`${esc(it.text).replace(/`/g, "'")}\`)">
      <strong>${it.label}</strong>: ${it.text.slice(0, 60)}${it.text.length > 60 ? "…" : ""}
    </button>`
  ).join("") || `<p style="font-size:.82rem;color:var(--muted)">Generate content first to quick-select text.</p>`;
}

function pickText(btn, text) {
  document.querySelectorAll(".modal-quickpick .qp-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");
  document.getElementById("modalText").value = text;
  updateCharCounter();
}

function updateCharCounter() {
  if (currentPostPlatform !== "twitter") return;
  const len = document.getElementById("modalText").value.length;
  const ctr = document.getElementById("charCounter");
  ctr.textContent = `${len}/280`;
  ctr.style.color = len > 280 ? "var(--red)" : "var(--muted)";
}

async function submitPost() {
  if (!currentPostPlatform) {
    showModalError("Please select a platform.");
    return;
  }
  const text = document.getElementById("modalText").value.trim();
  if (!text) {
    showModalError("Please add some content to post.");
    return;
  }

  const payload = { text };

  if (currentPostPlatform === "reddit") {
    payload.subreddit = document.getElementById("redditSubreddit").value.trim();
    payload.title = document.getElementById("redditTitle").value.trim();
    if (!payload.subreddit || !payload.title) {
      showModalError("Subreddit and post title are required for Reddit.");
      return;
    }
  }
  if (currentPostPlatform === "pinterest") {
    payload.board_id = document.getElementById("pinterestBoard").value;
    payload.title = document.getElementById("pinterestTitle").value.trim();
    if (!payload.board_id) {
      showModalError("Please select a board.");
      return;
    }
    if (!payload.title) payload.title = text.slice(0, 80);
  }

  document.getElementById("modalPostText").classList.add("hidden");
  document.getElementById("modalPostLoading").classList.remove("hidden");
  document.getElementById("modalError").classList.add("hidden");

  try {
    const res = await fetch(`/social/post/${currentPostPlatform}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      showToast(`Posted to ${capitalise(currentPostPlatform)}!`, "success");
      closePostModal(null);
    } else {
      showModalError(data.error || "Post failed. Please try again.");
    }
  } catch (e) {
    showModalError("Network error. Please try again.");
  } finally {
    document.getElementById("modalPostText").classList.remove("hidden");
    document.getElementById("modalPostLoading").classList.add("hidden");
  }
}

function closePostModal(event) {
  if (event && event.target !== document.getElementById("postModal")) return;
  document.getElementById("postModal").classList.add("hidden");
}

function showModalError(msg) {
  const el = document.getElementById("modalError");
  el.textContent = msg;
  el.classList.remove("hidden");
}

// ── Toast notifications ───────────────────────────────────────────────────────

function showToast(msg, type = "info") {
  const existing = document.querySelector(".toast-notification");
  if (existing) existing.remove();
  const toast = document.createElement("div");
  toast.className = `toast-notification toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add("visible"), 10);
  setTimeout(() => { toast.classList.remove("visible"); setTimeout(() => toast.remove(), 400); }, 3000);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function capitalise(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// Init
document.addEventListener("DOMContentLoaded", loadSocialStatus);
