import { expect, test } from '@playwright/test';
import { registerTestUser, seedToken } from './helpers';

const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

/**
 * Create landing (W2.3): intent → maker-tool resolution and creation modes.
 * The landing must resolve free-text descriptions to maker tools (never
 * plugin IDs), offer a small visual choice for ambiguous intents, and gate
 * the AI/upload modes behind "Coming soon".
 */
test.describe('Create landing (W2.3)', () => {
  let token = '';

  test.beforeAll(async ({ request }) => {
    await request.post(`${API}/api/v1/plugins/resync`);
    ({ token } = await registerTestUser(request));
  });

  test('typed intent with a clear match goes straight to the studio', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'What do you want to make?' })).toBeVisible();
    await page
      .getByRole('textbox', { name: 'What do you want to make?' })
      .fill('a nameplate for my workshop');
    await page.getByRole('button', { name: 'Make it', exact: true }).click();
    await expect(page).toHaveURL(/\/studio\/[0-9a-f-]+\?tool=nameplate/);
    await expect(page.getByRole('heading', { name: /Nameplate Maker project/ })).toBeVisible();
  });

  test('starter chips resolve through the same intent path', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await page.getByRole('button', { name: 'Light box', exact: true }).click();
    await expect(page).toHaveURL(/\/studio\/[0-9a-f-]+\?tool=logo-lightbox/);
    await expect(page.getByRole('heading', { name: /Light Box Maker project/ })).toBeVisible();
  });

  test('ambiguous intent offers a small visual choice of tools', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await page.getByRole('textbox', { name: 'What do you want to make?' }).fill('qr sign');
    await page.getByRole('button', { name: 'Make it', exact: true }).click();

    const result = page.locator('section[aria-labelledby="intent-result"]');
    await expect(result.getByRole('heading', { name: 'A few tools fit that' })).toBeVisible();
    await expect(result.getByRole('heading', { name: 'QR Sign Maker' })).toBeVisible();
    await expect(result.getByRole('heading', { name: 'Nameplate Maker' })).toBeVisible();

    await result.getByRole('button', { name: 'Make it' }).first().click();
    await expect(page).toHaveURL(/\/studio\/[0-9a-f-]+\?tool=(nameplate|qr-code-sign)/);
  });

  test('unmatched intent falls back to starter tools and Explore', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await page.getByRole('textbox', { name: 'What do you want to make?' }).fill('a phone stand');
    await page.getByRole('button', { name: 'Make it', exact: true }).click();

    const result = page.locator('section[aria-labelledby="intent-result"]');
    await expect(result.getByRole('heading', { name: 'Pick a maker tool to start' })).toBeVisible();
    await expect(result.getByRole('heading', { name: 'Nameplate Maker' })).toBeVisible();
    await expect(result.getByRole('link', { name: /Browse all maker tools/ })).toBeVisible();
  });

  test('mode cards route to Explore and My Models; AI and upload modes are gated', async ({
    page,
  }) => {
    await seedToken(page, token);
    await page.goto('/');
    await expect(page.getByText('Coming soon')).toHaveCount(3);
    await expect(page.locator('[aria-disabled="true"]')).toHaveCount(3);

    await page.getByRole('link', { name: 'Parametric builder' }).click();
    await expect(page).toHaveURL(/\/explore$/);
    await page.goBack();

    await page.getByRole('link', { name: 'Remix something' }).click();
    await expect(page).toHaveURL(/\/models$/);
  });

  test('classics row links to maker tool details', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Nameplate Maker' })).toBeVisible({
      timeout: 30_000,
    });
    await page.getByRole('link', { name: 'Nameplate Maker' }).click();
    await expect(page).toHaveURL(/\/explore\/nameplate$/);
  });
});
