import { expect, test } from '@playwright/test';

/**
 * Legacy-route redirects (IA W2.1). Old URLs must never 404, but the
 * canonical accessibility target is /explore — these are tested separately
 * so a11y coverage hits the real page, not a redirect hop.
 */
test.describe('Legacy route redirects', () => {
  test('/generators redirects permanently to /explore', async ({ page }) => {
    // maxRedirects 0 → the 301 itself is returned (page.goto would follow it).
    const res = await page.request.get('/generators', { maxRedirects: 0 });
    expect(res.status()).toBe(301);
    expect(res.headers().location).toBe('/explore');
    // And following it lands on the canonical page.
    await page.goto('/generators');
    await expect(page).toHaveURL(/\/explore$/);
    await expect(page.getByRole('heading', { name: 'Explore maker tools' })).toBeVisible();
  });

  test('/generators/[tool] redirects to /explore/[tool]', async ({ page }) => {
    const res = await page.request.get('/generators/nameplate', { maxRedirects: 0 });
    expect(res.status()).toBe(301);
    expect(res.headers().location).toBe('/explore/nameplate');
    await page.goto('/generators/nameplate');
    await expect(page).toHaveURL(/\/explore\/nameplate$/);
  });

  test('/health redirects to /admin/health', async ({ page }) => {
    const res = await page.request.get('/health', { maxRedirects: 0 });
    expect(res.status()).toBe(301);
    expect(res.headers().location).toBe('/admin/health');
  });

  test('/projects/[id] redirects to /studio/[id]', async ({ page }) => {
    const id = '00000000-0000-0000-0000-000000000000';
    const res = await page.request.get(`/projects/${id}`, { maxRedirects: 0 });
    expect(res.status()).toBe(301);
    expect(res.headers().location).toBe(`/studio/${id}`);
  });

  test('/projects/[id]/compare redirects to /studio/[id]/compare', async ({ page }) => {
    const id = '00000000-0000-0000-0000-000000000000';
    const res = await page.request.get(`/projects/${id}/compare`, { maxRedirects: 0 });
    expect(res.status()).toBe(301);
    expect(res.headers().location).toBe(`/studio/${id}/compare`);
  });
});
