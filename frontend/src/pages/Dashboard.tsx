import { useEffect, useState } from 'react';
import { getDashboardKPIs, getEvolution, getDistribution, getTopBottom } from '../api/dashboard';
import KpiCard from '../components/ui/KpiCard';
import EvolutionChart from '../components/charts/EvolutionChart';
import DonutChart from '../components/charts/DonutChart';
import { fmtBRL, fmtUSD, fmtPct, fmtDate, INSTRUMENT_TYPE_COLORS, CUSTODIAN_COLORS } from '../utils/formatters';

const RANGE_OPTIONS = [
  { label: '1A', value: '1y' },
  { label: '3A', value: '3y' },
  { label: '5A', value: '5y' },
  { label: 'Todo', value: 'all' },
];

export default function Dashboard() {
  const [kpis, setKpis] = useState<any>(null);
  const [evolution, setEvolution] = useState<any[]>([]);
  const [distribution, setDistribution] = useState<any>({ by_type: [], by_custodian: [] });
  const [topBottom, setTopBottom] = useState<any>(null);
  const [range, setRange] = useState('all');
  const [currency, setCurrency] = useState<'BRL' | 'USD'>('BRL');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([getDashboardKPIs(), getDistribution(), getTopBottom()])
      .then(([k, d, tb]) => {
        setKpis(k);
        setDistribution(d);
        setTopBottom(tb);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    getEvolution(range, currency).then(setEvolution);
  }, [range, currency]);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          loading={loading}
          title="Total Cartera"
          value={fmtBRL(kpis?.total_brl)}
          subtitle={kpis?.total_usd ? `≈ ${fmtUSD(kpis.total_usd)}` : undefined}
        />
        <KpiCard
          loading={loading}
          title="Variación del Mes"
          value={fmtBRL(kpis?.monthly_change_abs)}
          trend={kpis?.monthly_change_pct != null ? { value: kpis.monthly_change_pct, label: 'vs mes anterior' } : undefined}
        />
        <KpiCard
          loading={loading}
          title="YTD"
          value={fmtPct(kpis?.ytd_pct)}
          subtitle={kpis?.date ? `Al ${fmtDate(kpis.date)}` : undefined}
        />
        <KpiCard
          loading={loading}
          title="Proventos del Año"
          value={fmtBRL(kpis?.proventos_ytd)}
        />
      </div>

      {/* Evolution chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-800 dark:text-white">Evolución del Portfolio</h2>
          <div className="flex items-center gap-3">
            <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
              {['BRL', 'USD'].map(c => (
                <button
                  key={c}
                  onClick={() => setCurrency(c as any)}
                  className={`px-3 py-1 text-sm font-medium transition-colors ${currency === c ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50'}`}
                >
                  {c}
                </button>
              ))}
            </div>
            <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
              {RANGE_OPTIONS.map(o => (
                <button
                  key={o.value}
                  onClick={() => setRange(o.value)}
                  className={`px-3 py-1 text-sm font-medium transition-colors ${range === o.value ? 'bg-blue-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50'}`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <EvolutionChart data={evolution} currency={currency} height={300} />
      </div>

      {/* Distribution + Top/Bottom */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* By type */}
        <div className="card">
          <h2 className="font-semibold text-gray-800 dark:text-white mb-3">Por Tipo</h2>
          <DonutChart data={distribution.by_type} colors={INSTRUMENT_TYPE_COLORS} height={240} />
        </div>

        {/* By custodian */}
        <div className="card">
          <h2 className="font-semibold text-gray-800 dark:text-white mb-3">Por Custodio</h2>
          <DonutChart data={distribution.by_custodian} colors={CUSTODIAN_COLORS} height={240} />
        </div>

        {/* Top / Bottom 5 */}
        <div className="card">
          <h2 className="font-semibold text-gray-800 dark:text-white mb-3">Top / Bottom del Mes</h2>
          {topBottom ? (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mb-2">TOP 5</p>
                <ul className="space-y-1.5">
                  {topBottom.top5.map((inst: any) => (
                    <li key={inst.id} className="flex items-center justify-between text-sm">
                      <span className="text-gray-700 dark:text-gray-300 truncate max-w-[140px]" title={inst.name}>{inst.name}</span>
                      <span className="positive ml-2 shrink-0">{fmtPct(inst.return_1m)}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold text-red-500 mb-2">BOTTOM 5</p>
                <ul className="space-y-1.5">
                  {topBottom.bottom5.map((inst: any) => (
                    <li key={inst.id} className="flex items-center justify-between text-sm">
                      <span className="text-gray-700 dark:text-gray-300 truncate max-w-[140px]" title={inst.name}>{inst.name}</span>
                      <span className="negative ml-2 shrink-0">{fmtPct(inst.return_1m)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => <div key={i} className="animate-pulse bg-gray-200 dark:bg-gray-700 h-6 rounded" />)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
