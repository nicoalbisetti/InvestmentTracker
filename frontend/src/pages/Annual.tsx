import { useEffect, useState } from 'react';
import { getAnnualSummary } from '../api/annual';
import BarChartComp from '../components/charts/BarChartComp';
import { fmtBRL, fmtPct } from '../utils/formatters';

export default function Annual() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAnnualSummary().then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-96 rounded-xl" />;
  if (!data) return null;

  const items = data.items || [];
  const chartData = items.map((i: any) => ({
    year: String(i.year),
    Ganancia: i.gain || 0,
    Aplicaciones: i.net_flow || 0,
  }));

  return (
    <div className="space-y-5">
      {/* Global metrics */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Invertido (Histórico)', value: fmtBRL(data.metrics?.total_invested) },
          { label: 'Total Ganado (Histórico)', value: fmtBRL(data.metrics?.total_gained) },
          { label: 'Ratio Ganancia / Capital', value: fmtPct(data.metrics?.gain_ratio) },
        ].map(m => (
          <div key={m.label} className="card text-center">
            <p className="text-sm text-gray-500">{m.label}</p>
            <p className="text-2xl font-bold mt-1">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      <div className="card">
        <h2 className="font-semibold mb-4">Ganancia vs. Flujo Neto de Capital por Año</h2>
        <BarChartComp
          data={chartData}
          bars={[
            { key: 'Ganancia', label: 'Ganancia Pura', color: '#10b981' },
            { key: 'Aplicaciones', label: 'Aplicaciones/Rescates', color: '#3b82f6' },
          ]}
          xKey="year"
          height={300}
        />
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              {['Año', 'Saldo Final', 'Variación', 'Ganancia Pura', 'Flujo Neto de Capital'].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {[...items].reverse().map((row: any) => (
              <tr key={row.year} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="px-4 py-3 font-semibold text-gray-900 dark:text-white">{row.year}</td>
                <td className="px-4 py-3 font-mono">{fmtBRL(row.total)}</td>
                <td className={`px-4 py-3 font-mono ${(row.diff || 0) >= 0 ? 'positive' : 'negative'}`}>{fmtBRL(row.diff)}</td>
                <td className={`px-4 py-3 font-mono ${(row.gain || 0) >= 0 ? 'positive' : 'negative'}`}>{fmtBRL(row.gain)}</td>
                <td className={`px-4 py-3 font-mono ${(row.net_flow || 0) >= 0 ? 'text-blue-600' : 'negative'}`}>{fmtBRL(row.net_flow)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
