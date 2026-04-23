import { useEffect, useState } from 'react';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { getAnnualGrowth, getMonthlyGrowth } from '../api/growth';
import type { AnnualGrowthResponse, MonthlyGrowthResponse, MonthlyTransaction } from '../api/growth';
import { fmtBRL, fmtPct, fmtDate, MONTH_NAMES } from '../utils/formatters';

const BLUE = '#378ADD';
const GREEN = '#639922';
const RED = '#E24B4A';
const GRAY = '#9CA3AF';

function fmtAxisM(v: number) {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function BadgeBRL({ value, positive: positiveColor }: { value: number | null; positive: 'blue' | 'green' | 'growth' }) {
  if (value == null) return <span className="text-gray-400 text-xs">—</span>;
  const pos = value >= 0;
  let cls: string;
  if (positiveColor === 'blue') {
    cls = pos
      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
      : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
  } else {
    cls = pos
      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
      : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
  }
  return (
    <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${cls}`}>
      {fmtBRL(value)}
    </span>
  );
}

function BadgePct({ value }: { value: number | null }) {
  if (value == null) return <span className="text-gray-400 text-xs">—</span>;
  const pos = value >= 0;
  const cls = pos
    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
  return (
    <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${cls}`}>
      {fmtPct(value, 1)}
    </span>
  );
}

function AnnualTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload ?? {};
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-sm shadow-lg">
      <p className="font-bold mb-2">{label}</p>
      <p className="text-gray-600 dark:text-gray-400">
        Aportes netos: <span className="font-mono text-gray-900 dark:text-white">{fmtBRL(d.net_flow)}</span>
      </p>
      <p className="text-gray-600 dark:text-gray-400">
        Valorización: <span className="font-mono text-gray-900 dark:text-white">{fmtBRL(d.gain)}</span>
      </p>
      <p className="text-gray-600 dark:text-gray-400 mt-1 border-t border-gray-200 dark:border-gray-700 pt-1">
        Patrimonio fin: <span className="font-mono font-semibold text-gray-900 dark:text-white">{fmtBRL(d.patrimonio_fin)}</span>
      </p>
    </div>
  );
}

function AnnualLegend() {
  return (
    <div className="flex items-center gap-6 justify-center mt-3 text-xs text-gray-600 dark:text-gray-400">
      <div className="flex items-center gap-1.5">
        <span className="w-3 h-3 rounded inline-block" style={{ background: BLUE }} />
        Aportes netos
      </div>
      <div className="flex items-center gap-1.5">
        <span className="w-3 h-3 rounded inline-block" style={{ background: GREEN }} />
        Valorización
      </div>
      <div className="flex items-center gap-1.5">
        <svg width="24" height="10" className="inline-block">
          <line x1="0" y1="5" x2="24" y2="5" stroke={GRAY} strokeDasharray="4 2" strokeWidth="1.5" />
        </svg>
        Patrimonio fin de año
      </div>
    </div>
  );
}

function MonthlyTooltip({ active, payload, label, transactions }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload ?? {};
  const monthTxns: MonthlyTransaction[] = (transactions ?? []).filter((t: MonthlyTransaction) => t.month === d.month);
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-sm shadow-lg max-w-xs">
      <p className="font-bold mb-2">{label}</p>
      {d.patrimonio != null && (
        <p className="text-gray-600 dark:text-gray-400">
          Patrimonio: <span className="font-mono text-gray-900 dark:text-white">{fmtBRL(d.patrimonio)}</span>
        </p>
      )}
      {d.valorizacion_acum != null && (
        <p className="text-gray-600 dark:text-gray-400">
          Valoriz. acum.: <span className="font-mono text-gray-900 dark:text-white">{fmtBRL(d.valorizacion_acum)}</span>
        </p>
      )}
      {monthTxns.length > 0 && (
        <div className="mt-2 border-t border-gray-200 dark:border-gray-700 pt-2">
          <p className="text-xs text-gray-500 mb-1">Movimientos:</p>
          {monthTxns.map((t, i) => (
            <p key={i} className="text-xs">
              <span className={t.type === 'aplicacion' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                {t.type === 'aplicacion' ? '+' : '-'}{fmtBRL(Math.abs(t.amount_brl))}
              </span>
              {' '}
              <span className="text-gray-600 dark:text-gray-400">{t.instrument_name}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function CustomDot(props: any) {
  const { cx, cy, payload } = props;
  if (payload?.patrimonio == null || cx == null || cy == null) return null;
  const nf: number = payload.net_flow ?? 0;
  if (nf !== 0) {
    const fill = nf > 0 ? GREEN : RED;
    return <circle cx={cx} cy={cy} r={7} fill={fill} stroke="white" strokeWidth={1.5} />;
  }
  return <circle cx={cx} cy={cy} r={3} fill={BLUE} />;
}

export default function Annual() {
  const currentYear = new Date().getFullYear();
  const [view, setView] = useState<'anual' | 'mensual'>('anual');
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [annualData, setAnnualData] = useState<AnnualGrowthResponse | null>(null);
  const [monthlyData, setMonthlyData] = useState<MonthlyGrowthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [monthlyLoading, setMonthlyLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getAnnualGrowth().then(setAnnualData).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (view === 'mensual') {
      setMonthlyLoading(true);
      getMonthlyGrowth(selectedYear).then(setMonthlyData).finally(() => setMonthlyLoading(false));
    }
  }, [view, selectedYear]);

  if (loading) return <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-96 rounded-xl" />;
  if (!annualData) return null;

  const items = annualData.items;
  const metrics = annualData.metrics;
  const latestPatrimonio = items.length > 0 ? items[items.length - 1].patrimonio_fin : null;

  const bestYearItem = items.reduce<typeof items[0] | null>((best, item) => {
    if (item.gain == null) return best;
    if (best == null || best.gain == null || item.gain > best.gain) return item;
    return best;
  }, null);

  // ── VISTA ANUAL ──
  const annualChartData = items.map(item => ({
    year: String(item.year),
    net_flow: item.net_flow ?? 0,
    gain: item.gain ?? 0,
    patrimonio_fin: item.patrimonio_fin,
  }));

  // ── VISTA MENSUAL ──
  const monthChartData = (monthlyData?.months ?? []).map(m => ({
    month: m.month,
    label: MONTH_NAMES[m.month - 1],
    patrimonio: m.patrimonio,
    net_flow: m.net_flow,
    valorizacion_acum: m.valorizacion_acum,
  }));

  const availableYears = [...items].map(i => i.year).sort((a, b) => b - a);

  const monthlyTransactions = monthlyData?.transactions ?? [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Crecimiento de Patrimonio</h1>
          {latestPatrimonio != null && (
            <p className="text-gray-500 dark:text-gray-400 text-sm mt-0.5">
              Patrimonio actual: <span className="font-semibold text-gray-900 dark:text-white">{fmtBRL(latestPatrimonio)}</span>
            </p>
          )}
        </div>
        <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 text-sm">
          <button
            onClick={() => setView('anual')}
            className={`px-4 py-2 font-medium transition-colors ${
              view === 'anual'
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'
            }`}
          >
            Anual
          </button>
          <button
            onClick={() => setView('mensual')}
            className={`px-4 py-2 font-medium transition-colors ${
              view === 'mensual'
                ? 'bg-blue-600 text-white'
                : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'
            }`}
          >
            Mensual
          </button>
        </div>
      </div>

      {/* ══════════ VISTA ANUAL ══════════ */}
      {view === 'anual' && (
        <>
          {/* Metric cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total aportado</p>
              <p className="text-xl font-bold mt-1 text-gray-900 dark:text-white">{fmtBRL(metrics.total_invested)}</p>
              <p className="text-xs text-gray-400 mt-0.5">histórico</p>
            </div>
            <div className="card text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Ganado por mercado</p>
              <p className={`text-xl font-bold mt-1 ${(metrics.total_gained ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {fmtBRL(metrics.total_gained)}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">valorización</p>
            </div>
            <div className="card text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">CAGR del portfolio</p>
              <p className="text-xl font-bold mt-1 text-gray-900 dark:text-white">{fmtPct(metrics.cagr, 1)}</p>
              <p className="text-xs text-gray-400 mt-0.5">anualizado</p>
            </div>
            <div className="card text-center">
              <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Mejor año</p>
              <p className="text-xl font-bold mt-1 text-gray-900 dark:text-white">
                {bestYearItem ? String(bestYearItem.year) : '—'}
              </p>
              <p className="text-xs text-gray-400 mt-0.5">{bestYearItem ? fmtBRL(bestYearItem.gain) : '—'}</p>
            </div>
          </div>

          {/* Annual chart */}
          <div className="card">
            <h2 className="font-semibold text-gray-900 dark:text-white mb-4">Composición del crecimiento anual</h2>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={annualChartData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                <YAxis
                  yAxisId="left"
                  tickFormatter={fmtAxisM}
                  tick={{ fontSize: 11 }}
                  width={60}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tickFormatter={fmtAxisM}
                  tick={{ fontSize: 11 }}
                  width={60}
                />
                <Tooltip content={<AnnualTooltip />} />
                <Bar yAxisId="left" dataKey="net_flow" name="Aportes netos" maxBarSize={30}>
                  {annualChartData.map((entry, i) => (
                    <Cell key={i} fill={entry.net_flow >= 0 ? BLUE : RED} />
                  ))}
                </Bar>
                <Bar yAxisId="left" dataKey="gain" name="Valorización" maxBarSize={30}>
                  {annualChartData.map((entry, i) => (
                    <Cell key={i} fill={entry.gain >= 0 ? GREEN : RED} />
                  ))}
                </Bar>
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="patrimonio_fin"
                  name="Patrimonio fin de año"
                  stroke={GRAY}
                  strokeDasharray="4 2"
                  strokeWidth={1.5}
                  dot={{ r: 3, fill: GRAY }}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
            <AnnualLegend />
          </div>

          {/* Annual table */}
          <div className="card p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {['Año', 'Inicio', 'Aportes netos', 'Valorización', 'Fin', 'Crecim.', '% Valor.', 'Fuente'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {[...items].reverse().map(row => (
                    <tr key={row.year} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                      <td className="px-4 py-3 font-bold text-gray-900 dark:text-white">{row.year}</td>
                      <td className="px-4 py-3 font-mono text-gray-500 dark:text-gray-400 text-xs">{fmtBRL(row.patrimonio_inicio)}</td>
                      <td className="px-4 py-3">
                        <BadgeBRL value={row.net_flow} positive="blue" />
                      </td>
                      <td className="px-4 py-3">
                        <BadgeBRL value={row.gain} positive="green" />
                      </td>
                      <td className="px-4 py-3 font-bold font-mono text-gray-900 dark:text-white text-xs">{fmtBRL(row.patrimonio_fin)}</td>
                      <td className="px-4 py-3">
                        <BadgePct value={row.pct_growth} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">
                        {row.pct_valorization != null ? `${Math.round(row.pct_valorization * 100)}%` : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          title={row.data_source === 'calculated' ? 'Calculado desde transacciones' : 'Dato histórico importado'}
                          className="cursor-default text-base"
                        >
                          {row.data_source === 'calculated' ? '⚡' : '📋'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* ══════════ VISTA MENSUAL ══════════ */}
      {view === 'mensual' && (
        <>
          {/* Year selector */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Año:</label>
            <select
              value={selectedYear}
              onChange={e => setSelectedYear(Number(e.target.value))}
              className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {availableYears.map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {monthlyLoading ? (
            <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-64 rounded-xl" />
          ) : monthlyData ? (
            <>
              {/* Monthly metric cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card text-center">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Patrimonio fin {selectedYear}</p>
                  <p className="text-xl font-bold mt-1 text-gray-900 dark:text-white">
                    {fmtBRL(monthlyData.summary.patrimonio_fin)}
                  </p>
                </div>
                <div className="card text-center">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Aportes netos</p>
                  <p className={`text-xl font-bold mt-1 ${(monthlyData.summary.net_flow_total ?? 0) >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-600 dark:text-red-400'}`}>
                    {fmtBRL(monthlyData.summary.net_flow_total)}
                  </p>
                  {monthlyData.summary.pct_net_flow != null && (
                    <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-1.5 py-0.5 rounded">
                      {Math.round((monthlyData.summary.pct_net_flow) * 100)}% del crecimiento
                    </span>
                  )}
                </div>
                <div className="card text-center">
                  <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">Valorización</p>
                  <p className={`text-xl font-bold mt-1 ${(monthlyData.summary.gain_total ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {fmtBRL(monthlyData.summary.gain_total)}
                  </p>
                  {monthlyData.summary.pct_gain != null && (
                    <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 px-1.5 py-0.5 rounded">
                      {Math.round((monthlyData.summary.pct_gain) * 100)}% del crecimiento
                    </span>
                  )}
                </div>
              </div>

              {/* Monthly chart */}
              <div className="card">
                <h2 className="font-semibold text-gray-900 dark:text-white mb-4">Evolución mensual {selectedYear}</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={monthChartData} margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis
                      yAxisId="left"
                      tickFormatter={fmtAxisM}
                      tick={{ fontSize: 11 }}
                      width={65}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tickFormatter={fmtAxisM}
                      tick={{ fontSize: 11 }}
                      width={65}
                    />
                    <Tooltip content={<MonthlyTooltip transactions={monthlyTransactions} />} />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="patrimonio"
                      name="Patrimonio total"
                      stroke={BLUE}
                      strokeWidth={2}
                      connectNulls={false}
                      dot={<CustomDot />}
                      activeDot={{ r: 5 }}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="valorizacion_acum"
                      name="Valorización acum."
                      stroke={GREEN}
                      strokeDasharray="4 3"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
                <div className="flex items-center gap-6 justify-center mt-3 text-xs text-gray-600 dark:text-gray-400">
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full inline-block" style={{ background: BLUE }} />
                    Patrimonio total
                  </div>
                  <div className="flex items-center gap-1.5">
                    <svg width="24" height="10" className="inline-block">
                      <line x1="0" y1="5" x2="24" y2="5" stroke={GREEN} strokeDasharray="4 3" strokeWidth="1.5" />
                    </svg>
                    Valorización acum.
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full inline-block" style={{ background: GREEN }} />
                    Aporte
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full inline-block" style={{ background: RED }} />
                    Rescate
                  </div>
                </div>
              </div>

              {/* Transactions list */}
              <div className="card">
                <h2 className="font-semibold text-gray-900 dark:text-white mb-4">Movimientos del año {selectedYear}</h2>
                {monthlyTransactions.length === 0 ? (
                  <div className="text-center py-6">
                    <p className="text-gray-500 dark:text-gray-400">Sin movimientos registrados para este año</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      Los movimientos históricos provienen de datos importados
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100 dark:divide-gray-800">
                    {monthlyTransactions.map((t, i) => (
                      <div key={i} className="flex items-center justify-between py-3">
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-500 dark:text-gray-400 w-20">{fmtDate(t.date)}</span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                            t.type === 'aplicacion'
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          }`}>
                            {t.type === 'aplicacion' ? 'aporte' : 'rescate'}
                          </span>
                          <span className="text-sm text-gray-700 dark:text-gray-300">{t.instrument_name}</span>
                        </div>
                        <span className={`font-mono text-sm font-semibold ${
                          t.type === 'aplicacion'
                            ? 'text-green-600 dark:text-green-400'
                            : 'text-red-600 dark:text-red-400'
                        }`}>
                          {t.type === 'aplicacion' ? '+' : '-'}{fmtBRL(Math.abs(t.amount_brl))}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}
