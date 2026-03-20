import { useEffect, useState } from 'react';
import { getProventos, getMonthlyProventos } from '../api/proventos';
import BarChartComp from '../components/charts/BarChartComp';
import { fmtBRL, MONTH_NAMES } from '../utils/formatters';
import { SkeletonTable } from '../components/ui/SkeletonLoader';

export default function Proventos() {
  const [data, setData] = useState<any>({ items: [], years: [] });
  const [monthly, setMonthly] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([getProventos(page), getMonthlyProventos()])
      .then(([p, m]) => { setData(p); setMonthly(m); })
      .finally(() => setLoading(false));
  }, [page]);

  const monthlyChartData = (monthly?.monthly || []).map((m: any) => ({
    month: MONTH_NAMES[m.month - 1],
    Proventos: m.amount || 0,
  }));

  const years: number[] = data.years || [];

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      {monthly && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: `Total ${monthly.year}`, value: fmtBRL(monthly.total) },
            { label: `Total ${monthly.year - 1}`, value: fmtBRL(monthly.prev_year_total) },
            { label: 'Proyección Anual', value: fmtBRL(monthly.projection_annual) },
            {
              label: 'Variación vs año anterior',
              value: monthly.prev_year_total
                ? `${(((monthly.total - monthly.prev_year_total) / monthly.prev_year_total) * 100).toFixed(1)}%`
                : '—',
            },
          ].map(m => (
            <div key={m.label} className="card text-center">
              <p className="text-sm text-gray-500">{m.label}</p>
              <p className="text-xl font-bold mt-1">{m.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Monthly chart */}
      {monthly && (
        <div className="card">
          <h2 className="font-semibold mb-4">Proventos Mensuales {monthly.year}</h2>
          <BarChartComp
            data={monthlyChartData}
            bars={[{ key: 'Proventos', label: 'Proventos', color: '#10b981' }]}
            xKey="month"
            height={220}
          />
        </div>
      )}

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-5"><SkeletonTable rows={8} /></div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase sticky left-0 bg-gray-50 dark:bg-gray-800">Instrumento</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Saldo</th>
                    {years.map(y => (
                      <th key={y} className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">
                        {y}
                      </th>
                    ))}
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.items.map((row: any) => (
                    <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-3 py-2.5 font-medium max-w-[160px] truncate sticky left-0 bg-white dark:bg-gray-900" title={row.name}>
                        {row.name}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-gray-600">{fmtBRL(row.balance_brl)}</td>
                      {years.map(y => (
                        <td key={y} className={`px-3 py-2.5 text-right font-mono ${row.years[y] ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-300 dark:text-gray-600'}`}>
                          {row.years[y] ? fmtBRL(row.years[y]) : '—'}
                        </td>
                      ))}
                      <td className="px-3 py-2.5 text-right font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                        {fmtBRL(row.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
                <p className="text-sm text-gray-500">Página {page} de {data.pages}</p>
                <div className="flex gap-2">
                  <button className="btn-secondary text-sm py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
                  <button className="btn-secondary text-sm py-1" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Siguiente →</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
