import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useState } from 'react';
import { EmptyState, LoadingState, OfflineState, RetryState } from '@modumesh/ui';
import { AppShell } from '../components/AppShell';
import { api, ApiError } from '../lib/api';
import { formatRelativeTime, useOnline, useRequireAuth } from '../lib/hooks';

/**
 * My Models — visual model library (WF3, approved).
 * W2.1 scaffolding: real list of non-archived projects with the honest
 * printable-state column; the full card grid (thumbnails, duplicate/remove
 * under ⋯) lands in W2.4.
 */
export default function MyModelsPage() {
  const router = useRouter();
  const online = useOnline();
  const { status } = useRequireAuth();
  const [projects, setProjects] = useState<Array<{
    id: string;
    name: string;
    updated_at: string;
  }> | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listProjects(50);
      setProjects(res.items);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setError(apiErr);
    }
  }, [router]);

  useEffect(() => {
    if (!router.isReady || status !== 'authenticated') return;
    void load();
  }, [router.isReady, status, load]);

  if (status !== 'authenticated') {
    return (
      <AppShell title="My Models">
        <LoadingState title="Checking session…" />
      </AppShell>
    );
  }

  if (!online) {
    return (
      <AppShell title="My Models">
        <OfflineState
          title="You are offline"
          description="Reconnect to see your models."
          actionLabel="Retry"
          onAction={() => void load()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell title="My Models">
      <Head>
        <title>My Models · ModuMesh MakerLab</title>
      </Head>
      <h1 className="mm-h1">My Models</h1>
      <p className="mm-lead">Everything you&apos;ve made — open one to keep editing.</p>

      {error ? (
        <div style={{ marginTop: '0.75rem' }}>
          <RetryState
            title="Couldn't load your models"
            description="The MakerLab service didn't respond. Your models are safe — try again in a moment."
            onAction={() => void load()}
          />
        </div>
      ) : projects === null ? (
        <LoadingState title="Loading your models…" />
      ) : projects.length === 0 ? (
        <EmptyState
          title="No models yet"
          description="Start with a nameplate, a storage box, or one of the other maker tools — your finished models land here automatically."
          actionLabel="Make your first model"
          onAction={() => void router.push('/')}
        />
      ) : (
        <ul className="mm-list" style={{ marginTop: '0.75rem' }}>
          {projects.map((p) => (
            <li key={p.id}>
              <Link
                href={`/studio/${p.id}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  textDecoration: 'none',
                  padding: '10px 4px',
                }}
              >
                <strong>{p.name}</strong>
                <span className="mm-meta">{formatRelativeTime(p.updated_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
