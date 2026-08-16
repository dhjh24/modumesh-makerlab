import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api, ApiError } from '../lib/api';
import { clearToken, getToken, setAuthUser, type AuthUser } from '../lib/auth';

const NAV = [
  { href: '/', label: 'Create' },
  { href: '/explore', label: 'Explore' },
  { href: '/models', label: 'My Models' },
];

const USER_NAV = [
  { href: '/settings', label: 'Settings' },
  { href: '/admin/health', label: 'Developer' },
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
            <details className="mm-usermenu" style={{ position: 'relative' }}>
              <summary
                className="mm-btn mm-btn--ghost mm-btn--sm"
                style={{
                  listStyle: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
                aria-label="Account menu"
              >
                <span
                  className="mm-meta"
                  style={{ whiteSpace: 'nowrap' }}
                  title={user.email || undefined}
                >
                  {user.display_name || user.email}
                </span>
                ▾
              </summary>
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  top: 'calc(100% + 6px)',
                  background: 'white',
                  border: '1px solid var(--mm-line)',
                  borderRadius: '10px',
                  boxShadow: 'var(--mm-shadow, 0 4px 16px rgba(20,40,44,.12))',
                  padding: '6px',
                  minWidth: 180,
                  zIndex: 40,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                {USER_NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 8,
                      textDecoration: 'none',
                      color: 'var(--mm-ink)',
                      fontSize: '0.9rem',
                      fontWeight: 600,
                    }}
                  >
                    {item.label}
                  </Link>
                ))}
                <button
                  type="button"
                  className="mm-btn mm-btn--ghost mm-btn--sm"
                  style={{ justifyContent: 'flex-start', marginTop: 2 }}
                  onClick={() => void handleLogout()}
                >
                  Logout
                </button>
              </div>
            </details>
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
      <footer className="mm-footer">Make it · print it · keep it — ModuMesh Maker Studio</footer>
    </div>
  );
}
