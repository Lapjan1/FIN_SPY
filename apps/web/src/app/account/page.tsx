'use client';
import React, { useEffect, useState } from 'react';
import {
  AuthResult,
  BillingPlans,
  Me,
  clearSession,
  fetchBillingPlans,
  fetchMe,
  forgotPassword,
  getSessionUserId,
  login,
  register,
  resetPassword,
  setSessionUserId,
  startCheckout,
} from '../../lib/api';

type Mode = 'login' | 'register' | 'forgot' | 'reset';

const inputCls = 'w-full p-2 bg-slate-900 border border-slate-700 rounded';

export default function AccountPage() {
  const [mode, setMode] = useState<Mode>('login');
  const [uid, setUid] = useState('');
  const [me, setMe] = useState<Me | null>(null);
  const [plans, setPlans] = useState<BillingPlans | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [token, setToken] = useState('');
  const [working, setWorking] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgKind, setMsgKind] = useState<'info' | 'error' | 'ok'>('info');

  useEffect(() => {
    const saved = getSessionUserId();
    if (!saved) return;
    setUid(saved);
    fetchMe(saved).then(setMe, () => {
      clearSession();
      setUid('');
      setMe(null);
    });
  }, []);

  useEffect(() => {
    if (me && !plans) fetchBillingPlans().then(setPlans, () => setPlans(null));
  }, [me, plans]);

  function say(text: string, kind: 'info' | 'error' | 'ok' = 'info') {
    setMsg(text);
    setMsgKind(kind);
  }

  async function afterAuth(res: AuthResult) {
    const id = res.id.toString();
    setSessionUserId(id);
    setUid(id);
    setPassword('');
    try {
      setMe(await fetchMe(id));
      say(`Signed in as ${res.email}.`, 'ok');
    } catch {
      say('Signed in, but loading your trial status failed. Reload to retry.', 'error');
    }
  }

  async function submitLogin() {
    if (!email || !password) return say('Enter email and password.', 'error');
    setWorking(true);
    try {
      await afterAuth(await login(email, password));
    } catch (e) {
      say(e instanceof Error ? e.message : 'Sign in failed.', 'error');
    } finally {
      setWorking(false);
    }
  }

  async function submitRegister() {
    if (!email || !password) return say('Enter email and password (min 6 chars).', 'error');
    setWorking(true);
    try {
      await afterAuth(await register(email, password, name));
    } catch (e) {
      const text = e instanceof Error ? e.message : 'Registration failed.';
      say(text.includes('already exists') ? 'That email already has an account. Sign in instead.' : text, 'error');
    } finally {
      setWorking(false);
    }
  }

  async function submitForgot() {
    if (!email) return say('Enter your account email first.', 'error');
    setWorking(true);
    try {
      const out = await forgotPassword(email);
      if (out.reset_token) {
        setToken(out.reset_token);
        setMode('reset');
        say('Dev mode (no email key on server): reset token shown, paste it below with a new password.', 'info');
      } else {
        say('If that email has an account, a reset link is on its way (1h expiry).', 'ok');
      }
    } catch (e) {
      say(e instanceof Error ? e.message : 'Request failed.', 'error');
    } finally {
      setWorking(false);
    }
  }

  async function submitReset() {
    if (!token || !password) return say('Enter the reset token and a new password.', 'error');
    setWorking(true);
    try {
      await resetPassword(token, password);
      setToken('');
      setPassword('');
      setMode('login');
      say('Password changed. Sign in with the new one.', 'ok');
    } catch (e) {
      say(e instanceof Error ? e.message : 'Reset failed.', 'error');
    } finally {
      setWorking(false);
    }
  }

  async function subscribe(planCode: string) {
    if (!uid) return;
    setWorking(true);
    try {
      const out = await startCheckout(uid, planCode);
      if (out.free || !out.checkout_url) {
        setMe(await fetchMe(uid));
        say('Plan updated.', 'ok');
      } else {
        window.location.href = out.checkout_url;
      }
    } catch (e) {
      say(e instanceof Error ? e.message : 'Checkout failed.', 'error');
    } finally {
      setWorking(false);
    }
  }

  function signOut() {
    clearSession();
    setUid('');
    setMe(null);
    setPlans(null);
    setMode('login');
    say('Signed out.', 'info');
  }

  const msgCls =
    msgKind === 'error'
      ? 'border-red-800 bg-red-950'
      : msgKind === 'ok'
        ? 'border-green-800 bg-green-950'
        : 'border-slate-700 bg-slate-900';

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Account</h1>
        <p className="text-sm text-slate-400 mt-1">
          One login for every page. Free trial covers 20 pages, then pick a plan.
        </p>
      </div>

      {msg ? <div className={`border p-3 rounded text-sm ${msgCls}`}>{msg}</div> : null}

      {!me ? (
        <div className="border border-slate-800 rounded p-4 space-y-3">
          <div className="flex gap-2 text-sm">
            {(['login', 'register', 'forgot', 'reset'] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m);
                  setMsg('');
                }}
                className={`px-3 py-1 rounded ${mode === m ? 'bg-blue-600' : 'bg-slate-800'}`}
              >
                {m === 'login' ? 'Sign in' : m === 'register' ? 'Create account' : m === 'forgot' ? 'Forgot password' : 'Reset'}
              </button>
            ))}
          </div>

          {mode === 'register' ? (
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name (optional)" />
          ) : null}
          {mode === 'reset' ? (
            <input className={inputCls} value={token} onChange={(e) => setToken(e.target.value)} placeholder="Reset token from email" />
          ) : (
            <input className={inputCls} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" />
          )}
          {mode !== 'forgot' ? (
            <input className={inputCls} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={mode === 'reset' ? 'New password (min 6)' : 'Password (min 6)'} type="password" />
          ) : null}

          <button
            onClick={mode === 'login' ? submitLogin : mode === 'register' ? submitRegister : mode === 'forgot' ? submitForgot : submitReset}
            disabled={working}
            className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50"
          >
            {working
              ? 'Working'
              : mode === 'login'
                ? 'Sign in'
                : mode === 'register'
                  ? 'Create account'
                  : mode === 'forgot'
                    ? 'Send reset link'
                    : 'Set new password'}
          </button>
          {mode === 'login' ? (
            <p className="text-xs text-slate-500">New here? Use Create account. One login works on Upload, Review, Dashboard, and Chat.</p>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="border border-slate-800 rounded p-4 space-y-1 text-sm">
            <p><span className="text-slate-400">Signed in as</span> <span className="font-semibold">{me.user.email}</span></p>
            <p>
              <span className="text-slate-400">Plan status</span>{' '}
              {me.is_trial_unlimited ? (
                <span className="px-2 py-0.5 rounded text-xs bg-green-900 text-green-200">Pro: unlimited pages</span>
              ) : (
                <span className="px-2 py-0.5 rounded text-xs bg-amber-900 text-amber-200">
                  Trial: {me.trial_pages_remaining ?? 0} of 20 pages left
                </span>
              )}
            </p>
            <div className="pt-2">
              <button onClick={signOut} className="border border-slate-700 px-4 py-1 rounded text-sm">Sign out</button>
            </div>
          </div>

          <div className="border border-slate-800 rounded p-4 space-y-3">
            <h2 className="font-semibold">Plans</h2>
            {!plans ? (
              <p className="text-sm text-slate-400">Loading plans.</p>
            ) : (
              <div className="grid md:grid-cols-3 gap-3 text-sm">
                {Object.entries(plans).map(([code, p]) => (
                  <div key={code} className="border border-slate-700 rounded p-3 space-y-1">
                    <p className="font-semibold">{p.name}</p>
                    <p className="text-slate-300">{p.pages} pages</p>
                    <p className="text-slate-400">{p.price_display}</p>
                    {code !== 'free' && !me.is_trial_unlimited ? (
                      <button onClick={() => subscribe(code)} disabled={working} className="mt-2 bg-blue-600 px-3 py-1 rounded disabled:opacity-50">
                        Subscribe
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-slate-500">Payments via Paystack (test mode while we finish verification). Webhook activates your plan automatically.</p>
          </div>
        </div>
      )}

      <div className="border border-slate-800 rounded p-4 text-sm text-slate-400">
        <h3 className="font-semibold text-slate-200">How sign-in works here</h3>
        <ul className="list-disc pl-5 mt-1 space-y-1">
          <li>Passwords are hashed with bcrypt. Reset links expire after 1 hour.</li>
          <li>Each account gets its own private workspace; uploads never leak across accounts.</li>
          <li>Trial counts uploaded pages: 20 free, then subscribe or stop uploading.</li>
        </ul>
      </div>
    </main>
  );
}
