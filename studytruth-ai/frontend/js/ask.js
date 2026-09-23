const ASK_SUGGESTIONS = [
  "Is VLAN included in my CN syllabus?",
  "What should I study for my CN exam tomorrow?",
  "Explain VLAN like I'm a beginner.",
  "Give me 5 MCQs on VLAN.",
  "I have two syllabi. What changed?",
  "These two documents say different things. Which one should I follow?",
  "Give me PYQs related to checksum.",
];

let askInitialized = false;

function initAskPage() {
  const root = document.getElementById("page-ask");
  if (!askInitialized) {
    root.innerHTML = `
      <div class="topbar">
        <div><h1>Ask My Study Material</h1><p class="subtitle">Grounded answers with sources — conflicts are flagged automatically.</p></div>
        <select id="ask-subject" class="field" style="margin:0;" data-subject-select></select>
      </div>
      <div class="chat-layout">
        <div class="card chat-window">
          <div id="chat-scroll" class="chat-scroll"></div>
          <div class="chat-input-row">
            <textarea id="chat-input" placeholder="Ask anything about your syllabus, notes, PYQs..." rows="1"></textarea>
            <button id="chat-send" class="btn btn-primary">Ask</button>
          </div>
        </div>
        <div class="card">
          <div class="section-title" style="margin-bottom:10px;">Try asking</div>
          <div id="ask-suggestions"></div>
        </div>
      </div>
    `;
    document.getElementById("ask-suggestions").innerHTML = ASK_SUGGESTIONS
      .map((q) => `<button class="suggestion-chip" onclick="askQuestion(${JSON.stringify(q)})">${escapeHtml(q)}</button>`).join("");

    document.getElementById("chat-send").addEventListener("click", () => {
      const input = document.getElementById("chat-input");
      if (input.value.trim()) askQuestion(input.value.trim());
    });
    document.getElementById("chat-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const input = e.target;
        if (input.value.trim()) askQuestion(input.value.trim());
      }
    });

    renderChatEmptyState();
    askInitialized = true;
  }
  populateSubjectSelects();
}

function renderChatEmptyState() {
  document.getElementById("chat-scroll").innerHTML = stateBlock({
    icon: "chat", title: "Ask anything about your study material",
    body: "StudyTruth AI searches your syllabus, notes, PYQs and assignments — and flags it clearly if sources disagree.",
  });
}

async function askQuestion(query) {
  const scroll = document.getElementById("chat-scroll");
  if (scroll.querySelector(".state-block")) scroll.innerHTML = "";

  document.getElementById("chat-input").value = "";

  const userMsg = document.createElement("div");
  userMsg.className = "msg user";
  userMsg.innerHTML = `<div class="msg-bubble-user">${escapeHtml(query)}</div>`;
  scroll.appendChild(userMsg);

  const loadingMsg = document.createElement("div");
  loadingMsg.className = "msg assistant";
  loadingMsg.innerHTML = `<div class="assistant-block"><div class="assistant-answer flex items-center gap-8"><div class="spinner dark"></div> Searching your study material...</div></div>`;
  scroll.appendChild(loadingMsg);
  scroll.scrollTop = scroll.scrollHeight;

  const subject = document.getElementById("ask-subject").value || null;

  try {
    const res = await api.ask(query, subject);
    loadingMsg.innerHTML = renderAssistantResponse(res);
  } catch (e) {
    loadingMsg.innerHTML = `<div class="assistant-block"><div class="assistant-answer">${stateBlock({ icon: "alert", title: "Something went wrong", body: e.message, error: true })}</div></div>`;
  }
  scroll.scrollTop = scroll.scrollHeight;
}

function renderAssistantResponse(res) {
  const confClass = confidencePillClass(res.confidence);
  const groundingText = res.grounded
    ? `Grounded in ${res.citations.length} source${res.citations.length !== 1 ? "s" : ""} · ${titleCase(res.tool_used)}`
    : `Not found in your documents · General knowledge fallback`;

  let html = `<div class="assistant-block">`;
  html += `<div class="assistant-answer">${escapeHtml(res.answer).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/^• /gm, "&bull; ")}</div>`;

  if (res.ai_generated_note) {
    html += `<div class="ai-note">${ICONS.alert} <span>${escapeHtml(res.ai_generated_note)}</span></div>`;
  }

  if (res.conflicts && res.conflicts.length) {
    html += res.conflicts.map((c) => `
      <div class="conflict-block">
        <div class="conflict-title">${ICONS.conflict} Conflict detected: "${escapeHtml(c.topic)}"</div>
        <div class="text-sm" style="margin-bottom:6px;"><strong>${escapeHtml(c.doc_a.filename)}</strong>: ${escapeHtml(c.statement_a)}</div>
        <div class="text-sm" style="margin-bottom:10px;"><strong>${escapeHtml(c.doc_b.filename)}</strong>: ${escapeHtml(c.statement_b)}</div>
        <div class="text-sm" style="color:var(--text-secondary);">${escapeHtml(c.resolution)}</div>
        <div class="mt-8"><span class="pill pill-${c.confidence === "low" ? "red" : "green"}">${c.confidence === "low" ? "Unresolved — verify with faculty" : "Resolved via authority + recency"}</span></div>
      </div>`).join("");
  }

  if (res.quiz) html += renderInlineQuiz(res.quiz);
  if (res.study_plan) html += renderInlineStudyPlan(res.study_plan);
  if (res.comparison) html += renderInlineComparison(res.comparison);

  if (res.citations && res.citations.length) {
    html += `<div class="citations-wrap">
      <div class="citations-label">Sources used</div>
      ${res.citations.map(renderCitationCard).join("")}
    </div>`;
  }

  if (res.reasoning_trace && res.reasoning_trace.length) {
    html += `<details class="reasoning-trace"><summary>Agent reasoning (${res.reasoning_trace.length} steps)</summary>
      <ol>${res.reasoning_trace.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ol></details>`;
  }

  html += `<div class="grounding-bar">
    <span class="grounding-dot ${confClass === "green" ? "high" : confClass === "amber" ? "medium" : confClass === "red" ? "none" : "low"}"></span>
    <span>${escapeHtml(groundingText)}</span>
    <span class="pill pill-${confClass}" style="margin-left:auto;">${titleCase(res.confidence)} confidence</span>
  </div>`;
  html += `</div>`;
  return html;
}

function renderCitationCard(c) {
  return `<div class="citation-card">
    <div class="citation-icon">${ICONS.file}</div>
    <div>
      <div><span class="citation-filename">${escapeHtml(c.filename)}</span> <span class="pill pill-muted" style="margin-left:6px;">${DOC_TYPE_LABEL[c.doc_type] || c.doc_type}</span></div>
      <div class="citation-meta">${escapeHtml(c.subject)} · ${escapeHtml(c.version)} · ${fmtDate(c.upload_date)} · <span class="authority-rank-${c.authority_rank}" style="padding:1px 6px;border-radius:6px;">${authorityLabel(c.authority_rank)}</span></div>
      <div class="citation-snippet">"${escapeHtml(c.snippet)}"</div>
    </div>
  </div>`;
}

function renderInlineQuiz(quiz) {
  if (!quiz.questions || !quiz.questions.length) return "";
  return `<div style="margin:0 17px 15px;padding:13px 14px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--bg);">
    <div style="font-weight:700;font-size:12.5px;margin-bottom:8px;">${ICONS.quiz.replace('viewBox="0 0 24 24"','viewBox="0 0 24 24" style="width:14px;height:14px;vertical-align:-2px;"')} ${quiz.questions.length} practice questions generated</div>
    <div class="text-sm text-muted mt-8">Head to <a href="#" onclick="navigateTo('quiz');return false;" style="color:var(--indigo);font-weight:700;">Quiz Mode</a> to attempt these with scoring.</div>
  </div>`;
}

function renderInlineStudyPlan(plan) {
  if (!plan.plan || !plan.plan.length) return "";
  const top = plan.plan.filter((p) => p.status !== "done").slice(0, 5);
  return `<div style="margin:0 17px 15px;padding:13px 14px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--bg);">
    <div style="font-weight:700;font-size:12.5px;margin-bottom:8px;">Top priority topics</div>
    ${top.map((t) => `<div class="flex items-center gap-8" style="margin-bottom:6px;">
      <span class="priority-dot ${t.priority}"></span>
      <span class="text-sm" style="text-transform:capitalize;">${escapeHtml(t.topic)}</span>
    </div>`).join("")}
    <div class="text-sm text-muted mt-8">Full plan in <a href="#" onclick="navigateTo('exam');return false;" style="color:var(--indigo);font-weight:700;">Exam Mode</a>.</div>
  </div>`;
}

function renderInlineComparison(cmp) {
  return `<div style="margin:0 17px 15px;padding:13px 14px;border:1px solid var(--border);border-radius:var(--radius-md);background:var(--bg);">
    <div class="flex gap-12" style="flex-wrap:wrap;">
      <span class="pill pill-green">+${cmp.added_topics.length} added</span>
      <span class="pill pill-red">-${cmp.removed_topics.length} removed</span>
      <span class="pill pill-amber">${cmp.modified_topics.length} modified</span>
    </div>
    <div class="text-sm text-muted mt-8">Full breakdown in <a href="#" onclick="navigateTo('conflicts');return false;" style="color:var(--indigo);font-weight:700;">Conflict Checker</a>.</div>
  </div>`;
}
