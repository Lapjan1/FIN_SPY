'use client';
import React, { useEffect, useState } from 'react';
import SourceViewer from '../../components/SourceViewer';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import {
  Me,
  Transaction,
  TxnSources,
  fetchTransactionsAuth,
  fetchTxnSources,
  formatRands,
  rejectTransaction,
} from '../../lib/api';

export default function TransactionsPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <TransactionsInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function TransactionsInner({ uid, me }: { uid: string; me: Me }) {
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [sources, setSources] = useState<TxnSources | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [voidReason, setVoidReason] = useState('');
  const [voidWorking, setVoidWorking] = useState(false);
  const [voidMsg, setVoidMsg] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      setTxns(await fetchTransactionsAuth(uid));
      setSelected(null);
      setSources(null);
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

  async function select(txn: Transaction) {
    setSelected(txn);
    setSources(null);
    setError('');
    setVoidReason('');
    setVoidMsg('');
    try {
      setSources(await fetchTxnSources(uid, txn.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sources failed');
    }
  }

  async function voidTxn() {
    if (!selected || !voidReason.trim()) return;
    if (!window.confirm(`Void ${selected.description_raw}? Posted journals are reversed; history stays.`)) return;
    setVoidWorking(true);
    setError('');
    try {
      const out = await rejectTransaction(uid, selected.id, voidReason.trim());
      setVoidMsg(`Voided. Reversed journals: ${out.reversed_entry_ids.join(', ') || 'none (was never posted)'}.`);
      setVoidReason('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Void failed');
    } finally {
      setVoidWorking(false);
    }
  }

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Transactions - click any row to see its source line</h1>
        <p className="text-sm text-slate-400 mt-1">
          Every row carries line IDs and bounding boxes back to the exact line on the original PDF.
        </p>
      </div>

      <SessionBar me={me} />

      <div className="flex gap-2 items-center">
        <button onClick={load} disabled={loading} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          {loading ? 'Loading' : 'Reload'}
        </button>
      </div>

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}

      <div className="grid md:grid-cols-2 gap-6">
        <div className="border border-slate-800 rounded">
          <div className="p-3 border-b border-slate-800 font-semibold text-sm">Ledger ({txns.length})</div>
          {txns.length === 0 && !loading ? (
            <p className="p-4 text-sm text-slate-400">Empty - upload a statement first.</p>
          ) : null}
          <ul className="divide-y divide-slate-800 max-h-[560px] overflow-auto">
            {txns.map((txn) => (
              <li key={txn.id}>
                <button
                  onClick={() => select(txn)}
                  className={`w-full text-left p-3 hover:bg-slate-900 ${selected?.id === txn.id ? 'bg-slate-900' : ''}`}
                >
                  <div className="flex justify-between items-center gap-2">
                    <span className="text-sm font-medium truncate">{txn.description_raw}</span>
                    <span className="text-sm font-mono">{formatRands(txn.amount_minor)}</span>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {txn.txn_date} - {txn.direction} - {txn.status}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-4">
          {selected && selected.status !== 'rejected' ? (
            <div className="border border-slate-800 rounded p-3 space-y-2">
              <p className="text-sm font-semibold">Void this transaction</p>
              <input
                value={voidReason}
                onChange={(e) => setVoidReason(e.target.value)}
                placeholder="Reason (required, kept forever for audit)"
                className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm"
              />
              <button onClick={voidTxn} disabled={voidWorking || !voidReason.trim()} className="bg-red-800 px-4 py-2 rounded text-sm disabled:opacity-50">
                {voidWorking ? 'Working...' : 'Void with reversals'}
              </button>
              {voidMsg ? <p className="text-xs text-emerald-300">{voidMsg}</p> : null}
            </div>
          ) : null}
          {!selected ? (
            <p className="text-sm text-slate-400">Select a row to drill to its source.</p>
          ) : !sources ? (
            <p className="text-sm text-slate-400">Loading sources...</p>
          ) : sources.unlinked ? (
            <p className="text-sm text-slate-400">No source spans linked (manually added or legacy row).</p>
          ) : (
            <SourceViewer
              userId={uid}
              docId={sources.document_id}
              docSha256={sources.doc_sha256 || ''}
              pageNo={sources.page_no}
              pageWidth={sources.page_width}
              pageHeight={sources.page_height}
              lineIds={sources.line_ids}
              bboxes={sources.bboxes}
            />
          )}
        </div>
      </div>
    </main>
  );
}
