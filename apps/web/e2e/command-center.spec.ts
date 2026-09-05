import { expect, test } from '@playwright/test';

test('loads the risk command center and exercises scenario controls', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible();
  await expect(page.getByText('Unauthorized agent-initiated transaction defense')).toBeVisible();
  await expect(page.getByText('TEST MODE — NO REAL MONEY')).toBeVisible();

  await expect(page.getByText('Scenario lens', { exact: true })).toBeVisible();
  await expect(page.getByText('Within policy', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Behavioral anomaly' }).click();
  await expect(page.getByText('Step-up verification', { exact: true })).toBeVisible();
  await expect(page.getByText('New device · amount shift', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Agent limit violation' }).click();
  await expect(page.getByText('Intervention required', { exact: true })).toBeVisible();
  await expect(page.getByText('Daily budget exceeded', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Composite high risk' }).click();
  await expect(page.getByText('Velocity · novelty · amount', { exact: true })).toBeVisible();
});

test('navigates to control-plane views without losing shell navigation', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Policies' }).click();
  await expect(page.getByText('Policy versions', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Models' }).click();
  await expect(page.getByText('Model registry', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Audit' }).click();
  await expect(page.getByText('Audit stream', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'System Health' }).click();
  await expect(page.getByText('System health', { exact: true })).toBeVisible();
});
