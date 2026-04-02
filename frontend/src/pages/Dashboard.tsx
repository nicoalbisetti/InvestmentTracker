import { useEffect, useState } from 'react';
import { getDashboardKPIs, getEvolution, getDistribution, getTopBottom, getBenchmarks } from '../api/dashboard';
import client from '../api/client';
import KpiCard from '../components/ui/KpiCard';
import EvolutionChart from '../components/charts/EvolutionChart';
import BenchmarkChart from '../components/charts/BenchmarkChart';
import StackedAreaChart from '../components/charts/StackedAreaChart';
import DonutChart from '../components/charts/DonutChart';
import MaturityChart from '../components/charts/MaturityChart';
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
  const [noPriceCount, setNoPriceCount] = useState<number>(0);
  const [benchmarks, setBenchmarks] = useState<{ cdi: any[]; ipca: any[] } | null>(null);
  const [showCdi, setShowCdi] = useState(true);
  const [showIpca, setShowIpca] = useState(true);
  const [chartView, setChartView] = useState<'evolution' | 'benchmarks' | 'by-type'>('evolution');
  const [byType, setByType] = useState<{ data: any[]; types: string[] }>({ data: [], types: [] });
  const [maturities, setMaturities] = useState<{ data: any[]; types: string[]; outliers: any[] } | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getDashboardKPIs(), getDistribution(), getTopBottom()])
      .then(([k, d, tb]) => {
        setKpis(k);
        setDistribution(d);
        setTopBottom(tb);
      })
      .finally(() => setLoading(false));
    client.get('/api/positions/count-without-price').then(r => setNoPriceCount(r.data.count)).catch(() => {});
    client.get('/api/dashboard/maturities').then(r => setMaturities(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    getEvolution(range, currency).then(setEvolution);
    getBenchmarks(range).then(setBenchmarks).catch(() => setBenchmarks({ cdi: [], ipca: [] }));
    client.get('/api/dashboard/evolution-by-type', { params: { range } }).then(r => setByType(r.data)).catch(() => {});
  }, [range, currency]);

  // Build indexed benchmark series (base 100 from first portfolio date)
  const benchmarkData = (() => {
    if (!evolution.length) return [];
    const firstValue = evolution[0]?.value;
    if (!firstValue) return [];

    // Portfolio indexed: 100 * value / firstValue
    const portfolioByDate: Record<string, number> = {};
    evolution.forEach(p => {
      portfolioByDate[p.date.slice(0, 7)] = 100 * p.value / firstValue;
    });

    // CDI/IPCA: accumulate from 100
    const cdiByDate: Record<string, number> = {};
    if (benchmarks?.cdi?.length) {
      let acc = 100;
      benchmarks.cdi.forEach(r => { acc *= (1 + r.rate); cdiByDate[r.date] = acc; });
    }
    const ipcaByDate: Record<string, number> = {};
    if (benchmarks?.ipca?.length) {
      let acc = 100;
      benchmarks.ipca.forEach(r => { acc *= (1 + r.rate); ipcaByDate[r.date] = acc; });
    }

    // Merge on portfolio dates
    return evolution.map(p => {
      const key = p.date.slice(0, 7);
      return {
        date: key,
        portfolio: portfolioByDate[key] ?? null,
        cdi: cdiByDate[key] ?? null,
        ipca: ipcaByDate[key] ?? null,
      };
    });
  })();

  return (
    <div className="space-y-6">
      {/* No-price notice */}
      {noPriceCount > 0 && (
        <div className="text-xs text-gray-400 text-right -mb-4">
          {noPriceCount} instrumento{noPriceCount > 1 ? 's' : ''} de renta fija sin precio actualizado
        </div>
      )}
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
          subtitle={kpis?.proventos_projection ? `Proyección: ${fmtBRL(kpis.proventos_projection)}` : undefined}
        />
      </div>

      {/* Chart card with view selector */}
      <div className="card">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-4">
          {/* View tabs */}
          <div className="flex rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700">
            {([
              { key: 'evolution', label: 'Evolución' },
              { key: 'by-type', label: 'Por Tipo' },
              { key: 'benchmarks', label: 'vs Benchmarks' },
            ] as const).map(tab => (
              <button
                key={tab.key}
                onClick={() => setChartView(tab.key)}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${chartView === tab.key ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'}`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-3">
            {/* Chart-specific controls */}
            {chartView === 'evolution' && (
              <div className="flex rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700">
                {['BRL', 'USD'].map(c => (
                  <button
                    key={c}
                    onClick={() => setCurrency(c as any)}
                    className={`px-3 py-1.5 text-sm font-medium transition-colors ${currency === c ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'}`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            )}
            {chartView === 'benchmarks' && (
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input type="checkbox" checked={showCdi} onChange={e => setShowCdi(e.target.checked)} className="rounded accent-emerald-500" />
                  <span className="text-sm font-medium" style={{ color: '#10b981' }}>CDI</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input type="checkbox" checked={showIpca} onChange={e => setShowIpca(e.target.checked)} className="rounded accent-amber-500" />
                  <span className="text-sm font-medium" style={{ color: '#f59e0b' }}>IPCA</span>
                </label>
              </div>
            )}

            {/* Range selector — shared */}
            <div className="flex rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700">
              {RANGE_OPTIONS.map(o => (
                <button
                  key={o.value}
                  onClick={() => setRange(o.value)}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${range === o.value ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'}`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Chart */}
        {chartView === 'evolution' && (
          <EvolutionChart data={evolution} currency={currency} height={300} />
        )}
        {chartView === 'by-type' && (
          <StackedAreaChart data={byType.data} types={byType.types} height={300} />
        )}
        {chartView === 'benchmarks' && (
          <>
            <p className="text-xs text-slate-400 dark:text-slate-500 mb-3">Base 100 desde el inicio del período seleccionado</p>
            <BenchmarkChart data={benchmarkData} showCdi={showCdi} showIpca={showIpca} height={280} />
          </>
        )}
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

        {/* Maturity profile */}
        <div className="card col-span-full">
          <h2 className="font-semibold text-gray-800 dark:text-white mb-4">Perfil de Vencimientos</h2>
          {maturities ? (
            <MaturityChart data={maturities.data} types={maturities.types} outliers={maturities.outliers} height={300} />
          ) : (
            <div className="animate-pulse bg-gray-200 dark:bg-gray-700 rounded h-48" />
          )}
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
