/** Plugin SDK — TypeScript contract types aligned with manifest.v1. */

export const CURRENT_SDK_VERSION = '1.0.0' as const;
export const MANIFEST_SCHEMA_VERSION = '1' as const;

export type PluginEngine = 'python';
export type NetworkPolicy = 'deny' | 'allow';

export type PluginMediaType =
  | 'application/json'
  | 'text/plain'
  | 'text/csv'
  | 'application/octet-stream'
  | 'image/png'
  | 'model/stl'
  | 'model/step'
  | 'model/obj'
  | 'model/gltf-binary';

export interface PluginOutputDecl {
  name: string;
  mediaType: PluginMediaType;
  required?: boolean;
}

export interface PluginManifest {
  schemaVersion: typeof MANIFEST_SCHEMA_VERSION;
  id: string;
  name: string;
  version: string;
  sdkVersion: string;
  engine: PluginEngine;
  entrypoint: string;
  description?: string;
  categories: string[];
  outputs: PluginOutputDecl[];
  timeoutSeconds: number;
  memoryMb: number;
  networkPolicy: NetworkPolicy;
  inputSchema: Record<string, unknown> | string;
  maxInputBytes?: number;
  maxOutputBytes?: number;
}

export interface PluginRecord {
  pluginId: string;
  version: string;
  name: string;
  description: string;
  sdkVersion: string;
  engine: PluginEngine;
  entrypoint: string;
  categories: string[];
  outputs: PluginOutputDecl[];
  timeoutSeconds: number;
  memoryMb: number;
  networkPolicy: NetworkPolicy;
  enabled: boolean;
  status: 'active' | 'invalid' | 'incompatible';
  diagnostics?: string;
  discoveredAt: string;
  updatedAt: string;
}

export interface PluginJob {
  jobId: string;
  pluginId: string;
  pluginVersion: string;
  input: Record<string, unknown>;
  projectId: string;
}

export interface PluginResult {
  jobId: string;
  status: 'completed' | 'failed';
  outputs?: Array<{ name: string; sha256?: string; sizeBytes?: number }>;
  error?: string;
  durationMs: number;
}

export function isSdkCompatible(sdkVersion: string, hostMajor = 1): boolean {
  const major = Number.parseInt(sdkVersion.split('.')[0] ?? '', 10);
  return Number.isFinite(major) && major === hostMajor;
}

export function validateManifest(manifest: unknown): manifest is PluginManifest {
  if (typeof manifest !== 'object' || manifest === null) return false;
  const m = manifest as Record<string, unknown>;
  return (
    m.schemaVersion === MANIFEST_SCHEMA_VERSION &&
    typeof m.id === 'string' &&
    typeof m.name === 'string' &&
    typeof m.version === 'string' &&
    typeof m.sdkVersion === 'string' &&
    typeof m.engine === 'string' &&
    typeof m.entrypoint === 'string' &&
    Array.isArray(m.categories) &&
    Array.isArray(m.outputs) &&
    typeof m.timeoutSeconds === 'number' &&
    typeof m.memoryMb === 'number' &&
    typeof m.networkPolicy === 'string' &&
    m.inputSchema !== undefined &&
    isSdkCompatible(String(m.sdkVersion))
  );
}
