'use client';
import React from 'react';

export default function RefundPage() {
  return (
    <main className="legal-content max-w-3xl mx-auto px-4 py-8 pb-16">
      <h1 className="text-3xl font-bold mb-2">Refund Policy - FIN_SPY</h1>
      <p className="updated text-sm text-gray-500">Last updated: October 26, 2026</p>

      <h2 className="text-xl font-semibold mt-8">Free Trial</h2>
      <p className="text-gray-700 leading-7">All new accounts receive 20 free uploads before any payment is required. This allows you to fully evaluate the service before committing. Your remaining uploads are shown in the dashboard.</p>

      <h2 className="text-xl font-semibold mt-8">Subscription Cancellation</h2>
      <p className="text-gray-700 leading-7">You may cancel your subscription at any time from the Account page. Upon cancellation:</p>
      <ul className="list-disc pl-6 text-gray-700 leading-7">
        <li>Your subscription remains active until the end of the current billing period</li>
        <li>No further charges will be made</li>
        <li>You retain access to all features until the period ends</li>
        <li>Usage counters reset on renewal, not immediately on cancel</li>
      </ul>

      <h2 className="text-xl font-semibold mt-8">Refunds</h2>
      <p className="text-gray-700 leading-7">Because the service is digital and usable immediately (upload, vault storage, and extraction happen at once), we do not offer refunds for partial billing periods. If you cancel, you keep access until the end of the paid period, including any Excel workbooks, signed PDFs, and Evidence Packs already generated.</p>

      <h2 className="text-xl font-semibold mt-8">Exceptions</h2>
      <p className="text-gray-700 leading-7">If you experience a technical issue that prevents you from using the service for more than 48 consecutive hours (for example: reconciliation always failing, vault hash mismatch, extraction returning nothing, dashboard drill-down broken), contact us for a pro-rata refund or service credit. We verify such issues with our independent pack verifier and the audit hash chain.</p>

      <h2 className="text-xl font-semibold mt-8">Dispute Resolution</h2>
      <p className="text-gray-700 leading-7">If you have a billing dispute, email admin@fin-spy.example. We will respond within 5 business days. Please include your account ID, subscription code, and Paystack transaction reference.</p>

      <h2 className="text-xl font-semibold mt-8">Plans</h2>
      <ul className="list-disc pl-6 text-gray-700 leading-7">
        <li>Free: 20 uploads/mo R0</li>
        <li>Individual: 200 uploads/mo R149</li>
        <li>SME: 1000 uploads/mo R599, 2 entities</li>
        <li>Practice: custom</li>
      </ul>
      <p className="text-gray-700 leading-7">Metering counts statement uploads, AI tokens used, and exports generated, with per-account monthly caps. Estimated AI cost is tracked per document, with a global daily budget alarm and an automatic fallback to No-AI mode if the budget is exceeded.</p>

    </main>
  );
}
