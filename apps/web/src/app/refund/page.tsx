'use client';
import React from 'react';

export default function RefundPage() {
  return (
    <main className="legal-content max-w-3xl mx-auto px-4 py-8 pb-16">
      <h1 className="text-3xl font-bold mb-2">Refund Policy - FIN_SPY</h1>
      <p className="updated text-sm text-gray-500">Last updated: October 26, 2026 - Adapted from clearmind-ai/templates/refund.html</p>

      <h2 className="text-xl font-semibold mt-8">Free Trial</h2>
      <p className="text-gray-700 leading-7">All new accounts receive 20 free pages (default trial_pages setting configurable 0-50 like clearmind trial_sessions) before any payment required. This allows you to fully evaluate service before committing. Trial counts source_documents where uploaded_by not sessions. Remaining pages shown in dashboard per get_trial_pages_remaining(). Clearmind had 5 free sessions FIN_SPY 20 pages.</p>

      <h2 className="text-xl font-semibold mt-8">Subscription Cancellation</h2>
      <p className="text-gray-700 leading-7">You may cancel subscription anytime from Account page. Upon cancellation:</p>
      <ul className="list-disc pl-6 text-gray-700 leading-7">
        <li>Subscription remains active until end of current billing period</li>
        <li>No further charges will be made</li>
        <li>You retain access to all features until period ends</li>
        <li>builds_used reset on renewal per ClearFlag upsert pattern not immediate reset</li>
      </ul>

      <h2 className="text-xl font-semibold mt-8">Refunds</h2>
      <p className="text-gray-700 leading-7">Because service is digital and immediately accessible (PDF upload -> hash vault -> extraction) we do not offer refunds for partial billing periods. If you cancel you continue to have access until end of paid period. Excel workbook live formulas signed PDF Evidence Pack ZIP already generated are digital.</p>

      <h2 className="text-xl font-semibold mt-8">Exceptions</h2>
      <p className="text-gray-700 leading-7">If you experience technical issue that prevents you from using service for more than 48 consecutive hours (e.g. reconciliation gate always failing vault hash mismatch extraction 0% accuracy dashboard drill-to-bbox broken) contact us for pro-rata refund or service credit. Verification via scripts/verify_pack.py independent hasher + audit_log hash-chain check per Appendix D.</p>

      <h2 className="text-xl font-semibold mt-8">Dispute Resolution</h2>
      <p className="text-gray-700 leading-7">If you have billing dispute email admin@fin-spy.example. We will respond within 5 business days. Provide tenant_id subscription_code reference from Paystack transaction initialize.</p>

      <h2 className="text-xl font-semibold mt-8">Plans</h2>
      <ul className="list-disc pl-6 text-gray-700 leading-7">
        <li>Free: 20 pages/mo R0</li>
        <li>Individual: 200 pages/mo R149 (vs clearmind R370)</li>
        <li>SME: 1000 pages/mo R599 2 entities</li>
        <li>Practice: custom</li>
      </ul>
      <p className="text-gray-700 leading-7">Metering: pages processed + tokens + exports per usage_events table est_cost_usd tracked per homework Part 5.13 per-tenant monthly caps global daily Meta budget alarm kill switch to No-AI mode.</p>

      <footer className="text-center py-8 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a> · <a href="/terms" className="underline">Terms</a> · <a href="/refund" className="underline">Refund</a>
      </footer>
    </main>
  );
}
