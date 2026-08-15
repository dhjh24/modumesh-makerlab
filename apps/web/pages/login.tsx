import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { FormEvent, useEffect, useState } from 'react';
import { Button } from '@modumesh/ui';
import { api, ApiError } from '../lib/api';
import { clearToken, getToken, setAuthUser, setToken } from '../lib/auth';

/** Only allow internal `next` targets — never `//host` or backslash escapes. */
function safeNext(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (value && value.startsWith('/') && !value.startsWith('//') && !value.startsWith('/\\')) {
    return value;
  }
  return '/';
}

export default function LoginPage() {
  const router = useRouter();
  const registerMode = router.query.mode === 'register';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already signed in? Validate the stored token and go home. An expired
  // token is cleared here so the user can sign in again (avoids redirect loop).
  useEffect(() => {
    if (!router.isReady) return;
    if (!getToken()) return;
    let cancelled = false;
    api
      .me()
      .then(() => {
        if (!cancelled) void router.replace('/');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) clearToken();
        // Network errors: leave the form usable.
      });
    return () => {
      cancelled = true;
    };
  }, [router.isReady, router]);

  useEffect(() => {
    setError(null);
  }, [registerMode]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (registerMode && password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setSubmitting(true);
    try {
      const res = registerMode
        ? await api.register(email.trim(), password, displayName.trim() || undefined)
        : await api.login(email.trim(), password);
      setToken(res.access_token);
      setAuthUser(res.user);
      await router.replace(safeNext(router.query.next));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <>
      <Head>
        <title>{registerMode ? 'Create account' : 'Sign in'} · ModuMesh MakerLab</title>
      </Head>
      <main
        className="mm-shell"
        style={{ alignItems: 'center', justifyContent: 'center', padding: '2rem 1rem' }}
      >
        <div className="mm-panel" style={{ width: 'min(440px, 100%)' }}>
          <h1 className="mm-h1" style={{ fontSize: '1.4rem' }}>
            {registerMode ? 'Create your account' : 'Sign in'}
          </h1>
          <p className="mm-lead" style={{ marginBottom: '1.25rem' }}>
            {registerMode
              ? 'Projects, jobs, and files are private to your account.'
              : 'Access your projects, jobs, and files.'}
          </p>

          <form onSubmit={onSubmit} noValidate>
            {registerMode ? (
              <div className="mm-field">
                <label className="mm-field__label" htmlFor="auth-display-name">
                  Display name
                </label>
                <input
                  id="auth-display-name"
                  className="mm-input"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  autoComplete="name"
                  maxLength={255}
                  disabled={submitting}
                />
              </div>
            ) : null}
            <div className="mm-field">
              <label className="mm-field__label" htmlFor="auth-email">
                Email
              </label>
              <input
                id="auth-email"
                className="mm-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                maxLength={255}
                disabled={submitting}
              />
            </div>
            <div className="mm-field">
              <label className="mm-field__label" htmlFor="auth-password">
                Password
              </label>
              <input
                id="auth-password"
                className="mm-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={registerMode ? 'new-password' : 'current-password'}
                required
                minLength={registerMode ? 8 : undefined}
                maxLength={128}
                disabled={submitting}
              />
            </div>

            {error ? (
              <p className="mm-field__error" role="alert" style={{ marginBottom: '0.9rem' }}>
                {error}
              </p>
            ) : null}

            <Button type="submit" disabled={submitting} style={{ width: '100%' }}>
              {submitting
                ? registerMode
                  ? 'Creating account…'
                  : 'Signing in…'
                : registerMode
                  ? 'Create account'
                  : 'Sign in'}
            </Button>
          </form>

          <p className="mm-meta" style={{ marginTop: '1.25rem', textAlign: 'center' }}>
            {registerMode ? (
              <>
                Already have an account? <Link href="/login">Sign in</Link>
              </>
            ) : (
              <>
                No account yet? <Link href="/login?mode=register">Create one</Link>
              </>
            )}
          </p>
        </div>
      </main>
    </>
  );
}
