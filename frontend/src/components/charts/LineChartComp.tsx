import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { fmtBRL, fmtDate } from '../../utils/formatters';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];

interface Series {
  key: string;
  label: string;
}

interface Props {
  data: any[];
  series: Series[];
  xKey: string;
  height?: number;
  pct?: boolean;
}

export default function LineChartComp({ data, series, xKey, height = 320, pct = false }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey={xKey}
          tickFormatter={v => { const [y, m] = v.split('-'); return `${m}/${y.slice(2)}`; }}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={v => pct ? `${(v * 100).toFixed(1)}%` : v >= 1e6 ? `R$${(v / 1e6).toFixed(1)}M` : `R$${(v / 1e3).toFixed(0)}K`}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          width={70}
        />
        <Tooltip
          formatter={(val: any, name: any) => [pct ? `${(val * 100).toFixed(2)}%` : fmtBRL(val), name]}
          labelFormatter={label => fmtDate(label)}
          contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}
        />
        <Legend iconSize={10} formatter={v => <span style={{ fontSize: 12, color: '#6b7280' }}>{v}</span>} />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.label}
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
