let quizState = null;

async function initQuizPage() {
  const root = document.getElementById("page-quiz");
  root.innerHTML = `
    <div class="topbar">
      <div><h1>Quiz Mode</h1><p class="subtitle">Grounded multiple-choice questions generated straight from your study material.</p></div>
    </div>
    <div class="page-layout">
      <div>
        <div class="card">
          <div class="flex gap-12" style="align-items:flex-end;">
            <div class="field" style="flex:1;margin:0;"><label>Subject</label><select id="quiz-subject" data-subject-select></select></div>
            <div class="field" style="flex:1;margin:0;"><label>Topic</label><input id="quiz-topic" placeholder="e.g. VLAN, checksum, backpropagation" /></div>
            <div class="field" style="width:140px;margin:0;"><label># Questions</label><input id="quiz-num" type="number" value="5" min="3" max="10" /></div>
            <button class="btn btn-primary" id="quiz-start-btn">${ICONS.quiz} Start quiz</button>
          </div>
        </div>
        <div id="quiz-body" class="mt-24"></div>
      </div>
      ${sideRailShell({ goalIcon: "quiz", goalTitle: "Your Goal", goalSub: "Score higher. Stay consistent.", recentTitle: "Recent Quizzes" })}
    </div>
  `;
  populateSubjectSelects();
  document.getElementById("quiz-start-btn").addEventListener("click", startQuiz);
  document.getElementById("quiz-body").innerHTML = stateBlock({
    icon: "quiz", title: "Test yourself", body: "Enter a topic from your syllabus (e.g. VLAN) and generate a grounded quiz.",
  });

  loadQuizRail();
}

async function loadQuizRail() {
  try {
    const [dash, analytics] = await Promise.all([api.dashboard(), api.analytics()]);
    renderMiniStats(document.getElementById("rail-stats"), [
      { label: "Documents", value: dash.total_documents, icon: "docs", tone: "indigo" },
      { label: "Quiz Accuracy", value: dash.quiz_accuracy_percent != null ? `${dash.quiz_accuracy_percent}%` : "—", icon: "quiz", tone: "green" },
      { label: "Attempts", value: dash.total_quiz_attempts, icon: "dashboard", tone: "amber" },
      { label: "Weak Topics", value: (analytics.weak_topics || []).length, icon: "analytics", tone: "red" },
    ]);
    const stats = (analytics.quiz_stats || []).slice(0, 5);
    renderRecentRail(document.getElementById("rail-recent"), stats.map((q) => {
      const acc = q.total_count ? Math.round((q.correct_count / q.total_count) * 100) : 0;
      return { icon: "quiz", title: titleCase(q.topic), sub: `${q.correct_count}/${q.total_count} answered`, badge: `${acc}%`, badgeClass: acc >= 60 ? "pill-green" : "pill-red" };
    }), "No quizzes yet", "Take a quiz to see your recent topics here.");
  } catch (e) {
    document.getElementById("rail-stats").innerHTML = stateBlock({ icon: "alert", title: "Can't reach backend", body: "Start the FastAPI server to see live stats.", error: true });
    document.getElementById("rail-recent").innerHTML = "";
  }
}

async function startQuiz() {
  const subject = document.getElementById("quiz-subject").value || undefined;
  const topic = document.getElementById("quiz-topic").value.trim();
  const num = parseInt(document.getElementById("quiz-num").value, 10) || 5;
  const bodyEl = document.getElementById("quiz-body");
  if (!topic) { toast("Enter a topic first", "error"); return; }

  bodyEl.innerHTML = `<div class="card"><div class="flex items-center gap-8 text-muted text-sm"><div class="spinner dark"></div> Generating grounded questions...</div></div>`;

  try {
    const quiz = await api.generateQuiz(topic, subject, num);
    if (!quiz.questions.length) {
      bodyEl.innerHTML = `<div class="card">${stateBlock({ icon: "quiz", title: "Not enough material", body: `Couldn't find enough study material on "${topic}" to build a quiz. Try a different topic or upload more notes.` })}</div>`;
      return;
    }
    quizState = { topic, subject, questions: quiz.questions, answers: new Array(quiz.questions.length).fill(null), submitted: false };
    renderQuiz();
  } catch (e) {
    bodyEl.innerHTML = `<div class="card">${stateBlock({ icon: "alert", title: "Couldn't generate quiz", body: e.message, error: true })}</div>`;
  }
}

function renderQuiz() {
  const bodyEl = document.getElementById("quiz-body");
  const { questions, answers, submitted } = quizState;
  const letters = ["A", "B", "C", "D", "E"];

  bodyEl.innerHTML = questions.map((q, qi) => `
    <div class="card mt-16" style="${qi === 0 ? "margin-top:0;" : ""}">
      <div class="text-sm" style="font-weight:700;margin-bottom:12px;">Q${qi + 1}. ${escapeHtml(q.question)}</div>
      <div>
        ${q.options.map((opt, oi) => {
          let cls = "quiz-option";
          if (submitted) {
            if (oi === q.correct_index) cls += " correct";
            else if (answers[qi] === oi) cls += " incorrect";
          } else if (answers[qi] === oi) cls += " selected";
          return `<div class="${cls}" onclick="selectQuizAnswer(${qi}, ${oi})">
            <span class="opt-letter">${letters[oi]}</span><span>${escapeHtml(opt)}</span>
          </div>`;
        }).join("")}
      </div>
      ${submitted ? `<div class="text-sm mt-8" style="color:var(--text-secondary);background:var(--surface-sunken);padding:10px 12px;border-radius:8px;">💡 ${escapeHtml(q.explanation)}</div>` : ""}
    </div>
  `).join("") + renderQuizFooter();
}

function renderQuizFooter() {
  const { answers, submitted, questions } = quizState;
  if (submitted) {
    const correct = questions.filter((q, i) => answers[i] === q.correct_index).length;
    const pct = Math.round((correct / questions.length) * 100);
    return `<div class="card mt-16">
      <div class="flex items-center justify-between">
        <div>
          <div class="stat-value serif">${correct}/${questions.length}</div>
          <div class="text-sm text-muted">Score: ${pct}%</div>
        </div>
        <button class="btn btn-secondary" onclick="document.getElementById('quiz-topic').value='';document.getElementById('quiz-body').innerHTML='';initQuizPage();">Try another topic</button>
      </div>
    </div>`;
  }
  const answeredCount = answers.filter((a) => a !== null).length;
  return `<div class="card mt-16 flex items-center justify-between">
    <span class="text-sm text-muted">${answeredCount}/${questions.length} answered</span>
    <button class="btn btn-primary" onclick="submitQuiz()" ${answeredCount < questions.length ? "disabled" : ""}>Submit quiz</button>
  </div>`;
}

function selectQuizAnswer(qi, oi) {
  if (quizState.submitted) return;
  quizState.answers[qi] = oi;
  renderQuiz();
}

async function submitQuiz() {
  quizState.submitted = true;
  renderQuiz();
  const { topic, subject, questions, answers } = quizState;
  for (let i = 0; i < questions.length; i++) {
    try {
      await api.logQuizAnswer({
        subject, topic, question: questions[i].question,
        correct: answers[i] === questions[i].correct_index,
      });
    } catch (e) { /* non-fatal */ }
  }
  loadQuizRail();
}