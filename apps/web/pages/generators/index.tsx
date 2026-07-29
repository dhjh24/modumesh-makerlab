import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { PluginRecord, Project } from '@modumesh/shared-types';
import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  LoadingState,
  OfflineState,
  SchemaForm,
  defaultsFromSchema,
} from '@modumesh/ui';
import { AppShell } from '../../components/AppShell';
import { api, ApiError } from '../../lib/api';
import { useOnline } from '../../lib/hooks';

export default function GeneratorsPage() {
  const router = useRouter();
  const online = useOnline();
  const [plugins, setPlugins] = useState<PluginRecord[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<ApiError | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [formValue, setFormValue] = useState<Record<string, unknown>>({});
  const [projectId, setProjectId] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [plist, proj] = await Promise.all([api.listPlugins(true), api.listProjects(50)]);
      setPlugins(plist.items);
      setProjects(proj.items);
      const q = typeof router.query.plugin === 'string' ? router.query.plugin : null;
      const initial = q || plist.items[0]?.plugin_id || null;
      setSelectedId(initial);
      if (proj.items[0]) setProjectId(proj.items[0].id);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
    }
  }, [router.query.plugin]);

  useEffect(() => {
    if (!router.isReady) return;
    void load();
  }, [router.isReady, load]);

  const selected = useMemo(
    () => plugins?.find((p) => p.plugin_id === selectedId) ?? null,
    [plugins, selectedId],
  );

  useEffect(() => {
    if (!selected) return;
    setFormValue(defaultsFromSchema(selected.input_schema));
  }, [selected]);

  const openInEditor = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      let pid = projectId;
      if (!pid) {
        const created = await api.createProject({
          name: `${selected.name} project`,
          description: `Created from generator catalog for ${selected.plugin_id}`,
        });
        pid = created.id;
      }
      await router.push(`/projects/${pid}?plugin=${encodeURIComponent(selected.plugin_id)}`);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
      setBusy(false);
    }
  };

  if (!online) {
    return (
      <AppShell title="Generators">
        <OfflineState
          title="You are offline"
          description="The generator catalog needs API access."
          actionLabel="Retry"
          onAction={() => void load()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell title="Generators">
      <Head>
        <title>Generators · ModuMesh MakerLab</title>
      </Head>
      <h1 className="mm-h1">Generator catalog</h1>
      <p className="mm-lead">
        Driven entirely by plugin registry metadata — install a compatible plugin and it appears
        here with a usable form from its JSON Schema.
      </p>

      {error ? (
        <ErrorPanel
          message={error.message}
          technicalDetail={[
            error.correlationId ? `correlation_id=${error.correlationId}` : null,
            `status=${error.status}`,
            error.body,
          ]
            .filter(Boolean)
            .join('\n')}
          onRetry={() => void load()}
        />
      ) : null}

      {plugins === null && !error ? <LoadingState title="Discovering plugins…" /> : null}

      {plugins && plugins.length === 0 ? (
        <EmptyState
          title="No enabled plugins"
          description="Drop a plugin into the plugins directory and call POST /api/v1/plugins/resync."
        />
      ) : null}

      {plugins && plugins.length > 0 ? (
        <div className="mm-grid-3" style={{ gridTemplateColumns: 'minmax(240px, 320px) 1fr' }}>
          <section className="mm-panel" aria-label="Installed generators">
            <h2>Installed</h2>
            <ul className="mm-list">
              {plugins.map((p) => (
                <li key={`${p.plugin_id}@${p.version}`}>
                  <button
                    type="button"
                    className="mm-linkish"
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      padding: '0.55rem 0.65rem',
                      textDecoration: 'none',
                      background:
                        selectedId === p.plugin_id ? 'var(--mm-accent-soft)' : 'transparent',
                      borderRadius: 8,
                      border: '1px solid transparent',
                    }}
                    aria-current={selectedId === p.plugin_id ? 'true' : undefined}
                    onClick={() => setSelectedId(p.plugin_id)}
                  >
                    <strong>{p.name}</strong>
                    <div className="mm-meta">
                      {p.plugin_id} · v{p.version}
                    </div>
                    <div className="mm-row" style={{ marginTop: 4 }}>
                      {p.categories?.slice(0, 3).map((c) => (
                        <Badge key={c}>{c}</Badge>
                      ))}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="mm-panel" aria-live="polite">
            {selected ? (
              <>
                <h2>{selected.name}</h2>
                <p className="mm-meta">
                  {selected.description || 'No description provided.'} · engine {selected.engine} ·
                  timeout {selected.timeout_seconds}s
                </p>
                <div className="mm-row" style={{ margin: '0.75rem 0' }}>
                  <label className="mm-field__label" htmlFor="target-project">
                    Open in project
                  </label>
                  <select
                    id="target-project"
                    className="mm-input"
                    style={{ maxWidth: 320 }}
                    value={projectId}
                    onChange={(e) => setProjectId(e.target.value)}
                  >
                    <option value="">Create new project</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                  <Button onClick={() => void openInEditor()} disabled={busy}>
                    {busy ? 'Opening…' : 'Open editor'}
                  </Button>
                </div>
                <h3 className="mm-meta" style={{ fontWeight: 700, color: 'var(--mm-ink)' }}>
                  Schema preview
                </h3>
                <SchemaForm
                  schema={selected.input_schema}
                  value={formValue}
                  onChange={setFormValue}
                  disabled
                  idPrefix={`preview-${selected.plugin_id}`}
                />
                <p className="mm-meta">
                  Preview only — submit jobs from the{' '}
                  <Link
                    href={projectId ? `/projects/${projectId}?plugin=${selected.plugin_id}` : '/'}
                  >
                    project editor
                  </Link>
                  .
                </p>
              </>
            ) : (
              <EmptyState title="Select a generator" description="Choose a plugin from the list." />
            )}
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
