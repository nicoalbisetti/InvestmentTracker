import { ReactNode } from 'react';

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
        <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-4 w-1/2 rounded" />
        <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-8 w-3/4 rounded" />
        <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-3 w-1/3 rounded" />
      </div>
    );
  }

  return (
    <div className="card">
      <p className="text-sm text-gray-500 dark:text-gray-400 font-medium">{title}</p>
      <p className="text-2xl font-bold mt-1 text-gray-900 dark:text-white">{value}</p>
      {subtitle && <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{subtitle}</p>}
      {trend != null && (
        <p className={`text-sm font-medium mt-2 ${trend.value >= 0 ? 'positive' : 'negative'}`}>
          {trend.value >= 0 ? '▲' : '▼'} {Math.abs(trend.value * 100).toFixed(2)}%
          {trend.label && <span className="text-gray-400 font-normal ml-1">{trend.label}</span>}
        </p>
      )}
    </div>
  );
}
