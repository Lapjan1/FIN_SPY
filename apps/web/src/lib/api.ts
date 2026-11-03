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
  status: 'proposed' | 'confirmed' | 'rejected' | 'exception' | 'needs_password' | 'queued';
  doc_id: string;
  page_no: number;
  line_ids: string[];
  account_number?: string | null;
  bank_name?: string | null;
  original_filename?: string | null;
  nature?: string | null;
  category_id?: string | null;
};

export type DashboardSummary = {
  from_date: string | null;
  to_date: string | null;
  account_number: string | null;
  active_template: string;
  totals: {
    txn_count: number;
    inflow_count: number;
    outflow_count: number;
    inflow_minor: number;
    outflow_minor: number;
    net_flow_minor: number;
    monthly_inflow: Record<string, number>;
    monthly_outflow: Record<string, number>;
    vendor_counts: Record<string, number>;
  } | null;
  leak_score_per_month_minor: number;
  runway_months: number;
  burn_rate_minor: number;
  savings_rate_pct: number;
  private_vs_business_ratio: number;
  inflow_minor: number;
  outflow_minor: number;
  net_flow_minor: number;
  trial_pages_remaining: number | null;
  is_trial_unlimited: boolean;
};

export type TxnSources = {
  txn_id: string;
  document_id: string | null;
  doc_sha256: string | null;
  original_filename: string | null;
  page_no: number;
  page_width: number | null;
  page_height: number | null;
  line_ids: string[];
  bboxes: Array<{ line_id: string; x0: number; y0: number; x1: number; y1: number }>;
  unlinked?: boolean;
};

export type Flag = {
  id: string;
  tenant_id: string;
  test_id: string;
  severity: string | null;
  window_start: string | null;
  window_end: string | null;
  result_json: string | null;
  code_version: string | null;
  created_at: string | null;
};

export type DocInfo = {
  id: string;
  sha256: string;
  original_filename: string;
  size_bytes: number;
  status: string;
  uploaded_at_utc: string;
  account_id?: string | null;
  account_number?: string | null;
  asserted_account_number?: string | null;
  extracted_account_number?: string | null;
  account_match?: string | null;
  bank_name?: string | null;
  branch_code?: string | null;
  verification?: {
    is_bank_statement: boolean;
    confidence: number;
    needs_review: boolean;
    file_type: string;
  } | null;
  tamper?: {
    is_original_likely: boolean | null;
    tamper_chance: number | null;
    tamper_indicators: string[];
  } | null;
};

export type BankAccount = {
  account_number: string | null;
  bank_name: string | null;
  txn_count: number;
  last_upload: string | null;
};

export function fetchBankAccounts(userId: string): Promise<BankAccount[]> {
  return api<BankAccount[]>('/v1/bank-accounts', userId);
}

const ACCOUNT_KEY = 'finspy.account';

export function getStoredAccount(): string {
  try {
    return window.localStorage.getItem(ACCOUNT_KEY) || '';
  } catch {
    return '';
  }
}

export function setStoredAccount(acct: string): void {
  try {
    window.localStorage.setItem(ACCOUNT_KEY, acct);
  } catch {
    /* storage unavailable - picker just won't persist */
  }
}

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
  account_name?: string;
  account_type?: string;
  active_template?: string;
  mapped_from?: string;
};

export type AccountOption = {
  id: string;
  code: string;
  name: string;
  type: string;
};

export type AccountsList = {
  tenant_id: string;
  active_template: string;
  accounts: AccountOption[];
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
    const err = new Error(detail) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return data as T;
}

export function fetchReviewQueue(userId: string): Promise<ReviewQueue> {
  return api<ReviewQueue>('/v1/review-queue', userId);
}

export function fetchAccounts(userId: string): Promise<AccountsList> {
  return api<AccountsList>('/v1/accounts', userId);
}

// --- Books (P0-E). Trial balance + suspense + template switch. ---

export type BookTemplate = {
  name: string;
  description: string;
  count: number;
};

export type BooksActive = {
  tenant_id: string;
  active_template: string;
  total_accounts: number;
};

export type TrialLine = {
  account_id: string | null;
  code: string;
  name: string;
  type: string;
  debits: number;
  credits: number;
  net: number;
};

export type TrialBalance = {
  tenant_id: string;
  as_of: string | null;
  entity_id: string | null;
  account_number: string | null;
  lines: TrialLine[];
  total_debits: number;
  total_credits: number;
  balanced: boolean;
  zero: boolean;
};

export type SuspenseStatus = {
  tenant_id: string;
  suspense_code: string;
  balance_minor: number;
  debits_minor: number;
  credits_minor: number;
  txn_count: number;
  oldest_age_days: number | null;
  total_debits_minor: number;
  total_txns: number;
  unposted_confirmed_count: number;
  unposted_confirmed_ids: string[];
  thresholds: { pct_limit: number; max_age_days: number };
  status: 'ok' | 'review';
  reasons: string[];
};

export function fetchBookTemplates(userId: string): Promise<{ templates: BookTemplate[] }> {
  return api<{ templates: BookTemplate[] }>('/v1/books/templates', userId);
}

export function fetchActiveBook(userId: string): Promise<BooksActive> {
  return api<BooksActive>('/v1/books/active', userId);
}

export function selectBook(userId: string, template: string): Promise<BooksActive & { message: string }> {
  return api<BooksActive & { message: string }>('/v1/books/select', userId, {
    method: 'POST',
    body: JSON.stringify({ template }),
  });
}

export function fetchTrialBalance(userId: string, accountNumber?: string): Promise<TrialBalance> {
  const q = accountNumber ? `?account_number=${encodeURIComponent(accountNumber)}` : '';
  return api<TrialBalance>(`/v1/journal/trial-balance${q}`, userId);
}

export function fetchSuspense(userId: string): Promise<SuspenseStatus> {
  return api<SuspenseStatus>('/v1/journal/suspense', userId);
}

// --- Debt (P0-F). User-typed debts, ledger-backed extra-cash default. ---

export type DebtInput = {
  creditor: string;
  balance_minor: number;
  apr_pct: string;
  min_payment_minor: number;
};

export type DebtPlan = {
  method: string;
  order: string[];
  months: number;
  total_paid_minor: number;
  total_interest_minor: number;
  interest_saved_minor: number;
  warnings: string[];
  narrative: string;
  disclaimer: string;
  what_if?: {
    base_months: number;
    boosted_months: number;
    months_saved: number;
    base_interest_minor: number;
    boosted_interest_minor: number;
    interest_saved_minor: number;
    extra_per_month_minor: number;
  };
};

export type DebtDefaults = {
  tenant_id: string;
  months: number;
  avg_net_per_month_minor: number;
  extra_cash_default_minor: number;
};

export function fetchDebtDefaults(userId: string): Promise<DebtDefaults> {
  return api<DebtDefaults>('/v1/debt/defaults', userId);
}

export function postDebtPlan(
  userId: string,
  debts: DebtInput[],
  method: string,
  extraCashMinor: number,
): Promise<DebtPlan> {
  return api<DebtPlan>('/v1/debt/plan', userId, {
    method: 'POST',
    body: JSON.stringify({
      debts,
      method,
      extra_cash_per_month_minor: extraCashMinor,
    }),
  });
}

export async function downloadReport(userId: string, path: string, filename: string): Promise<string> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { 'X-User-Id': userId } });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const detail = (data as { detail?: string }).detail || `request failed ${res.status}`;
    const err = new Error(detail) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return res.headers.get('x-report-warning') || '';
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

export type RejectResult = {
  transaction_id: string;
  status: string;
  reversed_entry_ids: string[];
};

export type MoveResult = {
  transaction_id: string;
  from_code: string;
  to_code: string;
  classification_id: string;
  transfer_entry_id: string | null;
};

export function moveTransaction(
  userId: string,
  txnId: string,
  toCode: string,
  reason: string,
): Promise<MoveResult> {
  return api<MoveResult>(`/v1/transactions/${txnId}/move`, userId, {
    method: 'POST',
    body: JSON.stringify({ to_code: toCode, reason }),
  });
}

export function rejectTransaction(
  userId: string,
  txnId: string,
  reason: string,
): Promise<RejectResult> {
  return api<RejectResult>(`/v1/review-queue/${txnId}/reject`, userId, {
    method: 'POST',
    body: JSON.stringify({ reason }),
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

export function fetchDashboard(
  userId: string,
  params?: { from_date?: string; to_date?: string; account_number?: string },
): Promise<DashboardSummary> {
  const qs = params
    ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString()
    : '';
  return api<DashboardSummary>(`/v1/dashboard/summary${qs}`, userId);
}

export function fetchTransactionsAuth(
  userId: string,
  params?: { status?: string; account_number?: string; document_id?: string },
): Promise<Transaction[]> {
  const qs = params
    ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString()
    : '';
  return api<Transaction[]>(`/v1/transactions${qs}`, userId);
}

export function fetchTxnSources(userId: string, txnId: string): Promise<TxnSources> {
  return api<TxnSources>(`/v1/transactions/${txnId}/sources`, userId);
}

export function fetchFlags(userId: string): Promise<Flag[]> {
  return api<Flag[]>('/v1/flags', userId);
}

export function fetchDocuments(userId: string): Promise<DocInfo[]> {
  return api<DocInfo[]>('/v1/documents', userId);
}

export function requeueDocument(userId: string, docId: string): Promise<{ id: string; status: string; requeued: boolean }> {
  return api(`/v1/documents/${docId}/requeue`, userId, { method: 'POST' });
}

export function documentFileOptions(userId: string, docId: string) {
  return {
    url: `${API_BASE}/v1/documents/${docId}/file`,
    httpHeaders: { 'X-User-Id': userId },
  };
}

export async function uploadDocument(
  userId: string,
  file: File,
  password?: string,
  accountNumber?: string,
): Promise<Record<string, unknown>> {
  const form = new FormData();
  form.append('file', file);
  if (password) form.append('pdf_password', password);
  if (accountNumber) form.append('account_number', accountNumber);
  const res = await fetch(`${API_BASE}/v1/documents`, {
    method: 'POST',
    headers: { 'X-User-Id': userId },
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error((data as { detail?: string }).detail || `upload failed ${res.status}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return data as Record<string, unknown>;
}

export function runSpy(userId: string): Promise<{ txn_count: number; flags: number; by_code: Record<string, number>; leak_per_month_minor: number }> {
  return api('/v1/spy/run', userId, { method: 'POST' });
}

export type Me = {
  user: { id: number; email: string; tenant_id: string; name?: string };
  trial_pages_remaining: number | null;
  is_trial_unlimited: boolean;
};

export function fetchMe(userId: string): Promise<Me> {
  return api<Me>('/v1/auth/me', userId);
}

export type ChatReply = {
  answer: string;
  tool_calls: Array<{ tool: string; result: unknown }>;
  citations: Array<{ txn_id?: string; document_id?: string | null }>;
  model: string;
};

export function postChat(userId: string, tenantId: string, messages: Array<{ role: string; content: string }>): Promise<ChatReply> {
  return api<ChatReply>('/v1/chat', userId, {
    method: 'POST',
    body: JSON.stringify({ tenant_id: tenantId, messages }),
  });
}

export function formatRands(minor: number | undefined | null): string {
  if (minor === undefined || minor === null) return '—';
  return `R${(minor / 100).toFixed(2)}`;
}

// --- Session: one login shared by every page ---
const SESSION_KEY = 'finspy-user-id';

export function getSessionUserId(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(SESSION_KEY) || '';
}

export function setSessionUserId(id: string): void {
  if (typeof window === 'undefined') return;
  if (id) window.localStorage.setItem(SESSION_KEY, id);
  else window.localStorage.removeItem(SESSION_KEY);
}

export function clearSession(): void {
  setSessionUserId('');
}

// HTTP status rides on thrown errors so pages can branch (402 -> paywall, 401 -> sign in).
export function errorStatus(e: unknown): number | null {
  const s = (e as { status?: unknown } | null)?.status;
  return typeof s === 'number' ? s : null;
}

export function isPaywallError(e: unknown): boolean {
  return errorStatus(e) === 402;
}

export function isAuthError(e: unknown): boolean {
  return errorStatus(e) === 401;
}

// --- Auth + billing (public calls carry no X-User-Id) ---

async function publicApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: string }).detail || `request failed ${res.status}`;
    const err = new Error(detail) as Error & { status: number };
    err.status = res.status;
    throw err;
  }
  return data as T;
}

export type AuthResult = {
  id: number;
  email: string;
  tenant_id: string;
  message?: string;
};

// One tenant per user, derived deterministically from the unique email so it
// is stable across browsers with no extra round-trip. Backend creates it on register.
export function tenantIdForEmail(email: string): string {
  const slug = email
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48);
  return `t-${slug || 'user'}`;
}

export function register(email: string, password: string, name?: string): Promise<AuthResult> {
  return publicApi<AuthResult>('/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name: name || '', tenant_id: tenantIdForEmail(email) }),
  });
}

export function login(email: string, password: string): Promise<AuthResult> {
  return publicApi<AuthResult>('/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export type ForgotResult = { sent: boolean; reset_token?: string; note?: string };

export function forgotPassword(email: string): Promise<ForgotResult> {
  return publicApi<ForgotResult>('/v1/auth/forgot', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string): Promise<{ ok: boolean }> {
  return publicApi<{ ok: boolean }>('/v1/auth/reset', {
    method: 'POST',
    body: JSON.stringify({ token, password }),
  });
}

export type BillingPlans = Record<string, { name: string; pages: number; amount_minor: number; price_display: string }>;

export function fetchBillingPlans(): Promise<BillingPlans> {
  return publicApi<BillingPlans>('/v1/billing/plans');
}

export type CheckoutResult = {
  checkout_url: string | null;
  access_code?: string;
  reference?: string;
  plan_code: string;
  free?: boolean;
};

export function startCheckout(userId: string, planCode: string): Promise<CheckoutResult> {
  return api<CheckoutResult>(`/v1/billing/checkout?plan_code=${encodeURIComponent(planCode)}`, userId, {
    method: 'POST',
  });
}

export type CancelResult = { ok: boolean; status: string; note?: string };

export function cancelSubscription(userId: string): Promise<CancelResult> {
  return api<CancelResult>('/v1/billing/cancel', userId, { method: 'POST' });
}

export type FeedbackInput = {
  category: 'bug' | 'bank-layout' | 'question' | 'other';
  subject: string;
  message: string;
  document_id?: string;
  page_url?: string;
};

export type FeedbackResult = { id: string; emailed: boolean };

export function submitFeedback(userId: string, input: FeedbackInput): Promise<FeedbackResult> {
  return api<FeedbackResult>('/v1/feedback', userId, {
    method: 'POST',
    body: JSON.stringify(input),
  });
}
