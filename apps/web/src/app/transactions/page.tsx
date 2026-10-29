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
    try {
      setSources(await fetchTxnSources(uid, txn.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Sources failed');
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
