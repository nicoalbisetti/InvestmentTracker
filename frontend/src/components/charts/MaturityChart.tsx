import { useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { fmtBRL, INSTRUMENT_TYPE_COLORS } from '../../utils/formatters';

const TYPE_LABELS: Record<string, string> = {
  renta_fija: 'Renta Fija',
  accion: 'Acciones',
  fii: 'FII',
  fundo: 'Fondos',
  previdencia: 'Previdencia',
  prestamos: 'Préstamos',
  saving: 'Saving',
  fgts: 'FGTS',
  outro: 'Otro',
};

const FALLBACK_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];

function color(type: string, idx: number) {
  return (INSTRUMENT_TYPE_COLORS as any)[type] || FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
}

interface MaturityChartProps {
  data: Array<{
    month: string;
    total: number;
    by_type: Record<string, number>;
    instruments: Array<{ name: string; type: string; balance_brl: number }>;
  }>;
  types: string[];
  outliers: Array<{ name: string; maturity_date: string; balance_brl: number }>;
  height?: number;
}

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const instruments: any[] = payload[0]?.payload?.instruments || [];
  const label: string = payload[0]?.payload?.label || '';
  const total = payload.reduce((s: number, p: any) => s + (p.value || 0), 0);

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg shadow-lg p-3 max-w-xs">
      <p className="font-semibold text-slate-700 dark:text-slate-200 mb-2">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex justify-between gap-4 text-sm">
          <span style={{ color: p.fill }}>{TYPE_LABELS[p.dataKey] || p.dataKey}</span>
          <span className="font-mono text-slate-700 dark:text-slate-200">{fmtBRL(p.value)}</span>
        </div>
      ))}
      <div className="border-t border-slate-200 dark:border-slate-600 mt-2 pt-2 text-sm font-semibold flex justify-between">
        <span className="text-slate-600 dark:text-slate-300">Total</span>
        <span className="font-mono text-slate-800 dark:text-white">{fmtBRL(total)}</span>
      </div>
      {instruments.length > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-600 space-y-1">
          {instruments.map((inst: any) => (
            <div key={inst.name} className="flex justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="truncate max-w-[140px]" title={inst.name}>{inst.name}</span>
              <span className="font-mono shrink-0">{fmtBRL(inst.balance_brl)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function groupByYear(data: MaturityChartProps['data']) {
  const byYear: Record<string, { year: string; total: number; by_type: Record<string, number>; instruments: any[] }> = {};
  for (const d of data) {
    const year = d.month.slice(0, 4);
    if (!byYear[year]) byYear[year] = { year, total: 0, by_type: {}, instruments: [] };
    byYear[year].total += d.total;
    byYear[year].instruments.push(...d.instruments);
    for (const [t, v] of Object.entries(d.by_type)) {
      byYear[year].by_type[t] = (byYear[year].by_type[t] || 0) + v;
    }
  }
  return Object.values(byYear).map(y => ({
    ...y,
    total: Math.round(y.total * 100) / 100,
    by_type: Object.fromEntries(Object.entries(y.by_type).map(([t, v]) => [t, Math.round(v * 100) / 100])),
  }));
}

export default function MaturityChart({ data, types, outliers, height = 320 }: MaturityChartProps) {
  const [groupBy, setGroupBy] = useState<'month' | 'year'>('month');

  const yearData = groupByYear(data);
  const activeData = groupBy === 'year' ? yearData : data;

  const chartData = activeData.map((d: any) => ({
    label: groupBy === 'year' ? d.year : d.month,
    instruments: d.instruments,
    ...d.by_type,
  }));

  const totalMaturing = data.reduce((s, d) => s + d.total, 0);
  const outliersTotal = outliers.reduce((s, o) => s + o.balance_brl, 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-500 dark:text-slate-400">
          {groupBy === 'month' ? `${data.length} meses` : `${yearData.length} años`} con vencimientos · {fmtBRL(totalMaturing)} en horizonte 10 años
          {outliers.length > 0 && (
            <span className="ml-3 text-amber-500" title={outliers.map(o => `${o.name}: ${o.maturity_date}`).join('\n')}>
              +{outliers.length} fuera de horizonte ({fmtBRL(outliersTotal)})
            </span>
          )}
        </span>
        <div className="flex rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 shrink-0">
          {(['month', 'year'] as const).map(opt => (
            <button
              key={opt}
              onClick={() => setGroupBy(opt)}
              className={`px-3 py-1 text-xs font-medium transition-colors ${
                groupBy === opt
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
              }`}
            >
              {opt === 'month' ? 'Mensual' : 'Anual'}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: groupBy === 'month' ? 40 : 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: groupBy === 'month' ? 10 : 12, fill: '#94a3b8' }}
            angle={groupBy === 'month' ? -45 : 0}
            textAnchor={groupBy === 'month' ? 'end' : 'middle'}
            interval={groupBy === 'month' ? 'preserveStartEnd' : 0}
          />
          <YAxis
            tickFormatter={v => v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(0)}k` : String(v)}
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            width={52}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            formatter={t => TYPE_LABELS[t] || t}
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          />
          {types.map((type, idx) => (
            <Bar key={type} dataKey={type} stackId="a" fill={color(type, idx)} radius={idx === types.length - 1 ? [3, 3, 0, 0] : undefined} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
