import { useEffect, useState, useCallback } from 'react';
import { Download } from 'lucide-react';
import { getMonthlyHistory, getAnnualHistory, HistoryFilters, HistoryMonthlyResponse, HistoryAnnualResponse } from '../api/history';
import { getInstruments } from '../api/instruments';
import { fmtBRL, fmtUSD, MONTH_NAMES } from '../utils/formatters';

const TYPE_ORDER = ['accion', 'fii', 'renta_fija', 'fundo', 'previdencia', 'prestamos', 'saving', 'fgts', 'outro', 'exterior'];

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: 'renta_fija', label: 'Renta Fija' },
  { value: 'accion', label: 'Acción' },
  { value: 'fii', label: 'FII' },
  { value: 'fundo', label: 'Fondo' },
  { value: 'exterior', label: 'Exterior' },
  { value: 'cripto', label: 'Cripto' },
];

type HistoryItem = {
  instrument_id: number;
  name: string;
  custodian: string;
  type: string;
  location: string;
  values: (number | null)[];
};

function formatValue(v: number | null, currency: string): string {
  if (v === null || v === undefined || v === 0) return '—';
  return currency === 'USD' ? fmtUSD(v) : fmtBRL(v);
}

function sortItems(items: HistoryItem[]): HistoryItem[] {
  return [...items].sort((a, b) => {
    const aLoc = a.location === 'exterior' ? 1 : 0;
    const bLoc = b.location === 'exterior' ? 1 : 0;
    if (aLoc !== bLoc) return aLoc - bLoc;
    const aType = TYPE_ORDER.indexOf(a.type) === -1 ? 99 : TYPE_ORDER.indexOf(a.type);
    const bType = TYPE_ORDER.indexOf(b.type) === -1 ? 99 : TYPE_ORDER.indexOf(b.type);
    if (aType !== bType) return aType - bType;
    return a.name.localeCompare(b.name);
  });
}

function filterItems(items: HistoryItem[]): HistoryItem[] {
  return items.filter(item => item.values.some(v => v !== null && v !== 0));
}

// Returns true if value at index i increased vs previous period
// For monthly: previous = index i-1; for annual: years are desc so previous year = index i+1
function isIncrease(values: (number | null)[], i: number, view: 'monthly' | 'annual'): boolean {
  const curr = values[i];
  if (curr === null || curr === 0) return false;
  const prevIdx = view === 'monthly' ? i - 1 : i + 1;
  if (prevIdx < 0 || prevIdx >= values.length) return false;
  const prev = values[prevIdx];
  if (prev === null || prev === 0) return false;
  return curr > prev;
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

  const [view, setView] = useState<'monthly' | 'annual'>('monthly');
  const [year, setYear] = useState<number>(currentYear);
  const [currency, setCurrency] = useState<'BRL' | 'USD'>('BRL');

  const [custodianFilter, setCustodianFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [marketFilter, setMarketFilter] = useState('');
  const [instrumentFilter, setInstrumentFilter] = useState('');

  const [monthlyData, setMonthlyData] = useState<HistoryMonthlyResponse | null>(null);
  const [annualData, setAnnualData] = useState<HistoryAnnualResponse | null>(null);
  const [availableYears, setAvailableYears] = useState<number[]>([currentYear]);
  const [custodians, setCustodians] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasActiveFilters = !!(custodianFilter || typeFilter || marketFilter || instrumentFilter);

  const buildFilters = useCallback((): HistoryFilters => {
    const f: HistoryFilters = {};
    if (custodianFilter) f.custodian = custodianFilter;
    if (typeFilter) f.type = typeFilter;
    else if (marketFilter) f.market = marketFilter as 'brasil' | 'exterior';
    return f;
  }, [custodianFilter, typeFilter, marketFilter]);

  useEffect(() => {
    getInstruments({ limit: 500 })
      .then((r: any) => {
        const items: any[] = r.items ?? r;
        const unique = [...new Set(items.map((i: any) => i.custodian).filter(Boolean))] as string[];
        setCustodians(unique.sort());
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    getAnnualHistory('BRL', {})
      .then(r => { if (r.years.length > 0) setAvailableYears(r.years); })
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

  useEffect(() => { fetchData(); }, [fetchData]);

  const clearFilters = () => {
    setCustodianFilter('');
    setTypeFilter('');
    setMarketFilter('');
    setInstrumentFilter('');
  };

  const handleTypeChange = (val: string) => {
    setTypeFilter(val);
    if (val) setMarketFilter('');
  };

  const handleMarketChange = (val: string) => {
    setMarketFilter(val);
    if (val === 'exterior') setTypeFilter('');
  };

  const rawData = view === 'monthly' ? monthlyData : annualData;
  const periods: (string | number)[] =
    view === 'monthly'
      ? (monthlyData?.months ?? []).map(m => MONTH_NAMES[m - 1])
      : (annualData?.years ?? []);
  const totals = rawData?.totals ?? [];
  const items: HistoryItem[] = sortItems(filterItems((rawData?.items ?? []) as HistoryItem[])).filter(
    item => !instrumentFilter || item.name.toLowerCase().includes(instrumentFilter.toLowerCase())
  );

  const stickyCol = 'sticky left-0 z-10';
  const headerBg = 'bg-gray-50 dark:bg-gray-800';
  const cellClass = 'px-3 py-1.5 text-right font-mono text-xs whitespace-nowrap';

  const exportHistoryCSV = () => {
    const header = ['Instrumento', ...periods.map(p => String(p))];
    const totalRow = ['Total', ...totals.map(v => (v === null || v === 0) ? '' : String(v))];
    const rows = items.map(item => [
      item.name,
      ...item.values.map(v => (v === null || v === 0) ? '' : String(v)),
    ]);

    const csvContent = [header, totalRow, ...rows]
      .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      .join('\n');

    const filename = view === 'monthly'
      ? `historico_mensual_${year}_${currency}.csv`
      : `historico_anual_${currency}.csv`;

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 100);
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="card space-y-3">
        <div className="flex flex-wrap gap-3 items-center justify-between">
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
            {view === 'monthly' && (
              <select
                className="input w-28 text-sm"
                value={year}
                onChange={e => setYear(Number(e.target.value))}
              >
                {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
                {!availableYears.includes(currentYear) && (
                  <option value={currentYear}>{currentYear}</option>
                )}
              </select>
            )}
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
            <button
              className="btn-secondary text-sm p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={exportHistoryCSV}
              title="Exportar CSV"
              disabled={items.length === 0}
            >
              <Download size={18} />
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          <input
            type="text"
            className="input w-44 text-sm"
            placeholder="Buscar instrumento..."
            value={instrumentFilter}
            onChange={e => setInstrumentFilter(e.target.value)}
          />

          <select
            className="input w-40 text-sm"
            value={custodianFilter}
            onChange={e => setCustodianFilter(e.target.value)}
            disabled={custodians.length === 0}
          >
            <option value="">Todos los custodios</option>
            {custodians.map(c => <option key={c} value={c}>{c}</option>)}
          </select>

          <select
            className="input w-36 text-sm"
            value={typeFilter}
            onChange={e => handleTypeChange(e.target.value)}
            disabled={!!marketFilter}
          >
            <option value="">Todos los tipos</option>
            {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>

          <select
            className="input w-32 text-sm"
            value={marketFilter}
            onChange={e => handleMarketChange(e.target.value)}
            disabled={!!typeFilter}
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
            <button onClick={fetchData} className="btn-primary text-sm px-4 py-1.5">
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
              <thead className={`${headerBg} border-b border-gray-200 dark:border-gray-700`}>
                {/* Period headers */}
                <tr>
                  <th className={`${stickyCol} ${headerBg} px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider min-w-52`}>
                    Instrumento
                  </th>
                  {periods.map((p, i) => (
                    <th key={i} className="px-3 py-2.5 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      {p}
                    </th>
                  ))}
                </tr>
                {/* Totals row — sticky at top */}
                <tr className="border-t border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-700/60">
                  <td className={`${stickyCol} bg-gray-100 dark:bg-gray-700/60 px-4 py-1.5 font-semibold text-gray-700 dark:text-gray-300 text-xs border-r border-gray-200 dark:border-gray-700`}>
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
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {items.map(item => (
                  <tr key={item.instrument_id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                    <td className={`${stickyCol} bg-white dark:bg-gray-900 hover:bg-gray-50 dark:hover:bg-gray-800/40 px-4 py-1.5 min-w-52 border-r border-gray-100 dark:border-gray-800`}>
                      <div className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-48 text-xs">
                        {item.name}
                      </div>
                    </td>
                    {item.values.map((v, i) => {
                      const up = v !== null && v !== 0 && isIncrease(item.values, i, view);
                      const hasValue = v !== null && v !== 0;
                      return (
                        <td
                          key={i}
                          className={`${cellClass} ${
                            !hasValue
                              ? 'text-gray-400 dark:text-gray-600'
                              : up
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : 'text-gray-900 dark:text-gray-100'
                          }`}
                        >
                          {formatValue(v, currency)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
