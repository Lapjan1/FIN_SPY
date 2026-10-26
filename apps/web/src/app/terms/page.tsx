'use client';
import React from 'react';

export default function TermsPage() {
  return (
    <main className="legal-content max-w-3xl mx-auto px-4 py-8 pb-16">
      <h1 className="text-3xl font-bold mb-2">Terms of Service - FIN_SPY</h1>
      <p className="updated text-sm text-gray-500">Last updated: October 26, 2026 - Adapted from clearmind-ai/templates/terms.html</p>

      <h2 className="text-xl font-semibold mt-8">1. Service Description</h2>
      <p className="text-gray-700 leading-7">FIN_SPY provides forensic financial tools: SA bank PDF upload every number traced to exact bbox SHA256 vault + hash-chain audit dynamic double-entry books leak/subscription/duplicate spy KPIs runway/burn/savings_rate/debt-to-income debt snowball/avalanche signed PAdES PDF + Evidence Pack ZIP + PowerBI-ready pack. Subscription basis per docs/PLAN.md.</p>

      <h2 className="text-xl font-semibold mt-8">2. Account Registration</h2>
      <p className="text-gray-700 leading-7">You must register account. You are responsible for maintaining confidentiality of login credentials bcrypt $2b$ stored not SHA256 and all activity under account. Tenant isolation via tenant_id+user_id no cross-account access tested via test_user_isolation.</p>

      <h2 className="text-xl font-semibold mt-8">3. Subscription & Billing</h2>
      <p className="text-gray-700 leading-7">After free trial 20 pages default trial_pages setting vs clearmind 5 sessions continued use requires paid subscription Free 20 pages R0 Individual 200 pages R149/mo SME 1000 pages R599/mo Practice custom per docs/decisions/0001. Payments processed securely via Paystack timing-safe HMAC SHA512 raw body hmac.compare_digest per ClearFlag not plain == idempotent webhook_events. Subscriptions auto-renew monthly. You may cancel anytime - access continues until end of billing period builds_used reset on renewal per ClearFlag upsert pattern.</p>

      <h2 className="text-xl font-semibold mt-8">4. Acceptable Use</h2>
      <ul className="list-disc pl-6 text-gray-700 leading-7">
        <li>Use service only for lawful financial record-keeping own data or authorized</li>
        <li>Maintain confidentiality financial data per POPIA</li>
        <li>Not use service to generate harmful or fraudulent books</li>
        <li>Not attempt reverse-engineer or abuse AI systems not inject hidden text white/0pt to steer model</li>
        <li>Not upload malicious PDFs JS incremental updates zip bombs - sanitization checks size/type 50MB limit page-count limit worker timeouts per AGENTS.md security</li>
      </ul>

      <h2 className="text-xl font-semibold mt-8">5. AI-Generated Content & Court-Ready Disclaimer</h2>
      <p className="text-gray-700 leading-7">AI extraction fallback uses Meta Muse Spark 1.3 structured output line-ID grounding classification suggestions AI second opinion. All AI outputs labelled source=ai confidence rationale. AI never finalizes human decides. AI-generated classifications KPIs debt strategies tools to assist your bookkeeping judgement do not replace professional accountant assessment. You remain solely responsible for reviewing and approving all books before use. Private/business split needs professional review. Debt strategies calculation aid not financial advice (SARS deductibility need practitioner). Reports must state flags are indicators for inquiry not findings of fault. Court-ready means built to support admissibility and expert testimony per ECTA s15 NOT guaranteed admissible admissibility decided by court needs witness who can explain method per docs/METHOD_STATEMENT.md. AI disclosure in every report.</p>

      <h2 className="text-xl font-semibold mt-8">6. Limitation of Liability</h2>
      <p className="text-gray-700 leading-7">FIN_SPY provided as is without warranty. Not liable for damages arising from use of AI-generated content books service interruptions data loss reconciliation failures. Total liability limited to amount paid in preceding 12 months. Excel workbook live SUMIFS not tamper-proof integrity anchor is signed PDF + manifest SHA256 printed in PDF footer + QR verification page.</p>

      <h2 className="text-xl font-semibold mt-8">7. Termination</h2>
      <p className="text-gray-700 leading-7">We may suspend or terminate accounts violating terms (malicious PDFs prompt injection IDOR forged webhooks brute-force). You may delete account anytime. Upon termination data permanently deleted within 30 days per privacy audit non-personal skeleton may remain deletion certificate hash list legal_hold flag blocks deletion.</p>

      <h2 className="text-xl font-semibold mt-8">8. Changes to Terms</h2>
      <p className="text-gray-700 leading-7">We may update terms. Continued use after changes constitutes acceptance. Material changes notified via email.</p>

      <h2 className="text-xl font-semibold mt-8">9. Governing Law</h2>
      <p className="text-gray-700 leading-7">Terms governed by laws of South Africa. POPIA compliance ECTA s15 data messages admissibility.</p>

      <h2 className="text-xl font-semibold mt-8">10. Contact</h2>
      <p className="text-gray-700 leading-7">For questions email admin@fin-spy.example.</p>

      <footer className="text-center py-8 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a> · <a href="/terms" className="underline">Terms</a> · <a href="/refund" className="underline">Refund</a>
      </footer>
    </main>
  );
}
