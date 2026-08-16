import { expect, test } from '@playwright/test';

/**
 * Legacy-route redirects (IA W2.1). Old URLs must never 404, but the
 * canonical accessibility target is /explore — these are tested separately
 * so a11y coverage hits the real page, not a redirect hop.
 */
test.describe('Legacy route redirects', () => {
  test('/generators redirects permanently to /explore', async ({ page }) => {
    const response = await page.goto('/generators');
    // 301 permanent redirect to the canonical Maker Tools destination.
    expect(response?.status()).toBe(301);
    await expect(page).toHaveURL(/\/explore$/);
    await expect(page.getByRole('heading')).toBeVisible();
  });

  test('/generators/[tool] redirects to /explore/[tool]', async ({ page }) => {
    await page.goto('/generators/nameplate');
    await expect(page).toHaveURL(/\/explore\/nameplate$/);
  });

  test('/health redirects to /admin/health', async ({ page }) => {
    const response = await page.goto('/health');
    expect(response?.status()).toBe(301);
    await expect(page).toHaveURL(/\/admin\/health$/);
  });

  test('/projects/[id] redirects to /studio/[id]', async ({ page }) => {
    const response = await page.goto('/projects/00000000-0000-0000-0000-000000000000');
    expect(response?.status()).toBe(301);
    await expect(page).toHaveURL(/\/studio\/00000000-0000-0000-0000-000000000000/);
  });

  test('/projects/[id]/compare redirects to /studio/[id]/compare', async ({ page }) => {
    const response = await page.goto(
      '/projects/00000000-0000-0000-0000-000000000000/compare',
    );
    expect(response?.status()).toBe(301);
    await expect(page).toHaveURL(
      /\/studio\/00000000-0000-0000-0000-000000000000\/compare/,
    );
  });
});
