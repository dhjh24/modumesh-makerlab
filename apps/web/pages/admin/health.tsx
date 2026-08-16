import { useCallback, useEffect, useState } from 'react';
import Head from 'next/head';
import { AppShell } from '../../components/AppShell';
import { api, ApiError } from '../../lib/api';

interface CheckResult {
  status: string;
  latency_ms?: number;
  error?: string;
  [key: string]: unknown;
}

type HealthData = {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  checks: Record<string, CheckResult>;
};

function CheckRow({ name, result }: { name: string; result: CheckResult }) {
  const ok = result.status === 'ok';
  return (
    <tr>
      <td style={{ fontWeight: 600, padding: '0.5rem 1rem 0.5rem 0', whiteSpace: 'nowrap' }}>
        {name}
      </td>
      <td style={{ padding: '0.5rem 1rem' }}>
        <span
          style={{
            display: 'inline-block',
            width: 10,
            height: 10,
            borderRadius: '50%',
            backgroundColor: ok ? '#22c55e' : '#ef4444',
            marginRight: 8,
          }}
        />
        {result.status}
      </td>
      <td style={{ padding: '0.5rem 1rem', color: '#64748b', fontSize: '0.875rem' }}>
        {result.latency_ms != null ? `${result.latency_ms}ms` : ''}
        {result.active_workers != null ? `${result.active_workers} worker(s)` : ''}
        {result.total != null ? `${result.total} total, ${result.enabled} enabled` : ''}
        {result.error || ''}
      </td>
    </tr>
  );
}

export default function HealthPage() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getFullHealth();
      setData(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 15_000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <AppShell title="System Health">
      <Head>
        <title>System Health · ModuMesh MakerLab</title>
      </Head>

      <h1 className="mm-h1">System health</h1>
      <p className="mm-lead">
        Live status of all MakerLab services. Auto-refreshes every 15 seconds.
      </p>

      <div className="mm-panel" style={{ marginTop: '1rem' }}>
        {loading && !data ? (
          <p>Loading health data…</p>
        ) : error ? (
          <div>
            <p style={{ color: '#ef4444' }}>{error}</p>
            <button className="mm-btn" onClick={() => void load()} style={{ marginTop: 8 }}>
              Retry
            </button>
          </div>
        ) : data ? (
          <>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                marginBottom: '1rem',
              }}
            >
              <span
                style={{
                  display: 'inline-block',
                  width: 14,
                  height: 14,
                  borderRadius: '50%',
                  backgroundColor: data.status === 'ok' ? '#22c55e' : '#eab308',
                }}
              />
              <strong style={{ fontSize: '1.125rem' }}>
                {data.status === 'ok' ? 'All systems operational' : 'Degraded service'}
              </strong>
              <span style={{ color: '#64748b', fontSize: '0.875rem', marginLeft: 'auto' }}>
                {data.service} · v{data.version}
              </span>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '0.5rem 1rem 0.5rem 0', fontWeight: 600 }}>Component</th>
                  <th style={{ padding: '0.5rem 1rem', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '0.5rem 1rem', fontWeight: 600 }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(data.checks).map(([name, result]) => (
                  <CheckRow key={name} name={name} result={result} />
                ))}
              </tbody>
            </table>

            <p
              style={{
                marginTop: '1rem',
                fontSize: '0.75rem',
                color: '#94a3b8',
              }}
            >
              As of {new Date(data.timestamp).toLocaleString()}
            </p>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
