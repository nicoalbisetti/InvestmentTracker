import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { fmtBRL } from '../../utils/formatters';

interface DataItem {
  name: string;
  value: number;
}

interface Props {
  data: DataItem[];
  colors: Record<string, string>;
  height?: number;
}

const DEFAULT_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#6b7280'];

export default function DonutChart({ data, colors, height = 260 }: Props) {
  const filtered = data.filter(d => d.value > 0);
  const total = filtered.reduce((sum, d) => sum + d.value, 0);

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const item = payload[0];
    const pct = total > 0 ? (item.value / total) * 100 : 0;
    return (
      <div style={{
        background: '#fff', border: '1px solid #e5e7eb',
        borderRadius: 8, fontSize: 12, padding: '6px 10px',
      }}>
        <p style={{ fontWeight: 600, marginBottom: 2 }}>{item.name}</p>
        <p>{fmtBRL(item.value)}</p>
        <p style={{ color: '#6b7280' }}>{pct.toFixed(1)}%</p>
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={filtered}
          cx="50%"
          cy="50%"
          innerRadius="50%"
          outerRadius="75%"
          paddingAngle={2}
          dataKey="value"
        >
          {filtered.map((entry, i) => (
            <Cell
              key={entry.name}
              fill={colors[entry.name] || DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
            />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => {
            const item = filtered.find(d => d.name === value);
            const pct = item && total > 0 ? ((item.value / total) * 100).toFixed(1) : '0.0';
            return (
              <span style={{ fontSize: 11, color: '#6b7280' }}>
                {value} <span style={{ color: '#374151', fontWeight: 500 }}>{pct}%</span>
              </span>
            );
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
