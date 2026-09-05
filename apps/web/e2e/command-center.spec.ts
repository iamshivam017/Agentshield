import { expect, test } from '@playwright/test';

const transactionId = '11111111-1111-4111-8111-111111111111';

test('loads the risk command center and completes an investigation review', async ({ page }) => {
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
  await page.goto('/');

  await page.getByRole('button', { name: 'Policies' }).click();
  await expect(page.getByRole('heading', { name: 'Policy versions' })).toBeVisible();

  await page.getByRole('button', { name: 'Models' }).click();
  await expect(page.getByRole('heading', { name: 'Model registry' })).toBeVisible();
});
