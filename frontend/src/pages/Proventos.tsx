import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getProventos, getMonthlyProventos } from '../api/proventos';
import BarChartComp from '../components/charts/BarChartComp';
import { fmtBRL, MONTH_NAMES, INSTRUMENT_TYPE_LABELS } from '../utils/formatters';
import { SkeletonTable } from '../components/ui/SkeletonLoader';
import client from '../api/client';

const MONTH_NAMES_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
const MONTHS = [1,2,3,4,5,6,7,8,9,10,11,12];
const TYPE_OPTIONS = Object.entries(INSTRUMENT_TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }));

function fmtPosDate(d: string | null) {
  if (!d) return null;
  const [year, month] = d.split('-');
  return `${MONTH_NAMES_ES[parseInt(month) - 1]} ${year}`;
}

// ─── Forecast import modal ─────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  matched:   'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300',
  no_match:  'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  ambiguous: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300',
};
const STATUS_LABELS: Record<string, string> = {
  matched: 'Encontrado', no_match: 'Sin match', ambiguous: 'Ambiguo',
};

interface PreviewRow {
  activo_raw: string;
  status: 'matched' | 'no_match' | 'ambiguous';
  instrument_id: number | null;
  instrument_name: string | null;
  match_candidates: { id: number; name: string; ticker: string | null }[];
  months: Record<number, number>;
}

function ForecastImportModal({ year, onClose, onDone }: {
  year: number;
  onClose: () => void;
  onDone: () => void;
}) {
  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [overwrite, setOverwrite] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ year: number; rows: PreviewRow[]; warnings: string[] } | null>(null);
  const [result, setResult] = useState<{ upserted: number; skipped: number } | null>(null);
  // local overrides for ambiguous rows
  const [resolved, setResolved] = useState<Record<number, { id: number; name: string }>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const effectiveRows = (): PreviewRow[] =>
    (preview?.rows ?? []).map((r, i) =>
      resolved[i] ? { ...r, status: 'matched', instrument_id: resolved[i].id, instrument_name: resolved[i].name } : r
    );

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true); setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('year', String(year));
      const res = await client.post('/api/proventos/forecast/import/preview', fd);
      setPreview(res.data);
      setStep('preview');
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'Error desconocido');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    setLoading(true); setError(null);
    try {
      const rows = effectiveRows()
        .filter(r => r.instrument_id && Object.keys(r.months).length > 0)
        .map(r => ({ instrument_id: r.instrument_id, months: r.months }));
      const res = await client.post('/api/proventos/forecast/import/confirm', {
        year: preview.year,
        rows,
        overwrite,
      });
      setResult(res.data);
      setStep('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? 'Error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800">
          <div>
            <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">
              Importar Previsión de Proventos — {year}
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Excel con columnas: Activo, Enero, Febrero, …, Diciembre
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl leading-none">✕</button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error && (
            <div className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          {/* Step: upload */}
          {step === 'upload' && (
            <div className="space-y-5 max-w-md">
              <div
                className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center cursor-pointer hover:border-blue-400 transition-colors"
                onClick={() => fileRef.current?.click()}
              >
                <input ref={fileRef} type="file" accept=".xlsx,.xls" className="hidden"
                  onChange={e => setFile(e.target.files?.[0] ?? null)} />
                {file ? (
                  <div><div className="text-2xl mb-1">📄</div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300">{file.name}</div></div>
                ) : (
                  <div><div className="text-3xl mb-2">📂</div>
                    <div className="text-sm text-gray-400">Clic para seleccionar .xlsx</div></div>
                )}
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 cursor-pointer">
                <input type="checkbox" checked={overwrite} onChange={e => setOverwrite(e.target.checked)} />
                Sobreescribir valores existentes
              </label>
            </div>
          )}

          {/* Step: preview */}
          {step === 'preview' && preview && (() => {
            const rows = effectiveRows();
            const matchedCount = rows.filter(r => r.status === 'matched').length;
            const noMatchCount = rows.filter(r => r.status === 'no_match').length;
            return (
              <div className="space-y-3">
                <div className="flex gap-4 text-sm">
                  <span className="text-green-700 dark:text-green-400 font-medium">✓ {matchedCount} encontrados</span>
                  {noMatchCount > 0 && <span className="text-red-600 dark:text-red-400">✗ {noMatchCount} sin match (serán omitidos)</span>}
                </div>
                {preview.warnings.length > 0 && (
                  <div className="text-xs text-yellow-700 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded px-3 py-2 space-y-0.5">
                    {preview.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                  </div>
                )}
                <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-left">
                        <th className="px-2 py-2">Estado</th>
                        <th className="px-2 py-2">Activo</th>
                        {MONTHS.map(m => (
                          <th key={m} className="px-1.5 py-2 text-center w-14">{MONTH_NAMES_ES[m - 1]}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {rows.map((row, i) => (
                        <tr key={i} className={row.status === 'no_match' ? 'opacity-50' : ''}>
                          <td className="px-2 py-1.5">
                            <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[row.status]}`}>
                              {STATUS_LABELS[row.status]}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 max-w-[160px]">
                            {row.status === 'ambiguous' ? (
                              <div className="flex flex-col gap-0.5">
                                <span className="text-gray-400 italic text-xs truncate">{row.activo_raw}</span>
                                <div className="flex flex-wrap gap-1 mt-0.5">
                                  {row.match_candidates.slice(0, 3).map(c => (
                                    <button key={c.id}
                                      className="text-[10px] bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300 px-1.5 py-0.5 rounded hover:bg-yellow-200"
                                      onClick={() => setResolved(prev => ({ ...prev, [i]: { id: c.id, name: c.name } }))}
                                    >
                                      {c.ticker || c.name.slice(0, 10)}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <span className="truncate block font-medium" title={row.instrument_name ?? row.activo_raw}>
                                {row.instrument_name ?? row.activo_raw}
                              </span>
                            )}
                          </td>
                          {MONTHS.map(m => {
                            const val = row.months[m];
                            return (
                              <td key={m} className="px-1.5 py-1.5 text-center font-mono text-[11px]">
                                {val != null ? (
                                  <span className="text-emerald-600 dark:text-emerald-400">{fmtBRL(val)}</span>
                                ) : (
                                  <span className="text-gray-200 dark:text-gray-700">·</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })()}

          {/* Step: done */}
          {step === 'done' && result && (
            <div className="text-center py-10 space-y-4">
              <div className="text-4xl">✅</div>
              <p className="text-lg font-semibold text-gray-800 dark:text-gray-100">
                {result.upserted} celda{result.upserted !== 1 ? 's' : ''} importada{result.upserted !== 1 ? 's' : ''}
              </p>
              {result.skipped > 0 && (
                <p className="text-sm text-gray-400">{result.skipped} omitida{result.skipped !== 1 ? 's' : ''}</p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={step === 'preview' ? () => setStep('upload') : onClose}
            className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-700"
            disabled={loading}
          >
            {step === 'preview' ? '← Volver' : 'Cerrar'}
          </button>
          {step === 'upload' && (
            <button
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-5 rounded-lg disabled:opacity-50 text-sm"
              disabled={!file || loading}
              onClick={handleUpload}
            >
              {loading ? 'Analizando...' : 'Analizar →'}
            </button>
          )}
          {step === 'preview' && (
            <button
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-5 rounded-lg disabled:opacity-50 text-sm"
              disabled={loading || (preview?.rows ?? []).filter(r => r.instrument_id).length === 0}
              onClick={handleConfirm}
            >
              {loading ? 'Importando...' : 'Confirmar importación →'}
            </button>
          )}
          {step === 'done' && (
            <button
              className="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-5 rounded-lg text-sm"
              onClick={() => { onDone(); onClose(); }}
            >
              Ver previsión actualizada
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Paid proventos grid (editable, same pattern as ForecastTable) ─────────────

function PaidGrid() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [typeFilter, setTypeFilter] = useState('');
  const [gridData, setGridData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<{ instId: number; month: number; value: string } | null>(null);

  const loadGrid = () => {
    setLoading(true);
    client.get('/api/proventos/grid', { params: { year, type: typeFilter || undefined } })
      .then(r => setGridData(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadGrid(); }, [year, typeFilter]);

  const saveCell = async (instId: number, month: number, value: string) => {
    const num = value === '' ? null : parseFloat(value.replace(',', '.'));
    setEditing(null);
    await client.patch(`/api/proventos/grid/${instId}/${year}/${month}`, { amount: num });
    setGridData((prev: any) => {
      if (!prev) return prev;
      const items = prev.items.map((row: any) => {
        if (row.id !== instId) return row;
        const months = { ...row.months, [month]: num || undefined };
        const forecast_months = { ...row.forecast_months, [month]: undefined };
        const total = MONTHS.reduce((s: number, m: number) =>
          s + (months[m] != null ? months[m] : (forecast_months[m] || 0)), 0);
        return { ...row, months, forecast_months, total };
      });
      const month_totals = {
        ...prev.month_totals,
        [month]: items.reduce((s: number, r: any) =>
          s + (r.months[month] != null ? r.months[month] : (r.forecast_months?.[month] || 0)), 0),
      };
      const paid_month_totals = {
        ...prev.paid_month_totals,
        [month]: items.reduce((s: number, r: any) => s + (r.months[month] || 0), 0),
      };
      const grand_total = MONTHS.reduce((s: number, m: number) => s + (month_totals[m] || 0), 0);
      return { ...prev, items, month_totals, paid_month_totals, grand_total };
    });
  };

  if (loading) return <div className="p-5"><SkeletonTable rows={6} /></div>;
  if (!gridData) return null;

  const { items, month_totals, paid_month_totals, grand_total } = gridData;

  return (
    <div className="space-y-0">
      {/* Controls */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 dark:border-gray-800">
        <div className="flex rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
          {[currentYear - 1, currentYear, currentYear + 1].map(y => (
            <button
              key={y}
              onClick={() => setYear(y)}
              className={`px-3 py-1 text-xs font-medium transition-colors ${year === y ? 'bg-indigo-600 text-white' : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'}`}
            >
              {y}
            </button>
          ))}
        </div>
        <select
          className="input text-sm py-1 w-44"
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
        >
          <option value="">Todos los tipos</option>
          {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="text-xs text-slate-400">{items.length} instrumentos</span>
        <span className="ml-auto text-xs text-slate-400 hidden lg:block">
          Clic en una celda para editar · Enter o blur para guardar
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-1.5 border-b border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
          Verde = pagado
        </span>
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400"></span>
          Ámbar* = previsto sin pago registrado
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase sticky left-0 bg-gray-50 dark:bg-gray-800 whitespace-nowrap">Instrumento</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">Tipo</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
              {MONTHS.map(m => (
                <th key={m} className="px-2 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-20">{MONTH_NAMES_ES[m - 1]}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {/* Totals row */}
            <tr className="bg-slate-50 dark:bg-slate-800/70 font-semibold border-b-2 border-gray-200 dark:border-gray-600">
              <td className="px-3 py-2 text-xs text-gray-500 uppercase sticky left-0 bg-slate-50 dark:bg-slate-800">Total</td>
              <td />
              <td className="px-3 py-2 text-right font-mono text-emerald-700 dark:text-emerald-400">
                {fmtBRL(grand_total)}
              </td>
              {MONTHS.map(m => {
                const hasForecasts = paid_month_totals && month_totals[m] > (paid_month_totals[m] || 0);
                return (
                  <td key={m} className={`px-2 py-2 text-center font-mono text-xs ${hasForecasts ? 'text-amber-500 dark:text-amber-400' : 'text-emerald-700 dark:text-emerald-400'}`}>
                    {month_totals[m] ? fmtBRL(month_totals[m]) : '—'}
                  </td>
                );
              })}
            </tr>
            {/* Instrument rows */}
            {items.map((row: any) => (
              <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="px-3 py-1.5 font-medium max-w-[180px] truncate sticky left-0 bg-white dark:bg-gray-900" title={row.name}>
                  {row.name}
                </td>
                <td className="px-3 py-1.5 text-xs text-gray-400 whitespace-nowrap">{INSTRUMENT_TYPE_LABELS[row.type] || row.type}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  {row.total ? fmtBRL(row.total) : '—'}
                </td>
                {MONTHS.map(m => {
                  const isEditing = editing?.instId === row.id && editing?.month === m;
                  const paid = row.months[m];
                  const forecast = row.forecast_months?.[m];
                  return (
                    <td
                      key={m}
                      className="px-1 py-1 text-center cursor-pointer group"
                      onClick={() => {
                        if (isEditing) return;
                        const initialValue = paid != null
                          ? String(paid)
                          : forecast != null
                            ? String(forecast)
                            : '';
                        setEditing({ instId: row.id, month: m, value: initialValue });
                      }}
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          className="w-18 px-1 py-0.5 text-xs text-center border border-indigo-400 rounded font-mono w-full"
                          value={editing.value}
                          onChange={e => setEditing(ed => ed ? { ...ed, value: e.target.value } : ed)}
                          onBlur={() => saveCell(editing.instId, editing.month, editing.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') saveCell(editing.instId, editing.month, editing.value);
                            if (e.key === 'Escape') setEditing(null);
                          }}
                        />
                      ) : paid != null ? (
                        <span className="text-xs font-mono group-hover:underline decoration-dotted text-emerald-600 dark:text-emerald-400">
                          {fmtBRL(paid)}
                        </span>
                      ) : forecast != null ? (
                        <span className="text-xs font-mono group-hover:underline decoration-dotted text-amber-500 dark:text-amber-400 italic">
                          {fmtBRL(forecast)}*
                        </span>
                      ) : (
                        <span className="text-xs font-mono text-gray-200 dark:text-gray-700">·</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">
            No hay instrumentos con pago de proventos activos.
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Forecast table ────────────────────────────────────────────────────────────

function ForecastTable() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear);
  const [typeFilter, setTypeFilter] = useState('');
  const [forecastData, setForecastData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<{ instId: number; month: number; value: string } | null>(null);
  const [showImport, setShowImport] = useState(false);

  const loadForecast = () => {
    setLoading(true);
    client.get('/api/proventos/forecast', { params: { year, type: typeFilter || undefined } })
      .then(r => setForecastData(r.data))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadForecast(); }, [year, typeFilter]);

  const saveCell = async (instId: number, month: number, value: string) => {
    const num = value === '' ? null : parseFloat(value.replace(',', '.'));
    setEditing(null);
    await client.patch(`/api/proventos/forecast/${instId}/${year}/${month}`, { amount: num });
    // Update local state directly
    setForecastData((prev: any) => {
      if (!prev) return prev;
      const items = prev.items.map((row: any) => {
        if (row.id !== instId) return row;
        const months = { ...row.months, [month]: num || undefined };
        const total = MONTHS.reduce((s, m) => s + (months[m] || 0), 0);
        return { ...row, months, total };
      });
      const month_totals = { ...prev.month_totals, [month]: items.reduce((s: number, r: any) => s + (r.months[month] || 0), 0) };
      const grand_total = MONTHS.reduce((s, m) => s + (month_totals[m] || 0), 0);
      return { ...prev, items, month_totals, grand_total };
    });
  };

  if (loading) return (
    <>
      {showImport && <ForecastImportModal year={year} onClose={() => setShowImport(false)} onDone={loadForecast} />}
      <div className="p-5"><SkeletonTable rows={6} /></div>
    </>
  );
  if (!forecastData) return null;

  const { items, month_totals, grand_total } = forecastData;

  return (
    <div className="space-y-0">
      {showImport && <ForecastImportModal year={year} onClose={() => setShowImport(false)} onDone={loadForecast} />}
      {/* Controls */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-100 dark:border-gray-800">
        <div className="flex rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
          {[currentYear - 1, currentYear, currentYear + 1].map(y => (
            <button
              key={y}
              onClick={() => setYear(y)}
              className={`px-3 py-1 text-xs font-medium transition-colors ${year === y ? 'bg-indigo-600 text-white' : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'}`}
            >
              {y}
            </button>
          ))}
        </div>
        <select
          className="input text-sm py-1 w-44"
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
        >
          <option value="">Todos los tipos</option>
          {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="text-xs text-slate-400">{items.length} instrumentos</span>
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-slate-400 hidden lg:block">
            Clic en una celda para editar · Enter o blur para guardar
          </span>
          <button
            className="flex items-center gap-1 text-xs bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg transition-colors font-medium"
            onClick={() => setShowImport(true)}
          >
            ↑ Importar Excel
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase sticky left-0 bg-gray-50 dark:bg-gray-800 whitespace-nowrap">Instrumento</th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">Tipo</th>
              <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
              {MONTHS.map(m => (
                <th key={m} className="px-2 py-2.5 text-center text-xs font-semibold text-gray-500 uppercase w-20">{MONTH_NAMES_ES[m - 1]}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {/* Totals row */}
            <tr className="bg-slate-50 dark:bg-slate-800/70 font-semibold border-b-2 border-gray-200 dark:border-gray-600">
              <td className="px-3 py-2 text-xs text-gray-500 uppercase sticky left-0 bg-slate-50 dark:bg-slate-800">Total</td>
              <td />
              <td className="px-3 py-2 text-right font-mono text-emerald-700 dark:text-emerald-400">
                {fmtBRL(grand_total)}
              </td>
              {MONTHS.map(m => (
                <td key={m} className="px-2 py-2 text-center font-mono text-xs text-emerald-700 dark:text-emerald-400">
                  {month_totals[m] ? fmtBRL(month_totals[m]) : '—'}
                </td>
              ))}
            </tr>
            {/* Instrument rows */}
            {items.map((row: any) => (
              <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="px-3 py-1.5 font-medium max-w-[180px] truncate sticky left-0 bg-white dark:bg-gray-900" title={row.name}>
                  {row.name}
                </td>
                <td className="px-3 py-1.5 text-xs text-gray-400 whitespace-nowrap">{INSTRUMENT_TYPE_LABELS[row.type] || row.type}</td>
                <td className="px-3 py-1.5 text-right font-mono text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  {row.total ? fmtBRL(row.total) : '—'}
                </td>
                {MONTHS.map(m => {
                  const isEditing = editing?.instId === row.id && editing?.month === m;
                  const val = row.months[m];
                  return (
                    <td
                      key={m}
                      className="px-1 py-1 text-center cursor-pointer group"
                      onClick={() => !isEditing && setEditing({ instId: row.id, month: m, value: val != null ? String(val) : '' })}
                    >
                      {isEditing ? (
                        <input
                          autoFocus
                          className="w-18 px-1 py-0.5 text-xs text-center border border-indigo-400 rounded font-mono w-full"
                          value={editing.value}
                          onChange={e => setEditing(ed => ed ? { ...ed, value: e.target.value } : ed)}
                          onBlur={() => saveCell(editing.instId, editing.month, editing.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') saveCell(editing.instId, editing.month, editing.value);
                            if (e.key === 'Escape') setEditing(null);
                          }}
                        />
                      ) : (
                        <span className={`text-xs font-mono group-hover:underline decoration-dotted ${val ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-200 dark:text-gray-700'}`}>
                          {val ? fmtBRL(val) : '·'}
                        </span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="text-center text-sm text-gray-400 py-8">
            No hay instrumentos con pago de proventos activos.
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────────

export default function Proventos() {
  const navigate = useNavigate();
  const [data, setData] = useState<any>({ items: [], years: [], year_totals: {}, balance_total: 0, positions_as_of: null });
  const [monthly, setMonthly] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [soloActivos, setSoloActivos] = useState(true);
  const [tab, setTab] = useState<'historico' | 'mensual' | 'prevision'>('historico');

  useEffect(() => {
    setLoading(true);
    const status = soloActivos ? 'activo' : undefined;
    Promise.all([getProventos(page, 50, status), getMonthlyProventos()])
      .then(([p, m]) => { setData(p); setMonthly(m); })
      .finally(() => setLoading(false));
  }, [page, soloActivos]);

  const monthlyChartData = (monthly?.monthly || []).map((m: any) => ({
    month: MONTH_NAMES[m.month - 1],
    Pagado: m.amount || 0,
    Previsto: m.forecast || 0,
  }));

  const years: number[] = data.years || [];

  return (
    <div className="space-y-5">
      {/* Page header with import button */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">Proventos y Dividendos</h1>
        <button
          className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          onClick={() => navigate('/import/proventos')}
        >
          ↑ Importar Proventos
        </button>
      </div>
      {/* Summary cards */}
      {monthly && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: `Total ${monthly.year}`, value: fmtBRL(monthly.total) },
            { label: `Total ${monthly.year - 1}`, value: fmtBRL(monthly.prev_year_total) },
            { label: 'Proyección Anual', value: fmtBRL(monthly.projection_annual) },
            {
              label: 'Variación vs año anterior',
              value: monthly.prev_year_total
                ? `${(((monthly.projection_annual - monthly.prev_year_total) / monthly.prev_year_total) * 100).toFixed(1)}%`
                : '—',
            },
          ].map(m => (
            <div key={m.label} className="card text-center">
              <p className="text-sm text-gray-500">{m.label}</p>
              <p className="text-xl font-bold mt-1">{m.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Monthly chart */}
      {monthly && (
        <div className="card">
          <h2 className="font-semibold mb-4">Proventos Mensuales {monthly.year}</h2>
          <BarChartComp
            data={monthlyChartData}
            bars={[
              { key: 'Pagado', label: 'Pagado', color: '#10b981' },
              { key: 'Previsto', label: 'Previsto (proyección)', color: '#a7f3d0' },
            ]}
            xKey="month"
            height={220}
            stacked
          />
        </div>
      )}

      {/* Tabs */}
      <div className="card p-0 overflow-hidden">
        {/* Tab bar */}
        <div className="flex items-center border-b border-gray-100 dark:border-gray-800">
          <div className="flex">
            {([
              { key: 'historico', label: 'Histórico' },
              { key: 'mensual', label: 'Pagado mensual' },
              { key: 'prevision', label: 'Previsión' },
            ] as const).map(t => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
                  tab === t.key
                    ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {/* Controls shown only for histórico tab */}
          {tab === 'historico' && (
            <div className="flex items-center gap-3 ml-4 flex-1">
              <label className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="w-4 h-4 accent-blue-600"
                  checked={soloActivos}
                  onChange={e => { setSoloActivos(e.target.checked); setPage(1); }}
                />
                Solo activos
              </label>
              <span className="text-sm text-gray-400">{data.total} instrumentos</span>
              {data.positions_as_of && (
                <span className="ml-auto mr-4 text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 px-2.5 py-1 rounded-full border border-blue-200 dark:border-blue-800">
                  Posiciones al {fmtPosDate(data.positions_as_of)}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Tab content */}
        {tab === 'historico' && (
          <>
            {loading ? (
              <div className="p-5"><SkeletonTable rows={8} /></div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                      <tr>
                        <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase sticky left-0 bg-gray-50 dark:bg-gray-800">Instrumento</th>
                        <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">Tipo</th>
                        <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">Saldo</th>
                        {years.map(y => (
                          <th key={y} className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{y}</th>
                        ))}
                        <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                      <tr className="bg-slate-50 dark:bg-slate-800/70 font-semibold border-b-2 border-gray-200 dark:border-gray-600">
                        <td className="px-3 py-2.5 text-xs text-gray-500 uppercase sticky left-0 bg-slate-50 dark:bg-slate-800">Total</td>
                        <td />
                        <td className="px-3 py-2.5 text-right font-mono text-gray-800 dark:text-gray-200">{fmtBRL(data.balance_total)}</td>
                        {years.map(y => (
                          <td key={y} className="px-3 py-2.5 text-right font-mono text-emerald-700 dark:text-emerald-400">
                            {data.year_totals[y] ? fmtBRL(data.year_totals[y]) : '—'}
                          </td>
                        ))}
                        <td className="px-3 py-2.5 text-right font-mono text-emerald-700 dark:text-emerald-400">
                          {fmtBRL(Object.values(data.year_totals as Record<number, number>).reduce((s, v) => s + (v || 0), 0))}
                        </td>
                      </tr>
                      {data.items.map((row: any) => (
                        <tr key={row.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                          <td className="px-3 py-2.5 font-medium max-w-[160px] truncate sticky left-0 bg-white dark:bg-gray-900" title={row.name}>{row.name}</td>
                          <td className="px-3 py-2.5 text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">{row.type}</td>
                          <td className="px-3 py-2.5 text-right font-mono text-gray-600">{fmtBRL(row.balance_brl)}</td>
                          {years.map(y => (
                            <td key={y} className={`px-3 py-2.5 text-right font-mono ${row.years[y] ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-300 dark:text-gray-600'}`}>
                              {row.years[y] ? fmtBRL(row.years[y]) : '—'}
                            </td>
                          ))}
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-emerald-600 dark:text-emerald-400">{fmtBRL(row.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {data.pages > 1 && (
                  <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
                    <p className="text-sm text-gray-500">Página {page} de {data.pages}</p>
                    <div className="flex gap-2">
                      <button className="btn-secondary text-sm py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
                      <button className="btn-secondary text-sm py-1" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Siguiente →</button>
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {tab === 'mensual' && <PaidGrid />}
        {tab === 'prevision' && <ForecastTable />}
      </div>
    </div>
  );
}
