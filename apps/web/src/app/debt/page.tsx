'use client';
import React, { useEffect, useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import {
  Me,
  DebtInput,
  DebtPlan,
  DebtDefaults,
  fetchDebtDefaults,
  postDebtPlan,
} from '../../lib/api';

function rands(minor: number): string {
  return `R${(minor / 100).toFixed(2)}`;
}

function emptyDebt(): DebtInput {
  return { creditor: '', balance_minor: 0, apr_pct: '', min_payment_minor: 0 };
}

export default function DebtPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <DebtInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function DebtInner({ uid, me }: { uid: string; me: Me }) {
  const [debts, setDebts] = useState<DebtInput[]>([emptyDebt()]);
  const [method, setMethod] = useState('snowball');
  const [extra, setExtra] = useState('');
  const [defaults, setDefaults] = useState<DebtDefaults | null>(null);
  const [plan, setPlan] = useState<DebtPlan | null>(null);
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  useEffect(() => {
    fetchDebtDefaults(uid)
      .then((d) => {
        setDefaults(d);
        setExtra((d.extra_cash_default_minor / 100).toFixed(2));
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load defaults'));
  }, [uid]);

  function setRow(i: number, patch: Partial<DebtInput>) {
    setDebts((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  async function compute(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setPlan(null);
    const rows = debts.filter((d) => d.creditor.trim() && d.balance_minor > 0);
    if (rows.length === 0) {
      setError('Add at least one debt with a creditor and a balance.');
      return;
    }
    const extraMinor = Math.round(parseFloat(extra || '0') * 100);
    if (!Number.isFinite(extraMinor) || extraMinor < 0) {
      setError('Extra cash must be a non-negative rand amount.');
      return;
    }
    setWorking(true);
    try {
      const res = await postDebtPlan(uid, rows, method, extraMinor);
      setPlan(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Plan failed');
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="p-6 max-w-4xl mx-auto space-y-4">
      <SessionBar me={me} />
      <h1 className="text-2xl font-bold">Kill debt</h1>
      <p className="text-sm text-slate-400">
        Snowball pays the smallest balance first; avalanche pays the highest APR first.
        Type your debts below. Extra cash is prefilled from your average monthly
        surplus{defaults && defaults.months > 0 ? ` (${rands(defaults.avg_net_per_month_minor)}/month over ${defaults.months} month(s))` : ' (no postings yet, so R0.00)'};
        change it freely.
      </p>
      {error ? <p className="text-sm text-red-400">{error}</p> : null}

      <form onSubmit={compute} className="p-4 bg-slate-900 border border-slate-800 rounded space-y-3">
        {debts.map((d, i) => (
          <div key={i} className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Creditor</span>
              <input
                value={d.creditor}
                onChange={(e) => setRow(i, { creditor: e.target.value })}
                placeholder="e.g. Bank"
                className="block w-full p-2 bg-slate-950 border border-slate-700 rounded"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Balance (R)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={d.balance_minor ? (d.balance_minor / 100).toString() : ''}
                onChange={(e) => setRow(i, { balance_minor: Math.round(parseFloat(e.target.value || '0') * 100) })}
                className="block w-full p-2 bg-slate-950 border border-slate-700 rounded"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">APR %</span>
              <input
                value={d.apr_pct}
                onChange={(e) => setRow(i, { apr_pct: e.target.value })}
                placeholder="e.g. 21"
                className="block w-full p-2 bg-slate-950 border border-slate-700 rounded"
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-slate-400">Min payment (R)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={d.min_payment_minor ? (d.min_payment_minor / 100).toString() : ''}
                onChange={(e) => setRow(i, { min_payment_minor: Math.round(parseFloat(e.target.value || '0') * 100) })}
                className="block w-full p-2 bg-slate-950 border border-slate-700 rounded"
              />
            </label>
          </div>
        ))}
        <div className="flex flex-wrap gap-2 items-end text-sm">
          <button
            type="button"
            onClick={() => setDebts((rows) => [...rows, emptyDebt()])}
            className="px-3 py-2 rounded border border-slate-700"
          >
            Add debt
          </button>
          <label className="space-y-1">
            <span className="text-xs text-slate-400">Method</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="block p-2 bg-slate-950 border border-slate-700 rounded"
            >
              <option value="snowball">Snowball (smallest first)</option>
              <option value="avalanche">Avalanche (highest APR first)</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-xs text-slate-400">Extra cash / month (R)</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              className="block p-2 bg-slate-950 border border-slate-700 rounded w-40"
            />
          </label>
          <button type="submit" disabled={working} className="bg-blue-700 px-4 py-2 rounded text-sm disabled:opacity-50">
            {working ? 'Working...' : 'Compute plan'}
          </button>
        </div>
      </form>

      {plan ? (
        <section className="p-4 bg-slate-900 border border-slate-800 rounded space-y-2">
          <h2 className="font-medium">Plan: {plan.method}</h2>
          <p className="text-sm">{plan.narrative}</p>
          {plan.warnings.length > 0 ? (
            <ul className="list-disc pl-5 text-sm text-amber-200">
              {plan.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-1">#</th>
                <th className="py-1">Pay first</th>
              </tr>
            </thead>
            <tbody>
              {plan.order.map((creditor, i) => (
                <tr key={i} className="border-b border-slate-800">
                  <td className="py-1 font-mono">{i + 1}</td>
                  <td className="py-1">{creditor}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <div><p className="text-xs text-slate-400">Months</p><p className="font-mono">{plan.months}</p></div>
            <div><p className="text-xs text-slate-400">Total paid</p><p className="font-mono">{rands(plan.total_paid_minor)}</p></div>
            <div><p className="text-xs text-slate-400">Total interest</p><p className="font-mono">{rands(plan.total_interest_minor)}</p></div>
            <div><p className="text-xs text-slate-400">Saved vs other method</p><p className="font-mono">{rands(plan.interest_saved_minor)}</p></div>
          </div>
          {plan.what_if ? (
            <div className="text-sm pt-2 border-t border-slate-800">
              <p className="font-medium">What-if: extra {rands(plan.what_if.extra_per_month_minor)}/month</p>
              <p>
                {plan.what_if.base_months} months → {plan.what_if.boosted_months} months
                ({plan.what_if.months_saved} saved), interest {rands(plan.what_if.base_interest_minor)} → {rands(plan.what_if.boosted_interest_minor)}.
              </p>
            </div>
          ) : null}
          <p className="text-xs text-slate-500 pt-2">Disclaimer: {plan.disclaimer}</p>
        </section>
      ) : null}
    </main>
  );
}
