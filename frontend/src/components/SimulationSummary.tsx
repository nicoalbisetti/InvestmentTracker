import { SimulationResult, SimulationParams } from '../api/simulation';
import { SkeletonCard } from './ui/SkeletonLoader';

function fmtBRL(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

interface Props {
  result: SimulationResult | null;
  params: SimulationParams;
  isLoading: boolean;
}

export default function SimulationSummary({ result, params, isLoading }: Props) {
  if (isLoading || !result || result.data.length === 0) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  const lastPoint = result.data[result.data.length - 1];
  const finalValue = lastPoint.total;
  const totalContributed = params.monthly_contribution_brl * params.horizon_months;
  const gain = finalValue - result.initial_total_brl - totalContributed;
  const years = params.horizon_months / 12;
  const cagr =
    result.initial_total_brl > 0
      ? Math.pow(finalValue / result.initial_total_brl, 1 / years) - 1
      : 0;

  const isGainPositive = gain >= 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="card">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Valor final</p>
        <p className="text-2xl font-bold mt-2 text-slate-900 dark:text-white">{fmtBRL(finalValue)}</p>
      </div>

      <div className="card">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Total aportado</p>
        <p className="text-2xl font-bold mt-2 text-slate-900 dark:text-white">{fmtBRL(totalContributed)}</p>
      </div>

      <div className="card">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Ganancia estimada</p>
        <p className={`text-2xl font-bold mt-2 ${isGainPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'}`}>
          {isGainPositive ? '+' : ''}{fmtBRL(gain)}
        </p>
      </div>

      <div className="card">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">CAGR implícito</p>
        <p className={`text-2xl font-bold mt-2 ${cagr >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'}`}>
          {(cagr * 100).toFixed(1)}%
        </p>
        <p className="text-xs text-slate-400 mt-1">anual compuesto</p>
      </div>
    </div>
  );
}
