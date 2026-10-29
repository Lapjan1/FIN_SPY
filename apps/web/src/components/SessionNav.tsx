'use client';
import React, { useEffect, useState } from 'react';
import { Me, clearSession, fetchMe, getSessionUserId, isAuthError } from '../lib/api';

export default function SessionNav() {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const uid = getSessionUserId();
    if (!uid) {
      setReady(true);
      return;
    }
    let live = true;
    fetchMe(uid).then(
      (m) => {
        if (live) setMe(m);
      },
      (err) => {
        if (live) {
          if (isAuthError(err)) clearSession();
          setMe(null);
        }
      },
    ).finally(() => {
      if (live) setReady(true);
    });
    return () => {
      live = false;
    };
  }, []);

  function signOut() {
    clearSession();
    window.location.href = '/';
  }

  if (!ready) return null;
  if (!me) return <a href="/account" className="text-blue-400">Sign in</a>;

  const plan = me.is_trial_unlimited ? 'Pro' : `Trial: ${me.trial_pages_remaining ?? 0} pages left`;
  const badge = me.is_trial_unlimited
    ? 'bg-green-900 text-green-200'
    : 'bg-amber-900 text-amber-200';
  return (
    <span className="flex gap-3 items-center">
      <span className={`px-2 py-0.5 rounded text-xs ${badge}`}>{plan}</span>
      <button onClick={signOut} className="text-slate-300 underline">Sign out</button>
    </span>
  );
}
