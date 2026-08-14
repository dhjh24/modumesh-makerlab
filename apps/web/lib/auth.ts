/**
 * Client-side bearer-token persistence for the MakerLab API (GM-10).
 *
 * The token is stored in localStorage under a single key and attached to
 * every API request by `apiFetch` (see lib/api.ts). All accessors guard
 * `typeof window` so this module is safe to import during SSR.
 */

const TOKEN_KEY = 'modumesh_access_token';
const AUTH_USER_KEY = 'modumesh_auth_user';

/** Authenticated user profile (matches backend `UserOut`). */
export interface AuthUser {
  id: string;
  email?: string | null;
  display_name: string;
  is_admin: boolean;
  created_at: string;
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(raw: string | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (raw) window.localStorage.setItem(TOKEN_KEY, raw);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable (private mode / quota) — degrade gracefully.
  }
}

export function clearToken(): void {
  setToken(null);
  clearAuthUser();
}

/** Cached copy of the last successful `/auth/me` response. */
export function getAuthUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(AUTH_USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function setAuthUser(user: AuthUser | null): void {
  if (typeof window === 'undefined') return;
  try {
    if (user) window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    else window.localStorage.removeItem(AUTH_USER_KEY);
  } catch {
    // Ignore — the cache is best-effort.
  }
}

export function clearAuthUser(): void {
  setAuthUser(null);
}
