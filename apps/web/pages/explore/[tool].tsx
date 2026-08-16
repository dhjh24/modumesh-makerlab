import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useState } from 'react';
import type { CatalogItem } from '@modumesh/shared-types';
import { Button } from '@modumesh/ui';
import { AppShell } from '../../components/AppShell';
import { api, ApiError } from '../../lib/api';

const MATURITY_LABELS: Record<string, string> = {
  experimental: 'Experimental',
  stable: 'Stable',
  deprecated: 'Deprecated',
};

const MATURITY_COLORS: Record<string, string> = {
  experimental: '#eab308',
  stable: '#22c55e',
  deprecated: '#ef4444',
};

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '6px 0', borderBottom: '1px solid #1e293b' }}>
      <dt style={{ width: 140, flexShrink: 0, color: '#64748b', fontSize: '0.875rem' }}>{label}</dt>
      <dd style={{ margin: 0, fontSize: '0.875rem' }}>{children}</dd>
    </div>
  );
}

export default function GeneratorDetailPage() {
  const router = useRouter();
  const pluginId = typeof router.query.tool === 'string' ? router.query.tool : null;
  const [item, setItem] = useState<CatalogItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!pluginId) return;
    setError(null);
    api
      .getCatalogItem(pluginId)
      .then(setItem)
      .catch((err) => setError(err instanceof ApiError ? err.message : String(err)));
  }, [pluginId]);

  const handleUseGenerator = useCallback(async () => {
    if (!item) return;
    setCreating(true);
    try {
      const project = await api.createProject({
        name: `${item.name} project`,
        description: `Generated from ${item.plugin_id}@${item.version}`,
      });
      await router.push(`/studio/${project.id}?tool=${encodeURIComponent(item.plugin_id)}`);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        // Catalog stays public, but creating a project requires a session.
        await router.push(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setError(apiErr.message);
      setCreating(false);
    }
  }, [item, router]);

  const outputFormats = item?.outputs
    .map((o) => o.mediaType.replace(/^model\//, '').replace(/^application\//, ''))
    .join(', ');

  const caps = item?.capabilities || {};
  const activeCaps = Object.entries(caps)
    .filter(([, v]) => v)
    .map(([k]) => k);

  return (
    <AppShell title={item ? `${item.name} · Generator` : 'Generator'}>
      <Head>
        <title>{item ? `${item.name} · ModuMesh MakerLab` : 'Loading…'}</title>
      </Head>

      {error ? (
        <div className="mm-panel" style={{ marginTop: '1rem', color: '#ef4444' }}>
          <p>{error}</p>
          <Link href="/explore">← Back to maker tools</Link>
        </div>
      ) : !item ? (
        <p>Loading generator details…</p>
      ) : (
        <>
          <Link
            href="/explore"
            style={{ fontSize: '0.875rem', color: '#64748b', textDecoration: 'none' }}
          >
            ← Generator Marketplace
          </Link>

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              flexWrap: 'wrap',
              gap: 12,
              marginTop: 12,
            }}
          >
            <div>
              <h1 className="mm-h1" style={{ margin: 0 }}>
                {item.name}
              </h1>
              <p style={{ color: '#64748b', margin: '4px 0 0 0' }}>
                {item.plugin_id}@{item.version}
                {item.author ? ` · ${item.author}` : ''}
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 10px',
                  borderRadius: 10,
                  backgroundColor: MATURITY_COLORS[item.maturity] || '#64748b',
                  color: '#fff',
                }}
              >
                {MATURITY_LABELS[item.maturity] || item.maturity}
              </span>
            </div>
          </div>

          {item.description ? (
            <p style={{ marginTop: 12, color: '#94a3b8', maxWidth: 600 }}>{item.description}</p>
          ) : null}

          <Button
            onClick={handleUseGenerator}
            disabled={creating}
            style={{ marginTop: 16, marginBottom: 24 }}
          >
            {creating ? 'Creating project…' : `Use ${item.name}`}
          </Button>

          <div className="mm-grid-3" style={{ marginTop: 0 }}>
            {/* Details */}
            <section className="mm-panel" aria-labelledby="details-heading">
              <h2 id="details-heading" style={{ fontSize: '1rem', marginTop: 0 }}>
                Details
              </h2>
              <dl>
                <DetailRow label="Engine">{item.engine}</DetailRow>
                <DetailRow label="Output formats">{outputFormats || '—'}</DetailRow>
                <DetailRow label="Timeout">{item.timeout_seconds}s</DetailRow>
                <DetailRow label="Memory">{item.memory_mb} MB</DetailRow>
                <DetailRow label="SDK version">{item.sdk_version}</DetailRow>
              </dl>
            </section>

            {/* License */}
            <section className="mm-panel" aria-labelledby="license-heading">
              <h2 id="license-heading" style={{ fontSize: '1rem', marginTop: 0 }}>
                License
              </h2>
              {item.license ? (
                <dl>
                  <DetailRow label="SPDX">{item.license}</DetailRow>
                  {item.license_url ? (
                    <DetailRow label="URL">
                      <a
                        href={item.license_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#60a5fa' }}
                      >
                        {item.license_url}
                      </a>
                    </DetailRow>
                  ) : null}
                  {item.source_url ? (
                    <DetailRow label="Source">
                      <a
                        href={item.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: '#60a5fa' }}
                      >
                        Repository
                      </a>
                    </DetailRow>
                  ) : null}
                </dl>
              ) : (
                <p style={{ color: '#ef4444', fontSize: '0.875rem' }}>
                  No license declared — generator is quarantined.
                </p>
              )}
            </section>

            {/* Capabilities */}
            <section className="mm-panel" aria-labelledby="capabilities-heading">
              <h2 id="capabilities-heading" style={{ fontSize: '1rem', marginTop: 0 }}>
                Capabilities
              </h2>
              {activeCaps.length > 0 ? (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {activeCaps.map((cap) => (
                    <li
                      key={cap}
                      style={{
                        padding: '4px 0',
                        fontSize: '0.875rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      <span style={{ color: '#22c55e' }}>●</span> {cap}
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: '#64748b', fontSize: '0.875rem' }}>
                  No special capabilities declared.
                </p>
              )}
              {item.categories.length > 0 ? (
                <div style={{ marginTop: 12 }}>
                  <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: 4 }}>
                    Categories
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {item.categories.map((cat) => (
                      <span
                        key={cat}
                        style={{
                          fontSize: '0.7rem',
                          padding: '2px 8px',
                          borderRadius: 4,
                          backgroundColor: '#1e293b',
                          color: '#94a3b8',
                        }}
                      >
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
              {item.tags.length > 0 ? (
                <div style={{ marginTop: 12 }}>
                  <p style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: 4 }}>Tags</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        style={{
                          fontSize: '0.7rem',
                          padding: '2px 8px',
                          borderRadius: 4,
                          backgroundColor: '#334155',
                          color: '#94a3b8',
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        </>
      )}
    </AppShell>
  );
}
