async function loadDashboard() {
  const root = document.getElementById("page-dashboard");
  root.innerHTML = `
    <div class="hero-banner">
      <div class="hero-content">
        <h1>Welcome back 👋</h1>
        <p>Your study material, unified — StudyTruth AI checks every document for you and flags it when sources disagree.</p>
      </div>
      <div class="hero-actions">
        <button class="btn btn-primary" onclick="navigateTo('ask')">${ICONS.chat} Ask StudyTruth AI</button>
        <button class="btn btn-ghost-dark btn-secondary" style="border-color:transparent;" onclick="navigateTo('documents')">${ICONS.upload} Upload</button>
      </div>
    </div>

    <div id="dash-stats" class="grid grid-4">${skeletonRows(4, 100)}</div>

    <div class="grid grid-3 mt-24" style="grid-template-columns: 1.3fr 1fr;">
      <div class="card">
        <div class="section-title">Upcoming exams</div>
        <div id="dash-exams">${skeletonRows(2, 56)}</div>
      </div>
      <div class="card">
        <div class="section-title">Study progress</div>
        <div id="dash-progress">${skeletonRows(3, 40)}</div>
      </div>
    </div>

    <div class="grid grid-3 mt-24" style="grid-template-columns: 2fr 1fr;">
      <div class="card">
        <div class="section-title">Subjects <span class="link-btn" onclick="navigateTo('documents')">Manage documents →</span></div>
        <div id="dash-subjects">${skeletonRows(3, 60)}</div>
      </div>
      <div class="card">
        <div class="section-title">Quick actions</div>
        <div class="flex-col gap-8">
          <button class="quick-action" onclick="navigateTo('exam')">
            <span class="qa-icon">${ICONS.exam}</span>
            <span><span class="qa-label" style="display:block;">Exam prep mode</span><span class="qa-sub">Prioritized revision plan</span></span>
          </button>
          <button class="quick-action" onclick="navigateTo('quiz')">
            <span class="qa-icon">${ICONS.quiz}</span>
            <span><span class="qa-label" style="display:block;">Start a quiz</span><span class="qa-sub">Grounded MCQs</span></span>
          </button>
          <button class="quick-action" onclick="navigateTo('conflicts')">
            <span class="qa-icon">${ICONS.conflict}</span>
            <span><span class="qa-label" style="display:block;">Check for conflicts</span><span class="qa-sub">Compare two documents</span></span>
          </button>
          <button class="quick-action" onclick="navigateTo('documents')">
            <span class="qa-icon">${ICONS.upload}</span>
            <span><span class="qa-label" style="display:block;">Upload a document</span><span class="qa-sub">Syllabus, notes, PYQs...</span></span>
          </button>
        </div>
      </div>
    </div>

    <div class="card mt-24">
      <div class="section-title">Recent questions <span class="link-btn" onclick="navigateTo('ask')">Ask something new →</span></div>
      <div id="dash-recent">${skeletonRows(3, 44)}</div>
    </div>
  `;

  try {
    const data = await api.dashboard();
    renderDashStats(data);
    renderDashExams(data);
    renderDashProgress(data);
    renderDashSubjects(data);
    renderDashRecent(data);
  } catch (e) {
    document.getElementById("dash-stats").innerHTML = `<div class="card">${stateBlock({
      icon: "alert", title: "Can't reach the backend",
      body: "Start the FastAPI server (see README) then reload this page.", error: true,
    })}</div>`;
  }
}

function renderDashExams(data) {
  const el = document.getElementById("dash-exams");
  const exams = data.upcoming_exams || [];
  if (!exams.length) {
    el.innerHTML = stateBlock({ icon: "exam", title: "No exam dates found", body: "Upload an official notice with an exam date to see your countdown here." });
    return;
  }
  el.innerHTML = exams.map((e) => {
    const urgent = e.days_left <= 7;
    return `<div class="flex items-center justify-between hover-row" style="padding:12px 4px;border-bottom:1px solid var(--border);">
      <div class="flex items-center gap-12">
        <div class="citation-icon" style="${urgent ? "background:var(--red-bg);color:var(--red);" : ""}">${ICONS.exam}</div>
        <div>
          <div style="font-weight:700;font-size:13.5px;">${escapeHtml(e.subject)}</div>
          <div class="text-sm text-muted">${fmtDate(e.exam_date)}</div>
        </div>
      </div>
      <span class="pill ${urgent ? "pill-red" : "pill-indigo"}">${e.days_left >= 0 ? `${e.days_left} day${e.days_left !== 1 ? "s" : ""} left` : "Passed"}</span>
    </div>`;
  }).join("");
}

function renderDashProgress(data) {
  const el = document.getElementById("dash-progress");
  const progress = (data.study_progress || []).filter((p) => p.topics_total > 0);
  if (!progress.length) {
    el.innerHTML = stateBlock({ icon: "analytics", title: "No progress yet", body: "Mark topics done in Exam Mode to track progress here." });
    return;
  }
  el.innerHTML = progress.map((p) => `
    <div class="mt-8" style="margin-bottom:14px;">
      <div class="flex items-center justify-between text-sm" style="margin-bottom:5px;">
        <span style="font-weight:600;">${escapeHtml(p.subject)}</span>
        <span class="text-muted">${p.topics_done}/${p.topics_total} · ${p.percent}%</span>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${p.percent}%;"></div></div>
    </div>`).join("");
}

function renderDashStats(data) {
  const el = document.getElementById("dash-stats");
  const stats = [
    { label: "Documents indexed", value: data.total_documents, sub: `${data.subjects.length} subjects`, icon: "docs", tone: "indigo" },
    { label: "Quiz accuracy", value: data.quiz_accuracy_percent != null ? `${data.quiz_accuracy_percent}%` : "—", sub: `${data.total_quiz_attempts} attempts`, icon: "quiz", tone: "green" },
    { label: "Subjects tracked", value: data.subjects.length, sub: data.subjects.join(", ") || "None yet", icon: "dashboard", tone: "amber" },
    { label: "Questions asked", value: data.recent_questions.length, sub: "This session", icon: "chat", tone: "red" },
  ];
  el.innerHTML = stats.map((s) => `
    <div class="card stat-card">
      <div class="stat-icon stat-icon-${s.tone}">${ICONS[s.icon]}</div>
      <span class="stat-label">${escapeHtml(s.label)}</span>
      <span class="stat-value">${s.value}</span>
      <span class="stat-sub">${escapeHtml(String(s.sub))}</span>
    </div>`).join("");
}

function renderDashSubjects(data) {
  const el = document.getElementById("dash-subjects");
  if (!data.subjects.length) {
    el.innerHTML = stateBlock({ icon: "docs", title: "No documents yet", body: "Upload your syllabus, notes or PYQs to get started." });
    return;
  }
  el.innerHTML = data.subjects.map((s) => {
    const count = data.subject_document_counts[s] || 0;
    return `<div class="flex items-center justify-between hover-row" style="padding:11px 4px;border-bottom:1px solid var(--border);">
      <div class="flex items-center gap-12">
        <div class="citation-icon">${ICONS.docs}</div>
        <div>
          <div style="font-weight:700;font-size:13.5px;">${escapeHtml(s)}</div>
          <div class="text-sm text-muted">${count} document${count !== 1 ? "s" : ""}</div>
        </div>
      </div>
      <button class="btn btn-ghost btn-sm" onclick="goExamFor('${escapeHtml(s)}')">Study plan →</button>
    </div>`;
  }).join("");
}

function goExamFor(subject) {
  sessionStorage.setItem("studytruth_preselect_subject", subject);
  navigateTo("exam");
}

function renderDashRecent(data) {
  const el = document.getElementById("dash-recent");
  if (!data.recent_questions.length) {
    el.innerHTML = stateBlock({ icon: "chat", title: "No questions yet", body: "Ask StudyTruth AI something about your study material to see it here." });
    return;
  }
  el.innerHTML = data.recent_questions.map((q) => `
    <div class="flex items-center justify-between hover-row" style="padding:10px 4px;border-bottom:1px solid var(--border);">
      <div class="flex items-center gap-12">
        ${ICONS.chat.replace('viewBox="0 0 24 24"', 'viewBox="0 0 24 24" style="width:16px;height:16px;color:var(--text-muted)"')}
        <span class="text-sm" style="color:var(--text-primary);">${escapeHtml(q.query)}</span>
      </div>
      <span class="pill ${q.grounded ? "pill-green" : "pill-muted"}">${q.grounded ? "Grounded" : "General"}</span>
    </div>`).join("");
}
