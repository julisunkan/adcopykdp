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
  renderList("hooks", data.hooks || []);
  renderList("shortAds", data.short_ads || []);
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
  renderList("subjectLines", data.subject_lines || []);
  renderList("previewTexts", data.preview_texts || [], "preview-item");
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
