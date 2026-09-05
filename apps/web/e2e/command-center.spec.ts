import { expect, test } from '@playwright/test';

test('loads the risk command center and exercises scenario controls', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible();
  await expect(page.getByText('Unauthorized agent-initiated transaction defense')).toBeVisible();
  await expect(page.getByText('TEST MODE — NO REAL MONEY')).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Scenario lens' })).toBeVisible();
  await expect(page.getByText('Within policy')).toBeVisible();

  await page.getByRole('button', { name: 'Behavioral anomaly' }).click();
  await expect(page.getByRole('heading', { name: 'Step-up verification' })).toBeVisible();
  await expect(page.getByText('New device · amount shift')).toBeVisible();

  await page.getByRole('button', { name: 'Agent limit violation' }).click();
  await expect(page.getByRole('heading', { name: 'Intervention required' })).toBeVisible();
  await expect(page.getByText('Daily budget exceeded')).toBeVisible();

  await page.getByRole('button', { name: 'Composite high risk' }).click();
  await expect(page.getByText('Velocity · novelty · amount')).toBeVisible();
});

test('navigates to control-plane views without losing shell navigation', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Policies' }).click();
  await expect(page.getByRole('heading', { name: 'Policies' })).toBeVisible();

  await page.getByRole('button', { name: 'Models' }).click();
  await expect(page.getByRole('heading', { name: 'Models' })).toBeVisible();

  await page.getByRole('button', { name: 'Audit' }).click();
  await expect(page.getByRole('heading', { name: 'Audit' })).toBeVisible();

  await page.getByRole('button', { name: 'System Health' }).click();
  await expect(page.getByRole('heading', { name: 'System Health' })).toBeVisible();
});
