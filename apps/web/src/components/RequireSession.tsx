'use client';
import React, { useEffect, useState } from 'react';
import { Me, clearSession, fetchMe, getSessionUserId, isAuthError } from '../lib/api';

export type Session = { uid: string; me: Me };

// Gate: pages render only with a verified session. The uid passed down already
// survived a /auth/me round-trip, so pages can never send a stale/hand-typed id.
export default function RequireSession({ children }: { children: (s: Session) => React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const uid = getSessionUserId();
    if (!uid) {
      setReady(true);
      return;
    }
    let live = true;
    fetchMe(uid).then(
      (me) => {
        if (live) setSession({ uid, me });
      },
      (err) => {
        if (live) {
          if (isAuthError(err)) clearSession();
          setSession(null);
        }
      },
    ).finally(() => {
      if (live) setReady(true);
    });
    return () => {
      live = false;
    };
  }, []);

  if (!ready) {
    return (
      <main className="max-w-3xl mx-auto p-6">
        <p className="text-sm text-slate-400">Loading session.</p>
      </main>
    );
  }
  if (!session) {
    return (
      <main className="max-w-3xl mx-auto p-6 space-y-4">
        <h1 className="text-2xl font-bold">Sign in required</h1>
        <p className="text-sm text-slate-400">
          This page needs your account so it only ever shows your own data.
        </p>
        <a href="/account" className="inline-block bg-blue-600 px-4 py-2 rounded text-sm">
          Go to Account
        </a>
      </main>
    );
  }
  return <>{children(session)}</>;
}

export function SessionBar({ me }: { me: Me }) {
  const trial = me.is_trial_unlimited
    ? 'Pro: unlimited pages'
    : `Trial: ${me.trial_pages_remaining ?? 0} pages left`;
  const badge = me.is_trial_unlimited
    ? 'bg-green-900 text-green-200'
    : 'bg-amber-900 text-amber-200';
  return (
    <p className="text-sm text-slate-400">
      Signed in as <span className="text-slate-200">{me.user.email}</span>{' '}
      <span className={`px-2 py-0.5 rounded text-xs ${badge}`}>{trial}</span>
    </p>
  );
}
