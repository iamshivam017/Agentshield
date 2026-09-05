'use client';

import { useMemo, useState } from 'react';

const nav = [
  ['Overview', '01'], ['Risk Queue', '14'], ['Investigations', '06'], ['Agents', '12'],
  ['Policies', '08'], ['Models', '03'], ['Audit', '24'], ['System Health', '99'],
];

const scenarios = [
  { name: 'Safe purchase', decision: 'ALLOW', score: '0.08', detail: 'Known device · normal velocity' },
  { name: 'Behavioral anomaly', decision: 'VERIFY', score: '0.54', detail: 'New device · amount shift' },
  { name: 'Agent limit violation', decision: 'BLOCK', score: '0.22', detail: 'Daily budget exceeded' },
  { name: 'Composite high risk', decision: 'BLOCK', score: '0.87', detail: 'Velocity · novelty · amount' },
];

export default function Page() {
  const [active, setActive] = useState('Overview');
  const [scenario, setScenario] = useState(scenarios[0]);
  const [live, setLive] = useState(true);

  const headline = useMemo(() => {
    if (scenario.decision === 'BLOCK') return 'Intervention required';
    if (scenario.decision === 'VERIFY') return 'Step-up verification';
    return 'Within policy';
  }, [scenario]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark">A</div><div><strong>AgentShield</strong><span>Risk command center</span></div></div>
        <div className="env-chip"><span className="dot" /> TEST ENVIRONMENT</div>
        <nav aria-label="Primary navigation">
          {nav.map(([label, count]) => (
            <button key={label} className={`nav-item ${active === label ? 'active' : ''}`} onClick={() => setActive(label)}>
              <span>{label}</span><em>{count}</em>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot"><div className="health-row"><span className="dot" /> All systems nominal</div><div className="muted">Last sync · just now</div></div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div><span className="eyebrow">Risk operations</span><h1>{active}</h1></div>
          <div className="top-actions"><button className="quiet" onClick={() => setLive(v => !v)}><span className={live ? 'dot' : 'dot off'} /> Live mode</button><button className="primary">Run evaluation</button></div>
        </header>

        <div className="banner"><span className="pill">TRACK 02</span><div><strong>Unauthorized agent-initiated transaction defense</strong><p>ML predicts risk. Policy defines authority. AI explains evidence.</p></div><span className="test-label">TEST MODE — NO REAL MONEY</span></div>

        <section className="metrics-grid" aria-label="Risk posture">
          {[
            ['Risk posture', 'Elevated', '6.2% high-risk rate', 'accent'],
            ['Evaluations', '2,481', '+12.4% vs yesterday', ''],
            ['Verification', '184', '7.4% of evaluations', ''],
            ['Blocked', '67', '2.7% intervention rate', ''],
          ].map(([label, value, sub, cls]) => <article className={`metric-card ${cls}`} key={label}><span>{label}</span><strong>{value}</strong><small>{sub}</small></article>)}
        </section>

        <section className="grid-two">
          <article className="panel queue-panel">
            <div className="panel-head"><div><span className="eyebrow">Recent activity</span><h2>Risk queue</h2></div><button className="link-btn">View all</button></div>
            <div className="table-wrap"><table><thead><tr><th>Transaction</th><th>Agent</th><th>Risk</th><th>Decision</th><th>Time</th></tr></thead><tbody>
              {[
                ['TX-8F4A2', 'Shopping Agent', '0.87', 'BLOCK', '09:42'],
                ['TX-8F49C', 'Travel Agent', '0.54', 'VERIFY', '09:39'],
                ['TX-8F484', 'Finance Agent', '0.12', 'ALLOW', '09:37'],
                ['TX-8F47D', 'Shopping Agent', '0.31', 'VERIFY', '09:33'],
                ['TX-8F46B', 'Support Agent', '0.08', 'ALLOW', '09:30'],
              ].map(row => <tr key={row[0]}><td className="mono">{row[0]}</td><td>{row[1]}</td><td><div className="risk-score"><span style={{width: `${Number(row[2]) * 100}%`}} /><b>{row[2]}</b></div></td><td><span className={`decision ${row[3].toLowerCase()}`}>{row[3]}</span></td><td className="muted">{row[4]}</td></tr>)}
            </tbody></table></div>
          </article>

          <article className="panel scenario-panel">
            <div className="panel-head"><div><span className="eyebrow">Demo harness</span><h2>Decision simulator</h2></div><span className="live-badge">sandbox</span></div>
            <div className="scenario-tabs">{scenarios.map(s => <button key={s.name} onClick={() => setScenario(s)} className={scenario.name === s.name ? 'selected' : ''}>{s.name}</button>)}</div>
            <div className={`decision-card ${scenario.decision.toLowerCase()}`}><div><span className="eyebrow">Recommended response</span><h3>{headline}</h3><p>{scenario.detail}</p></div><strong>{scenario.decision}</strong></div>
            <div className="scenario-facts"><div><span>Risk score</span><b>{scenario.score}</b></div><div><span>Model</span><b>risk-v0.1</b></div><div><span>Policy</span><b>v12</b></div><div><span>Provider order</span><b>{scenario.decision === 'ALLOW' ? 'Created' : 'None'}</b></div></div>
            <button className="run-btn" onClick={() => setScenario({...scenario})}>Execute scenario</button>
          </article>
        </section>

        <section className="grid-three">
          <article className="panel mini-panel"><span className="eyebrow">Model health</span><div className="mini-value">99.98%</div><p>Serving availability · p95 74 ms</p><div className="sparkline"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div></article>
          <article className="panel mini-panel"><span className="eyebrow">Decision mix</span><div className="bars"><div><span>ALLOW</span><i style={{width:'78%'}} /></div><div><span>VERIFY</span><i style={{width:'15%'}} /></div><div><span>BLOCK</span><i style={{width:'7%'}} /></div></div></article>
          <article className="panel mini-panel"><span className="eyebrow">Control plane</span><div className="control-row"><span className="dot"/><b>Policy enforcement</b><span>Online</span></div><div className="control-row"><span className="dot"/><b>Audit stream</b><span>Online</span></div><div className="control-row"><span className="dot"/><b>Razorpay sandbox</b><span>Connected</span></div></article>
        </section>
      </section>
    </main>
  );
}
