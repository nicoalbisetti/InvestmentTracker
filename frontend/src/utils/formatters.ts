export function fmtBRL(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function fmtUSD(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function fmtPct(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
}

export function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  return `${d}/${m}/${y}`;
}

export function fmtNumber(value: number | null | undefined): string {
  if (value == null) return '—';
  return new Intl.NumberFormat('pt-BR').format(value);
}

export function colorPct(value: number | null | undefined): string {
  if (value == null) return '';
  return value >= 0 ? 'positive' : 'negative';
}

export const INSTRUMENT_TYPE_LABELS: Record<string, string> = {
  renta_fija: 'Renta Fija',
  accion: 'Acciones',
  fii: 'FIIs',
  fundo: 'Fondos',
  exterior: 'Exterior',
  previdencia: 'Previdencia',
  fgts: 'FGTS',
  outro: 'Otro',
};

export const INSTRUMENT_TYPE_COLORS: Record<string, string> = {
  renta_fija: '#3b82f6',
  accion: '#10b981',
  fii: '#f59e0b',
  fundo: '#8b5cf6',
  exterior: '#ec4899',
  previdencia: '#06b6d4',
  fgts: '#84cc16',
  outro: '#6b7280',
};

export const CUSTODIAN_COLORS: Record<string, string> = {
  HSBC: '#c0392b',
  Bradesco: '#e74c3c',
  'XP BR': '#2ecc71',
  'XP US': '#27ae60',
  Santander: '#e67e22',
  Inter: '#f39c12',
  FGTS: '#84cc16',
  Previdencia: '#06b6d4',
  USA: '#3b82f6',
};

export const MONTH_NAMES = [
  'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
  'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
];
