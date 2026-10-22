import { useEffect, useState } from 'react';
import { getInstallments, Installments } from '../../api/expenses';
import { fmtMoney, monthLabel } from '../../utils/expenses';

/** Cuotas ya comprometidas (n+1..N de la última fatura de cada tarjeta). Es un dato, no una proyección. */
export default function InstallmentsBlock() {
  const [data, setData] = useState<Installments | null>(null);
  useEffect(() => { getInstallments(6).then(setData).catch(() => setData(null)); }, []);
  if (!data || data.months.length === 0) return null;
  const cards = [...new Set(data.months.flatMap(m => Object.keys(m.by_card)))];
  const stale = data.cards.filter(c => c.stale);

  return (
    <div className="card space-y-2">
      <h2 className="text-sm font-semibold">Cuotas comprometidas</h2>
      <p className="text-xs text-slate-400">
        Desde la última fatura importada de cada tarjeta ({data.cards.map(c => `${c.name}: ${c.last_statement_due.slice(0, 7)}`).join(' · ')}).
        Importes en BRL al tipo de cambio de esa fatura (estimado).
      </p>
      {stale.length > 0 && <p className="text-xs text-amber-600">⚠ {stale.map(c => c.name).join(', ')}: la última fatura importada tiene más de 45 días; importá las nuevas para ver las cuotas vigentes.</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr><th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Mes</th>
              {cards.map(c => <th key={c} className="px-3 py-2 text-right text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{c}</th>)}
              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Total</th></tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {data.months.map(m => (
              <tr key={m.month} className="align-top">
                <td className="px-3 py-2 whitespace-nowrap">
                  <details><summary className="cursor-pointer">{monthLabel(m.month)}</summary>
                    <ul className="text-xs text-slate-500 mt-1 space-y-0.5">
                      {m.items.slice(0, 15).map((i, k) => <li key={k}>{i.merchant} · cuota {i.installment}/{i.of} · {fmtMoney(i.amount, i.currency, 2)}</li>)}
                      {m.items.length > 15 && <li>… y {m.items.length - 15} más</li>}
                    </ul></details>
                </td>
                {cards.map(c => <td key={c} className="px-3 py-2 text-right font-mono">{m.by_card[c] ? fmtMoney(m.by_card[c]) : '—'}</td>)}
                <td className="px-3 py-2 text-right font-mono font-semibold">{fmtMoney(m.total_brl)}</td>
              </tr>))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
