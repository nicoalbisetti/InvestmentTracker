import { useEffect, useRef, useState } from 'react';
import { getTransactions, createTransaction, updateTransaction, deleteTransaction } from '../api/transactions';
import { getInstruments } from '../api/instruments';
import Modal from '../components/ui/Modal';
import InstrumentCombobox from '../components/ui/InstrumentCombobox';
import { fmtBRL, fmtDate } from '../utils/formatters';
import client from '../api/client';

const TYPE_OPTIONS = [
  { value: 'aplicacion', label: 'Aplicación' },
  { value: 'rescate', label: 'Rescate' },
  { value: 'provento', label: 'Provento' },
  { value: 'outro', label: 'Otro' },
];

const TYPE_COLORS: Record<string, string> = {
  aplicacion: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  rescate: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  provento: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  outro: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
};

const CUSTODIAN_OPTIONS = ['XP', 'SANTANDER', 'INTER', 'XP_INTERNATIONAL'];

const EMPTY_FORM = { date: '', type: 'aplicacion', amount_brl: '', amount_usd: '', notes: '' };

const roundTo = (v: number, dec: number) => Math.round(v * 10 ** dec) / 10 ** dec;

export default function Transactions() {
  const [data, setData] = useState<any>({ items: [], total: 0, pages: 1 });
  const [instruments, setInstruments] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [formInstrumentId, setFormInstrumentId] = useState<number | ''>('');
  const [saving, setSaving] = useState(false);
  const [editingTx, setEditingTx] = useState<any | null>(null);

  const [filters, setFilters] = useState({
    custodian: '',
    month_year: '',
    type: '',
    instrument_id: '' as number | '',
  });

  // Quote lookup state
  const [quoteRate, setQuoteRate] = useState<number | null>(null);
  const [quoteFound, setQuoteFound] = useState<boolean | null>(null);
  const [manualRate, setManualRate] = useState('');
  const [overrideSecondary, setOverrideSecondary] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const hasActiveFilter = filters.custodian || filters.month_year || filters.type || filters.instrument_id !== '';

  // Derived values
  const selectedInstrument = instruments.find(i => i.id === formInstrumentId);
  const instrumentCurrency: 'BRL' | 'USD' | null = selectedInstrument?.currency ?? null;
  const isFlow = form.type === 'aplicacion' || form.type === 'rescate';
  const showCurrencyUI = isFlow && instrumentCurrency !== null;

  const effectiveRate = quoteRate ?? (manualRate ? parseFloat(manualRate) : null);

  let calculatedSecondary: number | null = null;
  if (showCurrencyUI && effectiveRate) {
    if (instrumentCurrency === 'USD' && form.amount_usd) {
      const v = parseFloat(form.amount_usd);
      if (!isNaN(v) && v > 0) calculatedSecondary = roundTo(v * effectiveRate, 2);
    } else if (instrumentCurrency === 'BRL' && form.amount_brl) {
      const v = parseFloat(form.amount_brl);
      if (!isNaN(v) && v > 0) calculatedSecondary = roundTo(v / effectiveRate, 2);
    }
  }

  const month = form.date ? form.date.substring(0, 7) : '';

  const buildParams = () => {
    const p: Record<string, any> = { page, limit: 50 };
    if (filters.custodian) p.custodian = filters.custodian;
    if (filters.month_year) p.month_year = filters.month_year;
    if (filters.type) p.type = filters.type;
    if (filters.instrument_id !== '') p.instrument_id = filters.instrument_id;
    return p;
  };

  const load = () => {
    setLoading(true);
    getTransactions(buildParams()).then(setData).finally(() => setLoading(false));
  };

  useEffect(() => {
    getInstruments({ limit: 200 }).then((r: any) => setInstruments(r.items));
  }, []);

  useEffect(() => { load(); }, [page, filters]);

  // Fetch quote when date/instrument/type changes (debounced 300ms)
  useEffect(() => {
    if (!isFlow || !form.date || formInstrumentId === '') {
      setQuoteRate(null);
      setQuoteFound(null);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await client.get('/api/quotes/lookup', { params: { month: form.date.substring(0, 7) } });
        setQuoteRate(res.data.rate);
        setQuoteFound(res.data.found);
        setManualRate('');
      } catch {
        setQuoteRate(null);
        setQuoteFound(null);
      }
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [form.date, formInstrumentId, form.type]);

  const setFilter = (key: string, value: any) => {
    setPage(1);
    setFilters(f => ({ ...f, [key]: value }));
  };

  const clearFilters = () => {
    setPage(1);
    setFilters({ custodian: '', month_year: '', type: '', instrument_id: '' });
  };

  const resetQuoteState = () => {
    setQuoteRate(null);
    setQuoteFound(null);
    setManualRate('');
    setOverrideSecondary(false);
  };

  const openNew = () => {
    setEditingTx(null);
    setForm(EMPTY_FORM);
    setFormInstrumentId('');
    resetQuoteState();
    setShowModal(true);
  };

  const openEdit = (tx: any) => {
    setEditingTx(tx);
    setForm({
      date: tx.date,
      type: tx.type,
      amount_brl: String(tx.amount_brl ?? ''),
      amount_usd: tx.amount_usd ? String(tx.amount_usd) : '',
      notes: tx.notes ?? '',
    });
    setFormInstrumentId(tx.instrument_id);
    resetQuoteState();
    setOverrideSecondary(true); // edit mode: both values already set intentionally
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingTx(null);
    setForm(EMPTY_FORM);
    setFormInstrumentId('');
    resetQuoteState();
  };

  const handleSave = async () => {
    if (!form.date) return;
    if (!editingTx && formInstrumentId === '') return;

    // Validate primary field
    if (showCurrencyUI && instrumentCurrency === 'USD') {
      if (!form.amount_usd) return;
    } else {
      if (!form.amount_brl) return;
    }

    setSaving(true);
    try {
      let amount_brl: number | undefined;
      let amount_usd: number | undefined;

      if (showCurrencyUI && instrumentCurrency === 'USD') {
        amount_usd = parseFloat(form.amount_usd) || undefined;
        amount_brl = overrideSecondary
          ? (parseFloat(form.amount_brl) || undefined)
          : (calculatedSecondary ?? undefined);
      } else if (showCurrencyUI && instrumentCurrency === 'BRL') {
        amount_brl = parseFloat(form.amount_brl) || undefined;
        amount_usd = overrideSecondary
          ? (parseFloat(form.amount_usd) || undefined)
          : (calculatedSecondary ?? undefined);
      } else {
        // provento/outro or no currency: free fields
        amount_brl = form.amount_brl ? Number(form.amount_brl) : undefined;
        amount_usd = form.amount_usd ? Number(form.amount_usd) : undefined;
      }

      const payload = {
        date: form.date,
        type: form.type,
        amount_brl,
        amount_usd,
        notes: form.notes || undefined,
      };

      if (editingTx) {
        await updateTransaction(editingTx.id, payload);
      } else {
        await createTransaction({ ...payload, instrument_id: Number(formInstrumentId) });
      }
      closeModal();
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar esta transacción?')) return;
    await deleteTransaction(id);
    load();
  };

  const showOverrideCheckbox = showCurrencyUI && form.date && formInstrumentId !== '' &&
    (quoteFound === true || (quoteFound === false && manualRate !== ''));

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-lg font-semibold">Transacciones</h1>
        <button className="btn-primary" onClick={openNew}>+ Nueva Transacción</button>
      </div>

      {/* Filters */}
      <div className="card p-3 space-y-2">
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex flex-col gap-1 min-w-[140px]">
            <label className="text-xs font-medium text-gray-500">Custodio</label>
            <select className="input text-sm py-1.5" value={filters.custodian} onChange={e => setFilter('custodian', e.target.value)}>
              <option value="">Todos</option>
              {CUSTODIAN_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1 min-w-[140px]">
            <label className="text-xs font-medium text-gray-500">Mes/Año</label>
            <input
              type="month"
              className="input text-sm py-1.5"
              value={filters.month_year}
              onChange={e => setFilter('month_year', e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1 min-w-[140px]">
            <label className="text-xs font-medium text-gray-500">Tipo</label>
            <select className="input text-sm py-1.5" value={filters.type} onChange={e => setFilter('type', e.target.value)}>
              <option value="">Todos los tipos</option>
              {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1 min-w-[200px]">
            <label className="text-xs font-medium text-gray-500">Instrumento</label>
            <InstrumentCombobox
              value={filters.instrument_id}
              onChange={v => setFilter('instrument_id', v)}
              instruments={instruments}
              placeholder="Todos los instrumentos"
            />
          </div>
          {hasActiveFilter && (
            <button className="btn-secondary text-sm py-1.5 self-end" onClick={clearFilters}>
              Limpiar filtros
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400">{data.total} transacciones</p>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              {['Fecha', 'Instrumento', 'Custodio', 'Tipo', 'Monto BRL', 'Monto USD', 'Notas', ''].map(h => (
                <th key={h} className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              [...Array(8)].map((_, i) => (
                <tr key={i}>
                  {[...Array(8)].map((_, j) => (
                    <td key={j} className="px-3 py-3">
                      <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-4 rounded" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.items.length === 0 ? (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">No hay transacciones registradas</td></tr>
            ) : (
              data.items.map((t: any) => (
                <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-3 py-2.5 whitespace-nowrap">{fmtDate(t.date)}</td>
                  <td className="px-3 py-2.5 max-w-[160px] truncate font-medium" title={t.instrument_name}>{t.instrument_name}</td>
                  <td className="px-3 py-2.5 text-gray-500">{t.instrument_custodian}</td>
                  <td className="px-3 py-2.5">
                    <span className={`badge ${TYPE_COLORS[t.type] || TYPE_COLORS.outro}`}>
                      {TYPE_OPTIONS.find(o => o.value === t.type)?.label || t.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono">{fmtBRL(t.amount_brl)}</td>
                  <td className="px-3 py-2.5 font-mono text-gray-500">{t.amount_usd ? `US$ ${t.amount_usd?.toLocaleString()}` : '—'}</td>
                  <td className="px-3 py-2.5 text-gray-500 max-w-[140px] truncate" title={t.notes}>{t.notes || '—'}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex gap-2">
                      <button onClick={() => openEdit(t)} className="text-indigo-400 hover:text-indigo-600 text-xs">Editar</button>
                      <button onClick={() => handleDelete(t.id)} className="text-red-400 hover:text-red-600 text-xs">Eliminar</button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {data.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-500">Página {page} de {data.pages} ({data.total} registros)</p>
            <div className="flex gap-2">
              <button className="btn-secondary text-sm py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
              <button className="btn-secondary text-sm py-1" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Siguiente →</button>
            </div>
          </div>
        )}
      </div>

      <Modal open={showModal} onClose={closeModal} title={editingTx ? 'Editar Transacción' : 'Nueva Transacción'} size="md">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Instrumento *</label>
            {editingTx ? (
              <div className="input bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400 cursor-not-allowed">
                {editingTx.instrument_name}
                <span className="ml-2 text-xs text-gray-400">({editingTx.instrument_custodian})</span>
              </div>
            ) : (
              <InstrumentCombobox
                value={formInstrumentId}
                onChange={setFormInstrumentId}
                instruments={instruments}
              />
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Fecha *</label>
              <input type="date" className="input" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tipo *</label>
              <select className="input" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}>
                {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>

          {/* Amount fields */}
          {showCurrencyUI ? (
            <>
              <div className="grid grid-cols-2 gap-3">
                {instrumentCurrency === 'BRL' ? (
                  <>
                    <div>
                      <label className="block text-sm font-medium mb-1">Monto BRL *</label>
                      <input
                        type="number"
                        className="input"
                        placeholder="0.00"
                        value={form.amount_brl}
                        onChange={e => setForm(f => ({ ...f, amount_brl: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="flex items-center gap-1.5 text-sm font-medium mb-1">
                        Monto USD
                        <span className={`text-xs px-1.5 py-0.5 rounded font-normal ${overrideSecondary ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                          {overrideSecondary ? 'manual' : 'calculado'}
                        </span>
                      </label>
                      <input
                        type="number"
                        className={`input ${!overrideSecondary ? 'bg-gray-50 dark:bg-gray-800 text-gray-400' : ''}`}
                        placeholder={!effectiveRate ? 'Sin cotización' : '0.00'}
                        disabled={!overrideSecondary}
                        value={overrideSecondary ? form.amount_usd : (calculatedSecondary !== null ? String(calculatedSecondary) : '')}
                        onChange={e => setForm(f => ({ ...f, amount_usd: e.target.value }))}
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-sm font-medium mb-1">Monto USD *</label>
                      <input
                        type="number"
                        className="input"
                        placeholder="0.00"
                        value={form.amount_usd}
                        onChange={e => setForm(f => ({ ...f, amount_usd: e.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="flex items-center gap-1.5 text-sm font-medium mb-1">
                        Monto BRL
                        <span className={`text-xs px-1.5 py-0.5 rounded font-normal ${overrideSecondary ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'}`}>
                          {overrideSecondary ? 'manual' : 'calculado'}
                        </span>
                      </label>
                      <input
                        type="number"
                        className={`input ${!overrideSecondary ? 'bg-gray-50 dark:bg-gray-800 text-gray-400' : ''}`}
                        placeholder={!effectiveRate ? 'Sin cotización' : '0.00'}
                        disabled={!overrideSecondary}
                        value={overrideSecondary ? form.amount_brl : (calculatedSecondary !== null ? String(calculatedSecondary) : '')}
                        onChange={e => setForm(f => ({ ...f, amount_brl: e.target.value }))}
                      />
                    </div>
                  </>
                )}
              </div>

              {/* Quote info block */}
              {form.date && formInstrumentId !== '' && (
                <div className="space-y-2">
                  {quoteFound === true && (
                    <p className="text-xs text-gray-400">
                      Cotización del mes: R$ {quoteRate!.toFixed(4)}
                    </p>
                  )}
                  {quoteFound === false && (
                    <>
                      <div className="text-xs bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 rounded px-3 py-2">
                        ⚠️ No hay cotización registrada para {month}.
                      </div>
                      <div>
                        <label className="block text-xs font-medium mb-1 text-gray-600 dark:text-gray-400">
                          Cotización USD/BRL (solo para este cálculo)
                        </label>
                        <input
                          type="number"
                          step="0.0001"
                          className="input text-sm"
                          placeholder="5.2000"
                          value={manualRate}
                          onChange={e => setManualRate(e.target.value)}
                        />
                        <p className="text-xs text-gray-400 mt-1">Este valor no se guarda. Solo se usa para calcular el segundo monto.</p>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Override checkbox */}
              {showOverrideCheckbox && (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={overrideSecondary}
                    className="rounded"
                    onChange={e => {
                      setOverrideSecondary(e.target.checked);
                      if (e.target.checked && calculatedSecondary !== null) {
                        if (instrumentCurrency === 'USD') {
                          setForm(f => ({ ...f, amount_brl: String(calculatedSecondary) }));
                        } else {
                          setForm(f => ({ ...f, amount_usd: String(calculatedSecondary) }));
                        }
                      }
                    }}
                  />
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Editar monto {instrumentCurrency === 'USD' ? 'BRL' : 'USD'} manualmente
                  </span>
                </label>
              )}
            </>
          ) : (
            /* provento / outro / no instrument selected */
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium mb-1">Monto BRL *</label>
                <input type="number" className="input" placeholder="0.00" value={form.amount_brl} onChange={e => setForm(f => ({ ...f, amount_brl: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Monto USD (opcional)</label>
                <input type="number" className="input" placeholder="0.00" value={form.amount_usd} onChange={e => setForm(f => ({ ...f, amount_usd: e.target.value }))} />
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Notas</label>
            <textarea className="input resize-none" rows={2} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>
          <div className="flex gap-3 pt-2">
            <button className="btn-secondary flex-1" onClick={closeModal}>Cancelar</button>
            <button className="btn-primary flex-1" onClick={handleSave} disabled={saving}>
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
