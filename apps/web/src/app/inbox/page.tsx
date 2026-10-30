'use client';
import React, { useEffect, useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import { DocInfo, Me, fetchDocuments, requeueDocument } from '../../lib/api';

export default function InboxPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <InboxInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function InboxInner({ uid, me }: { uid: string; me: Me }) {
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState('');
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setDocs(await fetchDocuments(uid));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function retry(id: string) {
    setWorking(id);
    setError('');
    try {
      await requeueDocument(uid, id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retry failed');
    } finally {
      setWorking('');
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Inbox - every upload and its status</h1>
        <p className="text-sm text-slate-400 mt-1">
          Queued, proposed, exception, or needs_password. Identities are SHA256 hashes, never the file itself.
        </p>
      </div>

      <SessionBar me={me} />

      <div className="flex gap-2 items-center">
        <button onClick={load} disabled={loading} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          {loading ? 'Loading' : 'Reload'}
        </button>
      </div>

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}

      <div className="border border-slate-800 rounded">
        <div className="p-3 border-b border-slate-800 font-semibold text-sm">Documents ({docs.length})</div>
        {docs.length === 0 && !loading ? (
          <p className="p-4 text-sm text-slate-400">
            Empty - <a href="/upload" className="text-blue-400 underline">upload a statement</a> first.
          </p>
        ) : null}
        <ul className="divide-y divide-slate-800">
          {docs.map((d) => (
            <li key={d.id} className="p-3 text-sm flex justify-between items-center gap-2">
              <span className="truncate">{d.original_filename}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 shrink-0">
                {(d.bank_name || 'Bank')} {(d.account_number || 'unknown')}
              </span>
              {d.account_match === 'mismatch' ? (
                <span className="text-xs px-2 py-0.5 rounded bg-red-900 text-red-200 shrink-0" title={`You said ${d.asserted_account_number}, the paper says ${d.extracted_account_number}`}>
                  mismatch
                </span>
              ) : d.account_match === 'match' ? (
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-900 text-emerald-200 shrink-0">
                  verified
                </span>
              ) : null}
              <span className="font-mono text-xs text-slate-500">{d.sha256.slice(0, 12)}</span>
              <span className="text-xs">{d.status}</span>
              {d.status === 'exception' ? (
                <button
                  onClick={() => retry(d.id)}
                  disabled={working === d.id}
                  className="bg-amber-700 px-3 py-1 rounded text-xs disabled:opacity-50"
                >
                  {working === d.id ? 'Queued...' : 'Retry'}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
