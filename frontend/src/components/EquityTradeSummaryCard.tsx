import { useEffect, useState } from 'react';
import { getEquityTradeSummary, EquityTradeSummary } from '../api/equityTrades';

interface Props {
  instrumentId: number;
}

export default function EquityTradeSummaryCard({ instrumentId }: Props) {
  const [summary, setSummary] = useState<EquityTradeSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getEquityTradeSummary(instrumentId)
      .then(setSummary)
      .finally(() => setLoading(false));
  }, [instrumentId]);

  if (loading) {
    return (
      <div className="card animate-pulse h-24 flex items-center justify-center">
        <span className="text-gray-400 text-sm">Cargando resumen...</span>
      </div>
    );
  }

  if (!summary) return null;

  const plPositive = summary.pl_no_realizado != null && summary.pl_no_realizado >= 0;
  const plColor = summary.pl_no_realizado == null
    ? 'text-gray-400'
    : plPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400';

  const fmtBRL = (v: number | null) =>
    v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 2 });

  const fmtQty = (v: number) =>
    v.toLocaleString('pt-BR', { maximumFractionDigits: 4 });

  const fmtPrice = (v: number | null) =>
    v == null ? '—' : v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="card border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <div>
          <span className="text-sm font-semibold text-gray-800 dark:text-gray-200">
            {summary.instrument_ticker && (
              <span className="font-mono text-indigo-600 dark:text-indigo-400 mr-1.5">{summary.instrument_ticker}</span>
            )}
            {summary.instrument_name}
          </span>
        </div>
        {summary.qty_actual < 0 && (
          <span className="text-xs bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400 px-2 py-0.5 rounded-full border border-rose-200 dark:border-rose-700 font-semibold">
            Cantidad negativa
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Cantidad actual</p>
          <p className={`font-mono font-semibold ${summary.qty_actual < 0 ? 'text-rose-500' : 'text-gray-800 dark:text-gray-200'}`}>
            {fmtQty(summary.qty_actual)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Precio prom. compra</p>
          <p className="font-mono font-semibold text-gray-800 dark:text-gray-200">
            R$ {fmtPrice(summary.avg_price_compra)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">Último precio</p>
          <p className="font-mono font-semibold text-gray-800 dark:text-gray-200">
            R$ {fmtPrice(summary.ultimo_precio)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">P&L no realizado</p>
          <p className={`font-mono font-semibold ${plColor}`}>
            {fmtBRL(summary.pl_no_realizado)}
            {summary.pl_no_realizado_pct != null && (
              <span className="ml-1 text-xs">
                ({summary.pl_no_realizado_pct >= 0 ? '+' : ''}{summary.pl_no_realizado_pct.toFixed(2)}%)
              </span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
