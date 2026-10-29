'use client';
import React from 'react';

export default function PrivacyPage() {
  return (
    <main className="legal-content max-w-3xl mx-auto px-4 py-8 pb-16">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy - FIN_SPY</h1>
      <p className="updated text-sm text-gray-500">Last updated: October 26, 2026</p>

      <h2 className="text-xl font-semibold mt-8">1. Information We Collect</h2>
      <p className="text-gray-700 leading-7">We collect information you provide when you register, upload bank statements (PDF/CSV/OFX) or invoices and receipts (images), create entities (personal/business), and use AI features. This includes your name, email, and hashed password; transaction details (date, description, amount, balance, fingerprint); document hashes and vault references; page coordinates and source spans; classifications with rationale; usage data (uploads, tokens, exports, audit actions); and technical data (upload IP, user agent, tenant ID).</p>
      <p className="text-gray-700 leading-7">We do NOT store your raw PDFs as searchable text beyond the extracted word spans. Originals are preserved byte-for-byte in an immutable, content-addressed vault (keyed by SHA256 hash) and are never overwritten.</p>

      <h2 className="text-xl font-semibold mt-8">2. How We Use Your Information</h2>
      <p className="text-gray-700 leading-7">Your data is used solely to provide the FIN_SPY service: forensic extraction with line-ID grounding, reconciliation checks, double-entry books, leak and subscription detection, KPIs (runway, burn, savings rate), debt strategies, signed PDF reports, and Evidence Packs. We do not sell, rent, or share your data.</p>

      <h2 className="text-xl font-semibold mt-8">3. Data Storage & Security</h2>
      <p className="text-gray-700 leading-7">Your data is stored securely on Railway and Supabase infrastructure. Each tenant's data is isolated, so no account can access another account's data (verified by automated isolation tests). Every action is recorded in an append-only, hash-chained audit log. Originals live in an immutable content-hash vault with trusted timestamps and PAdES digital signatures on reports. Passwords are hashed with bcrypt ($2b$). The session secret is required in production with a fail-closed startup check. Paystack secrets are verified with timing-safe HMAC SHA512 over the raw body, with idempotent webhook handling.</p>

      <h2 className="text-xl font-semibold mt-8">4. AI Processing</h2>
      <p className="text-gray-700 leading-7">Bank transaction descriptions, amounts, and dates are sent to Meta Muse Spark 1.3 standard edition (NOT the contributor edition). Routing is local-first: a local model is tried first, and a hosted model is only called after you approve the exact text to be sent. The Meta standard tier does NOT train on your prompts. The contributor tier does train on prompts, so it is NEVER used for real bank documents - only for synthetic test data. An anti-hallucination layer works from numbered source lines with page coordinates: the model must cite exact lines and quotes for every figure, and all figures pass a reconciliation check.</p>

      <h2 className="text-xl font-semibold mt-8">5. Data Retention & Legal Hold</h2>
      <p className="text-gray-700 leading-7">You retain ownership of your data. You may delete documents, transactions, or your entire account at any time; deletion removes your content but keeps a non-personal audit skeleton as required by law, with a deletion certificate listing the hashes. Retention periods depend on record type: commonly 5 years for tax and 7 years for company records in South Africa (confirm the periods that apply to you with your accountant or attorney). A legal hold on your account blocks deletion. POPIA requires retention to be justified, with deletion or de-identification once data is no longer needed, subject to legal-hold exceptions. Data is permanently removed within 30 days of account deletion.</p>

      <h2 className="text-xl font-semibold mt-8">6. Your Rights (POPIA)</h2>
      <p className="text-gray-700 leading-7">As a South African service, we comply with the Protection of Personal Information Act (POPIA). You may request a copy of your data, or its correction or deletion, by contacting admin@fin-spy.example or via your account page. You may request an export of all your data as an Evidence Pack ZIP (manifest, hashes, timestamp tokens, and verification instructions). Your data is isolated per tenant.</p>

      <h2 className="text-xl font-semibold mt-8">7. Cross-Border Transfers</h2>
      <p className="text-gray-700 leading-7">Our infrastructure providers (Railway, Supabase) and AI provider (Meta) may process your data outside South Africa. Transfers comply with POPIA section 72, and we maintain operator agreements with each sub-processor. Hosting data in South Africa (AWS Cape Town region) is on our roadmap.</p>

      <h2 className="text-xl font-semibold mt-8">8. Contact</h2>
      <p className="text-gray-700 leading-7">For privacy inquiries, email admin@fin-spy.example. Our method statement and AI disclosure describe in detail what we guarantee and what we do not.</p>

      <footer className="text-center py-8 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a> · <a href="/terms" className="underline">Terms</a> · <a href="/refund" className="underline">Refund</a>
      </footer>
    </main>
  );
}
