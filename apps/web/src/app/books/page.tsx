'use client';
import React, { useEffect, useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import {
  Me,
  BookTemplate,
  TrialBalance,
  SuspenseStatus,
  fetchBookTemplates,
  fetchActiveBook,
  selectBook,
  fetchTrialBalance,
  fetchSuspense,
} from '../../lib/api';

function rands(minor: number): string {
  return `R${(minor / 100).toFixed(2)}`;
}

export default function BooksPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <BooksInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function BooksInner({ uid, me }: { uid: string; me: Me }) {
  const [templates, setTemplates] = useState<BookTemplate[]>([]);
  const [active, setActive] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [trial, setTrial] = useState<TrialBalance | null>(null);
  const [suspense, setSuspense] = useState<SuspenseStatus | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load(acct: string) {
    setError('');
    try {
      const [tmpls, act, tb, sus] = await Promise.all([
        fetchBookTemplates(uid),
        fetchActiveBook(uid),
        fetchTrialBalance(uid, acct || undefined),
        fetchSuspense(uid),
      ]);
      setTemplates(tmpls.templates);
      setActive(act.active_template);
      setTrial(tb);
      setSuspense(sus);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load books');
    }
  }

  useEffect(() => {
    load('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid]);

  async function switchTemplate(template: string) {
    setError('');
    setNotice('');
    try {
      const res = await selectBook(uid, template);
      setActive(res.active_template);
      setNotice(res.message);
      await load(accountNumber);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Switch failed');
    }
  }

  function applyFilter(e: React.FormEvent) {
    e.preventDefault();
    load(accountNumber.trim());
  }

  const rows = (trial?.lines || []).filter((l) => l.debits !== 0 || l.credits !== 0);

  return (
    <main className="p-6 max-w-4xl mx-auto space-y-4">
      <SessionBar me={me} />
      <h1 className="text-2xl font-bold">Books</h1>
      <p className="text-sm text-slate-400">
        Your chart of accounts, trial balance, and parked money. Every figure comes
        from posted journals, never a sample.
      </p>
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {notice ? <p className="text-sm text-emerald-300">{notice}</p> : null}

      <section className="p-4 bg-slate-900 border border-slate-800 rounded space-y-2">
        <h2 className="font-medium">Active books: {active || '...'}</h2>
        <div className="flex flex-wrap gap-2 text-sm">
          {templates.map((t) => (
            <button
              key={t.name}
              onClick={() => switchTemplate(t.name)}
              disabled={t.name === active}
              title={t.description}
              className="px-3 py-1 rounded border border-slate-700 disabled:opacity-50 disabled:border-emerald-700"
            >
              {t.name} ({t.count})
            </button>
          ))}
        </div>
        <form onSubmit={applyFilter} className="flex gap-2 items-end text-sm pt-2">
          <label className="space-y-1">
            <span className="text-xs text-slate-400">Bank account number (blank = all)</span>
            <input
              value={accountNumber}
              onChange={(e) => setAccountNumber(e.target.value)}
              placeholder="e.g. 62123456789"
              className="block p-2 bg-slate-950 border border-slate-700 rounded w-64"
            />
          </label>
          <button type="submit" className="bg-blue-700 px-4 py-2 rounded text-sm">
            Apply
          </button>
        </form>
      </section>

      <section className="p-4 bg-slate-900 border border-slate-800 rounded space-y-2">
        <h2 className="font-medium">
          Trial balance{trial?.account_number ? ` — ${trial.account_number}` : ' — all accounts'}
        </h2>
        {!trial ? (
          <p className="text-sm text-slate-400">Loading...</p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-slate-400">
            No postings yet. Accept transactions in Review to build these books.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-1">Code</th>
                <th className="py-1">Account</th>
                <th className="py-1 text-right">Debits</th>
                <th className="py-1 text-right">Credits</th>
                <th className="py-1 text-right">Net</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l) => (
                <tr key={l.account_id || l.code} className="border-b border-slate-800">
                  <td className="py-1 font-mono">{l.code}</td>
                  <td className="py-1">{l.name}</td>
                  <td className="py-1 text-right font-mono">{rands(l.debits)}</td>
                  <td className="py-1 text-right font-mono">{rands(l.credits)}</td>
                  <td className="py-1 text-right font-mono">{rands(l.net)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-medium">
                <td className="py-1" colSpan={2}>Total</td>
                <td className="py-1 text-right font-mono">{rands(trial.total_debits)}</td>
                <td className="py-1 text-right font-mono">{rands(trial.total_credits)}</td>
                <td className="py-1 text-right font-mono">
                  {trial.balanced ? 'Balanced' : 'OUT OF BALANCE'}
                </td>
              </tr>
            </tfoot>
          </table>
        )}
      </section>

      <section className="p-4 bg-slate-900 border border-slate-800 rounded space-y-2">
        <h2 className="font-medium">Suspense (9999) watchdog</h2>
        {!suspense ? (
          <p className="text-sm text-slate-400">Loading...</p>
        ) : (
          <div className="text-sm space-y-1">
            <p>
              Status:{' '}
              <span className={suspense.status === 'ok' ? 'text-emerald-300' : 'text-amber-300'}>
                {suspense.status === 'ok' ? 'Clear' : 'Needs review'}
              </span>
            </p>
            <p>Parked: {rands(suspense.balance_minor)} across {suspense.txn_count} transaction(s)</p>
            {suspense.oldest_age_days !== null ? (
              <p>Oldest item: {suspense.oldest_age_days} day(s)</p>
            ) : null}
            {suspense.unposted_confirmed_count > 0 ? (
              <p className="text-amber-300">
                {suspense.unposted_confirmed_count} confirmed transaction(s) have no journal entry.
              </p>
            ) : null}
            {suspense.reasons.length > 0 ? (
              <ul className="list-disc pl-5 text-amber-200">
                {suspense.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </section>
    </main>
  );
}
