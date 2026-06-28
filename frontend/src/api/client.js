const API_BASE = "http://localhost:8000";

export const api = {
  // ── Court ──────────────────────────────────────────────────────────────
  convene: (objective) =>
    fetch(`${API_BASE}/court/convene`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_objective: objective }),
    }).then((r) => r.json()),

  courtStatus: (sessionId) =>
    fetch(`${API_BASE}/court/${sessionId}/status`).then((r) => r.json()),

  courtRecord: (sessionId) =>
    fetch(`${API_BASE}/court/${sessionId}/record`).then((r) => r.json()),

  resolveConflict: (sessionId, nodeId, action, instruction = null) =>
    fetch(`${API_BASE}/court/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        node_id: nodeId,
        resolution_action: action,
        modification_instruction: instruction,
      }),
    }).then((r) => r.json()),

  compile: (sessionId) =>
    fetch(`${API_BASE}/court/compile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }).then((r) => r.json()),

  // ── Cases ──────────────────────────────────────────────────────────────
  listCases: () => fetch(`${API_BASE}/cases`).then((r) => r.json()),

  getCase: (caseId) => fetch(`${API_BASE}/cases/${caseId}`).then((r) => r.json()),

  getAudit: (caseId) =>
    fetch(`${API_BASE}/cases/${caseId}/audit`).then((r) => r.json()),

  execute: (caseId) =>
    fetch(`${API_BASE}/cases/${caseId}/execute`, { method: "POST" }).then((r) =>
      r.json()
    ),

  approvePatch: (caseId) =>
    fetch(`${API_BASE}/cases/${caseId}/trc/approve`, { method: "POST" }).then(
      (r) => r.json()
    ),

  abandonCase: (caseId) =>
    fetch(`${API_BASE}/cases/${caseId}/trc/abandon`, { method: "POST" }).then(
      (r) => r.json()
    ),

  rollback: (caseId, targetNodeId) =>
    fetch(`${API_BASE}/cases/${caseId}/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_node_id: targetNodeId }),
    }).then((r) => r.json()),

  overrideADG: (caseId, nodeId, selectedBranch, reasoning) =>
    fetch(`${API_BASE}/cases/${caseId}/adg/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_id: nodeId,
        selected_branch: selectedBranch,
        reasoning: reasoning,
      }),
    }).then((r) => r.json()),

  // ── SSE stream ──────────────────────────────────────────────────────────
  streamEvents: (caseId, onEvent) => {
    const es = new EventSource(`${API_BASE}/cases/${caseId}/stream`);
    es.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        onEvent(parsed);
      } catch {}
    };
    es.onerror = () => es.close();
    return () => es.close();
  },
};
