import { expect, test } from '@playwright/test';

test('loads the risk command center and exercises scenario controls', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible();
  await expect(page.getByText('Unauthorized agent-initiated transaction defense')).toBeVisible();
  await expect(page.getByText('TEST MODE — NO REAL MONEY')).toBeVisible();

  await expect(page.getByRole('heading', { level: 2, name: 'Scenario lens' })).toBeVisible();
  await expect(page.getByRole('heading', { level: 3, name: 'Within policy' })).toBeVisible();

  await page.getByRole('button', { name: 'Behavioral anomaly' }).click();
  await expect(page.getByRole('heading', { level: 3, name: 'Step-up verification' })).toBeVisible();
  await expect(page.getByText('New device · amount shift')).toBeVisible();

  await page.getByRole('button', { name: 'Agent limit violation' }).click();
  await expect(page.getByRole('heading', { level: 3, name: 'Intervention required' })).toBeVisible();
  await expect(page.getByText('Daily budget exceeded')).toBeVisible();

  await page.getByRole('button', { name: 'Composite high risk' }).click();
  await expect(page.getByText('Velocity · novelty · amount')).toBeVisible();
});

test('navigates to control-plane views without losing shell navigation', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Policies' }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Policy versions' })).toBeVisible();

  await page.getByRole('button', { name: 'Models' }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Model registry' })).toBeVisible();

  await page.getByRole('button', { name: 'Audit' }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'Audit stream' })).toBeVisible();

  await page.getByRole('button', { name: 'System Health' }).click();
  await expect(page.getByRole('heading', { level: 2, name: 'System health' })).toBeVisible();
});
