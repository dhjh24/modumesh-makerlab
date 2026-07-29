import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { API, authHeaders, uiLogin } from './auth';

test.describe('Phase 4 accessibility @a11y', () => {
  test('home has no serious axe violations', async ({ page }) => {
    await uiLogin(page);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'ModuMesh MakerLab' })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const serious = results.violations.filter((v) =>
      ['serious', 'critical'].includes(v.impact || ''),
    );
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
  });

  test('generators page keyboard focus and labels', async ({ page }) => {
    await uiLogin(page);
    await page.goto('/generators');
    await expect(page.getByRole('heading', { name: 'Generator catalog' })).toBeVisible();

    await page.keyboard.press('Tab');
    const focused = page.locator(':focus');
    await expect(focused).toBeVisible();

    const mesh = page.getByRole('button', { name: /Fixture/i }).first();
    await mesh.click();
    const form = page.locator('.mm-schema-form');
    await expect(form).toBeVisible();
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
    const headers = await authHeaders(request);
    const create = await request.post(`${API}/api/v1/projects`, {
      headers,
      data: { name: `A11y ${Date.now()}` },
    });
    const project = await create.json();
    await uiLogin(page);
    await page.goto(`/projects/${project.id}?plugin=fixture-echo`);
    await expect(page.getByLabel('Generator')).toBeVisible();
    await expect(page.getByLabel('Job progress')).toBeVisible();
    await expect(page.locator('[aria-live="polite"]').first()).toBeVisible();

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.getByRole('button', { name: 'Fixture STL', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Wireframe' })).toBeVisible();
  });
});
