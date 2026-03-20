import { useEffect, useState } from 'react';
import { getInstruments } from '../api/instruments';
import { getInstrumentHistory, compareInstruments } from '../api/history';
import LineChartComp from '../components/charts/LineChartComp';
import { fmtPct, fmtBRL } from '../utils/formatters';

export default function History() {
  const [instruments, setInstruments] = useState<any[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [data, setData] = useState<any>(null);
  const [compareData, setCompareData] = useState<any[]>([]);
  const [view, setView] = useState<'balance' | 'pct'>('balance');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getInstruments({ status: 'activo', limit: 200 }).then((r: any) => setInstruments(r.items));
  }, []);

  useEffect(() => {
    if (selected.length === 0) { setData(null); setCompareData([]); return; }
    setLoading(true);
    if (selected.length === 1) {
      getInstrumentHistory(selected[0])
        .then(setData)
        .finally(() => setLoading(false));
    } else {
      compareInstruments(selected)
        .then((res: any[]) => {
          // Build combined timeline
          const allDates = [...new Set(res.flatMap(r => r.positions.map((p: any) => p.date)))].sort();
          const merged = allDates.map(date => {
            const row: any = { date };
            res.forEach(r => {
              const pos = r.positions.find((p: any) => p.date === date);
              row[r.instrument.name] = pos?.balance_brl;
            });
            return row;
          });
          setCompareData(merged);
          setData({ compare: res });
        })
        .finally(() => setLoading(false));
    }
  }, [selected]);

  const toggleSelect = (id: number) => {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  };

  const seriesForCompare = compareData.length > 0
    ? Object.keys(compareData[0]).filter(k => k !== 'date').map(k => ({ key: k, label: k }))
    : [];

  const singlePositions = data && !data.compare ? data.positions : [];
  const singleSeries = [{ key: 'balance_brl', label: data?.instrument?.name || 'Saldo' }];

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="font-semibold mb-3">Seleccionar instrumentos</h2>
        <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
          {instruments.map((inst: any) => (
            <button
              key={inst.id}
              onClick={() => toggleSelect(inst.id)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                selected.includes(inst.id)
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-400'
              }`}
            >
              {inst.name}
            </button>
          ))}
        </div>
        {selected.length > 0 && (
          <button className="mt-2 text-xs text-red-400 hover:text-red-600" onClick={() => setSelected([])}>
            Limpiar selección
          </button>
        )}
      </div>

      {data && (
        <>
          {/* Metrics (single instrument) */}
          {!data.compare && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: 'CAGR', value: fmtPct(data.metrics?.cagr) },
                { label: 'Retorno Total', value: fmtPct(data.metrics?.total_return) },
                { label: 'Volatilidad Anual', value: fmtPct(data.metrics?.volatility) },
                { label: 'Max Drawdown', value: fmtPct(data.metrics?.max_drawdown) },
              ].map(m => (
                <div key={m.label} className="card text-center">
                  <p className="text-xs text-gray-500">{m.label}</p>
                  <p className="text-xl font-bold mt-1">{m.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Chart */}
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">{data.compare ? 'Comparación' : data.instrument?.name}</h2>
              {!data.compare && (
                <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
                  {[{ v: 'balance', l: 'Saldo' }, { v: 'pct', l: '% Retorno' }].map(o => (
                    <button
                      key={o.v}
                      onClick={() => setView(o.v as any)}
                      className={`px-3 py-1 text-sm ${view === o.v ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600'}`}
                    >
                      {o.l}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {loading ? (
              <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-72 rounded" />
            ) : data.compare ? (
              <LineChartComp
                data={compareData}
                series={seriesForCompare}
                xKey="date"
                height={320}
              />
            ) : (
              <LineChartComp
                data={singlePositions.map((p: any) => ({ ...p, balance_brl: p.balance_brl, gain_pct: p.gain_pct }))}
                series={view === 'balance' ? singleSeries : [{ key: 'gain_pct', label: 'Retorno mensual' }]}
                xKey="date"
                height={320}
                pct={view === 'pct'}
              />
            )}
          </div>

          {/* Data table (single) */}
          {!data.compare && singlePositions.length > 0 && (
            <div className="card p-0 overflow-hidden">
              <div className="overflow-x-auto max-h-64">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
                    <tr>
                      {['Fecha', 'Saldo BRL', 'Ganancia', 'Ret. Mensual', 'Aplicaciones', 'Rescates'].map(h => (
                        <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {[...singlePositions].reverse().map((p: any) => (
                      <tr key={p.date} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-3 py-2">{p.date?.slice(0, 7)}</td>
                        <td className="px-3 py-2 font-mono">{fmtBRL(p.balance_brl)}</td>
                        <td className={`px-3 py-2 font-mono ${p.gain >= 0 ? 'positive' : 'negative'}`}>{fmtBRL(p.gain)}</td>
                        <td className={`px-3 py-2 font-mono ${(p.gain_pct || 0) >= 0 ? 'positive' : 'negative'}`}>{fmtPct(p.gain_pct)}</td>
                        <td className="px-3 py-2 font-mono text-gray-500">{fmtBRL(p.applications)}</td>
                        <td className="px-3 py-2 font-mono text-gray-500">{fmtBRL(p.redemptions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {!data && (
        <div className="card text-center text-gray-400 py-12">
          Selecciona uno o más instrumentos para ver su evolución histórica
        </div>
      )}
    </div>
  );
}
