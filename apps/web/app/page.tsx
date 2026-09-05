'use client';

import { useEffect, useMemo, useState } from 'react';
import ControlPlane from './control-plane';
import {
  createReview,
  getRiskMetrics,
  getRiskQueue,
  getTransaction,
  type RiskMetrics,
  type RiskQueueItem,
  type TransactionDetail,
} from '../lib/api';
import './investigation.css';

const nav = [
  ['Overview', ''],
  ['Risk Queue', ''],
  ['Investigations', ''],
  ['Agents', ''],
  ['Policies', ''],
  ['Models', ''],
  ['Audit', ''],
  ['System Health', ''],
] as const;

const controlPlaneSections = new Set(['Policies', 'Models', 'Audit', 'System Health']);

const scenarios = [
  { name: 'Safe purchase', decision: 'ALLOW', score: 'low', detail: 'Known device · normal velocity' },
  { name: 'Behavioral anomaly', decision: 'VERIFY', score: 'medium', detail: 'New device · amount shift' },
  { name: 'Agent limit violation', decision: 'BLOCK', score: 'policy', detail: 'Daily budget exceeded' },
  { name: 'Composite high risk', decision: 'BLOCK', score: 'high', detail: 'Velocity · novelty · amount' },
];

const emptyMetrics: RiskMetrics = { evaluations: 0, high_risk: 0, verification: 0, blocked: 0, allowed: 0 };

function formatAmount(amount: string, currency: string) {
  return `${currency} ${Number(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date(value));
}

export default function Page() {
  const [active, setActive] = useState<(typeof nav)[number][0]>('Overview');
  const [metrics, setMetrics] = useState<RiskMetrics>(emptyMetrics);
  const [queue, setQueue] = useState<RiskQueueItem[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<TransactionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenario, setScenario] = useState(scenarios[0]);
  const [reviewing, setReviewing] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricData, queueData] = await Promise.all([getRiskMetrics(), getRiskQueue({ limit: 8 })]);
      setMetrics(metricData);
      setQueue(queueData.items);
      setTotal(queueData.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load risk operations data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const headline = useMemo(() => {
    if (scenario.decision === 'BLOCK') return 'Intervention required';
    if (scenario.decision === 'VERIFY') return 'Step-up verification';
    return 'Within policy';
  }, [scenario]);

  const openInvestigation = async (item: RiskQueueItem) => {
    setError(null);
    try {
      setSelected(await getTransaction(item.transaction_id));
      setActive('Investigations');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load investigation');
    }
  };

  const submitReview = async (outcome: 'APPROVE' | 'REJECT' | 'ESCALATE') => {
    if (!selected) return;
    setReviewing(true);
    setError(null);
    try {
      await createReview(selected.transaction.transaction_id, { reviewer_id: 'dashboard-operator', outcome });
      setSelected(await getTransaction(selected.transaction.transaction_id));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to record review');
    } finally {
      setReviewing(false);
    }
  };

  const isControlPlane = controlPlaneSections.has(active);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">A</div><div><strong>AgentShield</strong><span>Risk command center</span></div></div>
        <div className="env-chip"><span className="dot" /> TEST ENVIRONMENT</div>
        <nav aria-label="Primary navigation">
          {nav.map(([label]) => (
            <button key={label} className={`nav-item ${active === label ? 'active' : ''}`} onClick={() => setActive(label)}>
              <span>{label}</span>{label === 'Risk Queue' && <em>{total}</em>}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot"><div className="health-row"><span className="dot" /> API connected</div><div className="muted">Live data · auto-loaded</div></div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div><span className="eyebrow">Risk operations</span><h1>{active}</h1></div>
          <div className="top-actions"><button className="quiet" onClick={() => void refresh()} disabled={loading}><span className="dot" /> {loading ? 'Refreshing' : 'Refresh'}</button><button className="primary" onClick={() => setActive('Risk Queue')}>Open queue</button></div>
        </header>

        <div className="banner"><span className="pill">TRACK 02</span><div><strong>Unauthorized agent-initiated transaction defense</strong><p>ML predicts risk. Policy defines authority. AI explains evidence.</p></div><span className="test-label">TEST MODE — NO REAL MONEY</span></div>

        {error && <div className="error-banner" role="alert"><strong>Data unavailable.</strong> {error}</div>}

        {isControlPlane ? (
          <ControlPlane section={active as 'Policies' | 'Models' | 'Audit' | 'System Health'} />
        ) : active === 'Investigations' && selected ? (
          <InvestigationView detail={selected} busy={reviewing} onReview={submitReview} />
        ) : (
          <>
            <section className="metrics-grid" aria-label="Risk posture">
              <article className="metric-card accent"><span>Risk posture</span><strong>{metrics.evaluations === 0 ? 'Standby' : `${((metrics.high_risk / metrics.evaluations) * 100).toFixed(1)}%`}</strong><small>high-risk share</small></article>
              <article className="metric-card"><span>Evaluations</span><strong>{metrics.evaluations.toLocaleString()}</strong><small>recorded decisions</small></article>
              <article className="metric-card"><span>Verification</span><strong>{metrics.verification.toLocaleString()}</strong><small>{metrics.evaluations ? `${((metrics.verification / metrics.evaluations) * 100).toFixed(1)}% of evaluations` : 'No evaluations yet'}</small></article>
              <article className="metric-card"><span>Blocked</span><strong>{metrics.blocked.toLocaleString()}</strong><small>{metrics.evaluations ? `${((metrics.blocked / metrics.evaluations) * 100).toFixed(1)}% intervention rate` : 'No interventions yet'}</small></article>
            </section>

            <section className="grid-two">
              <article className="panel queue-panel">
                <div className="panel-head"><div><span className="eyebrow">Recent activity</span><h2>Risk queue</h2></div><button className="link-btn" onClick={() => setActive('Risk Queue')}>View all</button></div>
                <div className="table-wrap">
                  <table><thead><tr><th>Transaction</th><th>Agent</th><th>Risk</th><th>Decision</th><th>Time</th></tr></thead>
                    <tbody>{queue.map(row => <tr key={row.transaction_id} tabIndex={0} onClick={() => void openInvestigation(row)} onKeyDown={event => { if (event.key === 'Enter') void openInvestigation(row); }}>
                      <td className="mono">{row.transaction_id.slice(0, 8).toUpperCase()}</td><td><div>{row.agent_name}</div><small className="muted">{formatAmount(row.amount, row.currency)} · {row.merchant_name}</small></td>
                      <td><div className="risk-score"><span style={{ width: `${Number(row.risk_score) * 100}%` }} /><b>{Number(row.risk_score).toFixed(2)}</b></div></td>
                      <td><span className={`decision ${row.decision.toLowerCase()}`}>{row.decision}</span></td><td className="muted">{formatTime(row.occurred_at)}</td>
                    </tr>)}{!loading && queue.length === 0 && <tr><td colSpan={5} className="empty-state">No risk evaluations recorded yet.</td></tr>}</tbody>
                  </table>
                </div>
              </article>

              <article className="panel scenario-panel">
                <div className="panel-head"><div><span className="eyebrow">Decision semantics</span><h2>Scenario lens</h2></div><span className="live-badge">defense-only</span></div>
                <div className="scenario-tabs">{scenarios.map(s => <button key={s.name} onClick={() => setScenario(s)} className={scenario.name === s.name ? 'selected' : ''}>{s.name}</button>)}</div>
                <div className={`decision-card ${scenario.decision.toLowerCase()}`}><div><span className="eyebrow">Expected response</span><h3>{headline}</h3><p>{scenario.detail}</p></div><strong>{scenario.decision}</strong></div>
                <div className="scenario-facts"><div><span>Risk</span><b>{scenario.score}</b></div><div><span>Authority</span><b>Policy</b></div><div><span>Execution</span><b>{scenario.decision === 'ALLOW' ? 'Eligible' : 'Held'}</b></div><div><span>Provider</span><b>{scenario.decision === 'ALLOW' ? 'Test Mode' : 'None'}</b></div></div>
                <p className="muted scenario-note">This lens documents expected control-plane behavior; production decisions come only from the API.</p>
              </article>
            </section>

            <section className="grid-three">
              <article className="panel mini-panel"><span className="eyebrow">Decision mix</span><div className="mini-value">{metrics.evaluations ? `${Math.round((metrics.allowed / metrics.evaluations) * 100)}%` : '—'}</div><p>ALLOW share of evaluated requests</p><div className="sparkline"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div></article>
              <article className="panel mini-panel"><span className="eyebrow">Verification pressure</span><div className="mini-value">{metrics.verification.toLocaleString()}</div><p>Requests currently requiring a step-up path</p></article>
              <article className="panel mini-panel"><span className="eyebrow">Control plane</span><div className="control-row"><span className="dot"/><b>Policy enforcement</b><span>Online</span></div><div className="control-row"><span className="dot"/><b>Risk queue</b><span>{total ? 'Populated' : 'Empty'}</span></div><div className="control-row"><span className="dot"/><b>Razorpay sandbox</b><span>Test-only</span></div></article>
            </section>
          </>
        )}
      </section>
    </main>
  );
}

function InvestigationView({ detail, busy, onReview }: { detail: TransactionDetail; busy: boolean; onReview: (outcome: 'APPROVE' | 'REJECT' | 'ESCALATE') => void }) {
  const item = detail.transaction;
  const signalList = detail.prediction?.signals?.signals ?? item.reason_codes;

  return (
    <div className="investigation-layout">
      <section className="panel investigation-hero">
        <div><span className="eyebrow">Investigation workspace</span><h2>{item.transaction_id}</h2><p>{item.agent_name} → {item.merchant_name} · {formatAmount(item.amount, item.currency)}</p></div>
        <div className="investigation-decision"><span className={`decision ${item.decision.toLowerCase()}`}>{item.decision}</span><strong>{Number(item.risk_score).toFixed(2)}</strong><small>{item.risk_band} risk</small></div>
      </section>
      <div className="investigation-grid">
        <section className="panel"><div className="panel-head"><div><span className="eyebrow">Evidence</span><h2>Decision inputs</h2></div></div><div className="evidence-grid">
          <EvidenceCard title="System" value={`${item.agent_name} · ${item.status}`} /><EvidenceCard title="Merchant" value={item.merchant_name} /><EvidenceCard title="Model" value={`${item.model_version} · ${item.risk_band}`} /><EvidenceCard title="Policy" value={`v${item.policy_version} · ${detail.policy_evaluation?.result ?? item.decision}`} />
        </div><div className="signal-list">{signalList.map(signal => <span key={signal} className="evidence-chip">{signal}</span>)}</div></section>
        <section className="panel"><div className="panel-head"><div><span className="eyebrow">Policy evaluation</span><h2>Authority check</h2></div></div><div className="kv-list"><div><span>Decision</span><b>{detail.policy_evaluation?.result ?? item.decision}</b></div><div><span>Violations</span><b>{detail.policy_evaluation?.violations.length ? detail.policy_evaluation.violations.join(', ') : 'None recorded'}</b></div><div><span>Payment order</span><b>{detail.payment_order?.provider_order_id ?? 'Not created'}</b></div></div></section>
      </div>
      <section className="panel review-panel"><div><span className="eyebrow">Human oversight</span><h2>Review decision</h2><p className="muted">Record an analyst outcome; the review is appended to the audit stream.</p></div><div className="review-actions"><button className="quiet" disabled={busy} onClick={() => onReview('ESCALATE')}>Escalate</button><button className="quiet" disabled={busy} onClick={() => onReview('REJECT')}>Reject</button><button className="primary" disabled={busy} onClick={() => onReview('APPROVE')}>Approve</button></div></section>
      <section className="panel"><div className="panel-head"><div><span className="eyebrow">Audit trail</span><h2>Immutable events</h2></div></div><div className="timeline">{detail.audit_events.map(event => <div className="timeline-row" key={event.id}><span className="dot"/><div><b>{event.event_type}</b><small>{event.actor_type}{event.actor_id ? ` · ${event.actor_id}` : ''} · {new Date(event.occurred_at).toLocaleString()}</small></div></div>)}</div></section>
    </div>
  );
}

function EvidenceCard({ title, value }: { title: string; value: string }) {
  return <div className="evidence-card"><span>{title}</span><strong>{value}</strong><small>TRUSTED INPUT</small></div>;
}
