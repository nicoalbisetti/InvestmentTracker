import { useEffect, useState, useCallback } from 'react';
import { getMonthlyHistory, getAnnualHistory, HistoryFilters, HistoryMonthlyResponse, HistoryAnnualResponse } from '../api/history';
import { getInstruments } from '../api/instruments';
import { fmtBRL, fmtUSD, MONTH_NAMES } from '../utils/formatters';

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'renta_fija', label: 'Renta Fija' },
  { value: 'accion', label: 'Acción' },
  { value: 'fii', label: 'FII' },
  { value: 'fundo', label: 'Fondo' },
  { value: 'exterior', label: 'Exterior' },
  { value: 'cripto', label: 'Cripto' },
];

function formatValue(v: number | null, currency: string): string {
  if (v === null || v === undefined) return '—';
  if (v === 0) return '—';
  return currency === 'USD' ? fmtUSD(v) : fmtBRL(v);
}

function SkeletonTable({ cols }: { cols: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm min-w-max">
        <thead>
          <tr>
            {Array.from({ length: cols + 1 }).map((_, i) => (
              <th key={i} className="px-3 py-2">
                <div className="animate-pulse h-4 bg-gray-200 dark:bg-gray-700 rounded w-16" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 8 }).map((_, r) => (
            <tr key={r}>
              {Array.from({ length: cols + 1 }).map((_, c) => (
                <td key={c} className="px-3 py-2">
                  <div className="animate-pulse h-4 bg-gray-100 dark:bg-gray-800 rounded w-20" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function History() {
  const currentYear = new Date().getFullYear();

  // View controls
  const [view, setView] = useState<'monthly' | 'annual'>('monthly');
  const [year, setYear] = useState<number>(currentYear);
  const [currency, setCurrency] = useState<'BRL' | 'USD'>('BRL');

  // Filters
  const [custodianFilter, setCustodianFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [marketFilter, setMarketFilter] = useState('');

  // Data
  const [monthlyData, setMonthlyData] = useState<HistoryMonthlyResponse | null>(null);
  const [annualData, setAnnualData] = useState<HistoryAnnualResponse | null>(null);
  const [availableYears, setAvailableYears] = useState<number[]>([currentYear]);
  const [custodians, setCustodians] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasActiveFilters = !!(custodianFilter || typeFilter || marketFilter);

  const buildFilters = useCallback((): HistoryFilters => {
    const f: HistoryFilters = {};
    if (custodianFilter) f.custodian = custodianFilter;
    if (typeFilter) f.type = typeFilter;
    else if (marketFilter) f.market = marketFilter as 'brasil' | 'exterior';
    return f;
  }, [custodianFilter, typeFilter, marketFilter]);

  // Load custodians on mount
  useEffect(() => {
    getInstruments({ limit: 500 })
      .then((r: any) => {
        const items: any[] = r.items ?? r;
        const unique = [...new Set(items.map((i: any) => i.custodian).filter(Boolean))] as string[];
        setCustodians(unique.sort());
      })
      .catch(() => {/* custodian dropdown will remain disabled */});
  }, []);

  // Load annual data once to populate available years
  useEffect(() => {
    getAnnualHistory('BRL', {})
      .then(r => {
        if (r.years.length > 0) setAvailableYears(r.years);
      })
      .catch(() => {});
  }, []);

  const fetchData = useCallback(() => {
    const filters = buildFilters();
    setLoading(true);
    setError(null);

    if (view === 'monthly') {
      getMonthlyHistory(year, currency, filters)
        .then(setMonthlyData)
        .catch(() => setError('Error al cargar los datos. Intenta nuevamente.'))
        .finally(() => setLoading(false));
    } else {
      getAnnualHistory(currency, filters)
        .then(setAnnualData)
        .catch(() => setError('Error al cargar los datos. Intenta nuevamente.'))
        .finally(() => setLoading(false));
    }
  }, [view, year, currency, buildFilters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const clearFilters = () => {
    setCustodianFilter('');
    setTypeFilter('');
    setMarketFilter('');
  };

  const handleTypeChange = (val: string) => {
    setTypeFilter(val);
    if (val) setMarketFilter('');
  };

  const handleMarketChange = (val: string) => {
    setMarketFilter(val);
    if (val === 'exterior') setTypeFilter('');
  };

  // Determine what to render
  const data = view === 'monthly' ? monthlyData : annualData;
  const periods: (string | number)[] =
    view === 'monthly'
      ? (monthlyData?.months ?? []).map(m => MONTH_NAMES[m - 1])
      : (annualData?.years ?? []);
  const items = data?.items ?? [];
  const totals = data?.totals ?? [];

  const cellClass = 'px-3 py-2 text-right font-mono text-xs whitespace-nowrap';
  const nullCellClass = `${cellClass} text-gray-400 dark:text-gray-600`;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="card space-y-3">
        <div className="flex flex-wrap gap-3 items-center justify-between">
          {/* View toggle */}
          <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
            {(['monthly', 'annual'] as const).map(v => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  view === v
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50'
                }`}
              >
                {v === 'monthly' ? 'Mensual' : 'Anual'}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            {/* Year selector (monthly only) */}
            {view === 'monthly' && (
              <select
                className="input w-28 text-sm"
                value={year}
                onChange={e => setYear(Number(e.target.value))}
              >
                {availableYears.map(y => (
                  <option key={y} value={y}>{y}</option>
                ))}
                {!availableYears.includes(currentYear) && (
                  <option value={currentYear}>{currentYear}</option>
                )}
              </select>
            )}

            {/* Currency toggle */}
            <div className="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
              {(['BRL', 'USD'] as const).map(c => (
                <button
                  key={c}
                  onClick={() => setCurrency(c)}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    currency === c
                      ? 'bg-indigo-600 text-white'
                      : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Filters row */}
        <div className="flex flex-wrap gap-2 items-center">
          {/* Custodian */}
          <select
            className="input w-40 text-sm"
            value={custodianFilter}
            onChange={e => setCustodianFilter(e.target.value)}
            disabled={custodians.length === 0}
            title={custodians.length === 0 ? 'No disponible' : undefined}
          >
            <option value="">Todos los custodios</option>
            {custodians.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>

          {/* Type */}
          <select
            className="input w-36 text-sm"
            value={typeFilter}
            onChange={e => handleTypeChange(e.target.value)}
            disabled={!!marketFilter}
            title={marketFilter ? 'Deshabilitado cuando Mercado está activo' : undefined}
          >
            <option value="">Todos los tipos</option>
            {TYPE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          {/* Market */}
          <select
            className="input w-32 text-sm"
            value={marketFilter}
            onChange={e => handleMarketChange(e.target.value)}
            disabled={!!typeFilter}
            title={typeFilter ? 'Deshabilitado cuando Tipo está activo' : undefined}
          >
            <option value="">Todos los mercados</option>
            <option value="brasil">Brasil</option>
            <option value="exterior">Exterior</option>
          </select>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline px-2 py-1"
            >
              Limpiar filtros
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-4">
            <SkeletonTable cols={view === 'monthly' ? 12 : 10} />
          </div>
        ) : error ? (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <p className="text-red-500 text-sm">{error}</p>
            <button
              onClick={fetchData}
              className="btn-primary text-sm px-4 py-1.5"
            >
              Reintentar
            </button>
          </div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-sm">
            {hasActiveFilters
              ? 'No hay instrumentos para los filtros seleccionados'
              : 'No hay datos para el período seleccionado'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-max">
              <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="sticky left-0 z-10 bg-gray-50 dark:bg-gray-800 px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider min-w-52">
                    Instrumento
                  </th>
                  {periods.map((p, i) => (
                    <th
                      key={i}
                      className="px-3 py-2.5 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap"
                    >
                      {p}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {items.map(item => (
                  <tr key={item.instrument_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                    <td className="sticky left-0 z-10 bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/40 px-4 py-2.5 min-w-52 border-r border-gray-100 dark:border-gray-800">
                      <div className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-48">
                        {item.name}
                      </div>
                      <div className="text-xs text-gray-400 truncate">{item.custodian}</div>
                    </td>
                    {item.values.map((v, i) => (
                      <td
                        key={i}
                        className={v !== null && v !== 0 ? cellClass : nullCellClass}
                      >
                        {formatValue(v, currency)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-gray-50 dark:bg-gray-800/60 border-t-2 border-gray-300 dark:border-gray-600">
                  <td className="sticky left-0 z-10 bg-gray-50 dark:bg-gray-800/60 px-4 py-2.5 font-semibold text-gray-700 dark:text-gray-300 border-r border-gray-200 dark:border-gray-700">
                    Total
                  </td>
                  {totals.map((t, i) => (
                    <td
                      key={i}
                      className={`${cellClass} font-semibold ${
                        t !== null && t !== 0
                          ? 'text-gray-900 dark:text-gray-100'
                          : 'text-gray-400 dark:text-gray-600'
                      }`}
                    >
                      {formatValue(t, currency)}
                    </td>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
