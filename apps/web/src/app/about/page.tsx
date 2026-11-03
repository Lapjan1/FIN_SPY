import React from 'react';

const linkCls = 'text-blue-400 underline';

export default function AboutPage() {
  return (
    <main className="max-w-3xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold">About FIN_SPY</h1>
        <p className="mt-2 text-slate-300">
          Financial Surveillance &amp; Peak Insights: upload a South African bank statement,
          and every number is traced to its exact position on the original page.
        </p>
      </div>

      <section>
        <h2 className="text-xl font-semibold mb-3">What it does</h2>
        <ul className="list-disc pl-6 space-y-2 text-sm text-slate-300">
          <li>Reads SA bank PDFs (plus CSV/OFX) into dated transactions with running balances.</li>
          <li>Checks every extraction against the statement totals before you see it.</li>
          <li>Builds double-entry books from your transactions, with private/business splits you approve.</li>
          <li>Watches for leaks: subscriptions, duplicates, and unusual charges.</li>
          <li>Exports evidence packs, Excel workbooks, and auditor CSVs.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">Honest limits</h2>
        <ul className="list-disc pl-6 space-y-2 text-sm text-slate-300">
          <li>Single-line rows only: a transaction split across two printed lines may need manual capture.</li>
          <li>Rows need an amount and a running balance to be verified; rows without them stay unaccounted, never invented.</li>
          <li>Each bank prints differently; a layout we have not seen yet may extract partially. Tell us via <a href="/contact" className={linkCls}>Contact</a>.</li>
          <li>Nothing here is legal, tax, or financial advice - your accountant signs off, FIN_SPY supplies the evidence.</li>
        </ul>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">How your data is handled</h2>
        <p className="text-sm text-slate-300">
          Originals are stored content-addressed by SHA256 and never modified. AI assists with
          reading and suggestions; a human always decides, and every report discloses AI use.
          Details in <a href="/privacy" className={linkCls}>Privacy</a>, <a href="/terms" className={linkCls}>Terms</a>,
          and <a href="/refund" className={linkCls}>Refunds</a>.
        </p>
      </section>

    </main>
  );
}
