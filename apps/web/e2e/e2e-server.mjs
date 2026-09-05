import http from 'node:http';
import { spawn } from 'node:child_process';

const transactionId = '11111111-1111-4111-8111-111111111111';
const queueItem = {
  transaction_id: transactionId,
  agent_id: '22222222-2222-4222-8222-222222222222',
  agent_name: 'Procurement Agent',
  merchant_id: '33333333-3333-4333-8333-333333333333',
  merchant_name: 'Trusted Software Co',
  amount: '425.00',
  currency: 'INR',
  status: 'EVALUATED',
  risk_score: '0.18',
  risk_band: 'LOW',
  decision: 'ALLOW',
  model_version: 'baseline-logistic-v1',
  policy_version: 2,
  reason_codes: ['MODEL_ARTIFACT_VERIFIED'],
  occurred_at: '2026-09-05T10:30:00Z',
};
const detail = {
  transaction: queueItem,
  features: {
    version: 'v1',
    values: {
      amount: 425,
      new_device: 0,
      new_merchant: 0,
      agent_count_1h_prior: 1,
      agent_tx_count_prior: 14,
      agent_amount_mean_prior: 390,
    },
    computed_at: '2026-09-05T10:29:59Z',
  },
  prediction: {
    model_version: 'baseline-logistic-v1',
    score: '0.18',
    risk_band: 'LOW',
    signals: { signals: ['MODEL_ARTIFACT_VERIFIED'] },
    created_at: '2026-09-05T10:30:01Z',
  },
  policy_evaluation: {
    policy_version: 2,
    result: 'ALLOW',
    violations: [],
    evaluated_at: '2026-09-05T10:30:01Z',
  },
  decision_record: {
    decision: 'ALLOW',
    risk_score: '0.18',
    risk_band: 'LOW',
    model_version: 'baseline-logistic-v1',
    policy_version: 2,
    reason_codes: ['MODEL_ARTIFACT_VERIFIED'],
  },
  reviews: [],
  audit_events: [
    {
      id: '44444444-4444-4444-8444-444444444444',
      transaction_id: transactionId,
      event_type: 'RISK_DECISION_CREATED',
      actor_type: 'AGENT',
      actor_id: queueItem.agent_id,
      payload: { decision: 'ALLOW' },
      occurred_at: '2026-09-05T10:30:01Z',
    },
  ],
  investigation: null,
  payment_order: null,
  provider_payment: null,
};

const json = (response, body, status = 200) => {
  response.writeHead(status, { 'Content-Type': 'application/json' });
  response.end(JSON.stringify(body));
};

const apiServer = http.createServer((request, response) => {
  const url = new URL(request.url ?? '/', 'http://127.0.0.1:8000');
  const path = url.pathname;
  if (request.method === 'GET' && path === '/health/ready') return json(response, { status: 'ready' });
  if (request.method === 'GET' && path === '/api/v1/risk/metrics') {
    return json(response, { evaluations: 42, high_risk: 3, verification: 7, blocked: 4, allowed: 31 });
  }
  if (request.method === 'GET' && path === '/api/v1/risk/transactions') {
    return json(response, { items: [queueItem], total: 1, limit: 8, offset: 0 });
  }
  if (request.method === 'GET' && path === `/api/v1/risk/transactions/${transactionId}`) return json(response, detail);
  if (request.method === 'POST' && path === `/api/v1/risk/transactions/${transactionId}/review`) {
    return json(response, {
      id: '55555555-5555-4555-8555-555555555555',
      transaction_id: transactionId,
      reviewer_id: 'dashboard-operator',
      outcome: 'APPROVE',
      note: null,
      created_at: '2026-09-05T10:31:00Z',
    }, 201);
  }
  if (request.method === 'GET' && (path === '/api/v1/policies' || path === '/api/v1/models' || path === '/api/v1/audit')) {
    return json(response, []);
  }
  return json(response, { error: { code: 'E2E_NOT_FOUND', message: 'Mock endpoint not configured' } }, 404);
});

let nextServer;
const shutdown = (code = 0) => {
  apiServer.close(() => {
    if (nextServer && !nextServer.killed) nextServer.kill('SIGTERM');
    process.exit(code);
  });
};

apiServer.listen(8000, '127.0.0.1', () => {
  nextServer = spawn('node', ['.next/standalone/server.js'], {
    stdio: 'inherit',
    env: { ...process.env, HOSTNAME: '127.0.0.1', PORT: '3000' },
  });
  nextServer.on('exit', (code) => shutdown(code ?? 1));
});

process.on('SIGINT', () => shutdown());
process.on('SIGTERM', () => shutdown());
