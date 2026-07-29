import { useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { api, ApiError, AuthUser } from '../lib/api';

type Status = Awaited<ReturnType<typeof api.adminStatus>>;

export default function AdminStatusPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.me();
        if (cancelled) return;
        setUser(me);
        if (me.role !== 'admin') {
          setError('Administrator role required');
          return;
        }
        const s = await api.adminStatus();
        if (!cancelled) setStatus(s);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load status');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell title="Admin status">
      <section className="mm-section">
        <h1 className="mm-display">Administrator status</h1>
        <p className="mm-lede">
          Service health, queue depth, job failures, storage, and plugin registry.
        </p>
        {error ? (
          <p className="mm-error" role="alert">
            {error}
          </p>
        ) : null}
        {user ? (
          <p className="mm-muted">
            Signed in as {user.display_name} ({user.role})
          </p>
        ) : null}
        {status ? (
          <div className="mm-admin-grid">
            <div>
              <h2>Services</h2>
              <ul>
                {Object.entries(status.services).map(([name, info]) => (
                  <li key={name}>
                    <strong>{name}</strong>:{' '}
                    {typeof info === 'object' && info && 'status' in info
                      ? String((info as { status: string }).status)
                      : JSON.stringify(info)}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2>Queue & jobs</h2>
              <ul>
                <li>Queue depth: {status.queue_depth}</li>
                <li>Active jobs: {status.active_jobs}</li>
                <li>Failed jobs: {status.failed_jobs}</li>
                <li>Projects: {status.project_count}</li>
              </ul>
            </div>
            <div>
              <h2>Storage</h2>
              <ul>
                <li>Files: {status.file_count}</li>
                <li>Bytes: {status.storage_bytes.toLocaleString()}</li>
                <li>Retention days: {status.retention_days}</li>
              </ul>
            </div>
            <div>
              <h2>Plugins</h2>
              <ul>
                {status.plugins.map((p) => (
                  <li key={`${p.plugin_id}@${p.version}`}>
                    {String(p.plugin_id)}@{String(p.version)} — {String(p.status)}
                    {p.enabled ? '' : ' (disabled)'}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : !error ? (
          <p>Loading…</p>
        ) : null}
      </section>
    </AppShell>
  );
}
