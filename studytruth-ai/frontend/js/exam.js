async function initExamPage() {
  const root = document.getElementById("page-exam");
  root.innerHTML = `
    <div class="topbar">
      <div><h1>Exam Preparation Mode</h1><p class="subtitle">A prioritized revision plan built from your syllabus + previous year questions.</p></div>
    </div>
    <div class="page-layout">
      <div>
        <div class="card">
          <div class="flex gap-12" style="align-items:flex-end;">
            <div class="field" style="flex:1;margin:0;"><label>Subject</label><select id="exam-subject" data-subject-select data-allow-empty="false"></select></div>
            <div class="field" style="flex:1;margin:0;"><label>Topics already completed (comma-separated, optional)</label><input id="exam-completed" placeholder="e.g. checksum, subnetting" /></div>
            <button class="btn btn-primary" id="exam-generate-btn">${ICONS.exam} Generate revision plan</button>
          </div>
        </div>
        <div id="exam-result" class="mt-24"></div>
      </div>
      ${sideRailShell({ goalIcon: "exam", goalTitle: "Your Goal", goalSub: "Score higher. Stay consistent.", recentTitle: "Study Progress" })}
    </div>
  `;
  populateSubjectSelects();

  const preselect = sessionStorage.getItem("studytruth_preselect_subject");
  if (preselect) {
    document.getElementById("exam-subject").value = preselect;
    sessionStorage.removeItem("studytruth_preselect_subject");
  }

  document.getElementById("exam-generate-btn").addEventListener("click", runExamPlan);
  document.getElementById("exam-result").innerHTML = stateBlock({
    icon: "exam", title: "Build your revision plan",
    body: "Pick a subject and generate a prioritized plan based on syllabus coverage and how often topics appear in past exams.",
  });

  loadExamRail();
}

async function loadExamRail() {
  try {
    const data = await api.dashboard();
    const doneTotal = (data.study_progress || []).reduce((acc, p) => {
      acc.done += p.topics_done; acc.total += p.topics_total; return acc;
    }, { done: 0, total: 0 });
    renderMiniStats(document.getElementById("rail-stats"), [
      { label: "Documents", value: data.total_documents, icon: "docs", tone: "indigo" },
      { label: "Quiz Accuracy", value: data.quiz_accuracy_percent != null ? `${data.quiz_accuracy_percent}%` : "—", icon: "quiz", tone: "green" },
      { label: "Subjects", value: data.subjects.length, icon: "dashboard", tone: "amber" },
      { label: "Topics Done", value: `${doneTotal.done}/${doneTotal.total}`, icon: "exam", tone: "red" },
    ]);
    const progress = (data.study_progress || []).filter((p) => p.topics_total > 0);
    renderRecentRail(document.getElementById("rail-recent"), progress.map((p) => ({
      icon: "exam", title: p.subject, sub: `${p.topics_done}/${p.topics_total} topics`,
      badge: `${p.percent}%`, badgeClass: p.percent >= 60 ? "pill-green" : "pill-amber",
    })), "No progress yet", "Mark topics done to see revision progress here.");
  } catch (e) {
    document.getElementById("rail-stats").innerHTML = stateBlock({ icon: "alert", title: "Can't reach backend", body: "Start the FastAPI server to see live stats.", error: true });
    document.getElementById("rail-recent").innerHTML = "";
  }
}

async function runExamPlan() {
  const subject = document.getElementById("exam-subject").value;
  const completedRaw = document.getElementById("exam-completed").value;
  const completed = completedRaw.split(",").map((t) => t.trim()).filter(Boolean);
  const resultEl = document.getElementById("exam-result");
  if (!subject) { toast("Select a subject first", "error"); return; }

  resultEl.innerHTML = `<div class="card"><div class="flex items-center gap-8 text-muted text-sm"><div class="spinner dark"></div> Building your revision plan...</div></div>`;

  try {
    const plan = await api.studyPlan(subject, completed);
    if (!plan.plan.length) {
      resultEl.innerHTML = `<div class="card">${stateBlock({ icon: "exam", title: "Not enough material yet", body: plan.summary || "Upload a syllabus and some notes for this subject first." })}</div>`;
      return;
    }
    const pct = plan.total_topics ? Math.round(((plan.total_topics - plan.topics_remaining) / plan.total_topics) * 100) : 0;

    resultEl.innerHTML = `
      <div class="card">
        <div class="flex items-center justify-between mt-8" style="margin-bottom:14px;">
          <div class="text-sm" style="color:var(--text-secondary);">${escapeHtml(plan.summary)}</div>
          <span class="pill pill-indigo">${pct}% covered</span>
        </div>
        <div class="progress-track mt-8" style="margin-bottom:20px;"><div class="progress-fill" style="width:${pct}%;"></div></div>
        <div id="plan-rows"></div>
      </div>
      <div class="grid grid-2 mt-24">
        <div class="card">
          <div class="section-title">Practice questions</div>
          <div id="exam-pyqs">${skeletonRows(2, 46)}</div>
        </div>
        <div class="card">
          <div class="section-title">Quick revision notes</div>
          <div id="exam-notes">${skeletonRows(2, 46)}</div>
        </div>
      </div>
    `;
    renderPlanRows(plan, subject);
    loadExamPyqsAndNotes(plan, subject);
  } catch (e) {
    resultEl.innerHTML = `<div class="card">${stateBlock({ icon: "alert", title: "Couldn't build a plan", body: e.message, error: true })}</div>`;
  }
}

function renderPlanRows(plan, subject) {
  const el = document.getElementById("plan-rows");
  el.innerHTML = plan.plan.map((t) => `
    <div class="plan-row ${t.status === "done" ? "done" : ""}" data-topic="${escapeHtml(t.topic)}">
      <span class="priority-dot ${t.priority}"></span>
      <div style="flex:1;">
        <div class="plan-topic">${escapeHtml(t.topic)}</div>
        <div class="plan-reason">${escapeHtml(t.reason)}</div>
      </div>
      <span class="pill pill-${t.priority === "high" ? "red" : t.priority === "medium" ? "amber" : "muted"}">${titleCase(t.priority)} priority</span>
      <button class="btn btn-sm ${t.status === "done" ? "btn-secondary" : "btn-primary"}" onclick="toggleTopicDone(this, '${escapeHtml(subject)}', '${escapeHtml(t.topic)}', '${t.status}')">
        ${t.status === "done" ? "✓ Done" : "Mark done"}
      </button>
    </div>`).join("");
}

async function toggleTopicDone(btn, subject, topic, currentStatus) {
  const newStatus = currentStatus === "done" ? "not_started" : "done";
  btn.disabled = true;
  try {
    await api.setTopicStatus(subject, topic, newStatus);
    const row = btn.closest(".plan-row");
    row.classList.toggle("done", newStatus === "done");
    btn.textContent = newStatus === "done" ? "✓ Done" : "Mark done";
    btn.className = `btn btn-sm ${newStatus === "done" ? "btn-secondary" : "btn-primary"}`;
    btn.setAttribute("onclick", `toggleTopicDone(this, '${subject}', '${topic}', '${newStatus}')`);
    loadExamRail();
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function loadExamPyqsAndNotes(plan, subject) {
  const topTopic = plan.plan.find((t) => t.status !== "done")?.topic || plan.plan[0].topic;
  try {
    const pyqRes = await api.pyqs(topTopic, subject);
    const pyqEl = document.getElementById("exam-pyqs");
    if (!pyqRes.results.length) {
      pyqEl.innerHTML = stateBlock({ icon: "exam", title: "No PYQs found", body: `No previous year questions matched "${topTopic}" yet.` });
    } else {
      pyqEl.innerHTML = `<div class="text-sm text-muted" style="margin-bottom:8px;">For: <strong style="text-transform:capitalize;">${escapeHtml(topTopic)}</strong></div>` +
        pyqRes.results.slice(0, 3).map(renderCitationCard).join("");
    }
  } catch (e) {
    document.getElementById("exam-pyqs").innerHTML = stateBlock({ icon: "alert", title: "Couldn't load PYQs", body: e.message, error: true });
  }

  try {
    const summary = await tools_summarize(topTopic, subject);
    document.getElementById("exam-notes").innerHTML = summary
      ? `<div class="text-sm" style="line-height:1.6;">${escapeHtml(summary)}</div>`
      : stateBlock({ icon: "docs", title: "No notes found", body: "Upload lecture notes for this topic to see quick revision notes." });
  } catch (e) {
    document.getElementById("exam-notes").innerHTML = stateBlock({ icon: "alert", title: "Couldn't load notes", body: e.message, error: true });
  }
}

async function tools_summarize(topic, subject) {
  const res = await api.ask(`Summarize ${topic}`, subject);
  return res.grounded ? res.answer : null;
}