'use client';
import React, { useEffect, useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import {
  AcceptResult,
  AccountOption,
  EditResult,
  Me,
  RejectResult,
  ReviewTxn,
  Suggestion,
  acceptTransaction,
  editTransaction,
  fetchAccounts,
  fetchReviewQueue,
  formatRands,
  rejectTransaction,
  suggestClassification,
} from '../../lib/api';

const NATURES = ['', 'business', 'private', 'mixed', 'unknown'];

function StatusBadge({ status }: { status: string }) {
  const color =
    status === 'confirmed'
      ? 'bg-green-900 text-green-200'
      : status === 'exception'
        ? 'bg-red-900 text-red-200'
        : status === 'needs_password'
          ? 'bg-orange-900 text-orange-200'
          : 'bg-amber-900 text-amber-200';
  return <span className={`px-2 py-0.5 rounded text-xs ${color}`}>{status}</span>;
}

export default function ReviewPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <ReviewInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function ReviewInner({ uid, me }: { uid: string; me: Me }) {
  const [queue, setQueue] = useState<ReviewTxn[]>([]);
  const [selected, setSelected] = useState<ReviewTxn | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [activeTemplate, setActiveTemplate] = useState('');
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<string>('');
  // Accept form
  const [nature, setNature] = useState('');
  const [businessPct, setBusinessPct] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [rationale, setRationale] = useState('');
  const [reason, setReason] = useState('');
  // Edit form
  const [editDesc, setEditDesc] = useState('');
  const [editDate, setEditDate] = useState('');
  const [editRands, setEditRands] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    setResult('');
    try {
      const [data, coa] = await Promise.all([fetchReviewQueue(uid), fetchAccounts(uid)]);
      setQueue(data.transactions);
      setAccounts(coa.accounts);
      setActiveTemplate(coa.active_template);
      setSelected(null);
      setSuggestion(null);
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

  async function select(txn: ReviewTxn) {
    setSelected(txn);
    setSuggestion(null);
    setResult('');
    setNature('');
    setBusinessPct('');
    setCategoryId('');
    setRationale('');
    setEditDesc(txn.description_raw);
    setEditDate(txn.txn_date);
    setEditRands((txn.amount_minor / 100).toFixed(2));
    try {
      const sug = await suggestClassification(uid, {
        description: txn.description_raw,
        account_number: txn.account_number || '',
        amount_minor: txn.amount_minor,
        direction: txn.direction,
      });
      setSuggestion(sug);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Suggest failed');
    }
  }

  function useSuggestion() {
    if (!suggestion) return;
    setNature(suggestion.nature);
    setBusinessPct(String(suggestion.business_pct));
    setCategoryId(suggestion.category_id);
    setRationale(suggestion.rationale);
    setResult('');
  }

  async function accept() {
    if (!selected || !reason.trim()) return;
    setWorking(true);
    setError('');
    try {
      const out: AcceptResult = await acceptTransaction(uid, selected.id, {
        nature: nature || undefined,
        business_pct: businessPct === '' ? undefined : Number(businessPct),
        category_id: categoryId || undefined,
        rationale,
        reason: reason.trim(),
      });
      setResult(`Accepted to ${out.status}. Classification ${JSON.stringify(out.classification)} Journal ${JSON.stringify(out.journal_entry)}`);
      setReason('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Accept failed');
    } finally {
      setWorking(false);
    }
  }

  async function reject() {
    if (!selected || !reason.trim()) return;
    if (!window.confirm(`Reject ${selected.description_raw}? Posted journals are voided with reversals; history stays.`)) return;
    setWorking(true);
    setError('');
    try {
      const out: RejectResult = await rejectTransaction(uid, selected.id, reason.trim());
      setResult(`Rejected. Reversed journals: ${out.reversed_entry_ids.join(', ') || 'none (was never posted)'}.`);
      setReason('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reject failed');
    } finally {
      setWorking(false);
    }
  }

  async function saveEdit() {
    if (!selected || !reason.trim()) return;
    setWorking(true);
    setError('');
    try {
      const patch: Parameters<typeof editTransaction>[2] = { reason: reason.trim() };
      if (editDesc !== selected.description_raw) patch.description_raw = editDesc;
      if (editDate !== selected.txn_date) patch.txn_date = editDate;
      if (editRands !== (selected.amount_minor / 100).toFixed(2)) {
        const cents = Math.round(Number(editRands) * 100);
        if (!Number.isFinite(cents)) throw new Error('Amount must be a number in rands, e.g. -450.00');
        patch.amount_minor = cents;
      }
      if (nature) patch.nature = nature;
      if (businessPct !== '') patch.business_pct = Number(businessPct);
      if (categoryId) patch.category_id = categoryId;
      if (rationale) patch.rationale = rationale;
      const out: EditResult = await editTransaction(uid, selected.id, patch);
      const reverify = out.reverification
        ? ` Reverify ${out.reverification.overall_pass ? 'PASS' : 'FAIL'} over ${out.reverification.rows_checked} rows.`
        : '';
      const repost = out.repost ? ` Reposted journal ${JSON.stringify(out.repost)}.` : '';
      setResult(`Saved fields: ${out.updated_fields.join(', ') || 'classification only'}.${repost}${reverify}`);
      setReason('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Edit failed');
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Review queue - accept or fix, every change keeps a reason</h1>
        <p className="text-sm text-slate-400 mt-1">
          Proposed and exception transactions. Accept posts the journal; editing amount or date reposts it and re-checks the chain. Nothing here deletes history. Rows missing or wrong? <a href="/contact" className="text-blue-400 underline">Contact us</a>.
        </p>
      </div>

      <SessionBar me={me} />

      <div className="flex gap-2 items-center">
        <button onClick={load} disabled={loading} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          {loading ? 'Loading' : 'Reload queue'}
        </button>
      </div>

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}

      <div className="grid md:grid-cols-2 gap-6">
        <div className="border border-slate-800 rounded">
          <div className="p-3 border-b border-slate-800 font-semibold text-sm">
            Queue ({queue.length})
          </div>
          {queue.length === 0 && !loading ? (
            <p className="p-4 text-sm text-slate-400">Empty - everything is already confirmed, or upload a statement first. Expected rows that never arrived? <a href="/contact" className="text-blue-400 underline">Contact us</a>.</p>
          ) : null}
          <ul className="divide-y divide-slate-800 max-h-[560px] overflow-auto">
            {queue.map((txn) => (
              <li key={txn.id}>
                <button
                  onClick={() => select(txn)}
                  className={`w-full text-left p-3 hover:bg-slate-900 ${selected?.id === txn.id ? 'bg-slate-900' : ''}`}
                >
                  <div className="flex justify-between items-center gap-2">
                    <span className="text-sm font-medium truncate">{txn.description_raw}</span>
                    <StatusBadge status={txn.status} />
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {txn.txn_date} - {formatRands(txn.amount_minor)} {txn.direction} - {txn.original_filename || 'no file'}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="border border-slate-800 rounded p-4 space-y-4">
          {!selected ? (
            <p className="text-sm text-slate-400">Select a transaction to review it.</p>
          ) : (
            <>
              <div>
                <h2 className="font-semibold truncate">{selected.description_raw}</h2>
                <p className="text-xs text-slate-400 mt-1">
                  {selected.txn_date} - {formatRands(selected.amount_minor)} {selected.direction} - account {selected.account_number || 'unknown'}
                </p>
              </div>

              <div className="bg-slate-900 rounded p-3 text-sm">
                <h3 className="font-semibold text-xs uppercase tracking-wide text-slate-400">Suggestion</h3>
                {!suggestion ? (
                  <p className="text-slate-400 mt-1">Loading suggestion</p>
                ) : (
                  <div className="mt-1 space-y-1">
                    <p>
                      <span className="font-medium">{suggestion.nature}</span> {suggestion.business_pct}% to {suggestion.category_id}
                      {suggestion.account_name ? ` - ${suggestion.account_name}` : ''}
                      {suggestion.account_type ? ` (${suggestion.account_type})` : ''}
                      <span className="text-slate-400"> ({suggestion.source}, confidence {suggestion.confidence})</span>
                    </p>
                    {suggestion.mapped_from ? (
                      <p className="text-slate-500 text-xs">Remapped from {suggestion.mapped_from} to match your {suggestion.active_template || activeTemplate} books.</p>
                    ) : null}
                    <p className="text-slate-400 text-xs">{suggestion.rationale}</p>
                    <button onClick={useSuggestion} className="text-xs text-blue-400 hover:text-blue-300 underline">
                      Use suggestion
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <label className="space-y-1">
                  <span className="text-xs text-slate-400">Nature (blank keeps suggestion)</span>
                  <select value={nature} onChange={(e) => setNature(e.target.value)} className="w-full p-2 bg-slate-900 border border-slate-700 rounded">
                    {NATURES.map((n) => (
                      <option key={n} value={n}>{n === '' ? 'auto' : n}</option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className="text-xs text-slate-400">Business % (blank keeps suggestion)</span>
                  <input value={businessPct} onChange={(e) => setBusinessPct(e.target.value)} inputMode="numeric" placeholder="0-100" className="w-full p-2 bg-slate-900 border border-slate-700 rounded" />
                </label>
                <label className="space-y-1 col-span-2">
                  <span className="text-xs text-slate-400">Category (auto keeps suggestion, {activeTemplate || 'books'} only - no new codes here)</span>
                  <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full p-2 bg-slate-900 border border-slate-700 rounded">
                    <option value="">auto (suggestion)</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.code}>{a.code} - {a.name} ({a.type})</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="border-t border-slate-800 pt-3 space-y-2">
                <h3 className="font-semibold text-xs uppercase tracking-wide text-slate-400">Fix fields (optional, reposts journals)</h3>
                <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} aria-label="Description" className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm" />
                <div className="grid grid-cols-2 gap-2">
                  <input value={editDate} onChange={(e) => setEditDate(e.target.value)} aria-label="Date" placeholder="YYYY-MM-DD" className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm" />
                  <input value={editRands} onChange={(e) => setEditRands(e.target.value)} aria-label="Amount in rands" inputMode="decimal" placeholder="-450.00" className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm" />
                </div>
              </div>

              <label className="block space-y-1">
                <span className="text-xs text-slate-400">Reason (required, kept forever for audit)</span>
                <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. till slip says 480" className="w-full p-2 bg-slate-900 border border-slate-700 rounded text-sm" />
              </label>
              <div className="flex gap-2">
                <button onClick={accept} disabled={working || !reason.trim()} className="bg-green-700 px-4 py-2 rounded text-sm disabled:opacity-50">
                  Accept and post
                </button>
                <button onClick={saveEdit} disabled={working || !reason.trim()} className="bg-blue-600 px-4 py-2 rounded text-sm disabled:opacity-50">
                  Save fixes
                </button>
                <button onClick={reject} disabled={working || !reason.trim()} className="bg-red-800 px-4 py-2 rounded text-sm disabled:opacity-50">
                  Reject / void
                </button>
              </div>

              {result ? <pre className="bg-slate-900 p-3 rounded text-xs whitespace-pre-wrap">{result}</pre> : null}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
