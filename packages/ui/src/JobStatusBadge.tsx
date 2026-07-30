import type { JobStatus } from '@modumesh/shared-types';
import { Badge } from './Badge';

const LABELS: Record<JobStatus, string> = {
  created: 'Created',
  queued: 'Queued',
  running: 'Running',
  validating: 'Validating',
  uploading: 'Uploading',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

const TONES: Record<JobStatus, 'neutral' | 'info' | 'success' | 'warning' | 'danger'> = {
  created: 'neutral',
  queued: 'info',
  running: 'info',
  validating: 'warning',
  uploading: 'warning',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
};

export function jobStatusLabel(status: JobStatus | string): string {
  return LABELS[status as JobStatus] ?? status;
}

export function JobStatusBadge({ status }: { status: JobStatus | string }) {
  const tone = TONES[status as JobStatus] ?? 'neutral';
  return <Badge tone={tone}>{jobStatusLabel(status)}</Badge>;
}
