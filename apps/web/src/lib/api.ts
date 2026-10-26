// Typed client generated from FastAPI OpenAPI - placeholder for now
// Per AGENTS.md: generate client from FastAPI's OpenAPI schema later

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export type Transaction = {
  id: string;
  tenant_id: string;
  txn_date: string;
  description_raw: string;
  amount_minor: number; // cents, never float
  direction: 'debit' | 'credit';
  balance_after_minor?: number;
  fingerprint_sha256: string;
  status: 'proposed' | 'confirmed' | 'rejected' | 'exception';
  doc_id: string;
  page_no: number;
  line_ids: string[];
};

export type DashboardSummary = {
  leak_score_per_month_minor: number;
  runway_months: number;
  burn_rate_minor: number;
  savings_rate_pct: number;
  private_vs_business_ratio: number;
  top_leaks: Array<{ merchant: string; amount_minor: number; cadence_days: number; leak_per_month_minor: number }>;
};

export async function fetchTransactions(params?: Record<string,string>): Promise<Transaction[]> {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  const res = await fetch(`${API_BASE}/v1/transactions${qs}`);
  if (!res.ok) throw new Error(`fetchTransactions ${res.status}`);
  return res.json();
}
