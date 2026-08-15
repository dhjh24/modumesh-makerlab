import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { authHeaders, registerTestUser, seedToken } from './helpers';

test.describe('Phase 4 accessibility @a11y', () => {
  let token = '';

  test.beforeAll(async ({ request }) => {
    ({ token } = await registerTestUser(request));
  });

  test('home has no serious axe violations', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'ModuMesh MakerLab' })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const serious = results.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact || ''),
    );
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });

  test('generators page keyboard focus and labels', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/generators');
    await expect(page.getByRole('heading', { name: 'Generator Marketplace' })).toBeVisible();
    await expect(page.getByText(/\d+ generators?/)).toBeVisible({ timeout: 30000 });

    await page.keyboard.press('Tab');
    // Skip link or nav should be reachable
    const focused = page.locator(':focus');
    await expect(focused).toBeVisible();

    const fixture = page.locator('a[href^="/generators/fixture-"]').first();
    await expect(fixture).toBeVisible();
    await fixture.click();
    await page.getByRole('button', { name: /Use /i }).click();
    const form = page.locator('.mm-schema-form');
    await expect(form).toBeVisible();
    // Every visible input/select in the form should have an accessible name
    const controls = form.locator('input, select, textarea');
    const count = await controls.count();
    for (let i = 0; i < count; i++) {
      const el = controls.nth(i);
      const name = await el.evaluate((node) => {
        const input = node as HTMLInputElement;
        if (input.getAttribute('aria-label')) return input.getAttribute('aria-label');
        if (input.labels && input.labels.length) return input.labels[0].textContent;
        return input.id;
      });
      expect(name && String(name).trim().length > 0).toBeTruthy();
    }

    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const serious = results.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact || ''),
    );
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });

  test('editor announces status updates', async ({ page, request }) => {
    const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';
    const create = await request.post(`${API}/api/v1/projects`, {
      data: { name: `A11y ${Date.now()}` },
      headers: authHeaders(token),
    });
    const project = await create.json();
    await seedToken(page, token);
    await page.goto(`/projects/${project.id}?plugin=fixture-echo`);
    await expect(page.getByLabel('Generator')).toBeVisible();
    await expect(page.getByLabel('Job progress')).toBeVisible();
    await expect(page.locator('[aria-live="polite"]').first()).toBeVisible();

    // Reduced motion should not break viewer toolbar
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.getByRole('button', { name: 'Fixture STL', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Wireframe' })).toBeVisible();
  });
});
