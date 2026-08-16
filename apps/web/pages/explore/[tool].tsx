import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useState } from 'react';
import { Button, LoadingState } from '@modumesh/ui';
import { AppShell } from '../../components/AppShell';
import { api, ApiError } from '../../lib/api';
import { makerToolFor } from '../../lib/makerTools';

export default function ToolDetailPage() {
  const router = useRouter();
  const slug = typeof router.query.tool === 'string' ? router.query.tool : null;
  const tool = makerToolFor(slug);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!slug || tool) return;
    // Unknown slug: fetch to confirm it's not an installed-but-unmapped tool.
    // (Every surfaced tool maps in makerTools.ts; this only catches stragglers.)
    api.getCatalogItem(slug).catch(() => setError('This maker tool is not available.'));
  }, [slug, tool]);

  const handleCreate = useCallback(async () => {
    if (!tool) return;
    setCreating(true);
    try {
      const project = await api.createProject({
        name: `${tool.name} project`,
        description: `Made with ${tool.name}`,
      });
      await router.push(`/studio/${project.id}?tool=${encodeURIComponent(tool.slug)}`);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        await router.push(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setError(apiErr.message);
      setCreating(false);
    }
  }, [tool, router]);

  return (
    <AppShell title={tool ? tool.name : 'Explore'}>
      <Head>
        <title>{tool ? `${tool.name} · ModuMesh MakerLab` : 'Explore'}</title>
      </Head>

      <Link
        href="/explore"
        style={{ fontSize: '0.875rem', color: '#5b6e72', textDecoration: 'none' }}
      >
        ← All maker tools
      </Link>

      {!tool ? (
        <div style={{ marginTop: '1.5rem' }}>
          {error ? (
            <div className="mm-panel" style={{ color: '#b91c1c' }}>
              <p>{error}</p>
              <Link href="/explore">Browse other maker tools</Link>
            </div>
          ) : (
            <LoadingState title="Loading tool…" />
          )}
        </div>
      ) : (
        <div style={{ marginTop: '1rem', maxWidth: 720 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span aria-hidden="true" style={{ fontSize: '2.4rem', lineHeight: 1 }}>
              {tool.icon}
            </span>
            <div>
              <h1 className="mm-h1" style={{ margin: 0 }}>
                {tool.name}
              </h1>
              <p style={{ color: '#5b6e72', margin: '2px 0 0 0', fontSize: '0.9rem' }}>
                {tool.categoryLabel} · {tool.difficulty}
              </p>
            </div>
          </div>

          <p style={{ marginTop: 16, fontSize: '1.05rem', maxWidth: 560 }}>{tool.promise}</p>

          <div className="mm-panel" style={{ marginTop: 20 }}>
            <h2 style={{ fontSize: '1rem', marginTop: 0 }}>What you can make</h2>
            <ul className="mm-list" style={{ margin: 0 }}>
              {tool.examples.map((ex) => (
                <li key={ex}>{ex}</li>
              ))}
            </ul>
          </div>

          <div className="mm-panel" style={{ marginTop: 12 }}>
            <h2 style={{ fontSize: '1rem', marginTop: 0 }}>How it works</h2>
            <p style={{ color: '#5b6e72', fontSize: '0.9rem', margin: 0 }}>
              {tool.inputModeLabel} You can fine-tune everything in the studio before generating.
            </p>
          </div>

          {error ? <p style={{ color: '#b91c1c', marginTop: 12 }}>{error}</p> : null}

          <div style={{ marginTop: 20 }}>
            <Button onClick={() => void handleCreate()} disabled={creating} size="md">
              {creating ? 'Setting up…' : `Create with ${tool.name}`}
            </Button>
            <p className="mm-meta" style={{ marginTop: 8 }}>
              Creates a project and opens it in the studio, ready to tune.
            </p>
          </div>
        </div>
      )}
    </AppShell>
  );
}
