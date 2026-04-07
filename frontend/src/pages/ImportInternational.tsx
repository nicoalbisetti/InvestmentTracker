import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  InternationalImportConfig,
  InternationalDiffItem,
  DividendDiffItem,
  PreviewResponse,
  ConfirmResponse,
  previewInternational,
  confirmInternational,
  getUsdRateForMonth,
} from '../api/importInternational';
import { fmtBRL, fmtUSD } from '../utils/formatters';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function defaultPeriod(): string {
  const now = new Date();
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}-01`;
}

function positionKey(d: InternationalDiffItem): string {
  return d.cusip || d.symbol || d.descricao;
}

// ─── Step indicator ───────────────────────────────────────────────────────────

function StepBar({ step }: { step: number }) {
  const steps = ['Configuración', 'Preview', 'Resultado'];
  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {steps.map((label, i) => {
        const n = i + 1;
        const active = n === step;
        const done = n < step;
        return (
          <div key={n} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold
                ${done ? 'bg-green-500 text-white' : active ? 'bg-blue-600 text-white' : 'bg-gray-200 dark:bg-gray-700 text-gray-500'}`}>
                {done ? '✓' : n}
              </div>
              <span className={`text-xs mt-1 whitespace-nowrap ${active ? 'text-blue-600 font-semibold' : 'text-gray-400'}`}>{label}</span>
            </div>
            {i < steps.length - 1 && (
              <div className={`w-16 h-0.5 mx-1 mb-5 ${done ? 'bg-green-400' : 'bg-gray-200 dark:bg-gray-700'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Badge helpers ────────────────────────────────────────────────────────────

function MatchBadge({ status }: { status: 'EXACT' | 'MAPPED' | 'NEW' }) {
  const cfg = {
    EXACT: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    MAPPED: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    NEW: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  }[status];
  const label = { EXACT: '✓ Exacto', MAPPED: 'Mapeado', NEW: 'Nuevo' }[status];
  return <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${cfg}`}>{label}</span>;
}

function DiffBadge({ status, willCreateInstrument }: { status: 'NEW' | 'UPDATED' | 'UNCHANGED' | 'DISAPPEARED'; willCreateInstrument?: boolean }) {
  const cfg = {
    NEW: willCreateInstrument
      ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400'
      : 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    UPDATED: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    UNCHANGED: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    DISAPPEARED: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  }[status];
  const label = {
    NEW: willCreateInstrument ? 'Instrumento nuevo' : '1er import',
    UPDATED: 'Actualizado',
    UNCHANGED: 'Sin cambio',
    DISAPPEARED: 'Desaparecido',
  }[status];
  return <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${cfg}`}>{label}</span>;
}

function DupBadge({ status }: { status: 'NEW' | 'DUPLICATE' }) {
  if (status === 'DUPLICATE') {
    return <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">Duplicado</span>;
  }
  return <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">Nuevo</span>;
}

// ─── Step 1: Upload + Config ──────────────────────────────────────────────────

interface Step1Props {
  onNext: (file: File, period: string, rate: number, cfg: InternationalImportConfig) => void;
  loading: boolean;
  error: string | null;
}

function Step1({ onNext, loading, error }: Step1Props) {
  const [file, setFile] = useState<File | null>(null);
  const [period, setPeriod] = useState(defaultPeriod());
  const [rate, setRate] = useState<number | null>(null);
  const [rateDate, setRateDate] = useState<string | null>(null);
  const [rateLoading, setRateLoading] = useState(false);
  const [rateError, setRateError] = useState<string | null>(null);
  const [createNew, setCreateNew] = useState(true);
  const [importPrice, setImportPrice] = useState(true);
  const [importQty, setImportQty] = useState(true);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const month = period.slice(0, 7); // YYYY-MM
    setRate(null);
    setRateDate(null);
    setRateError(null);
    setRateLoading(true);
    getUsdRateForMonth(month)
      .then(({ rate, ref_date }) => { setRate(rate); setRateDate(ref_date); })
      .catch(() => setRateError('No se pudo obtener la cotización'))
      .finally(() => setRateLoading(false));
  }, [period]);

  function handlePeriodChange(val: string) {
    setPeriod(val);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f && f.name.toLowerCase().endsWith('.pdf')) setFile(f);
  }

  function handleSubmit() {
    if (!file) return;
    const rateNum = rate ?? 0;
    const cfg: InternationalImportConfig = {
      usd_brl_rate: rateNum,
      create_new_instruments: createNew,
      import_unit_price: importPrice,
      import_quantities: importQty,
      period_date: period,
    };
    onNext(file, period, rateNum, cfg);
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* File upload */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">Archivo PDF</h2>
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
            ${drag ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/10' : 'border-gray-300 dark:border-gray-600 hover:border-blue-300 hover:bg-gray-50 dark:hover:bg-gray-700/30'}`}
          onDragOver={e => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); }}
          />
          {file ? (
            <div>
              <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
              <button
                className="mt-2 text-xs text-blue-500 hover:underline"
                onClick={e => { e.stopPropagation(); setFile(null); }}
              >Cambiar archivo</button>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-600 dark:text-gray-400">Arrastrá el PDF o hacé click para seleccionar</p>
              <p className="text-xs text-gray-400 mt-1">Solo archivos .pdf de XP International</p>
            </div>
          )}
        </div>
      </div>

      {/* Period + rate */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-4">
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">Período y tipo de cambio</h2>
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Mes del extracto</label>
            <input
              type="month"
              value={period.slice(0, 7)}
              onChange={e => handlePeriodChange(`${e.target.value}-01`)}
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Cotización USD/BRL
            </label>
            <div className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700/50 text-gray-900 dark:text-gray-100 min-h-[38px] flex items-center">
              {rateLoading && <span className="text-gray-400">Buscando...</span>}
              {!rateLoading && rate !== null && (
                <span className="font-mono font-medium">{rate.toFixed(4)}</span>
              )}
              {!rateLoading && rateError && (
                <span className="text-red-500 text-xs">{rateError}</span>
              )}
            </div>
            {rateDate && !rateLoading && (
              <p className="text-xs text-gray-400 mt-1">Último cierre: {rateDate}</p>
            )}
          </div>
        </div>
      </div>

      {/* Options */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 space-y-3">
        <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">Opciones</h2>
        {[
          { label: 'Crear instrumentos nuevos automáticamente', value: createNew, set: setCreateNew, tip: 'Los instrumentos sin match se crearán automáticamente' },
          { label: 'Importar precios unitarios', value: importPrice, set: setImportPrice, tip: '' },
          { label: 'Importar cantidades', value: importQty, set: setImportQty, tip: '' },
        ].map(({ label, value, set, tip }) => (
          <label key={label} className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={value}
              onChange={e => set(e.target.checked)}
              className="mt-0.5 rounded"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {label}
              {tip && <span className="block text-xs text-gray-400">{tip}</span>}
            </span>
          </label>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!file || loading}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white font-semibold rounded-xl transition-colors"
      >
        {loading ? 'Procesando PDF...' : 'Siguiente →'}
      </button>
    </div>
  );
}

// ─── Step 2: Preview ──────────────────────────────────────────────────────────

interface Step2Props {
  preview: PreviewResponse;
  onConfirm: (
    skipKeys: string[],
    skipDivIndices: number[],
    finalRate: number,
  ) => void;
  loading: boolean;
  error: string | null;
}

function Step2({ preview, onConfirm, loading, error }: Step2Props) {
  const [activeTab, setActiveTab] = useState<'positions' | 'dividends'>('positions');
  const [skippedKeys, setSkippedKeys] = useState<Set<string>>(new Set());
  const [skippedDivIdx, setSkippedDivIdx] = useState<Set<number>>(new Set());
  const [finalRate, setFinalRate] = useState<string>(
    String(preview.usd_brl_rate_suggested ?? '')
  );

  function togglePosition(key: string) {
    setSkippedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleDiv(idx: number) {
    setSkippedDivIdx(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  }

  const rate = parseFloat(finalRate) || 0;
  const { positions_summary: ps, dividends_summary: ds } = preview;

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      {/* Rate edit */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex flex-wrap items-center gap-6">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Tipo de cambio USD/BRL (ajustable)</label>
          <input
            type="number"
            step="0.001"
            value={finalRate}
            onChange={e => setFinalRate(e.target.value)}
            className="w-36 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
          />
        </div>
        {preview.usd_brl_rate_suggested && (
          <p className="text-xs text-gray-400">Sugerido por yfinance: {preview.usd_brl_rate_suggested.toFixed(4)}</p>
        )}
        {preview.account_number && (
          <p className="text-xs text-gray-400">Cuenta: <span className="font-mono font-medium">{preview.account_number}</span></p>
        )}
        {preview.period_end && (
          <p className="text-xs text-gray-400">Período fin: {preview.period_end}</p>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total USD', value: fmtUSD(ps.total_usd) },
          { label: 'Total BRL', value: fmtBRL(ps.total_usd * rate) },
          { label: 'Posiciones', value: `${ps.total_in_pdf}` },
          { label: 'Dividendos nuevos', value: `${ds.new}` },
        ].map(c => (
          <div key={c.label} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <p className="text-xs text-gray-500 dark:text-gray-400">{c.label}</p>
            <p className="text-lg font-bold text-gray-900 dark:text-gray-100 mt-0.5">{c.value}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveTab('positions')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === 'positions'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
          }`}
        >
          Posiciones ({ps.total_in_pdf})
        </button>
        <button
          onClick={() => setActiveTab('dividends')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
            activeTab === 'dividends'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400'
          }`}
        >
          Dividendos ({ds.total_in_pdf})
        </button>
      </div>

      {/* Positions tab */}
      {activeTab === 'positions' && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 dark:bg-gray-700/50">
                <tr>
                  <th className="px-2 py-2 text-left w-8"></th>
                  <th className="px-3 py-2 text-left">Instrumento</th>
                  <th className="px-3 py-2 text-left">Tipo</th>
                  <th className="px-3 py-2 text-right">Cantidad</th>
                  <th className="px-3 py-2 text-right">Precio USD</th>
                  <th className="px-3 py-2 text-right">Valor USD</th>
                  <th className="px-3 py-2 text-right">Valor BRL</th>
                  <th className="px-3 py-2 text-center">Match</th>
                  <th className="px-3 py-2 text-center">Status</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {preview.position_diffs.map((d) => {
                  const key = positionKey(d);
                  const skipped = skippedKeys.has(key);
                  return (
                    <tr
                      key={key}
                      className={`transition-colors ${skipped ? 'opacity-40' : 'hover:bg-gray-50 dark:hover:bg-gray-700/30'}`}
                    >
                      <td className="px-2 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={!skipped}
                          onChange={() => togglePosition(key)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-[200px]" title={d.descricao}>
                          {d.symbol || d.cusip || d.descricao.slice(0, 30)}
                        </p>
                        <p className="text-gray-400 truncate max-w-[200px]">{d.issuer}</p>
                      </td>
                      <td className="px-3 py-2 text-gray-500">{d.asset_class}</td>
                      <td className="px-3 py-2 text-right font-mono">{d.quantidade.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtUSD(d.preco_usd)}</td>
                      <td className="px-3 py-2 text-right font-mono font-medium">{fmtUSD(d.posicao_usd)}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtBRL(d.posicao_usd * rate)}</td>
                      <td className="px-3 py-2 text-center"><MatchBadge status={d.match_status} /></td>
                      <td className="px-3 py-2 text-center"><DiffBadge status={d.diff_status} willCreateInstrument={d.will_create_instrument} /></td>
                      <td className="px-2 py-2 text-center">
                        {d.warnings.length > 0 && (
                          <span title={d.warnings.join('\n')} className="text-yellow-500 cursor-help">⚠</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-700/30 border-t border-gray-100 dark:border-gray-700 flex gap-4 text-xs text-gray-500">
            <span>Nuevos: {ps.new}</span>
            <span>Actualizados: {ps.updated}</span>
            <span>Sin cambio: {ps.unchanged}</span>
            <span>Instrumentos nuevos: {ps.new_instruments}</span>
          </div>
        </div>
      )}

      {/* Dividends tab */}
      {activeTab === 'dividends' && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 dark:bg-gray-700/50">
                <tr>
                  <th className="px-2 py-2 text-left w-8"></th>
                  <th className="px-3 py-2 text-left">Fecha pago</th>
                  <th className="px-3 py-2 text-left">Instrumento</th>
                  <th className="px-3 py-2 text-right">Div/share</th>
                  <th className="px-3 py-2 text-right">Shares</th>
                  <th className="px-3 py-2 text-right">Neto USD</th>
                  <th className="px-3 py-2 text-right">Neto BRL</th>
                  <th className="px-3 py-2 text-right">WHT %</th>
                  <th className="px-3 py-2 text-center">Match</th>
                  <th className="px-3 py-2 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {preview.dividend_diffs.map((d, i) => {
                  const isDup = d.dup_status === 'DUPLICATE';
                  const skipped = skippedDivIdx.has(i);
                  return (
                    <tr
                      key={i}
                      className={`transition-colors ${isDup || skipped ? 'opacity-40' : 'hover:bg-gray-50 dark:hover:bg-gray-700/30'}`}
                    >
                      <td className="px-2 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={!isDup && !skipped}
                          disabled={isDup}
                          onChange={() => toggleDiv(i)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-3 py-2 font-mono">{d.pay_date}</td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {d.symbol || d.cusip || '—'}
                        </p>
                        {d.instrument_name_bd && (
                          <p className="text-gray-400">{d.instrument_name_bd}</p>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right font-mono">${d.dividend_per_share.toFixed(4)}</td>
                      <td className="px-3 py-2 text-right font-mono">{d.shares}</td>
                      <td className="px-3 py-2 text-right font-mono font-medium">{fmtUSD(d.valor_liquido_usd)}</td>
                      <td className="px-3 py-2 text-right font-mono">{fmtBRL(d.valor_liquido_usd * rate)}</td>
                      <td className="px-3 py-2 text-right">{(d.withholding_rate * 100).toFixed(0)}%</td>
                      <td className="px-3 py-2 text-center"><MatchBadge status={d.match_status} /></td>
                      <td className="px-3 py-2 text-center">
                        <DupBadge status={d.dup_status} />
                        {isDup && <span className="ml-1 text-gray-400" title="Ya existe en la BD del período">ℹ</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-700/30 border-t border-gray-100 dark:border-gray-700 flex gap-4 text-xs text-gray-500">
            <span>Nuevos: {ds.new}</span>
            <span>Duplicados: {ds.duplicates}</span>
            <span>Total neto: {fmtUSD(ds.total_usd_neto)}</span>
          </div>
        </div>
      )}

      {preview.parse_warnings.length > 0 && (
        <div className="bg-yellow-50 dark:bg-yellow-900/10 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 text-xs text-yellow-800 dark:text-yellow-400 space-y-1">
          <p className="font-semibold">Advertencias del parser:</p>
          {preview.parse_warnings.map((w, i) => <p key={i}>• {w}</p>)}
        </div>
      )}

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      <button
        onClick={() => onConfirm(Array.from(skippedKeys), Array.from(skippedDivIdx), rate)}
        disabled={loading || !rate}
        className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white font-semibold rounded-xl transition-colors"
      >
        {loading ? 'Importando...' : 'Confirmar importación'}
      </button>
    </div>
  );
}

// ─── Step 3: Result ───────────────────────────────────────────────────────────

function Step3({ result, onReset }: { result: ConfirmResponse; onReset: () => void }) {
  const navigate = useNavigate();
  const { positions_imported: pi, dividends_imported: di } = result;
  const hasUnassigned = false; // extend if needed

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-base font-semibold text-green-600 dark:text-green-400 mb-4">Importación completada</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-green-50 dark:bg-green-900/10 rounded-lg p-4">
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Posiciones</p>
            <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
              <li>Instrumentos nuevos: <span className="font-bold">{pi.new_instruments}</span></li>
              <li>Posiciones nuevas: <span className="font-bold">{pi.new_positions}</span></li>
              <li>Posiciones actualizadas: <span className="font-bold">{pi.updated_positions}</span></li>
              <li>Omitidas: <span className="font-bold">{pi.skipped}</span></li>
            </ul>
          </div>
          <div className="bg-green-50 dark:bg-green-900/10 rounded-lg p-4">
            <p className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Dividendos</p>
            <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
              <li>Nuevos: <span className="font-bold">{di.created}</span></li>
              <li>Duplicados omitidos: <span className="font-bold">{di.skipped_duplicates}</span></li>
              <li>Omitidos manualmente: <span className="font-bold">{di.skipped_manual}</span></li>
            </ul>
          </div>
        </div>
        {result.warnings.length > 0 && (
          <div className="mt-4 text-xs text-yellow-600 space-y-1">
            {result.warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
          </div>
        )}
        {hasUnassigned && (
          <p className="mt-4 text-xs text-yellow-600">
            ⚠ Algunos instrumentos quedaron sin asignar. Podés asignarlos desde Configuración.
          </p>
        )}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => navigate('/positions?custodian=XP_INTERNATIONAL')}
          className="flex-1 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl transition-colors text-sm"
        >
          Ver Posiciones XP International
        </button>
        <button
          onClick={onReset}
          className="flex-1 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-semibold rounded-xl transition-colors text-sm"
        >
          Importar otro archivo
        </button>
      </div>
    </div>
  );
}

// ─── Main wizard ──────────────────────────────────────────────────────────────

export default function ImportInternational() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [result, setResult] = useState<ConfirmResponse | null>(null);
  const configRef = useRef<InternationalImportConfig | null>(null);

  async function handleStep1(file: File, period: string, rate: number, cfg: InternationalImportConfig) {
    setLoading(true);
    setError(null);
    try {
      const res = await previewInternational(file, period, cfg);
      // Auto-populate rate from suggestion if user left 0
      if (!cfg.usd_brl_rate && res.usd_brl_rate_suggested) {
        cfg.usd_brl_rate = res.usd_brl_rate_suggested;
      }
      configRef.current = cfg;
      setPreview(res);
      setStep(2);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Error al procesar el PDF');
    } finally {
      setLoading(false);
    }
  }

  async function handleStep2(skipKeys: string[], skipDivIdx: number[], finalRate: number) {
    if (!preview || !configRef.current) return;
    setLoading(true);
    setError(null);
    try {
      const cfg: InternationalImportConfig = { ...configRef.current, usd_brl_rate: finalRate };
      const res = await confirmInternational({
        file_token: preview.file_token,
        config: cfg,
        skip_cusips: skipKeys,
        skip_dividend_indices: skipDivIdx,
        manual_mappings: [],
      });
      setResult(res);
      setStep(3);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Error al confirmar la importación');
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setStep(1);
    setPreview(null);
    setResult(null);
    setError(null);
    configRef.current = null;
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">Importar — XP International</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Importar posiciones y dividendos desde el extracto mensual PDF</p>
      </div>

      <StepBar step={step} />

      {step === 1 && <Step1 onNext={handleStep1} loading={loading} error={error} />}
      {step === 2 && preview && (
        <Step2
          preview={preview}
          onConfirm={handleStep2}
          loading={loading}
          error={error}
        />
      )}
      {step === 3 && result && <Step3 result={result} onReset={reset} />}
    </div>
  );
}
