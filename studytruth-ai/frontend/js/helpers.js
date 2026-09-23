/* Shared helpers used across all page modules */

const ICONS = {
  dashboard: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>`,
  chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
  docs: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>`,
  conflict: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4M12 17h.01M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0z"/></svg>`,
  exam: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
  quiz: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 2-3 4"/><path d="M12 17h.01"/></svg>`,
  analytics: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-3"/></svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>`,
  upload: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg>`,
  file: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>`,
  inbox: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>`,
  alert: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 9v4M12 17h.01M10.3 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.7 3.86a2 2 0 0 0-3.4 0z"/></svg>`,
  scale: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v18M5 7l-3 7a4 4 0 0 0 6.2 0L5 7zM19 7l-3 7a4 4 0 0 0 6.2 0L19 7zM3 7h18"/></svg>`,
};

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function fmtDate(dateStr) {
  if (!dateStr) return "-";
  try {
    return new Date(dateStr).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch (e) { return dateStr; }
}

function titleCase(s) {
  return (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const DOC_TYPE_LABEL = {
  syllabus: "Syllabus", lecture_notes: "Lecture Notes", faculty_material: "Faculty Material",
  assignment: "Assignment", pyq: "Previous Year Qs", lab_manual: "Lab Manual",
  exam_instructions: "Exam Instructions", notice: "Notice", other: "Other",
};

function authorityLabel(rank) {
  const map = { 1: "Highest authority", 2: "High authority", 3: "Medium authority", 4: "Medium authority", 5: "Lower authority", 6: "Reference only" };
  return map[rank] || "Reference";
}

function stateBlock({ icon = "inbox", title, body, error = false }) {
  return `<div class="state-block ${error ? "error" : ""}">
    <div class="icon-ring">${ICONS[icon] || ICONS.inbox}</div>
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(body)}</p>
  </div>`;
}

function skeletonRows(n = 3, height = 54) {
  return Array.from({ length: n }).map(() => `<div class="skeleton" style="height:${height}px;margin-bottom:10px;"></div>`).join("");
}

function toast(message, kind = "info") {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.style.cssText = "position:fixed;bottom:22px;right:22px;z-index:999;display:flex;flex-direction:column;gap:8px;";
    document.body.appendChild(el);
  }
  const bg = kind === "error" ? "#C23B3B" : kind === "success" ? "#1F8A57" : "#161B29";
  const item = document.createElement("div");
  item.textContent = message;
  item.style.cssText = `background:${bg};color:white;padding:11px 16px;border-radius:10px;font-size:13px;font-weight:600;box-shadow:0 10px 30px -8px rgba(0,0,0,.35);max-width:320px;`;
  el.appendChild(item);
  setTimeout(() => { item.style.transition = "opacity .3s"; item.style.opacity = "0"; setTimeout(() => item.remove(), 300); }, 3200);
}

function confidencePillClass(conf) {
  return { high: "green", medium: "amber", low: "muted", none: "red" }[conf] || "muted";
}

/* ---------- Shared right-hand rail (Exam Mode / Quiz Mode) ---------- */
function sideRailShell({ goalIcon = "exam", goalTitle = "Your Goal", goalSub, statsTitle = "Quick Stats", recentTitle = "Recent" }) {
  return `
    <div class="side-rail">
      <div class="card goal-card">
        <div class="goal-icon">${ICONS[goalIcon]}</div>
        <div>
          <div class="goal-title">${escapeHtml(goalTitle)}</div>
          <div class="goal-sub">${escapeHtml(goalSub)}</div>
        </div>
      </div>
      <div class="card">
        <div class="section-title">${escapeHtml(statsTitle)}</div>
        <div class="mini-stats" id="rail-stats">${skeletonRows(4, 74)}</div>
      </div>
      <div class="card">
        <div class="section-title">${escapeHtml(recentTitle)} <span class="link-btn" onclick="navigateTo('analytics')">View all →</span></div>
        <div id="rail-recent">${skeletonRows(3, 46)}</div>
      </div>
    </div>`;
}

function renderMiniStats(container, stats) {
  container.innerHTML = stats.map((s) => `
    <div class="mini-stat">
      <div class="mini-icon stat-icon-${s.tone}">${ICONS[s.icon]}</div>
      <div class="mini-label">${escapeHtml(s.label)}</div>
      <div class="mini-value">${escapeHtml(String(s.value))}</div>
    </div>`).join("");
}

function renderRecentRail(container, items, emptyTitle, emptyBody) {
  if (!items.length) {
    container.innerHTML = stateBlock({ icon: "docs", title: emptyTitle, body: emptyBody });
    return;
  }
  container.innerHTML = items.map((it) => `
    <div class="recent-row">
      <div class="recent-icon">${ICONS[it.icon || "docs"]}</div>
      <div style="flex:1;min-width:0;">
        <div class="recent-title">${escapeHtml(it.title)}</div>
        <div class="recent-sub">${escapeHtml(it.sub)}</div>
      </div>
      ${it.badge ? `<span class="pill ${it.badgeClass || "pill-indigo"}">${escapeHtml(it.badge)}</span>` : ""}
    </div>`).join("");
}