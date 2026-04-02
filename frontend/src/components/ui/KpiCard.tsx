import { ReactNode } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: ReactNode;
  subtitle?: ReactNode;
  trend?: { value: number; label?: string };
  loading?: boolean;
}

export default function KpiCard({ title, value, subtitle, trend, loading }: KpiCardProps) {
  if (loading) {
    return (
      <div className="card space-y-3">
        <div className="animate-pulse bg-slate-200 dark:bg-slate-700 h-3.5 w-1/2 rounded-lg" />
        <div className="animate-pulse bg-slate-200 dark:bg-slate-700 h-8 w-3/4 rounded-lg" />
        <div className="animate-pulse bg-slate-200 dark:bg-slate-700 h-3 w-1/3 rounded-lg" />
      </div>
    );
  }

  const isPositive = trend != null && trend.value >= 0;

  return (
    <div className="card">
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{title}</p>
      <p className="text-2xl font-bold mt-2 text-slate-900 dark:text-white">{value}</p>
      {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{subtitle}</p>}
      {trend != null && (
        <div className={`flex items-center gap-1 mt-2 text-sm font-semibold ${isPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'}`}>
          {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          <span>{Math.abs(trend.value * 100).toFixed(2)}%</span>
          {trend.label && <span className="text-slate-400 dark:text-slate-500 font-normal ml-0.5">{trend.label}</span>}
        </div>
      )}
    </div>
  );
}
