'use client';
import React, { useEffect, useState } from 'react';
import { uploadDocument } from '../../lib/api';

export default function UploadPage() {
  const [userId, setUserId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState('');

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? window.localStorage.getItem('finspy-user-id') : '';
    if (saved) setUserId(saved);
  }, []);

  async function send() {
    if (!userId) {
      setError('Enter your user id first (see Account page after login).');
      return;
    }
    if (!file) {
      setError('Choose a bank statement PDF first.');
      return;
    }
    setWorking(true);
    setError('');
    setResult('');
    try {
      window.localStorage.setItem('finspy-user-id', userId);
      const out = await uploadDocument(userId, file, password || undefined);
      setResult(JSON.stringify(out, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upload - hashed into the vault, never overwritten</h1>
        <p className="text-sm text-slate-400 mt-1">
          Any SA bank PDF. SHA256 content-hash + trial pages checked first; encrypted files need the password once (never stored).
        </p>
      </div>

      <div className="space-y-3">
        <input
          className="w-full p-2 bg-slate-900 border border-slate-700 rounded"
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="user id (X-User-Id, saved after first upload)"
        />
        <input
          type="file"
          accept="application/pdf,.pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="PDF password (only if encrypted, never stored)"
          className="w-full p-2 bg-slate-900 border border-slate-700 rounded"
        />
        <button onClick={send} disabled={working} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          {working ? 'Uploading' : 'Upload statement'}
        </button>
      </div>

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}
      {result ? (
        <div>
          <h2 className="font-semibold text-sm mb-2">Vault receipt</h2>
          <pre className="bg-slate-900 p-3 rounded text-xs whitespace-pre-wrap">{result}</pre>
          <p className="text-sm text-slate-400 mt-2">
            Next: <a href="/inbox" className="text-blue-400 underline">inbox</a> for status,
            then <a href="/transactions" className="text-blue-400 underline">transactions</a> to drill.
          </p>
        </div>
      ) : null}
    </main>
  );
}
