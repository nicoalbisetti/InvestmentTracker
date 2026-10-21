import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  bulkPatch, getAccounts, getCategories, getEntities, getTransactions, patchTransaction, previewRule,
  ExpAccount, ExpCategory, ExpEntity, ExpTx,
} from '../../api/expenses';
import { fmtDate } from '../../utils/formatters';
import { fmtMoney, KIND_LABELS, matchKey } from '../../utils/expenses';

const PAGE_SIZE = 50;
const EMPTY = { kind: '', category_id: '', entity: '', account_id: '', country: '', from: '', to: '', needs_review: false, q: '' };

export default function MovementsTab() {
  const [accounts, setAccounts] = useState<ExpAccount[]>([]);
  const [categories, setCategories] = useState<ExpCategory[]>([]);
  const [entities, setEntities] = useState<ExpEntity[]>([]);
  const [params] = useSearchParams();
  const [filters, setFilters] = useState({ ...EMPTY, needs_review: params.get('pending') === '1' });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ total: number; items: ExpTx[] }>({ total: 0, items: [] });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [makeRule, setMakeRule] = useState(false);
  const [bulk, setBulk] = useState({ kind: '', category_id: '', entity_id: '' });
  const [msg, setMsg] = useState('');

  useEffect(() => {
    Promise.all([getAccounts(), getCategories(), getEntities()]).then(([a, c, e]) => {
      setAccounts(a); setCategories(c); setEntities(e);
    }).catch(() => {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    const p: Record<string, string | number | boolean> = { page, page_size: PAGE_SIZE };
    if (filters.kind) p.kind = filters.kind;
    if (filters.category_id) p.category_id = filters.category_id;
    if (filters.entity) p.entity = filters.entity;
    if (filters.account_id) p.account_id = filters.account_id;
    if (filters.country) p.country = filters.country;
    if (filters.from) p.from = filters.from;
    if (filters.to) p.to = filters.to;
    if (filters.needs_review) p.needs_review = true;
    if (filters.q) p.q = filters.q;
    getTransactions(p).then(setData).finally(() => setLoading(false));
  }, [filters, page]);
  useEffect(load, [load]);

  const setFilter = (k: string, v: string | boolean) => { setFilters(f => ({ ...f, [k]: v })); setPage(1); setSelected(new Set()); };
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const entId = (code: string | null) => entities.find(e => e.code === code)?.id ?? '';

  const edit = async (t: ExpTx, change: { kind?: string; category_id?: number | null; entity_id?: number | null }) => {
    const body: Record<string, unknown> = { ...change };
    if (makeRule && t.merchant) {
      const probe = await previewRule({
        pattern: matchKey(t.merchant), field: 'merchant_normalized', set_kind: change.kind ?? t.kind,
        amount_sign: t.amount > 0 ? 'positive' : 'negative',
      });
      if (!confirm(`Se creará una regla para "${t.merchant}" y se aplicará a ${probe.count} movimiento(s) pendiente(s). ¿Continuar?`)) return;
      body.create_rule = true;
    }
    const r = await patchTransaction(t.id, body);
    setMsg(r.rule_applied_to != null && body.create_rule ? `Regla creada: reclasificó ${r.rule_applied_to} movimiento(s)` : '');
    load();
  };

  const toggle = (id: number) => setSelected(s => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const applyBulk = async () => {
    const body: Record<string, unknown> = { ids: [...selected] };
    if (bulk.kind) body.kind = bulk.kind;
    if (bulk.category_id) body.category_id = Number(bulk.category_id);
    if (bulk.entity_id) body.entity_id = Number(bulk.entity_id);
    if (Object.keys(body).length === 1) return;
    await bulkPatch(body);
    setSelected(new Set()); setBulk({ kind: '', category_id: '', entity_id: '' }); load();
  };

  return (
    <div className="space-y-4">
      <div className="card p-3 space-y-2">
        <div className="flex flex-wrap gap-2 items-end">
          <Sel label="Tipo" value={filters.kind} onChange={v => setFilter('kind', v)} options={Object.entries(KIND_LABELS).map(([v, l]) => [v, l])} />
          <Sel label="Categoría" value={filters.category_id} onChange={v => setFilter('category_id', v)} options={categories.map(c => [String(c.id), c.name])} />
          <Sel label="Entidad" value={filters.entity} onChange={v => setFilter('entity', v)} options={entities.map(e => [e.code, e.name])} />
          <Sel label="Cuenta" value={filters.account_id} onChange={v => setFilter('account_id', v)} options={accounts.map(a => [String(a.id), a.name])} />
          <Sel label="País" value={filters.country} onChange={v => setFilter('country', v)} options={[['BR', 'Brasil'], ['AR', 'Argentina']]} />
          <div className="flex flex-col gap-1"><label className="text-xs font-medium text-gray-500">Desde</label>
            <input type="date" className="input text-sm py-1.5" value={filters.from} onChange={e => setFilter('from', e.target.value)} /></div>
          <div className="flex flex-col gap-1"><label className="text-xs font-medium text-gray-500">Hasta</label>
            <input type="date" className="input text-sm py-1.5" value={filters.to} onChange={e => setFilter('to', e.target.value)} /></div>
          <div className="flex flex-col gap-1 min-w-[160px]"><label className="text-xs font-medium text-gray-500">Texto</label>
            <input className="input text-sm py-1.5" value={filters.q} onChange={e => setFilter('q', e.target.value)} placeholder="Buscar…" /></div>
          <label className="flex items-center gap-1.5 text-sm pb-1.5"><input type="checkbox" checked={filters.needs_review} onChange={e => setFilter('needs_review', e.target.checked)} />Sólo pendientes</label>
          <button className="btn-secondary text-sm py-1.5" onClick={() => { setFilters(EMPTY); setPage(1); }}>Limpiar</button>
        </div>
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>{data.total} movimientos</span>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={makeRule} onChange={e => setMakeRule(e.target.checked)} />Al corregir, crear regla para ese comercio</label>
        </div>
        {msg && <p className="text-xs text-emerald-600">{msg}</p>}
      </div>

      {selected.size > 0 && (
        <div className="card p-3 flex flex-wrap gap-2 items-end bg-indigo-50 dark:bg-indigo-900/20">
          <span className="text-sm font-medium pb-1.5">{selected.size} seleccionado(s)</span>
          <Sel label="Tipo" value={bulk.kind} onChange={v => setBulk(b => ({ ...b, kind: v }))} options={Object.entries(KIND_LABELS)} blank="Sin cambio" />
          <Sel label="Categoría" value={bulk.category_id} onChange={v => setBulk(b => ({ ...b, category_id: v }))} options={categories.map(c => [String(c.id), c.name])} blank="Sin cambio" />
          <Sel label="Entidad" value={bulk.entity_id} onChange={v => setBulk(b => ({ ...b, entity_id: v }))} options={entities.map(e => [String(e.id), e.name])} blank="Sin cambio" />
          <button className="btn-primary text-sm py-1.5" onClick={applyBulk}>Aplicar</button>
          <button className="btn-secondary text-sm py-1.5" onClick={() => setSelected(new Set())}>Cancelar</button>
        </div>
      )}

      <div className="card p-0 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-3 py-3 w-8"><input type="checkbox" checked={data.items.length > 0 && data.items.every(t => selected.has(t.id))}
                onChange={e => setSelected(e.target.checked ? new Set(data.items.map(t => t.id)) : new Set())} /></th>
              {['Fecha', 'Cuenta', 'Descripción', 'Importe', 'Tipo', 'Categoría', 'Entidad'].map(h =>
                <th key={h} className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? [...Array(8)].map((_, i) => (
              <tr key={i}><td colSpan={8} className="px-3 py-3"><div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-4 rounded" /></td></tr>
            )) : data.items.length === 0 ? (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">No hay movimientos</td></tr>
            ) : data.items.map(t => (
              <tr key={t.id} className={`hover:bg-gray-50 dark:hover:bg-gray-800/50 ${t.needs_review ? 'bg-amber-50/60 dark:bg-amber-900/10' : ''}`}>
                <td className="px-3 py-2"><input type="checkbox" checked={selected.has(t.id)} onChange={() => toggle(t.id)} /></td>
                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(t.date)}
                  {t.purchase_date && t.purchase_date !== t.date && <div className="text-[10px] text-gray-400">compra {fmtDate(t.purchase_date)}</div>}</td>
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{t.account}</td>
                <td className="px-3 py-2 max-w-[320px]">
                  <div className="truncate" title={t.description}>{t.description}</div>
                  {t.installment_total && <span className="badge bg-slate-100 text-slate-600">cuota {t.installment_number}/{t.installment_total}</span>}
                  {t.classification_source === 'manual' && <span className="badge bg-indigo-100 text-indigo-700 ml-1">manual</span>}
                </td>
                <td className={`px-3 py-2 font-mono whitespace-nowrap text-right ${t.amount < 0 ? 'negative' : 'positive'}`}>{fmtMoney(t.amount, t.currency, 2)}</td>
                <td className="px-3 py-2">
                  <select className="input text-xs py-1" value={t.kind} onChange={e => edit(t, { kind: e.target.value })}>
                    {Object.entries(KIND_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <select className="input text-xs py-1" value={t.category_id ?? ''} onChange={e => e.target.value && edit(t, { category_id: Number(e.target.value) })}>
                    <option value="">—</option>
                    {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <select className="input text-xs py-1" value={entId(t.entity)} onChange={e => e.target.value && edit(t, { entity_id: Number(e.target.value) })}>
                    <option value="">—</option>
                    {entities.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-center items-center gap-3 text-sm">
        <button className="btn-secondary py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>←</button>
        <span>Página {page} de {pages}</span>
        <button className="btn-secondary py-1" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>→</button>
      </div>
    </div>
  );
}

function Sel({ label, value, onChange, options, blank = 'Todos' }: { label: string; value: string; onChange: (v: string) => void; options: string[][]; blank?: string }) {
  return (
    <div className="flex flex-col gap-1 min-w-[130px]">
      <label className="text-xs font-medium text-gray-500">{label}</label>
      <select className="input text-sm py-1.5" value={value} onChange={e => onChange(e.target.value)}>
        <option value="">{blank}</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}
