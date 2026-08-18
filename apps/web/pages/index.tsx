import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Button, ErrorPanel, LoadingState, OfflineState } from '@modumesh/ui';
import { AppShell } from '../components/AppShell';
import { api, ApiError } from '../lib/api';
import {
  hasClearIntentWinner,
  listMakerTools,
  resolveIntent,
  STARTER_INTENTS,
  type IntentMatch,
  type MakerTool,
} from '../lib/makerTools';
import { useOnline, useRequireAuth } from '../lib/hooks';

/**
 * Create landing (IA §4.1, W2.3).
 *
 * Prompt-first: "What do you want to make?" resolves free-text intent to a
 * maker tool via keyword matching (lib/makerTools.ts) — never a plugin
 * picker. Unambiguous intent creates a project and opens the studio with the
 * tool pre-selected; ambiguous intent offers a small visual choice; the mode
 * cards route to Explore / My Models, with AI + upload modes gated.
 */

interface ModeCard {
  icon: string;
  title: string;
  description: string;
  /** When set, the card is a link to this route. */
  href?: string;
  /** When set, the card is disabled with this badge. */
  badge?: string;
  /** Small print under a disabled card (e.g. backend gap note). */
  note?: string;
}

const MODES: ModeCard[] = [
  {
    icon: '📐',
    title: 'Parametric builder',
    description: 'Pick a maker tool — nameplates, boxes, signs — and tune the dimensions.',
    href: '/explore',
  },
  {
    icon: '📝',
    title: 'Text to 3D',
    description: 'Describe an object and get a printable model.',
    badge: 'Coming soon',
    note: 'AI modes arrive once a model service is ready.',
  },
  {
    icon: '🖼️',
    title: 'Image to 3D',
    description: 'Turn a photo into a 3D model.',
    badge: 'Coming soon',
    note: 'AI modes arrive once a model service is ready.',
  },
  {
    icon: '📤',
    title: 'Upload a model',
    description: 'Import your own STL or GLB to check and refine.',
    badge: 'Coming soon',
    note: "We're building model upload — check back soon.",
  },
  {
    icon: '🔁',
    title: 'Remix something',
    description: 'Start from something you already made.',
    href: '/models',
  },
];

/** Small tool card used by the intent suggestions and the classics row. */
function ToolPick({
  tool,
  busy,
  onMake,
}: {
  tool: MakerTool;
  busy: boolean;
  onMake: (tool: MakerTool) => void;
}) {
  return (
    <article className="mm-panel" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span aria-hidden="true" style={{ fontSize: '1.4rem', lineHeight: 1 }}>
          {tool.icon}
        </span>
        <h3 style={{ margin: 0, fontSize: '0.95rem' }}>{tool.name}</h3>
      </div>
      <p style={{ margin: 0, flex: 1, fontSize: '0.8125rem', color: '#5b6e72' }}>{tool.promise}</p>
      <Button
        onClick={() => onMake(tool)}
        disabled={busy}
        style={{ alignSelf: 'flex-start' }}
        size="sm"
      >
        {busy ? 'Setting up…' : 'Make it'}
      </Button>
    </article>
  );
}

export default function CreatePage() {
  const router = useRouter();
  const online = useOnline();
  const { status } = useRequireAuth();

  const [intent, setIntent] = useState('');
  const [submitted, setSubmitted] = useState<string | null>(null);
  const [matches, setMatches] = useState<IntentMatch[] | null>(null);
  const [busySlug, setBusySlug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [available, setAvailable] = useState<Set<string> | null>(null);

  // Which tools are actually installed, from the catalog API (same signal the
  // Explore grid uses). Availability is only a filter for the suggestion and
  // classics cards — the hero prompt works regardless.
  const loadAvailability = useCallback(async () => {
    try {
      const res = await api.listCatalog({ limit: 100 });
      setAvailable(new Set(res.items.map((i) => i.plugin_id)));
    } catch {
      setAvailable(new Set());
    }
  }, []);

  useEffect(() => {
    void loadAvailability();
  }, [loadAvailability]);

  /** Create a project with the tool pre-selected and open the studio. */
  const makeWithTool = useCallback(
    async (tool: MakerTool) => {
      setBusySlug(tool.slug);
      setError(null);
      try {
        const project = await api.createProject({
          name: `${tool.name} project`,
          description: `Made with ${tool.name}`,
        });
        await router.push(`/studio/${project.id}?tool=${encodeURIComponent(tool.slug)}`);
      } catch (err) {
        const apiErr = err instanceof ApiError ? err : new ApiError(String(err), 0, String(err));
        if (apiErr.unauthorized) {
          void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
          return;
        }
        setError(apiErr.message);
        setBusySlug(null);
      }
    },
    [router],
  );

  /** Resolve a prompt: clear winner goes straight to the studio, otherwise
   *  the page offers a small visual choice of tools (IA §4.1). */
  const runIntent = useCallback(
    (raw: string) => {
      const text = raw.trim();
      if (!text) return;
      const resolved = resolveIntent(text);
      setIntent(text);
      setSubmitted(text);
      setMatches(resolved);
      if (hasClearIntentWinner(resolved)) {
        void makeWithTool(resolved[0].tool);
      }
    },
    [makeWithTool],
  );

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    runIntent(intent);
  };

  const tools = listMakerTools();
  const suggestionTools = (matches ?? [])
    .map((m) => m.tool)
    .filter((t) => available === null || available.has(t.slug))
    .slice(0, 3);
  const classicTools = tools.filter((t) => available === null || available.has(t.slug)).slice(0, 3);

  if (status !== 'authenticated') {
    return (
      <AppShell title="Create">
        <LoadingState title="Checking session…" />
      </AppShell>
    );
  }

  return (
    <AppShell title="Create">
      <Head>
        <title>Create · ModuMesh MakerLab</title>
        <meta
          name="description"
          content="Describe what you want to make and we'll set up the right tool."
        />
      </Head>

      {/* Hero prompt */}
      <section aria-labelledby="create-hero" style={{ maxWidth: 720 }}>
        <h1 id="create-hero" className="mm-h1" style={{ fontSize: '1.9rem' }}>
          What do you want to make?
        </h1>
        <p className="mm-lead">
          Describe it in your own words, or start from a ready-made idea. We&apos;ll pick the right
          maker tool and open it in the studio.
        </p>
        <form
          onSubmit={onSubmit}
          style={{ display: 'flex', gap: 10, marginTop: '1.25rem', flexWrap: 'wrap' }}
        >
          <label className="mm-sr-only" htmlFor="create-intent">
            What do you want to make?
          </label>
          <input
            id="create-intent"
            className="mm-input"
            style={{ flex: '1 1 320px', padding: '0.8rem 1rem', fontSize: '1rem' }}
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder="Describe the object you want to create…"
            maxLength={200}
            autoComplete="off"
          />
          <Button type="submit" disabled={!intent.trim() || busySlug !== null} size="md">
            Make it
          </Button>
        </form>

        <div
          role="group"
          aria-label="Starter ideas"
          style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: '0.9rem' }}
        >
          {STARTER_INTENTS.map((chip) => (
            <button
              key={chip.label}
              type="button"
              className="mm-btn"
              onClick={() => runIntent(chip.prompt)}
              disabled={busySlug !== null}
              style={{
                background: '#fff',
                color: '#5b6e72',
                border: '1px solid var(--mm-line, #d8e0e0)',
                borderRadius: 999,
                padding: '6px 14px',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </section>

      {error ? (
        <div style={{ marginTop: '1rem', maxWidth: 720 }}>
          <ErrorPanel
            message={error}
            onRetry={() => (submitted ? runIntent(submitted) : undefined)}
          />
        </div>
      ) : null}

      {/* Intent result: small visual choice of matching tools */}
      {submitted !== null && matches !== null && busySlug === null && !error ? (
        <section aria-labelledby="intent-result" style={{ maxWidth: 720, marginTop: '1.5rem' }}>
          <h2 id="intent-result" style={{ fontSize: '1.05rem', margin: 0 }}>
            {matches.length === 0 ? 'Pick a maker tool to start' : 'A few tools fit that'}
          </h2>
          <p className="mm-meta" style={{ marginTop: 4 }}>
            {matches.length === 0 ? (
              <>
                We couldn&apos;t match “{submitted}” to a maker tool yet. These are a good place to
                start — or browse everything in Explore.
              </>
            ) : (
              <>We matched “{submitted}” to a few tools — choose one to jump straight in.</>
            )}
          </p>
          <div className="mm-grid-3" style={{ marginTop: '0.75rem' }}>
            {(suggestionTools.length > 0 ? suggestionTools : classicTools).map((tool) => (
              <ToolPick
                key={tool.slug}
                tool={tool}
                busy={busySlug === tool.slug}
                onMake={(t) => void makeWithTool(t)}
              />
            ))}
          </div>
          <p style={{ marginTop: '0.75rem', fontSize: '0.875rem' }}>
            <Link href="/explore" style={{ color: 'var(--mm-accent, #0f766e)' }}>
              Browse all maker tools →
            </Link>
          </p>
        </section>
      ) : null}

      {/* Creation modes */}
      <section aria-labelledby="create-modes" style={{ marginTop: '2rem' }}>
        <h2 id="create-modes" style={{ fontSize: '1.05rem', margin: 0 }}>
          How do you want to start?
        </h2>
        <div className="mm-grid-3" style={{ marginTop: '0.75rem' }}>
          {MODES.map((mode) =>
            mode.href ? (
              <Link
                key={mode.title}
                href={mode.href}
                aria-label={mode.title}
                style={{ textDecoration: 'none' }}
              >
                <article
                  className="mm-panel"
                  style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}
                >
                  <ModeBody mode={mode} />
                </article>
              </Link>
            ) : (
              <article
                key={mode.title}
                className="mm-panel"
                aria-disabled="true"
                style={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                  opacity: 0.72,
                }}
              >
                <ModeBody mode={mode} />
              </article>
            ),
          )}
        </div>
      </section>

      {/* First-visit friendly intro: three example tools (IA §4.1) */}
      <section aria-labelledby="classic-tools" style={{ marginTop: '2rem' }}>
        <h2 id="classic-tools" style={{ fontSize: '1.05rem', margin: 0 }}>
          Start with a classic
        </h2>
        {!online ? (
          <div style={{ marginTop: '0.75rem' }}>
            <OfflineState
              title="You are offline"
              description="Reconnect to see the starter tools."
              actionLabel="Retry"
              onAction={() => void loadAvailability()}
            />
          </div>
        ) : available === null ? (
          <div style={{ marginTop: '0.75rem' }}>
            <LoadingState title="Loading starter tools…" />
          </div>
        ) : classicTools.length === 0 ? (
          <p className="mm-meta" style={{ marginTop: '0.75rem' }}>
            No starter tools available yet — more are on the way.
          </p>
        ) : (
          <div className="mm-grid-3" style={{ marginTop: '0.75rem' }}>
            {classicTools.map((tool) => (
              <Link
                key={tool.slug}
                href={`/explore/${tool.slug}`}
                aria-label={tool.name}
                style={{ textDecoration: 'none' }}
              >
                <article
                  className="mm-panel"
                  style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 8 }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span aria-hidden="true" style={{ fontSize: '1.4rem', lineHeight: 1 }}>
                      {tool.icon}
                    </span>
                    <h3 style={{ margin: 0, fontSize: '0.95rem' }}>{tool.name}</h3>
                  </div>
                  <p style={{ margin: 0, flex: 1, fontSize: '0.8125rem', color: '#5b6e72' }}>
                    {tool.promise}
                  </p>
                  <span style={{ fontSize: '0.7rem', color: '#8aa0a5' }}>
                    {tool.categoryLabel} · {tool.difficulty}
                  </span>
                </article>
              </Link>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  );
}

function ModeBody({ mode }: { mode: ModeCard }) {
  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span aria-hidden="true" style={{ fontSize: '1.4rem', lineHeight: 1 }}>
          {mode.icon}
        </span>
        {mode.badge ? (
          <span
            style={{
              fontSize: '0.65rem',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              color: '#5b6e72',
              border: '1px solid var(--mm-line, #d8e0e0)',
              borderRadius: 999,
              padding: '2px 8px',
            }}
          >
            {mode.badge}
          </span>
        ) : null}
      </div>
      <h3 style={{ margin: 0, fontSize: '0.95rem' }}>{mode.title}</h3>
      <p style={{ margin: 0, fontSize: '0.8125rem', color: '#5b6e72' }}>{mode.description}</p>
      {mode.note ? (
        <p style={{ margin: 0, fontSize: '0.75rem', color: '#8aa0a5' }}>{mode.note}</p>
      ) : null}
    </>
  );
}
