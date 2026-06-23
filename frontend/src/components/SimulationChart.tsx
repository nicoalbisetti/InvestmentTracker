import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Line, ComposedChart,
} from 'recharts';
import { INSTRUMENT_TYPE_COLORS } from '../utils/formatters';
import { SimulationDataPoint, CLASS_LABELS } from '../api/simulation';
import { SkeletonBlock } from './ui/SkeletonLoader';

const CLASSES = ['renta_fija', 'accion', 'fii', 'fundo', 'internacional'] as const;

function formatBRLAbbrev(value: number): string {
  if (value >= 1_000_000) return `R$ ${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `R$ ${(value / 1_000).toFixed(0)}k`;
  return `R$ ${value.toFixed(0)}`;
}

function formatDate(dateStr: string): string {
  const [year, month] = dateStr.split('-');
  const monthNames = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
  return `${monthNames[parseInt(month) - 1]} ${year.slice(2)}`;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const total = payload.find((p: any) => p.dataKey === 'total');
  const classes = payload.filter((p: any) => p.dataKey !== 'total');
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-3 shadow-lg text-xs space-y-1">
      <p className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{formatDate(label)}</p>
      {classes.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.fill }} />
            <span className="text-slate-600 dark:text-slate-300">{CLASS_LABELS[p.dataKey]}</span>
          </div>
          <span className="font-mono text-slate-800 dark:text-slate-100">{formatBRLAbbrev(p.value)}</span>
        </div>
      ))}
      {total && (
        <div className="flex items-center justify-between gap-4 border-t border-slate-200 dark:border-slate-700 pt-1 mt-1">
          <span className="font-semibold text-slate-700 dark:text-slate-200">Total</span>
          <span className="font-mono font-bold text-slate-900 dark:text-white">{formatBRLAbbrev(total.value)}</span>
        </div>
      )}
    </div>
  );
}

interface Props {
  data: SimulationDataPoint[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

export default function SimulationChart({ data, isLoading, error, onRetry }: Props) {
  if (isLoading) {
    return (
      <div className="card space-y-3">
        <SkeletonBlock className="h-6 w-1/3" />
        <SkeletonBlock className="h-72 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card flex flex-col items-center justify-center gap-3 py-12">
        <p className="text-rose-500 text-sm">{error}</p>
        <button onClick={onRetry} className="btn-secondary text-sm">Reintentar</button>
      </div>
    );
  }

  // Show tick every 12 months
  const tickIndices = new Set(data.filter((d) => d.month % 12 === 0).map((d) => d.date));

  return (
    <div className="card">
      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
          <defs>
            {CLASSES.map((cls) => (
              <linearGradient key={cls} id={`sim_grad_${cls}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={INSTRUMENT_TYPE_COLORS[cls]} stopOpacity={0.7} />
                <stop offset="95%" stopColor={INSTRUMENT_TYPE_COLORS[cls]} stopOpacity={0.35} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="date"
            tickFormatter={(v) => (tickIndices.has(v) ? formatDate(v) : '')}
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            interval={0}
          />
          <YAxis
            tickFormatter={formatBRLAbbrev}
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            width={80}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconSize={10}
            formatter={(v) => (
              <span style={{ fontSize: 12, color: '#6b7280' }}>
                {v === 'total' ? 'Total' : CLASS_LABELS[v] ?? v}
              </span>
            )}
          />
          {CLASSES.map((cls) => (
            <Area
              key={cls}
              type="monotone"
              dataKey={cls}
              name={cls}
              stackId="stack"
              stroke={INSTRUMENT_TYPE_COLORS[cls]}
              fill={`url(#sim_grad_${cls})`}
              strokeWidth={1}
              dot={false}
              activeDot={{ r: 3 }}
            />
          ))}
          <Line
            type="monotone"
            dataKey="total"
            name="total"
            stroke="#94a3b8"
            strokeDasharray="5 3"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
