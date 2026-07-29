import { expect, test } from '@playwright/test';

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
  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    await request.post(`${API}/api/v1/plugins/resync`);
  });

  test('home dashboard shows catalog and can create a project', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'ModuMesh MakerLab' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Generator catalog' })).toBeVisible();

    const name = `E2E Project ${Date.now()}`;
    await page.getByLabel('Name').fill(name);
    await page.getByRole('button', { name: 'Create project' }).click();
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+/);
    await expect(page.getByRole('heading', { name })).toBeVisible();
  });

  test('generator catalog renders schema form from plugin registry', async ({ page }) => {
    await page.goto('/generators');
    await expect(page.getByRole('heading', { name: 'Generator catalog' })).toBeVisible();

    // Prefer fixture-mesh if listed; otherwise first plugin.
    const mesh = page.getByRole('button', { name: /Fixture Mesh/i });
    if (await mesh.count()) {
      await mesh.first().click();
    } else {
      await page
        .getByRole('button', { name: /Fixture Echo/i })
        .first()
        .click();
    }

    await expect(page.getByText('Schema preview')).toBeVisible();
    // Schema-driven fields from registry (Nameplate is a real plugin in Phase 5).
    await expect(page.locator('.mm-schema-form')).toBeVisible();
  });

  test('editor submits fixture job and shows lifecycle + survives reload', async ({
    page,
    request,
  }) => {
    const create = await request.post(`${API}/api/v1/projects`, {
      data: { name: `Job lifecycle ${Date.now()}`, description: 'phase4 e2e' },
    });
    expect(create.ok()).toBeTruthy();
    const project = await create.json();

    await page.goto(`/projects/${project.id}?plugin=fixture-echo`);
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
    });
    const project = await create.json();
    await page.goto(`/projects/${project.id}`);

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
