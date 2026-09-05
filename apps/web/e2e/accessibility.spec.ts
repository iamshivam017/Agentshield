import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('command center has no critical accessibility violations', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible();

  const results = await new AxeBuilder({ page: page as never }).analyze();
  const critical = results.violations.filter((violation) => violation.impact === 'critical');
  expect(critical, JSON.stringify(critical, null, 2)).toEqual([]);
});

test('navigation controls are keyboard accessible', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible();

  const riskQueue = page.getByRole('button', { name: 'Risk Queue' });
  await riskQueue.focus();
  await expect(riskQueue).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { level: 1, name: 'Risk Queue' })).toBeVisible();
});
