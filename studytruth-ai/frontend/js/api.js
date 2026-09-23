/* StudyTruth AI - API client
   Talks to the FastAPI backend. Change API_BASE if you run the backend
   on a different host/port. */
const API_BASE = window.STUDYTRUTH_API_BASE || "http://localhost:8000";

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const body = await res.json(); detail = body.detail || JSON.stringify(body); } catch (e) {}
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json();
}

const api = {
  health: () => apiRequest("/api/health"),
  dashboard: () => apiRequest("/api/dashboard"),

  listDocuments: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return apiRequest(`/api/documents${qs ? "?" + qs : ""}`);
  },
  uploadDocument: (formData) =>
    fetch(`${API_BASE}/api/documents/upload`, { method: "POST", body: formData }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Upload failed");
      }
      return res.json();
    }),

  ask: (query, subject, completed_topics) =>
    apiRequest("/api/ask", { method: "POST", body: JSON.stringify({ query, subject, completed_topics }) }),

  compareDocuments: (doc_id_a, doc_id_b) =>
    apiRequest("/api/conflicts/compare", { method: "POST", body: JSON.stringify({ doc_id_a, doc_id_b }) }),
  detectConflicts: (topic, subject) => {
    const qs = new URLSearchParams({ topic, ...(subject ? { subject } : {}) }).toString();
    return apiRequest(`/api/conflicts/detect?${qs}`);
  },

  studyPlan: (subject, completed_topics = []) =>
    apiRequest("/api/exam/study-plan", { method: "POST", body: JSON.stringify({ subject, completed_topics }) }),
  pyqs: (topic, subject) => {
    const qs = new URLSearchParams({ topic, ...(subject ? { subject } : {}) }).toString();
    return apiRequest(`/api/exam/pyqs?${qs}`);
  },

  generateQuiz: (topic, subject, num_questions = 5) =>
    apiRequest("/api/quiz/generate", { method: "POST", body: JSON.stringify({ topic, subject, num_questions }) }),
  logQuizAnswer: (payload) => apiRequest("/api/quiz/log", { method: "POST", body: JSON.stringify(payload) }),
  quizStats: () => apiRequest("/api/quiz/stats"),

  analytics: (subject) => apiRequest(`/api/analytics${subject ? "?subject=" + encodeURIComponent(subject) : ""}`),
  setTopicStatus: (subject, topic, status) =>
    apiRequest("/api/topic-status", { method: "POST", body: JSON.stringify({ subject, topic, status }) }),
};
