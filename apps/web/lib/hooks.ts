import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import { isTerminalJobStatus, type JobProgress } from '@modumesh/shared-types';
import { api, ApiError } from './api';
import { clearToken, getToken, setAuthUser, type AuthUser } from './auth';

/**
 * Client-side auth guard for per-user pages (dashboard, project editor).
 *
 * - No stored token   -> redirects to /login?next=<current path>.
 * - Token present     -> validates it via GET /auth/me; a 401 clears the
 *                        token and redirects to /login. Network failures are
 *                        tolerated so offline pages can render their own UI.
 */
export function useRequireAuth(): {
  status: 'checking' | 'authenticated' | 'unauthenticated';
  user: AuthUser | null;
} {
  const router = useRouter();
  const [status, setStatus] = useState<'checking' | 'authenticated' | 'unauthenticated'>(
    'checking',
  );
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (!router.isReady) return;
    const token = getToken();
    if (!token) {
      setStatus('unauthenticated');
      void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (cancelled) return;
        setAuthUser(me);
        setUser(me);
        setStatus('authenticated');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          setStatus('unauthenticated');
          void router.replace(`/login?next=${encodeURIComponent(router.asPath)}`);
          return;
        }
        // API unreachable or 5xx: stay on the page and let the data load
        // surface the offline/error UI.
        setStatus('authenticated');
      });
    return () => {
      cancelled = true;
    };
  }, [router.isReady, router.asPath, router]);

  return { status, user };
}

export function useOnline(): boolean {
  const [online, setOnline] = useState(true);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    setOnline(navigator.onLine);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);
  return online;
}

export function useJobPolling(jobId: string | null, intervalMs = 1000) {
  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopped = useRef(false);

  const clear = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const tick = useCallback(async () => {
    if (!jobId || stopped.current) return;
    try {
      const next = await api.getJobProgress(jobId);
      setProgress(next);
      setError(null);
      if (!isTerminalJobStatus(next.status)) {
        timer.current = setTimeout(tick, intervalMs);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0, String(err)));
      timer.current = setTimeout(tick, intervalMs * 2);
    }
  }, [jobId, intervalMs]);

  useEffect(() => {
    stopped.current = false;
    setProgress(null);
    setError(null);
    clear();
    void tick();
    return () => {
      stopped.current = true;
      clear();
    };
  }, [tick]);

  return { progress, error, refresh: tick };
}

export function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const sec = Math.round((now - then) / 1000);
  if (Number.isNaN(sec)) return iso;
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return new Date(iso).toLocaleString();
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
