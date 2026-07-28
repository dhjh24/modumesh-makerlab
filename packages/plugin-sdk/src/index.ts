/** Plugin SDK — types and utilities for writing ModuMesh plugins. */

export interface PluginManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  inputSchemaUri: string;
  outputFormat: 'stl' | 'step' | 'obj' | 'glb';
}

export interface PluginJob {
  jobId: string;
  pluginId: string;
  input: Record<string, unknown>;
  projectId: string;
  versionId: string;
}

export interface PluginResult {
  jobId: string;
  status: 'completed' | 'failed';
  outputFile?: string;
  checksum?: string;
  error?: string;
  durationMs: number;
}

export function validateManifest(manifest: unknown): manifest is PluginManifest {
  if (typeof manifest !== 'object' || manifest === null) return false;
  const m = manifest as Record<string, unknown>;
  return typeof m.id === 'string' && typeof m.name === 'string' && typeof m.version === 'string';
}
