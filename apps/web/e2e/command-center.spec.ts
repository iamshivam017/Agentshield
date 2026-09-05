import { expect, test, type Page } from '@playwright/test';

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

const metrics = {
  evaluations: 42,
  high_risk: 3,
  verification: 7,
  blocked: 4,
  allowed: 31,
};

async function installApiFixture(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;

    if (pathname.endsWith('/risk/metrics')) return route.fulfill({ json: metrics });
    if (pathname.endsWith('/risk/transactions')) {
      return route.fulfill({ json: { items: [queueItem], total: 1, limit: 8, offset: 0 } });
    }
    if (pathname.endsWith(`/risk/transactions/${transactionId}/review`)) {
      return route.fulfill({
        status: 201,
        json: {
          id: '55555555-5555-4555-8555-555555555555',
          transaction_id: transactionId,
          reviewer_id: 'dashboard-operator',
          outcome: 'APPROVE',
          note: null,
          created_at: '2026-09-05T10:31:00Z',
        },
      });
    }
    if (pathname.endsWith(`/risk/transactions/${transactionId}`)) return route.fulfill({ json: detail });
    if (pathname.endsWith('/policies')) return route.fulfill({ json: [] });
    if (pathname.endsWith('/models')) return route.fulfill({ json: [] });
    if (pathname.endsWith('/audit')) return route.fulfill({ json: [] });

    await route.continue();
  });

  await page.route('**/health/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/health/ready')) return route.fulfill({ json: { status: 'ready' } });
    await route.continue();
  });
}

test('loads the risk command center and completes an investigation review', async ({ page }) => {
  await installApiFixture(page);
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible();
  await expect(page.getByText('42', { exact: true })).toBeVisible();
  await expect(page.getByText('Procurement Agent')).toBeVisible();
  await expect(page.getByRole('table').getByText('ALLOW', { exact: true })).toBeVisible();

  await page.getByText(transactionId.slice(0, 8).toUpperCase(), { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Investigations' })).toBeVisible();
  await expect(page.getByText('Point-in-time inputs')).toBeVisible();
  await expect(page.getByText('Agent history')).toBeVisible();

  await page.getByRole('button', { name: 'Approve' }).click();
  await expect(page.getByText('Immutable events')).toBeVisible();
});

test('navigates to control-plane views without losing shell navigation', async ({ page }) => {
  await installApiFixture(page);
  await page.goto('/');

  await page.getByRole('button', { name: 'Policies' }).click();
  await expect(page.getByRole('heading', { name: 'Policy versions' })).toBeVisible();

  await page.getByRole('button', { name: 'Models' }).click();
  await expect(page.getByRole('heading', { name: 'Model registry' })).toBeVisible();
});
