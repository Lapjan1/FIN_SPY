'use client';
import React, { useEffect, useState } from 'react';
import { DocInfo, fetchDocuments } from '../../lib/api';

export default function InboxPage() {
  const [userId, setUserId] = useState('');
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? window.localStorage.getItem('finspy-user-id') : '';
    if (saved) setUserId(saved);
  }, []);

  async function load() {
    if (!userId) {
      setError('Enter your user id first (see Account page after login).');
      return;
    }
    setLoading(true);
    setError('');
    try {
      window.localStorage.setItem('finspy-user-id', userId);
      setDocs(await fetchDocuments(userId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed');
    } finally {
      setLoading(false);
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

      <div className="flex gap-2 items-center">
        <input
          className="flex-1 p-2 bg-slate-900 border border-slate-700 rounded"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="user id (X-User-Id, saved after first load)"
        />
        <button onClick={load} disabled={loading} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          {loading ? 'Loading' : 'Load'}
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
            <li key={d.id} className="p-3 text-sm flex justify-between gap-2">
              <span className="truncate">{d.original_filename}</span>
              <span className="font-mono text-xs text-slate-500">{d.sha256.slice(0, 12)}</span>
              <span className="text-xs">{d.status}</span>
            </li>
          ))}
        </ul>
      </div>
    </main>
  );
}
