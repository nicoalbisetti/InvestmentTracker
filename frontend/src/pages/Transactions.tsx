import { useEffect, useState } from 'react';
import { getTransactions, createTransaction, deleteTransaction } from '../api/transactions';
import { getInstruments } from '../api/instruments';
import Modal from '../components/ui/Modal';
import { fmtBRL, fmtDate } from '../utils/formatters';

const TYPE_OPTIONS = [
  { value: 'aplicacion', label: 'Aplicación' },
  { value: 'rescate', label: 'Rescate' },
  { value: 'provento', label: 'Provento' },
  { value: 'outro', label: 'Otro' },
];

const TYPE_COLORS: Record<string, string> = {
  aplicacion: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  rescate: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  provento: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  outro: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
};

export default function Transactions() {
  const [data, setData] = useState<any>({ items: [], total: 0, pages: 1 });
  const [instruments, setInstruments] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ instrument_id: '', date: '', type: 'aplicacion', amount_brl: '', amount_usd: '', notes: '' });
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    getTransactions({ page, limit: 50 }).then(setData).finally(() => setLoading(false));
  };

  useEffect(() => {
    getInstruments({ limit: 200 }).then((r: any) => setInstruments(r.items));
  }, []);

  useEffect(() => { load(); }, [page]);

  const handleSave = async () => {
    if (!form.instrument_id || !form.date || !form.amount_brl) return;
    setSaving(true);
    try {
      await createTransaction({
        instrument_id: Number(form.instrument_id),
        date: form.date,
        type: form.type,
        amount_brl: Number(form.amount_brl),
        amount_usd: form.amount_usd ? Number(form.amount_usd) : undefined,
        notes: form.notes || undefined,
      });
      setShowModal(false);
      setForm({ instrument_id: '', date: '', type: 'aplicacion', amount_brl: '', amount_usd: '', notes: '' });
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('¿Eliminar esta transacción?')) return;
    await deleteTransaction(id);
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">{data.total} transacciones</p>
        <button className="btn-primary" onClick={() => setShowModal(true)}>+ Nueva Transacción</button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              {['Fecha', 'Instrumento', 'Custodio', 'Tipo', 'Monto BRL', 'Monto USD', 'Notas', ''].map(h => (
                <th key={h} className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {loading ? (
              [...Array(8)].map((_, i) => (
                <tr key={i}>
                  {[...Array(8)].map((_, j) => (
                    <td key={j} className="px-3 py-3">
                      <div className="animate-pulse bg-gray-200 dark:bg-gray-700 h-4 rounded" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.items.length === 0 ? (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-400">No hay transacciones registradas</td></tr>
            ) : (
              data.items.map((t: any) => (
                <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="px-3 py-2.5 whitespace-nowrap">{fmtDate(t.date)}</td>
                  <td className="px-3 py-2.5 max-w-[160px] truncate font-medium" title={t.instrument_name}>{t.instrument_name}</td>
                  <td className="px-3 py-2.5 text-gray-500">{t.instrument_custodian}</td>
                  <td className="px-3 py-2.5">
                    <span className={`badge ${TYPE_COLORS[t.type] || TYPE_COLORS.outro}`}>
                      {TYPE_OPTIONS.find(o => o.value === t.type)?.label || t.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 font-mono">{fmtBRL(t.amount_brl)}</td>
                  <td className="px-3 py-2.5 font-mono text-gray-500">{t.amount_usd ? `US$ ${t.amount_usd?.toLocaleString()}` : '—'}</td>
                  <td className="px-3 py-2.5 text-gray-500 max-w-[140px] truncate" title={t.notes}>{t.notes || '—'}</td>
                  <td className="px-3 py-2.5">
                    <button onClick={() => handleDelete(t.id)} className="text-red-400 hover:text-red-600 text-xs">Eliminar</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {data.pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-500">Página {page} de {data.pages} ({data.total} registros)</p>
            <div className="flex gap-2">
              <button className="btn-secondary text-sm py-1" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Anterior</button>
              <button className="btn-secondary text-sm py-1" disabled={page >= data.pages} onClick={() => setPage(p => p + 1)}>Siguiente →</button>
            </div>
          </div>
        )}
      </div>

      {/* New Transaction Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="Nueva Transacción" size="md">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Instrumento *</label>
            <select className="input" value={form.instrument_id} onChange={e => setForm(f => ({ ...f, instrument_id: e.target.value }))}>
              <option value="">Seleccionar...</option>
              {instruments.map((i: any) => (
                <option key={i.id} value={i.id}>{i.name} ({i.custodian})</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Fecha *</label>
              <input type="date" className="input" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tipo *</label>
              <select className="input" value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))}>
                {TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Monto BRL *</label>
              <input type="number" className="input" placeholder="0.00" value={form.amount_brl} onChange={e => setForm(f => ({ ...f, amount_brl: e.target.value }))} />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Monto USD (opcional)</label>
              <input type="number" className="input" placeholder="0.00" value={form.amount_usd} onChange={e => setForm(f => ({ ...f, amount_usd: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Notas</label>
            <textarea className="input resize-none" rows={2} value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
          </div>
          <div className="flex gap-3 pt-2">
            <button className="btn-secondary flex-1" onClick={() => setShowModal(false)}>Cancelar</button>
            <button className="btn-primary flex-1" onClick={handleSave} disabled={saving}>
              {saving ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
