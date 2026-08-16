import Head from 'next/head';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Button } from '@modumesh/ui';
import { AppShell } from '../components/AppShell';
import { api, ApiError } from '../lib/api';
import { setAuthUser, type AuthUser } from '../lib/auth';

/**
 * Settings — account + app preferences (IA §4.5).
 * W2.1 scaffolding: account read-only + units preference (canonical mm,
 * presentation only — locked in Phase 2 approval). Admin surface links here.
 */
const UNIT_PREF_KEY = 'makerlab.units';

export default function SettingsPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [units, setUnits] = useState<string>('mm');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setUnits(localStorage.getItem(UNIT_PREF_KEY) || 'mm');
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (cancelled) return;
        setAuthUser(me);
        setUser(me);
      })
      .catch((err: unknown) => {
        // 401 clears the token and the header shows Sign in; page stays usable.
        if (err instanceof ApiError && err.status === 401) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    localStorage.setItem(UNIT_PREF_KEY, units);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <AppShell title="Settings">
      <Head>
        <title>Settings · ModuMesh MakerLab</title>
      </Head>
      <h1 className="mm-h1">Settings</h1>
      <p className="mm-lead">Account and app preferences.</p>

      <div className="mm-panel" style={{ marginTop: '0.75rem', maxWidth: 560 }}>
        <h2>Account</h2>
        {user ? (
          <dl className="mm-list" style={{ marginTop: 6 }}>
            <div style={{ display: 'flex', gap: 8, padding: '8px 0' }}>
              <dt className="mm-meta" style={{ minWidth: 110 }}>
                Display name
              </dt>
              <dd>{user.display_name || '—'}</dd>
            </div>
            <div style={{ display: 'flex', gap: 8, padding: '8px 0' }}>
              <dt className="mm-meta" style={{ minWidth: 110 }}>
                Email
              </dt>
              <dd>{user.email}</dd>
            </div>
          </dl>
        ) : (
          <p className="mm-meta" style={{ marginTop: 6 }}>
            Not signed in — <Link href="/login">Sign in</Link>
          </p>
        )}
      </div>

      <div className="mm-panel" style={{ marginTop: '0.75rem', maxWidth: 560 }}>
        <h2>App</h2>
        <p className="mm-meta" style={{ marginBottom: 10 }}>
          Units are a display preference only — models are always stored in millimetres.
        </p>
        <form className="mm-inline-form" onSubmit={onSubmit} noValidate>
          <div className="mm-field">
            <label className="mm-field__label" htmlFor="settings-units">
              Units
            </label>
            <select
              id="settings-units"
              className="mm-input"
              value={units}
              onChange={(e) => setUnits(e.target.value)}
            >
              <option value="mm">Millimetres (mm)</option>
              <option value="in">Inches (in)</option>
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Button type="submit">Save preferences</Button>
            {saved ? <span className="mm-meta">Saved ✓</span> : null}
          </div>
        </form>
      </div>

      <div className="mm-panel" style={{ marginTop: '0.75rem', maxWidth: 560 }}>
        <h2>Advanced</h2>
        <p className="mm-meta" style={{ marginBottom: 10 }}>
          Plugin registry, submissions, and service health live in the developer area.
        </p>
        <Link
          href="/admin/health"
          className="mm-btn mm-btn--ghost"
          style={{ textDecoration: 'none', display: 'inline-block' }}
        >
          Developer area
        </Link>
      </div>
    </AppShell>
  );
}
