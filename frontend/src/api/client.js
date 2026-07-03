const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function safeFetch(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status}: ${text}`);
  }
  return resp.json();
}

export const api = {
  // ── Court ──────────────────────────────────────────────────────────────
  convene: (objective) =>
    safeFetch(`${API_BASE}/court/convene`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ business_objective: objective }),
    }),

  courtStatus: (sessionId) =>
    safeFetch(`${API_BASE}/court/${sessionId}/status`),

  courtRecord: (sessionId) =>
    safeFetch(`${API_BASE}/court/${sessionId}/record`),

  resolveConflict: (sessionId, nodeId, action, instruction = null) =>
    safeFetch(`${API_BASE}/court/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        node_id: nodeId,
        resolution_action: action,
        modification_instruction: instruction,
      }),
    }),

  compile: (sessionId) =>
    safeFetch(`${API_BASE}/court/compile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    }),

  // ── Cases ──────────────────────────────────────────────────────────────
  listCases: () => safeFetch(`${API_BASE}/cases`),

  getCase: (caseId) => safeFetch(`${API_BASE}/cases/${caseId}`),

  getAudit: (caseId) => safeFetch(`${API_BASE}/cases/${caseId}/audit`),

  execute: (caseId) =>
    safeFetch(`${API_BASE}/cases/${caseId}/execute`, { method: "POST" }),

  approvePatch: (caseId) =>
    safeFetch(`${API_BASE}/cases/${caseId}/trc/approve`, { method: "POST" }),

  abandonCase: (caseId) =>
    safeFetch(`${API_BASE}/cases/${caseId}/trc/abandon`, { method: "POST" }),

  rollback: (caseId, targetNodeId) =>
    safeFetch(`${API_BASE}/cases/${caseId}/rollback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_node_id: targetNodeId }),
    }),

  overrideADG: (caseId, nodeId, selectedBranch, reasoning) =>
    safeFetch(`${API_BASE}/cases/${caseId}/adg/override`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node_id: nodeId,
        selected_branch: selectedBranch,
        reasoning: reasoning,
      }),
    }),

  // ── SSE stream with auto-reconnect ─────────────────────────────────────
  streamEvents: (caseId, onEvent) => {
    let es = null;
    let closed = false;
    let reconnectTimer = null;

    function connect() {
      if (closed) return;
      es = new EventSource(`${API_BASE}/cases/${caseId}/stream`);
      
      es.onmessage = (e) => {
        try {
          const raw = JSON.parse(e.data);
          // Backend sends {event, data} — normalize to {type, payload}
          const normalized = {
            type: raw.event || raw.type,
            payload: raw.data || raw.payload || raw,
          };
          onEvent(normalized);
        } catch (err) {
          console.warn("[SSE] Parse error:", err);
        }
      };
      
      es.onerror = () => {
        // Don't permanently close — reconnect after 3s
        if (es) es.close();
        if (!closed) {
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
    }

    connect();

    // Return cleanup function
    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (es) es.close();
    };
  },
};
