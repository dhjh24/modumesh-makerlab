import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import type { Job, PluginRecord, Project } from '@modumesh/shared-types';
import {
  Button,
  EmptyState,
  ErrorPanel,
  JobStatusBadge,
  LoadingState,
  OfflineState,
  RetryState,
} from '@modumesh/ui';
import { AppShell } from '../components/AppShell';
import { api, ApiError } from '../lib/api';
import { formatRelativeTime, useOnline, useRequireAuth } from '../lib/hooks';

export default function HomePage() {
  const router = useRouter();
  const online = useOnline();
  const { status } = useRequireAuth();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [plugins, setPlugins] = useState<PluginRecord[] | null>(null);
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const load = useCallback(async () => {
    setError(null);
    try {
      const [p, g, j] = await Promise.all([
        api.listProjects(12),
        api.listPlugins(true),
        api.listRecentJobs(),
      ]);
      setProjects(p.items);
      setPlugins(g.items);
      setJobs(j);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
      if (apiErr.unauthorized) {
        // Token expired mid-session — apiFetch already cleared it.
        void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
        return;
      }
      setError(apiErr);
    }
  }, [router]);

  useEffect(() => {
    if (status !== 'authenticated') return;
    void load();
  }, [load, status]);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const project = await api.createProject({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      await router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
      setCreating(false);
    }
  };

  if (status !== 'authenticated') {
    return (
      <AppShell title="Home">
        <LoadingState title="Checking session…" />
      </AppShell>
    );
  }

  if (!online) {
    return (
      <AppShell title="Offline">
        <OfflineState
          title="You are offline"
          description="Reconnect to load projects, generators, and job activity."
          actionLabel="Retry"
          onAction={() => void load()}
        />
      </AppShell>
    );
  }

  return (
    <AppShell title="Home">
      <Head>
        <title>ModuMesh MakerLab</title>
        <meta name="description" content="Schema-driven generators, queued jobs, and 3D preview." />
      </Head>

      <h1 className="mm-h1">ModuMesh MakerLab</h1>
      <p className="mm-lead">
        Pick a generator, tune parameters from its schema, queue a job, and inspect the result.
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

      <div className="mm-grid-3" style={{ marginTop: '1rem' }}>
        <section className="mm-panel" aria-labelledby="recent-projects">
          <h2 id="recent-projects">Recent projects</h2>
          {projects === null && !error ? (
            <LoadingState title="Loading projects…" />
          ) : projects && projects.length === 0 ? (
            <EmptyState
              title="No projects yet"
              description="Create a project to start generating."
            />
          ) : (
            <ul className="mm-list">
              {projects?.map((p) => (
                <li key={p.id}>
                  <Link href={`/projects/${p.id}`}>
                    <strong>{p.name}</strong>
                    <div className="mm-meta">{formatRelativeTime(p.updated_at)}</div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="mm-panel" aria-labelledby="create-project">
          <h2 id="create-project">Create project</h2>
          <form className="mm-inline-form" onSubmit={onCreate}>
            <div className="mm-field">
              <label className="mm-field__label" htmlFor="project-name">
                Name
              </label>
              <input
                id="project-name"
                className="mm-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={255}
                disabled={creating}
              />
            </div>
            <div className="mm-field">
              <label className="mm-field__label" htmlFor="project-desc">
                Description
              </label>
              <textarea
                id="project-desc"
                className="mm-input"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={creating}
              />
            </div>
            <Button type="submit" disabled={creating || !name.trim()}>
              {creating ? 'Creating…' : 'Create project'}
            </Button>
          </form>
        </section>

        <section className="mm-panel" aria-labelledby="generators">
          <h2 id="generators">Generator catalog</h2>
          {plugins === null && !error ? (
            <LoadingState title="Loading generators…" />
          ) : plugins && plugins.length === 0 ? (
            <EmptyState
              title="No plugins discovered"
              description="Install a compatible plugin under /plugins and resync the registry."
            />
          ) : (
            <>
              <ul className="mm-list">
                {plugins?.slice(0, 6).map((g) => (
                  <li key={`${g.plugin_id}@${g.version}`}>
                    <Link href={`/generators?plugin=${encodeURIComponent(g.plugin_id)}`}>
                      <strong>{g.name}</strong>
                      <div className="mm-meta">
                        {g.plugin_id} · v{g.version}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: '0.75rem' }}>
                <Link href="/generators">Browse all generators</Link>
              </div>
            </>
          )}
        </section>
      </div>

      <section className="mm-panel" style={{ marginTop: '1rem' }} aria-labelledby="job-activity">
        <h2 id="job-activity">Job activity</h2>
        {jobs === null && !error ? (
          <LoadingState title="Loading jobs…" />
        ) : jobs && jobs.length === 0 ? (
          <EmptyState
            title="No jobs yet"
            description="Submit a generation from a project editor."
          />
        ) : jobs === null && error ? (
          <RetryState
            title="Could not load jobs"
            actionLabel="Retry"
            onAction={() => void load()}
          />
        ) : (
          <ul className="mm-list">
            {jobs?.map((job) => (
              <li key={job.id}>
                <Link href={`/projects/${job.project_id}?job=${job.id}`}>
                  <div className="mm-row">
                    <strong>{job.job_type}</strong>
                    <JobStatusBadge status={job.status} />
                  </div>
                  <div className="mm-meta">
                    {formatRelativeTime(job.created_at)}
                    {job.progress_message ? ` · ${job.progress_message}` : ''}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}
