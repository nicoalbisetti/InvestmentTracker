import { useCallback, useEffect, useState } from 'react';
import {
  applyMerchantGroups, ExpCategory, ExpEntity, getCategories, getEntities, getMerchantGroups, MerchantGroup, reapplyRules,
} from '../../api/expenses';
import { fmtMoney, KIND_LABELS } from '../../utils/expenses';

interface Choice { kind: string; category_id: string; entity_id: string; selected: boolean }
const groupId = (g: MerchantGroup) => `${g.key}|${g.sign}`;

/** Clasificar un comercio una vez crea una regla y la aplica a todas sus filas pendientes. */
export default function MerchantGroups({ onChanged }: { onChanged: () => void }) {
  const [groups, setGroups] = useState<MerchantGroup[]>([]);
  const [cats, setCats] = useState<ExpCategory[]>([]);
  const [ents, setEnts] = useState<ExpEntity[]>([]);
  const [choice, setChoice] = useState<Record<string, Choice>>({});
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { getMerchantGroups(100).then(setGroups).catch(() => setMsg('No se pudieron cargar los comercios')); }, []);
  useEffect(() => { load(); getCategories().then(setCats).catch(() => {}); getEntities().then(setEnts).catch(() => {}); }, [load]);

  const get = (g: MerchantGroup): Choice =>
    choice[groupId(g)] ?? { kind: g.sign === 'negative' ? 'expense' : 'income', category_id: '', entity_id: '', selected: false };
  const set = (g: MerchantGroup, patch: Partial<Choice>) =>
    setChoice(c => ({ ...c, [groupId(g)]: { ...get(g), ...patch } }));

  const chosen = groups.filter(g => get(g).selected && (get(g).category_id || get(g).kind !== 'expense'));

  const apply = async () => {
    setBusy(true); setMsg('');
    try {
      const res = await applyMerchantGroups(chosen.map(g => {
        const c = get(g);
        return { key: g.key, sign: g.sign, kind: c.kind, category_id: c.category_id ? Number(c.category_id) : undefined, entity_id: c.entity_id ? Number(c.entity_id) : undefined };
      }));
      setMsg(`${res.length} regla(s) creadas; reclasificaron ${res.reduce((s, r) => s + r.applied, 0)} movimiento(s).`);
      setChoice({}); load(); onChanged();
    } catch { setMsg('No se pudieron aplicar las reglas'); } finally { setBusy(false); }
  };

  const reapply = async () => {
    const r = await reapplyRules();
    setMsg(`Reglas reaplicadas: ${r.reclassified} movimiento(s) reclasificados.`); load(); onChanged();
  };

  return (
    <div className="space-y-2 mb-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-xs text-slate-500">Elegí tipo y categoría por comercio y marcalo: se crea una regla y se aplica a todas sus filas.</p>
        <button className="btn-primary text-xs py-1" disabled={busy || chosen.length === 0} onClick={apply}>Crear {chosen.length} regla(s)</button>
        <button className="btn-secondary text-xs py-1" onClick={reapply}>Reaplicar reglas a pendientes</button>
        {msg && <span className="text-xs text-emerald-600">{msg}</span>}
      </div>
      {groups.length === 0 ? <p className="text-sm text-slate-400">No quedan comercios sin clasificar.</p> : (
        <div className="max-h-96 overflow-auto border border-slate-100 dark:border-slate-800 rounded-lg">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>{['', 'Comercio', 'Filas', 'Monto', 'Tipo', 'Categoría', 'Entidad'].map(h => <th key={h} className="px-2 py-2 text-left font-semibold text-gray-500 uppercase">{h}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {groups.map(g => {
                const c = get(g);
                return (
                  <tr key={groupId(g)} className={c.selected ? 'bg-indigo-50/60 dark:bg-indigo-900/10' : ''}>
                    <td className="px-2 py-1"><input type="checkbox" checked={c.selected} onChange={e => set(g, { selected: e.target.checked })} /></td>
                    <td className="px-2 py-1 max-w-[260px]" title={g.sample.join(' · ')}>
                      <span className="truncate block">{g.sign === 'positive' ? '＋ ' : ''}{g.merchant}</span>
                      <span className="text-[10px] text-gray-400">{g.countries.join('/')} · {g.first.slice(0, 7)}→{g.last.slice(0, 7)}</span>
                    </td>
                    <td className="px-2 py-1 text-right">{g.count}</td>
                    <td className="px-2 py-1 font-mono text-right whitespace-nowrap">{fmtMoney(g.total_brl)}</td>
                    <td className="px-2 py-1"><select className="input text-xs py-0.5" value={c.kind} onChange={e => set(g, { kind: e.target.value, selected: true })}>
                      {Object.entries(KIND_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td>
                    <td className="px-2 py-1"><select className="input text-xs py-0.5" value={c.category_id} onChange={e => set(g, { category_id: e.target.value, selected: !!e.target.value })}>
                      <option value="">—</option>{cats.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></td>
                    <td className="px-2 py-1"><select className="input text-xs py-0.5" value={c.entity_id} onChange={e => set(g, { entity_id: e.target.value })}>
                      <option value="">—</option>{ents.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}</select></td>
                  </tr>);
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
