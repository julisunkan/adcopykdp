/* KDP AdCopy Generator – Frontend Logic */

// ── PWA Service Worker Registration ─────────────────────────────────────────
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/static/service-worker.js")
      .then((reg) => console.log("SW registered:", reg.scope))
      .catch((err) => console.warn("SW registration failed:", err));
  });
}

// ── PWA Install Prompt ───────────────────────────────────────────────────────
let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
});

// ── DOM Refs ─────────────────────────────────────────────────────────────────
const form = document.getElementById("generateForm");
const generateBtn = document.getElementById("generateBtn");
const btnText = document.getElementById("btnText");
const btnLoading = document.getElementById("btnLoading");
const errorBanner = document.getElementById("errorBanner");
const resultsSection = document.getElementById("results");

// ── Current result data (for export) ────────────────────────────────────────
let currentResult = null;

// ── Form Submit ──────────────────────────────────────────────────────────────
if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setLoading(true);
    hideError();
    resultsSection.classList.add("hidden");

    const payload = {
      url: form.url.value.trim(),
      title: form.title.value.trim(),
      description: form.description.value.trim(),
      keywords: form.keywords.value.trim(),
      target_audience: form.target_audience.value.trim(),
      platform: form.platform.value,
      tone: form.tone.value,
      min_words: parseInt(form.min_words.value) || 30,
      max_words: parseInt(form.max_words.value) || 100,
    };

    try {
      const res = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        showError(data.error || "Something went wrong. Please try again.");
        return;
      }
      currentResult = data;
      renderResults(data);
      resultsSection.classList.remove("hidden");
      resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showError("Network error: " + err.message);
    } finally {
      setLoading(false);
    }
  });
}

// ── Render Results ───────────────────────────────────────────────────────────
function renderResults(data) {
  // Product info
  const product = data.product || {};
  const productInfo = document.getElementById("productInfo");
  if (productInfo) {
    productInfo.innerHTML = `
      ${product.image ? `<img class="product-img" src="${esc(product.image)}" alt="Product" onerror="this.style.display='none'">` : ""}
      <div class="product-info">
        <h3>${esc(product.title || "Product")}</h3>
        ${product.url ? `<a href="${esc(product.url)}" target="_blank" rel="noopener">View on Amazon ↗</a>` : ""}
      </div>
    `;
  }

  renderList("headlines", data.headlines || []);
  renderList("hooks", data.hooks || []);
  renderList("shortAds", data.short_ads || []);
  renderList("longAds", data.long_ads || []);

  // Keywords cloud
  const kwEl = document.getElementById("keywords");
  if (kwEl) {
    kwEl.innerHTML = (data.keywords || [])
      .map((k) => `<span class="kw-tag">${esc(k)}</span>`)
      .join("");
  }
}

function renderList(containerId, items) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = items
    .map(
      (item, i) => `
      <div class="ad-item">
        <span>${esc(item)}</span>
        <button class="copy-btn" onclick="copyItem(this, '${esc(item).replace(/'/g, "\\'")}')">Copy</button>
      </div>`
    )
    .join("");
}

// ── Copy to Clipboard ────────────────────────────────────────────────────────
function copyItem(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = "Copied!";
    btn.classList.add("copied");
    setTimeout(() => {
      btn.textContent = "Copy";
      btn.classList.remove("copied");
    }, 1800);
  });
}

// ── Export ───────────────────────────────────────────────────────────────────
const exportHtmlBtn = document.getElementById("exportHtml");
const exportZipBtn = document.getElementById("exportZip");

if (exportHtmlBtn) {
  exportHtmlBtn.addEventListener("click", () => exportFile("/export/html", "ad_copy.html", "text/html"));
}
if (exportZipBtn) {
  exportZipBtn.addEventListener("click", () => exportFile("/export/zip", "ad_copy.zip", "application/zip"));
}

async function exportFile(endpoint, filename, mime) {
  if (!currentResult) return;
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentResult),
    });
    if (!res.ok) { showError("Export failed."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError("Export error: " + err.message);
  }
}

// ── UI Helpers ───────────────────────────────────────────────────────────────
function setLoading(on) {
  generateBtn.disabled = on;
  btnText.classList.toggle("hidden", on);
  btnLoading.classList.toggle("hidden", !on);
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.remove("hidden");
}

function hideError() {
  errorBanner.classList.add("hidden");
}

function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
