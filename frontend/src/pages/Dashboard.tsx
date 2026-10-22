import { useEffect, useState } from 'react';
import { getDashboardKPIs, getEvolution, getDistribution, getTopBottom, getBenchmarks } from '../api/dashboard';
import client from '../api/client';
import TickerBand from '../components/TickerBand';
import EvolutionChart from '../components/charts/EvolutionChart';
import BenchmarkChart from '../components/charts/BenchmarkChart';
import StackedAreaChart from '../components/charts/StackedAreaChart';
import DonutChart from '../components/charts/DonutChart';
import MaturityChart from '../components/charts/MaturityChart';
import { fmtBRL, fmtUSD, fmtPct, fmtDate, INSTRUMENT_TYPE_COLORS, CUSTODIAN_COLORS, LOCATION_COLORS } from '../utils/formatters';
import { TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

const RANGE_OPTIONS = [
  { label: 'Año', value: 'ytd' },
  { label: '1A', value: '1y' },
  { label: '3A', value: '3y' },
  { label: '5A', value: '5y' },
  { label: 'Todo', value: 'all' },
];

const FONT_SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const FONT_MONO = "'DM Mono', 'Fira Mono', monospace";

function KpiHero({ loading, totalBrl, totalUsd }: { loading: boolean; totalBrl: any; totalUsd: any }) {
  if (loading) {
    return (
      <div className="rounded-2xl p-5 space-y-3" style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)' }}>
        <div className="animate-pulse bg-white/10 h-3 w-1/3 rounded-lg" />
        <div className="animate-pulse bg-white/10 h-9 w-2/3 rounded-lg" />
        <div className="animate-pulse bg-white/10 h-3 w-1/4 rounded-lg" />
      </div>
    );
  }
  return (
    <div
      className="rounded-2xl p-5 relative overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)', fontFamily: FONT_SANS }}
    >
      <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full border border-indigo-500/20" />
      <div className="absolute -right-2 -top-2 w-24 h-24 rounded-full border border-indigo-400/15" />
      <p className="text-xs font-semibold uppercase tracking-widest text-indigo-300 mb-2">Total Cartera</p>
      <p className="font-bold text-white leading-none" style={{ fontSize: '1.875rem', fontFamily: FONT_MONO }}>
        {fmtBRL(totalBrl)}
      </p>
      {totalUsd && (
        <p className="text-sm text-indigo-300 mt-2" style={{ fontFamily: FONT_MONO }}>
          ≈ {fmtUSD(totalUsd)}
        </p>
      )}
    </div>
  );
}

function KpiCard({
  loading,
  title,
  value,
  subtitle,
  trend,
  tinted,
}: {
  loading?: boolean;
  title: string;
  value: any;
  subtitle?: any;
  trend?: { value: number; label?: string };
  tinted?: 'positive' | 'negative' | null;
}) {
  if (loading) {
    return (
      <div className="rounded-2xl p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
        <div className="animate-pulse bg-slate-200 dark:bg-slate-700 h-3 w-1/2 rounded-lg" />
        <div className="animate-pulse bg-slate-200 dark:bg-slate-700 h-8 w-3/4 rounded-lg" />
        <div className="animate-pulse bg-slate-200 dark:bg-slate-700 h-3 w-1/3 rounded-lg" />
      </div>
    );
  }

  const bgClass =
    tinted === 'positive'
      ? 'bg-emerald-50/60 dark:bg-emerald-950/25 border-emerald-200 dark:border-emerald-900'
      : tinted === 'negative'
      ? 'bg-rose-50/60 dark:bg-rose-950/25 border-rose-200 dark:border-rose-900'
      : 'bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800';

  const isPositive = trend != null && trend.value >= 0;

  return (
    <div className={`rounded-2xl p-5 border ${bgClass}`} style={{ fontFamily: FONT_SANS }}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">{title}</p>
      <p className="font-bold text-slate-900 dark:text-white mt-2 leading-none" style={{ fontSize: '1.5rem', fontFamily: FONT_MONO }}>
        {value}
      </p>
      {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5">{subtitle}</p>}
      {trend != null && (
        <div className={`flex items-center gap-1 mt-2 text-sm font-semibold ${isPositive ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'}`}>
          {isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          <span style={{ fontFamily: FONT_MONO }}>{Math.abs(trend.value * 100).toFixed(2)}%</span>
          {trend.label && <span className="text-slate-400 dark:text-slate-500 font-normal ml-0.5">{trend.label}</span>}
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const [kpis, setKpis] = useState<any>(null);
  const [evolution, setEvolution] = useState<any[]>([]);
  const [distribution, setDistribution] = useState<any>({ by_type: [], by_custodian: [], by_location: [] });
  const [topBottom, setTopBottom] = useState<any>(null);
  const [range, setRange] = useState('all');
  const [currency, setCurrency] = useState<'BRL' | 'USD'>('BRL');
  const [loading, setLoading] = useState(true);
  const [noPriceCount, setNoPriceCount] = useState<number>(0);
  const [benchmarks, setBenchmarks] = useState<{ cdi: any[]; ipca: any[]; usd: any[] } | null>(null);
  const [showCdi, setShowCdi] = useState(true);
  const [showIpca, setShowIpca] = useState(true);
  const [showUsd, setShowUsd] = useState(true);
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
    getBenchmarks(range).then(setBenchmarks).catch(() => setBenchmarks({ cdi: [], ipca: [], usd: [] }));
    client.get('/api/dashboard/evolution-by-type', { params: { range } }).then(r => setByType(r.data)).catch(() => {});
  }, [range, currency]);

  const benchmarkData = (() => {
    if (!evolution.length) return [];
    const firstValue = evolution[0]?.value;
    if (!firstValue) return [];
    const portfolioByDate: Record<string, number> = {};
    evolution.forEach(p => { portfolioByDate[p.date.slice(0, 7)] = 100 * p.value / firstValue; });
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
    const usdByDate: Record<string, number> = {};
    if (benchmarks?.usd?.length) {
      let acc = 100;
      benchmarks.usd.forEach(r => { acc *= (1 + r.rate); usdByDate[r.date] = acc; });
    }
    return evolution.map(p => {
      const key = p.date.slice(0, 7);
      return {
        date: key,
        portfolio: portfolioByDate[key] ?? null,
        cdi: cdiByDate[key] ?? null,
        ipca: ipcaByDate[key] ?? null,
        usd: usdByDate[key] ?? null,
      };
    });
  })();

  const monthTint = kpis == null ? null : kpis.monthly_change_abs >= 0 ? 'positive' : 'negative';

  const CHART_TABS = [
    { key: 'evolution', label: 'Evolución' },
    { key: 'by-type', label: 'Por Tipo' },
    { key: 'benchmarks', label: 'vs Benchmarks' },
  ] as const;

  return (
    <div style={{ fontFamily: FONT_SANS }}>
      <div className="-mx-6 -mt-6 mb-6">
        <TickerBand />
      </div>

      <div className="space-y-6">

        {noPriceCount > 0 && (
          <div className="flex items-center gap-2 text-xs font-medium text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl px-4 py-2.5 w-fit">
            <AlertTriangle size={13} />
            <span>{noPriceCount} instrumento{noPriceCount > 1 ? 's' : ''} de renta fija sin precio actualizado</span>
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiHero loading={loading} totalBrl={kpis?.total_brl} totalUsd={kpis?.total_usd} />
          <KpiCard
            loading={loading}
            title="Variación del Mes"
            value={fmtBRL(kpis?.monthly_change_abs)}
            trend={kpis?.monthly_change_pct != null ? { value: kpis.monthly_change_pct, label: 'vs mes anterior' } : undefined}
            tinted={monthTint}
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

        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-end gap-0 border-b border-slate-200 dark:border-slate-700">
              {CHART_TABS.map(tab => (
                <button
                  key={tab.key}
                  onClick={() => setChartView(tab.key)}
                  className={`px-4 pb-2.5 text-sm font-semibold transition-all relative ${
                    chartView === tab.key
                      ? 'text-indigo-600 dark:text-indigo-400'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                  }`}
                >
                  {tab.label}
                  {chartView === tab.key && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600 dark:bg-indigo-400 rounded-full" />
                  )}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {chartView === 'evolution' && (
                <div className="flex gap-1">
                  {['BRL', 'USD'].map(c => (
                    <button
                      key={c}
                      onClick={() => setCurrency(c as any)}
                      className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                        currency === c
                          ? 'bg-indigo-600 text-white'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              )}
              {chartView === 'benchmarks' && (
                <div className="flex gap-1">
                  <button
                    onClick={() => setShowCdi(v => !v)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                      showCdi ? 'bg-emerald-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                    }`}
                  >
                    CDI
                  </button>
                  <button
                    onClick={() => setShowIpca(v => !v)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                      showIpca ? 'bg-amber-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                    }`}
                  >
                    IPCA
                  </button>
                  <button
                    onClick={() => setShowUsd(v => !v)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                      showUsd ? 'bg-blue-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-400'
                    }`}
                  >
                    Dólar
                  </button>
                </div>
              )}

              <div className="flex gap-1">
                {RANGE_OPTIONS.map(o => (
                  <button
                    key={o.value}
                    onClick={() => setRange(o.value)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-colors ${
                      range === o.value
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {chartView === 'evolution' && <EvolutionChart data={evolution} currency={currency} height={300} />}
          {chartView === 'by-type' && <StackedAreaChart data={byType.data} types={byType.types} height={300} />}
          {chartView === 'benchmarks' && (
            <>
              <p className="text-xs text-slate-400 dark:text-slate-500 mb-3">Base 100 desde el inicio del período seleccionado</p>
              <BenchmarkChart data={benchmarkData} showCdi={showCdi} showIpca={showIpca} showUsd={showUsd} height={280} />
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <div className="card">
            <h2 className="font-semibold text-slate-800 dark:text-white mb-3 text-sm uppercase tracking-wide">Por Tipo</h2>
            <DonutChart data={distribution.by_type} colors={INSTRUMENT_TYPE_COLORS} height={240} />
          </div>

          <div className="card">
            <h2 className="font-semibold text-slate-800 dark:text-white mb-3 text-sm uppercase tracking-wide">Por Custodio</h2>
            <DonutChart data={distribution.by_custodian} colors={CUSTODIAN_COLORS} height={240} />
          </div>

          <div className="card">
            <h2 className="font-semibold text-slate-800 dark:text-white mb-3 text-sm uppercase tracking-wide">Por Localización</h2>
            <DonutChart data={distribution.by_location} colors={LOCATION_COLORS} height={240} />
          </div>

          <div className="card">
            <h2 className="font-semibold text-slate-800 dark:text-white mb-3 text-sm uppercase tracking-wide">Top / Bottom del Mes</h2>
            {topBottom ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2 tracking-widest">TOP 5</p>
                  <ul className="space-y-1.5">
                    {topBottom.top5.map((inst: any) => (
                      <li key={inst.id} className="flex items-center justify-between text-sm">
                        <span className="text-slate-700 dark:text-slate-300 truncate max-w-[120px]" title={inst.name}>{inst.name}</span>
                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold ml-2 shrink-0" style={{ fontFamily: FONT_MONO, fontSize: '0.8rem' }}>
                          {fmtPct(inst.return_1m)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="border-t border-slate-100 dark:border-slate-800 pt-3">
                  <p className="text-xs font-bold text-rose-500 mb-2 tracking-widest">BOTTOM 5</p>
                  <ul className="space-y-1.5">
                    {topBottom.bottom5.map((inst: any) => (
                      <li key={inst.id} className="flex items-center justify-between text-sm">
                        <span className="text-slate-700 dark:text-slate-300 truncate max-w-[120px]" title={inst.name}>{inst.name}</span>
                        <span className="text-rose-500 dark:text-rose-400 font-semibold ml-2 shrink-0" style={{ fontFamily: FONT_MONO, fontSize: '0.8rem' }}>
                          {fmtPct(inst.return_1m)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => <div key={i} className="animate-pulse bg-slate-200 dark:bg-slate-700 h-6 rounded-lg" />)}
              </div>
            )}
          </div>

          <div className="card col-span-full">
            <h2 className="font-semibold text-slate-800 dark:text-white mb-4 text-sm uppercase tracking-wide">Perfil de Vencimientos</h2>
            {maturities ? (
              <MaturityChart data={maturities.data} types={maturities.types} outliers={maturities.outliers} height={300} />
            ) : (
              <div className="animate-pulse bg-slate-200 dark:bg-slate-700 rounded-xl h-48" />
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
