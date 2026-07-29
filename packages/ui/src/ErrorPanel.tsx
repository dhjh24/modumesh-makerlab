import { useId, useState } from 'react';
import { Button } from './Button';

export interface ErrorPanelProps {
  /** User-facing summary. */
  message: string;
  /** Technical detail for administrators (correlation id, stack, raw API body). */
  technicalDetail?: string | null;
  onRetry?: () => void;
  className?: string;
}

export function ErrorPanel({ message, technicalDetail, onRetry, className = '' }: ErrorPanelProps) {
  const [open, setOpen] = useState(false);
  const detailId = useId();

  return (
    <div className={`mm-error-panel ${className}`.trim()} role="alert">
      <div className="mm-error-panel__body">
        <p className="mm-error-panel__message">{message}</p>
        {onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
      </div>
      {technicalDetail ? (
        <div className="mm-error-panel__tech">
          <button
            type="button"
            className="mm-linkish"
            aria-expanded={open}
            aria-controls={detailId}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? 'Hide technical details' : 'Show technical details'}
          </button>
          {open ? (
            <pre id={detailId} className="mm-error-panel__pre">
              {technicalDetail}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
