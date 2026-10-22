import { useCallback, useEffect, useMemo, useState } from 'react';
import Modal from '../ui/Modal';
import Combobox from './Combobox';
import {
  apiErrorDetail, createRule, deleteRule, ExpAccount, ExpCategory, ExpEntity, ExpRule, getAccounts, getCategories, getEntities,
  getRules, patchRule, previewRule, reorderRules, RuleInput,
} from '../../api/expenses';
import { KIND_LABELS } from '../../utils/expenses';

const FIELDS: Record<string, string> = { description_raw: 'Descripción', merchant_normalized: 'Comercio normalizado', counterparty: 'Contraparte' };
const SIGNS: Record<string, string> = { any: 'Cualquiera', negative: 'Sale plata (−)', positive: 'Entra plata (+)' };

interface Form {
  pattern: string; field: string; amount_sign: string; set_kind: string; category: string; entity: string; merchant: string;
  needs_review: boolean; counterparty: string; exclude_from_audit: boolean; active: boolean; account: string; apply: boolean;
}
const EMPTY: Form = {
  pattern: '', field: 'description_raw', amount_sign: 'any', set_kind: 'expense', category: '', entity: '', merchant: '',
  needs_review: false, counterparty: '', exclude_from_audit: false, active: true, account: '', apply: false,
};

const toForm = (r: ExpRule): Form => ({
  pattern: r.pattern, field: r.field, amount_sign: r.amount_sign, set_kind: r.set_kind, category: r.set_category_id ? String(r.set_category_id) : '',
  entity: r.set_entity_id ? String(r.set_entity_id) : '', merchant: r.set_merchant ?? '', needs_review: r.set_needs_review,
  counterparty: r.set_counterparty_account_id ? String(r.set_counterparty_account_id) : '', exclude_from_audit: r.set_exclude_from_audit,
  active: r.active, account: r.account_id ? String(r.account_id) : '', apply: false,
});

const toInput = (f: Form): RuleInput => ({
  pattern: f.pattern, field: f.field, amount_sign: f.amount_sign, set_kind: f.set_kind,
  set_category_id: f.category ? Number(f.category) : null, set_entity_id: f.entity ? Number(f.entity) : null,
  set_merchant: f.merchant || null, set_needs_review: f.needs_review,
  set_counterparty_account_id: f.counterparty ? Number(f.counterparty) : null, set_exclude_from_audit: f.exclude_from_audit,
  active: f.active, account_id: f.account ? Number(f.account) : null, apply_to_pending: f.apply,
});

export default function RulesTab() {
  const [rules, setRules] = useState<ExpRule[]>([]);
  const [cats, setCats] = useState<ExpCategory[]>([]);
  const [ents, setEnts] = useState<ExpEntity[]>([]);
  const [accounts, setAccounts] = useState<ExpAccount[]>([]);
  const [search, setSearch] = useState('');
  const [origin, setOrigin] = useState('');
  const [dragId, setDragId] = useState<number | null>(null);
  const [overId, setOverId] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ id: number | null; form: Form } | null>(null);
  const [impact, setImpact] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const load = useCallback(() => { getRules().then(setRules).catch(() => setError('No se pudieron cargar las reglas')); }, []);
  useEffect(() => {
    load(); getCategories().then(setCats).catch(() => {}); getEntities().then(setEnts).catch(() => {}); getAccounts().then(setAccounts).catch(() => {});
  }, [load]);

  const catName = (id: number | null) => cats.find(c => c.id === id)?.name ?? '';
  const entName = (id: number | null) => ents.find(e => e.id === id)?.name ?? '';
  const filtering = search.trim() !== '' || origin !== '';
  const shown = useMemo(() => rules.filter(r =>
    (!origin || r.origin === origin) &&
    (!search || `${r.pattern} ${catName(r.set_category_id)} ${KIND_LABELS[r.set_kind] ?? ''}`.toLowerCase().includes(search.toLowerCase()))),
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [rules, search, origin, cats]);

  const catOptions = cats.map(c => ({ value: String(c.id), label: c.name }));
  const entOptions = ents.map(e => ({ value: String(e.id), label: e.name }));
  const accOptions = accounts.map(a => ({ value: String(a.id), label: a.name }));

  const drop = async (target: ExpRule) => {
    if (dragId == null || dragId === target.id || filtering) { setDragId(null); setOverId(null); return; }
    const ids = rules.map(r => r.id).filter(i => i !== dragId);
    ids.splice(ids.indexOf(target.id), 0, dragId);
    setDragId(null); setOverId(null);
    try { const r = await reorderRules(ids); setMsg(`Orden actualizado (${r.moved} regla(s) cambiaron de prioridad)`); load(); }
    catch { setError('No se pudo reordenar'); }
  };

  const toggle = async (r: ExpRule) => { await patchRule(r.id, { active: !r.active }); load(); };
  const remove = async (r: ExpRule) => {
    if (!window.confirm(`¿Borrar la regla "${r.pattern}"? Los movimientos ya clasificados conservan su clasificación.`)) return;
    try { await deleteRule(r.id); load(); } catch (e) {
      const d = apiErrorDetail(e).detail; setError(typeof d === 'string' ? d : 'No se pudo borrar');
    }
  };

  const regexError = (p: string) => { try { new RegExp(p); return ''; } catch (e) { return String((e as Error).message); } };

  const probe = async () => {
    if (!editing) return;
    try {
      const r = await previewRule({ ...toInput(editing.form), apply_to_pending: undefined } as Record<string, unknown>);
      setImpact(r.count);
    } catch { setImpact(null); setError('No se pudo calcular el impacto'); }
  };

  const save = async () => {
    if (!editing) return;
    setError('');
    const err = !editing.form.pattern ? 'El patrón es obligatorio' : regexError(editing.form.pattern);
    if (err) { setError(err); return; }
    try {
      const body = toInput(editing.form);
      const r = editing.id == null ? await createRule(body) : await patchRule(editing.id, body);
      setMsg(r.applied ? `Regla guardada: reclasificó ${r.applied} movimiento(s) pendiente(s)` : 'Regla guardada');
      setEditing(null); setImpact(null); load();
    } catch (e) { const d = apiErrorDetail(e).detail; setError(typeof d === 'string' ? d : 'No se pudo guardar'); }
  };

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setEditing(e => e && ({ ...e, form: { ...e.form, [k]: v } }));

  return (
    <div className="space-y-3">
      <div className="card p-3 flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Buscar</label>
          <input className="input text-sm py-1.5" placeholder="patrón, categoría o tipo…" value={search} onChange={e => setSearch(e.target.value)} /></div>
        <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Origen</label>
          <select className="input text-sm py-1.5" value={origin} onChange={e => setOrigin(e.target.value)}>
            <option value="">Todas</option><option value="seed">Semilla</option><option value="manual">Manuales</option></select></div>
        <button className="btn-primary text-sm py-1.5" onClick={() => { setEditing({ id: null, form: EMPTY }); setImpact(null); setError(''); }}>+ Nueva regla</button>
        <span className="text-xs text-slate-400">
          {rules.length} reglas · se evalúan de arriba hacia abajo y gana la primera que coincide.
          {filtering ? ' Quitá los filtros para reordenar arrastrando.' : ' Arrastrá una fila para cambiar su prioridad.'}
        </span>
        {msg && <span className="text-xs text-emerald-600">{msg}</span>}
        {error && !editing && <span className="text-xs text-rose-500">{error}</span>}
      </div>

      <div className="card p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>{['', '#', 'Campo', 'Patrón', 'Signo', 'Clasifica como', 'Categoría', 'Entidad', 'Marcas', 'Origen', 'Activa', ''].map((h, i) =>
              <th key={i} className="px-2 py-2 text-left font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {shown.map(r => (
              <tr key={r.id} draggable={!filtering}
                onDragStart={() => setDragId(r.id)} onDragEnd={() => { setDragId(null); setOverId(null); }}
                onDragOver={e => { if (dragId != null) { e.preventDefault(); setOverId(r.id); } }} onDrop={() => drop(r)}
                className={`${!r.active ? 'opacity-50' : ''} ${overId === r.id && dragId !== r.id ? 'border-t-2 border-indigo-500' : ''} ${dragId === r.id ? 'bg-indigo-50 dark:bg-indigo-900/20' : ''}`}>
                <td className={`px-2 py-1.5 ${filtering ? 'text-slate-200' : 'cursor-grab text-slate-400'}`} title={filtering ? '' : 'Arrastrar para reordenar'}>⋮⋮</td>
                <td className="px-2 py-1.5 text-slate-400">{r.priority}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{FIELDS[r.field] ?? r.field}</td>
                <td className="px-2 py-1.5 font-mono max-w-[260px] truncate" title={r.pattern}>{r.pattern}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{SIGNS[r.amount_sign] ?? r.amount_sign}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{KIND_LABELS[r.set_kind] ?? r.set_kind}</td>
                <td className="px-2 py-1.5">{catName(r.set_category_id) || '—'}</td>
                <td className="px-2 py-1.5">{entName(r.set_entity_id) || '—'}</td>
                <td className="px-2 py-1.5 space-x-1">
                  {r.set_needs_review && <span className="badge bg-amber-100 text-amber-700">revisar</span>}
                  {r.set_counterparty_account_id && <span className="badge bg-sky-100 text-sky-700">contraparte</span>}
                  {r.set_exclude_from_audit && <span className="badge bg-slate-100 text-slate-600">sin auditoría</span>}
                </td>
                <td className="px-2 py-1.5"><span className={`badge ${r.origin === 'seed' ? 'bg-slate-100 text-slate-600' : 'bg-indigo-100 text-indigo-700'}`}>{r.origin === 'seed' ? 'semilla' : 'manual'}</span></td>
                <td className="px-2 py-1.5"><input type="checkbox" checked={r.active} onChange={() => toggle(r)} /></td>
                <td className="px-2 py-1.5 whitespace-nowrap">
                  <button className="text-indigo-400 hover:text-indigo-600 mr-2" onClick={() => { setEditing({ id: r.id, form: toForm(r) }); setImpact(null); setError(''); }}>Editar</button>
                  {r.origin === 'manual' && <button className="text-red-400 hover:text-red-600" onClick={() => remove(r)}>Borrar</button>}
                </td>
              </tr>))}
            {shown.length === 0 && <tr><td colSpan={12} className="px-3 py-6 text-center text-gray-400">No hay reglas</td></tr>}
          </tbody>
        </table>
      </div>

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={editing?.id == null ? 'Nueva regla' : 'Editar regla'} size="xl">
        {editing && (
          <div className="space-y-3 text-sm">
            {editing.id != null && rules.find(r => r.id === editing.id)?.origin === 'seed' &&
              <p className="text-xs text-amber-600">Es una regla semilla: al guardar pasa a "manual" y las recargas de semillas ya no la pisan.</p>}
            <div className="grid grid-cols-2 gap-3">
              <L label="Patrón (regex, sin distinguir mayúsculas)">
                <input className="input text-sm font-mono" value={editing.form.pattern} onChange={e => { set('pattern', e.target.value); setImpact(null); }} />
                {editing.form.pattern && regexError(editing.form.pattern) && <span className="text-xs text-rose-500">{regexError(editing.form.pattern)}</span>}
              </L>
              <L label="Se busca en"><select className="input text-sm" value={editing.form.field} onChange={e => set('field', e.target.value)}>
                {Object.entries(FIELDS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></L>
              <L label="Signo del importe"><select className="input text-sm" value={editing.form.amount_sign} onChange={e => set('amount_sign', e.target.value)}>
                {Object.entries(SIGNS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></L>
              <L label="Clasifica como"><select className="input text-sm" value={editing.form.set_kind} onChange={e => set('set_kind', e.target.value)}>
                {Object.entries(KIND_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></L>
              <L label="Categoría"><Combobox options={catOptions} value={editing.form.category} onChange={v => set('category', v)} clearLabel="— sin categoría" /></L>
              <L label="Entidad"><Combobox options={entOptions} value={editing.form.entity} onChange={v => set('entity', v)} clearLabel="— sin entidad" /></L>
              <L label="Sólo en la cuenta"><Combobox options={accOptions} value={editing.form.account} onChange={v => set('account', v)} clearLabel="Todas las cuentas" /></L>
              <L label="Cuenta de contraparte (transferencias)"><Combobox options={accOptions} value={editing.form.counterparty} onChange={v => set('counterparty', v)} clearLabel="— ninguna" /></L>
              <L label="Nombre de comercio (opcional)"><input className="input text-sm" value={editing.form.merchant} onChange={e => set('merchant', e.target.value)} /></L>
            </div>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={editing.form.active} onChange={e => set('active', e.target.checked)} />Activa</label>
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={editing.form.needs_review} onChange={e => set('needs_review', e.target.checked)} />Dejar en revisión</label>
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={editing.form.exclude_from_audit} onChange={e => set('exclude_from_audit', e.target.checked)} />Excluir de la auditoría</label>
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={editing.form.apply} onChange={e => set('apply', e.target.checked)} />Aplicar a los pendientes al guardar</label>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button className="btn-secondary text-sm py-1.5" disabled={!editing.form.pattern || !!regexError(editing.form.pattern)} onClick={probe}>Ver impacto en pendientes</button>
              {impact != null && <span className="text-xs text-slate-500">{impact} movimiento(s) pendiente(s) coinciden</span>}
            </div>
            {error && <p className="text-sm text-rose-500">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button className="btn-primary" onClick={save}>Guardar</button>
              <button className="btn-secondary" onClick={() => setEditing(null)}>Cancelar</button>
            </div>
          </div>)}
      </Modal>
    </div>
  );
}

function L({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex flex-col gap-1"><label className="text-xs font-medium text-gray-500">{label}</label>{children}</div>;
}
