import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { CopyPlus, Activity, DollarSign, Loader2, Upload, Globe, Download, ArrowDownCircle } from 'lucide-react';
import { getPositions, exportPositions, getCustodians, PositionFilters } from '../api/positions';
import { fmtBRL, fmtPct, fmtDate, fmtUSD, INSTRUMENT_TYPE_LABELS } from '../utils/formatters';
import { SkeletonTable } from '../components/ui/SkeletonLoader';
import { getLastFixedIncomeDate } from '../api/importFixedIncome';
import { rescateTotal } from '../api/instruments';
import Modal from '../components/ui/Modal';
import client from '../api/client';

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

const MONTH_NAMES_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];

function fmtLastDate(d: string | null) {
  if (!d) return null;
  const [year, month] = d.split('-');
  return `${MONTH_NAMES_ES[parseInt(month) - 1]} ${year}`;
}

export default function Positions() {
  const navigate = useNavigate();
  const [data, setData] = useState<any>({ items: [], total: 0, pages: 1, total_brl: null, total_usd: null });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<PositionFilters>({ status: 'activo', sort: 'default', order: 'asc', page: 1, limit: 50, with_position: true });
  const [search, setSearch] = useState('');
  const [lastFixedIncomeDate, setLastFixedIncomeDate] = useState<string | null>(null);
  const [updatingPrices, setUpdatingPrices] = useState(false);
  const [priceResult, setPriceResult] = useState<any>(null);
  const [updatingUsd, setUpdatingUsd] = useState(false);
  const [usdResult, setUsdResult] = useState<any>(null);
  const [copyingPrev, setCopyingPrev] = useState(false);
  const currentMonth = new Date().toISOString().slice(0, 7);
  const [priceMonth, setPriceMonth] = useState(currentMonth);
  const isHistorical = priceMonth !== currentMonth;
  const [editing, setEditing] = useState<{ mpId: number; instrumentId: number; field: 'balance_brl' | 'balance_usd' | 'quantity'; value: string } | null>(null);
  const [showReturns, setShowReturns] = useState(false);
  const [custodianOptions, setCustodianOptions] = useState<string[]>([]);
  const [rescateTarget, setRescateTarget] = useState<{
    id: number;
    name: string;
    custodian: string;
    balance_brl: number | null;
    balance_usd: number | null;
  } | null>(null);
  const [rescateDate, setRescateDate] = useState<string>('');
  const [rescateLoading, setRescateLoading] = useState(false);
  const [rescateError, setRescateError] = useState<string | null>(null);

  useEffect(() => {
    getLastFixedIncomeDate().then(r => setLastFixedIncomeDate(r.date)).catch(() => {});
    getCustodians().then(setCustodianOptions).catch(() => {});
  }, []);

  const load = (f: PositionFilters) => {
    setLoading(true);
    getPositions(f).then(setData).finally(() => setLoading(false));
  };

  useEffect(() => {
    const month = priceMonth !== currentMonth ? priceMonth : undefined;
    // In historical mode, don't filter by status — show all instruments that had positions then
    const effectiveFilters = month ? { ...filters, status: undefined } : filters;
    const timer = setTimeout(() => load({ ...effectiveFilters, search: search || undefined, month }), 300);
    return () => clearTimeout(timer);
  }, [filters, search, priceMonth]);

  const ensureMonthPosition = async (instrumentId: number, month: string): Promise<number> => {
    const r = await client.post('/api/positions/ensure-month', { instrument_id: instrumentId, month });
    return r.data.mp_id;
  };

  const saveBalance = async (mpId: number, field: 'balance_brl' | 'balance_usd' | 'quantity', value: string) => {
    const num = parseFloat(value.replace(',', '.'));
    if (isNaN(num)) { setEditing(null); return; }
    await client.patch(`/api/positions/${mpId}/balance`, { [field]: num });
    setEditing(null);
    const month = priceMonth !== currentMonth ? priceMonth : undefined;
    load({ ...filters, search: search || undefined, month });
  };

  const setSort = (col: string) => {
    setFilters(f => ({
      ...f,
      sort: col,
      order: f.sort === col && f.order === 'desc' ? 'asc' : 'desc',
      page: 1,
    }));
  };

  const handleRescateTotal = async () => {
    if (!rescateTarget || !rescateDate) return;
    setRescateLoading(true);
    setRescateError(null);
    try {
      await rescateTotal(rescateTarget.id, rescateDate);
      setRescateTarget(null);
      const month = priceMonth !== currentMonth ? priceMonth : undefined;
      load({ ...filters, search: search || undefined, month });
    } catch (err: any) {
      setRescateError(err.message || 'Error al procesar el rescate.');
    } finally {
      setRescateLoading(false);
    }
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
          {custodianOptions.map(c => (
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
          className="input w-36"
          value={filters.location || ''}
          onChange={e => setFilters(f => ({ ...f, location: e.target.value || undefined, page: 1 }))}
        >
          <option value="">Todas las ubicaciones</option>
          <option value="brasil">Brasil</option>
          <option value="exterior">Exterior</option>
        </select>
        <select
          className="input w-32"
          value={isHistorical ? '' : (filters.status || 'activo')}
          disabled={isHistorical}
          onChange={e => setFilters(f => ({ ...f, status: e.target.value || undefined, page: 1 }))}
        >
          {!isHistorical && STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          {isHistorical && <option value="">Todos los estados</option>}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer select-none">
          <input
            type="checkbox"
            className="w-4 h-4 accent-blue-600"
            checked={filters.with_position ?? true}
            onChange={e => setFilters(f => ({ ...f, with_position: e.target.checked, page: 1 }))}
          />
          Con posición
        </label>
        <label className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer select-none">
          <input
            type="checkbox"
            className="w-4 h-4 accent-blue-600"
            checked={showReturns}
            onChange={e => setShowReturns(e.target.checked)}
          />
          Rendimientos
        </label>
        <div className="ml-auto flex items-center gap-2 flex-wrap">
          {lastFixedIncomeDate && (
            <span className="text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-2.5 py-1 rounded-full border border-blue-200 dark:border-blue-800">
              Último extrato: {fmtLastDate(lastFixedIncomeDate)}
            </span>
          )}
          <span className="text-sm text-gray-500">{data.total} instrumentos</span>
          <div className="flex items-center gap-1">
            {isHistorical && (
              <span className="text-xs bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 px-2 py-1 rounded-full border border-amber-200 dark:border-amber-700 whitespace-nowrap">
                Vista histórica
              </span>
            )}
            <input
              type="month"
              className={`input text-sm py-1 ${isHistorical ? 'border-amber-400 dark:border-amber-600' : ''}`}
              value={priceMonth}
              onChange={e => setPriceMonth(e.target.value)}
            />
            <span title="Copiar instrumentos activos del mes anterior">
              <button
                className="btn-secondary p-2 disabled:opacity-50 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                disabled={copyingPrev}
                onClick={async () => {
                  setCopyingPrev(true);
                  try {
                    const r = await client.post('/api/positions/copy-previous-month', { target_month: priceMonth });
                    const month = priceMonth !== currentMonth ? priceMonth : undefined;
                    load({ ...filters, search: search || undefined, month });
                    alert(`Se copiaron ${r.data.copied} posiciones faltantes del mes anterior.`);
                  } catch (e) {
                    alert('Error copiando posiciones');
                  } finally {
                    setCopyingPrev(false);
                  }
                }}
              >
                {copyingPrev ? <Loader2 size={18} className="animate-spin" /> : <CopyPlus size={18} />}
              </button>
            </span>
            <span title="Actualizar precios de Renta Variable">
              <button
                className="btn-secondary p-2 disabled:opacity-50 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                disabled={updatingPrices}
                onClick={async () => {
                  setUpdatingPrices(true);
                  setPriceResult(null);
                  try {
                    const r = await client.post('/api/positions/update-equities-prices', null, { params: { month: priceMonth } });
                    setPriceResult(r.data);
                    load({ ...filters, search: search || undefined });
                  } finally {
                    setUpdatingPrices(false);
                  }
                }}
              >
                {updatingPrices ? <Loader2 size={18} className="animate-spin" /> : <Activity size={18} />}
              </button>
            </span>
            <span title={isHistorical ? 'Solo disponible para el mes actual' : 'Actualizar cotización USD/BRL'}>
              <button
                className="btn-secondary p-2 disabled:opacity-50 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                disabled={updatingUsd || isHistorical}
                onClick={async () => {
                  setUpdatingUsd(true);
                  setUsdResult(null);
                  try {
                    const r = await client.post('/api/positions/update-usd-rate', null, { params: { month: priceMonth } });
                    setUsdResult(r.data);
                  } finally {
                    setUpdatingUsd(false);
                  }
                }}
              >
                {updatingUsd ? <Loader2 size={18} className="animate-spin" /> : <DollarSign size={18} />}
              </button>
            </span>
          </div>
          <button
            className="btn-secondary text-sm p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            onClick={() => navigate('/import/fixed-income')}
            title="Importar Extracto B3"
          >
            <Upload size={18} />
          </button>
          <button
            className="btn-secondary text-sm p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            onClick={() => navigate('/import/international')}
            title="Importar Internacional"
          >
            <Globe size={18} />
          </button>
          <button
            className="btn-secondary text-sm p-2 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            onClick={() => exportPositions({ ...filters, search: search || undefined })}
            title="Exportar CSV"
          >
            <Download size={18} />
          </button>
        </div>
      </div>

      {/* USD rate update result */}
      {usdResult && (
        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-sm">
              {usdResult.updated ? (
                <>
                  <span className="font-semibold text-slate-700 dark:text-slate-200">Dólar actualizado</span>
                  <span className="text-slate-500">{usdResult.month}</span>
                  {usdResult.old_rate && <span className="text-slate-400">R$ {usdResult.old_rate.toFixed(4)} →</span>}
                  <span className="font-semibold text-emerald-600">R$ {usdResult.new_rate.toFixed(4)}</span>
                </>
              ) : (
                <span className="text-rose-500">{usdResult.error}</span>
              )}
            </div>
            <button className="text-slate-400 hover:text-slate-600 text-xs" onClick={() => setUsdResult(null)}>✕</button>
          </div>
        </div>
      )}

      {/* Price update result */}
      {priceResult && (
        <div className="card space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-sm">
              <span className="font-semibold text-slate-700 dark:text-slate-200">Precios B3 actualizados</span>
              <span className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 px-2 py-0.5 rounded-full text-xs font-medium">{priceResult.updated} actualizados</span>
              {priceResult.skipped > 0 && <span className="bg-slate-100 text-slate-500 dark:bg-slate-700 px-2 py-0.5 rounded-full text-xs">{priceResult.skipped} sin precio</span>}
            </div>
            <button className="text-slate-400 hover:text-slate-600 text-xs" onClick={() => setPriceResult(null)}>✕</button>
          </div>
          {priceResult.prices?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-400 uppercase">
                    <th className="text-left py-1 pr-4">Ticker</th>
                    <th className="text-right pr-4">Cantidad</th>
                    <th className="text-right pr-4">Precio ant.</th>
                    <th className="text-right pr-4">Precio actual</th>
                    <th className="text-right pr-4">Variación</th>
                    <th className="text-right pr-4">Saldo anterior</th>
                    <th className="text-right">Saldo nuevo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {priceResult.prices.map((p: any) => (
                    <tr key={p.ticker}>
                      <td className="py-1.5 pr-4 font-mono font-semibold">{p.ticker}</td>
                      <td className="py-1.5 pr-4 text-right text-slate-500">{p.quantity?.toLocaleString('pt-BR')}</td>
                      <td className="py-1.5 pr-4 text-right text-slate-500">{p.ref_price != null ? `R$ ${p.ref_price.toFixed(2)}` : '—'}</td>
                      <td className="py-1.5 pr-4 text-right font-medium">R$ {p.current_price.toFixed(2)}</td>
                      <td className={`py-1.5 pr-4 text-right font-semibold ${p.change_pct == null ? 'text-slate-400' : p.change_pct >= 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                        {p.change_pct != null ? `${p.change_pct >= 0 ? '+' : ''}${p.change_pct.toFixed(2)}%` : '—'}
                      </td>
                      <td className="py-1.5 pr-4 text-right text-slate-400">{fmtBRL(p.old_balance)}</td>
                      <td className="py-1.5 text-right font-medium">{fmtBRL(p.new_balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {priceResult.errors?.length > 0 && (
            <details className="text-xs text-slate-400">
              <summary className="cursor-pointer">{priceResult.errors.length} sin actualizar</summary>
              <ul className="mt-1 space-y-0.5 pl-2">{priceResult.errors.map((e: string, i: number) => <li key={i}>{e}</li>)}</ul>
            </details>
          )}
        </div>
      )}

      {/* Rescate Total Modal */}
      <Modal
        open={!!rescateTarget}
        onClose={() => { setRescateTarget(null); setRescateError(null); }}
        title="Rescate Total"
        size="sm"
      >
        {rescateTarget && (
          <div className="space-y-4">
            <div>
              <p className="text-base font-bold text-gray-900 dark:text-white">{rescateTarget.name}</p>
              <p className="text-sm text-gray-500 dark:text-gray-400">{rescateTarget.custodian}</p>
            </div>
            <hr className="border-gray-200 dark:border-gray-700" />
            <div className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Saldo BRL</span>
                <span className="font-mono font-medium">
                  {rescateTarget.balance_brl != null ? fmtBRL(rescateTarget.balance_brl) : 'Sin datos'}
                </span>
              </div>
              {rescateTarget.balance_usd != null && (
                <div className="flex justify-between">
                  <span className="text-gray-500">Saldo USD</span>
                  <span className="font-mono font-medium">{fmtUSD(rescateTarget.balance_usd)}</span>
                </div>
              )}
            </div>
            <hr className="border-gray-200 dark:border-gray-700" />
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Fecha de rescate
              </label>
              <input
                type="date"
                className="input w-full"
                value={rescateDate}
                onChange={e => setRescateDate(e.target.value)}
                required
              />
            </div>
            {(rescateTarget.balance_brl == null || rescateTarget.balance_brl === 0) && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-3 text-sm text-amber-700 dark:text-amber-400">
                ⚠️ El saldo actual es cero o desconocido. La transacción se registrará con monto R$ 0. Podés editarla después en Transacciones.
              </div>
            )}
            {rescateError && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-3 text-sm text-red-700 dark:text-red-400">
                {rescateError}
              </div>
            )}
            <div className="flex gap-3 justify-end pt-2">
              <button
                className="btn-secondary"
                onClick={() => { setRescateTarget(null); setRescateError(null); }}
                disabled={rescateLoading}
              >
                Cancelar
              </button>
              <button
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
                onClick={handleRescateTotal}
                disabled={rescateLoading || !rescateDate}
              >
                {rescateLoading && <Loader2 size={14} className="animate-spin" />}
                Confirmar rescate
              </button>
            </div>
          </div>
        )}
      </Modal>

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
                    <TH col="balance_usd" label="Saldo USD" />
                    <TH col="portfolio_pct" label="% Portfolio" />
                    {showReturns && <><TH col="return_1m" label="1M%" /><TH col="return_3m" label="3M%" /><TH col="return_6m" label="6M%" /><TH col="return_12m" label="12M%" /><TH col="rank_1m" label="Rank" /></>}
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Cantidad</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Precio actual</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">Precio medio</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Vencimiento</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider"></th>
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
                          {row.in_liquidation && (
                            <span className="ml-1 text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 px-1.5 py-0.5 rounded-full">Em liquidação</span>
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-gray-800 dark:text-gray-200 cursor-pointer group" onClick={async () => {
                            let mpId = row.mp_id;
                            if (!mpId) mpId = await ensureMonthPosition(row.id, priceMonth);
                            setEditing({ mpId, instrumentId: row.id, field: 'balance_brl', value: String(row.balance_brl ?? '') });
                          }}>
                          {editing?.instrumentId === row.id && editing.field === 'balance_brl' ? (
                            <input
                              autoFocus
                              className="w-28 px-1 py-0.5 text-sm border border-blue-400 rounded font-mono"
                              value={editing.value}
                              onChange={e => setEditing(ed => ed ? { ...ed, value: e.target.value } : ed)}
                              onBlur={() => saveBalance(editing.mpId, editing.field, editing.value)}
                              onKeyDown={e => { if (e.key === 'Enter') saveBalance(editing.mpId, editing.field, editing.value); if (e.key === 'Escape') setEditing(null); }}
                            />
                          ) : (
                            <span className="group-hover:underline decoration-dotted">
                              {row.balance_brl == null && row.type === 'renta_fija' ? <span className="text-xs text-gray-400 italic">Sin precio</span> : fmtBRL(row.balance_brl)}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-gray-600 dark:text-gray-400 cursor-pointer group"
                          onClick={async () => {
                            let mpId = row.mp_id;
                            if (!mpId) mpId = await ensureMonthPosition(row.id, priceMonth);
                            setEditing({ mpId, instrumentId: row.id, field: 'balance_usd', value: String(row.balance_usd ?? '') });
                          }}>
                          {editing?.instrumentId === row.id && editing.field === 'balance_usd' ? (
                            <input
                              autoFocus
                              className="w-24 px-1 py-0.5 text-sm border border-blue-400 rounded font-mono"
                              value={editing.value}
                              onChange={e => setEditing(ed => ed ? { ...ed, value: e.target.value } : ed)}
                              onBlur={() => saveBalance(editing.mpId, editing.field, editing.value)}
                              onKeyDown={e => { if (e.key === 'Enter') saveBalance(editing.mpId, editing.field, editing.value); if (e.key === 'Escape') setEditing(null); }}
                            />
                          ) : (
                            <span className="group-hover:underline decoration-dotted">
                              {row.balance_usd != null ? row.balance_usd.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) : '—'}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-gray-600 dark:text-gray-400">{fmtPct(row.portfolio_pct)}</td>
                        {showReturns && (() => {
                          const retTooltip = row.return_source === 'price'
                            ? 'Retorno calculado sobre precio unitario (excluye compras/ventas)'
                            : row.return_source === 'balance'
                            ? 'Retorno estimado sobre saldo (ajustado por transacciones registradas)'
                            : undefined;
                          return <>
                            <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_1m)}`} title={retTooltip}>{fmtPct(row.return_1m)}</td>
                            <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_3m)}`} title={retTooltip}>{fmtPct(row.return_3m)}</td>
                            <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_6m)}`} title={retTooltip}>{fmtPct(row.return_6m)}</td>
                            <td className={`px-3 py-2.5 font-mono ${colorReturn(row.return_12m)}`} title={retTooltip}>{fmtPct(row.return_12m)}</td>
                            <td className="px-3 py-2.5 text-center text-gray-500">{row.rank_1m ?? '—'}</td>
                          </>;
                        })()}
                        <td className="px-3 py-2 font-mono text-gray-600 dark:text-gray-400 cursor-pointer group"
                          onClick={async () => {
                            let mpId = row.mp_id;
                            if (!mpId) mpId = await ensureMonthPosition(row.id, priceMonth);
                            setEditing({ mpId, instrumentId: row.id, field: 'quantity', value: String(row.quantity ?? '') });
                          }}>
                          {editing?.instrumentId === row.id && editing.field === 'quantity' ? (
                            <input
                              autoFocus
                              className="w-20 px-1 py-0.5 text-sm border border-blue-400 rounded font-mono"
                              value={editing.value}
                              onChange={e => setEditing(ed => ed ? { ...ed, value: e.target.value } : ed)}
                              onBlur={() => saveBalance(editing.mpId, editing.field, editing.value)}
                              onKeyDown={e => { if (e.key === 'Enter') saveBalance(editing.mpId, editing.field, editing.value); if (e.key === 'Escape') setEditing(null); }}
                            />
                          ) : (
                            <span className="group-hover:underline decoration-dotted">
                              {row.quantity != null ? row.quantity.toLocaleString('pt-BR') : '—'}
                            </span>
                          )}
                        </td>
                        <td className={`px-3 py-2.5 font-mono text-sm ${
                          row.unit_price == null ? 'text-gray-400' :
                          row.avg_price == null ? 'text-gray-600 dark:text-gray-400' :
                          row.unit_price >= row.avg_price ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-500 dark:text-rose-400'
                        }`}>
                          {row.unit_price != null ? row.unit_price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                        </td>
                        <td className="px-3 py-2.5 font-mono text-sm text-gray-500">
                          {row.avg_price != null ? row.avg_price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
                        </td>
                        <td className={`px-3 py-2.5 ${nearMaturity ? 'text-amber-500 font-semibold' : 'text-gray-500'}`}>
                          {fmtDate(row.maturity_date)}
                          {nearMaturity && <span className="ml-1 text-xs">⚠️</span>}
                        </td>
                        {(row.type === 'accion' || row.type === 'fii') && (
                          <td className="px-3 py-2.5">
                            <Link
                              to={`/equity-trades?instrument_id=${row.id}`}
                              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline whitespace-nowrap"
                            >
                              Ver operaciones
                            </Link>
                          </td>
                        )}
                        {row.type === 'renta_fija' && row.status === 'activo' && (
                          <td className="px-3 py-2.5">
                            <button
                              title="Rescatar total"
                              className="text-gray-400 hover:text-red-500 transition-colors cursor-pointer"
                              onClick={() => {
                                setRescateTarget({
                                  id: row.id,
                                  name: row.name,
                                  custodian: row.custodian,
                                  balance_brl: row.balance_brl ?? null,
                                  balance_usd: row.balance_usd ?? null,
                                });
                                setRescateDate(new Date().toISOString().split('T')[0]);
                                setRescateError(null);
                              }}
                            >
                              <ArrowDownCircle size={16} />
                            </button>
                          </td>
                        )}
                        {row.type !== 'accion' && row.type !== 'fii' && row.type !== 'renta_fija' && <td />}
                        {row.type === 'renta_fija' && row.status !== 'activo' && <td />}
                      </tr>
                    );
                  })}
                  {data.items.length === 0 && (
                    <tr><td colSpan={12} className="px-3 py-8 text-center text-gray-400">No hay instrumentos</td></tr>
                  )}
                  {data.items.length > 0 && (
                    <tr className="bg-gray-50 dark:bg-gray-800/70 border-t-2 border-gray-200 dark:border-gray-600 font-semibold">
                      <td className="px-3 py-2.5 text-xs text-gray-500 uppercase" colSpan={3}>Total</td>
                      <td className="px-3 py-2.5 font-mono text-gray-800 dark:text-gray-200">{fmtBRL(data.total_brl)}</td>
                      <td className="px-3 py-2.5 font-mono text-gray-600 dark:text-gray-400">
                        {data.total_usd != null ? data.total_usd.toLocaleString('pt-BR', { maximumFractionDigits: 0 }) : '—'}
                      </td>
                      <td colSpan={showReturns ? 10 : 5} />
                    </tr>
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
