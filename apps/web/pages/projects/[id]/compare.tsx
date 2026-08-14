import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useState } from 'react';
import {
  isTerminalJobStatus,
  type FileObject,
  type Job,
  type PluginRecord,
  type Project,
} from '@modumesh/shared-types';
import {
  Button,
  EmptyState,
  ErrorPanel,
  JobStatusBadge,
  LoadingState,
  OfflineState,
} from '@modumesh/ui';
import { AppShell } from '../../../components/AppShell';
import {
  api,
  ApiError,
  fetchFileBlob,
  type CompareJobRef,
  type CompareResultRow,
  type DesignManifest,
} from '../../../lib/api';
import { formatDuration, useJobPolling, useOnline, useRequireAuth } from '../../../lib/hooks';

const MAX_GENERATORS = 6;

/** Fetch a protected JSON manifest and parse it; degrades to null. */
async function fetchJsonManifest<T>(file: FileObject): Promise<T | null> {
  try {
    const { blob } = await fetchFileBlob(file.id, file.filename);
    return JSON.parse(await blob.text()) as T;
  } catch {
    return null;
  }
}

/**
 * One comparison run card. Polls its job via useJobPolling, renders status +
 * progress, and once terminal lists the job's output files (design.json
 * summary + fetchFileBlob downloads). No bare URLs for protected files.
 */
function CompareJobCard({
  jobId,
  jobType,
  generatorName,
}: {
  jobId: string;
  jobType: string;
  generatorName?: string;
}) {
  const router = useRouter();
  const { progress, error: pollError } = useJobPolling(jobId);
  const [files, setFiles] = useState<FileObject[] | null>(null);
  const [design, setDesign] = useState<DesignManifest | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<ApiError | null>(null);

  const status = progress?.status ?? null;
  const terminal = status !== null && isTerminalJobStatus(status);

  const handleError = (err: unknown): boolean => {
    const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
    if (apiErr.unauthorized) {
      void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
      return true;
    }
    setFilesError(apiErr);
    return false;
  };

  useEffect(() => {
    if (!terminal) return;
    let cancelled = false;
    setFilesLoading(true);
    setFilesError(null);
    api
      .listJobFiles(jobId)
      .then(async (list) => {
        if (cancelled) return;
        setFiles(list.items);
        const designFile = list.items.find((f) => f.filename === 'design.json');
        if (designFile) {
          const manifest = await fetchJsonManifest<DesignManifest>(designFile);
          if (!cancelled) setDesign(manifest);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        handleError(err);
      })
      .finally(() => {
        if (!cancelled) setFilesLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, terminal]);

  const downloadFile = async (file: FileObject) => {
    try {
      const { blob, filename } = await fetchFileBlob(file.id, file.filename);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      handleError(err);
    }
  };

  const meta = design?.material_estimate;

  return (
    <div className="mm-panel" style={{ padding: '0.9rem' }}>
      <div
        className="mm-row"
        style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}
      >
        <strong>{generatorName || jobType}</strong>
        {status ? <JobStatusBadge status={status} /> : <span className="mm-meta">Starting…</span>}
      </div>
      <p className="mm-meta" style={{ margin: '2px 0 8px' }}>
        {jobType}
      </p>

      <div className="mm-progress">
        <div
          className="mm-progress__bar"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress?.progress_pct ?? 0}
          aria-label={`${jobType} progress`}
        >
          <div className="mm-progress__fill" style={{ width: `${progress?.progress_pct ?? 0}%` }} />
        </div>
        <p className="mm-meta" style={{ margin: 0 }} aria-live="polite">
          {progress?.progress_message || (status ? status : 'Waiting for status…')}
        </p>
      </div>

      {progress?.error_message ? (
        <p style={{ color: '#ef4444', fontSize: '0.85rem', margin: '6px 0 0' }}>
          {progress.error_message}
        </p>
      ) : null}
      {pollError ? (
        <div style={{ marginTop: 8 }}>
          <ErrorPanel message={pollError.message} technicalDetail={pollError.body} />
        </div>
      ) : null}

      {terminal ? (
        filesLoading ? (
          <p className="mm-meta" style={{ marginTop: 8 }}>
            Loading outputs…
          </p>
        ) : filesError ? (
          <div style={{ marginTop: 8 }}>
            <ErrorPanel message={filesError.message} technicalDetail={filesError.body} />
          </div>
        ) : (
          <div style={{ marginTop: 8 }}>
            {design ? (
              <div className="mm-meta" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span>Generation: {formatDuration(design.generation_duration_s)}</span>
                {meta ? (
                  <span>
                    Materials: ${(meta.filament_cost_usd ?? 0).toFixed(2)} filament + $
                    {(meta.led_kit_cost_usd ?? 0).toFixed(2)} LED kit ≈ $
                    {(meta.total_estimated_cost_usd ?? 0).toFixed(2)} total
                  </span>
                ) : null}
                {design.warnings && design.warnings.length > 0 ? (
                  <span>Warnings: {design.warnings.length}</span>
                ) : null}
              </div>
            ) : null}
            {files && files.length > 0 ? (
              <ul className="mm-list" style={{ marginTop: 6 }}>
                {files.map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      className="mm-linkish"
                      style={{
                        display: 'block',
                        width: '100%',
                        textAlign: 'left',
                        textDecoration: 'none',
                      }}
                      onClick={() => void downloadFile(f)}
                    >
                      <strong>{f.filename}</strong>
                      <div className="mm-meta">{(f.size_bytes / 1024).toFixed(1)} KiB</div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mm-meta">No output files.</p>
            )}
          </div>
        )
      ) : null}
    </div>
  );
}

export default function CompareGeneratorsPage() {
  const router = useRouter();
  const projectId = typeof router.query.id === 'string' ? router.query.id : null;
  const queryJob = typeof router.query.job === 'string' ? router.query.job : null;
  const online = useOnline();
  const { status } = useRequireAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [plugins, setPlugins] = useState<PluginRecord[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [payloadText, setPayloadText] = useState('');
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [pageError, setPageError] = useState<ApiError | null>(null);
  const [running, setRunning] = useState(false);
  const [cards, setCards] = useState<CompareJobRef[]>([]);
  const [existing, setExisting] = useState<CompareResultRow[]>([]);
  const [existingError, setExistingError] = useState<ApiError | null>(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    setPageError(null);
    try {
      const [proj, plist, jlist] = await Promise.all([
        api.getProject(projectId),
        api.listPlugins(true),
        api.listProjectJobs(projectId, 50),
      ]);
      setProject(proj);
      setPlugins(plist.items);
      setJobs(jlist.items);
      // Default input: the active job's payload (query ?job= or most recent).
      const source = jlist.items.find((j) => j.id === queryJob) ?? jlist.items[0];
      if (source) setPayloadText(JSON.stringify(source.input_payload ?? {}, null, 2));
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setPageError(apiErr);
    }
  }, [projectId, queryJob, router]);

  useEffect(() => {
    if (!router.isReady || status !== 'authenticated') return;
    void load();
  }, [router.isReady, status, load]);

  // Load any existing comparison runs for this project (most recent first).
  const loadExisting = useCallback(async () => {
    if (!projectId) return;
    try {
      const res = await api.getComparison(projectId);
      setExisting(res.results.slice(0, MAX_GENERATORS));
      setExistingError(null);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setExistingError(apiErr);
    }
  }, [projectId, router]);

  useEffect(() => {
    if (status === 'authenticated') void loadExisting();
  }, [status, loadExisting]);

  const toggleGenerator = (pluginId: string) => {
    setSelected((prev) => {
      if (prev.includes(pluginId)) return prev.filter((p) => p !== pluginId);
      if (prev.length >= MAX_GENERATORS) return prev;
      return [...prev, pluginId];
    });
  };

  const runComparison = async () => {
    if (!projectId) return;
    let payload: Record<string, unknown>;
    try {
      const parsed = JSON.parse(payloadText) as unknown;
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setPayloadError('Input payload must be a JSON object.');
        return;
      }
      payload = parsed as Record<string, unknown>;
    } catch {
      setPayloadError('Input payload is not valid JSON.');
      return;
    }
    if (selected.length === 0) {
      setPayloadError('Select at least one generator.');
      return;
    }
    setPayloadError(null);
    setPageError(null);
    setRunning(true);
    try {
      const res = await api.createComparison({
        project_id: projectId,
        input_payload: payload,
        generators: selected,
      });
      setCards(res.jobs);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setPageError(apiErr);
    } finally {
      setRunning(false);
    }
  };

  const generatorName = (pluginId: string) =>
    plugins.find((p) => p.plugin_id === pluginId)?.name;

  if (status !== 'authenticated') {
    return (
      <AppShell title="Compare generators">
        <LoadingState title="Checking session…" />
      </AppShell>
    );
  }

  if (!online) {
    return (
      <AppShell title="Compare generators">
        <OfflineState
          title="You are offline"
          description="Reconnect to run and poll comparisons."
          actionLabel="Retry"
          onAction={() => void load()}
        />
      </AppShell>
    );
  }

  if (!projectId) {
    return (
      <AppShell title="Compare generators">
        <LoadingState title="Opening project…" />
      </AppShell>
    );
  }

  if (!project && !pageError) {
    return (
      <AppShell title="Compare generators">
        <LoadingState title="Loading project…" />
      </AppShell>
    );
  }

  if (!project && pageError) {
    return (
      <AppShell title="Compare generators">
        <ErrorPanel
          message={pageError.message}
          technicalDetail={pageError.body}
          onRetry={() => void load()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell title="Compare generators">
      <Head>
        <title>Compare generators · ModuMesh MakerLab</title>
      </Head>

      <p className="mm-meta" style={{ margin: 0 }}>
        <Link href={`/projects/${projectId}`}>← Back to project</Link>
      </p>
      <h1 className="mm-h1" style={{ fontSize: '1.45rem' }}>
        Compare generators
      </h1>
      <p className="mm-meta">
        Run the same input through up to {MAX_GENERATORS} generators and compare their outputs.
      </p>

      {pageError ? (
        <div style={{ marginBottom: '0.75rem' }}>
          <ErrorPanel message={pageError.message} technicalDetail={pageError.body} onRetry={() => void load()} />
        </div>
      ) : null}

      <div className="mm-panel" style={{ marginTop: '0.75rem' }}>
        <h2>Input payload</h2>
        <p className="mm-meta">
          Shared across all selected generators. Defaults to the active job&apos;s payload.
        </p>
        <textarea
          className="mm-input"
          rows={8}
          value={payloadText}
          onChange={(e) => setPayloadText(e.target.value)}
          spellCheck={false}
          aria-label="Comparison input payload (JSON)"
        />
        {payloadError ? (
          <p style={{ color: '#ef4444', fontSize: '0.85rem', margin: '6px 0 0' }}>{payloadError}</p>
        ) : null}
        <div className="mm-row" style={{ gap: 8, marginTop: '0.5rem' }}>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              const source = jobs.find((j) => j.id === queryJob) ?? jobs[0];
              if (source) setPayloadText(JSON.stringify(source.input_payload ?? {}, null, 2));
            }}
          >
            Reset to last job payload
          </Button>
        </div>
      </div>

      <div className="mm-panel" style={{ marginTop: '0.75rem' }}>
        <h2>
          Generators ({selected.length}/{MAX_GENERATORS})
        </h2>
        {plugins.length === 0 ? (
          <EmptyState
            title="No enabled generators"
            description="Install plugins from the catalog first."
            actionLabel="Browse catalog"
            onAction={() => void router.push('/generators')}
          />
        ) : (
          <>
            <ul className="mm-list">
              {plugins.map((p) => (
                <li key={p.plugin_id}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selected.includes(p.plugin_id)}
                      onChange={() => toggleGenerator(p.plugin_id)}
                      disabled={running}
                    />
                    <span>
                      <strong>{p.name}</strong>{' '}
                      <span className="mm-meta">
                        {p.plugin_id}@{p.version}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            {selected.length >= MAX_GENERATORS ? (
              <p className="mm-meta">Maximum {MAX_GENERATORS} generators selected.</p>
            ) : null}
            <Button
              variant="primary"
              size="sm"
              onClick={() => void runComparison()}
              disabled={running || selected.length === 0}
            >
              {running ? 'Starting jobs…' : 'Run comparison'}
            </Button>
          </>
        )}
      </div>

      {cards.length > 0 ? (
        <section style={{ marginTop: '0.75rem' }}>
          <h2>Comparison runs</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {cards.map((c) => (
              <CompareJobCard
                key={c.job_id}
                jobId={c.job_id}
                jobType={c.generator}
                generatorName={generatorName(c.generator)}
              />
            ))}
          </div>
        </section>
      ) : null}

      {existing.length > 0 ? (
        <section style={{ marginTop: '0.75rem' }}>
          <h2>Recent runs</h2>
          <p className="mm-meta">Most recent jobs for this project from the comparison history.</p>
          {existingError ? (
            <div style={{ marginBottom: '0.5rem' }}>
              <ErrorPanel
                message={existingError.message}
                technicalDetail={existingError.body}
                onRetry={() => void loadExisting()}
              />
            </div>
          ) : null}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {existing.map((r) => (
              <CompareJobCard
                key={r.id}
                jobId={r.id}
                jobType={r.job_type}
                generatorName={generatorName(r.job_type)}
              />
            ))}
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}
