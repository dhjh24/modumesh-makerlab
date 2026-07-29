import { expect, test } from '@playwright/test';
import { API, authHeaders, uiLogin, waitForApi } from './auth';

const DEFAULT_INPUT = {
  text: 'MAKERLAB',
  font: 'DejaVuSans',
  width_mm: 80,
  height_mm: 30,
  base_thickness_mm: 3,
  text_depth_mm: 1.2,
  mode: 'raised',
  corner_radius_mm: 2,
  alignment: 'center',
  hole_count: 2,
  hole_diameter_mm: 3.2,
  edge_margin_mm: 8,
};

async function waitJob(
  request: import('@playwright/test').APIRequestContext,
  jobId: string,
  headers: Record<string, string>,
  timeoutMs = 180_000,
) {
  const deadline = Date.now() + timeoutMs;
  let last: { status?: string; error_message?: string } = {};
  while (Date.now() < deadline) {
    const res = await request.get(`${API}/api/v1/jobs/${jobId}/progress`, { headers });
    last = await res.json();
    if (last.status === 'completed' || last.status === 'failed' || last.status === 'cancelled') {
      return last;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  return last;
}

test.describe('Phase 5 Nameplate flow', () => {
  test.beforeAll(async ({ request }) => {
    await waitForApi(request);
    const headers = await authHeaders(request);
    await request.post(`${API}/api/v1/plugins/resync`, { headers });
  });

  test('catalog lists Nameplate with schema-driven form', async ({ page }) => {
    await uiLogin(page);
    await page.goto('/generators');
    await expect(page.getByRole('heading', { name: 'Generator catalog' })).toBeVisible();
    await page
      .getByRole('button', { name: /Nameplate/i })
      .first()
      .click();
    await expect(page.getByText('Schema preview')).toBeVisible();
    await expect(page.locator('.mm-schema-form')).toBeVisible();
    await expect(page.getByRole('textbox', { name: 'Text' })).toBeVisible();
    await expect(page.getByText(/mm/i).first()).toBeVisible();
  });

  test('create project, generate Nameplate, preview GLB, download STL', async ({
    page,
    request,
  }) => {
    const headers = await authHeaders(request);
    const create = await request.post(`${API}/api/v1/projects`, {
      headers,
      data: { name: `Nameplate E2E ${Date.now()}`, description: 'phase5' },
    });
    expect(create.ok()).toBeTruthy();
    const project = await create.json();

    const jobRes = await request.post(`${API}/api/v1/projects/${project.id}/jobs`, {
      headers,
      data: {
        job_type: 'nameplate',
        input_payload: DEFAULT_INPUT,
        timeout_seconds: 180,
      },
    });
    expect(jobRes.ok()).toBeTruthy();
    const job = await jobRes.json();
    const progress = await waitJob(request, job.id, headers);
    expect(progress.status).toBe('completed');

    await uiLogin(page);
    await page.goto(`/projects/${project.id}?plugin=nameplate&job=${job.id}`);
    await expect(page.getByRole('heading', { name: project.name })).toBeVisible();
    await expect(page.getByText(/nameplate/i).first()).toBeVisible();

    const glbBtn = page.getByRole('button', { name: /model\.glb/i });
    if (await glbBtn.count()) {
      await glbBtn.first().click();
    }
    await expect(page.getByLabel(/model preview/i)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Dimensions:/i)).toBeVisible({ timeout: 60_000 });

    const files = await request.get(`${API}/api/v1/jobs/${job.id}/files`, { headers });
    const fileList = await files.json();
    const stl = fileList.items.find((f: { filename: string }) => f.filename === 'model.stl');
    expect(stl).toBeTruthy();
    const dl = await request.get(`${API}/api/v1/files/${stl.id}/download`, { headers });
    expect(dl.ok()).toBeTruthy();
    const body = await dl.body();
    expect(body.byteLength).toBeGreaterThan(1000);

    await page.reload();
    await expect(page.getByRole('heading', { name: project.name })).toBeVisible();
    await expect(page.getByText(/Completed/i).first()).toBeVisible();
  });
});
