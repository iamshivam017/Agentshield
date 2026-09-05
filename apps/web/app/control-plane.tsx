'use client';

import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { getAudit, getHealth, getModels, getPolicies, type AuditItem, type HealthResponse, type ModelItem, type PolicyItem } from '../lib/api';

type Props = { section: 'Policies' | 'Models' | 'Audit' | 'System Health' };

function Panel({ title, eyebrow, children }: { title: string; eyebrow: string; children: ReactNode }) {
  return <section className="panel"><div className="panel-head"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div></div>{children}</section>;
}

export default function ControlPlane({ section }: Props) {
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [models, setModels] = useState<ModelItem[]>([]);
  const [audit, setAudit] = useState<AuditItem[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      const load = async () => {
        try {
          if (section === 'Policies') setPolicies(await getPolicies());
          if (section === 'Models') setModels(await getModels());
          if (section === 'Audit') setAudit(await getAudit(100));
          if (section === 'System Health') setHealth(await getHealth());
        } catch (err) {
          if (active) setError(err instanceof Error ? err.message : 'Unable to load control-plane data');
        } finally {
          if (active) setLoading(false);
        }
      };
      void load();
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [section]);

  if (loading) return <div className="panel loading-panel">Loading {section.toLowerCase()}…</div>;
  if (error) return <div className="error-banner" role="alert">{error}</div>;

  if (section === 'Policies') return <Panel title="Policy versions" eyebrow="Authority control"><div className="control-list">{policies.length ? policies.map(policy => <div className="control-item" key={policy.id}><div><strong>Agent {policy.agent_id.slice(0, 8).toUpperCase()}</strong><small>Version {policy.version} · {policy.is_active ? 'ACTIVE' : 'inactive'}</small></div><code>{JSON.stringify(policy.rules)}</code></div>) : <p className="empty-state">No policies are registered.</p>}</div></Panel>;

  if (section === 'Models') return <Panel title="Model registry" eyebrow="Measured risk models"><div className="control-list">{models.length ? models.map(model => <div className="control-item" key={model.version}><div><strong>{model.version}</strong><small>{model.status} · {new Date(model.created_at).toLocaleString()}</small></div><code title={model.artifact_sha256}>{model.artifact_sha256.slice(0, 16)}…</code></div>) : <p className="empty-state">No model registry records.</p>}</div></Panel>;

  if (section === 'Audit') return <Panel title="Audit stream" eyebrow="Decision integrity"><div className="timeline">{audit.length ? audit.map(event => <div className="timeline-row" key={event.id}><span className="dot"/><div><b>{event.event_type}</b><small>{event.actor_type}{event.transaction_id ? ` · tx ${event.transaction_id.slice(0, 8)}` : ''} · {new Date(event.occurred_at).toLocaleString()}</small></div></div>) : <p className="empty-state">No audit events recorded.</p>}</div></Panel>;

  return <Panel title="System health" eyebrow="Operational readiness"><div className="health-detail"><div className={`health-state ${health?.status === 'ready' ? 'healthy' : 'degraded'}`}><span className="dot"/><strong>{health?.status?.toUpperCase() ?? 'UNKNOWN'}</strong></div><p>Risk service readiness reflects critical serving dependencies. {health?.reason ? `Reason: ${health.reason}.` : 'No degradation reason reported.'}</p><div className="health-grid"><div><span>Database</span><b>Required for risk persistence</b></div><div><span>Risk model</span><b>{health?.status === 'ready' ? 'Serving' : 'Unavailable'}</b></div><div><span>Payments</span><b>Razorpay Test Mode boundary</b></div><div><span>AI investigations</span><b>Non-authoritative</b></div></div></div></Panel>;
}
