import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useState } from 'react';
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
import { api, ApiError, fileDownloadUrl } from '../../lib/api';
import { formatRelativeTime, newIdempotencyKey, useJobPolling, useOnline } from '../../lib/hooks';

type MobileTab = 'parameters' | 'preview' | 'project';

export default function ProjectEditorPage() {
  const router = useRouter();
  const projectId = typeof router.query.id === 'string' ? router.query.id : null;
  const queryPlugin = typeof router.query.plugin === 'string' ? router.query.plugin : null;
  const queryJob = typeof router.query.job === 'string' ? router.query.job : null;
  const online = useOnline();

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
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
    }
  }, [projectId, queryPlugin, queryJob]);

  useEffect(() => {
    if (!router.isReady) return;
    void load();
  }, [router.isReady, load]);

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
            setPreviewSrc(fileDownloadUrl(viewable.id));
            setPreviewFormat(fmt);
            setMobileTab('preview');
          }
        }
      })();
    }
  }, [progress, projectId]);

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
    setPreviewSrc(`/fixtures/sample-cube.${kind}`);
    setPreviewFormat(kind);
    setMobileTab('preview');
    setStatusMessage(`Loaded fixture ${kind.toUpperCase()}`);
  };

  const openFile = (file: FileObject) => {
    const fmt = inferModelFormat(file.filename, file.content_type);
    if (fmt) {
      setPreviewSrc(fileDownloadUrl(file.id));
      setPreviewFormat(fmt);
      setMobileTab('preview');
      setStatusMessage(`Previewing ${file.filename}`);
    } else {
      window.open(fileDownloadUrl(file.id), '_blank', 'noopener,noreferrer');
    }
  };

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
