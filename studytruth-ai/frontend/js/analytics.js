const DONUT_COLORS = ["#5B5FF2", "#17A566", "#E29314", "#3B82F6", "#E43F5A", "#8B7BFA"];

async function loadAnalyticsPage() {
  const root = document.getElementById("page-analytics");
  root.innerHTML = `
    <div class="topbar">
      <div class="page-head-row"><span class="page-icon page-icon-indigo">${ICONS.analytics}</span><div><h1>Study Analytics</h1><p class="subtitle">Track your performance, identify weak topics and make better study decisions.</p></div></div>
      <select id="analytics-subject" class="input" style="width:auto;" data-subject-select></select>
    </div>
    <div id="analytics-body">${skeletonRows(4, 100)}</div>
  `;
  populateSubjectSelects();
  document.getElementById("analytics-subject").addEventListener("change", () => renderAnalytics());
  renderAnalytics();
}

async function renderAnalytics() {
  const subject = document.getElementById("analytics-subject").value || undefined;
  const body = document.getElementById("analytics-body");
  body.innerHTML = skeletonRows(4, 100);

  try {
    const data = await api.analytics(subject);
    if (!data.quiz_stats.length && !data.topic_progress.length) {
      body.innerHTML = stateBlock({
        icon: "analytics", title: "No activity yet",
        body: "Take a quiz or mark topics as done in Exam Mode to start building your analytics.",
      });
      return;
    }

    const totalAttempts = data.quiz_stats.reduce((s, q) => s + q.total_count, 0);
    const totalCorrect = data.quiz_stats.reduce((s, q) => s + q.correct_count, 0);
    const overallAccuracy = totalAttempts ? Math.round((totalCorrect / totalAttempts) * 100) : 0;
    const withAccuracy = data.quiz_stats.map((q) => ({
      ...q, accuracy: q.total_count ? Math.round((q.correct_count / q.total_count) * 100) : 0,
    }));

    body.innerHTML = `
      <div class="grid grid-4">
        ${statCard("indigo", "docs", "Overall Accuracy", `${overallAccuracy}%`, totalAttempts >= 5 ? "up" : null, `${totalAttempts} question${totalAttempts !== 1 ? "s" : ""} attempted`)}
        ${statCard("green", "quiz", "Topics Attempted", data.quiz_stats.length, null, "via quizzes")}
        ${statCard("red", "alert", "Weak Topics", data.weak_topics.length, null, "below 60% accuracy")}
        ${statCard("amber", "exam", "Topics Completed", `${data.topics_done}/${data.topics_total}`, null, "marked done")}
      </div>

      <div class="grid mt-24" style="grid-template-columns: 1.3fr 1fr 1fr; align-items:start;">
        <div class="card">
          <div class="section-title">Performance Overview</div>
          <div class="linechart-wrap">${lineChartSvg(withAccuracy)}</div>
        </div>

        <div class="card">
          <div class="section-title">Topic-wise Accuracy</div>
          ${donutChart(withAccuracy, overallAccuracy)}
        </div>

        <div class="insights-panel">
          <div class="section-title">💡 AI Insights</div>
          <p>Based on your recent performance, focus on these topics:</p>
          ${data.weak_topics.length
            ? data.weak_topics.slice(0, 3).map((t, i) => `
              <div class="insight-row">
                <span class="insight-num">${i + 1}</span>
                <span class="insight-topic" style="text-transform:capitalize;">${escapeHtml(t.topic)}</span>
                <span class="insight-tag">${Math.round(t.accuracy * 100) < 50 ? "Weak" : "Medium"}</span>
              </div>`).join("")
            : `<div class="insight-row"><span class="insight-topic">No weak topics — nice work!</span></div>`}
          <button class="btn btn-primary" onclick="navigateTo('exam')">View Detailed Analysis →</button>
        </div>
      </div>

      <div class="grid mt-24" style="grid-template-columns: 2fr 1fr; align-items:start;">
        <div class="card">
          <div class="section-title">Topic Performance</div>
          ${withAccuracy.length ? `
          <table class="data-table">
            <thead><tr><th>Topic</th><th>Subject</th><th>Accuracy</th><th>Questions</th><th>Status</th></tr></thead>
            <tbody>
              ${withAccuracy.map((q) => `
                <tr>
                  <td><div class="dt-topic-row"><span class="citation-icon" style="width:28px;height:28px;border-radius:8px;">${ICONS.docs}</span><span style="text-transform:capitalize;">${escapeHtml(q.topic)}</span></div></td>
                  <td><span class="pill pill-indigo">${escapeHtml(q.subject || "")}</span></td>
                  <td><div class="dt-bar-cell"><div class="progress-track" style="width:70px;"><div class="progress-fill" style="width:${q.accuracy}%;background:${barColor(q.accuracy)};"></div></div><span class="text-sm text-muted">${q.accuracy}%</span></div></td>
                  <td class="text-sm text-muted">${q.total_count}</td>
                  <td><span class="pill ${statusPillClass(q.accuracy)}">${statusLabel(q.accuracy)}</span></td>
                </tr>`).join("")}
            </tbody>
          </table>` : stateBlock({ icon: "quiz", title: "No quizzes yet", body: "Take a quiz to see topic-wise performance here." })}
        </div>

        <div class="card">
          <div class="section-title">Quick Actions</div>
          <div class="flex-col gap-8">
            <button class="quick-action" onclick="navigateTo('quiz')">
              <span class="qa-icon">${ICONS.quiz}</span>
              <span><span class="qa-label" style="display:block;">Start Quiz</span><span class="qa-sub">Test your knowledge</span></span>
            </button>
            <button class="quick-action" onclick="navigateTo('exam')">
              <span class="qa-icon">${ICONS.exam}</span>
              <span><span class="qa-label" style="display:block;">Study Mode</span><span class="qa-sub">Revise &amp; learn topics</span></span>
            </button>
            <button class="quick-action" onclick="navigateTo('documents')">
              <span class="qa-icon">${ICONS.upload}</span>
              <span><span class="qa-label" style="display:block;">Upload Document</span><span class="qa-sub">Add notes, PYQs, syllabus</span></span>
            </button>
            <button class="quick-action" onclick="navigateTo('conflicts')">
              <span class="qa-icon">${ICONS.conflict}</span>
              <span><span class="qa-label" style="display:block;">Check Conflicts</span><span class="qa-sub">Compare 2 documents</span></span>
            </button>
          </div>
        </div>
      </div>

      <div class="card mt-24">
        <div class="section-title">Revision status</div>
        ${data.topic_progress.length ? `<div class="grid grid-3">
          ${data.topic_progress.map((p) => `
            <div class="flex items-center gap-8" style="padding:8px 0;">
              <span class="pill ${p.status === "done" ? "pill-green" : "pill-muted"}">${titleCase(p.status)}</span>
              <span class="text-sm" style="text-transform:capitalize;">${escapeHtml(p.topic)}</span>
            </div>`).join("")}
        </div>` : stateBlock({ icon: "exam", title: "Nothing marked yet", body: "Mark topics as done in Exam Mode to track revision status here." })}
      </div>
    `;
  } catch (e) {
    body.innerHTML = stateBlock({ icon: "alert", title: "Couldn't load analytics", body: e.message, error: true });
  }
}

function statCard(tone, icon, label, value, trend, sub) {
  const trendHtml = trend ? `<span class="trend-${trend}">${trend === "up" ? "↑" : "↓"}</span> ` : "";
  return `<div class="card stat-card">
    <div class="stat-icon stat-icon-${tone}">${ICONS[icon]}</div>
    <span class="stat-label">${escapeHtml(label)}</span>
    <span class="stat-value">${value}</span>
    <span class="stat-sub">${trendHtml}${escapeHtml(sub)}</span>
  </div>`;
}

function barColor(pct) {
  if (pct < 50) return "var(--red)";
  if (pct < 70) return "var(--amber)";
  return "linear-gradient(90deg, var(--indigo), #8B7BFA)";
}
function statusLabel(pct) {
  if (pct < 50) return "Weak";
  if (pct < 70) return "Needs Practice";
  if (pct < 85) return "Good";
  return "Excellent";
}
function statusPillClass(pct) {
  if (pct < 50) return "pill-red";
  if (pct < 70) return "pill-amber";
  return "pill-green";
}

function lineChartSvg(topics) {
  if (!topics.length) return stateBlock({ icon: "analytics", title: "Not enough data yet", body: "Attempt a few quizzes to see your trend here." });
  const w = 460, h = 200, padL = 34, padB = 24, padT = 14, padR = 10;
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const n = topics.length;
  const pts = topics.map((t, i) => {
    const x = padL + (n === 1 ? innerW / 2 : (innerW * i) / (n - 1));
    const y = padT + innerH - (innerH * t.accuracy) / 100;
    return [x, y];
  });
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const area = `${path} L${pts[pts.length - 1][0].toFixed(1)},${padT + innerH} L${pts[0][0].toFixed(1)},${padT + innerH} Z`;
  const gridLines = [0, 25, 50, 75, 100].map((v) => {
    const y = padT + innerH - (innerH * v) / 100;
    return `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="var(--border)" stroke-width="1"/>
            <text x="${padL - 8}" y="${y + 3}" text-anchor="end" class="linechart-axis">${v}%</text>`;
  }).join("");
  const labels = topics.map((t, i) => `<text x="${pts[i][0].toFixed(1)}" y="${h - 4}" text-anchor="middle" class="linechart-axis">${escapeHtml((t.topic || "").slice(0, 8))}</text>`).join("");
  const dots = pts.map((p) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.5" fill="#5B5FF2" stroke="#fff" stroke-width="1.5"/>`).join("");
  return `<svg viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg">
    <defs><linearGradient id="lcGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#5B5FF2" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#5B5FF2" stop-opacity="0"/>
    </linearGradient></defs>
    ${gridLines}
    <path d="${area}" fill="url(#lcGrad)"/>
    <path d="${path}" fill="none" stroke="#5B5FF2" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    ${dots}
    ${labels}
  </svg>`;
}

function donutChart(topics, overallAccuracy) {
  if (!topics.length) return stateBlock({ icon: "analytics", title: "No data yet", body: "Attempt a quiz to see this breakdown." });
  const grouped = {};
  topics.forEach((t) => {
    const key = t.subject || t.topic;
    if (!grouped[key]) grouped[key] = { correct: 0, total: 0 };
    grouped[key].correct += t.correct_count;
    grouped[key].total += t.total_count;
  });
  const entries = Object.entries(grouped).map(([name, v]) => ({ name, pct: v.total ? Math.round((v.correct / v.total) * 100) : 0 })).slice(0, 6);
  let acc = 0;
  const total = entries.reduce((s, e) => s + e.pct, 0) || 1;
  const stops = entries.map((e, i) => {
    const start = (acc / total) * 360;
    acc += e.pct;
    const end = (acc / total) * 360;
    return `${DONUT_COLORS[i % DONUT_COLORS.length]} ${start}deg ${end}deg`;
  }).join(", ");
  return `<div class="donut-wrap">
    <div class="donut-center" style="border-radius:50%; background:conic-gradient(${stops}); position:relative; display:flex; align-items:center; justify-content:center;">
      <div style="position:absolute; inset:16px; background:var(--surface); border-radius:50%; display:flex; flex-direction:column; align-items:center; justify-content:center;">
        <span class="donut-label"><span class="val">${overallAccuracy}%</span><span class="lbl">Accuracy</span></span>
      </div>
    </div>
    <div class="legend-list">
      ${entries.map((e, i) => `<div class="legend-row"><span class="legend-dot" style="background:${DONUT_COLORS[i % DONUT_COLORS.length]};"></span><span class="legend-name">${escapeHtml(e.name)}</span><span class="legend-val">${e.pct}%</span></div>`).join("")}
    </div>
  </div>`;
}