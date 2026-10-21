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
