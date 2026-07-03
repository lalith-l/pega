import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import ReactFlow, {
  Background, Controls, MiniMap,
  useNodesState, useEdgesState, MarkerType, Handle, Position
} from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from '../api/client';

const NODE_TYPE_ICONS = {
  API_CALL: '🔗', DATA_TRANSFORM: '⚙', DECISION_GATE: '⬦',
  NOTIFICATION: '🔔', HUMAN_REVIEW: '👁', VALIDATION: '✔',
  ADG_GATE: '🎯', DEFAULT: '◆', FIREWALL_GATE: '🛡',
};

/* ── Unified Custom Node ────────────────────────────────────────────────── */
function MorpheusNode({ data }) {
  const isExecuting = data.current_node_id === data.node_id;
  const isCompleted = data.completed?.includes(data.node_id);
  const isFirewallBlocked = data.checkpoint?.failure_node_id === data.node_id;
  const isCausal = data.trcHighlight?.includes(data.node_id);

  // Court states
  const disputeCount = Object.values(data.agent_verdicts || {})
    .filter((v) => v?.verdict === 'DISPUTE').length;
  const courtStatus = data.final_status || '';

  let statusClass = '';
  if (isFirewallBlocked) {
    statusClass = 'firewall-blocked bg-red-900 border-red-500 animate-pulse';
  }
  else if (isExecuting) statusClass = 'executing';
  else if (isCompleted) statusClass = 'completed';
  else if (courtStatus) statusClass = courtStatus.toLowerCase();
  if (isCausal && !isFirewallBlocked) statusClass += ' causal';

  return (
    <div
      className={`morpheus-node ${statusClass}`}
      onClick={() => data.onSelect && data.onSelect(data)}
      style={{ minWidth: 170, cursor: data.onSelect ? 'pointer' : 'default' }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#475569', border: 'none' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>{NODE_TYPE_ICONS[data.node_type] || '◆'}</span>
        <div className="node-label">{data.label}</div>
      </div>
      <div className="node-type-badge">{data.node_type}</div>

      {/* Court disputes */}
      {disputeCount > 0 && !isExecuting && !isCompleted && !isFirewallBlocked && (
        <div style={{
          marginTop: 8, padding: '3px 8px', borderRadius: 4,
          background: 'rgba(239,68,68,0.15)', color: '#fca5a5',
          fontSize: 10, fontWeight: 700,
        }}>
          ⚠ {disputeCount} dispute{disputeCount > 1 ? 's' : ''}
        </div>
      )}

      {/* Execution states */}
      {isExecuting && (
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--purple-400)' }}>
          <span className="pulse-dot purple" /> Executing
        </div>
      )}
      {isCompleted && !isFirewallBlocked && (
        <div style={{ marginTop: 8, fontSize: 10, color: 'var(--green-500)', fontWeight: 600 }}>✅ Completed</div>
      )}
      {isFirewallBlocked && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--red-500)', fontWeight: 800 }}>🔥 BLOCKED</div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ background: '#475569', border: 'none' }} />
    </div>
  );
}

const nodeTypes = { morpheusNode: MorpheusNode };

/* ── Conflict side panel (Court Phase) ──────────────────────────────────── */
function ConflictPanel({ node, sessionId, onResolved, onClose }) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);

  const disputes = Object.entries(node.agent_verdicts || {})
    .filter(([, v]) => v?.verdict === 'DISPUTE');

  const submit = async (act) => {
    setLoading(true);
    try {
      await api.resolveConflict(sessionId, node.node_id, act, instruction || null);
      onResolved(node.node_id, act);
      onClose();
    } catch (e) {
      alert('Failed to resolve: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="side-panel fade-in" style={{ position: 'absolute', right: 24, top: 24, zIndex: 10, background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 24, width: 350, boxShadow: '0 10px 30px rgba(0,0,0,0.3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>⚠ Conflict Resolution</div>
        <button onClick={onClose} className="btn btn-secondary btn-sm">✕</button>
      </div>

      <div className="card-elevated" style={{ padding: 16, marginBottom: 16 }}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>{node.label}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{node.node_type}</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{node.description}</div>
      </div>

      <div className="section-title">Agent Disputes</div>
      {disputes.map(([agent, v]) => (
        <div key={agent} style={{
          marginBottom: 12, padding: 14, borderRadius: 'var(--radius)',
          background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span className={`agent-chip agent-${agent.toLowerCase()}`}>{agent}</span>
            <span style={{
              fontSize: 10, padding: '2px 8px', borderRadius: 99,
              background: 'rgba(239,68,68,0.15)', color: '#fca5a5',
              fontWeight: 700,
            }}>{v.severity}</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{v.reasoning}</div>
        </div>
      ))}

      <div className="section-title" style={{ marginTop: 20 }}>Your Decision</div>
      <textarea
        className="input textarea"
        placeholder="Instruction..."
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        style={{ marginBottom: 12 }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button className="btn btn-success" onClick={() => submit('ACCEPT')} disabled={loading}>✅ Accept As-Is</button>
        <button className="btn btn-secondary" onClick={() => submit('MODIFY')} disabled={loading || !instruction}>✏ Modify</button>
        <button className="btn btn-danger" onClick={() => submit('REMOVE')} disabled={loading}>🗑 Remove Node</button>
      </div>
    </div>
  );
}

/* ── Main Case Journey ──────────────────────────────────────────────────── */
function CaseDashboard() {
  const { caseId: paramCaseId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const [objective, setObjective] = useState(location.state?.objective || '');
  const [caseId, setCaseId] = useState(paramCaseId || null);
  const [sessionId, setSessionId] = useState(null);

  // States
  const [caseData, setCaseData] = useState(null);
  const [courtStatus, setCourtStatus] = useState(null);
  const [courtRecord, setCourtRecord] = useState(null);
  const [auditTrail, setAuditTrail] = useState([]);

  // UI States
  const [showAudit, setShowAudit] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [compiling, setCompiling] = useState(false);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Execution States
  const [activeNodeId, setActiveNodeId] = useState(null);
  const [completedNodes, setCompletedNodes] = useState([]);
  const [firewallViolation, setFirewallViolation] = useState(null);
  const [trcPhases, setTrcPhases] = useState([
    { phase: 1, name: 'Self Autopsy', status: 'WAITING', result: null },
    { phase: 2, name: 'Causal Chain Reconstruction', status: 'WAITING', result: null },
    { phase: 3, name: 'Architectural Patch Proposal', status: 'WAITING', result: null },
    { phase: 4, name: 'Mini-Court Review', status: 'WAITING', result: null },
  ]);
  const [trcResult, setTrcResult] = useState(null);
  
  // ADG States
  const [adgDecision, setAdgDecision] = useState(null);
  const [adgTimeLeft, setAdgTimeLeft] = useState(0);
  const [adgOverrideReason, setAdgOverrideReason] = useState('');
  const [adgOverrideBranch, setAdgOverrideBranch] = useState('');

  const pollRef = useRef(null);
  const caseDataRef = useRef(caseData);

  // Keep ref in sync so callbacks see latest data without re-subscribing
  useEffect(() => { caseDataRef.current = caseData; }, [caseData]);

  /* Build Graph Helper */
  const buildGraph = useCallback((nodesList, isCourt, onSelect, checkpoint) => {
    if (!nodesList || nodesList.length === 0) return;

    // Deduplicate nodes
    const uniqueNodes = [];
    const seenIds = new Set();
    for (const n of nodesList) {
      if (!seenIds.has(n.node_id)) {
        seenIds.add(n.node_id);
        uniqueNodes.push(n);
      }
    }

    const rfNodes = uniqueNodes.map((n, i) => ({
      id: n.node_id,
      type: 'morpheusNode',
      position: { x: 80 + (i % 3) * 250, y: 80 + Math.floor(i / 3) * 160 },
      data: {
        ...n,
        onSelect: isCourt ? onSelect : null,
        current_node_id: checkpoint?.current_node_id,
        completed: checkpoint?.completed_nodes || [],
        checkpoint: checkpoint,
      },
    }));

    const rfEdges = [];
    uniqueNodes.forEach((n) => {
      (n.dependencies || []).forEach((depId) => {
        rfEdges.push({
          id: `${depId}-${n.node_id}`,
          source: depId, target: n.node_id,
          animated: true,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#475569' },
          style: { stroke: '#334155' },
        });
      });
    });

    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [setNodes, setEdges]);

  /* Live update execution graph visually */
  const updateGraphState = useCallback((currentId, completedId, blockedId, trcHighlightIds) => {
    setNodes((prev) => prev.map((n) => {
      const data = { ...n.data };
      if (currentId !== null && currentId !== undefined) data.current_node_id = currentId;
      if (completedId) data.completed = [...new Set([...(data.completed || []), completedId])];
      if (blockedId) data.checkpoint = { ...data.checkpoint, failure_node_id: blockedId };
      if (trcHighlightIds) data.trcHighlight = trcHighlightIds;

      if (completedId && currentId === null && data.current_node_id === completedId) {
        data.current_node_id = null;
      }
      return { ...n, data };
    }));
  }, [setNodes]);

  /* Refresh audit trail */
  const refreshAudit = useCallback(() => {
    if (caseId) {
      api.getAudit(caseId).then((res) => setAuditTrail(res.audit_trail)).catch(() => {});
    }
  }, [caseId]);

  /* Load Initial Data if caseId exists */
  useEffect(() => {
    if (!caseId) return;
    api.getCase(caseId).then((data) => {
      setCaseData(data);
      if (data.court_session_id && data.status === 'DRAFT') {
        setSessionId(data.court_session_id);
      }
      if (data.status !== 'DRAFT') {
        if (data.checkpoint) {
          setCompletedNodes(data.checkpoint.completed_nodes || []);
          if (data.checkpoint.current_node_id && data.status === 'EXECUTING') {
            setActiveNodeId(data.checkpoint.current_node_id);
          }
          if (data.checkpoint.violation_report) setFirewallViolation(data.checkpoint.violation_report);
          if (data.checkpoint.trc_result) setTrcResult(data.checkpoint.trc_result);
        }
        buildGraph(data.compiled_workflow?.nodes, false, null, data.checkpoint);
      }
    }).catch((e) => console.error("Failed to load case:", e));
    refreshAudit();
  }, [caseId, buildGraph, refreshAudit]);

  /* Poll Court Session — only when in DRAFT */
  useEffect(() => {
    if (!sessionId) return;
    // Guard: only poll court when status is DRAFT (or caseData is null, meaning just convened)
    const status = caseDataRef.current?.status;
    if (status && status !== 'DRAFT') return;

    const poll = async () => {
      try {
        const courtSt = await api.courtStatus(sessionId);
        setCourtStatus(courtSt);
        if (['AWAITING_HUMAN', 'COMPLETED', 'COMPILED'].includes(courtSt.session_status)) {
          const record = await api.courtRecord(sessionId);
          setCourtRecord(record.court_record);
          buildGraph(record.court_record?.proposed_nodes, true, setSelectedNode, null);
          clearInterval(pollRef.current);
        }
      } catch (e) {
        console.error("Court polling error:", e);
      }
    };
    poll();
    pollRef.current = setInterval(poll, 5000);
    return () => clearInterval(pollRef.current);
  }, [sessionId, buildGraph]);

  /* Execution & TRC Polling Safety Net — syncs state from backend every 5s */
  useEffect(() => {
    if (!caseId) return;
    const status = caseData?.status;
    if (!status || status === 'DRAFT' || status?.includes('CLOSED') || status === 'SUSPENDED') return;
    
    const pollSync = async () => {
      try {
        const data = await api.getCase(caseId);
        if (!data || !data.status) return;
        
        // Always sync status
        setCaseData(prev => {
          if (!prev || data.status !== prev.status || JSON.stringify(data.checkpoint) !== JSON.stringify(prev?.checkpoint)) {
            return data;
          }
          return prev;
        });

        // (Graph building is handled by initial load and handleCompile)

        if (data.checkpoint) {
          const cp = data.checkpoint;
          
          // Update executing node
          if (cp.current_node_id && data.status === 'EXECUTING') {
             setActiveNodeId(cp.current_node_id);
             updateGraphState(cp.current_node_id, null, null, null);
          }
          // Update completed nodes on canvas
          const cpCompleted = cp.completed_nodes || [];
          if (cpCompleted.length > 0) {
            setNodes(prev => prev.map(n => {
              if (cpCompleted.includes(n.id) && !(n.data.completed || []).includes(n.id)) {
                return { ...n, data: { ...n.data, completed: cpCompleted } };
              }
              return n;
            }));
          }
          // Firewall blocked
          if (cp.failure_node_id) {
             setFirewallViolation(cp.violation_report);
             updateGraphState(null, null, cp.failure_node_id, null);
          }
          // TRC result arrived via polling (backup for SSE miss)
          if (cp.trc_result && !trcResult) {
            setTrcResult(cp.trc_result);
          }
          
          // TRC phase progress sync
          setTrcPhases(prev => {
            const copy = [...prev];
            const updatePhase = (id, resultKey) => {
              if (cp[resultKey]) {
                 const idx = copy.findIndex(p => p.phase === id);
                 if (idx >= 0 && copy[idx].status !== 'DONE') {
                   copy[idx] = { ...copy[idx], status: 'DONE', result: cp[resultKey] };
                 }
              }
            };
            updatePhase(1, 'trc_autopsy');
            updatePhase(2, 'trc_causal_chain');
            updatePhase(3, 'trc_patch');
            updatePhase(4, 'trc_court_verdict');
            return copy;
          });
        }

        // Refresh audit trail periodically
        refreshAudit();
      } catch (e) {
        console.error("Execution poll error", e);
      }
    };
    
    const timer = setInterval(pollSync, 5000);
    pollSync();
    
    return () => clearInterval(timer);
  }, [caseId, caseData?.status, updateGraphState, buildGraph, refreshAudit, trcResult, setNodes]);

  /* SSE Subscription for Execution — real-time updates */
  useEffect(() => {
    if (!caseId) return;
    const status = caseData?.status;
    if (status === 'DRAFT') return;

    const unsub = api.streamEvents(caseId, (event) => {
      console.log("[SSE] Event:", event.type, event.payload);
      switch (event.type) {
        case 'NODE_STARTED':
          setActiveNodeId(event.payload.node_id);
          updateGraphState(event.payload.node_id, null, null, null);
          break;
        case 'NODE_COMPLETED':
          setActiveNodeId(null);
          updateGraphState(null, event.payload.node_id, null, null);
          break;
        case 'FIREWALL_KILLED':
          setActiveNodeId(null);
          setFirewallViolation({ node_id: event.payload.node_id, ...event.payload });
          updateGraphState(null, null, event.payload.node_id, null);
          setCaseData((prev) => prev ? { ...prev, status: 'PAUSED' } : prev);
          break;
        case 'TRC_PHASE':
          setTrcPhases((prev) => {
            const copy = [...prev];
            const pLoad = event?.payload;
            if (!pLoad || !pLoad.phase) return copy;
            
            const existingIdx = copy.findIndex(p => p.phase === pLoad.phase);
            if (existingIdx >= 0) {
              const old = copy[existingIdx];
              copy[existingIdx] = {
                ...old,
                name: pLoad.name || old.name,
                status: pLoad.status || old.status,
                result: pLoad.result || old.result
              };
            }
            return copy;
          });
          if (event.payload.highlight_nodes) {
            updateGraphState(null, null, null, event.payload.highlight_nodes);
          }
          break;
        case 'TRC_ACTIVATING':
          // Reset TRC phases when TRC starts
          setTrcPhases([
            { phase: 1, name: 'Self Autopsy', status: 'WAITING', result: null },
            { phase: 2, name: 'Causal Chain Reconstruction', status: 'WAITING', result: null },
            { phase: 3, name: 'Architectural Patch Proposal', status: 'WAITING', result: null },
            { phase: 4, name: 'Mini-Court Review', status: 'WAITING', result: null },
          ]);
          break;
        case 'ADG_DECISION':
          setAdgDecision(event.payload);
          setAdgTimeLeft(60);
          setCaseData((prev) => prev ? { ...prev, status: 'AWAITING_ADG_OVERRIDE' } : prev);
          break;
        case 'ADG_OVERRIDDEN':
          setAdgDecision(null);
          setAdgTimeLeft(0);
          break;
        case 'TRC_COMPLETE':
          setTrcResult(event.payload.trc_result);
          setCaseData((prev) => prev ? { ...prev, status: 'AWAITING_HUMAN' } : prev);
          break;
        case 'EXECUTION_STARTED':
          setCaseData((prev) => prev ? { ...prev, status: 'EXECUTING' } : prev);
          break;
        case 'CASE_COMPLETE':
        case 'CASE_CLOSED':
          setCaseData((prev) => prev ? { ...prev, status: event.payload.status || 'CLOSED_SUCCESS' } : prev);
          setActiveNodeId(null);
          break;
        case 'CASE_SUSPENDED':
          setCaseData((prev) => prev ? { ...prev, status: 'SUSPENDED' } : prev);
          setActiveNodeId(null);
          break;
        case 'PATCH_APPROVED':
          setTrcResult(null);
          setFirewallViolation(null);
          setTrcPhases([
            { phase: 1, name: 'Self Autopsy', status: 'WAITING', result: null },
            { phase: 2, name: 'Causal Chain Reconstruction', status: 'WAITING', result: null },
            { phase: 3, name: 'Architectural Patch Proposal', status: 'WAITING', result: null },
            { phase: 4, name: 'Mini-Court Review', status: 'WAITING', result: null },
          ]);
          setCaseData((prev) => prev ? { ...prev, status: 'RESUMING' } : prev);
          // Re-fetch full case data from backend
          api.getCase(caseId).then((data) => {
            setCaseData(data);
            if (data.compiled_workflow?.nodes) {
              buildGraph(data.compiled_workflow.nodes, false, null, data.checkpoint);
            }
          }).catch(() => {});
          break;
        case 'FIREWALL_PASSED':
          // No UI action needed, just log
          break;
        default:
          console.log("[SSE] Unhandled event:", event.type);
      }
    });
    return () => unsub();
  }, [caseId, caseData?.status, updateGraphState, buildGraph]);

  /* ADG Timer */
  useEffect(() => {
    if (adgTimeLeft > 0) {
      const timer = setTimeout(() => setAdgTimeLeft(t => t - 1), 1000);
      return () => clearTimeout(timer);
    } else if (adgTimeLeft === 0 && adgDecision) {
      setAdgDecision(null); // Auto-dismiss when timer expires
    }
  }, [adgTimeLeft, adgDecision]);

  /* Actions */
  const handleConvene = async () => {
    if (!objective.trim()) return;
    try {
      const res = await api.convene(objective.trim());
      setSessionId(res.session_id);
      setCaseId(res.case_id);
      setCaseData({ status: 'DRAFT', case_id: res.case_id, business_objective: objective.trim() });
      window.history.replaceState({}, '', `/cases/${res.case_id}`);
    } catch (e) {
      alert('Failed to convene court: ' + e.message);
    }
  };

  const handleResolved = (nodeId, action) => {
    setNodes((prev) => prev.map((n) =>
      n.id === nodeId
        ? { ...n, data: { ...n.data, final_status: action === 'REMOVE' ? 'REMOVED' : 'RESOLVED' } }
        : n
    ));
    if (sessionId) api.courtRecord(sessionId).then((r) => setCourtRecord(r.court_record)).catch(() => {});
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
      alert('Compile failed: ' + e.message);
    } finally {
      setCompiling(false);
    }
  };

  const handleExecute = async () => {
    try {
      await api.execute(caseId);
      setCaseData((prev) => prev ? { ...prev, status: 'EXECUTING' } : prev);
    } catch (e) {
      alert(e.message);
    }
  };

  const handleApprovePatch = async () => {
    try {
      const res = await api.approvePatch(caseId);
      // Always reset TRC UI — execution is resuming
      setTrcResult(null);
      setFirewallViolation(null);
      setTrcPhases([
        { phase: 1, name: 'Self Autopsy', status: 'WAITING', result: null },
        { phase: 2, name: 'Causal Chain Reconstruction', status: 'WAITING', result: null },
        { phase: 3, name: 'Architectural Patch Proposal', status: 'WAITING', result: null },
        { phase: 4, name: 'Mini-Court Review', status: 'WAITING', result: null },
      ]);
      // Force a clean fetch of the case data from backend
      const freshData = await api.getCase(caseId);
      setCaseData(freshData);
      if (freshData.compiled_workflow?.nodes) {
         buildGraph(freshData.compiled_workflow.nodes, false, null, freshData.checkpoint);
      }
      refreshAudit();
    } catch (e) {
      alert('Failed to approve patch: ' + e.message);
    }
  };

  const allResolved = courtRecord?.proposed_nodes?.every(
    (n) => ['CONSENSUS', 'RESOLVED', 'WARNED'].includes(n.final_status)
  );

  const handleADGOverride = async () => {
    if (!adgOverrideBranch) return;
    try {
      await api.overrideADG(caseId, adgDecision.node_id, adgOverrideBranch, adgOverrideReason);
    } catch (e) {
      alert('Override failed: ' + e.message);
    }
  };

  /* ── Render ── */
  return (
    <div className="page fade-in" style={{ position: 'relative' }}>

      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <h1 className="page-title" style={{ margin: 0 }}>Case Journey</h1>
            {caseData && (
              <span className={`badge badge-${['COMPILED', 'RESOLVED'].includes(caseData.status) ? 'resolved' : caseData.status === 'EXECUTING' ? 'executing' : caseData.status === 'PAUSED' ? 'paused' : caseData.status === 'SUSPENDED' ? 'suspended' : caseData.status?.includes('CLOSED') ? 'closed-success' : 'pending'}`}>
                {caseData.status}
              </span>
            )}
          </div>
          <p className="page-subtitle" style={{ maxWidth: 600 }}>{caseData?.business_objective || 'Start a new workflow automation.'}</p>
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          {caseData && (
            <button className="btn btn-secondary" onClick={() => { refreshAudit(); setShowAudit(true); }}>
              📋 Audit Trail
            </button>
          )}
          {caseData?.status === 'COMPILED' || caseData?.status === 'RESUMING' ? (
            <button className="btn btn-primary btn-lg pulse-bg" onClick={handleExecute}>
              ⚡ Execute Case
            </button>
          ) : null}
        </div>
      </div>

      {/* Suspended State Display */}
      {caseData?.status === 'SUSPENDED' && (
        <div className="card" style={{ padding: 24, margin: '20px 0', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <span style={{ fontSize: 24 }}>⚠️</span>
            <h3 style={{ margin: 0, color: '#fbbf24' }}>System Suspended</h3>
          </div>
          {(() => {
            const report = auditTrail.find(a => a.event_type === 'CASE_SUSPENDED')?.event_payload || {};
            return (
              <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                <p style={{ color: '#f87171', fontWeight: 600 }}>Conclusion: {report.conclusion || "Three TRC attempts exhausted. Irresolvable architectural contradiction."}</p>
                <p><strong>Required Action:</strong> {report.what_human_must_do || "Restate the objective with explicit priority ordering between conflicting constraints."}</p>
                <button 
                  className="btn btn-primary" 
                  style={{ marginTop: 16 }}
                  onClick={() => {
                    navigate('/');
                    window.location.reload();
                  }}
                >
                  ↩ Restate Objective
                </button>
              </div>
            );
          })()}
        </div>
      )}

      {/* Closed Success */}
      {caseData?.status?.includes('CLOSED') && (
        <div className="card" style={{ padding: 24, margin: '20px 0', border: '1px solid rgba(16, 185, 129, 0.3)', background: 'rgba(16, 185, 129, 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
            <span style={{ fontSize: 28 }}>✅</span>
            <h3 style={{ margin: 0, color: '#10b981' }}>Case {caseData.status === 'CLOSED_SUCCESS' ? 'Completed Successfully' : 'Closed'}</h3>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>All workflow nodes executed successfully. See the Audit Trail for full details.</p>
        </div>
      )}

      {/* 1. Init state (No caseId) */}
      {!caseId && (
        <div className="card" style={{ padding: 24, maxWidth: 700, margin: '40px auto' }}>
          <div className="section-title">Business Objective</div>
          <textarea
            className="input textarea"
            placeholder="e.g. Automate vendor invoice processing: verify GST, validate vendor..."
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            style={{ marginBottom: 12, minHeight: 100 }}
          />
          <button className="btn btn-primary" onClick={handleConvene} disabled={!objective.trim()}>
            ⬡ Convene Court
          </button>
        </div>
      )}

      {/* 2. Court Phase */}
      {sessionId && caseData?.status === 'DRAFT' && (
        <div className="fade-in">
          <div className="grid-4" style={{ marginBottom: 20 }}>
            {['ARCHITECT', 'SECURITY', 'EFFICIENCY', 'COMPLIANCE'].map((agent) => {
              const doneKey = `${agent.toLowerCase()}_done`;
              const done = courtStatus?.[doneKey];
              const running = !done && courtStatus?.session_status === 'DEBATING' &&
                ['ARCHITECT', 'SECURITY', 'EFFICIENCY', 'COMPLIANCE']
                  .slice(0, ['ARCHITECT', 'SECURITY', 'EFFICIENCY', 'COMPLIANCE'].indexOf(agent))
                  .every((a) => courtStatus?.[`${a.toLowerCase()}_done`]);
              return (
                <div key={agent} className="card-elevated" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: 12, borderColor: done ? 'rgba(16,185,129,0.3)' : running ? 'rgba(139,92,246,0.4)' : undefined }}>
                  {done ? <span>✅</span> : running ? <div className="spinner" /> : <div style={{ width: 16, height: 16, borderRadius: '50%', background: 'var(--border)' }} />}
                  <div>
                    <span className={`agent-chip agent-${agent.toLowerCase()}`}>{agent}</span>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                      {done ? 'Verdicts recorded' : running ? 'Deliberating…' : 'Awaiting…'}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {courtRecord && (
            <div className="fade-in" style={{ position: 'relative' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {allResolved ? '✅ All conflicts resolved — ready to compile' : '⚠ Resolve highlighted conflicts to proceed'}
                </div>
                <button className="btn btn-primary" onClick={handleCompile} disabled={!allResolved || compiling}>
                  {compiling ? <><div className="spinner" /> Compiling…</> : '⚡ Compile & Start Case'}
                </button>
              </div>
              <div style={{ height: 500, borderRadius: 'var(--radius-lg)', overflow: 'hidden', border: '1px solid var(--border)', position: 'relative' }}>
                {(nodes && nodes.length > 0) ? (
                  <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
                    <Background color="#1e293b" gap={24} size={1} />
                    <Controls />
                  </ReactFlow>
                ) : (
                  <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                    <div className="spinner" style={{ marginRight: 12 }} /> Waiting for Architecture Court debate...
                  </div>
                )}
                {selectedNode && (
                  <ConflictPanel node={selectedNode} sessionId={sessionId} onResolved={handleResolved} onClose={() => setSelectedNode(null)} />
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3. Execution Phase */}
      {caseData && caseData.status !== 'DRAFT' && (
        <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

          <div className="card-elevated" style={{ height: 500, overflow: 'hidden' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 14 }}>
              Execution Graph
            </div>
            <div style={{ height: 'calc(100% - 45px)' }}>
              {(nodes && nodes.length > 0) ? (
                <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }}>
                  <Background color="#1e293b" gap={24} size={1} />
                  <Controls />
                </ReactFlow>
              ) : (
                <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: '#94a3b8' }}>
                  <div className="spinner" style={{ marginRight: 12 }} /> Loading graph...
                </div>
              )}
            </div>
          </div>

          {firewallViolation && (
            <div className="firewall-alert slide-in" style={{ borderColor: '#ef4444', borderWidth: 2 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <span style={{ fontSize: 24 }}>🔥</span>
                <div>
                  <div style={{ fontWeight: 900, color: 'var(--red-500)', fontSize: 16 }}>HALLUCINATION FIREWALL KILLED EXECUTION</div>
                  <div style={{ fontSize: 13, color: 'var(--red-500)', opacity: 0.8 }}>Node: {firewallViolation.node_id}</div>
                </div>
              </div>
              <div className="code-block" style={{ borderColor: 'rgba(239,68,68,0.3)', color: '#fca5a5', whiteSpace: 'pre-wrap', wordBreak: 'break-all', fontFamily: 'monospace', background: 'rgba(0,0,0,0.4)', padding: 14, borderRadius: 6 }}>
                Violation: {firewallViolation?.violation_type} (Layer {firewallViolation?.layer})<br />
                {JSON.stringify(firewallViolation?.details, null, 2)}
              </div>
            </div>
          )}

          {adgDecision && (
            <div className="card-elevated fade-in" style={{ padding: 24, borderColor: '#3b82f6', borderWidth: 2, background: 'rgba(59,130,246,0.05)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                  <span style={{ fontSize: 24 }}>🎯</span>
                  <div>
                    <div style={{ fontWeight: 900, color: '#3b82f6', fontSize: 16 }}>ADAPTIVE DECISIONING GATE</div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Node: {adgDecision.node_id} ({adgDecision.label})</div>
                  </div>
                </div>
                <div style={{ fontSize: 24, fontWeight: 800, color: adgTimeLeft < 10 ? '#ef4444' : '#3b82f6' }}>
                  {adgTimeLeft}s
                </div>
              </div>
              
              <div className="card" style={{ padding: 16, marginBottom: 16, background: 'var(--bg-base)' }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8 }}>LLM Proposed Decision</div>
                <div style={{ fontSize: 13, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Branch:</span> <span style={{ fontWeight: 700, color: 'var(--green-500)' }}>{adgDecision?.decision?.selected_branch}</span>
                </div>
                <div style={{ fontSize: 13, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Confidence:</span> {adgDecision?.decision?.confidence}%
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Reasoning:</span> {adgDecision?.decision?.reasoning}
                </div>
              </div>

              <div className="section-title">Human Override (Optional)</div>
              <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                <input
                  type="text"
                  className="input"
                  placeholder="Override Branch (e.g. MANUAL_REVIEW)"
                  value={adgOverrideBranch}
                  onChange={(e) => setAdgOverrideBranch(e.target.value)}
                  style={{ flex: 1 }}
                />
                <input
                  type="text"
                  className="input"
                  placeholder="Reasoning"
                  value={adgOverrideReason}
                  onChange={(e) => setAdgOverrideReason(e.target.value)}
                  style={{ flex: 2 }}
                />
              </div>
              <button className="btn btn-primary" onClick={handleADGOverride} disabled={!adgOverrideBranch}>
                ⚡ Submit Override
              </button>
            </div>
          )}

          {firewallViolation && !trcResult && (
            <div className="card-elevated fade-in" style={{ padding: 24, borderColor: 'var(--purple-500)', borderWidth: 2, background: 'var(--bg-elevated)', borderRadius: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                <div className="spinner" style={{ borderColor: 'var(--purple-500)', borderTopColor: 'transparent', width: 24, height: 24, borderRadius: '50%', borderStyle: 'solid', borderWidth: 2 }} />
                <div>
                  <div style={{ fontWeight: 800, color: 'var(--purple-400)', fontSize: 16 }}>Temporal Reasoning Cortex Activating...</div>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Analyzing failure and computing architectural patch. <strong style={{ color: 'var(--purple-300)' }}>This process may take 60-90 seconds. Please wait.</strong></div>
                </div>
              </div>

              <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                {[
                  { id: 1, name: 'Self Autopsy' },
                  { id: 2, name: 'Causal Chain Reconstruction' },
                  { id: 3, name: 'Architectural Patch Proposal' },
                  { id: 4, name: 'Mini-Court Review' },
                ].map((phase) => {
                  const state = trcPhases.find(p => p.phase === phase.id);
                  const statusClass = state?.status === 'DONE' ? 'done' : state?.status === 'RUNNING' ? 'running' : 'waiting';
                  return (
                    <div key={phase.id} className={`trc-phase ${statusClass}`} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px', background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 12, opacity: statusClass === 'waiting' ? 0.4 : 1, borderColor: statusClass === 'running' ? 'var(--purple-500)' : statusClass === 'done' ? 'rgba(16,185,129,0.3)' : 'var(--border)' }}>
                      <div className={`phase-number ${statusClass}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: '50%', fontSize: 12, fontWeight: 700, background: statusClass === 'done' ? 'rgba(16,185,129,0.2)' : statusClass === 'running' ? 'rgba(139,92,246,0.25)' : 'var(--border)', color: statusClass === 'done' ? 'var(--green-500)' : statusClass === 'running' ? 'var(--purple-400)' : 'var(--text-muted)' }}>
                        {state?.status === 'DONE' ? '✓' : phase.id}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>{phase.name}</div>
                        {state?.result && (
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                            {phase.id === 1 && state?.result?.preliminary_root_cause}
                            {phase.id === 2 && state?.result?.causal_narrative}
                            {phase.id === 3 && `Proposed: ${state?.result?.patch_type}`}
                            {phase.id === 4 && `Verdict: ${state?.result?.court_verdict}`}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {trcResult && (() => {
            try {
              const patch = trcResult?.patch || {};
              const autopsy = trcResult?.autopsy || {};
              const causalChain = trcResult?.causal_chain || {};
              const pathNodes = Array.isArray(causalChain?.path_nodes) ? causalChain.path_nodes : [];
              const newNodes = Array.isArray(patch?.new_nodes) ? patch.new_nodes : [];

              return (
                <div className="card-elevated fade-in" style={{ padding: 24, border: '2px solid var(--purple-500)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                    <div style={{ fontSize: 24 }}>🧠</div>
                    <div>
                      <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--purple-400)' }}>TRC Patch Proposed (Attempt #{trcResult?.attempt_number ?? 1})</div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Human approval required to apply patch and resume execution.</div>
                    </div>
                  </div>

                  <div className="grid-2" style={{ marginBottom: 20 }}>
                    <div>
                      <div className="section-title">Autopsy Result</div>
                      <div className="code-block" style={{ marginBottom: 12 }}>
                        <span style={{ color: '#fca5a5' }}>Failure: </span>{autopsy?.failure_type || 'SCHEMA_VIOLATION'}<br />
                        <span style={{ color: '#86efac' }}>Root Cause: </span>{autopsy?.preliminary_root_cause || 'Hallucinated parameter detected by Firewall.'}
                      </div>
                      <div className="section-title">Causal Chain Narrative</div>
                      {pathNodes.length > 0 ? (
                        <div style={{ display: 'flex', alignItems: 'center', overflowX: 'auto', gap: 8, padding: 12, background: 'var(--bg-base)', borderRadius: 'var(--radius-sm)' }}>
                          {pathNodes.map((n, i, arr) => (
                            <React.Fragment key={i}>
                              <div style={{ padding: 12, borderRadius: 8, background: n?.is_failure ? 'rgba(239,68,68,0.1)' : 'var(--bg-elevated)', border: `1px solid ${n?.is_failure ? '#ef4444' : 'var(--border)'}`, minWidth: 150 }}>
                                <div style={{ fontWeight: 700, fontSize: 13, color: n?.is_failure ? '#ef4444' : 'var(--text-primary)' }}>{n?.label || n?.node_id || 'Node'}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                   {n?.schema_version && `Schema: ${n.schema_version}`}
                                   {n?.declared_params_v21 && (
                                     <div style={{ marginTop: 4 }}>
                                       <div style={{ color: '#ef4444' }}>Decl: {String(n.declared_params_v21)}</div>
                                       <div style={{ color: '#10b981' }}>Exp: {String(n.expected_params_v24 ?? '')}</div>
                                     </div>
                                   )}
                                   {n?.failed_param && `Failed: ${n.failed_param}`}
                                </div>
                              </div>
                              {i < arr.length - 1 && <div style={{ color: 'var(--text-muted)' }}>→</div>}
                            </React.Fragment>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', background: 'var(--bg-base)', padding: 12, borderRadius: 'var(--radius-sm)' }}>
                          {causalChain?.causal_narrative || 'Workflow progressed → Firewall blocked hallucinated parameter → FAILURE'}
                        </div>
                      )}
                    </div>

                    <div>
                      <div className="section-title">Proposed Architecture Patch</div>
                      <div className="card" style={{ padding: 14, background: 'rgba(139,92,246,0.05)', borderColor: 'rgba(139,92,246,0.3)' }}>
                        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8, color: 'var(--text-primary)' }}>
                          Type: {patch?.patch_type || 'MODIFY_PARAMETERS'}
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
                          {patch?.patch_rationale || 'Patching declared parameters to align with production schema.'}
                        </div>
                        {newNodes.length > 0 ? newNodes.map((n, idx) => (
                          <div key={n?.node_id || idx} style={{ fontSize: 12, padding: 8, background: 'var(--bg-base)', borderRadius: 4, borderLeft: '2px solid var(--green-500)', marginBottom: 6 }}>
                            <span style={{ fontWeight: 700 }}>+ Node:</span> {n?.label || n?.node_id || 'Updated Node'} ({n?.node_type || 'API_CALL'})<br />
                            {n?.description && <span style={{ color: 'var(--text-muted)' }}>{n.description}</span>}
                            {n?.declared_parameters && typeof n.declared_parameters === 'object' && Object.keys(n.declared_parameters).length > 0 && (
                              <div style={{ marginTop: 4, fontSize: 11, color: '#86efac' }}>
                                ✓ Parameters: {Object.keys(n.declared_parameters).join(', ')}
                              </div>
                            )}
                          </div>
                        )) : (
                          <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>
                            Parameters will be corrected in the existing node to match production schema.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 12 }}>
                    <button className="btn btn-primary" onClick={handleApprovePatch}>✅ Approve &amp; Apply Patch</button>
                    <button className="btn btn-danger" onClick={async () => {
                      try {
                        await api.abandonCase(caseId);
                        const data = await api.getCase(caseId);
                        setCaseData(data);
                      } catch (e) {
                        alert('Failed: ' + e.message);
                      }
                    }}>🗑 Abandon Case</button>
                  </div>
                </div>
              );
            } catch (renderErr) {
              console.error('[TRC Render Error]', renderErr);
              return (
                <div className="card-elevated fade-in" style={{ padding: 24, border: '2px solid var(--purple-500)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                    <div style={{ fontSize: 24 }}>🧠</div>
                    <div>
                      <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--purple-400)' }}>TRC Patch Proposed</div>
                      <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Human approval required to apply patch and resume execution.</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 12 }}>
                    <button className="btn btn-primary" onClick={handleApprovePatch}>✅ Approve &amp; Apply Patch</button>
                    <button className="btn btn-danger" onClick={async () => {
                      try {
                        await api.abandonCase(caseId);
                        const data = await api.getCase(caseId);
                        setCaseData(data);
                      } catch (e) {
                        alert('Failed: ' + e.message);
                      }
                    }}>🗑 Abandon Case</button>
                  </div>
                </div>
              );
            }
          })()}

        </div>
      )}

      {/* Side Drawer: Audit Trail */}
      {showAudit && (
        <>
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }} onClick={() => setShowAudit(false)} />
          <div className="slide-in" style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 400, background: 'var(--bg-base)', borderLeft: '1px solid var(--border)', zIndex: 50, display: 'flex', flexDirection: 'column', boxShadow: '-10px 0 30px rgba(0,0,0,0.5)' }}>
            <div style={{ padding: 20, borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>Immutable Audit Trail</div>
              <button className="btn btn-secondary btn-sm" onClick={() => setShowAudit(false)}>✕</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 20 }} className="timeline">
              {auditTrail.map((log) => (
                <div key={log.log_id} className="timeline-item">
                  <div className="timeline-dot" style={{ background: log.event_type.includes('FIREWALL') ? 'rgba(239,68,68,0.1)' : 'var(--bg-elevated)', color: log.event_type.includes('FIREWALL') ? '#ef4444' : 'inherit' }}>
                    {log.sequence_number}
                  </div>
                  <div className="timeline-content">
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>{log.event_type}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                      {new Date(log.event_timestamp).toLocaleTimeString()} · By {log.triggered_by}
                    </div>
                    {log.node_id && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Node: {log.node_id}</div>}
                  </div>
                </div>
              ))}
              {auditTrail.length === 0 && <div className="empty-state" style={{ padding: 20 }}>No events yet.</div>}
            </div>
          </div>
        </>
      )}

    </div>
  );
}

export default CaseDashboard;
