/**
 * main.js — Design Audit Agent front-end logic
 *
 * Handles:
 *  - Drag-and-drop file uploads
 *  - File validation (type + size)
 *  - Image previews
 *  - Form submission with loading overlay
 *  - Error display
 *  - Report history panel
 */

"use strict";

const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_TYPES  = ["image/png", "image/jpeg", "image/webp"];

/* ── Utility Helpers ──────────────────────────────────────────────────────── */

function formatBytes(bytes) {
  if (bytes < 1024)      return bytes + " B";
  if (bytes < 1048576)   return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function showError(msg) {
  const el = document.getElementById("error-alert");
  document.getElementById("error-msg").textContent = msg;
  el.classList.remove("hidden");
  el.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function dismissError() {
  document.getElementById("error-alert").classList.add("hidden");
}

function validateFile(file) {
  if (!ALLOWED_TYPES.includes(file.type)) {
    showError(`Unsupported file type: ${file.type}. Please upload PNG, JPG, or WebP.`);
    return false;
  }
  if (file.size > MAX_FILE_BYTES) {
    showError(`File too large (${formatBytes(file.size)}). Maximum allowed size is 10 MB.`);
    return false;
  }
  return true;
}

/* ── Preview Management ───────────────────────────────────────────────────── */

function showPreview(file, previewId, dropId) {
  const previewArea = document.getElementById(previewId);
  const dropZone    = document.getElementById(dropId);

  // Derive thumb / name / size element IDs from previewId prefix
  const prefix = previewId.replace("-preview", "");
  const thumb  = document.getElementById(`${prefix}-thumb`);
  const fname  = document.getElementById(`${prefix}-fname`);
  const fsize  = document.getElementById(`${prefix}-fsize`);

  const reader = new FileReader();
  reader.onload = (e) => {
    if (thumb) thumb.src = e.target.result;
    if (fname) fname.textContent = file.name;
    if (fsize) fsize.textContent = formatBytes(file.size);
    dropZone.classList.add("hidden");
    previewArea.classList.remove("hidden");
  };
  reader.readAsDataURL(file);
}

function clearFile(inputId, previewId, dropId) {
  document.getElementById(inputId).value = "";
  document.getElementById(previewId).classList.add("hidden");
  document.getElementById(dropId).classList.remove("hidden");
}

/* ── Drag & Drop Handlers ─────────────────────────────────────────────────── */

function onDragOver(event) {
  event.preventDefault();
  event.currentTarget.classList.add("drag-over");
}

function onDragLeave(event) {
  event.currentTarget.classList.remove("drag-over");
}

function onDrop(event, inputId, previewId, dropId) {
  event.preventDefault();
  event.currentTarget.classList.remove("drag-over");

  const file = event.dataTransfer.files[0];
  if (!file) return;
  if (!validateFile(file)) return;

  // Programmatically set the file on the hidden input via DataTransfer
  const dt = new DataTransfer();
  dt.items.add(file);
  const input = document.getElementById(inputId);
  input.files = dt.files;

  showPreview(file, previewId, dropId);
}

function onFileChange(input, previewId, dropId) {
  const file = input.files[0];
  if (!file) return;
  if (!validateFile(file)) {
    input.value = "";
    return;
  }
  showPreview(file, previewId, dropId);
}

/* ── Loading Overlay ──────────────────────────────────────────────────────── */

function showLoading(isRegression) {
  const overlay = document.getElementById("loading-overlay");
  const title   = document.getElementById("loading-title");
  const sub     = document.getElementById("loading-sub");

  title.textContent = isRegression ? "Comparing designs…" : "Analysing design…";
  sub.textContent   = isRegression
    ? "Running before/after comparison with Gemini Vision. This may take 20–40 seconds."
    : "Running Gemini Vision analysis. This may take 15–30 seconds.";

  overlay.classList.remove("hidden");

  // Animate the loading steps
  setTimeout(() => {
    const s2 = document.getElementById("step-2");
    const s3 = document.getElementById("step-3");
    if (s2) { s2.classList.remove("step-active"); }
    if (s3) { s3.classList.remove("step-dim"); s3.classList.add("step-active"); }
  }, 12000);
}

/* ── Form Submission ──────────────────────────────────────────────────────── */

document.getElementById("audit-form").addEventListener("submit", function (e) {
  e.preventDefault();
  dismissError();

  const file = document.getElementById("audit-file").files[0];
  if (!file) {
    showError("Please select a screenshot before running the audit.");
    return;
  }

  showLoading(false);

  const formData = new FormData(this);
  fetch("/audit", { method: "POST", body: formData })
    .then((res) => {
      if (res.redirected) {
        window.location.href = res.url;
        return;
      }
      // Handle JSON error responses
      return res.json().then((data) => {
        document.getElementById("loading-overlay").classList.add("hidden");
        showError(data.error || "An unknown error occurred.");
      });
    })
    .catch((err) => {
      document.getElementById("loading-overlay").classList.add("hidden");
      showError("Network error: " + err.message);
    });
});

document.getElementById("regression-form").addEventListener("submit", function (e) {
  e.preventDefault();
  dismissError();

  const before = document.getElementById("before-file").files[0];
  const after  = document.getElementById("after-file").files[0];

  if (!before || !after) {
    showError("Please select both BEFORE and AFTER screenshots.");
    return;
  }

  showLoading(true);

  const formData = new FormData(this);
  fetch("/regression", { method: "POST", body: formData })
    .then((res) => {
      if (res.redirected) {
        window.location.href = res.url;
        return;
      }
      return res.json().then((data) => {
        document.getElementById("loading-overlay").classList.add("hidden");
        showError(data.error || "An unknown error occurred.");
      });
    })
    .catch((err) => {
      document.getElementById("loading-overlay").classList.add("hidden");
      showError("Network error: " + err.message);
    });
});

/* ── History Panel ────────────────────────────────────────────────────────── */

function formatTimestamp(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function loadHistory() {
  const section = document.getElementById("history-section");
  const list    = document.getElementById("history-list");

  // Toggle off if already visible
  if (section.style.display !== "none") {
    section.style.display = "none";
    return;
  }

  list.innerHTML = "<p style='color:var(--text-3);font-size:0.85rem;padding:12px 0'>Loading…</p>";
  section.style.display = "block";

  fetch("/history")
    .then((r) => r.json())
    .then((items) => {
      if (!items || items.length === 0) {
        list.innerHTML = "<p style='color:var(--text-3);font-size:0.85rem;padding:12px 0'>No reports yet.</p>";
        return;
      }

      list.innerHTML = items.map((item) => {
        const icon   = item.report_type === "audit" ? "bi-search" : "bi-arrow-left-right";
        const right  = item.report_type === "audit"
          ? `<span class="history-score">Score: ${item.score ?? "—"}</span>`
          : `<span class="history-score">${item.verdict ?? "—"}</span>`;
        const count  = item.report_type === "audit"
          ? `${item.finding_count} finding${item.finding_count !== 1 ? "s" : ""}`
          : `${item.change_count} change${item.change_count !== 1 ? "s" : ""}`;

        return `
          <a class="history-item" href="/report/${item.report_id}">
            <div class="history-item-left">
              <i class="bi ${icon} history-icon"></i>
              <div>
                <div class="history-name">${escapeHtml(item.original_filename)}</div>
                <div class="history-time">${formatTimestamp(item.timestamp)} · ${escapeHtml(count)}</div>
              </div>
            </div>
            ${right}
          </a>
        `;
      }).join("");
    })
    .catch(() => {
      list.innerHTML = "<p style='color:var(--red);font-size:0.85rem'>Failed to load history.</p>";
    });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
