export function fmtMoney(value: number | null | undefined, currency = 'BRL', decimals = 0): string {
  if (value == null) return '—';
  return new Intl.NumberFormat(currency === 'BRL' ? 'pt-BR' : 'es-AR', {
    style: 'currency', currency, minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }).format(value);
}

export const KIND_LABELS: Record<string, string> = {
  expense: 'Gasto', refund: 'Devolución', income: 'Ingreso', own_transfer: 'Transf. propia',
  card_payment: 'Pago tarjeta', investment_contribution: 'Aporte inversión',
  investment_withdrawal: 'Rescate inversión', provento: 'Provento', fx_conversion: 'Cambio de moneda',
  unknown: 'Desconocido',
};

export const PARSER_LABELS: Record<string, string> = {
  mercadopago_pdf: 'Mercado Pago · cuenta (PDF)', santander_ar_account_pdf: 'Santander AR · cuenta (PDF)', santander_ar_card_pdf: 'Santander AR · tarjeta VISA/AMEX (PDF)', xp_account_csv: 'XP · cuenta (CSV)', xp_card_csv: 'XP · fatura tarjeta (CSV)', inter_account_csv: 'Inter · cuenta (CSV)',
};

const PALETTE = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6', '#ec4899', '#84cc16',
  '#f97316', '#14b8a6', '#a855f7', '#eab308', '#3b82f6', '#f43f5e', '#22c55e', '#0ea5e9'];
const SPECIAL: Record<string, string> = { 'Tarjeta sin detalle': '#94a3b8', 'Sin clasificar': '#cbd5e1' };

export function categoryColor(name: string, all: string[]): string {
  return SPECIAL[name] ?? PALETTE[all.indexOf(name) % PALETTE.length];
}

/** Clave de matching igual a la del backend (sin acentos ni no-alfanuméricos). */
export function matchKey(raw: string): string {
  return raw.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/[^A-Z0-9]/g, '');
}

export function monthLabel(ym: string): string {
  const [y, m] = ym.split('-');
  return `${['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'][+m - 1]} ${y.slice(2)}`;
}

export const ACCOUNT_KIND_LABELS: Record<string, string> = { bank: 'Banco', wallet: 'Billetera', credit_card: 'Tarjeta de crédito' };
export const BATCH_STATUS_LABELS: Record<string, string> = { preview: 'Preview', confirmed: 'Importado', discarded: 'Descartado' };
