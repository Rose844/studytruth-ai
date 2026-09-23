async function initConflictsPage() {
  const root = document.getElementById("page-conflicts");
  root.innerHTML = `
    <div class="topbar">
      <div><h1>Conflict Checker</h1><p class="subtitle">Compare any two documents and see exactly what changed — and why one source wins.</p></div>
    </div>

    <div class="card">
      <div class="section-title">Compare two documents</div>
      <div class="conflict-selectors">
        <div class="field" style="margin:0;"><label>Document A</label><select id="doc-a"></select></div>
        <div class="vs-badge">VS</div>
        <div class="field" style="margin:0;"><label>Document B</label><select id="doc-b"></select></div>
      </div>
      <button class="btn btn-primary" id="compare-btn">${ICONS.conflict} Compare documents</button>
      <div id="compare-result" class="mt-24"></div>
    </div>

    <div class="card mt-24">
      <div class="section-title">Check a specific topic for contradictions</div>
      <div class="flex gap-12" style="align-items:flex-end;">
        <div class="field" style="flex:1;margin:0;"><label>Topic</label><input id="conflict-topic" placeholder="e.g. VLAN" /></div>
        <div class="field" style="width:220px;margin:0;"><label>Subject</label><select id="conflict-subject" data-subject-select></select></div>
        <button class="btn btn-secondary" id="topic-conflict-btn">Check</button>
      </div>
      <div id="topic-conflict-result" class="mt-16"></div>
    </div>
  `;

  const docSelectOptions = STATE.documents.length
    ? STATE.documents.map((d) => `<option value="${d.doc_id}">${escapeHtml(d.filename)} (${escapeHtml(d.subject)}, ${escapeHtml(d.version)})</option>`).join("")
    : `<option value="">No documents uploaded</option>`;
  document.getElementById("doc-a").innerHTML = docSelectOptions;
  document.getElementById("doc-b").innerHTML = docSelectOptions;
  // sensible default: pick two syllabus docs of the same subject if available
  const syllabi = STATE.documents.filter((d) => d.doc_type === "syllabus");
  if (syllabi.length >= 2) {
    document.getElementById("doc-a").value = syllabi[0].doc_id;
    document.getElementById("doc-b").value = syllabi[1].doc_id;
  }

  populateSubjectSelects();

  document.getElementById("compare-btn").addEventListener("click", runCompare);
  document.getElementById("topic-conflict-btn").addEventListener("click", runTopicConflictCheck);

  document.getElementById("compare-result").innerHTML = stateBlock({
    icon: "conflict", title: "Pick two documents to compare",
    body: "Try comparing the two Computer Networks syllabus versions to see the VLAN conflict demo.",
  });
}

async function runCompare() {
  const a = document.getElementById("doc-a").value;
  const b = document.getElementById("doc-b").value;
  const resultEl = document.getElementById("compare-result");
  if (!a || !b || a === b) { toast("Pick two different documents", "error"); return; }

  resultEl.innerHTML = `<div class="flex items-center gap-8 text-muted text-sm"><div class="spinner dark"></div> Comparing documents...</div>`;
  try {
    const cmp = await api.compareDocuments(a, b);
    resultEl.innerHTML = `
      <div class="text-sm" style="margin-bottom:16px;color:var(--text-secondary);line-height:1.6;">${escapeHtml(cmp.explanation)}</div>
      <div class="diff-columns">
        <div class="diff-col">
          <h4>${escapeHtml(cmp.doc_a.filename)}</h4>
          <div class="diff-meta">${escapeHtml(cmp.doc_a.version)} · ${fmtDate(cmp.doc_a.upload_date)} · <span class="pill authority-rank-${cmp.doc_a.authority_rank}" style="padding:1px 6px;">${authorityLabel(cmp.doc_a.authority_rank)}</span></div>
          <ul class="diff-list">${(cmp.doc_a.topic_tags || []).map((t) => `<li class="diff-unchanged">${escapeHtml(t)}</li>`).join("") || '<li class="diff-unchanged">No tagged topics</li>'}</ul>
        </div>
        <div class="diff-col">
          <h4>${escapeHtml(cmp.doc_b.filename)}</h4>
          <div class="diff-meta">${escapeHtml(cmp.doc_b.version)} · ${fmtDate(cmp.doc_b.upload_date)} · <span class="pill authority-rank-${cmp.doc_b.authority_rank}" style="padding:1px 6px;">${authorityLabel(cmp.doc_b.authority_rank)}</span></div>
          <ul class="diff-list">${(cmp.doc_b.topic_tags || []).map((t) => `<li class="diff-unchanged">${escapeHtml(t)}</li>`).join("") || '<li class="diff-unchanged">No tagged topics</li>'}</ul>
        </div>
      </div>
      <div class="grid grid-3 mt-16">
        <div>
          <div class="text-sm" style="font-weight:700;margin-bottom:8px;">Added</div>
          <ul class="diff-list">${cmp.added_topics.map((t) => `<li class="diff-added">+ ${escapeHtml(t)}</li>`).join("") || '<li class="diff-unchanged">None</li>'}</ul>
        </div>
        <div>
          <div class="text-sm" style="font-weight:700;margin-bottom:8px;">Removed</div>
          <ul class="diff-list">${cmp.removed_topics.map((t) => `<li class="diff-removed">${escapeHtml(t)}</li>`).join("") || '<li class="diff-unchanged">None</li>'}</ul>
        </div>
        <div>
          <div class="text-sm" style="font-weight:700;margin-bottom:8px;">Modified</div>
          <ul class="diff-list">${cmp.modified_topics.map((t) => `<li class="diff-modified">~ ${escapeHtml(t)}</li>`).join("") || '<li class="diff-unchanged">None</li>'}</ul>
        </div>
      </div>
    `;
  } catch (e) {
    resultEl.innerHTML = stateBlock({ icon: "alert", title: "Comparison failed", body: e.message, error: true });
  }
}

async function runTopicConflictCheck() {
  const topic = document.getElementById("conflict-topic").value.trim();
  const subject = document.getElementById("conflict-subject").value || undefined;
  const resultEl = document.getElementById("topic-conflict-result");
  if (!topic) { toast("Enter a topic first", "error"); return; }

  resultEl.innerHTML = `<div class="flex items-center gap-8 text-muted text-sm"><div class="spinner dark"></div> Checking...</div>`;
  try {
    const res = await api.detectConflicts(topic, subject);
    if (!res.has_conflicts) {
      resultEl.innerHTML = stateBlock({ icon: "conflict", title: "No conflicts found", body: `Your documents agree on "${topic}" — no contradictions detected.` });
      return;
    }
    resultEl.innerHTML = res.conflicts.map((c) => `
      <div class="conflict-block" style="margin:0 0 12px;">
        <div class="conflict-title">${ICONS.conflict} ${escapeHtml(c.topic)}</div>
        <div class="text-sm" style="margin-bottom:6px;"><strong>${escapeHtml(c.doc_a.filename)}</strong>: ${escapeHtml(c.statement_a)}</div>
        <div class="text-sm" style="margin-bottom:10px;"><strong>${escapeHtml(c.doc_b.filename)}</strong>: ${escapeHtml(c.statement_b)}</div>
        <div class="text-sm" style="color:var(--text-secondary);">${escapeHtml(c.resolution)}</div>
      </div>`).join("");
  } catch (e) {
    resultEl.innerHTML = stateBlock({ icon: "alert", title: "Check failed", body: e.message, error: true });
  }
}
