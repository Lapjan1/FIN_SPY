'use client';
import React, { useState, useEffect } from 'react';
import MetaModelSelector from '../../components/settings/MetaModelSelector';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import { Me } from '../../lib/api';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function SettingsPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <SettingsInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function SettingsInner({ uid, me }: { uid: string; me: Me }) {
  const [settings,setSettings]=useState<Record<string,string>>({});
  const [model,setModel]=useState('muse-spark-1.1');
  const [effort,setEffort]=useState('medium');
  const [msg,setMsg]=useState('');
  const [isAdmin,setIsAdmin]=useState(false);
  const [isOwner,setIsOwner]=useState(false);

  useEffect(()=>{
    // Admins get the full table; owners fall back to non-secret preferences.
    fetch(`${API_BASE}/v1/settings`,{headers:{'X-User-Id':uid}}).then(r=>r.json()).then(data=>{
      if(data.detail) {
        fetch(`${API_BASE}/v1/settings/preferences`,{headers:{'X-User-Id':uid}}).then(r=>r.json()).then(prefs=>{
          if(prefs.detail) { setMsg('Settings need an owner or admin login'); return; }
          setSettings(prefs); setIsOwner(true);
          if(prefs.model) setModel(prefs.model);
          if(prefs.effort) setEffort(prefs.effort);
        }).catch(()=>setMsg('Failed to fetch preferences - are you signed in?'));
        return;
      }
      setSettings(data); setIsAdmin(true);
      if(data.model) setModel(data.model);
      if(data.effort) setEffort(data.effort);
    }).catch(()=>setMsg('Failed to fetch settings - are you signed in?'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);

  async function saveSetting(key:string,value:string) {
    // Admins POST /v1/settings; owners POST /v1/settings/preferences (model/effort only).
    // Secret keys are forbidden on both per docs/SETTINGS.md.
    const forbidden = ['meta_api_key','paystack_secret_key','session_secret','paystack_public_key'];
    if(forbidden.includes(key.toLowerCase())) {
      setMsg(`Reject 400: ${key} must be an env var per security guide, not a DB table (fail-closed)`);
      return;
    }
    const path = isAdmin ? '/v1/settings' : '/v1/settings/preferences';
    const res = await fetch(`${API_BASE}${path}`,{method:'POST',headers:{'Content-Type':'application/json','X-User-Id':uid},body:JSON.stringify({key,value})});
    const data = await res.json();
    setMsg(JSON.stringify(data));
    if(data.ok) setSettings({...settings,[key]:value});
  }

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Settings - Meta Models Compliance</h1>
      <p className="text-sm text-slate-400">Owners change model/effort; keys, billing, and cost guards stay admin-only (***REDACTED*** + last4). Ollama-local only as privacy fallback.</p>

      <SessionBar me={me} />

      <div className="border border-slate-800 rounded p-4 space-y-2">
        <div className="text-xs">Access: {isAdmin?'Admin (full table)':isOwner?'Owner (model/effort preferences)':'None - sign in as owner or admin'}</div>
        <div className="flex gap-2">
          <span className="px-2 py-1 bg-green-900 text-green-300 rounded text-xs">freellmapi dev http://127.0.0.1:3001/v1 (local dev only)</span>
          <span className="px-2 py-1 bg-yellow-900 text-yellow-300 rounded text-xs">meta_official via server env (worker only, never in this table)</span>
        </div>
      </div>

      {(isAdmin || isOwner) ? (
        <MetaModelSelector currentModel={model} effort={effort} onChange={(m,e)=>{setModel(m); setEffort(e); saveSetting('model',m); saveSetting('effort',e);}} />
      ) : (
        <p className="text-sm text-slate-400">Sign in as the account owner (or an admin) to change model/effort.</p>
      )}

      {isAdmin ? (
      <div className="border border-slate-800 rounded p-4 space-y-3">
        <h3 className="font-semibold">Cost Guards (config/models.yaml, admin-only)</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Per Document Token Ceiling: <input className="bg-slate-900 border border-slate-700 rounded px-1" value={settings.per_document_token_ceiling||'15000'} onChange={e=>saveSetting('per_document_token_ceiling',e.target.value)} /></div>
          <div>Trial Uploads Free: <input className="bg-slate-900 border border-slate-700 rounded px-1" value={settings.trial_pages||'20'} onChange={e=>saveSetting('trial_pages',e.target.value)} /></div>
          <div>Global Daily Budget USD: <input className="bg-slate-900 border border-slate-700 rounded px-1" value={settings.global_daily_budget_usd||'10'} onChange={e=>saveSetting('global_daily_budget_usd',e.target.value)} /></div>
          <div>Rate Limit RPM: <input className="bg-slate-900 border border-slate-700 rounded px-1" value={settings.meta_rate_limit_rpm||'100'} onChange={e=>saveSetting('meta_rate_limit_rpm',e.target.value)} /></div>
        </div>
      </div>
      ) : null}

      <div className="border border-slate-800 rounded p-4 space-y-3">
        <h3 className="font-semibold">Env Guards + Privacy Gate</h3>
        <div className="text-xs space-y-1">
          <div>REQUIRED fail-closed: SESSION_SECRET, DATABASE_URL, META_API_KEY worker only - never in settings table, must be env var per docs/SETTINGS.md</div>
          <div>OPTIONAL env_or_setting: FREELLMAPI_API_KEY, OLLAMA_BASE_URL, PAYSTACK_SECRET_KEY api only, ADMIN_EMAIL allowlist, APP_BASE_URL for the Paystack callback URL</div>
          <div>Privacy Gate: show_exact_text_before_hosted=true per config/models.yaml, local-first per Flowchart #2, audit_log hash-chain</div>
          <div>Forbidden keys via POST: meta_api_key, paystack_secret_key, session_secret, paystack_public_key must be env var - if attempted 400 per security guide hooks outside sandbox</div>
        </div>
      </div>

      {(isAdmin || isOwner) ? (
      <div className="border border-slate-800 rounded p-4">
        <h3 className="font-semibold">{isAdmin ? 'Current Settings (admin, redacted secrets)' : 'My Preferences (non-secret only)'}</h3>
        <pre className="bg-slate-900 p-2 rounded text-xs whitespace-pre-wrap">{JSON.stringify(settings,null,2)}</pre>
        <p className="text-xs mt-2 text-slate-500">Secrets shown redacted (***REDACTED*** + last4), never returned for secret keys; full table is admin-only.</p>
      </div>
      ) : null}

      <pre className="bg-slate-900 p-4 rounded text-xs whitespace-pre-wrap">{msg}</pre>
    </main>
  );
}
