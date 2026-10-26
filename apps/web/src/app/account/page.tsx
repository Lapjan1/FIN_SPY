'use client';
import React, { useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function AccountPage() {
  const [email,setEmail]=useState('demo@fin-spy.example');
  const [password,setPassword]=useState('demo123');
  const [userId,setUserId]=useState('');
  const [msg,setMsg]=useState('');

  async function register() {
    const res = await fetch(`${API_BASE}/v1/auth/register`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password,name:'Demo',tenant_id:'demo-tenant'})});
    const data = await res.json(); setMsg(JSON.stringify(data)); if(data.id) setUserId(data.id.toString());
  }
  async function login() {
    const res = await fetch(`${API_BASE}/v1/auth/login`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password})});
    const data = await res.json(); setMsg(JSON.stringify(data)); if(data.id) setUserId(data.id.toString());
  }
  async function me() {
    const res = await fetch(`${API_BASE}/v1/auth/me`,{headers:{'X-User-Id':userId}});
    const data = await res.json(); setMsg(JSON.stringify(data,null,2));
  }
  async function trial() {
    const res = await fetch(`${API_BASE}/v1/dashboard/summary`,{headers:{'X-User-Id':userId}});
    const data = await res.json(); setMsg(JSON.stringify(data,null,2));
  }
  async function checkout() {
    const res = await fetch(`${API_BASE}/v1/billing/checkout?plan_code=individual`,{method:'POST',headers:{'X-User-Id':userId}});
    const data = await res.json(); setMsg(JSON.stringify(data,null,2));
  }

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Account - Auth + Trial Pages + Paystack (clearmind pattern upgraded)</h1>
      <p className="text-sm text-slate-400">Based on clearmind-ai/app.py:152-172 require_login + get_trial_remaining 5 sessions, now bcrypt not SHA256, trial pages free 20 individual 200 sme 1000, timing-safe paystack HMAC SHA512 raw body per ClearFlag, hash-chain audit</p>
      <div className="border border-slate-800 rounded p-4 space-y-3">
        <input className="w-full p-2 bg-slate-900 border border-slate-700 rounded" value={email} onChange={e=>setEmail(e.target.value)} placeholder="email" />
        <input className="w-full p-2 bg-slate-900 border border-slate-700 rounded" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="password min 6" />
        <input className="w-full p-2 bg-slate-900 border border-slate-700 rounded" value={userId} onChange={e=>setUserId(e.target.value)} placeholder="user_id after login (X-User-Id header for dev)" />
        <div className="flex gap-2">
          <button onClick={register} className="bg-blue-600 px-4 py-1 rounded">Register</button>
          <button onClick={login} className="bg-green-600 px-4 py-1 rounded">Login</button>
          <button onClick={me} className="bg-slate-700 px-4 py-1 rounded">/auth/me (trial)</button>
          <button onClick={trial} className="bg-slate-700 px-4 py-1 rounded">Dashboard summary trial</button>
          <button onClick={checkout} className="bg-purple-600 px-4 py-1 rounded">Paystack Checkout R149</button>
        </div>
      </div>
      <pre className="bg-slate-900 p-4 rounded text-xs whitespace-pre-wrap">{msg}</pre>
      <div className="border border-slate-800 rounded p-4 text-sm text-slate-400">
        <h3 className="font-semibold">Security improvements over clearmind:</h3>
        <ul className="list-disc pl-5">
          <li>Passwords bcrypt $2b$ 60 chars gensalt not SHA256 hex no salt database.py:308 weak</li>
          <li>Session secret fail-closed REQUIRED production per ClearFlag server.js not random persisted like clearmind app.py:10 bug</li>
          <li>Paystack webhook timing-safe hmac.compare_digest HMAC SHA512 raw body per ClearFlag routes/paystack.js not plain ==, idempotent webhook_events table</li>
          <li>Trial pages 20/200/1000 vs 5 sessions, get_trial_pages_remaining counts source_documents where uploaded_by, None unlimited when active</li>
          <li>Isolation tenant_id+user_id WHERE tenant_id=? like clearmind WHERE user_id=? + test_user_isolation tenant-a can't see doc-b 403, RLS path Supabase prod</li>
          <li>Audit log hash-chain row_hash=SHA256(prev||canonical_json) append-only per AGENTS.md vs clearmind no chain</li>
        </ul>
      </div>
    </main>
  );
}
