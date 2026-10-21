import { ReactNode, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Audit, confirmLink, confirmPair, getAudit, getLinkSuggestions, getReviewQueueTyped, LinkSuggestion, QueueItem,
  rebuildLinks, rejectLink, ReviewQueue,
} from '../../api/expenses';
import { fmtDate } from '../../utils/formatters';
import { fmtMoney } from '../../utils/expenses';

function Section({ title, count, hint, children, open = false }: { title: string; count: number; hint?: string; children: ReactNode; open?: boolean }) {
  return (
    <details className="card p-0" open={open && count > 0}>
      <summary className="px-4 py-3 cursor-pointer flex items-center gap-3 text-sm font-semibold">
        <span>{title}</span>
        <span className={`badge ${count ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>{count}</span>
        {hint && <span className="text-xs font-normal text-slate-400">{hint}</span>}
      </summary>
      <div className="px-4 pb-4 overflow-x-auto">{count === 0 ? <p className="text-sm text-slate-400">Nada para revisar</p> : children}</div>
    </details>
  );
}

function ItemsTable({ items }: { items: QueueItem[] }) {
  return (
    <table className="w-full text-xs">
      <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
        {items.slice(0, 100).map(i => (
          <tr key={i.id}>
            <td className="py-1.5 pr-3 whitespace-nowrap">{fmtDate(i.date)}</td>
            <td className="py-1.5 pr-3 max-w-[420px] truncate" title={i.description}>{i.description}</td>
            <td className={`py-1.5 pr-3 font-mono text-right whitespace-nowrap ${i.amount < 0 ? 'negative' : 'positive'}`}>{fmtMoney(i.amount, i.currency, 2)}</td>
          </tr>
        ))}
        {items.length > 100 && <tr><td colSpan={3} className="py-1.5 text-slate-400">… y {items.length - 100} más</td></tr>}
      </tbody>
    </table>
  );
}

export default function ReviewTab() {
  const [q, setQ] = useState<ReviewQueue | null>(null);
  const [sugg, setSugg] = useState<LinkSuggestion[]>([]);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [range, setRange] = useState({ from: '', to: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = useCallback(() => {
    getReviewQueueTyped().then(setQ).catch(() => setMsg('No se pudo cargar la cola'));
    getLinkSuggestions().then(setSugg).catch(() => {});
  }, []);
  useEffect(load, [load]);

  const search = async () => {
    setBusy(true); setMsg('');
    try {
      const r = await rebuildLinks();
      setMsg(`Vínculos sugeridos: ${r.investments ?? 0} de inversiones, ${r.proventos ?? 0} de proventos. Pares nuevos: ${r.pairs ?? 0}.`);
      load();
    } catch { setMsg('No se pudieron buscar vínculos'); } finally { setBusy(false); }
  };
  const act = async (fn: () => Promise<unknown>) => { await fn(); load(); };

  if (!q) return <p className="text-sm text-slate-400">{msg || 'Cargando…'}</p>;
  const investSugg = sugg.filter(s => s.link_type === 'investment');
  const provSugg = sugg.filter(s => s.link_type === 'provento');

  return (
    <div className="space-y-3">
      <div className="card flex flex-wrap items-center gap-3">
        <button className="btn-primary" disabled={busy} onClick={search}>{busy ? 'Buscando…' : 'Buscar vínculos con inversiones'}</button>
        <span className="text-xs text-slate-400">Sólo sugiere: nada se confirma solo ni se modifica en Inversiones.</span>
        {msg && <span className="text-sm text-emerald-600">{msg}</span>}
      </div>

      <Section title="Sin clasificar" count={q.unclassified.length} open hint="se resuelven en Movimientos (con 'crear regla')">
        <p className="text-sm mb-2"><Link className="text-indigo-500 underline" to="/gastos?tab=movimientos&pending=1">Ver en Movimientos →</Link></p>
        <ItemsTable items={q.unclassified} />
      </Section>

      <Section title="Pares de transferencias sugeridos" count={q.pair_suggestions.length} open hint="mismo importe, otra cuenta, a más de 1 día o ambiguos">
        <table className="w-full text-xs"><tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {q.pair_suggestions.map(p => (
            <tr key={`${p.out_id}-${p.in_id}`}>
              <td className="py-1.5 pr-3">{fmtDate(p.out.date)} → {fmtDate(p.in.date)}</td>
              <td className="py-1.5 pr-3 max-w-[300px] truncate">{p.out.description}</td>
              <td className="py-1.5 pr-3 font-mono whitespace-nowrap">{fmtMoney(p.amount, p.out.currency, 2)}</td>
              <td className="py-1.5 text-slate-400">{p.days} día(s)</td>
              <td className="py-1.5"><button className="text-emerald-600 text-xs" onClick={() => act(() => confirmPair(p.out_id, p.in_id))}>Vincular</button></td>
            </tr>))}
        </tbody></table>
      </Section>

      <Section title="Transferencias propias sin par" count={q.unpaired_transfers.length} hint="hay otra cuenta importada que cubre la fecha">
        <ItemsTable items={q.unpaired_transfers} />
      </Section>
      <Section title="Transferencias propias con contraparte no importada" count={q.unpaired_transfers_counterparty_not_imported.length} hint="informativo">
        <ItemsTable items={q.unpaired_transfers_counterparty_not_imported} />
      </Section>

      <Section title="Pagos de tarjeta sin fatura" count={q.card_payments_without_statement.length} open hint="se cuentan como 'Tarjeta sin detalle' hasta importar la fatura">
        <ItemsTable items={q.card_payments_without_statement} />
      </Section>
      <Section title="Pagos de tarjeta con monto distinto al de la fatura" count={q.card_payments_inexact.length} hint="pagos parciales, cargos o dólares con TC: cubiertos, pero verificá">
        <ItemsTable items={q.card_payments_inexact} />
      </Section>

      <LinkGroup title="Aportes y rescates: vínculos sugeridos" groups={investSugg} onConfirm={id => act(() => confirmLink(id))} onReject={id => act(() => rejectLink(id))} />
      <Section title="Aportes y rescates sin vincular" count={q.investments_unlinked.length} hint="p. ej. compras de cripto que no están en Inversiones">
        <ItemsTable items={q.investments_unlinked} />
      </Section>
      <LinkGroup title="Proventos: vínculos sugeridos" groups={provSugg} onConfirm={id => act(() => confirmLink(id))} onReject={id => act(() => rejectLink(id))} />
      <Section title="Proventos cobrados sin vincular" count={q.proventos_unlinked.length}>
        <ItemsTable items={q.proventos_unlinked} />
      </Section>

      <Section title="Signo inconsistente con el tipo" count={q.sign_inconsistent.length}><ItemsTable items={q.sign_inconsistent} /></Section>
      <Section title="Sin tipo de cambio" count={q.fx_missing.length} hint="cargalo a mano por API y recalculá"><ItemsTable items={q.fx_missing} /></Section>
      <Section title="Tipo de cambio estimado" count={q.fx_estimated.length}><ItemsTable items={q.fx_estimated} /></Section>

      <div className="card space-y-3">
        <h2 className="text-sm font-semibold">Auditoría de inversiones (sólo lectura)</h2>
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Desde</label><input type="date" className="input text-sm py-1.5" value={range.from} onChange={e => setRange(r => ({ ...r, from: e.target.value }))} /></div>
          <div className="flex flex-col gap-1"><label className="text-xs text-gray-500">Hasta</label><input type="date" className="input text-sm py-1.5" value={range.to} onChange={e => setRange(r => ({ ...r, to: e.target.value }))} /></div>
          <button className="btn-secondary" onClick={() => getAudit(range.from, range.to).then(setAudit)}>Auditar</button>
        </div>
        {audit && (
          <div className="space-y-3 text-xs">
            <AuditBlock title="Movimientos bancarios sin Transaction vinculada" rows={audit.bank_movements_without_transaction.map(r => [fmtDate(r.date), r.description, fmtMoney(r.amount, 'BRL', 2)])} />
            <AuditBlock title="Transactions de custodias importadas sin movimiento bancario" rows={audit.transactions_without_bank_movement.map(r => [fmtDate(r.date), `${r.instrument ?? ''} (${r.type}, ${r.custodian ?? ''})`, fmtMoney(r.amount_brl, 'BRL', 2)])} />
            <AuditBlock title="Diferencias en vínculos confirmados" rows={audit.confirmed_link_differences.map(r => [fmtDate(r.date), `banco ${fmtMoney(r.bank_amount, 'BRL', 2)} vs vinculado ${fmtMoney(r.linked_amount, 'BRL', 2)} · ${r.max_days_apart} día(s)`, fmtMoney(r.difference, 'BRL', 2)])} />
            <AuditBlock title="Vínculos cuyo destino cambió" rows={audit.drifted_links.map(r => [String(r.link_id), `${r.label ?? ''}: ${r.reason}`, ''])} />
          </div>
        )}
      </div>
    </div>
  );
}

function AuditBlock({ title, rows }: { title: string; rows: string[][] }) {
  return (
    <div>
      <p className="font-semibold mb-1">{title} <span className="badge bg-slate-100 text-slate-600">{rows.length}</span></p>
      {rows.length > 0 && (
        <div className="max-h-64 overflow-auto"><table className="w-full"><tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {rows.slice(0, 200).map((r, i) => <tr key={i}><td className="py-1 pr-3 whitespace-nowrap">{r[0]}</td><td className="py-1 pr-3">{r[1]}</td><td className="py-1 text-right font-mono whitespace-nowrap">{r[2]}</td></tr>)}
        </tbody></table></div>
      )}
    </div>
  );
}

function LinkGroup({ title, groups, onConfirm, onReject }: { title: string; groups: LinkSuggestion[]; onConfirm: (id: number) => void; onReject: (id: number) => void }) {
  return (
    <Section title={title} count={groups.length} open hint="sugeridos: confirmá o rechazá cada uno">
      <div className="space-y-3">
        {groups.map(g => (
          <div key={g.exp_transaction.id} className="border border-slate-100 dark:border-slate-800 rounded-lg p-2 text-xs">
            <div className="flex flex-wrap justify-between gap-2">
              <span>{fmtDate(g.exp_transaction.date)} · {g.exp_transaction.description}</span>
              <span className="font-mono">{fmtMoney(g.exp_transaction.amount, g.exp_transaction.currency, 2)}</span>
            </div>
            {Math.abs(g.difference_brl) > 0.5 && <p className="text-amber-600">Diferencia vinculado − banco: {fmtMoney(g.difference_brl, 'BRL', 2)}</p>}
            {g.links.map(l => (
              <div key={l.id} className="flex flex-wrap items-center gap-3 mt-1 pl-3">
                <span>↳ {l.label ?? `#${l.target_id}`} · {fmtDate(l.date)}</span>
                <span className="font-mono">{fmtMoney(l.amount, 'BRL', 2)}</span>
                <span className="text-slate-400">score {l.score}</span>
                <button className="text-emerald-600" onClick={() => onConfirm(l.id)}>Confirmar</button>
                <button className="text-rose-500" onClick={() => onReject(l.id)}>Rechazar</button>
              </div>))}
          </div>))}
      </div>
    </Section>
  );
}
