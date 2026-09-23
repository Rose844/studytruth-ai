/* App shell: sidebar nav + page switching + global bootstrap */

const STATE = {
  subjects: [],
  documents: [],
  currentPage: "dashboard",
};

function navigateTo(page) {
  STATE.currentPage = page;
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === `page-${page}`));
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.page === page));
  const loaders = {
    dashboard: loadDashboard,
    ask: initAskPage,
    documents: loadDocumentsPage,
    conflicts: initConflictsPage,
    exam: initExamPage,
    quiz: initQuizPage,
    analytics: loadAnalyticsPage,
  };
  if (loaders[page]) loaders[page]();
}

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => navigateTo(btn.dataset.page));
  });
}

async function refreshSubjects() {
  try {
    const docs = await api.listDocuments();
    STATE.documents = docs;
    STATE.subjects = [...new Set(docs.map((d) => d.subject))].sort();
  } catch (e) {
    STATE.documents = [];
    STATE.subjects = [];
  }
  populateSubjectSelects();
}

function populateSubjectSelects() {
  document.querySelectorAll("[data-subject-select]").forEach((sel) => {
    const current = sel.value;
    const allowEmpty = sel.dataset.allowEmpty !== "false";
    sel.innerHTML = (allowEmpty ? `<option value="">All subjects</option>` : "") +
      STATE.subjects.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
    if (current && STATE.subjects.includes(current)) sel.value = current;
  });
}

async function checkBackendHealth() {
  const dot = document.getElementById("mode-dot");
  const label = document.getElementById("mode-label");
  try {
    const health = await api.health();
    const llmCloud = health.mode.llm === "foundry";
    dot.classList.toggle("offline", !llmCloud);
    label.textContent = llmCloud
      ? "Connected · Foundry LLM"
      : "Connected · Local engine (offline mode)";
  } catch (e) {
    dot.classList.add("offline");
    label.textContent = "Backend unreachable — start the FastAPI server";
  }
}

window.addEventListener("DOMContentLoaded", async () => {
  setupNav();
  checkBackendHealth();
  await refreshSubjects();
  navigateTo("dashboard");
});
