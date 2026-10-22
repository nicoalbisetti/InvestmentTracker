import { useCallback, useEffect, useState } from 'react';
import { apiErrorDetail, deleteFxRate, FxRate, getFxRates, putFxRate, recomputeFx } from '../../api/expenses';
import { fmtDate } from '../../utils/formatters';

const PAIRS: Record<string, string> = { USDBRL_PTAX: 'USD→BRL (PTAX venta, BCB)', USDARS_MEP: 'USD→ARS (dólar MEP, venta)' };
const SOURCES: Record<string, string> = { ptax: 'BCB', argentinadatos: 'argentinadatos', manual: 'manual' };
const iso = (d: Date) => d.toISOString().slice(0, 10);

export default function FxTab() {
  const today = new Date();
  const [pair, setPair] = useState('USDBRL_PTAX');
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 60 * 86400000)));
  const [to, setTo] = useState(iso(today));
  const [rates, setRates] = useState<FxRate[]>([]);
  const [form, setForm] = useState({ date: iso(today), rate: '' });
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(() => { getFxRates(pair, from, to).then(setRates).catch(() => setError('No se pudo cargar')); }, [pair, from, to]);
  useEffect(load, [load]);

  const save = async () => {
    setError(''); setMsg('');
    const v = Number(form.rate.replace(',', '.'));
    if (!form.date || !(v > 0)) { setError('Fecha y tipo de cambio (> 0) son obligatorios'); return; }
    try { await putFxRate(pair, form.date, v); setMsg(`Guardado ${form.date}: ${v}. Recalculá los movimientos para que lo usen.`); setForm(f => ({ ...f, rate: '' })); load(); }
    catch (e) { const d = apiErrorDetail(e).detail; setError(typeof d === 'string' ? d : 'No se pudo guardar'); }
  };
  const remove = async (r: FxRate) => {
    const res = await deleteFxRate(pair, r.date).catch(() => null);
    setMsg(res ? (res.restored ? 'Carga manual quitada; se restauró el valor de la fuente.' : 'Carga manual quitada, pero la fuente no respondió (sin valor para ese día).') : '');
    load();
  };
  const recompute = async () => {
    if (!window.confirm(`Se recalculan BRL y USD de los movimientos entre ${fmtDate(from)} y ${fmtDate(to)} con los tipos de cambio vigentes (incluidas las cargas manuales). ¿Continuar?`)) return;
    const r = await recomputeFx(from, to).catch(() => null);
    setMsg(r ? `Recalculados ${r.recomputed} movimiento(s).` : 'No se pudo recalcular');
  };

  return (
    <div className="space-y-3">
      <div className="card p-3 flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Par</label>
          <select className="input text-sm py-1.5" value={pair} onChange={e => setPair(e.target.value)}>{Object.entries(PAIRS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Desde</label><input type="date" className="input text-sm py-1.5" value={from} onChange={e => setFrom(e.target.value)} /></div>
        <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Hasta</label><input type="date" className="input text-sm py-1.5" value={to} onChange={e => setTo(e.target.value)} /></div>
        <button className="btn-secondary text-sm py-1.5" onClick={recompute}>Recalcular movimientos del rango</button>
      </div>
      <div className="card p-3 flex flex-wrap gap-3 items-end">
        <span className="text-sm font-semibold pb-1.5">Cargar un valor a mano</span>
        <input type="date" className="input text-sm py-1.5 w-44" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
        <input className="input text-sm py-1.5 w-32" placeholder="tipo de cambio" value={form.rate} onChange={e => setForm(f => ({ ...f, rate: e.target.value }))} />
        <button className="btn-primary text-sm py-1.5" onClick={save}>Guardar</button>
        <span className="text-xs text-slate-400">Una carga manual nunca se pisa al actualizar desde la fuente.</span>
        {msg && <span className="text-xs text-emerald-600">{msg}</span>}
        {error && <span className="text-xs text-rose-500">{error}</span>}
      </div>
      <div className="card p-0 overflow-x-auto max-h-[28rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0"><tr>{['Fecha', 'Tipo de cambio', 'Fuente', ''].map(h => <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {rates.length === 0 ? <tr><td colSpan={4} className="px-3 py-6 text-center text-gray-400">Sin valores en el rango (se descargan al importar extractos)</td></tr> :
              [...rates].reverse().map(r => (
                <tr key={r.date}><td className="px-3 py-1.5">{fmtDate(r.date)}</td><td className="px-3 py-1.5 font-mono">{r.rate.toLocaleString('es-AR', { maximumFractionDigits: 4 })}</td>
                  <td className="px-3 py-1.5"><span className={`badge ${r.source === 'manual' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>{SOURCES[r.source] ?? r.source}</span></td>
                  <td className="px-3 py-1.5">{r.source === 'manual' && <button className="text-red-400 hover:text-red-600 text-xs" onClick={() => remove(r)}>Quitar</button>}</td></tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
