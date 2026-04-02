import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';

interface BenchmarkSeries {
  date: string;
  portfolio?: number | null;
  cdi?: number | null;
  ipca?: number | null;
}

interface Props {
  data: BenchmarkSeries[];
  showCdi: boolean;
  showIpca: boolean;
  height?: number;
}

function fmtPctReturn(v: number) {
  const pct = v - 100;
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`;
}

export default function BenchmarkChart({ data, showCdi, showIpca, height = 260 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          tickFormatter={v => { const [y, m] = v.split('-'); return `${m}/${y.slice(2)}`; }}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={fmtPctReturn}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          width={60}
        />
        <Tooltip
          formatter={(val: any, name: string) => [fmtPctReturn(val), name]}
          labelFormatter={label => { const [y, m] = label.split('-'); return `${m}/${y}`; }}
          contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 16px rgba(0,0,0,0.08)' }}
        />
        <Legend iconSize={10} formatter={v => <span style={{ fontSize: 12, color: '#6b7280' }}>{v}</span>} />
        <Line
          type="monotone"
          dataKey="portfolio"
          name="Portfolio"
          stroke="#6366f1"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4 }}
        />
        {showCdi && (
          <Line
            type="monotone"
            dataKey="cdi"
            name="CDI"
            stroke="#10b981"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            strokeDasharray="4 2"
          />
        )}
        {showIpca && (
          <Line
            type="monotone"
            dataKey="ipca"
            name="IPCA"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            strokeDasharray="4 2"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}
