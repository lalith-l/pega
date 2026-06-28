import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';

const STATUS_COLOR = {
  DRAFT: 'pending',
  COMPILED: 'resolved',
  EXECUTING: 'executing',
  PAUSED: 'paused',
  AWAITING_HUMAN: 'warned',
  RESUMING: 'executing',
  FAILED: 'disputed',
  SUSPENDED: 'disputed',
  CLOSED_SUCCESS: 'closed-success',
  CLOSED_FAILURE: 'disputed',
};

const STATUS_ICON = {
  DRAFT: '📝', COMPILED: '✅', EXECUTING: '⚡', PAUSED: '⏸',
  AWAITING_HUMAN: '🧠', RESUMING: '▶', FAILED: '❌',
  SUSPENDED: '🚫', CLOSED_SUCCESS: '🏆', CLOSED_FAILURE: '💀',
};

const DEMO_SCENARIOS = [
  "Automate vendor invoice processing for INV-2024-7821: verify GST, validate vendor, deduct TDS, post payment via ERP, notify finance team",
  "Process employee expense reimbursements: validate receipts, check GST compliance, get manager approval, trigger bank transfer via NEFT",
  "Automate purchase order lifecycle: validate PO, verify vendor GSTIN, check budget, approve payment, update ERP inventory",
];

function Landing() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.listCases()
      .then(setCases)
      .catch(() => setCases([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page fade-in">
      {/* Hero */}
      <div style={{ textAlign: 'center', padding: '48px 0 56px', position: 'relative' }}>
        <div style={{
          position: 'absolute', top: '-20px', left: '50%', transform: 'translateX(-50%)',
          width: '600px', height: '300px',
          background: 'radial-gradient(ellipse at center, rgba(139,92,246,0.12) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 16px', borderRadius: 99,
          background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.25)',
          fontSize: 12, fontWeight: 600, color: 'var(--purple-400)',
          marginBottom: 20, letterSpacing: '0.05em',
        }}>
          <span className="pulse-dot purple" /> MORPHEUS v1.0 · 5-Pillar Agentic System
        </div>

        <h1 style={{
          fontSize: 52, fontWeight: 900, letterSpacing: '-2px',
          background: 'linear-gradient(135deg, #fff 30%, var(--purple-300) 70%, var(--gold) 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          marginBottom: 16, lineHeight: 1.1,
        }}>
          Multi-Agent Orchestration<br />& Reasoning Platform
        </h1>
        <p style={{ fontSize: 17, color: 'var(--text-secondary)', maxWidth: 560, margin: '0 auto 36px', lineHeight: 1.7 }}>
          Enterprise workflow automation with an Architecture Court, Hallucination Firewall,
          and self-healing Temporal Reasoning Cortex.
        </p>
        <button className="btn btn-primary btn-lg" onClick={() => navigate('/court/new')}>
          ⬡ Convene Architecture Court
        </button>
      </div>

      {/* Pillar cards */}
      <div className="grid-3 section" style={{ marginBottom: 48 }}>
        {[
          { icon: '🏛', title: 'Architecture Court', desc: '4 AI agents debate every workflow node. Conflicts surface as red nodes on the canvas.', color: '#818cf8' },
          { icon: '🔥', title: 'Hallucination Firewall', desc: 'Schema-validates every API call. Catches hallucinated parameters before execution.', color: '#fca5a5' },
          { icon: '🧠', title: 'Temporal Reasoning Cortex', desc: 'Self-healing failure analysis. Causal chain reconstruction + automated patch proposals.', color: '#c4b5fd' },
          { icon: '⚡', title: 'Living Case Object', desc: 'Finite state machine with append-only audit trail. Full rollback via sequence numbers.', color: '#86efac' },
          { icon: '🎯', title: 'Adaptive Decisioning Gate', desc: 'Context-aware branching with 60s human override window. Every decision is audited.', color: '#fcd34d' },
          { icon: '🇮🇳', title: 'Sarvam AI Compliance', desc: 'Indian regulatory context: GST, RBI, TDS, DPDP Act. Built-in for Indian enterprise.', color: '#fb923c' },
        ].map((p, i) => (
          <div key={i} className="card glow-hover" style={{ padding: '20px 24px', cursor: 'default' }}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>{p.icon}</div>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6, color: p.color }}>{p.title}</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{p.desc}</div>
          </div>
        ))}
      </div>

      {/* Demo scenarios */}
      <div className="section">
        <div className="section-title">Quick Start — Demo Scenarios</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {DEMO_SCENARIOS.map((s, i) => (
            <button
              key={i}
              onClick={() => navigate('/court/new', { state: { objective: s } })}
              className="card glow-hover"
              style={{
                padding: '14px 20px', textAlign: 'left', cursor: 'pointer',
                border: '1px solid var(--border)', background: 'var(--bg-elevated)',
                display: 'flex', alignItems: 'center', gap: 12,
                color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14,
                transition: 'var(--transition)',
              }}
            >
              <span style={{ color: 'var(--purple-400)', fontSize: 18 }}>→</span>
              <span>{s}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Recent Cases */}
      <div className="section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Recent Cases</div>
          {loading && <div className="spinner" />}
        </div>

        {!loading && cases.length === 0 && (
          <div className="card" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No cases yet. Convene your first Architecture Court to get started.
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {cases.map((c) => (
            <div
              key={c.case_id}
              className="card glow-hover"
              style={{ padding: '16px 20px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16 }}
              onClick={() => navigate(`/cases/${c.case_id}`)}
            >
              <span style={{ fontSize: 20 }}>{STATUS_ICON[c.status] || '📋'}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.title}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {new Date(c.created_at).toLocaleString('en-IN')}
                </div>
              </div>
              <span className={`badge badge-${STATUS_COLOR[c.status] || 'pending'}`}>
                {c.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default Landing;
