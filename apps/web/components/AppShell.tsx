import Link from 'next/link';
import { useRouter } from 'next/router';
import { ReactNode, useEffect, useState } from 'react';
import { api, AuthUser, getStoredToken, setStoredToken } from '../lib/api';

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/generators', label: 'Generators' },
  { href: '/admin', label: 'Admin', adminOnly: true },
];

export function AppShell({ children, title }: { children: ReactNode; title?: string }) {
  const router = useRouter();
  const pageTitle = title ? `${title} · ModuMesh MakerLab` : 'ModuMesh MakerLab';
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (!getStoredToken()) return;
    api
      .me()
      .then(setUser)
      .catch(() => setStoredToken(null));
  }, []);

  async function onLogout() {
    await api.logout();
    setUser(null);
    await router.push('/login');
  }

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
          {NAV.filter((item) => !item.adminOnly || user?.role === 'admin').map((item) => {
            const current =
              item.href === '/' ? router.pathname === '/' : router.pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} aria-current={current ? 'page' : undefined}>
                {item.label}
              </Link>
            );
          })}
          {user ? (
            <button type="button" className="mm-nav-btn" onClick={onLogout}>
              Sign out ({user.username || user.display_name})
            </button>
          ) : router.pathname !== '/login' ? (
            <Link href="/login">Sign in</Link>
          ) : null}
        </nav>
      </header>
      <main id="main" className="mm-main">
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
