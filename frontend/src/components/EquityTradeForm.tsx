import { useState, useEffect, useRef } from 'react';
import client from '../api/client';
import { EquityTradeCreate, EquityTradeUpdate } from '../api/equityTrades';

interface InstrumentOption {
  id: number;
  name: string;
  ticker: string | null;
  currency: string;
}

interface Props {
  initialValues?: {
    instrument_id?: number;
    instrument_name?: string;
    instrument_ticker?: string | null;
    instrument_currency?: string;
    date?: string;
    trade_type?: 'compra' | 'venta';
    quantity?: number;
    price?: number;
    usd_rate?: number | null;
    notes?: string;
  };
  onSubmit: (data: EquityTradeCreate | EquityTradeUpdate) => Promise<void>;
  submitLabel?: string;
  isEdit?: boolean;
}

function parseBR(val: string): number {
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
  const [instrumentCurrency, setInstrumentCurrency] = useState<string>(initialValues?.instrument_currency ?? 'BRL');
  const [instrumentOptions, setInstrumentOptions] = useState<InstrumentOption[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [tradeType, setTradeType] = useState<'compra' | 'venta'>(initialValues?.trade_type ?? 'compra');
  const [date, setDate] = useState(initialValues?.date ?? today);
  const [quantity, setQuantity] = useState(initialValues?.quantity?.toString().replace('.', ',') ?? '');
  const [price, setPrice] = useState(initialValues?.price?.toString().replace('.', ',') ?? '');
  const [usdRateStr, setUsdRateStr] = useState(
    initialValues?.usd_rate != null ? initialValues.usd_rate.toString().replace('.', ',') : ''
  );
  const [usdRateFromDb, setUsdRateFromDb] = useState<number | null>(null);
  const [usdRateOverride, setUsdRateOverride] = useState(initialValues?.usd_rate != null);
  const [notes, setNotes] = useState(initialValues?.notes ?? '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isUsd = instrumentCurrency === 'USD';
  const qtyNum = parseBR(quantity) || 0;
  const priceNum = parseBR(price) || 0;
  const effectiveRate = usdRateOverride ? (parseBR(usdRateStr) || null) : usdRateFromDb;
  const amountUsd = isUsd && qtyNum > 0 && priceNum > 0 ? qtyNum * priceNum : null;
  const amountBrl = amountUsd != null && effectiveRate ? amountUsd * effectiveRate : (!isUsd && qtyNum > 0 && priceNum > 0 ? qtyNum * priceNum : null);

  // Fetch USD rate from DB when instrument is USD and date changes
  useEffect(() => {
    if (!isUsd) return;
    const month = date.slice(0, 7);
    client.get('/api/quotes/lookup', { params: { month } })
      .then(r => {
        setUsdRateFromDb(r.data.rate ?? null);
        if (!usdRateOverride) {
          setUsdRateStr(r.data.rate != null ? r.data.rate.toString().replace('.', ',') : '');
        }
      })
      .catch(() => setUsdRateFromDb(null));
  }, [isUsd, date]);

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
          const items: InstrumentOption[] = r.data?.items ?? r.data ?? [];
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
    setInstrumentCurrency(inst.currency ?? 'BRL');
    setInstrumentSearch(inst.ticker ? `${inst.ticker} — ${inst.name}` : inst.name);
    setShowDropdown(false);
    setUsdRateOverride(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const qty = parseBR(quantity);
    const prc = parseBR(price);

    if (!isEdit && !instrumentId) { setError('Seleccioná un instrumento'); return; }
    if (isNaN(qty) || qty <= 0) { setError('Cantidad debe ser mayor a 0'); return; }
    if (isNaN(prc) || prc <= 0) { setError('Precio debe ser mayor a 0'); return; }

    const finalRate = effectiveRate;
    if (isUsd && !finalRate) {
      setError('Ingresá la cotización USD/BRL');
      return;
    }

    setSubmitting(true);
    try {
      if (isEdit) {
        const data: EquityTradeUpdate = {
          date,
          trade_type: tradeType,
          quantity: qty,
          price: prc,
          notes: notes || undefined,
          ...(isUsd && finalRate ? { usd_rate: finalRate } : {}),
        };
        await onSubmit(data);
      } else {
        const data: EquityTradeCreate = {
          instrument_id: instrumentId!,
          date,
          trade_type: tradeType,
          quantity: qty,
          price: prc,
          notes: notes || undefined,
          ...(isUsd && finalRate ? { usd_rate: finalRate } : {}),
        };
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
            onChange={e => { setInstrumentSearch(e.target.value); setInstrumentId(null); setInstrumentCurrency('BRL'); }}
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
                  {inst.currency === 'USD' && (
                    <span className="ml-2 text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded font-semibold">USD</span>
                  )}
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
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {isUsd ? 'Precio (USD)' : 'Precio (BRL)'}
          </label>
          <input
            className="input w-full"
            placeholder="0,00"
            value={price}
            onChange={e => setPrice(e.target.value)}
            required
          />
        </div>
      </div>

      {/* Cotización USD/BRL — solo para instrumentos USD */}
      {isUsd && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Cotización USD/BRL
            </label>
            {usdRateFromDb != null && !usdRateOverride && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                Del mes · <button type="button" className="text-indigo-500 hover:underline" onClick={() => setUsdRateOverride(true)}>Editar</button>
              </span>
            )}
          </div>
          {usdRateFromDb != null && !usdRateOverride ? (
            <div className="input w-full bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono cursor-default">
              1 USD = R$ {usdRateFromDb.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
            </div>
          ) : (
            <input
              className="input w-full"
              placeholder="Ej: 5,75"
              value={usdRateStr}
              onChange={e => setUsdRateStr(e.target.value)}
              required={isUsd}
            />
          )}
          {usdRateFromDb == null && (
            <p className="text-xs text-amber-500 mt-1">No hay cotización registrada para este mes. Ingresá el rate manualmente.</p>
          )}
        </div>
      )}

      {/* Monto total calculado */}
      <div>
        <label className="block text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">Monto total</label>
        {isUsd ? (
          <div className="input w-full bg-gray-50 dark:bg-gray-800 font-mono cursor-not-allowed space-y-0.5">
            <div className="text-blue-600 dark:text-blue-400">
              {amountUsd != null
                ? `USD ${amountUsd.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : '—'}
            </div>
            <div className="text-gray-500 dark:text-gray-400 text-xs">
              {amountBrl != null
                ? `≈ R$ ${amountBrl.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : effectiveRate ? '—' : 'ingresá la cotización'}
            </div>
          </div>
        ) : (
          <div className="input w-full bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono cursor-not-allowed">
            {amountBrl != null
              ? amountBrl.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
              : '—'}
          </div>
        )}
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
