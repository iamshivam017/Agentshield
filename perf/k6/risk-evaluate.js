import http from 'k6/http';
import { check, sleep } from 'k6';
import { randomUUID } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const baseUrl = __ENV.AGENTSHIELD_BASE_URL || 'http://127.0.0.1:8000';
const agentId = __ENV.AGENT_ID;
const merchantId = __ENV.MERCHANT_ID;
const agentApiKey = __ENV.AGENT_API_KEY || '';
const profile = (__ENV.K6_PROFILE || 'load').toLowerCase();

if (!agentId || !merchantId) {
  throw new Error('AGENT_ID and MERCHANT_ID are required');
}

const scenarios = {
  smoke: {
    smoke: {
      executor: 'constant-vus',
      vus: 2,
      duration: '15s',
    },
  },
  load: {
    load: {
      executor: 'ramping-vus',
      startVUs: 2,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '60s', target: 10 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  stress: {
    stress: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '30s', target: 25 },
        { duration: '60s', target: 50 },
        { duration: '60s', target: 75 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  soak: {
    soak: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '60s', target: 20 },
        { duration: '10m', target: 20 },
        { duration: '60s', target: 0 },
      ],
    },
  },
};

const thresholds = {
  smoke: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
  },
  load: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
  },
  stress: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<750', 'p(99)<1500'],
  },
  soak: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<750', 'p(99)<1500'],
  },
};

if (!Object.prototype.hasOwnProperty.call(scenarios, profile)) {
  throw new Error(`Unsupported K6_PROFILE: ${profile}. Use smoke, load, stress, or soak`);
}

export const options = {
  scenarios: scenarios[profile],
  thresholds: thresholds[profile],
  tags: { profile },
};

export default function () {
  const payload = JSON.stringify({
    agent_id: agentId,
    merchant_id: merchantId,
    amount: '125.00',
    currency: 'INR',
    category: 'SOFTWARE',
    device_id: 'perf-device',
    idempotency_key: `perf-${randomUUID()}`,
  });

  const response = http.post(`${baseUrl}/api/v1/risk/evaluate`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'X-Agent-ID': agentId,
      'X-Agent-API-Key': agentApiKey,
    },
    tags: { endpoint: 'risk_evaluate' },
  });

  check(response, {
    'risk evaluation returns success or policy decision': (res) => [200, 409].includes(res.status),
  });

  sleep(0.1);
}
