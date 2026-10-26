'use client';
import React from 'react';

export default function PrivacyPage() {
  return (
    <main className="legal-content max-w-3xl mx-auto px-4 py-8 pb-16">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy - FIN_SPY</h1>
      <p className="updated text-sm text-gray-500">Last updated: October 26, 2026 - Adapted from clearmind-ai/templates/privacy.html POPIA template</p>

      <h2 className="text-xl font-semibold mt-8">1. Information We Collect</h2>
      <p className="text-gray-700 leading-7">We collect information you provide when you register, upload bank statements (PDF/CSV/OFX), invoices/receipts (images), create entities (personal/business), and use AI features. This includes name, email, password_hash bcrypt $2b$, financial transactions date/description_raw/amount_minor Decimal/balance_after/fingerprint SHA256(date|amount|desc_norm), document SHA256 storage_key content-hash vault, page bbox line_id source_spans, classification private/business/mixed %, category rationale decided_by, usage pages/tokens/exports audit_log actions, technical upload IP user_agent tenant_id.</p>
      <p className="text-gray-700 leading-7">We do NOT store raw PDFs as searchable text beyond bbox spans - originals preserved byte-for-byte SHA256 vault immutable data/vault/ (MVP) or Supabase Storage (prod) content-addressed key=SHA256 never overwritten.</p>

      <h2 className="text-xl font-semibold mt-8">2. How We Use Your Information</h2>
      <p className="text-gray-700 leading-7">Your data used solely to provide FIN_SPY service: forensic extraction line-ID grounding, reconciliation gate, double-entry books, leak/subscription/duplicate spy, KPI peek runway/burn/savings_rate, debt snowball/avalanche, signed PAdES PDF + Evidence Pack ZIP. We do not sell, rent, share data.</p>

      <h2 className="text-xl font-semibold mt-8">3. Data Storage & Security</h2>
      <p className="text-gray-700 leading-7">Stored securely on Railway/Supabase infrastructure per config/models.yaml. Tenant data isolated by tenant_id+user_id - no cross-account access, tested via test_user_isolation tenant-a can't see doc-b, RLS path Supabase prod. Append-only audit_log hash-chained row_hash=SHA256(prev||canonical_json) per AGENTS.md. Content-hash vault immutable derivatives separate derived_from link TSA RFC3161 FreeTSA/DigiCert free no SLA pyHanko PAdES signature. Passwords bcrypt $2b$ 60 chars gensalt not SHA256 hex (clearmind weak fixed). Session secret fail-closed REQUIRED production per ClearFlag, not random persisted like clearmind bug. Paystack secret timing-safe hmac.compare_digest HMAC SHA512 raw body per ClearFlag idempotent webhook_events.</p>

      <h2 className="text-xl font-semibold mt-8">4. AI Processing</h2>
      <p className="text-gray-700 leading-7">Bank transaction description/amount/date sent to Meta Muse Spark 1.3 standard NOT contributor via apps/worker/llm/client.py adapter: config/models.yaml capabilities max_context 1M supports_images parallel tools effort low/medium/high/xhigh. Routing local-first per docs/FLOWS.md Flowchart #2 local ollama llama3.2 first hosted only after user approval gate showing exact text to be sent show_exact_text_before_hosted=true. Meta standard tier does NOT train on prompts. Contributor tier muse-spark-1.3-contributor trains on prompts - NEVER for real bank docs only synthetic test data data/samples/. Line-ID grounding anti-hallucination model gets Lxxx numbered lines + bbox must return line_ids + source_quote exact match quote validation + reconciliation gate.</p>

      <h2 className="text-xl font-semibold mt-8">5. Data Retention & Legal Hold</h2>
      <p className="text-gray-700 leading-7">You retain ownership. You may delete documents transactions or entire tenant anytime - deletes content but leaves non-personal audit skeleton per law deletion certificate hash list. Retention per record type legal decision: commonly 5 years tax 7 years company per SA anchors [VERIFY with accountant/attorney] per docs/METHOD_STATEMENT.md. Tenant-level legal_hold flag blocks deletion. POPIA expects justified retention + deletion/de-identification when no longer needed with legal-hold exceptions. Data permanently removed within 30 days of account deletion.</p>

      <h2 className="text-xl font-semibold mt-8">6. Your Rights (POPIA)</h2>
      <p className="text-gray-700 leading-7">As South African service we comply with POPIA Protection of Personal Information Act. You may request copy correct delete by contacting admin at admin@fin-spy.example or via /v1/auth/me. You may request export of all data as Evidence Pack ZIP manifest.json + manifest.sha256 + .tsr tokens + verification instructions per Appendix D. Data on Railway isolated by tenant_id.</p>

      <h2 className="text-xl font-semibold mt-8">7. Cross-Border Transfers</h2>
      <p className="text-gray-700 leading-7">Dev Railway EU approx Supabase free region may not be SA [VERIFY]. POPIA s72 disclosure applies operator agreements with sub-processors (Railway Supabase Meta) roadmap AWS af-south-1 Cape Town per docs/PLAN.md.</p>

      <h2 className="text-xl font-semibold mt-8">8. Contact</h2>
      <p className="text-gray-700 leading-7">For privacy inquiries email admin@example.com or check docs/METHOD_STATEMENT.md court wording what we guarantee vs not AI disclosure.</p>

      <footer className="text-center py-8 text-sm text-gray-500">
        <a href="/privacy" className="underline">Privacy</a> · <a href="/terms" className="underline">Terms</a> · <a href="/refund" className="underline">Refund</a>
      </footer>
    </main>
  );
}
