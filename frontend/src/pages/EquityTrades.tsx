import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  getEquityTrades, createEquityTrade, updateEquityTrade, deleteEquityTrade,
  EquityTradeOut, GetTradesParams,
} from '../api/equityTrades';
import EquityTradeForm from '../components/EquityTradeForm';
import EquityTradeSummaryCard from '../components/EquityTradeSummaryCard';
import client from '../api/client';

// Simple toast
function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium animate-in">
      {message}
    </div>
  );
}

// Modal wrapper
function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none">✕</button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

// Alert dialog for delete confirmation
function DeleteAlert({ trade, onConfirm, onCancel }: { trade: EquityTradeOut; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">¿Eliminar operación?</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Las posiciones de <strong>{trade.instrument_ticker ?? trade.instrument_name}</strong> serán
          recalculadas desde <strong>{trade.date}</strong> en adelante.
        </p>
        <div className="flex gap-3">
          <button onClick={onCancel} className="flex-1 btn-secondary">Cancelar</button>
          <button onClick={onConfirm} className="flex-1 py-2 rounded-xl bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 transition-colors">
            Eliminar
          </button>
        </div>
      </div>
    </div>
  );
}

interface InstrumentOption { id: number; name: string; ticker: string | null; }

export default function EquityTrades() {
  const [searchParams] = useSearchParams();
  const preselectedId = searchParams.get('instrument_id') ? Number(searchParams.get('instrument_id')) : null;

  // Filter state
  const [filterInstrumentId, setFilterInstrumentId] = useState<number | null>(preselectedId);
  const [filterInstrumentLabel, setFilterInstrumentLabel] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [filterType, setFilterType] = useState('');
  const [page, setPage] = useState(1);

  // Data
  const [data, setData] = useState<{ items: EquityTradeOut[]; total: number; pages: number }>({ items: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);

  // Instrument search for filter
  const [instrSearch, setInstrSearch] = useState('');
  const [instrOptions, setInstrOptions] = useState<InstrumentOption[]>([]);
  const [showInstrDropdown, setShowInstrDropdown] = useState(false);

  // Toast
  const [toast, setToast] = useState<string | null>(null);

  // Modals
  const [editTrade, setEditTrade] = useState<EquityTradeOut | null>(null);
  const [deleteTrade, setDeleteTrade] = useState<EquityTradeOut | null>(null);

  // Load preselected instrument label
  useEffect(() => {
    if (preselectedId) {
      client.get(`/api/instruments/${preselectedId}`)
        .then(r => {
          const inst = r.data;
          setFilterInstrumentLabel(inst.ticker ? `${inst.ticker} — ${inst.name}` : inst.name);
          setInstrSearch(inst.ticker ? `${inst.ticker} — ${inst.name}` : inst.name);
        })
        .catch(() => {});
    }
  }, [preselectedId]);

  const load = useCallback(() => {
    setLoading(true);
    const params: GetTradesParams = { page, limit: 50 };
    if (filterInstrumentId) params.instrument_id = filterInstrumentId;
    if (filterDateFrom) params.date_from = filterDateFrom;
    if (filterDateTo) params.date_to = filterDateTo;
    if (filterType) params.trade_type = filterType;
    getEquityTrades(params)
      .then(r => setData({ items: r.items, total: r.total, pages: r.pages }))
      .finally(() => setLoading(false));
  }, [page, filterInstrumentId, filterDateFrom, filterDateTo, filterType]);

  useEffect(() => { load(); }, [load]);

  // Instrument search for filter dropdown
  useEffect(() => {
    if (instrSearch.length < 2) { setInstrOptions([]); setShowInstrDropdown(false); return; }
    const t = setTimeout(() => {
      client.get('/api/instruments', { params: { search: instrSearch, limit: 20 } })
        .then(r => { setInstrOptions(r.data?.items ?? r.data ?? []); setShowInstrDropdown(true); })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [instrSearch]);

  const handleCreate = async (formData: any) => {
    const result = await createEquityTrade(formData);
    setToast(`Operación registrada. ${result.recalculated_months} meses recalculados desde ${result.affected_from}`);
    load();
  };

  const handleEdit = async (formData: any) => {
    if (!editTrade) return;
    const result = await updateEquityTrade(editTrade.id, formData);
    setEditTrade(null);
    setToast(`Operación actualizada. ${result.recalculated_months} meses recalculados desde ${result.affected_from}`);
    load();
  };

  const handleDelete = async () => {
    if (!deleteTrade) return;
    await deleteEquityTrade(deleteTrade.id);
    setDeleteTrade(null);
    setToast('Operación eliminada. Posiciones recalculadas.');
    load();
  };

  const fmtDate = (d: string) => { const [y, m, day] = d.split('-'); return `${day}/${m}/${y}`; };
  const fmtNum = (v: number) => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
  const fmtBRL = (v: number | null) => v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}
      {editTrade && (
        <Modal title="Editar Operación" onClose={() => setEditTrade(null)}>
          <EquityTradeForm
            isEdit
            initialValues={{
              instrument_id: editTrade.instrument_id,
              instrument_name: editTrade.instrument_name,
              instrument_ticker: editTrade.instrument_ticker,
              date: editTrade.date,
              trade_type: editTrade.trade_type as 'compra' | 'venta',
              quantity: editTrade.quantity,
              price: editTrade.price,
              notes: editTrade.notes ?? '',
            }}
            onSubmit={handleEdit}
            submitLabel="Guardar cambios"
          />
        </Modal>
      )}
      {deleteTrade && (
        <DeleteAlert
          trade={deleteTrade}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTrade(null)}
        />
      )}

      {/* Form section */}
      <div className="card">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200 mb-4">Nueva Operación</h2>
        <EquityTradeForm onSubmit={handleCreate} />
      </div>

      {/* Filters */}
      <div className="card space-y-3">
        <h2 className="text-base font-semibold text-gray-800 dark:text-gray-200">Historial</h2>
        <div className="flex flex-wrap gap-3 items-end">
          {/* Instrument filter */}
          <div className="relative">
            <input
              className="input w-56"
              placeholder="Filtrar por instrumento..."
              value={instrSearch}
              onChange={e => {
                setInstrSearch(e.target.value);
                if (!e.target.value) { setFilterInstrumentId(null); setFilterInstrumentLabel(''); }
              }}
              onFocus={() => instrOptions.length > 0 && setShowInstrDropdown(true)}
              autoComplete="off"
            />
            {showInstrDropdown && instrOptions.length > 0 && (
              <div className="absolute z-40 left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg max-h-48 overflow-y-auto">
                {instrOptions.map(inst => (
                  <button
                    key={inst.id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                    onClick={() => {
                      setFilterInstrumentId(inst.id);
                      const label = inst.ticker ? `${inst.ticker} — ${inst.name}` : inst.name;
                      setFilterInstrumentLabel(label);
                      setInstrSearch(label);
                      setShowInstrDropdown(false);
                      setPage(1);
                    }}
                  >
                    <span className="font-mono text-indigo-600 dark:text-indigo-400 mr-1">{inst.ticker ?? '—'}</span>
                    {inst.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <input
            type="date"
            className="input"
            value={filterDateFrom}
            onChange={e => { setFilterDateFrom(e.target.value); setPage(1); }}
            title="Desde"
          />
          <input
            type="date"
            className="input"
            value={filterDateTo}
            onChange={e => { setFilterDateTo(e.target.value); setPage(1); }}
            title="Hasta"
          />
          <select
            className="input w-36"
            value={filterType}
            onChange={e => { setFilterType(e.target.value); setPage(1); }}
          >
            <option value="">Todos</option>
            <option value="compra">Compra</option>
            <option value="venta">Venta</option>
          </select>
          {(filterInstrumentId || filterDateFrom || filterDateTo || filterType) && (
            <button
              className="btn-secondary text-sm"
              onClick={() => {
                setFilterInstrumentId(null);
                setFilterInstrumentLabel('');
                setInstrSearch('');
                setFilterDateFrom('');
                setFilterDateTo('');
                setFilterType('');
                setPage(1);
              }}
            >
              Limpiar filtros
            </button>
          )}
          <span className="ml-auto text-sm text-gray-500">{data.total} operaciones</span>
        </div>

        {/* Summary card when instrument selected */}
        {filterInstrumentId && (
          <EquityTradeSummaryCard instrumentId={filterInstrumentId} />
        )}
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Cargando...</div>
        ) : data.items.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">No hay operaciones</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Fecha</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Instrumento</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tipo</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Cantidad</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Precio Unit.</th>
                    <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Monto Total</th>
                    <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Notas</th>
                    <th className="px-3 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Acciones</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.items.map(trade => (
                    <tr key={trade.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                      <td className="px-3 py-2.5 font-mono text-gray-700 dark:text-gray-300 whitespace-nowrap">{fmtDate(trade.date)}</td>
                      <td className="px-3 py-2.5 max-w-[160px]">
                        {trade.instrument_ticker && (
                          <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400 mr-1">{trade.instrument_ticker}</span>
                        )}
                        <span className="text-gray-700 dark:text-gray-300 truncate">{trade.instrument_name}</span>
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                          trade.trade_type === 'compra'
                            ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400'
                            : 'bg-rose-100 dark:bg-rose-900/30 text-rose-700 dark:text-rose-400'
                        }`}>
                          {trade.trade_type === 'compra' ? 'Compra' : 'Venta'}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-gray-700 dark:text-gray-300">{fmtNum(trade.quantity)}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-gray-700 dark:text-gray-300">
                        {trade.price.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-gray-800 dark:text-gray-200">{fmtBRL(trade.amount_brl)}</td>
                      <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400 max-w-[120px] truncate" title={trade.notes ?? ''}>
                        {trade.notes || '—'}
                      </td>
                      <td className="px-3 py-2.5 text-center">
                        <div className="flex gap-1.5 justify-center">
                          <button
                            onClick={() => setEditTrade(trade)}
                            className="text-xs px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/30 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
                          >
                            Editar
                          </button>
                          <button
                            onClick={() => setDeleteTrade(trade)}
                            className="text-xs px-2.5 py-1 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-rose-100 dark:hover:bg-rose-900/30 hover:text-rose-600 dark:hover:text-rose-400 transition-colors"
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Pagination */}
            {data.pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
                <p className="text-sm text-gray-500">Página {page} de {data.pages} ({data.total} registros)</p>
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
