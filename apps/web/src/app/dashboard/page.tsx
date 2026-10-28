'use client';
import React, { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { KpiCards } from '../../components/KpiCards';
import {
  DashboardSummary,
  Flag,
  fetchDashboard,
  fetchFlags,
  formatRands,
  runSpy,
} from '../../lib/api';

export default function DashboardPage() {
  const [userId, setUserId] = useState('');
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
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
      const [summary, flagList] = await Promise.all([
        fetchDashboard(userId),
        fetchFlags(userId).catch(() => [] as Flag[]),
      ]);
      setData(summary);
      setFlags(flagList);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Load failed');
    } finally {
      setLoading(false);
    }
  }

  async function spy() {
    if (!userId) return;
    setLoading(true);
    setError('');
    try {
      await runSpy(userId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Spy run failed');
    } finally {
      setLoading(false);
    }
  }

  const months = data?.totals
    ? Array.from(new Set([
      ...Object.keys(data.totals.monthly_inflow),
      ...Object.keys(data.totals.monthly_outflow),
    ])).sort()
    : [];
  const chartOption = {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: { trigger: 'axis' },
    legend: { data: ['Inflow', 'Outflow'], textStyle: { color: '#94a3b8' } },
    xAxis: { type: 'category', data: months },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'Inflow',
        type: 'bar',
        data: months.map((m) => (data?.totals?.monthly_inflow[m] || 0) / 100),
        itemStyle: { color: '#22c55e' },
      },
      {
        name: 'Outflow',
        type: 'bar',
        data: months.map((m) => (data?.totals?.monthly_outflow[m] || 0) / 100),
        itemStyle: { color: '#f43f5e' },
      },
    ],
  };

  return (
    <main className="max-w-6xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard - every number traces to source</h1>
        <p className="text-sm text-slate-400 mt-1">
          Live KPIs from your books ({data?.active_template || 'no data yet'}). Click any transaction to drill to the exact line on the original PDF.
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
        <button onClick={spy} disabled={loading || !userId} className="bg-rose-700 px-4 py-2 rounded disabled:opacity-50">
          Run spy
        </button>
      </div>

      {error ? <div className="border border-red-800 bg-red-950 p-3 rounded text-sm">{error}</div> : null}

      {data ? (
        <>
          <KpiCards
            kpis={[
              { label: 'Net flow', value: formatRands(data.net_flow_minor), delta: `${data.totals?.txn_count || 0} txns` },
              { label: 'Leak / month', value: formatRands(data.leak_score_per_month_minor), accent: 'leak', delta: 'subscriptions' },
              { label: 'Burn / month', value: formatRands(data.burn_rate_minor), delta: `runway ${data.runway_months} mo` },
              { label: 'Savings rate', value: `${data.savings_rate_pct}%`, delta: `in ${formatRands(data.inflow_minor)} out ${formatRands(data.outflow_minor)}` },
            ]}
          />

          <div className="border border-slate-800 rounded p-4">
            <h2 className="font-semibold text-sm mb-2">Monthly cashflow (R)</h2>
            {months.length === 0 ? (
              <p className="text-sm text-slate-400">No monthly data yet - upload a statement first.</p>
            ) : (
              <ReactECharts option={chartOption} style={{ height: 280 }} />
            )}
          </div>

          <div className="border border-slate-800 rounded">
            <div className="p-3 border-b border-slate-800 font-semibold text-sm">Spy flags ({flags.length})</div>
            {flags.length === 0 ? (
              <p className="p-4 text-sm text-slate-400">No flags - press Run spy after uploading statements.</p>
            ) : (
              <ul className="divide-y divide-slate-800 max-h-64 overflow-auto">
                {flags.map((f) => (
                  <li key={f.id} className="p-3 text-sm flex justify-between gap-2">
                    <span className="font-mono">{f.test_id}</span>
                    <span className="text-slate-400 truncate">{(f.result_json || '').slice(0, 120)}</span>
                    <span className="text-xs text-slate-500">{f.severity || ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : (
        !loading && <p className="text-sm text-slate-400">Load to see live KPIs from your ledger.</p>
      )}
    </main>
  );
}
