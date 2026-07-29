import { APIRequestContext, expect, Page } from '@playwright/test';

const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';
const ADMIN_USER = process.env.API_BOOTSTRAP_ADMIN_USERNAME || 'admin';
const ADMIN_PASS = process.env.API_BOOTSTRAP_ADMIN_PASSWORD || 'change_me_admin';

export async function waitForApi(request: APIRequestContext) {
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

export async function apiLogin(request: APIRequestContext): Promise<string> {
  const res = await request.post(`${API}/api/v1/auth/login`, {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  return body.access_token as string;
}

export async function authHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  const token = await apiLogin(request);
  return { Authorization: `Bearer ${token}` };
}

export async function uiLogin(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(ADMIN_USER);
  await page.getByLabel('Password').fill(ADMIN_PASS);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

export { API, ADMIN_USER, ADMIN_PASS };
