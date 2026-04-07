import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { fmtBRL, fmtUSD, fmtDate } from '../../utils/formatters';

interface DataPoint {
  date: string;
  value: number;
}

interface Props {
  data: DataPoint[];
  currency?: 'BRL' | 'USD';
  height?: number;
}

function formatYAxis(value: number, currency: string) {
  if (value >= 1_000_000) return `${currency === 'BRL' ? 'R$' : 'US$'}${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${currency === 'BRL' ? 'R$' : 'US$'}${(value / 1_000).toFixed(0)}K`;
  return String(value);
}

export default function EvolutionChart({ data, currency = 'BRL', height = 300 }: Props) {
  const fmt = currency === 'BRL' ? fmtBRL : fmtUSD;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <defs>
          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-gray-700" />
        <XAxis
          dataKey="date"
          tickFormatter={v => {
            const [y, m] = v.split('-');
            return `${m}/${y.slice(2)}`;
          }}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={v => formatYAxis(v, currency)}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          width={65}
        />
        <Tooltip
          formatter={(val: any) => [fmt(val), 'Total']}
          labelFormatter={label => {
            const [y, m] = label.split('-');
            const lastDay = new Date(Number(y), Number(m), 0).getDate();
            return fmtDate(`${y}-${m}-${String(lastDay).padStart(2, '0')}`);
          }}
          contentStyle={{ background: 'var(--tw-bg, #fff)', border: '1px solid #e5e7eb', borderRadius: 8 }}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke="#3b82f6"
          strokeWidth={2}
          fill="url(#colorValue)"
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
