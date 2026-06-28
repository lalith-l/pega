import { Fragment, jsx, jsxs } from "react/jsx-runtime";
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position
} from "reactflow";
import "reactflow/dist/style.css";
import { api } from "../api/client";
const NODE_TYPE_ICONS = {
  API_CALL: "\u{1F517}",
  DATA_TRANSFORM: "\u2699",
  DECISION_GATE: "\u2B26",
  NOTIFICATION: "\u{1F514}",
  HUMAN_REVIEW: "\u{1F441}",
  VALIDATION: "\u2714",
  ADG_GATE: "\u{1F3AF}",
  DEFAULT: "\u25C6",
  FIREWALL_GATE: "\u{1F6E1}"
};
function MorpheusNode({ data }) {
  const isExecuting = data.current_node_id === data.node_id;
  const isCompleted = data.completed?.includes(data.node_id);
  const isFirewallBlocked = data.checkpoint?.failure_node_id === data.node_id;
  const isCausal = data.trcHighlight?.includes(data.node_id);
  const disputeCount = Object.values(data.agent_verdicts || {}).filter((v) => v?.verdict === "DISPUTE").length;
  const courtStatus = data.final_status || "";
  let statusClass = "";
  if (isFirewallBlocked) {
    statusClass = "firewall-blocked bg-red-900 border-red-500 animate-pulse";
  } else if (isExecuting) statusClass = "executing";
  else if (isCompleted) statusClass = "completed";
  else if (courtStatus) statusClass = courtStatus.toLowerCase();
  if (isCausal && !isFirewallBlocked) statusClass += " causal";
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: `morpheus-node ${statusClass}`,
      onClick: () => data.onSelect && data.onSelect(data),
      style: { minWidth: 170, cursor: data.onSelect ? "pointer" : "default" },
      children: [
        /* @__PURE__ */ jsx(Handle, { type: "target", position: Position.Top, style: { background: "#475569", border: "none" } }),
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }, children: [
          /* @__PURE__ */ jsx("span", { style: { fontSize: 14 }, children: NODE_TYPE_ICONS[data.node_type] || "\u25C6" }),
          /* @__PURE__ */ jsx("div", { className: "node-label", children: data.label })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "node-type-badge", children: data.node_type }),
        disputeCount > 0 && !isExecuting && !isCompleted && !isFirewallBlocked && /* @__PURE__ */ jsxs("div", { style: {
          marginTop: 8,
          padding: "3px 8px",
          borderRadius: 4,
          background: "rgba(239,68,68,0.15)",
          color: "#fca5a5",
          fontSize: 10,
          fontWeight: 700
        }, children: [
          "\u26A0 ",
          disputeCount,
          " dispute",
          disputeCount > 1 ? "s" : ""
        ] }),
        isExecuting && /* @__PURE__ */ jsxs("div", { style: { marginTop: 8, display: "flex", alignItems: "center", gap: 6, fontSize: 10, color: "var(--purple-400)" }, children: [
          /* @__PURE__ */ jsx("span", { className: "pulse-dot purple" }),
          " Executing"
        ] }),
        isCompleted && !isFirewallBlocked && /* @__PURE__ */ jsx("div", { style: { marginTop: 8, fontSize: 10, color: "var(--green-500)", fontWeight: 600 }, children: "\u2705 Completed" }),
        isFirewallBlocked && /* @__PURE__ */ jsx("div", { style: { marginTop: 8, fontSize: 11, color: "var(--red-500)", fontWeight: 800 }, children: "\u{1F525} BLOCKED" }),
        /* @__PURE__ */ jsx(Handle, { type: "source", position: Position.Bottom, style: { background: "#475569", border: "none" } })
      ]
    }
  );
}
const nodeTypes = { morpheusNode: MorpheusNode };
function ConflictPanel({ node, sessionId, onResolved, onClose }) {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const disputes = Object.entries(node.agent_verdicts || {}).filter(([, v]) => v?.verdict === "DISPUTE");
  const submit = async (act) => {
    setLoading(true);
    try {
      await api.resolveConflict(sessionId, node.node_id, act, instruction || null);
      onResolved(node.node_id, act);
      onClose();
    } catch (e) {
      alert("Failed to resolve: " + e.message);
    } finally {
      setLoading(false);
    }
  };
  return /* @__PURE__ */ jsxs("div", { className: "side-panel fade-in", style: { position: "absolute", right: 24, top: 24, zIndex: 10, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: 24, width: 350, boxShadow: "0 10px 30px rgba(0,0,0,0.3)" }, children: [
    /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }, children: [
      /* @__PURE__ */ jsx("div", { style: { fontWeight: 700, fontSize: 16 }, children: "\u26A0 Conflict Resolution" }),
      /* @__PURE__ */ jsx("button", { onClick: onClose, className: "btn btn-secondary btn-sm", children: "\u2715" })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "card-elevated", style: { padding: 16, marginBottom: 16 }, children: [
      /* @__PURE__ */ jsx("div", { style: { fontWeight: 700, marginBottom: 4 }, children: node.label }),
      /* @__PURE__ */ jsx("div", { style: { fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }, children: node.node_type }),
      /* @__PURE__ */ jsx("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: node.description })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "section-title", children: "Agent Disputes" }),
    disputes.map(([agent, v]) => /* @__PURE__ */ jsxs("div", { style: {
      marginBottom: 12,
      padding: 14,
      borderRadius: "var(--radius)",
      background: "rgba(239,68,68,0.06)",
      border: "1px solid rgba(239,68,68,0.2)"
    }, children: [
      /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }, children: [
        /* @__PURE__ */ jsx("span", { className: `agent-chip agent-${agent.toLowerCase()}`, children: agent }),
        /* @__PURE__ */ jsx("span", { style: {
          fontSize: 10,
          padding: "2px 8px",
          borderRadius: 99,
          background: "rgba(239,68,68,0.15)",
          color: "#fca5a5",
          fontWeight: 700
        }, children: v.severity })
      ] }),
      /* @__PURE__ */ jsx("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: v.reasoning })
    ] }, agent)),
    /* @__PURE__ */ jsx("div", { className: "section-title", style: { marginTop: 20 }, children: "Your Decision" }),
    /* @__PURE__ */ jsx(
      "textarea",
      {
        className: "input textarea",
        placeholder: "Instruction...",
        value: instruction,
        onChange: (e) => setInstruction(e.target.value),
        style: { marginBottom: 12 }
      }
    ),
    /* @__PURE__ */ jsxs("div", { style: { display: "flex", flexDirection: "column", gap: 8 }, children: [
      /* @__PURE__ */ jsx("button", { className: "btn btn-success", onClick: () => submit("ACCEPT"), disabled: loading, children: "\u2705 Accept As-Is" }),
      /* @__PURE__ */ jsx("button", { className: "btn btn-secondary", onClick: () => submit("MODIFY"), disabled: loading || !instruction, children: "\u270F Modify" }),
      /* @__PURE__ */ jsx("button", { className: "btn btn-danger", onClick: () => submit("REMOVE"), disabled: loading, children: "\u{1F5D1} Remove Node" })
    ] })
  ] });
}
function CaseDashboard() {
  const { caseId: paramCaseId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [objective, setObjective] = useState(location.state?.objective || "");
  const [caseId, setCaseId] = useState(paramCaseId || null);
  const [sessionId, setSessionId] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [courtStatus, setCourtStatus] = useState(null);
  const [courtRecord, setCourtRecord] = useState(null);
  const [auditTrail, setAuditTrail] = useState([]);
  const [showAudit, setShowAudit] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [compiling, setCompiling] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [activeNodeId, setActiveNodeId] = useState(null);
  const [completedNodes, setCompletedNodes] = useState([]);
  const [firewallViolation, setFirewallViolation] = useState(null);
  const [trcPhases, setTrcPhases] = useState([]);
  const [trcResult, setTrcResult] = useState(null);
  const [adgDecision, setAdgDecision] = useState(null);
  const [adgTimeLeft, setAdgTimeLeft] = useState(0);
  const [adgOverrideReason, setAdgOverrideReason] = useState("");
  const [adgOverrideBranch, setAdgOverrideBranch] = useState("");
  const pollRef = useRef(null);
  const buildGraph = useCallback((nodesList, isCourt, onSelect, checkpoint) => {
    if (!nodesList) return;
    const rfNodes = nodesList.map((n, i) => ({
      id: n.node_id,
      type: "morpheusNode",
      position: { x: 80 + i % 3 * 250, y: 80 + Math.floor(i / 3) * 160 },
      data: {
        ...n,
        onSelect: isCourt ? onSelect : null,
        current_node_id: checkpoint?.current_node_id,
        completed: checkpoint?.completed_nodes || [],
        checkpoint
      }
    }));
    const rfEdges = [];
    nodesList.forEach((n) => {
      (n.dependencies || []).forEach((depId) => {
        rfEdges.push({
          id: `${depId}-${n.node_id}`,
          source: depId,
          target: n.node_id,
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed, color: "#475569" },
          style: { stroke: "#334155" }
        });
      });
    });
    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [setNodes, setEdges]);
  useEffect(() => {
    if (!caseId) return;
    api.getCase(caseId).then((data) => {
      setCaseData(data);
      if (data.court_session_id && data.status === "DRAFT") {
        setSessionId(data.court_session_id);
      }
      if (data.status !== "DRAFT") {
        if (data.checkpoint) {
          setCompletedNodes(data.checkpoint.completed_nodes || []);
          if (data.checkpoint.current_node_id && data.status === "EXECUTING") {
            setActiveNodeId(data.checkpoint.current_node_id);
          }
          if (data.checkpoint.violation_report) setFirewallViolation(data.checkpoint.violation_report);
          if (data.checkpoint.trc_result) setTrcResult(data.checkpoint.trc_result);
        }
        buildGraph(data.compiled_workflow?.nodes, false, null, data.checkpoint);
      }
    });
    api.getAudit(caseId).then((res) => setAuditTrail(res.audit_trail));
  }, [caseId, buildGraph]);
  useEffect(() => {
    if (!sessionId || caseData && caseData.status !== "DRAFT") return;
    const poll = async () => {
      try {
        const status = await api.courtStatus(sessionId);
        setCourtStatus(status);
        if (status.session_status === "AWAITING_HUMAN" || status.session_status === "COMPLETED" || status.session_status === "COMPILED") {
          const record = await api.courtRecord(sessionId);
          console.log("courtRecord fetched:", record);
          console.log("proposed_nodes inside:", record.court_record?.proposed_nodes);
          setCourtRecord(record.court_record);
          buildGraph(record.court_record?.proposed_nodes, true, setSelectedNode, null);
          clearInterval(pollRef.current);
        }
      } catch (e) {
        console.error("Court polling error:", e);
      }
    };
    poll();
    pollRef.current = setInterval(poll, 2e3);
    return () => clearInterval(pollRef.current);
  }, [sessionId, caseData, buildGraph]);
  const updateGraphState = useCallback((currentId, completedId, blockedId, trcHighlightIds) => {
    setNodes((prev) => prev.map((n) => {
      const data = { ...n.data };
      if (currentId !== null) data.current_node_id = currentId;
      if (completedId) data.completed = [.../* @__PURE__ */ new Set([...data.completed || [], completedId])];
      if (blockedId) data.checkpoint = { ...data.checkpoint, failure_node_id: blockedId };
      if (trcHighlightIds) data.trcHighlight = trcHighlightIds;
      if (completedId && currentId === null && data.current_node_id === completedId) {
        data.current_node_id = null;
      }
      return { ...n, data };
    }));
  }, [setNodes]);
  useEffect(() => {
    if (!caseId || caseData && caseData.status === "DRAFT") return;
    const unsub = api.streamEvents(caseId, (event) => {
      switch (event.type) {
        case "NODE_STARTED":
          setActiveNodeId(event.payload.node_id);
          updateGraphState(event.payload.node_id, null, null, null);
          break;
        case "NODE_COMPLETED":
          setActiveNodeId(null);
          updateGraphState(null, event.payload.node_id, null, null);
          break;
        case "FIREWALL_KILLED":
          setActiveNodeId(null);
          setFirewallViolation({ node_id: event.payload.node_id, ...event.payload });
          updateGraphState(null, null, event.payload.node_id, null);
          setCaseData((prev) => ({ ...prev, status: "PAUSED" }));
          break;
        case "TRC_PHASE":
          setTrcPhases((prev) => {
            const copy = [...prev];
            const existingIdx = copy.findIndex((p) => p.phase === event.payload.phase);
            if (existingIdx >= 0) copy[existingIdx] = event.payload;
            else copy.push(event.payload);
            return copy.sort((a, b) => a.phase - b.phase);
          });
          if (event.payload.highlight_nodes) {
            updateGraphState(null, null, null, event.payload.highlight_nodes);
          }
          break;
        case "ADG_DECISION":
          setAdgDecision(event.payload);
          setAdgTimeLeft(60);
          setCaseData((prev) => ({ ...prev, status: "AWAITING_ADG_OVERRIDE" }));
          break;
        case "ADG_OVERRIDDEN":
          setAdgDecision(null);
          setAdgTimeLeft(0);
          break;
        case "TRC_COMPLETE":
          setTrcResult(event.payload.trc_result);
          setCaseData((prev) => ({ ...prev, status: "AWAITING_HUMAN" }));
          break;
        case "CASE_COMPLETE":
        case "CASE_CLOSED":
        case "CASE_SUSPENDED":
          setCaseData((prev) => ({ ...prev, status: event.payload.status || event.type }));
          setActiveNodeId(null);
          break;
        case "PATCH_APPROVED":
          setTrcResult(null);
          setFirewallViolation(null);
          setTrcPhases([]);
          api.getCase(caseId).then((data) => {
            setCaseData(data);
            buildGraph(data.compiled_workflow?.nodes, false, null, data.checkpoint);
          });
          break;
      }
    });
    return () => unsub();
  }, [caseId, caseData?.status, updateGraphState, buildGraph]);
  useEffect(() => {
    if (adgTimeLeft > 0) {
      const timer = setTimeout(() => setAdgTimeLeft((t) => t - 1), 1e3);
      return () => clearTimeout(timer);
    } else if (adgTimeLeft === 0 && adgDecision) {
      setAdgDecision(null);
    }
  }, [adgTimeLeft, adgDecision]);
  const handleConvene = async () => {
    if (!objective.trim()) return;
    const res = await api.convene(objective.trim());
    setSessionId(res.session_id);
    setCaseId(res.case_id);
    window.history.replaceState({}, "", `/cases/${res.case_id}`);
  };
  const handleResolved = (nodeId, action) => {
    setNodes((prev) => prev.map(
      (n) => n.id === nodeId ? { ...n, data: { ...n.data, final_status: action === "REMOVE" ? "REMOVED" : "RESOLVED" } } : n
    ));
    if (sessionId) api.courtRecord(sessionId).then((r) => setCourtRecord(r.court_record));
  };
  const handleCompile = async () => {
    setCompiling(true);
    try {
      await api.compile(sessionId);
      const data = await api.getCase(caseId);
      setCaseData(data);
      setCourtRecord(null);
      buildGraph(data.compiled_workflow?.nodes, false, null, data.checkpoint);
    } catch (e) {
      alert("Compile failed: " + e.message);
    } finally {
      setCompiling(false);
    }
  };
  const handleExecute = async () => {
    try {
      await api.execute(caseId);
      setCaseData((prev) => ({ ...prev, status: "EXECUTING" }));
    } catch (e) {
      alert(e.message);
    }
  };
  const handleApprovePatch = async () => {
    try {
      await api.approvePatch(caseId);
    } catch (e) {
      alert("Failed to approve patch: " + e.message);
    }
  };
  const allResolved = courtRecord?.proposed_nodes?.every(
    (n) => ["CONSENSUS", "RESOLVED", "WARNED"].includes(n.final_status)
  );
  const handleADGOverride = async () => {
    if (!adgOverrideBranch) return;
    try {
      await api.overrideADG(caseId, adgDecision.node_id, adgOverrideBranch, adgOverrideReason);
    } catch (e) {
      alert("Override failed: " + e.message);
    }
  };
  return /* @__PURE__ */ jsxs("div", { className: "page fade-in", style: { position: "relative" }, children: [
    /* @__PURE__ */ jsxs("div", { className: "page-header", style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start" }, children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }, children: [
          /* @__PURE__ */ jsx("h1", { className: "page-title", style: { margin: 0 }, children: "Case Journey" }),
          caseData && /* @__PURE__ */ jsx("span", { className: `badge badge-${["COMPILED", "RESOLVED"].includes(caseData.status) ? "resolved" : caseData.status === "EXECUTING" ? "executing" : caseData.status === "PAUSED" ? "paused" : caseData.status.includes("CLOSED") ? "closed-success" : "pending"}`, children: caseData.status })
        ] }),
        /* @__PURE__ */ jsx("p", { className: "page-subtitle", style: { maxWidth: 600 }, children: caseData?.business_objective || "Start a new workflow automation." })
      ] }),
      /* @__PURE__ */ jsxs("div", { style: { display: "flex", gap: 12 }, children: [
        caseData && /* @__PURE__ */ jsx("button", { className: "btn btn-secondary", onClick: () => setShowAudit(true), children: "\u{1F4CB} Audit Trail" }),
        caseData?.status === "COMPILED" || caseData?.status === "RESUMING" ? /* @__PURE__ */ jsx("button", { className: "btn btn-primary btn-lg pulse-bg", onClick: handleExecute, children: "\u26A1 Execute Case" }) : null
      ] })
    ] }),
    !caseId && /* @__PURE__ */ jsxs("div", { className: "card", style: { padding: 24, maxWidth: 700, margin: "40px auto" }, children: [
      /* @__PURE__ */ jsx("div", { className: "section-title", children: "Business Objective" }),
      /* @__PURE__ */ jsx(
        "textarea",
        {
          className: "input textarea",
          placeholder: "e.g. Automate vendor invoice processing: verify GST, validate vendor...",
          value: objective,
          onChange: (e) => setObjective(e.target.value),
          style: { marginBottom: 12, minHeight: 100 }
        }
      ),
      /* @__PURE__ */ jsx("button", { className: "btn btn-primary", onClick: handleConvene, disabled: !objective.trim(), children: "\u2B21 Convene Court" })
    ] }),
    sessionId && caseData?.status === "DRAFT" && /* @__PURE__ */ jsxs("div", { className: "fade-in", children: [
      /* @__PURE__ */ jsx("div", { className: "grid-4", style: { marginBottom: 20 }, children: ["ARCHITECT", "SECURITY", "EFFICIENCY", "COMPLIANCE"].map((agent) => {
        const doneKey = `${agent.toLowerCase()}_done`;
        const done = courtStatus?.[doneKey];
        const running = !done && courtStatus?.session_status === "DEBATING" && ["ARCHITECT", "SECURITY", "EFFICIENCY", "COMPLIANCE"].slice(0, ["ARCHITECT", "SECURITY", "EFFICIENCY", "COMPLIANCE"].indexOf(agent)).every((a) => courtStatus?.[`${a.toLowerCase()}_done`]);
        return /* @__PURE__ */ jsxs("div", { className: "card-elevated", style: { padding: "16px", display: "flex", alignItems: "center", gap: 12, borderColor: done ? "rgba(16,185,129,0.3)" : running ? "rgba(139,92,246,0.4)" : void 0 }, children: [
          done ? /* @__PURE__ */ jsx("span", { children: "\u2705" }) : running ? /* @__PURE__ */ jsx("div", { className: "spinner" }) : /* @__PURE__ */ jsx("div", { style: { width: 16, height: 16, borderRadius: "50%", background: "var(--border)" } }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("span", { className: `agent-chip agent-${agent.toLowerCase()}`, children: agent }),
            /* @__PURE__ */ jsx("div", { style: { fontSize: 11, color: "var(--text-muted)", marginTop: 4 }, children: done ? "Verdicts recorded" : running ? "Deliberating\u2026" : "Awaiting\u2026" })
          ] })
        ] }, agent);
      }) }),
      courtRecord && /* @__PURE__ */ jsxs("div", { className: "fade-in", style: { position: "relative" }, children: [
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }, children: [
          /* @__PURE__ */ jsx("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: allResolved ? "\u2705 All conflicts resolved \u2014 ready to compile" : "\u26A0 Resolve highlighted conflicts to proceed" }),
          /* @__PURE__ */ jsx("button", { className: "btn btn-primary", onClick: handleCompile, disabled: !allResolved || compiling, children: compiling ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx("div", { className: "spinner" }),
            " Compiling\u2026"
          ] }) : "\u26A1 Compile & Start Case" })
        ] }),
        /* @__PURE__ */ jsxs("div", { style: { height: 500, borderRadius: "var(--radius-lg)", overflow: "hidden", border: "1px solid var(--border)", position: "relative" }, children: [
          /* @__PURE__ */ jsxs(ReactFlow, { nodes, edges, onNodesChange, onEdgesChange, nodeTypes, fitView: true, proOptions: { hideAttribution: true }, children: [
            /* @__PURE__ */ jsx(Background, { color: "#1e293b", gap: 24, size: 1 }),
            /* @__PURE__ */ jsx(Controls, {})
          ] }),
          selectedNode && /* @__PURE__ */ jsx(ConflictPanel, { node: selectedNode, sessionId, onResolved: handleResolved, onClose: () => setSelectedNode(null) })
        ] })
      ] })
    ] }),
    caseData && caseData.status !== "DRAFT" && /* @__PURE__ */ jsxs("div", { className: "fade-in", style: { display: "flex", flexDirection: "column", gap: 24 }, children: [
      /* @__PURE__ */ jsxs("div", { className: "card-elevated", style: { height: 500, overflow: "hidden" }, children: [
        /* @__PURE__ */ jsx("div", { style: { padding: "12px 16px", borderBottom: "1px solid var(--border)", fontWeight: 600, fontSize: 14 }, children: "Execution Graph" }),
        /* @__PURE__ */ jsx("div", { style: { height: "calc(100% - 45px)" }, children: /* @__PURE__ */ jsxs(ReactFlow, { nodes, edges, nodeTypes, fitView: true, proOptions: { hideAttribution: true }, children: [
          /* @__PURE__ */ jsx(Background, { color: "#1e293b", gap: 24, size: 1 }),
          /* @__PURE__ */ jsx(Controls, {})
        ] }) })
      ] }),
      firewallViolation && /* @__PURE__ */ jsxs("div", { className: "firewall-alert slide-in", style: { borderColor: "#ef4444", borderWidth: 2 }, children: [
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }, children: [
          /* @__PURE__ */ jsx("span", { style: { fontSize: 24 }, children: "\u{1F525}" }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { style: { fontWeight: 900, color: "var(--red-500)", fontSize: 16 }, children: "HALLUCINATION FIREWALL KILLED EXECUTION" }),
            /* @__PURE__ */ jsxs("div", { style: { fontSize: 13, color: "var(--red-500)", opacity: 0.8 }, children: [
              "Node: ",
              firewallViolation.node_id
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "code-block", style: { borderColor: "rgba(239,68,68,0.3)", color: "#fca5a5", whiteSpace: "pre-wrap", wordBreak: "break-all", fontFamily: "monospace", background: "rgba(0,0,0,0.4)", padding: 14, borderRadius: 6 }, children: [
          "Violation: ",
          firewallViolation.violation_type,
          " (Layer ",
          firewallViolation.layer,
          ")",
          /* @__PURE__ */ jsx("br", {}),
          /* @__PURE__ */ jsx("br", {}),
          JSON.stringify(firewallViolation.details, null, 2)
        ] })
      ] }),
      adgDecision && /* @__PURE__ */ jsxs("div", { className: "card-elevated fade-in", style: { padding: 24, borderColor: "#3b82f6", borderWidth: 2, background: "rgba(59,130,246,0.05)" }, children: [
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start" }, children: [
          /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }, children: [
            /* @__PURE__ */ jsx("span", { style: { fontSize: 24 }, children: "\u{1F3AF}" }),
            /* @__PURE__ */ jsxs("div", { children: [
              /* @__PURE__ */ jsx("div", { style: { fontWeight: 900, color: "#3b82f6", fontSize: 16 }, children: "ADAPTIVE DECISIONING GATE" }),
              /* @__PURE__ */ jsxs("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: [
                "Node: ",
                adgDecision.node_id,
                " (",
                adgDecision.label,
                ")"
              ] })
            ] })
          ] }),
          /* @__PURE__ */ jsxs("div", { style: { fontSize: 24, fontWeight: 800, color: adgTimeLeft < 10 ? "#ef4444" : "#3b82f6" }, children: [
            adgTimeLeft,
            "s"
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "card", style: { padding: 16, marginBottom: 16, background: "var(--bg-base)" }, children: [
          /* @__PURE__ */ jsx("div", { style: { fontWeight: 600, fontSize: 14, marginBottom: 8 }, children: "LLM Proposed Decision" }),
          /* @__PURE__ */ jsxs("div", { style: { fontSize: 13, marginBottom: 4 }, children: [
            /* @__PURE__ */ jsx("span", { style: { color: "var(--text-muted)" }, children: "Branch:" }),
            " ",
            /* @__PURE__ */ jsx("span", { style: { fontWeight: 700, color: "var(--green-500)" }, children: adgDecision.decision.selected_branch })
          ] }),
          /* @__PURE__ */ jsxs("div", { style: { fontSize: 13, marginBottom: 4 }, children: [
            /* @__PURE__ */ jsx("span", { style: { color: "var(--text-muted)" }, children: "Confidence:" }),
            " ",
            adgDecision.decision.confidence,
            "%"
          ] }),
          /* @__PURE__ */ jsxs("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: [
            /* @__PURE__ */ jsx("span", { style: { color: "var(--text-muted)" }, children: "Reasoning:" }),
            " ",
            adgDecision.decision.reasoning
          ] })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "section-title", children: "Human Override (Optional)" }),
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", gap: 12, marginBottom: 12 }, children: [
          /* @__PURE__ */ jsx(
            "input",
            {
              type: "text",
              className: "input",
              placeholder: "Override Branch (e.g. MANUAL_REVIEW)",
              value: adgOverrideBranch,
              onChange: (e) => setAdgOverrideBranch(e.target.value),
              style: { flex: 1 }
            }
          ),
          /* @__PURE__ */ jsx(
            "input",
            {
              type: "text",
              className: "input",
              placeholder: "Reasoning",
              value: adgOverrideReason,
              onChange: (e) => setAdgOverrideReason(e.target.value),
              style: { flex: 2 }
            }
          )
        ] }),
        /* @__PURE__ */ jsx("button", { className: "btn btn-primary", onClick: handleADGOverride, disabled: !adgOverrideBranch, children: "\u26A1 Submit Override" })
      ] }),
      firewallViolation && !trcResult && /* @__PURE__ */ jsxs("div", { className: "card-elevated fade-in", style: { padding: 24, borderColor: "var(--purple-500)", borderWidth: 2, background: "var(--bg-elevated)", borderRadius: 16 }, children: [
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }, children: [
          /* @__PURE__ */ jsx("div", { className: "spinner", style: { borderColor: "var(--purple-500)", borderTopColor: "transparent", width: 24, height: 24, borderRadius: "50%", borderStyle: "solid", borderWidth: 2 } }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { style: { fontWeight: 800, color: "var(--purple-400)", fontSize: 16 }, children: "Temporal Reasoning Cortex Activating..." }),
            /* @__PURE__ */ jsxs("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: [
              "Analyzing failure and computing architectural patch. ",
              /* @__PURE__ */ jsx("strong", { style: { color: "var(--purple-300)" }, children: "This process may take 60-90 seconds to communicate with all LLM agents. Please wait." })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "grid-2", style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }, children: [
          { id: 1, name: "Self Autopsy" },
          { id: 2, name: "Causal Chain Reconstruction" },
          { id: 3, name: "Architectural Patch Proposal" },
          { id: 4, name: "Mini-Court Review" }
        ].map((phase) => {
          const state = trcPhases.find((p) => p.phase === phase.id);
          const statusClass = state?.status === "DONE" ? "done" : state?.status === "RUNNING" ? "running" : "waiting";
          return /* @__PURE__ */ jsxs("div", { className: `trc-phase ${statusClass}`, style: { display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", background: "var(--bg-surface)", border: "1px solid var(--border)", borderRadius: 12, opacity: statusClass === "waiting" ? 0.4 : 1, borderColor: statusClass === "running" ? "var(--purple-500)" : statusClass === "done" ? "rgba(16,185,129,0.3)" : "var(--border)" }, children: [
            /* @__PURE__ */ jsx("div", { className: `phase-number ${statusClass}`, style: { display: "flex", alignItems: "center", justifyContent: "center", width: 28, height: 28, borderRadius: "50%", fontSize: 12, fontWeight: 700, background: statusClass === "done" ? "rgba(16,185,129,0.2)" : statusClass === "running" ? "rgba(139,92,246,0.25)" : "var(--border)", color: statusClass === "done" ? "var(--green-500)" : statusClass === "running" ? "var(--purple-400)" : "var(--text-muted)" }, children: state?.status === "DONE" ? "\u2713" : phase.id }),
            /* @__PURE__ */ jsxs("div", { style: { flex: 1 }, children: [
              /* @__PURE__ */ jsx("div", { style: { fontWeight: 600, fontSize: 14, color: "var(--text-primary)" }, children: phase.name }),
              state?.result && /* @__PURE__ */ jsxs("div", { style: { fontSize: 12, color: "var(--text-secondary)", marginTop: 4 }, children: [
                phase.id === 1 && state.result.preliminary_root_cause,
                phase.id === 2 && state.result.causal_narrative,
                phase.id === 3 && `Proposed: ${state.result.patch_type}`,
                phase.id === 4 && `Verdict: ${state.result.court_verdict}`
              ] })
            ] })
          ] }, phase.id);
        }) })
      ] }),
      trcResult && /* @__PURE__ */ jsxs("div", { className: "card-elevated fade-in", style: { padding: 24, border: "2px solid var(--purple-500)" }, children: [
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }, children: [
          /* @__PURE__ */ jsx("div", { style: { fontSize: 24 }, children: "\u{1F9E0}" }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsxs("div", { style: { fontWeight: 800, fontSize: 16, color: "var(--purple-400)" }, children: [
              "TRC Patch Proposed (Attempt #",
              trcResult.attempt_number,
              ")"
            ] }),
            /* @__PURE__ */ jsx("div", { style: { fontSize: 13, color: "var(--text-secondary)" }, children: "Human approval required to apply patch and resume execution." })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "grid-2", style: { marginBottom: 20 }, children: [
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { className: "section-title", children: "Autopsy Result" }),
            /* @__PURE__ */ jsxs("div", { className: "code-block", style: { marginBottom: 12 }, children: [
              /* @__PURE__ */ jsx("span", { style: { color: "#fca5a5" }, children: "Failure: " }),
              trcResult.autopsy.failure_type,
              /* @__PURE__ */ jsx("br", {}),
              /* @__PURE__ */ jsx("span", { style: { color: "#86efac" }, children: "Root Cause: " }),
              trcResult.autopsy.preliminary_root_cause
            ] }),
            /* @__PURE__ */ jsx("div", { className: "section-title", children: "Causal Chain Narrative" }),
            /* @__PURE__ */ jsx("div", { style: { fontSize: 13, color: "var(--text-secondary)", background: "var(--bg-base)", padding: 12, borderRadius: "var(--radius-sm)" }, children: trcResult.causal_chain.causal_narrative })
          ] }),
          /* @__PURE__ */ jsxs("div", { children: [
            /* @__PURE__ */ jsx("div", { className: "section-title", children: "Proposed Architecture Patch" }),
            /* @__PURE__ */ jsxs("div", { className: "card", style: { padding: 14, background: "rgba(139,92,246,0.05)", borderColor: "rgba(139,92,246,0.3)" }, children: [
              /* @__PURE__ */ jsxs("div", { style: { fontWeight: 600, fontSize: 14, marginBottom: 8, color: "var(--text-primary)" }, children: [
                "Type: ",
                trcResult.patch.patch_type
              ] }),
              /* @__PURE__ */ jsx("div", { style: { fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }, children: trcResult.patch.patch_rationale }),
              trcResult.patch.new_nodes?.map((n) => /* @__PURE__ */ jsxs("div", { style: { fontSize: 12, padding: 8, background: "var(--bg-base)", borderRadius: 4, borderLeft: "2px solid var(--green-500)" }, children: [
                /* @__PURE__ */ jsx("span", { style: { fontWeight: 700 }, children: "+ Node:" }),
                " ",
                n.label,
                " (",
                n.node_type,
                ")",
                /* @__PURE__ */ jsx("br", {}),
                /* @__PURE__ */ jsx("span", { style: { color: "var(--text-muted)" }, children: n.description })
              ] }, n.node_id))
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { style: { display: "flex", gap: 12 }, children: [
          /* @__PURE__ */ jsx("button", { className: "btn btn-primary", onClick: handleApprovePatch, children: "\u2705 Approve & Apply Patch" }),
          /* @__PURE__ */ jsx("button", { className: "btn btn-danger", onClick: () => navigate("/"), children: "\u{1F5D1} Abandon Case" })
        ] })
      ] })
    ] }),
    showAudit && /* @__PURE__ */ jsxs(Fragment, { children: [
      /* @__PURE__ */ jsx("div", { style: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 40 }, onClick: () => setShowAudit(false) }),
      /* @__PURE__ */ jsxs("div", { className: "slide-in", style: { position: "fixed", top: 0, right: 0, bottom: 0, width: 400, background: "var(--bg-base)", borderLeft: "1px solid var(--border)", zIndex: 50, display: "flex", flexDirection: "column", boxShadow: "-10px 0 30px rgba(0,0,0,0.5)" }, children: [
        /* @__PURE__ */ jsxs("div", { style: { padding: 20, borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }, children: [
          /* @__PURE__ */ jsx("div", { style: { fontWeight: 700, fontSize: 16 }, children: "Immutable Audit Trail" }),
          /* @__PURE__ */ jsx("button", { className: "btn btn-secondary btn-sm", onClick: () => setShowAudit(false), children: "\u2715" })
        ] }),
        /* @__PURE__ */ jsxs("div", { style: { flex: 1, overflowY: "auto", padding: 20 }, className: "timeline", children: [
          auditTrail.map((log) => /* @__PURE__ */ jsxs("div", { className: "timeline-item", children: [
            /* @__PURE__ */ jsx("div", { className: "timeline-dot", style: { background: log.event_type.includes("FIREWALL") ? "rgba(239,68,68,0.1)" : "var(--bg-elevated)", color: log.event_type.includes("FIREWALL") ? "#ef4444" : "inherit" }, children: log.sequence_number }),
            /* @__PURE__ */ jsxs("div", { className: "timeline-content", children: [
              /* @__PURE__ */ jsx("div", { style: { fontWeight: 600, fontSize: 13, marginBottom: 2 }, children: log.event_type }),
              /* @__PURE__ */ jsxs("div", { style: { fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }, children: [
                new Date(log.event_timestamp).toLocaleTimeString(),
                " \xB7 By ",
                log.triggered_by
              ] }),
              log.node_id && /* @__PURE__ */ jsxs("div", { style: { fontSize: 12, color: "var(--text-secondary)" }, children: [
                "Node: ",
                log.node_id
              ] })
            ] })
          ] }, log.log_id)),
          auditTrail.length === 0 && /* @__PURE__ */ jsx("div", { className: "empty-state", style: { padding: 20 }, children: "No events yet." })
        ] })
      ] })
    ] })
  ] });
}
export default CaseDashboard;
