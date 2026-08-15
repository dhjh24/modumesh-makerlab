import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api, ApiError } from '../lib/api';
import { clearToken, getToken, setAuthUser, type AuthUser } from '../lib/auth';

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/generators', label: 'Marketplace' },
  { href: '/health', label: 'Health' },
];

export function AppShell({ children, title }: { children: ReactNode; title?: string }) {
  const router = useRouter();
  const pageTitle = title ? `${title} · ModuMesh MakerLab` : 'ModuMesh MakerLab';
  const [user, setUser] = useState<AuthUser | null>(null);

  // Refresh the user chip on mount when a token exists. Public pages
  // (health, generators) render the shell too — they just show "Sign in".
  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (cancelled) return;
        setAuthUser(me);
        setUser(me);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setUser(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLogout = async () => {
    try {
      await api.logout(); // best-effort server-side revocation
    } catch {
      // Token may already be expired — always clear locally.
    }
    clearToken();
    setUser(null);
    await router.push('/login');
  };

  return (
    <div className="mm-shell">
      <a className="mm-skip" href="#main">
        Skip to content
      </a>
      <header className="mm-header">
        <Link className="mm-brand" href="/">
          ModuMesh <span>MakerLab</span>
        </Link>
        <nav className="mm-nav" aria-label="Primary">
          {NAV.map((item) => {
            const current =
              item.href === '/' ? router.pathname === '/' : router.pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} aria-current={current ? 'page' : undefined}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {user ? (
            <>
              <span
                className="mm-meta"
                style={{ whiteSpace: 'nowrap' }}
                title={user.email || undefined}
              >
                {user.display_name || user.email}
              </span>
              <button
                type="button"
                className="mm-btn mm-btn--ghost mm-btn--sm"
                onClick={() => void handleLogout()}
              >
                Logout
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="mm-btn mm-btn--secondary mm-btn--sm"
              style={{ textDecoration: 'none' }}
            >
              Sign in
            </Link>
          )}
        </div>
      </header>
      <main id="main" className="mm-main">
        {/* Keep document title in sync for screen readers without forcing Head in every page */}
        <span className="mm-sr-only" aria-live="polite">
          {pageTitle}
        </span>
        {children}
      </main>
      <footer className="mm-footer">
        Self-hosted generators · schema-driven · no CAD in the request path
      </footer>
    </div>
  );
}
