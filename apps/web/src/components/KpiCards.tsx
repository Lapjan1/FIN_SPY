'use client';
import React from 'react';

type Kpi = { label: string; value: string; delta?: string; accent?: 'leak'|'success'|'warning' };

export function KpiCards({ kpis }: { kpis: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {kpis.map(k => (
        <div key={k.label} className={`p-4 rounded border bg-slate-900 ${k.accent==='leak' ? 'border-rose-500' : 'border-slate-700'}`}>
          <div className="text-xs opacity-60">{k.label}</div>
          <div className="text-xl font-mono mt-1">{k.value}</div>
          {k.delta && <div className="text-xs mt-1 opacity-70">{k.delta}</div>}
        </div>
      ))}
    </div>
  );
}
