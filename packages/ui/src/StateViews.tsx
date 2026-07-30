import type { ReactNode } from 'react';
import { Button } from './Button';

export interface StateViewProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  children?: ReactNode;
}

export function LoadingState({ title, description }: StateViewProps) {
  return (
    <div className="mm-state" role="status" aria-live="polite" aria-busy="true">
      <div className="mm-spinner" aria-hidden="true" />
      <h2 className="mm-state__title">{title}</h2>
      {description ? <p className="mm-state__desc">{description}</p> : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  children,
}: StateViewProps) {
  return (
    <div className="mm-state">
      <h2 className="mm-state__title">{title}</h2>
      {description ? <p className="mm-state__desc">{description}</p> : null}
      {children}
      {actionLabel && onAction ? (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

export function OfflineState({ title, description, actionLabel, onAction }: StateViewProps) {
  return (
    <div className="mm-state mm-state--offline" role="alert">
      <h2 className="mm-state__title">{title}</h2>
      {description ? <p className="mm-state__desc">{description}</p> : null}
      {actionLabel && onAction ? (
        <Button variant="secondary" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

export function RetryState({
  title,
  description,
  actionLabel = 'Retry',
  onAction,
}: StateViewProps) {
  return (
    <div className="mm-state mm-state--error" role="alert">
      <h2 className="mm-state__title">{title}</h2>
      {description ? <p className="mm-state__desc">{description}</p> : null}
      {onAction ? (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
