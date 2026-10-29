'use client';
import React from 'react';

export default function TermsPage() {
  return (
    <main className="legal-content max-w-3xl mx-auto px-4 py-8 pb-16">
      <h1 className="text-3xl font-bold mb-2">Terms of Service - FIN_SPY</h1>
      <p className="updated text-sm text-gray-500">Last updated: October 26, 2026</p>

      <h2 className="text-xl font-semibold mt-8">1. Service Description</h2>
      <p className="text-gray-700 leading-7">FIN_SPY provides forensic financial tools: SA bank statement upload with every number traced to its exact position in the original document, an immutable vault with hash-chained audit trail, dynamic double-entry books, leak and subscription detection, KPIs (runway, burn, savings rate, debt-to-income), debt strategies, signed PDF reports, Evidence Packs, and PowerBI-ready exports. The service is offered on a subscription basis.</p>

      <h2 className="text-xl font-semibold mt-8">2. Account Registration</h2>
      <p className="text-gray-700 leading-7">You must register an account. You are responsible for keeping your login credentials confidential (passwords are stored hashed with bcrypt) and for all activity under your account. Accounts are strictly isolated: no account can access another account's data.</p>

      <h2 className="text-xl font-semibold mt-8">3. Subscription & Billing</h2>
      <p className="text-gray-700 leading-7">After the free trial of 20 uploads, continued use requires a paid subscription: Free 20 uploads R0, Individual 200 uploads R149/mo, SME 1000 uploads R599/mo, Practice custom pricing. Payments are processed securely via Paystack. Subscriptions auto-renew monthly. You may cancel at any time - access continues until the end of the billing period, and usage counters reset on renewal.</p>

      <h2 className="text-xl font-semibold mt-8">4. Acceptable Use</h2>
      <ul className="list-disc pl-6 text-gray-700 leading-7">
        <li>Use the service only for lawful financial record-keeping, for your own data or data you are authorized to process</li>
        <li>Maintain the confidentiality of financial data per POPIA</li>
        <li>Not use the service to generate harmful or fraudulent books</li>
        <li>Not attempt to reverse-engineer or abuse the AI systems, including injecting hidden text to steer the model</li>
        <li>Not upload malicious PDFs (embedded scripts, zip bombs, malformed files) - uploads are limited to 50MB with page-count limits and processing timeouts</li>
      </ul>

      <h2 className="text-xl font-semibold mt-8">5. AI-Generated Content & Court-Ready Disclaimer</h2>
      <p className="text-gray-700 leading-7">AI extraction uses Meta Muse Spark 1.3 with structured output and line-ID grounding, plus classification suggestions as a second opinion. All AI outputs are labelled with their source, confidence, and rationale. AI never finalizes anything - a human always decides. AI-generated classifications, KPIs, and debt strategies are tools to assist your bookkeeping judgement; they do not replace professional accountant assessment. You remain solely responsible for reviewing and approving all books before use. Private/business splits need professional review. Debt strategies are a calculation aid, not financial advice (ask a tax practitioner about SARS deductibility). Reports state that flags are indicators for inquiry, not findings of fault. "Court-ready" means the product is built to support admissibility and expert testimony under ECTA section 15 - admissibility itself is NOT guaranteed, as it is decided by the court and requires a witness who can explain the method. Every report includes an AI disclosure.</p>

      <h2 className="text-xl font-semibold mt-8">6. Limitation of Liability</h2>
      <p className="text-gray-700 leading-7">FIN_SPY is provided "as is" without warranty. We are not liable for damages arising from AI-generated content, your books, service interruptions, data loss, or reconciliation failures. Total liability is limited to the amount you paid in the preceding 12 months. Note that Excel workbooks are not tamper-proof; the integrity anchor is the signed PDF with the manifest hash printed in its footer, verifiable via the QR verification page.</p>

      <h2 className="text-xl font-semibold mt-8">7. Termination</h2>
      <p className="text-gray-700 leading-7">We may suspend or terminate accounts that violate these terms (malicious uploads, prompt injection, unauthorized access attempts, forged webhooks, brute-force attacks). You may delete your account at any time. Upon termination, data is permanently deleted within 30 days as described in the privacy policy; a non-personal audit skeleton may remain, a deletion certificate lists the hashes, and an active legal hold blocks deletion.</p>

      <h2 className="text-xl font-semibold mt-8">8. Changes to Terms</h2>
      <p className="text-gray-700 leading-7">We may update these terms. Continued use after changes constitutes acceptance. Material changes will be notified via email.</p>

      <h2 className="text-xl font-semibold mt-8">9. Governing Law</h2>
      <p className="text-gray-700 leading-7">These terms are governed by the laws of South Africa, including POPIA and ECTA section 15 on the admissibility of data messages.</p>

      <h2 className="text-xl font-semibold mt-8">10. Contact</h2>
      <p className="text-gray-700 leading-7">For questions email admin@fin-spy.example.</p>

      <footer className="text-center py-8 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a> · <a href="/terms" className="underline">Terms</a> · <a href="/refund" className="underline">Refund</a>
      </footer>
    </main>
  );
}
