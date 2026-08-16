import { expect, test } from '@playwright/test';
import { authHeaders, registerTestUser, seedToken } from './helpers';

/**
 * Dev-copy regression gate (W2.2, locked).
 *
 * Banned developer-facing strings must never appear in user-visible text on
 * normal screens. Each page has an explicit allowance list for strings that
 * are scheduled to be removed by a later wave (they must NOT be added to
 * silently — they're tracked). Anything outside the allowances fails.
 *
 * Allowance bookkeeping:
 * - `/`          → W2.3 (Create landing) removes the remaining catalog copy
 * - `/studio/*`  → W2.5 (Studio re-skin) removes generator/fixture language
 * - `/explore`   → must be ZERO (this wave)
 * - `/models`    → must be ZERO
 */
const BANNED = [
  'plugin',
  'Plugin',
  'generator',
  'Generator',
  'marketplace',
  'Marketplace',
  'sdk',
  'SDK',
  'engine',
  'Engine',
  'maturity',
  'experimental',
  'Experimental',
  'deprecated',
  'Deprecated',
  'license',
  'License',
  'registry',
  'Registry',
  'resync',
  'fixture',
  'Fixture',
  'content-type',
  'KiB',
  'payload',
  'Payload',
  'immutable version',
  'correlation',
  'v1.0.0',
];

/** Pages where some banned strings remain by design (wave-tracked). */
const ALLOWED: Record<string, string[]> = {
  '/': [
    // W2.3 Create landing rebuilds this page; ALL current dev copy is tracked
    // until then: catalog section, plugin-id rows (fixture-echo · v1.0.0),
    // empty-state registry copy, "queue a job" lead.
    'generator',
    'Generator',
    'plugin',
    'Plugin',
    'fixture',
    'Fixture',
    'resync',
    'registry',
    'v1.0.0',
    'schema',
    'queue',
  ],
  '/studio/[id]': [
    // W2.5 Studio re-skin removes these; tracked until then.
    'Generator',
    'generator',
    'Fixture',
    'fixture',
    'immutable version',
    'v1.0.0',
  ],
};

const SCREENS: Array<{ name: string; path: string; needsAuth: boolean }> = [
  { name: 'create', path: '/', needsAuth: true },
  { name: 'explore', path: '/explore', needsAuth: false },
  { name: 'models', path: '/models', needsAuth: true },
  { name: 'studio', path: '/studio/00000000-0000-0000-0000-000000000000', needsAuth: true },
];

test.describe('dev-copy regression gate @devcopy', () => {
  let token = '';
  let projectId = '';

  test.beforeAll(async ({ request }) => {
    ({ token } = await registerTestUser(request));
    const create = await request.post(
      `${process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000'}/api/v1/projects`,
      { data: { name: 'DevCopy gate' }, headers: authHeaders(token) },
    );
    if (create.ok()) {
      const project = (await create.json()) as { id: string };
      projectId = project.id;
    }
  });

  for (const screen of SCREENS) {
    test(`${screen.name} (${screen.path}) has no dev-facing strings`, async ({ page }) => {
      await seedToken(page, token);
      const path =
        screen.path === '/studio/00000000-0000-0000-0000-000000000000' && projectId
          ? `/studio/${projectId}`
          : screen.path;
      // Allowance lookup key: normalized (studio real id → [id] template).
      const allowKey =
        screen.name === 'studio' && path.startsWith('/studio/') ? '/studio/[id]' : path;
      await page.goto(path);
      // Give client-rendered pages a beat to settle.
      await page.waitForLoadState('networkidle').catch(() => undefined);
      await page.waitForTimeout(1200);

      // Sample the visible text: body innerText minus our own banned tokens.
      const text = (await page.evaluate(() => document.body?.innerText ?? '')) as string;
      const allowances = ALLOWED[allowKey] ?? [];
      const violations = BANNED.filter(
        (banned) => text.includes(banned) && !allowances.includes(banned),
      );
      expect(
        violations,
        `Banned dev strings on ${path}:\n${violations.join('\n')}\n\nVisible text (first 600 chars):\n${text.slice(0, 600)}`,
      ).toEqual([]);
    });
  }
});
