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

/** Bytes + metadata for a protected file fetched with the bearer token. */
export interface FileBlob {
  blob: Blob;
  filename: string;
  contentType: string;
}

/** Parses `Content-Disposition` (plain `filename="…"` and RFC 5987 `filename*=UTF-8''…`). */
function filenameFromContentDisposition(value: string | null): string | null {
  if (!value) return null;
  const encoded = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(value);
  if (encoded) {
    try {
      const decoded = decodeURIComponent(encoded[1].trim());
      if (decoded) return decoded;
    } catch {
      // Malformed percent-encoding — fall through to the plain form.
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(value);
  return plain && plain[1].trim() ? plain[1].trim() : null;
}

/** Maps a MIME type to a sensible file extension for fallback names. */
function extensionForContentType(contentType: string): string {
  const ct = contentType.toLowerCase();
  if (ct.includes('stl')) return 'stl';
  if (ct.includes('gltf-binary') || ct.includes('glb')) return 'glb';
  if (ct.includes('gltf')) return 'gltf';
  if (ct.includes('json')) return 'json';
  if (ct.includes('text/plain')) return 'txt';
  return '';
}

/**
 * Fetch a file's bytes from the protected download endpoint. A bare URL
 * (<img>/anchor/window.open) cannot carry the `Authorization` header, so
 * downloads/previews must fetch with the bearer token and use a blob: object
 * URL instead. Mirrors apiFetch's error handling: a 401 clears the stored
 * token and sets `ApiError.unauthorized` so callers can redirect to /login.
 */
export async function fetchFileBlob(fileId: string, fallbackName = 'model'): Promise<FileBlob> {
  const base = apiBase();
  const url = `${base}/api/v1/files/${fileId}/download`;
  const token = getToken();
  let response: Response;
  try {
    response = await fetch(url, {
      headers: {
        Accept: '*/*',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
  if (!response.ok) {
    const text = await response.text();
    let friendly = `Request failed (${response.status}).`;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === 'string') friendly = parsed.detail;
      else if (parsed.detail) friendly = JSON.stringify(parsed.detail);
    } catch {
      if (text) friendly = text.slice(0, 240);
    }
    // The download endpoint is always protected: a 401 means the stored
    // token is invalid/expired — drop it so the next navigation lands on
    // /login (same semantics as apiFetch on non-auth routes).
    const unauthorized = response.status === 401;
    if (unauthorized) clearToken();
    throw new ApiError(friendly, response.status, text, correlationId, unauthorized);
  }

  const blob = await response.blob();
  const contentType = response.headers.get('content-type') || blob.type || '';
  const dispositionName = filenameFromContentDisposition(
    response.headers.get('content-disposition'),
  );
  const ext = extensionForContentType(contentType);
  const filename =
    dispositionName || (ext ? `model-${fileId}.${ext}` : `${fallbackName}-${fileId}`);
  return { blob, filename, contentType };
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

// ── Job result workspace (GM-11) ───────────────────────────────────────
// Response shapes mirror apps/api routers (jobs/files, shop, compare) and
// the plugin output manifests (design.json, slicing-report.json).

export interface PriceBreakdown {
  materials: number;
  labor: number;
  machine_time: number;
  shipping_handling: number;
}

/** GET /api/v1/projects/{pid}/jobs/{jid}/pricing */
export interface JobPricing {
  job_id: string;
  project_id: string;
  currency: string;
  price_breakdown: PriceBreakdown;
  markup_pct: number;
  markup_amount: number;
  total: number;
  includes: string[];
  disclaimer: string;
}

/** pricing nested in the shop-handoff response (zeroed when no estimate). */
export interface ShopHandoffPricing {
  currency: string;
  total: number;
  price_breakdown?: PriceBreakdown;
  markup_pct?: number;
  markup_amount?: number;
  includes?: string[];
  disclaimer?: string;
}

/** Vendure-compatible payload built by apps/api/app/services/pricing.py. */
export interface ShopHandoffPayload {
  schema_version: string;
  platform: string;
  project_id: string;
  project_name: string;
  artifact_ids: string[];
  preview_id: string | null;
  design_id: string | null;
  options: {
    generator: string;
    artwork_type: string;
    dimensions: {
      width_mm: unknown;
      height_mm: unknown;
      depth_mm: unknown;
    };
    material: string;
  };
  price: {
    currency: string;
    total: number;
    breakdown: Record<string, unknown>;
  };
  manufacturing_notes: string[];
  generated_at: string;
}

/** POST /api/v1/projects/{pid}/jobs/{jid}/shop-handoff */
export interface ShopHandoffResponse {
  handoff: ShopHandoffPayload;
  pricing: ShopHandoffPricing;
  note: string;
}

/** POST /api/v1/compare body. */
export interface CompareCreateRequest {
  project_id: string;
  input_payload: Record<string, unknown>;
  generators: string[];
}

export interface CompareJobRef {
  generator: string;
  job_id: string;
}

/** POST /api/v1/compare response (201). */
export interface CompareCreateResponse {
  project_id: string;
  comparison: { generator_count: number };
  jobs: CompareJobRef[];
  note: string;
}

/** One row of GET /api/v1/compare/{project_id} results (`id` is a job id). */
export interface CompareResultRow {
  id: string;
  job_type: string;
  status: import('@modumesh/shared-types').JobStatus;
  progress_pct: number;
  error_message: string | null;
}

export interface CompareResultsResponse {
  project_id: string;
  results: CompareResultRow[];
  total: number;
}

// ── Job output manifests (stored files, parsed client-side) ────────────

/** design.json produced by generators (e.g. logo-lightbox). */
export interface DesignManifest {
  schema_version?: string;
  generator?: string;
  generator_version?: string;
  parameters?: Record<string, unknown>;
  outputs?: Record<string, { size_bytes?: number }>;
  generation_duration_s?: number;
  warnings?: string[];
  material_estimate?: MaterialEstimate;
  generated_at?: string;
}

export interface MaterialEstimate {
  material?: string;
  total_volume_cm3?: number;
  estimated_mass_g?: number;
  filament_cost_usd?: number;
  led_kit_cost_usd?: number;
  total_estimated_cost_usd?: number;
  estimated_print_time_min?: number;
  disclaimer?: string;
}

/** slicing-report.json produced by the slicer plugin. */
export interface SlicingReport {
  schema_version?: string;
  plugin_id?: string;
  plugin_version?: string;
  source?: { filename?: string };
  slice?: {
    printer_profile?: string;
    nozzle_mm?: number | string;
    layer_height_mm?: number | string;
    infill_pct?: number | string;
    supports?: boolean | string;
    material?: string;
  };
  estimated?: {
    print_time_estimate?: string;
    filament_length_mm?: string;
    filament_weight_g?: string;
    note?: string;
  };
  return_code?: number;
  generated_at?: string;
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
  getJobPricing: (projectId: string, jobId: string) =>
    apiFetch<JobPricing>(`/api/v1/projects/${projectId}/jobs/${jobId}/pricing`),
  createShopHandoff: (projectId: string, jobId: string) =>
    apiFetch<ShopHandoffResponse>(
      `/api/v1/projects/${projectId}/jobs/${jobId}/shop-handoff`,
      { method: 'POST' },
    ),
  createComparison: (body: CompareCreateRequest) =>
    apiFetch<CompareCreateResponse>('/api/v1/compare', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  getComparison: (projectId: string, generators?: string[]) =>
    apiFetch<CompareResultsResponse>(
      `/api/v1/compare/${projectId}${
        generators && generators.length > 0
          ? `?generators=${encodeURIComponent(generators.join(','))}`
          : ''
      }`,
    ),
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
