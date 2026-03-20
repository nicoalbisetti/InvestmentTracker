import { useEffect, useState } from 'react';
import { getPositions, exportPositions, PositionFilters } from '../api/positions';
import { fmtBRL, fmtPct, fmtDate, INSTRUMENT_TYPE_LABELS } from '../utils/formatters';
import { SkeletonTable } from '../components/ui/SkeletonLoader';

const TYPE_OPTIONS = Object.entries(INSTRUMENT_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }));
const STATUS_OPTIONS = [
  { value: 'activo', label: 'Activo' },
  { value: 'cerrado', label: 'Cerrado' },
];

function SortIcon({ active, order }: { active: boolean; order: string }) {
  if (!active) return <span className="text-gray-400 ml-1">↕</span>;
  return <span className="text-blue-500 ml-1">{order === 'asc' ? '↑' : '↓'}</span>;
}

function colorReturn(val: number | null) {
  if (val == null) return 'text-gray-400';
  return val >= 0 ? 'positive' : 'negative';
}

export default function Positions() {
  const [data, setData] = useState<any>({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<PositionFilters>({ status: 'activo', sort: 'current_balance_brl', order: 'desc', page: 1, limit: 50 });
  const [search, setSearch] = useState('');

  const load = (f: PositionFilters) => {
    setLoading(true);
    getPositions(f).then(setData).finally(() => setLoading(false));
  };

  useEffect(() => {
    const timer = setTimeout(() => load({ ...filters, search: search || undefined }), 300);
    return () => clearTimeout(timer);
  }, [filters, search]);

  const setSort = (col: string) => {
    setFilters(f => ({
      ...f,
      sort: col,
      order: f.sort === col && f.order === 'desc' ? 'asc' : 'desc',
      page: 1,
    }));
  };

  const TH = ({ col, label }: { col: string; label: string }) => (
    <th
      onClick={() => setSort(col)}
      className="px-3 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 whitespace-nowrap select-none"
    >
      {label}
      <SortIcon active={filters.sort === col} order={filters.order || 'desc'} />
    </th>
  );

  const today = new Date();
  const in90 = new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="card flex flex-wrap gap-3 items-center">
        <input
          className="input w-48"
          placeholder="Buscar instrumento..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className="input w-40"
          value={filters.custodian || ''}
          onChange={e => setFilters(f => ({ ...f, custodian: e.target.value || undefined, page: 1 }))}
        >
          <option value="">Todos los custodios</option>
          {['HSBC', 'Bradesco', 'XP', 'Santander', 'Inter', 'CITI'].map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          className="input w-40"
          value={filters.type || ''}
          onChange={e => setFilters(f => ({ ...f, type: e.target.value || undefined, page: 1 }))}
        >
          <option value="">Todos los tipos</option>
          {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select
          className="input w-32"
          value={filters.status || 'activo'}
          onChange={e => setFilters(f => ({ ...f, status: e.target.value || undefined, page: 1 }))}
        >
          {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm text-gray-500">{data.total} instrumentos</span>
          <button
            className="btn-secondary text-sm"
            onClick={() => exportPositions({ ...filters, search: search || undefined })}
          >
            Exportar CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-5"><SkeletonTable rows={10} /></div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                  <tr>
                    <TH col="name" label="Instrumento" />
                    <TH col="custodian" label="Custodio" />
                    <TH col="type" label="Tipo" />
                    <TH col="current_balance_brl" label="Saldo BRL" />
                    <TH col="portfolio_pct" label="% Portfolio" />
                    <TH col="return_1m" label="1M%" />
                    <TH col="return_3m" label="3M%" />
                    <TH col="return_6m" label="6M%" />
                    <TH col="return_12m" label="12M%" />
                    <TH col="rank_1m" label="Rank" />
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Liquidez</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Vencimiento</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.items.map((row: any) => {
                    const nearMaturity = row.maturity_date && row.maturity_date <= in90;
                    return (
                      <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                        <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-white max-w-[180px] truncate" title={row.name}>{row.name}</td>
                        <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400">{row.custodian}</td>
                        <td className="px-3 py-2.5">
                          <span className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded-full">
                            {INSTRUMENT_TYPE_LABELS[row.type] || row.type}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 font-mono text-gray-800 dark:text-gray-200">{fmtBRL(row.balance_brl)}</td>
                        <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400">{fmtPct(row.portfolio_pct)}</td>
                        <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_1m)}`}>{fmtPct(row.return_1m)}</td>
                        <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_3m)}`}>{fmtPct(row.return_3m)}</td>
                        <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_6m)}`}>{fmtPct(row.return_6m)}</td>
                        <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_12m)}`}>{fmtPct(row.return_12m)}</td>
                        <td className="px-3 py-2.5 text-center text-gray-500">{row.rank_1m ?? '—'}</td>
                        <td className="px-3 py-2.5 text-gray-500">{row.liquidity || '—'}</td>
                        <td className={`px-3 py-2.5 ${nearMaturity ? 'text-amber-500 font-semibold' : 'text-gray-500'}`}>
                          {fmtDate(row.maturity_date)}
                          {nearMaturity && <span className="ml-1 text-xs">⚠️</span>}
                        </td>
                      </tr>
                    );
                  })}
                  {data.items.length === 0 && (
                    <tr><td colSpan={12} className="px-3 py-8 text-center text-gray-400">No hay instrumentos</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {/* Pagination */}
            {data.pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
                <p className="text-sm text-gray-500">
                  Página {filters.page} de {data.pages} ({data.total} registros)
                </p>
                <div className="flex gap-2">
                  <button
                    className="btn-secondary text-sm py-1"
                    disabled={(filters.page || 1) <= 1}
                    onClick={() => setFilters(f => ({ ...f, page: (f.page || 1) - 1 }))}
                  >
                    ← Anterior
                  </button>
                  <button
                    className="btn-secondary text-sm py-1"
                    disabled={(filters.page || 1) >= data.pages}
                    onClick={() => setFilters(f => ({ ...f, page: (f.page || 1) + 1 }))}
                  >
                    Siguiente →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
