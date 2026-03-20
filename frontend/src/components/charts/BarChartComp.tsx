import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { fmtBRL } from '../../utils/formatters';

interface Props {
  data: any[];
  bars: { key: string; label: string; color: string }[];
  xKey: string;
  height?: number;
  stacked?: boolean;
}

export default function BarChartComp({ data, bars, xKey, height = 300, stacked = false }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey={xKey} tick={{ fontSize: 12, fill: '#9ca3af' }} />
        <YAxis
          tickFormatter={v => v >= 1e6 ? `R$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `R$${(v / 1e3).toFixed(0)}K` : String(v)}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          width={65}
        />
        <Tooltip
          formatter={(val: any, name: any) => [fmtBRL(val), name]}
          contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 12 }}
        />
        <Legend iconSize={10} formatter={v => <span style={{ fontSize: 12, color: '#6b7280' }}>{v}</span>} />
        {bars.map(b => (
          <Bar key={b.key} dataKey={b.key} name={b.label} fill={b.color} stackId={stacked ? 'a' : undefined} radius={stacked ? undefined : [3, 3, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
