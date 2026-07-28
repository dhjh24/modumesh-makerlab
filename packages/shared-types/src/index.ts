/** Shared types across ModuMesh MakerLab services. */

// ── Projects ───────────────────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectVersion {
  id: string;
  projectId: string;
  version: number;
  pluginId: string;
  input: Record<string, unknown>;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  outputFile?: string;
  checksum?: string;
  createdAt: string;
  completedAt?: string;
}

// ── Jobs ───────────────────────────────────────────────────────────────
export interface Job {
  id: string;
  projectId: string;
  versionId: string;
  pluginId: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  input: Record<string, unknown>;
  outputFile?: string;
  checksum?: string;
  error?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
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
