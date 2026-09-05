import { expect, test } from '@playwright/test';

test('control-plane requests are authenticated by the server-side proxy', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Policies' }).click();
  await expect(page.getByText('Policy versions', { exact: true })).toBeVisible();

  const result = await page.evaluate(async () => {
    const response = await fetch('/api/v1/policies');
    return { status: response.status, body: await response.json() };
  });

  expect(result.status).toBe(200);
  expect(result.body).toEqual([]);
});

test('operator credentials are not exposed to browser JavaScript', async ({ page }) => {
  await page.goto('/');

  const leaked = await page.evaluate(() => {
    const sources = [document.documentElement.outerHTML, document.body.innerHTML].join('\n');
    return sources.includes('e2e-secret') || sources.includes('AGENTSHIELD_OPERATOR_API_KEY');
  });

  expect(leaked).toBe(false);
});
