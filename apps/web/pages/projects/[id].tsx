import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  inferModelFormat,
  isTerminalJobStatus,
  isViewableFilename,
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
  SchemaForm,
  defaultsFromSchema,
} from '@modumesh/ui';
import { AppShell } from '../../components/AppShell';
import { LazyModelViewer } from '../../components/LazyModelViewer';
import {
  api,
  ApiError,
  fetchFileBlob,
  type DesignManifest,
  type JobPricing,
  type ShopHandoffResponse,
  type SlicingReport,
} from '../../lib/api';
import {
  formatDuration,
  formatRelativeTime,
  newIdempotencyKey,
  useJobPolling,
  useOnline,
  useRequireAuth,
} from '../../lib/hooks';

type MobileTab = 'parameters' | 'preview' | 'project';

export default function ProjectEditorPage() {
  const router = useRouter();
  const projectId = typeof router.query.id === 'string' ? router.query.id : null;
  const queryPlugin = typeof router.query.plugin === 'string' ? router.query.plugin : null;
  const queryJob = typeof router.query.job === 'string' ? router.query.job : null;
  const online = useOnline();
  const { status } = useRequireAuth();

  const [project, setProject] = useState<Project | null>(null);
  const [plugins, setPlugins] = useState<PluginRecord[]>([]);
  const [pluginId, setPluginId] = useState<string>('');
  const [formValue, setFormValue] = useState<Record<string, unknown>>({});
  const [jobs, setJobs] = useState<Job[]>([]);
  const [files, setFiles] = useState<FileObject[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [mobileTab, setMobileTab] = useState<MobileTab>('parameters');
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [previewFormat, setPreviewFormat] = useState<'stl' | 'glb' | null>(null);
  const [fixtureChoice, setFixtureChoice] = useState<'stl' | 'glb'>('stl');
  const [statusMessage, setStatusMessage] = useState('Ready');

  // Blob object URL backing the current preview. Revoked before replacement
  // and on unmount so we never leak browser memory.
  const previewUrlRef = useRef<string | null>(null);
  const previewLoadingRef = useRef(false);

  const revokePreviewUrl = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  }, []);

  // Revoke any live blob URL when the component unmounts.
  useEffect(() => revokePreviewUrl, [revokePreviewUrl]);

  /** Fetch a protected file with the bearer token and show it via a blob: URL. */
  const loadPreview = useCallback(
    async (fileId: string, filename: string) => {
      if (previewLoadingRef.current) return; // guard against stacked double-clicks
      previewLoadingRef.current = true;
      try {
        const { blob } = await fetchFileBlob(fileId, filename);
        const url = URL.createObjectURL(blob);
        // Replace: revoke the previous blob URL before handing out a new one.
        revokePreviewUrl();
        previewUrlRef.current = url;
        setPreviewSrc(url);
      } catch (err) {
        const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
        if (apiErr.unauthorized) {
          // Token expired mid-session — fetchFileBlob already cleared it.
          void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
          return;
        }
        setError(apiErr);
      } finally {
        previewLoadingRef.current = false;
      }
    },
    [revokePreviewUrl, router],
  );

  /** Fetch a protected file and trigger a browser download with its real name. */
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
      setStatusMessage(`Downloaded ${filename}`);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setError(apiErr);
    }
  };

  const selectedPlugin = useMemo(
    () => plugins.find((p) => p.plugin_id === pluginId) ?? null,
    [plugins, pluginId],
  );

  const { progress, error: pollError } = useJobPolling(activeJobId);

  const load = useCallback(async () => {
    if (!projectId) return;
    setError(null);
    try {
      const [proj, plist, jlist, flist] = await Promise.all([
        api.getProject(projectId),
        api.listPlugins(true),
        api.listProjectJobs(projectId, 50),
        api.listProjectFiles(projectId),
      ]);
      setProject(proj);
      setProjectName(proj.name);
      setProjectDesc(proj.description || '');
      setPlugins(plist.items);
      setJobs(jlist.items);
      setFiles(flist.items);

      const preferred =
        queryPlugin ||
        jlist.items[0]?.job_type ||
        plist.items.find((p) => p.plugin_id === 'fixture-mesh')?.plugin_id ||
        plist.items[0]?.plugin_id ||
        '';
      setPluginId(preferred);

      const initialJob = queryJob || jlist.items[0]?.id || null;
      setActiveJobId(initialJob);
      setStatusMessage('Project loaded');
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        // Token expired mid-session — apiFetch already cleared it.
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setError(apiErr);
    }
  }, [projectId, queryPlugin, queryJob, router]);

  useEffect(() => {
    if (!router.isReady || status !== 'authenticated') return;
    void load();
  }, [router.isReady, status, load]);

  // Any 401 surfaced by the polling hook (token expired mid-session) should
  // bounce to the login page rather than spin in the error panel.
  useEffect(() => {
    const err = error || pollError;
    if (err instanceof ApiError && err.unauthorized) {
      void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
    }
  }, [error, pollError, router]);

  useEffect(() => {
    if (!selectedPlugin) return;
    setFormValue(defaultsFromSchema(selectedPlugin.input_schema));
  }, [selectedPlugin?.plugin_id, selectedPlugin?.version]);

  useEffect(() => {
    if (!progress) return;
    setStatusMessage(
      `${progress.status}${progress.progress_message ? ` — ${progress.progress_message}` : ''} (${progress.progress_pct}%)`,
    );
    setJobs((prev) =>
      prev.map((j) =>
        j.id === progress.id
          ? {
              ...j,
              status: progress.status,
              progress_pct: progress.progress_pct,
              progress_message: progress.progress_message,
              error_message: progress.error_message,
              cancel_requested: progress.cancel_requested,
              updated_at: progress.updated_at,
            }
          : j,
      ),
    );
    if (isTerminalJobStatus(progress.status) && projectId) {
      void (async () => {
        const [jlist, flist] = await Promise.all([
          api.listProjectJobs(projectId, 50),
          api.listProjectFiles(projectId),
        ]);
        setJobs(jlist.items);
        setFiles(flist.items);
        const viewable = flist.items.find(
          (f) => f.job_id === progress.id && isViewableFilename(f.filename),
        );
        if (viewable) {
          const fmt = inferModelFormat(viewable.filename, viewable.content_type);
          if (fmt) {
            setPreviewFormat(fmt);
            setMobileTab('preview');
            void loadPreview(viewable.id, viewable.filename);
          }
        }
      })();
    }
  }, [progress, projectId, loadPreview]);

  const saveProject = async () => {
    if (!projectId) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateProject(projectId, {
        name: projectName.trim(),
        description: projectDesc.trim() || undefined,
      });
      setProject(updated);
      setStatusMessage('Project saved');
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
    } finally {
      setSaving(false);
    }
  };

  const submitJob = async (value: Record<string, unknown>) => {
    if (!projectId || !selectedPlugin) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await api.createJob(
        projectId,
        {
          job_type: selectedPlugin.plugin_id,
          input_payload: value,
          timeout_seconds: selectedPlugin.timeout_seconds,
          plugin_version: selectedPlugin.version,
        },
        newIdempotencyKey(),
      );
      setActiveJobId(job.id);
      setJobs((prev) => [job, ...prev.filter((j) => j.id !== job.id)]);
      setStatusMessage(`Job ${job.status}`);
      await router.replace(
        {
          pathname: `/projects/${projectId}`,
          query: { plugin: selectedPlugin.plugin_id, job: job.id },
        },
        undefined,
        { shallow: true },
      );
      setMobileTab('project');
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
    } finally {
      setSubmitting(false);
    }
  };

  const cancelActive = async () => {
    if (!activeJobId) return;
    try {
      await api.cancelJob(activeJobId);
      setStatusMessage('Cancel requested');
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
    }
  };

  const loadFixture = (kind: 'stl' | 'glb') => {
    setFixtureChoice(kind);
    revokePreviewUrl(); // drop any blob-backed preview before swapping in the fixture
    setPreviewSrc(`/fixtures/sample-cube.${kind}`);
    setPreviewFormat(kind);
    setMobileTab('preview');
    setStatusMessage(`Loaded fixture ${kind.toUpperCase()}`);
  };

  const openFile = (file: FileObject) => {
    const fmt = inferModelFormat(file.filename, file.content_type);
    if (fmt) {
      setPreviewFormat(fmt);
      setMobileTab('preview');
      setStatusMessage(`Previewing ${file.filename}`);
      void loadPreview(file.id, file.filename);
    } else {
      void downloadFile(file);
    }
  };

  if (status !== 'authenticated') {
    return (
      <AppShell title="Editor">
        <LoadingState title="Checking session…" />
      </AppShell>
    );
  }

  if (!online) {
    return (
      <AppShell title="Editor">
        <OfflineState
          title="You are offline"
          description="Reconnect to save projects and poll jobs."
          actionLabel="Retry"
          onAction={() => void load()}
        />
      </AppShell>
    );
  }

  if (!projectId) {
    return (
      <AppShell title="Editor">
        <LoadingState title="Opening project…" />
      </AppShell>
    );
  }

  if (!project && !error) {
    return (
      <AppShell title="Editor">
        <LoadingState title="Loading project…" />
      </AppShell>
    );
  }

  if (!project && error) {
    return (
      <AppShell title="Editor">
        <ErrorPanel
          message={error.message}
          technicalDetail={error.body}
          onRetry={() => void load()}
        />
      </AppShell>
    );
  }

  const activeJob = jobs.find((j) => j.id === activeJobId) || null;
  const pct = progress?.progress_pct ?? activeJob?.progress_pct ?? 0;

  return (
    <AppShell title={project?.name || 'Editor'}>
      <Head>
        <title>{project?.name || 'Project'} · ModuMesh MakerLab</title>
      </Head>

      <div className="mm-row" style={{ justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <div>
          <p className="mm-meta" style={{ margin: 0 }}>
            <Link href="/">Home</Link> / Project
          </p>
          <h1 className="mm-h1" style={{ fontSize: '1.45rem' }}>
            {project?.name}
          </h1>
        </div>
        <div className="mm-row">
          <Button variant="secondary" size="sm" onClick={() => loadFixture('stl')}>
            Fixture STL
          </Button>
          <Button variant="secondary" size="sm" onClick={() => loadFixture('glb')}>
            Fixture GLB
          </Button>
        </div>
      </div>

      {error || pollError ? (
        <div style={{ marginBottom: '0.75rem' }}>
          <ErrorPanel
            message={(error || pollError)!.message}
            technicalDetail={[
              (error || pollError)!.correlationId
                ? `correlation_id=${(error || pollError)!.correlationId}`
                : null,
              `status=${(error || pollError)!.status}`,
              (error || pollError)!.body,
            ]
              .filter(Boolean)
              .join('\n')}
            onRetry={() => void load()}
          />
        </div>
      ) : null}

      <div className="mm-tabs" role="tablist" aria-label="Editor sections">
        {(
          [
            ['parameters', 'Parameters'],
            ['preview', 'Preview'],
            ['project', 'Project / Files'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={mobileTab === id}
            onClick={() => setMobileTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="mm-editor">
        <section
          className={`mm-panel mm-editor__params mm-editor__pane ${mobileTab === 'parameters' ? 'is-active' : ''}`}
          aria-label="Parameters"
        >
          <h2>Parameters</h2>
          <div className="mm-field">
            <label className="mm-field__label" htmlFor="plugin-select">
              Generator
            </label>
            <select
              id="plugin-select"
              className="mm-input"
              value={pluginId}
              onChange={(e) => setPluginId(e.target.value)}
            >
              {plugins.map((p) => (
                <option key={p.plugin_id} value={p.plugin_id}>
                  {p.name} (v{p.version})
                </option>
              ))}
            </select>
          </div>
          {selectedPlugin ? (
            <SchemaForm
              schema={selectedPlugin.input_schema}
              value={formValue}
              onChange={setFormValue}
              onSubmit={submitJob}
              submitLabel={submitting ? 'Submitting…' : 'Generate'}
              disabled={submitting}
              idPrefix="editor"
            />
          ) : (
            <EmptyState
              title="No generator selected"
              description="Install plugins or pick one from the catalog."
              actionLabel="Browse catalog"
              onAction={() => void router.push('/generators')}
            />
          )}
        </section>

        <section
          className={`mm-panel mm-editor__viewer mm-editor__pane ${mobileTab === 'preview' ? 'is-active' : ''}`}
          aria-label="3D preview"
          style={{ padding: 0, overflow: 'hidden' }}
        >
          {previewSrc && previewFormat ? (
            <LazyModelViewer
              src={previewSrc}
              format={previewFormat}
              ariaLabel={`${fixtureChoice.toUpperCase()} model preview`}
            />
          ) : (
            <div style={{ padding: '1rem' }}>
              <EmptyState
                title="No model loaded"
                description="Generate a fixture-mesh job, open a mesh file, or load a packaged STL/GLB fixture."
                actionLabel="Load sample STL"
                onAction={() => loadFixture('stl')}
              />
            </div>
          )}
        </section>

        <section
          className={`mm-panel mm-editor__side mm-editor__pane ${mobileTab === 'project' ? 'is-active' : ''}`}
          aria-label="Project, versions, and files"
        >
          <h2>Project</h2>
          <div className="mm-inline-form">
            <div className="mm-field">
              <label className="mm-field__label" htmlFor="edit-name">
                Name
              </label>
              <input
                id="edit-name"
                className="mm-input"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </div>
            <div className="mm-field">
              <label className="mm-field__label" htmlFor="edit-desc">
                Description
              </label>
              <textarea
                id="edit-desc"
                className="mm-input"
                rows={2}
                value={projectDesc}
                onChange={(e) => setProjectDesc(e.target.value)}
              />
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void saveProject()}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Save project'}
            </Button>
          </div>

          <h2 style={{ marginTop: '1.25rem' }}>Version history</h2>
          <p className="mm-meta">Each job attempt is an immutable version of this project.</p>
          {jobs.length === 0 ? (
            <EmptyState
              title="No versions yet"
              description="Submit a generation to create history."
            />
          ) : (
            <ul className="mm-list">
              {jobs.map((job) => (
                <li key={job.id}>
                  <button
                    type="button"
                    className="mm-linkish"
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      padding: '0.45rem 0.5rem',
                      background: job.id === activeJobId ? 'var(--mm-accent-soft)' : 'transparent',
                      borderRadius: 8,
                      textDecoration: 'none',
                    }}
                    onClick={() => {
                      setActiveJobId(job.id);
                      setStatusMessage(`Selected version attempt #${job.attempt_number}`);
                    }}
                  >
                    <div className="mm-row">
                      <strong>
                        {job.job_type} #{job.attempt_number}
                      </strong>
                      <JobStatusBadge status={job.status} />
                    </div>
                    <div className="mm-meta">{formatRelativeTime(job.created_at)}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h2 style={{ marginTop: '1.25rem' }}>Files</h2>
          {files.length === 0 ? (
            <EmptyState title="No files" description="Completed jobs attach outputs here." />
          ) : (
            <ul className="mm-list">
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
                    onClick={() => openFile(f)}
                  >
                    <strong>{f.filename}</strong>
                    <div className="mm-meta">
                      {f.content_type} · {(f.size_bytes / 1024).toFixed(1)} KiB
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {plugins.length >= 2 ? (
            <div style={{ marginTop: '1.25rem' }}>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  void router.push(
                    `/projects/${projectId}/compare${
                      activeJobId ? `?job=${encodeURIComponent(activeJobId)}` : ''
                    }`,
                  )
                }
              >
                Compare generators
              </Button>
            </div>
          ) : null}

          {activeJob && isTerminalJobStatus(activeJob.status) ? (
            <JobResultPanel job={activeJob} />
          ) : null}
        </section>

        <section className="mm-panel mm-editor__status" aria-label="Job status">
          <div className="mm-progress">
            <div className="mm-row" style={{ justifyContent: 'space-between' }}>
              <div className="mm-row">
                <strong>Status</strong>
                {activeJob ? (
                  <JobStatusBadge status={progress?.status || activeJob.status} />
                ) : null}
              </div>
              <div className="mm-row">
                {activeJob && !isTerminalJobStatus(progress?.status || activeJob.status) ? (
                  <Button variant="danger" size="sm" onClick={() => void cancelActive()}>
                    Cancel
                  </Button>
                ) : null}
                {activeJob && (progress?.status === 'failed' || activeJob.status === 'failed') ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      void api.retryJob(activeJob.id).then((j) => setActiveJobId(j.id))
                    }
                  >
                    Retry
                  </Button>
                ) : null}
              </div>
            </div>
            <div
              className="mm-progress__bar"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              aria-label="Job progress"
            >
              <div className="mm-progress__fill" style={{ width: `${pct}%` }} />
            </div>
            <p className="mm-meta" style={{ margin: 0 }} aria-live="polite">
              {statusMessage}
            </p>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

// ── Job result workspace (GM-11) ───────────────────────────────────────
// Renders the active job's outputs below the Files list: validation report
// from design.json, slicer panel from slicing-report.json (when present),
// and pricing + shop handoff with gate status. Only mounted for terminal
// jobs; every protected fetch goes through apiFetch/fetchFileBlob.

/** Fetch a protected JSON manifest and parse it; degrades to null. */
async function fetchJsonManifest<T>(file: FileObject): Promise<T | null> {
  try {
    const { blob } = await fetchFileBlob(file.id, file.filename);
    return JSON.parse(await blob.text()) as T;
  } catch {
    return null;
  }
}

function JobResultPanel({ job }: { job: Job }) {
  const router = useRouter();
  // Guards against stale async writes when the active job changes mid-fetch.
  const activeJobIdRef = useRef<string | null>(null);
  const [filesLoading, setFilesLoading] = useState(true);
  const [filesError, setFilesError] = useState<ApiError | null>(null);
  const [design, setDesign] = useState<DesignManifest | null>(null);
  const [slice, setSlice] = useState<SlicingReport | null>(null);
  const [pricing, setPricing] = useState<JobPricing | null>(null);
  const [pricingLoading, setPricingLoading] = useState(false);
  const [pricingError, setPricingError] = useState<ApiError | null>(null);
  const [handoff, setHandoff] = useState<ShopHandoffResponse | null>(null);
  const [handoffLoading, setHandoffLoading] = useState(false);
  const [handoffError, setHandoffError] = useState<ApiError | null>(null);

  const toApiError = (err: unknown): ApiError =>
    err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));

  const handleError = (err: unknown, set: (e: ApiError) => void): boolean => {
    const apiErr = toApiError(err);
    if (apiErr.unauthorized) {
      void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
      return true;
    }
    set(apiErr);
    return false;
  };

  /** Fetch the job's output files and parse design.json / slicing-report.json. */
  const loadOutputs = async (jobId: string) => {
    activeJobIdRef.current = jobId;
    setFilesLoading(true);
    setFilesError(null);
    try {
      const list = await api.listJobFiles(jobId);
      if (activeJobIdRef.current !== jobId) return; // stale — a newer job took over
      const designFile = list.items.find((f) => f.filename === 'design.json');
      const sliceFile = list.items.find((f) => f.filename === 'slicing-report.json');
      // Both manifests are protected: parse them via fetchFileBlob (never a
      // bare URL). A missing/unparseable manifest degrades to an empty
      // sub-block rather than failing the whole panel.
      const [parsedDesign, parsedSlice] = await Promise.all([
        designFile ? fetchJsonManifest<DesignManifest>(designFile) : Promise.resolve(null),
        sliceFile ? fetchJsonManifest<SlicingReport>(sliceFile) : Promise.resolve(null),
      ]);
      if (activeJobIdRef.current !== jobId) return;
      setDesign(parsedDesign);
      setSlice(parsedSlice);
    } catch (err) {
      if (activeJobIdRef.current !== jobId) return;
      handleError(err, setFilesError);
    } finally {
      if (activeJobIdRef.current === jobId) setFilesLoading(false);
    }
  };

  // Reload outputs when the active job changes to another terminal job.
  useEffect(() => {
    setFilesLoading(true);
    setFilesError(null);
    setDesign(null);
    setSlice(null);
    setPricing(null);
    setPricingError(null);
    setHandoff(null);
    setHandoffError(null);
    void loadOutputs(job.id);
    return () => {
      if (activeJobIdRef.current === job.id) activeJobIdRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.id]);

  const getPrice = async () => {
    setPricingLoading(true);
    setPricingError(null);
    try {
      setPricing(await api.getJobPricing(job.project_id, job.id));
    } catch (err) {
      handleError(err, setPricingError);
    } finally {
      setPricingLoading(false);
    }
  };

  const sendToShop = async () => {
    setHandoffLoading(true);
    setHandoffError(null);
    try {
      setHandoff(await api.createShopHandoff(job.project_id, job.id));
    } catch (err) {
      handleError(err, setHandoffError);
    } finally {
      setHandoffLoading(false);
    }
  };

  const metaColumn: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
    margin: '4px 0 0',
  };

  const meta = design?.material_estimate;
  const gatePricing = meta ? 'passed' : 'blocked';
  const gateHandoff = job.status === 'completed' ? 'passed' : 'blocked';

  return (
    <>
      <h2 style={{ marginTop: '1.25rem' }}>Job results</h2>
      <p className="mm-meta">
        Outputs and analysis for {job.job_type} #{job.attempt_number}.
      </p>

      {filesLoading ? (
        <LoadingState title="Loading job outputs…" />
      ) : filesError ? (
        <ErrorPanel
          message={filesError.message}
          technicalDetail={filesError.body}
          onRetry={() => void loadOutputs(job.id)}
        />
      ) : (
        <>
          <h3 style={{ margin: '0.75rem 0 0.25rem', fontSize: '1rem' }}>Validation report</h3>
          {design ? (
            <>
              <div className="mm-meta" style={metaColumn}>
                <span>Generation time: {formatDuration(design.generation_duration_s)}</span>
                {design.generated_at ? (
                  <span>Generated: {new Date(design.generated_at).toLocaleString()}</span>
                ) : null}
                {meta ? (
                  <span>
                    Materials: ${(meta.filament_cost_usd ?? 0).toFixed(2)} filament + $
                    {(meta.led_kit_cost_usd ?? 0).toFixed(2)} LED kit ≈ $
                    {(meta.total_estimated_cost_usd ?? 0).toFixed(2)} total
                  </span>
                ) : null}
              </div>
              {(design.warnings ?? []).length > 0 ? (
                <ul className="mm-list" style={{ marginTop: '0.4rem' }}>
                  {design.warnings!.map((w, i) => (
                    <li key={i} className="mm-meta">
                      {w}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mm-meta" style={{ marginTop: '0.4rem' }}>
                  No warnings.
                </p>
              )}
            </>
          ) : (
            <EmptyState
              title="No validation report"
              description="design.json was not produced by this job."
            />
          )}

          {slice ? (
            <>
              <h3 style={{ margin: '0.75rem 0 0.25rem', fontSize: '1rem' }}>Slicer</h3>
              <div className="mm-meta" style={metaColumn}>
                <span>Printer: {slice.slice?.printer_profile ?? 'n/a'}</span>
                <span>
                  Nozzle: {slice.slice?.nozzle_mm ?? 'n/a'} mm · Layer:{' '}
                  {slice.slice?.layer_height_mm ?? 'n/a'} mm
                </span>
                <span>
                  Infill: {slice.slice?.infill_pct ?? 'n/a'}% · Supports:{' '}
                  {String(slice.slice?.supports ?? 'n/a')} · Material:{' '}
                  {slice.slice?.material ?? 'n/a'}
                </span>
                <span>Print time: {slice.estimated?.print_time_estimate ?? 'n/a'}</span>
                <span>
                  Filament: {slice.estimated?.filament_length_mm ?? 'n/a'} mm ·{' '}
                  {slice.estimated?.filament_weight_g ?? 'n/a'} g
                </span>
              </div>
            </>
          ) : null}

          <h3 style={{ margin: '0.75rem 0 0.25rem', fontSize: '1rem' }}>Pricing &amp; shop</h3>
          <div className="mm-meta" style={metaColumn}>
            <span>
              Pricing gate:{' '}
              {gatePricing === 'passed'
                ? 'material estimate available'
                : 'no material estimate — pricing will return 400 with the reason'}
            </span>
            <span>
              Shop handoff gate:{' '}
              {gateHandoff === 'passed'
                ? 'job completed'
                : `job status is "${job.status}" — handoff requires "completed" (400: Job must be completed)`}
            </span>
          </div>
          <div className="mm-row" style={{ gap: 8, marginTop: '0.5rem', flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void getPrice()}
              disabled={pricingLoading}
            >
              {pricingLoading ? 'Pricing…' : pricing ? 'Refresh price' : 'Get price'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void sendToShop()}
              disabled={handoffLoading}
            >
              {handoffLoading ? 'Sending…' : 'Send to shop'}
            </Button>
          </div>

          {pricingError ? (
            <div style={{ marginTop: '0.5rem' }}>
              <ErrorPanel
                message={pricingError.message}
                technicalDetail={pricingError.body}
                onRetry={() => void getPrice()}
              />
            </div>
          ) : null}

          {pricing ? (
            <div className="mm-meta" style={metaColumn}>
              <div className="mm-row" style={{ justifyContent: 'space-between' }}>
                <span>Materials</span>
                <strong>${pricing.price_breakdown.materials.toFixed(2)}</strong>
              </div>
              <div className="mm-row" style={{ justifyContent: 'space-between' }}>
                <span>Labor</span>
                <strong>${pricing.price_breakdown.labor.toFixed(2)}</strong>
              </div>
              <div className="mm-row" style={{ justifyContent: 'space-between' }}>
                <span>Machine time</span>
                <strong>${pricing.price_breakdown.machine_time.toFixed(2)}</strong>
              </div>
              <div className="mm-row" style={{ justifyContent: 'space-between' }}>
                <span>Shipping &amp; handling</span>
                <strong>${pricing.price_breakdown.shipping_handling.toFixed(2)}</strong>
              </div>
              <div className="mm-row" style={{ justifyContent: 'space-between' }}>
                <span>Markup ({pricing.markup_pct}%)</span>
                <strong>${pricing.markup_amount.toFixed(2)}</strong>
              </div>
              <div className="mm-row" style={{ justifyContent: 'space-between' }}>
                <span>Total</span>
                <strong>
                  {pricing.currency} {pricing.total.toFixed(2)}
                </strong>
              </div>
              {pricing.includes.length > 0 ? (
                <ul className="mm-list" style={{ marginTop: '0.4rem' }}>
                  {pricing.includes.map((inc) => (
                    <li key={inc} className="mm-meta">
                      {inc}
                    </li>
                  ))}
                </ul>
              ) : null}
              {pricing.disclaimer ? <span>{pricing.disclaimer}</span> : null}
            </div>
          ) : null}

          {handoffError ? (
            <div style={{ marginTop: '0.5rem' }}>
              <ErrorPanel
                message={handoffError.message}
                technicalDetail={handoffError.body}
                onRetry={() => void sendToShop()}
              />
            </div>
          ) : null}

          {handoff ? (
            <details style={{ marginTop: '0.5rem' }}>
              <summary className="mm-linkish">
                Shop handoff payload · {handoff.pricing.currency}{' '}
                {Number(handoff.pricing.total).toFixed(2)}
              </summary>
              <pre
                className="mm-error-panel__pre"
                style={{ marginTop: '0.4rem', fontSize: '0.75rem' }}
              >
                {JSON.stringify(handoff.handoff, null, 2)}
              </pre>
            </details>
          ) : null}
        </>
      )}
    </>
  );
}
