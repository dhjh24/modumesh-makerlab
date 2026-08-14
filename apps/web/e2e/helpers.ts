import type { APIRequestContext, Page } from '@playwright/test';

const API = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

/**
 * Registers a throwaway user for e2e. Auth (GM-10) protects project/job/file
 * routes, so browser tests seed a real bearer token before navigating.
 */
export async function registerTestUser(
  request: APIRequestContext,
): Promise<{ token: string; email: string; password: string }> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@modumesh.test`;
  const password = 'e2e-password-123';
  const res = await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password, display_name: 'E2E Tester' },
  });
  if (!res.ok()) {
    throw new Error(`registerTestUser failed: ${res.status()} ${await res.text()}`);
  }
  const body = (await res.json()) as { access_token: string };
  return { token: body.access_token, email, password };
}

/** Injects the bearer token into localStorage before any page script runs. */
export function seedToken(page: Page, token: string): Promise<void> {
  return page.addInitScript(
    (t) => window.localStorage.setItem('modumesh_access_token', t),
    token,
  );
}

/** Headers for direct API calls from the test process (projects, jobs). */
export function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}
