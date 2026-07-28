/** Shared types across ModuMesh MakerLab services. */

// ── Projects ───────────────────────────────────────────────────────────
export type ProjectStatus = 'active' | 'archived';

export interface Project {
  id: string;
  ownerId: string;
  name: string;
  description?: string;
  status: ProjectStatus;
  createdAt: string;
  updatedAt: string;
  archivedAt?: string;
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

export interface Job {
  id: string;
  projectId: string;
  parentJobId?: string;
  jobType: string;
  status: JobStatus;
  inputPayload: Record<string, unknown>;
  progressPct: number;
  progressMessage?: string;
  errorMessage?: string;
  idempotencyKey?: string;
  attemptNumber: number;
  workerId?: string;
  timeoutSeconds: number;
  cancelRequested: boolean;
  createdAt: string;
  updatedAt: string;
  queuedAt?: string;
  startedAt?: string;
  completedAt?: string;
}

export interface JobProgress {
  id: string;
  status: JobStatus;
  progressPct: number;
  progressMessage?: string;
  errorMessage?: string;
  cancelRequested: boolean;
  updatedAt: string;
}

// ── Files ──────────────────────────────────────────────────────────────
export interface FileObject {
  id: string;
  projectId: string;
  jobId?: string;
  objectKey: string;
  filename: string;
  contentType: string;
  sizeBytes: number;
  sha256: string;
  createdAt: string;
}

// ── Plugins ────────────────────────────────────────────────────────────
export interface PluginRecord {
  id: string;
  name: string;
  version: string;
  description: string;
  inputSchema: unknown;
  outputFormat: string;
  enabled: boolean;
  createdAt: string;
}
