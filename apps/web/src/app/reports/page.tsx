'use client';
import React, { useState } from 'react';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import AccountSelector from '../../components/AccountSelector';
import { Me, downloadReport, getStoredAccount, setStoredAccount } from '../../lib/api';

type Item = {
  id: string;
  title: string;
  blurb: string;
  path: (from: string, to: string) => string;
  filename: string;
  dated: boolean;
  accounted: boolean;
};

const ITEMS: Item[] = [
  {
    id: 'excel',
    title: 'Excel workbook',
    blurb: '12 sheets: trial balance, journals, accounts, flags. Opens in Excel or LibreOffice.',
    path: (from, to) => `/v1/reports/excel${dates(from, to)}`,
    filename: 'finspy-workbook.xlsx',
    dated: true,
    accounted: true,
  },
  {
    id: 'powerbi',
    title: 'PowerBI pack',
    blurb: 'Star-schema CSVs plus a starter workbook. Import into PowerBI Desktop.',
    path: () => '/v1/reports/powerbi',
    filename: 'finspy-powerbi.zip',
    dated: false,
    accounted: true,
  },
  {
    id: 'auditor',
    title: 'Auditor CSV',
    blurb: 'One flat file of every transaction with its bookkeeping. Hand it to your accountant.',
    path: () => '/v1/reports/auditor-csv',
    filename: 'finspy-auditor.csv',
    dated: false,
    accounted: true,
  },
  {
    id: 'evidence',
    title: 'Evidence pack',
    blurb: 'Originals plus manifest plus audit chain, zipped for disputes. Verifiable offline.',
    path: () => '/v1/reports/evidence-pack',
    filename: 'finspy-evidence.zip',
    dated: false,
    accounted: true,
  },
  {
    id: 'signed',
    title: 'Signed PDF summary',
    blurb: 'PAdES-stamped totals for the period. Unsigned warning is shown, never hidden.',
    path: (from, to) => `/v1/reports/signed-pdf${dates(from, to)}`,
    filename: 'finspy-summary.pdf',
    dated: true,
    accounted: true,
  },
  {
    id: 'popia',
    title: 'My data (POPIA)',
    blurb: 'Everything held on you: profile, documents, books, flags, audit trail, originals.',
    path: () => '/v1/me/export',
    filename: 'finspy-my-data.zip',
    dated: false,
    accounted: true,
  },
];

function dates(from: string, to: string): string {
  const q = new URLSearchParams();
  if (from) q.set('from_date', from);
  if (to) q.set('to_date', to);
  const s = q.toString();
  return s ? `?${s}` : '';
}

export default function ReportsPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <ReportsInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function ReportsInner({ uid, me }: { uid: string; me: Me }) {
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [account, setAccount] = useState(() => getStoredAccount());
  const [working, setWorking] = useState('');
  const [warning, setWarning] = useState('');
  const [error, setError] = useState('');

  function pickAccount(acct: string) {
    setAccount(acct);
    setStoredAccount(acct);
  }

  async function download(item: Item) {
    setWorking(item.id);
    setError('');
    setWarning('');
    try {
      let path = item.path(from, to);
      if (item.accounted && account) {
        path += `${path.includes('?') ? '&' : '?'}account_number=${encodeURIComponent(account)}`;
      }
      const warn = await downloadReport(uid, path, item.filename);
      if (warn) setWarning(warn);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed');
    } finally {
      setWorking('');
    }
  }

  return (
    <main className="p-6 max-w-3xl mx-auto space-y-4">
      <SessionBar me={me} />
      <h1 className="text-2xl font-bold">Reports</h1>
      <p className="text-sm text-slate-400">
        Generated live from your books on every click. Nothing here is a sample.
      </p>
      <div className="flex gap-3 text-sm items-end">
        <label className="space-y-1">
          <span className="text-xs text-slate-400">From (dated reports)</span>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="block p-2 bg-slate-900 border border-slate-700 rounded" />
        </label>
        <label className="space-y-1">
          <span className="text-xs text-slate-400">To (dated reports)</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="block p-2 bg-slate-900 border border-slate-700 rounded" />
        </label>
        <AccountSelector uid={uid} value={account} onChange={pickAccount} />
      </div>
      <p className="text-xs text-slate-500">
        Every download respects the account picker: pick an account and the file contains only that
        account&apos;s rows and originals. &quot;All accounts&quot; exports the whole tenant.
      </p>
      <p className="text-sm">
        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-200">
          Scope: {account === '__unknown' ? 'Unknown account' : account || 'Whole tenant'}
        </span>{' '}
        {account ? (
          <span className="text-xs text-slate-400">safe to share for this account only</span>
        ) : (
          <span className="text-xs text-amber-300">contains every account on this login - do not share if you hold accounts for others</span>
        )}
      </p>
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {warning ? <p className="text-sm text-amber-300">Warning: {warning}</p> : null}
      <ul className="space-y-2">
        {ITEMS.map((item) => (
          <li key={item.id} className="p-4 bg-slate-900 border border-slate-800 rounded flex justify-between items-center gap-3">
            <div>
              <p className="font-medium">{item.title}</p>
              <p className="text-xs text-slate-400">{item.blurb}</p>
            </div>
            <button
              onClick={() => download(item)}
              disabled={working === item.id}
              className="bg-blue-700 px-4 py-2 rounded text-sm disabled:opacity-50 shrink-0"
            >
              {working === item.id ? 'Working...' : 'Download'}
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
