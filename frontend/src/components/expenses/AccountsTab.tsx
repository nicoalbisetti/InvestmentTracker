import { useCallback, useEffect, useState } from 'react';
import { apiErrorDetail, createAccount, ExpAccount, getAccount, getAccounts, patchAccount } from '../../api/expenses';
import { PARSER_LABELS } from '../../utils/expenses';

const EMPTY = {
  name: '', institution: '', country: 'BR', kind: 'bank', currency: 'BRL', parser_key: '',
  paid_from_account_id: '', has_statements: true, owner_identifiers: '',
};

export default function AccountsTab() {
  const [accounts, setAccounts] = useState<ExpAccount[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => { getAccounts().then(setAccounts).catch(() => {}); }, []);
  useEffect(load, [load]);
  const set = (k: string, v: string | boolean) => setForm(f => ({ ...f, [k]: v }));

  const payload = () => ({
    name: form.name, institution: form.institution, country: form.country as 'AR' | 'BR', kind: form.kind as ExpAccount['kind'],
    currency: form.currency, parser_key: form.parser_key || null,
    paid_from_account_id: form.paid_from_account_id ? Number(form.paid_from_account_id) : null,
    has_statements: form.has_statements,
    owner_identifiers: form.owner_identifiers.split('\n').map(s => s.trim()).filter(Boolean),
  });

  const save = async () => {
    setError('');
    if (!form.name || !form.institution) { setError('Nombre e institución son obligatorios'); return; }
    try {
      if (editing) await patchAccount(editing, payload()); else await createAccount(payload());
      setForm(EMPTY); setEditing(null); load();
    } catch (e) { const d = apiErrorDetail(e).detail; setError(typeof d === 'string' ? d : 'No se pudo guardar'); }
  };

  const startEdit = async (a: ExpAccount) => {
    const full = await getAccount(a.id);
    setEditing(a.id);
    setForm({
      name: full.name, institution: full.institution, country: full.country, kind: full.kind, currency: full.currency,
      parser_key: full.parser_key ?? '', paid_from_account_id: full.paid_from_account_id ? String(full.paid_from_account_id) : '',
      has_statements: full.has_statements, owner_identifiers: (full.owner_identifiers ?? []).join('\n'),
    });
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <h2 className="text-sm font-semibold">{editing ? `Editar cuenta #${editing}` : 'Nueva cuenta'}</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <L label="Nombre"><input className="input text-sm" value={form.name} onChange={e => set('name', e.target.value)} /></L>
          <L label="Institución"><input className="input text-sm" value={form.institution} onChange={e => set('institution', e.target.value)} /></L>
          <L label="País"><select className="input text-sm" value={form.country} onChange={e => set('country', e.target.value)}><option>BR</option><option>AR</option></select></L>
          <L label="Tipo">
            <select className="input text-sm" value={form.kind} onChange={e => set('kind', e.target.value)}>
              <option value="bank">Banco</option><option value="wallet">Billetera</option><option value="credit_card">Tarjeta de crédito</option>
            </select>
          </L>
          <L label="Moneda principal"><select className="input text-sm" value={form.currency} onChange={e => set('currency', e.target.value)}><option>BRL</option><option>ARS</option><option>USD</option></select></L>
          <L label="Formato de extracto">
            <select className="input text-sm" value={form.parser_key} onChange={e => set('parser_key', e.target.value)}>
              <option value="">— (sin extractos)</option>
              {Object.entries(PARSER_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </L>
          <L label="Se paga desde (tarjetas)">
            <select className="input text-sm" value={form.paid_from_account_id} onChange={e => set('paid_from_account_id', e.target.value)}>
              <option value="">—</option>
              {accounts.filter(a => a.kind !== 'credit_card' && a.id !== editing).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </L>
          <label className="flex items-center gap-2 text-sm pt-5"><input type="checkbox" checked={form.has_statements} onChange={e => set('has_statements', e.target.checked)} />Tiene extractos</label>
        </div>
        <L label="Identificadores propios (uno por línea: nombre del titular, CBU/CVU, etc.)">
          <textarea className="input text-sm font-mono h-20" value={form.owner_identifiers} onChange={e => set('owner_identifiers', e.target.value)} />
        </L>
        <p className="text-xs text-slate-400">Sirven para reconocer transferencias entre cuentas propias. Se guardan sólo en la base local de gastos.</p>
        {error && <p className="text-sm text-rose-500">{String(error)}</p>}
        <div className="flex gap-2">
          <button className="btn-primary" onClick={save}>{editing ? 'Guardar cambios' : 'Crear cuenta'}</button>
          {editing && <button className="btn-secondary" onClick={() => { setEditing(null); setForm(EMPTY); }}>Cancelar</button>}
        </div>
      </div>

      <div className="card p-0 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>{['Nombre', 'Institución', 'País', 'Tipo', 'Moneda', 'Formato', 'Paga desde', 'Extractos', ''].map(h => <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {accounts.length === 0 ? <tr><td colSpan={9} className="px-3 py-6 text-center text-gray-400">No hay cuentas</td></tr> :
              accounts.map(a => (
                <tr key={a.id}>
                  <td className="px-3 py-2 font-medium">{a.name}</td><td className="px-3 py-2">{a.institution}</td><td className="px-3 py-2">{a.country}</td>
                  <td className="px-3 py-2">{a.kind}</td><td className="px-3 py-2">{a.currency}</td>
                  <td className="px-3 py-2">{a.parser_key ? PARSER_LABELS[a.parser_key] ?? a.parser_key : '—'}</td>
                  <td className="px-3 py-2">{accounts.find(x => x.id === a.paid_from_account_id)?.name ?? '—'}</td>
                  <td className="px-3 py-2">{a.has_statements ? 'sí' : 'no'}</td>
                  <td className="px-3 py-2"><button className="text-indigo-400 hover:text-indigo-600 text-xs" onClick={() => startEdit(a)}>Editar</button></td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function L({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex flex-col gap-1"><label className="text-xs font-medium text-gray-500">{label}</label>{children}</div>;
}
