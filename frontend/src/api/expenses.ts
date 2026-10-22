import client from './client';

type Params = Record<string, string | number | boolean | undefined>;
type Body = Record<string, unknown>;

export interface ExpAccount {
  id: number; name: string; institution: string; country: 'AR' | 'BR'; kind: 'bank' | 'wallet' | 'credit_card';
  currency: string; parser_key: string | null; paid_from_account_id: number | null;
  default_entity_id: number | null; has_statements: boolean; active: boolean; owner_identifiers?: string[];
}
export interface ExpCategory { id: number; name: string; is_system: boolean; active: boolean }
export interface ExpEntity { id: number; code: string; name: string; active: boolean }
export interface ExpTx {
  id: number; account_id: number; account: string; country: string; date: string; purchase_date: string | null;
  description: string; counterparty: string | null; merchant: string | null; amount: number; currency: string;
  amount_brl: number | null; amount_usd: number | null; kind: string; category_id: number | null;
  category: string | null; entity_id: number | null; entity: string | null; installment_number: number | null;
  installment_total: number | null; classification_source: string; needs_review: boolean; notes: string | null;
  paired: boolean; statement_batch_id: number | null; fx_estimated: boolean;
}
export interface SummaryMonth {
  month: string; expenses: number; income: number; proventos: number; savings: number; no_detail: number;
  by_category: Record<string, number>; by_entity: Record<string, number>;
}
export interface SummaryBlock { months: SummaryMonth[]; rows_without_fx: number }
export interface Summary extends Partial<SummaryBlock> {
  currency: string; pending_review_pct: number; coverage: { account_id: number; name: string; months: string[] }[];
  by_currency?: Record<string, SummaryBlock>;
}
export interface Check { name: string; ok: boolean; detail: string }
export interface PreviewRow {
  date: string; description_raw: string; amount: number; currency: string; kind: string; category_id: number | null;
  needs_review: boolean; duplicate: boolean; installment_number: number | null; installment_total: number | null;
}
export interface Batch {
  id: number; account_id: number; parser_key: string; status: string; period_start: string | null;
  period_end: string | null; statement_period: string | null; validation: Check[]; rows_total: number;
  rows_new: number; rows_duplicate: number; created_at: string; confirmed_at: string | null; rows?: PreviewRow[];
}

const B = '/api/expenses';
export const getAccounts = (): Promise<ExpAccount[]> => client.get(`${B}/accounts`).then(r => r.data);
export const getAccount = (id: number): Promise<ExpAccount> => client.get(`${B}/accounts/${id}`).then(r => r.data);
export const createAccount = (d: Partial<ExpAccount>) => client.post(`${B}/accounts`, d).then(r => r.data);
export const patchAccount = (id: number, d: Partial<ExpAccount>) => client.patch(`${B}/accounts/${id}`, d).then(r => r.data);
export const getCategories = (): Promise<ExpCategory[]> => client.get(`${B}/categories`).then(r => r.data);
export const getEntities = (): Promise<ExpEntity[]> => client.get(`${B}/entities`).then(r => r.data);
export const getSummary = (params: Params): Promise<Summary> =>
  client.get(`${B}/summary`, { params }).then(r => r.data);
export const getTransactions = (params: Params): Promise<{ total: number; page: number; page_size: number; items: ExpTx[] }> =>
  client.get(`${B}/transactions`, { params }).then(r => r.data);
export const patchTransaction = (id: number, d: Body) =>
  client.patch(`${B}/transactions/${id}`, d).then(r => r.data);
export const bulkPatch = (d: Body) => client.post(`${B}/transactions/bulk`, d).then(r => r.data);
export const previewRule = (d: Body): Promise<{ count: number }> =>
  client.post(`${B}/rules/preview`, d).then(r => r.data);
export const getImports = (): Promise<Batch[]> => client.get(`${B}/imports`).then(r => r.data);
export const uploadImport = (file: File, accountId?: number, dueDate?: string): Promise<Batch> => {
  const f = new FormData();
  f.append('file', file);
  if (accountId) f.append('account_id', String(accountId));
  if (dueDate) f.append('due_date', dueDate);
  return client.post(`${B}/imports`, f).then(r => r.data);
};
export const confirmImport = (id: number, force = false): Promise<Batch> =>
  client.post(`${B}/imports/${id}/confirm`, { force }).then(r => r.data);
export const deleteImport = (id: number) => client.delete(`${B}/imports/${id}`).then(r => r.data);
export const getReviewQueue = (): Promise<Record<string, unknown[]>> => client.get(`${B}/review-queue`).then(r => r.data);

/** Mensaje de error de una respuesta de axios (FastAPI: detail string u objeto). */
export function apiErrorDetail(e: unknown): { status?: number; detail?: unknown } {
  const r = (e as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  return { status: r?.status, detail: r?.data?.detail };
}

export interface QueueItem { id: number; date: string; description: string; amount: number; currency: string; kind: string }
export interface PairSuggestion { kind: string; out_id: number; in_id: number; amount: number; days: number; out: QueueItem; in: QueueItem }
export interface ReviewQueue {
  unclassified: QueueItem[]; sign_inconsistent: QueueItem[]; unpaired_transfers: QueueItem[];
  unpaired_transfers_counterparty_not_imported: QueueItem[]; pair_suggestions: PairSuggestion[];
  card_payments_without_statement: QueueItem[]; card_payments_inexact: QueueItem[];
  fx_missing: QueueItem[]; fx_estimated: QueueItem[]; investments_unlinked: QueueItem[]; proventos_unlinked: QueueItem[];
}
export interface LinkSuggestion {
  exp_transaction: { id: number; date: string; description: string; amount: number; currency: string; amount_brl: number | null; kind: string };
  link_type: string; difference_brl: number;
  links: { id: number; target_type: string; target_id: number; label: string | null; date: string | null; amount: number | null; allocated: number | null; score: number | null }[];
}
export interface Audit {
  bank_movements_without_transaction: { id: number; date: string; description: string; amount: number }[];
  transactions_without_bank_movement: { id: number; date: string; type: string; amount_brl: number | null; instrument: string | null; custodian: string | null }[];
  confirmed_link_differences: { exp_transaction_id: number; date: string; bank_amount: number; linked_amount: number; difference: number; max_days_apart: number }[];
  drifted_links: { link_id: number; exp_transaction_id: number; label: string | null; reason: string }[];
}
export const getReviewQueueTyped = (): Promise<ReviewQueue> => client.get(`${B}/review-queue`).then(r => r.data);
export const rebuildLinks = (): Promise<Record<string, number>> => client.post(`${B}/links/rebuild`).then(r => r.data);
export const getLinkSuggestions = (status = 'suggested'): Promise<LinkSuggestion[]> =>
  client.get(`${B}/links/suggestions`, { params: { status } }).then(r => r.data);
export const confirmLink = (id: number) => client.post(`${B}/links/${id}/confirm`).then(r => r.data);
export const rejectLink = (id: number) => client.post(`${B}/links/${id}/reject`).then(r => r.data);
export const confirmPair = (outId: number, inId: number) =>
  client.post(`${B}/links/pairs`, { out_id: outId, in_id: inId }).then(r => r.data);
export const getAudit = (from?: string, to?: string): Promise<Audit> =>
  client.get(`${B}/audit/investments`, { params: { from: from || undefined, to: to || undefined } }).then(r => r.data);

export interface MerchantGroup {
  key: string; sign: 'positive' | 'negative'; merchant: string; count: number; total_brl: number;
  first: string; last: string; countries: string[]; sample: string[];
}
export interface GroupRuleInput { key: string; sign: string; kind: string; category_id?: number; entity_id?: number; needs_review?: boolean }
export const getMerchantGroups = (limit = 100): Promise<MerchantGroup[]> =>
  client.get(`${B}/review/merchant-groups`, { params: { limit } }).then(r => r.data);
export const applyMerchantGroups = (items: GroupRuleInput[]): Promise<{ key: string; rule_id: number; applied: number }[]> =>
  client.post(`${B}/review/merchant-groups/apply`, { items }).then(r => r.data);
export const reapplyRules = (): Promise<{ reclassified: number; resolved: number }> =>
  client.post(`${B}/rules/reapply`).then(r => r.data);
