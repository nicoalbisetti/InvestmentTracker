import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  DiffItem, PreviewResponse, ImportResult,
  previewImport, confirmImport, mapInstrument, revertBatch,
} from '../api/importProventos';
import { getInstruments } from '../api/instruments';
import { fmtBRL } from '../utils/formatters';

// ─── Types ────────────────────────────────────────────────────────────────────

interface InstrumentOption {
  id: number;
  name: string;
  ticker: string | null;
  type: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  NEW: 'Nuevo',
  DUPLICATE: 'Duplicado',
  CONFLICT: 'Conflicto',
  NO_MATCH: 'Sin match',
  AMBIGUOUS_MATCH: 'Ambiguo',
};

const STATUS_COLORS: Record<string, string> = {
  NEW: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  DUPLICATE: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
  CONFLICT: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300',
  NO_MATCH: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  AMBIGUOUS_MATCH: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
};

const ROW_BG: Record<string, string> = {
  NEW: '',
  DUPLICATE: 'bg-gray-50 dark:bg-gray-800/50 opacity-70',
  CONFLICT: 'bg-orange-50 dark:bg-orange-900/10',
  NO_MATCH: 'bg-red-50 dark:bg-red-900/10',
  AMBIGUOUS_MATCH: 'bg-yellow-50 dark:bg-yellow-900/10',
};

function fmtDate(iso: string): string {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function fmtNum(v: number | null | undefined, dec = 2): string {
  if (v == null) return '—';
  return v.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

// ─── Step bar ─────────────────────────────────────────────────────────────────

function StepBar({ step }: { step: number }) {
  const steps = ['Upload', 'Preview', 'Resultado'];
  return (
    <div className="flex items-center justify-center gap-0 mb-8">
      {steps.map((label, i) => {
        const n = i + 1;
        const done = n < step;
        const active = n === step;
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

// ─── Instrument search mini-selector ─────────────────────────────────────────

function InstrumentPicker({
  onSelect,
  onCancel,
}: {
  onSelect: (id: number, name: string) => void;
  onCancel: () => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<InstrumentOption[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); return; }
    setLoading(true);
    try {
      const data = await getInstruments({ search: q, limit: 15 });
      setResults(data.items ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="absolute z-50 mt-1 w-96 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl p-3">
      <input
        autoFocus
        className="w-full border border-gray-300 dark:border-gray-600 rounded px-2 py-1.5 text-sm bg-white dark:bg-gray-900 dark:text-white mb-2"
        placeholder="Buscar instrumento..."
        value={query}
        onChange={e => { setQuery(e.target.value); search(e.target.value); }}
      />
      {loading && <div className="text-xs text-gray-400 py-1">Buscando...</div>}
      <div className="max-h-48 overflow-y-auto">
        {results.map(r => (
          <button
            key={r.id}
            className="w-full text-left px-2 py-1.5 text-sm hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
            onClick={() => onSelect(r.id, r.name)}
          >
            <span className="font-medium">{r.ticker || r.name}</span>
            <span className="text-gray-400 ml-2 text-xs truncate">{r.name}</span>
          </button>
        ))}
        {!loading && query.length >= 2 && results.length === 0 && (
          <div className="text-xs text-gray-400 py-1">Sin resultados</div>
        )}
      </div>
      <button className="text-xs text-gray-400 mt-2 hover:text-gray-600" onClick={onCancel}>Cancelar</button>
    </div>
  );
}

// ─── Step 1: Upload ────────────────────────────────────────────────────────────

const MONTH_NAMES_ES = [
  'Enero','Febrero','Marzo','Abril','Mayo','Junio',
  'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre',
];

function defaultPeriod(): { month: number; year: number } {
  const d = new Date();
  // Default to previous month
  const prev = new Date(d.getFullYear(), d.getMonth() - 1, 1);
  return { month: prev.getMonth() + 1, year: prev.getFullYear() };
}

function Step1({
  onSubmit,
  loading,
}: {
  onSubmit: (file: File, periodLabel: string, forceOverwrite: boolean) => void;
  loading: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const { month: defMonth, year: defYear } = defaultPeriod();
  const [periodMonth, setPeriodMonth] = useState(defMonth);
  const [periodYear, setPeriodYear] = useState(defYear);
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const periodLabel = `${MONTH_NAMES_ES[periodMonth - 1]} ${periodYear}`;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) setFile(f);
  };

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Archivo Excel</label>
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${dragOver ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'}`}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden"
            onChange={e => setFile(e.target.files?.[0] ?? null)} />
          {file ? (
            <div>
              <div className="text-2xl mb-1">📄</div>
              <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{file.name}</div>
              <div className="text-xs text-gray-400">{(file.size / 1024).toFixed(1)} KB</div>
            </div>
          ) : (
            <div>
              <div className="text-3xl mb-2">📂</div>
              <div className="text-sm text-gray-500">Arrastrá o hacé click para seleccionar el archivo .xlsx</div>
            </div>
          )}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Período</label>
        <div className="flex gap-2">
          <select
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-900 dark:text-white"
            value={periodMonth}
            onChange={e => setPeriodMonth(Number(e.target.value))}
          >
            {MONTH_NAMES_ES.map((name, i) => (
              <option key={i + 1} value={i + 1}>{name}</option>
            ))}
          </select>
          <select
            className="w-28 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-900 dark:text-white"
            value={periodYear}
            onChange={e => setPeriodYear(Number(e.target.value))}
          >
            {[periodYear - 1, periodYear, periodYear + 1].map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            className="mt-0.5"
            checked={forceOverwrite}
            onChange={e => setForceOverwrite(e.target.checked)}
          />
          <div>
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">Sobreescribir proventos duplicados si el monto cambió</div>
            <div className="text-xs text-gray-400 mt-0.5">Marcar si estás reimportando un mes corregido.</div>
          </div>
        </label>
      </div>

      <button
        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2.5 px-4 rounded-lg disabled:opacity-50 transition-colors"
        disabled={!file || loading}
        onClick={() => file && onSubmit(file, periodLabel, forceOverwrite)}
      >
        {loading ? 'Analizando...' : 'Analizar proventos →'}
      </button>
    </div>
  );
}

// ─── Step 2: Preview ──────────────────────────────────────────────────────────

function Step2({
  preview,
  forceOverwrite,
  fileToken,
  onConfirm,
  onBack,
  loading,
}: {
  preview: PreviewResponse;
  forceOverwrite: boolean;
  fileToken: string;
  onConfirm: (skipIndices: number[], manualMappings: { index: number; instrument_id: number }[]) => void;
  onBack: () => void;
  loading: boolean;
}) {
  const { summary, differences, parse_warnings } = preview;

  // Track which items are selected (checked = will be imported)
  const [checked, setChecked] = useState<Record<number, boolean>>(() => {
    const init: Record<number, boolean> = {};
    for (const item of differences) {
      init[item.index] = item.status === 'NEW' || item.status === 'AMBIGUOUS_MATCH';
    }
    return init;
  });

  // Track manual mappings: index → {instrument_id, name}
  const [manualMappings, setManualMappings] = useState<Record<number, { id: number; name: string }>>({});
  const [pickerFor, setPickerFor] = useState<number | null>(null);

  // Track local overrides for AMBIGUOUS items resolved by user
  const [resolvedItems, setResolvedItems] = useState<Record<number, DiffItem>>({});
  const [warningsOpen, setWarningsOpen] = useState(false);

  const effectiveItem = (item: DiffItem): DiffItem => resolvedItems[item.index] ?? item;

  const totalSelected = differences
    .filter(i => checked[i.index])
    .reduce((s, i) => s + i.amount_brl, 0);

  const selectedCount = Object.values(checked).filter(Boolean).length;

  const handleConfirm = () => {
    const skipIndices = differences
      .filter(i => !checked[i.index])
      .map(i => i.index);
    const mappings = Object.entries(manualMappings).map(([idx, v]) => ({
      index: Number(idx),
      instrument_id: v.id,
    }));
    onConfirm(skipIndices, mappings);
  };

  const handleAssign = (index: number, instId: number, instName: string) => {
    setManualMappings(prev => ({ ...prev, [index]: { id: instId, name: instName } }));
    setResolvedItems(prev => {
      const base = differences.find(i => i.index === index);
      if (!base) return prev;
      return {
        ...prev,
        [index]: { ...base, status: 'NEW', instrument_id: instId, instrument_name: instName },
      };
    });
    setChecked(prev => ({ ...prev, [index]: true }));
    setPickerFor(null);
    // Also notify backend
    mapInstrument(fileToken, index, instId).catch(() => {});
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            Proventos Recibidos{preview.period_label ? ` — ${preview.period_label}` : ''}
          </h2>
          <div className="text-sm text-gray-500 mt-0.5">
            {summary.total_in_file} proventos &nbsp;|&nbsp;
            Total: <strong>{fmtBRL(summary.total_amount_brl)}</strong>
            &nbsp;
            {summary.total_validated
              ? <span className="text-green-600">✅ Total validado</span>
              : <span className="text-orange-500">⚠️ Total no coincide</span>}
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-5 gap-2 text-sm">
        {[
          { label: 'Nuevos', count: summary.new, color: 'text-green-700 dark:text-green-400' },
          { label: 'Duplicados', count: summary.duplicates, color: 'text-gray-500' },
          { label: 'Conflictos', count: summary.conflicts, color: 'text-orange-600' },
          { label: 'Sin match', count: summary.no_match, color: 'text-red-600' },
          { label: 'Ambiguos', count: summary.ambiguous_match, color: 'text-yellow-600' },
        ].map(({ label, count, color }) => (
          <div key={label} className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center border border-gray-100 dark:border-gray-700">
            <div className={`text-xl font-bold ${color}`}>{count}</div>
            <div className="text-xs text-gray-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Warnings */}
      {parse_warnings.length > 0 && (
        <div className="border border-yellow-200 dark:border-yellow-700 rounded-lg overflow-hidden">
          <button
            className="w-full text-left px-3 py-2 bg-yellow-50 dark:bg-yellow-900/20 text-xs font-medium text-yellow-800 dark:text-yellow-300 flex justify-between items-center"
            onClick={() => setWarningsOpen(v => !v)}
          >
            ⚠️ {parse_warnings.length} advertencia{parse_warnings.length > 1 ? 's' : ''} del parser
            <span>{warningsOpen ? '▲' : '▼'}</span>
          </button>
          {warningsOpen && (
            <ul className="px-3 py-2 space-y-1">
              {parse_warnings.map((w, i) => (
                <li key={i} className="text-xs text-yellow-700 dark:text-yellow-400">• {w}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-left">
              <th className="px-2 py-2 w-8">
                <input type="checkbox"
                  checked={selectedCount === differences.length}
                  onChange={e => {
                    const v = e.target.checked;
                    setChecked(Object.fromEntries(differences.map(i => [i.index, v])));
                  }}
                />
              </th>
              <th className="px-2 py-2">Estado</th>
              <th className="px-2 py-2">Fecha</th>
              <th className="px-2 py-2">Instrumento</th>
              <th className="px-2 py-2">Tipo</th>
              <th className="px-2 py-2 text-right">Cantidad</th>
              <th className="px-2 py-2 text-right">P. Unit</th>
              <th className="px-2 py-2 text-right font-semibold">Valor</th>
              <th className="px-2 py-2">Custodia</th>
              <th className="px-2 py-2">Acción</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {differences.map(rawItem => {
              const item = effectiveItem(rawItem);
              return (
                <tr key={item.index} className={`${ROW_BG[item.status]} transition-colors`}>
                  <td className="px-2 py-2">
                    <input
                      type="checkbox"
                      checked={!!checked[item.index]}
                      onChange={e => setChecked(prev => ({ ...prev, [item.index]: e.target.checked }))}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[item.status]}`}>
                      {STATUS_LABELS[item.status]}
                    </span>
                  </td>
                  <td className="px-2 py-2 whitespace-nowrap">{fmtDate(item.fecha_pago)}</td>
                  <td className="px-2 py-2 max-w-[180px]">
                    {item.instrument_name ? (
                      <div>
                        <div className="font-medium truncate">{item.instrument_ticker || item.instrument_name}</div>
                        <div className="text-gray-400 truncate">{item.instrument_ticker ? item.instrument_name : ''}</div>
                      </div>
                    ) : (
                      <span className="text-gray-400 italic truncate block max-w-[160px]" title={item.produto_raw}>
                        {item.produto_raw.length > 30 ? item.produto_raw.slice(0, 30) + '…' : item.produto_raw}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-2">
                    <span className={`text-xs ${item.type === 'jcp' ? 'text-blue-600 dark:text-blue-400' : 'text-green-600 dark:text-green-400'}`}>
                      {item.type === 'jcp' ? 'JCP' : 'Rend.'}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-right font-mono">{fmtNum(item.cantidad, 0)}</td>
                  <td className="px-2 py-2 text-right font-mono">{item.precio_unitario != null ? fmtNum(item.precio_unitario, 4) : '—'}</td>
                  <td className="px-2 py-2 text-right font-semibold font-mono">
                    {fmtBRL(item.amount_brl)}
                    {item.status === 'CONFLICT' && item.existing_amount_brl != null && (
                      <div className="text-[10px] text-orange-500 font-normal">BD: {fmtBRL(item.existing_amount_brl)}</div>
                    )}
                  </td>
                  <td className="px-2 py-2 text-gray-500">{item.custodian}</td>
                  <td className="px-2 py-2 relative">
                    {item.status === 'NO_MATCH' && pickerFor !== item.index && (
                      <button
                        className="text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 px-2 py-0.5 rounded hover:bg-red-200 dark:hover:bg-red-900/60 whitespace-nowrap"
                        onClick={() => setPickerFor(item.index)}
                      >
                        Asignar
                      </button>
                    )}
                    {item.status === 'AMBIGUOUS_MATCH' && pickerFor !== item.index && (
                      <div className="flex flex-col gap-0.5">
                        {item.match_candidates.slice(0, 3).map(c => (
                          <button
                            key={c.id}
                            className="text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 px-1.5 py-0.5 rounded hover:bg-yellow-200 text-left"
                            onClick={() => handleAssign(item.index, c.id, c.name)}
                          >
                            {c.ticker || c.name.slice(0, 12)}
                          </button>
                        ))}
                        <button
                          className="text-xs text-gray-400 hover:text-gray-600"
                          onClick={() => setPickerFor(item.index)}
                        >
                          Buscar otro…
                        </button>
                      </div>
                    )}
                    {pickerFor === item.index && (
                      <InstrumentPicker
                        onSelect={(id, name) => handleAssign(item.index, id, name)}
                        onCancel={() => setPickerFor(null)}
                      />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-2">
        <button
          className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700"
          onClick={onBack}
          disabled={loading}
        >
          ← Volver
        </button>
        <button
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg disabled:opacity-50 transition-colors"
          disabled={selectedCount === 0 || loading}
          onClick={handleConfirm}
        >
          {loading
            ? 'Importando...'
            : `Importar seleccionados (${selectedCount} / ${fmtBRL(totalSelected)}) →`}
        </button>
      </div>
    </div>
  );
}

// ─── Step 3: Result ───────────────────────────────────────────────────────────

function Step3({
  result,
  periodLabel,
  onRestart,
}: {
  result: ImportResult;
  periodLabel: string;
  onRestart: () => void;
}) {
  const navigate = useNavigate();
  const [reverting, setReverting] = useState(false);
  const [reverted, setReverted] = useState(false);
  const [confirmRevert, setConfirmRevert] = useState(false);

  const totalImported = result.imported.new + result.imported.overwritten;

  const handleRevert = async () => {
    setReverting(true);
    try {
      await revertBatch(result.batch_id);
      setReverted(true);
    } finally {
      setReverting(false);
      setConfirmRevert(false);
    }
  };

  if (reverted) {
    return (
      <div className="text-center py-12 space-y-4">
        <div className="text-4xl">↩️</div>
        <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-200">Importación revertida</h2>
        <p className="text-sm text-gray-500">Los proventos importados fueron eliminados.</p>
        <button className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg" onClick={onRestart}>
          Importar otro archivo
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto text-center space-y-6 py-8">
      <div className="text-5xl">✅</div>
      <h2 className="text-xl font-bold text-gray-800 dark:text-gray-100">
        {totalImported} provento{totalImported !== 1 ? 's' : ''} importado{totalImported !== 1 ? 's' : ''}
        &nbsp;— {fmtBRL(result.total_amount_imported)}
      </h2>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
          <div className="text-2xl font-bold text-green-700 dark:text-green-400">{result.imported.new}</div>
          <div className="text-xs text-gray-500 mt-1">Nuevos</div>
        </div>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
          <div className="text-2xl font-bold text-gray-500">{result.skipped.duplicates}</div>
          <div className="text-xs text-gray-500 mt-1">Omitidos</div>
        </div>
        <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
          <div className="text-2xl font-bold text-red-600 dark:text-red-400">{result.skipped.no_match}</div>
          <div className="text-xs text-gray-500 mt-1">Sin match</div>
        </div>
      </div>

      {result.skipped.no_match > 0 && (
        <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700 rounded-lg p-4 text-sm text-left">
          <p className="font-medium text-orange-700 dark:text-orange-300">
            ⚠️ {result.skipped.no_match} provento{result.skipped.no_match > 1 ? 's' : ''} no pudo importarse por falta de instrumento.
          </p>
        </div>
      )}

      {result.warnings.length > 0 && (
        <ul className="text-xs text-left text-yellow-700 dark:text-yellow-400 space-y-1 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg p-3">
          {result.warnings.map((w, i) => <li key={i}>• {w}</li>)}
        </ul>
      )}

      <div className="flex flex-col gap-3">
        <button
          className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg"
          onClick={() => navigate('/proventos')}
        >
          Ver proventos del período
        </button>
        <button
          className="border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 py-2 px-6 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800"
          onClick={onRestart}
        >
          Importar otro archivo
        </button>
      </div>

      {/* Revert link */}
      {!confirmRevert && (
        <button
          className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 mt-2"
          onClick={() => setConfirmRevert(true)}
        >
          Revertir esta importación
        </button>
      )}
      {confirmRevert && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg p-3 text-sm">
          <p className="text-red-700 dark:text-red-300 mb-2">¿Confirmar reversión? Se eliminarán {totalImported} proventos.</p>
          <div className="flex gap-2 justify-center">
            <button
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-1.5 rounded-lg text-xs font-medium disabled:opacity-50"
              onClick={handleRevert}
              disabled={reverting}
            >
              {reverting ? 'Revirtiendo...' : 'Sí, revertir'}
            </button>
            <button
              className="border border-gray-300 dark:border-gray-600 px-4 py-1.5 rounded-lg text-xs text-gray-600 dark:text-gray-300"
              onClick={() => setConfirmRevert(false)}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main wizard ──────────────────────────────────────────────────────────────

export default function ImportProventos() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  const handleUpload = async (file: File, periodLabel: string, force: boolean) => {
    setLoading(true);
    setError(null);
    setForceOverwrite(force);
    try {
      const data = await previewImport(file, periodLabel);
      setPreview(data);
      setStep(2);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Error desconocido';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async (skipIndices: number[], manualMappings: { index: number; instrument_id: number }[]) => {
    if (!preview) return;
    setLoading(true);
    setError(null);
    try {
      const data = await confirmImport(
        preview.file_token,
        preview.period_label,
        forceOverwrite,
        skipIndices,
        manualMappings,
      );
      setResult(data);
      setStep(3);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Error desconocido';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const handleRestart = () => {
    setStep(1);
    setPreview(null);
    setResult(null);
    setError(null);
    setForceOverwrite(false);
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">Importar Proventos</h1>
        <p className="text-sm text-gray-500 mt-1">Desde la hoja "Proventos Recebidos" del reporte mensual XP/Santander</p>
      </div>

      <StepBar step={step} />

      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {step === 1 && <Step1 onSubmit={handleUpload} loading={loading} />}
      {step === 2 && preview && (
        <Step2
          preview={preview}
          forceOverwrite={forceOverwrite}
          fileToken={preview.file_token}
          onConfirm={handleConfirm}
          onBack={() => setStep(1)}
          loading={loading}
        />
      )}
      {step === 3 && result && (
        <Step3
          result={result}
          periodLabel={preview?.period_label ?? ''}
          onRestart={handleRestart}
        />
      )}
    </div>
  );
}
