import { useEffect, useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { getEntities, getSummary, ExpEntity, Summary, SummaryBlock } from '../../api/expenses';
import KpiCard from '../ui/KpiCard';
import { categoryColor, fmtMoney, monthLabel } from '../../utils/expenses';

export default function SummaryTab() {
  const [entities, setEntities] = useState<ExpEntity[]>([]);
  const [filters, setFilters] = useState({ from: '', to: '', entity: '', country: '', currency: 'BRL' });
  const [data, setData] = useState<Summary | null>(null);
  const [nativeCur, setNativeCur] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { getEntities().then(setEntities).catch(() => {}); }, []);
  useEffect(() => {
    setLoading(true); setError('');
    const params: Record<string, string> = { currency: filters.currency };
    (['from', 'to', 'entity', 'country'] as const).forEach(k => { if (filters[k]) params[k] = filters[k]; });
    getSummary(params).then(d => {
      setData(d);
      if (d.by_currency) setNativeCur(c => (c && d.by_currency![c] ? c : Object.keys(d.by_currency!)[0] ?? ''));
    }).catch(() => setError('No se pudo cargar el resumen')).finally(() => setLoading(false));
  }, [filters]);

  const block: SummaryBlock | undefined = useMemo(() => (data?.by_currency
    ? data.by_currency[nativeCur]
    : data?.months ? { months: data.months, rows_without_fx: data.rows_without_fx ?? 0 } : undefined), [data, nativeCur]);
  const cur = filters.currency === 'native' ? nativeCur || 'BRL' : filters.currency;
  const months = useMemo(() => block?.months ?? [], [block]);
  const categories = useMemo(() => {
    const tot: Record<string, number> = {};
    months.forEach(m => Object.entries(m.by_category).forEach(([k, v]) => { tot[k] = (tot[k] ?? 0) + v; }));
    return Object.keys(tot).sort((a, b) => tot[b] - tot[a]);
  }, [months]);
  const chartData = months.map(m => ({ month: monthLabel(m.month), ...m.by_category }));
  // Mes de referencia de los KPIs: el último mes con extracto de TODAS las cuentas que tienen datos
  // (si no, un mes con una cuenta sin importar parecería un mes de poco gasto).
  const ref = useMemo(() => {
    const cov = (data?.coverage ?? []).filter(c => c.months.length > 0);
    const full = months.filter(m => cov.every(c => c.months.includes(m.month)));
    return full.length ? full[full.length - 1] : months[months.length - 1];
  }, [months, data]);
  const last = ref;
  const refIdx = ref ? months.findIndex(m => m.month === ref.month) : -1;
  const partial = !!ref && refIdx !== months.length - 1;
  const lastSix = months.slice(Math.max(0, refIdx - 5), refIdx + 1);
  const avg6 = lastSix.length ? lastSix.reduce((s, m) => s + m.expenses, 0) / lastSix.length : 0;
  const money = (v: number | null | undefined) => fmtMoney(v, cur);
  const set = (k: string, v: string) => setFilters(f => ({ ...f, [k]: v }));

  return (
    <div className="space-y-4">
      <div className="card p-3 flex flex-wrap gap-3 items-end">
        <Field label="Desde"><input type="month" className="input text-sm py-1.5" value={filters.from} onChange={e => set('from', e.target.value)} /></Field>
        <Field label="Hasta"><input type="month" className="input text-sm py-1.5" value={filters.to} onChange={e => set('to', e.target.value)} /></Field>
        <Field label="Entidad">
          <select className="input text-sm py-1.5" value={filters.entity} onChange={e => set('entity', e.target.value)}>
            <option value="">Todas</option>
            {entities.map(e => <option key={e.code} value={e.code}>{e.name}</option>)}
            <option value="sin_entidad">Sin entidad</option>
          </select>
        </Field>
        <Field label="País">
          <select className="input text-sm py-1.5" value={filters.country} onChange={e => set('country', e.target.value)}>
            <option value="">Todos</option><option value="BR">Brasil</option><option value="AR">Argentina</option>
          </select>
        </Field>
        <Field label="Moneda">
          <select className="input text-sm py-1.5" value={filters.currency} onChange={e => set('currency', e.target.value)}>
            <option value="BRL">BRL</option><option value="USD">USD</option><option value="native">Nativa</option>
          </select>
        </Field>
        {filters.currency === 'native' && data?.by_currency && (
          <Field label="Moneda nativa">
            <select className="input text-sm py-1.5" value={nativeCur} onChange={e => setNativeCur(e.target.value)}>
              {Object.keys(data.by_currency).map(c => <option key={c}>{c}</option>)}
            </select>
          </Field>
        )}
      </div>

      {error && <div className="card text-rose-500 text-sm">{error}</div>}

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KpiCard loading={loading} title={`Gasto ${last ? monthLabel(last.month) : ''}`} value={money(last?.expenses)}
          subtitle={partial ? 'último mes con todos los extractos' : undefined} />
        <KpiCard loading={loading} title="Promedio 6 meses" value={money(avg6)} />
        <KpiCard loading={loading} title="Ingresos" value={money(last?.income)} subtitle={last && last.proventos ? `+ proventos ${money(last.proventos)}` : undefined} />
        <KpiCard loading={loading} title="Ahorro" value={money(last?.savings)} />
        <KpiCard loading={loading} title="Pendiente de revisar" value={`${data?.pending_review_pct ?? 0}%`} subtitle="de los movimientos" />
      </div>

      {block && block.rows_without_fx > 0 && (
        <div className="card text-sm text-amber-600">⚠ {block.rows_without_fx} movimientos sin tipo de cambio quedaron fuera de los totales.</div>
      )}

      <div className="card">
        <h2 className="text-sm font-semibold mb-3">Gasto por categoría y mes</h2>
        {months.length === 0 && !loading ? (
          <p className="text-sm text-slate-400 py-8 text-center">Sin datos para el filtro elegido. Importá un extracto en la pestaña Importar.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#9ca3af' }} />
              <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} width={70}
                tickFormatter={(v: number) => (v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : String(v))} />
              <Tooltip formatter={(v, n) => [money(Number(v)), String(n)]} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
              <Legend iconSize={10} formatter={v => <span style={{ fontSize: 12, color: '#6b7280' }}>{v}</span>} />
              {categories.map(c => <Bar key={c} dataKey={c} stackId="a" fill={categoryColor(c, categories)} isAnimationActive={false} />)}
            </BarChart>
          </ResponsiveContainer>
        )}
        {categories.includes('Tarjeta sin detalle') && (
          <p className="text-xs text-slate-400 mt-2">
            "Tarjeta sin detalle" = pagos de tarjetas sin fatura importada: es un gasto estimado, sin categoría.
          </p>
        )}
      </div>

      {months.length > 0 && (
        <div className="card p-0 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Categoría</th>
                {months.map(m => <th key={m.month} className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{monthLabel(m.month)}</th>)}
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {categories.map(c => (
                <tr key={c}>
                  <td className="px-3 py-2 whitespace-nowrap"><span className="inline-block w-2.5 h-2.5 rounded-full mr-2" style={{ background: categoryColor(c, categories) }} />{c}</td>
                  {months.map(m => <td key={m.month} className="px-3 py-2 text-right font-mono">{m.by_category[c] ? money(m.by_category[c]) : '—'}</td>)}
                  <td className="px-3 py-2 text-right font-mono font-semibold">{money(months.reduce((s, m) => s + (m.by_category[c] ?? 0), 0))}</td>
                </tr>
              ))}
              <tr className="font-semibold bg-gray-50 dark:bg-gray-800/50">
                <td className="px-3 py-2">Total gasto</td>
                {months.map(m => <td key={m.month} className="px-3 py-2 text-right font-mono">{money(m.expenses)}</td>)}
                <td className="px-3 py-2 text-right font-mono">{money(months.reduce((s, m) => s + m.expenses, 0))}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {data && data.coverage.length > 0 && <Coverage coverage={data.coverage} />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex flex-col gap-1 min-w-[120px]"><label className="text-xs font-medium text-gray-500">{label}</label>{children}</div>;
}

function Coverage({ coverage }: { coverage: Summary['coverage'] }) {
  const all = [...new Set(coverage.flatMap(c => c.months))].sort();
  if (all.length === 0) return null;
  return (
    <div className="card overflow-x-auto">
      <h2 className="text-sm font-semibold mb-1">Cobertura de extractos</h2>
      <p className="text-xs text-slate-400 mb-3">Un mes sin extracto no es un mes sin gasto: sólo no hay datos.</p>
      <table className="text-xs">
        <thead><tr><th />{all.map(m => <th key={m} className="px-2 py-1 font-normal text-gray-500">{monthLabel(m)}</th>)}</tr></thead>
        <tbody>
          {coverage.map(c => (
            <tr key={c.account_id}>
              <td className="pr-3 py-1 whitespace-nowrap">{c.name}</td>
              {all.map(m => <td key={m} className="px-2 py-1 text-center">{c.months.includes(m) ? <span className="text-emerald-500">●</span> : <span className="text-slate-300">·</span>}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
