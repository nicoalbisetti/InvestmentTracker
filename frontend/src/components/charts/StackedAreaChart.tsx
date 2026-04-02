import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { fmtBRL } from '../../utils/formatters';
import { INSTRUMENT_TYPE_COLORS } from '../../utils/formatters';

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

const FALLBACK_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#6b7280'];

interface Props {
  data: any[];
  types: string[];
  height?: number;
}

export default function StackedAreaChart({ data, types, height = 300 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <defs>
          {types.map((t, i) => {
            const color = INSTRUMENT_TYPE_COLORS[t] || FALLBACK_COLORS[i % FALLBACK_COLORS.length];
            return (
              <linearGradient key={t} id={`grad_${t}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.7} />
                <stop offset="95%" stopColor={color} stopOpacity={0.4} />
              </linearGradient>
            );
          })}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          tickFormatter={v => { const [y, m] = v.split('-'); return `${m}/${y.slice(2)}`; }}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={v => v >= 1e6 ? `R$${(v / 1e6).toFixed(1)}M` : `R$${(v / 1e3).toFixed(0)}K`}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          width={70}
        />
        <Tooltip
          formatter={(val: any, name: string) => [fmtBRL(val), TYPE_LABELS[name] || name]}
          labelFormatter={v => { const [y, m] = v.split('-'); return `${m}/${y}`; }}
          contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}
        />
        <Legend
          iconSize={10}
          formatter={v => <span style={{ fontSize: 12, color: '#6b7280' }}>{TYPE_LABELS[v] || v}</span>}
        />
        {types.map((t, i) => {
          const color = INSTRUMENT_TYPE_COLORS[t] || FALLBACK_COLORS[i % FALLBACK_COLORS.length];
          return (
            <Area
              key={t}
              type="monotone"
              dataKey={t}
              name={t}
              stackId="stack"
              stroke={color}
              fill={`url(#grad_${t})`}
              strokeWidth={1}
              dot={false}
              activeDot={{ r: 3 }}
            />
          );
        })}
      </AreaChart>
    </ResponsiveContainer>
  );
}
