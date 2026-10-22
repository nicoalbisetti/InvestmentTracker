import { useCallback, useEffect, useState } from 'react';
import { applyUnpairedGroups, ExpAccount, getAccounts, getUnpairedGroups, UnpairedGroup } from '../../api/expenses';
import { fmtMoney } from '../../utils/expenses';

const gid = (g: UnpairedGroup) => `${g.key}|${g.sign}`;

/** Asignar la cuenta de la otra punta a transferencias propias sin par (aunque esa cuenta no se importe). */
export default function UnpairedGroups({ onChanged }: { onChanged: () => void }) {
  const [groups, setGroups] = useState<UnpairedGroup[]>([]);
  const [accounts, setAccounts] = useState<ExpAccount[]>([]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => { getUnpairedGroups(100).then(setGroups).catch(() => setMsg('No se pudieron cargar los grupos')); }, []);
  useEffect(() => { load(); getAccounts().then(setAccounts).catch(() => {}); }, [load]);

  const chosen = groups.filter(g => choice[gid(g)]);
  const apply = async () => {
    setBusy(true); setMsg('');
    try {
      const res = await applyUnpairedGroups(chosen.map(g => ({ key: g.key, sign: g.sign, account_id: Number(choice[gid(g)]) })));
      setMsg(`${res.length} regla(s) guardadas; ${res.reduce((s, r) => s + r.assigned, 0)} transferencia(s) asignadas.`);
      setChoice({}); load(); onChanged();
    } catch { setMsg('No se pudo asignar'); } finally { setBusy(false); }
  };

  if (groups.length === 0) return <p className="text-sm text-slate-400 mb-2">Todas las transferencias sin par ya tienen cuenta de contraparte.</p>;
  return (
    <div className="space-y-2 mb-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-xs text-slate-500">Indicá a qué cuenta propia van (o de cuál vienen). Si esa cuenta no tiene extractos, dejan de ser sospechosas.</p>
        <button className="btn-primary text-xs py-1" disabled={busy || chosen.length === 0} onClick={apply}>Asignar {chosen.length} grupo(s)</button>
        {msg && <span className="text-xs text-emerald-600">{msg}</span>}
      </div>
      <div className="max-h-80 overflow-auto border border-slate-100 dark:border-slate-800 rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
            <tr>{['Descripción', 'Filas', 'Monto', 'Cuenta de contraparte'].map(h => <th key={h} className="px-2 py-2 text-left font-semibold text-gray-500 uppercase">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {groups.map(g => (
              <tr key={gid(g)}>
                <td className="px-2 py-1 max-w-[320px]" title={g.sample.join(' · ')}><span className="truncate block">{g.sign === 'positive' ? '＋ ' : '− '}{g.merchant}</span></td>
                <td className="px-2 py-1 text-right">{g.count}</td>
                <td className="px-2 py-1 font-mono text-right whitespace-nowrap">{fmtMoney(g.total_brl)}</td>
                <td className="px-2 py-1">
                  <select className="input text-xs py-0.5" value={choice[gid(g)] ?? ''} onChange={e => setChoice(c => ({ ...c, [gid(g)]: e.target.value }))}>
                    <option value="">—</option>
                    {accounts.filter(a => !g.accounts.includes(a.id) || g.accounts.length > 1).map(a => <option key={a.id} value={a.id}>{a.name}{a.has_statements ? '' : ' (sin extractos)'}</option>)}
                  </select>
                </td>
              </tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
