'use client';
import React, { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { KpiCards } from '../../components/KpiCards';
import RequireSession, { SessionBar } from '../../components/RequireSession';
import {
  DashboardSummary,
  Flag,
  Me,
  fetchDashboard,
  fetchFlags,
  formatRands,
  runSpy,
} from '../../lib/api';

export default function DashboardPage() {
  return (
    <RequireSession>
      {({ uid, me }) => <DashboardInner uid={uid} me={me} />}
    </RequireSession>
  );
}

function DashboardInner({ uid, me }: { uid: string; me: Me }) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    setLoading(true);
    setError('');
    try {
      const [summary, flagList] = await Promise.all([
        fetchDashboard(uid),
        fetchFlags(uid).catch(() => [] as Flag[]),
      ]);
      setData(summary);
      setFlags(flagList);
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

  async function spy() {
    setLoading(true);
    setError('');
    try {
      await runSpy(uid);
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
  const inflowR = (data?.inflow_minor || 0) / 100;
  const outflowR = (data?.outflow_minor || 0) / 100;
  const netR = (data?.net_flow_minor || 0) / 100;
  const waterfallOption = {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'category', data: ['Inflow', 'Outflow', 'Net'] },
    yAxis: { type: 'value' },
    series: [
      {
        name: 'assist', type: 'bar', stack: 'total',
        itemStyle: { borderColor: 'transparent', color: 'transparent' },
        emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
        data: [0, netR, 0],
      },
      {
        name: 'flow', type: 'bar', stack: 'total',
        data: [
          { value: inflowR, itemStyle: { color: '#22c55e' } },
          { value: outflowR, itemStyle: { color: '#f43f5e' } },
          { value: netR, itemStyle: { color: '#3b82f6' } },
        ],
      },
    ],
  };

  const treemapData = data?.totals
    ? Object.entries(data.totals.vendor_counts)
      .map(([name, minor]) => ({ name, value: Math.round((minor / 100) * 100) / 100 }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 12)
    : [];
  const treemapOption = {
    backgroundColor: 'transparent',
    textStyle: { color: '#e2e8f0' },
    tooltip: { formatter: (p: { name: string; value: number }) => `${p.name}: R${p.value}` },
    series: [{ type: 'treemap', data: treemapData, label: { color: '#e2e8f0' } }],
  };

  const radarSubs = flags
    .filter((f) => f.test_id === 'SUB')
    .map((f) => {
      try {
        return JSON.parse(f.result_json || '{}') as { merchant?: string; monthly_cost_minor?: number };
      } catch {
        return {};
      }
    })
    .filter((s): s is { merchant: string; monthly_cost_minor: number } =>
      typeof s.merchant === 'string' && typeof s.monthly_cost_minor === 'number')
    .sort((a, b) => b.monthly_cost_minor - a.monthly_cost_minor)
    .slice(0, 6);
  const radarMerchants = radarSubs.map((s) => s.merchant);
  const radarMax = Math.max(...radarSubs.map((s) => s.monthly_cost_minor / 100), 1);
  const radarOption = {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: {},
    radar: {
      indicator: radarMerchants.map((m) => ({ name: m, max: radarMax })),
      axisName: { color: '#94a3b8' },
    },
    series: [{
      type: 'radar',
      data: [{ value: radarSubs.map((s) => s.monthly_cost_minor / 100), name: 'R/mo',
        itemStyle: { color: '#f43f5e' }, areaStyle: { opacity: 0.25 } }],
    }],
  };

  const heatRows = ['Inflow', 'Outflow', 'Net'];
  const heatData: Array<[number, number, number]> = [];
  months.forEach((m, xi) => {
    const inflow = (data?.totals?.monthly_inflow[m] || 0) / 100;
    const outflow = (data?.totals?.monthly_outflow[m] || 0) / 100;
    heatData.push([xi, 0, Math.round(inflow * 100) / 100]);
    heatData.push([xi, 1, Math.round(outflow * 100) / 100]);
    heatData.push([xi, 2, Math.round((inflow - outflow) * 100) / 100]);
  });
  const heatMax = Math.max(1, ...heatData.map((d) => Math.abs(d[2])));
  const heatmapOption = {
    backgroundColor: 'transparent',
    textStyle: { color: '#94a3b8' },
    tooltip: {
      formatter: (p: { value: [number, number, number] }) =>
        `${months[p.value[0]]} ${heatRows[p.value[1]]}: R${p.value[2]}`,
    },
    grid: { height: '50%', top: '10%' },
    xAxis: { type: 'category', data: months, splitArea: { show: true } },
    yAxis: { type: 'category', data: heatRows, splitArea: { show: true } },
    visualMap: {
      min: -heatMax, max: heatMax, calculable: true, orient: 'horizontal',
      left: 'center', bottom: '0%', inRange: { color: ['#f43f5e', '#1e293b', '#22c55e'] },
      textStyle: { color: '#94a3b8' },
    },
    series: [{ type: 'heatmap', data: heatData, label: { show: false } }],
  };

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

      <SessionBar me={me} />

      <div className="flex gap-2 items-center">
        <button onClick={load} disabled={loading} className="bg-blue-600 px-4 py-2 rounded disabled:opacity-50">
          {loading ? 'Loading' : 'Reload'}
        </button>
        <button onClick={spy} disabled={loading} className="bg-rose-700 px-4 py-2 rounded disabled:opacity-50">
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

          <div className="grid md:grid-cols-2 gap-6">
            <div className="border border-slate-800 rounded p-4">
              <h2 className="font-semibold text-sm mb-2">Flow waterfall (R)</h2>
              <ReactECharts option={waterfallOption} style={{ height: 260 }} />
            </div>
            <div className="border border-slate-800 rounded p-4">
              <h2 className="font-semibold text-sm mb-2">Outflow by vendor</h2>
              {treemapData.length === 0 ? (
                <p className="text-sm text-slate-400">No vendor data yet.</p>
              ) : (
                <ReactECharts option={treemapOption} style={{ height: 260 }} />
              )}
            </div>
          </div>

          <div className="border border-slate-800 rounded p-4">
            <h2 className="font-semibold text-sm mb-2">Monthly intensity (R)</h2>
            {months.length === 0 ? (
              <p className="text-sm text-slate-400">No monthly data yet.</p>
            ) : (
              <ReactECharts option={heatmapOption} style={{ height: 220 }} />
            )}
          </div>

          <div className="border border-slate-800 rounded p-4">
            <h2 className="font-semibold text-sm mb-2">Subscription radar (R/mo)</h2>
            {radarMerchants.length === 0 ? (
              <p className="text-sm text-slate-400">No subscriptions detected - press Run spy to scan.</p>
            ) : (
              <ReactECharts option={radarOption} style={{ height: 300 }} />
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
        !loading && <p className="text-sm text-slate-400">Loading live KPIs from your ledger.</p>
      )}
    </main>
  );
}
