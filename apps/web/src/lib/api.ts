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

// --- Review queue (Day 4 books). Thin typed wrappers, no logic. ---

export type ReviewTxn = {
  id: string;
  txn_date: string;
  description_raw: string;
  amount_minor: number;
  direction: string;
  status: string;
  fingerprint_sha256: string;
  original_filename?: string;
  doc_sha256?: string;
  account_number?: string;
};

export type ReviewQueue = {
  transactions: ReviewTxn[];
  documents: Array<Record<string, unknown>>;
  count: number;
};

export type Suggestion = {
  nature: string;
  business_pct: number;
  category_id: string;
  rationale: string;
  source: string;
  confidence: number;
};

export type AcceptResult = {
  transaction_id: string;
  status: string;
  classification: Record<string, unknown>;
  journal_entry: Record<string, unknown>;
};

export type EditResult = {
  transaction_id: string;
  revisions: string[];
  updated_fields: string[];
  classification: Record<string, unknown> | null;
  repost: Record<string, unknown> | null;
  reverification: {
    overall_pass: boolean;
    rows_checked: number;
    running_top_bottom: { pass: boolean; break_count: number };
    running_bottom_top: { pass: boolean; break_count: number };
  } | null;
};

async function api<T>(path: string, userId: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', 'X-User-Id': userId, ...(init?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: string }).detail || `request failed ${res.status}`;
    throw new Error(detail);
  }
  return data as T;
}

export function fetchReviewQueue(userId: string): Promise<ReviewQueue> {
  return api<ReviewQueue>('/v1/review-queue', userId);
}

export function suggestClassification(
  userId: string,
  input: { description: string; account_number: string; entity_kind?: string; amount_minor?: number; direction?: string },
): Promise<Suggestion> {
  return api<Suggestion>('/v1/classifications/suggest', userId, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function acceptTransaction(
  userId: string,
  txnId: string,
  input: { nature?: string; business_pct?: number; category_id?: string; rationale?: string; reason: string },
): Promise<AcceptResult> {
  return api<AcceptResult>(`/v1/review-queue/${txnId}/accept`, userId, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function editTransaction(
  userId: string,
  txnId: string,
  input: {
    description_raw?: string;
    txn_date?: string;
    amount_minor?: number;
    nature?: string;
    business_pct?: number;
    category_id?: string;
    rationale?: string;
    reason: string;
  },
): Promise<EditResult> {
  return api<EditResult>(`/v1/review-queue/${txnId}/edit`, userId, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function formatRands(minor: number | undefined | null): string {
  if (minor === undefined || minor === null) return '—';
  return `R${(minor / 100).toFixed(2)}`;
}
