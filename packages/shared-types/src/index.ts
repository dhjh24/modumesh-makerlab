/** Shared types across ModuMesh MakerLab services.
 *
 * API wire format uses snake_case (FastAPI / Pydantic). Frontend code should
 * prefer these types when talking to the API.
 */

// ── Projects ───────────────────────────────────────────────────────────
export type ProjectStatus = 'active' | 'archived';

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description?: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
}

export interface ProjectList {
  items: Project[];
  total: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

// ── Jobs ───────────────────────────────────────────────────────────────
export type JobStatus =
  | 'created'
  | 'queued'
  | 'running'
  | 'validating'
  | 'uploading'
  | 'completed'
  | 'failed'
  | 'cancelled';

export const ACTIVE_JOB_STATUSES: JobStatus[] = [
  'created',
  'queued',
  'running',
  'validating',
  'uploading',
];

export const TERMINAL_JOB_STATUSES: JobStatus[] = ['completed', 'failed', 'cancelled'];

export function isTerminalJobStatus(status: JobStatus | string): boolean {
  return (TERMINAL_JOB_STATUSES as string[]).includes(status);
}

export interface Job {
  id: string;
  project_id: string;
  parent_job_id?: string | null;
  job_type: string;
  status: JobStatus;
  input_payload: Record<string, unknown>;
  plugin_version?: string | null;
  progress_pct: number;
  progress_message?: string | null;
  error_message?: string | null;
  idempotency_key?: string | null;
  attempt_number: number;
  worker_id?: string | null;
  timeout_seconds: number;
  cancel_requested: boolean;
  created_at: string;
  updated_at: string;
  queued_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface JobList {
  items: Job[];
  total: number;
}

export interface JobCreate {
  job_type: string;
  input_payload?: Record<string, unknown>;
  timeout_seconds?: number;
  plugin_version?: string;
}

export interface JobProgress {
  id: string;
  status: JobStatus;
  progress_pct: number;
  progress_message?: string | null;
  error_message?: string | null;
  cancel_requested: boolean;
  updated_at: string;
}

// ── Files ──────────────────────────────────────────────────────────────
export interface FileObject {
  id: string;
  project_id: string;
  job_id?: string | null;
  object_key: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface FileList {
  items: FileObject[];
  total: number;
}

// ── Plugins ────────────────────────────────────────────────────────────
export interface PluginOutputDecl {
  name: string;
  mediaType: string;
  required?: boolean;
}

export interface PluginRecord {
  id: string;
  plugin_id: string;
  version: string;
  name: string;
  description?: string | null;
  sdk_version: string;
  engine: string;
  entrypoint: string;
  categories: string[];
  outputs: PluginOutputDecl[];
  timeout_seconds: number;
  memory_mb: number;
  network_policy: 'deny' | 'allow' | string;
  input_schema: JsonSchemaObject;
  enabled: boolean;
  status: string;
  diagnostics?: string | null;
  max_input_bytes: number;
  max_output_bytes: number;
  source_path: string;
  discovered_at: string;
  updated_at: string;
}

export interface PluginList {
  items: PluginRecord[];
  total: number;
  issues?: Array<Record<string, unknown>>;
}

// ── JSON Schema (subset used by the form renderer) ─────────────────────
export type JsonSchemaType = 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array';

export interface JsonSchemaProperty {
  title?: string;
  description?: string;
  type?: JsonSchemaType | JsonSchemaType[];
  enum?: Array<string | number | boolean>;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  multipleOf?: number;
  format?: string;
  /** Custom unit hint rendered beside numeric fields (e.g. "mm", "s"). */
  'x-unit'?: string;
  unit?: string;
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  additionalProperties?: boolean;
  items?: JsonSchemaProperty;
}

export interface JsonSchemaObject extends JsonSchemaProperty {
  $schema?: string;
  type?: 'object' | JsonSchemaType | JsonSchemaType[];
}

/** Content types the Phase 4 viewer can preview. */
export const VIEWABLE_CONTENT_TYPES = [
  'model/stl',
  'model/gltf-binary',
  'model/gltf+json',
  'application/octet-stream',
] as const;

export function isViewableFilename(filename: string): boolean {
  const lower = filename.toLowerCase();
  return lower.endsWith('.stl') || lower.endsWith('.glb') || lower.endsWith('.gltf');
}

export function inferModelFormat(
  filename: string,
  contentType?: string | null,
): 'stl' | 'glb' | null {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.stl') || contentType === 'model/stl') return 'stl';
  if (lower.endsWith('.glb') || contentType === 'model/gltf-binary') return 'glb';
  if (lower.endsWith('.gltf') || contentType === 'model/gltf+json') return 'glb';
  return null;
}
