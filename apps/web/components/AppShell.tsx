import Link from 'next/link';
import { useRouter } from 'next/router';
import type { ReactNode } from 'react';

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/generators', label: 'Generators' },
  { href: '/health', label: 'Health' },
];

export function AppShell({ children, title }: { children: ReactNode; title?: string }) {
  const router = useRouter();
  const pageTitle = title ? `${title} · ModuMesh MakerLab` : 'ModuMesh MakerLab';

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
