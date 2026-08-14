/**
 * Browser API client. Uses same-origin `/api/v1` rewrites by default so the
 * heavyweight 3D stack is never required for API traffic and CORS is optional.
 */

import { clearToken, getToken } from './auth';
import type { AuthUser } from './auth';

export type { AuthUser };

/** Login/register success payload (matches backend `TokenResponse`). */
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
}

export class ApiError extends Error {
  status: number;
  body: string;
  correlationId?: string;
  /** True when a protected endpoint rejected an invalid/expired token (401). */
  unauthorized: boolean;

  constructor(
    message: string,
    status: number,
    body: string,
    correlationId?: string,
    unauthorized = false,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
    this.correlationId = correlationId;
    this.unauthorized = unauthorized;
  }
}

function apiBase(): string {
  const pub = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  if (typeof window === 'undefined') {
    return process.env.API_INTERNAL_URL || pub || 'http://api:8000';
  }
  // Browser: explicit public API URL (Compose), otherwise same-origin rewrites.
  if (pub) return pub;
  return '';
}

export function fileDownloadUrl(fileId: string): string {
  const base = apiBase();
  return `${base}/api/v1/files/${fileId}/download`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = apiBase();
  const url = `${base}${path.startsWith('/') ? path : `/${path}`}`;
  const token = getToken();
  // Auth endpoints validate credentials themselves — their 401s must not
  // wipe a token or be treated as "session expired".
  const isAuthRequest = path.startsWith('/api/v1/auth/');
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers || {}),
      },
    });
  } catch (err) {
    const offline = err instanceof TypeError;
    const reason = offline
      ? `Unable to reach the MakerLab API. Tried: ${url}`
      : `Request failed: ${url}`;
    throw new ApiError(reason, 0, err instanceof Error ? err.message : String(err));
  }

  const correlationId = response.headers.get('X-Correlation-ID') || undefined;
  const text = await response.text();
  if (!response.ok) {
    let friendly = `Request failed (${response.status}).`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === 'string') friendly = parsed.detail;
      else if (parsed.detail) friendly = JSON.stringify(parsed.detail);
    } catch {
      if (text) friendly = text.slice(0, 240);
    }
    // A 401 on a protected (non-auth) endpoint means the stored token is
    // invalid or expired: drop it so the next navigation lands on /login.
    // Callers decide whether/how to redirect (apiFetch stays a pure client).
    const unauthorized = response.status === 401 && !isAuthRequest;
    if (unauthorized) clearToken();
    throw new ApiError(friendly, response.status, text, correlationId, unauthorized);
  }

  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export const api = {
  register: (email: string, password: string, displayName?: string) =>
    apiFetch<TokenResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        ...(displayName ? { display_name: displayName } : {}),
      }),
    }),
  login: (email: string, password: string) =>
    apiFetch<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => apiFetch<void>('/api/v1/auth/logout', { method: 'POST' }),
  me: () => apiFetch<AuthUser>('/api/v1/auth/me'),
  listProjects: (limit = 20) =>
    apiFetch<{ items: import('@modumesh/shared-types').Project[]; total: number }>(
      `/api/v1/projects?limit=${limit}`,
    ),
  getProject: (id: string) =>
    apiFetch<import('@modumesh/shared-types').Project>(`/api/v1/projects/${id}`),
  createProject: (body: { name: string; description?: string }) =>
    apiFetch<import('@modumesh/shared-types').Project>(`/api/v1/projects`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateProject: (id: string, body: { name?: string; description?: string }) =>
    apiFetch<import('@modumesh/shared-types').Project>(`/api/v1/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  listPlugins: (enabledOnly = true) =>
    apiFetch<import('@modumesh/shared-types').PluginList>(
      `/api/v1/plugins?enabled_only=${enabledOnly ? 'true' : 'false'}`,
    ),
  getPlugin: (pluginId: string) =>
    apiFetch<import('@modumesh/shared-types').PluginRecord>(`/api/v1/plugins/${pluginId}`),
  listCatalog: (params?: {
    category?: string;
    engine?: string;
    maturity?: string;
    capability?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.category) q.set('category', params.category);
    if (params?.engine) q.set('engine', params.engine);
    if (params?.maturity) q.set('maturity', params.maturity);
    if (params?.capability) q.set('capability', params.capability);
    if (params?.search) q.set('search', params.search);
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    return apiFetch<{
      items: import('@modumesh/shared-types').CatalogItem[];
      total: number;
      categories?: string[];
    }>(`/api/v1/catalog${q.toString() ? `?${q.toString()}` : ''}`);
  },
  getCatalogItem: (pluginId: string) =>
    apiFetch<import('@modumesh/shared-types').CatalogItem>(`/api/v1/catalog/${pluginId}`),
  listCatalogCategories: () =>
    apiFetch<{ categories: string[]; total: number }>('/api/v1/catalog/categories'),
  getFullHealth: () =>
    apiFetch<{
      status: string;
      service: string;
      version: string;
      timestamp: string;
      checks: Record<
        string,
        { status: string; latency_ms?: number; error?: string; [key: string]: unknown }
      >;
    }>(`/health/full`),
  listProjectJobs: (projectId: string, limit = 50) =>
    apiFetch<import('@modumesh/shared-types').JobList>(
      `/api/v1/projects/${projectId}/jobs?limit=${limit}`,
    ),
  createJob: (
    projectId: string,
    body: import('@modumesh/shared-types').JobCreate,
    idempotencyKey?: string,
  ) =>
    apiFetch<import('@modumesh/shared-types').Job>(`/api/v1/projects/${projectId}/jobs`, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : undefined,
    }),
  getJob: (jobId: string) =>
    apiFetch<import('@modumesh/shared-types').Job>(`/api/v1/jobs/${jobId}`),
  getJobProgress: (jobId: string) =>
    apiFetch<import('@modumesh/shared-types').JobProgress>(`/api/v1/jobs/${jobId}/progress`),
  cancelJob: (jobId: string) =>
    apiFetch<import('@modumesh/shared-types').Job>(`/api/v1/jobs/${jobId}/cancel`, {
      method: 'POST',
    }),
  retryJob: (jobId: string) =>
    apiFetch<import('@modumesh/shared-types').Job>(`/api/v1/jobs/${jobId}/retry`, {
      method: 'POST',
    }),
  listJobFiles: (jobId: string) =>
    apiFetch<import('@modumesh/shared-types').FileList>(`/api/v1/jobs/${jobId}/files`),
  listProjectFiles: (projectId: string) =>
    apiFetch<import('@modumesh/shared-types').FileList>(`/api/v1/projects/${projectId}/files`),
  listRecentJobs: async (limitProjects = 8, perProject = 5) => {
    const projects = await api.listProjects(limitProjects);
    const batches = await Promise.all(
      projects.items.map((p) =>
        api.listProjectJobs(p.id, perProject).catch(() => ({ items: [], total: 0 })),
      ),
    );
    const jobs = batches.flatMap((b) => b.items);
    jobs.sort((a, b) => b.created_at.localeCompare(a.created_at));
    return jobs.slice(0, 20);
  },
};
