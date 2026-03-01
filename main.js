/* Local SEO Audit Tool — Frontend */

const LOADING_MESSAGES = [
  "Fetching page content…",
  "Checking SSL certificate…",
  "Auditing meta tags…",
  "Analyzing structured data…",
  "Checking NAP consistency…",
  "Scanning Google signals…",
  "Measuring page speed…",
  "Testing mobile friendliness…",
  "Reviewing content signals…",
  "Running technical checks…",
  "Checking social signals…",
  "Calculating scores…",
];

let loadingInterval = null;
let progressInterval = null;

// ── Input handling ──────────────────────────────────

document.getElementById("urlInput").addEventListener("keydown", e => {
  if (e.key === "Enter") runAudit();
});

// ── Main audit function ─────────────────────────────

async function runAudit() {
  const input = document.getElementById("urlInput");
  const url = input.value.trim();

  if (!url) {
    showError("Please enter a website URL.");
    return;
  }

  hideError();
  showLoading();

  try {
    const res = await fetch("/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const data = await res.json();
    stopLoading();

    if (!res.ok || data.error) {
      showError(data.error || "Something went wrong. Please try again.");
      hideLoading();
      return;
    }

    renderResults(data);
  } catch (err) {
    stopLoading();
    hideLoading();
    showError("Network error — please check your connection and try again.");
  }
}

// ── Loading helpers ─────────────────────────────────

function showLoading() {
  document.getElementById("loadingSection").classList.remove("hidden");
  document.getElementById("resultsSection").classList.add("hidden");
  document.getElementById("featuresSection").classList.add("hidden");

  const btn = document.getElementById("auditBtn");
  btn.disabled = true;
  btn.querySelector(".btn-text").textContent = "Auditing…";
  btn.querySelector(".btn-spinner").classList.remove("hidden");

  let msgIdx = 0;
  const msgEl = document.getElementById("loadingMsg");
  const fill = document.getElementById("progressFill");

  msgEl.textContent = LOADING_MESSAGES[0];
  fill.style.width = "5%";

  loadingInterval = setInterval(() => {
    msgIdx = (msgIdx + 1) % LOADING_MESSAGES.length;
    msgEl.textContent = LOADING_MESSAGES[msgIdx];
  }, 1800);

  let progress = 5;
  progressInterval = setInterval(() => {
    progress = Math.min(progress + Math.random() * 4, 90);
    fill.style.width = progress + "%";
  }, 400);
}

function stopLoading() {
  clearInterval(loadingInterval);
  clearInterval(progressInterval);
  document.getElementById("progressFill").style.width = "100%";
  setTimeout(() => hideLoading(), 300);
}

function hideLoading() {
  document.getElementById("loadingSection").classList.add("hidden");
  const btn = document.getElementById("auditBtn");
  btn.disabled = false;
  btn.querySelector(".btn-text").textContent = "Run Audit";
  btn.querySelector(".btn-spinner").classList.add("hidden");
}

// ── Error helpers ───────────────────────────────────

function showError(msg) {
  const el = document.getElementById("errorMsg");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideError() {
  document.getElementById("errorMsg").classList.add("hidden");
}

// ── Results rendering ───────────────────────────────

function renderResults(data) {
  document.getElementById("resultsSection").classList.remove("hidden");
  document.getElementById("featuresSection").classList.add("hidden");

  // Scroll to results
  document.getElementById("resultsSection").scrollIntoView({ behavior: "smooth" });

  // Score
  const score = data.score.overall;
  const color = data.score.color;
  const grade = data.score.grade;

  animateNumber(document.getElementById("scoreNumber"), score);
  document.getElementById("scoreGrade").textContent = grade;
  document.getElementById("scoreGrade").style.color = color;

  // Arc
  const arc = document.getElementById("scoreArc");
  const circumference = 326.7;
  arc.style.stroke = color;
  setTimeout(() => {
    arc.style.strokeDashoffset = circumference - (circumference * score / 100);
  }, 100);

  // URL & date
  document.getElementById("auditedUrl").textContent = data.url;
  document.getElementById("auditedAt").textContent = `Audited at ${data.audited_at}`;

  // Summary pills
  document.getElementById("passCount").textContent = data.summary.pass;
  document.getElementById("warnCount").textContent = data.summary.warn;
  document.getElementById("failCount").textContent = data.summary.fail;

  // Categories grid
  renderCategories(data.sections);

  // Sections detail
  renderSections(data.sections);
}

function renderCategories(sections) {
  const grid = document.getElementById("categoriesGrid");
  grid.innerHTML = "";

  sections.forEach((section, idx) => {
    const score = section.score ?? 0;
    const color = scoreColor(score);

    const card = document.createElement("div");
    card.className = "cat-card";
    card.innerHTML = `
      <div class="cat-name">${section.name}</div>
      <div class="cat-score-row">
        <span class="cat-score" style="color:${color}">${score}%</span>
      </div>
      <div class="cat-bar">
        <div class="cat-bar-fill" style="width:0%;background:${color}" data-target="${score}"></div>
      </div>
    `;
    card.addEventListener("click", () => {
      const el = document.getElementById(`section-${idx}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        openSection(idx);
      }
    });
    grid.appendChild(card);
  });

  // Animate bars
  setTimeout(() => {
    document.querySelectorAll(".cat-bar-fill").forEach(bar => {
      bar.style.width = bar.dataset.target + "%";
    });
  }, 200);
}

function renderSections(sections) {
  const wrap = document.getElementById("sectionsWrap");
  wrap.innerHTML = "";

  sections.forEach((section, idx) => {
    const score = section.score ?? 0;
    const color = scoreColor(score);

    const passItems = section.items.filter(i => i.status === "pass").length;
    const total = section.items.length;

    const card = document.createElement("div");
    card.className = "section-card";
    card.id = `section-${idx}`;

    card.innerHTML = `
      <div class="section-header" onclick="toggleSection(${idx})">
        <div class="section-title-row">
          <span class="section-title-text">${section.name}</span>
          <span class="section-score-badge" style="color:${color};border:1px solid ${color}40">${score}% · ${passItems}/${total}</span>
        </div>
        <span class="section-chevron" id="chevron-${idx}">▼</span>
      </div>
      <div class="section-body hidden" id="body-${idx}">
        ${section.items.map(item => renderItem(item)).join("")}
      </div>
    `;
    wrap.appendChild(card);
  });

  // Open first failed section by default
  const firstFailed = sections.findIndex(s => s.items.some(i => i.status === "fail"));
  if (firstFailed >= 0) openSection(firstFailed);
  else openSection(0);
}

function renderItem(item) {
  const statusClass = `status-${item.status}`;
  const badgeClass = `badge-${item.status}`;
  const badgeText = item.status.toUpperCase();

  return `
    <div class="audit-item ${statusClass}">
      <span class="item-icon"></span>
      <div>
        <div class="item-label">${escHtml(item.label)}</div>
        <div class="item-detail">${escHtml(item.detail)}</div>
      </div>
      <span class="item-badge ${badgeClass}">${badgeText}</span>
    </div>
  `;
}

// ── Section accordion ───────────────────────────────

function toggleSection(idx) {
  const body = document.getElementById(`body-${idx}`);
  const chevron = document.getElementById(`chevron-${idx}`);
  const isOpen = !body.classList.contains("hidden");
  body.classList.toggle("hidden", isOpen);
  chevron.classList.toggle("open", !isOpen);
}

function openSection(idx) {
  const body = document.getElementById(`body-${idx}`);
  const chevron = document.getElementById(`chevron-${idx}`);
  if (body) body.classList.remove("hidden");
  if (chevron) chevron.classList.add("open");
}

// ── Reset ───────────────────────────────────────────

function resetForm() {
  document.getElementById("resultsSection").classList.add("hidden");
  document.getElementById("featuresSection").classList.remove("hidden");
  document.getElementById("urlInput").value = "";
  document.getElementById("urlInput").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Utils ───────────────────────────────────────────

function scoreColor(score) {
  if (score >= 90) return "#22c55e";
  if (score >= 75) return "#84cc16";
  if (score >= 60) return "#eab308";
  if (score >= 40) return "#f97316";
  return "#ef4444";
}

function animateNumber(el, target) {
  let current = 0;
  const step = target / 40;
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = Math.round(current);
    if (current >= target) clearInterval(timer);
  }, 25);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
