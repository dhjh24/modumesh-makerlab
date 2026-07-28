import type { NextPage } from 'next';
import Head from 'next/head';
import { useEffect, useState } from 'react';

type ServiceStatus = 'ok' | 'degraded' | 'error' | 'loading';

interface HealthCheck {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  checks: Record<string, { status: string; latency_ms?: number; error?: string }>;
}

const Home: NextPage = () => {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [status, setStatus] = useState<ServiceStatus>('loading');

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((data: HealthCheck) => {
        setHealth(data);
        setStatus(data.status as ServiceStatus);
      })
      .catch(() => {
        setStatus('error');
      });
  }, []);

  const statusColor = (s: string) => {
    switch (s) {
      case 'ok':
        return '#22c55e';
      case 'ready':
        return '#22c55e';
      case 'alive':
        return '#22c55e';
      case 'degraded':
        return '#f59e0b';
      case 'error':
      case 'not_ready':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  return (
    <div
      style={{
        fontFamily: 'system-ui, sans-serif',
        padding: '2rem',
        maxWidth: 800,
        margin: '0 auto',
      }}
    >
      <Head>
        <title>ModuMesh MakerLab</title>
        <meta name="description" content="Self-hosted 3D generator platform" />
      </Head>

      <header style={{ marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0 }}>ModuMesh MakerLab</h1>
        <p style={{ color: '#6b7280', margin: '0.25rem 0 0' }}>Self-hosted 3D generator platform</p>
      </header>

      {/* Overall Status */}
      <section
        style={{
          padding: '1rem',
          borderRadius: 8,
          border: '1px solid #e5e7eb',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
        }}
      >
        <span
          style={{
            width: 12,
            height: 12,
            borderRadius: '50%',
            backgroundColor: statusColor(status),
            display: 'inline-block',
          }}
        />
        <span style={{ fontWeight: 600 }}>
          {status === 'loading'
            ? 'Checking...'
            : status === 'ok'
              ? 'All Systems Operational'
              : status === 'degraded'
                ? 'Degraded Performance'
                : 'Service Unavailable'}
        </span>
        {health && (
          <span style={{ color: '#6b7280', fontSize: '0.875rem', marginLeft: 'auto' }}>
            v{health.version}
          </span>
        )}
      </section>

      {/* Service Checks */}
      {health?.checks && (
        <section>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '0.75rem' }}>
            Services
          </h2>
          {Object.entries(health.checks).map(([name, check]) => (
            <div
              key={name}
              style={{
                padding: '0.75rem 1rem',
                borderRadius: 8,
                border: '1px solid #e5e7eb',
                marginBottom: '0.5rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
              }}
            >
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  backgroundColor: statusColor(check.status),
                  display: 'inline-block',
                }}
              />
              <span style={{ fontWeight: 500, textTransform: 'capitalize' }}>{name}</span>
              <span style={{ color: '#6b7280', fontSize: '0.875rem' }}>{check.status}</span>
              {check.latency_ms !== undefined && (
                <span style={{ color: '#9ca3af', fontSize: '0.8rem', marginLeft: 'auto' }}>
                  {check.latency_ms}ms
                </span>
              )}
              {check.error && (
                <span style={{ color: '#ef4444', fontSize: '0.8rem', marginLeft: 'auto' }}>
                  {check.error}
                </span>
              )}
            </div>
          ))}
        </section>
      )}

      {status === 'loading' && !health && (
        <p style={{ color: '#6b7280' }}>Loading service status...</p>
      )}

      <footer style={{ marginTop: '2rem', color: '#9ca3af', fontSize: '0.75rem' }}>
        <a href="/api/health" style={{ color: '#3b82f6' }}>
          Raw Health API
        </a>
      </footer>
    </div>
  );
};

export default Home;
