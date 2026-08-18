import { expect, test } from '@playwright/test';
import { authHeaders, registerTestUser, seedToken } from './helpers';

const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

async function waitForApi(request: import('@playwright/test').APIRequestContext) {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await request.get(`${API}/health/live`);
      if (res.ok()) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error('API not reachable for e2e');
}

test.describe('Phase 4 core flows', () => {
  let token = '';

  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    await request.post(`${API}/api/v1/plugins/resync`);
    ({ token } = await registerTestUser(request));
  });

  test('create landing resolves an intent and opens the studio with the tool', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'What do you want to make?' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Parametric builder' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Text to 3D' })).toBeVisible();

    await page
      .getByRole('textbox', { name: 'What do you want to make?' })
      .fill('a storage box with compartments');
    await page.getByRole('button', { name: 'Make it' }).click();
    await expect(page).toHaveURL(/\/studio\/[0-9a-f-]+\?tool=openscad-template/);
    await expect(
      page.getByRole('heading', { name: /Box & Organizer Maker project/ }),
    ).toBeVisible();
  });

  test('explore page opens maker tool and creates a project from it', async ({ page }) => {
    await seedToken(page, token);
    await page.goto('/explore');
    await expect(page.getByRole('heading', { name: 'Explore maker tools' })).toBeVisible();
    // Maker-tool cards surface user-facing names (never plugin IDs).
    await expect(page.getByRole('link', { name: /Nameplate Maker/i })).toBeVisible({
      timeout: 30000,
    });

    // Open the Nameplate Maker tool detail and create a project from it.
    await page.getByRole('link', { name: /Nameplate Maker/i }).click();
    await expect(page).toHaveURL(/\/explore\/nameplate/);
    await page.getByRole('button', { name: /Create with Nameplate Maker/i }).click();

    await expect(page).toHaveURL(/\/studio\/[0-9a-f-]+\?tool=nameplate/);
    // Schema-driven fields from the plugin registry (not a hard-coded form).
    await expect(page.locator('.mm-schema-form')).toBeVisible();
  });

  test('editor submits fixture job and shows lifecycle + survives reload', async ({
    page,
    request,
  }) => {
    const create = await request.post(`${API}/api/v1/projects`, {
      data: { name: `Job lifecycle ${Date.now()}`, description: 'phase4 e2e' },
      headers: authHeaders(token),
    });
    expect(create.ok()).toBeTruthy();
    const project = await create.json();

    await seedToken(page, token);
    await page.goto(`/studio/${project.id}?tool=fixture-echo`);
    await expect(page.getByLabel('Generator')).toBeVisible();

    // Fill schema form
    const message = page.getByLabel(/^Message/);
    await message.fill('phase4 lifecycle');
    await page.getByRole('button', { name: 'Generate' }).click();

    const status = page.locator('.mm-editor__status');
    await expect(
      status.getByText('Queued', { exact: true }).or(status.getByText('Running', { exact: true })),
    ).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      status
        .getByText('Completed', { exact: true })
        .or(status.getByText('Failed', { exact: true })),
    ).toBeVisible({ timeout: 90_000 });

    // Version history should list the job
    await expect(page.getByText(/fixture-echo/i).first()).toBeVisible();

    const url = page.url();
    await page.reload();
    await expect(page).toHaveURL(url);
    await expect(page.getByRole('heading', { name: project.name })).toBeVisible();
    await expect(page.getByText(/fixture-echo/i).first()).toBeVisible();
  });

  test('STL and GLB fixtures render in the viewer', async ({ page, request }) => {
    const create = await request.post(`${API}/api/v1/projects`, {
      data: { name: `Viewer ${Date.now()}` },
      headers: authHeaders(token),
    });
    const project = await create.json();
    await seedToken(page, token);
    await page.goto(`/studio/${project.id}`);

    await page.getByRole('button', { name: 'Fixture STL', exact: true }).click();
    await expect(page.getByLabel(/model preview/i)).toBeVisible();
    await expect(page.getByText(/Dimensions:|Loading model/i)).toBeVisible();
    await expect(page.getByRole('button', { name: 'Wireframe' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Build plate' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Reset camera' })).toBeVisible();

    // Wait for dimensions (model loaded)
    await expect(page.getByText(/Dimensions:/i)).toBeVisible({ timeout: 30_000 });

    await page.getByRole('button', { name: 'Fixture GLB', exact: true }).click();
    await expect(page.getByText(/Dimensions:/i)).toBeVisible({ timeout: 30_000 });
  });
});
