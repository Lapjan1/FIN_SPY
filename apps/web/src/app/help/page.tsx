import React from 'react';

const stepCls = 'border border-slate-800 rounded p-4';
const linkCls = 'text-blue-400 underline';

export default function HelpPage() {
  return (
    <main className="max-w-4xl mx-auto p-6 space-y-10">
      <div>
        <h1 className="text-3xl font-bold">Help - how FIN_SPY works</h1>
        <p className="mt-2 text-slate-300">
          The short version: upload a statement, check what was read, then peek at your money.
          Everything below links straight into the app.
        </p>
      </div>

      <section>
        <h2 className="text-xl font-semibold mb-4">The sequence: three steps</h2>
        <ol className="grid md:grid-cols-3 gap-4 text-sm">
          <li className={stepCls}>
            <span className="font-bold text-blue-400">Step 1 - Upload.</span>{' '}
            <span className="text-slate-300">
              Drop in a bank statement (PDF, CSV or OFX) on <a href="/upload" className={linkCls}>Upload</a>.
              It is hashed into an immutable vault and queued for extraction behind a
              reconciliation gate (opening + rows must equal closing, both directions).
            </span>
          </li>
          <li className={stepCls}>
            <span className="font-bold text-blue-400">Step 2 - Check and decide.</span>{' '}
            <span className="text-slate-300">
              Confirm extractions in the <a href="/review" className={linkCls}>Review queue</a> and
              accept private/business suggestions. Unsure items park in Suspense for your
              accountant. Nothing posts without your say-so, and every fix keeps a reason.
            </span>
          </li>
          <li className={stepCls}>
            <span className="font-bold text-blue-400">Step 3 - Peek and export.</span>{' '}
            <span className="text-slate-300">
              Drill any <a href="/dashboard" className={linkCls}>Dashboard</a> number back to the
              exact highlighted line, ask <a href="/chat" className={linkCls}>Spy Chat</a>, check your
              payoff plan on <a href="/debt" className={linkCls}>Debt</a>, then export from
              the <a href="/reports" className={linkCls}>Reports</a> page: Excel, a signed PDF,
              a verifiable evidence pack, or your full POPIA data ZIP.
            </span>
          </li>
        </ol>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4">Every function</h2>
        <div className="space-y-3 text-sm">
          <div className={stepCls}>
            <a href="/upload" className={`${linkCls} font-semibold`}>Upload</a>
            <p className="text-slate-300 mt-1">One statement file per upload. Encrypted PDFs ask for the password once - it is never stored. Each upload decrements your free quota by one.</p>
          </div>
          <div className={stepCls}>
            <a href="/inbox" className={`${linkCls} font-semibold`}>Inbox</a>
            <p className="text-slate-300 mt-1">Every upload and its status: queued, proposed, exception, or needs_password. SHA256 identities, never the file itself.</p>
          </div>
          <div className={stepCls}>
            <a href="/review" className={`${linkCls} font-semibold`}>Review queue</a>
            <p className="text-slate-300 mt-1">Accept suggestions to post journals, or fix description, date, and amount with a required reason. Fixes repost the journal and re-check the running balance chain. Wrong rows get Reject / void: proposed rows flip to rejected, posted ones are cancelled with mirror-image reversals - history always stays.</p>
          </div>
          <div className={stepCls}>
            <a href="/transactions" className={`${linkCls} font-semibold`}>Transactions</a>
            <p className="text-slate-300 mt-1">Your ledger. Click any row to see the exact highlighted line on the original it came from, or void it with a reason.</p>
          </div>
          <div className={stepCls}>
            <a href="/books" className={`${linkCls} font-semibold`}>Books</a>
            <p className="text-slate-300 mt-1">Your chart of accounts: switch templates (personal, SME, mixed sole-prop), read the trial balance per bank account, and watch the 9999 suspense watchdog for parked money.</p>
          </div>
          <div className={stepCls}>
            <a href="/debt" className={`${linkCls} font-semibold`}>Debt</a>
            <p className="text-slate-300 mt-1">Type what you owe and compare snowball vs avalanche payoff plans on your real monthly surplus, with a what-if for extra payments.</p>
          </div>
          <div className={stepCls}>
            <a href="/reports" className={`${linkCls} font-semibold`}>Reports</a>
            <p className="text-slate-300 mt-1">Every download, regenerated from your books on each click: Excel workbook, PowerBI pack, auditor CSV, evidence pack, signed PDF, and your full POPIA data ZIP. Excel totals are live formulas: if they show 0, click Enable Editing, then press F9 (Excel) or Ctrl+Shift+F9 (LibreOffice).</p>
          </div>
          <div className={stepCls}>
            <a href="/dashboard" className={`${linkCls} font-semibold`}>Dashboard</a>
            <p className="text-slate-300 mt-1">Net flow, leak score, burn, runway, savings rate, cashflow charts, and spy flags. Run spy re-scans for subscriptions, duplicates, fees, and anomalies.</p>
          </div>
          <div className={stepCls}>
            <a href="/chat" className={`${linkCls} font-semibold`}>Spy Chat</a>
            <p className="text-slate-300 mt-1">Ask about your money in plain words - totals, vendors, subscriptions, duplicates, fees. Every number is cited to your ledger, never invented.</p>
          </div>
          <div className={stepCls}>
            <a href="/account" className={`${linkCls} font-semibold`}>Account</a>
            <p className="text-slate-300 mt-1">Sign in, plans, subscribe, and cancel. Your trial status lives here and in the nav badge.</p>
          </div>
          <div className={stepCls}>
            <a href="/settings" className={`${linkCls} font-semibold`}>Settings</a>
            <p className="text-slate-300 mt-1">Owners change model and effort; cost guards, billing keys, and the full table stay admin-only. Secret keys live in server env vars only - never in this table.</p>
          </div>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4">Trial, billing, cancel</h2>
        <div className="space-y-3 text-sm text-slate-300">
          <p><span className="font-semibold text-slate-100">What does the free trial include?</span> 20 uploads. Each statement file you upload counts once, however many pages it has. Confirming, reviewing, and exporting never consume quota - only uploads do.</p>
          <p><span className="font-semibold text-slate-100">What are the paid plans?</span> Individual R149/mo for 200 uploads, SME R599/mo for 1000 uploads. Payments go through Paystack (currently in test mode while verification completes).</p>
          <p><span className="font-semibold text-slate-100">How do I cancel?</span> On the Account page while subscribed, press Cancel subscription and confirm. It takes effect immediately and you drop back to trial metering.</p>
          <p><span className="font-semibold text-slate-100">I hit my limit mid-work.</span> The upload page shows a paywall with your options. Your existing data, books, and exports stay untouched - limits only gate new uploads.</p>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-4">Proof and privacy</h2>
        <div className="space-y-3 text-sm text-slate-300">
          <p>Originals live content-addressed by SHA256 (immutable - re-uploading the same file is detected, never duplicated). Every human change is revisioned with a reason, and the audit log is hash-chained. See <a href="/privacy" className={linkCls}>Privacy</a>, <a href="/terms" className={linkCls}>Terms</a>, and <a href="/refund" className={linkCls}>Refunds</a>.</p>
          <p>Hosted AI only ever processes what the task needs, and approval-gated where it matters. Nothing here is legal or tax advice - your accountant signs off, FIN_SPY supplies the evidence.</p>
        </div>
      </section>
    </main>
  );
}
