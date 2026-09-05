import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

// @axe-core/playwright can resolve a nested playwright-core copy whose Page
// type is structurally compatible at runtime but not identical to the test
// runner's Page type. Keep the compatibility cast isolated to this adapter.
function createAxeBuilder(page: Parameters<typeof AxeBuilder>[0]['page']) {
  return new AxeBuilder({ page: page as never });
}

test('command center has no critical accessibility violations', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible();

  const results = await createAxeBuilder(page).analyze();
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
