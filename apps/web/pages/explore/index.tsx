import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { LoadingState, OfflineState } from '@modumesh/ui';
import { AppShell } from '../../components/AppShell';
import { api } from '../../lib/api';
import { listMakerTools, TOOL_CATEGORIES, type MakerTool } from '../../lib/makerTools';
import { useOnline } from '../../lib/hooks';

function ToolCard({ tool }: { tool: MakerTool }) {
  return (
    <Link href={`/explore/${tool.slug}`} aria-label={tool.name} style={{ textDecoration: 'none' }}>
      <article
        className="mm-panel"
        style={{
          cursor: 'pointer',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span aria-hidden="true" style={{ fontSize: '1.6rem', lineHeight: 1 }}>
            {tool.icon}
          </span>
          <h3 style={{ margin: 0, fontSize: '1rem' }}>{tool.name}</h3>
        </div>
        <p
          style={{
            fontSize: '0.8125rem',
            color: '#5b6e72',
            margin: 0,
            flex: 1,
          }}
        >
          {tool.promise}
        </p>
        <div
          style={{
            display: 'flex',
            gap: 6,
            fontSize: '0.7rem',
            color: '#8aa0a5',
            flexWrap: 'wrap',
          }}
        >
          <span>{tool.categoryLabel}</span>
          <span aria-hidden="true">·</span>
          <span>{tool.difficulty}</span>
        </div>
      </article>
    </Link>
  );
}

export default function ExplorePage() {
  const online = useOnline();
  const [available, setAvailable] = useState<Set<string> | null>(null);
  const [selected, setSelected] = useState<string>('');

  // Which tools are actually installed/enabled, from the catalog API.
  const load = useCallback(async () => {
    try {
      const res = await api.listCatalog({ limit: 100 });
      setAvailable(new Set(res.items.map((i) => i.plugin_id)));
    } catch {
      setAvailable(new Set());
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const tools = useMemo(() => {
    const all = listMakerTools().filter((t) => available === null || available.has(t.slug));
    return selected ? all.filter((t) => t.category === selected) : all;
  }, [available, selected]);

  return (
    <AppShell title="Explore">
      <Head>
        <title>Explore maker tools · ModuMesh MakerLab</title>
      </Head>

      <h1 className="mm-h1">Explore maker tools</h1>
      <p className="mm-lead">
        What do you want to make? Pick a tool, set the size, and generate — the rest happens for
        you.
      </p>

      {!online ? (
        <OfflineState
          title="You are offline"
          description="Reconnect to browse maker tools."
          actionLabel="Retry"
          onAction={() => void load()}
        />
      ) : available === null ? (
        <LoadingState title="Loading maker tools…" />
      ) : tools.length === 0 ? (
        <div className="mm-panel" style={{ marginTop: '1rem' }}>
          <p>No maker tools available yet — more are on the way.</p>
        </div>
      ) : (
        <>
          <div
            role="group"
            aria-label="Filter tools by category"
            style={{
              display: 'flex',
              gap: 8,
              flexWrap: 'wrap',
              margin: '1rem 0',
            }}
          >
            <button
              type="button"
              className="mm-btn"
              aria-pressed={selected === ''}
              onClick={() => setSelected('')}
              style={{
                background: selected === '' ? 'var(--mm-accent, #0f766e)' : '#fff',
                color: selected === '' ? '#fff' : '#5b6e72',
                border: '1px solid var(--mm-line, #d8e0e0)',
                borderRadius: 999,
                padding: '6px 14px',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              All
            </button>
            {TOOL_CATEGORIES.map((c) => (
              <button
                key={c.key}
                type="button"
                className="mm-btn"
                aria-pressed={selected === c.key}
                onClick={() => setSelected(selected === c.key ? '' : c.key)}
                style={{
                  background: selected === c.key ? 'var(--mm-accent, #0f766e)' : '#fff',
                  color: selected === c.key ? '#fff' : '#5b6e72',
                  border: '1px solid var(--mm-line, #d8e0e0)',
                  borderRadius: 999,
                  padding: '6px 14px',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {c.label}
              </button>
            ))}
          </div>

          <div className="mm-grid-3" style={{ marginTop: 0 }}>
            {tools.map((tool) => (
              <ToolCard key={tool.slug} tool={tool} />
            ))}
          </div>
        </>
      )}
    </AppShell>
  );
}
