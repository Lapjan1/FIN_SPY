'use client';
import React, { useEffect, useState } from 'react';
import { API_BASE } from '../lib/api';

type ApiState = 'checking' | 'online' | 'unreachable';

function ApiStatus() {
  const [state, setState] = useState<ApiState>('checking');
  useEffect(() => {
    let live = true;
    fetch(`${API_BASE}/health/ready`)
      .then((r) => (live ? setState(r.ok ? 'online' : 'unreachable') : undefined))
      .catch(() => (live ? setState('unreachable') : undefined));
    return () => {
      live = false;
    };
  }, []);
  const style =
    state === 'online'
      ? 'bg-green-900 text-green-200'
      : state === 'unreachable'
        ? 'bg-amber-900 text-amber-200'
        : 'bg-slate-800 text-slate-300';
  const label =
    state === 'online' ? 'API online' : state === 'unreachable' ? 'API unreachable' : 'Checking API';
  return <span className={`px-2 py-0.5 rounded text-xs ${style}`}>{label}</span>;
}

export default function HomePage() {
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-10">
      <div className="py-10 flex flex-col md:flex-row md:items-end gap-6">
        <div className="flex-1">
          <h1 className="text-4xl font-bold">Every rand, traced to the page.</h1>
          <p className="mt-4 text-slate-300 max-w-2xl">
            Upload any South African bank statement. FIN_SPY extracts every transaction,
            pins each one to the exact line on your original PDF, builds your books,
            hunts leaks and duplicate fees, and exports court-ready reports.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href="/upload" className="bg-blue-600 px-6 py-2 rounded">Upload a statement</a>
            <a href="/review" className="border border-slate-700 px-6 py-2 rounded">Review queue</a>
            <a href="/dashboard" className="border border-slate-700 px-6 py-2 rounded">Dashboard</a>
          </div>
        </div>
        <div className="flex flex-col items-start gap-2">
          <ApiStatus />
          <p className="text-xs text-slate-500">Free trial: 20 pages, no card required.</p>
        </div>
      </div>

      <section>
        <h2 className="text-xl font-semibold mb-4">What you get</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="border border-slate-800 rounded p-4">
            <h3 className="font-semibold">1. Proof, not just numbers</h3>
            <p className="text-sm text-slate-300 mt-1">
              Click any transaction to see the exact highlighted line on your original
              statement. SHA256 vault plus hash-chained audit log, ready for your
              accountant or a dispute.
            </p>
          </div>
          <div className="border border-slate-800 rounded p-4">
            <h3 className="font-semibold">2. Books that build themselves</h3>
            <p className="text-sm text-slate-300 mt-1">
              Private vs business classification with merchant memory, double-entry
              journals, and trial balances per bank account. You confirm or correct
              with a reason; every change is revisioned.
            </p>
          </div>
          <div className="border border-slate-800 rounded p-4">
            <h3 className="font-semibold">3. A spy for your leaks</h3>
            <p className="text-sm text-slate-300 mt-1">
              Recurring subscriptions, duplicates, bank fees, and anomalies flagged
              automatically, with a monthly leak score and KPIs: runway, burn,
              savings rate.
            </p>
          </div>
          <div className="border border-slate-800 rounded p-4">
            <h3 className="font-semibold">4. A plan to kill debt</h3>
            <p className="text-sm text-slate-300 mt-1">
              Snowball vs avalanche payoff plans computed on your real cashflow,
              plus Excel, signed PDF, and evidence-pack exports your auditor can
              verify independently.
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4">How it works</h2>
        <ol className="grid md:grid-cols-3 gap-4 text-sm">
          <li className="border border-slate-800 rounded p-4">
            <span className="font-bold text-blue-400">Step 1 — Upload.</span>{' '}
            <span className="text-slate-300">
              Drop in a PDF. It is hashed into an immutable vault and queued for
              extraction with a reconciliation gate.
            </span>
          </li>
          <li className="border border-slate-800 rounded p-4">
            <span className="font-bold text-blue-400">Step 2 — Check and decide.</span>{' '}
            <span className="text-slate-300">
              Confirm extractions in the review queue and accept private/business
              suggestions. Nothing posts without your say-so.
            </span>
          </li>
          <li className="border border-slate-800 rounded p-4">
            <span className="font-bold text-blue-400">Step 3 — Peek and export.</span>{' '}
            <span className="text-slate-300">
              Drill any dashboard number back to source, ask Spy Chat, then export
              Excel, signed PDF, or a verifiable evidence pack.
            </span>
          </li>
        </ol>
      </section>

      <section className="border border-slate-800 rounded p-4 flex flex-col md:flex-row md:items-center gap-3 justify-between">
        <p className="text-sm text-slate-300">
          Built with Meta Muse Spark, Wonder, Image, and SAM 3.1. Your documents are
          processed under POPIA-aware handling; hosted AI only ever sees what you approve.
        </p>
        <div className="flex gap-3 text-sm shrink-0">
          <a href="/privacy" className="text-blue-400 underline">Privacy</a>
          <a href="/terms" className="text-blue-400 underline">Terms</a>
          <a href="/refund" className="text-blue-400 underline">Refunds</a>
        </div>
      </section>
    </main>
  );
}
