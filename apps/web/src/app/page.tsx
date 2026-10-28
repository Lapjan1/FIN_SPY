'use client';
import React from 'react';
import { KpiCards } from '../components/KpiCards';
import SourceViewer from '../components/SourceViewer';

export default function HomePage() {
  return (
    <main className="max-w-6xl mx-auto p-6 space-y-8">
      <div className="text-center py-12">
        <h1 className="text-4xl font-bold">Your money has a stalker. Find it.</h1>
        <p className="mt-4 text-slate-400">Upload any SA bank PDF - every number traces to exact bbox, SHA256 vault + hash-chain audit, dynamic books, spy for leaks, KPI peek + debt kill plan.</p>
        <div className="mt-6 flex justify-center gap-4">
          <a href="/account" className="bg-blue-600 px-6 py-2 rounded">Upload PDF</a>
          <a href="/review" className="border border-slate-700 px-6 py-2 rounded">Review queue</a>
          <a href="/privacy" className="border border-slate-700 px-6 py-2 rounded">See Privacy POPIA</a>
        </div>
        <p className="mt-3 text-xs text-slate-500">Built with Meta Muse Spark/Wonder/Image/SAM 3.1 - Startup track - commits during Oct26-Nov4</p>
      </div>

      <KpiCards kpis={[
        {label:"Leak Score R/mo",value:"R187",delta:"+R12 vs last month",accent:"leak"},
        {label:"Runway months",value:"4.5",delta:"burn R25k/mo"},
        {label:"Savings Rate",value:"12.5%",delta:"private vs business 35%"},
        {label:"Trial Pages Remaining",value:"20",delta:"Free plan"},
      ]} />

      <div className="grid md:grid-cols-2 gap-6">
        <div className="border border-slate-800 rounded p-4">
          <h3 className="font-semibold mb-2">Hero Demo Flow (2-3 min)</h3>
          <ol className="list-decimal pl-5 text-sm text-slate-400 space-y-1">
            <li>Problem: pile PDFs no proof</li>
            <li>Upload 3 statements - hash + timestamp appear vault immutable</li>
            <li>Extraction line-ID grounding + reconciliation gate opening+sum=closing</li>
            <li>Private vs business AI rationale mixed split merchant memory</li>
            <li>Dashboard click bar - grid - PDF page highlighted bbox (pdf.js)</li>
            <li>Forensic flags duplicate F-010 Benford F-020 + Leak Score</li>
            <li>KPI peek runway burn savings + debt snowball vs avalanche</li>
            <li>Generate Excel live SUMIFS + signed PAdES PDF + Evidence Pack ZIP verify_pack.py</li>
            <li>Billing test-mode Paystack + Built with Meta</li>
          </ol>
        </div>
        <SourceViewer docSha256="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4" pageNo={3} lineIds={["L012","L013"]} bboxes={[{line_id:"L012",x0:10,y0:20,x1:90,y1:25}]} />
      </div>

      <div className="border border-slate-800 rounded p-4">
        <h3 className="font-semibold">Architecture - DB-first per AGENTS.md</h3>
        <pre className="text-xs text-slate-400 mt-2 whitespace-pre-wrap">Browser Next.js → FastAPI /v1 → Vault content-hash SHA256 → Queue SQLite→Postgres → Worker intake→hash→text+bbox→extract→reconcile → LLM Meta Adapter freellmapi:3001 dev llama.com 1.3 prod → SQLite fin_spy.db Supabase RLS audit_log hash-chain → Spy Engine subscription/duplicate/fee/anomaly → KPI Engine → Dashboard API + Chat tool-calling → Reports Excel+Signed PDF+Evidence Pack</pre>
      </div>
    </main>
  );
}
