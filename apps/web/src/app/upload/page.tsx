'use client';
import React, { useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import PaywallNotice from '../../components/PaywallNotice';
import { Me, fetchMe, isPaywallError, uploadDocument } from '../../lib/api';

type VaultReceipt = {
  id: string;
  sha256: string;
  original_filename: string;
  size_bytes: number;
  status: string;
  duplicate?: boolean;
  requeued?: boolean;
  bytes_restored?: boolean;
  trial_pages_remaining?: number;
};

type Outcome = { name: string; ok: boolean; receipt?: VaultReceipt; error?: string };

export default function UploadPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <UploadInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function UploadInner({ uid, me }: { uid: string; me: Me }) {
  const [files, setFiles] = useState<File[]>([]);
  const [password, setPassword] = useState('');
  const [working, setWorking] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [paywallDetail, setPaywallDetail] = useState('');
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [meState, setMeState] = useState<Me>(me);

  const exhausted = !meState.is_trial_unlimited && (meState.trial_pages_remaining ?? 0) <= 0;

  async function send() {
    if (files.length === 0) {
      setError('Choose one or more bank statement PDFs first.');
      return;
    }
    setWorking(true);
    setError('');
    setPaywallDetail('');
    setOutcomes([]);
    const done: Outcome[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setProgress(`Uploading ${i + 1} of ${files.length}: ${file.name}`);
      try {
        const out = (await uploadDocument(uid, file, password || undefined)) as unknown as VaultReceipt;
        done.push({ name: file.name, ok: true, receipt: out });
      } catch (e) {
        if (isPaywallError(e)) {
          setPaywallDetail(e instanceof Error ? e.message : '');
          break;
        }
        done.push({ name: file.name, ok: false, error: e instanceof Error ? e.message : 'Upload failed' });
      }
      setOutcomes([...done]);
    }
    setProgress('');
    setFiles([]);
    fetchMe(uid).then(setMeState, () => {});
    setWorking(false);
  }

  return (
    <main className="max-w-3xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upload - hashed into the vault, never overwritten</h1>
        <p className="text-sm text-slate-400 mt-1">
          One or more SA bank PDFs at a time. SHA256 content-hash + trial quota checked first;
          encrypted files need the password once (never stored). Extraction starts within seconds.
        </p>
      </div>

      <SessionBar me={meState} />

      {exhausted ? (
        <PaywallNotice detail="Your trial uploads are used up." />
      ) : (
        <div className="space-y-3">
          <input
            type="file"
            multiple
            accept="application/pdf,.pdf"
            onChange={(e) => setFiles(Array.from(e.target.files || []))}
            className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm"
          />
          {files.length > 0 ? (
            <p className="text-sm text-slate-400">
              {files.length} file{files.length === 1 ? '' : 's'} selected: {files.map((f) => f.name).join(', ')}
            </p>
          ) : null}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="PDF password (only if encrypted, never stored)"
            className="w-full p-2 bg-slate-900 border border-slate-700 rounded"
          />
          <button onClick={send} disabled={working} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
            {working ? 'Uploading' : `Upload ${files.length === 0 ? 'statements' : `${files.length} file${files.length === 1 ? '' : 's'}`}`}
          </button>
          {progress ? <p className="text-sm text-slate-400">{progress}</p> : null}
        </div>
      )}

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}
      {paywallDetail ? <PaywallNotice detail={paywallDetail} /> : null}
      {outcomes.length > 0 ? (
        <div className="space-y-3">
          <h2 className="font-semibold text-sm">Vault receipts ({outcomes.filter((o) => o.ok).length} of {outcomes.length} stored)</h2>
          {outcomes.map((o, i) => (
            <div key={i} className={`border rounded p-3 text-sm space-y-1 ${o.ok ? 'border-slate-800' : 'border-red-800 bg-red-950'}`}>
              <p className="font-medium truncate">{o.name}</p>
              {o.ok && o.receipt ? (
                <>
                  <p>
                    <span className="px-2 py-0.5 rounded text-xs bg-blue-900 text-blue-200">{o.receipt.status}</span>{' '}
                    <span className="text-slate-400">
                      {o.receipt.requeued
                        ? 'file bytes were missing - restored, extracting again, no quota used'
                        : o.receipt.duplicate
                          ? 'already in your vault - no quota used'
                          : 'extraction starts within seconds'}
                    </span>
                  </p>
                  <p className="font-mono text-xs text-slate-500">sha256:{o.receipt.sha256.slice(0, 16)}... - {(o.receipt.size_bytes / 1024).toFixed(1)} KB</p>
                  {typeof o.receipt.trial_pages_remaining === 'number' ? (
                    <p className="text-xs text-slate-400">Trial uploads left: {o.receipt.trial_pages_remaining}</p>
                  ) : null}
                </>
              ) : (
                <p className="text-sm">{o.error}</p>
              )}
            </div>
          ))}
          <p className="text-sm text-slate-400">
            Next: <a href="/inbox" className="text-blue-400 underline">inbox</a> for extraction status,
            then <a href="/review" className="text-blue-400 underline">review queue</a> to confirm.
          </p>
        </div>
      ) : null}
    </main>
  );
}
