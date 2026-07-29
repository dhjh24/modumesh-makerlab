/**
 * Browser API client with session token support (Phase 6).
 */

export class ApiError extends Error {
  status: number;
  body: string;
  correlationId?: string;

  constructor(message: string, status: number, body: string, correlationId?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
    this.correlationId = correlationId;
  }
}

const TOKEN_KEY = 'modumesh_token';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

function apiBase(): string {
  const pub = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  if (typeof window === 'undefined') {
    return process.env.API_INTERNAL_URL || pub || 'http://localhost:8000';
  }
  if (pub) return pub;
  return '';
}

export function fileDownloadUrl(fileId: string): string {
  const base = apiBase();
  const token = getStoredToken();
  const url = `${base}/api/v1/files/${fileId}/download`;
  // Prefer authenticated fetch via signed URL endpoint from callers; this
  // path works when the browser sends Authorization from apiFetch downloads.
  return token ? url : url;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = apiBase();
  const url = `${base}${path.startsWith('/') ? path : `/${path}`}`;
  const token = getStoredToken();
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers || {}),
      },
    });
  } catch (err) {
    const offline = err instanceof TypeError;
    throw new ApiError(
      offline ? 'Unable to reach the MakerLab API. Check your connection.' : 'Request failed.',
      0,
      err instanceof Error ? err.message : String(err),
    );
  }

  const correlationId = response.headers.get('X-Correlation-ID') || undefined;
  const text = await response.text();
  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') {
      const onLogin = window.location.pathname.startsWith('/login');
      if (!onLogin) {
        setStoredToken(null);
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.href = `/login?next=${next}`;
      }
    }
    let friendly = `Request failed (${response.status}).`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === 'string') friendly = parsed.detail;
      else if (parsed.detail) friendly = JSON.stringify(parsed.detail);
    } catch {
      if (text) friendly = text.slice(0, 240);
    }
    throw new ApiError(friendly, response.status, text, correlationId);
  }

  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export type AuthUser = {
  id: string;
  username?: string | null;
  display_name: string;
  role: string;
  is_active: boolean;
};

export const api = {
  login: async (username: string, password: string) => {
    const data = await apiFetch<{
      access_token: string;
      user: AuthUser;
      expires_at: string;
    }>(`/api/v1/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    setStoredToken(data.access_token);
    return data;
  },
  logout: async () => {
    try {
      await apiFetch(`/api/v1/auth/logout`, { method: 'POST' });
    } finally {
      setStoredToken(null);
    }
  },
  me: () => apiFetch<AuthUser>(`/api/v1/auth/me`),
  adminStatus: () =>
    apiFetch<{
      timestamp: string;
      services: Record<string, unknown>;
      queue_depth: number;
      active_jobs: number;
      failed_jobs: number;
      project_count: number;
      storage_bytes: number;
      file_count: number;
      plugins: Array<Record<string, unknown>>;
      retention_days: number;
      version: string;
    }>(`/api/v1/admin/status`),
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
  deleteProject: (id: string) =>
    apiFetch<{ project_id: string; files_removed: number }>(`/api/v1/projects/${id}`, {
      method: 'DELETE',
    }),
  listPlugins: (enabledOnly = true) =>
    apiFetch<import('@modumesh/shared-types').PluginList>(
      `/api/v1/plugins?enabled_only=${enabledOnly ? 'true' : 'false'}`,
    ),
  getPlugin: (pluginId: string) =>
    apiFetch<import('@modumesh/shared-types').PluginRecord>(`/api/v1/plugins/${pluginId}`),
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
  signedDownloadUrl: (fileId: string) =>
    apiFetch<{ url: string; expires_at: string; expires_in_seconds: number }>(
      `/api/v1/files/${fileId}/signed-url`,
      { method: 'POST' },
    ),
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
