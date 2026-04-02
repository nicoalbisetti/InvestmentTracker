import { useState, useEffect, useRef } from 'react';
import client from '../api/client';
import { EquityTradeCreate, EquityTradeUpdate } from '../api/equityTrades';

interface InstrumentOption {
  id: number;
  name: string;
  ticker: string | null;
}

interface Props {
  initialValues?: {
    instrument_id?: number;
    instrument_name?: string;
    instrument_ticker?: string | null;
    date?: string;
    trade_type?: 'compra' | 'venta';
    quantity?: number;
    price?: number;
    notes?: string;
  };
  onSubmit: (data: EquityTradeCreate | EquityTradeUpdate) => Promise<void>;
  submitLabel?: string;
  isEdit?: boolean;
}

function parseBR(val: string): number {
  // "1.234,56" -> 1234.56
  return parseFloat(val.replace(/\./g, '').replace(',', '.'));
}

export default function EquityTradeForm({ initialValues, onSubmit, submitLabel = 'Registrar Operación', isEdit = false }: Props) {
  const today = new Date().toISOString().split('T')[0];

  const [instrumentSearch, setInstrumentSearch] = useState(
    initialValues?.instrument_ticker
      ? `${initialValues.instrument_ticker} — ${initialValues.instrument_name}`
      : initialValues?.instrument_name || ''
  );
  const [instrumentId, setInstrumentId] = useState<number | null>(initialValues?.instrument_id ?? null);
  const [instrumentOptions, setInstrumentOptions] = useState<InstrumentOption[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [tradeType, setTradeType] = useState<'compra' | 'venta'>(initialValues?.trade_type ?? 'compra');
  const [date, setDate] = useState(initialValues?.date ?? today);
  const [quantity, setQuantity] = useState(initialValues?.quantity?.toString().replace('.', ',') ?? '');
  const [price, setPrice] = useState(initialValues?.price?.toString().replace('.', ',') ?? '');
  const [notes, setNotes] = useState(initialValues?.notes ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const qtyNum = parseBR(quantity) || 0;
  const priceNum = parseBR(price) || 0;
  const amountTotal = qtyNum > 0 && priceNum > 0 ? qtyNum * priceNum : null;

  // Fetch instruments on search change
  useEffect(() => {
    if (instrumentSearch.length < 2) {
      setInstrumentOptions([]);
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(() => {
      client.get('/api/instruments', { params: { search: instrumentSearch, status: 'activo', limit: 20 } })
        .then(r => {
          const items = r.data?.items ?? r.data ?? [];
          setInstrumentOptions(items);
          setShowDropdown(true);
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [instrumentSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSelectInstrument = (inst: InstrumentOption) => {
    setInstrumentId(inst.id);
    setInstrumentSearch(inst.ticker ? `${inst.ticker} — ${inst.name}` : inst.name);
    setShowDropdown(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const qty = parseBR(quantity);
    const prc = parseBR(price);

    if (!isEdit && !instrumentId) { setError('Seleccioná un instrumento'); return; }
    if (isNaN(qty) || qty <= 0) { setError('Cantidad debe ser mayor a 0'); return; }
    if (isNaN(prc) || prc <= 0) { setError('Precio debe ser mayor a 0'); return; }

    setSubmitting(true);
    try {
      if (isEdit) {
        const data: EquityTradeUpdate = { date, trade_type: tradeType, quantity: qty, price: prc, notes: notes || undefined };
        await onSubmit(data);
      } else {
        const data: EquityTradeCreate = { instrument_id: instrumentId!, date, trade_type: tradeType, quantity: qty, price: prc, notes: notes || undefined };
        await onSubmit(data);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Error al guardar');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Instrumento */}
      {!isEdit && (
        <div className="relative" ref={dropdownRef}>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Instrumento</label>
          <input
            className="input w-full"
            placeholder="Buscar por ticker o nombre..."
            value={instrumentSearch}
            onChange={e => { setInstrumentSearch(e.target.value); setInstrumentId(null); }}
            onFocus={() => instrumentOptions.length > 0 && setShowDropdown(true)}
            autoComplete="off"
          />
          {showDropdown && instrumentOptions.length > 0 && (
            <div className="absolute z-50 left-0 right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg max-h-56 overflow-y-auto">
              {instrumentOptions.map(inst => (
                <button
                  key={inst.id}
                  type="button"
                  className="w-full text-left px-4 py-2.5 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                  onClick={() => handleSelectInstrument(inst)}
                >
                  <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400 mr-2">{inst.ticker ?? '—'}</span>
                  <span className="text-gray-700 dark:text-gray-300">{inst.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tipo */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Tipo</label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setTradeType('compra')}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
              tradeType === 'compra'
                ? 'bg-emerald-600 border-emerald-600 text-white'
                : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-emerald-400'
            }`}
          >
            Compra
          </button>
          <button
            type="button"
            onClick={() => setTradeType('venta')}
            className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
              tradeType === 'venta'
                ? 'bg-rose-600 border-rose-600 text-white'
                : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-rose-400'
            }`}
          >
            Venta
          </button>
        </div>
      </div>

      {/* Fecha */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Fecha</label>
        <input
          type="date"
          className="input w-full"
          value={date}
          onChange={e => setDate(e.target.value)}
          required
        />
      </div>

      {/* Cantidad y Precio */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Cantidad</label>
          <input
            className="input w-full"
            placeholder="0"
            value={quantity}
            onChange={e => setQuantity(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Precio (BRL)</label>
          <input
            className="input w-full"
            placeholder="0,00"
            value={price}
            onChange={e => setPrice(e.target.value)}
            required
          />
        </div>
      </div>

      {/* Monto total calculado */}
      <div>
        <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Monto total</label>
        <div className="input w-full bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono cursor-not-allowed">
          {amountTotal != null
            ? amountTotal.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            : '—'}
        </div>
      </div>

      {/* Notas */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Notas (opcional)</label>
        <textarea
          className="input w-full resize-none"
          rows={2}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Corretora, orden, etc."
        />
      </div>

      {error && <p className="text-sm text-rose-500">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="btn-primary w-full disabled:opacity-50"
      >
        {submitting ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
            Guardando...
          </span>
        ) : submitLabel}
      </button>
    </form>
  );
}
