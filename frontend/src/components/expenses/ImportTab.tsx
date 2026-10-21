import { useCallback, useEffect, useRef, useState } from 'react';
import {
  apiErrorDetail, Batch, confirmImport, deleteImport, ExpAccount, getAccounts, getCategories, getImports, uploadImport, ExpCategory,
} from '../../api/expenses';
import { fmtDate } from '../../utils/formatters';
import { fmtMoney, KIND_LABELS, PARSER_LABELS } from '../../utils/expenses';

interface Need { message: string; candidates?: { id: number; name: string }[]; needsDueDate?: boolean }

export default function ImportTab() {
  const [accounts, setAccounts] = useState<ExpAccount[]>([]);
  const [categories, setCategories] = useState<ExpCategory[]>([]);
  const [history, setHistory] = useState<Batch[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [accountId, setAccountId] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [need, setNeed] = useState<Need | null>(null);
  const [preview, setPreview] = useState<Batch | null>(null);
  const [force, setForce] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const input = useRef<HTMLInputElement>(null);

  const loadHistory = useCallback(() => { getImports().then(setHistory).catch(() => {}); }, []);
  useEffect(() => {
    getAccounts().then(setAccounts).catch(() => {}); getCategories().then(setCategories).catch(() => {}); loadHistory();
  }, [loadHistory]);

  const reset = () => { setFile(null); setPreview(null); setNeed(null); setAccountId(''); setDueDate(''); setForce(false); if (input.current) input.current.value = ''; };

  const upload = async (f: File | null = file) => {
    if (!f) return;
    setBusy(true); setError(''); setOk(''); setNeed(null);
    try {
      setPreview(await uploadImport(f, accountId ? Number(accountId) : undefined, dueDate || undefined));
    } catch (e) {
      const { status, detail: d } = apiErrorDetail(e);
      if (status === 409) setError('Este archivo ya fue importado para esa cuenta.');
      else if (d && typeof d === 'object') {
        const o = d as { message: string; candidates?: Need['candidates']; needs_due_date?: boolean };
        setNeed({ message: o.message, candidates: o.candidates, needsDueDate: o.needs_due_date });
      } else setError(typeof d === 'string' ? d : 'No se pudo leer el archivo');
      setPreview(null);
    } finally { setBusy(false); }
  };

  const confirm = async () => {
    if (!preview) return;
    setBusy(true); setError('');
    try {
      const b = await confirmImport(preview.id, force);
      setOk(`Importado: ${b.rows_new} movimientos nuevos, ${b.rows_duplicate} duplicados omitidos.`);
      reset(); loadHistory();
    } catch (e) {
      const d = apiErrorDetail(e).detail;
      setError(typeof d === 'string' ? d : (d as { message?: string } | undefined)?.message ?? 'No se pudo confirmar');
    } finally { setBusy(false); }
  };

  const discard = async () => { if (preview) await deleteImport(preview.id).catch(() => {}); reset(); loadHistory(); };
  const removeBatch = async (b: Batch) => {
    if (!confirmDialog(`¿Borrar el lote #${b.id}? Se eliminan sus movimientos (incluidas las ediciones manuales).`)) return;
    await deleteImport(b.id); loadHistory();
  };

  const accName = (id: number) => accounts.find(a => a.id === id)?.name ?? `#${id}`;
  const catName = (id: number | null) => categories.find(c => c.id === id)?.name ?? '—';
  const failed = preview?.validation.some(c => !c.ok);

  return (
    <div className="space-y-4">
      {accounts.length === 0 && (
        <div className="card text-sm text-amber-600">Primero creá una cuenta en la pestaña Configuración (con el formato de archivo que va a importar).</div>
      )}
      <div className="card space-y-3">
        <h2 className="text-sm font-semibold">1. Subir extracto</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <input ref={input} type="file" accept=".csv,.pdf" className="text-sm"
            onChange={e => { setFile(e.target.files?.[0] ?? null); setPreview(null); setNeed(null); setError(''); }} />
          <div className="flex flex-col gap-1 min-w-[180px]">
            <label className="text-xs font-medium text-gray-500">Cuenta (opcional si es única)</label>
            <select className="input text-sm py-1.5" value={accountId} onChange={e => setAccountId(e.target.value)}>
              <option value="">Detectar</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          {(need?.needsDueDate || dueDate) && (
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-gray-500">Vencimiento de la fatura</label>
              <input type="date" className="input text-sm py-1.5" value={dueDate} onChange={e => setDueDate(e.target.value)} />
            </div>
          )}
          <button className="btn-primary" disabled={!file || busy} onClick={() => upload()}>{busy ? 'Procesando…' : 'Previsualizar'}</button>
        </div>
        {need && (
          <p className="text-sm text-amber-600">
            {need.message}{need.candidates ? ': ' + need.candidates.map(c => c.name).join(', ') : ''}. Completá el dato y volvé a previsualizar.
          </p>
        )}
        {error && <p className="text-sm text-rose-500">{error}</p>}
        {ok && <p className="text-sm text-emerald-600">{ok}</p>}
      </div>

      {preview && (
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold">2. Revisar y confirmar</h2>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span><b>Formato:</b> {PARSER_LABELS[preview.parser_key] ?? preview.parser_key}</span>
            <span><b>Cuenta:</b> {accName(preview.account_id)}</span>
            <span><b>Período:</b> {fmtDate(preview.period_start)} → {fmtDate(preview.period_end)}</span>
            <span><b>Filas:</b> {preview.rows_total} ({preview.rows_new} nuevas, {preview.rows_duplicate} duplicadas)</span>
            <span><b>Sin clasificar:</b> {preview.rows?.filter(r => !r.duplicate && r.needs_review).length ?? 0}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {preview.validation.map(c => (
              <span key={c.name} title={c.detail} className={`badge ${c.ok ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                {c.ok ? '✓' : '✗'} {c.name}{!c.ok && c.detail ? `: ${c.detail}` : ''}
              </span>
            ))}
          </div>
          <div className="max-h-96 overflow-auto border border-slate-100 dark:border-slate-800 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
                <tr>{['Fecha', 'Descripción', 'Importe', 'Tipo', 'Categoría', ''].map(h => <th key={h} className="px-2 py-2 text-left font-semibold text-gray-500 uppercase">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {(preview.rows ?? []).map((r, i) => (
                  <tr key={i} className={r.duplicate ? 'opacity-40' : r.needs_review ? 'bg-amber-50/60 dark:bg-amber-900/10' : ''}>
                    <td className="px-2 py-1.5 whitespace-nowrap">{fmtDate(r.date)}</td>
                    <td className="px-2 py-1.5 max-w-[320px] truncate" title={r.description_raw}>{r.description_raw}{r.installment_total ? ` (${r.installment_number}/${r.installment_total})` : ''}</td>
                    <td className="px-2 py-1.5 font-mono text-right whitespace-nowrap">{fmtMoney(r.amount, r.currency, 2)}</td>
                    <td className="px-2 py-1.5">{KIND_LABELS[r.kind] ?? r.kind}</td>
                    <td className="px-2 py-1.5">{catName(r.category_id)}</td>
                    <td className="px-2 py-1.5">{r.duplicate ? 'duplicada' : r.needs_review ? 'revisar' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {failed && (
            <label className="flex items-center gap-2 text-sm text-rose-600">
              <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} />
              Hay checks de validación en rojo. Confirmar igualmente (no recomendado).
            </label>
          )}
          <div className="flex gap-2">
            <button className="btn-primary" disabled={busy || (failed && !force)} onClick={confirm}>Confirmar importación</button>
            <button className="btn-secondary" disabled={busy} onClick={discard}>Descartar</button>
          </div>
        </div>
      )}

      <div className="card p-0 overflow-x-auto">
        <h2 className="text-sm font-semibold px-4 pt-4 pb-2">Historial de lotes</h2>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>{['#', 'Cuenta', 'Formato', 'Período', 'Nuevas', 'Duplicadas', 'Estado', ''].map(h => <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {history.length === 0 ? <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-400">Todavía no hay importaciones</td></tr> :
              history.map(b => (
                <tr key={b.id}>
                  <td className="px-3 py-2">{b.id}</td><td className="px-3 py-2">{accName(b.account_id)}</td>
                  <td className="px-3 py-2">{PARSER_LABELS[b.parser_key] ?? b.parser_key}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{b.statement_period ?? `${fmtDate(b.period_start)} → ${fmtDate(b.period_end)}`}</td>
                  <td className="px-3 py-2">{b.rows_new}</td><td className="px-3 py-2">{b.rows_duplicate}</td>
                  <td className="px-3 py-2"><span className={`badge ${b.status === 'confirmed' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{b.status}</span></td>
                  <td className="px-3 py-2"><button className="text-red-400 hover:text-red-600 text-xs" onClick={() => removeBatch(b)}>Borrar</button></td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const confirmDialog = (m: string) => window.confirm(m);
